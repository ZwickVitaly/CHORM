#!/usr/bin/env python
"""Example: Multi-Database Support in CHORM.

This example demonstrates how to:
1. Create and drop databases
2. Define tables with __database__ attribute
3. Use qualified table names in queries
4. Work with tables across multiple databases

Requirements:
    - ClickHouse running on localhost:8123
    - User with CREATE DATABASE permissions
"""

import os
from chorm import create_engine, Session, Table, Column
from chorm.types import UInt64, String, DateTime
from chorm.table_engines import MergeTree
from chorm.sql import select, insert
from chorm.sql.ddl import create_database, drop_database, drop_table


# =============================================================================
# 1. DATABASE MANAGEMENT
# =============================================================================

def database_operations_demo(session: Session):
    """Demonstrate CREATE/DROP DATABASE operations."""
    print("\n" + "=" * 60)
    print("1. DATABASE OPERATIONS")
    print("=" * 60)
    
    # Create a new database
    stmt = create_database("analytics", if_not_exists=True)
    print(f"\nSQL: {stmt.to_sql()}")
    session.execute(stmt.to_sql())
    print("✅ Database 'analytics' created")
    
    # Create with engine specification
    stmt = create_database(
        "reporting",
        if_not_exists=True,
        engine="Atomic",
        comment="Reporting database"
    )
    print(f"\nSQL: {stmt.to_sql()}")
    session.execute(stmt.to_sql())
    print("✅ Database 'reporting' created with Atomic engine")
    
    # Verify databases exist
    result = session.execute("SHOW DATABASES LIKE 'analytics'")
    print(f"\n📋 Databases: {[r[0] for r in result.all()]}")


# =============================================================================
# 2. TABLES WITH __database__ ATTRIBUTE  
# =============================================================================

class AnalyticsEvent(Table):
    """Table in 'analytics' database."""
    __tablename__ = "events"
    __database__ = "analytics"  # <-- Target database
    __engine__ = MergeTree()
    __order_by__ = ["id"]
    
    id = Column(UInt64(), primary_key=True)
    event_name = Column(String())
    user_id = Column(UInt64())


class Report(Table):
    """Table in 'reporting' database."""
    __tablename__ = "daily_reports"
    __database__ = "reporting"
    __engine__ = MergeTree()
    __order_by__ = ["id"]
    
    id = Column(UInt64(), primary_key=True)
    report_date = Column(DateTime())
    total_events = Column(UInt64())


def tables_with_database_demo(session: Session):
    """Demonstrate tables with __database__ attribute."""
    print("\n" + "=" * 60)
    print("2. TABLES WITH __database__ ATTRIBUTE")
    print("=" * 60)
    
    # Check qualified names
    print(f"\n📍 AnalyticsEvent.qualified_name: {AnalyticsEvent.__table__.qualified_name}")
    print(f"📍 Report.qualified_name: {Report.__table__.qualified_name}")
    
    # Create tables
    session.execute(drop_table("analytics.events", if_exists=True).to_sql())
    session.execute(drop_table("reporting.daily_reports", if_exists=True).to_sql())
    
    ddl = AnalyticsEvent.create_table()
    print(f"\n📝 DDL:\n{ddl}")
    session.execute(ddl)
    print("✅ Table analytics.events created")
    
    ddl = Report.create_table()
    print(f"\n📝 DDL:\n{ddl}")
    session.execute(ddl)
    print("✅ Table reporting.daily_reports created")


# =============================================================================
# 3. QUERIES WITH QUALIFIED NAMES
# =============================================================================

def queries_demo(session: Session):
    """Demonstrate queries with fully qualified table names."""
    print("\n" + "=" * 60)
    print("3. QUERIES WITH QUALIFIED NAMES")
    print("=" * 60)
    
    # INSERT with qualified name
    stmt = insert(AnalyticsEvent).values([
        {"id": 1, "event_name": "page_view", "user_id": 100},
        {"id": 2, "event_name": "click", "user_id": 100},
        {"id": 3, "event_name": "purchase", "user_id": 101},
    ])
    print(f"\n📝 INSERT SQL:\n{stmt.to_sql()}")
    session.execute(stmt.to_sql())
    print("✅ Data inserted into analytics.events")
    
    # SELECT with qualified column names
    stmt = select(
        AnalyticsEvent.id,
        AnalyticsEvent.event_name,
        AnalyticsEvent.user_id
    ).where(
        AnalyticsEvent.user_id == 100
    )
    print(f"\n📝 SELECT SQL:\n{stmt.to_sql()}")
    
    result = session.execute(stmt.to_sql())
    print("\n📊 Results:")
    for row in result.all():
        print(f"   id={row[0]}, event={row[1]}, user={row[2]}")


# =============================================================================
# 4. CROSS-DATABASE QUERIES
# =============================================================================

def cross_database_demo(session: Session):
    """Demonstrate working with multiple databases."""
    print("\n" + "=" * 60)
    print("4. CROSS-DATABASE QUERIES")
    print("=" * 60)
    
    # You can query tables from different databases in the same session
    print("\n📍 Query from analytics database:")
    result = session.execute("SELECT count() FROM analytics.events")
    print(f"   Event count: {result.first()[0]}")
    
    print("\n📍 Query from reporting database:")
    result = session.execute("SELECT count() FROM reporting.daily_reports")
    print(f"   Report count: {result.first()[0]}")


# =============================================================================
# CLEANUP
# =============================================================================

def cleanup(session: Session):
    """Clean up test databases."""
    print("\n" + "=" * 60)
    print("CLEANUP")
    print("=" * 60)
    
    session.execute(drop_database("analytics", if_exists=True).to_sql())
    print("✅ Database 'analytics' dropped")
    
    session.execute(drop_database("reporting", if_exists=True).to_sql())
    print("✅ Database 'reporting' dropped")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("CHORM Multi-Database Support Demo")
    print("=" * 60)
    
    # Connect to ClickHouse
    password = os.getenv("CLICKHOUSE_PASSWORD", "123")
    engine = create_engine(
        "clickhouse://localhost:8123/default",
        username="default",
        password=password
    )
    
    session = Session(engine)
    
    try:
        database_operations_demo(session)
        tables_with_database_demo(session)
        queries_demo(session)
        cross_database_demo(session)
    finally:
        cleanup(session)
    
    print("\n" + "=" * 60)
    print("Demo completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
