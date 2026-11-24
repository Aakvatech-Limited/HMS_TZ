import frappe
from frappe import _

from hms_tz.hms_tz.setup_screens.company_records import CompanyRecords


class Coverage(CompanyRecords):
	"""Setup screen of the company's Healthcare Service Insurance Coverages: which plan covers which service.

	A company can hold tens of thousands of coverages, so the list is filtered by service type, service and
	plan and shows at most page_length rows. The plan filter comes from the DocType JSON link_filters.
	"""

	doctype = "Healthcare Service Insurance Coverage"
	label = "coverage"
	plural_label = "coverages"
	extra_fields = {
		"is_active": {},
		"approval_mandatory_for_claim": {},
		"start_date": {},
		"has_copayment": {},
		"maximum_quantity": {},
		"maximum_quantity_outpatient": {},
		"maximum_quantity_inpatient": {},
	}
	list_filters = ("healthcare_service", "healthcare_service_template", "healthcare_insurance_coverage_plan")
	page_length = 500

	def validate(self, doc):
		"""The plan filter only limits the list; an imported row may still name another company's plan."""
		plan_company = frappe.db.get_value(
			"Healthcare Insurance Coverage Plan", doc.healthcare_insurance_coverage_plan, "company"
		)
		if plan_company != self.company:
			frappe.throw(
				_("Coverage plan {0} is not one of the coverage plans of {1}.").format(
					doc.healthcare_insurance_coverage_plan, self.company
				)
			)

	def get_existing_name(self, values):
		"""The plan's coverage of the row's service, so a re-import changes it."""
		plan = values.get("healthcare_insurance_coverage_plan")
		template = values.get("healthcare_service_template")
		if not (plan and template):
			return None
		return frappe.db.get_value(
			self.doctype,
			{
				**self.filters,
				"healthcare_insurance_coverage_plan": plan,
				"healthcare_service_template": template,
			},
		)
