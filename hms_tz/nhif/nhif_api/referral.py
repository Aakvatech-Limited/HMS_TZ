import json

import frappe
import requests
from frappe.utils import get_datetime, get_fullname

from hms_tz.nhif.doctype.nhif_response_log.nhif_response_log import add_log


def create_referral(doc):
	"""
	Creates a referral to NHIF based on the type of referral.
	"""

	if doc.referral_type == "Form 2C/2E":
		return create_service_referral(doc)
	elif doc.referral_type == "Treatment":
		return create_treatment_referral(doc)
	else:
		frappe.throw("Invalid Referral Type")


def create_treatment_referral(doc):
	payload = {
		"cardNo": doc.card_no or doc.national_id,
		"authorizationNo": doc.authorization_no,
		"fullName": doc.patient_name,
		"gender": doc.gender,
		"referralDate": get_datetime(doc.referral_date).isoformat(),
		"practitionerNo": doc.practitioner_no,
		"practitionersRemarks": doc.reason_for_referral,
		"fromFacilityCode": doc.source_facility_code,
		"toFacilityCode": doc.referred_to_facility_code,
		"diagnosis": ", ".join([d.disease_code for d in doc.diagnosis]),
		"createdBy": get_fullname(frappe.session.user),
	}

	payload = json.dumps(payload)

	settings_doc = frappe.get_cached_doc("HMS TZ Setting", doc.source_facility)

	token = settings_doc.get_nhif_token()

	url = f"{settings_doc.nhifservice_url}/api/Referrals/CreateTreatmentReferral"
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	r = requests.request("Post", url, data=payload, headers=headers, timeout=120)
	if r.status_code != 200:
		data = json.loads(r.text)
		add_log(
			request_type="CreateTreatmentReferral",
			request_url=url,
			request_header=headers,
			request_body=payload,
			response_data=r.text,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype=doc.doctype,
			ref_docname=doc.name,
		)
		doc.add_comment(
			comment_type="Comment",
			text=f"Failed to create treatment referral!<br><br><b>Message from NHIF:</b><br>{data.get('message')}",
		)
		frappe.db.commit()

		frappe.throw(str(data.get("message")))

	else:
		data = json.loads(r.text)
		add_log(
			request_type="CreateTreatmentReferral",
			request_url=url,
			request_header=headers,
			request_body=payload,
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype=doc.doctype,
			ref_docname=doc.name,
		)

		doc.referral_submitted_by = get_fullname(frappe.session.user)
		doc.referral_no = data.get("ReferralNo")
		doc.referral_id = data.get("ReferralID")
		doc.referral_status = "Success"

		doc.add_comment(
			comment_type="Comment",
			text=f"Treatment Referral created successfully!<br><br><b>Message from NHIF:</b><br>{data.get('ReferralID')}",
		)

		return True


def create_service_referral(doc):
	diseases = []
	services = []
	for disease in doc.diagnosis:
		diseases.append(
			{
				"diseaseCode": get_disease_code(disease.disease_code),
				"status": disease.status,
			}
		)

	for service in doc.services:
		services.append(
			{
				"itemCode": service.item_code,
				"itemQuantity": service.qty,
				"approvalRefNo": service.approval_ref_no,
				"notes": service.notes,
			}
		)

	payload = {
		"authorizationNo": doc.authorization_no,
		"firstName": doc.first_name,
		"lastName": doc.last_name,
		"gender": doc.gender,
		"dateOfBirth": str(doc.dob),
		"telephoneNo": doc.mobile_no,
		"patientFileNo": doc.patient,
		"practitionerNo": doc.practitioner_no,
		"attendanceDate": str(doc.attendance_date),
		"patientTypeCode": doc.patient_type_code,
		"facilityCode": doc.referred_to_facility_code,
		"createdBy": get_fullname(frappe.session.user),
		"diseases": diseases,
		"services": services,
	}

	payload = json.dumps(payload)

	settings_doc = frappe.get_cached_doc("HMS TZ Setting", doc.source_facility)

	token = settings_doc.get_nhif_token()

	url = f"{settings_doc.nhifservice_url}/api/Referrals/CreateServiceReferral"
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	r = requests.request("Post", url, data=payload, headers=headers, timeout=120)
	if r.status_code != 200:
		data = json.loads(r.text)
		add_log(
			request_type="CreateServiceReferral",
			request_url=url,
			request_header=headers,
			request_body=payload,
			response_data=r.text,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype=doc.doctype,
			ref_docname=doc.name,
		)

		doc.add_comment(
			comment_type="Comment",
			text=f"Failed to create service referral!<br><br><b>Message from NHIF:</b><br>{data.get('message')}",
		)
		frappe.db.commit()
		frappe.throw(str(data.get("message")))

	else:
		data = json.loads(r.text)
		add_log(
			request_type="CreateServiceReferral",
			request_url=url,
			request_header=headers,
			request_body=payload,
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype=doc.doctype,
			ref_docname=doc.name,
		)

		doc.referral_submitted_by = get_fullname(frappe.session.user)
		doc.referral_no = data.get("ReferralNo") or data.get("ReferrralNo")
		doc.referral_id = data.get("ReferralID")
		doc.referral_status = "Success"

		doc.add_comment(
			comment_type="Comment",
			text=f"Service Referral created successfully!<br><br><b>Message from NHIF:</b><br>{data.get('ReferralID')}",
		)

		return True


