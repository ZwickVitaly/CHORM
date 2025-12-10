import sys
from unittest.mock import MagicMock

# Mock clickhouse_connect to avoid installation requirement for SQL generation testing
sys.modules["clickhouse_connect"] = MagicMock()

from chorm import Table, Column, MergeTree, select, insert, update, delete
from chorm.types import UInt64, String

class User(Table):
    __tablename__ = "users"
    __engine__ = MergeTree()
    
    id = Column(UInt64(), primary_key=True)
    name = Column(String())

print("--- SELECT ---")
stmt = select(User.id, User.name).where(User.id > 10).order_by(User.name).limit(5)
print(stmt.to_sql())

print("\n--- INSERT ---")
stmt = insert(User).values(id=1, name="Alice")
print(stmt.to_sql())

print("\n--- UPDATE ---")
stmt = update(User).where(User.id == 1).values(name="Bob")
print(stmt.to_sql())

print("\n--- DELETE ---")
stmt = delete(User).where(User.id == 1)
print(stmt.to_sql())
