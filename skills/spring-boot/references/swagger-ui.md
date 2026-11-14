# Swagger UI (springdoc)

springdoc hosts Swagger UI for the hand-written spec (see "Contract-First REST API" in `openapi.md`). Swagger UI loads `openapi.yaml` itself, so it shows the contract exactly as written, including `info`, the security schemes and the "Authorize" button, with no `@OpenAPIDefinition`, `@SecurityScheme` or `@Operation` annotations in Java. Pick the starter from the build file (`pom.xml` or `build.gradle(.kts)`), and skip this step if any `springdoc-openapi-starter-*` dependency is already there:

| Build file contains | Add |
|--------------------|-----|
| `spring-boot-starter-webmvc` | `springdoc-openapi-starter-webmvc-ui` |
| `spring-boot-starter-webflux` (reactive REST API, no `webmvc`) | `springdoc-openapi-starter-webflux-ui` |
| Neither | Nothing |

Use springdoc 3.x, the line for Boot 4 (2.x is for Boot 3). Look up the latest 3.x release on Maven Central (3.2.0 at the time of writing) and use it for `3.x.y` below:

```xml
<properties>
    <springdoc.version>3.x.y</springdoc.version>
</properties>

<dependency>
    <groupId>org.springdoc</groupId>
    <artifactId>springdoc-openapi-starter-webmvc-ui</artifactId> <!-- or -webflux-ui -->
    <version>${springdoc.version}</version>
</dependency>
```

```kotlin
// build.gradle.kts (springdoc is not managed by the Spring Boot BOM, so give the version)
implementation("org.springdoc:springdoc-openapi-starter-webmvc-ui:3.x.y") // or -webflux-ui
```

## Endpoints (same for WebMVC and WebFlux)

| Path | Serves |
|------|--------|
| `/openapi.yaml` | The hand-written spec, as a static resource from `src/main/resources/static/` |
| `/swagger-ui.html` | Redirects to `/swagger-ui/index.html` |
| `/swagger-ui/**` | Swagger UI assets |
| `/v3/api-docs/swagger-config` | UI config, loaded by Swagger UI; points it at `/openapi.yaml` |

springdoc also serves its own spec at `/v3/api-docs`, rebuilt from the controller mappings. Swagger UI does not use it, and since the contract is `openapi.yaml` it stays out of the permitted paths below. Keep it enabled anyway: `springdoc.api-docs.enabled: false` also switches off `swagger-config` and Swagger UI.

## Configuration

```yaml
# application.yml
springdoc:
  swagger-ui:
    url: /openapi.yaml           # show the hand-written spec, not springdoc's /v3/api-docs
```

The spec and Swagger UI stay enabled in production. The spec has no `servers` entry, so Swagger UI calls the host and scheme it was loaded from, and behind a reverse proxy the docs need no forwarded-header setting.

## Behind a Kubernetes Ingress

The Ingress must route the docs paths to the pod:

- **One host per service** (`users.example.com`, path `/`): the default paths work as they are.
- **Shared host, one path prefix per service** (`api.example.com/api/users`): every service would claim `/openapi.yaml` and `/swagger-ui.html`. Move the docs under the service's prefix, so the existing Ingress rule covers them and each service keeps its own docs. Move the spec file to `src/main/resources/static/api/users/openapi.yaml`, point the generator's `inputSpec` at the new location, and set:

```yaml
# application.yml
springdoc:
  api-docs:
    path: /api/users/v3/api-docs        # swagger-config moves to /api/users/v3/api-docs/swagger-config
  swagger-ui:
    path: /api/users/swagger-ui.html    # UI assets move to /api/users/swagger-ui/**
    url: /api/users/openapi.yaml
```

Prefix the security matchers the same way (`/api/users/openapi.yaml`, `/api/users/v3/api-docs/swagger-config`, `/api/users/swagger-ui/**`, `/api/users/swagger-ui.html`), and put them before any `/api/users/**` role rule: the first matching rule wins.

If CSRF protection is on, "Try it out" needs two things, or POST/PUT/DELETE are rejected: Spring Security must issue the `XSRF-TOKEN` cookie eagerly and accept its raw value, which `csrf.spa()` does (see `security.md`; a bare `CookieCsrfTokenRepository.withHttpOnlyFalse()` issues no cookie for Swagger UI), and Swagger UI must send it back. With CSRF disabled, leave this out:

```yaml
# application.yml
springdoc:
  swagger-ui:
    csrf:
      enabled: true   # reads the XSRF-TOKEN cookie, sends X-XSRF-TOKEN
```

## Authentication in Swagger UI

For an API secured with JWT, the spec declares the bearer scheme (`components.securitySchemes.bearerAuth` plus the top-level `security`, as in "The Spec" in `openapi.md`). Swagger UI then shows the "Authorize" button and sends `Authorization: Bearer <token>` with every call. Operations with `security: []` (e.g. login) are shown as public. No Java configuration is needed.

## Spring Security

If Spring Security is present, permit the paths above in every profile, production included. Only the docs become public: the API endpoints stay authenticated, and Swagger UI calls them with the token from "Authorize". springdoc's own `/v3/api-docs` stays authenticated, so permit only its `swagger-config` child:

```java
private static final String[] OPENAPI_PATHS = {
    "/openapi.yaml", "/v3/api-docs/swagger-config", "/swagger-ui/**", "/swagger-ui.html"
};

// WebMVC: SecurityFilterChain
.authorizeHttpRequests(auth -> auth
    .requestMatchers(OPENAPI_PATHS).permitAll()
    .anyRequest().authenticated())

// WebFlux: SecurityWebFilterChain
.authorizeExchange(exchange -> exchange
    .pathMatchers(OPENAPI_PATHS).permitAll()
    .anyExchange().authenticated())
```

## Tests

- Positive: without credentials, `GET /openapi.yaml` returns 200 and `GET /v3/api-docs/swagger-config` returns `$.url` = `/openapi.yaml`.
- Negative: without credentials, `/v3/api-docs` and an API endpoint return 401, so the permit list opened only the docs.
