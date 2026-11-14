---
name: design-patterns
description: Design patterns for Spring Boot - the Spring form of the classic patterns (Factory, Builder, Strategy, Observer, Decorator, Adapter) and full examples of Transactional Outbox, Saga and CQRS. Use when designing extensible components or consistency between services.
when_to_use: 'Implementing a named pattern; designing extensible components; replacing rigid conditionals or inheritance with a pattern; dual writes or distributed transactions between services.'
---

# Design Patterns Skill

Use a pattern only when it removes a concrete problem in the code; a plain class or `new` is the default. In Spring, the container already provides most classic patterns:

| Pattern | Use when | Spring form |
|---------|----------|-------------|
| **Builder** | Many optional parameters | Lombok `@Builder`; on entities only on a constructor (`references/lombok.md` in the `java-modern` skill) |
| **Factory** | The implementation is chosen at runtime | Inject `List<Sender>` and index it in a `Map<String, Sender>` by a key method; no `switch` over types |
| **Strategy** | Several algorithms for one operation | One `@Component` per strategy behind an interface, selected the same way as the Factory; a lambda for single-method strategies |
| **Observer** | Other parts react to a state change | `ApplicationEventPublisher` with `@EventListener`; `@TransactionalEventListener` to react only after commit; `@Async` needs `@EnableAsync` |
| **Decorator** | Cross-cutting behavior (caching, retries, metrics) | `@Cacheable`, `@Retryable` (`cloud.md` in the `spring-boot` skill) or an aspect; a hand-written wrapper bean marked `@Primary` only when no annotation fits |
| **Adapter** | A third-party or legacy API doesn't fit the domain | A `@Component` that implements the domain interface and calls the client (`RestClient`) |
| **Outbox** | A DB update and an event must happen together | Below |
| **Saga** | One business process spans several services | Below |
| **CQRS** | Reads and writes need different models or scaling | Below |

## Enterprise / Microservices Patterns

### Transactional Outbox
**Problem:** Atomically update database AND publish an event (dual-write problem)

```java
// ✅ Outbox pattern - write event to DB in same transaction, poll and publish later
@Entity
@Table(name = "outbox_events")
@Getter
@Setter
public class OutboxEvent {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Setter(AccessLevel.NONE)
    private Long id;

    private String topic;
    private String aggregateId;              // Kafka key: one order's events stay in order
    private String eventType;

    @Column(columnDefinition = "TEXT")
    private String payload;

    private LocalDateTime createdAt;
    private boolean published;
}

public record OrderCreatedEvent(Long orderId, BigDecimal amount) {}

@Service
@RequiredArgsConstructor
public class OrderService {
    private final OrderRepository orderRepository;
    private final OutboxEventRepository outboxRepository;
    private final JsonMapper jsonMapper;

    @Transactional
    public Order createOrder(OrderRequest request) {
        Order order = new Order();
        order.setStatus(OrderStatus.PENDING);
        order.setTotalAmount(request.getAmount());
        order = orderRepository.save(order);

        OutboxEvent event = new OutboxEvent();
        event.setTopic("order-events");
        event.setAggregateId(order.getId().toString());
        event.setEventType("OrderCreated");
        event.setPayload(jsonMapper.writeValueAsString(new OrderCreatedEvent(order.getId(), order.getTotalAmount())));
        event.setCreatedAt(LocalDateTime.now());
        outboxRepository.save(event);
        return order;
    }
}

public interface OutboxEventRepository extends JpaRepository<OutboxEvent, Long> {
    // SKIP LOCKED (PostgreSQL, MySQL 8): each pod claims a different batch
    @Query(value = """
        SELECT * FROM outbox_events WHERE published = false
        ORDER BY id LIMIT :limit FOR UPDATE SKIP LOCKED
        """, nativeQuery = true)
    List<OutboxEvent> lockUnpublished(int limit);
}

// Poller publishes events and marks them as published; needs @EnableScheduling on a @Configuration class
@Component
@RequiredArgsConstructor
public class OutboxPoller {
    private final OutboxEventRepository outboxRepository;
    private final KafkaTemplate<String, String> kafka;

    @Scheduled(fixedDelay = 1000)
    @Transactional
    public void publishPendingEvents() {
        for (OutboxEvent event : outboxRepository.lockUnpublished(100)) {
            // wait for the broker; a failure rolls back the batch, which goes again (at-least-once)
            kafka.send(event.getTopic(), event.getAggregateId(), event.getPayload()).join();
            event.setPublished(true);
        }
    }
}
```

### Saga (Choreography)
**Problem:** Distributed transaction across multiple microservices

