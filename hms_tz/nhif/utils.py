from collections import defaultdict

import frappe
from frappe.utils import get_url_to_form

from hms_tz.hms_tz.doctype.healthcare_service_request.healthcare_service_request import get_item_refcode
from hms_tz.nhif.doctype.insurance_approval_log.insurance_approval_log import add_approval_usage
from hms_tz.nhif.nhif_api.approval import issue_approved_service
from hms_tz.nhif.nhif_api.approval_status import validate_approved_qty
from hms_tz.nhif.nhif_api.verification import get_poc_reference_no

SERVICE_FIELDS = {
	"Lab Test": ("Lab Test Template", "template"),
	"Radiology Examination": ("Radiology Examination Template", "radiology_examination_template"),
	"Clinical Procedure": ("Clinical Procedure Template", "procedure_template"),
	"Therapy Session": ("Therapy Type", "therapy_type"),
}
SERVICE_TYPES = (*(service_type for service_type, _field in SERVICE_FIELDS.values()), "Medication")
NOT_SERVICED_STATES = ("Not Serviced", "Submitted but Not Serviced")


@frappe.whitelist()
def get_poc_reference_no_for_lrpmt(
	ref_doctype,
	ref_docname,
	service_type,
	service_name,
	fingerprint=None,
	fpcode=None,
	biometric_method="NONE",
):
	"""
	Get POC reference number for a given document.
	"""

	doc = frappe.get_cached_doc(ref_doctype, ref_docname)
	if doc.get("poc_reference_no"):
		frappe.msgprint(f"POC Reference No: {doc.poc_reference_no} already exists for this document")
		return

	point_of_care = get_patient_care_name(service_type, service_name)

	data = get_poc_reference_no(
		point_of_care=point_of_care,
		practitioner=doc.get("practitioner") or doc.get("healthcare_practitioner"),
		fingerprint=fingerprint,
		fpcode=fpcode,
		biometric_method=biometric_method.upper(),
		company=doc.company,
		appointment_id=doc.get("appointment") or doc.get("hms_tz_appointment_no"),
		authorization_no=doc.get("authorization_number") or "",
		ref_doctype=ref_doctype,
		ref_docname=ref_docname,
	)

	if data:
		doc.db_set("poc_reference_no", data.get("ReferenceNo"))
		doc.add_comment(
			"Comment",
			text=f"POC Reference No: <strong>{data.get('ReferenceNo')}</strong> for {point_of_care} is successfully created.",
		)

		filters = {
			"name": ["!=", doc.name],
		}
		if doc.doctype == "Delivery Note":
			filters["reference_name"] = doc.get("reference_name")
			filters["reference_doctype"] = doc.get("reference_doctype")
		else:
			filters["ref_docname"] = doc.get("ref_docname")
			filters["ref_doctype"] = doc.get("ref_doctype")

		records = frappe.db.get_all(
			doc.doctype,
			filters=filters,
		)

		for record in records:
			record_doc = frappe.get_cached_doc(doc.doctype, record.name)
			if not record_doc.get("insurance_company") and not record_doc.get("coverage_plan_name"):
				continue

			record_doc.db_set("poc_reference_no", data.get("ReferenceNo"))
			record_doc.add_comment(
				"Comment",
				text=f"POC Reference No: <strong>{data.get('ReferenceNo')}</strong> for {point_of_care} is successfully created.",
			)

		return True


@frappe.whitelist()
def issue_nhif_service(
	ref_doctype, ref_docname, service_type, service_name, fingerprint, fpcode, qty=1, biometric_method="NONE"
):
	# not cached: the Delivery Note Item set_value below leaves a cached Delivery Note stale
	doc = frappe.get_doc(ref_doctype, ref_docname)
	if doc.get("service_reference_no"):
		frappe.msgprint(
			f"Service Reference No: {doc.service_reference_no} is already issued for this document"
		)
		return {}

	settings_doc = frappe.get_cached_doc("HMS TZ Setting", doc.company)

	if not settings_doc.enable_nhif_api:
		frappe.msgprint("NHIF API is disabled")
		return {}

	data = {}

	if doc.doctype == "Delivery Note":
		approval_items = []
		for row in doc.items:
			if row.is_restricted == 1 and not row.service_reference_no:
				if row.approval_number:
					validate_approved_qty(row, f"{row.item_code} (line {row.idx})")
					approval_items.append(row)
				else:
					frappe.throw(f"Item: {row.item_code} require Approval Number to issue this Item")

		for d in approval_items:
			service_data = issue_approved_service(
				doc,
				d.approval_number,
				service_type,
				d.item_code,
				fingerprint,
				fpcode,
				qty=d.qty,
				rate=d.rate,
				settings_doc=settings_doc,
				biometric_method=biometric_method,
			)

			if service_data:
				frappe.db.set_value(
					"Delivery Note Item",
					d.name,
					"service_reference_no",
					service_data.get("ServiceReferenceNo"),
				)
				add_approval_usage(doc, d.approval_number, d.qty, service_data.get("ServiceReferenceNo"))

				data.update(service_data)

	else:
		if not doc.approval_number:
			frappe.throw(
				"Approval Number is not set for this document, Please get Approval Number from NHIF."
			)

		service_data = issue_approved_service(
			doc,
			doc.approval_number,
			service_type,
			service_name,
			fingerprint,
			fpcode,
			qty=1,
			settings_doc=settings_doc,
			biometric_method=biometric_method,
		)

		if service_data:
			doc.db_set("service_reference_no", service_data.get("ServiceReferenceNo"))
			add_approval_usage(doc, doc.approval_number, 1, service_data.get("ServiceReferenceNo"))

			data.update(service_data)

	if data and not doc.get("poc_reference_no"):
		# keep the issued service reference if the POC request fails
		frappe.db.commit()  # nosemgrep
		get_poc_reference_no_for_lrpmt(
			doc.doctype, doc.name, service_type, service_name, fingerprint, fpcode, biometric_method
		)

	return data


