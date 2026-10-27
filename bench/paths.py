"""CLI-only data paths: durable primary-checkout data, never worktree output."""
from __future__ import annotations

from functools import cached_property
from pathlib import Path
import tomllib


class DataPathError(ValueError):
    """A CLI data path cannot be resolved or would write into a linked checkout."""


def _checkout(path):
    path = Path(path).resolve()
    for directory in (path, *path.parents):
        marker = directory / ".git"
        if marker.is_dir() or marker.is_file():
            return directory
    return None


def _primary(checkout):
    marker = checkout / ".git"
    if marker.is_dir():
        return checkout
    try:
        line = marker.read_text(encoding="utf-8").strip()
        if not line.startswith("gitdir: "):
            raise ValueError("missing gitdir")
        gitdir = (checkout / line.removeprefix("gitdir: ")).resolve()
        common = (gitdir / (gitdir / "commondir").read_text(encoding="utf-8").strip()).resolve()
        primary = common.parent
        backlink = (gitdir / (gitdir / "gitdir").read_text(encoding="utf-8").strip()).resolve()
        if (common.name != ".git" or not common.is_dir()
                or not (primary / ".git").is_dir()
                or (primary / ".git").resolve() != common
                or gitdir.parent != common / "worktrees" or backlink != marker.resolve()):
            raise ValueError("nonconventional worktree metadata")
        return primary
    except (OSError, ValueError) as error:
        raise DataPathError(
            f"Cannot identify the primary checkout from {marker}; expected conventional Git worktree metadata. "
            "Use an explicit absolute external data path or a conventional harness checkout."
        ) from error


def _harness(checkout):
    try:
        project = tomllib.loads((checkout / "pyproject.toml").read_text(encoding="utf-8"))
        return (project.get("project", {}).get("name") == "vrc-translator-bench"
                and (checkout / "bench" / "cli.py").is_file())
    except (OSError, ValueError):
        return False


class DataPaths:
    """Resolve CLI arguments lazily; explicit library paths are not affected.

    The loaded package's checkout wins over cwd. An installed package may use an
    identifiable harness checkout enclosing cwd, but never an arbitrary cwd/.data.
    """

    def __init__(self, *, anchor=None, cwd=None):
        self.anchor = Path(anchor) if anchor is not None else Path(__file__)
        self.cwd = Path(cwd).resolve() if cwd is not None else Path.cwd()

    @cached_property
    def primary(self):
        checkout = _checkout(self.anchor)
        if checkout is None:
            checkout = _checkout(self.cwd)
            if checkout is None or not _harness(checkout):
                raise DataPathError(
                    "Cannot identify the primary harness checkout for relative .data paths; "
                    "run from a harness checkout or supply an explicit absolute data path."
                )
        return _primary(checkout)

    def input(self, path, *, base=None):
        """Map CLI .data inputs; absolute inputs and artifact children stay intact.

        base is only for the two catalogue-selected CLI source-data fallbacks;
        ordinary library artifact-relative lookup does not use this resolver.
        """
        path = Path(path)
        if path.is_absolute():
            return path
        if path.parts and path.parts[0] == ".data":
            return (self.primary / path).resolve()
        candidate = ((Path(base) if base is not None else self.cwd) / path).resolve()
        checkout = _checkout(candidate)
        if checkout is not None and candidate.is_relative_to(checkout / ".data"):
            if _primary(checkout) == self.primary:
                return self.primary / ".data" / candidate.relative_to(checkout / ".data")
        return candidate if base is not None else path

    def output(self, path):
        """Resolve an output and reject linked destinations before any side effect."""
        path = self.input(path)
        target = (self.cwd / path).resolve()
        checkout = _checkout(target)
        if checkout is not None and (checkout / ".git").is_file():
            primary = _primary(checkout)
            suffix = target.relative_to(checkout)
            if suffix.parts and suffix.parts[0] == ".data":
                suffix = Path(*suffix.parts[1:])
            suggestion = primary / ".data" / suffix
            raise DataPathError(
                f"Refusing output inside linked checkout: {target}. Use primary data path {suggestion} instead."
            )
        return target
