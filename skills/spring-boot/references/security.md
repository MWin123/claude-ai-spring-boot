# Security - Spring Security 7

Bearer tokens go through Spring Security's resource server: `spring-boot-starter-security-oauth2-resource-server` (Spring Security plus Nimbus JOSE + JWT, no Jackson 2), and `spring-boot-starter-security-oauth2-resource-server-test` for tests. The app issues its own tokens below; with Keycloak, Auth0 or another OAuth2 server see "Tokens from an External Issuer".

## Security Configuration

```java
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http, UserDetailsService users) throws Exception {
        http
            .csrf(csrf -> csrf
                // XSRF-TOKEN cookie, issued eagerly; accepts the raw value in X-XSRF-TOKEN (SPAs, Swagger UI).
                // Requests with a bearer token skip it (oauth2ResourceServer): browsers never attach one by themselves
                .spa()
                .ignoringRequestMatchers("/api/auth/**")
            )
            .cors(cors -> cors.configurationSource(corsConfigurationSource()))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/auth/**", "/actuator/health").permitAll()
                // OpenAPI spec file and Swagger UI (springdoc, see web.md)
                .requestMatchers("/openapi.yaml", "/v3/api-docs/swagger-config", "/swagger-ui/**", "/swagger-ui.html").permitAll()
                .requestMatchers("/api/v1/admin/**").hasRole("ADMIN")
                .requestMatchers(HttpMethod.POST, "/api/v1/products/**").hasRole("ADMIN")
                .requestMatchers("/api/v1/users/**").hasAnyRole("USER", "ADMIN")
                .anyRequest().authenticated()
            )
            .sessionManagement(session -> session
                .sessionCreationPolicy(SessionCreationPolicy.STATELESS)
            )
            // Missing, malformed or expired token: 401 with WWW-Authenticate; missing role: 403
            .oauth2ResourceServer(oauth2 -> oauth2
                .jwt(jwt -> jwt.jwtAuthenticationConverter(token -> authenticate(users, token)))
            );

        return http.build();
    }

    // A valid access token becomes the app's user: a deleted (UsernameNotFoundException), disabled or
    // locked account gets 401 on its next request, and roles come from the database instead of a claim
    private static AbstractAuthenticationToken authenticate(UserDetailsService users, Jwt token) {
        UserDetails user = users.loadUserByUsername(token.getSubject());
        new AccountStatusUserDetailsChecker().check(user);
        return UsernamePasswordAuthenticationToken.authenticated(user, token, user.getAuthorities());
    }

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration configuration = new CorsConfiguration();
        configuration.setAllowedOrigins(List.of("http://localhost:3000"));
        configuration.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE", "OPTIONS"));
        configuration.setAllowedHeaders(List.of("*"));
        configuration.setAllowCredentials(true);
        configuration.setMaxAge(3600L);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", configuration);
        return source;
    }

    @Bean
    public AuthenticationManager authenticationManager(
            AuthenticationConfiguration config) throws Exception {
        return config.getAuthenticationManager();
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder(12);
    }
}
```

## JWT Configuration

One HMAC key signs and verifies both token types; a `token_type` claim keeps refresh tokens out of API calls.

```yaml
app:
  jwt:
    secret: ${JWT_SECRET}   # Base64, at least 256 bits: openssl rand -base64 32
    access-token-ttl: 15m
    refresh-token-ttl: 7d
```

`@SpringBootTest`s load `JwtConfig` too, so give the `testcontainers` profile (`testing-patterns`) its own throwaway `app.jwt.secret` from `openssl rand -base64 32`; slice tests mock `JwtDecoder` instead.

```java
@ConfigurationProperties("app.jwt")
public record JwtProperties(String secret, Duration accessTokenTtl, Duration refreshTokenTtl) {}

@Configuration
@EnableConfigurationProperties(JwtProperties.class)
public class JwtConfig {
    static final String TOKEN_TYPE = "token_type";

    @Bean
    public SecretKey jwtKey(JwtProperties properties) {
        return new SecretKeySpec(Base64.getDecoder().decode(properties.secret()), "HmacSHA256");
    }

    @Bean
    public JwtEncoder jwtEncoder(SecretKey jwtKey) {
        return NimbusJwtEncoder.withSecretKey(jwtKey).build();
    }

    @Bean   // used by oauth2ResourceServer: API calls accept access tokens only
    public JwtDecoder jwtDecoder(SecretKey jwtKey) {
        return decoder(jwtKey, "access");
    }

    static JwtDecoder decoder(SecretKey key, String tokenType) {
        NimbusJwtDecoder decoder = NimbusJwtDecoder.withSecretKey(key).macAlgorithm(MacAlgorithm.HS256).build();
        decoder.setJwtValidator(new DelegatingOAuth2TokenValidator<>(
            JwtValidators.createDefault(),   // expiry
            new JwtClaimValidator<String>(TOKEN_TYPE, tokenType::equals)));
        return decoder;
    }
}
```

