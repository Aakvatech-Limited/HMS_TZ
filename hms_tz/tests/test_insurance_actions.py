from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.api.setup_records import get_company_records, run_screen_action
from hms_tz.hms_tz.setup_screens.insurance_company import INSURANCE_ACTIONS

SCREEN = "insurance_companies"
COMPANY = "_Test Company"
FORM_SCRIPT = "nhif/api/insurance_company.js"


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

	def test_actions_call_the_insurer_form_methods(self):
		with open(frappe.get_app_path("hms_tz", FORM_SCRIPT)) as script:
			form_script = "".join(script.read().split())
		for action in INSURANCE_ACTIONS:
			self.assertIn("".join(f'"{action["label"]}"'.split()), form_script)
			self.assertIn(action["method"], form_script)
			self.assertTrue(callable(frappe.get_attr(action["method"])))

	def test_an_action_runs_with_the_company_and_the_form_arguments(self):
		set_connections(1, 0)
		with patch("hms_tz.nhif.nhif_api.price_package.get_nhif_schemes", return_value="ok") as method:
			self.assertEqual(run_screen_action(SCREEN, COMPANY, "nhif_schemes"), "ok")
		method.assert_called_once_with(company=COMPANY, caller="Front End")

	def test_an_action_of_a_switched_off_connection_is_refused(self):
		set_connections(1, 0)
		target = "hms_tz.jubilee.api.price_package.enqueue_get_jubilee_price_packages"
		with patch(target) as method:
			with self.assertRaisesRegex(frappe.ValidationError, "connection that is on"):
				run_screen_action(SCREEN, COMPANY, "jubilee_packages")
		method.assert_not_called()
