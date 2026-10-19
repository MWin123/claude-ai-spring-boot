# Spring Boot 4 - What Changed vs 3.x

Target: Spring Boot 4.x, Spring Framework 7, Spring Security 7, Jackson 3, Java 21+.

## Modular Starters
- Auto-configuration is split into focused modules; `spring-boot-starter-web` is now `spring-boot-starter-webmvc`.
- Every technology has a matching test starter (e.g. `spring-boot-starter-webmvc-test`). Add the test starter for each technology used in tests.
- Classic starters still work as a deprecated stopgap; do not use them in new code.

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-webmvc</artifactId>
</dependency>
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-webmvc-test</artifactId>
    <scope>test</scope>
</dependency>
```

## Jackson 3
- Packages: `tools.jackson.*` instead of `com.fasterxml.jackson.*` (databind, core).
- Annotations such as `@JsonProperty` stay in `com.fasterxml.jackson.annotation`.
- Inject `tools.jackson.databind.json.JsonMapper` instead of `ObjectMapper` (Jackson 2).
- Exceptions are unchecked (`JacksonException`).
- Migrate automatically with OpenRewrite: `org.openrewrite.java.jackson.UpgradeJackson_2_3`.

## Testing
- `@MockBean`/`@SpyBean` are removed. Use `@MockitoBean`/`@MockitoSpyBean` from `org.springframework.test.context.bean.override.mockito`.
- Prefer `RestTestClient` with `@AutoConfigureRestTestClient` for integration tests.

## Declarative HTTP Clients: @ImportHttpServices
Define a `@HttpExchange` interface; Spring registers a proxy bean. No manual `HttpServiceProxyFactory`.

```java
public interface UserClient {
    @GetExchange("/users/{id}")
    UserResponse get(@PathVariable Long id);
}

@Configuration
@ImportHttpServices(group = "userApi", types = UserClient.class)
class HttpClientConfig { }
```

```properties
spring.http.serviceclient.userApi.base-url=https://api.example.com
```

## API Versioning
Versions are declared on mappings and resolved from header, path, or media-type parameter (configurable).

```properties
spring.mvc.apiversion.use.header=API-Version
```

```java
@GetMapping(path = "/{id}", version = "1.0")
UserV1 getV1(@PathVariable Long id) { ... }

@GetMapping(path = "/{id}", version = "2.0")
UserV2 getV2(@PathVariable Long id) { ... }
```

## Null Safety: JSpecify
- Spring Framework 7 is annotated with JSpecify (`org.jspecify.annotations`).
- Put `@NullMarked` on packages (`package-info.java`): everything is non-null unless annotated `@Nullable`.
- Use `org.jspecify.annotations.Nullable`, not Spring's or JSR-305 annotations, in new code.

```java
@NullMarked
package com.example.user;
```

## Migration Checklist
1. Replace classic starters with modular ones and add `-test` starters.
2. Run the OpenRewrite Jackson 2 -> 3 recipe; replace `ObjectMapper` injection with `JsonMapper`.
3. Replace `@MockBean`/`@SpyBean` with `@MockitoBean`/`@MockitoSpyBean`.
4. Review renamed properties and Spring Security 7 changes.
5. Add `@NullMarked` to packages incrementally.
