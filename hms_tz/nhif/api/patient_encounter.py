# -*- coding: utf-8 -*-
# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import json

import frappe
from erpnext.accounts.utils import get_balance_on
from frappe import _
from frappe.query_builder import DocType
from frappe.query_builder.functions import Date
from frappe.utils import cint, cstr, date_diff, flt, fmt_money, getdate, nowdate, nowtime
from healthcare.healthcare.doctype.healthcare_settings.healthcare_settings import (
    get_income_account,
    get_receivable_account,
)

from hms_tz.hms_tz.doctype.healthcare_service_request.healthcare_service_request import (
    create_healthcare_docs,
    create_service_request,
    get_childs_map,
    get_discount_percent,
    get_drug_quantity,
    get_item_price,
    get_item_rate,
    get_mop_amount,
    inpatient_billing,
    msgPrint,
    msgThrow,
    validate_nhif_patient_claim_status,
    validate_stock_item,
)
from hms_tz.hms_tz.doctype.hospital_revenue_entry.hospital_revenue_entry import create_revenue_entry
from hms_tz.nhif.api.patient_appointment import calculate_patient_age
from hms_tz.nhif.utils import validate_main_diagnosis_code, validate_point_of_care


def on_trash(doc, method):
    pmr_list = frappe.get_all(
        "Patient Medical Record",
        fields={"name"},
        filters={
            "reference_doctype": "Patient Encounter",
            "reference_name": doc.name,
        },
    )
    for pmr_doc in pmr_list:
        frappe.delete_doc("Patient Medical Record", pmr_doc.name, ignore_permissions=True)


def before_insert(doc, method):
    doc.encounter_date = nowdate()
    doc.encounter_time = nowtime()

    if not doc.patient_age:
        doc.patient_age = calculate_patient_age(doc.patient)

    if doc.insurance_company and "NHIF" in doc.insurance_company:
        validate_nhif_patient_claim_status(
            "Patient Encounter",
            doc.company,
            doc.appointment,
            doc.insurance_company,
        )
    set_admission_service_type(doc)


# regency rock: 95
def after_insert(doc, method):
    if not doc.patient_age:
        doc.patient_age = calculate_patient_age(doc.patient)

    if doc.company and doc.mode_of_payment:
        pharmacy_details = frappe.get_cached_value(
            "HMS TZ Setting",
            doc.company,
            [
                "auto_set_pharmacy_on_patient_encounter",
                "opd_cash_pharmacy",
                "ipd_cash_pharmacy",
            ],
            as_dict=1,
        )

        if pharmacy_details and pharmacy_details.auto_set_pharmacy_on_patient_encounter == 1:
            if doc.inpatient_record:
                if not pharmacy_details.ipd_cash_pharmacy:
                    frappe.throw(
                        _(f"<b>Please set IPD Cash Pharmacy in Company: <b>{doc.company}</b> to allow auto set of pharmacy</b>"))
                doc.default_healthcare_service_unit = pharmacy_details.ipd_cash_pharmacy
            else:
                if not pharmacy_details.opd_cash_pharmacy:
                    frappe.throw(
                        _(f"<b>Please set OPD Cash Pharmacy in Company: <b>{doc.company}</b>  to allow auto set of pharmacy</b>"))
                doc.default_healthcare_service_unit = pharmacy_details.opd_cash_pharmacy

    if doc.insurance_coverage_plan:
        pharmacy_details = frappe.get_cached_value(
            "Healthcare Insurance Coverage Plan",
            doc.insurance_coverage_plan,
            [
                "auto_set_pharmacy_on_patient_encounter",
                "opd_insurance_pharmacy",
                "ipd_insurance_pharmacy",
            ],
            as_dict=1,
        )

        if pharmacy_details and pharmacy_details.auto_set_pharmacy_on_patient_encounter == 1:
            if doc.inpatient_record:
                if not pharmacy_details.ipd_insurance_pharmacy:
                    frappe.throw(
                        _(f"<b>Please set IPD Insurance Pharmacy in Healthcare Insurance Coverage Plan: <b>{doc.insurance_coverage_plan}</b> to allow auto set of pharmacy</b>"))
                doc.default_healthcare_service_unit = pharmacy_details.ipd_insurance_pharmacy
            else:
                if not pharmacy_details.opd_insurance_pharmacy:
                    frappe.throw(
                        _(f"<b>Please set OPD Insurance Pharmacy in Healthcare Insurance Coverage Plan: <b>{doc.insurance_coverage_plan}</b> to allow auto set of pharmacy</b>"))
                doc.default_healthcare_service_unit = pharmacy_details.opd_insurance_pharmacy
    set_price_list(doc)

    if doc.encounter_type == "Initial":
        doc.poc_reference_no = ""

    doc.save()

    if doc.appointment and doc.encounter_type == "Initial":
        appointment_doc = frappe.get_cached_doc("Patient Appointment", doc.appointment)
        create_revenue_entry(appointment_doc)


def set_price_list(doc):
    price_list = None
    if doc.insurance_subscription:
        hic_plan = frappe.get_cached_value(
            "Healthcare Insurance Subscription",
            doc.insurance_subscription,
            "healthcare_insurance_coverage_plan",
        )
        price_list = frappe.get_cached_value("Healthcare Insurance Coverage Plan", hic_plan, "price_list")
    elif doc.mode_of_payment:
        price_list = frappe.get_cached_value("Mode of Payment", doc.mode_of_payment, "price_list")
    if price_list:
        doc.price_list = price_list


def on_submit_validation(doc, method):
    child_tables = {
        "lab_test_prescription": "lab_test_code",
        "radiology_procedure_prescription": "radiology_examination_template",
        "procedure_prescription": "procedure",
        "drug_prescription": "drug_code",
        "therapies": "therapy_type",
    }

    if not doc.reference_encounter and doc.encounter_type == "Initial":
        doc.reference_encounter = doc.name

    if not doc.healthcare_package_order:
        show_last_prescribed(doc, method)
        show_last_prescribed_for_lrpt(doc, method)

    checkـforـduplicate(doc, method)
    add_LRPMT_template_attributes(doc, method)
    validate_prescribed_items(doc, method, child_tables)
    validate_medical_code(doc, method)

    # shm rock: 151
    set_practitioner_name(doc, method)

    if (
        not doc.healthcare_service_unit and
        not doc.healthcare_package_order and
        "Direct Cash" not in doc.practitioner
    ):
        frappe.throw(_("Healthcare Service Unit not set"))

    set_item_coverage(doc, method, child_tables)

    validate_totals(doc, method)


def add_LRPMT_template_attributes(doc, method):
    childs_map = get_childs_map()

    for child in childs_map:
        for row in doc.get(child.get("table")):
            template_doc = frappe.get_cached_doc(child.get("doctype"), row.get(child.get("item")))
            if template_doc.disabled:
                msgThrow(
                    _(f"{child.get('doctype')}: <b>{row.get(child.get('item'))}</b> selected at Row#: {row.idx} is <b>disabled</b>. Please select an enabled item."),
                    method,
                )
            company_option = None
            for option in template_doc.company_options:
                if doc.company == option.company:
                    company_option = option.company

                    if child.get("doctype") != "Medication" and row.doctype != "Drug Prescription":
                        row.department_hsu = option.service_unit

            if not company_option:
                msgThrow(
                    _(f"No company option found for template: {frappe.bold(row.get(child.get('item')))} and company: {frappe.bold(doc.company)}"),
                    method,
                )

            if child.get("doctype") == "Clinical Procedure Template" and row.doctype == "Procedure Prescription":
                if template_doc.is_inpatient and not doc.inpatient_record:
                    msgThrow(
                        _(f"<h4>This Procedure: <strong>{frappe.bold(row.get(child.get('item')))}</strong> is allowed for Admitted Patient only</h4>"),
                        method,
                    )
            if child.get("doctype") == "Medication" and row.doctype == "Drug Prescription":
                if doc.insurance_subscription and template_doc.medication_category == "Category S Medication":
                    frappe.msgprint(
                        f"Item: {row.get(child.get('item'))} is Category S Medication",
                        alert=True,
                    )

                # auto calculating quantity
                if not row.quantity:
                    row.quantity = get_drug_quantity(row)


