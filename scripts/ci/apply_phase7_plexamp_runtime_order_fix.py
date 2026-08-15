from __future__ import annotations

from pathlib import Path


installer = Path("scripts/install-plexamp-runtime.sh")
source = installer.read_text(encoding="utf-8")

old = '''cleanup_downloads() { rm -rf -- "$DOWNLOAD_DIR"; }
trap cleanup_downloads EXIT
'''
new = '''cleanup_downloads() { rm -rf -- "$DOWNLOAD_DIR"; }

cleanup_stage_parents() {
    local previous
    if [[ -n "${NODE_STAGE_PARENT:-}" && -d "$NODE_STAGE_PARENT" ]]; then
        previous="${NODE_PREVIOUS:-}"
        if [[ -z "$previous" || ! -e "$previous" ]]; then
            if [[ "$ROOT" == / ]]; then
                sudo -- rm -rf -- "$NODE_STAGE_PARENT" >/dev/null 2>&1 || true
            else
                rm -rf -- "$NODE_STAGE_PARENT" >/dev/null 2>&1 || true
            fi
        fi
    fi
    if [[ -n "${PLEXAMP_STAGE_PARENT:-}" && -d "$PLEXAMP_STAGE_PARENT" ]]; then
        previous="${PLEXAMP_PREVIOUS:-}"
        if [[ -z "$previous" || ! -e "$previous" ]]; then
            rm -rf -- "$PLEXAMP_STAGE_PARENT" >/dev/null 2>&1 || true
        fi
    fi
}

cleanup_pretransaction() {
    cleanup_stage_parents
    cleanup_downloads
}
trap cleanup_pretransaction EXIT
'''
assert source.count(old) == 1, "download cleanup anchor changed"
source = source.replace(old, new)

old = '''if [[ "$ROOT" == / ]] && command -v systemd-analyze >/dev/null 2>&1; then
    systemd-analyze verify "$UNIT_CANDIDATE" >/dev/null
fi

# The unit uses exact-file transaction primitives. Runtime directories use a
'''
new = '''# The unit uses exact-file transaction primitives. Runtime directories use a
'''
assert source.count(old) == 1, "early systemd verify anchor changed"
source = source.replace(old, new)

old = '''cleanup_transaction() { rm -rf -- "$TRANSACTION_PARENT"; }
trap 'cleanup_transaction; cleanup_downloads' EXIT
'''
new = '''cleanup_transaction() { rm -rf -- "$TRANSACTION_PARENT"; }
trap 'cleanup_transaction; cleanup_stage_parents; cleanup_downloads' EXIT
'''
assert source.count(old) == 1, "transaction cleanup anchor changed"
source = source.replace(old, new)

old = '''acp_install_file "$UNIT_CANDIDATE" "$UNIT_TARGET" 0644 || fail_after_mutation 'Could not install plexamp.service.'

[[ -x "$NODE_TARGET_PATH/bin/node" ]] || fail_after_mutation 'Activated Node runtime is incomplete.'
[[ "$($NODE_TARGET_PATH/bin/node --version 2>/dev/null || true)" == "v$ACP_NODE_VERSION" ]] || fail_after_mutation 'Activated Node runtime version mismatch.'
manifest_matches "$NODE_MANIFEST" node "$ACP_NODE_VERSION" "$EXPECTED_NODE_SHA" || fail_after_mutation 'Activated Node runtime manifest mismatch.'
[[ -f "$PLEXAMP_TARGET_PATH/js/index.js" ]] || fail_after_mutation 'Activated Plexamp runtime is incomplete.'
manifest_matches "$PLEXAMP_MANIFEST" plexamp "$ACP_PLEXAMP_VERSION" "$EXPECTED_PLEXAMP_SHA" || fail_after_mutation 'Activated Plexamp runtime manifest mismatch.'

if [[ "$ROOT" != / && "${ACP_PLEXAMP_TEST_FAIL_AFTER_SWAP:-0}" == 1 ]]; then
'''
new = '''[[ -x "$NODE_TARGET_PATH/bin/node" ]] || fail_after_mutation 'Activated Node runtime is incomplete.'
[[ "$($NODE_TARGET_PATH/bin/node --version 2>/dev/null || true)" == "v$ACP_NODE_VERSION" ]] || fail_after_mutation 'Activated Node runtime version mismatch.'
manifest_matches "$NODE_MANIFEST" node "$ACP_NODE_VERSION" "$EXPECTED_NODE_SHA" || fail_after_mutation 'Activated Node runtime manifest mismatch.'
[[ -f "$PLEXAMP_TARGET_PATH/js/index.js" ]] || fail_after_mutation 'Activated Plexamp runtime is incomplete.'
manifest_matches "$PLEXAMP_MANIFEST" plexamp "$ACP_PLEXAMP_VERSION" "$EXPECTED_PLEXAMP_SHA" || fail_after_mutation 'Activated Plexamp runtime manifest mismatch.'

# systemd-analyze resolves ExecStart while verifying a unit. On a genuinely
# fresh Pi the pinned Node path does not exist until the runtime candidate has
# been promoted. Keep verification fail-closed, but perform it here inside the
# runtime transaction so the exact rendered paths exist and any failure can
# restore the captured runtime/service pre-state.
if [[ "$ROOT" == / ]] && command -v systemd-analyze >/dev/null 2>&1; then
    systemd-analyze verify "$UNIT_CANDIDATE" >/dev/null || \
        fail_after_mutation 'Rendered plexamp.service failed systemd verification after runtime activation.'
fi

acp_install_file "$UNIT_CANDIDATE" "$UNIT_TARGET" 0644 || fail_after_mutation 'Could not install plexamp.service.'

if [[ "$ROOT" != / && "${ACP_PLEXAMP_TEST_FAIL_AFTER_SWAP:-0}" == 1 ]]; then
'''
assert source.count(old) == 1, "runtime/unit activation anchor changed"
source = source.replace(old, new)
installer.write_text(source, encoding="utf-8")


