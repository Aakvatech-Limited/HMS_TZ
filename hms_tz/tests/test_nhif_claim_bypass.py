# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.doctype.nhif_patient_claim import nhif_patient_claim
from hms_tz.nhif.doctype.nhif_patient_claim.nhif_patient_claim import NHIFPatientClaim
from hms_tz.nhif.nhif_api import patient_claim
from hms_tz.tests.test_nhif_claim_signed_amount import make_claim
from hms_tz.tests.test_nhif_sign_folio import get_cached_doc_with_fake_settings, nhif_response


@patch.object(patient_claim, "add_log", new=lambda **kwargs: None)
@patch.object(patient_claim.frappe, "get_cached_doc", new=get_cached_doc_with_fake_settings)
class TestGetReceiptValidateOnly(FrappeTestCase):
	def setUp(self):
		self.claim = make_claim(facility_code="04069", claim_year=2026, claim_month=11, folio_no=42)

	def get_receipt(self, response):
		with patch.object(patient_claim.requests, "request", return_value=response) as request:
			result = patient_claim.get_receipt(doc=self.claim, validate_only=True)
		self.assertIn("facilityCode=04069&claimYear=2026&claimMonth=11&folioNo=42", request.call_args.args[1])
		return result

	def test_claim_with_nhif_receipt_passes_without_saving(self):
		self.assertTrue(self.get_receipt(nhif_response(200, json.dumps({"ReceiptNo": "R-1001"}))))
		self.assertFalse(self.claim.receipt_no)

	def test_claim_without_nhif_receipt_stops_submit(self):
		for response in (
			nhif_response(404, json.dumps({"Message": "Folio not found"})),
			nhif_response(200, json.dumps({"ReceiptNo": None})),
		):
			with self.subTest(status_code=response.status_code):
				self.assertRaisesRegex(
					frappe.ValidationError, "has not yet reached NHIF", self.get_receipt, response
				)


@patch.object(nhif_patient_claim, "validate_submit_date", new=lambda doc: None)
@patch.object(nhif_patient_claim, "get_missing_patient_signature", new=lambda doc: None)
@patch.object(NHIFPatientClaim, "validate_multiple_appointments_per_authorization_no", new=lambda self: None)
@patch.object(nhif_patient_claim, "submit_folio")
@patch.object(nhif_patient_claim, "get_receipt")
class TestClaimSubmitNHIFCheck(FrappeTestCase):
	def test_bypassed_claim_checks_receipt(self, get_receipt, submit_folio):
		claim = make_claim(total_amount=1500)
		claim.run_method("before_submit")
		get_receipt.assert_called_once_with(doc=claim, validate_only=True)
		submit_folio.assert_not_called()

	def test_claim_sent_to_nhif_skips_receipt_check(self, get_receipt, submit_folio):
		make_claim(total_amount=1500, bypass_sending_to_nhif=0).run_method("before_submit")
		submit_folio.assert_called_once()
		get_receipt.assert_not_called()


@patch.object(patient_claim, "add_log", new=lambda **kwargs: None)
@patch.object(patient_claim.frappe, "get_cached_doc", new=get_cached_doc_with_fake_settings)
class TestGetReceiptButton(FrappeTestCase):
	def test_success_comment_shows_receipt_no(self):
		claim = MagicMock(company="_Test Company")
		response = nhif_response(200, json.dumps({"ReceiptNo": "S300022050162", "ClaimMonth": 10}))
		with patch.object(patient_claim.requests, "request", return_value=response):
			self.assertTrue(patient_claim.get_receipt(doc=claim))

		self.assertEqual(claim.receipt_no, "S300022050162")
		comment = claim.add_comment.call_args.kwargs["text"]
		self.assertIn("S300022050162", comment)
		self.assertNotIn("None", comment)
