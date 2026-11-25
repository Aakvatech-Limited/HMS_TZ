import frappe
from frappe import _

from hms_tz.hms_tz.setup_screens.company_records import CompanyRecords

ITEM_GROUP_FILTERS = [["Item Group", "is_group", "=", 0]]


class HealthcareTemplate(CompanyRecords):
	"""Setup screen of a healthcare template that all companies share, such as Lab Test Template.

	A template holds one company options row per company: the service unit where the company gives the
	service, and whether the company offers it. The screen shows and saves the screen company's row, and the
	list shows every template, so templates that have no row for the company yet can be completed here.
	"""

	company_field = None
	company_table = "company_options"
	company_table_fields = {
		"service_unit": {
			"link_filters": [
				["Healthcare Service Unit", "company", "=", "eval: doc.company"],
				["Healthcare Service Unit", "is_group", "=", 0],
			]
		},
		"is_not_available": {},
	}
	page_length = 500

	def validate(self, doc):
		"""The company's row names one of the company's service units; the list filter only guides the picker."""
		row = next(row for row in doc.company_options if row.company == self.company)
		if frappe.db.get_value("Healthcare Service Unit", row.service_unit, "company") != self.company:
			frappe.throw(
				_("Service unit {0} is not one of the service units of {1}.").format(
					row.service_unit, self.company
				)
			)
