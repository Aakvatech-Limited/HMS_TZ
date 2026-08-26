import frappe
from frappe import _
from frappe.query_builder import DocType

from hms_tz.hms_tz.doctype.hospital_revenue_entry.hospital_revenue_entry import update_revenue_entry
from hms_tz.nhif.utils import validate_issued_services, validate_point_of_care


def before_insert(doc, method):
	validate_not_serviced(doc)


def after_insert(doc, method):
	if doc.therapy_plan:
		plan = frappe.get_cached_doc("Therapy Plan", doc.therapy_plan)
		doc.hms_tz_insurance_coverage_plan = plan.hms_tz_insurance_coverage_plan
		doc.insurance_company = plan.insurance_company
		doc.ref_doctype = plan.ref_doctype
		doc.ref_docname = plan.ref_docname

		if not doc.appointment:
			doc.appointment = plan.hms_tz_appointment

	if doc.therapy_type:
		for row in plan.therapy_plan_details:
			if row.therapy_type == doc.therapy_type:
				doc.is_restricted = row.is_restricted
				doc.hms_tz_ref_childname = row.hms_tz_ref_childname
				doc.service_unit = row.department_hsu
				break

	doc.save(ignore_permissions=True)

	update_revenue_entry(
		"Therapy Session",
		doc.name,
		"Therapy Plan Detail",
		doc.hms_tz_ref_childname,
		therapy_plan=doc.therapy_plan,
	)


def before_submit(doc, method):
	validate_not_serviced(doc)
	validate_point_of_care(doc, "validate_poc_at_therapy")
	validate_issued_services(doc.doctype, doc.name, is_restricted=doc.is_restricted, company=doc.company)

	if doc.is_restricted and not doc.approval_number:
		frappe.throw(
			_(f"Approval number is required for <b>{doc.therapy_type}</b>. Please set the Approval Number.")
		)


def on_submit(doc, method):
	update_therapy_detail(doc)
	update_revenue_entry(
		"Therapy Session", doc.name, "Therapy Plan Detail", doc.hms_tz_ref_childname, lrpmt_status="Submitted"
	)


def validate_not_serviced(doc):
	if doc.therapy_plan:
		status = frappe.get_cached_value("Therapy Plan", doc.therapy_plan, "status")
		if status == "Not Serviced":
			frappe.throw(
				f"This Therapy Plan: {frappe.bold(doc.therapy_plan)} is Not Serviced,\
                    Please select another Therapy Plan. or cancel this therapy session"
			)


def update_therapy_detail(doc):
	if doc.ref_doctype == "Patient Encounter":
		hsrp = DocType("Healthcare Service Request Payment")
		(
			frappe.qb.update(hsrp)
			.set(hsrp.lrpmt_status, "Submitted")
			.where(hsrp.ref_docname == doc.hms_tz_ref_childname)
		).run()
