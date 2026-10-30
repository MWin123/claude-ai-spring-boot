# Security - Spring Security 7

## Security Configuration

```java
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
            .csrf(csrf -> csrf
                // XSRF-TOKEN cookie, issued eagerly; accepts the raw value in X-XSRF-TOKEN (SPAs, Swagger UI)
                .spa()
                .ignoringRequestMatchers("/api/auth/**")
            )
            .cors(cors -> cors.configurationSource(corsConfigurationSource()))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/auth/**", "/actuator/health").permitAll()
                // OpenAPI spec file and Swagger UI (springdoc, see web.md)
                .requestMatchers("/openapi.yaml", "/v3/api-docs/swagger-config", "/swagger-ui/**", "/swagger-ui.html").permitAll()
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                .requestMatchers("/api/users/**").hasAnyRole("USER", "ADMIN")
                .anyRequest().authenticated()
            )
            .sessionManagement(session -> session
                .sessionCreationPolicy(SessionCreationPolicy.STATELESS)
            )
            .exceptionHandling(ex -> ex
                .authenticationEntryPoint(authenticationEntryPoint())
                .accessDeniedHandler(accessDeniedHandler())
            )
            .addFilterBefore(jwtAuthenticationFilter(),
                           UsernamePasswordAuthenticationFilter.class);

        return http.build();
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

## JWT Authentication Filter

```java
@Component
@Slf4j
@RequiredArgsConstructor
public class JwtAuthenticationFilter extends OncePerRequestFilter {
    private final JwtService jwtService;
    private final UserDetailsService userDetailsService;

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain) throws ServletException, IOException {

        final String authHeader = request.getHeader("Authorization");
        final String jwt;
        final String username;

        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            filterChain.doFilter(request, response);
            return;
        }

        jwt = authHeader.substring(7);

        try {
            username = jwtService.extractUsername(jwt);

            if (username != null && SecurityContextHolder.getContext()
                    .getAuthentication() == null) {
                UserDetails userDetails = userDetailsService.loadUserByUsername(username);

                if (jwtService.isTokenValid(jwt, userDetails)) {
                    UsernamePasswordAuthenticationToken authToken =
                        new UsernamePasswordAuthenticationToken(
                            userDetails,
                            null,
                            userDetails.getAuthorities()
                        );

                    authToken.setDetails(
                        new WebAuthenticationDetailsSource().buildDetails(request)
                    );

                    SecurityContextHolder.getContext().setAuthentication(authToken);
                }
            }
        } catch (JwtException e) {
            log.error("JWT validation failed", e);
        }

        filterChain.doFilter(request, response);
    }
}
```

## JWT Service

```java
@Service
public class JwtService {
    // Inject via @ConfigurationProperties — never hardcode credentials
    private final JwtProperties jwtProperties;

    public JwtService(JwtProperties jwtProperties) {
        this.jwtProperties = jwtProperties;
    }

    public String extractUsername(String token) {
        return extractClaim(token, Claims::getSubject);
    }

    public <T> T extractClaim(String token, Function<Claims, T> claimsResolver) {
        final Claims claims = extractAllClaims(token);
        return claimsResolver.apply(claims);
    }

    public String generateToken(UserDetails userDetails) {
        List<String> roles = userDetails.getAuthorities()
            .stream()
            .map(GrantedAuthority::getAuthority)
            .toList();
        Map<String, Object> extraClaims = Map.of("roles", roles);

        return generateToken(extraClaims, userDetails);
    }

    public String generateToken(
            Map<String, Object> extraClaims,
            UserDetails userDetails) {
        return buildToken(extraClaims, userDetails, jwtProperties.expiration());
    }

    public String generateRefreshToken(UserDetails userDetails) {
        return buildToken(Map.of(), userDetails, jwtProperties.refreshExpiration());
    }

