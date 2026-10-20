"""Keep one-off generators out of the core ETL package."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class Layout(unittest.TestCase):
    def test_no_act_generators_in_etl(self):
        offenders = sorted(p.name for p in (ROOT / "etl").glob("*.py")
                           if p.name.startswith(("gen_", "clone_", "vary_")))
        self.assertEqual(offenders, [])

    def test_generators_have_main_guard(self):
        missing = []
        local = ROOT / "act_tools" / "generators"
        if not local.is_dir():
            self.skipTest("act_tools is local-only (generated act workspace)")
        for path in local.glob("*.py"):
            if path.name == "__init__.py":
                continue
            text = path.read_text(encoding="utf-8")
            if 'if __name__ == "__main__":' not in text:
                missing.append(path.name)
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
