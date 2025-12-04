# Changelog

All notable changes to CHORM will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-12-05

### Added

#### Core ORM Features
- Declarative table definitions with `Table` base class
- Column descriptors with type safety
- Support for all ClickHouse data types (21+ types)
- MergeTree family engines with full configuration
- Synchronous and asynchronous session management
- Query builder with fluent API

#### Query Construction
- SELECT queries with WHERE, ORDER BY, LIMIT, OFFSET
- ClickHouse-specific clauses: PREWHERE, FINAL, SAMPLE, SETTINGS
- JOIN support (INNER, LEFT, RIGHT, FULL, CROSS, ASOF, ARRAY JOIN)
- GROUP BY and HAVING clauses
- Subqueries and Common Table Expressions (CTEs)
- Window functions with PARTITION BY and ORDER BY
- UNION, INTERSECT, EXCEPT set operations
- DISTINCT, LIMIT BY, WITH TOTALS

#### DML Operations
- INSERT with batch support
- UPDATE (mapped to ALTER TABLE UPDATE)
- DELETE (mapped to ALTER TABLE DELETE)
- Bulk insert operations (100,000+ rows/batch)
- DataFrame integration for pandas

#### DDL Operations
- CREATE TABLE with all MergeTree engines
- DROP TABLE, TRUNCATE TABLE, RENAME TABLE
- ALTER TABLE: ADD/DROP/MODIFY/RENAME COLUMN
- Index management (minmax, set, bloom_filter, tokenbf, ngrambf)
- TTL support for data retention policies
- Partition management (DETACH, ATTACH, DROP, FETCH)
- Materialized views
- Dictionary support

#### Advanced Features
- Connection pooling (sync and async)
- Retry logic with exponential backoff
- Health checks and monitoring
- Query caching with LRU eviction
- Performance metrics collection
- Query complexity analysis
- Batch operations optimization
- Model validation system (7 validators)

#### CLI Tools
- `chorm init` - Initialize new project
- `chorm make-migration` - Generate migration files
- `chorm migrate` - Apply migrations
- `chorm show-migrations` - List migration status
- `chorm downgrade` - Rollback migrations
- `chorm introspect` - Generate models from existing tables

#### Production Features
- Comprehensive error handling with ClickHouse-specific errors
- Connection timeout configuration
- SSL/TLS support
- Proxy support
- Compression (lz4, zstd, brotli, gzip)
- Query settings presets (fast, memory_efficient, heavy_analytics, etc.)
- Execution statistics tracking

### Documentation
- Comprehensive README with examples
- Advanced analytics guide
- Connection configuration guide
- Pooling guide
- ClickHouse indexes guide
- Validation guide
- 14 example scripts

### Testing
- 628 unit and integration tests
- 60 integration tests with live ClickHouse
- Full test coverage for all major features

[0.1.0]: https://github.com/zwickvitaly/chorm/releases/tag/v0.1.0
