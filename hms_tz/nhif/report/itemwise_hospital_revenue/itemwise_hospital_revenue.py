# apps/hms_tz/hms_tz/nhif/report/itemwise_hospital_revenue/itemwise_hospital_revenue.py

# Copyright (c) 2023, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe.query_builder import DocType
import frappe.utils

# Correct imports: Case and ValueWrapper come from pypika.terms
from pypika.terms import Case, ValueWrapper, Criterion


def execute(filters=None):
    """
    Entry point for the “Itemwise Hospital Revenue” Query Report.
    Validates that mutually‐exclusive filters are not both set,
    then builds columns and fetches data accordingly.
    """
    if not filters:
        filters = {}

    # Prevent mutually exclusive filters
    if filters.get("show_only_ongoing_ipds") == 1 and filters.get("show_only_prev_items_for_discharged_ipds") == 1:
        frappe.throw(
            "Cannot filter by both Ongoing IPDs and Discharged IPDs<br>"
            "Uncheck one of these filters and try again."
        )

    # Build report columns
    columns = get_columns(filters)

    # Decide which data‐fetching function to call
    if filters.get("show_only_cancelled_items") == 1:
        data = get_cancelled_data(filters)
    elif not filters.get("payment_mode"):
        data = get_cash_insurance_data(filters)
    elif filters.get("payment_mode") == "Cash":
        data = get_cash_data(filters)
    else:
        data = get_insurance_data(filters)

    return columns, data