def get_patient_care_name(service_type, service_name):
	"""
	Get the name of the point of care based on service type and service name.
	"""
	if not service_type:
		return None

	if not service_name and service_type == "Medication":
		return "Pharmacy"

	points_of_care = frappe.get_cached_value(service_type, service_name, "points_of_care")

	if not points_of_care:
		url = get_url_to_form(service_type, service_name)
		frappe.throw(
			f"Point of care is not set for <a href='{url}'>{frappe.bold(service_name)}</a>, Please set it first."
		)

	return points_of_care


def validate_point_of_care(doc, field):
	"""
	Validate that the point of care is set for the given document.
	"""

	if doc.doctype == "Delivery Note" and doc.is_return:
		return

	insurance_field = "insurance_company"
	if doc.doctype == "Delivery Note":
		insurance_field = "customer"

	if not doc.get(insurance_field) or "NHIF" not in doc.get(insurance_field, ""):
		return

	if not frappe.get_cached_value("HMS TZ Setting", doc.company, "enable_nhif_api"):
		return

	if not doc.get("poc_reference_no"):
		if frappe.get_cached_value("HMS TZ Setting", doc.company, field):
			frappe.throw(
				"<b>POC reference</b> no is not set for this document, Please get POC reference no from NHIF."
			)


def validate_issued_services(ref_doctype, ref_docname, is_restricted=False, company=None):
	"""
	Validate if there are issued services for the given document.
	"""

	if not is_restricted:
		return

	settings_doc = frappe.get_cached_doc("HMS TZ Setting", company)
	if not settings_doc.enable_nhif_api:
		return

	if not frappe.get_cached_value(ref_doctype, ref_docname, "service_reference_no"):
		frappe.throw("Service is not Issued to NHIF. Please issue NHIF services before proceeding.")


def validate_main_diagnosis_code(doc):
	if not doc.main_diagnosis_code and doc.insurance_company and "NHIF" in doc.insurance_company:
		frappe.throw(
			title="<b>Main Diagnosis Code Missing</b>",
			msg="<b>Main Diagnosis Code is required for NHIF insured patients. Please set it first.</b>",
		)


def needs_approval_number(target):
	return target.is_restricted and not target.approval_number


def get_nhif_visit(doc):
	"""Return the card no and insurance company of an NHIF visit; other insurers have no approval API yet."""
	appointment = doc.get("appointment") or doc.get("hms_tz_appointment_no")
	if not appointment:
		return None

	visit = frappe.get_cached_value(
		"Patient Appointment", appointment, ["coverage_plan_card_number", "insurance_company"], as_dict=True
	)
	if not visit or "NHIF" not in (visit.insurance_company or "") or not visit.coverage_plan_card_number:
		return None

	return visit


def get_services_needing_approval(doc):
	"""Yield (row, service type, service name) of each restricted service without an approval number."""
	if doc.doctype == "Delivery Note":
		for item in doc.items:
			if needs_approval_number(item) and item.reference_name:
				drug_code = frappe.db.get_value(item.reference_doctype, item.reference_name, "drug_code")
				yield item, "Medication", drug_code
	elif needs_approval_number(doc):
		service_type, service_field = SERVICE_FIELDS[doc.doctype]
		yield doc, service_type, doc.get(service_field)


def get_approval_targets(doc, visit):
	"""Map each insurer item code to the rows of a draft, serviceable `doc` that still need an approval number."""
	targets = defaultdict(list)
	if doc.docstatus != 0 or doc.get("workflow_state") in NOT_SERVICED_STATES:
		return targets

	for target, service_type, service_name in get_services_needing_approval(doc):
		if not service_name:
			continue

		item_code = get_item_refcode(service_type, service_name, doc.company, visit.insurance_company)
		label = (
			f"Row {target.idx}: {target.item_name}"
			if target.doctype == "Delivery Note Item"
			else service_name
		)
		targets[item_code].append({"doctype": target.doctype, "name": target.name, "label": label})

	return targets


def get_service_names(item_codes, insurance_customer):
	"""Map each insurer item code to the names of our service templates whose item carries that code."""
	codes_of_item = defaultdict(set)
	for row in frappe.get_all(
		"Item Customer Detail",
		filters={"customer_name": insurance_customer, "ref_code": ["in", list(item_codes)]},
		fields=["parent", "ref_code"],
	):
		codes_of_item[row.parent].add(row.ref_code)

	names = defaultdict(list)
	if not codes_of_item:
		return names

	for service_type in SERVICE_TYPES:
		for template in frappe.get_all(
			service_type, filters={"item": ["in", list(codes_of_item)]}, fields=["name", "item"]
		):
			for item_code in codes_of_item[template.item]:
				names[item_code].append(template.name)

	return names
