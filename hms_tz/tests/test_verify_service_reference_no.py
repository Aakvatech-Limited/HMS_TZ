# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.nhif_api import approval
from hms_tz.patches.custom_fields.show_verify_button_only_with_service_reference_no import (
	execute,
	get_verify_button_fields,
)

DOCTYPES = [
	"Lab Test",
	"Radiology Examination",
	"Clinical Procedure",
	"Therapy Session",
	"Delivery Note Item",
]
OLD_DEPENDS_ON = "eval: doc.is_restricted == 1 && doc.approval_number"


class TestVerifyButtonPatch(FrappeTestCase):
	def setUp(self):
		for doctype in DOCTYPES:
			frappe.db.set_value(
				"Custom Field",
				{"dt": doctype, "fieldname": "verify_approval_no"},
				"depends_on",
				OLD_DEPENDS_ON,
			)
			frappe.clear_cache(doctype=doctype)

	def test_json_shows_button_only_with_service_reference_no(self):
		fields = get_verify_button_fields()
		self.assertEqual({field["dt"] for field in fields}, set(DOCTYPES))
		for field in fields:
			self.assertEqual(field["depends_on"], "eval: doc.service_reference_no", field["dt"])

	def test_patch_copies_depends_on_from_json(self):
		execute()

		for doctype in DOCTYPES:
			field = frappe.get_meta(doctype).get_field("verify_approval_no")
			self.assertEqual(field.depends_on, "eval: doc.service_reference_no", doctype)


class TestVerifyServiceReferenceNo(FrappeTestCase):
	def verify(self, status):
		settings = SimpleNamespace(
			name="_Test Company",
			enable_nhif_api=1,
			nhifservice_url="https://nhif.test",
			get_nhif_token=lambda: "token",
		)
		appointment = frappe._dict(insurance_company="NHIF", coverage_plan_card_number="CARD-1")
		response = MagicMock(status_code=200, text=f'{{"status": "{status}"}}')
		with (
			patch.object(approval.frappe, "get_cached_doc", return_value=settings),
			patch.object(approval, "get_appointment_details", return_value=appointment),
			patch.object(approval, "get_item_refcode", return_value="1001"),
			patch.object(approval, "add_log"),
			patch.object(approval.frappe, "msgprint"),
			patch.object(approval.requests, "request", return_value=response) as request,
		):
			result = approval.verify_service_reference_no(
				"_Test Company", "SRN-1", "Lab Test Template", "CBC", "APP-1", "Lab Test", "LT-1"
			)
		return result, request.call_args.args[1]

	def test_sends_service_reference_no_as_reference(self):
		result, url = self.verify("VALID")

		self.assertTrue(result)
		self.assertIn("cardNo=CARD-1&referenceNo=SRN-1&itemCode=1001", url)

	def test_invalid_reference_returns_false(self):
		result, _url = self.verify("INVALID")

		self.assertFalse(result)