def validate_prescribed_items(doc, method, child_tables):
    if doc.healthcare_package_order:
        return

    prescribed_list = ""
    for key, value in child_tables.items():
        table = doc.get(key)
        for row in table:
            quantity = 0
            row_item = row.get("drug_code") or row.get("therapy_type")
            if row_item:
                quantity += cint(row.get("quantity")) or cint(row.get("no_of_sessions"))

                if not quantity:
                    frappe.throw(
                        _(f"Quantity for Item: {frappe.bold(row_item)}, Row: {frappe.bold(row.idx)} can not be zero")
                    )

            if (not doc.insurance_subscription) or row.prescribe or row.is_not_available_inhouse:
                row.prescribe = 1
                prescribed_list += "-  <b>" + row.get(value) + "</b><BR>"

                if row.is_not_available_inhouse:
                    prescribed_list += " - THIS ITEM IS NOT AVAILABLE INHOUSE "
                prescribed_list += "<BR>"

            elif not row.prescribe:
                if row.get("no_of_sessions") and doc.insurance_subscription:
                    if row.no_of_sessions != 1:
                        row.no_of_sessions = 1
                        frappe.msgprint(
                            _(f"No of sessions have been set to 1 for {row.get(value)} as per insurance rules."),
                            alert=True,
                        )

            if not row.is_not_available_inhouse and row.get("doctype") == "Drug Prescription":
                validate_stock_item(
                    row.get(value),
                    quantity,
                    doc.company,
                    row.get("prescribe"),
                    healthcare_service_unit=row.get("healthcare_service_unit"),
                    method=method,
                )

    if prescribed_list:
        msgPrint(
            _(
                f"{prescribed_list}<BR>The above been prescribed. <b>Request the patient to visit the"
                " cashier for billing/cash payment</b> or prescription printout."
            ),
            method,
        )


def set_item_coverage(doc, method, child_tables):
    if not doc.insurance_subscription:
        return

    if not doc.insurance_coverage_plan:
        frappe.throw(_("Healthcare Insurance Coverage Plan is Not defiend"))

    service_templates = {}
    for key, value in child_tables.items():
        for row in doc.get(key):
            if row.get("override_subscription") == 1 or row.prescribe == 1:
                row.is_restricted = 0
                row.has_copayment = 0
                continue

            # service_templates is like
            # {
            #   "CBC": [cbc1_lab_prescription_line_object, # cbc2_lab_prescription_line_object],
            #   "XRay Abdomen": [radiology_prescription_line_object],
            #   "Panadol": [drug_prescription_line_object]
            # }
            rows_affected = service_templates.setdefault(row.get(value), [])
            rows_affected.append(row)

    # hsic => Healthcare Service Insurance Coverage
    hsic_list = frappe.get_all(
        "Healthcare Service Insurance Coverage",
        fields={
            "healthcare_service_template",
            "maximum_quantity",
            "has_copayment",
            "approval_mandatory_for_claim",
        },
        filters={
            "is_active": 1,
            "healthcare_insurance_coverage_plan": doc.insurance_coverage_plan,
            "start_date": ("<=", nowdate()),
            "end_date": (">=", nowdate()),
            "healthcare_service_template": ("in", service_templates.keys()),
        },
        order_by="modified desc",
    )
    # hsic_map is like {"CBC": HSIC_object_for_CBC, "XRay Abdomen":
    # HSIC_object_for_xray_abdomen, "Panadol": HSIC_object_for_panadol}
    hsic_map = {hsic.healthcare_service_template: hsic for hsic in hsic_list}
    is_exclusions = frappe.get_cached_value(
        "Healthcare Insurance Coverage Plan",
        doc.insurance_coverage_plan,
        "is_exclusions",
    )

    validate_item_coverage(
        method,
        doc.company,
        hsic_map,
        is_exclusions,
        service_templates,
        doc.insurance_coverage_plan,
    )


def validate_item_coverage(
    method,
    company,
    hsic_map,
    is_exclusions,
    service_templates,
    insurance_coverage_plan,
):
    for template in service_templates:
        """
        If the value of "is_exclusions" is 1, it means the template should not be listed in the "hsic_map". This is because when "is_exclusions" is 1, it indicates that the template which is in "hsic_map" is not covered.

        However, there's an exception to this rule. If the "approval_mandatory_for_claim" for that template is also 1, it means the template is covered but needs extra authorization for approval.

        This apply for NHIF and Non NHIF Insurance
        """

        if is_exclusions:
            if template in hsic_map.keys() and hsic_map[template].approval_mandatory_for_claim == 0:
                mark_item_not_covered(
                    method,
                    company,
                    template,
                    service_templates,
                    insurance_coverage_plan,
                )

            elif template in hsic_map.keys() and hsic_map[template].approval_mandatory_for_claim == 1:
                set_copayment_and_restricted(template, service_templates, hsic_map)

        else:
            """
            If the value of "is_exclusions" is 0, it means the template must be listed in the "hsic_map" for it to be covered.
            This is because when "is_exclusions" is 0, it indicates that the template which is in "hsic_map" is covered.

            No need to check for "approval_mandatory_for_claim" on this part because if the template is not listed in the "hsic_map" means the template is completely not covered.

            This apply for NHIF and Non NHIF Insurance.
            """
            if template not in hsic_map.keys():
                mark_item_not_covered(
                    method,
                    company,
                    template,
                    service_templates,
                    insurance_coverage_plan,
                )

            elif template in hsic_map.keys():
                set_copayment_and_restricted(template, service_templates, hsic_map)


def mark_item_not_covered(
    method,
    company,
    template,
    service_templates,
    insurance_coverage_plan,
):
    for row_item in service_templates[template]:
        if (
            company
            and frappe.get_cached_value(
                "HMS TZ Setting",
                company,
                "auto_prescribe_items_on_patient_encounter",
            )
            == 1
        ):
            row_item.prescribe = 1

        row_item.is_restricted = 0
        row_item.has_copayment = 0

    msg = _(
        f"{template} <h4 style='background-color:LightCoral'>NOT COVERED</h4> \
            in Healthcare Insurance Coverage Plan {str(insurance_coverage_plan)} plan.<br>Patient should pay cash for this service"
    )
    msgThrow(
        msg,
        method,
    )


def set_copayment_and_restricted(template, service_templates, hsic_map):
    """
    This function is used to set the "has_copayment" and "is_restricted" fields for each row in the "service_templates" dictionary.
    """

    coverage_info = hsic_map[template]
    for row in service_templates[template]:
        row.has_copayment = coverage_info.has_copayment
        row.is_restricted = coverage_info.approval_mandatory_for_claim
        if row.is_restricted == 1:
            frappe.msgprint(
                _(f"{row.doctype} with template {template} requires additional authorization"),
                alert=True,
            )


def checkـforـduplicate(doc, method):
    items = []
    for item in doc.drug_prescription:
        if item.drug_code not in items:
            items.append(item.drug_code)
        else:
            msgThrow(
                _(f"Drug '{item.drug_code}' is duplicated in line '{item.idx}' in Drug Prescription"),
                method,
            )


