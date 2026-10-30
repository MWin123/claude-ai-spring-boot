# Web Layer - Controllers & REST APIs

## Contract-First REST API (OpenAPI Generator)

The API is spec-first: a hand-written OpenAPI spec is the contract, and the build generates the controller interfaces and the request/response models from it. The controllers implement the generated interfaces. They never declare `@RequestMapping`, `@PathVariable`, `@RequestBody` or `@Valid`, because those come from the interface. To change the API, edit the spec and rebuild. Never edit generated code, and never write a controller mapping or API DTO that the spec does not define.

| Piece | Where | Written by |
|-------|-------|------------|
| Spec (OpenAPI 3.0.x) | `src/main/resources/static/openapi.yaml` (also served to Swagger UI, see below) | You |
| API interfaces (`UsersApi`, one per tag) | `<base package>.api`, under `target/generated-sources/openapi` (Maven) or `build/generated/openapi` (Gradle) | Generator |
| Models (`CreateUserRequest`, `UserResponse`) | `<base package>.api.model` | Generator |
| Controllers implementing the interfaces | `<base package>.controller` | You |

Keep the spec on OpenAPI 3.0.x (`openapi: 3.0.3`), because the generator's 3.1 support is incomplete. Leave `servers` out, so Swagger UI calls the host it was loaded from.

### The Spec

```yaml
# src/main/resources/static/openapi.yaml
openapi: 3.0.3
info:
  title: User API
  version: 1.0.0          # keep in step with the project version
security:
  - bearerAuth: []        # every operation needs a JWT unless it says otherwise
paths:
  /api/v1/users:
    get:
      tags: [Users]       # one generated interface per tag: UsersApi
      operationId: listUsers   # becomes the Java method name
      parameters:
        - { name: page, in: query, schema: { type: integer, minimum: 0, default: 0 } }
        - { name: size, in: query, schema: { type: integer, minimum: 1, maximum: 100, default: 20 } }
      responses:
        '200':
          description: One page of users
          content:
            application/json:
              schema: { $ref: '#/components/schemas/UserPage' }
    post:
      tags: [Users]
      operationId: createUser
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/CreateUserRequest' }
      responses:
        '201':
          description: Created
          headers: { Location: { schema: { type: string, format: uri } } }
          content:
            application/json:
              schema: { $ref: '#/components/schemas/UserResponse' }
        '400': { $ref: '#/components/responses/BadRequest' }
  /api/v1/users/{id}:
    parameters:
      - { name: id, in: path, required: true, schema: { type: integer, format: int64 } }
    get:
      tags: [Users]
      operationId: getUser
      responses:
        '200':
          description: The user
          content:
            application/json:
              schema: { $ref: '#/components/schemas/UserResponse' }
        '404': { $ref: '#/components/responses/NotFound' }
    delete:
      tags: [Users]
      operationId: deleteUser
      responses:
        '204': { description: Deleted }
        '404': { $ref: '#/components/responses/NotFound' }
components:
  responses:                # shared error responses, referenced per operation
    BadRequest:
      description: Invalid request
      content: { application/problem+json: { schema: { $ref: '#/components/schemas/ProblemDetail' } } }
    NotFound:
      description: Not found
      content: { application/problem+json: { schema: { $ref: '#/components/schemas/ProblemDetail' } } }
  securitySchemes:
    bearerAuth: { type: http, scheme: bearer, bearerFormat: JWT }
  schemas:
    CreateUserRequest:
      type: object
      required: [email, username]
      properties:
        email: { type: string, format: email, maxLength: 100 }        # @NotNull @Email @Size; same length as the users.email column
        username: { type: string, minLength: 3, maxLength: 50, pattern: '^[a-zA-Z0-9_]+$' }
    UserResponse:
      type: object
      required: [id, email, username]
      properties:
        id: { type: integer, format: int64 }
        email: { type: string }
        username: { type: string }
        createdAt: { type: string, format: date-time }                # OffsetDateTime
    UserPage:
      type: object
      required: [content, totalElements]
      properties:
        content: { type: array, items: { $ref: '#/components/schemas/UserResponse' } }
        totalElements: { type: integer, format: int64 }
    ProblemDetail:          # mapped to Spring's ProblemDetail, not generated (schemaMappings below)
      type: object
      properties:
        type: { type: string, format: uri }
        title: { type: string }
        status: { type: integer }
        detail: { type: string }
        instance: { type: string, format: uri }
```

