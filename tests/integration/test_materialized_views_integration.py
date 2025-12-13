
import os
from chorm import Table, Column, create_engine, Session, select
from chorm.types import UInt64, String
from chorm.table_engines import MergeTree, MaterializedView
from chorm.sql.expression import func
from chorm.introspection import TableIntrospector, ModelGenerator

def main():
    print("=" * 60)
    print("CHORM Integration Test - Materialized Views")
    print("=" * 60)

    # 1. Connect
    print("\n1. Connecting to ClickHouse...")
    password = os.getenv("CLICKHOUSE_PASSWORD", "123")
    # Assuming standard ports active
    engine = create_engine("clickhouse://localhost:8123/default", username="default", password=password)
    session = Session(engine)
    print("✓ Connected successfully")

    # 2. Define Models
    class MvSource(Table):
        __tablename__ = "mv_source_test"
        __engine__ = MergeTree()
        id = Column(UInt64())
        val = Column(UInt64())
        
    class MvTarget(Table):
        __tablename__ = "mv_target_test"
        __engine__ = MergeTree()
        id = Column(UInt64())
        sum_val = Column(UInt64())
        
    class MvView(Table):
        __tablename__ = "mv_view_test"
        __engine__ = MaterializedView(to_table="mv_target_test")
        # Select sum(val) grouped by id
        __select__ = select(MvSource.id, func.sum(MvSource.val).label("sum_val")).select_from(MvSource).group_by(MvSource.id)

    class MvViewInner(Table):
        __tablename__ = "mv_view_inner_test"
        __engine__ = MaterializedView(engine=MergeTree(), populate=True)
        # Select count(*) grouped by id
        __select__ = select(MvSource.id, func.count().label("cnt")).select_from(MvSource).group_by(MvSource.id)
        
        # Columns must be defined for introspection to match
        id = Column(UInt64())
        cnt = Column(UInt64())

    # 3. Create Tables
    print("\n2. Creating tables...")
    with engine.connect() as conn:
        conn.execute("DROP TABLE IF EXISTS mv_view_test")
        conn.execute("DROP TABLE IF EXISTS mv_view_inner_test")
        conn.execute("DROP TABLE IF EXISTS mv_target_test")
        conn.execute("DROP TABLE IF EXISTS mv_source_test")
        
        # Order matters: Target, Source, View
        print("  Creating Target...")
        conn.execute(MvTarget.create_table())
        print("  Creating Source...")
        conn.execute(MvSource.create_table())
        print("  Creating Views...")
        conn.execute(MvView.create_table())
        conn.execute(MvViewInner.create_table())
    print("✓ Tables created")

    # 4. Insert Data
    print("\n3. Inserting data into Source...")
    # Insert multiple rows
    data = [
        MvSource(id=1, val=10),
        MvSource(id=1, val=20),
        MvSource(id=2, val=5),
    ]
    for item in data:
        session.add(item)
    session.commit()
    print("✓ Inserted 3 rows")

    # 5. Verify Target
    print("\n4. Verifying Target table data...")
    stmt = select(MvTarget.id, MvTarget.sum_val).order_by(MvTarget.id)
    result = session.execute(stmt).all()
    print("  Target rows:", result)
    
    # Verify Inner MV
    print("\n   Verifying Inner MV data (populated)...")
    # For Inner MV with populate=True, it should have the data
    stmt = select(MvViewInner.id, MvViewInner.cnt).order_by(MvViewInner.id)
    # Note: Introspection won't know MvViewInner is a table to query unless we made a model. We did.
    
    # Wait, 'MaterializedView' engine tables can be queried directly? Yes.
    # But CHORM Session.execute(select...) expects a Table model. MvViewInner is one.
    
    result_inner = session.execute(stmt).all()
    print("  Inner MV rows:", result_inner)


    # 6. Introspection
    print("\n5. Testing Introspection...")
    with engine.connect() as conn:
        introspector = TableIntrospector(conn.client)
        generator = ModelGenerator()
        
        # Test TO table view
        info = introspector.get_table_info("mv_view_test")
        code = generator.generate_model(info)
        print("\n  Generated Code (TO table):\n")
        print(code)
        
        if "to_table=\"default.mv_target_test\"" in code or 'to_table="mv_target_test"' in code:
             print("✓ 'to_table' correctly introspected")
        else:
             print("✗ 'to_table' failed introspection")

        # Test Inner engine view
        info_inner = introspector.get_table_info("mv_view_inner_test")
        code_inner = generator.generate_model(info_inner)
        print("\n  Generated Code (Inner Engine):\n")
        print(code_inner)
        
        if "engine=MergeTree()" in code_inner:
             print("✓ 'engine' correctly introspected")
             if "populate=True" in code_inner:
                  print("Warning: 'populate=True' found in introspection (unexpected but accepted)")
             else:
                  print("✓ 'populate=True' correctly absent (one-time op)")
        else:
             print(f"✗ Inner engine failed introspection. Code: {code_inner}")

    # Cleanup
    print("\n6. Cleaning up...")
    with engine.connect() as conn:
        conn.execute("DROP TABLE IF EXISTS mv_view_test")
        conn.execute("DROP TABLE IF EXISTS mv_view_inner_test")
        conn.execute("DROP TABLE IF EXISTS mv_target_test")
        conn.execute("DROP TABLE IF EXISTS mv_source_test")
    print("✓ Cleanup complete")

if __name__ == "__main__":
    main()
