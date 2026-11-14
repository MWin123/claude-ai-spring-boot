# Contract-First REST API (OpenAPI Generator)

The API is spec-first: a hand-written OpenAPI spec is the contract, and the build generates the controller interfaces and the request/response models from it. The controllers implement the generated interfaces. They never declare `@RequestMapping`, `@PathVariable`, `@RequestBody` or `@Valid`, because those come from the interface. To change the API, edit the spec and rebuild. Never edit generated code, and never write a controller mapping or API DTO that the spec does not define.

| Piece | Where | Written by |
|-------|-------|------------|
| Spec (OpenAPI 3.0.x) | `src/main/resources/static/openapi.yaml` (also served to Swagger UI, see `swagger-ui.md`) | You |
| API interfaces (`UsersApi`, one per tag) | `<base package>.api`, under `target/generated-sources/openapi` (Maven) or `build/generated/openapi` (Gradle) | Generator |
| Models (`CreateUserRequest`, `UserResponse`) | `<base package>.api.model` | Generator |
| Controllers implementing the interfaces | `<base package>.controller` | You |

Keep the spec on OpenAPI 3.0.x (`openapi: 3.0.3`), because the generator's 3.1 support is incomplete. Leave `servers` out, so Swagger UI calls the host it was loaded from.

The controllers that implement the interfaces, the exception handler and the rest of the web layer are in `web.md`; Swagger UI is in `swagger-ui.md`.

## The Spec

```yaml
# src/main/resources/static/openapi.yaml
openapi: 3.0.3
info:
  title: User API
  version: 1.0.0          # keep in step with the project version
security:
  - bearerAuth: []        # every operation needs a JWT unless it says otherwise
paths:
  /api/v1/users:
    get:
      tags: [Users]       # one generated interface per tag: UsersApi
      operationId: listUsers   # becomes the Java method name
      parameters:
        - { name: page, in: query, schema: { type: integer, minimum: 0, default: 0 } }
        - { name: size, in: query, schema: { type: integer, minimum: 1, maximum: 100, default: 20 } }
      responses:
        '200':
          description: One page of users
          content:
            application/json:
              schema: { $ref: '#/components/schemas/UserPage' }
    post:
      tags: [Users]
      operationId: createUser
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/CreateUserRequest' }
      responses:
        '201':
          description: Created
          headers: { Location: { schema: { type: string, format: uri } } }
          content:
            application/json:
              schema: { $ref: '#/components/schemas/UserResponse' }
        '400': { $ref: '#/components/responses/BadRequest' }
  /api/v1/users/{id}:
    parameters:
      - { name: id, in: path, required: true, schema: { type: integer, format: int64 } }
    get:
      tags: [Users]
      operationId: getUser
      responses:
        '200':
          description: The user
          content:
            application/json:
              schema: { $ref: '#/components/schemas/UserResponse' }
        '404': { $ref: '#/components/responses/NotFound' }
    delete:
      tags: [Users]
      operationId: deleteUser
      responses:
        '204': { description: Deleted }
        '404': { $ref: '#/components/responses/NotFound' }
components:
  responses:                # shared error responses, referenced per operation
    BadRequest:
      description: Invalid request
      content: { application/problem+json: { schema: { $ref: '#/components/schemas/ProblemDetail' } } }
    NotFound:
      description: Not found
      content: { application/problem+json: { schema: { $ref: '#/components/schemas/ProblemDetail' } } }
  securitySchemes:
    bearerAuth: { type: http, scheme: bearer, bearerFormat: JWT }
  schemas:
    CreateUserRequest:
      type: object
      required: [email, username]
      properties:
        email: { type: string, format: email, maxLength: 100 }        # @NotNull @Email @Size; same length as the users.email column
        username: { type: string, minLength: 3, maxLength: 50, pattern: '^[a-zA-Z0-9_]+$' }
    UserResponse:
      type: object
      required: [id, email, username]
      properties:
        id: { type: integer, format: int64 }
        email: { type: string }
        username: { type: string }
        createdAt: { type: string, format: date-time }                # OffsetDateTime
    UserPage:
      type: object
      required: [content, totalElements]
      properties:
        content: { type: array, items: { $ref: '#/components/schemas/UserResponse' } }
        totalElements: { type: integer, format: int64 }
    ProblemDetail:          # mapped to Spring's ProblemDetail, not generated (schemaMappings below)
      type: object
      properties:
        type: { type: string, format: uri }
        title: { type: string }
        status: { type: integer }
        detail: { type: string }
        instance: { type: string, format: uri }
```

