---
name: logging-patterns
description: Java logging best practices with SLF4J, structured logging (JSON), and MDC for request tracing. Use when adding or changing logging, or reading application logs.
when_to_use: '"add logging", "improve logs"; debugging from application logs; structured JSON logging; request tracing with correlation IDs.'
---

# Logging Patterns Skill

JSON is the default log format: production, CI/CD and Kubernetes log structured JSON (the default `application.yml` in the `conventions` skill sets `logging.structured.format.console: logstash`). Plain text is only for local development with the `human-logs` profile ("Profile-Based Switching").

## Log Fields

```json
{
  "timestamp": "2026-01-29T10:15:30.123Z",
  "level": "INFO",
  "logger": "com.example.OrderService",
  "message": "Order created",
  "requestId": "req-abc123",
  "traceId": "trace-xyz",
  "orderId": 12345,
  "userId": "user-789",
  "duration_ms": 45,
  "step": "payment_completed"
}
```

Log these fields so a request can be followed through the logs:
- `requestId` - groups all logs of one request (MDC, below)
- `step` - progress through a flow
- `duration_ms` - slow operations
- `level` - filter for errors

## Reading Logs

The console is JSON, one object per line, so filter it with `jq` instead of reading it raw:

```bash
# Locally: java -jar target/<app>.jar | jq ...
# Get recent errors
kubectl logs deploy/<app-name> | jq 'select(.level == "ERROR")' | tail -20

# Follow specific request
kubectl logs deploy/<app-name> | jq 'select(.requestId == "req-abc123")'

# Find slow operations
kubectl logs deploy/<app-name> | jq 'select(.duration_ms > 1000)'
```

## Quick Setup (Spring Boot 4.x)

### Native Structured Logging

Spring Boot 4.x has built-in JSON logging — no extra dependencies required.

```yaml
# application.yml (already in the conventions default)
logging:
  structured:
    format:
      console: logstash    # or "ecs" for Elastic Common Schema

# Supported formats:
#   logstash - JSON (most common, compatible with ELK and OpenTelemetry Collector)
#   ecs      - Elastic Common Schema (native Elastic/Kibana integration)
#   gelf     - Graylog Extended Log Format
```

### OpenTelemetry Integration

When Micrometer Tracing is on the classpath, `traceId` and `spanId` are automatically included in every JSON log line. This allows OTel Collector to correlate logs with distributed traces.

```yaml
# application.yml — with the JSON format above, traceId/spanId come from the MDC; logging.pattern.level has no effect
management:
  tracing:
    sampling:
      probability: 1.0
```

Output:
```json
{"@timestamp":"2026-01-29T10:15:30.123Z","level":"INFO","logger_name":"com.example.OrderService","message":"Order created","traceId":"abc123def456","spanId":"789xyz","service.name":"order-service"}
```

The `traceId` field in JSON logs is the same trace ID visible in Jaeger, Tempo, or any OTel-compatible backend — enabling direct log-to-trace correlation.

### Profile-Based Switching

```yaml
# application.yml: after the default document with the JSON format above, so JSON applies under
# every profile (kubernetes, prod, ...) unless human-logs is active
---
spring:
  config:
    activate:
      on-profile: human-logs
logging:
  structured:
    format:
      console: ""   # empty turns structured logging off
  pattern:
    console: "%d{HH:mm:ss.SSS} %-5level [%thread] %logger{36} - %msg%n"
```

**Usage:**
```bash
# Default: JSON (CI/CD, production)
./mvnw spring-boot:run

# Human-readable when needed
./mvnw spring-boot:run -Dspring-boot.run.profiles=human-logs
./gradlew bootRun --args='--spring.profiles.active=human-logs'   # Gradle
```

### Custom Fields

Boot's JSON formats write SLF4J key-value pairs as separate JSON members, so no Logstash encoder is needed:

```java
log.atInfo()
    .addKeyValue("orderId", order.getId())
    .addKeyValue("total", order.getTotal())
    .log("Order created");
// {"message":"Order created","orderId":123,"total":99.99,...}
```

Fields for every line (e.g. the environment) go in `logging.structured.json.add.<name>: <value>`.

## Logger

Declare the logger with `@Slf4j` (`LoggerFactory.getLogger(MyClass.class)` where the class can't use Lombok). Use `{}` placeholders instead of string concatenation, and pass the exception as the last argument, without a placeholder, so the stack trace is logged.

## MDC (Mapped Diagnostic Context)

MDC attaches context (request ID, user ID) to every log line in the current thread automatically.

### Request Filter for Correlation IDs

```java
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class MdcFilter implements Filter {

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        try {
            HttpServletRequest httpRequest = (HttpServletRequest) request;
            String requestId = httpRequest.getHeader("X-Request-Id");
            if (requestId == null) {
                requestId = UUID.randomUUID().toString().substring(0, 8);
            }
            MDC.put("requestId", requestId);
            MDC.put("clientIp", httpRequest.getRemoteAddr());

            chain.doFilter(request, response);
        } finally {
            MDC.clear();
        }
    }
}
```

### MDC with Virtual Threads

Virtual threads don't inherit MDC from parent threads. Use `TaskDecorator` to propagate:

```java
@Configuration
public class AsyncConfig {

    @Bean
    public TaskDecorator mdcTaskDecorator() {
        return runnable -> {
            Map<String, String> context = MDC.getCopyOfContextMap();
            return () -> {
                if (context != null) {
                    MDC.setContextMap(context);
                }
                try {
                    runnable.run();
                } finally {
                    MDC.clear();
                }
            };
        };
    }
}
```
