from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "inspect-plexamp-home-hubs.py"


def load_probe_module():
    spec = importlib.util.spec_from_file_location("acp_test_home_hub_probe", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load Home hub probe module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PlexampHomeHubProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_probe_module()
        cls.expression = cls.module.RUNTIME_EXPRESSION

    def test_probe_is_bounded_to_discovery_hub_shape(self) -> None:
        expression = self.expression
        self.assertIn("MAX_HUBS = 24", expression)
        self.assertIn("rootStore.discovery.$mobx.values.hubs.value.$mobx.values", expression)
        self.assertIn("hub_shapes", expression)
        self.assertIn("observable_values", expression)

    def test_probe_keeps_sensitive_values_out_of_output(self) -> None:
        expression = self.expression
        self.assertIn("SENSITIVE_NAME", expression)
        self.assertIn("values_exposed: false", expression)
        self.assertIn("getters_invoked: false", expression)
        self.assertIn("Object.getOwnPropertyDescriptor", expression)
        self.assertNotIn("document.cookie", expression)
        self.assertNotIn("localStorage", expression)
        self.assertNotIn("sessionStorage", expression)

    def test_probe_does_not_accept_arbitrary_expression_input(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("--expression", source)
        self.assertNotIn("--javascript", source)
        self.assertNotIn("--script", source)
        self.assertIn('"method": "Runtime.evaluate"', source)
        self.assertIn('"expression": RUNTIME_EXPRESSION', source)

    def test_transport_is_reused_from_existing_bounded_probe(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('with_name("inspect-plexamp-home-runtime.py")', source)
        self.assertIn("transport.require_safe_port", source)
        self.assertIn("transport.plexamp_target", source)
        self.assertIn("transport.connect_devtools", source)


if __name__ == "__main__":
    unittest.main()
