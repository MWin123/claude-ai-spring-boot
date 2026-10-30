---
name: logging-patterns
description: Java logging best practices with SLF4J, structured logging (JSON), and MDC for request tracing. Includes AI-friendly log formats for Claude Code debugging. Use when user asks about logging, debugging application flow, or analyzing logs.
when_to_use: '"add logging", "improve logs", "debug this"; analyzing application flow from logs; structured JSON logging; request tracing with correlation IDs.'
---

# Logging Patterns Skill

**Rule: JSON is the default log format.** Plain text logging is only for local development with `human-logs` profile. Production, CI/CD, and Kubernetes environments must use structured JSON.

## AI-Friendly Logging

> **Key insight:** JSON logs are better for AI analysis - faster parsing, fewer tokens, direct field access.

### Why JSON for AI/Claude Code?

```
# Text format - AI must "interpret" the string
2026-01-29 10:15:30 INFO OrderService - Order 12345 created for user-789, total: 99.99

# JSON format - AI extracts fields directly
{"timestamp":"2026-01-29T10:15:30Z","level":"INFO","orderId":12345,"userId":"user-789","total":99.99}
```

| Aspect | Text | JSON |
|--------|------|------|
| Parsing | Regex/interpretation | Direct field access |
| Token usage | Higher (repeated patterns) | Lower (structured) |
| Error extraction | Parse stack trace text | `exception` field |
| Filtering | grep patterns | `jq` queries |

### Recommended Setup for AI-Assisted Development

```yaml
# application.yml - JSON by default
logging:
  structured:
    format:
      console: logstash  # Spring Boot 4.x

# When YOU need to read logs manually:
# Option 1: Use jq
# tail -f app.log | jq .

# Option 2: Switch profile temporarily
# java -jar app.jar --spring.profiles.active=human-logs
```

### Log Format Optimized for AI Analysis

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

**Key fields for AI debugging:**
- `requestId` - group all logs from same request
- `step` - track progress through flow
- `duration_ms` - identify slow operations
- `level` - quick filter for errors

### Reading Logs with AI/Claude Code

When asking AI to analyze logs:

```bash
# Get recent errors
cat app.log | jq 'select(.level == "ERROR")' | tail -20

# Follow specific request
cat app.log | jq 'select(.requestId == "req-abc123")'

# Find slow operations
cat app.log | jq 'select(.duration_ms > 1000)'
```

AI can then:
1. Parse JSON directly (no guessing)
2. Follow request flow via requestId
3. Identify exactly where errors occurred
4. Measure timing between steps

## Quick Setup (Spring Boot 4.x)

### Native Structured Logging

Spring Boot 4.x has built-in JSON logging — no extra dependencies required.

```yaml
# application.yml — this is the REQUIRED default for every app
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
# application.yml — tracing + structured logging together
management:
  tracing:
    sampling:
      probability: 1.0

logging:
  structured:
    format:
      console: logstash
  pattern:
    level: "%5p [${spring.application.name:},%X{traceId:-},%X{spanId:-}]"
```

Output:
```json
{"@timestamp":"2026-01-29T10:15:30.123Z","level":"INFO","logger_name":"com.example.OrderService","message":"Order created","traceId":"abc123def456","spanId":"789xyz","service.name":"order-service"}
```

The `traceId` field in JSON logs is the same trace ID visible in Jaeger, Tempo, or any OTel-compatible backend — enabling direct log-to-trace correlation.

### Profile-Based Switching

```yaml
# application.yml (default - JSON for AI/prod)
spring:
  profiles:
    default: json-logs

---
spring:
  config:
    activate:
      on-profile: json-logs
logging:
  structured:
    format:
      console: logstash

---
spring:
  config:
    activate:
      on-profile: human-logs
# No structured format = human-readable default
logging:
  pattern:
    console: "%d{HH:mm:ss.SSS} %-5level [%thread] %logger{36} - %msg%n"
```

**Usage:**
```bash
# Default: JSON (for AI, CI/CD, production)
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

## SLF4J Basics

### Logger Declaration

```java
@Service
@Slf4j
public class OrderService {
    // use `log` directly for logging
}
```

Without Lombok:

```java
private static final Logger log = LoggerFactory.getLogger(OrderService.class);
```

### Parameterized Logging

```java
// ✅ GOOD: Evaluated only if level enabled
log.debug("Processing order {} for user {}", orderId, userId);

// ❌ BAD: Always concatenates
log.debug("Processing order " + orderId + " for user " + userId);

// ✅ For expensive operations
if (log.isDebugEnabled()) {
    log.debug("Order details: {}", order.toDetailedString());
}
```

### Exception Logging

```java
// ✅ GOOD: Pass exception as last argument
try {
    processOrder(order);
} catch (PaymentException e) {
    log.error("Payment failed for order {}", order.getId(), e);
}

// ❌ BAD: Loses stack trace
log.error("Payment failed: " + e.getMessage());

// ❌ BAD: Exception in placeholder (toString only)
log.error("Payment failed for order {}: {}", order.getId(), e);
```

### Log Levels Guide

| Level | When to use |
|-------|------------|
| `ERROR` | Something broke — action needed. Failed payment, unrecoverable state |
| `WARN` | Something unexpected but handled. Retry succeeded, fallback used |
| `INFO` | Business events. Order created, user logged in, job completed |
| `DEBUG` | Technical details. SQL queries, HTTP requests, cache hits |
| `TRACE` | Verbose internals. Method entry/exit, loop iterations |

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

### MDC in Service Layer

```java
@Service
@Slf4j
public class OrderService {

    public Order createOrder(OrderRequest request) {
        MDC.put("userId", request.userId());
        MDC.put("orderId", String.valueOf(request.orderId()));

        log.info("Creating order");
        // All subsequent log lines in this thread automatically include userId and orderId

        return processOrder(request);
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

## Quick Reference

| Pattern | Use |
|---------|-----|
| `@Slf4j` | Declare logger (always, when the class can use Lombok); `LoggerFactory.getLogger(MyClass.class)` otherwise |
| `log.info("msg {}", var)` | Parameterized logging |
| `log.error("msg {}", var, exception)` | Log with stack trace |
| `MDC.put("key", "value")` | Add context to all logs in thread |
| `MDC.clear()` | Clean up in `finally` block |
| `logging.structured.format.console: logstash` | Enable JSON (Spring Boot 4.x) |
| `kv("field", value)` | Structured argument (Logstash encoder) |
