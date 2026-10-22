import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.patches import unique_patient_appointment_on_inpatient_record as patch

PATIENT = "_Test IR Appointment Patient"
APPOINTMENT = "_Test IR Appointment"
ENCOUNTER = "_Test IR Appointment PE"
KEPT_RECORD = "_Test IR Kept"
ORPHAN_RECORD = "_Test IR Orphan"
RECORDS = {KEPT_RECORD, ORPHAN_RECORD}


def insert(doctype, name, **values):
	doc = frappe.new_doc(doctype)
	doc.update({"name": name, **values})
	doc.db_insert()


def insert_inpatient_record(name, status="Admission Scheduled"):
	insert(
		"Inpatient Record",
		name,
		patient=PATIENT,
		status=status,
		admission_encounter=ENCOUNTER,
		patient_appointment=APPOINTMENT,
	)


def orphan_row(status="Admission Scheduled"):
	return frappe._dict(name=ORPHAN_RECORD, status=status)


def new_inpatient_record(appointment):
	return frappe.get_doc(doctype="Inpatient Record", patient=PATIENT, patient_appointment=appointment)


class TestInpatientRecordAppointment(FrappeTestCase):
	def setUp(self):
		insert("Patient", PATIENT, first_name="Test", sex="Male")
		insert("Patient Appointment", APPOINTMENT, patient=PATIENT)
		insert("Patient Encounter", ENCOUNTER, patient=PATIENT, appointment=APPOINTMENT)

	def tearDown(self):
		frappe.db.rollback()

	def test_second_record_for_appointment_is_blocked(self):
		insert_inpatient_record(KEPT_RECORD, status="Discharged")

		with self.assertRaisesRegex(frappe.ValidationError, "already has Inpatient Record"):
			new_inpatient_record(APPOINTMENT).validate_appointment_not_admitted()

	def test_first_record_for_appointment_is_allowed(self):
		new_inpatient_record(APPOINTMENT).validate_appointment_not_admitted()
		new_inpatient_record(None).validate_appointment_not_admitted()

	def test_double_submitted_record_is_orphan(self):
		self.assertTrue(patch.is_orphan(orphan_row(), KEPT_RECORD, RECORDS))

	def test_admitted_record_is_not_orphan(self):
		self.assertFalse(patch.is_orphan(orphan_row(status="Admitted"), KEPT_RECORD, RECORDS))

	def test_record_kept_by_encounter_is_not_orphan(self):
		self.assertFalse(patch.is_orphan(orphan_row(), ORPHAN_RECORD, RECORDS))
		self.assertFalse(patch.is_orphan(orphan_row(), None, RECORDS))

	def test_record_linked_from_encounter_is_not_orphan(self):
		insert("Patient Encounter", "_Test IR Ward PE", patient=PATIENT, inpatient_record=ORPHAN_RECORD)

		self.assertFalse(patch.is_orphan(orphan_row(), KEPT_RECORD, RECORDS))

	def test_record_with_occupancy_is_not_orphan(self):
		insert(
			"Inpatient Occupancy",
			"_Test IR Occupancy",
			parent=ORPHAN_RECORD,
			parenttype="Inpatient Record",
			parentfield="inpatient_occupancies",
		)

		self.assertFalse(patch.is_orphan(orphan_row(), KEPT_RECORD, RECORDS))
