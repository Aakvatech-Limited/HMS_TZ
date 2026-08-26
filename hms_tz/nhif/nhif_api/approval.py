import base64
import json

import frappe
import requests
from frappe.core.utils import html2text
from frappe.query_builder import DocType
from frappe.utils import cint, get_datetime, get_fullname

from hms_tz.hms_tz.doctype.healthcare_service_request.healthcare_service_request import (
	get_item_rate,
	get_item_refcode,
)
from hms_tz.nhif.doctype.nhif_response_log.nhif_response_log import add_log
from hms_tz.nhif.nhif_api.referral import get_disease_code


@frappe.whitelist()
def get_service_approval(
	ref_doctype,
	ref_docname,
	service_type,
	service_name,
	start_date,
	expire_date,
	clinical_notes,
	qty=1,
	item_code=None,
	reference_name=None,
	reference_doctype=None,
	supportive_document="",
):
	if not ref_doctype or not ref_docname:
		frappe.throw("Document Type and Document Name are required")

	doc = frappe.get_cached_doc(ref_doctype, ref_docname)

	settings_doc = frappe.get_cached_doc("HMS TZ Setting", doc.company)

	if not settings_doc.enable_nhif_api:
		frappe.msgprint("NHIF API is disabled")
		return {
			"status": "error",
		}

	payload = get_request_approval_payload(
		doc,
		settings_doc.facility_code,
		service_type,
		service_name,
		start_date,
		expire_date,
		clinical_notes,
		qty,
		item_code=item_code,
		reference_name=reference_name,
		reference_doctype=reference_doctype,
		supportive_document=supportive_document,
	)

	payload = json.dumps(payload)

	token = settings_doc.get_nhif_token()

	url = f"{settings_doc.nhifservice_url}/api/Approvals/RequestApproval"
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	r = requests.request("POST", url, headers=headers, data=payload, timeout=120)

	if r.status_code != 200:
		add_log(
			request_type="RequestApproval",
			request_url=url,
			request_header=headers,
			request_body=payload,
			response_data=r.text,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype=ref_doctype,
			ref_docname=ref_docname,
		)

		data = json.loads(r.text) if r.text else {}

		doc.add_comment(
			comment_type="Comment",
			text=f"Service approval request failed<br><br>Status Code: {r.status_code}<br>NHIF Response: <b>{data.get('message') or r.text}<b>",
		)
		doc.reload()
		frappe.msgprint(
			title="NHIF API Error",
			msg=f"Request Approval Failed<br><br>Status Code: {r.status_code}<br>NHIF Response: <b>{data.get('message') or r.text}<b>",
			indicator="red",
		)
		if r.text:
			return {
				"status": "error",
			}

	else:
		data = json.loads(r.text)

		add_log(
			request_type="RequestApproval",
			request_url=url,
			request_header=headers,
			request_body=payload,
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype=ref_doctype,
			ref_docname=ref_docname,
		)

		return set_service_approval(
			doc,
			data,
			item_code=item_code,
			reference_name=reference_name,
			reference_doctype=reference_doctype,
		)


@frappe.whitelist()
def get_approval_status(ref_doctype, ref_docname, dni_id=None):
	doc = frappe.get_cached_doc(ref_doctype, ref_docname)

	settings_doc = frappe.get_cached_doc("HMS TZ Setting", doc.company)

	if not settings_doc.enable_nhif_api:
		frappe.msgprint("NHIF API is disabled")
		return {
			"status": "error",
		}

	appointment = doc.get("appointment") or doc.get("hms_tz_appointment_no")

	authorization_no = ""
	if doc.doctype == "Delivery Note":
		authorization_no = doc.get("authorization_number")
	else:
		authorization_no = frappe.get_cached_value("Patient Appointment", appointment, "authorization_number")

	url = f"{settings_doc.nhifservice_url}/api/Approvals/GetApprovalStatus?authorizationNo={authorization_no}"

	token = settings_doc.get_nhif_token()

	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	r = requests.request("GET", url, headers=headers, timeout=120)
	if r.status_code != 200:
		add_log(
			request_type="GetApprovalStatus",
			request_url=url,
			request_header=headers,
			request_body="",
			response_data=r.text,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype=ref_doctype,
			ref_docname=ref_docname,
		)
		return {
			"status": "error",
		}
	else:
		data = json.loads(r.text)
		add_log(
			request_type="GetApprovalStatus",
			request_url=url,
			request_header=headers,
			request_body="",
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype=ref_doctype,
			ref_docname=ref_docname,
		)

		return update_approval_status(doc, appointment, data, dni_id=dni_id)


