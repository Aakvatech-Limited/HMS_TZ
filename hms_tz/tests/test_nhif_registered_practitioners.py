# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.nhif_api.healthcare_practitioner import (
	get_practitioner_details,
	get_registered_practitioners,
	register_practitioner,
	terminate_practitioner,
)

MODULE = "hms_tz.nhif.nhif_api.healthcare_practitioner"


def response_for(status_code, text):
	return MagicMock(status_code=status_code, text=text, json=lambda: frappe.parse_json(text))


class TestNHIFRegisteredPractitioners(FrappeTestCase):
	def setUp(self):
		settings = MagicMock(nhifservice_url="https://nhif.test")
		settings.get_nhif_token.return_value = "token"
		self.start_patch("frappe.get_cached_doc", return_value=settings)
		self.request = self.start_patch("requests.request")
		self.add_log = self.start_patch("add_log")

	def start_patch(self, target, **kwargs):
		patcher = patch(f"{MODULE}.{target}", **kwargs)
		self.addCleanup(patcher.stop)
		return patcher.start()

	def test_returns_practitioners_and_logs_the_call(self):
		practitioners = [{"practitionerNo": "MCT-1"}]
		self.request.return_value = response_for(200, frappe.as_json(practitioners))

		result = get_registered_practitioners("Test Company")

		self.assertEqual(result, practitioners)
		self.assertEqual(self.request.call_args.args[1], "https://nhif.test/api/Practitioners")
		self.assertEqual(self.request.call_args.kwargs["headers"]["Authorization"], "Bearer token")
		self.assertEqual(self.add_log.call_args.kwargs["request_type"], "GetPractitioners")

	def test_error_response_is_logged_and_raised(self):
		self.request.return_value = response_for(403, "<html>Forbidden</html>")

		with self.assertRaises(frappe.ValidationError):
			get_registered_practitioners("Test Company")

		self.assertEqual(self.add_log.call_args.kwargs["status_code"], 403)

	def test_user_without_practitioner_read_is_refused(self):
		frappe.set_user("Guest")
		self.addCleanup(frappe.set_user, "Administrator")

		with self.assertRaises(frappe.PermissionError):
			get_registered_practitioners("Test Company")

		self.request.assert_not_called()

	def test_returns_practitioner_details_for_mct_number(self):
		details = {"registrationNo": "MCT/1", "practicingStatus": "Allowed"}
		self.request.return_value = response_for(200, frappe.as_json(details))

		result = get_practitioner_details("Test Company", "MCT/1")

		self.assertEqual(result, details)
		self.assertEqual(
			self.request.call_args.args[1], "https://nhif.test/api/Practitioners/details/MCT%2F1"
		)
		self.assertEqual(self.add_log.call_args.kwargs["request_type"], "GetPractitionerDetails")

	def test_practitioner_not_registered_at_facility_is_raised(self):
		self.request.return_value = response_for(404, "Practitioner not found")

		with self.assertRaises(frappe.ValidationError):
			get_practitioner_details("Test Company", "MCT-404")

		self.assertEqual(self.add_log.call_args.kwargs["status_code"], 404)

	def test_error_shows_nhif_message_instead_of_raw_json(self):
		body = {"status": 404, "message": "Practitioner with Registration No. 4781 is not registered"}
		self.request.return_value = response_for(404, frappe.as_json(body))

		with self.assertRaises(frappe.ValidationError) as error:
			get_practitioner_details("Test Company", "4781")

		self.assertIn(body["message"], str(error.exception))
		self.assertNotIn('"status"', str(error.exception))

	def start_update_patches(self, tz_mct_code="4540"):
		doc = MagicMock(tz_mct_code=tz_mct_code, hms_tz_company="Test Company")
		doc.name = "HLC-PRAC-0001"
		self.start_patch("frappe.get_doc", return_value=doc)
		self.start_patch("frappe.get_cached_value", return_value="FAC01")
		self.start_patch("get_fullname", return_value="Test User")
		return doc

	def test_register_posts_practitioner_for_facility(self):
		doc = self.start_update_patches()
		self.request.return_value = response_for(200, "")

		result = register_practitioner(doc.name)

		self.assertEqual(result, {})
		doc.check_permission.assert_called_once_with("write")
		self.assertEqual(self.request.call_args.args[0], "Post")
		self.assertEqual(self.request.call_args.args[1], "https://nhif.test/api/Practitioners/register")
		self.assertEqual(
			frappe.parse_json(self.request.call_args.kwargs["data"]),
			{"practitionerNo": "4540", "facilityCode": "FAC01", "createdBy": "Test User"},
		)
		self.assertEqual(self.add_log.call_args.kwargs["request_type"], "RegisterPractitioner")

	def test_register_without_mct_code_is_refused(self):
		doc = self.start_update_patches(tz_mct_code=None)

		with self.assertRaises(frappe.ValidationError):
			register_practitioner(doc.name)

		self.request.assert_not_called()

	def test_register_without_write_permission_is_refused(self):
		doc = self.start_update_patches()
		doc.check_permission.side_effect = frappe.PermissionError

		with self.assertRaises(frappe.PermissionError):
			register_practitioner(doc.name)

		self.request.assert_not_called()

	def test_terminate_posts_reasons_for_facility(self):
		doc = self.start_update_patches()
		self.request.return_value = response_for(200, frappe.as_json({"success": True}))

		terminate_practitioner(doc.name, "Left the facility")

		doc.check_permission.assert_called_once_with("write")
		self.assertEqual(self.request.call_args.args[1], "https://nhif.test/api/Practitioners/terminate")
		self.assertEqual(
			frappe.parse_json(self.request.call_args.kwargs["data"]),
			{
				"practitionerNo": "4540",
				"facilityCode": "FAC01",
				"terminatedBy": "Test User",
				"terminationReasons": "Left the facility",
			},
		)
		self.assertEqual(self.add_log.call_args.kwargs["request_type"], "TerminatePractitioner")

	def test_plain_text_success_response_is_returned_as_message(self):
		doc = self.start_update_patches()
		self.request.return_value = response_for(200, "Practitioner terminated successfully")

		result = terminate_practitioner(doc.name, "He is no longer with us")

		self.assertEqual(result, {"message": "Practitioner terminated successfully"})

	def test_terminate_without_reasons_is_refused(self):
		doc = self.start_update_patches()

		with self.assertRaises(frappe.ValidationError):
			terminate_practitioner(doc.name, "")

		self.request.assert_not_called()
