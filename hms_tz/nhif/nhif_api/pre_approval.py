import json

import frappe
import requests
from frappe.core.utils import html2text
from frappe.utils import getdate, nowdate
from frappe.utils.caching import request_cache

from hms_tz.hms_tz.doctype.healthcare_service_request.healthcare_service_request import (
	get_childs_map,
	get_item_rate,
	get_item_refcode,
)
from hms_tz.nhif.doctype.nhif_response_log.nhif_response_log import add_log
from hms_tz.nhif.nhif_api.referral import get_disease_code

MAX_BEDS_PER_REQUEST = 10


@frappe.whitelist()
def get_service_preapproval(
	ref_doctype,
	ref_docname,
	authorization_no=None,
	settings_doc=None,
):
	# source doc can be either Patient Encounter or Medication Change Request
	source_doc = frappe.get_doc(ref_doctype, ref_docname)

	insurance_company = source_doc.get("insurance_company") or ""
	if "NHIF" not in insurance_company:
		frappe.throw(
			f"Cannot request NHIF pre-approval: {ref_doctype} {ref_docname} "
			f"belongs to insurance company '{insurance_company}', not NHIF"
		)

	if not settings_doc:
		settings_doc = frappe.get_cached_doc("HMS TZ Setting", source_doc.company)

	services, requested_rows, diseases = get_services(source_doc)
	if len(services) == 0:
		frappe.msgprint("No service(s) to request an Pre-Approvals")
		return False

	first_name, last_name, dob, patient_sex = frappe.get_cached_value(
		"Patient", source_doc.patient, ["first_name", "last_name", "dob", "sex"]
	)

	practitioner = source_doc.get("practitioner") or source_doc.get("healthcare_practitioner")
	mct_code, mobile = frappe.get_cached_value(
		"Healthcare Practitioner",
		practitioner,
		["tz_mct_code", "mobile_phone"],
	)
	if not authorization_no:
		authorization_no = frappe.get_cached_value(
			"Patient Appointment",
			source_doc.appointment,
			"authorization_number",
		)

	notes = ""
	if source_doc.doctype == "Patient Encounter":
		notes = source_doc.get("examination_detail")
	else:
		notes = frappe.get_cached_value(
			"Patient Encounter",
			source_doc.get("patient_encounter"),
			"examination_detail",
		)

	clinical_notes = html2text(notes).lstrip("\n")

	payload = {
		"authorizationNo": authorization_no,
		"firstName": first_name,
		"lastName": last_name,
		"gender": patient_sex,
		"dateOfBirth": str(dob),
		"patientFileNo": source_doc.patient,
		"clinicalNotes": clinical_notes,
		"practitionerNo": mct_code,
		"practitionersRemarks": "",
		"telephoneNo": mobile,
		"facilityCode": settings_doc.facility_code,
		"diseases": diseases,
		"requestedServices": services,
	}
	payload = json.dumps(payload)

	url = f"{settings_doc.nhifservice_url}/api/PreApprovals/RequestServices"

	token = settings_doc.get_nhif_token()
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	r = requests.request("Post", url, data=payload, headers=headers, timeout=60)
	if r.status_code != 200:
		add_log(
			request_type="RequestServices",
			request_url=url,
			request_header=headers,
			request_body=payload,
			response_data=r.text,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype=ref_doctype,
			ref_docname=ref_docname,
		)

		source_doc.add_comment(
			comment_type="Comment",
			text=f"Pre-approval request Failed..!<br><br>Status Code: {r.status_code}<br>NHIF Response: <b>{r.text}<b>",
		)
		frappe.db.commit()

		frappe.throw(
			title="NHIF API Error",
			msg=f"Pre-approval failed<br><br>Status Code: {r.status_code}<br>NHIF Response: <b>{r.text}<b>",
		)
	else:
		data = json.loads(r.text)
		add_log(
			request_type="RequestServices",
			request_url=url,
			request_header=headers,
			request_body=payload,
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype=ref_doctype,
			ref_docname=ref_docname,
		)

		rejected_count = 0
		msg = "Pre-Approval request were rejected for the following services:<hr>\
            <table class='table table-condensed table-bordered'><tr><th>Service Type</th><th>Service</th><th>Status</th><th>Reason</th></tr>"

		for row, template_name, ref_code in requested_rows:
			if not ref_code:
				continue

			for d in data.get("services"):
				if d.get("itemCode") == ref_code:
					row.preapproval_status = d.get("status")
					row.preapproval_no = data.get("requestNo") if d.get("status") != "REJECTED" else ""
					row.rejection_reason_code = d.get("rejectionReasonCode")
					row.rejection_details = d.get("rejectionDetails")
					row.preapproval_cancel_remarks = ""
					row.db_update()
					row.reload()

					if d.get("status") == "REJECTED":
						rejected_count += 1
						msg += f"<tr>\
                            <td>{row.doctype.split(' ')[0]}</td>\
                            <td>{template_name}</td>\
                            <td style='color: red'>{d.get('status')}</td>\
                            <td>{d.get('rejectionDetails')}</td>\
                        </tr>"
					break

		source_doc.db_update()
		source_doc.db_update_all()
		source_doc.reload()

		source_doc.add_comment(
			comment_type="Comment",
			text=f"Pre-approval request sent successful!<br>RequestID: <b>{data.get('requestID')}</b><br>",
		)
		if rejected_count > 0:
			msg += "</table>"
			frappe.msgprint(msg, title="Pre-Approval Status", indicator="red")
		else:
			frappe.msgprint(
				"<b>Pre-Approval request were successful for all services</b>",
				title="Pre-Approval Status",
				indicator="green",
			)

		return True


