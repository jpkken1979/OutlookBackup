---
name: dotnet-backend-patterns
description: Master C#/.NET backend development patterns for building robust APIs, MCP servers, and enterprise applications. Covers async/await, dependency injection, Entity Framework Core, Dapper, configuration, caching, and testing with xUnit. Use when developing .NET backends, reviewing C# code, or designing API architectures.
type: feature
---

# .NET Backend Development Patterns

Master C#/.NET patterns for building production-grade APIs, MCP servers, and enterprise backends with modern best practices.

## When to Use This Skill

- Developing new .NET Web APIs or MCP servers
- Reviewing C# code for quality and performance
- Designing service architectures with dependency injection
- Implementing caching strategies with Redis
- Writing unit and integration tests
- Optimizing database access with EF Core or Dapper
- Configuring applications with IOptions pattern
- Handling errors and implementing resilience patterns

## Architecture Patterns

### Clean Architecture Structure

```
src/
├── Domain/               # Enterprise business rules
│   ├── Entities/         # Core business objects
│   ├── ValueObjects/     # Immutable value types
│   ├── Enums/            # Domain enums
│   └── Interfaces/       # Repository contracts
├── Application/          # Application business rules
│   ├── DTOs/            # Data transfer objects
│   ├── Interfaces/       # Service contracts
│   ├── Services/         # Business logic services
│   └── Behaviors/        # MediatR pipeline behaviors
├── Infrastructure/       # External concerns
│   ├── Data/            # EF Core, repositories
│   ├── Services/         # External service implementations
│   └── Caching/         # Redis cache implementations
└── Presentation/        # Web API layer
    ├── Controllers/     # API controllers
    ├── Filters/         # Action filters
    └── Middleware/      # Custom middleware
```

### Layered Architecture

```
Controllers → Services → Repositories → Database
```

## Core Patterns

### Pattern 1: Dependency Injection

```csharp
// Program.cs
var builder = WebApplication.CreateBuilder(args);

// Add services
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

// Register application services
builder.Services.AddScoped<IUserService, UserService>();
builder.Services.AddScoped<IUserRepository, UserRepository>();

// Register infrastructure
builder.Services.AddDbContext<AppDbContext>(
    options => options.UseSqlServer(builder.Configuration.GetConnectionString("Default"))
);

// Keyed services for multiple implementations
builder.Services.AddKeyedScoped<IMessageSender, EmailSender>("email");
builder.Services.AddKeyedScoped<IMessageSender, SmsSender>("sms");

// Options pattern
builder.Services.Configure<CacheOptions>(
    builder.Configuration.GetSection("Cache")
);

var app = builder.Build();
```

```csharp
// Constructor injection
public class UserService : IUserService
{
    private readonly IUserRepository _userRepository;
    private readonly ICacheService _cache;
    private readonly ILogger<UserService> _logger;

    public UserService(
        IUserRepository userRepository,
        ICacheService cache,
        ILogger<UserService> logger)
    {
        _userRepository = userRepository;
        _cache = cache;
        _logger = logger;
    }
}
```

### Pattern 2: Async/Await with ConfigureAwait

```csharp
// Always use async for I/O operations
public async Task<UserDto?> GetUserByIdAsync(int id, CancellationToken ct = default)
{
    // ConfigureAwait(false) in library code prevents deadlocks
    // In ASP.NET Core controllers, ConfigureAwait(true) or omitted is fine
    var user = await _dbContext.Users
        .AsNoTracking()
        .FirstOrDefaultAsync(u => u.Id == id, ct)
        .ConfigureAwait(false);

    return user is null ? null : MapToDto(user);
}

// Never use .Result or .GetAwaiter().GetResult() - causes deadlocks
// Correct:
public async Task<UserDto> GetUserAsync(int id)
{
    return await _userService.GetUserByIdAsync(id);
}

// For background operations, use IBackgroundTaskQueue
public class BackgroundTaskQueue : IBackgroundTaskQueue
{
    private readonly Channel<Func<CancellationToken, Task>> _queue;

    public async Task<Func<CancellationToken, Task>> DequeueAsync(CancellationToken ct)
    {
        return await _queue.Reader.ReadAsync(ct).ConfigureAwait(false);
    }
}
```

### Pattern 3: IOptions Pattern for Configuration

