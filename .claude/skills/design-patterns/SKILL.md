---
name: design-patterns
description: Design patterns with Java examples - classic (Factory, Builder, Strategy, Observer, Decorator, Adapter) and enterprise/microservices (Saga, Outbox, CQRS). Use when user asks about patterns, designing extensible components, or distributed transaction strategies.
---

# Design Patterns Skill

Quick reference for common design patterns in Java.

## When to Use
- User asks to implement a specific pattern
- Designing extensible/flexible components
- Refactoring rigid code

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

---

## Creational Patterns

### Builder
**Problem:** Telescoping constructors, many optional parameters

```java
// ✅ Builder pattern
public class User {
    private final String name;  // required
    private final String email; // required
    private final int age;      // optional

    private User(Builder builder) {
        this.name = builder.name;
        this.email = builder.email;
        this.age = builder.age;
    }

    public static Builder builder(String name, String email) {
        return new Builder(name, email);
    }

    public static class Builder {
        private final String name;
        private final String email;
        private int age = 0;

        private Builder(String name, String email) {
            this.name = name;
            this.email = email;
        }

        public Builder age(int age) {
            this.age = age;
            return this;
        }

        public User build() {
            return new User(this);
        }
    }
}

// Usage
User user = User.builder("John", "john@example.com")
    .age(30)
    .build();
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

---

## Behavioral Patterns

### Strategy
**Problem:** Multiple algorithms for same operation, choose at runtime

```java
// ✅ Strategy pattern
public interface PaymentStrategy {
    void pay(BigDecimal amount);
}

public class CreditCardPayment implements PaymentStrategy {
    private final String cardNumber;

    public CreditCardPayment(String cardNumber) {
        this.cardNumber = cardNumber;
    }

    @Override
    public void pay(BigDecimal amount) {
        System.out.println("Paid " + amount + " with card " + cardNumber);
    }
}

public class ShoppingCart {
    private PaymentStrategy paymentStrategy;

    public void setPaymentStrategy(PaymentStrategy strategy) {
        this.paymentStrategy = strategy;
    }

    public void checkout(BigDecimal total) {
        paymentStrategy.pay(total);
    }
}

// Usage
cart.setPaymentStrategy(new CreditCardPayment("4111..."));
cart.checkout(new BigDecimal("99.99"));

// Functional variant (Java 8+)
@FunctionalInterface
public interface PaymentStrategy {
    void pay(BigDecimal amount);
}

PaymentStrategy creditCard = amount -> System.out.println("Card: " + amount);
cart.setPaymentStrategy(creditCard);
```

### Observer
**Problem:** Notify multiple objects when state changes

```java
// ✅ Spring Events (preferred)
public record OrderPlacedEvent(Order order) {}

@Service
public class OrderService {
    private final ApplicationEventPublisher eventPublisher;

