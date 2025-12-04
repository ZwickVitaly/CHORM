# CHORM Model Validation Guide

CHORM provides a comprehensive validation system that ensures data integrity before database operations. Validators can be applied to columns to automatically validate values on assignment and before database commits.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Standard Validators](#standard-validators)
3. [Custom Validators](#custom-validators)
4. [Validation Behavior](#validation-behavior)
5. [Best Practices](#best-practices)

---

## Quick Start

```python
from chorm import Table, Column, Int32, String, Session, create_engine
from chorm.validators import RangeValidator, EmailValidator, LengthValidator
from chorm.table_engines import MergeTree

class User(Table):
    __tablename__ = "users"
    __order_by__ = ("id",)
    engine = MergeTree()
    
    id = Column(Int32(), primary_key=True)
    age = Column(Int32(), validators=[RangeValidator(0, 150)])
    email = Column(String(), validators=[EmailValidator()])
    name = Column(String(), validators=[LengthValidator(1, 100)])

# Validation happens automatically
engine = create_engine("clickhouse://localhost:8123/default")
session = Session(engine)

user = User(id=1, age=25, email="user@example.com", name="Alice")
session.add(user)  # Validates automatically
session.commit()   # Validates again before commit

# Invalid values raise ValidationError
try:
    user.age = 200  # Raises ValidationError immediately
except ValidationError as e:
    print(f"Validation failed: {e}")
```

---

## Standard Validators

### RangeValidator

Validates that a numeric value is within a specified range.

```python
from chorm.validators import RangeValidator

# Both min and max
age = Column(Int32(), validators=[RangeValidator(0, 150)])

# Only minimum
price = Column(Float64(), validators=[RangeValidator(0)])

# Only maximum
discount = Column(Float64(), validators=[RangeValidator(max_value=100)])

# Usage
user.age = 25      # OK
user.age = 200     # Raises ValidationError
user.age = -5      # Raises ValidationError
```

### LengthValidator

Validates the length of strings or sequences.

```python
from chorm.validators import LengthValidator

# Both min and max length
name = Column(String(), validators=[LengthValidator(1, 100)])

# Only minimum length
description = Column(String(), validators=[LengthValidator(min_length=10)])

# Only maximum length
code = Column(String(), validators=[LengthValidator(max_length=10)])

# Works with lists and tuples too
tags = Column(Array(String()), validators=[LengthValidator(1, 10)])

# Usage
user.name = "Alice"           # OK
user.name = ""                # Raises ValidationError (too short)
user.name = "A" * 200         # Raises ValidationError (too long)
```

### EmailValidator

Validates email address format.

```python
from chorm.validators import EmailValidator

email = Column(String(), validators=[EmailValidator()])

# Usage
user.email = "user@example.com"     # OK
user.email = "invalid-email"         # Raises ValidationError
user.email = "user @example.com"     # Raises ValidationError (contains space)
user.email = "@example.com"          # Raises ValidationError
```

### RegexValidator

Validates that a string matches a regular expression.

```python
from chorm.validators import RegexValidator

# Phone number validation
phone = Column(String(), validators=[RegexValidator(r'^\+?[1-9]\d{1,14}$')])

# Alphanumeric only
username = Column(String(), validators=[RegexValidator(r'^[a-zA-Z0-9_]+$')])

# With flags
case_insensitive = Column(String(), validators=[
    RegexValidator(r'^[a-z]+$', flags=re.IGNORECASE)
])

# Usage
user.phone = "+1234567890"    # OK
user.phone = "abc"            # Raises ValidationError
```

### InValidator

Validates that a value is in a set of allowed values.

```python
from chorm.validators import InValidator

status = Column(String(), validators=[InValidator(['active', 'inactive', 'pending'])])

# Usage
order.status = "active"      # OK
order.status = "deleted"      # Raises ValidationError
```

### NotInValidator

Validates that a value is NOT in a set of disallowed values.

```python
from chorm.validators import NotInValidator

username = Column(String(), validators=[NotInValidator(['admin', 'root', 'system'])])

# Usage
user.username = "alice"       # OK
user.username = "admin"       # Raises ValidationError
```

---

## Custom Validators

### Using CustomValidator

Wrap any custom validation function.

```python
from chorm.validators import CustomValidator, ValidationError

def is_positive(value, column_name=None):
    if value <= 0:
        raise ValidationError(
            f"{column_name} must be positive",
            column_name,
            value
        )
    return value

def is_even(value, column_name=None):
    if value % 2 != 0:
        raise ValidationError(
            f"{column_name} must be even",
            column_name,
            value
        )
    return value

# Usage
price = Column(Float64(), validators=[CustomValidator(is_positive)])
quantity = Column(Int32(), validators=[CustomValidator(is_even)])

# With custom error message
price = Column(Float64(), validators=[
    CustomValidator(is_positive, error_message="Price must be greater than zero")
])
```

### Multiple Validators

Apply multiple validators to a single column.

```python
from chorm.validators import RangeValidator, CustomValidator

def is_even(value, column_name=None):
    if value % 2 != 0:
        raise ValidationError(f"{column_name} must be even", column_name, value)
    return value

# Multiple validators are applied in order
quantity = Column(
    Int32(),
    validators=[
        RangeValidator(0, 1000),      # First: check range
        CustomValidator(is_even),     # Then: check if even
    ]
)

# Usage
product.quantity = 50     # OK (in range and even)
product.quantity = 51     # Raises ValidationError (not even)
product.quantity = 2000   # Raises ValidationError (out of range)
```

---

## Validation Behavior

### When Validation Occurs

Validation happens at multiple points:

1. **On Assignment** - When you set a column value via `__set__`:
   ```python
   user.age = 200  # Raises ValidationError immediately
   ```

2. **On Table.validate()** - When you explicitly call `validate()`:
   ```python
   user.__dict__['age'] = 200  # Bypass __set__
   user.validate()  # Raises ValidationError
   ```

3. **On Session.add()** - When adding an instance to a session:
   ```python
   user.__dict__['age'] = 200
   session.add(user)  # Raises ValidationError
   ```

4. **On Session.commit()** - Before committing to database:
   ```python
   user = User(id=1, age=25)
   session.add(user)
   user.__dict__['age'] = 200
   session.commit()  # Raises ValidationError
   ```

### Nullable Columns

None values are handled specially:

- If a column is `nullable=True`, `None` values are allowed and validators are skipped
- If a column is `nullable=False`, `None` values raise `ValidationError`

```python
class User(Table):
    __tablename__ = "users"
    __order_by__ = ("id",)
    engine = MergeTree()
    
    id = Column(Int32(), primary_key=True)
    name = Column(String(), nullable=True, validators=[LengthValidator(1, 100)])
    email = Column(String(), nullable=False, validators=[EmailValidator()])

user = User(id=1)
user.name = None      # OK (nullable=True)
user.email = None     # Raises ValidationError (nullable=False)
```

---

## Best Practices

### 1. Use Appropriate Validators

Choose validators that match your data requirements:

```python
# Good: Specific validators
age = Column(Int32(), validators=[RangeValidator(0, 150)])
email = Column(String(), validators=[EmailValidator()])

# Avoid: Overly complex custom validators when standard ones exist
# Bad:
def validate_age(value, _):
    if not isinstance(value, int):
        raise ValidationError("Must be int")
    if value < 0 or value > 150:
        raise ValidationError("Out of range")
    return value
age = Column(Int32(), validators=[CustomValidator(validate_age)])

# Good: Use RangeValidator instead
age = Column(Int32(), validators=[RangeValidator(0, 150)])
```

### 2. Validate Early

Validation happens automatically, but you can also validate explicitly:

```python
# Validate before expensive operations
user = User(id=1, age=25, email="user@example.com")
user.validate()  # Check early

# Then proceed with expensive operations
process_user(user)
session.add(user)
```

### 3. Combine Validators for Complex Rules

Use multiple validators for complex validation logic:

```python
# Complex validation: price must be positive, divisible by 0.01, and < 10000
def is_cent_precise(value, column_name=None):
    if round(value, 2) != value:
        raise ValidationError(
            f"{column_name} must be precise to cents",
            column_name,
            value
        )
    return value

price = Column(
    Float64(),
    validators=[
        RangeValidator(0, 10000),
        CustomValidator(is_cent_precise),
    ]
)
```

### 4. Provide Clear Error Messages

Custom validators should provide clear error messages:

```python
# Good: Clear error message
def validate_discount(value, column_name=None):
    if not 0 <= value <= 100:
        raise ValidationError(
            f"{column_name} must be between 0 and 100 percent",
            column_name,
            value
        )
    return value

# Bad: Vague error message
def validate_discount(value, column_name=None):
    if not 0 <= value <= 100:
        raise ValidationError("Invalid", column_name, value)
    return value
```

### 5. Handle Validation Errors Gracefully

```python
from chorm.exceptions import ValidationError

try:
    user = User(id=1, age=200, email="invalid")
    session.add(user)
except ValidationError as e:
    print(f"Validation failed for column '{e.column}': {e}")
    # Handle error appropriately
```

---

## Complete Example

```python
from chorm import Table, Column, Int32, String, Float64, Session, create_engine
from chorm.validators import (
    RangeValidator,
    EmailValidator,
    LengthValidator,
    RegexValidator,
    InValidator,
    CustomValidator,
)
from chorm.exceptions import ValidationError
from chorm.table_engines import MergeTree

class Product(Table):
    __tablename__ = "products"
    __order_by__ = ("id",)
    engine = MergeTree()
    
    id = Column(Int32(), primary_key=True)
    name = Column(String(), validators=[LengthValidator(1, 200)])
    price = Column(Float64(), validators=[RangeValidator(0, 1000000)])
    status = Column(String(), validators=[InValidator(['active', 'inactive', 'archived'])])
    
    def validate_price_precision(self, value, column_name=None):
        """Ensure price is precise to cents."""
        if round(value, 2) != value:
            raise ValidationError(
                f"{column_name} must be precise to cents",
                column_name,
                value
            )
        return value

# Add custom validator
Product.__table__.column_map['price'].column.validators += (
    CustomValidator(Product.validate_price_precision),
)

# Usage
engine = create_engine("clickhouse://localhost:8123/default")
session = Session(engine)

try:
    product = Product(
        id=1,
        name="Laptop",
        price=999.99,
        status="active"
    )
    session.add(product)
    session.commit()
    print("Product created successfully!")
    
except ValidationError as e:
    print(f"Validation failed: {e}")
```

---

## Summary

- **Validation is automatic** - Happens on assignment and before database operations
- **Standard validators** - Range, Length, Email, Regex, In, NotIn
- **Custom validators** - Use `CustomValidator` for complex logic
- **Multiple validators** - Apply multiple validators to a single column
- **Nullable handling** - None values are handled based on `nullable` flag
- **Clear errors** - `ValidationError` provides column name and value for debugging

Validation ensures data integrity at the ORM level, catching errors before they reach the database!

