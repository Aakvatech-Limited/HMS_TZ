import frappe
from frappe.utils import getdate, nowdate


@frappe.whitelist()
def get_nhif_practitioner_login_status():
	practitioner_details = frappe.get_cached_value(
		"Healthcare Practitioner",
		{"user_id": frappe.session.user},
		["hms_tz_company", "date_loggedin_to_nhif"],
		as_dict=True,
	)
	if not practitioner_details:
		return {"show_login": False, "show_logout": False}

	hms_tz_details = frappe.get_cached_value(
		"HMS TZ Setting",
		practitioner_details.hms_tz_company,
		["validate_nhif_practitioner_attendance", "enable_nhif_api"],
		as_dict=True,
	)

	if not hms_tz_details.enable_nhif_api:
		return {"show_login": False, "show_logout": False, "show_poc": False}

	if not hms_tz_details.validate_nhif_practitioner_attendance:
		return {"show_login": False, "show_logout": False, "show_poc": True}

	if not practitioner_details.date_loggedin_to_nhif or (
		getdate(practitioner_details.date_loggedin_to_nhif) != getdate(nowdate())
	):
		return {"show_login": True, "show_logout": False, "show_poc": False}

	elif practitioner_details.date_loggedin_to_nhif and (
		getdate(practitioner_details.date_loggedin_to_nhif) == getdate(nowdate())
	):
		return {"show_login": False, "show_logout": True, "show_poc": True}