Validation lives in the spec: `required` becomes `@NotNull`, while `minLength`/`maxLength`, `minimum`/`maximum`, `pattern` and `format: email` become `@Size`, `@Min`/`@Max`, `@Pattern` and `@Email`. A required request body gets `@Valid @RequestBody` on the generated method. Mark a public operation (e.g. login) with `security: []`. Keep `maxLength` equal to the column length in the migration, or a valid request fails in the database.

### Spec Design Checklist

Before writing or changing the spec, settle these points. Take the answer from the request, the existing code or the existing spec. Ask the user only about a point that none of them settles and that would be costly to change later (auth, versioning, error format). For the rest, apply the default and say so in the report. Show the user the finished YAML before generating code from it.

| Topic | Decide | Default |
|-------|--------|---------|
| Resources and operations | Nouns for paths (`/users/{id}`), HTTP verbs for actions; every operation has a unique `operationId` and a tag per resource | Plural nouns, `kebab-case` path segments, `camelCase` `operationId` (`listUsers`) |
| Versioning | Where the version lives | `/api/v1/...` prefix; `info.version` follows the project version |
| Authentication | Which operations are public | JWT bearer scheme on every operation; `security: []` only on login, registration and similar |
| Authorization | Who may call what | Not in the spec: enforce with Spring Security. Mention the required role in the operation `description` |
| Pagination | Every list operation that can grow | `page` (min 0, default 0) and `size` (min 1, max 100, default 20) query parameters; response with `content` and `totalElements`. Never return an unbounded array |
| Filtering and sorting | Which fields are queryable | Only the ones the request needs, as explicit query parameters |
| Success responses | Status code per operation | `200` read/update, `201` create (with `Location` header), `204` delete or no body |
| Errors | Which failures each operation can produce | `400` for operations with input, `404` for operations with `{id}`, `409` for unique-field conflicts, `401`/`403` follow from `security`. All `application/problem+json` with the `ProblemDetail` schema |
| Constraints | Every input field | `required` where the service needs the value; `minLength`/`maxLength` on every string, `minimum`/`maximum` on numbers, `pattern` or `format` where it applies. No unbounded strings |
| Schemas | Separate request and response schemas | `CreateXRequest` / `UpdateXRequest` / `XResponse`; never one schema for both directions; no entity fields the client must not see (password hashes, internal ids); IDs `int64` or `uuid` |
| Update semantics | Full or partial update | `PUT` replaces (all fields required), `PATCH` takes an all-optional schema |
| Dates and money | Wire formats | `format: date-time` (ISO 8601, UTC) for instants, `format: date` for dates; money as a decimal string (see "Money" below) or integer minor units, never `number` |
| Enums and nullability | Closed value sets, optional vs nullable | `enum` only for sets the server controls; `required` marks always-present properties, `nullable: true` only where `null` carries meaning |
| Compatibility | Is this a change to a published API? | Adding optional fields or operations is safe; removing or renaming fields, tightening constraints, changing status codes or making a field required needs a new version or the user's explicit approval |

Reuse shared pieces through `components` (`ProblemDetail`, `UserPage`, repeated parameters, standard error `responses`) instead of repeating them per operation, and give every schema, operation and non-obvious parameter a `description`. After editing, run the generator and read the generated interfaces to check that the Java signatures match the intended contract.

#### Money

`type: string, format: decimal` generates a `BigDecimal`, and the generator option `bigDecimalAsString` writes it as a JSON string, so no client parses it into a float. `minimum` and `maxLength` do not apply to a string-typed decimal (`maxLength` even puts `@Size` on the `BigDecimal`, which fails at runtime); bound it with Bean Validation through `x-field-extra-annotation`, with `@Digits` matching the column's `precision`/`scale`:

```yaml
price:
  type: string
  format: decimal
  example: "19.99"
  x-field-extra-annotation: '@jakarta.validation.constraints.DecimalMin("0") @jakarta.validation.constraints.Digits(integer = 8, fraction = 2)'
```

### Generator Plugin

The generator is not managed by the Spring Boot BOM. Look up the latest `openapi-generator-maven-plugin` release on Maven Central (7.26.0 at the time of writing; the Gradle plugin `org.openapi.generator` has the same version). `useSpringBoot4` needs 7.x.

