# Hub Prioritization Framework

A SOLID-principles based framework for identifying, classifying, and prioritizing integrated transport hubs (מתח"מים) in Israel.

## Overview

This framework provides a systematic approach to:
- Identify potential integrated transport hubs
- Classify hubs into hierarchy tiers (ארצי/מטרופוליני/עירוני)
- Score hubs across multiple criteria
- Prioritize hubs for investment and development

## SOLID Principles Implementation

This codebase is architected around SOLID principles:

### Single Responsibility Principle (SRP)
Each class has one clear responsibility:
- `ActivityScorer`: Only scores passenger activity
- `MinMaxNormalizer`: Only normalizes values
- `PassengerEligibilityFilter`: Only checks passenger eligibility

### Open/Closed Principle (OCP)
The system is open for extension but closed for modification:
- Add new scorers by extending `BaseScorer`
- Add new filters by implementing `IEligibilityFilter`
- Add new normalizers by implementing `INormalizer`

Example:
```python
class CustomScorer(BaseScorer):
    def extract_raw_value(self, hub_data: HubData) -> float:
        return custom_logic(hub_data)

    def get_criterion_name(self) -> str:
        return "custom_criterion"
```

### Liskov Substitution Principle (LSP)
All implementations can be substituted for their interfaces:
- Any `IScorer` can replace another `IScorer`
- Any `INormalizer` can replace another `INormalizer`
- All maintain the contract defined by the interface

### Interface Segregation Principle (ISP)
Interfaces are small and focused:
- `IScorer`: Just `calculate_score()` and `get_criterion_name()`
- `IEligibilityFilter`: Just `is_eligible()`
- `INormalizer`: Just `normalize()`

### Dependency Inversion Principle (DIP)
High-level modules depend on abstractions:
- Scorers depend on `INormalizer`, not concrete normalizer
- Services depend on `IDataRepository`, not concrete repository
- Classifiers depend on `IConfiguration`, not concrete config

Example:
```python
class ActivityScorer(BaseScorer):
    def __init__(self, normalizer: INormalizer):  # Depends on abstraction
        self.normalizer = normalizer
```

## Project Structure

```
HubPrioritizing/
├── src/
│   ├── interfaces.py           # Core interfaces and protocols
│   ├── config.py               # Configuration management
│   ├── data/                   # Data layer (SRP)
│   │   ├── loaders.py          # Data loading
│   │   ├── validators.py       # Data validation
│   │   └── repository.py       # Data persistence
│   ├── spatial/                # Spatial operations
│   │   ├── h3_operations.py    # H3 hexagon operations
│   │   └── geometry.py         # Geometric calculations
│   ├── classification/         # Hub classification
│   │   ├── eligibility.py      # Eligibility filtering
│   │   └── hierarchy.py        # Tier classification
│   └── scoring/                # Scoring system (OCP)
│       ├── base.py             # Base scorer (Template Method)
│       ├── activity.py         # Activity scorer
│       ├── service.py          # Service/mode scorer
│       ├── location.py         # Location scorer
│       ├── demographics.py     # Demographics scorer
│       ├── terminals.py        # Bus terminal scorer
│       ├── normalization.py    # Normalization strategies
│       └── aggregation.py      # Score aggregation
├── tests/
│   └── test_solid_principles.py  # Tests demonstrating SOLID
├── data/                       # Data files (not in git)
├── docs/                       # Documentation
└── CLAUDE.md                   # Comprehensive framework documentation
```

## Installation

```bash
# Clone repository
git clone <repository-url>
cd HubPrioritizing

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Basic Hub Classification

```python
from src.interfaces import HubData, HubLocation, TransitMode
from src.classification.hierarchy import PassengerBasedClassifier
from src.config import get_config

# Create hub data
hub = HubData(
    hub_id="tlv_savidor",
    name="Tel Aviv Savidor",
    location=HubLocation(
        lat=32.0853,
        lon=34.7818,
        h3_index="h3_index",
        region="center",
        metropolitan_ring="core"
    ),
    tier=None,
    passengers_2050=120000,
    modes=[TransitMode.RAIL, TransitMode.METRO],
    metadata={}
)

# Classify hub
classifier = PassengerBasedClassifier(config=get_config())
tier = classifier.classify(hub)
print(f"Hub tier: {tier.value}")  # Output: ארצי (National)
```

### Hub Scoring

```python
from src.scoring.activity import ActivityScorer
from src.scoring.normalization import LogNormalizer

# Create scorer with dependency injection
normalizer = LogNormalizer(base=10)
scorer = ActivityScorer(normalizer)

# Score hub
result = scorer.calculate_score(hub)
print(f"Activity score: {result.normalized_score}/10")
```

### Eligibility Filtering

```python
from src.classification.eligibility import create_default_eligibility_filter

# Create composite filter
eligibility_filter = create_default_eligibility_filter()

# Check eligibility
is_eligible, reason = eligibility_filter.is_eligible(hub)
print(f"Eligible: {is_eligible} - {reason}")
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src tests/

# Run SOLID principles tests specifically
pytest tests/test_solid_principles.py -v
```

## Extending the Framework

### Adding a New Scorer

```python
from src.scoring.base import BaseScorer
from src.interfaces import HubData, INormalizer

class MyCustomScorer(BaseScorer):
    def __init__(self, normalizer: INormalizer):
        super().__init__(normalizer)

    def extract_raw_value(self, hub_data: HubData) -> float:
        # Your custom scoring logic
        return calculate_custom_score(hub_data)

    def get_criterion_name(self) -> str:
        return "my_custom_criterion"
```

### Adding a New Filter

```python
from src.interfaces import IEligibilityFilter, HubData

class MyCustomFilter(IEligibilityFilter):
    def is_eligible(self, hub_data: HubData) -> tuple[bool, str]:
        # Your custom filtering logic
        if meets_criteria(hub_data):
            return True, "Meets custom criteria"
        return False, "Does not meet custom criteria"
```

## Architecture Highlights

### Dependency Injection
Components receive their dependencies via constructor:
```python
scorer = ActivityScorer(normalizer=LogNormalizer())
classifier = PassengerBasedClassifier(config=custom_config)
```

### Strategy Pattern
Different algorithms can be swapped:
```python
# Use different normalization strategies
min_max_scorer = ActivityScorer(MinMaxNormalizer())
log_scorer = ActivityScorer(LogNormalizer())
```

### Composite Pattern
Filters can be composed:
```python
composite = CompositeEligibilityFilter([
    PassengerEligibilityFilter(),
    ModeEligibilityFilter(),
    CustomFilter()
])
```

### Template Method Pattern
Base scorer defines algorithm structure:
```python
class BaseScorer:
    def calculate_score(self, hub_data):
        raw_value = self.extract_raw_value(hub_data)  # Subclass implements
        transformed = self.transform_value(raw_value)   # Subclass can override
        normalized = self.normalize_value(transformed)
        return self._create_result(normalized)
```

## Documentation

See `CLAUDE.md` for comprehensive framework documentation including:
- Detailed methodology
- Scoring criteria definitions
- Hub hierarchy explained
- Data requirements
- Development workflows

## Contributing

1. Follow SOLID principles
2. Write tests for new features
3. Update documentation
4. Run linters and type checks

## License

[Add license information]

## Contact

[Add contact information]