@frappe.whitelist()
def update_service_approval(
	ref_doctype,
	ref_docname,
	service_type,
	service_name,
	qty=1,
	item_row={},
	reference_name=None,
	reference_doctype=None,
	item_authorization_id=None,
	service_authorization_id=None,
):
	if not ref_doctype or not ref_docname:
		frappe.throw("Document Type and Document Name are required")

	doc = frappe.get_cached_doc(ref_doctype, ref_docname)

	settings_doc = frappe.get_cached_doc("HMS TZ Setting", doc.company)

	if not settings_doc.enable_nhif_api:
		frappe.msgprint("NHIF API is disabled")
		return False

	appointment = doc.get("appointment") or doc.get("hms_tz_appointment_no")

	payload = get_update_approval_payload(
		doc,
		settings_doc.facility_code,
		service_type,
		service_name,
		appointment,
		qty,
		item_row=item_row,
		item_authorization_id=item_authorization_id,
		service_authorization_id=service_authorization_id,
	)

	payload = json.dumps(payload)

	token = settings_doc.get_nhif_token()

	url = f"{settings_doc.nhifservice_url}/api/Approvals/UpdateApprovalRequest"

	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	r = requests.request("POST", url, headers=headers, data=payload, timeout=120)

	if r.status_code != 200:
		add_log(
			request_type="UpdateApprovalRequest",
			request_url=url,
			request_header=headers,
			request_body=payload,
			response_data=r.text,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype=ref_doctype,
			ref_docname=ref_docname,
		)

		data = json.loads(r.text) if r.text else {}

		doc.add_comment(
			comment_type="Comment",
			text=f"Update approval request failed<br><br>Status Code: {r.status_code}<br>NHIF Response: <b>{data.get('message') or data}<b>",
		)
		doc.reload()
		frappe.msgprint(
			title="NHIF API Error",
			msg=f"Request Approval Failed<br><br>Status Code: {r.status_code}<br>NHIF Response: <b>{data.get('message') or data}<b>",
			indicator="red",
		)
		if r.text:
			return {
				"status": "error",
			}
	else:
		data = json.loads(r.text)
		add_log(
			request_type="UpdateApprovalRequest",
			request_url=url,
			request_header=headers,
			request_body=payload,
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype=ref_doctype,
			ref_docname=ref_docname,
		)

		return set_service_approval(
			doc,
			data,
			item_code=item_row.get("item_code") if item_row else "",
			reference_name=reference_name,
			reference_doctype=reference_doctype,
		)


