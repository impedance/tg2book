import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import channel_registry


def test_add_new_channel(tmp_path):
    db_path = tmp_path / "channels.db"

    added = channel_registry.add_channel("testchannel", str(db_path))

    assert added is True
    assert channel_registry.get_channels(str(db_path)) == ["testchannel"]


def test_reject_duplicate_add(tmp_path):
    db_path = tmp_path / "channels.db"

    assert channel_registry.add_channel("@TestChannel", str(db_path)) is True
    assert channel_registry.add_channel("testchannel", str(db_path)) is False
    assert channel_registry.get_channels(str(db_path)) == ["testchannel"]


def test_remove_existing_channel(tmp_path):
    db_path = tmp_path / "channels.db"
    channel_registry.add_channel("testchannel", str(db_path))

    removed = channel_registry.remove_channel("@testchannel", str(db_path))

    assert removed is True
    assert channel_registry.get_channels(str(db_path)) == []


def test_remove_unknown_channel(tmp_path):
    db_path = tmp_path / "channels.db"

    removed = channel_registry.remove_channel("unknown_channel", str(db_path))

    assert removed is False


def test_list_channels_stable_order(tmp_path):
    db_path = tmp_path / "channels.db"
    channel_registry.add_channel("zeta", str(db_path))
    channel_registry.add_channel("-1001234567890", str(db_path))
    channel_registry.add_channel("alpha", str(db_path))

    channels = channel_registry.get_channels(str(db_path))

    assert channels == ["-1001234567890", "alpha", "zeta"]


def test_registry_persists_between_module_reloads(tmp_path):
    db_path = tmp_path / "channels.db"
    channel_registry.add_channel("https://t.me/TestChannel", str(db_path))

    reloaded = importlib.reload(channel_registry)

    assert reloaded.get_channels(str(db_path)) == ["testchannel"]


@pytest.mark.parametrize("identifier", ["", "   ", "@", None])
def test_invalid_identifier_raises_value_error(tmp_path, identifier):
    db_path = tmp_path / "channels.db"

    with pytest.raises(ValueError):
        channel_registry.add_channel(identifier, str(db_path))