```csharp
// Configuration class
public class AppSettings
{
    public DatabaseSettings Database { get; set; } = new();
    public CacheSettings Cache { get; set; } = new();
    public AuthSettings Auth { get; set; } = new();
}

public class DatabaseSettings
{
    public string ConnectionString { get; set; } = "";
    public int CommandTimeout { get; set; } = 30;
}

// Binding in Program.cs
builder.Services.Configure<AppSettings>(
    builder.Configuration.GetSection("AppSettings")
);

// Usage in service
public class UserRepository : IUserRepository
{
    private readonly AppDbContext _db;
    private readonly int _commandTimeout;

    public UserRepository(AppDbContext db, IOptions<AppSettings> options)
    {
        _db = db;
        _commandTimeout = options.Value.Database.CommandTimeout;
    }
}

// IOptionsSnapshot for per-request configuration (scoped)
public class PerRequestConfigService
{
    public PerRequestConfigService(IOptionsSnapshot<FeaturesSettings> features)
    {
        var enabled = features.Value.EnableNewFeature; // Changes per request
    }
}

// IOptionsMonitor for real-time changes (singleton)
public class ConfigMonitorService
{
    public ConfigMonitorService(IOptionsMonitor<CacheSettings> monitor)
    {
        monitor.OnChange(settings => {
            // React to configuration changes
            _cacheDuration = settings.Duration;
        });
    }
}
```

### Pattern 4: Result Pattern for Error Handling

```csharp
// Result type definition
public class Result<T>
{
    public bool IsSuccess { get; }
    public T? Value { get; }
    public Error? Error { get; }

    private Result(bool isSuccess, T? value, Error? error)
    {
        IsSuccess = isSuccess;
        Value = value;
        Error = error;
    }

    public static Result<T> Success(T value) => new(true, value, null);
    public static Result<T> Failure(Error error) => new(false, default, error);
}

public record Error(string Code, string Message);

// Usage in service
public async Task<Result<UserDto>> CreateUserAsync(CreateUserCommand command)
{
    if (await _userRepository.ExistsByEmailAsync(command.Email))
    {
        return Result<UserDto>.Failure(
            new Error("USER_EXISTS", "A user with this email already exists.")
        );
    }

    var user = User.Create(command.Name, command.Email);
    await _userRepository.AddAsync(user);

    return Result<UserDto>.Success(MapToDto(user));
}

// Controller handling
[HttpPost]
public async Task<IActionResult> CreateUser([FromBody] CreateUserCommand command)
{
    Result<UserDto> result = await _mediator.Send(command);

    return result.IsSuccess
        ? CreatedAtAction(nameof(GetUser), new { id = result.Value.Id }, result.Value)
        : BadRequest(result.Error);
}
```

### Pattern 5: Entity Framework Core

```csharp
// DbContext with query filters
public class AppDbContext : DbContext
{
    private readonly int _tenantId;

    public AppDbContext(DbContextOptions<AppDbContext> options, ITenantProvider tenant)
        : base(options)
    {
        _tenantId = tenant.TenantId;
    }

    public DbSet<User> Users => Set<User>();
    public DbSet<Order> Orders => Set<Order>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        // Global query filter for multi-tenancy
        modelBuilder.Entity<User>()
            .HasQueryFilter(u => u.TenantId == _tenantId);

        // Entity configurations
        modelBuilder.ApplyConfigurationsFromAssembly(Assembly.GetExecutingAssembly());
    }
}

// Entity with owned types
public class Order : Entity
{
    public int CustomerId { get; private set; }
    public OrderStatus Status { get; private set; }
    public Money TotalAmount { get; private set; }  // Value object
    public Address ShippingAddress { get;; set; }   // Owned type

    private readonly List<OrderLine> _lines = new();
    public IReadOnlyCollection<OrderLine> Lines => _lines.AsReadOnly();
}

public class OrderConfiguration : IEntityTypeConfiguration<Order>
{
    public void Configure(EntityTypeBuilder<Order> builder)
    {
        builder.ToTable("Orders");

        builder.HasKey(o => o.Id);

        builder.OwnsOne(o => o.TotalAmount, money =>
        {
            money.Property(m => m.Currency).HasMaxLength(3);
            money.Property(m => m.Amount).HasPrecision(18, 2);
        });

        builder.OwnsOne(o => o.ShippingAddress);

        builder.HasMany(o => o.Lines)
            .WithOne()
            .HasForeignKey(l => l.OrderId);
    }
}

// Explicit loading for related data
public async Task<OrderDto?> GetOrderWithLinesAsync(int orderId)
{
    var order = await _db.Orders
        .Include(o => o.Lines.Where(l => !l.IsDeleted))
        .Include(o => o.Customer)
        .FirstOrDefaultAsync(o => o.Id == orderId);

    return order is null ? null : MapToDto(order);
}
```

