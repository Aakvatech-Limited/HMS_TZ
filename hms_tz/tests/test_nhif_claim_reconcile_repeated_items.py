# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.doctype.nhif_patient_claim.nhif_patient_claim import (
	NHIFPatientClaim,
	reconcile_repeated_items,
)

CLAIM_NAME = "_Test Reconcile Claim"
DENTURE_CODE = "6424"


def claim_row(ref_docname, item_code=DENTURE_CODE, quantity=1, unit_price=25000):
	return {
		"ref_doctype": "Procedure Prescription",
		"ref_docname": ref_docname,
		"item_name": "Denture Single Tooth",
		"item_code": item_code,
		"item_quantity": quantity,
		"unit_price": unit_price,
		"amount_claimed": quantity * unit_price,
		"status": "Submitted",
	}


@patch.object(NHIFPatientClaim, "validate_appointment_info", new=lambda self: None)
@patch.object(NHIFPatientClaim, "set_folio_count", new=lambda self: None)
class TestNHIFClaimReconcileRepeatedItems(FrappeTestCase):
	def setUp(self):
		rows = [claim_row(f"_PP-{index}") for index in range(1, 9)]
		rows.append(claim_row("_APP-1", item_code="10002", unit_price=15000))
		claim = frappe.new_doc("NHIF Patient Claim")
		claim.name = CLAIM_NAME
		claim.update(
			{
				"patient": "_Test Reconcile Patient",
				"patient_appointment": "_APP-1",
				"authorization_no": "_TEST-RECONCILE-AUTH",
				"cardno": "_TEST-RECONCILE-CARD",
				"naming_series": "NPC-",
				"allow_changes": 1,
				"nhif_patient_claim_item": rows,
				"original_nhif_patient_claim_item": rows,
			}
		)
		claim.db_insert()
		for row in claim.nhif_patient_claim_item + claim.original_nhif_patient_claim_item:
			row.db_insert()

	def tearDown(self):
		frappe.db.rollback()
		frappe.clear_document_cache("NHIF Patient Claim", CLAIM_NAME)

	def get_quantities(self, table):
		claim = frappe.get_doc("NHIF Patient Claim", CLAIM_NAME)
		return [row.item_quantity for row in claim.get(table) if row.item_code == DENTURE_CODE]

	def test_reconcile_merges_repeated_rows_in_both_tables(self):
		reconcile_repeated_items(CLAIM_NAME)
		self.assertEqual(self.get_quantities("nhif_patient_claim_item"), [8])
		self.assertEqual(self.get_quantities("original_nhif_patient_claim_item"), [8])

	def test_saving_reconciled_claim_does_not_copy_rows_to_original(self):
		reconcile_repeated_items(CLAIM_NAME)
		for _ in range(3):
			frappe.get_doc("NHIF Patient Claim", CLAIM_NAME).save()
		self.assertEqual(self.get_quantities("original_nhif_patient_claim_item"), [8])

	def test_reconcile_again_keeps_quantities(self):
		reconcile_repeated_items(CLAIM_NAME)
		frappe.get_doc("NHIF Patient Claim", CLAIM_NAME).save()
		reconcile_repeated_items(CLAIM_NAME)
		self.assertEqual(self.get_quantities("nhif_patient_claim_item"), [8])
		self.assertEqual(self.get_quantities("original_nhif_patient_claim_item"), [8])

	def test_new_claim_row_is_still_copied_to_original(self):
		claim = frappe.get_doc("NHIF Patient Claim", CLAIM_NAME)
		claim.append("nhif_patient_claim_item", claim_row("_PP-NEW", item_code="5064", unit_price=150000))
		claim.save()
		original_refs = [row.ref_docname for row in claim.original_nhif_patient_claim_item]
		self.assertEqual(original_refs.count("_PP-NEW"), 1)