@frappe.whitelist()
def issue_approved_service(
	doc,
	approval_number,
	service_type,
	service_name,
	fingerprint,
	fpcode,
	qty=1,
	rate=0,
	settings_doc=None,
	biometric_method="NONE",
):
	item = ""
	item_rate = 0
	if doc.doctype == "Delivery Note":
		item = service_name
		item_rate = rate
	else:
		item = frappe.get_cached_value(service_type, service_name, "item")

		insurance_subscription = doc.get("insurance_subscription")
		if not insurance_subscription:
			appointment = doc.get("appointment") or doc.get("hms_tz_appointment_no")
			insurance_subscription = frappe.get_cached_value(
				"Patient Appointment", appointment, "insurance_subscription"
			)

		item_rate = get_item_rate(item, doc.company, insurance_subscription, doc.insurance_company)

	payload = {
		"approvalReferenceNo": approval_number,
		"isBiometricVerified": False if biometric_method == "NONE" else True,
		"biometricMethod": biometric_method,
		"fpCode": fpcode,
		"imageData": fingerprint,
		"description": service_name,
		"quantity": cint(qty),
		"unitPrice": item_rate or 0,
		"createdBy": doc.get("practitioner") or doc.get("healthcare_practitioner"),
	}

	payload = json.dumps(payload)

	if not settings_doc:
		settings_doc = frappe.get_cached_doc("HMS TZ Setting", doc.company)

	token = settings_doc.get_nhif_token()

	url = f"{settings_doc.nhifservice_url}/api/Approvals/IssueApprovedService"

	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	r = requests.request("POST", url, headers=headers, data=payload, timeout=120)
	if r.status_code != 200:
		data = json.loads(r.text) if r.text else {}
		add_log(
			request_type="IssueApprovedService",
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
			"Comment",
			text=f"Failed to Issue Service<br><br>Status Code: {r.status_code}<br>NHIF Response: <b>{data.get('errors') or data.get('message')}<b>",
		)
		frappe.db.commit()

		frappe.throw(
			title="NHIF API Error",
			msg=f"Failed to Issue Service<br><br>Status Code: {r.status_code}<br>NHIF Response: <b>{data.get('errors') or data.get('message')}<b>",
		)
	else:
		data = json.loads(r.text)
		add_log(
			request_type="IssueApprovedService",
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
			"Comment",
			text=f"Service Reference No: <strong>{data.get('ServiceReferenceNo')}</strong> is successfully created.",
		)
		frappe.db.commit()

		frappe.msgprint("Service Issued Successfully..!!", alert=True)
		return data


def get_request_approval_payload(
	doc,
	facility_code,
	service_type,
	service_name,
	start_date,
	expire_date,
	clinical_notes,
	qty=1,
	item_code=None,
	reference_name=None,
	reference_doctype=None,
	supportive_document="",
):
	clinical_notes = html2text(clinical_notes).lstrip("\n")
	patient_doc = frappe.get_cached_doc("Patient", doc.patient)

	appointment = doc.get("appointment") or doc.get("hms_tz_appointment_no")
	appointment_info = get_appointment_details(appointment)

	encounter_id = doc.get("ref_docname") or doc.get("reference_name")

	practitioner = doc.get("practitioner") or doc.get("healthcare_practitioner")
	practitioner_no = frappe.get_cached_value("Healthcare Practitioner", practitioner, "tz_mct_code")
	attendance_date = get_datetime(
		f"{appointment_info.appointment_date} {appointment_info.appointment_time}"
	).isoformat(timespec="milliseconds")

	payload = {
		"firstName": patient_doc.first_name,
		"lastName": patient_doc.last_name,
		"gender": patient_doc.sex,
		"telephoneNo": patient_doc.mobile,
		"clinicalNotes": clinical_notes,
		"dateOfBirth": str(patient_doc.dob),
		"authorizationNo": appointment_info.authorization_number,
		"facilityPatientFileNumber": doc.patient,
		"attendanceDate": attendance_date,
		"serviceDate": str(start_date),
		"expiryDate": str(expire_date),
		"sourceFacilityCode": facility_code,
		"practitionerNo": practitioner_no,
		"prescribedBy": practitioner,
		"requestedBy": practitioner,
		"createdBy": practitioner,
		"approvalDiseases": get_approval_diseases(doc, practitioner, encounter_id),
		"authorizedItems": get_authorized_items(
			doc,
			service_type,
			service_name,
			appointment_info.years_of_insurance,
			appointment,
			practitioner,
			qty=qty,
			item_code=item_code,
			reference_name=reference_name,
			reference_doctype=reference_doctype,
		),
		"approvalSupportingDocuments": [],
	}

	# Add supporting documents if available
	if supportive_document:
		file_doc = frappe.get_doc("File", {"file_url": supportive_document})

		if file_doc:
			file_path = file_doc.get_full_path()

			document_data = ""
			with open(file_path, "rb") as f:
				file_content = f.read()
				document_data = base64.b64encode(file_content).decode("utf-8")

			supporting_doc = {
				"documentTypeID": 1,
				"documentDetails": file_doc.file_name or "",
				"filePath": supportive_document,
				"documentData": document_data,
				"fileType": file_doc.file_type,
			}

			payload["approvalSupportingDocuments"].append(supporting_doc)

	return payload


