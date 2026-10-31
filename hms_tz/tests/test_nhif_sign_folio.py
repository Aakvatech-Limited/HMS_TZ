# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
import json
from unittest.mock import MagicMock, patch

import frappe
import requests
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.nhif_api import patient_claim
from hms_tz.nhif.nhif_api.patient_claim import SIGN_FOLIO_TIMEOUT, sign_folio

CLAIM = "_Test Sign Folio Claim"


SETTINGS = MagicMock(nhif_claim_url="https://nhif.test", get_nhif_token=lambda: "token")
get_cached_doc = frappe.get_cached_doc


def nhif_response(status_code, text='{"Message": "OK"}'):
	return MagicMock(status_code=status_code, text=text)


def get_cached_doc_with_fake_settings(doctype, *args, **kwargs):
	if doctype == "HMS TZ Setting":
		return SETTINGS
	return get_cached_doc(doctype, *args, **kwargs)


def delete_test_claim():
	# sign_folio commits on NHIF failure, so the rollback alone does not clean up
	frappe.db.delete("NHIF Patient Claim", CLAIM)
	frappe.db.delete("NHIF Patient Claim Item", {"parent": CLAIM})
	frappe.db.delete("Comment", {"reference_name": CLAIM})
	frappe.db.delete("Error Log", {"reference_name": CLAIM})
	frappe.db.commit()


@patch.object(patient_claim, "add_log", new=lambda **kwargs: None)
@patch.object(patient_claim.frappe, "get_cached_doc", new=get_cached_doc_with_fake_settings)
class TestNHIFSignFolio(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		delete_test_claim()

	def setUp(self):
		"""Insert without validation so the test needs no appointment or NHIF masters."""
		claim = frappe.new_doc("NHIF Patient Claim")
		claim.name = CLAIM
		claim.cardno = " 01-99282742 "
		claim.authorization_no = "AUTH-1"
		claim.first_name = "Test"
		claim.last_name = "Patient"
		claim.company = "_Test Company"
		claim.append("nhif_patient_claim_item", {"amount_claimed": 1500})
		claim.db_insert()
		claim.nhif_patient_claim_item[0].db_insert()

	def tearDown(self):
		delete_test_claim()

	def sign(self, **kwargs):
		return sign_folio("NHIF Patient Claim", CLAIM, signature="data:image/png;base64,abc", **kwargs)

	def is_signed(self):
		return frappe.db.get_value("NHIF Patient Claim", CLAIM, "folio_signed")

	@patch.object(patient_claim.requests, "request", return_value=nhif_response(200))
	def test_success_marks_folio_signed(self, request):
		self.assertTrue(self.sign())
		claim = frappe.db.get_value(
			"NHIF Patient Claim", CLAIM, ["folio_signed", "signed_amount", "patient_signature"], as_dict=True
		)
		self.assertEqual(claim.folio_signed, 1)
		self.assertEqual(claim.signed_amount, 1500)
		self.assertEqual(claim.patient_signature, "data:image/png;base64,abc")
		self.assertEqual(request.call_args.kwargs["timeout"], SIGN_FOLIO_TIMEOUT)

	@patch.object(patient_claim.requests, "request", return_value=nhif_response(200))
	def test_payload_matches_signature_model(self, request):
		self.sign()
		self.assertEqual(
			json.loads(request.call_args.kwargs["data"]),
			{
				"CardNo": "01-99282742",
				"AuthorizationNo": "AUTH-1",
				"AmountClaimed": 1500,
				"SignedBy": "PATIENT",
				"SignatureData": "abc",
				"SignatureMethod": "SIGNATURE",
				"SignedByName": "Test Patient",
			},
		)

	@patch.object(patient_claim.requests, "request", return_value=nhif_response(200))
	def test_parent_signing_for_child(self, request):
		self.sign(signed_by="PARENT", signed_by_name="Jane Mother")
		payload = json.loads(request.call_args.kwargs["data"])
		self.assertEqual(payload["SignedBy"], "PARENT")
		self.assertEqual(payload["SignedByName"], "Jane Mother")

	@patch.object(patient_claim.requests, "request")
	def test_signed_by_outside_nhif_codes_is_rejected(self, request):
		"""NHIF rejects a name in SignedBy, which the old payload sent."""
		with self.assertRaises(frappe.ValidationError):
			self.sign(signed_by="Test Patient")
		request.assert_not_called()

	@patch.object(patient_claim.requests, "request", return_value=nhif_response(200))
	def test_fingerprint_is_signed_by_patient(self, request):
		sign_folio(
			"NHIF Patient Claim", CLAIM, signature_method="fingerprint", fingerprint="fp-data", fpcode="R1"
		)
		payload = json.loads(request.call_args.kwargs["data"])
		self.assertEqual(payload["SignatureMethod"], "FINGERPRINT")
		self.assertEqual(payload["FpCode"], "R1")
		self.assertEqual(payload["SignatureData"], "fp-data")
		self.assertEqual(payload["SignedBy"], "PATIENT")
		self.assertEqual(payload["SignedByName"], "Test Patient")
		self.assertFalse(frappe.db.get_value("NHIF Patient Claim", CLAIM, "patient_signature"))

	@patch.object(patient_claim.requests, "request", side_effect=requests.Timeout("read timed out"))
	def test_network_failure_returns_error_without_signing(self, request):
		self.assertEqual(self.sign(), "Error")
		self.assertEqual(self.is_signed(), 0)
		self.assertTrue(
			frappe.db.exists(
				"Error Log", {"reference_doctype": "NHIF Patient Claim", "reference_name": CLAIM}
			)
		)

	@patch.object(patient_claim.requests, "request", return_value=nhif_response(400, "Invalid card"))
	def test_nhif_rejection_returns_error_without_signing(self, request):
		self.assertEqual(self.sign(), "Error")
		self.assertEqual(self.is_signed(), 0)
		self.assertFalse(frappe.db.get_value("NHIF Patient Claim", CLAIM, "patient_signature"))

	@patch.object(patient_claim.requests, "request")
	def test_already_signed_folio_is_not_sent_again(self, request):
		frappe.db.set_value("NHIF Patient Claim", CLAIM, "folio_signed", 1)
		self.assertTrue(self.sign())
		request.assert_not_called()

	def test_other_doctypes_are_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			sign_folio("Patient", CLAIM, signature="data:image/png;base64,abc")

	def test_blank_signature_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			sign_folio("NHIF Patient Claim", CLAIM)
