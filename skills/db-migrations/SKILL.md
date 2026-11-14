---
name: db-migrations
description: Database schema migrations for Spring Boot with Liquibase (default) or Flyway - new tables or columns, indexes, data backfills, safe NOT NULL/rename/drop changes, kept consistent with the JPA entities.
when_to_use: 'Changing an entity; a new table, column or index; a Liquibase changelog or Flyway migration; "schema change", "add a column".'
---

# Database Migrations Skill

Schema changes live only in versioned migrations; JPA never creates or alters tables.

## Choosing the Tool

- Detect what the project uses: `spring-boot-starter-liquibase` / `db/changelog/` (Liquibase) or `spring-boot-starter-flyway` / `db/migration/` (Flyway). Follow it; never mix both, and never switch tools unasked.
- No migration tool yet: use Liquibase and add `spring-boot-starter-liquibase`.

## Rules (both tools)

- Never edit a migration that may already be applied. Add a new one instead.
- `spring.jpa.hibernate.ddl-auto=validate` in every non-test profile; never `update` or `create`.
- Match the database in use (check the build file and `compose.yaml`); do not mix dialects.
- Each migration is one logical change and must run on a database that already has data.
- Column names, types, nullability and lengths match the `@Column`/`@Table` mappings exactly.

## Tool Reference

Read only the reference for the project's tool: `references/liquibase.md` (master changelog, changeSet rules, YAML examples) or `references/flyway.md` (file naming, database module, SQL examples). Both create the same tables.

## Safe Changes

- New `NOT NULL` column on an existing table: add it with a default, or add nullable → backfill → add the constraint in a later migration.
- Renames and drops: add the new name first, migrate the data, drop the old one in a later release.
- Indexes on large tables: use the database's non-blocking option (e.g. `CREATE INDEX CONCURRENTLY` on PostgreSQL), which must run outside a transaction (`runInTransaction: false` in Liquibase, `executeInTransaction=false` in Flyway).
- Add an index for every foreign key and every column used in frequent filters.

## Workflow

1. Read the entity changes and the existing migrations.
2. Write the migration with the project's tool, following its reference.
3. Verify with the `testcontainers` test profile from the `testing-patterns` skill (PostgreSQL through `@ServiceConnection`), run by the `tests` agent: the migrations must run from scratch and Hibernate's `validate` must pass. The H2 `test` profile skips migrations, so it proves nothing here.
4. Tell the user about any manual or irreversible steps (data loss, long locks).
