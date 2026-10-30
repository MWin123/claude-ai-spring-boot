---
name: db-migrations
description: Database schema migrations for Spring Boot with Liquibase (default) or Flyway - new tables or columns, indexes, data backfills, safe NOT NULL/rename/drop changes, kept consistent with the JPA entities. Use when an entity changes or the user asks for a migration, changelog or schema change.
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

## Liquibase

- Master file `src/main/resources/db/changelog/db.changelog-master.yaml` (Spring Boot's default location) that only includes the others; one file per change in `db/changelog/changes/`, named `NNN-description.yaml` (zero-padded, next free number).
- Prefer YAML with Liquibase change types (`createTable`, `addColumn`, `createIndex`) so the changes stay portable; use `sql` changes only when no change type fits.
- Every `changeSet` has a unique `id` (the file number plus a short slug) and an `author` (the project or team name, not a person). Add `rollback` blocks where Liquibase can't infer one (raw SQL, data changes).
- Never use `runOnChange` or edit a changeSet after it ran: Liquibase checksums it and startup fails.
- `preConditions` with `onFail: MARK_RAN` only to adopt an existing database, never to hide errors.
- Contexts (`context: test`) only for test data, never for schema.

```yaml
# src/main/resources/db/changelog/db.changelog-master.yaml
databaseChangeLog:
  - include:
      file: db/changelog/changes/001-create-users-table.yaml
  - include:
      file: db/changelog/changes/002-create-addresses-and-roles.yaml
```

```yaml
# src/main/resources/db/changelog/changes/001-create-users-table.yaml
databaseChangeLog:
  - changeSet:
      id: 001-create-users-table
      author: app
      changes:
        - createTable:
            tableName: users
            columns:
              - column: { name: id, type: BIGINT, autoIncrement: true, constraints: { primaryKey: true } }
              - column: { name: email, type: VARCHAR(100), constraints: { nullable: false, unique: true } }
              - column: { name: password, type: VARCHAR(100), constraints: { nullable: false } }
              - column: { name: username, type: VARCHAR(50), constraints: { nullable: false, unique: true } }
              - column: { name: active, type: BOOLEAN, defaultValueBoolean: true, constraints: { nullable: false } }
              - column: { name: created_at, type: TIMESTAMP, defaultValueComputed: CURRENT_TIMESTAMP, constraints: { nullable: false } }
              - column: { name: updated_at, type: TIMESTAMP, defaultValueComputed: CURRENT_TIMESTAMP, constraints: { nullable: false } }
              - column: { name: version, type: BIGINT, defaultValueNumeric: 0, constraints: { nullable: false } }
        - createIndex:
            indexName: idx_users_active
            tableName: users
            columns:
              - column: { name: active }
```

```yaml
# src/main/resources/db/changelog/changes/002-create-addresses-and-roles.yaml
databaseChangeLog:
  - changeSet:
      id: 002-create-addresses-and-roles
      author: app
      changes:
        - createTable:
            tableName: addresses
            columns:
              - column: { name: id, type: BIGINT, autoIncrement: true, constraints: { primaryKey: true } }
              - column: { name: user_id, type: BIGINT, constraints: { nullable: false, foreignKeyName: fk_addresses_user, references: users(id), deleteCascade: true } }
              - column: { name: street, type: VARCHAR(200), constraints: { nullable: false } }
              - column: { name: city, type: VARCHAR(100), constraints: { nullable: false } }
              - column: { name: country, type: VARCHAR(2), constraints: { nullable: false } }
              - column: { name: created_at, type: TIMESTAMP, defaultValueComputed: CURRENT_TIMESTAMP, constraints: { nullable: false } }
        - createIndex:
            indexName: idx_addresses_user_id
            tableName: addresses
            columns:
              - column: { name: user_id }
        - createTable:
            tableName: roles
            columns:
              - column: { name: id, type: BIGINT, autoIncrement: true, constraints: { primaryKey: true } }
              - column: { name: name, type: VARCHAR(50), constraints: { nullable: false, unique: true } }
        - createTable:
            tableName: user_roles
            columns:
              - column: { name: user_id, type: BIGINT, constraints: { nullable: false, primaryKey: true, foreignKeyName: fk_user_roles_user, references: users(id), deleteCascade: true } }
              - column: { name: role_id, type: BIGINT, constraints: { nullable: false, primaryKey: true, foreignKeyName: fk_user_roles_role, references: roles(id) } }
        - insert:
            tableName: roles
            columns:
              - column: { name: name, value: USER }
```

## Flyway

- SQL in `src/main/resources/db/migration`, named `V<n>__<snake_case_description>.sql`; take the next free number after checking existing files.

```sql
-- V1__create_users_table.sql
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(100) NOT NULL,
    username VARCHAR(50) NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    version BIGINT NOT NULL DEFAULT 0
);

CREATE INDEX idx_users_active ON users(active);

-- V2__create_addresses_table.sql
CREATE TABLE addresses (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    street VARCHAR(200) NOT NULL,
    city VARCHAR(100) NOT NULL,
    country VARCHAR(2) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_addresses_user_id ON addresses(user_id);

-- V3__create_roles_tables.sql
CREATE TABLE roles (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE user_roles (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id BIGINT NOT NULL REFERENCES roles(id),
    PRIMARY KEY (user_id, role_id)
);

INSERT INTO roles (name) VALUES ('USER');
```

## Safe Changes

- New `NOT NULL` column on an existing table: add it with a default, or add nullable → backfill → add the constraint in a later migration.
- Renames and drops: add the new name first, migrate the data, drop the old one in a later release.
- Indexes on large tables: use the database's non-blocking option (e.g. `CREATE INDEX CONCURRENTLY` on PostgreSQL), which must run outside a transaction (`runInTransaction: false` in Liquibase, `executeInTransaction=false` in Flyway).
- Add an index for every foreign key and every column used in frequent filters.

## Workflow

1. Read the entity changes and the existing migrations.
2. Write the migration with the project's tool.
3. Verify with the `testcontainers` test profile from the `testing-patterns` skill (PostgreSQL through `@ServiceConnection`), run by the `tests` agent: the migrations must run from scratch and Hibernate's `validate` must pass. The H2 `test` profile skips migrations, so it proves nothing here.
4. Tell the user about any manual or irreversible steps (data loss, long locks).