```java
// ✅ Choreography-based saga - each service listens and reacts
// Order Service: createOrder (Outbox above) saves a PENDING order and sends OrderCreatedEvent to "order-events"
@Transactional
public void handlePaymentFailed(Long orderId) {                  // compensating action in OrderService
    Order order = orderRepository.findById(orderId).orElseThrow();
    order.setStatus(OrderStatus.CANCELLED);
}

// Payment Service listens to OrderCreated, publishes PaymentCompleted or PaymentFailed
@Component
@RequiredArgsConstructor
public class PaymentEventHandler {
    private final PaymentService paymentService;

    @KafkaListener(topics = "order-events")
    public void handleOrderCreated(OrderCreatedEvent event) {
        try {
            paymentService.charge(event.orderId(), event.amount());   // idempotent: the outbox may resend
            // Publish PaymentCompleted
        } catch (PaymentException e) {
            // Publish PaymentFailed → triggers compensating action
        }
    }
}

// The outbox sends JSON strings; without this bean the listener fails with "Cannot convert from [java.lang.String]"
@Bean
RecordMessageConverter messageConverter() {
    return new StringJacksonJsonMessageConverter();             // Jackson 3
}
```

**Choreography vs Orchestration:**
| Aspect | Choreography | Orchestration |
|--------|-------------|---------------|
| Coupling | Low - services react to events | Higher - orchestrator knows all steps |
| Complexity | Hard to trace full flow | Centralized, easier to understand |
| Use when | Few steps, simple flows | Many steps, complex compensation |

### CQRS (Command Query Responsibility Segregation)
**Problem:** Read and write models have different optimization needs

```java
// ✅ CQRS - separate command and query models

// Command side - normalized, validates business rules
@Service
@Transactional
@RequiredArgsConstructor
public class OrderCommandService {
    private final OrderRepository orderRepository;
    private final ApplicationEventPublisher eventPublisher;

    public Long createOrder(CreateOrderCommand command) {
        Order order = new Order();
        order.setCustomerId(command.customerId());
        order.setStatus(OrderStatus.CREATED);
        command.items().forEach(order::addItem);
        order = orderRepository.save(order);
        eventPublisher.publishEvent(new OrderCreatedEvent(order.getId(), order.getTotalAmount()));
        return order.getId();
    }
}

// Query side - denormalized, optimized for reads
@Service
@Transactional(readOnly = true)
@RequiredArgsConstructor
public class OrderQueryService {
    private final OrderViewRepository viewRepository;

    public OrderView findById(Long id) {
        return viewRepository.findById(id)
            .orElseThrow(() -> new ResourceNotFoundException("Order not found"));
    }

    public Page<OrderView> findByCustomer(Long customerId, Pageable pageable) {
        return viewRepository.findByCustomerId(customerId, pageable);
    }
}

// Read model - flat, pre-joined
@Entity
@Table(name = "order_views")
@Getter
@Setter                       // id is copied from the order, not generated, so it keeps a setter
public class OrderView {
    @Id
    private Long id;
    private Long customerId;
    private String customerName;
    private String status;
    private BigDecimal totalAmount;
    private int itemCount;
    private LocalDateTime createdAt;
}

// Projection updater - runs after the command commits, so a failure here can't roll back the order
@Component
@RequiredArgsConstructor
public class OrderViewUpdater {
    private final OrderRepository orderRepository;
    private final OrderViewRepository viewRepository;

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    @Transactional(propagation = Propagation.REQUIRES_NEW)      // the command's transaction is already over
    public void on(OrderCreatedEvent event) {
        Order order = orderRepository.findById(event.orderId()).orElseThrow();
        OrderView view = new OrderView();
        view.setId(order.getId());
        view.setCustomerId(order.getCustomerId());
        view.setStatus(order.getStatus().name());
        view.setTotalAmount(order.getTotalAmount());
        view.setItemCount(order.getItems().size());
        view.setCreatedAt(order.getCreatedAt());
        viewRepository.save(view);
    }
}
```

**When to use CQRS:**
- Read/write ratio is heavily skewed (many reads, few writes)
- Read model needs different shape than write model (denormalized views)
- Different scaling requirements for reads vs writes

**When NOT to use:** Simple CRUD applications - adds unnecessary complexity.

## Anti-Patterns to Avoid

| Anti-Pattern | Problem | Better Approach |
|--------------|---------|-----------------|
| Singleton abuse | Global state, hard to test | Dependency Injection |
| Factory everywhere | Over-engineering | Simple `new` if type known |
| Deep decorator chains | Hard to debug | Composition, keep chains short |
| CQRS for simple CRUD | Unnecessary complexity | Single model, standard repository |
| Saga without idempotency | Duplicate processing | Idempotent consumers + dedup key |
