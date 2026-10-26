---
name: spring-boot
description: Spring Boot 4.x development - REST APIs, JPA, Security, Testing, and Cloud-native patterns. Use for building enterprise Java applications with Spring Boot.
metadata:
  version: "1.0.0"
  domain: backend
  triggers: Spring Boot, Spring Framework, Spring Security, Spring Data JPA, Spring WebFlux, Java REST API, Microservices Java
  role: specialist
  scope: implementation
  output-format: code
---

# Spring Boot Skill

Enterprise Spring Boot 4.x development with focus on clean architecture and production-ready code.

## Core Workflow

1. **Analyze** - Understand requirements, identify service boundaries, APIs, data models
2. **Design** - Plan architecture, confirm design before coding
3. **Implement** - Build with constructor injection and layered architecture
4. **Secure** - Add Spring Security, OAuth2, method security; verify tests pass
5. **Test** - Write unit, integration tests; run `./mvnw test` (Gradle: `./gradlew test`) and confirm all pass
6. **Deploy** - Configure health checks via Actuator; validate `/actuator/health` returns UP

## Quick Start Templates

Modern Java first: DTOs are records; Lombok rules (including the safe subset for entities) are in the `java-modern` skill.

### Entity
```java
@Entity
@Table(name = "products")
@Getter
@Setter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Product {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Setter(AccessLevel.NONE)
    private Long id;

    @NotBlank
    private String name;

    @DecimalMin("0.0")
    private BigDecimal price;

    @Builder                                    // business fields only: no id
    public Product(String name, BigDecimal price) {
        this.name = name;
        this.price = price;
    }

    // equals/hashCode: write by hand, id-based (never @Data/@EqualsAndHashCode)
}
```

### Repository
```java
public interface ProductRepository extends JpaRepository<Product, Long> {
    List<Product> findByNameContainingIgnoreCase(String name);
}
```

### Service
```java
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ProductService {
    private final ProductRepository repo;

    public List<ProductResponse> search(String name) {
        return repo.findByNameContainingIgnoreCase(name).stream()
            .map(ProductResponse::from)
            .toList();
    }

    @Transactional
    public ProductResponse create(ProductRequest request) {
        var product = Product.builder().name(request.name()).price(request.price()).build();
        return ProductResponse.from(repo.save(product));
    }
}
```

### REST Controller (contract-first)

The endpoints and models are defined in `src/main/resources/static/openapi.yaml`. openapi-generator turns each tag into an interface (`ProductsApi`) and each schema into a model (`ProductRequest`, `ProductResponse`) at build time, and the controller implements the interface (full setup in `references/web.md`):

```yaml
# openapi.yaml (excerpt)
/api/v1/products:
  post:
    tags: [Products]
    operationId: createProduct
    requestBody:
      required: true
      content:
        application/json:
          schema: { $ref: '#/components/schemas/ProductRequest' }   # name: minLength 1, price: minimum 0
    responses:
      '201':
        description: Created
        content:
          application/json:
            schema: { $ref: '#/components/schemas/ProductResponse' }
```

```java
@RestController
@RequiredArgsConstructor
public class ProductController implements ProductsApi {   // generated: mappings, @Valid, Bean Validation
    private final ProductService service;

    @Override
    public ResponseEntity<ProductResponse> createProduct(ProductRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED).body(service.create(request));
    }
}
```

### Models and Mapping
```java
// ProductRequest/ProductResponse are generated; map entities to them in one place
final class ProductMapper {
    private ProductMapper() {}

    static ProductResponse toResponse(Product product) {
        return new ProductResponse(product.getId(), product.getName(), product.getPrice());
    }
}
```

### Global Exception Handler
```java
@RestControllerAdvice
public class GlobalExceptionHandler extends ResponseEntityExceptionHandler {   // full version: references/web.md
    @ExceptionHandler(EntityNotFoundException.class)
    public ProblemDetail handleNotFound(EntityNotFoundException ex) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, ex.getMessage());
    }

    @ExceptionHandler(ConstraintViolationException.class)   // query/path parameters of the @Validated *Api interfaces
    public ProblemDetail handleConstraintViolation(ConstraintViolationException ex) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, ex.getMessage());
    }
}
```

### Test Slice
```java
@WebMvcTest(ProductController.class)
class ProductControllerTest {
    @Autowired MockMvc mockMvc;
    @MockitoBean ProductService service;

    @Test
    void createProduct_validRequest_returns201() throws Exception {
        var response = new ProductResponse(1L, "Widget", new BigDecimal("10.00"));
        when(service.create(any())).thenReturn(response);

        mockMvc.perform(post("/api/v1/products")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    {"name":"Widget","price":10.0}
                    """))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.name").value("Widget"));
    }
}
```

