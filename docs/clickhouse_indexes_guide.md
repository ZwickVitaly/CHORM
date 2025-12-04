"""
ClickHouse Index Types and Granularity Guide

This guide explains ClickHouse data skipping indexes and the critical GRANULARITY parameter.
"""

# =============================================================================
# GRANULARITY EXPLAINED
# =============================================================================

"""
GRANULARITY is the number of granules (data blocks) that are grouped together
for index calculation. It's a critical parameter that affects:

1. Index Size: Higher granularity = smaller index (fewer entries)
2. Index Precision: Lower granularity = more precise (can skip smaller blocks)
3. Query Performance: Trade-off between index size and skip precision

DEFAULT: 1 (most precise, largest index)
RECOMMENDED: 1-4 for most cases
LARGE TABLES: 8-16 for very large tables (billions of rows)

Example:
- index_granularity = 8192 (table setting, rows per granule)
- GRANULARITY = 1 (index setting, granules per index block)
- Result: Index calculated every 8192 rows

- GRANULARITY = 4
- Result: Index calculated every 32768 rows (8192 * 4)
"""

# =============================================================================
# INDEX TYPES
# =============================================================================

from chorm import Table, Column, add_index
from chorm.types import UInt64, String, DateTime
from chorm.table_engines import MergeTree
from chorm.sql.expression import Identifier

class User(Table):
    __tablename__ = "users"
    __engine__ = MergeTree()
    __order_by__ = ["id"]
    
    id = Column(UInt64())
    email = Column(String())
    name = Column(String())
    country = Column(String())
    created_at = Column(DateTime())
    description = Column(String())


# -----------------------------------------------------------------------------
# 1. MINMAX INDEX
# -----------------------------------------------------------------------------
"""
Best for: Range queries on ordered/semi-ordered data
Use cases: Timestamps, IDs, counters, prices
How it works: Stores min/max values per index block

Granularity recommendation: 1-2 (needs precision for ranges)
"""

# Good for timestamp ranges
add_index(User, "idx_created", Identifier("created_at"), 
          index_type="minmax", granularity=1)

# Query benefits:
# SELECT * FROM users WHERE created_at > '2024-01-01'
# SELECT * FROM users WHERE id BETWEEN 1000 AND 2000


# -----------------------------------------------------------------------------
# 2. SET INDEX
# -----------------------------------------------------------------------------
"""
Best for: Low-to-medium cardinality columns with clustered values
Use cases: Country codes, status fields, categories
How it works: Stores set of unique values per index block
Parameter: max_rows (0 = unlimited, N = max unique values to store)

Granularity recommendation: 2-4 (can be less precise)
"""

# Set index with max 100 unique values per block
add_index(User, "idx_country", Identifier("country"), 
          index_type="set(100)", granularity=4)

# Set index with unlimited unique values
add_index(User, "idx_status", Identifier("status"), 
          index_type="set(0)", granularity=2)

# Query benefits:
# SELECT * FROM users WHERE country = 'US'
# SELECT * FROM users WHERE country IN ('US', 'UK', 'DE')


# -----------------------------------------------------------------------------
# 3. BLOOM_FILTER INDEX
# -----------------------------------------------------------------------------
"""
Best for: Equality checks on high-cardinality columns
Use cases: Email, user IDs, UUIDs, hashes
How it works: Probabilistic filter (may have false positives)
Parameter: false_positive_rate (0.0-1.0, default 0.025)

Granularity recommendation: 1 (needs precision for equality)
"""

# Default bloom filter (2.5% false positive rate)
add_index(User, "idx_email", Identifier("email"), 
          index_type="bloom_filter", granularity=1)

# Custom false positive rate (1% = more precise, larger index)
add_index(User, "idx_email_precise", Identifier("email"), 
          index_type="bloom_filter(0.01)", granularity=1)

# Query benefits:
# SELECT * FROM users WHERE email = 'user@example.com'
# SELECT * FROM users WHERE id IN (1, 2, 3, 4, 5)


# -----------------------------------------------------------------------------
# 4. TOKENBF_V1 INDEX
# -----------------------------------------------------------------------------
"""
Best for: Full-text search on tokenized text
Use cases: Names, titles, log messages, tags
How it works: Splits text into alphanumeric tokens, stores in bloom filter
Parameters:
  - size: Bloom filter size in bytes (256-1024 recommended)
  - hash_functions: Number of hash functions (2-5 recommended)
  - seed: Random seed (0 is fine)

Granularity recommendation: 1-2 (text search needs precision)
"""

