"""OS-independent application paths. Windows is the acceptance platform."""

from pathlib import Path


def package_dir() -> Path:
    return Path(__file__).resolve().parent


def source_root() -> Path:
    return Path(__file__).resolve().parents[2]
