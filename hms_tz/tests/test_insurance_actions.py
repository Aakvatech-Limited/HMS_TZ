from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.api.setup_records import get_company_records, run_screen_action
from hms_tz.hms_tz.doctype.setup_action_run.setup_action_run import run_action_job
from hms_tz.hms_tz.setup_screens.insurance_company import INSURANCE_ACTIONS

SCREEN = "insurance_companies"
COMPANY = "_Test Company"
FORM_SCRIPT = "nhif/api/insurance_company.js"
RUN_MODULE = "hms_tz.hms_tz.doctype.setup_action_run.setup_action_run"


def set_connections(nhif, jubilee):
	frappe.db.set_value("HMS TZ Setting", COMPANY, {"enable_nhif_api": nhif, "enable_jubilee_api": jubilee})


class TestInsuranceActions(FrappeTestCase):
	def setUp(self):
		frappe.delete_doc_if_exists("Setup Status", COMPANY)
		frappe.delete_doc_if_exists("HMS TZ Setting", COMPANY)
		frappe.db.set_single_value(
			"Healthcare Settings", {"collect_registration_fee": 0, "enable_free_follow_ups": 0}
		)
		frappe.get_doc({"doctype": "HMS TZ Setting", "company": COMPANY, "facility_code": "TEST"}).insert()
		commit = patch.object(frappe.db, "commit")
		commit.start()
		self.addCleanup(commit.stop)

	def group_labels(self):
		return [group["label"] for group in get_company_records(SCREEN, COMPANY)["action_groups"]]

	def test_each_connection_switch_shows_or_hides_its_dropdown(self):
		set_connections(0, 0)
		self.assertEqual(self.group_labels(), [])
		set_connections(1, 0)
		self.assertEqual(self.group_labels(), ["NHIF actions"])
		set_connections(0, 1)
		self.assertEqual(self.group_labels(), ["Jubilee actions"])
		set_connections(1, 1)
		self.assertEqual(self.group_labels(), ["NHIF actions", "Jubilee actions"])

	def test_a_dropdown_holds_only_its_connection_actions(self):
		set_connections(0, 1)
		[group] = get_company_records(SCREEN, COMPANY)["action_groups"]
		keys = [action["key"] for action in group["actions"]]
		self.assertEqual(keys, ["jubilee_packages", "jubilee_process_records", "jubilee_procedures"])

	def test_other_screens_have_no_actions(self):
		self.assertEqual(get_company_records("doctors", COMPANY)["action_groups"], [])
		with self.assertRaisesRegex(frappe.ValidationError, "has no action"):
			run_screen_action("doctors", COMPANY, "nhif_schemes")

	def test_actions_keep_the_form_labels_and_run_existing_functions(self):
		with open(frappe.get_app_path("hms_tz", FORM_SCRIPT)) as script:
			form_script = script.read()
		for action in INSURANCE_ACTIONS:
			self.assertIn(f'"{action["label"]}"', form_script)
			self.assertTrue(callable(frappe.get_attr(action["method"])))
			self.assertTrue(frappe.db.exists("DocType", action["doctype"]), action["doctype"])

	def queue(self, key):
		with patch("frappe.enqueue") as enqueue:
			run_screen_action(SCREEN, COMPANY, key)
		return enqueue.call_args.kwargs

	def run_queued(self, key, method_effect=None):
		kwargs = self.queue(key)
		with patch(kwargs["action"]["method"], side_effect=method_effect) as method:
			run_action_job(kwargs["company"], kwargs["row"], kwargs["action"])
		return method

	def get_run(self, key):
		return get_company_records(SCREEN, COMPANY)["action_runs"][key]

	def test_an_action_is_queued_as_a_background_job(self):
		set_connections(1, 0)
		kwargs = self.queue("nhif_schemes")
		self.assertEqual(kwargs["job_id"], f"hms_tz_setup_action::{COMPANY}::nhif_schemes")
		self.assertEqual(kwargs["action"]["method"], "hms_tz.nhif.nhif_api.price_package.get_nhif_schemes")
		self.assertEqual(self.get_run("nhif_schemes").status, "Queued")

	def test_a_run_keeps_when_it_ran_and_what_it_changed(self):
		set_connections(1, 0)
		method = self.run_queued("nhif_schemes")
		method.assert_called_once_with(company=COMPANY, caller="Front End")
		run = self.get_run("nhif_schemes")
		self.assertEqual(run.status, "Done")
		self.assertTrue(run.started_on and run.finished_on)
		self.assertRegex(run.result, r"^NHIF Scheme: \d+ → \d+ \(\+0\)$")

	def test_a_failed_run_is_logged_with_the_setting(self):
		set_connections(0, 1)
		with patch.object(frappe.db, "rollback"):
			self.run_queued("jubilee_packages", frappe.ValidationError("Jubilee is down"))
		run = self.get_run("jubilee_packages")
		self.assertEqual((run.status, run.error), ("Failed", "Jubilee is down"))
		error_log = frappe.get_doc("Error Log", run.error_log)
		self.assertEqual((error_log.reference_doctype, error_log.reference_name), ("HMS TZ Setting", COMPANY))

	def test_a_running_action_is_not_queued_twice(self):
		set_connections(1, 0)
		with patch(f"{RUN_MODULE}.is_job_enqueued", return_value=True):
			with self.assertRaisesRegex(frappe.ValidationError, "already running"):
				run_screen_action(SCREEN, COMPANY, "nhif_items")

	def test_an_action_of_a_switched_off_connection_is_refused(self):
		set_connections(1, 0)
		with patch("frappe.enqueue") as enqueue:
			with self.assertRaisesRegex(frappe.ValidationError, "connection that is on"):
				run_screen_action(SCREEN, COMPANY, "jubilee_packages")
		enqueue.assert_not_called()