def get_columns(filters):
    """
    Defines the column structure for the report header.
    """
    base_columns = [
        {"fieldname": "date", "label": "Date", "fieldtype": "Date", "width": 120},
        {"fieldname": "patient", "label": "Patient", "fieldtype": "Data", "width": 120},
        {"fieldname": "patient_name", "label": "Patient Name", "fieldtype": "Data", "width": 150},
        {"fieldname": "patient_type", "label": "Patient Type", "fieldtype": "Data", "width": 120},
        {"fieldname": "appointment_no", "label": "Appointment No", "fieldtype": "Link",
         "options": "Patient Appointment", "width": 140},
    ]

    if filters.get("show_only_cancelled_items"):
        # When only cancelled items are requested, show these extra columns
        return base_columns + [
            {"fieldname": "encounter_no", "label": "Encounter No", "fieldtype": "Link",
             "options": "Patient Encounter", "width": 140},
            {"fieldname": "bill_doctype", "label": "Bill Doctype", "fieldtype": "Data", "width": 140},
            {"fieldname": "bill_no", "label": "Bill No", "fieldtype": "Data", "width": 140},
            {"fieldname": "service_name", "label": "Service Name", "fieldtype": "Data", "width": 200},
            {"fieldname": "qty", "label": "Qty", "fieldtype": "Int", "width": 80},
            {"fieldname": "rate", "label": "Rate", "fieldtype": "Currency", "width": 120},
            {"fieldname": "amount", "label": "Amount", "fieldtype": "Currency", "width": 120},
            {"fieldname": "payment_method", "label": "Payment Method", "fieldtype": "Data", "width": 140},
            {"fieldname": "reference_no", "label": "LRPMT Return No", "fieldtype": "Data", "width": 160},
            {"fieldname": "reason", "label": "Cancellation Reason", "fieldtype": "Data", "width": 200},
            {"fieldname": "date_modified", "label": "Date Modified", "fieldtype": "Datetime", "width": 180},
        ]

    # Default (non‐cancelled) columns
    return base_columns + [
        {"fieldname": "bill_no", "label": "Bill No", "fieldtype": "Data", "width": 140},
        {"fieldname": "service_type", "label": "Service Type", "fieldtype": "Data", "width": 160},
        {"fieldname": "service_name", "label": "Service Name", "fieldtype": "Data", "width": 200},
        {"fieldname": "qty", "label": "Qty", "fieldtype": "Int", "width": 80},
        {"fieldname": "rate", "label": "Rate", "fieldtype": "Currency", "width": 120},
        {"fieldname": "discount_amount", "label": "Discount Amount", "fieldtype": "Currency", "width": 140},
        {"fieldname": "amount", "label": "Amount", "fieldtype": "Currency", "width": 120},
        {"fieldname": "payment_method", "label": "Payment Method", "fieldtype": "Data", "width": 140},
        {"fieldname": "department", "label": "Department", "fieldtype": "Data", "width": 150},
        {"fieldname": "practitioner", "label": "Practitioner", "fieldtype": "Link",
         "options": "Healthcare Practitioner", "width": 160},
        {"fieldname": "service_unit", "label": "Service Unit", "fieldtype": "Link",
         "options": "Healthcare Service Unit", "width": 160},
        {"fieldname": "sales_invoice", "label": "Sales Invoice", "fieldtype": "Link",
         "options": "Sales Invoice", "width": 140},
        {"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 120},
        {"fieldname": "date_modified", "label": "Date Modified", "fieldtype": "Datetime", "width": 180},
    ]


# ====================== DATA HANDLERS ======================

def get_cash_insurance_data(filters):
    """
    When no payment_mode is specified, return both Cash (Appointment/Lab)
    + Insurance (Appointment/Lab) data.
    """
    appoints = get_prev_and_ongoing_ipds(filters)
    data = []

    # Cash (appointment + lab) stubs
    data += get_cash_appointment_data(filters, appoints)
    data += get_cash_lab_data(filters, appoints)

    # Insurance HSR (appointment + lab)
    data += get_insurance_hsr_appointment_data(filters, appoints)
    data += get_insurance_hsr_lab_data(filters, appoints)

    return data


def get_cash_data(filters):
    """
    When payment_mode == “Cash”, return only Cash data.
    """
    appoints = get_prev_and_ongoing_ipds(filters)
    data = []
    data += get_cash_appointment_data(filters, appoints)
    data += get_cash_lab_data(filters, appoints)
    return data


def get_insurance_data(filters):
    """
    When payment_mode != “Cash” (i.e. an insurance company is selected),
    return only Insurance HSR data.
    """
    appoints = get_prev_and_ongoing_ipds(filters)
    data = []
    data += get_insurance_hsr_appointment_data(filters, appoints)
    data += get_insurance_hsr_lab_data(filters, appoints)
    return data


# ====================== CASH DATA IMPLEMENTATIONS ======================

def get_cash_appointment_data(filters, appoints):
    # Stub: replace this block with your actual “cash appointment” logic if needed.
    return []


def get_cash_lab_data(filters, appoints):
    # Stub: replace this block with your actual “cash lab” logic if needed.
    return []


# ====================== INSURANCE HSR IMPLEMENTATIONS ======================

def get_insurance_hsr_appointment_data(filters, appoints):
    """
    Fetch all Healthcare Service Request Payments with payment_type="Insurance"
    that are linked to a Patient Appointment.
    """
    hsr = DocType("Healthcare Service Request")
    hsr_payment = DocType("Healthcare Service Request Payment")
    pa = DocType("Patient Appointment")

    query = (
        frappe.qb
            .from_(hsr_payment)
            .inner_join(hsr).on(hsr_payment.parent == hsr.name)
            .inner_join(pa).on(hsr.source_docname == pa.name)
            .select(
                pa.appointment_date.as_("date"),
                pa.name.as_("appointment_no"),
                pa.name.as_("bill_no"),
                pa.patient.as_("patient"),
                pa.patient_name.as_("patient_name"),
                Case()
                    .when(pa.appointment_type.like("Emergency"), "In-Patient")
                    .else_("Out-Patient")
                    .as_("patient_type"),
                hsr_payment.service_type.as_("service_type"),
                hsr_payment.service_name.as_("service_name"),
                hsr_payment.insurance_company.as_("payment_method"),
                hsr_payment.qty.as_("qty"),
                hsr_payment.rate.as_("rate"),
                hsr_payment.amount.as_("amount"),
                Case()
                    .when(pa.status == "Closed", "Submitted")
                    .else_("Draft")
                    .as_("status"),
                pa.practitioner.as_("practitioner"),
                pa.department.as_("department"),  # Patient Appointment *does* have a 'department' field
                pa.service_unit.as_("service_unit"),
                pa.modified.as_("date_modified"),
            )
            .where(
                (hsr.company == filters.get("company"))
                & (hsr_payment.payment_type == "Insurance")
                & (pa.status != "Cancelled")
                & (pa.follow_up == 0)
                & (pa.has_no_consultation_charges == 0)
                & (hsr.docstatus == 1)
            )
    )

    # If “previous items for discharged IPDs” is checked, limit to < from_date AND only listed appointments
    if filters.get("show_only_prev_items_for_discharged_ipds") == 1 and appoints:
        query = query.where(
            (pa.appointment_date < filters.get("from_date"))
            & (pa.name.isin(appoints))
        )
    else:
        # Otherwise, filter by the date range [from_date : to_date]
        query = query.where(
            (pa.appointment_date[filters.get("from_date"):filters.get("to_date")])
        )

    # Apply “service_type” filter if given
    if filters.get("service_type"):
        query = query.where(hsr_payment.service_type == filters.get("service_type"))

    # If payment_mode is set (and not “Cash”), filter by the insurance_company
    if filters.get("payment_mode") and filters.get("payment_mode") != "Cash":
        query = query.where(hsr_payment.insurance_company == filters.get("payment_mode"))

    # If “only ongoing IPDs” is checked, restrict to appointments in that IPD list
    if filters.get("show_only_ongoing_ipds") == 1 and appoints:
        query = query.where(pa.name.isin(appoints))

    return query.run(as_dict=True)


def get_insurance_hsr_lab_data(filters, appoints):
    """
    Fetch all Healthcare Service Request Payments with payment_type="Insurance"
    that are linked to a Lab Prescription (child of Patient Encounter).
    NOTE: We do NOT reference “Lab Test” here. We join HSR → Lab Prescription → Patient Encounter.
    """
    hsr = DocType("Healthcare Service Request")
    hsr_payment = DocType("Healthcare Service Request Payment")
    lab_prescription = DocType("Lab Prescription")
    pe = DocType("Patient Encounter")

    query = (
        frappe.qb
            .from_(hsr_payment)
            .inner_join(hsr).on(hsr_payment.parent == hsr.name)
            # Join the HSR Payment’s ref_docname (Lab Prescription name)
            .inner_join(lab_prescription).on(hsr_payment.ref_docname == lab_prescription.name)
            # Join that Lab Prescription back to its parent Patient Encounter
            .inner_join(pe).on(lab_prescription.parent == pe.name)
            .select(
                pe.encounter_date.as_("date"),
                pe.appointment.as_("appointment_no"),
                lab_prescription.name.as_("bill_no"),
                pe.patient.as_("patient"),
                pe.patient_name.as_("patient_name"),
                Case()
                    .when(pe.inpatient_record.isnull(), "Out-Patient")
                    .else_("In-Patient")
                    .as_("patient_type"),
                hsr_payment.service_type.as_("service_type"),
                hsr_payment.service_name.as_("service_name"),
                hsr_payment.insurance_company.as_("payment_method"),
                hsr_payment.qty.as_("qty"),
                hsr_payment.rate.as_("rate"),
                hsr_payment.amount.as_("amount"),
                # Lab prescriptions do not have a submitted state; default all to “Draft”
                ValueWrapper("Draft").as_("status"),
                pe.practitioner.as_("practitioner"),
                pe.medical_department.as_("department"),  # ← corrected: use 'medical_department'
                lab_prescription.department_hsu.as_("service_unit"),
                lab_prescription.modified.as_("date_modified"),
            )
            .where(
                (hsr.company == filters.get("company"))
                & (hsr_payment.payment_type == "Insurance")
                & (lab_prescription.prescribe == 0)
                & (lab_prescription.is_cancelled == 0)
                & (lab_prescription.is_not_available_inhouse == 0)
                & (hsr.docstatus == 1)
            )
    )

    # If “previous items for discharged IPDs” is checked AND appoints list is non‐empty:
    if filters.get("show_only_prev_items_for_discharged_ipds") == 1 and appoints:
        query = query.where(
            (pe.encounter_date < filters.get("from_date"))
            & (pe.appointment.isin(appoints))
        )
    else:
        # Otherwise, filter by encounter_date in [from_date : to_date]
        query = query.where(
            (pe.encounter_date[filters.get("from_date"):filters.get("to_date")])
        )

    # Service type filter
    if filters.get("service_type"):
        query = query.where(hsr_payment.service_type == filters.get("service_type"))

    # Insurance company filter (if not Cash)
    if filters.get("payment_mode") and filters.get("payment_mode") != "Cash":
        query = query.where(hsr_payment.insurance_company == filters.get("payment_mode"))

    # Ongoing IPD filter
    if filters.get("show_only_ongoing_ipds") == 1 and appoints:
        query = query.where(pe.appointment.isin(appoints))

    return query.run(as_dict=True)


# ====================== UTILITY FUNCTIONS ======================

def get_prev_and_ongoing_ipds(filters):
    """
    Returns a list of 'Patient Appointment' names that correspond to:
      • Ongoing IPDs (if show_only_ongoing_ipds == 1), OR
      • Previously discharged IPDs (if show_only_prev_items_for_discharged_ipds == 1)
    """
    ip = DocType("Inpatient Record")

    query = (
        frappe.qb
            .from_(ip)
            .select(ip.patient_appointment.as_("patient_appointment"))
            .where((ip.company == filters.get("company")))
    )

    # Filter IPDs by payment_mode: “Cash” means no insurance_subscription
    if filters.get("payment_mode") == "Cash":
        query = query.where(
            (ip.insurance_subscription.isnull())
            | (ip.insurance_subscription == "")
        )
    elif filters.get("payment_mode") and filters.get("payment_mode") != "Cash":
        query = query.where(ip.insurance_company == filters.get("payment_mode"))

    # If only ongoing IPDs:
    if filters.get("show_only_ongoing_ipds") == 1:
        query = query.where(
            Criterion.any([
                (
                    (ip.scheduled_date <= filters.get("to_date"))
                    & (ip.status != "Discharged")
                ),
                (
                    (ip.scheduled_date <= filters.get("to_date"))
                    & (ip.discharge_date > filters.get("to_date"))
                    & (ip.status == "Discharged")
                )
            ])
        )
    # If only previous discharged IPDs:
    elif filters.get("show_only_prev_items_for_discharged_ipds") == 1:
        query = query.where(
            (ip.scheduled_date < filters.get("from_date"))
            & (ip.discharge_date <= filters.get("to_date"))
            & (ip.status == "Discharged")
        )

    results = query.run(as_dict=True)
    # Return unique patient_appointment names
    return list({row.patient_appointment for row in results if row.patient_appointment})


def get_cancelled_data(filters):
    """
    Stub for “show_only_cancelled_items”. Implement as needed.
    Currently returns an empty list.
    """
    return []


@frappe.whitelist()
def get_payment_modes(company):
    """
    Returns a list of payment modes (Cash + healthcare insurance companies)
    for the given company—used to populate a filter dropdown.
    """
    payment_modes = ["", "Cash"]
    if not company:
        return payment_modes

    insurance_companies = frappe.get_all(
        "Healthcare Insurance Company",
        filters={"company": company},
        pluck="name",
    )

    return payment_modes + sorted(insurance_companies)
