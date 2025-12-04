"""Tests for connection timeout and configuration parameters."""

import pytest
from chorm.engine import EngineConfig, create_engine
from chorm.async_engine import create_async_engine


class TestEngineConfig:
    """Test EngineConfig with timeout parameters."""

    def test_default_timeouts(self):
        """Test default timeout values."""
        config = EngineConfig()
        assert config.connect_timeout == 10
        assert config.send_receive_timeout == 300

    def test_custom_timeouts(self):
        """Test custom timeout values."""
        config = EngineConfig(connect_timeout=5, send_receive_timeout=60)
        assert config.connect_timeout == 5
        assert config.send_receive_timeout == 60

    def test_compression_settings(self):
        """Test compression configuration."""
        # Boolean compression
        config1 = EngineConfig(compress=True)
        assert config1.compress is True

        # String compression type
        config2 = EngineConfig(compress="lz4")
        assert config2.compress == "lz4"

        # No compression
        config3 = EngineConfig(compress=False)
        assert config3.compress is False

    def test_security_parameters(self):
        """Test security-related parameters."""
        config = EngineConfig(
            secure=True,
            verify=True,
            ca_cert="/path/to/ca.pem",
            client_cert="/path/to/client.pem",
            client_cert_key="/path/to/key.pem",
        )
        assert config.secure is True
        assert config.verify is True
        assert config.ca_cert == "/path/to/ca.pem"
        assert config.client_cert == "/path/to/client.pem"
        assert config.client_cert_key == "/path/to/key.pem"

    def test_proxy_parameters(self):
        """Test proxy configuration."""
        config = EngineConfig(http_proxy="http://proxy:8080", https_proxy="https://proxy:8443")
        assert config.http_proxy == "http://proxy:8080"
        assert config.https_proxy == "https://proxy:8443"

    def test_monitoring_parameters(self):
        """Test monitoring parameters."""
        config = EngineConfig(client_name="my-app", query_limit=1000)
        assert config.client_name == "my-app"
        assert config.query_limit == 1000

    def test_with_overrides(self):
        """Test with_overrides method includes new parameters."""
        config = EngineConfig(connect_timeout=10)
        new_config = config.with_overrides(
            connect_timeout=5, send_receive_timeout=60, compress="zstd", client_name="test-client"
        )

        assert new_config.connect_timeout == 5
        assert new_config.send_receive_timeout == 60
        assert new_config.compress == "zstd"
        assert new_config.client_name == "test-client"

        # Original config unchanged
        assert config.connect_timeout == 10


class TestCreateEngine:
    """Test create_engine with timeout parameters."""

    def test_create_engine_with_timeouts(self):
        """Test creating engine with timeout parameters."""
        engine = create_engine(host="localhost", port=8123, connect_timeout=5, send_receive_timeout=120)

        assert engine.config.connect_timeout == 5
        assert engine.config.send_receive_timeout == 120

    def test_create_engine_with_compression(self):
        """Test creating engine with compression."""
        engine = create_engine(host="localhost", compress="lz4")

        assert engine.config.compress == "lz4"

    def test_create_engine_with_security(self):
        """Test creating engine with security parameters."""
        engine = create_engine(host="localhost", secure=True, verify=True, ca_cert="certifi")

        assert engine.config.secure is True
        assert engine.config.verify is True
        assert engine.config.ca_cert == "certifi"

    def test_create_engine_with_client_name(self):
        """Test creating engine with client name for monitoring."""
        engine = create_engine(host="localhost", client_name="chorm-test-app")

        assert engine.config.client_name == "chorm-test-app"

    def test_create_engine_from_url_with_params(self):
        """Test creating engine from URL with query parameters."""
        # Note: URL parsing for new parameters would need to be added
        # to EngineConfig.from_url if we want to support them in URLs
        engine = create_engine("clickhouse://localhost:8123/default", connect_timeout=15, compress=True)

        assert engine.config.host == "localhost"
        assert engine.config.port == 8123
        assert engine.config.connect_timeout == 15
        assert engine.config.compress is True


class TestCreateAsyncEngine:
    """Test create_async_engine with timeout parameters."""

    def test_create_async_engine_with_timeouts(self):
        """Test creating async engine with timeout parameters."""
        engine = create_async_engine(host="localhost", port=8123, connect_timeout=5, send_receive_timeout=120)

        assert engine.config.connect_timeout == 5
        assert engine.config.send_receive_timeout == 120

    def test_create_async_engine_with_all_params(self):
        """Test creating async engine with multiple parameters."""
        engine = create_async_engine(
            host="localhost",
            connect_timeout=5,
            send_receive_timeout=120,
            compress="zstd",
            verify=True,
            client_name="async-app",
            query_limit=5000,
        )

        assert engine.config.connect_timeout == 5
        assert engine.config.send_receive_timeout == 120
        assert engine.config.compress == "zstd"
        assert engine.config.verify is True
        assert engine.config.client_name == "async-app"
        assert engine.config.query_limit == 5000


class TestConnectArgs:
    """Test that connect_args are properly passed through."""

    def test_connect_args_override(self):
        """Test that connect_args can override config values."""
        engine = create_engine(host="localhost", connect_timeout=10, connect_args={"connect_timeout": 5})

        # connect_args should override config
        # This is tested by verifying the engine accepts connect_args
        assert engine._connect_args.get("connect_timeout") == 5

    def test_mixed_config_and_connect_args(self):
        """Test mixing config and connect_args."""
        engine = create_engine(
            host="localhost",
            connect_timeout=10,
            compress="lz4",
            connect_args={"send_receive_timeout": 60, "client_name": "test"},
        )

        assert engine.config.connect_timeout == 10
        assert engine.config.compress == "lz4"
        assert engine._connect_args.get("send_receive_timeout") == 60
        assert engine._connect_args.get("client_name") == "test"