```xml
<properties>
    <openapi-generator.version>7.x.y</openapi-generator.version>
</properties>

<plugin>
    <groupId>org.openapitools</groupId>
    <artifactId>openapi-generator-maven-plugin</artifactId>
    <version>${openapi-generator.version}</version>
    <executions>
        <execution>
            <goals><goal>generate</goal></goals>
            <configuration>
                <inputSpec>${project.basedir}/src/main/resources/static/openapi.yaml</inputSpec>
                <generatorName>spring</generatorName>
                <apiPackage>com.example.api</apiPackage>             <!-- base package + .api -->
                <modelPackage>com.example.api.model</modelPackage>
                <generateSupportingFiles>false</generateSupportingFiles>
                <schemaMappings>ProblemDetail=org.springframework.http.ProblemDetail</schemaMappings>
                <configOptions>
                    <interfaceOnly>true</interfaceOnly>              <!-- interfaces + models, no stub controllers -->
                    <useSpringBoot4>true</useSpringBoot4>            <!-- jakarta.*, Boot 4 -->
                    <useTags>true</useTags>                          <!-- UsersApi per tag, not per path segment -->
                    <skipDefaultInterface>true</skipDefaultInterface><!-- unimplemented operations fail to compile -->
                    <bigDecimalAsString>true</bigDecimalAsString>    <!-- BigDecimal as a JSON string, see "Money" -->
                    <openApiNullable>false</openApiNullable>         <!-- no jackson-databind-nullable (Jackson 2) -->
                    <documentationProvider>none</documentationProvider> <!-- Swagger UI shows the spec file itself -->
                    <generateJsonIncludeAnnotations>false</generateJsonIncludeAnnotations>
                    <generateJsonSetterNullsAnnotations>false</generateJsonSetterNullsAnnotations>
                </configOptions>
            </configuration>
        </execution>
    </executions>
</plugin>
```

The plugin runs in `generate-sources` and adds the output to the compile sources. In Gradle, wire it in yourself:

```kotlin
// build.gradle.kts
plugins {
    id("org.openapi.generator") version "7.x.y"
}

openApiGenerate {
    generatorName = "spring"
    inputSpec = layout.projectDirectory.file("src/main/resources/static/openapi.yaml")
    outputDir = layout.buildDirectory.dir("generated/openapi")
    apiPackage = "com.example.api"
    modelPackage = "com.example.api.model"
    globalProperties = mapOf("apis" to "", "models" to "")   // no supporting files
    schemaMappings = mapOf("ProblemDetail" to "org.springframework.http.ProblemDetail")
    configOptions = mapOf(
        "interfaceOnly" to "true",
        "useSpringBoot4" to "true",
        "useTags" to "true",
        "skipDefaultInterface" to "true",
        "bigDecimalAsString" to "true",
        "openApiNullable" to "false",
        "documentationProvider" to "none",
        "generateJsonIncludeAnnotations" to "false",
        "generateJsonSetterNullsAnnotations" to "false",
    )
}

sourceSets { main { java { srcDir(layout.buildDirectory.dir("generated/openapi/src/main/java")) } } }
tasks.compileJava { dependsOn(tasks.openApiGenerate) }
```

The generated code needs `spring-boot-starter-validation`; everything else comes with the web starter. For a WebFlux app, add `reactive=true` to the config options. The methods then return `Mono<ResponseEntity<...>>`, take `Mono<Body>` and get a trailing `ServerWebExchange` parameter (see "Reactive Controller (WebFlux)" below).

### Controller

```java
@RestController
@RequiredArgsConstructor
public class UserController implements UsersApi {
    private final UserService userService;

    @Override
    public ResponseEntity<UserPage> listUsers(Integer page, Integer size) {
        return ResponseEntity.ok(userService.findAll(PageRequest.of(page, size, Sort.by("createdAt"))));
    }

    @Override
    public ResponseEntity<UserResponse> getUser(Long id) {
        return ResponseEntity.ok(userService.findById(id));
    }

    @Override
    public ResponseEntity<UserResponse> createUser(CreateUserRequest request) {
        UserResponse user = userService.create(request);
        URI location = ServletUriComponentsBuilder.fromCurrentRequest()
                .path("/{id}").buildAndExpand(user.getId()).toUri();
        return ResponseEntity.created(location).body(user);
    }

    @Override
    public ResponseEntity<Void> deleteUser(Long id) {
        userService.delete(id);
        return ResponseEntity.noContent().build();
    }
}
```

Only the parameters go in the override: mappings, binding and validation annotations are inherited from the interface. Status codes come from the spec, so return `ResponseEntity` with the status it declares (201 + `Location`, 204). `@WebMvcTest(UserController.class)` tests work unchanged against the paths in the spec.

