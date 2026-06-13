"""Tests for src/core/utils/ids.py."""
import re
import uuid

import pytest

from src.core.utils.ids import uuid7


class TestUuid7:
    def test_returns_string(self):
        result = uuid7()
        assert isinstance(result, str)

    def test_valid_uuid_format(self):
        result = uuid7()
        # Should match UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        assert re.match(pattern, result)

    def test_is_valid_uuid(self):
        result = uuid7()
        # Should be parseable as a UUID
        parsed = uuid.UUID(result)
        assert str(parsed) == result

    def test_version_7(self):
        result = uuid7()
        parsed = uuid.UUID(result)
        # UUID version is in bits 48-51 of the time_hi_and_version field
        # Version 7 means version field should be 7
        assert parsed.version == 7

    def test_uniqueness(self):
        ids = {uuid7() for _ in range(1000)}
        assert len(ids) == 1000

    def test_time_ordered(self):
        # Generate two UUIDs with a small delay
        id1 = uuid7()
        import time
        time.sleep(0.001)
        id2 = uuid7()

        # UUIDv7 should be time-ordered, so id2 > id1
        assert id2 > id1

    def test_hex_only(self):
        result = uuid7()
        # Remove hyphens and check all remaining chars are hex
        hex_chars = result.replace("-", "")
        assert all(c in "0123456789abcdef" for c in hex_chars)

    def test_length(self):
        result = uuid7()
        assert len(result) == 36  # Standard UUID length with hyphens
