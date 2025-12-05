---
name: Feature Request
about: Suggest an idea for CHORM
title: '[FEATURE] '
labels: enhancement
assignees: ''
---

## Feature Description
A clear and concise description of the feature you'd like to see in CHORM.

## Problem Statement
Describe the problem this feature would solve. For example:
- "I'm always frustrated when..."
- "It's difficult to..."
- "There's no way to..."

## Proposed Solution
Describe how you envision this feature working. Include:
- API design (if applicable)
- Example usage code
- Expected behavior

## Example Usage
```python
# How you would like to use this feature
from chorm import Model, Column, String

class User(Model):
    __tablename__ = "users"
    # ... your example code here
```

## Alternatives Considered
Describe alternative solutions or features you've considered and why they might not be ideal.

## ClickHouse Feature Support
If this feature relates to a specific ClickHouse capability:
- **ClickHouse Feature**: [e.g., ARRAY JOIN, LIMIT BY, WITH TOTALS]
- **ClickHouse Documentation**: [link to relevant ClickHouse docs]
- **ClickHouse Version**: [minimum version that supports this feature]

## Benefits
Explain the benefits of implementing this feature:
- Who would benefit from this?
- What use cases does it enable?
- How does it improve the developer experience?

## Implementation Complexity
If you have thoughts on implementation difficulty:
- [ ] Simple (minor API addition)
- [ ] Moderate (requires new internal logic)
- [ ] Complex (significant architectural changes)

## Additional Context
Add any other context, screenshots, or examples about the feature request here.

## Willingness to Contribute
- [ ] I'm willing to submit a PR for this feature
- [ ] I can help with testing
- [ ] I can help with documentation
- [ ] I'm just suggesting the idea
