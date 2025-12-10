"""
ARRAY JOIN Example
-----------------

This example demonstrates how to use ARRAY JOIN and LEFT ARRAY JOIN
to unnest array columns in ClickHouse.
"""

import os
from chorm import Table, Column, MergeTree, select, insert, create_engine
from chorm.session import Session
from chorm.types import UInt64, String, Array
from chorm.sql.expression import Identifier, func


# Define our model
class Product(Table):
    __tablename__ = "products_demo"
    __engine__ = MergeTree()
    
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    tags = Column(Array(String()))
    prices = Column(Array(UInt64()))  # Price history


def main():
    # Connect to ClickHouse
    host = os.getenv("CLICKHOUSE_HOST", "localhost")
    port = int(os.getenv("CLICKHOUSE_PORT", "8123"))
    database = os.getenv("CLICKHOUSE_DB", "default")
    
    engine = create_engine(
        host=host,
        port=port,
        username="default",
        password="",
        database=database,
    )
    session = Session(engine)

    # 1. Setup: Create table and insert data
    print("--- Setting up data ---")
    session.execute(f"DROP TABLE IF EXISTS {Product.__tablename__}")
    session.execute(Product.create_table())

    products = [
        Product(id=1, name="Laptop", tags=["electronics", "work"], prices=[1000, 950, 900]),
        Product(id=2, name="Coffee", tags=["food", "drink"], prices=[5, 6]),
        Product(id=3, name="Mystery Box", tags=[], prices=[]),  # Empty arrays
    ]
    
    for p in products:
        session.execute(insert(Product).values(**p.to_dict()))
    session.commit()

    # 2. Basic ARRAY JOIN
    # Flatten tags for each product
    print("\n--- Basic ARRAY JOIN (Flatten Tags) ---")
    stmt = (
        select(Product.name, Identifier("tag"))
        .select_from(Product)
        .array_join(Product.tags.label("tag"))
        .order_by(Product.id, Identifier("tag"))
    )
    
    print(f"SQL: {stmt.to_sql()}")
    results = session.execute(stmt).all()
    for row in results:
        print(f"{row.name}: {row.tag}")
    # Note: "Mystery Box" is excluded because it has empty tags

    # 3. LEFT ARRAY JOIN
    # Include rows with empty arrays
    print("\n--- LEFT ARRAY JOIN (Include Empty) ---")
    stmt = (
        select(Product.name, Identifier("tag"))
        .select_from(Product)
        .left_array_join(Product.tags.label("tag"))
        .order_by(Product.id)
    )
    
    print(f"SQL: {stmt.to_sql()}")
    results = session.execute(stmt).all()
    for row in results:
        tag_display = row.tag if row.tag else "<empty>"
        print(f"{row.name}: {tag_display}")

    # 4. Aggregation after ARRAY JOIN
    # Count products per tag
    print("\n--- Aggregation after ARRAY JOIN (Tag Counts) ---")
    stmt = (
        select(Identifier("tag"), func.count().label("count"))
        .select_from(Product)
        .array_join(Product.tags.label("tag"))
        .group_by(Identifier("tag"))
        .order_by(func.count().desc())
    )
    
    print(f"SQL: {stmt.to_sql()}")
    results = session.execute(stmt).all()
    for row in results:
        print(f"Tag '{row.tag}': {row.count}")

    # 5. Multiple Arrays (Chained)
    # Cartesian product of tags and prices (be careful with this!)
    print("\n--- Multiple Arrays (Chained - Cartesian Product) ---")
    stmt = (
        select(Product.name, Identifier("tag"), Identifier("price"))
        .select_from(Product)
        .array_join(Product.tags.label("tag"))
        .array_join(Product.prices.label("price"))
        .where(Product.name == "Coffee")
    )
    
    print(f"SQL: {stmt.to_sql()}")
    results = session.execute(stmt).all()
    for row in results:
        print(f"{row.name}: {row.tag} - ${row.price}")

    # Cleanup
    session.execute(f"DROP TABLE IF EXISTS {Product.__tablename__}")


if __name__ == "__main__":
    main()
