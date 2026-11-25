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

SCREEN = "radiology_templates"
DOCTYPE = "Radiology Examination Template"
NAMES = ["Test Setup Chest X-Ray", "Test Setup Abdomen USS", "Test Setup Imported X-Ray"]
CODES = ["_TSRAD-1", "_TSRAD-2", "_TSRAD-3"]
XRAY = "_Test Setup X-Ray"
ULTRASOUND = "_Test Setup Ultrasound"


class TestSetupRadiologyTemplates(FrappeTestCase):
	def setUp(self):
		delete_templates(DOCTYPE, NAMES, CODES)
		prepare_company()
		for modality in (XRAY, ULTRASOUND):
			if not frappe.db.exists("Modality Type", modality):
				frappe.get_doc({"doctype": "Modality Type", "modality_type": modality}).insert()
		self.room = get_service_unit(COMPANY, "_Test Setup X-Ray Room")
		self.foreign_room = get_service_unit(OTHER_COMPANY, "_Test Setup X-Ray Room")

	def values(self, index=0, **values):
		return {
			"procedure_name": NAMES[index],
			"abbr": f"XR{index}",
			"item_code": CODES[index],
			"item_group": "_Test Item Group",
			"description": NAMES[index],
			"medical_department": "_Test Medical Department",
			"modality_type": XRAY,
			"service_unit": self.room,
			**values,
		}

	def save(self, values, name=None):
		return save_company_record(SCREEN, COMPANY, frappe.as_json(values), name=name)

	def get_names(self, **list_filters):
		result = get_company_records(SCREEN, COMPANY, frappe.as_json(list_filters))
		return [record.name for record in result["records"] if record.name in NAMES]

	def test_fields_hold_the_company_row_and_fix_the_names(self):
		screen = get_screen_fields(SCREEN)
		fields = {field["fieldname"]: field for field in screen["fields"]}
		self.assertEqual(screen["plural_label"], "radiology templates")
		self.assertEqual(
			(fields["procedure_name"]["set_only_once"], fields["item_code"]["set_only_once"]), (1, 1)
		)
		self.assertEqual((fields["modality_type"]["reqd"], fields["service_unit"]["reqd"]), (1, 1))
		self.assertIn("is_group", fields["item_group"]["link_filters"])
		self.assertNotIn("company_options", fields)

	def test_a_new_template_gets_its_item_the_company_row_and_ticks_the_step(self):
		name = self.save(self.values())
		template = frappe.get_doc(DOCTYPE, name)
		self.assertEqual((name, template.item), (NAMES[0], CODES[0]))
		self.assertEqual(
			[(row.company, row.service_unit) for row in template.company_options], [(COMPANY, self.room)]
		)
		self.assertTrue(get_setup_status(COMPANY).get_step(DOCTYPE).completed)

	def test_a_billable_template_needs_a_rate_and_a_unit_of_the_company(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Rate"):
			self.save(self.values(is_billable=1, rate=None))
		with self.assertRaisesRegex(frappe.ValidationError, "is not one of the service units of"):
			self.save(self.values(service_unit=self.foreign_room))

	def test_list_filters_by_modality_and_part_of_the_name(self):
		self.save(self.values())
		self.save(self.values(1, modality_type=ULTRASOUND))
		self.assertEqual(self.get_names(modality_type=ULTRASOUND), [NAMES[1]])
		self.assertEqual(self.get_names(procedure_name="chest x"), [NAMES[0]])

	def test_import_adds_and_changes_templates_by_item_code(self):
		self.save(self.values())
		header = get_template_rows(SCREEN)[0]
		rows = []
		for index, unit_values in ((0, {"modality_type": ULTRASOUND}), (2, {})):
			values = self.values(index, **unit_values)
			row = [""] * len(header)
			for label, fieldname in (
				("Procedure Name", "procedure_name"),
				("Abbr", "abbr"),
				("Item Code", "item_code"),
				("Item Group", "item_group"),
				("Description", "description"),
				("Medical Department", "medical_department"),
				("Modality Type", "modality_type"),
				("Default Service Unit", "service_unit"),
			):
				row[column(header, label)] = values[fieldname]
			rows.append(row)
		result = import_company_records(SCREEN, COMPANY, upload_csv([header, *rows], "radiology.csv"))
		self.assertEqual((result["added"], result["changed"], result["errors"]), (1, 1, []))
		self.assertEqual(frappe.db.get_value(DOCTYPE, NAMES[0], "modality_type"), ULTRASOUND)
		self.assertEqual(frappe.db.get_value(DOCTYPE, NAMES[2], "item"), CODES[2])
