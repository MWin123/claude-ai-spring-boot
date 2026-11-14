---
name: code-quality
description: Clean-code rules for Java and Spring Boot - where validation and the API contract live, null safety, exception handling and resource management; performance pitfalls are in jpa-patterns. Use when writing or refactoring code; reviews go to the code-reviewer agent.
when_to_use: '"refactor", "clean this code", "improve readability", "simplify this"; fixing the findings of a review.'
---

# Code Quality Skill

Rules to apply while writing or refactoring. What a review flags is in the `review-checklist` skill, which the `code-reviewer` agent loads.

- **DRY, KISS, YAGNI:** one source of truth for every rule, and no abstraction before a second use needs it. Input validation is not a DRY case for Java code: it lives once, in the OpenAPI spec (`conventions` skill).
- **API design:** the REST contract is the OpenAPI spec: HTTP verbs, status codes, versioning, pagination and separate request/response schemas follow the "Spec Design Checklist" in `openapi.md` of the `spring-boot` skill. Controllers only implement the generated interfaces, and entities never leave the service layer.
- **Null safety:** return `Optional` or an empty collection instead of `null`, and never call `Optional.get()` unchecked. Public APIs declare nullability with JSpecify: `@NullMarked` on packages, `org.jspecify.annotations.Nullable` where null is allowed (`boot4.md` in the `spring-boot` skill).
- **Exceptions:** catch the narrowest exception type, never leave a catch block empty or unlogged, and pass the original exception as the cause when you rethrow.
- **Resources:** try-with-resources for everything `AutoCloseable`, never a manual `close()`.
- **Transactions:** the rules are in the `conventions` skill, the pitfalls in `jpa-patterns`.
- **Performance:** N+1 queries, fetch joins and pagination of large result sets are in the `jpa-patterns` skill.
