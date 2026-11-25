import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.api.setup_records import (
	get_company_records,
	get_screen_fields,
	import_company_records,
	save_company_record,
)
from hms_tz.hms_tz.doctype.setup_status.setup_status import get_setup_status
from hms_tz.tests.setup_template_helpers import (
	COMPANY,
	OTHER_COMPANY,
	column,
	delete_templates,
	get_service_unit,
	get_template_rows,
	prepare_company,
	upload_csv,
)

SCREEN = "lab_templates"
DOCTYPE = "Lab Test Template"
CODES = ["_TSLAB-1", "_TSLAB-2", "_TSLAB-3"]


class TestSetupLabTemplates(FrappeTestCase):
	def setUp(self):
		delete_templates(DOCTYPE, CODES, CODES)
		prepare_company()
		self.lab = get_service_unit(COMPANY, "_Test Setup Lab")
		self.other_lab = get_service_unit(COMPANY, "_Test Setup Lab Annex")
		self.foreign_lab = get_service_unit(OTHER_COMPANY, "_Test Setup Lab")

	def values(self, code=CODES[0], **values):
		return {
			"lab_test_name": f"Test Setup Haemoglobin {code}",
			"abbr": "HB",
			"lab_test_code": code,
			"lab_test_group": "_Test Item Group",
			"department": "_Test Medical Department",
			"is_billable": 0,
			"service_unit": self.lab,
			**values,
		}

	def save(self, values, name=None):
		return save_company_record(SCREEN, COMPANY, frappe.as_json(values), name=name)

	def create_without_company_row(self, code, **values):
		"""A template made the way automatic creation makes it: no company row and missing values."""
		values = {key: value for key, value in self.values(code, **values).items() if key != "service_unit"}
		return frappe.get_doc({"doctype": DOCTYPE, **values}).insert(ignore_mandatory=True).name

	def get_records(self, **list_filters):
		result = get_company_records(SCREEN, COMPANY, frappe.as_json(list_filters))
		return {record.name: record for record in result["records"] if record.name in CODES}

	def test_fields_hold_the_company_row_and_fix_the_code(self):
		screen = get_screen_fields(SCREEN)
		fields = {field["fieldname"]: field for field in screen["fields"]}
		self.assertEqual((screen["label"], screen["plural_label"]), ("lab template", "lab templates"))
		self.assertEqual((fields["service_unit"]["reqd"], fields["service_unit"]["doctype"]), (1, DOCTYPE))
		self.assertIn("eval: doc.company", fields["service_unit"]["link_filters"])
		self.assertIn("is_not_available", fields)
		self.assertEqual(fields["lab_test_code"]["set_only_once"], 1)
		self.assertNotIn("company_options", fields)
		for fieldname in ("lab_test_template_type", "lab_test_rate", "lab_test_normal_range", "sample"):
			self.assertIn(fieldname, fields)

	def test_a_new_template_gets_its_item_the_company_row_and_ticks_the_step(self):
		name = self.save(self.values())
		template = frappe.get_doc(DOCTYPE, name)
		rows = [(row.company, row.service_unit) for row in template.company_options]
		self.assertEqual((name, template.item), (CODES[0], CODES[0]))
		self.assertEqual(rows, [(COMPANY, self.lab)])
		self.assertTrue(frappe.db.exists("Item", CODES[0]))
		self.assertTrue(get_setup_status(COMPANY).get_step(DOCTYPE).completed)

	def test_a_billable_template_needs_a_rate(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Rate"):
			self.save(self.values(is_billable=1))

	def test_the_service_unit_must_be_one_of_the_company(self):
		with self.assertRaisesRegex(frappe.ValidationError, "is not one of the service units of"):
			self.save(self.values(service_unit=self.foreign_lab))
		self.assertFalse(frappe.db.exists(DOCTYPE, CODES[0]))

	def test_list_shows_every_template_with_the_company_service_unit(self):
		self.save(self.values())
		self.create_without_company_row(CODES[1])
		records = self.get_records()
		self.assertEqual((records[CODES[0]].service_unit, records[CODES[1]].service_unit), (self.lab, None))
		self.assertEqual(list(self.get_records(lab_test_name="haemoglobin _TSLAB-2")), [CODES[1]])

	def test_completing_an_automatic_template_adds_the_company_row_and_keeps_others(self):
		name = self.create_without_company_row(CODES[1])
		template = frappe.get_doc(DOCTYPE, name)
		template.append("company_options", {"company": OTHER_COMPANY, "service_unit": self.foreign_lab})
		template.save(ignore_permissions=True)
		with self.assertRaisesRegex(frappe.ValidationError, "Service Unit"):
			self.save({**self.values(CODES[1]), "service_unit": None}, name=name)
		self.save(self.values(CODES[1], lab_test_code="_TSLAB-9", is_not_available=1), name=name)
		template = frappe.get_doc(DOCTYPE, name)
		rows = {row.company: (row.service_unit, row.is_not_available) for row in template.company_options}
		self.assertEqual(rows, {OTHER_COMPANY: (self.foreign_lab, 0), COMPANY: (self.lab, 1)})
		self.assertEqual(template.lab_test_code, CODES[1])

	def test_import_changes_ranges_and_only_the_company_row(self):
		name = self.save(self.values())
		template = frappe.get_doc(DOCTYPE, name)
		template.append("company_options", {"company": OTHER_COMPANY, "service_unit": self.foreign_lab})
		template.append("normal_test_templates", {"lab_test_event": "HB", "normal_range": "12-16"})
		template.save()
		header, *rows = [
			row
			for index, row in enumerate(get_template_rows(SCREEN))
			if index == 0 or CODES[0] in row or not row[0]
		]
		rows[0][column(header, "Normal Range (normal")] = "11-15"
		for row in rows:
			if row[column(header, "Company (")] == COMPANY:
				row[column(header, "Default Service Unit")] = self.other_lab
		result = import_company_records(SCREEN, COMPANY, upload_csv([header, *rows], "lab_templates.csv"))
		template = frappe.get_doc(DOCTYPE, name)
		units = {row.company: row.service_unit for row in template.company_options}
		self.assertEqual((result["added"], result["changed"], result["errors"]), (0, 1, []))
		self.assertEqual([row.normal_range for row in template.normal_test_templates], ["11-15"])
		self.assertEqual(units, {COMPANY: self.other_lab, OTHER_COMPANY: self.foreign_lab})

	def test_import_without_a_company_adds_the_template_for_the_screen_company(self):
		header = get_template_rows(SCREEN)[0]
		row = [""] * len(header)
		values = self.values(CODES[2], lab_test_name="Test Setup Imported")
		for label, fieldname in (
			("Test Name", "lab_test_name"),
			("Abbr", "abbr"),
			("Item Code", "lab_test_code"),
			("Item Group", "lab_test_group"),
			("Department", "department"),
			("Is Billable", "is_billable"),
			("Default Service Unit", "service_unit"),
		):
			row[column(header, label)] = values[fieldname]
		result = import_company_records(SCREEN, COMPANY, upload_csv([header, row], "lab_templates.csv"))
		self.assertEqual((result["added"], result["errors"]), (1, []))
		template = frappe.get_doc(DOCTYPE, CODES[2])
		self.assertEqual(
			[(row.company, row.service_unit) for row in template.company_options], [(COMPANY, self.lab)]
		)
