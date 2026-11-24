import frappe
from frappe import _

from hms_tz.hms_tz.setup_screens.company_records import CompanyRecords


class CoveragePlan(CompanyRecords):
	"""Setup screen of the company's coverage plans, where the manager confirms and changes them.

	The insurer and price list filters come from the DocType JSON link_filters. A plan is named by its
	plan name, so the name is fixed once the plan exists. The price list may stay empty until an NHIF or
	Jubilee price download creates it.
	"""

	doctype = "Healthcare Insurance Coverage Plan"
	label = "coverage plan"
	plural_label = "coverage plans"
	extra_fields = {
		"coverage_plan_name": {"reqd": 1, "set_only_once": 1},
		"insurance_company": {"reqd": 1},
		"is_active": {},
		"price_list": {},
		"secondary_price_list": {},
		"nhif_scheme_id": {},
		"has_followup_charges": {},
		"has_fasttrack_charges": {},
	}
	match_field = "coverage_plan_name"

	def validate(self, doc):
		"""The insurer filter only limits the list; an imported row may still name another company's insurer."""
		insurer_company = frappe.db.get_value(
			"Healthcare Insurance Company", doc.insurance_company, "company"
		)
		if insurer_company != self.company:
			frappe.throw(
				_("Insurance company {0} is not one of the insurance companies of {1}.").format(
					doc.insurance_company, self.company
				)
			)
