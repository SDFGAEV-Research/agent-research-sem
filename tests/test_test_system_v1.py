from __future__ import annotations

import unittest

from scripts.test_system import CATALOG_PATH, ROOT, check, inventory, load_catalog


class TestSystemV1Tests(unittest.TestCase):
    def test_catalog_is_valid_and_covers_every_top_level_test_file(self) -> None:
        rows = check()
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual({row.path for row in rows}, {path.relative_to(ROOT).as_posix() for path in (ROOT / "tests").glob("test_*.py")})

    def test_hierarchy_has_explicit_release_and_live_boundaries(self) -> None:
        catalog = load_catalog(CATALOG_PATH)
        self.assertEqual(catalog["gates"]["release"]["families"][-1], "release-deployment")
        self.assertEqual(catalog["gates"]["live"]["families"], ["live-qualified"])
        self.assertEqual(catalog["families"]["live-qualified"]["level"], "L8")

    def test_inventory_rows_have_intent_and_risk(self) -> None:
        rows = inventory()
        self.assertTrue(all(row.intent and row.risk and row.gates for row in rows))
