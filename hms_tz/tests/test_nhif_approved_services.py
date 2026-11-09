# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.nhif_api import approval

COMPANY = "_Test AS Company"
DENTURE = {
	"CardNo": "CARD-0001",
	"AuthorizedItemID": "8e8e6704-03ad-48a6-aae5-18c6d6a6b429",
	"ServiceAuthorizationID": "614e430e-5775-41cb-baff-4a4346a968bd",
	"ServiceTypeName": "Medical,Dental and Orthopaedic Appliances",
	"ServiceTypeID": 6,
	"RequiresBiometric": False,
	"ItemCode": "6424",
	"UnitPrice": 25000,
	"NationalID": None,
	"ItemName": "Denture per tooth up to 12 number of teeth (each)",
	"Quantity": 8,
	"RemainQuantity": 0,
	"Description": "",
}


def insert(doctype, name, **values):
	doc = frappe.new_doc(doctype)
	doc.update({"name": name, **values})
	doc.db_insert()
	return doc


def nhif_response(status_code=200, data=None):
	return MagicMock(status_code=status_code, json=MagicMock(return_value=data), text=str(data))


def get_requested_numbers():
	return [
		call.args[1].rsplit("approvalReferenceNo=", 1)[1] for call in approval.requests.request.call_args_list
	]


class TestNHIFApprovedServices(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		insert("Company", COMPANY, company_name=COMPANY, abbr="_TAS", default_currency="TZS")

	def setUp(self):
		frappe.db.savepoint("approved_services_test")
		self.addCleanup(frappe.db.rollback, save_point="approved_services_test")
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
				side_effect=lambda doctype, *args: self.settings
				if doctype == "HMS TZ Setting"
				else get_cached_doc(doctype, *args),
			),
			patch.object(approval, "add_log"),
			patch.object(approval.requests, "request", return_value=nhif_response(data=[DENTURE])),
		]
		for patcher in patches:
			patcher.start()
			self.addCleanup(patcher.stop)

	def insert_delivery_note(self, approval_numbers):
		insert("Delivery Note", "_Test AS DN", company=COMPANY)
		for idx, approval_number in enumerate(approval_numbers, 1):
			insert(
				"Delivery Note Item",
				f"_Test AS DN Item {idx}",
				parent="_Test AS DN",
				parenttype="Delivery Note",
				parentfield="items",
				idx=idx,
				is_restricted=1,
				approval_number=approval_number,
			)

	def test_service_returns_lines_of_its_approval_number(self):
		insert("Clinical Procedure", "_Test AS Procedure", company=COMPANY, approval_number="580625628084")

		approvals = approval.get_approved_services("Clinical Procedure", "_Test AS Procedure")

		self.assertEqual(approvals, [{"approval_number": "580625628084", "services": [DENTURE]}])
		self.assertIn(
			"https://nhif.test/api/Approvals/GetApprovedServices?approvalReferenceNo=580625628084",
			approval.requests.request.call_args.args[1],
		)
		self.assertEqual(approval.add_log.call_args.kwargs["request_type"], "GetApprovedServices")

	def test_delivery_note_calls_nhif_once_per_distinct_approval_number(self):
		self.insert_delivery_note(["111", None, "222", "111"])
		approval.requests.request.side_effect = [nhif_response(data=[DENTURE]), nhif_response(data=[])]

		approvals = approval.get_approved_services("Delivery Note", "_Test AS DN")

		self.assertEqual(get_requested_numbers(), ["111", "222"])
		self.assertEqual(
			approvals,
			[{"approval_number": "111", "services": [DENTURE]}, {"approval_number": "222", "services": []}],
		)

	def test_one_failed_approval_number_fails_the_whole_request(self):
		self.insert_delivery_note(["111", "222"])
		approval.requests.request.side_effect = [nhif_response(data=[DENTURE]), nhif_response(400, "bad")]

		with self.assertRaisesRegex(frappe.ValidationError, "approvalReferenceNo=222"):
			approval.get_approved_services("Delivery Note", "_Test AS DN")
		self.assertEqual(approval.add_log.call_count, 2)

	def test_document_without_approval_number_is_rejected(self):
		self.insert_delivery_note([None])

		with self.assertRaisesRegex(frappe.ValidationError, "has no approval number"):
			approval.get_approved_services("Delivery Note", "_Test AS DN")
		approval.requests.request.assert_not_called()

	def test_disabled_nhif_api_is_rejected(self):
		insert("Clinical Procedure", "_Test AS Procedure", company=COMPANY, approval_number="580625628084")
		self.settings.enable_nhif_api = 0

		with self.assertRaisesRegex(frappe.ValidationError, "NHIF API is disabled"):
			approval.get_approved_services("Clinical Procedure", "_Test AS Procedure")
		approval.requests.request.assert_not_called()

	def test_other_doctype_is_rejected(self):
		with self.assertRaisesRegex(frappe.ValidationError, "not available for Patient"):
			approval.get_approved_services("Patient", "_Test AS Patient")
