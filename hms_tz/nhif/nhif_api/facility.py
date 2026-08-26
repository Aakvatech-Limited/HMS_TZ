import json

import frappe
import requests
from frappe.utils.background_jobs import enqueue

from hms_tz.nhif.doctype.nhif_response_log.nhif_response_log import add_log


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
	has_changed = False
	hf_doc = frappe.get_cached_doc("Healthcare Facility", facility.get("FacilityName"))

	if hf_doc.facility_name != facility.get("FacilityName"):
		has_changed = True
		hf_doc.facility_name = facility.get("FacilityName")

	if hf_doc.facility_code != facility.get("FacilityCode"):
		has_changed = True
		hf_doc.facility_code = facility.get("FacilityCode")

	if hf_doc.facility_level_code != facility.get("FacilityLevelCode"):
		has_changed = True
		hf_doc.facility_level_code = facility.get("FacilityLevelCode")

	if hf_doc.certification_no != facility.get("CertificationNo"):
		has_changed = True
		hf_doc.certification_no = facility.get("CertificationNo")

	if hf_doc.abbreviation_code != facility.get("AbbreviationCode"):
		has_changed = True
		hf_doc.abbreviation_code = facility.get("AbbreviationCode")

	if hf_doc.classification != facility.get("Classification"):
		has_changed = True
		hf_doc.classification = facility.get("Classification")

	if hf_doc.classification_id != facility.get("ClassificationID"):
		has_changed = True
		hf_doc.classification_id = facility.get("ClassificationID")

	if hf_doc.ward_code != facility.get("WardCode"):
		has_changed = True
		hf_doc.ward_code = facility.get("WardCode")

	if hf_doc.postal_address != facility.get("PostalAddress"):
		has_changed = True
		hf_doc.postal_address = facility.get("PostalAddress")

	if hf_doc.owner_code != facility.get("OwnerCode"):
		has_changed = True
		hf_doc.owner_code = facility.get("OwnerCode")

	if hf_doc.ownership_type_code != facility.get("OwnershipTypeCode"):
		has_changed = True
		hf_doc.ownership_type_code = facility.get("OwnershipTypeCode")

	if hf_doc.pay_to_code != facility.get("PayToCode"):
		has_changed = True
		hf_doc.pay_to_code = facility.get("PayToCode")

	if hf_doc.percent_sent != facility.get("PercentSent"):
		has_changed = True
		hf_doc.percent_sent = facility.get("PercentSent")

	if hf_doc.certification_application_date != facility.get("CertificationApplicationDate"):
		has_changed = True
		hf_doc.certification_application_date = facility.get("CertificationApplicationDate")

	if hf_doc.status != facility.get("Status"):
		has_changed = True
		hf_doc.status = facility.get("Status")

	if hf_doc.has_eclaims != facility.get("HasEClaims"):
		has_changed = True
		hf_doc.has_eclaims = facility.get("HasEClaims")

	if hf_doc.send_amount_to_msd != facility.get("SendAmountToMSD"):
		has_changed = True
		hf_doc.send_amount_to_msd = facility.get("SendAmountToMSD")

	if hf_doc.key_contact != facility.get("KeyContact"):
		has_changed = True
		hf_doc.key_contact = facility.get("KeyContact")

	if hf_doc.telephone_no != facility.get("TelephoneNo"):
		has_changed = True
		hf_doc.telephone_no = facility.get("TelephoneNo")

	if hf_doc.email_address != facility.get("EmailAddress"):
		has_changed = True
		hf_doc.email_address = facility.get("EmailAddress")

	if hf_doc.website != facility.get("Website"):
		has_changed = True
		hf_doc.website = facility.get("Website")

	if hf_doc.fax != facility.get("Fax"):
		has_changed = True
		hf_doc.fax = facility.get("Fax")

	if hf_doc.longitude != facility.get("Longitude"):
		has_changed = True
		hf_doc.longitude = facility.get("Longitude")

	if hf_doc.latitude != facility.get("Latitude"):
		has_changed = True
		hf_doc.latitude = facility.get("Latitude")

	if has_changed:
		hf_doc.save(ignore_permissions=True)
		hf_doc.reload()


def create_facility(record):
	hf_doc = frappe.new_doc("Healthcare Facility")
	hf_doc.facility_name = record.get("FacilityName")
	hf_doc.facility_code = record.get("FacilityCode")
	hf_doc.certification_no = record.get("CertificationNo")
	hf_doc.abbreviation_code = record.get("AbbreviationCode")
	hf_doc.postal_address = record.get("PostalAddress")
	hf_doc.ward_code = record.get("WardCode")
	hf_doc.classification_id = record.get("ClassificationID")
	hf_doc.classification = record.get("Classification")
	hf_doc.facility_level_code = record.get("FacilityLevelCode")
	hf_doc.ownership_type_code = record.get("OwnershipTypeCode")
	hf_doc.status = record.get("Status")
	hf_doc.has_eclaims = record.get("HasEClaims")
	hf_doc.owner_code = record.get("OwnerCode")
	hf_doc.pay_to_code = record.get("PayToCode")
	hf_doc.email_address = record.get("EmailAddress")
	hf_doc.telephone_no = record.get("TelephoneNo")
	hf_doc.website = record.get("Website")
	hf_doc.key_contact = record.get("KeyContact")
	hf_doc.fax = record.get("Fax")
	hf_doc.send_amount_to_msd = record.get("SendAmountToMSD")
	hf_doc.percent_sent = record.get("PercentSent")
	hf_doc.longitude = record.get("Longitude")
	hf_doc.latitude = record.get("Latitude")
	hf_doc.certification_application_date = record.get("CertificationApplicationDate")
	hf_doc.insert(ignore_permissions=True)
	hf_doc.reload()
	hf_doc.reload()
