import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.hms_tz.doctype.nhif_template_mapping.nhif_knowledge import get_knowledge
from hms_tz.hms_tz.doctype.nhif_template_mapping.nhif_template_mapping import (
	accept_proposals,
	classify_new_nhif_items,
	create_mappings,
	create_nhif_templates,
)
from hms_tz.tests.setup_template_helpers import COMPANY, delete_items, prepare_company
from hms_tz.tests.test_standard_records import FakeProgress

CUSTOMER = "_Test Customer"
VISIT_TYPE = "Normal Visit"
# NHIF items of the tests: known codes of the shipped data and made-up codes starting with T.
ITEMS = {
	"5003": ("AFB Staining", 5, 11),
	"7202": ("Physiotherapy and Rehabilitative Service", 7, 8),
	"22": ("ICU Service Charges", 2, 8),
	"163698": ("Medical Officer/Dental Surgeon follow up consultation fee", 1, 8),
	"T-CAP": ("Capitation Payment", 19, 8),
	"T-SSF": ("Super specialist follow up consultation fee", 1, 8),
	"T-BED": ("Admission Charges for Premium Wards", 2, 8),
	"T-CT": ("CT Scan Pelvis", 5, 10),
	"T-XR": ("X-Ray Left Femur AP and Lateral", 5, 11),
	"T-ODD": ("Qwerty Zxcvb Plorp", 7, 8),
}


def add_nhif_item(code, name, item_type, service_type, priced=True, active=1, **values):
	frappe.get_doc(
		{
			"doctype": "NHIF Item",
			"itemcode": code,
			"itemname": name,
			"itemtypeid": item_type,
			"servicetypeid": service_type,
			"isactive": active,
			**values,
		}
	).insert(ignore_permissions=True)
	if priced:
		frappe.get_doc(
			{"doctype": "NHIF Price Package", "company": COMPANY, "itemcode": code, "itemname": name}
		).insert(ignore_permissions=True)


def delete_nhif_test_data():
	"""Remove the test mappings, the templates and Items they made, and the NHIF test items."""
	for mapping in frappe.get_all("NHIF Template Mapping", pluck="name"):
		for record in frappe.get_doc("NHIF Template Mapping", mapping).created_records:
			if record.action == "Created":
				delete_record(record.reference_doctype, record.reference_name)
	for table in ("NHIF Template Mapping Record", "NHIF Template Mapping", "NHIF Item", "NHIF Price Package"):
		frappe.db.delete(table)
	frappe.db.delete("Item Customer Detail", {"customer_name": CUSTOMER, "parenttype": "Item"})


def delete_record(doctype, name):
	item = name if doctype == "Item" else frappe.db.get_value(doctype, name, "item")
	if doctype != "Item":
		for table in frappe.get_meta(doctype).get_table_fields():
			frappe.db.delete(table.options, {"parenttype": doctype, "parent": name})
		frappe.db.delete(doctype, {"name": name})
	delete_items([item])


def prepare_nhif_company():
	prepare_company()
	frappe.db.set_value("HMS TZ Setting", COMPANY, "nhif_customer_name", CUSTOMER)
	frappe.db.set_value(
		"Appointment Type", VISIT_TYPE, {"gp_followup_item": None, "super_specialist_followup_item": None}
	)


def get_mapping(code):
	return frappe.get_doc("NHIF Template Mapping", code)


def get_codes(item):
	return frappe.get_all(
		"Item Customer Detail", filters={"parent": item, "customer_name": CUSTOMER}, pluck="ref_code"
	)