@frappe.whitelist()
def update_referral(ref_doctype, ref_docname):
	"""
	Update referral.
	"""
	doc = frappe.get_cached_doc(ref_doctype, ref_docname)

	payload = {
		"referralNo": doc.referral_no,
		"practitionerNo": doc.practitioner_no,
		"practitionersRemarks": doc.reason_for_referral,
		"toFacilityCode": doc.referred_to_facility_code,
		"createdBy": get_fullname(frappe.session.user),
	}

	payload = json.dumps(payload)

	settings_doc = frappe.get_cached_doc("HMS TZ Setting", doc.source_facility)

	token = settings_doc.get_nhif_token()

	url = f"{settings_doc.nhifservice_url}/api/Referrals/UpdateReferral"
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	r = requests.request("Post", url, data=payload, headers=headers, timeout=120)
	if r.status_code != 200:
		data = json.loads(r.text)
		add_log(
			request_type="UpdateReferral",
			request_url=url,
			request_header=headers,
			request_body=payload,
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype=doc.doctype,
			ref_docname=doc.name,
		)
		doc.add_comment(
			comment_type="Comment",
			text=f"Failed to update referral!<br><br><b>Message from NHIF:</b><br>{data.get('reasonPhrase')}",
		)
		doc.reload()
		frappe.msgprint(str(data.get("reasonPhrase")))

	else:
		data = json.loads(r.text)
		add_log(
			request_type="UpdateReferral",
			request_url=url,
			request_header=headers,
			request_body=payload,
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype=doc.doctype,
			ref_docname=doc.name,
		)

		# TODO: update response values to Healthcare Referral doc

		doc.referral_updated_by = get_fullname(frappe.session.user)
		doc.save(ignore_permissions=True)
		doc.reload()

		return True


def acknowledge_referral(company, referral_no):
	settings_doc = frappe.get_cached_doc("HMS TZ Setting", company)

	token = settings_doc.get_nhif_token()

	url = f"{settings_doc.nhifservice_url}/api/Referrals/AcknowledgeServiceReferral?referralNo={referral_no}"
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	r = requests.request("Get", url, headers=headers, timeout=120)
	if r.status_code != 200:
		data = json.loads(r.text)
		add_log(
			request_type="AcknowledgeServiceReferral",
			request_url=url,
			request_header=headers,
			request_body="",
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
		)
		frappe.throw(str(data.get("reasonPhrase")))

	else:
		data = json.loads(r.text)
		add_log(
			request_type="AcknowledgeServiceReferral",
			request_url=url,
			request_header=headers,
			request_body="",
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
		)
		create_healthcare_referral(data)


def create_healthcare_referral(data):
	referral_doc = frappe.new_doc("Healthcare Referral")
	referral_doc.referral_no = data.get("ReferralNo")
	referral_doc.referral_id = data.get("ReferralID")
	referral_doc.referral_status = "Success"
	referral_doc.save(ignore_permissions=True)
	referral_doc.reload()
	return True


def get_disease_code(code):
	# Convert the ICD code of CDC to NHIF
	disease_code = None
	if code and len(code) > 3 and "." not in code:
		disease_code = code[:3] + "." + (code[3:4] or "0")
	elif code and len(code) <= 5 and "." in code:
		disease_code = code
	elif code and len(code) > 5 and "." in code:
		disease_code = code[:6]
	else:
		disease_code = code[:3]

	return disease_code