Validation lives in the spec: `required` becomes `@NotNull`, while `minLength`/`maxLength`, `minimum`/`maximum`, `pattern` and `format: email` become `@Size`, `@Min`/`@Max`, `@Pattern` and `@Email`. A required request body gets `@Valid @RequestBody` on the generated method. Mark a public operation (e.g. login) with `security: []`. Keep `maxLength` equal to the column length in the migration, or a valid request fails in the database.

## Spec Design Checklist

Before writing or changing the spec, settle these points. Take the answer from the request, the existing code or the existing spec. Ask the user only about a point that none of them settles and that would be costly to change later (auth, versioning, error format). For the rest, apply the default and say so in the report. Show the user the finished YAML before generating code from it.

| Topic | Decide | Default |
|-------|--------|---------|
| Resources and operations | Nouns for paths (`/users/{id}`), HTTP verbs for actions; every operation has a unique `operationId` and a tag per resource | Plural nouns, `kebab-case` path segments, `camelCase` `operationId` (`listUsers`) |
| Versioning | Where the version lives | `/api/v1/...` prefix; `info.version` follows the project version |
| Authentication | Which operations are public | JWT bearer scheme on every operation; `security: []` only on login, registration and similar |
| Authorization | Who may call what | Not in the spec: enforce with Spring Security. Mention the required role in the operation `description` |
| Pagination | Every list operation that can grow | `page` (min 0, default 0) and `size` (min 1, max 100, default 20) query parameters; response with `content` and `totalElements`. Never return an unbounded array |
| Filtering and sorting | Which fields are queryable | Only the ones the request needs, as explicit query parameters |
| Success responses | Status code per operation | `200` read/update, `201` create (with `Location` header), `204` delete or no body |
| Errors | Which failures each operation can produce | `400` for operations with input, `404` for operations with `{id}`, `409` for unique-field conflicts and concurrent updates (`@Version`), `401`/`403` follow from `security`. All `application/problem+json` with the `ProblemDetail` schema |
| Constraints | Every input field | `required` where the service needs the value; `minLength`/`maxLength` on every string, `minimum`/`maximum` on numbers, `pattern` or `format` where it applies. No unbounded strings |
| Schemas | Separate request and response schemas | `CreateXRequest` / `UpdateXRequest` / `XResponse`; never one schema for both directions; no entity fields the client must not see (password hashes, internal ids); IDs `int64` or `uuid` |
| Update semantics | Full or partial update | `PUT` replaces (all fields required), `PATCH` takes an all-optional schema |
| Dates and money | Wire formats | `format: date-time` (ISO 8601, UTC) for instants, `format: date` for dates; money as a decimal string (see "Money" below) or integer minor units, never `number` |
| Enums and nullability | Closed value sets, optional vs nullable | `enum` only for sets the server controls; `required` marks always-present properties, `nullable: true` only where `null` carries meaning |
| Compatibility | Is this a change to a published API? | Adding optional fields or operations is safe; removing or renaming fields, tightening constraints, changing status codes or making a field required needs a new version or the user's explicit approval |

Reuse shared pieces through `components` (`ProblemDetail`, `UserPage`, repeated parameters, standard error `responses`) instead of repeating them per operation, and give every schema, operation and non-obvious parameter a `description`. After editing, run the generator and read the generated interfaces to check that the Java signatures match the intended contract.

### Money

`type: string, format: decimal` generates a `BigDecimal`, and the generator option `bigDecimalAsString` writes it as a JSON string, so no client parses it into a float. `minimum` and `maxLength` do not apply to a string-typed decimal (`maxLength` even puts `@Size` on the `BigDecimal`, which fails at runtime); bound it with Bean Validation through `x-field-extra-annotation`, with `@Digits` matching the column's `precision`/`scale`:

