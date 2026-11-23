from contextlib import ExitStack
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.api.setup import get_company_setup
from hms_tz.api.setup_run import get_setup_run
from hms_tz.hms_tz.doctype.setup_status import setup_runner
from hms_tz.hms_tz.doctype.setup_status.setup_status import complete_setup_step, get_setup_status

COMPANY = "_Test Company"
BROKEN = {"is_broken": True}


def count_three(setting, progress):
	progress.set_total(3)
	for _record in range(3):
		progress.advance()
	return "3 records"


def fail_until_fixed(setting, progress):
	if BROKEN["is_broken"]:
		frappe.throw("Payment method missing")
	return "fixed"


def run_last(setting, progress):
	return "last"


def runner_step(key, method):
	return {"key": key, "label": key.title(), "method": f"hms_tz.tests.test_setup_runner.{method}"}


STEPS = [
	runner_step("count", "count_three"),
	runner_step("flaky", "fail_until_fixed"),
	runner_step("last", "run_last"),
]


class TestSetupRunner(FrappeTestCase):
	def setUp(self):
		BROKEN["is_broken"] = True
		frappe.delete_doc_if_exists("Setup Status", COMPANY)
		frappe.delete_doc_if_exists("HMS TZ Setting", COMPANY)
		frappe.db.set_single_value(
			"Healthcare Settings", {"collect_registration_fee": 0, "enable_free_follow_ups": 0}
		)
		frappe.get_doc({"doctype": "HMS TZ Setting", "company": COMPANY, "facility_code": "TEST"}).insert()
		complete_setup_step(COMPANY, "Healthcare Service Unit")
		get_company_setup(COMPANY)
		self.patches = ExitStack()
		self.patches.enter_context(patch.object(setup_runner, "SETUP_RUNNER_STEPS", STEPS))
		self.patches.enter_context(patch.object(frappe.db, "commit"))
		self.patches.enter_context(patch.object(frappe.db, "rollback"))
		self.enqueue = self.patches.enter_context(patch("frappe.enqueue"))
		self.log_error = self.patches.enter_context(patch.object(frappe, "log_error"))
		self.addCleanup(self.patches.close)

	def get_steps(self):
		return {row.step: row for row in get_setup_status(COMPANY).run_steps}

	def test_run_records_progress_and_stops_at_the_first_failure(self):
		setup_runner.start_setup(COMPANY)
		setup_runner.run_setup(COMPANY)
		steps = self.get_steps()
		self.assertEqual((steps["count"].status, steps["count"].done, steps["count"].total), ("Done", 3, 3))
		self.assertEqual(steps["count"].result, "3 records")
		self.assertEqual((steps["flaky"].status, steps["flaky"].error), ("Failed", "Payment method missing"))
		self.assertEqual(steps["last"].status, "Waiting")
		self.assertEqual(self.log_error.call_args.kwargs["reference_name"], COMPANY)

	def test_try_again_runs_from_the_failed_step(self):
		setup_runner.start_setup(COMPANY)
		setup_runner.run_setup(COMPANY)
		BROKEN["is_broken"] = False
		setup_runner.start_setup(COMPANY, from_step="flaky")
		self.assertEqual(self.enqueue.call_args.kwargs["from_step"], "flaky")
		self.assertEqual(self.get_steps()["count"].status, "Done")
		self.assertEqual(self.get_steps()["flaky"].status, "Waiting")
		setup_runner.run_setup(COMPANY, from_step="flaky")
		self.assertEqual([row.status for row in self.get_steps().values()], ["Done", "Done", "Done"])

	def test_setup_stays_locked_without_rooms_or_complete_settings(self):
		status = get_setup_status(COMPANY)
		status.get_step("Healthcare Service Unit").completed = 0
		status.save()
		with self.assertRaises(frappe.ValidationError):
			setup_runner.start_setup(COMPANY)
		complete_setup_step(COMPANY, "Healthcare Service Unit")
		get_setup_status(COMPANY).set_settings_complete(False)
		with self.assertRaises(frappe.ValidationError):
			setup_runner.start_setup(COMPANY)
		self.enqueue.assert_not_called()

	def test_a_running_setup_is_not_started_twice(self):
		with patch.object(setup_runner, "is_setup_running", return_value=True):
			with self.assertRaises(frappe.ValidationError):
				setup_runner.start_setup(COMPANY)

	def test_run_steps_follow_the_runner_list_and_keep_results(self):
		setup_runner.start_setup(COMPANY)
		setup_runner.run_setup(COMPANY)
		with patch.object(setup_runner, "SETUP_RUNNER_STEPS", [STEPS[2], STEPS[0]]):
			setup_runner.sync_run_steps(get_setup_status(COMPANY))
		steps = get_setup_status(COMPANY).run_steps
		self.assertEqual([row.step for row in steps], ["last", "count"])
		self.assertEqual(steps[1].result, "3 records")

	def test_setup_page_gets_the_banner_and_the_steps(self):
		run = get_setup_run(COMPANY)
		self.assertTrue(run["settings_complete"] and run["has_rooms"])
		self.assertEqual([step["step"] for step in run["steps"]], ["count", "flaky", "last"])
		self.assertIn("insurers", run["standard_records"])
