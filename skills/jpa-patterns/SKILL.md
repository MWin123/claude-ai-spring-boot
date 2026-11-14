---
name: jpa-patterns
description: JPA/Hibernate patterns and common pitfalls (N+1, lazy loading, transactions, queries).
when_to_use: '"N+1 problem", "too many queries", one extra query per row or per entity when loading a list or its associations; LazyInitializationException; fetch strategies (EAGER vs LAZY); transaction issues; entity relationship design; query optimization.'
---

# JPA Patterns Skill

Best practices and common pitfalls for JPA/Hibernate in Spring applications.

## Quick Reference: Common Problems

| Problem | Symptom | Solution |
|---------|---------|----------|
| N+1 queries | Many SELECT statements | JOIN FETCH, @EntityGraph |
| LazyInitializationException | Error outside transaction | JOIN FETCH, DTO projection, mapping inside the `@Transactional` service; never re-enable Open Session in View (off in the `conventions` default `application.yml`) |
| Slow queries | Performance issues | Pagination, projections, indexes |
| Dirty checking overhead | Slow updates | Read-only transactions, DTOs |
| Lost updates | Concurrent modifications | Optimistic locking (@Version) |
| Deleted rows must stay | Hard deletes lose history | `@SoftDelete` |
| UUID primary key | Sequential IDs leak or collide across services | `@GeneratedValue(strategy = GenerationType.UUID)` |

## N+1 Problem

> The #1 JPA performance killer

### The Problem

```java
// ❌ BAD: N+1 queries
@Entity
public class Author {
    @Id private Long id;
    private String name;

    @OneToMany(mappedBy = "author", fetch = FetchType.LAZY)
    private List<Book> books;
}

// This innocent code...
List<Author> authors = authorRepository.findAll();  // 1 query
for (Author author : authors) {
    System.out.println(author.getBooks().size());   // N queries!
}
// Result: 1 + N queries (if 100 authors = 101 queries)
```

### Solution 1: JOIN FETCH (JPQL)

```java
// ✅ GOOD: Single query with JOIN FETCH
public interface AuthorRepository extends JpaRepository<Author, Long> {

    @Query("SELECT a FROM Author a LEFT JOIN FETCH a.books")   // LEFT: authors without books stay
    List<Author> findAllWithBooks();
}

// Usage - single query
List<Author> authors = authorRepository.findAllWithBooks();
```

### Solution 2: @EntityGraph

```java
// ✅ GOOD: EntityGraph for declarative fetching
public interface AuthorRepository extends JpaRepository<Author, Long> {

    @EntityGraph(attributePaths = {"books"})
    List<Author> findAll();

    // Or with named graph
    @EntityGraph(value = "Author.withBooks")
    List<Author> findAllWithBooks();
}

// Define named graph on entity
@Entity
@NamedEntityGraph(
    name = "Author.withBooks",
    attributeNodes = @NamedAttributeNode("books")
)
public class Author {
    // ...
}
```

### Solution 3: Batch Fetching

```java
// ✅ GOOD: Batch fetching (Hibernate-specific)
@Entity
public class Author {

    @OneToMany(mappedBy = "author")
    @BatchSize(size = 25)  // Fetch 25 at a time
    private List<Book> books;
}
```

```yaml
# Or globally in application.yml
spring:
  jpa:
    properties:
      hibernate:
        default_batch_fetch_size: 25
```

### Detecting N+1

```yaml
# Enable SQL logging to detect N+1
spring:
  jpa:
    show-sql: true
    properties:
      hibernate:
        format_sql: true

logging:
  level:
    org.hibernate.SQL: DEBUG
    org.hibernate.orm.jdbc.bind: TRACE
```

## Lazy Loading

Declare every association `LAZY`: collections are lazy by default, but `@ManyToOne` and `@OneToOne` default to EAGER, so set `fetch = FetchType.LAZY` on them and fetch what a use case needs in its query.

### LazyInitializationException

This needs `spring.jpa.open-in-view: false`. With Boot's default (`true`), the same code runs without an error and silently runs one extra query per lazy access.

```java
// ❌ BAD: Accessing lazy field outside transaction
@Service
public class OrderService {

    public Order getOrder(Long id) {
        return orderRepository.findById(id).orElseThrow();
    }
}

// In controller (no transaction)
Order order = orderService.getOrder(1L);
order.getItems().size();  // 💥 LazyInitializationException!
```

