"""The app server must accept bursts of parallel connections, as a browser sends when the preview refreshes."""

import socket
from concurrent.futures import ThreadPoolExecutor

import pytest

pytestmark = pytest.mark.e2e


def _get(port: int) -> bytes:
    with socket.create_connection(("127.0.0.1", port), timeout=15) as s:
        s.sendall(f"GET / HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n".encode())
        data = b""
        while chunk := s.recv(65536):
            data += chunk
    return data


def test_parallel_connection_burst(server):
    # With the socket default backlog of 5, Windows reset some of these connections.
    for _ in range(10):
        with ThreadPoolExecutor(max_workers=100) as pool:
            responses = list(pool.map(lambda _: _get(server["port"]), range(100)))
        assert all(r.startswith((b"HTTP/1.0 200", b"HTTP/1.1 200")) for r in responses)
