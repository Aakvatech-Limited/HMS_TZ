import frappe
from erpnext import get_default_company
from frappe.tests.utils import FrappeTestCase

from hms_tz.hms_tz.report.ipd_billing_report.ipd_billing_report import execute, get_no_records_message

PATIENT = "_Test IPDBR Patient"
APPOINTMENT = "_Test IPDBR Appointment"
ENCOUNTER = "_Test IPDBR Encounter"
INPATIENT_RECORD = "_Test IPDBR Inpatient Record"
SERVICE_UNIT_TYPE = "_Test IPDBR Bed Type"
SERVICE_UNIT = "_Test IPDBR Bed"
BED_AMOUNT = 30000


def insert(doctype, name, **values):
	doc = frappe.new_doc(doctype)
	doc.update({"name": name, **values})
	doc.db_insert()


def get_dates(rows):
	return [str(row["date"]) for row in rows if row.get("date") not in (None, "Total")]


class TestIPDBillingReport(FrappeTestCase):
	def setUp(self):
		self.company = get_default_company()
		insert("Patient", PATIENT, first_name="Test", sex="Male")
		insert("Patient Appointment", APPOINTMENT, patient=PATIENT)
		insert(
			"Patient Encounter",
			ENCOUNTER,
			patient=PATIENT,
			appointment=APPOINTMENT,
			inpatient_record=INPATIENT_RECORD,
			docstatus=1,
		)
		insert(
			"Inpatient Record",
			INPATIENT_RECORD,
			patient=PATIENT,
			patient_appointment=APPOINTMENT,
			admission_encounter=ENCOUNTER,
		)
		insert("Healthcare Service Unit Type", SERVICE_UNIT_TYPE, item_group="Services")
		insert("Healthcare Service Unit", SERVICE_UNIT, service_unit_type=SERVICE_UNIT_TYPE)
		insert(
			"Inpatient Occupancy",
			frappe.generate_hash(),
			parent=INPATIENT_RECORD,
			parenttype="Inpatient Record",
			parentfield="inpatient_occupancies",
			service_unit=SERVICE_UNIT,
			check_in="2026-01-05 10:00:00",
			amount=BED_AMOUNT,
			is_confirmed=1,
		)

	def tearDown(self):
		frappe.db.rollback()

	def run_report(self, summarized_view, **date_filters):
		filters = {
			"patient": PATIENT,
			"appointment_no": APPOINTMENT,
			"inpatient_record": INPATIENT_RECORD,
			"company": self.company,
			"patient_type": "In-Patient",
			"summarized_view": summarized_view,
			**date_filters,
		}
		return execute(frappe._dict(filters))

	def test_patient_without_customer_shows_zero_deposit(self):
		for summarized_view in (0, 1):
			with self.subTest(summarized_view=summarized_view):
				dashboard = {row["label"]: row["value"] for row in self.run_report(summarized_view)[4]}

				self.assertEqual(str(dashboard["Total Deposited Amount"]), "0")
				self.assertEqual(dashboard["Total Amount Used"], BED_AMOUNT)

	def test_both_views_apply_date_range_to_bed_charges(self):
		frappe.db.set_value("Inpatient Record", INPATIENT_RECORD, "admitted_datetime", "2026-01-05 09:00:00")
		frappe.db.set_value("Patient Encounter", ENCOUNTER, "encounter_date", "2026-01-05")
		insert(
			"Inpatient Occupancy",
			frappe.generate_hash(),
			parent=INPATIENT_RECORD,
			parenttype="Inpatient Record",
			parentfield="inpatient_occupancies",
			service_unit=SERVICE_UNIT,
			check_in="2026-01-07 10:00:00",
			amount=BED_AMOUNT,
			is_confirmed=1,
		)

		for summarized_view in (0, 1):
			with self.subTest(summarized_view=summarized_view):
				all_days = self.run_report(summarized_view)[1]
				one_day = self.run_report(summarized_view, from_date="2026-01-07", to_date="2026-01-07")[1]

				self.assertEqual(get_dates(all_days), ["2026-01-05", "2026-01-07"])
				self.assertEqual(get_dates(one_day), ["2026-01-07"])

	def test_no_records_message_lists_only_set_filters(self):
		message = get_no_records_message(frappe._dict(patient=PATIENT, from_date="2026-01-01"))

		self.assertIn("From Date", message)
		self.assertNotIn("To Date", message)
		self.assertNotIn("None", message)
