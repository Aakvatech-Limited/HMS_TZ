# -*- coding: utf-8 -*-
# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import json

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.utils import flt, get_fullname, nowdate

from hms_tz.hms_tz.doctype.hospital_revenue_entry.hospital_revenue_entry import (
    create_revenue_entry,
    update_revenue_entry,
)
from hms_tz.nhif.api.healthcare_utils import create_delivery_note_from_LRPT
from hms_tz.nhif.api.lab_test import check_cash_payments_from_encounter
from hms_tz.nhif.api.medical_record import update_medical_record
from hms_tz.nhif.utils import validate_issued_services, validate_point_of_care


def after_insert(doc, method):
    create_revenue_entry(doc)


def before_save(doc, method):
    get_ot_schedule(doc)
    get_preop_notes(doc)


def onload(doc, method):
    check_cash_payments_from_encounter(
        doc=doc,
        ref_doctype="ref_doctype",
        ref_docname_field="ref_docname",
        prescription_field="procedure_prescription",
        item_name_field="procedure_name",
        item_descriptor="Clinical Procedures",
    )


def on_submit(doc, methd):
    validate_swab_count(doc)
    update_procedure_prescription(doc)
    update_revenue_entry(
        "Clinical Procedure",
        doc.name,
        "Procedure Prescription",
        doc.hms_tz_ref_childname,
        lrpmt_status="Submitted",
    )
    if doc.inpatient_record:
        create_postoperative_recovery(doc)

    if doc.ot_schedule:
        frappe.db.set_value(
            "OT Schedule",
            doc.ot_schedule,
            "status",
            "Completed"
        )


def on_update_after_submit(doc, method=None):
    update_medical_record(doc)


def before_submit(doc, method):
    if not doc.procedure_notes:
        frappe.throw(
            title= _("<b style='color: red; font-size: 16px; font-weight: bold;'>Procedure Notes Missing</b>"),
            msg=_(
                """<div style='border-left: 4px solid #ffc107; background-color: #fff3cd; padding: 15px; border-radius: 10px; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1); margin: 10px;'>
                    <p style='font-size: 16px;'>Procedure notes are required. Please write the Procedure Notes.</p>
                </div>"""
            )
        )

    if doc.is_restricted and not doc.approval_number:
        frappe.throw(
            _(f"Approval number is required for <b>{doc.procedure_template}</b>. Please set the Approval Number.")
        )

    validate_point_of_care(doc, "validate_poc_at_procedure")
    validate_issued_services(doc.doctype, doc.name, is_restricted=doc.is_restricted, company=doc.company)

    doc.hms_tz_submitted_by = get_fullname(frappe.session.user)
    doc.hms_tz_user_id = frappe.session.user
    doc.hms_tz_submitted_date = nowdate()


def create_delivery_note(doc):
    if doc.ref_doctype and doc.ref_docname and doc.ref_doctype == "Patient Encounter":
        patient_encounter_doc = frappe.get_cached_doc(doc.ref_doctype, doc.ref_docname)
        create_delivery_note_from_LRPT(doc, patient_encounter_doc)


def update_procedure_prescription(doc):
    if doc.ref_doctype == "Patient Encounter":
        hsrp = DocType("Healthcare Service Request Payment")
        (
            frappe.qb.update(hsrp)
            .set(hsrp.lrpmt_status, "Submitted")
            .where((hsrp.ref_docname == doc.hms_tz_ref_childname))
        ).run()


def get_ot_schedule(doc):
    if doc.ot_schedule:
        return

    ot_schedule = frappe.get_cached_value(
        "OT Schedule",
        {
            "patient": doc.patient,
            "company": doc.company,
            "procedure_template": doc.procedure_template
        },
        "name"
    )
    if not ot_schedule:
        return

    doc.ot_schedule = ot_schedule
    doc.surgical_team = []

    ot_schedule_doc = frappe.get_cached_doc("OT Schedule", ot_schedule)
    for row in ot_schedule_doc.get("surgical_team"):
        doc.append("surgical_team", {
            "practitioner": row.practitioner,
            "role": row.role
        })