@frappe.whitelist()
def cancel_preapproval(
	ref_doctype,
	ref_docname,
	preapproval_no,
	remarks,
	settings_doc=None,
):
	source_doc = frappe.get_cached_doc(ref_doctype, ref_docname)

	insurance_company = source_doc.get("insurance_company") or ""
	if "NHIF" not in insurance_company:
		frappe.throw(
			f"Cannot cancel NHIF pre-approval: {ref_doctype} {ref_docname} "
			f"belongs to insurance company '{insurance_company}', not NHIF"
		)

	services, _requested_rows, _diseases = get_services(source_doc, preapproval_no)
	if len(services) == 0:
		frappe.msgprint("No servuce(s) to cancel an Pre-Approvals")
		return False

	if not settings_doc:
		settings_doc = frappe.get_cached_doc("HMS TZ Setting", source_doc.company)

	url = f"{settings_doc.nhifservice_url}/api/PreApprovals/CancelRequest?requestNo={preapproval_no}&remarks={remarks}"

	token = settings_doc.get_nhif_token()
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	r = requests.request("Post", url, headers=headers, timeout=60)
	if r.status_code != 200:
		add_log(
			request_type="CancelRequest",
			request_url=url,
			request_header=headers,
			request_body="",
			response_data=r.text,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype=ref_doctype,
			ref_docname=ref_docname,
		)

		source_doc.add_comment(
			comment_type="Comment",
			text=f"Cancel Pre-approval request Failed..!<br><br>Status Code: {r.status_code}<br>NHIF Response: <b>{r.text}<b>",
		)
		frappe.db.commit()

		frappe.msgprint(
			title="NHIF API Error",
			msg=f"Cancel Pre-approval failed<br><br>Status Code: {r.status_code}<br>NHIF Response: <b>{r.text}<b>",
			indicator="red",
		)
		return False

	else:
		data = json.loads(r.text)
		add_log(
			request_type="CancelRequest",
			request_url=url,
			request_header=headers,
			request_body="",
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype=ref_doctype,
			ref_docname=ref_docname,
		)

		for row, _template_doctype, _template_name in get_service_rows(source_doc):
			if row.preapproval_no == preapproval_no:
				row.preapproval_status = "Cancelled"
				row.preapproval_no = ""
				row.preapproval_cancel_remarks = remarks
				row.db_update()
				row.reload()

		source_doc.db_update()
		source_doc.db_update_all()
		source_doc.reload()

		request_ids = "<ul>"
		for row in data:
			request_ids += f"<li>{row.get('RequestedServiceID')} <br> {row.get('RequestID')}</li>"
		request_ids += "</ul>"

		source_doc.add_comment(
			comment_type="Comment",
			text=f"Pre-approval request canceled successfully!<br><br>Pre-Approval No: <b>{preapproval_no}</b><br><br>NHIF RequestID(s): {request_ids}",
		)

		return True


