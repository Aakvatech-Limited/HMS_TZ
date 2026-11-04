# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.doctype.nhif_patient_claim import nhif_patient_claim
from hms_tz.nhif.doctype.nhif_patient_claim.nhif_patient_claim import NHIFPatientClaim
from hms_tz.nhif.nhif_api.patient_claim import get_payload

AUTHORIZATION_NO = "_TEST-SIGNED-AMOUNT-AUTH"


def make_claim(**values):
	claim = frappe.new_doc("NHIF Patient Claim")
	claim.update(
		{
			"patient": "_Test Signed Amount Patient",
			"cardno": "01-99282742",
			"authorization_no": AUTHORIZATION_NO,
			"main_diagnosis_code": "A00.0",
			"allow_changes": 1,
			"bypass_sending_to_nhif": 1,
			**values,
		}
	)
	return claim


def insert_claim(name, **values):
	"""Insert without validation so the test needs no appointment or NHIF masters."""
	claim = make_claim(**values)
	claim.name = name
	claim.db_insert()
	return claim


@patch.object(nhif_patient_claim, "validate_submit_date", new=lambda doc: None)
@patch.object(NHIFPatientClaim, "validate_multiple_appointments_per_authorization_no", new=lambda self: None)
class TestNHIFClaimSignedAmount(FrappeTestCase):
	@patch.object(nhif_patient_claim, "get_missing_patient_signature")
	def test_signed_folio_keeps_signature_empty(self, get_missing_patient_signature):
		make_claim(folio_signed=1, signed_amount=1500, total_amount=1500).run_method("before_submit")
		get_missing_patient_signature.assert_not_called()

	@patch.object(nhif_patient_claim, "get_missing_patient_signature")
	def test_unsigned_folio_takes_patient_signature(self, get_missing_patient_signature):
		make_claim(total_amount=1500).run_method("before_submit")
		get_missing_patient_signature.assert_called_once()

	@patch.object(nhif_patient_claim, "get_missing_patient_signature", new=lambda doc: None)
	def test_total_above_signed_amount_blocks_submit(self):
		claim = make_claim(folio_signed=1, signed_amount=1500, total_amount=2000)
		self.assertRaisesRegex(frappe.ValidationError, "Signed Amount", claim.run_method, "before_submit")

	@patch.object(nhif_patient_claim, "get_missing_patient_signature", new=lambda doc: None)
	def test_signed_amount_check_needs_signed_folio_and_amount(self):
		make_claim(folio_signed=1, signed_amount=2000, total_amount=1500).run_method("before_submit")
		make_claim(folio_signed=1, signed_amount=0, total_amount=2000).run_method("before_submit")
		make_claim(folio_signed=0, signed_amount=1500, total_amount=2000).run_method("before_submit")


