"""Before/after fixtures for each rule, including cases that must stay quiet."""
import os
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from weakcheck import compare_sources  # noqa: E402


def run(before, after):
    flags, cond = compare_sources(textwrap.dedent(before), textwrap.dedent(after))
    return sorted(f["type"] for f in flags), sorted(c["type"] for c in cond)


BASE = """
import pytest
import numpy as np

def test_energy():
    x = compute()
    assert x > 0
    np.testing.assert_allclose(x, 1.0, rtol=1e-6)

class TestModel:
    def test_fit(self):
        self.assertEqual(fit(), 3)
        self.assertAlmostEqual(score(), 0.5, places=7)
"""


# ---------- flagged ----------

def test_removed_test_is_flagged():
    after = BASE.replace("def test_energy():", "def helper():")
    assert run(BASE, after) == (["removed_test"], [])


def test_unconditional_pytest_skip_is_flagged():
    after = BASE.replace("def test_energy():", "@pytest.mark.skip(reason='flaky')\ndef test_energy():")
    assert run(BASE, after) == (["new_unconditional_skip"], [])


def test_unittest_skip_decorator_is_flagged():
    after = BASE.replace("    def test_fit(self):", "    @unittest.skip('later')\n    def test_fit(self):")
    assert run(BASE, after) == (["new_unconditional_skip"], [])


def test_skip_call_at_top_of_body_is_flagged():
    after = BASE.replace("    x = compute()", "    pytest.skip('broken')\n    x = compute()")
    assert run(BASE, after) == (["new_unconditional_skip"], [])


def test_skiptest_call_is_flagged():
    after = BASE.replace("        self.assertEqual(fit(), 3)", "        self.skipTest('todo')\n        self.assertEqual(fit(), 3)")
    assert run(BASE, after) == (["new_unconditional_skip"], [])


def test_xfail_without_condition_is_flagged():
    after = BASE.replace("def test_energy():", "@pytest.mark.xfail\ndef test_energy():")
    assert run(BASE, after) == (["new_unconditional_skip"], [])


def test_class_level_skip_applies_to_methods():
    after = BASE.replace("class TestModel:", "@unittest.skip('later')\nclass TestModel:")
    assert run(BASE, after) == (["new_unconditional_skip"], [])


def test_fewer_bare_assertions_is_flagged():
    after = BASE.replace("    assert x > 0\n", "")
    assert run(BASE, after) == (["fewer_assertions"], [])


def test_fewer_unittest_assertions_is_flagged():
    after = BASE.replace("        self.assertEqual(fit(), 3)\n", "        fit()\n")
    assert run(BASE, after) == (["fewer_assertions"], [])


def test_rtol_loosened_is_flagged():
    after = BASE.replace("rtol=1e-6", "rtol=1e-3")
    assert run(BASE, after) == (["tolerance_loosened"], [])


def test_places_reduced_is_flagged():
    after = BASE.replace("places=7", "places=3")
    assert run(BASE, after) == (["tolerance_loosened"], [])


# ---------- listed separately ----------

def test_skipif_is_listed_not_flagged():
    after = BASE.replace("def test_energy():", "@pytest.mark.skipif(NO_GPU, reason='gpu')\ndef test_energy():")
    assert run(BASE, after) == ([], ["new_conditional_skip"])


def test_skipunless_is_listed_not_flagged():
    after = BASE.replace("    def test_fit(self):", "    @unittest.skipUnless(HAVE_NODE, 'node')\n    def test_fit(self):")
    assert run(BASE, after) == ([], ["new_conditional_skip"])


def test_skip_inside_if_is_listed_not_flagged():
    after = BASE.replace("    x = compute()", "    if not have_data():\n        pytest.skip('no data')\n    x = compute()")
    assert run(BASE, after) == ([], ["new_conditional_skip"])


def test_xfail_with_condition_is_listed_not_flagged():
    after = BASE.replace("def test_energy():", "@pytest.mark.xfail(sys.platform == 'win32', reason='win')\ndef test_energy():")
    assert run(BASE, after) == ([], ["new_conditional_skip"])


def test_importorskip_is_listed_not_flagged():
    after = BASE.replace("    x = compute()", "    pytest.importorskip('scipy')\n    x = compute()")
    assert run(BASE, after) == ([], ["new_conditional_skip"])


# ---------- quiet ----------

def test_unchanged_is_quiet():
    assert run(BASE, BASE) == ([], [])


def test_added_test_is_quiet():
    after = BASE + "\ndef test_new():\n    assert True\n"
    assert run(BASE, after) == ([], [])


def test_more_assertions_is_quiet():
    after = BASE.replace("    assert x > 0\n", "    assert x > 0\n    assert x < 2\n")
    assert run(BASE, after) == ([], [])


def test_tightened_tolerance_is_quiet():
    after = BASE.replace("rtol=1e-6", "rtol=1e-9").replace("places=7", "places=9")
    assert run(BASE, after) == ([], [])


def test_removed_skip_is_quiet():
    before = BASE.replace("def test_energy():", "@pytest.mark.skip(reason='flaky')\ndef test_energy():")
    assert run(before, BASE) == ([], [])


def test_conditional_to_unconditional_is_flagged():
    before = BASE.replace("def test_energy():", "@pytest.mark.skipif(NO_GPU, reason='gpu')\ndef test_energy():")
    after = BASE.replace("def test_energy():", "@pytest.mark.skip(reason='gpu')\ndef test_energy():")
    assert run(before, after) == (["new_unconditional_skip"], [])


def test_new_file_is_quiet():
    flags, cond = compare_sources(None, textwrap.dedent(BASE))
    assert (flags, cond) == ([], [])


def test_deleted_file_flags_its_tests():
    flags, _ = compare_sources(textwrap.dedent(BASE), None)
    assert sorted(f["type"] for f in flags) == ["removed_test", "removed_test"]


def test_syntax_error_raises():
    import pytest
    with pytest.raises(SyntaxError):
        compare_sources("def test_x(:\n", BASE)
