# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document
from frappe.query_builder import DocType


class HealthcareInsurancePaymentRequest(Document):
	pass


@frappe.whitelist()
def get_claim_item(insurance_company, from_date=False, to_date=False, posting_date_type=""):
	claim = DocType("Healthcare Insurance Claim")
	posting_date = (
		claim.claim_posting_date
		if posting_date_type == "Claim Posting Date"
		else claim.sales_invoice_posting_date
	)

	query = (
		frappe.qb.from_(claim)
		.select(
			claim.name,
			claim.patient,
			claim.healthcare_service_type,
			claim.service_template,
			claim.sales_invoice,
			claim.discount,
			claim.coverage,
			claim.coverage_amount,
		)
		.where(
			(claim.insurance_company == insurance_company)
			& (claim.docstatus == 1)
			& (claim.claim_status == "Approved")
		)
	)

	if from_date:
		query = query.where(posting_date >= from_date)

	if to_date:
		query = query.where(posting_date <= to_date)

	claim_list = query.run(as_dict=True)
	if claim_list:
		return claim_list
	return False
