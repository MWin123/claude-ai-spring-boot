# Cloud Native - Spring Cloud

## Setup

Spring Cloud starters take their versions from the `spring-cloud-dependencies` BOM, whose release train must match the Boot version: 2025.1.x for Boot 4.0 and 4.1. Initializr adds it with the first Spring Cloud starter.

```xml
<properties>
    <spring-cloud.version>2025.1.4</spring-cloud.version>
</properties>
<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-dependencies</artifactId>
            <version>${spring-cloud.version}</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>
```

Gradle: `implementation(platform("org.springframework.cloud:spring-cloud-dependencies:2025.1.4"))`.

## Spring Cloud Config Server

```java
@SpringBootApplication
@EnableConfigServer   // spring-cloud-config-server
public class ConfigServerApplication {
    public static void main(String[] args) {
        SpringApplication.run(ConfigServerApplication.class, args);
    }
}
```

```yaml
# application.yml (Config Server)
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
```

```yaml
# application.yml (Config Client, spring-cloud-starter-config)
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
@ConfigurationProperties("app.feature")   // registered by @ConfigurationPropertiesScan
@Getter
@Setter   // a refresh re-binds through the setters; a record keeps its startup values
public class FeatureProperties {
    private boolean enabled;
    private int maxConnections = 100;
}

// Inject FeatureProperties into services. POST /actuator/refresh (add refresh to
// management.endpoints.web.exposure.include) re-binds it with the new values; no @RefreshScope needed
```

## Service Discovery - Eureka

```java
// Eureka Server (spring-cloud-starter-netflix-eureka-server)
@SpringBootApplication
@EnableEurekaServer
public class EurekaServerApplication {
    public static void main(String[] args) {
        SpringApplication.run(EurekaServerApplication.class, args);
    }
}

// Eureka Client (spring-cloud-starter-netflix-eureka-client)
@SpringBootApplication
@EnableDiscoveryClient
public class UserServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(UserServiceApplication.class, args);
    }
}
```

```yaml
# application.yml (Eureka Server)
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
```

```yaml
# application.yml (Eureka Client)
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

`spring-cloud-starter-gateway-server-webflux`; the `circuitBreaker` filter needs `spring-cloud-starter-circuitbreaker-reactor-resilience4j`, `RedisRateLimiter` needs `spring-boot-starter-data-redis-reactive`.

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
```

```yaml
# application.yml (Gateway)
spring:
  cloud:
    gateway:
      server:
        webflux:
          discovery:
            locator:
              enabled: true
              lower-case-service-id: true
          default-filters:
            - DedupeResponseHeader=Access-Control-Allow-Origin
          globalcors:
            cors-configurations:
              '[/**]':
                allowed-origins: ${CORS_ALLOWED_ORIGINS}   # e.g. https://app.example.com; never "*"
                allowed-methods: [GET, POST, PUT, DELETE]
                allowed-headers: "*"
```

## Circuit Breaker - Spring Cloud CircuitBreaker

`spring-cloud-starter-circuitbreaker-resilience4j` (Initializr: "Resilience4J"). Resilience4j's own annotations (`@CircuitBreaker(name = …)`, `@Retry`, `@RateLimiter`) need `resilience4j-spring-boot3`, which refuses to start on Boot 4.

```java
@Service
@Slf4j
public class ExternalApiService {
    private final RestClient restClient;
    private final CircuitBreaker circuitBreaker;   // org.springframework.cloud.client.circuitbreaker

    public ExternalApiService(RestClient.Builder builder, CircuitBreakerFactory<?, ?> circuitBreakers) {
        this.restClient = builder.baseUrl("https://api.external.com").build();
        this.circuitBreaker = circuitBreakers.create("externalApi");   // settings: resilience4j.*.instances.externalApi
    }

    public ExternalData getData(String id) {
        return circuitBreaker.run(
            () -> restClient.get().uri("/data/{id}", id).retrieve().body(ExternalData.class),
            e -> {   // failed call, timeout or open circuit
                log.warn("Fallback triggered for id: {}, error: {}", id, e.getMessage());
                return new ExternalData(id, "Fallback data", LocalDateTime.now());
            });
    }
}
```