def get_preop_notes(doc):
    if doc.pre_operative_note:
        return

    pre_operative_note = frappe.get_cached_value(
        "Preoperative Assessment",
        {"clinical_procedure": doc.name},
        "pre_operative_note"
    )

    if not pre_operative_note:
        pre_operative_note = frappe.get_cached_value(
            "Preoperative Assessment",
            {
                "patient": doc.patient,
                "ot_schedule": doc.ot_schedule,
                "service_name": doc.procedure_template
            },
            "pre_operative_note"
        )

    if not pre_operative_note:
        return

    doc.pre_operative_note = pre_operative_note


def validate_swab_count(doc):
    """Validate swab and instrument counts match before/after surgery.

    Called from on_submit of Clinical Procedure.
    """
    # Only validate if counts have been entered
    if not doc.get("swab_count_before") and not doc.get("instrument_count_before"):
        return

    errors = []

    swab_before = doc.get("swab_count_before") or 0
    swab_after = doc.get("swab_count_after") or 0
    instrument_before = doc.get("instrument_count_before") or 0
    instrument_after = doc.get("instrument_count_after") or 0

    if swab_before and swab_before != swab_after:
        errors.append(
            _("Swab count mismatch: Before ({0}) ≠ After ({1})").format(
                swab_before, swab_after
            )
        )

    if instrument_before and instrument_before != instrument_after:
        errors.append(
            _("Instrument count mismatch: Before ({0}) ≠ After ({1})").format(
                instrument_before, instrument_after
            )
        )

    if errors and not doc.get("count_verified"):
        frappe.throw(
            _("Count verification failed:<br>{0}<br><br>"
              "Please verify counts are correct and check 'Count Verified' to proceed.").format(
                "<br>".join(errors)
            )
        )


@frappe.whitelist()
def create_vital_signs_from_cp(clinical_procedure: str, **kwargs) -> str:
    """Create a Vital Signs record from the Clinical Procedure Charts tab.

    Reuses the same pattern as nurse_record.create_vital_signs.
    """
    cp = frappe.get_doc("Clinical Procedure", clinical_procedure)
    vs = frappe.new_doc("Vital Signs")
    vs.patient = cp.patient
    vs.appointment = cp.appointment
    vs.inpatient_record = cp.inpatient_record
    vs.company = cp.company

    vital_fields = [
        "temperature", "pulse", "respiratory_rate",
        "bp_systolic", "bp_diastolic",
        "oxygen_saturation_spo2", "rbg",
        "weight", "height_in_cm",
        "tongue", "abdomen", "reflexes",
        "vital_signs_note",
        "signs_date",
        "signs_time",
    ]
    for field in vital_fields:
        if kwargs.get(field):
            vs.set(field, kwargs[field])

    # Convert height_in_cm to height (in meters) and calculate BMI
    if vs.height_in_cm:
        vs.height = flt(vs.height_in_cm) / 100.0
        if flt(vs.weight) and vs.height:
            vs.bmi = flt(flt(vs.weight) / (vs.height * vs.height), 2)

    # Set BP display string
    if vs.bp_systolic and vs.bp_diastolic:
        vs.bp = f"{vs.bp_systolic}/{vs.bp_diastolic} mmHg"

    vs.flags.ignore_permissions = True
    vs.flags.ignore_mandatory = True
    vs.flags.ignore_create_encounter = True
    vs.insert()
    vs.submit()
    return vs.name


@frappe.whitelist()
def get_anesthesia_records(clinical_procedure: str) -> list[dict]:
    """Fetch existing Anesthesia Records linked to a Clinical Procedure."""
    return frappe.db.get_all(
        "Anesthesia Record",
        filters={"clinical_procedure": clinical_procedure},
        fields=[
            "name", "anesthetist", "anesthesia_type",
            "asa_grade", "airway_approach",
            "start_time", "end_time", "complications",
        ],
        order_by="creation desc",
    )


