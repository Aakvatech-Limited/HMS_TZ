from frappe import _, throw
from frappe.utils import flt

from hms_tz.hms_tz.setup_screens.company_records import CompanyRecords


class Practitioner(CompanyRecords):
	"""Setup screen of the company's doctors, with the consultation fee and NHIF registration number.

	The schedule and consultation room are linked when the doctor is created, by the practitioner hook.
	"""

	doctype = "Healthcare Practitioner"
	company_field = "hms_tz_company"
	label = "doctor"
	plural_label = "doctors"
	extra_fields = {
		"middle_name": {},
		"last_name": {},
		"tz_mct_code": {"reqd": 1},
		"nhif_physician_qualification": {},
		"department": {},
		"mobile_phone": {},
		"op_consulting_charge_item": {
			"reqd": 1,
			"link_filters": [["Item", "is_stock_item", "=", 0], ["Item", "disabled", "=", 0]],
		},
		"op_consulting_charge": {"reqd": 1},
	}
	fixed_values = {"practitioner_role": "Doctor"}
	match_field = "tz_mct_code"

	def validate(self, doc):
		"""Bookings bill the consultation fee, so a doctor needs one above zero."""
		if flt(doc.op_consulting_charge) <= 0:
			throw(_("Set an Out Patient Consulting Charge above 0 for {0}.").format(doc.first_name))