```yaml
price:
  type: string
  format: decimal
  example: "19.99"
  x-field-extra-annotation: '@jakarta.validation.constraints.DecimalMin("0") @jakarta.validation.constraints.Digits(integer = 8, fraction = 2)'
```

## Generator Plugin

The generator is not managed by the Spring Boot BOM. Look up the latest `openapi-generator-maven-plugin` release on Maven Central (7.26.0 at the time of writing; the Gradle plugin `org.openapi.generator` has the same version). `useSpringBoot4` needs 7.x.

```xml
<properties>
    <openapi-generator.version>7.x.y</openapi-generator.version>
</properties>

<plugin>
    <groupId>org.openapitools</groupId>
    <artifactId>openapi-generator-maven-plugin</artifactId>
    <version>${openapi-generator.version}</version>
    <executions>
        <execution>
            <goals><goal>generate</goal></goals>
            <configuration>
                <inputSpec>${project.basedir}/src/main/resources/static/openapi.yaml</inputSpec>
                <generatorName>spring</generatorName>
                <apiPackage>com.example.api</apiPackage>             <!-- base package + .api -->
                <modelPackage>com.example.api.model</modelPackage>
                <generateSupportingFiles>false</generateSupportingFiles>
                <schemaMappings>ProblemDetail=org.springframework.http.ProblemDetail</schemaMappings>
                <configOptions>
                    <interfaceOnly>true</interfaceOnly>              <!-- interfaces + models, no stub controllers -->
                    <useSpringBoot4>true</useSpringBoot4>            <!-- jakarta.*, Boot 4 -->
                    <useTags>true</useTags>                          <!-- UsersApi per tag, not per path segment -->
                    <skipDefaultInterface>true</skipDefaultInterface><!-- unimplemented operations fail to compile -->
                    <bigDecimalAsString>true</bigDecimalAsString>    <!-- BigDecimal as a JSON string, see "Money" -->
                    <openApiNullable>false</openApiNullable>         <!-- no jackson-databind-nullable (Jackson 2) -->
                    <documentationProvider>none</documentationProvider> <!-- Swagger UI shows the spec file itself -->
                    <generateJsonIncludeAnnotations>false</generateJsonIncludeAnnotations>
                    <generateJsonSetterNullsAnnotations>false</generateJsonSetterNullsAnnotations>
                </configOptions>
            </configuration>
        </execution>
    </executions>
</plugin>
```

The plugin runs in `generate-sources` and adds the output to the compile sources. In Gradle, wire it in yourself:

```kotlin
// build.gradle.kts
plugins {
    id("org.openapi.generator") version "7.x.y"
}

openApiGenerate {
    generatorName = "spring"
    inputSpec = layout.projectDirectory.file("src/main/resources/static/openapi.yaml")
    outputDir = layout.buildDirectory.dir("generated/openapi")
    apiPackage = "com.example.api"
    modelPackage = "com.example.api.model"
    globalProperties = mapOf("apis" to "", "models" to "")   // no supporting files
    schemaMappings = mapOf("ProblemDetail" to "org.springframework.http.ProblemDetail")
    configOptions = mapOf(
        "interfaceOnly" to "true",
        "useSpringBoot4" to "true",
        "useTags" to "true",
        "skipDefaultInterface" to "true",
        "bigDecimalAsString" to "true",
        "openApiNullable" to "false",
        "documentationProvider" to "none",
        "generateJsonIncludeAnnotations" to "false",
        "generateJsonSetterNullsAnnotations" to "false",
    )
}

sourceSets { main { java { srcDir(layout.buildDirectory.dir("generated/openapi/src/main/java")) } } }
tasks.compileJava { dependsOn(tasks.openApiGenerate) }
```

The generated code needs `spring-boot-starter-validation`; everything else comes with the web starter. For a WebFlux app, add `reactive=true` to the config options. The methods then return `Mono<ResponseEntity<...>>`, take `Mono<Body>` and get a trailing `ServerWebExchange` parameter (see "Reactive Controller (WebFlux)" in `web.md`).
