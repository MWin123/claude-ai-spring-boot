---
name: java-modern
description: Java 21+ for Spring Boot - records, the Lombok rules for services and JPA entities, virtual threads, and the project's language preferences (pattern matching, switch expressions, sealed types). Use when writing records, entities or Lombok-annotated classes, or when modernizing existing code.
when_to_use: Writing records, entities or Lombok-annotated classes; modernizing existing code to Java 21 features; questions about records, sealed classes, pattern matching or virtual threads.
---

# Java Modern Skill

Java 21+ language features and how to use them in Spring Boot applications.

## Records (Java 16+)

### DTOs

API request/response models are generated from the OpenAPI spec (`conventions` skill). Every other DTO is a record: service results, events, messages, projections.

```java
// ✅ Records for non-API DTOs
public record ProductPriceChanged(Long productId, BigDecimal oldPrice, BigDecimal newPrice, Instant at) {}

public record ProductStats(
    Long productId,
    long orderCount,
    BigDecimal revenue
) {
    public ProductStats {                              // compact constructor validates
        if (orderCount < 0) throw new IllegalArgumentException("orderCount < 0");
    }
}
```

### Configuration Properties

```java
// ✅ Records for config properties (Spring Boot 4.x)
@ConfigurationProperties(prefix = "app.notification")
public record NotificationProperties(
    boolean enabled,
    String fromEmail,
    Duration timeout,
    Retry retry
) {
    public record Retry(int maxAttempts, Duration delay) {}
}
```

### When NOT to use records
- JPA entities (Hibernate needs mutable objects, no-arg constructor)
- Classes that need inheritance
- Objects with mutable state

## Lombok

The Lombok rules, including the safe subset on JPA entities and the Maven/Gradle setup, are in `references/lombok.md`. Read it before writing or reviewing an entity or a Lombok-annotated class.

## Language Preferences

- `instanceof` with a pattern (`obj instanceof String s`) instead of a cast
- `switch` expressions with patterns and guards (`case Order o when ...`) instead of if-else chains or `switch` with `break`
- `sealed` interfaces with record implementations for closed hierarchies (payment results, domain events), so a `switch` over them is exhaustive without `default`
- `.toList()` instead of `Collectors.toList()`; `getFirst()`/`getLast()`/`reversed()` on ordered collections
- Text blocks for multi-line JPQL, SQL and JSON test data

## Virtual Threads (Java 21 + Spring Boot 4.x)

The default `application.yml` in the `conventions` skill turns them on with `spring.threads.virtual.enabled: true`. That single property:
- Runs each HTTP request on a virtual thread (Tomcat)
- Makes `@Async` methods use virtual threads
- Allows blocking I/O (JDBC, RestClient) to scale like reactive code

```java
// ✅ Blocking code scales with virtual threads - no code changes needed
@Service
@RequiredArgsConstructor
public class ReportService {   // no @Transactional: it would hold a JDBC connection during the remote call
    private final OrderRepository orderRepository;
    private final RestClient externalApi;

    public Report generate(Long customerId) {
        // Both blocking calls - on virtual threads this scales to thousands of concurrent requests
        List<Order> orders = orderRepository.findByCustomerId(customerId);
        CustomerData data = externalApi.get()
            .uri("/customers/{id}", customerId)
            .retrieve()
            .body(CustomerData.class);
        return new Report(orders, data);
    }
}
```

**Avoid with virtual threads:**
- On Java 21–23, `synchronized` blocks around blocking calls: they pin the carrier thread, so use `ReentrantLock` there. Java 24+ no longer pins them (JEP 491).
- Thread-local heavy frameworks (check compatibility first)

**When to still use WebFlux:** streaming responses, SSE, WebSocket, or when you need backpressure.
