from unittest.mock import MagicMock, patch

import frappe
import requests
from frappe.tests.utils import FrappeTestCase

from hms_tz.hms_tz.doctype.hms_tz_setting import hms_tz_setting
from hms_tz.tests.utils import insert

COMPANY = "_Test Jubilee Token Company"
REJECTED = {"Status": "ERROR", "Description": "Invalid Username, Password or ProviderID"}
ACCEPTED = {
	"Status": "OK",
	"Description": {"access_token": "_test_token", "issued_at": 0, "expires_in": 3600},
}


def jubilee_response(status_code, data):
	response = MagicMock(status_code=status_code, ok=status_code < 400)
	response.json.return_value = data
	return response


@patch.object(hms_tz_setting, "sleep", new=lambda seconds: None)
@patch.object(hms_tz_setting, "add_jubilee_log", new=lambda **kwargs: None)
@patch.object(hms_tz_setting.HMSTZSetting, "get_password", new=lambda self, fieldname: "_test_password")
class TestJubileeToken(FrappeTestCase):
	def setUp(self):
		insert("Company", COMPANY, company_name=COMPANY, abbr="_TJT", default_currency="TZS")
		insert(
			"HMS TZ Setting",
			COMPANY,
			company=COMPANY,
			enable_jubilee_api=1,
			jubilee_url="https://jubilee.invalid",
			jubilee_user="_test_user",
			jubilee_provider_id="_test_provider",
		)
		self.setting = frappe.get_doc("HMS TZ Setting", COMPANY)

	def tearDown(self):
		frappe.db.rollback()

	def test_rejected_login_shows_jubilee_message_without_retrying(self):
		with patch.object(requests, "post", return_value=jubilee_response(401, REJECTED)) as post:
			with self.assertRaisesRegex(
				frappe.ValidationError,
				"Status Code: 401 — Jubilee Response: Invalid Username, Password or ProviderID",
			):
				self.setting.get_jubilee_token()

		self.assertEqual(post.call_count, 1)

	def test_non_json_rejection_shows_the_response_text(self):
		response = jubilee_response(502, None)
		response.json.side_effect = ValueError
		response.text = "Bad Gateway"

		with patch.object(requests, "post", return_value=response):
			with self.assertRaisesRegex(
				frappe.ValidationError, "Status Code: 502 — Jubilee Response: Bad Gateway"
			):
				self.setting.get_jubilee_token()

	def test_network_failure_is_retried(self):
		responses = [requests.ConnectionError(), jubilee_response(200, ACCEPTED)]

		with patch.object(requests, "post", side_effect=responses) as post:
			self.assertEqual(self.setting.get_jubilee_token(), "_test_token")

		self.assertEqual(post.call_count, 2)

	def test_accepted_login_stores_the_token(self):
		with patch.object(requests, "post", return_value=jubilee_response(200, ACCEPTED)):
			self.setting.get_jubilee_token()

		self.assertEqual(frappe.db.get_value("HMS TZ Setting", COMPANY, "jubilee_token"), "_test_token")