class TestNHIFTemplates(FrappeTestCase):
	def setUp(self):
		delete_nhif_test_data()
		prepare_nhif_company()
		for code, (name, item_type, service_type) in ITEMS.items():
			add_nhif_item(code, name, item_type, service_type)

	def tearDown(self):
		delete_nhif_test_data()

	def test_codes_are_classified_by_type_known_code_rule_and_name(self):
		add_nhif_item("T-OFF", "Inactive Item", 5, 11, active=0)
		add_nhif_item("T-UNPRICED", "Unpriced Item", 5, 11, priced=False)
		self.assertEqual(classify_new_nhif_items(COMPANY), len(ITEMS))
		expected = {
			"5003": ("Lab Test Template", "Proposed", "Known code"),
			"7202": ("Therapy Type", "Proposed", "Known code"),
			"22": ("Bed Item", "Proposed", "Known code"),
			"T-CAP": ("Ignore", "Ignored", "Rule"),
			"T-SSF": ("Consultation Item", "Proposed", "Rule"),
			"T-BED": ("Bed Item", "Review", "Rule"),
			"T-CT": ("Radiology Examination Template", "Proposed", "Rule"),
			"T-ODD": (None, "Review", "Name match"),
		}
		for code, (doctype, status, method) in expected.items():
			mapping = get_mapping(code)
			self.assertEqual((mapping.status, mapping.method), (status, method), code)
			if doctype:
				self.assertEqual(mapping.proposed_doctype, doctype, code)
		self.assertEqual(get_mapping("T-CT").modality_type, "CT Scan")
		xray = get_mapping("T-XR")
		self.assertEqual(
			(xray.proposed_doctype, xray.modality_type), ("Radiology Examination Template", "X-Ray")
		)
		self.assertTrue(xray.nearest_templates)
		self.assertEqual(get_mapping("7202").matched_template_name.count("\n") + 1, 75)
		self.assertFalse(frappe.db.exists("NHIF Template Mapping", "T-OFF"))
		self.assertFalse(frappe.db.exists("NHIF Template Mapping", "T-UNPRICED"))
		self.assertEqual(classify_new_nhif_items(COMPANY), 0)

	def test_known_codes_create_or_map_templates_items_and_visit_type_links(self):
		classify_new_nhif_items(COMPANY)
		self.assertEqual(create_mappings(COMPANY, ["5003", "22", "163698"]), ["Created"] * 3)
		lab = frappe.get_doc("Lab Test Template", "AFB Staining")
		self.assertEqual((lab.item, lab.lab_test_group, lab.is_billable), ("AFB Staining", "Laboratory", 0))
		self.assertEqual(get_codes(lab.item), ["5003"])
		self.assertEqual(get_codes("ICU Service Charges"), ["22"])
		self.assertEqual([row.action for row in get_mapping("22").created_records], ["Mapped"])
		followup = "Medical Officer/Dental Surgeon follow up consultation fee"
		self.assertEqual(get_codes(followup), ["163698"])
		self.assertEqual(frappe.db.get_value("Appointment Type", VISIT_TYPE, "gp_followup_item"), followup)

	def test_a_known_medication_takes_the_nhif_name_and_strength_with_the_shipped_class(self):
		add_nhif_item("11001", "Lidocaine", 3, 2, strength="2%", dosage="Gel")
		classify_new_nhif_items(COMPANY)
		create_mappings(COMPANY, ["11001"])
		medication = frappe.get_doc("Medication", "Lidocaine 2%")
		self.assertEqual(
			(medication.medication_class, medication.strength_text, medication.default_dosage_form),
			("Anesthetics", "2%", "Gel"),
		)
		self.assertEqual(get_codes(medication.item), ["11001"])

	def test_one_code_makes_every_shipped_therapy_type(self):
		classify_new_nhif_items(COMPANY)
		create_mappings(COMPANY, ["7202"])
		shipped = [row["name"] for row in get_knowledge().rows_by_code["7202"]]
		records = get_mapping("7202").created_records
		self.assertEqual(sorted(record.reference_name for record in records), sorted(shipped))
		for name in shipped[:5]:
			self.assertEqual(get_codes(frappe.db.get_value("Therapy Type", name, "item")), ["7202"])

	def test_new_codes_create_named_templates_and_consultation_links(self):
		add_nhif_item("T-MED", "Paracetamol", 3, 2, strength="500mg", dosage="Tablet")
		classify_new_nhif_items(COMPANY)
		medication = get_mapping("T-MED")
		medication.update({"proposed_doctype": "Medication", "medication_class": "Analgesics"})
		medication.save()
		create_mappings(COMPANY, ["T-MED", "T-CT", "T-SSF"])
		template = frappe.get_doc("Medication", "Paracetamol 500mg")
		self.assertEqual(
			(
				template.strength_text,
				template.default_dosage_form,
				template.stock_uom,
				template.medication_class,
			),
			("500mg", "Tablet", "Tablet", "Analgesics"),
		)
		self.assertEqual(get_codes(template.item), ["T-MED"])
		self.assertEqual(
			frappe.db.get_value("Radiology Examination Template", "CT Scan Pelvis", "modality_type"),
			"CT Scan",
		)
		item = "Super specialist follow up consultation fee"
		self.assertEqual(
			frappe.db.get_value("Appointment Type", VISIT_TYPE, "super_specialist_followup_item"), item
		)

	def test_two_codes_with_one_nhif_name_get_records_of_their_own(self):
		add_nhif_item("T-AFB", "AFB Staining", 5, 11)
		classify_new_nhif_items(COMPANY)
		frappe.db.set_value("NHIF Template Mapping", "T-AFB", "proposed_doctype", "Lab Test Template")
		self.assertEqual(create_mappings(COMPANY, ["5003", "T-AFB"]), ["Created", "Created"])
		self.assertEqual(
			get_codes(frappe.db.get_value("Lab Test Template", "AFB Staining", "item")), ["5003"]
		)
		self.assertEqual(
			get_codes(frappe.db.get_value("Lab Test Template", "AFB Staining (T-AFB)", "item")), ["T-AFB"]
		)

	def test_classifying_adds_the_masters_the_proposals_link_to(self):
		knowledge = get_knowledge()
		row = next(
			row
			for row in knowledge.rows
			if row.get("values", {}).get("medication_class")
			and knowledge.get_known_proposal(row["nhif_code"]) == "Medication"
		)
		medication_class = row["values"]["medication_class"]
		frappe.db.delete("Medication Class", {"name": medication_class})
		add_nhif_item(row["nhif_code"], row["nhif_item_name"], row["item_type_id"], row["service_type_id"])
		classify_new_nhif_items(COMPANY)
		self.assertEqual(get_mapping(row["nhif_code"]).medication_class, medication_class)
		self.assertTrue(frappe.db.exists("Medication Class", medication_class))

	def test_a_filled_visit_type_field_is_left_as_it_is(self):
		frappe.db.set_value("Appointment Type", VISIT_TYPE, "super_specialist_followup_item", "_Test Item")
		classify_new_nhif_items(COMPANY)
		create_mappings(COMPANY, ["T-SSF"])
		self.assertEqual(
			frappe.db.get_value("Appointment Type", VISIT_TYPE, "super_specialist_followup_item"),
			"_Test Item",
		)

	def test_an_existing_template_is_mapped_and_one_with_another_code_is_left_to_it(self):
		classify_new_nhif_items(COMPANY)
		create_mappings(COMPANY, ["5003"])
		frappe.db.delete("NHIF Template Mapping", {"name": "5003"})
		classify_new_nhif_items(COMPANY)
		self.assertEqual(create_mappings(COMPANY, ["5003"]), ["Created"])
		self.assertEqual([row.action for row in get_mapping("5003").created_records], ["Mapped"])
		self.assertEqual(frappe.db.count("Lab Test Template", {"name": "AFB Staining"}), 1)
		frappe.db.set_value(
			"Item Customer Detail", {"parent": "AFB Staining", "customer_name": CUSTOMER}, "ref_code", "OTHER"
		)
		frappe.db.delete("NHIF Template Mapping", {"name": "5003"})
		classify_new_nhif_items(COMPANY)
		self.assertEqual(create_mappings(COMPANY, ["5003"]), ["Created"])
		self.assertEqual(get_codes("AFB Staining"), ["OTHER"])
		self.assertEqual(
			get_codes(frappe.db.get_value("Lab Test Template", "AFB Staining (5003)", "item")), ["5003"]
		)

	def test_a_bed_item_with_another_code_fails_alone(self):
		item = frappe.get_doc("Item", "ICU Service Charges")
		item.append("customer_items", {"customer_name": CUSTOMER, "ref_code": "OTHER"})
		item.save()
		classify_new_nhif_items(COMPANY)
		self.assertEqual(create_mappings(COMPANY, ["22", "T-CT"]), ["Failed", "Created"])
		self.assertIn("already has the NHIF code OTHER", get_mapping("22").error)

	def test_the_setup_step_needs_the_downloads_and_creates_sure_proposals_once(self):
		setting = frappe.db.get_value("HMS TZ Setting", {"company": COMPANY})
		frappe.db.set_value("HMS TZ Setting", setting, "enable_nhif_api", 0)
		self.assertEqual(create_nhif_templates(setting, FakeProgress()), "NHIF is off")
		frappe.db.set_value("HMS TZ Setting", setting, "enable_nhif_api", 1)
		frappe.db.delete("NHIF Price Package")
		with self.assertRaisesRegex(frappe.ValidationError, "NHIF price package"):
			create_nhif_templates(setting, FakeProgress())
		for code in ("5003", "T-CT", "T-BED"):
			frappe.get_doc({"doctype": "NHIF Price Package", "company": COMPANY, "itemcode": code}).insert()
		progress = FakeProgress()
		self.assertEqual(create_nhif_templates(setting, progress), "2 created, 1 review")
		self.assertEqual((progress.total, progress.added), (2, 2))
		count = frappe.db.count("Item")
		self.assertEqual(create_nhif_templates(setting, FakeProgress()), "2 created, 1 review")
		self.assertEqual(frappe.db.count("Item"), count)

	def test_accepting_proposals_confirms_and_creates_one_doctype(self):
		classify_new_nhif_items(COMPANY)
		accept_proposals(COMPANY, "Bed Item")
		self.assertEqual((get_mapping("22").status, get_mapping("T-BED").status), ("Created", "Created"))
		self.assertEqual(get_mapping("T-BED").confirmed_by, frappe.session.user)
		self.assertEqual(get_codes("Admission Charges for Premium Wards"), ["T-BED"])
		self.assertEqual(get_mapping("T-CT").status, "Proposed")
