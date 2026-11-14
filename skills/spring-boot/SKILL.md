---
name: spring-boot
description: Building features in a Spring Boot 4.x app - contract-first REST endpoints (OpenAPI spec + openapi-generator), entities and repositories, transactional services, mappers, Problem Details, security, configuration and tests. Use when building or changing a feature.
when_to_use: Adding or changing an endpoint, entity, repository, service, controller, exception handler or security rule; "build a REST API", "add a CRUD", "new feature"; questions about Spring Security, Spring Cloud or Boot 4 APIs (JPA pitfalls such as N+1 and lazy loading go to `jpa-patterns`).
---

# Spring Boot Skill

Enterprise Spring Boot 4.x development with focus on clean architecture and production-ready code. The rules in the `conventions` skill apply to everything below.

## Core Workflow

1. Understand requirements, identify entities, APIs, and service boundaries
2. Write or extend the OpenAPI spec `src/main/resources/static/openapi.yaml` following the "Spec Design Checklist" in `references/openapi.md`, and tell the user which defaults you applied. Add the openapi-generator plugin and `spring-boot-starter-validation` if missing (same reference). Run the build's generate step (`./mvnw generate-sources`, Gradle: `./gradlew openApiGenerate`) and read the generated interfaces before writing the code that implements them
3. Create entity classes, repositories, the mapper between entities and generated models, and any non-API records; schema changes go into a migration (`db-migrations` skill)
4. Implement service layer with transaction management
5. Build controllers that implement the generated `*Api` interfaces; add the springdoc starter for Swagger UI (`references/swagger-ui.md`; webmvc or webflux variant, only if not already present)
6. Add global exception handler (`references/web.md`)
7. Write unit tests (MockitoExtension), controller slice tests against the spec's paths (positive and spec-violating requests), repository tests (`@DataJpaTest`) and integration tests (`@SpringBootTest` with the `testcontainers` profile), following the `testing-patterns` skill
8. Configure `application.yml` (start from the defaults in the `conventions` skill), plus, when springdoc was added, the springdoc settings (`swagger-ui.url: /openapi.yaml`) and the security matchers from `references/swagger-ui.md`; if existing Kubernetes manifests or a Helm chart route the app by a shared path prefix, move the spec file and docs under that prefix
9. Add the local dependencies the app needs to Docker Compose and adapt an existing CI pipeline (`deployment` skill)
10. Have the `tests` agent run the build with all tests, integration tests included (`./mvnw verify`, Gradle: `./gradlew build`), and fix every failure
11. Update README.md

## Quick Start Templates

Modern Java first: non-API DTOs are records; the Lombok rules (including the safe subset for entities) are in `references/lombok.md` of the `java-modern` skill; read it before writing an entity.

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

    @Column(nullable = false, length = 100)     // same as the migration and the spec's maxLength
    private String name;

    @Column(nullable = false, precision = 10, scale = 2)
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
            .map(ProductMapper::toResponse)
            .toList();
    }

    @Transactional
    public ProductResponse create(ProductRequest request) {   // generated model: getters, not record accessors
        var product = Product.builder().name(request.getName()).price(request.getPrice()).build();
        return ProductMapper.toResponse(repo.save(product));
    }
}
```

### REST Controller (contract-first)

The endpoints and models are defined in `src/main/resources/static/openapi.yaml`. openapi-generator turns each tag into an interface (`ProductsApi`) and each schema into a model (`ProductRequest`, `ProductResponse`) at build time, and the controller implements the interface (full setup in `references/openapi.md`):

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
          schema: { $ref: '#/components/schemas/ProductRequest' }   # required: name (minLength 1, maxLength 100), price (decimal string >= 0)
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

Copy the `GlobalExceptionHandler` from "Global Exception Handling" in `references/web.md` as it is, with `ResourceNotFoundException` as the app's own `RuntimeException` in `exception/`. It covers 404, 400 for query and path parameters (`ConstraintViolationException`), 409 for conflicts, and the `errors.<field>` map of an invalid body that the slice tests assert.

### Test Slice

Start from `ProductControllerTest` in the "Controller Slice Tests" section of the `testing-patterns` skill.

## Reference Guide

Load detailed patterns based on context:

| Topic | Reference | When to Load |
|-------|-----------|-------------|
| OpenAPI | `references/openapi.md` | Contract-first API: the spec, Spec Design Checklist, money fields, openapi-generator plugin (Maven, Gradle) |
| Web/REST | `references/web.md` | Controllers (WebMVC, WebFlux), generated models and mapping, exception handling, custom validation, RestClient, CORS, Problem Details (RFC 7807) |
| Swagger UI | `references/swagger-ui.md` | springdoc starter, Kubernetes Ingress path prefixes, docs security matchers |
| Data Access | `references/data.md` | Entities, repositories, auditing, projections |
| Security | `references/security.md` | Spring Security 7, OAuth2 Resource Server, JWT, method security, SSL Bundles, hardening checklist |
| Cloud/Config | `references/cloud.md` | Config server, discovery, resilience, HTTP interfaces, GraalVM native, OTLP tracing |
| Boot 4 | `references/boot4.md` | Modular starters, Jackson 3, @MockitoBean, @ImportHttpServices, API versioning, JSpecify |
| Testing | `testing-patterns` skill | Unit, slice and integration tests, H2 and Testcontainers profiles |
| JPA pitfalls | `jpa-patterns` skill | N+1, lazy loading, transactions, optimistic locking, Hibernate 7 |
| Logging | `logging-patterns` skill | Structured JSON logging, MDC, correlation IDs |
| Design | `design-patterns` and `code-quality` skills | Strategy, Outbox, Saga, CQRS; clean code and refactoring |

## Architecture Patterns

```
src/main/java/com/example/
├── api/            # generated from src/main/resources/static/openapi.yaml (build output, never edited)
├── controller/     # @RestController classes implementing the generated *Api interfaces
├── service/        # Business logic (@Service, @Transactional), mappers
├── repository/     # Data access (extends JpaRepository)
├── model/          # JPA entities (@Entity)
├── dto/            # Non-API records (service results, events); API models are generated
├── config/         # @Configuration, @ConfigurationProperties
└── exception/      # @RestControllerAdvice + custom exceptions
```

Layering: Controller (HTTP only) → Service (business logic, transactions) → Repository (persistence). Controllers never call repositories. Never mix blocking and reactive code in one request path.