def get_approval_diseases(
	doc, practitioner, encounter_id, app_disease_id="", service_authorization_id="", caller="Request Approval"
):
	diseases = []

	encounter_doc = frappe.get_cached_doc("Patient Encounter", encounter_id)

	for d in encounter_doc.patient_encounter_preliminary_diagnosis:
		preliminary = {
			"diseaseCode": get_disease_code(d.code),
			"notes": d.description,
			"createdBy": practitioner,
			"dateCreated": doc.creation.isoformat(timespec="milliseconds"),
		}

		if caller == "Update Request Approval":
			preliminary["appDiseaseID"] = app_disease_id
			preliminary["serviceAuthorizationID"] = service_authorization_id
			preliminary["lastModifiedBy"] = get_fullname(doc.modified_by)
			preliminary["lastModified"] = doc.modified.isoformat(timespec="milliseconds")

		diseases.append(preliminary)

	for d in encounter_doc.patient_encounter_final_diagnosis:
		final = {
			"diseaseCode": get_disease_code(d.code),
			"notes": d.description,
			"createdBy": practitioner,
			"dateCreated": doc.creation.isoformat(timespec="milliseconds"),
		}

		if caller == "Update Request Approval":
			final["appDiseaseID"] = app_disease_id
			final["serviceAuthorizationID"] = service_authorization_id
			final["lastModifiedBy"] = get_fullname(doc.modified_by)
			final["lastModified"] = doc.modified.isoformat(timespec="milliseconds")

		diseases.append(final)

	return diseases


def get_authorized_items(
	doc,
	service_type,
	service_name,
	years_of_insurance,
	appointment,
	practitioner,
	qty=1,
	item_code=None,
	reference_name=None,
	reference_doctype=None,
	item_authorization_id=None,
	service_authorization_id=None,
	caller="Request Approval",
):
	items = []

	item = ""
	if doc.doctype == "Delivery Note" and item_code:
		item = item_code

		if not service_name and reference_name and reference_doctype:
			service_name = frappe.get_cached_value(reference_doctype, reference_name, "drug_code")
	else:
		item = frappe.get_cached_value(service_type, service_name, "item")

	insurance_coverage_plan = doc.get("hms_tz_insurance_coverage_plan") or doc.get("coverage_plan_name")
	insurance_subscription = doc.get("insurance_subscription")
	insurance_company = doc.get("insurance_company") or ""
	if not insurance_subscription:
		insurance_subscription, insurance_company = frappe.get_cached_value(
			"Patient Appointment", appointment, ["insurance_subscription", "insurance_company"]
		)

	item_rate = get_item_rate(item, doc.company, insurance_subscription, insurance_company)

	ref_code = get_item_refcode(service_type, service_name, doc.company, insurance_company)

	service_type_id = get_service_type_id(ref_code)

	scheme_id = frappe.get_cached_value(
		"Healthcare Insurance Coverage Plan",
		insurance_coverage_plan,
		"nhif_scheme_id",
	)

	percent_covered = (
		frappe.get_cached_value(
			"NHIF Co-Payment Item",
			{
				"itemcode": ref_code,
				"schemeid": scheme_id,
				"yearno": years_of_insurance,
			},
			"percentcovered",
		)
		or 100
	)

	new_item = {
		"serviceTypeID": service_type_id,
		"itemCode": ref_code,
		"description": service_name,
		"quantityRequested": qty,
		"unitPrice": item_rate or 0,
		"percentCovered": percent_covered or 100,
		"createdBy": practitioner,
		"dateCreated": doc.creation.isoformat(timespec="milliseconds"),
	}

	if caller == "Update Request Approval":
		new_item["quantity"] = qty
		new_item["authorizedItemID"] = item_authorization_id
		new_item["serviceAuthorizationID"] = service_authorization_id
		new_item["lastModifiedBy"] = get_fullname(doc.modified_by)
		new_item["lastModified"] = doc.modified.isoformat(timespec="milliseconds")

	items.append(new_item)

	return items