## Token Service

```java
@Service
public class TokenService {
    private final JwtEncoder encoder;
    private final JwtDecoder refreshDecoder;
    private final JwtProperties properties;

    public TokenService(JwtEncoder encoder, SecretKey jwtKey, JwtProperties properties) {
        this.encoder = encoder;
        this.refreshDecoder = JwtConfig.decoder(jwtKey, "refresh");   // not a bean: the API must not accept refresh tokens
        this.properties = properties;
    }

    public String accessToken(String username) {
        return encode(username, "access", properties.accessTokenTtl());
    }

    public String refreshToken(String username) {
        return encode(username, "refresh", properties.refreshTokenTtl());
    }

    /** The username of a valid refresh token; throws JwtException for anything else, access tokens included. */
    public String refreshTokenSubject(String token) {
        return refreshDecoder.decode(token).getSubject();
    }

    private String encode(String username, String tokenType, Duration ttl) {
        Instant now = Instant.now();
        JwtClaimsSet claims = JwtClaimsSet.builder()
            .subject(username)
            .issuedAt(now)
            .expiresAt(now.plus(ttl))
            .claim(JwtConfig.TOKEN_TYPE, tokenType)
            .build();
        return encoder.encode(JwtEncoderParameters.from(JwsHeader.with(MacAlgorithm.HS256).build(), claims))
            .getTokenValue();
    }
}
```

## UserDetailsService Implementation

```java
@Service
@RequiredArgsConstructor
public class CustomUserDetailsService implements UserDetailsService {
    private final UserRepository userRepository;

    @Override
    @Transactional(readOnly = true)
    public UserDetails loadUserByUsername(String username) throws UsernameNotFoundException {
        User user = userRepository.findByEmailWithRoles(username)
            .orElseThrow(() -> new UsernameNotFoundException(
                "User not found with email: " + username));

        return org.springframework.security.core.userdetails.User
            .builder()
            .username(user.getEmail())
            .password(user.getPassword())
            .authorities(user.getRoles().stream()
                .map(role -> new SimpleGrantedAuthority("ROLE_" + role.getName()))
                .toList())
            .accountExpired(false)
            .accountLocked(!user.getActive())
            .credentialsExpired(false)
            .disabled(!user.getActive())
            .build();
    }
}
```

## Authentication Controller

The auth endpoints are part of the contract-first spec (see "Contract-First REST API" in `web.md`). The spec marks the public operations with `security: []` and holds the request and response models:

```yaml
# openapi.yaml (excerpt): register, login and refresh opt out of the global bearerAuth
/api/auth/register:
  post:
    tags: [Auth]
    operationId: register
    security: []
    requestBody: { required: true, content: { application/json: { schema: { $ref: '#/components/schemas/RegisterRequest' } } } }
    responses:
      '201': { description: Registered, content: { application/json: { schema: { $ref: '#/components/schemas/AuthenticationResponse' } } } }
      '409': { $ref: '#/components/responses/Conflict' }
/api/auth/login:
  post:
    tags: [Auth]
    operationId: login
    security: []
    requestBody: { required: true, content: { application/json: { schema: { $ref: '#/components/schemas/LoginRequest' } } } }
    responses:
      '200': { description: Logged in, content: { application/json: { schema: { $ref: '#/components/schemas/AuthenticationResponse' } } } }
      '401': { $ref: '#/components/responses/Unauthorized' }
/api/auth/refresh:
  post:
    tags: [Auth]
    operationId: refreshToken
    security: []
    requestBody: { required: true, content: { application/json: { schema: { $ref: '#/components/schemas/RefreshTokenRequest' } } } }
    responses:
      '200': { description: New access token, content: { application/json: { schema: { $ref: '#/components/schemas/AuthenticationResponse' } } } }
      '401': { $ref: '#/components/responses/Unauthorized' }
# components.schemas: RegisterRequest (email, password, username), LoginRequest (email, password),
# RefreshTokenRequest (refreshToken), AuthenticationResponse (required: [accessToken, refreshToken])
```

