import frappe
from frappe.tests.utils import FrappeTestCase


def make_session(start_time, duration, patient="_Test Overlap Patient"):
	"""Unsaved session named as `insert` names it before `validate`."""
	return frappe.get_doc(
		doctype="Therapy Session",
		name=frappe.generate_hash(),
		patient=patient,
		start_date="2026-01-05",
		start_time=start_time,
		duration=duration,
	)


class TestTherapySessionOverlap(FrappeTestCase):
	def setUp(self):
		make_session("10:00:00", 30).db_insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_partial_overlap_raises_overlap_message(self):
		with self.assertRaisesRegex(frappe.ValidationError, "overlaps with"):
			make_session("10:10:00", 30).validate_duplicate()

	def test_session_containing_existing_raises(self):
		with self.assertRaises(frappe.ValidationError):
			make_session("09:50:00", 60).validate_duplicate()

	def test_back_to_back_session_is_allowed(self):
		make_session("10:30:00", 30).validate_duplicate()
		make_session("09:30:00", 30).validate_duplicate()

	def test_other_patient_is_allowed(self):
		make_session("10:10:00", 30, patient="_Test Other Patient").validate_duplicate()

	def test_session_without_start_time_is_allowed(self):
		make_session("00:00:00", 30).db_insert()

		make_session(None, 30).validate_duplicate()

	def test_overlap_past_midnight_raises(self):
		make_session("23:45:00", 10).db_insert()

		with self.assertRaises(frappe.ValidationError):
			make_session("23:30:00", 60).validate_duplicate()