## Reference Guide

Load detailed patterns based on context:

| Topic | Reference | When to Load |
|-------|-----------|-------------|
| Web/REST | `references/web.md` | Contract-first API (OpenAPI spec + openapi-generator), controllers, validation, exception handling, Problem Details (RFC 7807), Swagger UI (springdoc) |
| Data Access | `references/data.md` | JPA, repositories, transactions, queries |
| Security | `references/security.md` | Spring Security 7, OAuth2, JWT, auth |
| Cloud/Config | `references/cloud.md` | Config server, discovery, resilience, virtual threads, HTTP interfaces, GraalVM native, OTLP tracing |
| Boot 4 | `references/boot4.md` | Modular starters, Jackson 3, @MockitoBean, @ImportHttpServices, API versioning, JSpecify |
| Testing | `testing-patterns` skill | Unit, slice and integration tests, H2 and Testcontainers profiles |

## Constraints

### MUST DO
- Constructor injection (no field injection), generated with Lombok `@RequiredArgsConstructor`
- Records for DTOs, Lombok only for boilerplate a record cannot replace, only the safe Lombok subset on `@Entity` classes
- `@Valid` on all request bodies
- `@Transactional` for multi-step writes
- `@Transactional(readOnly = true)` for reads
- Type-safe config with `@ConfigurationProperties`
- Global exception handling with `@RestControllerAdvice`
- Externalize secrets (use env vars, not properties files)

### MUST NOT DO
- Field injection (`@Autowired` on fields)
- Skip input validation on endpoints
- Mix blocking and reactive code
- Store secrets in application.properties
- Use deprecated Spring Boot 2.x/3.x patterns
- Use `@MockBean`/`@SpyBean` (use `@MockitoBean`/`@MockitoSpyBean`)
- Use `com.fasterxml.jackson.databind` (Jackson 3: `tools.jackson.databind`)
- Use classic starters such as `spring-boot-starter-web` (use `spring-boot-starter-webmvc` plus matching `-test` starters)
- Hardcode URLs, credentials, environment values

## Architecture Patterns

**Project Structure:**
```
src/main/java/com/example/
├── controller/     # REST endpoints
├── service/        # Business logic
├── repository/     # Data access
├── model/          # Entities
├── dto/            # Request/Response DTOs
├── config/         # Configuration
└── exception/      # Custom exceptions + handler
```

**Layering:**
- Controller → Service → Repository
- Controller handles HTTP, validation
- Service handles business logic, transactions
- Repository handles data persistence

**Clean Architecture Principles:**
- Domain models independent of frameworks
- Use case driven design
- Dependency inversion (interfaces)
- Clear boundaries between layers

## Common Annotations

| Annotation | Purpose |
|------------|---------|
| `@RestController` | REST controller (combines @Controller + @ResponseBody) |
| `@Service` | Business logic component |
| `@Repository` | Data access component |
| `@Transactional` | Transaction management |
| `@Valid` | Trigger validation |
| `@ConfigurationProperties` | Bind properties to class |
| `@EnableMethodSecurity` | Enable method security |

## Reactive WebFlux Endpoint

Same contract-first setup with `reactive=true` in the generator's config options: the generated `OrdersApi` methods return `Mono`, take the body as `Mono` and get the `ServerWebExchange`.

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

## Spring Security JWT

```java
@Configuration
@EnableMethodSecurity
public class SecurityConfig {
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
                .csrf(AbstractHttpConfigurer::disable)
                .sessionManagement(s -> s.sessionCreationPolicy(STATELESS))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/actuator/health").permitAll()
                        // OpenAPI spec file and Swagger UI (springdoc, references/web.md)
                        .requestMatchers("/openapi.yaml", "/v3/api-docs/swagger-config", "/swagger-ui/**", "/swagger-ui.html").permitAll()
                        .anyRequest().authenticated())
                .oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()))
                .build();
    }
}
```

## Knowledge Base

Spring Boot 4.x, Java 21+, Spring WebFlux, Project Reactor, Spring Data JPA, Spring Security, OAuth2/JWT, Hibernate, R2DBC, Spring Cloud, Resilience4j, Micrometer, JUnit 5, Testcontainers, Mockito, Maven, Gradle, Paketo Buildpacks, Skaffold
