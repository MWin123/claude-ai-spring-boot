# Web Layer - Controllers & REST APIs

## REST Controller Pattern

```java
@RestController
@RequestMapping("/api/users")
@Validated
@RequiredArgsConstructor
public class UserController {
    private final UserService userService;
    
    @GetMapping
    public ResponseEntity<Page<UserResponse>> getUsers(
            @PageableDefault(size = 20, sort = "createdAt") Pageable pageable) {
        Page<UserResponse> users = userService.findAll(pageable);
        return ResponseEntity.ok(users);
    }

    @GetMapping("/{id}")
    public ResponseEntity<UserResponse> getUser(@PathVariable Long id) {
        UserResponse user = userService.findById(id);
        return ResponseEntity.ok(user);
    }

    @PostMapping
    public ResponseEntity<UserResponse> createUser(
            @Valid @RequestBody UserCreateRequest request) {
        UserResponse user = userService.create(request);
        URI location = ServletUriComponentsBuilder
                .fromCurrentRequest()
                .path("/{id}")
                .buildAndExpand(user.id())
                .toUri();
        return ResponseEntity.created(location).body(user);
    }

    @PutMapping("/{id}")
    public ResponseEntity<UserResponse> updateUser(
            @PathVariable Long id,
            @Valid @RequestBody UserUpdateRequest request) {
        UserResponse user = userService.update(id, request);
        return ResponseEntity.ok(user);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void deleteUser(@PathVariable Long id) {
        userService.delete(id);
    }
}
```

## Request DTOs with Validation

```java
public record UserCreateRequest(
    @NotBlank(message = "Email is required")
    @Email(message = "Email must be valid")
    String email,

    @NotBlank(message = "Password is required")
    @Size(min = 8, max = 100, message = "Password must be 8-100 characters")
    @Pattern(regexp = "^(?=.*[A-Z])(?=.*[a-z])(?=.*\\d).*$",
             message = "Password must contain uppercase, lowercase, and digit")
    String password,

    @NotBlank(message = "Username is required")
    @Size(min = 3, max = 50)
    @Pattern(regexp = "^[a-zA-Z0-9_]+$", message = "Username must be alphanumeric")
    String username,

    @Min(value = 18, message = "Must be at least 18")
    @Max(value = 120, message = "Must be at most 120")
    Integer age
) {}

public record UserUpdateRequest(
    @Email(message = "Email must be valid")
    String email,

    @Size(min = 3, max = 50)
    String username
) {}
```

## Response DTOs

```java
public record UserResponse(
    Long id,
    String email,
    String username,
    Integer age,
    Boolean active,
    LocalDateTime createdAt,
    LocalDateTime updatedAt
) {
    public static UserResponse from(User user) {
        return new UserResponse(
            user.getId(),
            user.getEmail(),
            user.getUsername(),
            user.getAge(),
            user.getActive(),
            user.getCreatedAt(),
            user.getUpdatedAt()
        );
    }
}
```

## Global Exception Handling

```java
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {
    @ExceptionHandler(ResourceNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleNotFound(
            ResourceNotFoundException ex, WebRequest request) {
        log.error("Resource not found: {}", ex.getMessage());
        ErrorResponse error = new ErrorResponse(
            HttpStatus.NOT_FOUND.value(),
            ex.getMessage(),
            request.getDescription(false),
            LocalDateTime.now()
        );
        return new ResponseEntity<>(error, HttpStatus.NOT_FOUND);
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ValidationErrorResponse> handleValidation(
            MethodArgumentNotValidException ex) {
        Map<String, String> errors = ex.getBindingResult()
            .getFieldErrors()
            .stream()
            .collect(Collectors.toMap(
                FieldError::getField,
                error -> error.getDefaultMessage() != null
                    ? error.getDefaultMessage()
                    : "Invalid value"
            ));

        ValidationErrorResponse response = new ValidationErrorResponse(
            HttpStatus.BAD_REQUEST.value(),
            "Validation failed",
            errors,
            LocalDateTime.now()
        );
        return new ResponseEntity<>(response, HttpStatus.BAD_REQUEST);
    }

    @ExceptionHandler(DataIntegrityViolationException.class)
    public ResponseEntity<ErrorResponse> handleDataIntegrity(
            DataIntegrityViolationException ex, WebRequest request) {
        log.error("Data integrity violation", ex);
        ErrorResponse error = new ErrorResponse(
            HttpStatus.CONFLICT.value(),
            "Data integrity violation - resource may already exist",
            request.getDescription(false),
            LocalDateTime.now()
        );
        return new ResponseEntity<>(error, HttpStatus.CONFLICT);
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleGlobalException(
            Exception ex, WebRequest request) {
        log.error("Unexpected error", ex);
        ErrorResponse error = new ErrorResponse(
            HttpStatus.INTERNAL_SERVER_ERROR.value(),
            "An unexpected error occurred",
            request.getDescription(false),
            LocalDateTime.now()
        );
        return new ResponseEntity<>(error, HttpStatus.INTERNAL_SERVER_ERROR);
    }
}

record ErrorResponse(
    int status,
    String message,
    String path,
    LocalDateTime timestamp
) {}

record ValidationErrorResponse(
    int status,
    String message,
    Map<String, String> errors,
    LocalDateTime timestamp
) {}
```

