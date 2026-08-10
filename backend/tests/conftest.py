"""Shared pytest fixtures — session-scoped event loop so Motor client (bound to
the first loop it saw) works across all async tests in the session."""
import asyncio
import pytest


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
