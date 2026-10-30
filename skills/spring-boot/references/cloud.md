# Cloud Native - Spring Cloud

## Spring Cloud Config Server

```java
// Config Server
@SpringBootApplication
@EnableConfigServer
public class ConfigServerApplication {
    public static void main(String[] args) {
        SpringApplication.run(ConfigServerApplication.class, args);
    }
}

// application.yml
server:
  port: 8888

spring:
  cloud:
    config:
      server:
        git:
          uri: https://github.com/example/config-repo
          default-label: main
          search-paths: '{application}'
          # credentials: configure via environment variables
        native:
          search-locations: classpath:/config

// Config Client
@SpringBootApplication
public class ClientApplication {
    public static void main(String[] args) {
        SpringApplication.run(ClientApplication.class, args);
    }
}

// application.yml (Config Client)
spring:
  application:
    name: user-service
  config:
    import: "configserver:http://localhost:8888"
  cloud:
    config:
      # credentials: configure via environment variables
      fail-fast: true
      retry:
        max-attempts: 6
        initial-interval: 1000
```

## Dynamic Configuration Refresh

```java
@Component
@RefreshScope   // recreated with the new values on the next call after a refresh
public class FeatureFlags {
    @Value("${app.feature.enabled:false}")
    private boolean featureEnabled;

    @Value("${app.max-connections:100}")
    private int maxConnections;

    public boolean featureEnabled() { return featureEnabled; }
    public int maxConnections() { return maxConnections; }
}

// Inject FeatureFlags into services; refresh via the Actuator endpoint:
// POST /actuator/refresh
```

## Service Discovery - Eureka

```java
// Eureka Server
@SpringBootApplication
@EnableEurekaServer
public class EurekaServerApplication {
    public static void main(String[] args) {
        SpringApplication.run(EurekaServerApplication.class, args);
    }
}

// application.yml (Eureka Server)
server:
  port: 8761

eureka:
  instance:
    hostname: localhost
  client:
    register-with-eureka: false
    fetch-registry: false
    service-url:
      defaultZone: http://${eureka.instance.hostname}:${server.port}/eureka/

// Eureka Client
@SpringBootApplication
@EnableDiscoveryClient
public class UserServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(UserServiceApplication.class, args);
    }
}

// application.yml (Eureka Client)
spring:
  application:
    name: user-service

eureka:
  client:
    service-url:
      defaultZone: http://localhost:8761/eureka/
    registry-fetch-interval-seconds: 5
  instance:
    prefer-ip-address: true
    lease-renewal-interval-in-seconds: 10
    lease-expiration-duration-in-seconds: 30
```

## Spring Cloud Gateway

```java
@SpringBootApplication
public class GatewayApplication {
    public static void main(String[] args) {
        SpringApplication.run(GatewayApplication.class, args);
    }

    @Bean
    public RouteLocator customRouteLocator(RouteLocatorBuilder builder) {
        return builder.routes()
            .route("user-service", r -> r
                .path("/api/users/**")
                .filters(f -> f
                    .rewritePath("/api/users/(?<segment>.*)", "/users/${segment}")
                    .addRequestHeader("X-Gateway", "Spring-Cloud-Gateway")
                    .circuitBreaker(config -> config
                        .setName("userServiceCircuitBreaker")
                        .setFallbackUri("forward:/fallback/users")
                    )
                    .retry(config -> config
                        .setRetries(3)
                        .setStatuses(HttpStatus.SERVICE_UNAVAILABLE)
                    )
                )
                .uri("lb://user-service")
            )
            .route("order-service", r -> r
                .path("/api/orders/**")
                .filters(f -> f
                    .rewritePath("/api/orders/(?<segment>.*)", "/orders/${segment}")
                    .requestRateLimiter(config -> config
                        .setRateLimiter(redisRateLimiter())
                        .setKeyResolver(userKeyResolver())
                    )
                )
                .uri("lb://order-service")
            )
            .build();
    }

    @Bean
    public RedisRateLimiter redisRateLimiter() {
        return new RedisRateLimiter(10, 20); // replenishRate, burstCapacity
    }

    @Bean
    public KeyResolver userKeyResolver() {
        return exchange -> Mono.justOrEmpty(
            exchange.getRequest().getHeaders().getFirst("X-User-Id")
        ).defaultIfEmpty("anonymous");
    }
}

// application.yml (Gateway)
spring:
  cloud:
    gateway:
      discovery:
        locator:
          enabled: true
          lower-case-service-id: true
      default-filters:
        - DedupeResponseHeader=Access-Control-Allow-Origin
      globalcors:
        cors-configurations:
          '[/**]':
            allowed-origins: "*"
            allowed-methods:
              - GET
              - POST
              - PUT
              - DELETE
            allowed-headers: "*"
```

