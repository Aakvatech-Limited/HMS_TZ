from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from hms_tz.api import appointment as appointment_api
from hms_tz.hms_tz.doctype.patient_appointment import patient_appointment
from hms_tz.nhif.api import patient_appointment as nhif_appointment
from hms_tz.nhif.nhif_api import pre_approval

PATIENT = "_Test Cancel Patient"
APPOINTMENT = "_Test Cancel Appointment"
ENCOUNTER = "_Test Cancel PE"


def insert(doctype, name, **values):
	doc = frappe.new_doc(doctype)
	doc.update({"name": name, **values})
	doc.db_insert()


def insert_encounter(docstatus=0):
	insert(
		"Patient Encounter",
		ENCOUNTER,
		patient=PATIENT,
		appointment=APPOINTMENT,
		encounter_type="Initial",
		docstatus=docstatus,
	)


def get_appointment():
	return frappe.get_doc("Patient Appointment", APPOINTMENT)


def get_status():
	return frappe.db.get_value("Patient Appointment", APPOINTMENT, "status")


@patch.object(patient_appointment, "manage_fee_validity", new=lambda appointment: None)
class TestAppointmentCancelAfterDraftEncounter(FrappeTestCase):
	def setUp(self):
		insert("Patient", PATIENT, first_name="Test", sex="Male")
		insert(
			"Patient Appointment", APPOINTMENT, patient=PATIENT, status="Closed", appointment_date=nowdate()
		)

	def tearDown(self):
		frappe.db.rollback()

	def test_closed_appointment_with_draft_encounter_is_cancellable(self):
		insert_encounter()

		self.assertTrue(nhif_appointment.is_cancellable(get_appointment()))

	def test_closed_appointment_with_submitted_encounter_is_not_cancellable(self):
		insert_encounter(docstatus=1)

		self.assertFalse(nhif_appointment.is_cancellable(get_appointment()))

	def test_closed_appointment_without_encounter_is_not_cancellable(self):
		self.assertFalse(nhif_appointment.is_cancellable(get_appointment()))

	def test_open_appointment_is_cancellable_and_cancelled_is_not(self):
		appointment = get_appointment()
		appointment.status = "Open"
		self.assertTrue(nhif_appointment.is_cancellable(appointment))

		appointment.status = "Cancelled"
		self.assertFalse(nhif_appointment.is_cancellable(appointment))

	def test_appointment_onload_flags_cancellable(self):
		insert_encounter()

		appointment = get_appointment()
		appointment.run_method("onload")

		self.assertTrue(appointment.get_onload().is_cancellable)

	def test_update_status_cancels_closed_appointment_with_draft_encounter(self):
		insert_encounter()

		patient_appointment.update_status(APPOINTMENT, "Cancelled")

		self.assertEqual(get_status(), "Cancelled")

	def test_update_status_blocks_appointment_with_submitted_encounter(self):
		insert_encounter(docstatus=1)

		with self.assertRaisesRegex(frappe.ValidationError, "cannot be cancelled"):
			patient_appointment.update_status(APPOINTMENT, "Cancelled")
		self.assertEqual(get_status(), "Closed")

	def test_frontend_cancel_blocks_appointment_with_submitted_encounter(self):
		insert_encounter(docstatus=1)

		with self.assertRaisesRegex(frappe.ValidationError, "cannot be cancelled"):
			appointment_api.cancel_appointment(APPOINTMENT)
		self.assertEqual(get_status(), "Closed")

	def test_set_status_keeps_cancelled_appointment_for_today(self):
		appointment = get_appointment()
		appointment.status = "Cancelled"

		appointment.set_status()

		self.assertEqual(appointment.status, "Cancelled")

	def test_draft_encounter_of_cancelled_appointment_cannot_be_saved_or_submitted(self):
		insert_encounter()
		patient_appointment.update_status(APPOINTMENT, "Cancelled")
		encounter = frappe.get_doc("Patient Encounter", ENCOUNTER)

		for method in ("before_save", "before_submit"):
			with self.assertRaisesRegex(frappe.ValidationError, "contact reception"):
				encounter.run_method(method)

	def test_closed_appointment_with_only_followup_draft_is_not_cancellable(self):
		insert_encounter(docstatus=1)
		frappe.db.set_value("Patient Encounter", ENCOUNTER, "encounter_type", "Final")
		insert(
			"Patient Encounter",
			"_Test Cancel PE Ongoing",
			patient=PATIENT,
			appointment=APPOINTMENT,
			encounter_type="Ongoing",
		)

		self.assertFalse(nhif_appointment.is_cancellable(get_appointment()))

	def test_encounter_onload_flags_cancelled_appointment(self):
		insert_encounter()
		patient_appointment.update_status(APPOINTMENT, "Cancelled")

		encounter = frappe.get_doc("Patient Encounter", ENCOUNTER)
		encounter.run_method("onload")

		self.assertIn("contact reception", encounter.get_onload().cancelled_appointment_message)

	def test_preapproval_is_blocked_for_cancelled_appointment(self):
		insert_encounter()
		patient_appointment.update_status(APPOINTMENT, "Cancelled")

		with self.assertRaisesRegex(frappe.ValidationError, "contact reception"):
			pre_approval.get_service_preapproval("Patient Encounter", ENCOUNTER)

	def test_cancel_adds_comment_to_appointment_and_draft_encounter(self):
		insert_encounter()

		patient_appointment.update_status(APPOINTMENT, "Cancelled")

		for doctype, name in (("Patient Appointment", APPOINTMENT), ("Patient Encounter", ENCOUNTER)):
			comment = frappe.db.get_value(
				"Comment",
				{"reference_doctype": doctype, "reference_name": name, "comment_type": "Comment"},
				"content",
			)
			self.assertIn(APPOINTMENT, comment)

	def test_cancelled_appointment_onload_has_headline_message(self):
		insert_encounter()
		patient_appointment.update_status(APPOINTMENT, "Cancelled")

		appointment = get_appointment()
		appointment.run_method("onload")

		self.assertIn("contact reception", appointment.get_onload().cancelled_appointment_message)