```java
@RestController
@RequiredArgsConstructor
public class AuthenticationController implements AuthApi {   // generated from the Auth tag
    private final AuthenticationService authenticationService;

    @Override
    public ResponseEntity<AuthenticationResponse> register(RegisterRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED).body(authenticationService.register(request));
    }

    @Override
    public ResponseEntity<AuthenticationResponse> login(LoginRequest request) {
        return ResponseEntity.ok(authenticationService.login(request));
    }

    @Override
    public ResponseEntity<AuthenticationResponse> refreshToken(RefreshTokenRequest request) {
        return ResponseEntity.ok(authenticationService.refreshToken(request));
    }
}
```

There is no logout endpoint: a signed token stays valid until it expires, so the client discards its tokens. Deactivating the account stops both token types at once, since `SecurityConfig` and `refreshToken` check it.

## Authentication Service

```java
@Service
@Transactional
@RequiredArgsConstructor
public class AuthenticationService {
    private final UserRepository userRepository;
    private final RoleRepository roleRepository;
    private final PasswordEncoder passwordEncoder;
    private final TokenService tokenService;
    private final AuthenticationManager authenticationManager;
    private final UserDetailsService userDetailsService;
    private final UserDetailsChecker accountChecker = new AccountStatusUserDetailsChecker();

    public AuthenticationResponse register(RegisterRequest request) {
        if (userRepository.existsByEmail(request.getEmail())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Email already registered");   // a 409 Problem Detail
        }

        User user = User.builder()
            .email(request.getEmail())
            .password(passwordEncoder.encode(request.getPassword()))
            .username(request.getUsername())
            .build();
        // Load the persisted role: a new Role() would be transient and fail at flush
        Role userRole = roleRepository.findByName("USER")
            .orElseThrow(() -> new IllegalStateException("Role USER is not seeded"));
        user.getRoles().add(userRole);
        userRepository.save(user);

        return tokensFor(user.getEmail());
    }

    public AuthenticationResponse login(LoginRequest request) {
        // Wrong password, disabled or locked account: AuthenticationException, answered with 401
        Authentication authentication = authenticationManager.authenticate(
            UsernamePasswordAuthenticationToken.unauthenticated(request.getEmail(), request.getPassword()));
        return tokensFor(authentication.getName());
    }

    @Transactional(readOnly = true)
    public AuthenticationResponse refreshToken(RefreshTokenRequest request) {
        String username;
        try {
            username = tokenService.refreshTokenSubject(request.getRefreshToken());
        } catch (JwtException e) {   // bad signature, expired, or an access token
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid refresh token");
        }
        // A user deactivated since login gets no new access token
        accountChecker.check(userDetailsService.loadUserByUsername(username));
        return new AuthenticationResponse(tokenService.accessToken(username), request.getRefreshToken());
    }

    private AuthenticationResponse tokensFor(String username) {
        return new AuthenticationResponse(tokenService.accessToken(username), tokenService.refreshToken(username));
    }
}
```

## Method Security

`@EnableMethodSecurity` turns on `@PreAuthorize`/`@PostAuthorize`; ownership checks go through a bean, since the principal (`UserDetails`) has no id:

```java
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class UserService {
    private final UserRepository userRepository;

    @PreAuthorize("hasRole('ADMIN')")
    public List<User> getAllUsers() {
        return userRepository.findAll();
    }

    @PreAuthorize("hasRole('ADMIN') or @userAccess.isSelf(#userId, authentication.name)")
    public User getUserById(Long userId) {
        return userRepository.findById(userId)
            .orElseThrow(() -> new ResourceNotFoundException("User not found"));
    }

    // Checked before the write: a @PostAuthorize denial comes after save() and, without a rollback, keeps the change
    @Transactional
    @PreAuthorize("hasRole('ADMIN') or @userAccess.isSelf(#userId, authentication.name)")
    public User updateProfile(Long userId, UserUpdateRequest request) {
        User user = userRepository.findById(userId)   // not getUserById(): a self-call skips its @PreAuthorize
            .orElseThrow(() -> new ResourceNotFoundException("User not found"));
        user.setUsername(request.getUsername());
        return userRepository.save(user);
    }

    @Transactional
    @PreAuthorize("hasAnyRole('ADMIN', 'MANAGER')")   // @Secured is ignored unless @EnableMethodSecurity(securedEnabled = true)
    public void deleteUser(Long userId) {
        userRepository.deleteById(userId);
    }
}

@Component("userAccess")
@RequiredArgsConstructor
public class UserAccess {
    private final UserRepository userRepository;

    // The username is the email (CustomUserDetailsService)
    public boolean isSelf(Long userId, String username) {
        return userRepository.findById(userId)
            .map(user -> user.getEmail().equals(username))
            .orElse(false);
    }
}
```

## Tokens from an External Issuer