    private String buildToken(
            Map<String, Object> extraClaims,
            UserDetails userDetails,
            long expiration) {
        return Jwts
            .builder()
            .claims(extraClaims)
            .subject(userDetails.getUsername())
            .issuedAt(new Date(System.currentTimeMillis()))
            .expiration(new Date(System.currentTimeMillis() + expiration))
            .signWith(getSignInKey())
            .compact();
    }

    public boolean isTokenValid(String token, UserDetails userDetails) {
        final String username = extractUsername(token);
        return username.equals(userDetails.getUsername()) && !isTokenExpired(token);
    }

    private boolean isTokenExpired(String token) {
        return extractExpiration(token).before(new Date());
    }

    private Date extractExpiration(String token) {
        return extractClaim(token, Claims::getExpiration);
    }

    private Claims extractAllClaims(String token) {
        return Jwts
            .parser()
            .verifyWith(getSignInKey())
            .build()
            .parseSignedClaims(token)
            .getPayload();
    }

    private SecretKey getSignInKey() {
        byte[] keyBytes = Decoders.BASE64.decode(jwtProperties.secret());
        return Keys.hmacShaKeyFor(keyBytes);
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

There is no logout endpoint: a signed JWT stays valid until it expires, so the client discards its tokens, and access tokens stay short-lived.

## Authentication Service

```java
@Service
@Transactional
@RequiredArgsConstructor
public class AuthenticationService {
    private final UserRepository userRepository;
    private final RoleRepository roleRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;
    private final AuthenticationManager authenticationManager;

    public AuthenticationResponse register(RegisterRequest request) {
        if (userRepository.existsByEmail(request.getEmail())) {
            throw new DuplicateResourceException("Email already registered");
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

        user = userRepository.save(user);

        String accessToken = jwtService.generateToken(convertToUserDetails(user));
        String refreshToken = jwtService.generateRefreshToken(convertToUserDetails(user));

        return new AuthenticationResponse(accessToken, refreshToken);
    }

    public AuthenticationResponse login(LoginRequest request) {
        authenticationManager.authenticate(
            new UsernamePasswordAuthenticationToken(
                request.getEmail(),
                request.getPassword()
            )
        );

        User user = userRepository.findByEmail(request.getEmail())
            .orElseThrow(() -> new UsernameNotFoundException("User not found"));

        String accessToken = jwtService.generateToken(convertToUserDetails(user));
        String refreshToken = jwtService.generateRefreshToken(convertToUserDetails(user));

        return new AuthenticationResponse(accessToken, refreshToken);
    }

    public AuthenticationResponse refreshToken(RefreshTokenRequest request) {
        String username = jwtService.extractUsername(request.getRefreshToken());

        User user = userRepository.findByEmail(username)
            .orElseThrow(() -> new UsernameNotFoundException("User not found"));

        UserDetails userDetails = convertToUserDetails(user);

        if (!jwtService.isTokenValid(request.getRefreshToken(), userDetails)) {
            throw new InvalidTokenException("Invalid refresh token");
        }

        String accessToken = jwtService.generateToken(userDetails);

        return new AuthenticationResponse(accessToken, request.getRefreshToken());
    }

    private UserDetails convertToUserDetails(User user) {
        return org.springframework.security.core.userdetails.User
            .builder()
            .username(user.getEmail())
            .password(user.getPassword())
            .authorities(user.getRoles().stream()
                .map(role -> new SimpleGrantedAuthority("ROLE_" + role.getName()))
                .toList())
            .build();
    }
}
```

## Method Security

```java
@Service
@RequiredArgsConstructor
public class UserService {
    private final UserRepository userRepository;

    @PreAuthorize("hasRole('ADMIN')")
    public List<User> getAllUsers() {
        return userRepository.findAll();
    }

    @PreAuthorize("hasRole('ADMIN') or #userId == authentication.principal.id")
    public User getUserById(Long userId) {
        return userRepository.findById(userId)
            .orElseThrow(() -> new ResourceNotFoundException("User not found"));
    }

    @PreAuthorize("isAuthenticated()")
    @PostAuthorize("returnObject.email == authentication.principal.username")
    public User updateProfile(Long userId, UserUpdateRequest request) {
        User user = getUserById(userId);
        // Update logic
        return userRepository.save(user);
    }

    @Secured({"ROLE_ADMIN", "ROLE_MANAGER"})
    public void deleteUser(Long userId) {
        userRepository.deleteById(userId);
    }
}
```

## OAuth2 Resource Server (JWT)

```java
@Configuration
@EnableWebSecurity
public class OAuth2ResourceServerConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/actuator/health").permitAll()
                // OpenAPI spec file and Swagger UI (springdoc, see web.md)
                .requestMatchers("/openapi.yaml", "/v3/api-docs/swagger-config", "/swagger-ui/**", "/swagger-ui.html").permitAll()
                .anyRequest().authenticated()
            )
            .oauth2ResourceServer(oauth2 -> oauth2
                .jwt(jwt -> jwt
                    .jwtAuthenticationConverter(jwtAuthenticationConverter())
                )
            );

        return http.build();
    }

    @Bean
    public JwtDecoder jwtDecoder() {
        return JwtDecoders.fromIssuerLocation("https://auth.example.com");
    }

    @Bean
    public JwtAuthenticationConverter jwtAuthenticationConverter() {
        JwtGrantedAuthoritiesConverter grantedAuthoritiesConverter =
            new JwtGrantedAuthoritiesConverter();
        grantedAuthoritiesConverter.setAuthoritiesClaimName("roles");
        grantedAuthoritiesConverter.setAuthorityPrefix("ROLE_");

        JwtAuthenticationConverter jwtAuthenticationConverter =
            new JwtAuthenticationConverter();
        jwtAuthenticationConverter.setJwtGrantedAuthoritiesConverter(
            grantedAuthoritiesConverter);

        return jwtAuthenticationConverter;
    }
}
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
| `@PostAuthorize` | Checks authorization after method execution |
| `@Secured` | Role-based method security |
| `@WithMockUser` | Mock authenticated user in tests |
| `@AuthenticationPrincipal` | Inject current user in controller |

## Hardening Checklist

What a secure app needs; `code-reviewer` flags anything missing.

- **Input validation**: constraints live in `openapi.yaml` (the generated interfaces carry `@Valid`); validate path variables and query params too; never trust client-side validation alone
- **Authentication & authorization**: `SecurityFilterChain` bean; stateless sessions for REST APIs; OAuth2 Resource Server or a JWT filter; `@EnableMethodSecurity` with `@PreAuthorize`; only health, docs and auth endpoints permitted without authentication; BCrypt (strength 12+) for passwords; token refresh; session timeout for session-based apps
- **Injection**: parameterized `@Query` and native queries (`@Param`); no string concatenation in `@Query`, `EntityManager.createQuery()` or JDBC
- **Secrets**: credentials, JWT keys and API keys from environment variables or mounted files (Config Tree on Kubernetes), bound with `@ConfigurationProperties`; never in `application.yml` or Git
- **TLS**: HTTPS in production; SSL Bundles (`spring.ssl.bundle.*`) for the server, `RestClient` and data sources, with `reload-on-update: true` for rotation (cert-manager on Kubernetes)
- **CORS & CSRF**: explicit allowed origins (never `*` in production); CSRF disabled only for stateless REST APIs, enabled for session-based apps
- **Headers**: Spring Security's defaults (Content-Security-Policy, X-Content-Type-Options, X-Frame-Options, Strict-Transport-Security) stay enabled
- **Error responses**: Problem Details without stack traces or internal details; generic messages for 5xx
- **Rate limiting**: auth endpoints behind `@RateLimiter` (Resilience4j); API-level limits via Spring Cloud Gateway or Bucket4j
- **Dependencies**: latest stable versions; scan for CVEs with the OWASP dependency-check plugin (`./mvnw dependency-check:check`, Gradle: `./gradlew dependencyCheckAnalyze` with `org.owasp.dependencycheck`)
- **Audit trail**: log security events (logins, failures, access denied) without secrets or tokens