@frappe.whitelist()
def duplicate_encounter(encounter):
    doc = frappe.get_cached_doc("Patient Encounter", encounter)
    if doc.healthcare_package_order:
        frappe.throw(
            _("Cannot duplicate an encounter of healthcare package order, Please let the patient to create appointment again"))
    if doc.insurance_company and "NHIF" in doc.insurance_company:
        validate_nhif_patient_claim_status(
            "Patient Encounter",
            doc.company,
            doc.appointment,
            doc.insurance_company,
        )

    if not doc.docstatus == 1 or doc.encounter_type == "Final" or doc.duplicated == 1:
        frappe.msgprint(
            _("This encounter cannot be duplicated. Check if it is already duplicated" " using Menu/Links."),
            alert=True,
        )
        return
    encounter_doc = frappe.copy_doc(doc)
    encounter_dict = encounter_doc.as_dict()
    child_tables = {
        "drug_prescription": "previous_drug_prescription",
        "lab_test_prescription": "previous_lab_prescription",
        "procedure_prescription": "previous_procedure_prescription",
        "radiology_procedure_prescription": "previous_radiology_procedure_prescription",
        "therapies": "previous_therapy_plan_detail",
    }

    # Copy the examination detail from previous encounter before clearing it
    clinical_notes = (
        cstr(encounter_dict["hms_tz_previous_examination_detail"]) + "\n" + cstr(encounter_dict["examination_detail"])
    )

    fields_to_clear = [
        "name",
        "owner",
        "creation",
        "modified",
        "modified_by",
        "docstatus",
        "amended_from",
        "amendment_date",
        "parentfield",
        "parenttype",
        "sales_invoice",
    ]

    for key, value in child_tables.items():
        cur_table = encounter_dict.get(key)
        if not cur_table:
            continue
        for row in cur_table:
            new_row = row
            for fieldname in fields_to_clear:
                new_row[fieldname] = None
            encounter_dict[value].append(new_row)
        encounter_dict[key] = []
    encounter_dict["duplicated"] = 0
    encounter_dict["examination_detail"] = ""
    encounter_dict["hms_tz_previous_examination_detail"] = clinical_notes

    encounter_dict["encounter_type"] = "Ongoing"
    if not encounter_dict.get("reference_encounter"):
        encounter_dict["reference_encounter"] = doc.name

    encounter_dict["from_encounter"] = doc.name
    encounter_dict["previous_total"] = doc.previous_total + doc.current_total
    encounter_dict["current_total"] = 0
    encounter_dict["encounter_date"] = nowdate()
    encounter_dict["encounter_time"] = nowtime()
    encounter_doc = frappe.get_doc(encounter_dict)
    encounter_doc.save(ignore_permissions=True)
    frappe.db.set_value(doc.doctype, doc.name, "duplicated", 1)
    frappe.msgprint(_(f"Patient Encounter {encounter_doc.name} created"))
    return encounter_doc.name


def on_submit(doc, method):
    if doc.inpatient_record and not doc.insurance_subscription and not doc.healthcare_package_order:
        # Cash inpatient billing
        if doc.mode_of_payment:
            validate_patient_balance_vs_patient_costs(
                doc.patient,
                doc.patient_name,
                doc.appointment,
                doc.inpatient_record,
                doc.company,
            )
        inpatient_billing(doc, method)
    else:
        # insurance patient
        on_submit_validation(doc, method)
        create_service_request(doc_obj=doc)

    if doc.healthcare_package_order and not doc.inpatient_record:
        # package patient
        encounter_list = [doc.name]
        create_healthcare_docs(doc.reference_encounter, encounter_list, method="on_submit")

    if doc.inpatient_record:
        update_inpatient_record_consultancy(doc)


@frappe.whitelist()
def get_chronic_diagnosis(patient):
    data = frappe.db.get_all(
        "Codification Table",
        filters={
            "parent": patient,
            "parenttype": "Patient",
            "parentfield": "codification_table",
        },
        fields=["code_value", "code", "definition"],
    )
    return data


@frappe.whitelist()
def add_chronic_diagnosis(patient, encounter):
    patient_doc = frappe.get_cached_doc("Patient", patient)
    encounter_doc = frappe.get_cached_doc("Patient Encounter", encounter)

    prev_diagnos = len(patient_doc.codification_table)
    medical_codes = []
    if len(patient_doc.codification_table) == 0:
        for row in encounter_doc.patient_encounter_preliminary_diagnosis:
            patient_doc.append("codification_table", row)
        patient_doc.save(ignore_permissions=True)

    else:
        for d in patient_doc.codification_table:
            medical_codes.append(d.code_value)
            for row in encounter_doc.patient_encounter_preliminary_diagnosis:
                if row.code_value not in medical_codes:
                    patient_doc.append("codification_table", row)
        patient_doc.save(ignore_permissions=True)

    if len(patient_doc.codification_table) > prev_diagnos:
        frappe.msgprint("Chronic diagnosis added successfully")
    else:
        if prev_diagnos == 0:
            frappe.msgprint("No chronic diagnosis added, <i>please save encounter and try again</i>")
        else:
            frappe.msgprint("Chronic diagnosis already exist")


@frappe.whitelist()
def get_chronic_medications(patient):
    data = frappe.get_all(
        "Chronic Medications",
        filters={
            "parent": patient,
            "parenttype": "Patient",
            "parentfield": "chronic_medications",
        },
        fields=["*"],
    )
    return data


@frappe.whitelist()
def add_chronic_medications(patient, encounter, items):
    def clear_fields(drug_row):
        for field in [
            "name",
            "owner",
            "creation",
            "modified",
            "modified_by",
            "docstatus",
            "parent",
            "parentfield",
            "parenttype",
            "doctype",
            "idx",
        ]:
            if isinstance(drug_row, dict):
                row = frappe.parse_json(drug_row)
                if hasattr(row, field):
                    del row[field]
                drug_row = frappe._dict(row)
            elif isinstance(drug_row, object):
                row = drug_row.as_dict()
                if hasattr(row, field):
                    del row[field]
                drug_row = frappe._dict(row)
            else:
                raise ValueError("Unknown type for drug_row")

        return drug_row

    patient_doc = frappe.get_cached_doc("Patient", patient)
    encounter_doc = frappe.get_cached_doc("Patient Encounter", encounter)

    chronic_drug_items = []
    items = frappe.parse_json(items)
    if len(items) > 0:
        chronic_drug_items = items
    else:
        chronic_drug_items = encounter_doc.drug_prescription

    if len(chronic_drug_items) == 0:
        frappe.throw(_("No Chronic medications to add"))

    medications = []
    prev_chronic_medications = len(patient_doc.chronic_medications)
    if len(patient_doc.chronic_medications) == 0:
        for row in chronic_drug_items:
            new_row = clear_fields(row)
            patient_doc.append("chronic_medications", new_row)
        patient_doc.save(ignore_permissions=True)

    else:
        for d in patient_doc.chronic_medications:
            for row in chronic_drug_items:
                new_row = clear_fields(row)
                if d.drug_code == new_row.drug_code:
                    d.update(new_row)
                    medications.append(d.drug_code)
                    continue

        for d_row in chronic_drug_items:
            d_new_row = clear_fields(d_row)
            if d_new_row.drug_code not in medications:
                patient_doc.append("chronic_medications", d_new_row)
        patient_doc.save(ignore_permissions=True)

    if len(patient_doc.chronic_medications) > prev_chronic_medications:
        frappe.msgprint("Chronic medication added successfully")
    else:
        frappe.msgprint("Chronic medication already exist")