## Custom Validation

```java
@Target({ElementType.FIELD, ElementType.PARAMETER})
@Retention(RetentionPolicy.RUNTIME)
@Constraint(validatedBy = UniqueEmailValidator.class)
public @interface UniqueEmail {
    String message() default "Email already exists";
    Class<?>[] groups() default {};
    Class<? extends Payload>[] payload() default {};
}

@Component
@RequiredArgsConstructor
public class UniqueEmailValidator implements ConstraintValidator<UniqueEmail, String> {
    private final UserRepository userRepository;

    @Override
    public boolean isValid(String email, ConstraintValidatorContext context) {
        if (email == null) return true;
        return !userRepository.existsByEmail(email);
    }
}
```

## RestClient for External APIs

```java
@Configuration
@Slf4j
public class RestClientConfig {
    @Bean
    public RestClient restClient(RestClient.Builder builder) {
        return builder
            .baseUrl("https://api.example.com")
            .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
            .requestInterceptor((request, body, execution) -> {
                log.info("Request: {} {}", request.getMethod(), request.getURI());
                return execution.execute(request, body);
            })
            .build();
    }
}

@Service
@RequiredArgsConstructor
public class ExternalApiService {
    private final RestClient restClient;

    public ExternalDataResponse fetchData(String id) {
        return restClient
            .get()
            .uri("/data/{id}", id)
            .retrieve()
            .onStatus(HttpStatusCode::is4xxClientError, (request, response) -> {
                throw new ResourceNotFoundException("External resource not found");
            })
            .onStatus(HttpStatusCode::is5xxServerError, (request, response) -> {
                throw new ServiceUnavailableException("External service unavailable");
            })
            .body(ExternalDataResponse.class);
    }
}
```

Use `RestClient` for blocking calls (default with virtual threads). Use `WebClient` only for reactive/streaming scenarios.

## CORS Configuration

```java
@Configuration
public class WebConfig implements WebMvcConfigurer {

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
            .allowedOrigins("http://localhost:3000", "https://example.com")
            .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
            .allowedHeaders("*")
            .allowCredentials(true)
            .maxAge(3600);
    }
}
```

## Problem Details (RFC 7807)

```yaml
# application.yml - enables standard error response format
spring:
  mvc:
    problemdetails:
      enabled: true
```

With this enabled, Spring Boot returns RFC 7807 responses for standard exceptions:

```json
{
  "type": "about:blank",
  "title": "Not Found",
  "status": 404,
  "detail": "User with id 42 not found",
  "instance": "/api/v1/users/42"
}
```

Custom Problem Detail exceptions:

```java
public class UserNotFoundException extends ErrorResponseException {

    public UserNotFoundException(Long userId) {
        super(HttpStatus.NOT_FOUND,
            ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND,
                "User with id " + userId + " not found"),
            null);
        setTitle("User Not Found");
        setType(URI.create("https://api.example.com/errors/user-not-found"));
    }
}
```

## OpenAPI Spec (springdoc)

Every REST API gets a generated OpenAPI spec. Pick the starter from the build file (`pom.xml` or `build.gradle(.kts)`), and skip this step if any `springdoc-openapi-starter-*` dependency is already there:

| Build file contains | Add |
|--------------------|-----|
| `spring-boot-starter-webmvc` | `springdoc-openapi-starter-webmvc-ui` |
| `spring-boot-starter-webflux` (reactive REST API, no `webmvc`) | `springdoc-openapi-starter-webflux-ui` |
| Neither | Nothing |

Use springdoc 3.x, the line for Boot 4 (2.x is for Boot 3). Look up the latest 3.x release on Maven Central (3.2.0 at the time of writing) and use it for `3.x.y` below:

```xml
<properties>
    <springdoc.version>3.x.y</springdoc.version>
</properties>

<dependency>
    <groupId>org.springdoc</groupId>
    <artifactId>springdoc-openapi-starter-webmvc-ui</artifactId> <!-- or -webflux-ui -->
    <version>${springdoc.version}</version>
</dependency>
```

```kotlin
// build.gradle.kts (springdoc is not managed by the Spring Boot BOM, so give the version)
implementation("org.springdoc:springdoc-openapi-starter-webmvc-ui:3.x.y") // or -webflux-ui
```

springdoc reads the mappings, records and Bean Validation annotations. Add `@Operation`/`@Schema` only where the generated output is unclear, not on every endpoint.

### Endpoints (same for WebMVC and WebFlux)

| Path | Serves |
|------|--------|
| `/v3/api-docs` | Spec as JSON |
| `/v3/api-docs.yaml` | Spec as YAML |
| `/v3/api-docs/swagger-config` | UI config, loaded by Swagger UI |
| `/swagger-ui.html` | Redirects to `/swagger-ui/index.html` |
| `/swagger-ui/**` | Swagger UI assets |

