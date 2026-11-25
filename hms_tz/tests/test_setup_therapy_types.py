import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.api.setup import is_rule_true
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

SCREEN = "therapy_types"
DOCTYPE = "Therapy Type"
NAMES = ["Test Setup Knee Physiotherapy", "Test Setup Back Physiotherapy", "Test Setup Imported Therapy"]
CODES = ["_TSTHER-1", "_TSTHER-2", "_TSTHER-3"]


class TestSetupTherapyTypes(FrappeTestCase):
	def setUp(self):
		delete_templates(DOCTYPE, NAMES, CODES)
		prepare_company()
		self.room = get_service_unit(COMPANY, "_Test Setup Physiotherapy Room")
		self.foreign_room = get_service_unit(OTHER_COMPANY, "_Test Setup Physiotherapy Room")

	def values(self, index=0, **values):
		return {
			"therapy_type": NAMES[index],
			"item_code": CODES[index],
			"item_name": NAMES[index],
			"item_group": "_Test Item Group",
			"default_duration": 30,
			"service_unit": self.room,
			**values,
		}

	def save(self, values, name=None):
		return save_company_record(SCREEN, COMPANY, frappe.as_json(values), name=name)

	def get_names(self, **list_filters):
		result = get_company_records(SCREEN, COMPANY, frappe.as_json(list_filters))
		return [record.name for record in result["records"] if record.name in NAMES]

	def test_fields_hold_the_company_row_and_fix_the_names(self):
		fields = {field["fieldname"]: field for field in get_screen_fields(SCREEN)["fields"]}
		self.assertEqual(
			(fields["therapy_type"]["set_only_once"], fields["item_code"]["set_only_once"]), (1, 1)
		)
		self.assertEqual((fields["item_name"]["reqd"], fields["service_unit"]["reqd"]), (1, 1))
		for fieldname in ("default_duration", "medical_department", "rate", "is_not_available"):
			self.assertIn(fieldname, fields)
		self.assertNotIn("exercises", fields)

	def test_therapy_types_sharing_one_insurer_code_are_separate_records(self):
		knee = self.save(self.values())
		back = self.save(self.values(1))
		self.assertEqual(
			[frappe.db.get_value(DOCTYPE, name, "item") for name in (knee, back)], [CODES[0], CODES[1]]
		)
		template = frappe.get_doc(DOCTYPE, knee)
		self.assertEqual(
			[(row.company, row.service_unit) for row in template.company_options], [(COMPANY, self.room)]
		)
		self.assertTrue(get_setup_status(COMPANY).get_step(DOCTYPE).completed)

	def test_a_billable_therapy_needs_a_rate_and_a_unit_of_the_company(self):
		self.assertEqual(
			frappe.get_meta(DOCTYPE).get_field("rate").mandatory_depends_on, "eval:doc.is_billable;"
		)
		self.assertTrue(is_rule_true("eval:doc.is_billable;", {"is_billable": 1}))
		with self.assertRaisesRegex(frappe.ValidationError, "Rate"):
			self.save(self.values(is_billable=1, rate=None))
		with self.assertRaisesRegex(frappe.ValidationError, "is not one of the service units of"):
			self.save(self.values(service_unit=self.foreign_room))
		self.save(self.values(is_billable=1, rate=15000))
		self.assertEqual(frappe.db.get_value(DOCTYPE, NAMES[0], "rate"), 15000)

	def test_list_filters_by_part_of_the_name(self):
		self.save(self.values())
		self.save(self.values(1))
		self.assertEqual(self.get_names(therapy_type="back phys"), [NAMES[1]])

	def test_import_adds_and_changes_therapy_types_by_item_code(self):
		self.save(self.values())
		header = get_template_rows(SCREEN)[0]
		rows = []
		for index, extra in ((0, {"default_duration": 45}), (2, {})):
			values = self.values(index, **extra)
			row = [""] * len(header)
			for label, fieldname in (
				("Therapy Type", "therapy_type"),
				("Item Code", "item_code"),
				("Item Name", "item_name"),
				("Item Group", "item_group"),
				("Default Duration", "default_duration"),
				("Default Service Unit", "service_unit"),
			):
				row[column(header, label)] = values[fieldname]
			rows.append(row)
		result = import_company_records(SCREEN, COMPANY, upload_csv([header, *rows], "therapy_types.csv"))
		self.assertEqual((result["added"], result["changed"], result["errors"]), (1, 1, []))
		self.assertEqual(frappe.db.get_value(DOCTYPE, NAMES[0], "default_duration"), 45)
		self.assertEqual(frappe.db.get_value(DOCTYPE, NAMES[2], "item"), CODES[2])