def validate_totals(doc, method, show_alert=True):
    def get_current_total(doc, childs_map):
        doc.current_total = 0

        # apply discount if it is available on Heathcare Insurance Company
        discount_percent = 0
        if doc.insurance_company and "NHIF" not in doc.insurance_company:
            discount_percent = get_discount_percent(doc.insurance_company)

        for child in childs_map:
            for row in doc.get(child.get("table")):
                if (
                    row.prescribe
                    or row.is_not_available_inhouse
                    or (row.is_cancelled and not row.hms_tz_is_limit_exceeded)
                ):
                    continue

                item_code = frappe.get_cached_value(child.get("doctype"), row.get(child.get("item")), "item")
                item_price_rate = get_item_rate(
                    item_code,
                    doc.company,
                    doc.insurance_subscription,
                    doc.insurance_company,
                )

                if hasattr(row, "quantity"):
                    quantity = flt(row.quantity)
                else:
                    quantity = 1

                item_rate = item_price_rate * quantity
                doc.current_total += item_rate - (item_rate * (discount_percent / 100))

    def mark_limit_exceeded(doc, childs_map):
        for child in childs_map:
            for row in doc.get(child.get("table")):
                if row.prescribe and row.hms_tz_is_limit_exceeded:
                    row.hms_tz_is_limit_exceeded = 0
                    row.is_cancelled = 0

                if (
                    row.prescribe
                    or row.is_not_available_inhouse
                    or (row.is_cancelled and not row.hms_tz_is_limit_exceeded)
                ):
                    continue

                if not row.hms_tz_is_limit_exceeded:
                    row.hms_tz_is_limit_exceeded = 1
                    row.is_cancelled = 1

    def unmark_limit_exceeded(doc, childs_map):
        for child in childs_map:
            for row in doc.get(child.get("table")):
                if row.hms_tz_is_limit_exceeded == 1:
                    row.hms_tz_is_limit_exceeded = 0
                    row.is_cancelled = 0

    if (
        not doc.insurance_company
        or not doc.insurance_subscription
        or "NHIF" in doc.insurance_company
        or not doc.daily_limit
        or doc.daily_limit == 0
        or doc.inpatient_record
        or doc.healthcare_package_order
    ):
        return

    # Check if full Jubilee API has enabled, If yes, then no need for manual validation of daily limit
    if (
        "Jubilee" in doc.insurance_company and
        cint(frappe.get_cached_value("HMS TZ Setting", doc.company, "enable_jubilee_api")) == 1
    ):
        return

    childs_map = get_childs_map()
    if doc.encounter_type == "Initial":
        appointment_amount = frappe.get_cached_value("Patient Appointment", doc.appointment, "paid_amount")
        doc.previous_total = appointment_amount

    get_current_total(doc, childs_map)

    diff = doc.daily_limit - doc.current_total - doc.previous_total
    if diff < 0:
        diff = abs(diff)
        allow_submit_of_encounter_on_limit_exceed = frappe.get_cached_value(
            "Healthcare Insurance Coverage Plan",
            doc.insurance_coverage_plan,
            "hms_tz_submit_encounter_on_limit_exceed",
        )
        if allow_submit_of_encounter_on_limit_exceed == 0 and show_alert:
            msgThrow(_(
                f"The total daily limit of <b>{doc.daily_limit}</b> for the Insurance Subscription <b>{doc.insurance_subscription}</b> has \
                    been exceeded by <b>{diff}</b>. <br> Please contact the reception to increase \
                    limit or prescribe the items"), method=method, )
        else:
            mark_limit_exceeded(doc, childs_map)
            if show_alert:
                msgPrint(_(
                    f"The total daily limit of <b>{doc.daily_limit}</b> for the Insurance Subscription <b>{doc.insurance_subscription}</b> has \
                            been exceeded by <b>{diff}</b>. <br> Please contact the reception to increase limit"), method=method, )
    else:
        unmark_limit_exceeded(doc, childs_map)


@frappe.whitelist()
def create_sales_invoice(encounter, encounter_category, encounter_mode_of_payment):
    encounter_doc = frappe.get_cached_doc("Patient Encounter", encounter)
    encounter_category = frappe.get_cached_doc("Encounter Category", encounter_category)
    if not encounter_category.create_sales_invoice:
        return

    doc = frappe.new_doc("Sales Invoice")
    doc.patient = encounter_doc.patient
    doc.customer = frappe.get_cached_value("Patient", encounter_doc.patient, "customer")
    doc.due_date = getdate()
    doc.company = encounter_doc.company
    doc.debit_to = get_receivable_account(encounter_doc.company)
    doc.healthcare_service_unit = encounter_doc.healthcare_service_unit
    doc.healthcare_practitioner = encounter_doc.practitioner

    item = doc.append("items", {})
    item.item_code = encounter_category.encounter_fee_item
    item.description = _(f"Consulting Charges: {encounter_doc.practitioner}")
    item.income_account = get_income_account(encounter_doc.practitioner, encounter_doc.company)
    item.cost_center = frappe.get_cached_value("Company", encounter_doc.company, "cost_center")
    item.qty = 1
    item.rate = encounter_category.encounter_fee
    item.reference_dt = "Patient Encounter"
    item.reference_dn = encounter_doc.name
    item.amount = encounter_category.encounter_fee

    doc.is_pos = 1
    payment = doc.append("payments", {})
    payment.mode_of_payment = encounter_mode_of_payment
    payment.amount = encounter_category.encounter_fee

    doc.set_taxes()
    doc.flags.ignore_permissions = True
    doc.set_missing_values(for_validate=True)
    doc.flags.ignore_mandatory = True
    doc.save(ignore_permissions=True)
    doc.calculate_taxes_and_totals()
    doc.submit()
    frappe.msgprint(_(f"Sales Invoice {doc.name} created"))
    encounter_doc.sales_invoice = doc.name
    encounter_doc.db_update()

    return "true"


def update_inpatient_record_consultancy(doc):
    if doc.inpatient_record:
        item_code = frappe.get_cached_value(
            "Healthcare Practitioner",
            doc.practitioner,
            "inpatient_visit_charge_item",
        )
        rate = 0

        # apply discount if it is available on Heathcare Insurance Company
        discount_percent = 0
        if doc.insurance_company and "NHIF" not in doc.insurance_company:
            discount_percent = get_discount_percent(doc.insurance_company)

        if doc.insurance_subscription:
            item_rate = get_item_rate(
                item_code,
                doc.company,
                doc.insurance_subscription,
                doc.insurance_company,
            )
            rate = item_rate - (item_rate * (discount_percent / 100))

        elif doc.mode_of_payment:
            price_list = frappe.get_cached_value("Mode of Payment", doc.mode_of_payment, "price_list")
            rate = get_item_price(item_code, price_list, doc.company)

        record_doc = frappe.get_cached_doc("Inpatient Record", doc.inpatient_record)
        row = record_doc.append("inpatient_consultancy", {})
        row.date = nowdate()
        row.consultation_item = item_code
        row.rate = rate
        row.encounter = doc.name
        row.healthcare_practitioner = doc.practitioner
        if discount_percent > 0:
            row.hms_tz_is_discount_applied = 1

        record_doc.save(ignore_permissions=True)
        frappe.msgprint(
            _(f"Inpatient Consultancy record added for item {item_code}"),
            alert=True,
        )


def before_submit(doc, method):
    if doc.insurance_company and "NHIF" in doc.insurance_company:
        validate_main_diagnosis_code(doc)

        validate_nhif_patient_claim_status(
            "Patient Encounter",
            doc.company,
            doc.appointment,
            doc.insurance_company,
        )

    validate_preapproval_services(doc)
    validate_point_of_care(doc, "validate_poc_at_encounter")

    if not doc.healthcare_package_order:
        set_amounts(doc)

    # shm rock: 151
    set_practitioner_name(doc, method)

    if doc.inpatient_record:
        set_admission_service_type(doc)


@frappe.whitelist()
def finalized_encounter(cur_encounter, ref_encounter=None):
    patient, cur_inpatient_record = frappe.get_cached_value(
        "Patient Encounter", cur_encounter, ["patient", "inpatient_record"]
    )
    inpatient_status, inpatient_record = frappe.get_cached_value(
        "Patient", patient, ["inpatient_status", "inpatient_record"]
    )
    if inpatient_status and cur_inpatient_record == inpatient_record:
        frappe.throw(
            _(
                f"The patient {patient} has inpatient status <strong>{inpatient_status}</strong>.\
                Please process the discharge before proceeding to finalize the encounter."
            )
        )

    frappe.db.set_value("Patient Encounter", cur_encounter, "encounter_type", "Final")
    if not ref_encounter:
        frappe.db.set_value("Patient Encounter", cur_encounter, "finalized", 1)
        return

    encounters_list = frappe.db.get_all(
        "Patient Encounter",
        filters={"docstatus": 1, "reference_encounter": ref_encounter},
    )
    for element in encounters_list:
        frappe.db.set_value("Patient Encounter", element.name, "finalized", 1)

    return True


@frappe.whitelist()
def undo_finalized_encounter(cur_encounter, ref_encounter=None):
    frappe.set_value("Patient Encounter", cur_encounter, "encounter_type", "Ongoing")
    if not ref_encounter:
        frappe.set_value("Patient Encounter", cur_encounter, "finalized", 0)
        return

    encounters_list = frappe.get_all(
        "Patient Encounter",
        filters={"docstatus": 1, "reference_encounter": ref_encounter},
    )
    for element in encounters_list:
        frappe.set_value("Patient Encounter", element.name, "finalized", 0)

    return True


