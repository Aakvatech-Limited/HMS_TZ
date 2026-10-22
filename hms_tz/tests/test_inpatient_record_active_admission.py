import frappe
from frappe.tests.utils import FrappeTestCase

PATIENT = "_Test AA Patient"
EXISTING_RECORD = "_Test AA Existing Record"


def insert(doctype, name, **values):
	doc = frappe.new_doc(doctype)
	doc.update({"name": name, **values})
	doc.db_insert()


def validate_new_admission():
	frappe.get_doc(doctype="Inpatient Record", patient=PATIENT).validate_already_scheduled_or_admitted()


class TestInpatientRecordActiveAdmission(FrappeTestCase):
	def setUp(self):
		insert("Patient", PATIENT, first_name="Test", sex="Male")

	def tearDown(self):
		frappe.db.rollback()

	def test_active_admission_blocks_new_record(self):
		insert("Inpatient Record", EXISTING_RECORD, patient=PATIENT)

		for status in ("Admission Scheduled", "Admitted", "Discharge Scheduled"):
			with self.subTest(status=status):
				frappe.db.set_value("Inpatient Record", EXISTING_RECORD, "status", status)

				with self.assertRaisesRegex(frappe.ValidationError, f"Already {status}"):
					validate_new_admission()

	def test_discharged_admission_allows_new_record(self):
		insert("Inpatient Record", EXISTING_RECORD, patient=PATIENT, status="Discharged")

		validate_new_admission()
