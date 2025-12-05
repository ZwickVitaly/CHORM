---
name: Bug Report
about: Create a report to help us improve CHORM
title: '[BUG] '
labels: bug
assignees: ''
---

## Bug Description
A clear and concise description of what the bug is.

## To Reproduce
Steps to reproduce the behavior:
1. Define model '...'
2. Execute query '...'
3. See error

## Expected Behavior
A clear and concise description of what you expected to happen.

## Actual Behavior
What actually happened instead.

## Code Sample
```python
# Minimal reproducible example
from chorm import Model, Column, String, Int32

class User(Model):
    __tablename__ = "users"
    __engine__ = "MergeTree()"
    __order_by__ = ("id",)
    
    id = Column(Int32, primary_key=True)
    name = Column(String)

# Your code that triggers the bug
```

## Error Message/Traceback
```
Paste the full error message and traceback here
```

## Environment
- **CHORM Version**: [e.g., 0.1.0]
- **Python Version**: [e.g., 3.12.0]
- **ClickHouse Version**: [e.g., 24.3.1]
- **OS**: [e.g., Ubuntu 22.04, macOS 14.0, Windows 11]
- **Installation Method**: [e.g., pip, uv, poetry]

## Additional Context
Add any other context about the problem here, such as:
- Does this happen consistently or intermittently?
- Did this work in a previous version?
- Any relevant configuration or environment variables?

## Possible Solution
If you have suggestions on how to fix the bug, please describe them here.