def get_update_approval_payload(
	doc,
	facility_code,
	service_type,
	service_name,
	appointment,
	qty=1,
	item_row={},
	reference_name=None,
	reference_doctype=None,
	item_authorization_id=None,
	service_authorization_id=None,
):
	patient_doc = frappe.get_cached_doc("Patient", doc.patient)
	appointment_info = get_appointment_details(appointment)

	encounter_id = doc.get("ref_docname") or doc.get("reference_name")
	notes_html = frappe.get_cached_value("Patient Encounter", encounter_id, "examination_detail") or ""
	clinical_notes = html2text(notes_html).lstrip("\n")

	practitioner = doc.get("practitioner") or doc.get("healthcare_practitioner")
	practitioner_no, qualification = frappe.get_cached_value(
		"Healthcare Practitioner", practitioner, ["tz_mct_code", "nhif_physician_qualification"]
	)
	qualification_id = frappe.get_cached_value(
		"NHIF Physician Qualification", qualification, "physicianqualificationid"
	)

	insurance_coverage_plan = doc.get("hms_tz_insurance_coverage_plan") or doc.get("coverage_plan_name")

	if not service_name and reference_name and reference_doctype:
		service_name = frappe.get_cached_value(reference_doctype, reference_name, "drug_code")

	ref_code = get_item_refcode(service_type, service_name, doc.company, doc.get("insurance_company") or "")

	service_type_id = get_service_type_id(ref_code)

	scheme_id = frappe.get_cached_value(
		"Healthcare Insurance Coverage Plan",
		insurance_coverage_plan,
		"nhif_scheme_id",
	)

	start_date = doc.get("start_date") or doc.get("result_date") or doc.get("posting_date")
	approval_date = doc.get("approval_date") or item_row.get("approval_date")
	attendance_date = get_datetime(
		f"{appointment_info.appointment_date} {appointment_info.appointment_time}"
	).isoformat(timespec="milliseconds")

	payload = {
		"serviceAuthorizationID": service_authorization_id,
		"serviceTypeID": service_type_id,
		"cardNo": appointment_info.coverage_plan_card_number or appointment_info.national_id,
		"cardExistence": "",
		"firstName": patient_doc.first_name,
		"lastName": patient_doc.last_name,
		"gender": doc.get("hms_tz_patient_sex") or patient_doc.sex,
		"telephoneNo": patient_doc.mobile,
		"clinicalNotes": clinical_notes,
		"dateOfBirth": str(patient_doc.dob),
		"schemeID": scheme_id,
		"productCode": "",
		"authorizationNo": appointment_info.authorization_number,
		"facilityPatientFileNumber": doc.patient,
		"yearOfBirth": str(patient_doc.dob)[:4],
		"attendanceDate": attendance_date,
		"serviceDate": str(start_date),
		"expiryDate": str(start_date),
		"sourceFacilityCode": facility_code,
		"approvalStatusID": 0,
		"practitionerNo": practitioner_no,
		"prescribedBy": practitioner,
		"qualificationID": qualification_id,
		"issuingFacilityCode": facility_code,  # TODO: consider when patient was referred to this hospital and approval request was made from previous hospital
		"approvalIssuingFacilityCode": facility_code,  # TODO: consider when patient was referred to this hospital and approval request was made from previous hospital
		"officeCode": "",
		"referenceNo": doc.get("approval_number") or item_row.get("approval_number"),
		"serviceState": doc.get("approval_status") or item_row.get("approval_status"),
		"requestedBy": practitioner,  # TODO: add requested by
		"approvedBy": practitioner,  # TODO: add approved by
		"approvedDate": get_datetime(approval_date).isoformat(timespec="milliseconds")
		if approval_date
		else None,  # TODO: add approved date
		"createdBy": practitioner,
		"dateCreated": doc.creation.isoformat(timespec="milliseconds"),
		"lastModifiedBy": get_fullname(doc.modified_by),
		"lastModified": doc.modified.isoformat(timespec="milliseconds"),
		"approvalDiseases": get_approval_diseases(
			doc,
			practitioner,
			encounter_id,
			app_disease_id=doc.get("app_disease_id") or item_row.get("app_disease_id") or "",
			service_authorization_id=service_authorization_id,
			caller="Update Request Approval",
		),
		"authorizedItems": get_authorized_items(
			doc,
			service_type,
			service_name,
			appointment_info.years_of_insurance,
			appointment,
			practitioner,
			qty=qty,
			item_code=item_row.get("item_code"),
			reference_name=reference_name,
			reference_doctype=reference_doctype,
			item_authorization_id=item_authorization_id,
			service_authorization_id=service_authorization_id,
			caller="Update Request Approval",
		),
		"approvalSupportingDocuments": [],
	}

	# Add supporting documents if available
	supportive_document = doc.get("supportive_document") or item_row.get("supportive_document")
	if supportive_document:
		file_doc = frappe.get_doc("File", {"file_url": supportive_document})

		if file_doc:
			file_path = file_doc.get_full_path()
			file_doc.file_name.split(".")[-1].upper() if file_doc.file_name else ""

			document_data = ""
			with open(file_path, "rb") as f:
				file_content = f.read()
				document_data = base64.b64encode(file_content).decode("utf-8")

			supporting_doc = {
				"supportingDocumentID": "",
				"serviceAuthorizationID": service_authorization_id or "",
				"documentTypeID": 1,
				"documentDetails": file_doc.file_name or "",
				"filePath": supportive_document,
				"documentData": document_data,
				"fileType": file_doc.file_type,
			}

			payload["approvalSupportingDocuments"].append(supporting_doc)

	return payload


