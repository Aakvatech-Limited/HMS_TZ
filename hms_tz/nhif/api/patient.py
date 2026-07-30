# -*- coding: utf-8 -*-
# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

from datetime import date

import frappe
from erpnext import get_default_company
from frappe import _
from frappe.utils import flt, getdate, nowdate
from frappe.utils.background_jobs import enqueue

from hms_tz.jubilee.api.api import create_jubilee_subscription
from hms_tz.nhif.api.healthcare_utils import remove_special_characters
from hms_tz.nhif.nhif_api.verification import get_card_details_by_card_no, get_card_details_by_national_id


def validate(doc, method):
    # validate date of birth
    if date.today() < getdate(doc.dob):
        frappe.throw(_("The date of birth cannot be later than today's date"))

    check_national_id(doc.national_id, doc.is_new(), doc.name, "validate")
    check_card_number(doc.card_no, doc.is_new(), doc.name, "validate")

    # replace initial 0 with 255 and remove all the unnecessray characters
    if doc.mobile:
        doc.mobile = remove_special_characters(doc.mobile)
        if doc.mobile and doc.mobile[0] == "0":
            doc.mobile = "255" + doc.mobile[1:]
    if doc.next_to_kin_mobile_no:
        doc.next_to_kin_mobile_no = remove_special_characters(doc.next_to_kin_mobile_no)
        if doc.next_to_kin_mobile_no and doc.next_to_kin_mobile_no[0] == "0":
            doc.next_to_kin_mobile_no = "255" + doc.next_to_kin_mobile_no[1:]
    validate_mobile_number(doc.name, doc.mobile)
    if not doc.is_new():
        update_patient_history(doc)
    else:
        doc.insurance_card_detail = (doc.card_no or "") + ", "


@frappe.whitelist()
def validate_mobile_number(doc_name, mobile=None):
    if mobile:
        mobile_patients_list = frappe.get_all("Patient", filters={"mobile": mobile, "name": ["!=", doc_name]})
        if len(mobile_patients_list) > 0:
            frappe.msgprint(_("This mobile number is used by another patient"))


@frappe.whitelist()
def get_nhif_patient_info(
    card_no=None,
    national_id=None,
    ref_doctype=None,
    ref_docname=None,
    check_patient_info_from_his=False,
):
    if not card_no and not national_id:
        frappe.msgprint(_("Please provide either Card No or National ID"))
        return

    # TODO: need to be fixed to support multiple company
    company = get_default_company()
    if not company:
        company = frappe.defaults.get_user_default("Company")

    if not company:
        company = frappe.get_list(
            "HMS TZ Setting",
            fields=["company"],
            filters={"enable_nhif_api": 1},
        )[0].company

    if not company:
        frappe.throw(_("No companies found to connect to NHIF"))

    settings_doc = frappe.get_cached_doc("HMS TZ Setting", company)
    if settings_doc.enable_nhif_api == 0:
        frappe.msgprint("Please Enable NHIF API to proceed..")
        return

    if check_patient_info_from_his and settings_doc.check_patient_info_on_his == 0:
        return
        # frappe.msgprint("Please Enable Check Patient Info on HIS to proceed..")
        # return

    if card_no:
        card_details = get_card_details_by_card_no(
            company,
            card_no,
            ref_doctype,
            ref_docname=ref_docname,
            settings_doc=settings_doc,
        )
        return card_details
    elif national_id:
        card_details = get_card_details_by_national_id(
            company,
            national_id,
            ref_doctype,
            ref_docname=ref_docname,
            settings_doc=settings_doc,
        )
        return card_details


def update_patient_history(doc):
    # Remarked till multi company setting is required and feasible from Patient doctype 2021-03-20 19:57:14
    # company = get_default_company()
    # update_history = frappe.get_cached_value(
    #     "Company NHIF Settings", company, "update_patient_history")
    # if not update_history:
    #     return

    medical_history = ""
    for row in doc.codification_table:
        if row.definition:
            medical_history += row.definition + "\n"
    doc.medical_history = medical_history

    medication = ""
    for row in doc.chronic_medications:
        if row.drug_name:
            medication += row.drug_name + "\n"
    doc.medication = medication
    if doc.medical_history or doc.medication:
        frappe.msgprint(
            _("Update patient history for medical history and chronic medications"),
            alert=True,
        )


