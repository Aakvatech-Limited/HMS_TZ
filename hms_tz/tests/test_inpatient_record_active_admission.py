from unittest.mock import patch

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

	def test_patient_row_is_locked_while_checking(self):
		with patch.object(frappe.db, "get_value", wraps=frappe.db.get_value) as get_value:
			validate_new_admission()

		get_value.assert_any_call("Patient", PATIENT, "inpatient_record", for_update=True)

	def test_active_admission_on_patient_blocks_new_record(self):
		insert("Inpatient Record", EXISTING_RECORD, patient=PATIENT, status="Admitted")
		frappe.db.set_value(
			"Patient", PATIENT, {"inpatient_record": EXISTING_RECORD, "inpatient_status": "Admitted"}
		)

		with self.assertRaisesRegex(frappe.ValidationError, f"Already Admitted .*{EXISTING_RECORD}"):
			validate_new_admission()

	def test_pointer_to_deleted_record_does_not_block(self):
		frappe.db.set_value(
			"Patient", PATIENT, {"inpatient_record": "_Test AA Deleted", "inpatient_status": "Admitted"}
		)

		validate_new_admission()
