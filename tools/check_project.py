"""Validate sources/fixtures without installing Home Assistant or touching devices."""

import ast
import json
import math
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IGNORED_PARTS = {
    ".venv",
    "venv",
    ".git",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "ha-config",
    "config",
    ".storage",
    "hassfest-core",
}


def translation_keys(value, prefix=()):
    """All translated leaf paths must match, including errors and field labels."""
    result = set()
    for key, item in value.items():
        path = (*prefix, key)
        if isinstance(item, dict):
            result.update(translation_keys(item, path))
        else:
            assert isinstance(item, str) and item
            result.add(path)
    return result


def check():
    for path in ROOT.rglob("*.py"):
        if any(part in IGNORED_PARTS for part in path.relative_to(ROOT).parts):
            continue
        ast.parse(path.read_text(), filename=str(path))
    for path in ROOT.rglob("*.json"):
        if any(part in IGNORED_PARTS for part in path.relative_to(ROOT).parts):
            continue
        json.loads(path.read_text())
    manifest = json.loads((ROOT / "custom_components/sema/manifest.json").read_text())
    assert manifest["domain"] == "sema"
    if manifest["config_flow"]:
        assert (ROOT / "custom_components/sema/config_flow.py").is_file()
        strings = json.loads((ROOT / "custom_components/sema/strings.json").read_text())
        for lang in ("sk", "en"):
            translation = json.loads(
                (ROOT / f"custom_components/sema/translations/{lang}.json").read_text()
            )
            assert translation_keys(translation) == translation_keys(strings)
    info = json.loads((ROOT / "fixtures/info.json").read_text())
    assert info["api_version"] == 1
    assert info["device_uid"]
    assert info["recommended_poll_interval_seconds"] > 0
    assert info["max_age_seconds"] > info["recommended_poll_interval_seconds"]
    for name in ["state.json", "state_pump_unavailable.json"]:
        state = json.loads((ROOT / "fixtures" / name).read_text())
        assert state["device_uid"] == info["device_uid"]
        assert state["api_version"] == info["api_version"]
        assert type(state["pump_available"]) is bool
        for field in ["generated_at", "observed_at"]:
            value = state[field]
            if value is not None:
                assert (
                    datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo
                    is not None
                )
        for value in [*state["temperatures"].values(), state["power_percent"]]:
            assert value is None or (
                type(value) in (int, float) and math.isfinite(value)
            )
        for value in state["states"].values():
            assert value is None or type(value) is bool
        if not state["pump_available"]:
            assert all(value is None for value in state["temperatures"].values())
            assert all(value is None for value in state["states"].values())
            assert state["power_percent"] is None
    for path in ROOT.rglob("*.md"):
        if any(part in IGNORED_PARTS for part in path.relative_to(ROOT).parts):
            continue
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
            if "://" in target or target.startswith("#"):
                continue
            assert (path.parent / target.split("#")[0]).exists(), (
                f"Broken link: {path}: {target}"
            )
    print("Project syntax, JSON fixtures, contract and local documentation links: OK")
    print("This static check does not run Home Assistant or test real devices.")


if __name__ == "__main__":
    check()
