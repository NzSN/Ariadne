"""Canonical Rust source inventory and isolated copies of the single package."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
MODELS = (
    "AriadnePredicateAdmission.tla",
    "AriadneGuardedTargetResolution.tla",
    "AriadneLoopTargetClosure.tla",
)


def source_files():
    paths = {ROOT / "Cargo.toml", ROOT / "Cargo.lock", Path(__file__)}
    for tree in ("src", "tests"):
        paths.update(p for p in (ROOT / tree).rglob("*")
                     if p.is_file() and p.suffix != ".md"
                     and "__pycache__" not in p.parts)
    paths.update(ROOT / "Specs" / name for name in MODELS)
    return paths


def copy_sut(destination):
    """Copy the same package and observers, retaining its external client pin."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for tree in ("src", "tests", "native/bap"):
        shutil.copytree(ROOT / tree, destination / tree)
    shutil.copy2(ROOT / "Cargo.lock", destination / "Cargo.lock")
    (destination / "Specs").mkdir(exist_ok=True)
    for name in MODELS:
        shutil.copy2(ROOT / "Specs" / name, destination / "Specs" / name)
    manifest = (ROOT / "Cargo.toml").read_text()
    old = 'path = "../MirrorRust"'
    assert manifest.count(old) == 1, "external MirrorRust dependency must stay explicit"
    manifest = manifest.replace(old, f'path = "{ROOT.parent / "MirrorRust"}"')
    (destination / "Cargo.toml").write_text(manifest)
    return destination / "Cargo.toml"
