---
name: design-patterns
description: Design patterns with Java examples - classic (Factory, Builder, Strategy, Observer, Decorator, Adapter) and enterprise/microservices (Saga, Outbox, CQRS). Use when user asks about patterns, designing extensible components, or distributed transaction strategies.
when_to_use: 'Implementing a named pattern; designing extensible components; refactoring rigid code; dual writes or distributed transactions between services.'
---

# Design Patterns Skill

Quick reference for common design patterns in Java.

## Quick Reference: When to Use What

| Problem | Pattern | Use When |
|---------|---------|----------|
| Complex object construction | **Builder** | Many parameters, some optional |
| Create objects without specifying class | **Factory** | Type determined at runtime |
| Multiple algorithms, swap at runtime | **Strategy** | Behavior varies by context |
| Add behavior without changing class | **Decorator** | Dynamic composition needed |
| Notify multiple objects of changes | **Observer** | One-to-many dependency |
| Convert incompatible interfaces | **Adapter** | Integrate legacy/3rd party code |
| DB update + event publish atomically | **Outbox** | Dual-write problem in microservices |
| Distributed transaction across services | **Saga** | Multi-service business process |
| Separate read/write models | **CQRS** | Heavy read/write ratio skew |

## Creational Patterns

### Builder
**Problem:** Telescoping constructors, many optional parameters

```java
// ✅ Many optional parameters: Lombok @Builder works on records
@Builder
public record SearchCriteria(String name, String email, Integer minAge, Integer maxAge) { }

SearchCriteria criteria = SearchCriteria.builder().name("John").minAge(18).build();

// ✅ Few optional parameters: record with compact constructor + static factory (no builder needed)
public record User(String name, String email, int age) {
    public User {                                   // validation in compact constructor
        Objects.requireNonNull(name);
        Objects.requireNonNull(email);
    }

    public static User of(String name, String email) {
        return new User(name, email, 0);             // default for optional field
    }

    public User withAge(int age) {                   // "wither" for a single optional field
        return new User(name, email, age);
    }
}

User user = User.of("John", "john@example.com").withAge(30);
```

### Factory
**Problem:** Create objects without knowing exact class upfront

```java
// ✅ Factory pattern
public interface Notification {
    void send(String message);
}

public class NotificationFactory {
    public static Notification create(String type) {
        return switch (type.toUpperCase()) {
            case "EMAIL" -> new EmailNotification();
            case "SMS" -> new SmsNotification();
            case "PUSH" -> new PushNotification();
            default -> throw new IllegalArgumentException("Unknown: " + type);
        };
    }
}

// Spring version - preferred
@Component
public class NotificationFactory {
    private final Map<String, NotificationSender> senders;

    public NotificationFactory(List<NotificationSender> senderList) {
        this.senders = senderList.stream()
            .collect(Collectors.toMap(
                NotificationSender::getType,
                Function.identity()
            ));
    }

    public NotificationSender get(String type) {
        return Optional.ofNullable(senders.get(type))
            .orElseThrow(() -> new IllegalArgumentException("Unknown: " + type));
    }
}
```

## Behavioral Patterns

### Strategy
**Problem:** Multiple algorithms for same operation, choose at runtime

```java
// ✅ Strategy pattern
public interface PaymentStrategy {
    void pay(BigDecimal amount);
}

public record CreditCardPayment(String cardNumber) implements PaymentStrategy {
    @Override
    public void pay(BigDecimal amount) {
        System.out.println("Paid " + amount + " with " + this);
    }

    // records print all components; never log a full card number
    @Override
    public String toString() {
        String last4 = cardNumber == null || cardNumber.length() < 4
            ? "" : cardNumber.substring(cardNumber.length() - 4);
        return "CreditCardPayment[****" + last4 + "]";
    }
}

@Setter
public class ShoppingCart {
    private PaymentStrategy paymentStrategy;

    public void checkout(BigDecimal total) {
        paymentStrategy.pay(total);
    }
}

// Usage
cart.setPaymentStrategy(new CreditCardPayment("4111..."));
cart.checkout(new BigDecimal("99.99"));

// Functional variant: PaymentStrategy has one method (mark it @FunctionalInterface), so a lambda implements it
PaymentStrategy creditCard = amount -> System.out.println("Card: " + amount);
cart.setPaymentStrategy(creditCard);
```

