import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.api.inpatient_record import on_update, update_latest_encounter_status

PATIENT = "_Test IS Patient"
INPATIENT_RECORD = "_Test IS Inpatient Record"
OLD_ENCOUNTER = "_Test IS Old Encounter"
LATEST_ENCOUNTER = "_Test IS Latest Encounter"
OLD_MODIFIED = "2026-01-05 08:00:00"


def insert(doctype, name, **values):
	doc = frappe.new_doc(doctype)
	doc.update({"name": name, **values})
	doc.db_insert()


def insert_encounter(name, creation, docstatus=1, duplicated=0):
	insert(
		"Patient Encounter",
		name,
		patient=PATIENT,
		inpatient_record=INPATIENT_RECORD,
		inpatient_status="Admission Scheduled",
		docstatus=docstatus,
		duplicated=duplicated,
		creation=creation,
		modified=OLD_MODIFIED,
	)


def get_status(encounter):
	return frappe.db.get_value("Patient Encounter", encounter, "inpatient_status")


class TestEncounterInpatientStatus(FrappeTestCase):
	def setUp(self):
		insert("Patient", PATIENT, first_name="Test", sex="Male")
		insert("Inpatient Record", INPATIENT_RECORD, patient=PATIENT, status="Admitted")
		insert_encounter(OLD_ENCOUNTER, "2026-01-05 08:00:00", duplicated=1)
		insert_encounter(LATEST_ENCOUNTER, "2026-01-06 08:00:00", docstatus=0)

	def tearDown(self):
		frappe.db.rollback()

	def test_status_change_updates_only_latest_encounter(self):
		record = frappe.get_doc("Inpatient Record", INPATIENT_RECORD)
		record._doc_before_save = frappe.copy_doc(record)
		record.status = "Discharged"

		on_update(record, "on_update")

		self.assertEqual(get_status(LATEST_ENCOUNTER), "Discharged")
		self.assertEqual(get_status(OLD_ENCOUNTER), "Admission Scheduled")
		self.assertEqual(
			str(frappe.db.get_value("Patient Encounter", LATEST_ENCOUNTER, "modified")), OLD_MODIFIED
		)

	def test_unchanged_status_leaves_encounter(self):
		record = frappe.get_doc("Inpatient Record", INPATIENT_RECORD)
		record._doc_before_save = frappe.copy_doc(record)

		on_update(record, "on_update")

		self.assertEqual(get_status(LATEST_ENCOUNTER), "Admission Scheduled")

	def test_newer_duplicated_encounter_is_skipped(self):
		insert_encounter("_Test IS Duplicated Encounter", "2026-01-07 08:00:00", duplicated=1)

		update_latest_encounter_status(INPATIENT_RECORD, "Discharge Scheduled")

		self.assertEqual(get_status(LATEST_ENCOUNTER), "Discharge Scheduled")
		self.assertEqual(get_status("_Test IS Duplicated Encounter"), "Admission Scheduled")

	def test_cancelled_encounter_is_skipped(self):
		frappe.db.set_value("Patient Encounter", LATEST_ENCOUNTER, "docstatus", 2)

		update_latest_encounter_status(INPATIENT_RECORD, "Discharge Scheduled")

		self.assertEqual(get_status(LATEST_ENCOUNTER), "Admission Scheduled")
		self.assertEqual(get_status(OLD_ENCOUNTER), "Admission Scheduled")

	def test_record_without_encounter_is_ignored(self):
		update_latest_encounter_status("_Test IS Missing Record", "Discharged")