    public void placeOrder(Order order) {
        saveOrder(order);
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
    @Async
    public void handleOrderPlaced(OrderPlacedEvent event) {
        // Send email
    }
}
```

---

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

public abstract class CoffeeDecorator implements Coffee {
    protected final Coffee coffee;
    public CoffeeDecorator(Coffee coffee) { this.coffee = coffee; }
}

public class MilkDecorator extends CoffeeDecorator {
    public MilkDecorator(Coffee coffee) { super(coffee); }

    public String getDescription() {
        return coffee.getDescription() + ", Milk";
    }

    public BigDecimal getCost() {
        return coffee.getCost().add(new BigDecimal("0.50"));
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
public class Mp3PlayerAdapter implements MediaPlayer {
    private final LegacyAudioPlayer legacyPlayer = new LegacyAudioPlayer();

    @Override
    public void play(String filename) {
        legacyPlayer.playMp3(filename);
    }
}

// Usage
MediaPlayer player = new Mp3PlayerAdapter();
player.play("song.mp3");
```

---

## Enterprise / Microservices Patterns

### Transactional Outbox
**Problem:** Atomically update database AND publish an event (dual-write problem)

```java
// ✅ Outbox pattern - write event to DB in same transaction, poll and publish later
@Entity
@Table(name = "outbox_events")
public class OutboxEvent {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String aggregateType;
    private String aggregateId;
    private String eventType;

    @Column(columnDefinition = "TEXT")
    private String payload;

    private LocalDateTime createdAt;
    private boolean published;

    // getters/setters
}

@Service
public class OrderService {
    private final OrderRepository orderRepository;
    private final OutboxEventRepository outboxRepository;

    public OrderService(OrderRepository orderRepository, OutboxEventRepository outboxRepository) {
        this.orderRepository = orderRepository;
        this.outboxRepository = outboxRepository;
    }

    @Transactional
    public Order createOrder(OrderRequest request) {
        Order order = new Order();
        order.setStatus(OrderStatus.CREATED);
        order = orderRepository.save(order);

        OutboxEvent event = new OutboxEvent();
        event.setAggregateType("Order");
        event.setAggregateId(order.getId().toString());
        event.setEventType("OrderCreated");
        event.setPayload(toJson(order));
        event.setCreatedAt(LocalDateTime.now());
        event.setPublished(false);
        outboxRepository.save(event);

        return order;
    }
}

// Poller publishes events and marks them as published
@Component
public class OutboxPoller {
    private final OutboxEventRepository outboxRepository;
    private final KafkaTemplate<String, String> kafka;

    public OutboxPoller(OutboxEventRepository outboxRepository,
                        KafkaTemplate<String, String> kafka) {
        this.outboxRepository = outboxRepository;
        this.kafka = kafka;
    }

    @Scheduled(fixedDelay = 1000)
    @Transactional
    public void publishPendingEvents() {
        List<OutboxEvent> events = outboxRepository.findByPublishedFalse();
        for (OutboxEvent event : events) {
            kafka.send(event.getAggregateType(), event.getAggregateId(), event.getPayload());
            event.setPublished(true);
        }
    }
}
```

### Saga (Choreography)
**Problem:** Distributed transaction across multiple microservices

```java
// ✅ Choreography-based saga - each service listens and reacts
// Order Service publishes OrderCreated
@Service
public class OrderService {
    private final ApplicationEventPublisher eventPublisher;
    private final OrderRepository orderRepository;

    public OrderService(ApplicationEventPublisher eventPublisher, OrderRepository orderRepository) {
        this.eventPublisher = eventPublisher;
        this.orderRepository = orderRepository;
    }

    @Transactional
    public Order createOrder(OrderRequest request) {
        Order order = new Order();
        order.setStatus(OrderStatus.PENDING);
        order = orderRepository.save(order);
        eventPublisher.publishEvent(new OrderCreatedEvent(order.getId(), request.items()));
        return order;
    }

    @Transactional
    public void handlePaymentFailed(Long orderId) {
        Order order = orderRepository.findById(orderId).orElseThrow();
        order.setStatus(OrderStatus.CANCELLED);
        orderRepository.save(order);
    }
}

// Payment Service listens to OrderCreated, publishes PaymentCompleted or PaymentFailed
@Component
public class PaymentEventHandler {
    private final PaymentService paymentService;

    public PaymentEventHandler(PaymentService paymentService) {
        this.paymentService = paymentService;
    }

    @KafkaListener(topics = "order-events")
    public void handleOrderCreated(OrderCreatedEvent event) {
        try {
            paymentService.charge(event.orderId(), event.amount());
            // Publish PaymentCompleted
        } catch (PaymentException e) {
            // Publish PaymentFailed → triggers compensating action
        }
    }
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
public class OrderCommandService {
    private final OrderRepository orderRepository;
    private final ApplicationEventPublisher eventPublisher;

    public OrderCommandService(OrderRepository orderRepository,
                                ApplicationEventPublisher eventPublisher) {
        this.orderRepository = orderRepository;
        this.eventPublisher = eventPublisher;
    }

    public Long createOrder(CreateOrderCommand command) {
        Order order = new Order();
        order.setCustomerId(command.customerId());
        order.setStatus(OrderStatus.CREATED);
        command.items().forEach(order::addItem);
        order = orderRepository.save(order);
        eventPublisher.publishEvent(new OrderCreatedEvent(order));
        return order.getId();
    }
}

// Query side - denormalized, optimized for reads
@Service
@Transactional(readOnly = true)
public class OrderQueryService {
    private final OrderViewRepository viewRepository;

    public OrderQueryService(OrderViewRepository viewRepository) {
        this.viewRepository = viewRepository;
    }

    public OrderView findById(Long id) {
        return viewRepository.findById(id)
            .orElseThrow(() -> new EntityNotFoundException("Order not found"));
    }

    public Page<OrderView> findByCustomer(Long customerId, Pageable pageable) {
        return viewRepository.findByCustomerId(customerId, pageable);
    }
}

// Read model - flat, pre-joined
@Entity
@Table(name = "order_views")
public class OrderView {
    @Id
    private Long id;
    private Long customerId;
    private String customerName;
    private String status;
    private BigDecimal totalAmount;
    private int itemCount;
    private LocalDateTime createdAt;

    // getters/setters
}

// Projection updater - keeps query model in sync
@Component
public class OrderViewUpdater {

    private final OrderViewRepository viewRepository;

    public OrderViewUpdater(OrderViewRepository viewRepository) {
        this.viewRepository = viewRepository;
    }

    @EventListener
    public void on(OrderCreatedEvent event) {
        OrderView view = new OrderView();
        view.setId(event.order().getId());
        view.setCustomerId(event.order().getCustomerId());
        view.setStatus(event.order().getStatus().name());
        view.setTotalAmount(event.order().getTotalAmount());
        view.setItemCount(event.order().getItems().size());
        view.setCreatedAt(event.order().getCreatedAt());
        viewRepository.save(view);
    }
}
```

**When to use CQRS:**
- Read/write ratio is heavily skewed (many reads, few writes)
- Read model needs different shape than write model (denormalized views)
- Different scaling requirements for reads vs writes

**When NOT to use:** Simple CRUD applications - adds unnecessary complexity.

---

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
