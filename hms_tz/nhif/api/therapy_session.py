import frappe


def before_insert(doc, method):
    validate_not_serviced(doc)


def after_insert(doc, method):
    if doc.therapy_plan:
        plan = frappe.get_doc("Therapy Plan", doc.therapy_plan)
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
                break

    doc.save(ignore_permissions=True)


def before_submit(doc, method):
    validate_not_serviced(doc)


def validate_not_serviced(doc):
    if doc.therapy_plan:
        status = frappe.db.get_value("Therapy Plan", doc.therapy_plan, "status")
        if status == "Not Serviced":
            frappe.throw(
                f"This Therapy Plan: {frappe.bold(doc.therapy_plan)} is Not Serviced,\
                    Please select another Therapy Plan. or cancel this therapy session"
            )