### Pattern 6: Dapper for High-Performance Queries

```csharp
// Dapper repository implementation
public class OrderRepository : IOrderRepository
{
    private readonly IDbConnection _connection;

    public OrderRepository(IDbConnection connection)
    {
        _connection = connection;
    }

    // Multi-mapping for complex objects
    public async Task<OrderDto?> GetOrderWithDetailsAsync(int orderId)
    {
        const string sql = @"
            SELECT
                o.Id, o.OrderDate, o.Status,
                c.Id, c.Name, c.Email,
                ol.Id, ol.ProductName, ol.Quantity, ol.UnitPrice
            FROM Orders o
            INNER JOIN Customers c ON o.CustomerId = c.Id
            INNER JOIN OrderLines ol ON ol.OrderId = o.Id
            WHERE o.Id = @OrderId";

        var orders = await _connection.QueryAsync<Order, Customer, OrderLine, Order>(
            sql,
            (order, customer, line) =>
            {
                order.SetCustomer(customer);
                order.AddLine(line);
                return order;
            },
            new { OrderId = orderId },
            splitOn: "Id,Id"
        );

        return orders.FirstOrDefault();
    }

    // Async enumerate for large result sets
    public async IAsyncEnumerable<Order> GetOrdersByStatusAsync(OrderStatus status)
    {
        const string sql = "SELECT Id, OrderDate, Status, Total FROM Orders WHERE Status = @Status";

        await using var reader = await _connection.ExecuteReaderAsync(sql, new { Status = status });

        var parser = reader.GetRowParser<Order>();

        while (await reader.ReadAsync())
        {
            yield return parser(reader);
        }
    }

    // Transaction for multi-statement operations
    public async Task<bool> CreateOrderAsync(Order order)
    {
        using var transaction = _connection.BeginTransaction();

        try
        {
            const string insertOrder = @"
                INSERT INTO Orders (CustomerId, Status, Total, CreatedAt)
                VALUES (@CustomerId, @Status, @Total, @CreatedAt);
                SELECT CAST(SCOPE_IDENTITY() as int);";

            var orderId = await _connection.ExecuteScalarAsync<int>(
                insertOrder, order, transaction);

            foreach (var line in order.Lines)
            {
                await _connection.ExecuteAsync(
                    "INSERT INTO OrderLines (OrderId, ProductId, Quantity) VALUES (@OrderId, @ProductId, @Quantity)",
                    new { OrderId = orderId, line.ProductId, line.Quantity },
                    transaction);
            }

            transaction.Commit();
            return true;
        }
        catch
        {
            transaction.Rollback();
            throw;
        }
    }
}
```

### Pattern 7: Multi-Level Redis Cache

```csharp
// Cache service with multi-level strategy
public class MultiLevelCacheService : ICacheService
{
    private readonly IMemoryCache _memoryCache;
    private readonly IDatabase _redis;
    private readonly ILogger<MultiLevelCacheService> _logger;

    public MultiLevelCacheService(
        IMemoryCache memoryCache,
        IConnectionMultiplexer redis,
        ILogger<MultiLevelCacheService> logger)
    {
        _memoryCache = memoryCache;
        _redis = redis.GetDatabase();
        _logger = logger;
    }

    public async Task<T?> GetOrCreateAsync<T>(
        string key,
        Func<Task<T?>> factory,
        TimeSpan localExpiry,
        TimeSpan remoteExpiry) where T : class
    {
        // Level 1: Memory cache
        if (_memoryCache.TryGetValue(key, out T? localValue))
        {
            _logger.LogDebug("Cache hit (memory): {Key}", key);
            return localValue;
        }

        // Level 2: Redis
        var remoteValue = await _redis.StringGetAsync(key);
        if (remoteValue.HasValue)
        {
            var deserialized = JsonSerializer.Deserialize<T>(remoteValue!);
            // Populate memory cache
            _memoryCache.Set(key, deserialized, localExpiry);
            _logger.LogDebug("Cache hit (redis): {Key}", key);
            return deserialized;
        }

        // Level 3: Source
        var freshValue = await factory();
        if (freshValue is not null)
        {
            var serialized = JsonSerializer.Serialize(freshValue);
            await _redis.StringSetAsync(key, serialized, remoteExpiry);
            _memoryCache.Set(key, freshValue, localExpiry);
            _logger.LogDebug("Cache populated: {Key}", key);
        }

        return freshValue;
    }

    public async Task InvalidateAsync(string key)
    {
        _memoryCache.Remove(key);
        await _redis.KeyDeleteAsync(key);
        _logger.LogDebug("Cache invalidated: {Key}", key);
    }

    public async Task InvalidatePatternAsync(string pattern)
    {
        var server = _redis.ConnectedServer;
        var keys = server.Keys(pattern: $"*{pattern}*").ToArray();

        foreach (var key in keys)
        {
            await _redis.KeyDeleteAsync(key);
        }

        _logger.LogDebug("Cache pattern invalidated: {Pattern} ({Count} keys)", pattern, keys.Length);
    }
}
```

