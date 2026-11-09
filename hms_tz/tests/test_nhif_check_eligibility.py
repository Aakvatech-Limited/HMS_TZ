# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif import utils
from hms_tz.nhif.nhif_api import approval

COMPANY = "_Test CE Company"
ELIGIBLE = {"CanAccess": True, "Remarks": "The access to the service Octreotide can be granted"}
NOT_ELIGIBLE = {"CanAccess": False, "Remarks": "The beneficiary is not eligible for the service"}
REF_CODES = {"Octreotide": "10101", "Insulin": "20202", "MRI Brain": "30303"}


def insert(doctype, name, **values):
	doc = frappe.new_doc(doctype)
	doc.update({"name": name, **values})
	doc.db_insert()
	return doc


def nhif_response(status_code=200, data=None):
	return MagicMock(status_code=status_code, json=MagicMock(return_value=data), text=str(data))


def get_requested_queries():
	return [parse_qs(urlsplit(call.args[1]).query) for call in approval.requests.request.call_args_list]


class TestNHIFCheckEligibility(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		insert("Company", COMPANY, company_name=COMPANY, abbr="_TCE", default_currency="TZS")

	def setUp(self):
		frappe.db.savepoint("check_eligibility_test")
		self.addCleanup(frappe.db.rollback, save_point="check_eligibility_test")
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
			patch.object(
				approval,
				"get_item_refcode",
				side_effect=lambda service_type, service_name, *args: REF_CODES.get(service_name, ""),
			),
			patch.object(approval, "add_log"),
			patch.object(approval.requests, "request", return_value=nhif_response(data=ELIGIBLE)),
		]
		for patcher in patches:
			patcher.start()
			self.addCleanup(patcher.stop)

	def insert_delivery_note(self, items):
		insert("Delivery Note", "_Test CE DN", company=COMPANY)
		for idx, (drug_code, is_restricted) in enumerate(items, 1):
			insert("Drug Prescription", f"_Test CE MR {idx}", drug_code=drug_code)
			insert(
				"Delivery Note Item",
				f"_Test CE DN Item {idx}",
				parent="_Test CE DN",
				parenttype="Delivery Note",
				parentfield="items",
				idx=idx,
				item_name=drug_code,
				is_restricted=is_restricted,
				reference_doctype="Drug Prescription",
				reference_name=f"_Test CE MR {idx}",
			)

	def test_service_checks_its_card_and_item_code(self):
		insert(
			"Radiology Examination",
			"_Test CE Radiology",
			company=COMPANY,
			is_restricted=1,
			radiology_examination_template="MRI Brain",
		)

		services = approval.check_eligibility("Radiology Examination", "_Test CE Radiology")

		self.assertEqual(services, [{"service": "MRI Brain", "item_code": "30303", **ELIGIBLE}])
		self.assertEqual(get_requested_queries(), [{"cardNo": ["CARD-0001"], "itemCode": ["30303"]}])
		self.assertIn(
			"https://nhif.test/api/Approvals/CheckEligibility?", approval.requests.request.call_args.args[1]
		)
		self.assertEqual(approval.add_log.call_args.kwargs["request_type"], "CheckEligibility")
		self.assertEqual(approval.add_log.call_args.kwargs["card_no"], "CARD-0001")

	def test_delivery_note_checks_each_restricted_item_once_per_item_code(self):
		self.insert_delivery_note([("Octreotide", 1), ("Paracetamol", 0), ("Insulin", 1), ("Octreotide", 1)])
		approval.requests.request.side_effect = [
			nhif_response(data=ELIGIBLE),
			nhif_response(data=NOT_ELIGIBLE),
		]

		services = approval.check_eligibility("Delivery Note", "_Test CE DN")

		self.assertEqual([query["itemCode"] for query in get_requested_queries()], [["10101"], ["20202"]])
		self.assertEqual(
			services,
			[
				{"service": "Row 1: Octreotide", "item_code": "10101", **ELIGIBLE},
				{"service": "Row 3: Insulin", "item_code": "20202", **NOT_ELIGIBLE},
				{"service": "Row 4: Octreotide", "item_code": "10101", **ELIGIBLE},
			],
		)

	def test_failed_request_throws_nhif_error(self):
		self.insert_delivery_note([("Octreotide", 1), ("Insulin", 1)])
		approval.requests.request.side_effect = [nhif_response(data=ELIGIBLE), nhif_response(400, "bad")]

		with self.assertRaisesRegex(frappe.ValidationError, "itemCode=20202"):
			approval.check_eligibility("Delivery Note", "_Test CE DN")
		self.assertEqual(approval.add_log.call_count, 2)

	def test_item_without_nhif_code_is_rejected(self):
		self.insert_delivery_note([("Unmapped Drug", 1)])

		with self.assertRaisesRegex(frappe.ValidationError, "has no NHIF item code"):
			approval.check_eligibility("Delivery Note", "_Test CE DN")
		approval.requests.request.assert_not_called()

	def test_document_without_restricted_service_is_rejected(self):
		self.insert_delivery_note([("Paracetamol", 0)])

		with self.assertRaisesRegex(frappe.ValidationError, "has no restricted service"):
			approval.check_eligibility("Delivery Note", "_Test CE DN")
		approval.requests.request.assert_not_called()

	def test_visit_without_nhif_card_is_rejected(self):
		self.insert_delivery_note([("Octreotide", 1)])
		utils.get_nhif_visit.return_value = None

		with self.assertRaisesRegex(frappe.ValidationError, "NHIF visit with a card number"):
			approval.check_eligibility("Delivery Note", "_Test CE DN")
		approval.requests.request.assert_not_called()

	def test_disabled_nhif_api_is_rejected(self):
		self.insert_delivery_note([("Octreotide", 1)])
		self.settings.enable_nhif_api = 0

		with self.assertRaisesRegex(frappe.ValidationError, "NHIF API is disabled"):
			approval.check_eligibility("Delivery Note", "_Test CE DN")
		approval.requests.request.assert_not_called()