def set_amounts(doc):
    childs_map = get_childs_map()

    # apply discount if it is available on Heathcare Insurance Company
    discount_percent = 0
    if doc.insurance_company and "NHIF" not in doc.insurance_company:
        discount_percent = get_discount_percent(doc.insurance_company)

    for child in childs_map:
        for row in doc.get(child.get("table")):
            if row.amount:
                continue

            item_rate = 0
            item_code = frappe.get_cached_value(child.get("doctype"), row.get(child.get("item")), "item")
            if not item_code:
                frappe.throw(
                    _(f"Item code for {row.get(child.get('item'))} set in row {row.idx} was not found.<br>Please set the item code in {child.get('doctype')}."))

            if row.prescribe and not doc.insurance_subscription:
                mode_of_payment = ""
                if doc.get("mode_of_payment"):
                    mode_of_payment = doc.get("mode_of_payment")
                elif doc.get("encounter_mode_of_payment"):
                    mode_of_payment = doc.get("encounter_mode_of_payment")
                item_rate = get_mop_amount(item_code, mode_of_payment, doc.company, doc.patient)
                if not item_rate or item_rate == 0:
                    frappe.throw(_(f"Cannot get rate for item {item_code} in {mode_of_payment}"))

            elif row.prescribe and doc.insurance_subscription:
                price_list = frappe.get_cached_value("Company", doc.company, "default_price_list")
                if not price_list:
                    frappe.throw(_(f"Please set default price list in company {doc.company}"))

                item_rate = get_item_price(item_code, price_list, doc.company)
                if not item_rate or item_rate == 0:
                    frappe.throw(_(f"Cannot get mode of payment rate for item {item_code}"))

            elif not row.prescribe:
                item_price_rate = get_item_rate(
                    item_code,
                    doc.company,
                    doc.insurance_subscription,
                    doc.insurance_company,
                )
                item_rate = item_price_rate - (item_price_rate * (discount_percent / 100))

                if discount_percent > 0:
                    row.hms_tz_is_discount_applied = 1
                    if row.doctype == "Drug Prescription":
                        row.hms_tz_is_discount_percent = discount_percent

            row.amount = item_rate


def show_last_prescribed(doc, method):
    if doc.is_new():
        return

    if method != "before_save":
        return

    msg = None
    valid_days_msg = ""
    dn = DocType("Delivery Note")
    dni = DocType("Delivery Note Item")

    for row in doc.drug_prescription:
        if row.is_cancelled or row.is_not_available_inhouse:
            continue

        item_code = frappe.get_cached_value("Medication", row.drug_code, "item")

        medication_list = (
            frappe.qb.from_(dn)
            .inner_join(dni)
            .on(dni.parent == dn.name)
            .select(
                dn.posting_date,
                dni.item_code,
                dni.stock_qty,
                dni.uom,
            )
            .where((dn.docstatus == 1) & (dn.patient == doc.patient) & (dni.item_code == item_code))
            .orderby(dn.posting_date, order=frappe.qb.desc)
            .limit(1)
        ).run(as_dict=True)

        if len(medication_list) > 0:
            msg = (
                (msg or "")
                + _(
                    "<strong>"
                    + row.drug_code
                    + "</strong>"
                    + " qty: <strong>"
                    + str(medication_list[0].get("stock_qty"))
                    + "</strong>, prescribed lastly on: <strong>"
                    + str(medication_list[0].get("posting_date"))
                )
                + "</strong><br>"
            )

            val_msg = validate_prescribe_days(
                doc,
                "Medication",
                row.drug_code,
                medication_list[0].get("posting_date"),
            )
            if val_msg:
                valid_days_msg += val_msg

            # SHM Rock#: 169
            validate_medication_class(doc.company, doc.name, doc.patient, row.drug_code)

    if valid_days_msg:
        frappe.msgprint(
            _(
                "These Items should not be prescribed, because days are below minimum prescription days:<br>"
                + valid_days_msg
            )
        )
    elif msg:
        frappe.msgprint(_("The below are the last related medication prescriptions:<br><br>" + msg))


def validate_patient_balance_vs_patient_costs(
    patient,
    patient_name,
    appointment,
    inpatient_record,
    company,
    inpatient_cost=0,
    cash_limit=0,
    caller="",
    encounters=[],
    exclude_consumable=None,
):
    def get_encounter_costs(encounters):
        encounter_cost = 0
        child_map = [
            {"child_table": "lab_test_prescription"},
            {"child_table": "radiology_procedure_prescription"},
            {"child_table": "procedure_prescription"},
            {"child_table": "drug_prescription"},
            {"child_table": "therapies"},
        ]
        for enc in encounters:
            encounter_doc = frappe.get_cached_doc("Patient Encounter", enc)

            for row in child_map:
                for child in encounter_doc.get(row.get("child_table")):
                    if (
                        child.prescribe == 0
                        or child.is_not_available_inhouse == 1
                        or child.invoiced == 1
                        or child.is_cancelled == 1
                    ):
                        continue

                    if child.doctype == "Drug Prescription":
                        encounter_cost += (child.quantity - child.quantity_returned) * child.amount
                    else:
                        encounter_cost += child.amount
        return encounter_cost

    def get_inpatient_costs(inpatient_record):
        inpatient_cost = 0
        inpatient_record_doc = frappe.get_cached_doc("Inpatient Record", inpatient_record)
        cash_limit = inpatient_record_doc.cash_limit
        for record in inpatient_record_doc.inpatient_occupancies:
            if not record.is_confirmed:
                continue

            inpatient_cost += record.amount

        for record in inpatient_record_doc.inpatient_consultancy:
            if not record.is_confirmed:
                continue

            inpatient_cost += record.rate

        return inpatient_cost, cash_limit

    def get_consumable_costs(patient, appointment, exclude_consumable=None):
        """Sum total_amount from cash Consumable Records (draft + submitted)."""
        filters = {
            "patient": patient,
            "payment_type": "Cash",
            "docstatus": ["in", [0, 1]],
        }
        if appointment:
            filters["appointment"] = appointment
        if exclude_consumable:
            filters["name"] = ["!=", exclude_consumable]

        consumable_total = frappe.db.get_all(
            "Consumable Record",
            filters=filters,
            fields=["sum(total_amount) as total"],
        )
        return flt(consumable_total[0].total) if consumable_total else 0

    cash_limit_details = frappe.get_cached_value(
        "HMS TZ Setting",
        {"company": company, "hms_tz_has_cash_limit_alert": 1},
        [
            "hms_tz_minimum_cash_limit_percent",
            "hms_tz_limit_exceed_action",
            "hms_tz_limit_under_minimum_percent_action",
        ],
        as_dict=1,
    )
    if not cash_limit_details:
        return

    total_amount_billed = 0
    if not encounters or len(encounters) == 0:
        encounters = get_patient_encounters(patient, appointment, inpatient_record)

    if encounters and len(encounters) > 0:
        total_amount_billed += get_encounter_costs(encounters)

    if inpatient_cost == 0 and cash_limit == 0:
        inpatient_cost, cash_limit = get_inpatient_costs(inpatient_record)

    total_amount_billed += flt(inpatient_cost)

    # Include consumable record costs for cash patients
    total_amount_billed += get_consumable_costs(patient, appointment, exclude_consumable)

    if total_amount_billed <= 0:
        return

    # get balance from payment entry after patient has deposit advances
    deposit_balance = get_balance_on(party_type="Customer", party=patient_name, company=company)

    patient_balance = (-1 * deposit_balance) + flt(cash_limit)
    cost_diff = fmt_money(total_amount_billed - patient_balance)

    if flt(patient_balance) <= 0:
        cash_limit_percent = -100
    else:
        cash_limit_percent = 100 - ((total_amount_billed / patient_balance) * 100)

    return make_cash_limit_alert(
        patient,
        patient_name,
        cash_limit_percent,
        cash_limit_details,
        cost_diff,
        caller,
    )