```yaml
# application.yml
resilience4j:
  circuitbreaker:
    instances:
      externalApi:
        sliding-window-size: 10
        minimum-number-of-calls: 5
        permitted-number-of-calls-in-half-open-state: 3
        automatic-transition-from-open-to-half-open-enabled: true
        wait-duration-in-open-state: 5s
        failure-rate-threshold: 50
  timelimiter:
    instances:
      externalApi:
        timeout-duration: 5s   # default 1s: slower calls count as failures
spring:
  cloud:
    circuitbreaker:
      http-services:
        enabled: false   # else every @ImportHttpServices group gets a breaker with the 1 s default time limit
```

Retries and concurrency limits are built into Spring Framework 7, without a library:

```java
@Configuration
@EnableResilientMethods
class ResilienceConfig {
}

@Service
@RequiredArgsConstructor
public class InventoryClient {
    private final InventoryApi inventoryApi;   // @HttpExchange client (boot4.md)

    @Retryable(includes = ResourceAccessException.class, maxRetries = 3, delay = 1000, multiplier = 2)   // I/O errors, not 4xx
    @ConcurrencyLimit(10)   // callers beyond 10 wait
    public Stock getStock(String sku) {
        return inventoryApi.getStock(sku);
    }
}
```

## Distributed Tracing - Micrometer + OpenTelemetry

### OTLP Exporter (Preferred)

```yaml
# application.yml - OpenTelemetry Protocol (recommended over Zipkin)
management:
  tracing:
    sampling:
      probability: 1.0
  opentelemetry:
    tracing:
      export:
        otlp:
          endpoint: http://localhost:4318/v1/traces
```

```xml
<!-- pom.xml: Micrometer Tracing with the OpenTelemetry bridge and the OTLP exporter -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-opentelemetry</artifactId>
</dependency>
```

### Zipkin Exporter (Alternative)

`spring-boot-starter-zipkin` (Brave) instead of the OpenTelemetry starter:

```yaml
management:
  tracing:
    sampling:
      probability: 1.0
    export:
      zipkin:
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
class LoadBalancerConfiguration {
}

// No @Configuration: as a scanned bean it would apply to every client
class UserServiceLoadBalancerConfig {

    @Bean
    ReactorLoadBalancer<ServiceInstance> randomLoadBalancer(Environment environment,
            LoadBalancerClientFactory clientFactory) {
        String name = environment.getProperty(LoadBalancerClientFactory.PROPERTY_NAME);   // "user-service"
        return new RandomLoadBalancer(clientFactory.getLazyProvider(name, ServiceInstanceListSupplier.class), name);
    }
}

// Without a base-url, a group gets http://<group name> and is load-balanced
@Configuration
@ImportHttpServices(group = "user-service", types = UserClient.class)
class UserClientConfig {
}
```

`UserClient` is the `@HttpExchange` interface from `boot4.md`. A hand-built `RestClient` resolves `http://user-service` only through a `@LoadBalanced RestClient.Builder` bean.

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

## HTTP Interface Clients

Declarative clients (`@HttpExchange` interfaces registered with `@ImportHttpServices`, no `HttpServiceProxyFactory`) are in "Declarative HTTP Clients: @ImportHttpServices" in `boot4.md`; load-balanced groups are in "Load Balancing with Spring Cloud LoadBalancer" above.

## GraalVM Native Image

```xml
<!-- pom.xml: the Boot parent already has the native profile; add the plugin -->
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
| **Circuit Breaker** | Fault tolerance and fallbacks (Spring Cloud CircuitBreaker); retries and limits in Spring Framework 7 |
| **Load Balancer** | Client-side load balancing |
| **Tracing (OTLP)** | Distributed tracing with OpenTelemetry |
| **Actuator** | Production-ready monitoring and management |
| **Virtual Threads** | High-throughput blocking I/O without WebFlux |
| **HTTP Interfaces** | Declarative HTTP clients (replaces Feign) |
| **Native Image** | Fast startup, low memory with GraalVM |
| **SSL Bundles** | Unified SSL config with hot reload (see security reference) |

Container images, Kubernetes manifests (including Config Tree and cert-manager), Helm charts and Skaffold are in the `deployment` skill.
