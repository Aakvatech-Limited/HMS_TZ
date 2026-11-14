import json

import frappe
import requests
from frappe.utils import cast
from frappe.utils.background_jobs import enqueue

from hms_tz.nhif.doctype.nhif_response_log.nhif_response_log import add_log

# Healthcare Facility fieldname -> NHIF GetFacilities key
FACILITY_FIELD_MAP = {
	"facility_name": "FacilityName",
	"facility_code": "FacilityCode",
	"facility_level_code": "FacilityLevelCode",
	"certification_no": "CertificationNo",
	"abbreviation_code": "AbbreviationCode",
	"classification": "Classification",
	"classification_id": "ClassificationID",
	"ward_code": "WardCode",
	"postal_address": "PostalAddress",
	"owner_code": "OwnerCode",
	"ownership_type_code": "OwnershipTypeCode",
	"pay_to_code": "PayToCode",
	"percent_sent": "PercentSent",
	"certification_application_date": "CertificationApplicationDate",
	"status": "Status",
	"has_eclaims": "HasEClaims",
	"send_amount_to_msd": "SendAmountToMSD",
	"key_contact": "KeyContact",
	"telephone_no": "TelephoneNo",
	"email_address": "EmailAddress",
	"website": "Website",
	"fax": "Fax",
	"longitude": "Longitude",
	"latitude": "Latitude",
}


@frappe.whitelist()
def enqueue_get_facilities(company):
	enqueue(
		method=get_facilities,
		job_name="get_facilities",
		queue="default",
		timeout=1800,
		is_async=True,
		company=company,
	)
	frappe.msgprint("Fetch Facilities via backaground job", alert=True)


def get_facilities(company=None):
	if not company:
		settings = frappe.db.get_all(
			"HMS TZ Setting",
			filters={"enable_nhif_api": 1},
			fields=["company"],
		)
		company = settings[0].company

	if not company:
		return

	settings_doc = frappe.get_cached_doc("HMS TZ Setting", company)

	token = settings_doc.get_nhif_token()

	url = f"{settings_doc.nhif_claim_url}/api/Facilities/GetFacilities"
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	r = requests.request("Get", url, headers=headers, timeout=180)
	if r.status_code != 200:
		add_log(
			request_type="GetFacilities",
			request_url=url,
			request_header=headers,
			request_body="",
			response_data=r.text,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype="Healthcare Facility",
		)

	else:
		data = json.loads(r.text)
		add_log(
			request_type="GetFacilities",
			request_url=url,
			request_header=headers,
			request_body="",
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype="Healthcare Facility",
		)

		if len(data) == 0:
			return

		for facility in data:
			if not facility.get("FacilityName"):
				continue

			try:
				if frappe.db.exists("Healthcare Facility", facility.get("FacilityName")):
					update_facility(facility)
				else:
					create_facility(facility)

			except Exception:
				traceback = frappe.get_traceback()
				frappe.log_error(
					title=f"Facility: {facility.get('FacilityName')}",
					message=traceback,
				)


def update_facility(facility):
	hf_doc = frappe.get_doc("Healthcare Facility", facility.get("FacilityName"))
	has_changed = False

	for fieldname, key in FACILITY_FIELD_MAP.items():
		value = facility.get(key)
		fieldtype = hf_doc.meta.get_field(fieldname).fieldtype

		# API values are untyped JSON ("2" vs 2, None vs 0); compare as the field's type
		# so unchanged facilities aren't re-saved (and versioned) on every sync
		if cast(fieldtype, hf_doc.get(fieldname)) != cast(fieldtype, value):
			hf_doc.set(fieldname, value)
			has_changed = True

	if has_changed:
		hf_doc.save(ignore_permissions=True)


def create_facility(record):
	hf_doc = frappe.new_doc("Healthcare Facility")
	for fieldname, key in FACILITY_FIELD_MAP.items():
		hf_doc.set(fieldname, record.get(key))

	hf_doc.insert(ignore_permissions=True)
