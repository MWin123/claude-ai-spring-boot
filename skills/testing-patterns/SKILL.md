---
name: testing-patterns
description: Testing patterns for Spring Boot - JUnit 5, Mockito, MockMvc, WebTestClient, RestTestClient, @DataJpaTest on H2 or Testcontainers, positive and negative test cases. Use when user asks about testing, writing tests, test coverage, or test failures.
---

# Testing Patterns Skill

Testing strategies for Spring Boot applications. Always write both positive and negative test cases.

## When to Use
- "write tests" / "add test coverage" / "test this"
- Test failures or debugging test issues
- Choosing between unit, slice, and integration tests

---

## Test Pyramid

| Level | Annotation | Speed | Scope | When to Use |
|-------|-----------|-------|-------|-------------|
| Unit | `@ExtendWith(MockitoExtension.class)` | Fast | Single class | Business logic in services |
| Slice | `@WebMvcTest`, `@WebFluxTest`, `@DataJpaTest` | Medium | One layer | Controllers, repositories |
| Integration | `@SpringBootTest` | Slow | Full app | End-to-end flows, cross-layer |

---

## Test Profiles

Two profiles with separate jobs. Both live in `src/test/resources`.

```yaml
# application-test.yml: fast repository tests on in-memory H2 (com.h2database:h2, test scope).
# MODE=PostgreSQL makes H2 accept more PostgreSQL syntax; Hibernate builds the schema.
# Migrations are off because they may use PostgreSQL-only SQL.
spring:
  datasource:
    url: jdbc:h2:mem:testdb;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DEFAULT_NULL_ORDERING=HIGH
    driver-class-name: org.h2.Driver
  test:
    database:
      replace: none   # keep the URL above; @DataJpaTest would otherwise swap in a default embedded H2
  flyway:
    enabled: false
  liquibase:
    enabled: false
  jpa:
    hibernate:
      ddl-auto: create-drop
```

```yaml
# application-testcontainers.yml: real PostgreSQL through @ServiceConnection.
# Migrations build the schema; validate fails if they drift from the entities.
spring:
  jpa:
    hibernate:
      ddl-auto: validate
```

- `test` (H2) checks repository queries and mappings without Docker. It cannot catch a migration that no longer matches the entities, or a query that only fails on PostgreSQL (native queries, database functions).
- `testcontainers` catches both. Use it for integration tests and for verifying migrations.

---

## Unit Tests (Service Layer)

```java
@ExtendWith(MockitoExtension.class)
class OrderServiceTest {

    @Mock
    private OrderRepository orderRepository;

    @Mock
    private ProductService productService;

    @InjectMocks
    private OrderService orderService;

    // ✅ Positive test
    @Test
    @DisplayName("Should create order with valid items")
    void shouldCreateOrder() {
        // Given
        var request = new OrderRequest(List.of(
            new OrderItem(1L, 2)
        ));
        var product = Product.builder().price(new BigDecimal("10.00")).build();
        ReflectionTestUtils.setField(product, "id", 1L);   // generated id has no setter

        when(productService.findById(1L)).thenReturn(product);
        when(orderRepository.save(any(Order.class))).thenAnswer(inv -> {
            Order o = inv.getArgument(0);
            ReflectionTestUtils.setField(o, "id", 1L);
            return o;
        });

        // When
        Order result = orderService.create(request);

        // Then
        assertThat(result.getId()).isEqualTo(1L);
        verify(orderRepository).save(any(Order.class));
    }

    // ✅ Negative test
    @Test
    @DisplayName("Should throw when product not found")
    void shouldThrowWhenProductNotFound() {
        // Given
        var request = new OrderRequest(List.of(
            new OrderItem(999L, 1)
        ));
        when(productService.findById(999L))
            .thenThrow(new EntityNotFoundException("Product not found"));

        // When & Then
        assertThatThrownBy(() -> orderService.create(request))
            .isInstanceOf(EntityNotFoundException.class)
            .hasMessageContaining("Product not found");

        verify(orderRepository, never()).save(any());
    }

    // ✅ Negative test - empty input
    @Test
    @DisplayName("Should throw when order has no items")
    void shouldThrowWhenNoItems() {
        var request = new OrderRequest(List.of());

        assertThatThrownBy(() -> orderService.create(request))
            .isInstanceOf(IllegalArgumentException.class);
    }
}
```

