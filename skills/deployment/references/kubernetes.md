# Kubernetes

## Spring Boot Deployment Manifest

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: <app-name>
spec:
  replicas: 2
  selector:
    matchLabels:
      app: <app-name>
  template:
    metadata:
      labels:
        app: <app-name>
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/actuator/prometheus"
    spec:
      serviceAccountName: <app-name>
      containers:
      - name: <app-name>
        image: <registry>/<app-name>:<version>
        ports:
        - containerPort: 8080
        envFrom:
        - configMapRef:
            name: <app-name>-config
        - secretRef:
            name: <app-name>-secrets
        env:
        - name: SPRING_PROFILES_ACTIVE
          value: "kubernetes"
        livenessProbe:
          httpGet:
            path: /actuator/health/liveness
            port: 8080
          periodSeconds: 10
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /actuator/health/readiness
            port: 8080
          periodSeconds: 5
          failureThreshold: 3
        startupProbe:
          httpGet:
            path: /actuator/health/liveness
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
          failureThreshold: 20
        lifecycle:
          preStop:
            sleep:
              seconds: 10
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop: ["ALL"]
        volumeMounts:
        - name: tmp
          mountPath: /tmp
      volumes:
      - name: tmp
        emptyDir: {}
      securityContext:
        runAsNonRoot: true
        seccompProfile:
          type: RuntimeDefault

---
apiVersion: v1
kind: Service
metadata:
  name: <app-name>
spec:
  selector:
    app: <app-name>
  ports:
  - port: 80
    targetPort: 8080
  type: ClusterIP
```

## ConfigMap and Secret

```yaml
# ConfigMap - application properties (non-sensitive defaults)
apiVersion: v1
kind: ConfigMap
metadata:
  name: <app-name>-config
data:
  SPRING_DATASOURCE_URL: "jdbc:postgresql://postgres-service:5432/mydb"
  SPRING_JPA_HIBERNATE_DDL_AUTO: "validate"
  MANAGEMENT_ENDPOINTS_WEB_EXPOSURE_INCLUDE: "health,info,metrics,prometheus"
  MANAGEMENT_ENDPOINT_HEALTH_PROBES_ENABLED: "true"
  SERVER_SHUTDOWN: "graceful"
```

Configure sensitive values (datasource credentials, JWT signing keys) via Kubernetes Secrets mounted as environment variables or using Config Tree.

Spring Boot binds environment variables automatically:
- `SPRING_DATASOURCE_URL` → `spring.datasource.url`
- Relaxed binding: `SPRING_JPA_HIBERNATE_DDL_AUTO` → `spring.jpa.hibernate.ddl-auto`

## Actuator for Kubernetes

Enable the probe endpoints and Prometheus as in "Health Checks, Actuator & Prometheus" in `cloud.md`; `/actuator/prometheus` then serves all Micrometer metrics.

## Config Tree for Mounted Secrets

Instead of env vars, read secrets from mounted files using Config Tree (more secure — secrets don't leak via `/proc/environ`):

```yaml
# application.yml
spring:
  config:
    import: "optional:configtree:/run/secrets/"
```

With a Kubernetes Secret mounted at `/run/secrets/`, each key becomes a file. Spring Boot reads the file content as the property value.

```yaml
# Kubernetes volume mount for Config Tree
spec:
  containers:
  - name: app
    volumeMounts:
    - name: secrets
      mountPath: /run/secrets
      readOnly: true
  volumes:
  - name: secrets
    secret:
      secretName: user-service-secrets
```

## Ingress TLS with cert-manager

cert-manager automatically provisions and renews TLS certificates on Kubernetes.

```yaml
# ClusterIssuer for Let's Encrypt
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@example.com
    privateKeySecretRef:
      name: letsencrypt-prod-key
    solvers:
    - http01:
        ingress:
          class: nginx
```

```yaml
# Ingress with automatic TLS
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: user-service-ingress
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - api.example.com
    secretName: user-service-tls
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /api/users
        pathType: Prefix
        backend:
          service:
            name: user-service
            port:
              number: 80
```

This Ingress routes only `/api/users`. If the service exposes its OpenAPI spec and Swagger UI (springdoc), serve them under that prefix (`/api/users/openapi.yaml`, `/api/users/swagger-ui.html`) so this rule covers them; see "Behind a Kubernetes Ingress" in `web.md`.

cert-manager creates and renews the `user-service-tls` Secret automatically. For end-to-end TLS (not just ingress termination), mount the same Secret into the pod and configure Spring Boot SSL Bundles with `reload-on-update: true` (see `security.md` in the `spring-boot` skill). That moves the app to HTTPS on 8443, so keep Actuator on plain HTTP 8080 for the probes, the Prometheus annotation and the Dockerfile `HEALTHCHECK`:

```yaml
# application.yml, next to the SSL bundle
management:
  server:
    port: 8080      # the probes and prometheus.io/port stay on 8080; the Service doesn't route it
    ssl:
      enabled: false
