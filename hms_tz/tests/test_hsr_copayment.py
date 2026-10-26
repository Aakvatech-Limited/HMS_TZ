from unittest.mock import patch

import frappe
from frappe.query_builder import DocType
from frappe.tests.utils import FrappeTestCase

from hms_tz.hms_tz.doctype.healthcare_service_request.test_healthcare_service_request import (
	add_payment,
	make_request,
)
from hms_tz.nhif.api.sales_invoice import create_healthcare_docs, set_invoiced_references

TEMPLATE = "_Test Copayment X-Ray"
REQUEST_ID = "_test_copay_request"
CREATE_RADIOLOGY = (
	"hms_tz.hms_tz.doctype.healthcare_service_request.healthcare_service_request"
	".create_individual_radiology_examination"
)


def make_prescription(**overrides):
	row = frappe.get_doc(
		doctype="Radiology Procedure Prescription",
		name=frappe.generate_hash(),
		parent="_Test Copayment Encounter",
		parenttype="Patient Encounter",
		parentfield="radiology_procedure_prescription",
		radiology_examination_template=TEMPLATE,
		**overrides,
	)
	row.db_insert()

	return row


def make_copayment_request(prescription, cash_invoiced=0):
	"""Submitted request with an 80% NHIF row and a 20% cash row for one X-Ray."""
	hsr = make_request(name=frappe.generate_hash(), docstatus=1)
	shared = {
		"service_type": "Radiology Examination Template",
		"service_name": TEMPLATE,
		"ref_doctype": prescription.doctype,
		"ref_docname": prescription.name,
		"request_id": REQUEST_ID,
		"qty": 1,
		"rate": 10000,
	}
	payments = [
		{"payment_type": "Insurance", "insurance_company": "NHIF", "percent_covered": 80, "amount": 8000},
		{"payment_type": "Cash", "percent_covered": 20, "amount": 2000, "invoiced": cash_invoiced},
	]
	for payment in payments:
		add_payment(hsr, **shared, **payment)

	hsr.db_insert()
	for row in hsr.payments:
		row.db_insert()

	return frappe.get_doc(hsr.doctype, hsr.name)


def invoice_cash_row(hsr):
	cash_row = next(row for row in hsr.payments if row.payment_type == "Cash")
	item = frappe._dict(
		reference_dt=cash_row.ref_doctype,
		reference_dn=cash_row.ref_docname,
		service_request=cash_row.name,
	)
	invoice = frappe.new_doc("Sales Invoice")
	invoice.update({"name": "_Test Copayment Invoice", "docstatus": 1})
	invoice.items = [item]

	set_invoiced_references(invoice, invoice.name)
	create_healthcare_docs(invoice)


class TestHSRCopaymentInvoice(FrappeTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_invoice_releases_the_insurance_row(self):
		hsr = make_copayment_request(make_prescription())

		with patch(CREATE_RADIOLOGY) as create_radiology:
			invoice_cash_row(hsr)

		create_radiology.assert_called_once()
		self.assertEqual(create_radiology.call_args.args[2].payment_type, "Insurance")

	def test_rerun_skips_service_marked_created_after_cache_was_filled(self):
		hsr = make_copayment_request(make_prescription(), cash_invoiced=1)
		frappe.get_cached_doc(hsr.doctype, hsr.name)

		hsrp = DocType("Healthcare Service Request Payment")
		frappe.qb.update(hsrp).set(hsrp.lrpmt_doc_created, 1).where(hsrp.parent == hsr.name).run()

		with patch(CREATE_RADIOLOGY) as create_radiology:
			invoice_cash_row(hsr)

		create_radiology.assert_not_called()

	def test_reads_current_prescription_state(self):
		prescription = make_prescription()
		hsr = make_copayment_request(prescription, cash_invoiced=1)
		frappe.get_cached_doc(prescription.doctype, prescription.name)

		prescription.radiology_examination_created = 1
		prescription.db_update()

		with patch(CREATE_RADIOLOGY) as create_radiology:
			invoice_cash_row(hsr)

		self.assertEqual(create_radiology.call_args.args[1].radiology_examination_created, 1)


class TestNHIFClaimCopayment(FrappeTestCase):
	def claim_with(self, percent_covered):
		claim = frappe.new_doc("NHIF Patient Claim")
		hsr_row = frappe._dict(
			insurance_company="NHIF",
			percent_covered=percent_covered,
			service_name=TEMPLATE,
			qty=2,
			rate=10000,
		)
		claim.add_LRPMT_claim_item(hsr_row, frappe._dict())
		claim.calculate_totals()

		return claim

	def test_claims_only_the_nhif_share_of_a_copayment_item(self):
		claim = self.claim_with(80)

		self.assertEqual(claim.nhif_patient_claim_item[0].unit_price, 10000)
		self.assertEqual(claim.nhif_patient_claim_item[0].amount_claimed, 16000)
		self.assertEqual(claim.total_amount, 16000)

	def test_claims_full_amount_of_a_fully_covered_item(self):
		self.assertEqual(self.claim_with(100).total_amount, 20000)

	def test_item_without_percent_is_claimed_in_full(self):
		self.assertEqual(self.claim_with(None).total_amount, 20000)