def make_cash_limit_alert(
    patient,
    patient_name,
    cash_limit_percent,
    cash_limit_details,
    cost_diff,
    caller,
):
    if cash_limit_percent > 0 and cash_limit_percent <= cash_limit_details.get("hms_tz_minimum_cash_limit_percent"):
        msg_per = f"""<div style="border: 1px solid #ccc; background-color: #f9f9f9; padding: 10px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); margin: 10px;">
                <p style="font-weight: normal; font-size: 14px; justify-content: left;">The patient: <span style="font-weight: bold;">{patient}</span> - <span style="font-weight: bold;">{patient_name}</span>\
                    has reached <span style="font-weight: bold;">{100 - flt(cash_limit_percent, 2)}%</span> of his/her cash limit.</p>
                <p style="font-style: italic; font-weight: bold; font-size: 14px; justify-content: left;">please request patient to deposit advances or ask patient to request cash limit adjustment</p>
            </div>"""

        if cash_limit_details.get("hms_tz_limit_under_minimum_percent_action") == "Warn":
            frappe.msgprint(
                title="Cash Limit Exceeded",
                msg=msg_per,
            )

        elif cash_limit_details.get("hms_tz_limit_under_minimum_percent_action") == "Stop":
            if caller == "Inpatient Record":
                frappe.msgprint(
                    title="Cash Limit Exceeded",
                    msg=msg_per,
                )
                return True

            frappe.throw(
                title="Cash Limit Exceeded",
                msg=msg_per,
            )

    elif cash_limit_percent < 0:
        msg = f"""<div style="border: 1px solid #ccc; background-color: #f9f9f9; padding: 10px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); margin: 10px;">
                <p style="font-weight: normal; font-size: 14px; justify-content: left;">The deposit balance of this patient: <span style="font-weight: bold;">{patient}</span> - <span style="font-weight: bold;">{patient_name}</span>\
                    is not enough or Patient has reached the cash limit.</p>
                <p style="font-style: italic; font-weight: bold; font-size: 14px; justify-content: left;">please request patient to deposit advances or ask patient to request cash limit adjustment</p>
            </div>"""

        if cash_limit_details.get("hms_tz_limit_exceed_action") == "Warn":
            frappe.msgprint(
                title=f"Cash Limit Exceeded by: <b>{cost_diff}</b>",
                msg=msg,
            )

        if cash_limit_details.get("hms_tz_limit_exceed_action") == "Stop":
            if caller == "Inpatient Record":
                frappe.msgprint(
                    title=f"Cash Limit Exceeded by: <b>{cost_diff}</b>",
                    msg=msg,
                )
                return True

            frappe.throw(
                title=f"Cash Limit Exceeded by: <b>{cost_diff}</b>",
                msg=msg,
            )


def get_patient_encounters(patient, appointment, inpatient_record):
    patient_encounters = frappe.get_all(
        "Patient Encounter",
        filters={
            "patient": patient,
            "appointment": appointment,
            "inpatient_record": inpatient_record,
        },
        fields=["name"],
        pluck="name",
    )
    return patient_encounters


def show_last_prescribed_for_lrpt(doc, method):
    childs_map = [
        {
            "table": "lab_test_prescription",
            "doctype": "Lab Test Template",
            "item": "lab_test_code",
            "ref_doc": "Lab Test",
            "field_name": "template",
        },
        {
            "table": "radiology_procedure_prescription",
            "doctype": "Radiology Examination Template",
            "item": "radiology_examination_template",
            "ref_doc": "Radiology Examination",
            "field_name": "radiology_examination_template",
        },
        {
            "table": "procedure_prescription",
            "doctype": "Clinical Procedure Template",
            "item": "procedure",
            "ref_doc": "Clinical Procedure",
            "field_name": "procedure_template",
        },
        # {
        # "table": "therapies",
        # "doctype": "Therapy Type",
        # "item": "therapy_type",
        # "ref_doc": "Therapy Plan",
        # "field_name": "therapy_plan_template"
        # }
    ]

    if method != "before_save":
        return

    msg = ""
    valid_days_msg = ""
    for child in childs_map:
        msg_print = ""
        for entry in doc.get(child.get("table")):
            conditions = {
                "patient": doc.patient,
                child.get("field_name"): entry.get(child.get("item")),
            }

            item_doc = frappe.db.get_all(
                child.get("ref_doc"),
                filters=conditions,
                fields=[child.get("field_name"), "creation"],
                order_by="creation DESC",
                limit=1,
            )

            if len(item_doc) > 0:
                date = item_doc[0]["creation"].strftime("%Y-%m-%d")

                msg_print += _(
                    f"{frappe.bold(entry.get(child.get('item')))} prescribed last on: {frappe.bold(date)}" + "<br>"
                )

                val_msg = validate_prescribe_days(
                    doc,
                    child.get("doctype"),
                    entry.get(child.get("item")),
                    date,
                )
                if val_msg:
                    valid_days_msg += val_msg

        msg += msg_print

    tp = DocType("Therapy Plan")
    tpd = DocType("Therapy Plan Detail")
    for plan in doc.therapies:
        items = (
            frappe.qb.from_(tpd)
            .inner_join(tp)
            .on(tpd.parent == tp.name)
            .select(
                tpd.therapy_type,
                Date(tpd.creation).as_("date"),
            )
            .where((tp.patient == doc.patient) & (tpd.therapy_type == plan.therapy_type))
            .orderby(tpd.creation, order=frappe.qb.desc)
            .limit(1)
        ).run(as_dict=True)

        if items:
            msg = _(
                msg
                + f"{frappe.bold(items[0]['therapy_type'])} prescribed last on: {frappe.bold(items[0]['date'])} <br>"
            )
            val_msg = validate_prescribe_days(doc, "Therapy Type", items[0]["therapy_type"], items[0]["date"])
            if val_msg:
                valid_days_msg += val_msg

    if valid_days_msg:
        frappe.throw(
            _(
                "These Items should not be prescribed, since days are below minimum prescription days:<br>"
                + valid_days_msg
            ),
        )
    elif msg:
        frappe.msgprint(_("The below are the last related Item prescribed:<br><br>" + msg))


def validate_prescribe_days(doc, doctype, item_value, date):
    valid_min_presribe_days = None
    if doc.insurance_company:
        valid_min_presribe_days = frappe.get_cached_value(
            doctype,
            {
                "name": item_value,
                "hms_tz_validate_prescription_days_for_insurance": 1,
            },
            "hms_tz_insurance_min_no_of_days_for_prescription",
        )

    elif doc.mode_of_payment:
        valid_min_presribe_days = frappe.get_cached_value(
            doctype,
            {
                "name": item_value,
                "hms_tz_validate_prescription_days_for_cash": 1,
            },
            "hms_tz_cash_min_no_of_days_for_prescription",
        )

    if valid_min_presribe_days and (date_diff(nowdate(), date) < cint(valid_min_presribe_days)):
        item = item_value
        msg = _(
            f"<p style='background-color: #CCFB5D;'><b>{item}</b> was lastly prescribed on: <b>{date}</b> and it should be prescribed again after: <b>{valid_min_presribe_days} days</b></p><br>"
        )

        return msg


