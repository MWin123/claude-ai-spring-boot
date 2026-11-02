---
name: code-quality
description: Clean code for Java and Spring Boot - DRY, KISS, YAGNI, null safety, exception handling, resource management, transaction boundaries and naming, with bad and good examples; performance pitfalls are in jpa-patterns. Use when writing or refactoring code; reviews go to the code-reviewer or quick-reviewer agent.
when_to_use: '"refactor", "clean this code", "improve readability", "simplify this"; fixing the findings of a review.'
---

# Code Quality Skill

Clean code principles and Java pitfalls to apply while writing or refactoring. What a review flags is in the `review-checklist` skill, which the `code-reviewer` and `quick-reviewer` agents load.

## Clean Code Principles

### DRY - Don't Repeat Yourself

**Violation:**
```java
// ❌ The same discount rule in two places
public BigDecimal orderTotal(Order order) {
    BigDecimal total = order.subtotal();
    return total.compareTo(new BigDecimal("100")) > 0 ? total.multiply(new BigDecimal("0.9")) : total;
}

public BigDecimal quoteTotal(Quote quote) {
    BigDecimal total = quote.subtotal();
    return total.compareTo(new BigDecimal("100")) > 0 ? total.multiply(new BigDecimal("0.9")) : total;
}
```

**Fix:**
```java
// ✅ Single source of truth
final class Discounts {
    private static final BigDecimal THRESHOLD = new BigDecimal("100");
    private static final BigDecimal RATE = new BigDecimal("0.9");

    static BigDecimal apply(BigDecimal total) {
        return total.compareTo(THRESHOLD) > 0 ? total.multiply(RATE) : total;
    }
}
```

Input validation is not a DRY case for Java code: it lives once, in the OpenAPI spec (`conventions` skill).

### KISS - Keep It Simple

**Violation:**
```java
// ❌ Over-engineered
public interface UserFactory {
    User createUser();
}
public class ConcreteUserFactory implements UserFactory {
    public User createUser() { return new User(); }
}
```

**Fix:**
```java
// ✅ Simple
public User createUser() { return new User(); }
```

### YAGNI - You Aren't Gonna Need It

**Violation:**
```java
// ❌ Premature abstraction
public class ConfigurableUserServiceFactoryProvider { }
```

**Fix:**
```java
// ✅ Implement when actually needed
public class UserService { }
```

## API Design

The REST contract is the OpenAPI spec: HTTP verbs, status codes, versioning, pagination and separate request/response schemas follow the "Spec Design Checklist" in `openapi.md` of the `spring-boot` skill. Controllers only implement the generated interfaces, and entities never leave the service layer.

## Java Pitfalls

### Null Safety

```java
// ❌ NPE risk
String name = user.getName().toUpperCase();

// ✅ Safe with Optional
String name = Optional.ofNullable(user.getName())
    .map(String::toUpperCase)
    .orElse("");

// ✅ Safe with early return
if (user.getName() == null) return "";
return user.getName().toUpperCase();
```

Return `Optional` or an empty collection instead of `null`, and never call `Optional.get()` unchecked. Public APIs declare nullability with JSpecify: `@NullMarked` on packages, `org.jspecify.annotations.Nullable` where null is allowed (`boot4.md` in the `spring-boot` skill).

### Exception Handling

```java
// ❌ Swallowing exceptions
try {
    process();
} catch (Exception e) { }  // Silent failure

// ❌ Losing stack trace
catch (IOException e) {
    throw new RuntimeException(e.getMessage());  // Lost context
}

// ✅ Proper handling
catch (IOException e) {
    log.error("Failed to process file: {}", filename, e);
    throw new ProcessingException("File processing failed", e);
}
```

Catch the narrowest exception type, never leave a catch block empty or unlogged, and pass the original exception as the cause when you rethrow.

### Resource Management

```java
// ❌ Resource leak
FileInputStream fis = new FileInputStream(file);
String content = read(fis);
fis.close();  // Won't execute if read() throws

// ✅ Try-with-resources
try (FileInputStream fis = new FileInputStream(file)) {
    return read(fis);
}  // Auto-closed
```

### Transaction Boundaries

```java
// ❌ Missing transaction
public void createUser(UserRequest request) {
    User user = new User();
    userRepository.save(user);
    roleRepository.save(new Role(user));  // Two separate transactions
}

// ✅ Proper transaction
@Transactional
public void createUser(UserRequest request) {
    User user = new User();
    userRepository.save(user);
    roleRepository.save(new Role(user));  // Single atomic transaction
}
```

### Naming Conventions

**Good:**
```java
// ✅ Clear intent
public List<User> findActiveUsersByRole(String role) { }
public boolean isEmailValid(String email) { }
public void activateUser(Long userId) { }
```

**Bad:**
```java
// ❌ Unclear
public List<User> get(String s) { }
public boolean check(String str) { }
public void doStuff(Long id) { }
```

### Performance

N+1 queries, fetch joins and pagination of large result sets are in the `jpa-patterns` skill.
