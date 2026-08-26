# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.model.document import Document
from frappe.utils import flt, get_fullname, now_datetime

from hms_tz.nhif.nhif_api.patient_claim import submit_monthly_claim


class NHIFMonthlyClaim(Document):
	def before_save(self):
		self.posting_date = now_datetime()
		self.get_erp_monthly_claims()

	def before_submit(self):
		self.validate_reqd_fields()
		self.validate_claim_detail()
		self.posting_date = now_datetime()
		self.submitted_by = get_fullname(frappe.session.user)
		submit_monthly_claim(self)

	def validate_reqd_fields(self):
		for fieldname in ["company", "claim_year", "claim_month"]:
			if not self.get(fieldname):
				frappe.throw(frappe.bold(f"{fieldname} is required"))

	def validate_claim_detail(self):
		if self.folio_submitted == 0:
			frappe.throw(f"No claims submitted for this month: {self.claim_month}")

		if self.total_amount_claimed == 0:
			frappe.throw(f"No claims submitted for this month: {self.claim_month}")

	def get_erp_monthly_claims(self):
		"""
		Get all claims for the month
		"""

		if self.folio_submitted and self.total_amount_claimed:
			return

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

		self.folio_submitted = len(claims)
		self.total_amount_claimed = erp_total_claims


@frappe.whitelist()
def submit_monthly_claim_via_api(data):
	"""
	Submit the monthly claim to NHIF API
	"""

	data = json.loads(data)
	nmc_doc = frappe.new_doc("NHIF Monthly Claim")
	nmc_doc.update(data)
	nmc_doc.save(ignore_permissions=True)
	nmc_doc.reload()

	nmc_doc.submit()
	return nmc_doc.name
