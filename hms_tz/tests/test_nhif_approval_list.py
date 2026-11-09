# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif import utils
from hms_tz.nhif.nhif_api import approval

COMPANY = "_Test AL Company"
APPROVALS = [
	{
		"AuthorizationNo": "501627864350",
		"ItemCode": "7202",
		"ItemName": "Physiotherapy and Rehabilitative Service",
		"ApprovalStatus": "Waiting for Approval",
	},
	{
		"AuthorizationNo": "401627865020",
		"ApprovalReferenceNo": "601627873100",
		"ItemCode": "5064",
		"ItemName": "CT Scan Chest",
		"ApprovalStatus": "Approved",
	},
]


def insert(doctype, name, **values):
	doc = frappe.new_doc(doctype)
	doc.update({"name": name, **values})
	doc.db_insert()
	return doc


def nhif_response(status_code=200, data=None):
	return MagicMock(status_code=status_code, json=MagicMock(return_value=data), text=str(data))


class TestNHIFApprovalList(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		insert("Company", COMPANY, company_name=COMPANY, abbr="_TAL", default_currency="TZS")

	def setUp(self):
		frappe.db.savepoint("approval_list_test")
		self.addCleanup(frappe.db.rollback, save_point="approval_list_test")
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
			patch.object(
				utils,
				"get_nhif_visit",
				return_value=frappe._dict(coverage_plan_card_number="CARD-0001", insurance_company="NHIF"),
			),
			patch.object(approval, "add_log"),
			patch.object(approval.requests, "request", return_value=nhif_response(data=APPROVALS)),
		]
		for patcher in patches:
			patcher.start()
			self.addCleanup(patcher.stop)

	def test_returns_approvals_of_the_card(self):
		for doctype in ("Patient Encounter", "Lab Test", "Delivery Note"):
			with self.subTest(doctype=doctype):
				insert(doctype, f"_Test AL {doctype}", company=COMPANY)

				self.assertEqual(approval.get_approval_list(doctype, f"_Test AL {doctype}"), APPROVALS)
				url = approval.requests.request.call_args.args[1]
				self.assertTrue(url.startswith("https://nhif.test/api/Approvals/GetApprovals?"))
				self.assertEqual(parse_qs(urlsplit(url).query), {"cardNo": ["CARD-0001"]})
				self.assertEqual(approval.add_log.call_args.kwargs["request_type"], "GetApprovals")
				self.assertEqual(approval.add_log.call_args.kwargs["ref_doctype"], doctype)

	def test_failed_request_throws_nhif_error(self):
		insert("Lab Test", "_Test AL Lab Test", company=COMPANY)
		approval.requests.request.return_value = nhif_response(400, "bad")

		with self.assertRaisesRegex(frappe.ValidationError, "GetApprovals"):
			approval.get_approval_list("Lab Test", "_Test AL Lab Test")
		approval.add_log.assert_called_once()

	def test_visit_without_nhif_card_is_rejected(self):
		insert("Patient Encounter", "_Test AL Encounter", company=COMPANY)
		utils.get_nhif_visit.return_value = None

		with self.assertRaisesRegex(frappe.ValidationError, "NHIF visit with a card number"):
			approval.get_approval_list("Patient Encounter", "_Test AL Encounter")
		approval.requests.request.assert_not_called()

	def test_other_doctype_is_rejected(self):
		with self.assertRaisesRegex(frappe.ValidationError, "not available for Sales Invoice"):
			approval.get_approval_list("Sales Invoice", "_Test AL Invoice")
		approval.requests.request.assert_not_called()

	def test_disabled_nhif_api_is_rejected(self):
		insert("Patient Encounter", "_Test AL Encounter", company=COMPANY)
		self.settings.enable_nhif_api = 0

		with self.assertRaisesRegex(frappe.ValidationError, "NHIF API is disabled"):
			approval.get_approval_list("Patient Encounter", "_Test AL Encounter")
		approval.requests.request.assert_not_called()
