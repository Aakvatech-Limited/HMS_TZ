from urllib.parse import quote

import frappe
import requests
from frappe.utils import escape_html, getdate, nowdate

from hms_tz.nhif.doctype.nhif_response_log.nhif_response_log import add_log


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


@frappe.whitelist(methods=["GET"])
def get_registered_practitioners(company: str) -> list:
	"""Return the practitioners NHIF has registered at the facility of the company's token."""
	return get_nhif_practitioners_response(company, "/api/Practitioners", "GetPractitioners")


@frappe.whitelist(methods=["GET"])
def get_practitioner_details(company: str, practitioner_no: str) -> dict:
	"""Return the NHIF registration details of one practitioner at the facility of the company's token."""
	return get_nhif_practitioners_response(
		company,
		f"/api/Practitioners/details/{quote(practitioner_no, safe='')}",
		"GetPractitionerDetails",
	)


def get_nhif_practitioners_response(company: str, path: str, request_type: str):
	frappe.has_permission("Healthcare Practitioner", throw=True)

	settings_doc = frappe.get_cached_doc("HMS TZ Setting", company)
	url = f"{settings_doc.nhifservice_url}{path}"
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {settings_doc.get_nhif_token()}",
	}

	r = requests.request("Get", url, headers=headers, timeout=60)
	add_log(
		request_type=request_type,
		request_url=url,
		request_header=headers,
		request_body="",
		response_data=r.text,
		status_code=r.status_code,
		company=company,
		ref_doctype="Healthcare Practitioner",
	)

	if r.status_code != 200:
		try:
			message = r.json().get("message") or r.text
		except (ValueError, AttributeError):
			message = r.text

		frappe.throw(
			title="NHIF API Error",
			msg=f"<b>{escape_html(message)}</b><br><br>Status Code: {r.status_code}",
		)

	return r.json()
