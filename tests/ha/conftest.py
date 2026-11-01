"""HA-native fixtures; no production configuration or network access."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.sema.protocol import parse_info, parse_state

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Allow loading this development custom integration in the test HA."""


@pytest.fixture
def info():
    return parse_info(json.loads((ROOT / "fixtures/info.json").read_text()))


@pytest.fixture
def client(info):
    client = AsyncMock()
    client.async_get_info.return_value = info
    client.async_get_state.return_value = parse_state(
        json.loads((ROOT / "fixtures/state.json").read_text()), info
    )
    return client


@pytest.fixture
def flow_client(client):
    with patch(
        "custom_components.sema.config_flow.SemaClient", return_value=client
    ) as factory:
        yield factory


@pytest.fixture
def skip_setup():
    with patch("custom_components.sema.async_setup_entry", return_value=True) as setup:
        yield setup
