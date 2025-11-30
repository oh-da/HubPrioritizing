# SOLID Principles in Hub Prioritization Framework

This document explains how SOLID principles are implemented throughout the codebase.

## Table of Contents
1. [Single Responsibility Principle](#single-responsibility-principle)
2. [Open/Closed Principle](#openclosed-principle)
3. [Liskov Substitution Principle](#liskov-substitution-principle)
4. [Interface Segregation Principle](#interface-segregation-principle)
5. [Dependency Inversion Principle](#dependency-inversion-principle)

---

## Single Responsibility Principle

**Definition**: A class should have one, and only one, reason to change.

### Implementation Examples

#### Data Layer
Each component has one clear responsibility:

```python
# src/data/loaders.py
class CSVDataLoader(IDataLoader):
    """Single Responsibility: Load CSV files only"""
    def load(self): ...
    def validate_schema(self, data): ...

class GeoJSONDataLoader(IDataLoader):
    """Single Responsibility: Load GeoJSON files only"""
    def load(self): ...
    def validate_schema(self, data): ...
```

**Why this matters**: If CSV format changes, only `CSVDataLoader` changes. If validation logic changes, only validators change.

#### Scoring System
Each scorer focuses on one criterion:

```python
# src/scoring/activity.py
class ActivityScorer(BaseScorer):
    """Single Responsibility: Score passenger activity only"""
    def extract_raw_value(self, hub_data):
        return float(hub_data.passengers_2050)

# src/scoring/location.py
class LocationScorer(BaseScorer):
    """Single Responsibility: Score geographic location only"""
    def extract_raw_value(self, hub_data):
        return calculate_location_score(hub_data.location)
```

**Why this matters**: Changing how we score activity doesn't affect location scoring.

#### Normalization
Normalizers only normalize:

```python
# src/scoring/normalization.py
class MinMaxNormalizer(INormalizer):
    """Single Responsibility: Min-max normalization only"""
    def normalize(self, values, min_score, max_score):
        # Only normalization logic, nothing else
        ...
```

**Benefits**:
- Easy to understand
- Easy to test
- Easy to modify
- Easy to reuse

---

## Open/Closed Principle

**Definition**: Software entities should be open for extension but closed for modification.

### Implementation Examples

#### Extending Scorers
Add new scoring criteria without modifying existing code:

```python
# Existing base (closed for modification)
class BaseScorer(IScorer, ABC):
    def calculate_score(self, hub_data):
        # Template method - defines workflow
        raw_value = self.extract_raw_value(hub_data)
        transformed = self.transform_value(raw_value)
        normalized = self.normalize_value(transformed)
        return self._create_result(...)

# New scorer (open for extension)
class EnvironmentalImpactScorer(BaseScorer):
    """New scorer added without modifying BaseScorer"""
    def extract_raw_value(self, hub_data):
        return calculate_environmental_impact(hub_data)

    def get_criterion_name(self):
        return "environmental_impact"
```

**Why this matters**: Adding a new criterion doesn't break existing scorers or require changing the framework.

#### Extending Filters

```python
# Add new eligibility criteria without modifying existing filters
class AccessibilityEligibilityFilter(IEligibilityFilter):
    """New filter added without modifying existing code"""
    def is_eligible(self, hub_data):
        if hub_data.metadata.get('wheelchair_accessible'):
            return True, "Fully accessible"
        return False, "Accessibility requirements not met"

# Use with existing composite
composite = CompositeEligibilityFilter([
    PassengerEligibilityFilter(),  # Existing
    ModeEligibilityFilter(),        # Existing
    AccessibilityEligibilityFilter() # New - no modification needed
])
```

#### Factory Pattern

```python
# src/data/loaders.py
class DataLoaderFactory:
    _loaders = {
        '.csv': CSVDataLoader,
        '.geojson': GeoJSONDataLoader,
    }

    @classmethod
    def register_loader(cls, extension, loader_class):
        """Extend with new loader types without modifying factory"""
        cls._loaders[extension] = loader_class

# Add new loader without modifying factory code
DataLoaderFactory.register_loader('.parquet', ParquetDataLoader)
```

**Benefits**:
- Add features without breaking existing code
- Reduced risk of regression bugs
- Easier to maintain and test

---

## Liskov Substitution Principle

**Definition**: Objects of a superclass should be replaceable with objects of a subclass without breaking the application.

### Implementation Examples

#### Scorer Substitutability

```python
def score_all_hubs(hubs: List[HubData], scorers: List[IScorer]):
    """Works with ANY IScorer implementation"""
    results = []
    for hub in hubs:
        for scorer in scorers:
            result = scorer.calculate_score(hub)  # Any scorer works
            results.append(result)
    return results

# All these are interchangeable
scorers = [
    ActivityScorer(normalizer),
    LocationScorer(normalizer),
    ServiceModeScorer(normalizer, mode_weights),
    CustomScorer(normalizer),  # Your custom scorer
]
```

**Contract maintained**: All scorers:
- Accept `HubData`
- Return `ScoringResult`
- Have a criterion name
- Produce normalized scores (1-10)

#### Normalizer Substitutability

```python
# Use any normalizer - behavior is consistent
normalizer = MinMaxNormalizer()
# OR
normalizer = LogNormalizer()
# OR
normalizer = CustomNormalizer()

scorer = ActivityScorer(normalizer)  # Works with any INormalizer
```

**Contract maintained**: All normalizers:
- Accept list of values
- Return normalized list (same length)
- Respect min/max range parameters

#### Repository Substitutability

```python
# Use any repository implementation
repository = HubDataRepository()  # In-memory
# OR
repository = FileBasedHubRepository(file_path)  # File-based
# OR
repository = DatabaseHubRepository(connection)  # Database

# All work the same way
hub = repository.get_hub("hub_001")
all_hubs = repository.get_all_hubs()
```

**Benefits**:
- Implementations are interchangeable
- Easy to mock for testing
- Can swap implementations without code changes

---

## Interface Segregation Principle

**Definition**: Clients should not be forced to depend on interfaces they don't use.

### Implementation Examples

#### Focused Interfaces

Instead of one large interface:
```python
# BAD: Fat interface
class IHubOperations(ABC):
    def load_data(self): ...
    def validate_data(self): ...
    def score_hub(self): ...
    def classify_hub(self): ...
    def export_results(self): ...
    # Too many responsibilities!
```

We have focused interfaces:
```python
# GOOD: Segregated interfaces
class IDataLoader(ABC):
    def load(self): ...
    def validate_schema(self, data): ...

class IScorer(ABC):
    def calculate_score(self, hub_data): ...
    def get_criterion_name(self): ...

class IHubClassifier(ABC):
    def classify(self, hub_data): ...

class IExporter(ABC):
    def export(self, data, output_path): ...
```

**Why this matters**:
- Scorers don't need to know about data loading
- Data loaders don't need to know about classification
- Each client depends only on what it needs

#### Minimal Method Contracts

```python
# IScorer: Just 2 methods
class IScorer(ABC):
    @abstractmethod
    def calculate_score(self, hub_data: HubData) -> ScoringResult: ...

    @abstractmethod
    def get_criterion_name(self) -> str: ...

# INormalizer: Just 1 method
class INormalizer(ABC):
    @abstractmethod
    def normalize(self, values: List[float], ...) -> List[float]: ...

# IEligibilityFilter: Just 1 method
class IEligibilityFilter(ABC):
    @abstractmethod
    def is_eligible(self, hub_data: HubData) -> tuple[bool, str]: ...
```

**Benefits**:
- Easy to implement
- Easy to test
- Easy to understand
- No unused methods

---

## Dependency Inversion Principle

**Definition**: High-level modules should depend on abstractions, not on low-level modules.

### Implementation Examples

#### Scorers Depend on Normalizer Abstraction

```python
# HIGH-LEVEL MODULE
class ActivityScorer(BaseScorer):
    def __init__(self, normalizer: INormalizer):  # ← Depends on abstraction
        self.normalizer = normalizer

# LOW-LEVEL MODULES (implementations)
class MinMaxNormalizer(INormalizer): ...
class LogNormalizer(INormalizer): ...

# Dependency injection - can swap implementations
scorer1 = ActivityScorer(MinMaxNormalizer())
scorer2 = ActivityScorer(LogNormalizer())
scorer3 = ActivityScorer(MockNormalizer())  # For testing
```

**Why this matters**: ActivityScorer doesn't know or care which normalizer it uses.

#### Services Depend on Repository Abstraction

```python
# HIGH-LEVEL MODULE
class HubScoringService:
    def __init__(self, repository: IDataRepository, scorers: List[IScorer]):
        self.repository = repository  # ← Abstraction
        self.scorers = scorers        # ← Abstraction

    def score_all_hubs(self):
        hubs = self.repository.get_all_hubs()
        # ... scoring logic

# LOW-LEVEL MODULES
class HubDataRepository(IDataRepository): ...
class FileBasedHubRepository(IDataRepository): ...

# Inject dependencies
service = HubScoringService(
    repository=HubDataRepository(),
    scorers=[ActivityScorer(normalizer), LocationScorer(normalizer)]
)
```

#### Configuration Dependency Inversion

```python
# Components depend on IConfiguration protocol
class PassengerEligibilityFilter:
    def __init__(self, config: IConfiguration):  # ← Abstraction
        self.min_passengers = config.get_int('min_passengers')

# Can inject different configurations
filter1 = PassengerEligibilityFilter(ProductionConfig())
filter2 = PassengerEligibilityFilter(TestConfig())
filter3 = PassengerEligibilityFilter(MockConfig())
```

**Benefits**:
- Easy to test (inject mocks)
- Loose coupling between modules
- Can swap implementations without changing high-level code
- Configurations can be changed without code changes

### Dependency Injection in Action

```python
# All dependencies injected at construction
normalizer = LogNormalizer(base=10)
mode_weights = get_config().mode_weights

scorer = ServiceModeScorer(
    normalizer=normalizer,      # INormalizer
    mode_weights=mode_weights   # Config data
)

# Easy to test with mocks
test_scorer = ServiceModeScorer(
    normalizer=MockNormalizer(),
    mode_weights={'rail': 1.0, 'bus': 0.5}
)
```

---

## Testing SOLID Principles

The test suite demonstrates SOLID principles:

```bash
# Run SOLID principles tests
pytest tests/test_solid_principles.py -v
```

Tests include:
- **SRP**: Each component's single responsibility
- **OCP**: Adding new implementations without modification
- **LSP**: Substituting implementations
- **ISP**: Minimal interface contracts
- **DIP**: Dependency injection and abstraction

---

## Summary

### Key Takeaways

1. **Single Responsibility**: Each class has one job
2. **Open/Closed**: Extend behavior, don't modify existing code
3. **Liskov Substitution**: Implementations are interchangeable
4. **Interface Segregation**: Small, focused interfaces
5. **Dependency Inversion**: Depend on abstractions, inject dependencies

### Benefits Achieved

- ✅ **Maintainable**: Changes are localized
- ✅ **Testable**: Easy to mock and test
- ✅ **Extensible**: Add features without breaking existing code
- ✅ **Flexible**: Swap implementations easily
- ✅ **Understandable**: Clear responsibilities and contracts

### Further Reading

- See `tests/test_solid_principles.py` for working examples
- See `src/interfaces.py` for all interface definitions
- See individual modules for implementation patterns