def get_appointment_details(appointment):
	appointment_info = frappe.get_cached_value(
		"Patient Appointment",
		appointment,
		[
			"authorization_number",
			"appointment_date",
			"appointment_time",
			"years_of_insurance",
			"coverage_plan_card_number",
			"national_id",
			"insurance_company",
		],
		as_dict=True,
	)

	return appointment_info


def get_service_type_id(ref_code):
	service_type_id = frappe.get_cached_value("NHIF Item", {"itemcode": ref_code}, "servicetypeid")
	return service_type_id


@frappe.whitelist()
def verify_approval_number(
	company,
	approval_number,
	service_type,
	service_name,
	appointment,
	ref_doctype,
	ref_docname,
):
	settings_doc = frappe.get_cached_doc("HMS TZ Setting", company)

	if not settings_doc.enable_nhif_api:
		frappe.msgprint("NHIF API is disabled")
		return False

	appointment_info = get_appointment_details(appointment)

	ref_code = get_item_refcode(
		service_type, service_name, company, appointment_info.get("insurance_company") or ""
	)
	card_no = appointment_info.coverage_plan_card_number or appointment_info.national_id

	url = f"{settings_doc.nhifservice_url}/api/Approvals/GetReferenceNoStatus?cardNo={card_no}&referenceNo={approval_number}&itemCode={ref_code}"

	token = settings_doc.get_nhif_token()
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}
	r = requests.request("Get", url, headers=headers, timeout=60)
	if r.status_code != 200:
		add_log(
			request_type="GetReferenceNoStatus",
			request_url=url,
			request_header=headers,
			request_body="",
			response_data=r.text,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype=ref_doctype,
			ref_docname=ref_docname,
			card_no=card_no,
		)
		frappe.msgprint(
			title="NHIF API Error",
			msg=f"Failed to Verify Service Approval Number<br><br>Status Code: {r.status_code}<br>NHIF Response: <b>{r.text}<b>",
			indicator="red",
		)
		return False
	else:
		data = json.loads(r.text)
		add_log(
			request_type="GetReferenceNoStatus",
			request_url=url,
			request_header=headers,
			request_body="",
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype=ref_doctype,
			ref_docname=ref_docname,
			card_no=card_no,
		)
		if data["status"] == "VALID":
			return True
		else:
			frappe.msgprint(
				f"<h4 class='text-center' style='background-color: #D3D3D3; font-weight: bold;'>\
                This ApprovalNumber: <strong>{approval_number}</strong> for CardNo: <strong>{card_no}</strong> and ItemCode: <strong>{ref_code}</strong> is not Valid</h4>"
			)
			return False


