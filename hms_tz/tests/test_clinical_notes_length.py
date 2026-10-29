import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.api.patient_encounter import validate_clinical_notes_length

COMPANY = "_Test CN Company"


def make_encounter(notes, **fields):
	fields.setdefault("company", COMPANY)
	fields.setdefault("appointment", "_Test CN Appointment")
	return frappe._dict(examination_detail=notes, **fields)


class TestClinicalNotesLength(FrappeTestCase):
	def setUp(self):
		setting = frappe.new_doc("HMS TZ Setting")
		setting.update({"name": COMPANY, "company": COMPANY})
		setting.db_insert()

	def tearDown(self):
		frappe.db.rollback()
		frappe.clear_document_cache("HMS TZ Setting", COMPANY)

	def set_minimum(self, value):
		frappe.db.set_value("HMS TZ Setting", COMPANY, "minimum_clinical_notes_length", value)

	def test_new_setting_defaults_to_twenty(self):
		self.assertEqual(frappe.db.get_value("HMS TZ Setting", COMPANY, "minimum_clinical_notes_length"), 20)

	def test_dot_or_empty_notes_are_blocked(self):
		for notes in ("<p>.</p>", "", None, "<p>&nbsp; . , ; - </p>"):
			with self.subTest(notes=notes), self.assertRaises(frappe.ValidationError):
				validate_clinical_notes_length(make_encounter(notes))

	def test_html_tags_do_not_count(self):
		self.set_minimum(10)

		with self.assertRaises(frappe.ValidationError):
			validate_clinical_notes_length(make_encounter("<p><strong>Fever</strong></p>"))

	def test_notes_at_minimum_pass(self):
		self.set_minimum(10)

		validate_clinical_notes_length(make_encounter("<p>Fever, cough</p>"))

	def test_zero_disables_check(self):
		self.set_minimum(0)

		validate_clinical_notes_length(make_encounter("<p>.</p>"))

	def test_direct_practitioner_is_skipped(self):
		validate_clinical_notes_length(make_encounter("", practitioner="Direct Cash"))

	def test_package_order_encounter_is_skipped(self):
		validate_clinical_notes_length(make_encounter("<p>.</p>", healthcare_package_order="_Test CN PO"))

	def test_encounter_without_appointment_is_skipped(self):
		validate_clinical_notes_length(make_encounter("<p>.</p>", appointment=None))

	def test_company_without_setting_is_skipped(self):
		validate_clinical_notes_length(make_encounter("", company="_Test CN Other Company"))
