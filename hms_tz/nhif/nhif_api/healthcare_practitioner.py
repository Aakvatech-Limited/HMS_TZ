from urllib.parse import quote

import frappe
import requests
from frappe.utils import escape_html, get_fullname, getdate, nowdate

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
	return make_nhif_practitioners_request(company, "/api/Practitioners", "GetPractitioners")


@frappe.whitelist(methods=["GET"])
def get_practitioner_details(company: str, practitioner_no: str) -> dict:
	"""Return the NHIF registration details of one practitioner at the facility of the company's token."""
	return make_nhif_practitioners_request(
		company,
		f"/api/Practitioners/details/{quote(practitioner_no, safe='')}",
		"GetPractitionerDetails",
	)


@frappe.whitelist(methods=["POST"])
def register_practitioner(practitioner: str) -> dict:
	"""Register the practitioner's MCT number with NHIF at the facility of the practitioner's company."""
	doc = get_practitioner_to_update(practitioner)
	payload = {
		"practitionerNo": doc.tz_mct_code,
		"facilityCode": frappe.get_cached_value("HMS TZ Setting", doc.hms_tz_company, "facility_code"),
		"createdBy": get_fullname(frappe.session.user),
	}
	return make_nhif_practitioners_request(
		doc.hms_tz_company, "/api/Practitioners/register", "RegisterPractitioner", payload
	)


@frappe.whitelist(methods=["POST"])
def terminate_practitioner(practitioner: str, termination_reasons: str) -> dict:
	"""Terminate the practitioner's NHIF registration at the facility of the practitioner's company."""
	doc = get_practitioner_to_update(practitioner)
	if not termination_reasons:
		frappe.throw("Please set the termination reasons")

	payload = {
		"practitionerNo": doc.tz_mct_code,
		"facilityCode": frappe.get_cached_value("HMS TZ Setting", doc.hms_tz_company, "facility_code"),
		"terminatedBy": get_fullname(frappe.session.user),
		"terminationReasons": termination_reasons,
	}
	return make_nhif_practitioners_request(
		doc.hms_tz_company, "/api/Practitioners/terminate", "TerminatePractitioner", payload
	)


def get_practitioner_to_update(practitioner: str):
	doc = frappe.get_doc("Healthcare Practitioner", practitioner)
	doc.check_permission("write")
	if not doc.tz_mct_code:
		frappe.throw(f"Please set MCT Code for practitioner: <b>{doc.name}</b>")

	return doc


def make_nhif_practitioners_request(company: str, path: str, request_type: str, payload: dict | None = None):
	frappe.has_permission("Healthcare Practitioner", throw=True)

	settings_doc = frappe.get_cached_doc("HMS TZ Setting", company)
	url = f"{settings_doc.nhifservice_url}{path}"
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {settings_doc.get_nhif_token()}",
	}

	body = frappe.as_json(payload) if payload else ""
	r = requests.request("Post" if payload else "Get", url, headers=headers, data=body, timeout=60)
	add_log(
		request_type=request_type,
		request_url=url,
		request_header=headers,
		request_body=body,
		response_data=r.text,
		status_code=r.status_code,
		company=company,
		ref_doctype="Healthcare Practitioner",
	)

	try:
		data = r.json() if r.text else {}
	except ValueError:
		data = {"message": r.text}

	if r.status_code != 200:
		message = data.get("message") if isinstance(data, dict) else None
		frappe.throw(
			title="NHIF API Error",
			msg=f"<b>{escape_html(message or r.text)}</b><br><br>Status Code: {r.status_code}",
		)

	return data
