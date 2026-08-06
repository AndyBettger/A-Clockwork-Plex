#!/usr/bin/python3
from __future__ import annotations

"""Guarded persistent Stage C EQ installation using the v17 adapter fix."""

from . import current_package_terminal_install_v16 as v16
from .current_package_terminal_install_adapter_v17 import (
    CurrentPackageTerminalInstallAdapterV17,
)


def main(argv: list[str] | None = None) -> int:
    v16.CurrentPackageTerminalInstallAdapterV16 = CurrentPackageTerminalInstallAdapterV17
    return v16.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