---

## Controller Slice Tests (@WebMvcTest)

```java
@WebMvcTest(ProductController.class)
@Import(SecurityConfig.class)   // assumes it restricts POST to ADMIN
class ProductControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private ProductService productService;

    // Jackson 3: tools.jackson.databind.json.JsonMapper (not com.fasterxml.jackson.databind)
    @Autowired
    private JsonMapper jsonMapper;

    // ✅ Positive - successful creation
    @Test
    @WithMockUser(roles = "ADMIN")
    @DisplayName("POST /api/v1/products - returns 201")
    void createProduct_validRequest_returns201() throws Exception {
        var request = new ProductRequest("Widget", new BigDecimal("10.00"));
        var product = Product.builder().name("Widget").build();
        ReflectionTestUtils.setField(product, "id", 1L);

        when(productService.create(any())).thenReturn(product);

        mockMvc.perform(post("/api/v1/products")
                .contentType(MediaType.APPLICATION_JSON)
                .content(jsonMapper.writeValueAsString(request)))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.name").value("Widget"));
    }

    // ✅ Negative - validation failure
    @Test
    @WithMockUser(roles = "ADMIN")
    @DisplayName("POST /api/v1/products - blank name returns 400")
    void createProduct_blankName_returns400() throws Exception {
        var request = new ProductRequest("", new BigDecimal("10.00"));

        mockMvc.perform(post("/api/v1/products")
                .contentType(MediaType.APPLICATION_JSON)
                .content(jsonMapper.writeValueAsString(request)))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.name").exists());

        verify(productService, never()).create(any());
    }

    // ✅ Negative - not found
    @Test
    @WithMockUser
    @DisplayName("GET /api/v1/products/999 - returns 404")
    void getProduct_notFound_returns404() throws Exception {
        when(productService.findById(999L))
            .thenThrow(new EntityNotFoundException("Product not found"));

        mockMvc.perform(get("/api/v1/products/999"))
            .andExpect(status().isNotFound());
    }

    // ✅ Negative - security rule
    @Test
    @WithMockUser(roles = "USER")
    @DisplayName("POST /api/v1/products - non-admin returns 403")
    void createProduct_nonAdmin_returns403() throws Exception {
        var request = new ProductRequest("Widget", new BigDecimal("10.00"));

        mockMvc.perform(post("/api/v1/products")
                .contentType(MediaType.APPLICATION_JSON)
                .content(jsonMapper.writeValueAsString(request)))
            .andExpect(status().isForbidden());
    }
}
```

---

## Reactive Controller Slice Tests (@WebFluxTest)

```java
@WebFluxTest(ProductReactiveController.class)
class ProductReactiveControllerTest {

    @Autowired
    private WebTestClient webTestClient;

    @MockitoBean
    private ProductReactiveService productService;

    // ✅ Positive
    @Test
    @DisplayName("GET /api/v1/products/1 - returns the product")
    void getProduct_exists_returns200() {
        when(productService.findById(1L))
            .thenReturn(Mono.just(new ProductResponse(1L, "Widget", new BigDecimal("10.00"))));

        webTestClient.get()
            .uri("/api/v1/products/{id}", 1L)
            .exchange()
            .expectStatus().isOk()
            .expectBody(ProductResponse.class)
            .value(product -> assertThat(product.name()).isEqualTo("Widget"));
    }

    // ✅ Negative
    @Test
    @DisplayName("GET /api/v1/products/999 - returns 404")
    void getProduct_missing_returns404() {
        when(productService.findById(999L)).thenReturn(Mono.empty());

        webTestClient.get()
            .uri("/api/v1/products/{id}", 999L)
            .exchange()
            .expectStatus().isNotFound();
    }
}
```

