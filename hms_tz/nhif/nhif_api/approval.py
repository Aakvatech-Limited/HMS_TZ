import base64
import json
from urllib.parse import urlencode

import frappe
import requests
from frappe import _
from frappe.core.utils import html2text
from frappe.utils import add_months, cint, get_datetime, get_fullname, getdate

from hms_tz.hms_tz.doctype.healthcare_service_request.healthcare_service_request import (
	get_appointment,
	get_item_rate,
	get_item_refcode,
)
from hms_tz.nhif.doctype.insurance_approval_log.insurance_approval_log import insert_unissued_lines
from hms_tz.nhif.doctype.nhif_response_log.nhif_response_log import add_log
from hms_tz.nhif.nhif_api.approval_status import update_approval_status
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

	appointment = get_appointment(doc)

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
def get_unissued_services(ref_doctype, ref_docname):
	"""Return the NHIF approvals of the visit's card with unissued qty, with our service name and the rows it can fill.

	The approvals are logged, so issuing a service with one of them counts its usage.
	"""
	# nhif.utils imports this module
	from hms_tz.nhif.utils import (
		get_approval_targets,
		get_nhif_visit,
		get_service_names,
		get_services_of_drafts,
	)

	doc, settings_doc = get_nhif_document(ref_doctype, ref_docname, _("Unissued services"))
	visit = get_nhif_visit(doc)
	if not visit:
		frappe.throw(_("Unissued services are only available for an NHIF visit with a card number"))

	data = request_unissued_services(settings_doc, visit.coverage_plan_card_number, ref_doctype, ref_docname)
	insert_unissued_lines(data, get_appointment(doc), get_services_of_drafts([doc], visit.insurance_company))
	targets = get_approval_targets(doc, visit)
	service_names = get_service_names(
		{line.get("ItemCode") for line in data}, settings_doc.nhif_customer_name
	)
	return [
		{
			**line,
			"service_name": ", ".join(service_names.get(line.get("ItemCode"), [])) or line.get("ItemName"),
			"targets": targets.get(line.get("ItemCode"), []),
		}
		for line in data
	]


def request_unissued_services(settings_doc, card_no, ref_doctype, ref_docname):
	"""Return the approvals of the card that NHIF has not fully issued yet."""
	return request_approvals_api(
		settings_doc, "GetUnIssuedServices", {"cardNo": card_no}, ref_doctype, ref_docname
	)


@frappe.whitelist()
def get_approved_services(ref_doctype, ref_docname):
	"""Return the NHIF approved services of each approval number on the document, grouped by that number."""
	doc, settings_doc = get_nhif_document(ref_doctype, ref_docname, _("Approved services"))
	rows = doc.items if ref_doctype == "Delivery Note" else [doc]
	approval_numbers = list(dict.fromkeys(row.approval_number for row in rows if row.get("approval_number")))
	if not approval_numbers:
		frappe.throw(_("{0} {1} has no approval number").format(_(ref_doctype), ref_docname))

	return [
		{
			"approval_number": approval_number,
			"services": request_approvals_api(
				settings_doc,
				"GetApprovedServices",
				{"approvalReferenceNo": approval_number},
				ref_doctype,
				ref_docname,
			),
		}
		for approval_number in approval_numbers
	]


@frappe.whitelist()
def check_eligibility(ref_doctype, ref_docname):
	"""Return whether the visit's card may get an approval for each restricted service on the document.

	NHIF is called once per distinct item code.
	"""
	# nhif.utils imports this module
	from hms_tz.nhif.utils import get_nhif_visit, get_restricted_services, get_service_label

	doc, settings_doc = get_nhif_document(ref_doctype, ref_docname, _("Eligibility checks"))
	visit = get_nhif_visit(doc)
	if not visit:
		frappe.throw(_("Eligibility check is only available for an NHIF visit with a card number"))

	services = []
	for row, service_type, service_name in get_restricted_services(doc):
		label = get_service_label(row, service_name)
		item_code = get_item_refcode(service_type, service_name, doc.company, visit.insurance_company)
		if not item_code:
			frappe.throw(_("{0} has no NHIF item code").format(frappe.bold(label)))
		services.append({"service": label, "item_code": item_code})
	if not services:
		frappe.throw(_("{0} {1} has no restricted service").format(_(ref_doctype), ref_docname))

	eligibility = {
		item_code: request_approvals_api(
			settings_doc,
			"CheckEligibility",
			{"cardNo": visit.coverage_plan_card_number, "itemCode": item_code},
			ref_doctype,
			ref_docname,
		)
		for item_code in dict.fromkeys(service["item_code"] for service in services)
	}
	return [{**service, **eligibility[service["item_code"]]} for service in services]


