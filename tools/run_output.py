"""Keep generated validation products outside maintained repository source."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_output(path):
    path = Path(path).resolve()
    if path.is_relative_to(ROOT) and not any(path.is_relative_to(ROOT / directory)
                                            for directory in ("target", "mbt/.work")):
        raise ValueError("test output must be under target/ or an external temporary workspace: " + str(path))
    return path