@frappe.whitelist()
def check_national_id(national_id, is_new=None, patient=None, caller=None):
    if not national_id:
        return False

    filters = {"national_id": national_id}
    if not is_new and patient:
        filters["name"] = ["!=", patient]

    patients = frappe.db.get_all("Patient", filters=filters)
    if len(patients):
        if caller:
            frappe.throw(
                f"NationalID: <b>{national_id}</b> used with patient: <b>{patient}</b>, Please change NationalID to Proceed"
            )
        return patients[0].name
    else:
        return False


@frappe.whitelist()
def check_card_number(card_no, is_new=None, patient=None, caller=None):
    if not card_no:
        return False

    filters = {"insurance_card_detail": ["like", "%" + card_no + "%"]}
    if not is_new and patient:
        filters["name"] = ["!=", patient]

    patients = frappe.db.get_all("Patient", filters=filters)
    if len(patients):
        if caller:
            frappe.throw(
                f"Cardno: <b>{card_no}</b> used with patient: <b>{patient}</b>, Please change Cardno to Proceed"
            )
        return patients[0].name
    else:
        return False


def create_nhif_subscription(doc):
    plan = frappe.db.get_list(
        "Healthcare Insurance Coverage Plan",
        filters={"nhif_scheme_id": doc.scheme_id, "is_active": 1},
        fields=["name", "insurance_company"],
    )

    plan_row = plan[0] if len(plan) == 1 else None
    if not plan_row:
        frappe.msgprint(
            _(f"Failed to find matching plan for SchemeId: {doc.scheme_id}"),
            alert=True,
        )
        return

    sub_doc = frappe.new_doc("Healthcare Insurance Subscription")
    sub_doc.patient = doc.name
    sub_doc.insurance_company = plan_row.insurance_company
    sub_doc.healthcare_insurance_coverage_plan = plan_row.name
    sub_doc.coverage_plan_card_number = doc.card_no
    sub_doc.national_id = doc.national_id
    sub_doc.hms_tz_scheme_id = doc.scheme_id


    if doc.card_type:
        verifier_doc = frappe.get_cached_doc("Healthcare Card Verifier", doc.card_type)

        sub_doc.verifier_id = verifier_doc.verifier_id
        sub_doc.card_type_id = verifier_doc.card_type_id
        sub_doc.card_type_name = verifier_doc.card_type_name

    frappe.flags.auto_his = True
    sub_doc.save(ignore_permissions=True)
    sub_doc.submit()
    frappe.msgprint(
        _(f"<h3>AUTO</h3> Healthcare Insurance Subscription: {sub_doc.name} is created for {plan_row.name}")
    )
    frappe.flags.auto_his = False


def after_insert(doc, method):
    if doc.card_no:
        doc.insurance_card_detail = (doc.card_no or "") + ", "

    if doc.scheme_id:
        create_nhif_subscription(doc)

    if doc.insurance_provider == "Jubilee":
        card_no = doc.card_no or doc.national_id
        create_jubilee_subscription(doc.name, card_no, "Jubilee")


@frappe.whitelist()
def enqueue_update_cash_limit(old_cash_limit, new_cash_limit):
    if getdate(nowdate()).strftime("%A") != "Saturday":
        frappe.throw(
            "<h4 class='font-weight-bold text-center'>\
            Please run this routine only on Saturday</h4>"
        )

    data = dict(old_value=old_cash_limit, new_value=new_cash_limit)

    enqueue(
        method=update_cash_limit,
        queue="default",
        timeout=600000,
        job_name="update_new_cash_limit",
        is_async=True,
        kwargs=data,
    )


def update_cash_limit(kwargs):
    data = kwargs
    patient_list = frappe.get_all("Patient", {"status": "Active"}, pluck="name")
    for name in patient_list:
        try:
            doc = frappe.get_cached_doc("Patient", name)
            if flt(doc.cash_limit) != flt(data.get("new_value")):
                doc.cash_limit = flt(data.get("new_value"))
                doc.db_update()
        except Exception:
            frappe.log_error(frappe.get_traceback())

    frappe.db.commit()


@frappe.whitelist()
def validate_missing_patient_dob(patient: str):
    patient_name, dob = frappe.get_cached_value("Patient", patient, ["patient_name", "dob"])
    if not dob:
        return False
    return True


@frappe.whitelist()
def get_card_verifier():
    verifiers = frappe.db.get_all("Healthcare Card Verifier", pluck="name", order_by="card_type_name asc")
    return verifiers