The generated interfaces are `@Validated`. A query or path parameter that breaks its spec constraint (`size=500` against `maximum: 100`) therefore throws `ConstraintViolationException`, which ends up as a 500 unless the global handler maps it (see "Global Exception Handling" below). An invalid body still raises `MethodArgumentNotValidException` as usual.

### Reactive Controller (WebFlux)

With `reactive=true`, the generated `OrdersApi` methods return `Mono`, take the body as `Mono` and get the `ServerWebExchange`:

```java
@RestController
@RequiredArgsConstructor
public class OrderController implements OrdersApi {
    private final OrderService orderService;

    @Override
    public Mono<ResponseEntity<OrderResponse>> getOrder(UUID id, ServerWebExchange exchange) {
        return orderService.findById(id)
                .map(ResponseEntity::ok)
                .defaultIfEmpty(ResponseEntity.notFound().build());
    }

    @Override
    public Mono<ResponseEntity<OrderResponse>> createOrder(Mono<CreateOrderRequest> request,
                                                           ServerWebExchange exchange) {
        return request.flatMap(orderService::create)
                .map(order -> ResponseEntity.status(HttpStatus.CREATED).body(order));
    }
}
```

### Models and Mapping

The generator (7.x) produces the models as mutable classes with getters, fluent setters and a constructor taking the required properties, not as records. They count as generated code, not hand-written DTOs. Use them directly at the API boundary: don't wrap them in parallel records, and don't add methods to them. `format: date-time` becomes `OffsetDateTime`. Map between entities and models in a hand-written mapper next to the service:

```java
final class UserMapper {
    private UserMapper() {}

    static UserResponse toResponse(User user) {
        return new UserResponse(user.getId(), user.getEmail(), user.getUsername())   // required properties
                .createdAt(user.getCreatedAt().atOffset(ZoneOffset.UTC));   // optional ones via fluent setters
    }
}
```

The service builds new entities from the request with the entity's `@Builder` (`User.builder().email(request.getEmail())...`), so values the request doesn't carry, like an encoded password, stay in the service.

Records stay the rule for every other DTO and value type (service results, events, `@ConfigurationProperties`).

## Global Exception Handling

Every error is a `ProblemDetail` (`application/problem+json`), matching the error responses in the spec. Extending `ResponseEntityExceptionHandler` covers Spring MVC's own exceptions and `ErrorResponseException` subclasses (see "Problem Details" below). Don't add an `@ExceptionHandler(Exception.class)`: it also catches the `AuthorizationDeniedException` of `@PreAuthorize`, turning Spring Security's 403 into a 500, and Spring Boot already logs unhandled exceptions and answers 500 without details.

```java
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler extends ResponseEntityExceptionHandler {

    @ExceptionHandler(ResourceNotFoundException.class)
    public ProblemDetail handleNotFound(ResourceNotFoundException ex) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, ex.getMessage());
    }

    @ExceptionHandler(ConstraintViolationException.class)   // query/path parameters (@Validated interfaces)
    public ProblemDetail handleConstraintViolation(ConstraintViolationException ex) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, ex.getMessage()); // "listUsers.size: must be less than or equal to 100"
    }

    @ExceptionHandler(DataIntegrityViolationException.class)
    public ProblemDetail handleDataIntegrity(DataIntegrityViolationException ex) {
        log.warn("Data integrity violation", ex);
        return ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT, "Resource may already exist");
    }

    @Override   // invalid body: add the field errors to the 400 response
    protected ResponseEntity<Object> handleMethodArgumentNotValid(MethodArgumentNotValidException ex,
            HttpHeaders headers, HttpStatusCode status, WebRequest request) {
        ex.getBody().setProperty("errors", ex.getBindingResult().getFieldErrors().stream()
                .collect(Collectors.toMap(FieldError::getField,
                        error -> Objects.requireNonNullElse(error.getDefaultMessage(), "Invalid value"),
                        (first, second) -> first)));   // a field can break several constraints
        return super.handleMethodArgumentNotValid(ex, headers, status, request);
    }
}
```

## Custom Validation

Put a custom constraint on a generated model with the `x-field-extra-annotation` vendor extension on the property in the spec (`x-field-extra-annotation: "@com.example.validation.UniqueEmail"`), so the annotation survives regeneration:

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

