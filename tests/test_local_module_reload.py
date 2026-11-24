"""Reload stale local helpers after a Streamlit deploy. No Sheets or email."""
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

from test_equipment_squawks import _exec_equipment_helpers


CACHE_NAME = "_cvhapp_local_module_signatures"
FAKE_MODULE = "_cvhapp_reload_test_helper"


def _clear_cache():
    sys.modules.pop(CACHE_NAME, None)


def _remove_fake(directory=None):
    sys.modules.pop(FAKE_MODULE, None)
    if directory is None:
        return
    path = Path(directory) / (FAKE_MODULE + ".py")
    path.unlink(missing_ok=True)
    cache_dir = Path(directory) / "__pycache__"
    if cache_dir.is_dir():
        for item in cache_dir.glob(FAKE_MODULE + "*"):
            item.unlink(missing_ok=True)


def _write_helper(directory, version, extra=""):
    path = Path(directory) / (FAKE_MODULE + ".py")
    body = "VERSION = %s\n" % version
    if extra:
        body += extra if extra.endswith("\n") else extra + "\n"
    path.write_text(body, encoding="utf-8")
    return path


def _bump_mtime(path):
    """Force a later mtime so filesystems with 1s resolution still see a change."""
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns + 1_000_000_000, stat.st_mtime_ns + 1_000_000_000))


def _load_fake(directory):
    if directory not in sys.path:
        sys.path.insert(0, directory)
    sys.modules.pop(FAKE_MODULE, None)
    return importlib.import_module(FAKE_MODULE)


class LocalModuleReloadTests(unittest.TestCase):
    def setUp(self):
        self.s = _exec_equipment_helpers()
        self._saved_cache = sys.modules.get(CACHE_NAME)
        _clear_cache()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.directory = self.tmpdir.name
        _remove_fake(self.directory)

    def tearDown(self):
        _remove_fake(self.directory)
        if self.directory in sys.path:
            sys.path.remove(self.directory)
        _clear_cache()
        if self._saved_cache is not None:
            sys.modules[CACHE_NAME] = self._saved_cache
        self.tmpdir.cleanup()

    def _reload(self, names=(FAKE_MODULE,)):
        return self.s["_reload_local_modules_if_changed"](names)

    def test_helper_list_covers_every_local_module_app_imports(self):
        self.assertEqual(
            self.s["_LOCAL_HELPER_MODULES"],
            (
                "timesheet_mail",
                "timesheet_company_mail",
                "timesheet_pin",
                "employee_receipts",
                "bnsf_weather",
                "bnsf_daily_report",
                "bnsf_notice",
                "driver_checklists",
            ),
        )
        import employee_receipts
        import bnsf_weather
        import bnsf_daily_report
        import bnsf_notice
        import driver_checklists
        self.assertTrue(hasattr(employee_receipts, "vendor_choice_from_text"))
        self.assertTrue(hasattr(bnsf_weather, "locate_milepost"))
        self.assertTrue(hasattr(bnsf_daily_report, "gather_daily_report"))
        self.assertTrue(hasattr(bnsf_notice, "parse_ten_day_notice"))
        self.assertTrue(hasattr(driver_checklists, "BNSF_HELI2_SPRAY_CHECKLIST"))

    def test_first_sight_records_signature_and_does_not_reload(self):
        path = _write_helper(self.directory, 1)
        module = _load_fake(self.directory)
        before = module.VERSION
        self.assertEqual(self._reload(), [])
        self.assertIs(sys.modules[FAKE_MODULE], module)
        self.assertEqual(module.VERSION, before)
        signature = self.s["_local_module_signature_cache"]()[FAKE_MODULE]
        self.assertEqual(signature[2], self.s["_local_module_hash"](path))

    def test_unchanged_file_is_not_reloaded_or_rehashed(self):
        _write_helper(self.directory, 1)
        _load_fake(self.directory)
        self.assertEqual(self._reload(), [])
        calls = []
        original = self.s["_local_module_hash"]

        def counted(target):
            calls.append(target)
            return original(target)

        self.s["_local_module_hash"] = counted
        try:
            self.assertEqual(self._reload(), [])
        finally:
            self.s["_local_module_hash"] = original
        self.assertEqual(calls, [])
        self.assertEqual(sys.modules[FAKE_MODULE].VERSION, 1)

    def test_content_change_reloads_module(self):
        path = _write_helper(self.directory, 1)
        module = _load_fake(self.directory)
        self.assertEqual(self._reload(), [])
        _write_helper(self.directory, 2, extra="NEW_ATTR = 'vendor_choice_from_text'\n")
        _bump_mtime(path)
        self.assertEqual(self._reload(), [FAKE_MODULE])
        fresh = sys.modules[FAKE_MODULE]
        self.assertEqual(fresh.VERSION, 2)
        self.assertEqual(fresh.NEW_ATTR, "vendor_choice_from_text")
        # importlib.reload updates the same module object in place.
        self.assertIs(fresh, module)

    def test_touch_without_content_change_does_not_reload(self):
        path = _write_helper(self.directory, 1)
        module = _load_fake(self.directory)
        self.assertEqual(self._reload(), [])
        _bump_mtime(path)
        self.assertEqual(self._reload(), [])
        self.assertIs(sys.modules[FAKE_MODULE], module)
        self.assertEqual(module.VERSION, 1)

    def test_signatures_survive_app_py_re_exec(self):
        path = _write_helper(self.directory, 1)
        _load_fake(self.directory)
        self.assertEqual(self._reload(), [])
        # A Streamlit rerun re-executes app.py (new locals) but keeps sys.modules.
        again = _exec_equipment_helpers()
        self.assertIs(
            again["_local_module_signature_cache"](),
            self.s["_local_module_signature_cache"](),
        )
        self.assertEqual(again["_reload_local_modules_if_changed"]((FAKE_MODULE,)), [])
        _write_helper(self.directory, 2)
        _bump_mtime(path)
        self.assertEqual(again["_reload_local_modules_if_changed"]((FAKE_MODULE,)), [FAKE_MODULE])
        self.assertEqual(sys.modules[FAKE_MODULE].VERSION, 2)

    def test_missing_attribute_after_deploy_is_restored(self):
        """The live crash: new app.py calls a helper function the stale module lacks."""
        path = _write_helper(
            self.directory,
            1,
            extra="def vendor_choice_from_text(text):\n    return text\n",
        )
        module = _load_fake(self.directory)
        self.assertEqual(self._reload(), [])
        delattr(module, "vendor_choice_from_text")
        self.assertFalse(hasattr(sys.modules[FAKE_MODULE], "vendor_choice_from_text"))
        path.write_text(
            "VERSION = 2\n"
            "def vendor_choice_from_text(text):\n"
            "    return 'Napa'\n",
            encoding="utf-8",
        )
        _bump_mtime(path)
        self.assertEqual(self._reload(), [FAKE_MODULE])
        self.assertEqual(sys.modules[FAKE_MODULE].vendor_choice_from_text("napa"), "Napa")


if __name__ == "__main__":
    unittest.main()
