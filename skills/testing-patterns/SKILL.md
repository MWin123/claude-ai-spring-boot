---
name: testing-patterns
description: Testing patterns for Spring Boot - JUnit 5, Mockito, MockMvc, WebTestClient, RestTestClient, @DataJpaTest on H2 or Testcontainers, positive and negative test cases.
when_to_use: '"write tests", "add test coverage", "test this"; failing tests; choosing between unit, slice and integration tests.'
---

# Testing Patterns Skill

Testing strategies for Spring Boot applications. Always write both positive and negative test cases, named `methodUnderTest_condition_expectedResult`.

Unit tests (`MockitoExtension`) cover business logic in services, slice tests (`@WebMvcTest`, `@WebFluxTest`, `@DataJpaTest`) one layer, and `@SpringBootTest` end-to-end flows across layers.

## References

| Topic | Reference |
|-------|-----------|
| Reactive controller slice tests (`@WebFluxTest`), integration tests (`@SpringBootTest` with `RestTestClient`), test configuration and test data | `references/integration.md` |

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
        var request = new OrderRequest(List.of(new OrderItem(1L, 2)));
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
        var request = new OrderRequest(List.of(new OrderItem(999L, 1)));
        when(productService.findById(999L))
            .thenThrow(new ResourceNotFoundException("Product not found"));

        // When & Then
        assertThatThrownBy(() -> orderService.create(request))
            .isInstanceOf(ResourceNotFoundException.class)
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

## Controller Slice Tests (@WebMvcTest)

```java
@WebMvcTest(ProductController.class)
@Import(SecurityConfig.class)   // restricts POST to ADMIN and keeps CSRF on for requests without a bearer token (security.md in the spring-boot skill)
class ProductControllerTest {

    @Autowired private MockMvc mockMvc;
    @MockitoBean private ProductService productService;
    // SecurityConfig's resource server needs both; @WithMockUser authenticates without a token
    @MockitoBean private JwtDecoder jwtDecoder;
    @MockitoBean private UserDetailsService userDetailsService;

    // Jackson 3: tools.jackson.databind.json.JsonMapper (not com.fasterxml.jackson.databind)
    @Autowired private JsonMapper jsonMapper;

    // ✅ Positive - successful creation (ProductRequest/ProductResponse are the generated models)
    @Test
    @WithMockUser(roles = "ADMIN")
    @DisplayName("POST /api/v1/products - returns 201")
    void createProduct_validRequest_returns201() throws Exception {
        var request = new ProductRequest("Widget", new BigDecimal("10.00"));
        when(productService.create(any())).thenReturn(new ProductResponse(1L, "Widget", new BigDecimal("10.00")));

        mockMvc.perform(post("/api/v1/products")
                .with(csrf())   // SecurityMockMvcRequestPostProcessors.csrf(); without it every POST is 403
                .contentType(MediaType.APPLICATION_JSON)
                .content(jsonMapper.writeValueAsString(request)))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.name").value("Widget"))
            .andExpect(jsonPath("$.price").value("10.00"));   // bigDecimalAsString
    }

    // ✅ Negative - validation failure at the spec's limits (name: minLength 1, maxLength 100)
    @ParameterizedTest
    @ValueSource(ints = {0, 101})
    @WithMockUser(roles = "ADMIN")
    @DisplayName("POST /api/v1/products - name length out of range returns 400")
    void createProduct_nameLengthOutOfRange_returns400(int length) throws Exception {
        var request = new ProductRequest("x".repeat(length), new BigDecimal("10.00"));

        mockMvc.perform(post("/api/v1/products")
                .with(csrf())   // SecurityMockMvcRequestPostProcessors.csrf(); without it every POST is 403
                .contentType(MediaType.APPLICATION_JSON)
                .content(jsonMapper.writeValueAsString(request)))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.errors.name").exists());   // field errors from the handler in web.md of the spring-boot skill

        verify(productService, never()).create(any());
    }

    // ✅ Negative - not found
    @Test
    @WithMockUser
    @DisplayName("GET /api/v1/products/999 - returns 404")
    void getProduct_notFound_returns404() throws Exception {
        when(productService.findById(999L))
            .thenThrow(new ResourceNotFoundException("Product not found"));

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
                .with(csrf())   // SecurityMockMvcRequestPostProcessors.csrf(); without it every POST is 403
                .contentType(MediaType.APPLICATION_JSON)
                .content(jsonMapper.writeValueAsString(request)))
            .andExpect(status().isForbidden());
    }
}
```

Test input validation in this slice, as `createProduct_nameLengthOutOfRange_returns400` does: the constraints live on the generated interfaces and models, not on the service.

## Testcontainers Reusable Config

```java
@TestConfiguration(proxyBeanMethods = false)
public class TestcontainersConfig {

    @Bean
    @ServiceConnection
    public PostgreSQLContainer postgresContainer() {   // Testcontainers 2: org.testcontainers.postgresql, not generic
        return new PostgreSQLContainer("postgres:16-alpine");
    }
}
```

Import it with `@Import(TestcontainersConfig.class)` together with the `testcontainers` profile. `@ServiceConnection` replaces `@DynamicPropertySource`.

## Repository Slice Tests (@DataJpaTest)

### On H2 (default, fast)

Entities with auditing fields (`@CreatedDate`, like `User` in `data.md` of the `spring-boot` skill) also need `@Import(JpaAuditingConfig.class)`: slices don't load the `@Configuration` that carries `@EnableJpaAuditing`, so `created_at` stays NULL and the insert fails.

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
