from hms_tz.hms_tz.insurance_actions import InsuranceActions
from hms_tz.hms_tz.setup_screens.company_records import CompanyRecords


class InsuranceCompany(CompanyRecords):
	"""Setup screen of the company's insurers, where the manager confirms and changes them.

	The account fields take their company filters from the DocType JSON link_filters. The NHIF and Jubilee
	actions of the insurer form are offered as dropdowns for the connections switched on.
	"""

	doctype = "Healthcare Insurance Company"
	label = "insurance company"
	plural_label = "insurance companies"
	extra_fields = {
		"default_price_list": {
			"link_filters": [["Price List", "selling", "=", 1], ["Price List", "enabled", "=", 1]],
		},
		"no_of_days_for_follow_up": {},
		"hms_tz_has_price_discount": {},
		"hms_tz_price_discount": {},
		"disabled": {},
	}
	match_field = "insurance_company_name"

	@property
	def action_groups(self):
		return InsuranceActions(self.company).groups

	def run_action(self, key):
		return InsuranceActions(self.company).run(key)
