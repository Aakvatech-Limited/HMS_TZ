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

SCREEN = "medications"
DOCTYPE = "Medication"
NAMES = ["Test Setup Paracetamol 500mg", "Test Setup IV Giving Set", "Test Setup Imported Amoxicillin"]
DRUGS = "_Test Setup Analgesics"
CONSUMABLES = "_Test Setup Consumables"


class TestSetupMedications(FrappeTestCase):
	def setUp(self):
		delete_templates(DOCTYPE, NAMES, NAMES)
		prepare_company()
		for medication_class in (DRUGS, CONSUMABLES):
			if not frappe.db.exists("Medication Class", medication_class):
				frappe.get_doc({"doctype": "Medication Class", "medication_class": medication_class}).insert(
					ignore_mandatory=True
				)
		self.pharmacy = get_service_unit(COMPANY, "_Test Setup Pharmacy")
		self.foreign_pharmacy = get_service_unit(OTHER_COMPANY, "_Test Setup Pharmacy")

	def values(self, index=0, **values):
		return {
			"medication_name": NAMES[index],
			"medication_class": DRUGS,
			"item_code": NAMES[index],
			"item_group": "_Test Item Group",
			"stock_uom": "Nos",
			"description": NAMES[index],
			"service_unit": self.pharmacy,
			**values,
		}

	def save(self, values, name=None):
		return save_company_record(SCREEN, COMPANY, frappe.as_json(values), name=name)

	def get_names(self, **list_filters):
		result = get_company_records(SCREEN, COMPANY, frappe.as_json(list_filters))
		return [record.name for record in result["records"] if record.name in NAMES]

	def test_fields_hold_the_company_row_and_fix_the_name(self):
		fields = {field["fieldname"]: field for field in get_screen_fields(SCREEN)["fields"]}
		self.assertEqual(fields["medication_name"]["set_only_once"], 1)
		for fieldname in ("medication_class", "stock_uom", "description", "service_unit"):
			self.assertEqual(fields[fieldname]["reqd"], 1)
		for fieldname in ("generic_name", "strength_text", "default_dosage_form", "rate", "is_not_available"):
			self.assertIn(fieldname, fields)
		self.assertNotIn("allergy_interaction", fields)

	def test_a_new_medication_gets_its_item_the_company_row_and_ticks_the_step(self):
		name = self.save(self.values(strength_text="500mg"))
		medication = frappe.get_doc(DOCTYPE, name)
		self.assertEqual((name, medication.item, medication.strength_text), (NAMES[0], NAMES[0], "500mg"))
		self.assertEqual(
			[(row.company, row.service_unit) for row in medication.company_options],
			[(COMPANY, self.pharmacy)],
		)
		self.assertTrue(get_setup_status(COMPANY).get_step(DOCTYPE).completed)

	def test_a_billable_medication_needs_a_rate_and_a_unit_of_the_company(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Rate"):
			self.save(self.values(is_billable=1, rate=None))
		with self.assertRaisesRegex(frappe.ValidationError, "is not one of the service units of"):
			self.save(self.values(service_unit=self.foreign_pharmacy))

	def test_changing_a_medication_keeps_its_name(self):
		name = self.save(self.values())
		self.save(self.values(medication_name="Test Setup Renamed", generic_name="Paracetamol"), name=name)
		medication = frappe.get_doc(DOCTYPE, name)
		self.assertEqual((medication.medication_name, medication.generic_name), (NAMES[0], "Paracetamol"))

	def test_list_separates_consumables_by_class_and_finds_part_of_the_name(self):
		self.save(self.values())
		self.save(self.values(1, medication_class=CONSUMABLES))
		self.assertEqual(self.get_names(medication_class=CONSUMABLES), [NAMES[1]])
		self.assertEqual(self.get_names(medication_name="paracetamol"), [NAMES[0]])

	def test_import_adds_and_changes_medications_by_name(self):
		self.save(self.values())
		header = get_template_rows(SCREEN)[0]
		rows = []
		for index, extra in ((0, {"description": "Changed"}), (2, {})):
			values = self.values(index, **extra)
			row = [""] * len(header)
			for label, fieldname in (
				("Medication Name", "medication_name"),
				("Medication Class", "medication_class"),
				("Item Code", "item_code"),
				("Item Group", "item_group"),
				("Stock UOM", "stock_uom"),
				("Description", "description"),
				("Default Service Unit", "service_unit"),
			):
				row[column(header, label)] = values[fieldname]
			rows.append(row)
		result = import_company_records(SCREEN, COMPANY, upload_csv([header, *rows], "medications.csv"))
		self.assertEqual((result["added"], result["changed"], result["errors"]), (1, 1, []))
		self.assertEqual(frappe.db.get_value(DOCTYPE, NAMES[0], "description"), "Changed")
		self.assertEqual(frappe.db.get_value(DOCTYPE, NAMES[2], "item"), NAMES[2])
