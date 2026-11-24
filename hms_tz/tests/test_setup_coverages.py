from unittest.mock import patch

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
from hms_tz.hms_tz.setup_screens.coverage import Coverage
from hms_tz.tests.test_standard_records import create_for

SCREEN = "coverages"
COMPANY = "_Test Company"
DOCTYPE = "Healthcare Service Insurance Coverage"
PLAN_DOCTYPE = "Healthcare Insurance Coverage Plan"
SERVICE = "Healthcare Service Unit Type"


class TestSetupCoverages(FrappeTestCase):
	def setUp(self):
		frappe.delete_doc_if_exists("Setup Status", COMPANY)
		frappe.delete_doc_if_exists("HMS TZ Setting", COMPANY)
		frappe.db.set_single_value(
			"Healthcare Settings", {"collect_registration_fee": 0, "enable_free_follow_ups": 0}
		)
		frappe.get_doc({"doctype": "HMS TZ Setting", "company": COMPANY, "facility_code": "TEST"}).insert()
		create_for(COMPANY)
		create_for("_Test Company 1")
		self.plan, self.other_plan = frappe.get_all(
			PLAN_DOCTYPE, filters={"company": COMPANY}, pluck="name", order_by="name", limit=2
		)
		self.foreign_plan = frappe.db.get_value(PLAN_DOCTYPE, {"company": "_Test Company 1"})
		self.templates = self.get_templates()
		frappe.db.delete(DOCTYPE, {"company": ["in", [COMPANY, "_Test Company 1"]]})
		self.labels = {field["fieldname"]: field["label"] for field in get_screen_fields(SCREEN)["fields"]}
		get_company_records(SCREEN, COMPANY)

	def get_templates(self):
		for name in ("_Test Setup Coverage Service A", "_Test Setup Coverage Service B"):
			if not frappe.db.exists(SERVICE, name):
				frappe.get_doc(
					{"doctype": SERVICE, "service_unit_type": name, "allow_appointments": 1}
				).insert(ignore_mandatory=True)
		return ["_Test Setup Coverage Service A", "_Test Setup Coverage Service B"]

	def save(self, values, name=None):
		return save_company_record(SCREEN, COMPANY, frappe.as_json(values), name=name)

	def coverage_values(self, template=None, plan=None, **values):
		return {
			"healthcare_service": SERVICE,
			"healthcare_service_template": template or self.templates[0],
			"healthcare_insurance_coverage_plan": plan or self.plan,
			"end_date": "2099-12-31",
			"is_active": 1,
			**values,
		}

	def upload(self, *rows):
		fieldnames = (
			"healthcare_service",
			"healthcare_service_template",
			"healthcare_insurance_coverage_plan",
		)
		header = [*[self.labels[fieldname] for fieldname in fieldnames], self.labels["end_date"]]
		content = to_csv([header, *[[*row, "2099-12-31"] for row in rows]])
		file = frappe.get_doc(
			{"doctype": "File", "file_name": "coverages.csv", "content": content, "is_private": 1}
		)
		return file.insert().file_url

	def test_coverage_fields_and_list_filters(self):
		screen = get_screen_fields(SCREEN)
		fields = {field["fieldname"]: field for field in screen["fields"]}
		self.assertEqual((screen["label"], screen["plural_label"]), ("coverage", "coverages"))
		for fieldname in ("healthcare_service", "healthcare_service_template", "end_date"):
			self.assertEqual(fields[fieldname]["reqd"], 1)
		self.assertIn("eval: doc.company", fields["healthcare_insurance_coverage_plan"]["link_filters"])
		self.assertEqual(fields["healthcare_service_template"]["fieldtype"], "Dynamic Link")
		self.assertNotIn("company", fields)
		filters = {field["fieldname"]: field["reqd"] for field in screen["list_filters"]}
		self.assertEqual(filters, {"healthcare_service": 0, "healthcare_insurance_coverage_plan": 0})

	def test_a_new_coverage_gets_the_company_and_ticks_the_step(self):
		name = self.save(self.coverage_values(maximum_quantity=3))
		coverage = frappe.get_doc(DOCTYPE, name)
		self.assertEqual((coverage.company, coverage.maximum_quantity), (COMPANY, 3))
		self.assertTrue(get_setup_status(COMPANY).get_step(DOCTYPE).completed)

	def test_changing_a_coverage(self):
		name = self.save(self.coverage_values())
		self.save(self.coverage_values(is_active=0, approval_mandatory_for_claim=1), name=name)
		coverage = frappe.get_doc(DOCTYPE, name)
		self.assertEqual((coverage.is_active, coverage.approval_mandatory_for_claim), (0, 1))

	def test_a_coverage_needs_a_plan_of_the_company(self):
		with self.assertRaisesRegex(frappe.ValidationError, "is not one of the coverage plans of"):
			self.save(self.coverage_values(plan=self.foreign_plan))

	def test_list_filters_by_plan_and_refuses_other_fields(self):
		self.save(self.coverage_values())
		self.save(self.coverage_values(template=self.templates[1], plan=self.other_plan))
		filters = frappe.as_json({"healthcare_insurance_coverage_plan": self.other_plan})
		records = get_company_records(SCREEN, COMPANY, filters)["records"]
		self.assertEqual([record.healthcare_service_template for record in records], [self.templates[1]])
		self.assertEqual(len(get_company_records(SCREEN, COMPANY)["records"]), 2)
		with self.assertRaisesRegex(frappe.ValidationError, "cannot filter the coverages"):
			get_company_records(SCREEN, COMPANY, frappe.as_json({"is_active": 1}))

	def test_list_shows_at_most_page_length_records(self):
		self.save(self.coverage_values())
		self.save(self.coverage_values(template=self.templates[1]))
		with patch.object(Coverage, "page_length", 1):
			result = get_company_records(SCREEN, COMPANY)
		self.assertEqual((len(result["records"]), result["has_more"]), (1, True))
		self.assertFalse(get_company_records(SCREEN, COMPANY)["has_more"])

	def test_import_adds_coverages_reports_bad_rows_and_changes_them_again(self):
		rows = [(SERVICE, self.templates[0], self.plan), (SERVICE, self.templates[1], self.foreign_plan)]
		result = import_company_records(SCREEN, COMPANY, self.upload(*rows))
		self.assertEqual(result["added"], 1)
		self.assertEqual([error["row"] for error in result["errors"]], [3])
		result = import_company_records(SCREEN, COMPANY, self.upload(rows[0]))
		self.assertEqual((result["added"], result["changed"], result["errors"]), (0, 1, []))
