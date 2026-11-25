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

SCREEN = "procedure_templates"
DOCTYPE = "Clinical Procedure Template"
NAMES = ["Test Setup Wound Dressing", "Test Setup Appendicectomy", "Test Setup Imported Suturing"]
POINT_OF_CARE = "_Test Setup Procedure Point"


class TestSetupProcedureTemplates(FrappeTestCase):
	def setUp(self):
		delete_templates(DOCTYPE, NAMES, NAMES)
		prepare_company()
		if not frappe.db.exists("Healthcare Points of Care", POINT_OF_CARE):
			frappe.get_doc(
				{"doctype": "Healthcare Points of Care", "point_of_care_name": POINT_OF_CARE}
			).insert()
		self.theatre = get_service_unit(COMPANY, "_Test Setup Theatre")
		self.foreign_theatre = get_service_unit(OTHER_COMPANY, "_Test Setup Theatre")

	def values(self, index=0, **values):
		return {
			"template": NAMES[index],
			"item_code": NAMES[index],
			"item_group": "_Test Item Group",
			"points_of_care": POINT_OF_CARE,
			"description": NAMES[index],
			"service_unit": self.theatre,
			**values,
		}

	def save(self, values, name=None):
		return save_company_record(SCREEN, COMPANY, frappe.as_json(values), name=name)

	def get_names(self, **list_filters):
		result = get_company_records(SCREEN, COMPANY, frappe.as_json(list_filters))
		return [record.name for record in result["records"] if record.name in NAMES]

	def test_fields_hold_the_company_row_and_fix_the_template_name(self):
		fields = {field["fieldname"]: field for field in get_screen_fields(SCREEN)["fields"]}
		self.assertEqual(fields["template"]["set_only_once"], 1)
		self.assertEqual((fields["points_of_care"]["reqd"], fields["service_unit"]["reqd"]), (1, 1))
		for fieldname in ("medical_department", "is_inpatient", "rate", "is_not_available"):
			self.assertIn(fieldname, fields)
		self.assertNotIn("items", fields)

	def test_a_new_template_gets_its_item_the_company_row_and_ticks_the_step(self):
		name = self.save(self.values())
		template = frappe.get_doc(DOCTYPE, name)
		self.assertEqual((name, template.item), (NAMES[0], NAMES[0]))
		self.assertEqual(
			[(row.company, row.service_unit) for row in template.company_options], [(COMPANY, self.theatre)]
		)
		self.assertTrue(get_setup_status(COMPANY).get_step(DOCTYPE).completed)

	def test_a_billable_template_needs_a_rate_and_a_unit_of_the_company(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Rate"):
			self.save(self.values(is_billable=1, rate=None))
		with self.assertRaisesRegex(frappe.ValidationError, "is not one of the service units of"):
			self.save(self.values(service_unit=self.foreign_theatre))

	def test_changing_a_template_keeps_its_name(self):
		name = self.save(self.values())
		self.save(self.values(template="Test Setup Renamed", is_inpatient=1), name=name)
		template = frappe.get_doc(DOCTYPE, name)
		self.assertEqual((template.template, template.is_inpatient), (NAMES[0], 1))

	def test_list_filters_by_inpatient_and_part_of_the_name(self):
		self.save(self.values())
		self.save(self.values(1, is_inpatient=1))
		self.assertEqual(self.get_names(is_inpatient=1), [NAMES[1]])
		self.assertEqual(self.get_names(template="wound"), [NAMES[0]])

	def test_import_adds_and_changes_templates_by_name(self):
		self.save(self.values())
		header = get_template_rows(SCREEN)[0]
		rows = []
		for index, extra in ((0, {"description": "Changed"}), (2, {})):
			values = self.values(index, **extra)
			row = [""] * len(header)
			for label, fieldname in (
				("Template Name", "template"),
				("Item Code", "item_code"),
				("Item Group", "item_group"),
				("Points of Care", "points_of_care"),
				("Description", "description"),
				("Default Service Unit", "service_unit"),
			):
				row[column(header, label)] = values[fieldname]
			rows.append(row)
		result = import_company_records(SCREEN, COMPANY, upload_csv([header, *rows], "procedures.csv"))
		self.assertEqual((result["added"], result["changed"], result["errors"]), (1, 1, []))
		self.assertEqual(frappe.db.get_value(DOCTYPE, NAMES[0], "description"), "Changed")
		self.assertEqual(frappe.db.get_value(DOCTYPE, NAMES[2], "item"), NAMES[2])
