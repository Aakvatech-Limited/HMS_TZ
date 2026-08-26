import frappe
from frappe.utils import get_url_to_form

from hms_tz.nhif.nhif_api.approval import issue_approved_service
from hms_tz.nhif.nhif_api.verification import get_poc_reference_no


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
	doc = frappe.get_cached_doc(ref_doctype, ref_docname)

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

			data.update(service_data)

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