When Keycloak, Auth0 or another OAuth2 server issues the tokens, the app only validates them. Drop `JwtConfig`, `TokenService`, `authenticate` and the auth endpoints, keep the filter chain with `.jwt(Customizer.withDefaults())`, and let Boot build the decoder and map the roles claim:

```yaml
spring:
  security:
    oauth2:
      resourceserver:
        jwt:
          issuer-uri: ${JWT_ISSUER_URI}   # e.g. https://auth.example.com/realms/app; keys are fetched on the first request, not at startup
          authorities-claim-name: roles   # ["ADMIN"] -> ROLE_ADMIN, so hasRole() works unchanged
          authority-prefix: ROLE_
```

## SSL Bundles & Certificate Hot Reload

Spring Boot provides unified SSL configuration (since 3.1, available in 4.x) via SSL Bundles, with automatic reload when certificates change on disk.

### PEM-based SSL Bundle (e.g., cert-manager on Kubernetes)

```yaml
# application.yml
spring:
  ssl:
    bundle:
      pem:
        server:
          reload-on-update: true
          keystore:
            certificate: /etc/tls/tls.crt
            private-key: /etc/tls/tls.key
          truststore:
            certificate: /etc/tls/ca.crt

server:
  port: 8443
  ssl:
    bundle: server
```

### Applying SSL Bundles to RestClient

```java
@Configuration
public class RestClientSslConfig {

    @Bean
    public RestClient secureRestClient(RestClient.Builder builder, RestClientSsl ssl) {
        return builder
            .baseUrl("https://internal-service")
            .apply(ssl.fromBundle("server"))   // org.springframework.boot.restclient.autoconfigure.RestClientSsl
            .build();
    }
}
```

### JKS-based SSL Bundle

```yaml
spring:
  ssl:
    bundle:
      jks:
        server:
          reload-on-update: true
          keystore:
            location: classpath:keystore.p12
            # credentials: configure via environment variables
            type: PKCS12
```

When `reload-on-update: true` is set, Spring Boot watches the certificate files and automatically reloads the SSL context when they change — no application restart required. This works seamlessly with Kubernetes cert-manager, which writes renewed certificates to the mounted Secret volume.

## Quick Reference

| Annotation | Purpose |
|------------|---------|
| `@EnableWebSecurity` | Enables Spring Security |
| `@EnableMethodSecurity` | Enables method-level security annotations |
| `@PreAuthorize` | Checks authorization before method execution |
| `@PostAuthorize` | Checks the return value after execution; on a write, only `@Transactional` rolls a denial back |
| `@WithMockUser` | Mock authenticated user in tests |
| `@AuthenticationPrincipal` | Inject current user in controller |

## Hardening Checklist

What a secure app needs; `code-reviewer` flags anything missing.

- **Input validation**: constraints live in `openapi.yaml` (the generated interfaces carry `@Valid`); validate path variables and query params too; never trust client-side validation alone
- **Authentication & authorization**: `SecurityFilterChain` bean; stateless sessions for REST APIs; OAuth2 Resource Server for bearer tokens (no hand-written JWT filter), with refresh tokens rejected by the API (`token_type`); `@EnableMethodSecurity` with `@PreAuthorize`; only health, docs and auth endpoints permitted without authentication; BCrypt (strength 12+) for passwords; token refresh; session timeout for session-based apps
- **Injection**: parameterized `@Query` and native queries (`@Param`); no string concatenation in `@Query`, `EntityManager.createQuery()` or JDBC
- **Secrets**: credentials, JWT keys and API keys from environment variables or mounted files (Config Tree on Kubernetes), bound with `@ConfigurationProperties`; never in `application.yml` or Git
- **TLS**: HTTPS in production; SSL Bundles (`spring.ssl.bundle.*`) for the server, `RestClient` and data sources, with `reload-on-update: true` for rotation (cert-manager on Kubernetes)
- **CORS & CSRF**: explicit allowed origins (never `*` in production); CSRF disabled only for stateless REST APIs, enabled for session-based apps
- **Headers**: Spring Security's defaults (Content-Security-Policy, X-Content-Type-Options, X-Frame-Options, Strict-Transport-Security) stay enabled
- **Error responses**: Problem Details without stack traces or internal details; generic messages for 5xx
- **Rate limiting**: auth endpoints behind `@RateLimiter` (Resilience4j); API-level limits via Spring Cloud Gateway or Bucket4j
- **Dependencies**: latest stable versions; scan for CVEs with the OWASP dependency-check plugin (`./mvnw dependency-check:check`, Gradle: `./gradlew dependencyCheckAnalyze` with `org.owasp.dependencycheck`)
- **Audit trail**: log security events (logins, failures, access denied) without secrets or tokens