@frappe.whitelist()
def convert_opd_encounter_to_ipd_encounter(encounter):
    """Convert an out-patient encounter into list of inpatient encounters.

    This can be used when items for opd encounters needs to be created with inpatient
    functionality of create pending healthcare services while the encounter
    does not have inpatient record

    :param of encounter: name of the encounter to be converted to inpatient encounter
    """

    doc = frappe.get_cached_doc("Patient Encounter", encounter)
    if doc.inpatient_record:
        frappe.msgprint(
            f"<p class='text-center font-weight-bold h6' style='background-color: #DCDCDC; font-size: 12pt;'>\
                This encounter having inpatient record: {doc.inpatient_record} already"
            + "</p>"
        )
        return

    inpatient_record, inpatient_status = frappe.get_cached_value(
        "Patient", doc.patient, ["inpatient_record", "inpatient_status"]
    )
    if not inpatient_record:
        inpatient_details_from_encounters = frappe.get_all(
            "Patient Encounter",
            filters={
                "appointment": doc.appointment,
                "inpatient_record": ["!=", ""],
            },
            fields=["inpatient_record", "inpatient_status"],
            page_length=1,
        )
        if inpatient_details_from_encounters:
            inpatient_record = inpatient_details_from_encounters[0].inpatient_record
            inpatient_status = inpatient_details_from_encounters[0].inpatient_status

        if not inpatient_record:
            frappe.throw(
                f"<p class='text-center font-weight-bold h6' style='background-color: #DCDCDC; font-size: 11pt;'>\
                    Scheduling admission was not done for this patient: {frappe.bold(doc.patient)} of appointment: \
                    {frappe.bold(doc.appointment)}. </p>"
            )

    doc.inpatient_record = inpatient_record
    doc.inpatient_status = inpatient_status
    doc.save(ignore_permissions=True)
    doc.reload()

    if doc.get("inpatient_record"):
        encounter_list = [doc.name]
        create_healthcare_docs(doc.reference_encounter, encounter_list, method="on_submit")

        frappe.msgprint(
            f"<p class='text-center font-weight-bold h6' style='background-color: #DCDCDC; font-size: 11pt;'>\
            This encounter is now having inpatient record: {frappe.bold(doc.get('inpatient_record'))} </p>"
        )
        return True


@frappe.whitelist()
def validate_admission_encounter(encounter):
    """Validate encounter if it has duplicated = 1 and if it has healthcare package order"""

    duplicated_encounter = frappe.get_cached_value("Patient Encounter", {"from_encounter": encounter}, "name")
    if duplicated_encounter:
        url = frappe.utils.get_link_to_form("Patient Encounter", duplicated_encounter)
        frappe.msgprint(
            f"You can't schedule Admission on this encounter: {frappe.bold(encounter)},<br>\
            Please, Click Here: {frappe.bold(url)} to open the right encounter"
        )
        return True


@frappe.whitelist()
def get_previous_diagnosis_and_lrpmt_items_to_reuse(kwargs, caller):
    """Get unique Diagnosis and LRPMT items from previous encounters that can be reused on current encounters"""

    kwargs = frappe.parse_json(kwargs)
    if not kwargs.get("patient"):
        return []

    appointments = frappe.get_all(
        "Patient Appointment",
        filters={
            "patient": kwargs.get("patient"),
            "name": ["!=", kwargs.get("appointment")],
            "status": "Closed",
        },
        fields=["name"],
        limit_page_length=kwargs.get("number_of_visit"),
        order_by="appointment_date desc",
        pluck="name",
    )
    if not appointments:
        return []

    enc_cond = {"appointment": ["in", appointments]}
    if not kwargs.get("include_ipd_encounters"):
        enc_cond["inpatient_record"] = ("=", "")

    encounters = frappe.get_all("Patient Encounter", filters=enc_cond, fields=["name"], pluck="name")
    if not encounters:
        return []

    data = []
    if caller == "Diagnosis":
        diagnosis = frappe.get_all(
            kwargs.doctype,
            fields=kwargs.get("fields"),
            filters={
                "parent": ["in", encounters],
                "parentfield": "patient_encounter_final_diagnosis",
            },
            order_by="creation desc",
        )

        unique_codes = []
        for diag in diagnosis:
            if diag.get("item") in unique_codes:
                continue

            unique_codes.append(diag.get("item"))

            diagnosis_info = frappe.get_cached_value(
                "Code Value", diag.get("item"), ["disabled", "is_non_specific"], as_dict=True
            )
            if diagnosis_info.get("disabled") or diagnosis_info.get("is_non_specific"):
                continue

            data.append(diag)

    else:
        items = frappe.get_all(
            kwargs.doctype,
            fields=kwargs.get("fields"),
            filters={
                "parent": ["in", encounters],
                "is_cancelled": 0,
                "is_not_available_inhouse": 0,
            },
            order_by="creation desc",
        )
        unique_items = []
        for item in items:
            if item.item not in unique_items:
                unique_items.append(item.item)
                data.append(item)

    return data


@frappe.whitelist()
def get_encounter_cost_estimate(encounter_doc):
    """Get encounter cost estimate"""
    if not encounter_doc:
        return

    childs_map = [
        {
            "table": "lab_test_prescription",
            "lable": "Lab Test",
            "item": "lab_test_code",
        },
        {
            "table": "radiology_procedure_prescription",
            "lable": "Radiology Examination",
            "item": "radiology_examination_template",
        },
        {
            "table": "procedure_prescription",
            "lable": "Clinical Procedure",
            "item": "procedure",
        },
        {
            "table": "drug_prescription",
            "lable": "Medication",
            "item": "drug_code",
        },
        {
            "table": "therapies",
            "lable": "Therapy Type",
            "item": "therapy_type",
        },
    ]

    encounter_doc = frappe.get_doc(json.loads(encounter_doc))
    # set encounter amounts
    set_amounts(encounter_doc)
    # get encounter cost estimate details
    cost_dict = {}
    for child_table_dict in childs_map:
        child_table = child_table_dict.get("table")
        if not encounter_doc.get(child_table):
            continue
        cost_dict.setdefault(child_table_dict["lable"], [])

        for row in encounter_doc.get(child_table):
            cost_row = {}
            quantity = 1
            if hasattr(row, "quantity"):
                quantity = row.quantity

            cost_row["item"] = row.get(child_table_dict.get("item"))
            cost_row["amount"] = row.amount * quantity

            cost_dict[child_table_dict["lable"]].append(cost_row)

    total_cost = 0
    # calculate total cost
    for key, value in cost_dict.items():
        for row in value:
            total_cost += row.get("amount") or 0

    return {"total_cost": total_cost, "details": cost_dict}


@frappe.whitelist()
def validate_medication_class(company, encounter, patient, drug_item, caller="Backend"):
    """Validate medication class based on company settings

    Args:
        company (str): company name
        encounter (str): patient encounter id
        patient (str): patient id
        drug_item (str): drug item name
        caller (str, optional): excute location. Defaults to "Backend".
    """

    validate_medication_class = frappe.get_cached_value("HMS TZ Setting", company, "validate_medication_class")
    if int(validate_medication_class) == 0:
        return

    medication_class = frappe.get_cached_value("Medication", drug_item, "medication_class")
    if not medication_class:
        return

    medication_class_list = frappe.db.sql(
        f"""
        SELECT dp.drug_code, pe.name, pe.encounter_date, mc.prescribed_after as valid_days
        FROM `tabDrug Prescription` dp
        INNER JOIN `tabMedication` m ON m.name = dp.drug_code
        INNER JOIN `tabMedication Class` mc ON mc.name = m.medication_class
        INNER JOIN `tabPatient Encounter` pe ON pe.name = dp.parent
        WHERE dp.is_cancelled = 0
            AND dp.is_not_available_inhouse = 0
            AND dp.dn_detail != ""
            AND dp.parent != {frappe.db.escape(encounter)}
            AND mc.name = {frappe.db.escape(medication_class)}
            AND pe.docstatus = 1
            AND pe.patient = {frappe.db.escape(patient)}
        order by pe.encounter_date Desc
    """,
        as_dict=1,
    )

    if len(medication_class_list) == 0:
        return

    prescribed_date = medication_class_list[0].encounter_date
    drug_code = medication_class_list[0].drug_code
    valid_days = medication_class_list[0].valid_days
    if not int(valid_days):
        return

    if int(date_diff(nowdate(), prescribed_date)) < int(valid_days):
        if caller == "Front End":
            return {
                "prescribed_date": prescribed_date,
                "drug_item": drug_code,
                "valid_days": valid_days,
                "medication_class": medication_class,
            }

        frappe.msgprint(_(
            f"Item: <strong>{drug_code}</strong> with same Medication Class: <strong>{medication_class}</strong> was lastly prescribed on: <strong>{prescribed_date}</strong><br>\
            Therefore item with same <b>medication class</b> were supposed to be prescribed after: <strong>{valid_days}</strong> days"))


