from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from audio_eq_camilladsp import cli  # noqa: E402


class FakeResult:
    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode


class EqStatusPrivilegeTests(unittest.TestCase):
    def test_non_root_installed_status_uses_existing_restricted_sudo_rule(self) -> None:
        calls: list[tuple[list[str], dict[str, object]]] = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return FakeResult()

        result = cli._delegate_status_if_needed(
            'status',
            2,
            effective_uid=1000,
            module_path=cli.INSTALLED_CLI,
            runner=runner,
        )

        self.assertEqual(result, 0)
        self.assertEqual(
            calls,
            [([
                '/usr/bin/sudo',
                '-n',
                '/usr/local/bin/a-clockwork-plex-audio-eq',
                'status',
            ], {'check': False})],
        )

    def test_root_status_does_not_delegate(self) -> None:
        result = cli._delegate_status_if_needed(
            'status',
            2,
            effective_uid=0,
            module_path=cli.INSTALLED_CLI,
            runner=lambda *args, **kwargs: self.fail('root status delegated'),
        )
        self.assertIsNone(result)

    def test_source_tree_status_does_not_request_production_sudo(self) -> None:
        result = cli._delegate_status_if_needed(
            'status',
            2,
            effective_uid=1000,
            module_path=ROOT / 'scripts' / 'audio_eq_camilladsp' / 'cli.py',
            runner=lambda *args, **kwargs: self.fail('source-tree status delegated'),
        )
        self.assertIsNone(result)

    def test_mutations_never_use_status_delegation(self) -> None:
        result = cli._delegate_status_if_needed(
            'set',
            4,
            effective_uid=1000,
            module_path=cli.INSTALLED_CLI,
            runner=lambda *args, **kwargs: self.fail('mutation delegated'),
        )
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