@frappe.whitelist()
def get_approval_services(company=None, caller=None):
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
	url = f"{settings_doc.nhifservice_url}/api/Approvals/GetApprovalServices"
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}
	r = requests.request("Get", url, headers=headers, timeout=60)
	if r.status_code != 200:
		add_log(
			request_type="GetApprovalServices",
			request_url=url,
			request_header=headers,
			request_body="",
			response_data=r.text,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype="NHIF Service Type",
		)
		return

	else:
		data = json.loads(r.text)
		add_log(
			request_type="GetApprovalServices",
			request_url=url,
			request_header=headers,
			request_body="",
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype="NHIF Service Type",
		)

		for row in data:
			if frappe.db.exists("NHIF Service Type", row["ServiceTypeName"]):
				has_changed = False
				doc = frappe.get_cached_doc("NHIF Service Type", row["ServiceTypeName"])
				if doc.service_type_id != row["ServiceTypeID"]:
					has_changed = True
					doc.service_type_id = row["ServiceTypeID"]

				if doc.require_nhif_number != row["RequireNhifNumber"]:
					has_changed = True
					doc.require_nhif_number = row["RequireNhifNumber"]

				if has_changed:
					doc.save(ignore_permissions=True)

				continue
			else:
				doc = frappe.new_doc("NHIF Service Type")
				doc.service_type_id = row["ServiceTypeID"]
				doc.service_type_name = row["ServiceTypeName"]
				doc.require_nhif_number = row["RequireNhifNumber"]

				doc.save(ignore_permissions=True)

		if company and caller == "Front End":
			frappe.msgprint(
				"successfully fetched Service Types",
				alert=True,
				indicator="green",
			)


