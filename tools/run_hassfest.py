"""Run official pinned hassfest without mixing its dependencies into HA tests."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

HASSFEST_COMMIT = "357cae5c598dfcd7a0ea7dc5b1facccd4ec6037b"  # Core 2026.10.4
ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-path", type=Path, required=True)
    args = parser.parse_args()
    source = args.core_path.resolve()
    if not (source / "script/hassfest/__main__.py").is_file():
        parser.error("Expected a Core checkout containing script/hassfest")
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=source, text=True
    ).strip()
    if commit != HASSFEST_COMMIT:
        parser.error("Expected pinned Core 2026.10.4 commit; see docs/VALIDATION.md")
    env = os.environ.copy()
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "script.hassfest",
            "--action",
            "validate",
            "--integration-path",
            str(ROOT / "custom_components/sema"),
        ],
        cwd=source,
        env=env,
        check=False,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
