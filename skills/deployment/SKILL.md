---
name: deployment
description: Deploying Spring Boot apps - container images (Paketo Buildpacks, multi-stage Dockerfile), Docker Compose for local dependencies, CI/CD pipelines, Kubernetes manifests, Helm charts and Skaffold. Use when containerizing an app, adding Compose services, extending a CI pipeline, or writing Kubernetes or Helm files.
---

# Deployment Skill

Container images, local dependencies, CI/CD and Kubernetes for Spring Boot 4.x / Java 21+ apps.

## Reference Guide

| Topic | Reference | When to Load |
|-------|-----------|-------------|
| Containers | `references/containers.md` | Paketo Buildpacks, multi-stage Dockerfile (Maven and Gradle), Docker Compose, CI/CD pipelines |
| Kubernetes | `references/kubernetes.md` | Deployment, probes, ConfigMap/Secret, Config Tree, cert-manager, NetworkPolicy, HPA/PDB, Skaffold |
| Helm | `references/helm.md` | Helm chart (Deployment or StatefulSet), values, templates, Ingress, `helm test`, lint and verify, Skaffold with Helm |

Helm charts follow the workload rules in `references/kubernetes.md`; read both for a chart.

## Rules

- `<app-name>` is the kebab-case project name: `artifactId` in `pom.xml` or `rootProject.name` in `settings.gradle(.kts)`. Kubernetes, chart and image names must be lowercase
- Extend an existing compose file, pipeline, manifest directory or chart instead of creating a second one (applies to every reference below)
- Externalize secrets via environment variables, never in config files
- Semantic versioning for image tags, never `latest` in production
- All infrastructure config is version-controlled
- Prefer declarative configuration over scripts
