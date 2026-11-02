# Web Layer - Controllers & REST APIs

The controllers implement the `*Api` interfaces that openapi-generator builds from the spec. The spec, the "Spec Design Checklist" and the generator plugin are in `openapi.md`; Swagger UI (springdoc) is in `swagger-ui.md`.

## Controller

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

## Reactive Controller (WebFlux)

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

## Models and Mapping

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

    @ExceptionHandler(OptimisticLockingFailureException.class)   // @Version conflict, raised at commit (jpa-patterns)
    public ProblemDetail handleOptimisticLock(OptimisticLockingFailureException ex) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT, "Resource was modified concurrently; reload and retry");
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
    public RestClient restClient(RestClient.Builder builder,
            @Value("${app.external-api.base-url}") String baseUrl) {   // set through APP_EXTERNAL_API_BASE_URL
        return builder
            .baseUrl(baseUrl)
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
            // The first matching handler wins
            .onStatus(status -> status.value() == 404, (request, response) -> {
                throw new ResourceNotFoundException("External resource not found");
            })
            .onStatus(status -> status.value() == 429 || status.value() == 503, (request, response) -> {
                throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "External service busy; retry later");
            })
            .onStatus(HttpStatusCode::isError, (request, response) -> {
                throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "External service failed");
            })
            .body(ExternalDataResponse.class);
    }
}
```

The client never sees the remote status as its own. A remote 404 means the resource doesn't exist, so it becomes the app's 404. A remote 429 or 503 is worth retrying later, so it becomes 503. Every other remote error becomes 502, including 401 and 403, which mean the app's own credentials for the remote service are wrong. `ResponseStatusException` reaches the client as a Problem Detail through the handler above. The base URL is environment-specific, so it comes from the environment, not from `application.yml` (`conventions` skill).

Use `RestClient` for blocking calls (default with virtual threads). Use `WebClient` only for reactive/streaming scenarios.

## CORS Configuration

Configure CORS in one place. With Spring Security, that place is the `CorsConfigurationSource` bean in "Security Configuration" in `security.md`. `.cors(...)` applies it before authentication, so preflight requests need no token. Don't add a `WebMvcConfigurer` CORS mapping next to it. Without Spring Security, register the same origins, methods and headers in `WebMvcConfigurer.addCorsMappings`.

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

## Tests

- Positive: a valid create returns 201 with a `Location` header and the declared response body.
- Negative: an invalid body returns 400 with `errors.<field>`; a parameter outside its spec bounds (`size=500`) returns 400 `application/problem+json`, not 500.