### Pattern 8: Middleware Pipeline

```csharp
// Exception handling middleware
public class ExceptionHandlingMiddleware
{
    private readonly RequestDelegate _next;
    private readonly ILogger<ExceptionHandlingMiddleware> _logger;

    public ExceptionHandlingMiddleware(RequestDelegate next, ILogger<ExceptionHandlingMiddleware> logger)
    {
        _next = next;
        _logger = logger;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        try
        {
            await _next(context);
        }
        catch (Exception ex)
        {
            await HandleExceptionAsync(context, ex);
        }
    }

    private async Task HandleExceptionAsync(HttpContext context, Exception exception)
    {
        var (statusCode, message) = exception switch
        {
            NotFoundException => (StatusCodes.Status404NotFound, exception.Message),
            ValidationException ve => (StatusCodes.Status400BadRequest, ve.Message),
            UnauthorizedException => (StatusCodes.Status401Unauthorized, "Unauthorized"),
            _ => (StatusCodes.Status500InternalServerError, "An error occurred processing your request.")
        };

        _logger.LogError(exception, "Unhandled exception: {Message}", exception.Message);

        context.Response.StatusCode = statusCode;
        context.Response.ContentType = "application/json";

        await context.Response.WriteAsync(
            JsonSerializer.Serialize(new { error = message, traceId = context.TraceIdentifier })
        );
    }
}

// Registration
app.UseMiddleware<ExceptionHandlingMiddleware>();
```

### Pattern 9: Health Checks

```csharp
// Custom health check
public class DatabaseHealthCheck : IHealthCheck
{
    private readonly AppDbContext _db;

    public DatabaseHealthCheck(AppDbContext db) => _db = db;

    public async Task<HealthCheckResult> CheckHealthAsync(
        HealthCheckContext context,
        CancellationToken cancellationToken = default)
    {
        try
        {
            await _db.Database.CanConnectAsync(cancellationToken);
            return HealthCheckResult.Healthy("Database connection is healthy.");
        }
        catch (Exception ex)
        {
            return HealthCheckResult.Unhealthy("Database connection failed.", ex);
        }
    }
}

// Registration
builder.Services.AddHealthChecks()
    .AddCheck<DatabaseHealthCheck>("database")
    .AddRedis(builder.Configuration["Redis:ConnectionString"], name: "redis")
    .AddDbContextCheck<AppDbContext>();

// Endpoint
app.MapHealthChecks("/health", new HealthCheckOptions
{
    ResponseWriter = async (context, report) =>
    {
        context.Response.ContentType = "application/json";
        await context.Response.WriteAsync(JsonSerializer.Serialize(new
        {
            status = report.Status.ToString(),
            checks = report.Entries.Select(e => new
            {
                name = e.Key,
                status = e.Value.Status.ToString(),
                duration = e.Value.Duration.TotalMilliseconds,
                description = e.Value.Description
            })
        }));
    }
});
```

## Testing Patterns

### Unit Tests with xUnit and Moq

