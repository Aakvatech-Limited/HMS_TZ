import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.csvutils import to_csv

from hms_tz.api.setup_records import (
	download_records_template,
	get_company_records,
	get_screen_fields,
	import_company_records,
	save_company_record,
)
from hms_tz.hms_tz.doctype.setup_status.setup_status import get_setup_status
from hms_tz.hms_tz.standard_records.standard_records import StandardRecords
from hms_tz.tests.test_standard_records import FakeProgress

COMPANY = "_Test Company"
ITEM = "_Test Setup Consultation"
DOCTOR = "_Test Setup Doctor"
STEP = "Healthcare Practitioner"
HEADER = [
	"National ID",
	"First Name",
	"Abbreviation",
	"TZ MCT Code",
	"Out Patient Consulting Charge Item",
	"Out Patient Consulting Charge",
]


def add_consultation_item():
	if not frappe.db.exists("Item", ITEM):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": ITEM,
				"item_group": "Services",
				"stock_uom": "Nos",
				"is_stock_item": 0,
			}
		).insert(ignore_permissions=True)


class TestSetupDoctors(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Healthcare Practitioner", {"first_name": ["like", f"{DOCTOR}%"]})
		frappe.delete_doc_if_exists("Setup Status", COMPANY)
		frappe.delete_doc_if_exists("HMS TZ Setting", COMPANY)
		frappe.db.set_single_value(
			"Healthcare Settings", {"collect_registration_fee": 0, "enable_free_follow_ups": 0}
		)
		frappe.get_doc({"doctype": "HMS TZ Setting", "company": COMPANY, "facility_code": "TEST"}).insert()
		StandardRecords(COMPANY, FakeProgress()).create("Practitioner Schedule")
		add_consultation_item()
		get_company_records("doctors", COMPANY)

	def doctor_values(self, code="MCT-1", **values):
		return {
			"national_id": f"NID-{code}",
			"first_name": f"{DOCTOR} {code}",
			"abbreviation": "TSD",
			"status": "Active",
			"tz_mct_code": code,
			"op_consulting_charge_item": ITEM,
			"op_consulting_charge": 20000,
			**values,
		}

	def doctor_codes(self):
		return {doctor.tz_mct_code for doctor in get_company_records("doctors", COMPANY)["records"]}

	def upload(self, *rows):
		content = to_csv([HEADER, *[list(row) for row in rows]])
		file = frappe.get_doc(
			{"doctype": "File", "file_name": "doctors.csv", "content": content, "is_private": 1}
		)
		return file.insert().file_url

	def test_doctor_fields_ask_for_the_fee_and_nhif_registration_number(self):
		screen = get_screen_fields("doctors")
		fields = {field["fieldname"]: field for field in screen["fields"]}
		self.assertEqual((screen["label"], screen["plural_label"]), ("doctor", "doctors"))
		self.assertTrue({"first_name", "middle_name", "last_name"} <= set(fields))
		self.assertEqual(fields["tz_mct_code"]["reqd"], 1)
		self.assertEqual(fields["op_consulting_charge"]["reqd"], 1)
		self.assertIn("is_stock_item", fields["op_consulting_charge_item"]["link_filters"])
		self.assertNotIn("hms_tz_company", fields)
		self.assertNotIn("practitioner_role", fields)

	def test_a_new_doctor_can_take_bookings_and_ticks_the_step(self):
		values = self.doctor_values(middle_name="Ally", last_name="Kiboto")
		name = save_company_record("doctors", COMPANY, frappe.as_json(values))
		doctor = frappe.get_doc("Healthcare Practitioner", name)
		self.assertEqual(
			(doctor.hms_tz_company, doctor.practitioner_role, doctor.status), (COMPANY, "Doctor", "Active")
		)
		self.assertEqual((doctor.op_consulting_charge_item, doctor.op_consulting_charge), (ITEM, 20000))
		self.assertEqual(doctor.practitioner_name, f"{DOCTOR} MCT-1 Kiboto")
		self.assertEqual(doctor.practitioner_schedules[0].schedule, "Weekdays 08:00 - 17:00")
		self.assertTrue(get_setup_status(COMPANY).get_step(STEP).completed)

	def test_a_doctor_needs_the_fee_and_nhif_registration_number(self):
		for fieldname, label in (("op_consulting_charge", "Charge"), ("tz_mct_code", "MCT Code")):
			with self.assertRaisesRegex(frappe.ValidationError, label):
				save_company_record("doctors", COMPANY, self.doctor_values(**{fieldname: None}))

	def test_changing_a_doctor_keeps_the_company_and_role(self):
		name = save_company_record("doctors", COMPANY, self.doctor_values())
		values = self.doctor_values(op_consulting_charge=25000, hms_tz_company="_Test Company 1")
		save_company_record("doctors", COMPANY, values, name=name)
		doctor = frappe.get_doc("Healthcare Practitioner", name)
		self.assertEqual((doctor.op_consulting_charge, doctor.hms_tz_company), (25000, COMPANY))

	def test_only_the_company_doctors_are_listed_and_changed(self):
		name = save_company_record("doctors", COMPANY, self.doctor_values())
		frappe.db.set_value("Healthcare Practitioner", name, "practitioner_role", "Nurse")
		self.assertNotIn("MCT-1", self.doctor_codes())
		with self.assertRaisesRegex(frappe.ValidationError, "is not one of the doctors of"):
			save_company_record("doctors", COMPANY, self.doctor_values(), name=name)

	def test_doctors_stay_locked_until_settings_are_complete(self):
		frappe.db.set_value("HMS TZ Setting", COMPANY, "enable_nhif_api", 1)
		self.assertFalse(get_company_records("doctors", COMPANY)["settings_complete"])
		with self.assertRaises(frappe.ValidationError):
			save_company_record("doctors", COMPANY, self.doctor_values())
		with self.assertRaises(frappe.ValidationError):
			import_company_records("doctors", COMPANY, self.upload())

	def test_template_holds_the_doctor_fields(self):
		save_company_record("doctors", COMPANY, self.doctor_values())
		download_records_template("doctors", COMPANY, samples="all", file_type="CSV")
		header, *rows = [line for line in frappe.response["result"].splitlines() if line]
		self.assertIn("TZ MCT Code", header)
		self.assertNotIn("Practitioner Role", header)
		self.assertTrue(any("MCT-1" in row for row in rows))

	def test_import_adds_doctors_and_reports_invalid_rows(self):
		result = import_company_records(
			"doctors",
			COMPANY,
			self.upload(
				("NID-A", f"{DOCTOR} A", "TSD", "MCT-A", ITEM, 15000),
				("NID-B", f"{DOCTOR} B", "TSD", "", ITEM, 15000),
				("NID-C", f"{DOCTOR} C", "TSD", "MCT-C", "No Such Item", 15000),
			),
		)
		self.assertEqual(result["added"], 1)
		self.assertEqual([error["row"] for error in result["errors"]], [3, 4])
		self.assertIn("No Such Item", result["errors"][1]["message"])
		codes = self.doctor_codes()
		self.assertIn("MCT-A", codes)
		self.assertNotIn("MCT-C", codes)
		self.assertTrue(get_setup_status(COMPANY).get_step(STEP).completed)

	def test_repeated_import_changes_doctors_by_nhif_registration_number(self):
		row = ("NID-A", f"{DOCTOR} A", "TSD", "MCT-A", ITEM, 15000)
		import_company_records("doctors", COMPANY, self.upload(row))
		result = import_company_records("doctors", COMPANY, self.upload((*row[:5], 18000)))
		self.assertEqual((result["added"], result["changed"], result["errors"]), (0, 1, []))
		charges = frappe.get_all(
			"Healthcare Practitioner", filters={"tz_mct_code": "MCT-A"}, pluck="op_consulting_charge"
		)
		self.assertEqual(charges, [18000])