tests = Path("tests/test_plexamp_runtime_installer.py")
test_source = tests.read_text(encoding="utf-8")

old = '''            self.assertIn(
                "ExecStart=/opt/a-clockwork-plex/node-v20.20.2-linux-arm64/bin/node /home/clockuser/plexamp/js/index.js",
                unit_text,
            )

    def test_claimed_rerun_is_idempotent_and_does_not_need_archives_again(self) -> None:
'''
new = '''            self.assertIn(
                "ExecStart=/opt/a-clockwork-plex/node-v20.20.2-linux-arm64/bin/node /home/clockuser/plexamp/js/index.js",
                unit_text,
            )
            self.assertEqual(list((root / "opt/a-clockwork-plex").glob(".acp-node-stage.*")), [])
            self.assertEqual(list((root / "home/clockuser").glob(".acp-plexamp-stage.*")), [])

    def test_claimed_rerun_is_idempotent_and_does_not_need_archives_again(self) -> None:
'''
assert test_source.count(old) == 1, "fresh install cleanup test anchor changed"
test_source = test_source.replace(old, new)

old = '''            self.assertFalse((old_node / "bin/node").exists())
            self.assertFalse((old_plex / "js/index.js").exists())

    def test_digest_mismatch_fails_before_runtime_or_unit_mutation(self) -> None:
'''
new = '''            self.assertFalse((old_node / "bin/node").exists())
            self.assertFalse((old_plex / "js/index.js").exists())
            self.assertEqual(list((root / "opt/a-clockwork-plex").glob(".acp-node-stage.*")), [])
            self.assertEqual(list((root / "home/clockuser").glob(".acp-plexamp-stage.*")), [])

    def test_digest_mismatch_fails_before_runtime_or_unit_mutation(self) -> None:
'''
assert test_source.count(old) == 1, "rollback cleanup test anchor changed"
test_source = test_source.replace(old, new)

marker = '''    def test_production_test_digest_overrides_are_explicitly_forbidden(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("ACP_PLEXAMP_TEST_* digest overrides are forbidden on the production root", source)
'''
addition = '''    def test_systemd_verify_runs_only_after_activated_runtime_checks(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        verify_at = source.index('systemd-analyze verify "$UNIT_CANDIDATE"')
        node_at = source.index("Activated Node runtime is incomplete.")
        plexamp_at = source.index("Activated Plexamp runtime is incomplete.")
        unit_install_at = source.index('acp_install_file "$UNIT_CANDIDATE" "$UNIT_TARGET"')

        self.assertGreater(verify_at, node_at)
        self.assertGreater(verify_at, plexamp_at)
        self.assertLess(verify_at, unit_install_at)
        self.assertIn(
            "Rendered plexamp.service failed systemd verification after runtime activation.",
            source,
        )

    def test_runtime_staging_cleanup_preserves_rollback_payloads(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("cleanup_stage_parents()", source)
        self.assertIn('previous="${NODE_PREVIOUS:-}"', source)
        self.assertIn('previous="${PLEXAMP_PREVIOUS:-}"', source)
        self.assertIn('[[ -z "$previous" || ! -e "$previous" ]]', source)
        self.assertIn("cleanup_transaction; cleanup_stage_parents; cleanup_downloads", source)

''' + marker
assert test_source.count(marker) == 1, "static regression anchor changed"
test_source = test_source.replace(marker, addition)
tests.write_text(test_source, encoding="utf-8")
