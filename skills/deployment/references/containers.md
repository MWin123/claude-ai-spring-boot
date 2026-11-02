# Containers, Docker Compose and CI/CD

## CI/CD Pipelines

- Only when asked or when a pipeline exists (CI rule in the `conventions` skill); match the existing system's style
- Build pipeline: checkout → restore cache → `./mvnw verify` (Gradle: `./gradlew build`) → save cache → build image → push to registry
- Quality gates: test pass, code coverage threshold, vulnerability scan
- Environment-specific deployment stages (dev → staging → prod)
- Cache between builds: Maven `~/.m2/repository`, keyed on `pom.xml`; Gradle `~/.gradle/caches` and `~/.gradle/wrapper`, keyed on the `*.gradle*` files, `gradle.properties` and the files under `gradle/` (wrapper properties, version catalog) (on GitHub Actions use `gradle/actions/setup-gradle`)

## Container Images

**Preferred: Paketo Buildpacks** via the Spring Boot Maven or Gradle plugin (no Dockerfile needed). Use a Dockerfile only when you need full control over the build.

```bash
./mvnw spring-boot:build-image -Dspring-boot.build-image.imageName=myapp:1.0.0
./mvnw -Pnative spring-boot:build-image -Dspring-boot.build-image.imageName=myapp:1.0.0-native

# Gradle (native: apply the org.graalvm.buildtools.native plugin, then the same task builds a native image)
./gradlew bootBuildImage --imageName=myapp:1.0.0
```

```xml
<plugin>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-maven-plugin</artifactId>
    <configuration>
        <image>
            <name>${project.artifactId}:${project.version}</name>
        </image>
    </configuration>
</plugin>
```

```kotlin
// build.gradle.kts
tasks.bootBuildImage {
    imageName = "${project.name}:${project.version}"
}
```

The plugin passes the project's Java version to the buildpacks (`BP_JVM_VERSION`); setting it by hand only lets it drift from the build.

Advantages over a Dockerfile: reproducible builds with nothing to maintain, automatic security patching of the base image layers, and layering that caches dependencies separately from the app code.

**Alternative: multi-stage Dockerfile**

```dockerfile
# The project's Java version (java.version in pom.xml, the toolchain in Gradle)
ARG JAVA_VERSION=21
FROM eclipse-temurin:${JAVA_VERSION}-jdk-alpine AS build
WORKDIR /workspace/app
COPY mvnw .
COPY .mvn .mvn
COPY pom.xml .
RUN ./mvnw dependency:go-offline -B
COPY src src
RUN ./mvnw package -DskipTests

FROM eclipse-temurin:${JAVA_VERSION}-jre-alpine
RUN addgroup -S -g 1000 app && adduser -S -u 1000 -G app app && apk add --no-cache curl
WORKDIR /app
COPY --from=build /workspace/app/target/*.jar app.jar
USER 1000
HEALTHCHECK --interval=30s --timeout=3s CMD curl -sf http://localhost:8080/actuator/health || exit 1
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75.0", "-jar", "app.jar"]
```

For Gradle, replace the build stage (the runtime stage stays the same; `bootJar` writes only the executable jar, `build` would add a `-plain.jar`). `./gradlew dependencies` would not download the jars, so a BuildKit cache mount keeps them between builds instead:

```dockerfile
ARG JAVA_VERSION=21
FROM eclipse-temurin:${JAVA_VERSION}-jdk-alpine AS build
WORKDIR /workspace/app
COPY gradlew .
COPY gradle gradle
# Groovy DSL: build.gradle settings.gradle; also copy gradle.properties if the project has one
COPY build.gradle.kts settings.gradle.kts ./
COPY src src
RUN --mount=type=cache,target=/root/.gradle ./gradlew bootJar --no-daemon
# runtime stage: COPY --from=build /workspace/app/build/libs/*.jar app.jar
```

- Cache dependency downloads (Maven: dependencies before source; Gradle: cache mount); separate build and runtime stages
- Non-root `USER` in the runtime stage, as a numeric UID (Kubernetes `runAsNonRoot` cannot verify a user name); `HEALTHCHECK` on the Actuator health endpoint
- `.dockerignore`: `.git`, `target/`, `build/`, `.gradle/`, `.idea/`, `*.iml`, `*.md`, `.claude/`
- Pin base image versions (tag or digest, never `latest`); scan with `docker scout` or Trivy
- No secrets in the image or Dockerfile; read-only root filesystem and dropped capabilities where possible

## Docker Compose

- Extend an existing compose file (`compose.yaml`, `docker-compose.yml`) instead of creating a new one; default name for new files: `compose.yaml`
- Define all application dependencies (PostgreSQL, Redis, Kafka, etc.)
- Health checks on all services (`pg_isready`, `mysqladmin ping`) with `depends_on.condition: service_healthy`
- Named volumes for data persistence
- Spring Boot configuration via environment variables (`SPRING_DATASOURCE_URL`, etc.)
- Port 5005 for remote debugging
