# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.nhif_api import approval

COMPANY = "_Test IS Company"
ISSUED_SERVICES = [
	{
		"ItemName": "CT Scan Chest",
		"Quantity": 1,
		"UnitPrice": 150000,
		"AmountClaimed": 150000,
		"ServiceReferenceNo": "211627873467",
		"CardNo": "CARD-0001",
		"FullName": "Sophia Wilson",
		"DateIssued": "2026-11-02T10:57:19.313",
	},
]


def insert(doctype, name, **values):
	doc = frappe.new_doc(doctype)
	doc.update({"name": name, **values})
	doc.db_insert()
	return doc


def nhif_response(status_code=200, data=None):
	return MagicMock(status_code=status_code, json=MagicMock(return_value=data), text=str(data))


class TestNHIFIssuedServices(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		insert("Company", COMPANY, company_name=COMPANY, abbr="_TIS", default_currency="TZS")

	def setUp(self):
		frappe.db.savepoint("issued_services_test")
		self.addCleanup(frappe.db.rollback, save_point="issued_services_test")
		self.settings = MagicMock(
			enable_nhif_api=1,
			nhifservice_url="https://nhif.test",
			get_nhif_token=MagicMock(return_value="t"),
		)
		get_cached_doc = frappe.get_cached_doc
		patches = [
			patch.object(
				approval.frappe,
				"get_cached_doc",
				side_effect=lambda doctype, *args: (
					self.settings if doctype == "HMS TZ Setting" else get_cached_doc(doctype, *args)
				),
			),
			patch.object(approval, "add_log"),
			patch.object(approval.requests, "request", return_value=nhif_response(data=ISSUED_SERVICES)),
		]
		for patcher in patches:
			patcher.start()
			self.addCleanup(patcher.stop)

	def test_posts_the_whole_date_range(self):
		for doctype in (
			"Delivery Note",
			"Lab Test",
			"Radiology Examination",
			"Clinical Procedure",
			"Therapy Session",
		):
			with self.subTest(doctype=doctype):
				insert(doctype, f"_Test IS {doctype}", company=COMPANY)

				result = approval.get_issued_services(
					doctype, f"_Test IS {doctype}", "2026-11-01", "2026-11-09"
				)

				self.assertEqual(result, ISSUED_SERVICES)
				method, url = approval.requests.request.call_args.args[:2]
				self.assertEqual(method, "POST")
				self.assertTrue(url.startswith("https://nhif.test/api/Approvals/GetIssuedServices?"))
				self.assertEqual(
					parse_qs(urlsplit(url).query),
					{"fromDate": ["2026-11-01T00:00:01"], "toDate": ["2026-11-09T23:59:59"]},
				)
				self.assertEqual(approval.add_log.call_args.kwargs["request_type"], "GetIssuedServices")
				self.assertEqual(approval.add_log.call_args.kwargs["ref_doctype"], doctype)

	def test_from_date_after_to_date_is_rejected(self):
		insert("Lab Test", "_Test IS Lab Test", company=COMPANY)

		with self.assertRaisesRegex(frappe.ValidationError, "From Date cannot be after To Date"):
			approval.get_issued_services("Lab Test", "_Test IS Lab Test", "2026-11-09", "2026-11-01")
		approval.requests.request.assert_not_called()

	def test_range_longer_than_one_month_is_rejected(self):
		insert("Lab Test", "_Test IS Lab Test", company=COMPANY)

		approval.get_issued_services("Lab Test", "_Test IS Lab Test", "2026-10-15", "2026-11-14")
		with self.assertRaisesRegex(frappe.ValidationError, "longer than one month"):
			approval.get_issued_services("Lab Test", "_Test IS Lab Test", "2026-10-15", "2026-11-15")
		approval.requests.request.assert_called_once()

	def test_failed_request_throws_nhif_error(self):
		insert("Lab Test", "_Test IS Lab Test", company=COMPANY)
		approval.requests.request.return_value = nhif_response(400, "bad")

		with self.assertRaisesRegex(frappe.ValidationError, "GetIssuedServices"):
			approval.get_issued_services("Lab Test", "_Test IS Lab Test", "2026-11-01", "2026-11-09")
		approval.add_log.assert_called_once()

	def test_other_doctype_is_rejected(self):
		with self.assertRaisesRegex(frappe.ValidationError, "not available for Patient Encounter"):
			approval.get_issued_services(
				"Patient Encounter", "_Test IS Encounter", "2026-11-01", "2026-11-09"
			)
		approval.requests.request.assert_not_called()

	def test_disabled_nhif_api_is_rejected(self):
		insert("Lab Test", "_Test IS Lab Test", company=COMPANY)
		self.settings.enable_nhif_api = 0

		with self.assertRaisesRegex(frappe.ValidationError, "NHIF API is disabled"):
			approval.get_issued_services("Lab Test", "_Test IS Lab Test", "2026-11-01", "2026-11-09")
		approval.requests.request.assert_not_called()