---

## Testcontainers Reusable Config

```java
@TestConfiguration(proxyBeanMethods = false)
public class TestcontainersConfig {

    @Bean
    @ServiceConnection
    public PostgreSQLContainer<?> postgresContainer() {
        return new PostgreSQLContainer<>("postgres:16-alpine");
    }
}
```

Import it with `@Import(TestcontainersConfig.class)` together with the `testcontainers` profile. `@ServiceConnection` replaces `@DynamicPropertySource`.

---

## Repository Slice Tests (@DataJpaTest)

### On H2 (default, fast)

```java
@DataJpaTest
@ActiveProfiles("test")
class ProductRepositoryTest {

    @Autowired
    private ProductRepository productRepository;

    @Autowired
    private TestEntityManager entityManager;

    // ✅ Positive
    @Test
    @DisplayName("Should find products by name containing")
    void shouldFindByNameContaining() {
        // Given
        var product = Product.builder()
            .name("Spring Widget")
            .price(new BigDecimal("10.00"))
            .build();
        entityManager.persistAndFlush(product);

        // When
        List<Product> results = productRepository
            .findByNameContainingIgnoreCase("widget");

        // Then
        assertThat(results).hasSize(1);
        assertThat(results.get(0).getName()).isEqualTo("Spring Widget");
    }

    // ✅ Negative
    @Test
    @DisplayName("Should return empty list when no match")
    void shouldReturnEmptyWhenNoMatch() {
        List<Product> results = productRepository
            .findByNameContainingIgnoreCase("nonexistent");

        assertThat(results).isEmpty();
    }
}
```

### On Testcontainers (migrations and PostgreSQL)

```java
@DataJpaTest
@ActiveProfiles("testcontainers")
@Import(TestcontainersConfig.class)
class ProductRepositoryContainerTest {

    @Autowired
    private ProductRepository productRepository;

    @Autowired
    private TestEntityManager entityManager;

    // ✅ Positive: the context only starts if the migrations ran and match the entities
    @Test
    @DisplayName("Should persist and find a product in PostgreSQL")
    void shouldPersistAndFind() {
        var product = Product.builder()
            .name("Spring Widget")
            .price(new BigDecimal("10.00"))
            .build();
        entityManager.persistAndFlush(product);

        assertThat(productRepository.findByNameContainingIgnoreCase("widget")).hasSize(1);
    }

    // ✅ Negative
    @Test
    @DisplayName("Should return empty list when no match")
    void shouldReturnEmptyWhenNoMatch() {
        assertThat(productRepository.findByNameContainingIgnoreCase("nonexistent")).isEmpty();
    }
}
```

Neither example needs `@AutoConfigureTestDatabase`. The `test` profile sets `spring.test.database.replace: none`, so its H2 URL is used. Under the `testcontainers` profile the Boot 4 default (`Replace.NON_TEST`) keeps the `@ServiceConnection` datasource.

---

## Integration Tests (@SpringBootTest)

