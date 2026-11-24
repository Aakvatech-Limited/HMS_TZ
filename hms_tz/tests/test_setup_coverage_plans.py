import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.csvutils import to_csv

from hms_tz.api.setup_records import (
	get_company_records,
	get_screen_fields,
	import_company_records,
	save_company_record,
)
from hms_tz.hms_tz.doctype.setup_status.setup_status import get_setup_status
from hms_tz.tests.test_standard_records import create_for

SCREEN = "coverage_plans"
COMPANY = "_Test Company"
PLAN = "_Test Setup Plan"
JUBILEE = "Jubilee Insurance - _TC"
OTHER_INSURER = "Jubilee Insurance - _TC1"
STEP = "Healthcare Insurance Coverage Plan"


class TestSetupCoveragePlans(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Healthcare Insurance Coverage Plan", {"coverage_plan_name": ["like", f"{PLAN}%"]})
		frappe.delete_doc_if_exists("Setup Status", COMPANY)
		frappe.delete_doc_if_exists("HMS TZ Setting", COMPANY)
		frappe.db.set_single_value(
			"Healthcare Settings", {"collect_registration_fee": 0, "enable_free_follow_ups": 0}
		)
		frappe.get_doc({"doctype": "HMS TZ Setting", "company": COMPANY, "facility_code": "TEST"}).insert()
		create_for(COMPANY)
		create_for("_Test Company 1")
		self.labels = {field["fieldname"]: field["label"] for field in get_screen_fields(SCREEN)["fields"]}
		get_company_records(SCREEN, COMPANY)

	def save(self, values, name=None):
		return save_company_record(SCREEN, COMPANY, frappe.as_json(values), name=name)

	def plan_values(self, name=PLAN, **values):
		return {"coverage_plan_name": name, "insurance_company": JUBILEE, "is_active": 1, **values}

	def upload(self, *rows):
		header = [self.labels[fieldname] for fieldname in ("coverage_plan_name", "insurance_company")]
		content = to_csv([header, *[list(row) for row in rows]])
		file = frappe.get_doc(
			{"doctype": "File", "file_name": "plans.csv", "content": content, "is_private": 1}
		)
		return file.insert().file_url

	def test_plan_fields_need_a_name_and_an_insurer_of_the_company(self):
		screen = get_screen_fields(SCREEN)
		fields = {field["fieldname"]: field for field in screen["fields"]}
		self.assertEqual((screen["label"], screen["plural_label"]), ("coverage plan", "coverage plans"))
		self.assertEqual(fields["coverage_plan_name"]["set_only_once"], 1)
		self.assertEqual(fields["insurance_company"]["reqd"], 1)
		self.assertIn("eval: doc.company", fields["insurance_company"]["link_filters"])
		self.assertIn("selling", fields["price_list"]["link_filters"])
		for fieldname in ("secondary_price_list", "nhif_scheme_id", "has_followup_charges", "is_active"):
			self.assertIn(fieldname, fields)
		self.assertNotIn("company", fields)

	def test_a_new_plan_gets_the_company_and_ticks_the_step(self):
		name = self.save(self.plan_values())
		plan = frappe.get_doc("Healthcare Insurance Coverage Plan", name)
		self.assertEqual((plan.name, plan.company, plan.insurance_company), (PLAN, COMPANY, JUBILEE))
		self.assertIsNone(plan.price_list)
		self.assertTrue(get_setup_status(COMPANY).get_step(STEP).completed)

	def test_changing_a_plan_keeps_its_name(self):
		name = self.save(self.plan_values())
		self.save(self.plan_values(name=f"{PLAN} Renamed", is_active=0, has_followup_charges=1), name=name)
		plan = frappe.get_doc("Healthcare Insurance Coverage Plan", name)
		self.assertEqual((plan.coverage_plan_name, plan.is_active, plan.has_followup_charges), (PLAN, 0, 1))

	def test_a_plan_needs_an_insurer_of_the_company(self):
		with self.assertRaisesRegex(frappe.ValidationError, self.labels["insurance_company"]):
			self.save(self.plan_values(insurance_company=None))
		with self.assertRaisesRegex(frappe.ValidationError, "is not one of the insurance companies of"):
			self.save(self.plan_values(insurance_company=OTHER_INSURER))

	def test_another_company_plan_is_not_changed(self):
		other = frappe.db.get_value("Healthcare Insurance Coverage Plan", {"company": "_Test Company 1"})
		with self.assertRaisesRegex(frappe.ValidationError, "is not one of the coverage plans of"):
			self.save(self.plan_values(), name=other)

	def test_plans_stay_locked_until_settings_are_complete(self):
		frappe.db.set_value("HMS TZ Setting", COMPANY, "enable_nhif_api", 1)
		self.assertFalse(get_company_records(SCREEN, COMPANY)["settings_complete"])
		with self.assertRaises(frappe.ValidationError):
			self.save(self.plan_values())

	def test_import_adds_plans_reports_bad_rows_and_changes_them_again(self):
		rows = [(f"{PLAN} A", JUBILEE), (f"{PLAN} B", OTHER_INSURER)]
		result = import_company_records(SCREEN, COMPANY, self.upload(*rows))
		self.assertEqual(result["added"], 1)
		self.assertEqual([error["row"] for error in result["errors"]], [3])
		self.assertIn(OTHER_INSURER, result["errors"][0]["message"])
		result = import_company_records(SCREEN, COMPANY, self.upload(rows[0]))
		self.assertEqual((result["added"], result["changed"], result["errors"]), (0, 1, []))