```csharp
// xUnit test class
public class UserServiceTests
{
    private readonly Mock<IUserRepository> _userRepository;
    private readonly Mock<ICacheService> _cache;
    private readonly Mock<ILogger<UserService>> _logger;
    private readonly UserService _sut;

    public UserServiceTests()
    {
        _userRepository = new Mock<IUserRepository>();
        _cache = new Mock<ICacheService>();
        _logger = new Mock<ILogger<UserService>>();

        _sut = new UserService(_userRepository.Object, _cache.Object, _logger.Object);
    }

    [Fact]
    public async Task GetUserById_WhenUserExists_ReturnsUserDto()
    {
        // Arrange
        var userId = 1;
        var user = new User { Id = userId, Name = "John", Email = "john@example.com" };

        _cache.Setup(c => c.GetAsync<UserDto>(It.IsAny<string>(), default))
            .ReturnsAsync((UserDto?)null);
        _userRepository.Setup(r => r.GetByIdAsync(userId, default))
            .ReturnsAsync(user);

        // Act
        var result = await _sut.GetUserByIdAsync(userId);

        // Assert
        result.Should().NotBeNull();
        result!.Id.Should().Be(userId);
        result.Name.Should().Be("John");
    }

    [Fact]
    public async Task GetUserById_WhenCached_ReturnsCachedValue()
    {
        // Arrange
        var cached = new UserDto { Id = 1, Name = "Cached User" };
        _cache.Setup(c => c.GetAsync<UserDto>(It.IsAny<string>(), default))
            .ReturnsAsync(cached);

        // Act
        var result = await _sut.GetUserByIdAsync(1);

        // Assert
        result.Should().BeEquivalentTo(cached);
        _userRepository.Verify(r => r.GetByIdAsync(It.IsAny<int>(), default), Times.Never);
    }

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    [InlineData(null)]
    public async Task CreateUser_WithInvalidEmail_ThrowsValidationException(string? email)
    {
        // Arrange
        var command = new CreateUserCommand("John", email!);

        // Act & Assert
        await Assert.ThrowsAsync<ValidationException>(
            () => _sut.CreateUserAsync(command)
        );
    }
}
```

### Integration Tests with WebApplicationFactory

```csharp
// Integration test base
public class IntegrationTestBase : IClassFixture<WebApplicationFactory<Program>>
{
    protected readonly WebApplicationFactory<Program> _factory;
    protected readonly HttpClient _client;

    public IntegrationTestBase(WebApplicationFactory<Program> factory)
    {
        _factory = factory.WithWebHostBuilder(builder =>
        {
            builder.ConfigureServices(services =>
            {
                // Replace services with test doubles
                services.RemoveAll(typeof(IEmailService));
                services.AddScoped<IEmailService, FakeEmailService>();

                // Use test database
                services.RemoveAll(typeof(DbContextOptions<AppDbContext>));
                services.AddDbContext<AppDbContext>(options =>
                    options.UseInMemoryDatabase("TestDb"));
            });
        });

        _client = _factory.CreateClient();
    }
}

// Full integration test
public class UserControllerTests : IntegrationTestBase
{
    public UserControllerTests(WebApplicationFactory<Program> factory) : base(factory) { }

    [Fact]
    public async Task CreateUser_ValidRequest_ReturnsCreatedResult()
    {
        // Arrange
        var request = new CreateUserRequest { Name = "John", Email = "john@test.com" };

        // Act
        var response = await _client.PostAsJsonAsync("/api/users", request);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Created);

        var created = await response.Content.ReadFromJsonAsync<UserDto>();
        created.Should().NotBeNull();
        created!.Name.Should().Be("John");
    }

    [Fact]
    public async Task GetUser_NotFound_Returns404()
    {
        // Act
        var response = await _client.GetAsync("/api/users/99999");

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }
}
```

## Best Practices

1. **Use async/await consistently** — Never block on async code
2. **ConfigureAwait(false) in library code** — Prevents deadlocks in ASP.NET Core
3. **Prefer constructor injection** — Makes dependencies explicit and testable
4. **Use IOptions<T> for configuration** — Type-safe, testable configuration
5. **Use Result<T> for error handling** — Explicit success/failure without exceptions
6. **Use Dapper for hot paths** — EF Core for CRUD, Dapper for complex reporting
7. **Implement health checks** — Critical for container orchestration
8. **Write integration tests** — WebApplicationFactory for true integration
9. **Use global query filters** — For multi-tenancy and soft deletes
10. **Rate limit public endpoints** — Prevent abuse with built-in middleware

## Limitations

- Use this skill only when the task clearly matches the scope described above.
- Do not treat the output as a substitute for environment-specific validation, testing, or expert review.
- Stop and ask for clarification if required inputs, permissions, safety boundaries, or success criteria are missing.