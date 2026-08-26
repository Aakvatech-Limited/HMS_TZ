# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document


class HealthcareServiceInsuranceCoverage(Document):
	def validate(self):
		self.validate_service_overlap()

	def validate_service_overlap(self):
		service_insurance_coverages = frappe.db.get_list(
			"Healthcare Service Insurance Coverage",
			{
				"healthcare_insurance_coverage_plan": self.healthcare_insurance_coverage_plan,
				"is_active": 1,
				"healthcare_service_template": self.healthcare_service_template,
				"name": ["!=", self.name],
				"end_date": ["<=", self.end_date],
			},
		)
		if len(service_insurance_coverages) > 0:
			frappe.throw(
				_(
					f"A Service {frappe.bold(self.healthcare_service_template)} already activated for this coverage plan {frappe.bold(self.healthcare_insurance_coverage_plan)}"
				),
				title=_("Changes Not Allowed"),
			)