def set_practitioner_name(doc, method):
    practitioner_info = frappe.get_cached_value(
        "Healthcare Practitioner",
        {"user_id": frappe.session.user, "hms_tz_company": doc.company},
        ["name", "practitioner_name", "date_loggedin_to_nhif"],
        as_dict=1,
    )

    if practitioner_info:
        doc.practitioner = practitioner_info.name
        doc.practitioner_name = practitioner_info.practitioner_name

        if doc.insurance_company and "NHIF" in doc.insurance_company and (
            not practitioner_info.date_loggedin_to_nhif
            or getdate(practitioner_info.date_loggedin_to_nhif) != getdate(nowdate())
        ):
            validate_nhif_attendance = frappe.get_cached_value(
                "HMS TZ Setting",
                doc.company,
                "validate_nhif_practitioner_attendance",
            )
            if (
                validate_nhif_attendance == 1 and
                method not in ("before_insert", "validate", "before_save")
            ):
                frappe.throw("Please Login to NHIF, to proceed attending NHIF Patients..")

    elif (
        doc.encounter_category == "Appointment"
        and not doc.healthcare_package_order
        and doc.practitioner not in ["Direct Cash", "Direct Insurance"]
    ):
        if method not in ("before_insert", "validate", "before_save"):
            frappe.throw(
                _(
                    f"Please set user id: <b>{frappe.session.user}</b>\
                in Healthcare Practitioner<br>\
                so as to set the correct practitioner, who submitting this encounter"
                )
            )


def validate_medical_code(doc, method):
    """
    Validate medical code on patient encounter based on the configuration

    for cash patients its configuration is on Healthcare Settings
    for insurance patients its configuration is on Healthcare Insurance Company
    """

    # Run on_submit
    mtuha_missing = ""
    for final_diagnosis in doc.patient_encounter_final_diagnosis:
        if not final_diagnosis.mtuha:
            mtuha_missing += "-  <b>" + final_diagnosis.code_value + "</b><br>"

    if mtuha_missing:
        msgThrow(
            _(f"{mtuha_missing}<br>MTUHA Code not defined for the above diagnosis"),
            method,
        )

    validation_for_medical_code = None
    if doc.insurance_subscription:
        validation_for_medical_code = frappe.get_cached_value(
            "Healthcare Insurance Company",
            doc.insurance_company,
            "validate_medical_code_for_insurance_patients",
        )
    else:
        validation_for_medical_code = frappe.db.get_single_value(
            "Healthcare Settings", "validate_medical_code_for_cash_patients"
        )

    if validation_for_medical_code == 0:
        return

    def medical_code_mapping():
        return {
            "patient_encounter_preliminary_diagnosis": [
                "lab_test_prescription",
                "radiology_procedure_prescription",
            ],
            "patient_encounter_final_diagnosis": [
                "procedure_prescription",
                "drug_prescription",
                "therapies",
            ],
        }

    def get_diagnosis_list(doc, diagnosis_table):
        diagnosis_list = []
        if doc.get(diagnosis_table):
            for row in doc.get(diagnosis_table):
                if not row.code_value:
                    continue

                d = str(row.code_value) + "\n " + str(row.definition)
                diagnosis_list.append(d)

        return diagnosis_list

    has_disease_code = False
    for from_table, fields in medical_code_mapping().items():
        diagnosis_list = get_diagnosis_list(doc, from_table)

        from_table_label = frappe.get_meta(doc.doctype).get_label(from_table)
        for fieldname in fields:
            if not doc.get(fieldname):
                continue

            fieldname_label = frappe.get_meta(doc.doctype).get_label(fieldname)
            for row in doc.get(fieldname):
                if row.medical_code not in diagnosis_list:
                    msgThrow(
                        _(
                            f"The Medical Code in the <strong>{fieldname_label}</strong> table at line <strong>{row.idx}</strong> is empty\
                            or does not exist in the <strong>{from_table_label}</strong> table."
                        ),
                            method,
                        )

        if (
            not has_disease_code and
            len(doc.get(from_table)) > 0
        ):
            has_disease_code = True

    if not has_disease_code:
        msgThrow(
            _(
                "No Preliminary or Final diagnosis found on this encounter, Please set at least one disease code"
            ),
            method
        )

@frappe.whitelist()
def get_filterd_drug(doctype, txt, searchfield, start, page_len, filters):
    """
    Get filtered drug based on the search criteria
    and retrun Mediction if it is not disabled and allowed price list is set
    """
    conditions = "MD.disabled = 0"
    if txt:
        conditions += f" AND MD.name LIKE '%{txt}%'"
    if filters.get("price_list"):
        conditions += f" AND APL.price_list = '{filters.get('price_list')}'"

    data = frappe.db.sql(
        f"""
        SELECT
            MD.name, MD.national_drug_code, MD.generic_name, MD.strength_text
        FROM
            `tabMedication` MD
        inner join
            `tabAllowed Price List` APL
        on
            MD.name = APL.parent
        WHERE
              {conditions}
        ORDER BY
            name ASC
        LIMIT
            {start}, {page_len}
    """
    )

    return data


@frappe.whitelist()
def get_filtered_dosage(doctype, txt, searchfield, start, page_len, filters):
    doctype = "Prescription Dosage"
    if filters.get("dosage_form"):
        if frappe.get_cached_value("Dosage Form", filters.get("dosage_form"), "has_restricted_qty") == 1:
            return frappe.get_all(
                doctype,
                filters={"has_restricted_qty": 1},
                fields=[searchfield],
                as_list=1,
            )
        else:
            return frappe.get_all(
                "Prescription Dosage",
                fields=[searchfield],
                as_list=1,
            )
    else:
        return frappe.get_all(
            "Prescription Dosage",
            fields=[searchfield],
            as_list=1,
        )


def set_admission_service_type(doc):
    """Set admission service type based on service unit type of inpatient record"""

    if doc.inpatient_record:
        admission_service_unit_type = frappe.get_cached_value(
            "Inpatient Record",
            doc.inpatient_record,
            "admission_service_unit_type",
        )
        if admission_service_unit_type and doc.admission_service_unit_type != admission_service_unit_type:
            doc.admission_service_unit_type = admission_service_unit_type


def validate_preapproval_services(doc):
    if doc.insurance_company and "NHIF" in doc.insurance_company:
        validate_nhif_pre_approval(doc)

    if doc.insurance_company and "Jubilee" in doc.insurance_company:
        validate_jubilee_pre_approval(doc)


def validate_nhif_pre_approval(doc):
    if not frappe.get_cached_value(
        "HMS TZ Setting",
        doc.company,
        "enable_nhif_api"
    ):
        return

    eligible_pre_approval_services = []
    for child in get_childs_map():
        for row in doc.get(child.get("table")):
            if (
                row.get("prescribe")
                or row.get("is_not_available_inhouse")
                or row.get("is_cancelled")
                # or row.get("is_restricted")
                or row.get("preapproval_status") in ["Accepted", "REJECTED"]
                or row.get("preapproval_no")
            ):
                continue

            eligible_pre_approval_services.append(row.get(child.get("item")))

    if len(eligible_pre_approval_services) > 0:
        frappe.throw(
            f"Pre-Approval is required for the <b>{len(eligible_pre_approval_services)}</b> service(s)\
              before submitting this encounter <br>Please request pre-approval"
        )


def validate_jubilee_pre_approval(doc):
    # Jubilee API is only for OPD
    if doc.inpatient_record:
        return

    if not frappe.get_cached_value(
        "HMS TZ Setting",
        doc.company,
        "enable_jubilee_api"
    ):
        return

    if frappe.flags.hsr_requires_approval:
        return

    eligible_pre_approval_services = []
    for child in get_childs_map():
        for row in doc.get(child.get("table")):
            if (
                row.get("prescribe")
                or row.get("is_not_available_inhouse")
                or row.get("is_cancelled")
                # or row.get("is_restricted")
                or row.get("preapproval_status") in ["Accepted", "REJECTED", "OK"]
                or row.get("preapproval_no")
            ):
                continue

            eligible_pre_approval_services.append(row.get(child.get("item")))

    if len(eligible_pre_approval_services) > 0:
        frappe.throw(
            f"Pre-Approval is required for the <b>{len(eligible_pre_approval_services)}</b> service(s)\
              before submitting this encounter <br>Please request pre-approval"
        )