def update_approval_status(doc, appointment, data, dni_id=None):
	records = []
	if doc.doctype != "Delivery Note":
		records = frappe.db.get_all(
			doc.doctype,
			filters={
				"appointment": appointment,
				"is_restricted": 1,
				"approval_number": ("is", "not set"),
			},
			fields=["name", "service_authorization_id"],
		)

	dni_reference_no = ""
	lrpt_reference_no = ""
	for record in records:
		for row in data:
			if row.get("ServiceAuthorizationID") == record.get("service_authorization_id"):
				rad_doc = None
				if record.get("name") == doc.name:
					rad_doc = doc
				else:
					rad_doc = frappe.get_cached_doc(doc.doctype, record.get("name"))

				if row.get("ReferenceNo"):
					rad_doc.approval_number = row.get("ReferenceNo")
					if record.get("name") == doc.name:
						lrpt_reference_no = row.get("ReferenceNo")

				rad_doc.approval_date = row.get("ApprovalDate")
				rad_doc.approval_status = row.get("ApprovalStatus")
				rad_doc.authorized_item_id = row.get("AuthorizedItemID")
				rad_doc.save(ignore_permissions=True)

				rad_doc.add_comment(
					comment_type="Comment",
					text=f"Approval status: <b>{row.get('ApprovalStatus')}</b><br>ReferenceNo: <b>{row.get('ReferenceNo') or 'Not Provided'}</b>\
                        <br>QuantityRequested: <b>{row.get('QuantityRequested')}</b>\
                        <br>QuantityApproved: <b>{row.get('QuantityApproved')}</b>\
                        <br>Remarks: <b>{row.get('Remarks') or row.get('SummaryRemarks')}</b>",
				)
				rad_doc.reload()

	dn = DocType("Delivery Note")
	dni = DocType("Delivery Note Item")

	dn_records = (
		frappe.qb.from_(dn)
		.inner_join(dni)
		.on(dn.name == dni.parent)
		.select(
			dni.item_code,
			dn.name.as_("dn_id"),
			dni.name.as_("dni_id"),
			dni.service_authorization_id,
		)
		.where(
			(dn.hms_tz_appointment_no == appointment)
			& (dni.is_restricted == 1)
			& (dni.approval_number.isnull() | (dni.approval_number == ""))
		)
	).run(as_dict=True)

	if len(dn_records) > 0:
		dn_map = {}
		reference_no = None
		for row in dn_records:
			dn_map.setdefault(row.get("dn_id"), []).append(row)

		for dn_id, dni_rows in dn_map.items():
			dn_doc = frappe.get_cached_doc("Delivery Note", dn_id)

			for dni in dni_rows:
				for row in data:
					if row.get("ServiceAuthorizationID") == dni.get("service_authorization_id"):
						fields = {
							"approval_status": row.get("ApprovalStatus"),
							"approval_date": row.get("ApprovalDate"),
							"authorized_item_id": row.get("AuthorizedItemID"),
						}
						if row.get("ReferenceNo"):
							fields["approval_number"] = row.get("ReferenceNo")

							if dni.get("dni_id") == dni_id:
								dni_reference_no = row.get("ReferenceNo")

						frappe.db.set_value("Delivery Note Item", dni.get("dni_id"), fields)
						comment = f"Item: <b>{dni.get('item_code')}</b><br>Approval status: <b>{row.get('ApprovalStatus')}</b><br>\
                                ReferenceNo: <b>{row.get('ReferenceNo') or 'Not Provided'}</b>\
                                <br>QuantityRequested: <b>{row.get('QuantityRequested')}</b>\
                                <br>QuantityApproved: <b>{row.get('QuantityApproved')}</b>\
                                <br>Remarks: <b>{row.get('Remarks') or row.get('SummaryRemarks')}</b>"

						dn_doc.add_comment(comment_type="Comment", text=comment)
						dn_doc.reload()

	reference_no = None
	if dni_id:
		reference_no = dni_reference_no
	else:
		reference_no = lrpt_reference_no

	return {"status": "success", "reference_no": reference_no}


def set_service_approval(
	doc,
	data,
	item_code=None,
	reference_name=None,
	reference_doctype=None,
):
	msg = "Request Approval successful!"
	if doc.doctype == "Delivery Note":
		fields = {
			"service_authorization_id": data.get("ServiceAuthorizationID"),
		}
		if data.get("ReferenceNo"):
			msg += f"<br>ReferenceNo: <b>{data.get('ReferenceNo')}</b>"
			fields["approval_number"] = data.get("ReferenceNo")
		else:
			msg += "<br>ReferenceNo: <b>Not Provided</b>"

		msg += f"<br>QuantityRequested: <b>{data.get('QuantityRequested')}</b>\
            <br>QuantityApproved: <b>{data.get('Quantity')}</b>\
            Remarks: <b>{data.get('Remarks') or data.get('SummaryRemarks')}</b>"

		frappe.db.set_value(
			"Delivery Note Item",
			{
				"parent": doc.name,
				"item_code": item_code,
				"reference_name": reference_name,
				"reference_doctype": reference_doctype,
			},
			fields,
		)
	else:
		if data.get("ReferenceNo"):
			msg += f"<br>ReferenceNo: <b>{data.get('ReferenceNo')}</b>"
		else:
			msg += "<br>ReferenceNo: <b>Not Provided</b>"

		msg += f"<br>QuantityRequested: <b>{data.get('QuantityRequested')}</b>\
            <br>QuantityApproved: <b>{data.get('Quantity')}</b>\
            Remarks: <b>{data.get('Remarks') or data.get('SummaryRemarks')}</b>"

		frappe.db.set_value(
			doc.doctype,
			doc.name,
			{
				"service_authorization_id": data.get("ServiceAuthorizationID"),
				"approval_number": data.get("ReferenceNo") or "",
			},
		)

	doc.add_comment(comment_type="Comment", text=msg)
	doc.reload()

	return {"status": "success", "reference_no": data.get("ReferenceNo")}
