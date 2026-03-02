import os
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# OFFLINE_BY_DEFAULT: Block real network access in tests unless explicitly opted in.
@pytest.fixture(autouse=True, scope="session")
def _offline_by_default_network_guard():
    if os.environ.get("INTEGRATION") == "1":
        yield
        return

    original_socket = socket.socket
    original_create_connection = socket.create_connection
    original_socketpair = socket.socketpair

    def _guarded_socket(*args, **kwargs):
        family = args[0] if args else kwargs.get("family", socket.AF_INET)
        if family in (socket.AF_INET, socket.AF_INET6):
            raise RuntimeError("Network is disabled for tests. Set INTEGRATION=1 to enable.")
        return original_socket(*args, **kwargs)

    def _blocked_create_connection(*_args, **_kwargs):
        raise RuntimeError("Network is disabled for tests. Set INTEGRATION=1 to enable.")

    socket.socket = _guarded_socket  # type: ignore[assignment]
    socket.create_connection = _blocked_create_connection  # type: ignore[assignment]
    socket.socketpair = original_socketpair  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket = original_socket  # type: ignore[assignment]
        socket.create_connection = original_create_connection  # type: ignore[assignment]
        socket.socketpair = original_socketpair  # type: ignore[assignment]
