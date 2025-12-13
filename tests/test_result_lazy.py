
import pytest
from unittest.mock import MagicMock
from chorm.result import Result, Row, ScalarResult, MappingResult, TupleResult
from chorm.declarative import Table, Column
from chorm.types import String, Int32

# Mock ClickHouse result set
class MockResultSet:
    def __init__(self, rows, columns):
        self.result_rows = rows
        self.column_names = columns

# Mock Model
class User(Table):
    __tablename__ = "users"
    id = Column(Int32)
    name = Column(String)

@pytest.fixture
def mock_data():
    rows = [
        (1, "Alice"),
        (2, "Bob"),
        (3, "Charlie")
    ]
    cols = ["id", "name"]
    return MockResultSet(rows, cols)

def test_result_lazy_iteration_rows(mock_data):
    """Test standard lazy iteration yielding Row objects."""
    result = Result(mock_data)
    
    # Ensure it's an iterator
    iterator = iter(result)
    assert iterator is not result  # Should return a generator/iterator
    
    # Test lazy yielding
    first = next(iterator)
    assert isinstance(first, Row)
    assert first.id == 1
    assert first.name == "Alice"
    
    # Consume rest
    rest = list(iterator)
    assert len(rest) == 2
    assert rest[0].name == "Bob"
    assert rest[1].name == "Charlie"

def test_result_lazy_iteration_model(mock_data):
    """Test lazy iteration yielding Model objects."""
    result = Result(mock_data, model=User)
    
    iterator = iter(result)
    
    first = next(iterator)
    assert isinstance(first, User)
    assert first.id == 1
    assert first.name == "Alice"
    
    rest = list(iterator)
    assert len(rest) == 2
    assert all(isinstance(r, User) for r in rest)

def test_tuples_access(mock_data):
    """Test .tuples() returns raw data without overhead."""
    result = Result(mock_data)
    tuple_res = result.tuples()
    
    # .all() should return raw list reference (mock_data.result_rows)
    assert tuple_res.all() is mock_data.result_rows
    
    # Iteration should yield raw tuples
    iterator = iter(tuple_res)
    first = next(iterator)
    assert isinstance(first, tuple)
    assert first == (1, "Alice")

def test_mapping_lazy_iteration(mock_data):
    """Test .mappings() lazy iteration."""
    result = Result(mock_data)
    mapping_res = result.mappings()
    
    iterator = iter(mapping_res)
    first = next(iterator)
    
    assert isinstance(first, dict)
    assert first == {"id": 1, "name": "Alice"}

def test_scalar_lazy_iteration(mock_data):
    """Test .scalars() lazy iteration."""
    result = Result(mock_data)
    scalar_res = result.scalars("name")
    
    iterator = iter(scalar_res)
    first = next(iterator)
    
    assert first == "Alice"
    assert list(iterator) == ["Bob", "Charlie"]

def test_scalar_lazy_iteration_with_index(mock_data):
    """Test .scalars() by index."""
    result = Result(mock_data)
    scalar_res = result.scalars(0) # id column
    
    assert list(scalar_res) == [1, 2, 3]

def test_lazy_iteration_reusability(mock_data):
    """Verify that we can iterate multiple times (if underlying list allows)."""
    # Note: result._rows is a list, so we can create multiple iterators
    result = Result(mock_data)
    
    iter1 = iter(result)
    assert next(iter1).id == 1
    
    iter2 = iter(result)
    assert next(iter2).id == 1
    
    # They are independent iterators
    assert next(iter1).id == 2