```

Then add `containerPort: 8443` to the Deployment and set the Service's `targetPort: 8443`. In the Helm chart, `service.targetPort` becomes 8443, so the probes and the Prometheus annotation need their own management port value instead of `http`.

## Certificate for mTLS between services

```yaml
# cert-manager Certificate for pod-level TLS
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: user-service-cert
spec:
  secretName: user-service-tls-pod
  issuerRef:
    name: internal-ca
    kind: ClusterIssuer
  dnsNames:
  - user-service
  - user-service.default.svc.cluster.local
  duration: 720h
  renewBefore: 48h
```

```yaml
# Mount into pod for Spring Boot SSL Bundle
spec:
  containers:
  - name: user-service
    volumeMounts:
    - name: tls-certs
      mountPath: /etc/tls        # not /etc/ssl/certs: the mount would hide the image's CA certificates
      readOnly: true
  volumes:
  - name: tls-certs
    secret:
      secretName: user-service-tls-pod
```

## Building Images

Build images with Paketo Buildpacks (`./mvnw spring-boot:build-image`, Gradle: `./gradlew bootBuildImage`); configuration in `containers.md`.

## Local Development with Skaffold

Skaffold automates the build → push → deploy loop for Kubernetes development.

```yaml
# skaffold.yaml
apiVersion: skaffold/v4beta11
kind: Config
metadata:
  name: <app-name>
build:
  artifacts:
  - image: <app-name>
    custom:
      buildCommand: |
        ./mvnw spring-boot:build-image \
          -Dspring-boot.build-image.imageName=$IMAGE -q
      dependencies:
        paths:
        - src/**
        - pom.xml
        # Gradle: buildCommand ./gradlew bootBuildImage --imageName=$IMAGE -q
        # and paths build.gradle*, settings.gradle*, gradle.properties, gradle/** instead of pom.xml
deploy:
  kubectl:
    manifests:
    - k8s/*.yaml
```

```bash
# Continuous development - rebuild and redeploy on code changes
skaffold dev

# One-time deploy
skaffold run

# Deploy to specific profile/environment
skaffold run -p production
```

## Key Practices

### Health & Lifecycle
- Liveness probe → `/actuator/health/liveness` (restart if dead)
- Readiness probe → `/actuator/health/readiness` (stop traffic if not ready)
- Startup probe → same as liveness, with higher `failureThreshold` (handles slow startup)
- Graceful shutdown: `server.shutdown=graceful` + `preStop` hook with the native `sleep: { seconds: 10 }` action (default Boot images have no shell, so `sh -c "sleep 10"` fails)
- `spring.lifecycle.timeout-per-shutdown-phase=30s` for in-flight request completion

### Resource Management
- Use `-XX:MaxRAMPercentage=75.0` instead of fixed `-Xmx` (adapts to container limits). Buildpack images already size the heap from the container limit with their memory calculator, which sets `-Xmx` and overrides this option, so it only takes effect on Dockerfile-built images
- Do NOT set CPU limits (causes throttling); set CPU requests only
- Use `PodDisruptionBudget` for HA services with more than one replica (`maxUnavailable: 1`; `minAvailable: 1` with a single replica blocks node drains)
- `HorizontalPodAutoscaler` based on CPU/memory or custom Prometheus metrics
- Spring Boot services are stateless: use a `Deployment`. Use a `StatefulSet` (headless Service plus `volumeClaimTemplates`) only for stable pod identity or per-pod storage; in a chart, set `workloadKind` (see `helm.md`)

### Configuration
- `ConfigMap` for non-sensitive properties (datasource URL, feature flags)
- `Secret` for credentials, keys, tokens
- Mount as env vars with `envFrom` (Spring Boot auto-binds)
- Default values in `application.yml` for local development: `${ENV_VAR:default}`
- Never bake config into container images

### Networking
- `ClusterIP` Service for internal communication
- Ingress for external HTTP traffic with TLS termination
- OpenAPI docs (springdoc): the Ingress must route the docs paths. With one host per service and path `/` that happens automatically. With a shared host and a path prefix per service, the app serves the docs under its prefix (`/api/users/openapi.yaml`, `/api/users/swagger-ui.html`; see `web.md` in the `spring-boot` skill), so the prefix rule covers them. Do not add separate `/openapi.yaml`, `/v3/api-docs` or `/swagger-ui` rules on a shared host, because each service would claim them
- Forwarded headers need no setting: Spring Boot detects Kubernetes and applies `server.forward-headers-strategy=native`. The spec has no `servers` entry, so Swagger UI calls the public host it was loaded from
- `NetworkPolicy` to restrict pod-to-pod traffic

### Security
- `runAsNonRoot: true` (leave `runAsUser` unset; Paketo images and the Dockerfile in `containers.md` run as a numeric non-root UID. An image with a non-numeric `USER` fails with `CreateContainerConfigError`: fix the image, or set `runAsUser`)
- Set `fsGroup` when the pod mounts volumes the app must write to
- Container `securityContext` with `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true` and `drop: ["ALL"]` (all required by the "restricted" Pod Security level, except the read-only root); mount an `emptyDir` on `/tmp` for the JVM and Tomcat
- Dedicated `ServiceAccount` with minimal RBAC permissions
- Use `External Secrets Operator` or `Sealed Secrets` for secret management in Git
