from contextlib import ExitStack
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.api.setup import get_setting_fields
from hms_tz.api.setup_run import get_setup_run
from hms_tz.hms_tz.doctype.setup_status import setup_runner
from hms_tz.hms_tz.doctype.setup_status.setup_status import complete_setup_step, get_setup_status

COMPANY = "_Test Company"
TEST_APP = "test_app"
HMS_TZ_STEP = {"key": "hms", "label": "Hms", "method": "hms_tz.tests.test_setup_hooks.run_hms_step"}
CLINIC_STEP = {
	"key": "clinic_rules",
	"label": "Clinic rules",
	"method": "hms_tz.tests.test_setup_hooks.run_clinic_step",
	"needs_rooms": False,
}
RUN_ORDER = []


def run_hms_step(setting, progress):
	RUN_ORDER.append("hms")
	return "hms done"


def run_clinic_step(setting, progress):
	RUN_ORDER.append("clinic_rules")
	progress.set_total(1)
	progress.advance(added=1)
	return "1 clinic rule"


class FakeHooks:
	"""Hooks of the installed apps plus test_app, which registers setup steps and setting defaults."""

	def __init__(self, steps=None, defaults=None):
		self.get_hooks = frappe.get_hooks
		self.hooks = {
			"hms_tz_setup_steps": steps if steps is not None else [CLINIC_STEP],
			"app_title": ["Test App"],
		}
		self.defaults = defaults or []

	def __call__(self, hook=None, default="_KEEP_DEFAULT_LIST", app_name=None):
		if app_name == TEST_APP:
			return self.hooks.get(hook, [])
		if hook == "hms_tz_setting_defaults" and not app_name:
			return self.defaults
		return self.get_hooks(hook, default, app_name)


class TestSetupHooks(FrappeTestCase):
	def setUp(self):
		RUN_ORDER.clear()
		frappe.delete_doc_if_exists("Setup Status", COMPANY)
		frappe.delete_doc_if_exists("HMS TZ Setting", COMPANY)
		frappe.db.set_single_value(
			"Healthcare Settings", {"collect_registration_fee": 0, "enable_free_follow_ups": 0}
		)
		frappe.get_doc({"doctype": "HMS TZ Setting", "company": COMPANY, "facility_code": "TEST"}).insert()
		complete_setup_step(COMPANY, "Healthcare Service Unit")
		get_setup_status(COMPANY).set_settings_complete(True)
		self.patches = ExitStack()
		self.addCleanup(self.patches.close)
		self.patches.enter_context(patch.object(setup_runner, "SETUP_RUNNER_STEPS", [HMS_TZ_STEP]))
		self.patches.enter_context(patch.object(frappe.db, "commit"))
		self.patches.enter_context(patch("frappe.enqueue"))
		installed = [*frappe.get_installed_apps(), TEST_APP]
		self.patches.enter_context(patch.object(frappe, "get_installed_apps", return_value=installed))

	def fake_hooks(self, **kwargs):
		self.patches.enter_context(patch.object(frappe, "get_hooks", FakeHooks(**kwargs)))

	def test_registered_step_runs_after_the_hms_tz_steps(self):
		self.fake_hooks()
		setup_runner.start_setup(COMPANY)
		setup_runner.run_setup(COMPANY)
		self.assertEqual(RUN_ORDER, ["hms", "clinic_rules"])
		rows = get_setup_status(COMPANY).run_steps
		self.assertEqual(
			[(row.step, row.app) for row in rows], [("hms", "hms_tz"), ("clinic_rules", TEST_APP)]
		)
		self.assertEqual((rows[1].status, rows[1].added, rows[1].result), ("Done", 1, "1 clinic rule"))

	def test_setup_page_shows_the_registered_step_with_its_app(self):
		self.fake_hooks()
		steps = get_setup_run(COMPANY)["steps"]
		self.assertEqual(steps[-1]["step"], "clinic_rules")
		self.assertEqual((steps[-1]["app"], steps[-1]["app_title"]), (TEST_APP, "Test App"))
		self.assertEqual(steps[0]["app"], "hms_tz")

	def test_removing_the_app_removes_its_step_row(self):
		self.fake_hooks()
		get_setup_run(COMPANY)
		self.fake_hooks(steps=[])
		self.assertEqual([step["step"] for step in get_setup_run(COMPANY)["steps"]], ["hms"])
		self.assertEqual([row.step for row in get_setup_status(COMPANY).run_steps], ["hms"])

	def test_a_step_key_registered_twice_fails_loudly(self):
		self.fake_hooks(steps=[{**CLINIC_STEP, "key": "hms"}])
		with self.assertRaises(frappe.ValidationError):
			setup_runner.get_runner_steps()

	def test_registered_defaults_prefill_a_new_setting(self):
		self.fake_hooks(defaults=[{"fieldname": "enable_nhif_api", "value": 1}])
		fields = {field["fieldname"]: field for field in get_setting_fields()}
		self.assertEqual(fields["enable_nhif_api"]["default"], 1)

	def test_a_default_for_an_unknown_field_fails_loudly(self):
		self.fake_hooks(defaults=[{"fieldname": "no_such_field", "value": 1}])
		with self.assertRaises(frappe.ValidationError):
			get_setting_fields()
