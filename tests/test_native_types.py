
import logging
import uuid
import ipaddress
from datetime import datetime, timezone

import pytest
from chorm import create_engine
from chorm.batch import bulk_insert

# Configure logging to see performance warnings or info
logging.basicConfig(level=logging.INFO)

class TestNativeTypes:
    @pytest.fixture
    def engine(self):
        engine = create_engine("clickhouse://default:123@localhost:8123/default")
        # Ensure table exists
        with engine.connection() as conn:
            conn.execute("DROP TABLE IF EXISTS test_native_types")
            conn.execute("""
                CREATE TABLE test_native_types (
                    id UInt64,
                    uuid UUID,
                    ip IPv4,
                    tags Array(String),
                    metadata Map(String, String),
                    status Enum8('active' = 1, 'inactive' = 0),
                    created_at DateTime('UTC')
                ) ENGINE = MergeTree() ORDER BY id
            """)
        yield engine
        with engine.connection() as conn:
            conn.execute("DROP TABLE IF EXISTS test_native_types")

    def test_bulk_insert_complex_types(self, engine):
        """Verify that bulk_insert handles complex Python types naturally."""
        
        # Prepare data with rich Python types
        u1 = uuid.uuid4()
        u2 = uuid.uuid4()
        ip1 = ipaddress.IPv4Address("192.168.1.1")
        ip2 = ipaddress.IPv4Address("10.0.0.1")
        # Use UTC aware datetime, strip microseconds to avoid precision issues if any
        now = datetime.now(timezone.utc).replace(microsecond=0)
        
        data = [
            [
                1, 
                u1, 
                ip1, 
                ["tag1", "tag2"], 
                {"key": "value", "env": "prod"}, 
                "active", 
                now
            ],
            [
                2, 
                u2, 
                ip2, 
                ["tag3"], 
                {"key": "value2"}, 
                "inactive", 
                now
            ]
        ]
        
        # Insert using bulk_insert (native)
        client = engine.connect().client
        stats = bulk_insert(
            client=client,
            table_name="test_native_types",
            data=data,
            columns=["id", "uuid", "ip", "tags", "metadata", "status", "created_at"]
        )
        
        assert stats["total_rows"] == 2
        
        # Verify data came back correctly
        with engine.connection() as conn:
            rows = conn.query("SELECT * FROM test_native_types ORDER BY id").result_rows
            
            # Row 1
            assert rows[0][0] == 1
            assert rows[0][1] == u1
            assert rows[0][2] == ip1
            assert rows[0][3] == ["tag1", "tag2"]
            assert rows[0][4] == {"key": "value", "env": "prod"}
            assert rows[0][5] == "active"
            
            ret_dt = rows[0][6]
            # Ensure comparison is apple-to-apple (both timezone aware)
            if ret_dt.tzinfo is None:
                ret_dt = ret_dt.replace(tzinfo=timezone.utc)
            
            assert ret_dt == now

            # Row 2
            assert rows[1][0] == 2
            assert rows[1][1] == u2
            assert rows[1][5] == "inactive"
