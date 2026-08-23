#!/usr/bin/env python3
"""Verify the NFC listener's owned Python dependency graph.

The NFC virtual environment deliberately uses ``--system-site-packages`` so the
Raspberry Pi OS ``python3-lgpio`` package is visible to Blinka.  A raw
``python -m pip check`` therefore audits every Python distribution inherited
from the OS as well as the packages needed by the NFC listener.  Debian may
ship unrelated distributions whose optional/type-stub metadata is not
self-contained inside that interpreter; those host-level issues must not become
A Clockwork Plex installer failures.

This verifier still uses pip's dependency checker as the authority for broken
requirements, but only fails for a requiring distribution reachable from the
NFC listener's own requirements.  Unrelated inherited issues are reported as
informational diagnostics.  Missing or version-incompatible top-level NFC
requirements always fail closed.
"""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import re
import subprocess
import sys
from collections import deque
from pathlib import Path
from typing import Iterable, Mapping

from pip._vendor.packaging.requirements import InvalidRequirement, Requirement


_CANONICALIZE = re.compile(r"[-_.]+")
_PIP_CHECK_ERROR = re.compile(
    r"^(?P<requiring>[A-Za-z0-9_.-]+)\s+\S+\s+"
    r"(?:requires\b|has requirement\b)"
)


def canonical_name(name: str) -> str:
    """Return the normalized distribution name used for ownership matching."""

    return _CANONICALIZE.sub("-", name).lower()


def marker_applies(requirement: Requirement) -> bool:
    """Evaluate a dependency marker for the running Pi/Python environment."""

    if requirement.marker is None:
        return True
    try:
        return bool(requirement.marker.evaluate({"extra": ""}))
    except Exception:
        # Fail-safe ownership: if unusual metadata cannot be evaluated, include
        # the dependency rather than risk classifying a real NFC break as host
        # noise.
        return True


def parse_root_requirements(path: Path) -> list[Requirement]:
    roots: list[Requirement] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # The vendored listener currently has ordinary PEP 508 requirement
        # lines.  Reject pip directives here rather than silently widening the
        # verifier's contract if that file changes later.
        if line.startswith("-"):
            raise ValueError(f"unsupported requirement directive at line {lineno}: {line}")
        if " #" in line:
            line = line.split(" #", 1)[0].rstrip()
        try:
            requirement = Requirement(line)
        except InvalidRequirement as exc:
            raise ValueError(f"invalid requirement at line {lineno}: {line}") from exc
        if marker_applies(requirement):
            roots.append(requirement)
    if not roots:
        raise ValueError("NFC requirements file contains no active requirements")
    return roots


def installed_distributions() -> dict[str, metadata.Distribution]:
    result: dict[str, metadata.Distribution] = {}
    for distribution in metadata.distributions():
        name = distribution.metadata.get("Name")
        if name:
            result[canonical_name(name)] = distribution
    return result


def validate_roots(
    roots: Iterable[Requirement],
    distributions: Mapping[str, metadata.Distribution],
) -> list[str]:
    errors: list[str] = []
    for requirement in roots:
        name = canonical_name(requirement.name)
        distribution = distributions.get(name)
        if distribution is None:
            errors.append(f"{requirement.name}: top-level NFC requirement is not installed")
            continue
        if requirement.specifier and not requirement.specifier.contains(
            distribution.version,
            prereleases=True,
        ):
            errors.append(
                f"{requirement.name}: installed {distribution.version} does not satisfy "
                f"{requirement.specifier}"
            )
    return errors


def owned_dependency_closure(
    roots: Iterable[Requirement],
    distributions: Mapping[str, metadata.Distribution],
) -> set[str]:
    """Return installed/required distributions reachable from NFC roots."""

    queue: deque[str] = deque(canonical_name(requirement.name) for requirement in roots)
    owned: set[str] = set()

    while queue:
        name = queue.popleft()
        if name in owned:
            continue
        owned.add(name)
        distribution = distributions.get(name)
        if distribution is None:
            continue
        for raw_dependency in distribution.requires or ():
            try:
                dependency = Requirement(raw_dependency)
            except InvalidRequirement:
                # pip check will surface malformed owned metadata if it affects
                # dependency validation.  Conservatively leave classification
                # to the unparsed-output fail-safe below.
                continue
            if marker_applies(dependency):
                dependency_name = canonical_name(dependency.name)
                if dependency_name not in owned:
                    queue.append(dependency_name)
    return owned


def classify_pip_check_output(
    output: str,
    owned: set[str],
) -> tuple[list[str], list[str], list[str]]:
    """Split pip-check failures into owned, inherited, and unclassified lines."""

    owned_errors: list[str] = []
    inherited_errors: list[str] = []
    unclassified: list[str] = []
    for raw in output.splitlines():
        line = raw.strip()
        if not line or line == "No broken requirements found.":
            continue
        match = _PIP_CHECK_ERROR.match(line)
        if match is None:
            unclassified.append(line)
            continue
        requiring = canonical_name(match.group("requiring"))
        if requiring in owned:
            owned_errors.append(line)
        else:
            inherited_errors.append(line)
    return owned_errors, inherited_errors, unclassified


def verify(requirements_path: Path) -> int:
    try:
        roots = parse_root_requirements(requirements_path)
    except (OSError, ValueError) as exc:
        print(f"NFC dependency verification error: {exc}", file=sys.stderr)
        return 1

    distributions = installed_distributions()
    root_errors = validate_roots(roots, distributions)
    if root_errors:
        for line in root_errors:
            print(f"NFC dependency error: {line}", file=sys.stderr)
        return 1

    owned = owned_dependency_closure(roots, distributions)
    completed = subprocess.run(
        [sys.executable, "-m", "pip", "check"],
        capture_output=True,
        text=True,
        check=False,
    )
    combined = "\n".join(part for part in (completed.stdout, completed.stderr) if part)

    if completed.returncode == 0:
        print(f"NFC_DEPENDENCY_CHECK=PASS owned-distributions={len(owned)} inherited-issues=0")
        return 0

    owned_errors, inherited_errors, unclassified = classify_pip_check_output(combined, owned)

    if inherited_errors:
        print(
            "INFO: pip check reported "
            f"{len(inherited_errors)} unrelated inherited system-site issue(s); "
            "they are outside the NFC dependency graph:"
        )
        for line in inherited_errors:
            print(f"  inherited: {line}")

    if owned_errors:
        print("NFC dependency graph has broken requirements:", file=sys.stderr)
        for line in owned_errors:
            print(f"  owned: {line}", file=sys.stderr)

    if unclassified:
        print(
            "NFC dependency verification could not classify pip-check output; "
            "failing closed:",
            file=sys.stderr,
        )
        for line in unclassified:
            print(f"  {line}", file=sys.stderr)

    if owned_errors or unclassified:
        return 1

    print(
        "NFC_DEPENDENCY_CHECK=PASS "
        f"owned-distributions={len(owned)} inherited-issues={len(inherited_errors)}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scope pip dependency verification to the Plexamp NFC Listener graph."
    )
    parser.add_argument("--requirements", required=True, type=Path)
    args = parser.parse_args(argv)
    return verify(args.requirements)


if __name__ == "__main__":
    raise SystemExit(main())
