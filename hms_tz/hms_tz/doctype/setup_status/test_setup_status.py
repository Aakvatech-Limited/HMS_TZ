# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.api.setup import get_company_setup, get_setting_fields
from hms_tz.hms_tz.doctype.setup_status.setup_status import SETUP_STEPS, complete_setup_step

SETTING = "_Test Setup Status Company"


class TestSetupStatus(FrappeTestCase):
	def setUp(self):
		frappe.delete_doc_if_exists("Setup Status", SETTING)
		frappe.delete_doc_if_exists("HMS TZ Setting", SETTING)
		frappe.get_doc({"doctype": "HMS TZ Setting", "company": SETTING, "facility_code": "TEST"}).insert(
			ignore_links=True
		)

	def get_status(self):
		return frappe.get_doc("Setup Status", SETTING)

	def is_completed(self, document_type):
		return self.get_status().get_step(document_type).completed

	def test_new_setting_ticks_only_the_settings_step(self):
		completed = [row.document_type for row in self.get_status().steps if row.completed]
		self.assertEqual(completed, ["HMS TZ Setting"])

	def test_status_lists_every_setup_doctype(self):
		self.assertEqual([row.document_type for row in self.get_status().steps], list(SETUP_STEPS))

	def test_one_status_per_setting(self):
		with self.assertRaises(frappe.DuplicateEntryError):
			frappe.get_doc({"doctype": "Setup Status", "hms_tz_setting": SETTING}).insert()

	def test_record_of_the_company_ticks_its_step(self):
		mode_of_payment = frappe.get_doc(
			{"doctype": "Mode of Payment", "mode_of_payment": "_Test Setup Status Mode", "type": "Cash"}
		)
		mode_of_payment.append("accounts", {"company": SETTING})
		mode_of_payment.flags.ignore_validate = True
		mode_of_payment.insert(ignore_links=True)
		self.get_status().mark_steps_with_records()
		self.assertTrue(self.is_completed("Mode of Payment"))
		self.assertFalse(self.is_completed("Healthcare Insurance Company"))

	def test_company_root_group_does_not_count_as_a_room(self):
		frappe.get_doc(
			{
				"doctype": "Healthcare Service Unit",
				"name": "_Test Setup Status Root",
				"healthcare_service_unit_name": "_Test Setup Status Root",
				"company": SETTING,
				"is_group": 1,
			}
		).db_insert()
		self.get_status().mark_steps_with_records()
		self.assertFalse(self.is_completed("Healthcare Service Unit"))

	def test_any_record_ticks_a_step_without_company_link(self):
		if not frappe.db.exists("Medical Department", "_Test Setup Status Department"):
			frappe.get_doc(
				{"doctype": "Medical Department", "department": "_Test Setup Status Department"}
			).insert()
		self.get_status().mark_steps_with_records()
		self.assertTrue(self.is_completed("Medical Department"))

	def test_unknown_step_fails(self):
		with self.assertRaises(frappe.ValidationError):
			complete_setup_step(SETTING, "ToDo")

	def test_company_without_setting_has_no_steps(self):
		self.assertEqual(get_company_setup("_Test Company Without Setting"), {"setting": None, "steps": []})

	def test_company_setup_returns_steps_of_its_setting(self):
		setup = get_company_setup(SETTING)
		self.assertEqual(setup["setting"], SETTING)
		self.assertEqual([step["document_type"] for step in setup["steps"]], list(SETUP_STEPS))

	def test_setting_fields_follow_the_doctype_layout(self):
		fields = {field["fieldname"]: field for field in get_setting_fields()}
		self.assertEqual(next(iter(fields)), "company")
		self.assertEqual(fields["nhif_tab"]["fieldtype"], "Tab Break")
		self.assertIn("eval: doc.company", fields["opd_cash_pharmacy"]["link_filters"])