### Configuration

```yaml
# application.yml - the defaults, set explicitly so the security matchers below stay in sync
springdoc:
  api-docs:
    path: /v3/api-docs
  swagger-ui:
    path: /swagger-ui.html
```

The spec and Swagger UI stay enabled in production. springdoc builds the spec's `servers` URL from the request, so behind a reverse proxy or load balancer it must honor the forwarded headers, or Swagger UI calls `http://<internal-host>` instead of the public `https` URL. On Kubernetes, Spring Boot detects the platform and applies `native` by default, so no setting is needed there (and the pods run the `kubernetes` profile, not `prod`). Everywhere else:

```yaml
# application-prod.yml
server:
  forward-headers-strategy: native   # X-Forwarded-Proto/Host/Port -> https://api.example.com in servers[0].url
```

Use `native`, not `framework`: with Tomcat it trusts the headers only from private-network proxy addresses (`server.tomcat.remoteip.internal-proxies`), while `framework` trusts them from any client.

### Behind a Kubernetes Ingress

The Ingress must route the docs paths to the pod:

- **One host per service** (`users.example.com`, path `/`): the default paths work as they are.
- **Shared host, one path prefix per service** (`api.example.com/api/users`): every service would claim `/v3/api-docs`. Move the docs under the service's prefix, so the existing Ingress rule covers them and each service keeps its own docs:

```yaml
# application.yml
springdoc:
  api-docs:
    path: /api/users/v3/api-docs        # YAML at /api/users/v3/api-docs.yaml
  swagger-ui:
    path: /api/users/swagger-ui.html    # UI assets move to /api/users/swagger-ui/**
```

Prefix the security matchers the same way (`/api/users/v3/api-docs/**`, `/api/users/v3/api-docs.yaml`, `/api/users/swagger-ui/**`, `/api/users/swagger-ui.html`), and put them before any `/api/users/**` role rule: the first matching rule wins.

If CSRF protection is on, "Try it out" needs two things, or POST/PUT/DELETE are rejected: Spring Security must issue the `XSRF-TOKEN` cookie eagerly and accept its raw value, which `csrf.spa()` does (see `security.md`; a bare `CookieCsrfTokenRepository.withHttpOnlyFalse()` issues no cookie for Swagger UI), and Swagger UI must send it back. With CSRF disabled, leave this out:

```yaml
# application.yml
springdoc:
  swagger-ui:
    csrf:
      enabled: true   # reads the XSRF-TOKEN cookie, sends X-XSRF-TOKEN
```

### Authentication in Swagger UI

For an API secured with JWT, declare the bearer scheme once, so Swagger UI shows the "Authorize" button and sends `Authorization: Bearer <token>` with every call:

```java
@Configuration
@OpenAPIDefinition(security = @SecurityRequirement(name = "bearerAuth"))
@SecurityScheme(name = "bearerAuth", type = SecuritySchemeType.HTTP, scheme = "bearer", bearerFormat = "JWT")
public class OpenApiConfig {}
```

Mark public endpoints (e.g. login) with `@SecurityRequirements` (empty) so the spec doesn't show them as secured.

### Spring Security

If Spring Security is present, permit the paths above in every profile, production included. Only the docs become public: the API endpoints stay authenticated, and Swagger UI calls them with the token from "Authorize". `/v3/api-docs/**` does not match `/v3/api-docs.yaml`, so list it separately:

```java
private static final String[] OPENAPI_PATHS = {
    "/v3/api-docs/**", "/v3/api-docs.yaml", "/swagger-ui/**", "/swagger-ui.html"
};

// WebMVC: SecurityFilterChain
.authorizeHttpRequests(auth -> auth
    .requestMatchers(OPENAPI_PATHS).permitAll()
    .anyRequest().authenticated())

// WebFlux: SecurityWebFilterChain
.authorizeExchange(exchange -> exchange
    .pathMatchers(OPENAPI_PATHS).permitAll()
    .anyExchange().authenticated())
```

### Tests

- Positive: `GET /v3/api-docs` returns 200 without credentials and the JSON contains the controller paths (e.g. `$.paths['/api/users']`) and `components.securitySchemes.bearerAuth`.
- Positive (prod profile): with `X-Forwarded-Proto: https` and `X-Forwarded-Host`, `servers[0].url` is the public `https` URL.
- Negative: with Spring Security, an API endpoint still returns 401 without credentials, so the permit list didn't open more than the docs.

## Quick Reference

| Annotation | Purpose |
|------------|---------|
| `@RestController` | Marks class as REST controller (combines @Controller + @ResponseBody) |
| `@RequestMapping` | Maps HTTP requests to handler methods |
| `@GetMapping/@PostMapping` | HTTP method-specific mappings |
| `@PathVariable` | Extracts values from URI path |
| `@RequestParam` | Extracts query parameters |
| `@RequestBody` | Binds request body to method parameter |
| `@Valid` | Triggers validation on request body |
| `@RestControllerAdvice` | Global exception handling for REST controllers |
| `@ResponseStatus` | Sets HTTP status code for method |
