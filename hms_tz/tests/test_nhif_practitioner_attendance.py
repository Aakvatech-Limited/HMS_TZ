from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.api.patient_encounter import set_practitioner_name

PRACTITIONER = frappe._dict(name="_Test Doctor", practitioner_name="Test Doctor", date_loggedin_to_nhif=None)


def get_cached_value(enable_nhif_api):
	setting = frappe._dict(enable_nhif_api=enable_nhif_api, validate_nhif_practitioner_attendance=1)
	return lambda doctype, *args, **kwargs: PRACTITIONER if doctype == "Healthcare Practitioner" else setting


class TestNHIFPractitionerAttendance(FrappeTestCase):
	def submit_nhif_encounter(self, enable_nhif_api):
		doc = frappe._dict(company="_Test Company", insurance_company="NHIF")
		target = "hms_tz.nhif.api.patient_encounter.frappe.get_cached_value"
		with patch(target, side_effect=get_cached_value(enable_nhif_api)):
			set_practitioner_name(doc, "before_submit")
		return doc

	def test_practitioner_must_log_in_to_nhif_when_nhif_is_on(self):
		with self.assertRaises(frappe.ValidationError):
			self.submit_nhif_encounter(enable_nhif_api=1)

	def test_attendance_is_not_checked_when_nhif_is_off(self):
		doc = self.submit_nhif_encounter(enable_nhif_api=0)
		self.assertEqual(doc.practitioner, "_Test Doctor")
