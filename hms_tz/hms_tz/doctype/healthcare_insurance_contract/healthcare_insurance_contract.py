# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate


class HealthcareInsuranceContract(Document):
	def validate(self):
		if self.is_active:
			contract = frappe.db.exists(
				"Healthcare Insurance Contract",
				{
					"insurance_company": self.insurance_company,
					"start_date": ("<=", getdate(nowdate())),
					"end_date": (">=", getdate(nowdate())),
					"is_active": 1,
				},
			)
			if contract and contract != self.name:
				frappe.throw(_(f"There exist an active contract with this insurance company {contract}"))
