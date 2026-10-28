# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.nhif_api.healthcare_practitioner import get_registered_practitioners

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