def get_service_rows(doc):
	"""Yield (row, template doctype, template name) for encounter services and inpatient beds.

	Only the oldest MAX_BEDS_PER_REQUEST beds awaiting pre-approval are yielded; later requests take the rest.
	"""
	for child in get_childs_map():
		for row in doc.get(child.get("table")) or []:
			yield row, child.get("doctype"), row.get(child.get("item"))

	if doc.doctype != "Patient Encounter" or not doc.get("inpatient_record"):
		return

	pending_beds = 0
	for row in frappe.get_doc("Inpatient Record", doc.inpatient_record).inpatient_occupancies:
		if is_preapproval_required(row):
			pending_beds += 1
			if pending_beds > MAX_BEDS_PER_REQUEST:
				continue

		service_unit_type = frappe.get_cached_value(
			"Healthcare Service Unit", row.service_unit, "service_unit_type"
		)
		yield row, "Healthcare Service Unit Type", service_unit_type


def is_preapproval_required(row):
	if row.doctype == "Inpatient Occupancy":
		return not row.preapproval_no

	return not (
		row.get("prescribe")
		or row.get("is_not_available_inhouse")
		or row.get("is_cancelled")
		or row.get("preapproval_status") == "Accepted"
	)


def get_service_dates(row):
	"""Beds run from check-in to check-out; an open bed ends today."""
	if row.doctype == "Inpatient Occupancy":
		return str(getdate(row.check_in)), str(getdate(row.check_out or nowdate()))

	return nowdate(), nowdate()


def get_disease_row(row):
	medical_code = row.get("medical_code") or ""
	preliminary_tables = ["lab_test_prescription", "radiology_procedure_prescription"]
	status = "Preliminary" if row.parentfield in preliminary_tables else "Final"
	return {"diseaseCode": get_disease_code(medical_code[6:].strip()), "status": status}


@request_cache
def get_service_item(template_doctype, template_name, company, insurance_company):
	"""Return (NHIF item code, item); beds of one type share the lookup."""
	ref_code = get_item_refcode(template_doctype, template_name, company, insurance_company)
	return ref_code, frappe.get_cached_value(template_doctype, template_name, "item")


def get_service_rate(row, item, doc):
	"""Beds use their stored amount, filling it in when it is missing."""
	if row.doctype != "Inpatient Occupancy":
		return get_item_rate(item, doc.company, doc.insurance_subscription, doc.insurance_company)

	if not row.amount:
		amount = get_item_rate(item, doc.company, doc.insurance_subscription, doc.insurance_company)
		row.db_set("amount", amount, update_modified=False)

	return row.amount


def get_services(doc, preapproval_no=None):
	diseases = []
	services = []
	requested_rows = []

	for row, template_doctype, template_name in get_service_rows(doc):
		if not template_name:
			continue

		if preapproval_no and row.preapproval_no == preapproval_no:
			services.append(template_name)
			continue

		if not is_preapproval_required(row):
			continue

		ref_code, item = get_service_item(template_doctype, template_name, doc.company, doc.insurance_company)
		item_rate = get_service_rate(row, item, doc)
		effective_date, end_date = get_service_dates(row)

		services.append(
			{
				"itemCode": ref_code,
				"usage": "",
				"effectiveDate": effective_date,
				"endDate": end_date,
				"quantityRequested": row.get("quantity") or 1,
				"unitPrice": item_rate,
				"remarks": "",
			}
		)
		requested_rows.append((row, template_name, ref_code))

		if row.doctype != "Inpatient Occupancy":
			diseases.append(get_disease_row(row))

	return services, requested_rows, diseases
