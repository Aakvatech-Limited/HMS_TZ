import json

import frappe
import requests
from frappe.utils import nowdate

from hms_tz.nhif.doctype.nhif_response_log.nhif_response_log import add_log


@frappe.whitelist()
def login_practitioner(fingerprint, fpcode, settings_doc=None):
	practitioner = frappe.get_cached_value(
		"Healthcare Practitioner",
		{"user_id": frappe.session.user},
		["tz_mct_code", "national_id", "name", "hms_tz_company"],
		as_dict=True,
	)
	if not practitioner:
		frappe.throw(
			f"No healthcare practitioner found for user id: {frappe.session.user}, Please set user id to healthcare practitioner"
		)

	if not settings_doc:
		settings_doc = frappe.get_cached_doc("HMS TZ Setting", practitioner.hms_tz_company)

	if not settings_doc.enable_nhif_api:
		frappe.msgprint("NHIF API is disabled")
		return False

	if not practitioner.national_id:
		frappe.throw(f"Please set National ID for a practitioner: <b>{practitioner.name}</b>")

	payload = {
		"nationalID": practitioner.national_id,
		"practitionerNo": practitioner.tz_mct_code,
		"biometricMethod": "FINGERPRINT",  # "NONE",
		"fpCode": fpcode,
		"imageData": fingerprint,
	}

	payload = json.dumps(payload)

	url = f"{settings_doc.nhifservice_url}/api/Attendance/LoginPractitioner"

	token = settings_doc.get_nhif_token()

	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	r = requests.request("Post", url, headers=headers, data=payload, timeout=60)
	data = json.loads(r.text) if r.text else {}

	if r.status_code == 200:
		add_log(
			request_type="LoginPractitioner",
			request_url=url,
			request_header=headers,
			request_body=payload,
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype="Healthcare Practitioner",
			ref_docname=practitioner.name,
		)
		frappe.db.set_value(
			"Healthcare Practitioner",
			{"national_id": practitioner.national_id},
			"date_loggedin_to_nhif",
			nowdate(),
			update_modified=False,
		)
		return data

	else:
		add_log(
			request_type="LoginPractitioner",
			request_url=url,
			request_header=headers,
			request_body=payload,
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype="Healthcare Practitioner",
			ref_docname=practitioner.name,
		)
		frappe.msgprint(
			title="NHIF API Error",
			msg=f"Failed to LoginPractitioner<br><br>Status Code: {r.status_code}<br>Response: <b>{data.get('errors') or data.get('message')}<b>",
			indicator="red",
		)
		return "Error"


@frappe.whitelist()
def logout_practitioner(settings_doc=None):
	practitioner = frappe.get_cached_value(
		"Healthcare Practitioner",
		{"user_id": frappe.session.user},
		["tz_mct_code", "national_id", "name", "hms_tz_company"],
		as_dict=True,
	)
	if not practitioner:
		frappe.throw(
			f"No healthcare practitioner found for user id: {frappe.session.user}, Please set user id to healthcare practitioner"
		)

	if not settings_doc:
		settings_doc = frappe.get_cached_doc("HMS TZ Setting", practitioner.hms_tz_company)

	if not settings_doc.enable_nhif_api:
		frappe.msgprint("NHIF API is disabled")
		return False

	if not practitioner.national_id:
		frappe.throw(f"Please set National ID for a practitioner: <b>{practitioner.name}</b>")

	payload = {
		"practitionerNo": practitioner.tz_mct_code,
		"facilityCode": settings_doc.facility_code,
	}

	payload = json.dumps(payload)

	url = f"{settings_doc.nhifservice_url}/api/Attendance/LogoutPractitioner"
	# url = f"{settings_doc.nhifservice_url}/api/Attendance/LogoutPractitioner?facilityCode={settings_doc.facility_code}&practitionerNo={practitioner.tz_mct_code}"

	token = settings_doc.get_nhif_token()

	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	# r = requests.request("Post", url, headers=headers,timeout=60)
	r = requests.request("Post", url, headers=headers, data=payload, timeout=60)
	data = json.loads(r.text) if r.text else {}

	if r.status_code == 200:
		add_log(
			request_type="LogoutPractitioner",
			request_url=url,
			request_header=headers,
			request_body=payload,
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype="Healthcare Practitioner",
			ref_docname=practitioner.name,
		)
		frappe.db.set_value(
			"Healthcare Practitioner",
			{"national_id": practitioner.national_id},
			"date_loggedin_to_nhif",
			"",
			update_modified=False,
		)
		return data

	else:
		add_log(
			request_type="LogoutPractitioner",
			request_url=url,
			request_header=headers,
			request_body=payload,
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype="Healthcare Practitioner",
			ref_docname=practitioner.name,
		)
		frappe.msgprint(
			title="NHIF API Error",
			msg=f"Failed to LogoutPractitioner<br><br>Status Code: {r.status_code}<br>Response: <b>{data.get('errors') or data.get('message')}<b>",
			indicator="red",
		)
		return "Error"
