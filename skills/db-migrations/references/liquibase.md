# Liquibase

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
      file: db/changelog/changes/002-create-addresses-table.yaml
  - include:
      file: db/changelog/changes/003-create-roles-tables.yaml
  - include:
      file: db/changelog/changes/004-create-products-table.yaml
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
# src/main/resources/db/changelog/changes/002-create-addresses-table.yaml
databaseChangeLog:
  - changeSet:
      id: 002-create-addresses-table
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
```

```yaml
# src/main/resources/db/changelog/changes/003-create-roles-tables.yaml
databaseChangeLog:
  - changeSet:
      id: 003-create-roles-tables
      author: app
      changes:
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
  - changeSet:
      id: 003-insert-user-role
      author: app
      changes:
        - insert:
            tableName: roles
            columns:
              - column: { name: name, value: USER }
      rollback:   # Liquibase can't derive one for data changes
        - delete:
            tableName: roles
            where: name = 'USER'
```

```yaml
# src/main/resources/db/changelog/changes/004-create-products-table.yaml (Product in the spring-boot skill)
databaseChangeLog:
  - changeSet:
      id: 004-create-products-table
      author: app
      changes:
        - createTable:
            tableName: products
            columns:
              - column: { name: id, type: BIGINT, autoIncrement: true, constraints: { primaryKey: true } }
              - column: { name: name, type: VARCHAR(100), constraints: { nullable: false } }
              - column: { name: price, type: "DECIMAL(10, 2)", constraints: { nullable: false } }
```
