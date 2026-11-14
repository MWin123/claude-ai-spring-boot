# Reactive Slices, Integration Tests and Test Data

More test types for the `testing-patterns` skill. The `test` and `testcontainers` profiles, `TestcontainersConfig` and the positive/negative rule are in its `SKILL.md`.

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
            .value(product -> assertThat(product.getName()).isEqualTo("Widget"));
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

## Integration Tests (@SpringBootTest)

```java
@SpringBootTest   // MOCK environment: requests run through MockMvc on the test thread, so @WithMockUser applies
@AutoConfigureMockMvc
@AutoConfigureRestTestClient   // bound to MockMvc when it is present
@ActiveProfiles("testcontainers")
@Import(TestcontainersConfig.class)
@WithMockUser(roles = "ADMIN")   // POST requires ADMIN, and CSRF applies without a bearer token (security.md in the spring-boot skill); 403 cases are in the slice test
class ProductIntegrationTest {

    @Autowired
    private RestTestClient restTestClient;

    @Autowired
    private ProductRepository productRepository;

    @BeforeEach
    void setUp() {
        productRepository.deleteAll();
        // CookieCsrfTokenRepository accepts any token whose cookie and header match
        restTestClient = restTestClient.mutate().defaultCookie("XSRF-TOKEN", "test").defaultHeader("X-XSRF-TOKEN", "test").build();
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

        Long id = created.getId();

        // Read
        restTestClient.get()
            .uri("/api/v1/products/{id}", id)
            .exchange()
            .expectStatus().isOk()
            .expectBody(ProductResponse.class)
            .value(product -> assertThat(product.getName()).isEqualTo("Widget"));

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
