# Copyright (c) 2022, Aakvatech and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document
from frappe.utils import flt, nowdate

from hms_tz.nhif.nhif_api.patient_claim import get_submitted_claims


class NHIFClaimReconciliation(Document):
	def before_save(self):
		self.posting_date = nowdate()
		self.get_erp_monthly_claims()

	def validate_reqd_fields(self):
		for fieldname in ["company", "claim_year", "claim_month"]:
			if not self.get(fieldname):
				frappe.throw(frappe.bold(f"{fieldname} is required"))

	def before_submit(self):
		self.validate_reqd_fields()
		self.posting_date = nowdate()
		get_submitted_claims(self)

	def get_erp_monthly_claims(self):
		"""
		Get all claims for the month
		"""
		if not self.claim_month or not self.claim_year:
			frappe.throw("Please set the claim month and year")

		filters = {
			"docstatus": 1,
			"company": self.company,
			"claim_month": self.claim_month,
			"claim_year": self.claim_year,
		}

		claims = frappe.db.get_all(
			"NHIF Patient Claim",
			filters=filters,
			fields=["name", "total_amount"],
		)
		if len(claims) == 0:
			return

		erp_total_claims = 0
		for claim in claims:
			erp_total_claims += flt(claim.total_amount)

		self.erp_number_of_submitted_claims = len(claims)
		self.erp_total_amount_claimed = erp_total_claims