@frappe.whitelist()
def create_anesthesia_record(clinical_procedure: str, **kwargs) -> str:
    """Create an Anesthesia Record from the Clinical Procedure dialog."""

    cp = frappe.get_doc("Clinical Procedure", clinical_procedure)
    ar = frappe.new_doc("Anesthesia Record")
    ar.patient = cp.patient
    ar.appointment = cp.appointment
    ar.inpatient_record = cp.inpatient_record
    ar.clinical_procedure = clinical_procedure
    ar.ot_schedule = cp.get("ot_schedule") or ""
    ar.company = cp.company

    simple_fields = [
        "anesthetist", "anesthesia_type", "airway_approach", "asa_grade",
        "start_time", "end_time",
        "pre_induction_vitals", "post_induction_vitals",
        "complications", "notes",
    ]
    for field in simple_fields:
        if kwargs.get(field):
            ar.set(field, kwargs[field])

    # Parse drugs_text into child table rows
    # Format: "Drug Name, Dosage, Route" — one per line
    drugs_text = kwargs.get("drugs") or []
    if drugs_text:
        drugs = json.loads(drugs_text)
        for drug in drugs:
            #  = json.loads(drg)
            ar.append("drugs_administered", {
                "drug": drug.get("drug"),
                # "drug_name": drug.get("drug"),
                "dosage": drug.get("dosage"),
                "route": drug.get("route"),
                "administered_time": drug.get("administered_time")
            })

    ar.insert(ignore_permissions=True)
    return ar.name


@frappe.whitelist()
def create_implant_registry(clinical_procedure: str, **kwargs) -> str:
    """Create an Implant Registry from the Clinical Procedure dialog and submit it."""
    cp = frappe.get_doc("Clinical Procedure", clinical_procedure)
    ir = frappe.new_doc("Implant Registry")
    ir.patient = cp.patient
    ir.clinical_procedure = clinical_procedure
    ir.company = cp.company

    simple_fields = [
        "implant_type", "manufacturer", "lot_number", "serial_number",
        "anatomical_location", "expiry_date", "implanted_by",
        "implant_date", "status", "notes",
    ]
    for field in simple_fields:
        if kwargs.get(field):
            ir.set(field, kwargs[field])

    ir.insert(ignore_permissions=True)
    ir.submit()

    # Link implant to the clinical procedure
    frappe.db.set_value(
        "Clinical Procedure", clinical_procedure, "implant", ir.name
    )

    return ir.name


@frappe.whitelist()
def create_surgical_specimen(clinical_procedure: str, **kwargs) -> str:
    """Create a Surgical Specimen from the Clinical Procedure dialog."""

    cp = frappe.get_doc("Clinical Procedure", clinical_procedure)
    ss = frappe.new_doc("Surgical Specimen")
    ss.patient = cp.patient
    ss.clinical_procedure = clinical_procedure
    ss.company = cp.company
    ss.patient_age = cp.patient_age
    ss.patient_sex = cp.patient_sex

    simple_fields = [
        "specimen_name",
        "biopsy_type",
        "fixative_used",
        "time_placed_in_fixative",
        "side",
        "no_of_containers",
        "special_request",
        "practitioner",
        "site_collected",
        "collection_date",
        "collection_time",
        "provisional_diagnosis",
        "relevant_findings",
    ]
    for field in simple_fields:
        if kwargs.get(field):
            ss.set(field, kwargs[field])

    ss.insert(ignore_permissions=True)

    frappe.db.set_value(
        "Clinical Procedure", clinical_procedure, "surgical_specimen", ss.name
    )

    return ss.name


def create_postoperative_recovery(doc):
    """Auto-create a Postoperative Recovery record when the Clinical Procedure
    has an inpatient record and is submitted."""
    # Avoid duplicates
    if frappe.db.exists("Postoperative Recovery", {"clinical_procedure": doc.name, "docstatus": ["!=", 2]}):
        return

    pr = frappe.new_doc("Postoperative Recovery")
    pr.patient = doc.patient
    pr.clinical_procedure = doc.name
    pr.company = doc.company
    pr.ot_schedule = doc.get("ot_schedule") or ""
    pr.posting_date = frappe.utils.nowdate()
    pr.admission_time = frappe.utils.now_datetime()

    pr.flags.ignore_permissions = True
    pr.flags.ignore_mandatory = True
    pr.insert()

    frappe.msgprint(
        _("Postoperative Recovery {0} created.").format(
            frappe.utils.get_link_to_form("Postoperative Recovery", pr.name)
        ),
        alert=True,
        indicator="green",
    )

