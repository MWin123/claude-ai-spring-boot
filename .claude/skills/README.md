# Skills

Skills are reusable prompts that teach Claude specific patterns for Java development.

## Structure Convention

Each skill folder contains:

| File | Purpose | Audience |
|------|---------|----------|
| `SKILL.md` | Instructions for Claude | AI (loaded with `view`) |

## Available Skills

### Core
| Skill | Description |
|-------|-------------|
| [spring-boot](spring-boot/) | Spring Boot 4.x development - REST APIs, JPA, Security, Testing, Cloud-native patterns. Includes reference guides for web, data, security, cloud, and testing |

### Code Quality
| Skill | Description |
|-------|-------------|
| [code-quality](code-quality/) | Comprehensive code review - clean code principles, API contracts, null safety, exception handling, performance |
| [design-patterns](design-patterns/) | Design patterns - classic (Factory, Builder, Strategy, Observer, Decorator, Adapter) and enterprise (Saga, Outbox, CQRS) |
| [testing-patterns](testing-patterns/) | Testing strategies - JUnit 5, Mockito, MockMvc, Testcontainers, positive and negative test cases |

### Language & Framework
| Skill | Description |
|-------|-------------|
| [java-modern](java-modern/) | Java 21+ features for Spring Boot - records, sealed classes, pattern matching, virtual threads, text blocks |
| [jpa-patterns](jpa-patterns/) | JPA/Hibernate patterns and common pitfalls (N+1, lazy loading, transactions, queries) |
| [logging-patterns](logging-patterns/) | Structured logging (JSON), SLF4J, MDC, AI-friendly formats for Spring Boot 4.x |

## Adding a New Skill

### Before You Start

Validate your skill idea against existing skills:

- [ ] **No significant overlap** - Check the table above for similar skills
- [ ] **Clear level** - Micro (functions) / Meso (classes) / Macro (packages) / Framework / Cross-cutting
- [ ] **Clear type** - Audit (review existing code) or Template (show how to write)
- [ ] **Unique value** - What does it add that doesn't exist?
- [ ] **Focused scope** - Can be applied in one session (<15 checklist items)

### Implementation Steps

1. Create folder: `.claude/skills/<skill-name>/`
2. Create `SKILL.md` with instructions for Claude
3. Update this table

## Usage

Skills are automatically loaded by Claude Code based on context. You can also invoke them directly:

```bash
# Automatic - Claude detects when to use skills
> "Review this code"              # Loads code-quality
> "Fix N+1 query problem"         # Loads jpa-patterns
> "Add structured logging"        # Loads logging-patterns

# Manual - invoke with slash command
> /code-quality
> /jpa-patterns
```