## Circuit Breaker - Resilience4j

```java
@Service
@Slf4j
public class ExternalApiService {
    private final RestClient restClient;

    public ExternalApiService(RestClient.Builder builder) {
        this.restClient = builder
            .baseUrl("https://api.external.com")
            .build();
    }

    @CircuitBreaker(name = "externalApi", fallbackMethod = "getFallbackData")
    @Retry(name = "externalApi")
    @RateLimiter(name = "externalApi")
    public ExternalData getData(String id) {
        return restClient
            .get()
            .uri("/data/{id}", id)
            .retrieve()
            .body(ExternalData.class);
    }

    private ExternalData getFallbackData(String id, Exception e) {
        log.warn("Fallback triggered for id: {}, error: {}", id, e.getMessage());
        return new ExternalData(id, "Fallback data", LocalDateTime.now());
    }
}

// application.yml
resilience4j:
  circuitbreaker:
    instances:
      externalApi:
        register-health-indicator: true
        sliding-window-size: 10
        minimum-number-of-calls: 5
        permitted-number-of-calls-in-half-open-state: 3
        automatic-transition-from-open-to-half-open-enabled: true
        wait-duration-in-open-state: 5s
        failure-rate-threshold: 50
        event-consumer-buffer-size: 10

  retry:
    instances:
      externalApi:
        max-attempts: 3
        wait-duration: 1s
        enable-exponential-backoff: true
        exponential-backoff-multiplier: 2

  ratelimiter:
    instances:
      externalApi:
        limit-for-period: 10
        limit-refresh-period: 1s
        timeout-duration: 0s
```

## Distributed Tracing - Micrometer + OpenTelemetry

### OTLP Exporter (Preferred)

```yaml
# application.yml - OpenTelemetry Protocol (recommended over Zipkin)
management:
  tracing:
    sampling:
      probability: 1.0
  otlp:
    tracing:
      endpoint: http://localhost:4318/v1/traces

logging:
  pattern:
    level: "%5p [${spring.application.name:},%X{traceId:-},%X{spanId:-}]"
```

```xml
<!-- pom.xml -->
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-tracing-bridge-otel</artifactId>
</dependency>
<dependency>
    <groupId>io.opentelemetry</groupId>
    <artifactId>opentelemetry-exporter-otlp</artifactId>
</dependency>
```

### Zipkin Exporter (Alternative)

```yaml
management:
  tracing:
    sampling:
      probability: 1.0
  zipkin:
    tracing:
      endpoint: http://localhost:9411/api/v2/spans
```

### Custom Spans with Observation API

```java
@Service
@RequiredArgsConstructor
public class OrderService {
    private final ObservationRegistry observationRegistry;
    private final OrderRepository orderRepository;

    public Order processOrder(OrderRequest request) {
        return Observation.createNotStarted("order.process", observationRegistry)
            .lowCardinalityKeyValue("order.type", request.type())
            .observe(() -> {
                Order order = createOrder(request);
                return order;
            });
    }
}
```

## Load Balancing with Spring Cloud LoadBalancer

```java
@Configuration
@LoadBalancerClient(name = "user-service", configuration = UserServiceLoadBalancerConfig.class)
public class LoadBalancerConfiguration {
}

@Configuration
public class UserServiceLoadBalancerConfig {

    @Bean
    public ReactorLoadBalancer<ServiceInstance> randomLoadBalancer(
            LoadBalancerClientFactory clientFactory,
            ObjectProvider<LoadBalancerProperties> properties) {
        return new RandomLoadBalancer(
            clientFactory.getLazyProvider("user-service", ServiceInstanceListSupplier.class),
            "user-service"
        );
    }
}

@Service
public class UserClientService {
    private final RestClient restClient;

    public UserClientService(RestClient.Builder builder) {
        this.restClient = builder
            .baseUrl("http://user-service")
            .build();
    }

    public User getUser(Long id) {
        return restClient
            .get()
            .uri("/users/{id}", id)
            .retrieve()
            .body(User.class);
    }
}
```