class TestNHIFClaimMergeSignedAmount(FrappeTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def merge(self, claim):
		claim.save = MagicMock()
		claim.get_appointments()
		return claim.signed_amount

	def test_adds_signed_amount_of_other_draft_claims(self):
		claim = insert_claim("_Test Merge A", patient_appointment="_APP-A", signed_amount=1000)
		insert_claim("_Test Merge B", patient_appointment="_APP-B", signed_amount=700)
		insert_claim("_Test Merge C", patient_appointment="_APP-C", signed_amount=300, docstatus=2)
		self.assertEqual(self.merge(claim), 1700)
		self.assertEqual(set(json.loads(claim.hms_tz_claim_appointment_list)), {"_APP-A", "_APP-B", "_APP-C"})

	def test_merging_again_does_not_add_twice(self):
		claim = insert_claim("_Test Merge A", patient_appointment="_APP-A", signed_amount=1000)
		insert_claim("_Test Merge B", patient_appointment="_APP-B", signed_amount=700)
		self.merge(claim)
		self.assertEqual(self.merge(claim), 1700)

	def test_hand_signed_claim_adds_its_total(self):
		claim = insert_claim(
			"_Test Merge A", patient_appointment="_APP-A", folio_signed=1, signed_amount=1000
		)
		insert_claim("_Test Merge B", patient_appointment="_APP-B", total_amount=800, patient_signature="sig")
		self.assertEqual(self.merge(claim), 1800)

	def test_signed_folio_without_signed_amount_adds_its_total(self):
		claim = insert_claim(
			"_Test Merge A", patient_appointment="_APP-A", folio_signed=1, signed_amount=1000
		)
		insert_claim("_Test Merge B", patient_appointment="_APP-B", folio_signed=1, total_amount=600)
		self.assertEqual(self.merge(claim), 1600)

	def test_claim_without_any_signature_stops_merge(self):
		claim = insert_claim(
			"_Test Merge A", patient_appointment="_APP-A", folio_signed=1, signed_amount=1000
		)
		insert_claim("_Test Merge B", patient_appointment="_APP-B", total_amount=800)
		self.assertRaisesRegex(frappe.ValidationError, "_Test Merge B", self.merge, claim)
		self.assertEqual(claim.signed_amount, 1000)
		self.assertFalse(claim.hms_tz_claim_appointment_list)

	def test_unsigned_target_claim_without_signature_stops_merge(self):
		claim = insert_claim("_Test Merge A", patient_appointment="_APP-A", total_amount=800)
		insert_claim("_Test Merge B", patient_appointment="_APP-B", folio_signed=1, signed_amount=700)
		self.assertRaisesRegex(frappe.ValidationError, "_Test Merge A", self.merge, claim)

	def test_claim_inside_earlier_merge_is_not_counted_twice(self):
		claim = insert_claim("_Test Merge A", patient_appointment="_APP-A", signed_amount=500)
		insert_claim(
			"_Test Merge B",
			patient_appointment="_APP-B",
			signed_amount=1000,
			hms_tz_claim_appointment_list=json.dumps(["_APP-B", "_APP-C"]),
		)
		insert_claim("_Test Merge C", patient_appointment="_APP-C", signed_amount=300)
		self.assertEqual(self.merge(claim), 1500)

	def test_claim_already_merged_elsewhere_takes_that_amount(self):
		claim = insert_claim("_Test Merge A", patient_appointment="_APP-A", signed_amount=1000)
		insert_claim(
			"_Test Merge B",
			patient_appointment="_APP-B",
			signed_amount=1700,
			hms_tz_claim_appointment_list=json.dumps(["_APP-A", "_APP-B"]),
		)
		self.assertEqual(self.merge(claim), 1700)

	def test_hand_signed_merged_claim_covers_claims_inside_it(self):
		claim = insert_claim("_Test Merge A", patient_appointment="_APP-A", signed_amount=1000)
		insert_claim(
			"_Test Merge B",
			patient_appointment="_APP-B",
			total_amount=900,
			patient_signature="sig",
			hms_tz_claim_appointment_list=json.dumps(["_APP-B", "_APP-C"]),
		)
		insert_claim("_Test Merge C", patient_appointment="_APP-C", signed_amount=300)
		self.assertEqual(self.merge(claim), 1900)

	def test_unsigned_claim_inside_merged_claim_does_not_stop_merge(self):
		claim = insert_claim("_Test Merge A", patient_appointment="_APP-A", signed_amount=1000)
		insert_claim(
			"_Test Merge B",
			patient_appointment="_APP-B",
			signed_amount=700,
			hms_tz_claim_appointment_list=json.dumps(["_APP-B", "_APP-C"]),
		)
		insert_claim("_Test Merge C", patient_appointment="_APP-C", total_amount=300)
		self.assertEqual(self.merge(claim), 1700)


class TestSubmitFolioSignatures(FrappeTestCase):
	def get_signatories(self, **values):
		claim = make_claim(
			attendance_date="2026-11-01",
			attendance_time="10:00:00",
			modified="2026-11-01 10:00:00",
			modified_by="Administrator",
			patient_signature="data:image/png;base64,abc",
			**values,
		)
		return [row["Signatory"] for row in json.loads(get_payload(claim))["Signatures"]]

	def test_signed_folio_sends_no_patient_signature(self):
		self.assertNotIn("PATIENT", self.get_signatories(folio_signed=1))

	def test_unsigned_folio_sends_patient_signature(self):
		self.assertIn("PATIENT", self.get_signatories(folio_signed=0))