### Observer
**Problem:** Notify multiple objects when state changes

```java
// ✅ Spring Events (preferred)
public record OrderPlacedEvent(Order order) {}

@Service
@RequiredArgsConstructor
public class OrderService {
    private final OrderRepository orderRepository;
    private final ApplicationEventPublisher eventPublisher;

    public void placeOrder(Order order) {
        orderRepository.save(order);
        eventPublisher.publishEvent(new OrderPlacedEvent(order));
    }
}

@Component
public class InventoryListener {
    @EventListener
    public void handleOrderPlaced(OrderPlacedEvent event) {
        // Reduce inventory
    }
}

@Component
public class EmailListener {
    @EventListener
    @Async                    // needs @EnableAsync on a @Configuration class, or it runs on the caller's thread
    public void handleOrderPlaced(OrderPlacedEvent event) {
        // Send email
    }
}
```

## Structural Patterns

### Decorator
**Problem:** Add behavior dynamically without modifying class

```java
// ✅ Decorator pattern
public interface Coffee {
    String getDescription();
    BigDecimal getCost();
}

public class SimpleCoffee implements Coffee {
    public String getDescription() { return "Coffee"; }
    public BigDecimal getCost() { return new BigDecimal("2.00"); }
}

// Decorators as records: the wrapped coffee is the only state
public record MilkDecorator(Coffee coffee) implements Coffee {
    public String getDescription() {
        return coffee.getDescription() + ", Milk";
    }

    public BigDecimal getCost() {
        return coffee.getCost().add(new BigDecimal("0.50"));
    }
}

public record SugarDecorator(Coffee coffee) implements Coffee {
    public String getDescription() {
        return coffee.getDescription() + ", Sugar";
    }

    public BigDecimal getCost() {
        return coffee.getCost().add(new BigDecimal("0.20"));
    }
}

// Usage
Coffee coffee = new SimpleCoffee();
coffee = new MilkDecorator(coffee);
coffee = new SugarDecorator(coffee);
```

### Adapter
**Problem:** Make incompatible interfaces work together

```java
// ✅ Adapter pattern
public interface MediaPlayer {
    void play(String filename);
}

// Legacy code
public class LegacyAudioPlayer {
    public void playMp3(String filename) { /* ... */ }
}

// Adapter
public record Mp3PlayerAdapter(LegacyAudioPlayer legacyPlayer) implements MediaPlayer {
    @Override
    public void play(String filename) {
        legacyPlayer.playMp3(filename);
    }
}

// Usage
MediaPlayer player = new Mp3PlayerAdapter(new LegacyAudioPlayer());
player.play("song.mp3");
```

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
        order.setTotalAmount(request.amount());
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

## Pattern Selection Guide

| Situation | Pattern |
|-----------|---------|
| Object creation is complex | Builder, Factory |
| Need to add features dynamically | Decorator |
| Multiple implementations of algorithm | Strategy |
| React to state changes | Observer (Spring Events) |
| Integrate with legacy code | Adapter |
| Update DB + publish event atomically | Outbox |
| Distributed transaction across services | Saga |
| Separate read/write optimization | CQRS |

## Anti-Patterns to Avoid

| Anti-Pattern | Problem | Better Approach |
|--------------|---------|-----------------|
| Singleton abuse | Global state, hard to test | Dependency Injection |
| Factory everywhere | Over-engineering | Simple `new` if type known |
| Deep decorator chains | Hard to debug | Composition, keep chains short |
| CQRS for simple CRUD | Unnecessary complexity | Single model, standard repository |
| Saga without idempotency | Duplicate processing | Idempotent consumers + dedup key |
