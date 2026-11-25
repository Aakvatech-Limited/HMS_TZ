# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.api.setup import (
	get_company_setup,
	get_setting_fields,
	get_settings_groups,
	get_setup_navigation,
	is_rule_true,
	save_billing,
	save_setting,
)
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
		setup = get_company_setup("_Test Company Without Setting")
		self.assertEqual((setup["setting"], setup["steps"]), (None, []))
		self.assertIsNone(setup["values"]["HMS TZ Setting"])

	def test_company_setup_returns_steps_of_its_setting(self):
		setup = get_company_setup(SETTING)
		self.assertEqual(setup["setting"], SETTING)
		self.assertEqual([step["document_type"] for step in setup["steps"]], list(SETUP_STEPS))

	def test_setup_navigation_has_the_steps_and_the_nhif_codes_to_review(self):
		frappe.db.delete("NHIF Template Mapping", {"nhif_code": "T-NAV"})
		frappe.get_doc(
			{
				"doctype": "NHIF Template Mapping",
				"nhif_code": "T-NAV",
				"proposed_doctype": "Item Only",
				"status": "Review",
			}
		).insert(ignore_permissions=True)
		navigation = get_setup_navigation(SETTING)
		self.assertEqual([step["document_type"] for step in navigation["steps"]], list(SETUP_STEPS))
		self.assertEqual(navigation["settings_complete"], get_company_setup(SETTING)["settings_complete"])
		self.assertEqual(
			navigation["nhif_templates_to_review"],
			frappe.db.count("NHIF Template Mapping", {"status": "Review"}),
		)
		self.assertGreaterEqual(navigation["nhif_templates_to_review"], 1)

	def test_insurer_customers_are_not_needed_to_complete_the_settings(self):
		values = {"HMS TZ Setting": {"enable_nhif_api": 1, "enable_jubilee_api": 1}}
		fields = get_setting_fields()
		missing = [label for group in get_settings_groups(fields, values) for label in group["missing"]]
		self.assertNotIn("NHIF Customer Name", missing)
		self.assertNotIn("Jubilee Customer Name", missing)
		by_fieldname = {field["fieldname"]: field for field in fields}
		self.assertFalse(by_fieldname["nhif_customer_name"]["mandatory_depends_on"])
		self.assertFalse(by_fieldname["jubilee_customer_name"]["reqd"])

	def test_setting_fields_follow_the_doctype_layout(self):
		fields = {field["fieldname"]: field for field in get_setting_fields()}
		self.assertEqual(fields["nhif_tab"]["fieldtype"], "Tab Break")
		self.assertIn("eval: doc.company", fields["opd_cash_pharmacy"]["link_filters"])
		for left_out in ("company", "get_nhif_token", "nhif_token"):
			self.assertNotIn(left_out, fields)

	def test_billing_tab_comes_from_healthcare_settings(self):
		fields = {field["fieldname"]: field for field in get_setting_fields()}
		self.assertEqual(fields["billing_tab"]["doctype"], "Healthcare Settings")
		self.assertEqual(fields["registration_fee"]["doctype"], "Healthcare Settings")
		self.assertEqual(fields["income_account"]["options"], "Account")
		self.assertIn("eval: doc.company", fields["income_account"]["link_filters"])

	def test_billing_sets_only_the_company_account_row(self):
		other = {"company": "_Test Company 1", "account": "Sales - _TC1"}
		settings = frappe.get_single("Healthcare Settings")
		settings.set("income_account", [other])
		settings.save()
		save_billing("_Test Company", {"income_account": "Sales - _TC", "registration_fee": 500})
		settings = frappe.get_single("Healthcare Settings")
		rows = {row.company: row.account for row in settings.income_account}
		self.assertEqual(rows, {"_Test Company 1": "Sales - _TC1", "_Test Company": "Sales - _TC"})
		self.assertEqual(settings.registration_fee, 500)

	def test_save_creates_the_setting_and_ignores_fields_the_page_does_not_edit(self):
		company = "_Test Company 2"
		frappe.delete_doc_if_exists("Setup Status", company)
		frappe.delete_doc_if_exists("HMS TZ Setting", company)
		save_setting(company, {"facility_code": "0042", "nhif_token": "forged"})
		setting = frappe.get_doc("HMS TZ Setting", company)
		self.assertEqual(setting.facility_code, "0042")
		self.assertFalse(setting.nhif_token)

	def get_missing(self, setting=None, billing=None):
		values = {"HMS TZ Setting": setting or {}, "Healthcare Settings": billing or {}}
		return {
			group["label"]: group["missing"] for group in get_settings_groups(get_setting_fields(), values)
		}

	def test_details_group_lists_the_missing_facility_code(self):
		self.assertIn("Facility Code", self.get_missing()["Details"])
		self.assertNotIn("Facility Code", self.get_missing({"facility_code": "0042"})["Details"])

	def test_connection_groups_need_values_only_when_switched_on(self):
		self.assertEqual(self.get_missing()["NHIF"], [])
		self.assertEqual(self.get_missing()["Jubilee"], [])
		missing = self.get_missing({"enable_nhif_api": 1, "nhif_user": "user", "enable_jubilee_api": 1})
		self.assertIn("NHIF Client Secret", missing["NHIF"])
		self.assertNotIn("NHIF User", missing["NHIF"])
		self.assertIn("Jubilee User", missing["Jubilee"])

	def test_billing_group_needs_the_registration_item_when_the_fee_is_collected(self):
		self.assertEqual(self.get_missing()["Billing"], [])
		missing = self.get_missing(billing={"collect_registration_fee": 1, "registration_fee": 500})
		self.assertEqual(missing["Billing"], ["Registration Item"])

	def test_settings_complete_follows_the_missing_values(self):
		frappe.db.set_single_value(
			"Healthcare Settings", {"collect_registration_fee": 0, "enable_free_follow_ups": 0}
		)
		self.assertTrue(get_company_setup(SETTING)["settings_complete"])
		self.get_status().validate_settings_complete()

		frappe.db.set_value("HMS TZ Setting", SETTING, "enable_nhif_api", 1)
		setup = get_company_setup(SETTING)
		self.assertFalse(setup["settings_complete"])
		self.assertFalse(self.get_status().settings_complete)
		with self.assertRaises(frappe.ValidationError):
			self.get_status().validate_settings_complete()

	def test_desk_rules_are_read_on_the_server(self):
		self.assertTrue(is_rule_true("eval: doc.a == 1 && !doc.b", {"a": 1, "b": 0}))
		self.assertFalse(is_rule_true("eval:doc.a == 1 || doc.b != 0", {"a": 0, "b": 0}))
		self.assertTrue(is_rule_true("a", {"a": 1}))
		self.assertTrue(is_rule_true(None, {}))