### Solutions for LazyInitializationException

**Solution 1: JOIN FETCH in query**
```java
// ✅ Fetch needed associations in query
@Query("SELECT o FROM Order o LEFT JOIN FETCH o.items WHERE o.id = :id")
Optional<Order> findByIdWithItems(@Param("id") Long id);
```

**Solution 2: @Transactional on service method**
```java
// ✅ Keep transaction open while accessing
@Service
public class OrderService {

    @Transactional(readOnly = true)
    public OrderDTO getOrderWithItems(Long id) {
        Order order = orderRepository.findById(id).orElseThrow();
        // Access within transaction - lazy collection loads here
        int itemCount = order.getItems().size();
        return new OrderDTO(order, itemCount);
    }
}
```

**Solution 3: DTO projection (best for read-only)**
```java
// ✅ Avoid lazy loading entirely - query only what you need
public interface OrderRepository extends JpaRepository<Order, Long> {

    @Query("SELECT new com.example.dto.OrderSummary(o.id, o.status, SIZE(o.items)) " +
           "FROM Order o WHERE o.id = :id")
    Optional<OrderSummary> findSummaryById(@Param("id") Long id);
}
```

## Transaction Management

### Read-Only Optimization

```java
@Service
@Transactional(readOnly = true)  // Default for all methods
@RequiredArgsConstructor
public class ProductService {
    private final ProductRepository repo;

    public List<ProductResponse> findAll() {
        return repo.findAll().stream().map(ProductMapper::toResponse).toList();  // Read-only: skips dirty checking
    }

    // Writes override it with @Transactional, as create() in the spring-boot skill's ProductService
}
```

### Self-Invocation

`@Transactional` is ignored when the method is called through `this`, because the call bypasses the proxy. Move the method to another bean.

## Optimistic Locking

```java
// Add to the Product entity of the spring-boot skill; the @Builder constructor stays without it
@Version
@Setter(AccessLevel.NONE)
private Long version;  // Hibernate checks this on update; never set it by hand

// A conflict surfaces at commit, after the method returns: the GlobalExceptionHandler in web.md of the spring-boot skill maps
// OptimisticLockingFailureException to 409. To handle it here instead, call repo.saveAndFlush(product) in a try.
@Service
@RequiredArgsConstructor
public class ProductService {
    private final ProductRepository repo;

    @Transactional
    public ProductResponse updatePrice(Long id, BigDecimal newPrice) {
        Product product = repo.findById(id)
            .orElseThrow(() -> new ResourceNotFoundException("Product not found"));
        product.setPrice(newPrice);   // managed entity: flushed and version-checked at commit
        return ProductMapper.toResponse(product);
    }
}
```

## Modern Hibernate Features

### UUID Generation

```java
@Entity
@Getter
@Setter
public class Event {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)  // Native UUID generation
    @Setter(AccessLevel.NONE)
    private UUID id;

    private String name;
}
```

### Soft Delete

```java
// Built-in soft delete support
@Entity
@SoftDelete  // Adds 'deleted' boolean column, filters automatically
@Getter
@Setter
public class Customer {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Setter(AccessLevel.NONE)
    private Long id;

    private String name;
}

// Custom column: ACTIVE stores 1 for live rows (the default DELETED stores true for deleted ones)
@Entity
@SoftDelete(columnName = "is_active", strategy = SoftDeleteType.ACTIVE, converter = NumericBooleanConverter.class)
public class Product {
    // ...
}
```

Both columns come from a migration (`db-migrations`): `deleted BOOLEAN NOT NULL DEFAULT FALSE`, or `is_active INTEGER NOT NULL DEFAULT 1` for the converter.

### Record as DTO in Queries

```java
// Records work natively in JPQL constructor expressions
public record ProductSummary(Long id, String name, BigDecimal price) {}

public interface ProductRepository extends JpaRepository<Product, Long> {

    @Query("SELECT new com.example.dto.ProductSummary(p.id, p.name, p.price) " +
           "FROM Product p WHERE p.price > :minPrice")
    List<ProductSummary> findExpensiveProducts(@Param("minPrice") BigDecimal minPrice);
}
```

## Pagination and Projections

Every list query that can grow takes a `Pageable` (`Slice` skips the COUNT query). Interface and record projections are under "Projections" in `data.md` of the `spring-boot` skill.
