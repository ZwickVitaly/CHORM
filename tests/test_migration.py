"""Tests for migration core logic."""

import pytest
from unittest.mock import MagicMock, call
from chorm.migration import Migration, MigrationManager
from chorm.session import Session


class ExampleMigration(Migration):
    id = "20230101_001"
    name = "initial_schema"

    def upgrade(self, session: Session) -> None:
        pass

    def downgrade(self, session: Session) -> None:
        pass


class TestMigrationManager:

    @pytest.fixture
    def mock_session(self):
        return MagicMock(spec=Session)

    @pytest.fixture
    def manager(self, mock_session):
        return MigrationManager(mock_session)

    def test_ensure_migration_table(self, manager, mock_session):
        manager.ensure_migration_table()

        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args[0][0]
        assert "CREATE TABLE IF NOT EXISTS chorm_migrations" in call_args

    def test_get_applied_migrations(self, manager, mock_session):
        # Mock result set
        mock_result = MagicMock()
        # Mock .all() to return list of rows (tuples or Row objects)
        # Since we access row[0], tuples are fine
        mock_result.all.return_value = [("20230101_001",), ("20230102_002",)]
        mock_session.execute.return_value = mock_result

        migrations = manager.get_applied_migrations()

        assert migrations == ["20230101_001", "20230102_002"]
        # Should ensure table exists first
        assert mock_session.execute.call_count == 2

    def test_apply_migration(self, manager, mock_session):
        migration = ExampleMigration()
        manager.apply_migration(migration)

        # Should ensure table exists and then insert
        assert mock_session.execute.call_count == 2
        insert_call = mock_session.execute.call_args
        sql = insert_call[0][0]

        assert "INSERT INTO chorm_migrations" in sql
        assert "20230101_001" in sql
        assert "initial_schema" in sql

    def test_unapply_migration(self, manager, mock_session):
        manager.unapply_migration("20230101_001")

        # Should ensure table exists and then delete
        assert mock_session.execute.call_count == 2
        delete_call = mock_session.execute.call_args
        sql = delete_call[0][0]

        assert "ALTER TABLE chorm_migrations DELETE" in sql
        assert "20230101_001" in sql
