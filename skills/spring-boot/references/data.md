# Data Access - Spring Data JPA

## JPA Entity Pattern

```java
@Entity
@Table(name = "users", indexes = @Index(name = "idx_users_active", columnList = "active"))   // as in the migration
@EntityListeners(AuditingEntityListener.class)
@Getter
@Setter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Setter(AccessLevel.NONE)
    private Long id;

    @Column(nullable = false, unique = true, length = 100)
    private String email;

    @Column(nullable = false, length = 100)
    private String password;

    @Column(nullable = false, unique = true, length = 50)
    private String username;

    @Column(nullable = false)
    private Boolean active = true;

    @OneToMany(mappedBy = "user", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<Address> addresses = new ArrayList<>();

    @ManyToMany
    @JoinTable(
        name = "user_roles",
        joinColumns = @JoinColumn(name = "user_id"),
        inverseJoinColumns = @JoinColumn(name = "role_id")
    )
    private Set<Role> roles = new HashSet<>();

    @CreatedDate
    @Column(nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @LastModifiedDate
    @Column(nullable = false)
    private LocalDateTime updatedAt;

    @Version
    @Setter(AccessLevel.NONE)                   // managed by Hibernate
    private Long version;

    @Builder                                    // business fields only: no id/version
    public User(String email, String password, String username) {
        this.email = email;
        this.password = password;
        this.username = username;
    }

    // Helper methods for bidirectional relationships
    public void addAddress(Address address) {
        addresses.add(address);
        address.setUser(this);
    }

    public void removeAddress(Address address) {
        addresses.remove(address);
        address.setUser(null);
    }
}
```

## Spring Data JPA Repository

```java
@Repository
public interface UserRepository extends JpaRepository<User, Long>,
                                       JpaSpecificationExecutor<User> {

    Optional<User> findByEmail(String email);

    Optional<User> findByUsername(String username);

    boolean existsByEmail(String email);

    boolean existsByUsername(String username);

    @Query("SELECT u FROM User u LEFT JOIN FETCH u.roles WHERE u.email = :email")
    Optional<User> findByEmailWithRoles(@Param("email") String email);

    @Query("SELECT u FROM User u WHERE u.active = true AND u.createdAt >= :since")
    List<User> findActiveUsersSince(@Param("since") LocalDateTime since);

    @Modifying   // runs in the caller's @Transactional service method
    @Query("UPDATE User u SET u.active = false WHERE u.updatedAt < :threshold")
    int deactivateInactiveUsers(@Param("threshold") LocalDateTime threshold);

    // Constructor expression: the target must be a class or record (UserSummaryDto below), not an interface
    @Query("SELECT new com.example.dto.UserSummaryDto(u.id, u.username, u.email) " +
           "FROM User u WHERE u.active = true")
    List<UserSummaryDto> findAllActiveSummaries();
}
```

Dynamic filters: compose `Specification<User>` predicates and pass them to `findAll(spec, pageable)` (`JpaSpecificationExecutor`).

## Transactions and Fetching

The transaction rules are in the `conventions` skill; N+1 fixes, lazy loading and transaction pitfalls are in the `jpa-patterns` skill.

## Auditing Configuration

```java
@Configuration
@EnableJpaAuditing
public class JpaAuditingConfig {

    @Bean
    public AuditorAware<String> auditorProvider() {
        return () -> {
            Authentication authentication = SecurityContextHolder
                .getContext()
                .getAuthentication();

            if (authentication == null || !authentication.isAuthenticated()) {
                return Optional.of("system");
            }

            return Optional.of(authentication.getName());
        };
    }
}

@MappedSuperclass
@EntityListeners(AuditingEntityListener.class)
@Getter
@Setter
public abstract class AuditableEntity {

    @CreatedDate
    @Column(nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @CreatedBy
    @Column(nullable = false, updatable = false, length = 100)
    private String createdBy;

    @LastModifiedDate
    @Column(nullable = false)
    private LocalDateTime updatedAt;

    @LastModifiedBy
    @Column(nullable = false, length = 100)
    private String updatedBy;
}
```

## Projections

```java
// Interface-based projection
public interface UserSummary {
    Long getId();
    String getUsername();
    String getEmail();

    @Value("#{target.username + ' <' + target.email + '>'}")   // open projection: loads the whole entity
    String getDisplayName();
}

// Class-based projection (DTO)
public record UserSummaryDto(
    Long id,
    String username,
    String email
) {}

// Usage
public interface UserRepository extends JpaRepository<User, Long> {
    List<UserSummary> findAllBy();

    <T> List<T> findAllBy(Class<T> type);
}

// Service usage
List<UserSummary> summaries = userRepository.findAllBy();
List<UserSummaryDto> dtos = userRepository.findAllBy(UserSummaryDto.class);
```

## Database Migrations

Schema changes live in versioned Liquibase or Flyway migrations, never in `ddl-auto`; rules and examples are in the `db-migrations` skill.