```java
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@AutoConfigureRestTestClient
@ActiveProfiles("testcontainers")
@Import(TestcontainersConfig.class)
class ProductIntegrationTest {

    @Autowired
    private RestTestClient restTestClient;

    @Autowired
    private ProductRepository productRepository;

    @BeforeEach
    void setUp() {
        productRepository.deleteAll();
    }

    // ✅ Positive
    @Test
    @DisplayName("Full CRUD flow works end-to-end")
    void crudFlow() {
        // Create
        var request = new ProductRequest("Widget", new BigDecimal("10.00"));
        var created = restTestClient.post()
            .uri("/api/v1/products")
            .contentType(MediaType.APPLICATION_JSON)
            .body(request)
            .exchange()
            .expectStatus().isCreated()
            .expectBody(ProductResponse.class)
            .returnResult()
            .getResponseBody();

        Long id = created.id();

        // Read
        restTestClient.get()
            .uri("/api/v1/products/{id}", id)
            .exchange()
            .expectStatus().isOk()
            .expectBody(ProductResponse.class)
            .value(product -> assertThat(product.name()).isEqualTo("Widget"));

        // Delete
        restTestClient.delete()
            .uri("/api/v1/products/{id}", id)
            .exchange()
            .expectStatus().isNoContent();

        restTestClient.get()
            .uri("/api/v1/products/{id}", id)
            .exchange()
            .expectStatus().isNotFound();
    }

    // ✅ Negative
    @Test
    @DisplayName("Invalid request returns 400")
    void invalidRequest_returns400() {
        restTestClient.post()
            .uri("/api/v1/products")
            .contentType(MediaType.APPLICATION_JSON)
            .body(new ProductRequest("", new BigDecimal("-1")))
            .exchange()
            .expectStatus().isBadRequest();
    }
}
```

---

## Test Configuration and Data

```java
@TestConfiguration(proxyBeanMethods = false)
public class TestConfig {

    @Bean
    @Primary
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder(4); // faster for tests
    }

    @Bean
    public Clock fixedClock() {
        return Clock.fixed(Instant.parse("2024-01-01T00:00:00Z"), ZoneOffset.UTC);
    }
}

public final class TestData {

    private TestData() {}

    public static Product product(String name) {
        return Product.builder().name(name).price(new BigDecimal("10.00")).build();
    }

    public static ProductRequest productRequest() {
        return new ProductRequest("Widget", new BigDecimal("10.00"));
    }
}
```

---

## Parameterized Tests

```java
@ParameterizedTest
@ValueSource(strings = {"", " ", "ab"})
@DisplayName("Should reject invalid usernames")
void shouldRejectInvalidUsername(String username) {
    var request = new UserRequest(username, "valid@email.com");

    assertThatThrownBy(() -> userService.create(request))
        .isInstanceOf(ConstraintViolationException.class);
}

@ParameterizedTest
@CsvSource({
    "admin@test.com, ADMIN, true",
    "user@test.com, USER, true",
    "guest@test.com, GUEST, false"
})
@DisplayName("Should check access by role")
void shouldCheckAccessByRole(String email, String role, boolean expected) {
    assertThat(securityService.hasAccess(email, role)).isEqualTo(expected);
}
```

---

## Quick Reference

| Pattern | Use For |
|---------|---------|
| `@ExtendWith(MockitoExtension.class)` | Unit tests with mocks |
| `@WebMvcTest(Controller.class)` | Controller tests with MockMvc |
| `@WebFluxTest(Controller.class)` | Reactive controller tests with WebTestClient |
| `@DataJpaTest` + `test` profile | Repository tests on H2 |
| `@DataJpaTest` + `testcontainers` profile | Repository tests on PostgreSQL, migrations validated |
| `@SpringBootTest` + `RANDOM_PORT` + `@AutoConfigureRestTestClient` | Full integration tests with `RestTestClient` |
| `@ServiceConnection` | Auto-configure Testcontainers (not `@DynamicPropertySource`) |
| `@MockitoBean` | Mock a bean in the Spring context (`@MockBean` is removed in Boot 4) |
| `@WithMockUser` | Authenticated user for security tests |
| `@ParameterizedTest` | Multiple inputs, same assertion |
| `assertThatThrownBy()` | Negative test - expect exception |
| `verify(mock, never())` | Verify method was NOT called |

## Naming Convention

```
methodUnderTest_condition_expectedResult
```

Examples: `createUser_validRequest_returns201`, `createUser_duplicateEmail_throws409`

## Best Practices

- Arrange / Act / Assert (Given / When / Then), descriptive `@DisplayName`
- A positive and a negative case for every behavior, including validation and security rules
- Mock external dependencies; use the `testcontainers` profile wherever the database matters
- Keep tests independent: no shared mutable state, no ordering between tests