## Health Checks, Actuator & Prometheus

```xml
<!-- pom.xml - Prometheus metrics endpoint -->
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-registry-prometheus</artifactId>
</dependency>
```

```yaml
# application.yml
management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus
  endpoint:
    health:
      show-details: when-authorized
      probes:
        enabled: true
  health:
    livenessState:
      enabled: true
    readinessState:
      enabled: true
  metrics:
    tags:
      application: ${spring.application.name}
```

```java
@Component
public class CustomHealthIndicator implements HealthIndicator {

    @Override
    public Health health() {
        boolean serviceUp = checkExternalService();

        if (serviceUp) {
            return Health.up()
                .withDetail("externalService", "Available")
                .withDetail("timestamp", LocalDateTime.now())
                .build();
        } else {
            return Health.down()
                .withDetail("externalService", "Unavailable")
                .withDetail("error", "Connection timeout")
                .build();
        }
    }

    private boolean checkExternalService() {
        // Check external dependency
        return true;
    }
}
```

## Virtual Threads

```yaml
# application.yml - one line enables virtual threads for all request handling
spring:
  threads:
    virtual:
      enabled: true
```

Virtual threads eliminate the need for WebFlux in most cases. With `spring.threads.virtual.enabled=true`:
- Tomcat handles each request on a virtual thread
- Blocking I/O (JDBC, RestClient, file I/O) no longer wastes platform threads
- `@Async` tasks run on virtual threads automatically
- No code changes required - existing blocking code scales like reactive

**When to still use WebFlux:** streaming responses, SSE, WebSocket, or when you need backpressure.

## HTTP Interface Clients (Spring 6+)

```java
// Declarative HTTP client - replaces OpenFeign
public interface UserClient {

    @GetExchange("/users/{id}")
    UserResponse getUser(@PathVariable Long id);

    @GetExchange("/users")
    List<UserResponse> getAllUsers();

    @PostExchange("/users")
    UserResponse createUser(@RequestBody UserCreateRequest request);
}

// Configuration
@Configuration
public class ClientConfig {

    @Bean
    public UserClient userClient(RestClient.Builder builder) {
        RestClient restClient = builder
            .baseUrl("http://user-service")
            .build();
        return HttpServiceProxyFactory
            .builderFor(RestClientAdapter.create(restClient))
            .build()
            .createClient(UserClient.class);
    }
}
```

## GraalVM Native Image

```xml
<!-- pom.xml - add native profile support -->
<parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>4.1.0</version>
</parent>

<plugin>
    <groupId>org.graalvm.buildtools</groupId>
    <artifactId>native-maven-plugin</artifactId>
</plugin>
```

```bash
# Build native image
./mvnw -Pnative native:compile

# Build native Docker image with Buildpacks
./mvnw -Pnative spring-boot:build-image
```

Gradle: apply the `org.graalvm.buildtools.native` plugin next to `org.springframework.boot`, then `./gradlew nativeCompile` builds the native executable and `./gradlew bootBuildImage` a native image.

Benefits: ~50ms startup, ~50MB RSS memory. Trade-offs: longer build time, reflection requires hints.

## Quick Reference

| Component | Purpose |
|-----------|---------|
| **Config Server** | Centralized configuration management |
| **Eureka** | Service discovery and registration |
| **Gateway** | API gateway with routing, filtering, load balancing |
| **Circuit Breaker** | Fault tolerance and fallback patterns |
| **Load Balancer** | Client-side load balancing |
| **Tracing (OTLP)** | Distributed tracing with OpenTelemetry |
| **Actuator** | Production-ready monitoring and management |
| **Virtual Threads** | High-throughput blocking I/O without WebFlux |
| **HTTP Interfaces** | Declarative HTTP clients (replaces Feign) |
| **Native Image** | Fast startup, low memory with GraalVM |
| **SSL Bundles** | Unified SSL config with hot reload (see security reference) |

Container images, Kubernetes manifests (including Config Tree and cert-manager), Helm charts and Skaffold are in the `deployment` skill.