@frappe.whitelist()
def get_approval_list(ref_doctype, ref_docname):
	"""Return every approval request NHIF holds for the visit's card, from any facility."""
	# nhif.utils imports this module
	from hms_tz.nhif.utils import get_nhif_visit

	doc, settings_doc = get_nhif_document(
		ref_doctype, ref_docname, _("Approval lists"), extra_doctypes=("Patient Encounter",)
	)
	visit = get_nhif_visit(doc)
	if not visit:
		frappe.throw(_("Approval list is only available for an NHIF visit with a card number"))

	return request_approvals_api(
		settings_doc, "GetApprovals", {"cardNo": visit.coverage_plan_card_number}, ref_doctype, ref_docname
	)


@frappe.whitelist()
def get_issued_services(ref_doctype: str, ref_docname: str, from_date: str, to_date: str):
	"""Return the services the facility issued to NHIF patients from the start of `from_date` to the end of `to_date`."""
	from_date, to_date = getdate(from_date), getdate(to_date)
	if from_date > to_date:
		frappe.throw(_("From Date cannot be after To Date"))
	if to_date >= add_months(from_date, 1):
		frappe.throw(_("The date range cannot be longer than one month"))

	_doc, settings_doc = get_nhif_document(ref_doctype, ref_docname, _("Issued services"))

	return request_approvals_api(
		settings_doc,
		"GetIssuedServices",
		{"fromDate": f"{from_date}T00:00:01", "toDate": f"{to_date}T23:59:59"},
		ref_doctype,
		ref_docname,
		method="POST",
	)


def get_nhif_document(ref_doctype, ref_docname, feature, extra_doctypes=()):
	"""Return the readable NHIF service document, Delivery Note or `extra_doctypes` document and its HMS TZ Setting.

	Throw when the NHIF API is disabled.
	"""
	# nhif.utils imports this module
	from hms_tz.nhif.utils import SERVICE_FIELDS

	doctypes = (*SERVICE_FIELDS, "Delivery Note", *extra_doctypes)
	if ref_doctype not in doctypes or not isinstance(ref_docname, str):
		frappe.throw(_("{0} are not available for {1}").format(feature, ref_doctype))

	doc = frappe.get_doc(ref_doctype, ref_docname)
	doc.check_permission("read")
	settings_doc = frappe.get_cached_doc("HMS TZ Setting", doc.company)
	if not settings_doc.enable_nhif_api:
		frappe.throw(_("NHIF API is disabled"))

	return doc, settings_doc


def request_approvals_api(settings_doc, request_type, query, ref_doctype, ref_docname, method="GET"):
	"""Call /api/Approvals/<request_type> on NHIF, log it and return the JSON. Throw on a non-200 response."""
	request = f"{request_type}?{urlencode(query)}"
	url = f"{settings_doc.nhifservice_url}/api/Approvals/{request}"
	headers = {"Content-Type": "application/json", "Authorization": f"Bearer {settings_doc.get_nhif_token()}"}
	r = requests.request(method, url, headers=headers, timeout=60)
	data = r.json() if r.status_code == 200 else r.text
	add_log(
		request_type=request_type,
		request_url=url,
		request_header=headers,
		request_body="",
		response_data=data,
		status_code=r.status_code,
		company=settings_doc.name,
		ref_doctype=ref_doctype,
		ref_docname=ref_docname,
		card_no=query.get("cardNo"),
	)
	if r.status_code != 200:
		frappe.throw(
			_("Request: {0}<br>Status Code: {1}<br>NHIF Response: {2}").format(
				frappe.utils.escape_html(request),
				r.status_code,
				frappe.bold(frappe.utils.escape_html(r.text)),
			),
			title=_("NHIF API Error"),
		)

	return data


@frappe.whitelist()
def update_service_approval(
	ref_doctype,
	ref_docname,
	service_type,
	service_name,
	qty=1,
	item_row=None,
	reference_name=None,
	reference_doctype=None,
	item_authorization_id=None,
	service_authorization_id=None,
):
	if item_row is None:
		item_row = {}
	if not ref_doctype or not ref_docname:
		frappe.throw("Document Type and Document Name are required")

	doc = frappe.get_cached_doc(ref_doctype, ref_docname)

	settings_doc = frappe.get_cached_doc("HMS TZ Setting", doc.company)

	if not settings_doc.enable_nhif_api:
		frappe.msgprint("NHIF API is disabled")
		return False

	appointment = get_appointment(doc)

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


@frappe.whitelist(methods=["POST"])
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
			appointment = get_appointment(doc)
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

	appointment = get_appointment(doc)
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
	item_row=None,
	reference_name=None,
	reference_doctype=None,
	item_authorization_id=None,
	service_authorization_id=None,
):
	if item_row is None:
		item_row = {}
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