With the handler above, every error response follows RFC 7807 (`spring.mvc.problemdetails.enabled` registers Boot's own `ResponseEntityExceptionHandler`, which backs off for this one):

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

## Swagger UI (springdoc)

springdoc hosts Swagger UI for the hand-written spec (see "Contract-First REST API" above). Swagger UI loads `openapi.yaml` itself, so it shows the contract exactly as written, including `info`, the security schemes and the "Authorize" button, with no `@OpenAPIDefinition`, `@SecurityScheme` or `@Operation` annotations in Java. Pick the starter from the build file (`pom.xml` or `build.gradle(.kts)`), and skip this step if any `springdoc-openapi-starter-*` dependency is already there:

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

### Endpoints (same for WebMVC and WebFlux)

| Path | Serves |
|------|--------|
| `/openapi.yaml` | The hand-written spec, as a static resource from `src/main/resources/static/` |
| `/swagger-ui.html` | Redirects to `/swagger-ui/index.html` |
| `/swagger-ui/**` | Swagger UI assets |
| `/v3/api-docs/swagger-config` | UI config, loaded by Swagger UI; points it at `/openapi.yaml` |

springdoc also serves its own spec at `/v3/api-docs`, rebuilt from the controller mappings. Swagger UI does not use it, and since the contract is `openapi.yaml` it stays out of the permitted paths below. Keep it enabled anyway: `springdoc.api-docs.enabled: false` also switches off `swagger-config` and Swagger UI.

### Configuration

```yaml
# application.yml
springdoc:
  swagger-ui:
    url: /openapi.yaml           # show the hand-written spec, not springdoc's /v3/api-docs
```

The spec and Swagger UI stay enabled in production. The spec has no `servers` entry, so Swagger UI calls the host and scheme it was loaded from, and behind a reverse proxy the docs need no forwarded-header setting.

### Behind a Kubernetes Ingress

The Ingress must route the docs paths to the pod:

- **One host per service** (`users.example.com`, path `/`): the default paths work as they are.
- **Shared host, one path prefix per service** (`api.example.com/api/users`): every service would claim `/openapi.yaml` and `/swagger-ui.html`. Move the docs under the service's prefix, so the existing Ingress rule covers them and each service keeps its own docs. Move the spec file to `src/main/resources/static/api/users/openapi.yaml`, point the generator's `inputSpec` at the new location, and set:

```yaml
# application.yml
springdoc:
  api-docs:
    path: /api/users/v3/api-docs        # swagger-config moves to /api/users/v3/api-docs/swagger-config
  swagger-ui:
    path: /api/users/swagger-ui.html    # UI assets move to /api/users/swagger-ui/**
    url: /api/users/openapi.yaml
```

Prefix the security matchers the same way (`/api/users/openapi.yaml`, `/api/users/v3/api-docs/swagger-config`, `/api/users/swagger-ui/**`, `/api/users/swagger-ui.html`), and put them before any `/api/users/**` role rule: the first matching rule wins.

If CSRF protection is on, "Try it out" needs two things, or POST/PUT/DELETE are rejected: Spring Security must issue the `XSRF-TOKEN` cookie eagerly and accept its raw value, which `csrf.spa()` does (see `security.md`; a bare `CookieCsrfTokenRepository.withHttpOnlyFalse()` issues no cookie for Swagger UI), and Swagger UI must send it back. With CSRF disabled, leave this out:

```yaml
# application.yml
springdoc:
  swagger-ui:
    csrf:
      enabled: true   # reads the XSRF-TOKEN cookie, sends X-XSRF-TOKEN
```

### Authentication in Swagger UI

For an API secured with JWT, the spec declares the bearer scheme (`components.securitySchemes.bearerAuth` plus the top-level `security`, as in "The Spec" above). Swagger UI then shows the "Authorize" button and sends `Authorization: Bearer <token>` with every call. Operations with `security: []` (e.g. login) are shown as public. No Java configuration is needed.

### Spring Security

If Spring Security is present, permit the paths above in every profile, production included. Only the docs become public: the API endpoints stay authenticated, and Swagger UI calls them with the token from "Authorize". springdoc's own `/v3/api-docs` stays authenticated, so permit only its `swagger-config` child:

```java
private static final String[] OPENAPI_PATHS = {
    "/openapi.yaml", "/v3/api-docs/swagger-config", "/swagger-ui/**", "/swagger-ui.html"
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

- Positive: without credentials, `GET /openapi.yaml` returns 200 and `GET /v3/api-docs/swagger-config` returns `$.url` = `/openapi.yaml`.
- Positive: a valid create returns 201 with a `Location` header and the declared response body.
- Negative: without credentials, `/v3/api-docs` and an API endpoint return 401, so the permit list opened only the docs.
- Negative: an invalid body returns 400 with `errors.<field>`; a parameter outside its spec bounds (`size=500`) returns 400 `application/problem+json`, not 500.
