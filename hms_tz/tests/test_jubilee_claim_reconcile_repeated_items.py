# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.jubilee.doctype.jubilee_patient_claim.jubilee_patient_claim import JubileePatientClaim

CLAIM_NAME = "_Test Jubilee Reconcile Claim"
DENTURE_CODE = "6424"


def claim_row(ref_docname, item_code=DENTURE_CODE, unit_price=25000):
	return {
		"ref_doctype": "Procedure Prescription",
		"ref_docname": ref_docname,
		"item_name": "Denture Single Tooth",
		"item_code": item_code,
		"item_quantity": 1,
		"unit_price": unit_price,
		"amount_claimed": unit_price,
		"status": "Submitted",
	}


@patch.object(JubileePatientClaim, "validate_appointment_info", new=lambda self: None)
class TestJubileeClaimReconcileRepeatedItems(FrappeTestCase):
	def setUp(self):
		rows = [claim_row(f"_PP-{index}") for index in range(1, 9)]
		rows.append(claim_row("_APP-1", item_code="10002", unit_price=15000))
		claim = frappe.new_doc("Jubilee Patient Claim")
		claim.name = CLAIM_NAME
		claim.update(
			{
				"patient": "_Test Jubilee Reconcile Patient",
				"patient_appointment": "_APP-1",
				"authorization_no": "_TEST-JUBILEE-RECONCILE-AUTH",
				"cardno": "_TEST-JUBILEE-RECONCILE-CARD",
				"allow_changes": 1,
				"jubilee_patient_claim_item": rows,
				"original_jubilee_patient_claim_item": rows,
			}
		)
		claim.db_insert()
		for row in claim.jubilee_patient_claim_item + claim.original_jubilee_patient_claim_item:
			row.db_insert()

	def tearDown(self):
		frappe.db.rollback()

	def get_claim(self):
		return frappe.get_doc("Jubilee Patient Claim", CLAIM_NAME)

	def get_quantities(self, table):
		return [row.item_quantity for row in self.get_claim().get(table) if row.item_code == DENTURE_CODE]

	def test_saving_reconciled_claim_does_not_copy_rows_to_original(self):
		self.get_claim().reconcile_repeated_items()
		for _ in range(3):
			self.get_claim().save()
		self.assertEqual(self.get_quantities("jubilee_patient_claim_item"), [8])
		self.assertEqual(self.get_quantities("original_jubilee_patient_claim_item"), [8])

	def test_reconcile_again_keeps_quantities(self):
		self.get_claim().reconcile_repeated_items()
		self.get_claim().save()
		self.get_claim().reconcile_repeated_items()
		self.assertEqual(self.get_quantities("original_jubilee_patient_claim_item"), [8])

	def test_new_claim_row_is_still_copied_to_original(self):
		claim = self.get_claim()
		claim.append("jubilee_patient_claim_item", claim_row("_PP-NEW", item_code="5064", unit_price=150000))
		claim.save()
		original_refs = [row.ref_docname for row in claim.original_jubilee_patient_claim_item]
		self.assertEqual(original_refs.count("_PP-NEW"), 1)