# Token bloom filter for name search
add_index(User, "idx_name_tokens", Identifier("name"), 
          index_type="tokenbf_v1(256, 3, 0)", granularity=1)

# Larger filter for better precision
add_index(User, "idx_desc_tokens", Identifier("description"), 
          index_type="tokenbf_v1(512, 4, 0)", granularity=2)

# Query benefits:
# SELECT * FROM users WHERE name LIKE '%John%'
# SELECT * FROM users WHERE hasToken(name, 'Smith')


# -----------------------------------------------------------------------------
# 5. NGRAMBF_V1 INDEX
# -----------------------------------------------------------------------------
"""
Best for: Substring search, fuzzy matching
Use cases: Search in descriptions, partial matching, typo tolerance
How it works: Splits text into n-character sequences, stores in bloom filter
Parameters:
  - n: N-gram size (3-5 recommended, 4 is common)
  - size: Bloom filter size in bytes (512-2048 recommended)
  - hash_functions: Number of hash functions (2-5 recommended)
  - seed: Random seed (0 is fine)

Granularity recommendation: 2-4 (can be less precise, expensive index)
"""

# 4-gram bloom filter for substring search
add_index(User, "idx_desc_ngrams", Identifier("description"), 
          index_type="ngrambf_v1(4, 512, 3, 0)", granularity=2)

# 3-gram for shorter substrings (more matches, less precise)
add_index(User, "idx_name_ngrams", Identifier("name"), 
          index_type="ngrambf_v1(3, 256, 3, 0)", granularity=1)

# Query benefits:
# SELECT * FROM users WHERE description LIKE '%search%'
# SELECT * FROM users WHERE name LIKE '%mit%'  -- matches "Smith", "Dmitry"


# =============================================================================
# GRANULARITY TUNING GUIDELINES
# =============================================================================

"""
RULE OF THUMB:

1. Start with granularity=1 for all indexes
2. Monitor index size and query performance
3. Increase granularity if:
   - Index is too large (>10% of table size)
   - Table has billions of rows
   - Index is rarely used but takes up space

4. Keep granularity=1 for:
   - Equality checks (bloom_filter, tokenbf_v1)
   - Precise range queries (minmax on timestamps)
   - Small-to-medium tables (<100M rows)

5. Increase to 2-4 for:
   - Set indexes on low-cardinality columns
   - N-gram indexes (expensive)
   - Very large tables (>1B rows)

6. Increase to 8-16 for:
   - Extremely large tables (>10B rows)
   - Rarely-used indexes
   - When index size is critical

EXAMPLE SCENARIOS:

Small table (1M rows):
  - All indexes: granularity=1

Medium table (100M rows):
  - bloom_filter: granularity=1
  - minmax: granularity=1
  - set: granularity=2
  - ngrambf_v1: granularity=4

Large table (1B rows):
  - bloom_filter: granularity=1-2
  - minmax: granularity=2
  - set: granularity=4
  - ngrambf_v1: granularity=8

Very large table (10B+ rows):
  - bloom_filter: granularity=2-4
  - minmax: granularity=4
  - set: granularity=8
  - ngrambf_v1: granularity=16
"""

# =============================================================================
# COMPLETE EXAMPLE
# =============================================================================

class Events(Table):
    __tablename__ = "events"
    __engine__ = MergeTree()
    __order_by__ = ["user_id", "timestamp"]
    __partition_by__ = "toYYYYMM(timestamp)"
    
    user_id = Column(UInt64())
    event_type = Column(String())
    timestamp = Column(DateTime())
    message = Column(String())
    country = Column(String())

# Create indexes with appropriate granularity
session.execute(Events.create_table())

# Timestamp range queries (precise)
session.execute(add_index(Events, "idx_timestamp", Identifier("timestamp"), 
                         "minmax", granularity=1).to_sql())

# Event type equality (medium cardinality)
session.execute(add_index(Events, "idx_event_type", Identifier("event_type"), 
                         "set(50)", granularity=2).to_sql())

# Country equality (low cardinality)
session.execute(add_index(Events, "idx_country", Identifier("country"), 
                         "set(200)", granularity=4).to_sql())

# Message text search (expensive, less precise OK)
session.execute(add_index(Events, "idx_message_tokens", Identifier("message"), 
                         "tokenbf_v1(512, 3, 0)", granularity=2).to_sql())

# Message substring search (very expensive, higher granularity)
session.execute(add_index(Events, "idx_message_ngrams", Identifier("message"), 
                         "ngrambf_v1(4, 1024, 3, 0)", granularity=4).to_sql())
