# -*- coding: utf-8 -*-
# Copyright (c) 2018, earthians and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import base64
import json
import re
from datetime import timedelta

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.utils import add_days, add_to_date, create_batch, get_url_to_form, now_datetime, nowdate, nowtime


def get_childs_map():
    childs_map = {
        "Lab Prescription": {
            "table": "lab_test_prescription",
            "doctype": "Lab Prescription",
            "template": "Lab Test Template",
            "item": "lab_test_code",
        },
        "Radiology Procedure Prescription": {
            "table": "radiology_procedure_prescription",
            "doctype": "Radiology Procedure Prescription",
            "template": "Radiology Examination Template",
            "item": "radiology_examination_template",
        },
        "Procedure Prescription": {
            "table": "procedure_prescription",
            "doctype": "Procedure Prescription",
            "template": "Clinical Procedure Template",
            "item": "procedure",
        },
        "Drug Prescription": {
            "table": "drug_prescription",
            "doctype": "Drug Prescription",
            "template": "Medication",
            "item": "drug_code",
        },
        "Therapy Plan Detail": {
            "table": "therapies",
            "doctype": "Therapy Plan Detail",
            "template": "Therapy Type",
            "item": "therapy_type",
        },
    }
    return childs_map


@frappe.whitelist()
def get_healthcare_services_to_invoice(
    encounter=None,
    patient_encounter_list=None,
):
    services_to_invoice = []

    encounter_dict = None
    if patient_encounter_list and len(patient_encounter_list) > 0:
        encounter_dict = patient_encounter_list
    else:
        if not encounter:
            return services_to_invoice

        reference_encounter = frappe.get_cached_value("Patient Encounter", encounter, "reference_encounter")

        encounter_dict = frappe.db.get_all(
            "Patient Encounter",
            filters={
                "reference_encounter": reference_encounter,
                "docstatus": 1,
            },
            fields=["name", "inpatient_record", "appointment"],
        )

    inpatient_record = None
    childs_map = get_childs_map()

    # Get services from Patient Encounter
    for i in encounter_dict:
        if not inpatient_record and i.inpatient_record:
            inpatient_record = i.inpatient_record

        encounter_doc = frappe.get_cached_doc("Patient Encounter", i.name)

        for key, value in childs_map.items():
            table = encounter_doc.get(value.get("table"))
            if not table:
                continue

            for row in table:
                if (
                    row.get("invoiced")
                    or row.get("is_cancelled")
                    or not row.get("prescribe")
                    or row.get("is_not_available_inhouse")
                ):
                    continue

                item_code = frappe.get_cached_value(
                    value.get("template"),
                    row.get(value.get("item")),
                    "item",
                )

                qty = 1
                if value.get("doctype") == "Therapy Plan Detail":
                    qty = (row.get("no_of_sessions") or 0) - (row.get("sessions_cancelled") or 0)

                if value.get("doctype") == "Drug Prescription":
                    qty = (row.get("quantity") or 0) - (row.get("quantity_returned") or 0)

                new_row = {}
                new_row["reference_type"] = row.doctype
                new_row["reference_name"] = row.name
                new_row["service"] = item_code
                new_row["rate"] = row.get("amount")
                new_row["qty"] = qty
                new_row["service_request"] = ""

                services_to_invoice.append(new_row)

    # Get services from Healthcare Service Request using Appointment No
    appointment = encounter_dict[0].appointment
    hsr = DocType("Healthcare Service Request")
    hsrp = DocType("Healthcare Service Request Payment")
    hsr_services = (
        frappe.qb.from_(hsr)
        .inner_join(hsrp)
        .on(hsr.name == hsrp.parent)
        .select(
            hsrp.service_name,
            hsrp.service_type,
            hsrp.ref_docname,
            hsrp.ref_doctype,
            hsrp.qty,
            hsrp.amount,
            hsrp.name.as_("service_request"),
        )
        .where(
            (hsr.docstatus == 1)
            & (hsrp.invoiced == 0)
            & (hsrp.is_cancelled == 0)
            & (hsrp.payment_type == "Cash")
            & (hsr.appointment == appointment)
        )
    ).run(as_dict=True)

    if len(hsr_services) > 0:
        for row in hsr_services:
            item = frappe.get_cached_value(row.service_type, row.service_name, "item")

            rate = row.amount / row.qty

            new_row = {}
            new_row["reference_type"] = row.ref_doctype
            new_row["reference_name"] = row.ref_docname
            new_row["service"] = item
            new_row["rate"] = rate
            new_row["qty"] = row.qty
            new_row["service_request"] = row.service_request

            services_to_invoice.append(new_row)

    # Get services from Inpatient Record
    if inpatient_record:
        inpatient_doc = frappe.get_cached_doc("Inpatient Record", inpatient_record)
        for row in inpatient_doc.inpatient_occupancies:
            if row.is_confirmed == 0 or row.invoiced == 1:
                continue

            service_unit_type = frappe.get_cached_value(
                "Healthcare Service Unit",
                row.service_unit,
                "service_unit_type",
            )
            item_code = frappe.get_cached_value("Healthcare Service Unit Type", service_unit_type, "item_code")

            new_row = {}
            new_row["reference_type"] = row.doctype
            new_row["reference_name"] = row.name
            new_row["service"] = item_code
            new_row["rate"] = row.amount
            new_row["qty"] = 1
            new_row["service_request"] = ""

            services_to_invoice.append(new_row)

        for row in inpatient_doc.inpatient_consultancy:
            if row.is_confirmed == 0 or row.hms_tz_invoiced == 1:
                continue

            new_row = {}
            new_row["reference_type"] = row.doctype
            new_row["reference_name"] = row.name
            new_row["service"] = row.consultation_item
            new_row["rate"] = row.rate
            new_row["qty"] = 1
            new_row["service_request"] = ""

            services_to_invoice.append(new_row)

    return services_to_invoice


def get_item_price(item_code, price_list, company):
    price = 0
    company_currency = frappe.get_cached_value("Company", company, "default_currency")
    item_prices_data = frappe.get_all(
        "Item Price",
        fields=["item_code", "price_list_rate", "currency"],
        filters={
            "price_list": price_list,
            "item_code": item_code,
            "currency": company_currency,
        },
        order_by="valid_from desc",
    )
    if len(item_prices_data):
        price = item_prices_data[0].price_list_rate
    return price


@frappe.whitelist()
def get_item_rate(
    item_code,
    company,
    insurance_subscription,
    insurance_company=None,
    for_service_request=False,
):
    price_list = None
    price_list_rate = None
    hic_plan = None
    if insurance_subscription:
        hic_plan = frappe.get_cached_value(
            "Healthcare Insurance Subscription",
            insurance_subscription,
            "healthcare_insurance_coverage_plan",
        )
        price_list, secondary_price_list, insurance_company = frappe.get_cached_value(
            "Healthcare Insurance Coverage Plan",
            hic_plan,
            ["price_list", "secondary_price_list", "insurance_company"],
        )
        if price_list:
            price_list_rate = get_item_price(item_code, price_list, company)
            if price_list_rate and price_list_rate != 0:
                if for_service_request:
                    return price_list_rate, price_list
                else:
                    return price_list_rate
            else:
                price_list_rate = None
        elif not price_list:
            frappe.throw(_(f"Default price list for {hic_plan} NOT FOUND!<br>Please set Price List in {hic_plan} plan"))
        if not price_list_rate:
            if price_list and not secondary_price_list:
                frappe.throw(
                    _(f"Item Price for {item_code} not found in Default Price List and Secondary price list for {hic_plan} not set!<br>Please set Item rate in {price_list} or set a Secondary Price List in {hic_plan} plan"))
            price_list_rate = get_item_price(item_code, secondary_price_list, company)
            if price_list_rate and price_list_rate != 0:
                if for_service_request:
                    return price_list_rate, price_list
                else:
                    return price_list_rate
            else:
                price_list_rate = None

    if not price_list_rate and insurance_company:
        price_list = frappe.get_cached_value(
            "Healthcare Insurance Company",
            insurance_company,
            "default_price_list",
        )
    if not price_list:
        frappe.throw(
            _(f"Default price list for {hic_plan} NOT FOUND!<br>Please set Price List in {insurance_company} insurance company"))
    else:
        price_list_rate = get_item_price(item_code, price_list, company)
    if price_list_rate and price_list_rate != 0:
        if for_service_request:
            return price_list_rate, price_list
        else:
            return price_list_rate
    else:
        frappe.throw(_(f"Please set Price List for item: {item_code} in price list {price_list}"))


@frappe.whitelist()
def get_mop_amount(
    billing_item,
    mop=None,
    company=None,
    patient=None,
):
    price_list = None
    if mop:
        price_list = frappe.get_cached_value("Mode of Payment", mop, "price_list")
    if not price_list and patient:
        price_list = get_default_price_list(patient)
    if not price_list:
        frappe.throw(_("Please set Price List in Mode of Payment"))
    return get_item_price(billing_item, price_list, company)


def get_default_price_list(patient):
    price_list = None
    price_list = frappe.get_cached_value("Patient", patient, "default_price_list")
    if not price_list:
        customer = frappe.get_cached_value("Patient", patient, "customer")
        if customer:
            price_list = frappe.get_cached_value("Customer", customer, "default_price_list")
    if not price_list:
        customer_group = frappe.get_cached_value("Customer", customer, "customer_group")
        frappe.get_cached_value("Customer Group", customer_group, "default_price_list")
    if not price_list:
        if frappe.db.exists("Price List", "Standard Selling"):
            price_list = "Standard Selling"
    return price_list


@frappe.whitelist()
def get_discount_percent(insurance_company):
    """Get discount percent (%) from Non NHIF Insurance Company"""

    discount_percent = 0
    has_price_discount, discount = frappe.get_cached_value(
        "Healthcare Insurance Company",
        insurance_company,
        ["hms_tz_has_price_discount", "hms_tz_price_discount"],
    )
    if has_price_discount and discount == 0:
        frappe.throw(_(f"Please set discount(%) for this insurance company: {frappe.bold(insurance_company)}"))

    if has_price_discount and discount > 0:
        discount_percent = discount

    return discount_percent


@frappe.whitelist()
def get_drug_quantity(drug_item):
    """Get drug quantity based on dosage, period, interval and interval uom

    :param drug_item: object or json string of drug item
    """
    if not frappe.db.get_single_value("Healthcare Settings", "enable_auto_quantity_calculation"):
        return 0

    quantity = 0
    strength_count = 0

    drug_row = frappe.parse_json(drug_item)

    if drug_row.dosage and drug_row.period:
        dosage = frappe.get_cached_doc("Prescription Dosage", drug_row.dosage)
        period = frappe.get_cached_doc("Prescription Duration", drug_row.period)
        for item in dosage.dosage_strength:
            strength_count += item.strength
        if strength_count == 0:
            strength_count = dosage.default_strength
        if strength_count > 0:
            if drug_row.interval and drug_row.interval_uom:
                if drug_row.interval_uom == "Day" and drug_row.interval:
                    quantity = strength_count * (period.get_days() / drug_row.interval)
                elif drug_row.interval_uom == "Hour" and drug_row.interval:
                    quantity = strength_count * (period.get_hours() / drug_row.interval)
            else:
                quantity = strength_count * period.get_days()

        # elif drug_row.interval and drug_row.interval_uom:
        #     if drug_row.interval_uom == "Day" and drug_row.interval:
        #         quantity = period.get_days() / drug_row.interval
        #     elif drug_row.interval_uom == "Hour" and drug_row.interval:
        #         quantity = period.get_hours() / drug_row.interval

    if quantity > 0:
        return quantity
    else:
        return 1


@frappe.whitelist()
def validate_stock_item(
    healthcare_service,
    qty,
    company,
    prescribe,
    warehouse=None,
    healthcare_service_unit=None,
    caller="Unknown",
    method=None,
):
    setting_doc = frappe.get_cached_doc("Healthcare Settings")

    if prescribe == 0:
        if setting_doc.only_alert_if_less_stock_of_drug_item_for_insurance_in_pe == 1:
            method = "validate"
        elif setting_doc.stop_encounter_if_less_stock_of_drug_item_for_insurance_in_pe == 1:
            method = method
        else:
            frappe.throw(
                "<b>Please set the stock validation method (either only alert or stop when less stock) in Healthcare Settings for Insurance Patients</b>"
            )

    elif prescribe == 1:
        if setting_doc.only_alert_if_less_stock_of_drug_item_for_cash_in_pe == 1:
            method = "validate"
        elif setting_doc.stop_encounter_if_less_stock_of_drug_item_for_cash_in_pe == 1:
            method = method
        else:
            frappe.throw(
                "<b>Please set the stock validation method (either only alert or stop when less stock) in Healthcare Settings for Cash Patients</b>"
            )

    if caller != "Drug Prescription" and not healthcare_service_unit:
        return

    qty = float(qty or 0)
    if qty == 0:
        qty = 1

    item_info = get_item_info(medication_name=healthcare_service)
    stock_qty = 0
    if healthcare_service_unit:
        warehouse = get_warehouse_from_service_unit(healthcare_service_unit)
    if not warehouse:
        msgThrow(
            _(f"Warehouse is missing in healthcare service unit {healthcare_service_unit} when checking for {item_info.get('item_code')}"),
            method,
        )
    if item_info.get("is_stock") and item_info.get("item_code"):
        stock_qty = get_stock_availability(item_info.get("item_code"), warehouse) or 0
        if float(qty) > float(stock_qty):
            # To be removed after few months of stability. 2021-03-18 17:01:46
            # This is to avoid socketio diconnection when bench is restarted
            # but user session is on.
            msgThrow(
                _(
                    f"Available quantity for item: <h4 style='background-color:\
                    LightCoral'>{item_info.get('item_code')} is {stock_qty}</h4>In {warehouse}/{healthcare_service_unit}."
                ),
                method,
            )
            return False
    return True


def get_item_info(item_code=None, medication_name=None):
    data = {}
    if not item_code and medication_name:
        item_code = frappe.get_cached_value("Medication", medication_name, "item")
    if item_code:
        is_stock, disabled = frappe.get_cached_value("Item", item_code, ["is_stock_item", "disabled"])
        data = {
            "item_code": item_code,
            "is_stock": is_stock,
            "disabled": disabled,
        }
    return data


def get_stock_availability(item_code, warehouse):
    latest_sle = frappe.db.sql(
        """SELECT qty_after_transaction AS actual_qty
        FROM `tabStock Ledger Entry`
        WHERE item_code = %s AND warehouse = %s
          AND is_cancelled = 0
        ORDER BY creation DESC
        LIMIT 1""",
        (item_code, warehouse),
        as_dict=1,
    )

    sle_qty = latest_sle[0].actual_qty or 0 if latest_sle else 0
    return sle_qty


def to_base64(value):
    data = base64.b64encode(value)
    return str(data)[2:-1]


def remove_special_characters(text):
    return re.sub("[^A-Za-z0-9]+", "", text)


def get_app_branch(app):
    """Returns branch of an app"""
    import subprocess

    try:
        branch = subprocess.check_output(f"cd ../apps/{app} && git rev-parse --abbrev-ref HEAD", shell=True)
        branch = branch.decode("utf-8")
        branch = branch.strip()
        return branch
    except Exception:
        return ""


def create_delivery_note_from_LRPT(LRPT_doc, patient_encounter_doc):
    if not patient_encounter_doc.appointment:
        return
    # purposely put this below to skip the delivery note process 2021-04-07
    # 14:36:07
    if patient_encounter_doc.appointment:
        return
    # purposely put this above to skip the delivery note process 2021-04-07
    # 14:36:04
    insurance_subscription, insurance_company = frappe.get_cached_value(
        "Patient Appointment",
        patient_encounter_doc.appointment,
        ["insurance_subscription", "insurance_company"],
    )
    if not insurance_subscription:
        return
    warehouse = get_warehouse_from_service_unit(patient_encounter_doc.healthcare_service_unit)
    items = []
    item = get_item_form_LRPT(LRPT_doc)
    item_code = item.get("item_code")
    if not item_code:
        return
    is_stock, item_name = frappe.get_cached_value("Item", item_code, ["is_stock_item", "item_name"])
    if is_stock:
        return
    item_row = frappe.new_doc("Delivery Note Item")
    item_row.item_code = item_code
    item_row.item_name = item_name
    item_row.warehouse = warehouse
    item_row.healthcare_service_unit = item.healthcare_service_unit
    item_row.practitioner = patient_encounter_doc.practitioner
    item_row.qty = item.qty
    item_row.rate = get_item_rate(
        item_code,
        patient_encounter_doc.company,
        insurance_subscription,
        insurance_company,
    )
    item_row.reference_doctype = LRPT_doc.doctype
    item_row.reference_name = LRPT_doc.name
    item_row.description = frappe.get_cached_value("Item", item_code, "description")
    items.append(item_row)

    if len(items) == 0:
        return
    doc = frappe.get_doc(
        dict(
            doctype="Delivery Note",
            posting_date=nowdate(),
            posting_time=nowtime(),
            set_warehouse=warehouse,
            company=patient_encounter_doc.company,
            customer=frappe.get_cached_value("Healthcare Insurance Company", insurance_company, "customer"),
            currency=frappe.get_cached_value("Company", patient_encounter_doc.company, "default_currency"),
            items=items,
            reference_doctype=LRPT_doc.doctype,
            reference_name=LRPT_doc.name,
            patient=patient_encounter_doc.patient,
            patient_name=patient_encounter_doc.patient_name,
        )
    )
    doc.flags.ignore_permissions = True
    # doc.set_missing_values()
    doc.insert(ignore_permissions=True)
    doc.submit()
    if doc.get("name"):
        frappe.msgprint(
            _(f"Delivery Note {frappe.bold(doc.name)} created successfully."),
            alert=True,
        )


def get_warehouse_from_service_unit(healthcare_service_unit):
    warehouse = frappe.get_cached_value("Healthcare Service Unit", healthcare_service_unit, "warehouse")
    if not warehouse:
        frappe.throw(_(f"Warehouse is missing in Healthcare Service Unit {healthcare_service_unit}"))
    return warehouse


def get_item_form_LRPT(LRPT_doc):
    item = frappe._dict()
    comapny_option = get_template_company_option(LRPT_doc.template, LRPT_doc.company)
    item.healthcare_service_unit = comapny_option.service_unit
    if LRPT_doc.doctype == "Lab Test":
        item.item_code = frappe.get_cached_value("Lab Test Template", LRPT_doc.template, "item")
        item.qty = 1
    elif LRPT_doc.doctype == "Radiology Examination":
        item.item_code = frappe.get_cached_value(
            "Radiology Examination Template",
            LRPT_doc.radiology_examination_template,
            "item",
        )
        item.qty = 1
    elif LRPT_doc.doctype == "Clinical Procedure":
        item.item_code = frappe.get_cached_value(
            "Clinical Procedure Template",
            LRPT_doc.procedure_template,
            "item",
        )
        item.qty = 1
    elif LRPT_doc.doctype == "Therapy Plan":
        item.item_code = None
        item.qty = 0
    return item


def update_dimensions(doc):
    for item in doc.items:
        refd, refn = get_references(item)
        if doc.healthcare_practitioner:
            item.healthcare_practitioner = doc.healthcare_practitioner
        elif refd and refn:
            item.healthcare_practitioner = get_healthcare_practitioner(item)

        if doc.healthcare_service_unit and not item.healthcare_service_unit and not refn:
            item.healthcare_service_unit = doc.healthcare_service_unit

        if refd and refn:
            item.healthcare_service_unit = get_healthcare_service_unit(item)


def get_references(item):
    refd = ""
    refn = ""
    if item.get("reference_doctype"):
        refd = item.get("reference_doctype")
        refn = item.get("reference_name")
    elif item.get("reference_dt"):
        refd = item.get("reference_dt")
        refn = item.get("reference_dn")
    return refd, refn


def get_healthcare_practitioner(item):
    refd, refn = get_references(item)
    if not refd or not refn:
        return

    ref_docs = [
        {"reference_doc": "Lab Prescription"},
        {"reference_doc": "Radiology Procedure Prescription"},
        {"reference_doc": "Procedure Prescription"},
        {"reference_doc": "Drug Prescription"},
        {"reference_doc": "Therapy Plan Detail"},
    ]

    for ref_doc in ref_docs:
        if refd == ref_doc.get("reference_doc"):
            parent, parenttype = frappe.get_cached_value(ref_doc.get("reference_doc"), refn, ["parent", "parenttype"])
            if parent and parenttype == "Patient Encounter":
                return frappe.get_cached_value("Patient Encounter", parent, "practitioner")

    if refd == "Patient Encounter":
        return frappe.get_cached_value("Patient Encounter", refn, "practitioner")
    elif refd == "Patient Appointment":
        return frappe.get_cached_value("Patient Appointment", refn, "practitioner")
    elif refd == "Inpatient Consultancy":
        return frappe.get_cached_value("Inpatient Consultancy", refn, "healthcare_practitioner")
    elif refd == "Healthcare Service Order":
        encounter = frappe.get_cached_value("Healthcare Service Order", refn, "order_group")
        if encounter:
            return frappe.get_cached_value("Patient Encounter", encounter, "practitioner")


def get_healthcare_service_unit(item):
    refd, refn = get_references(item)
    if not refd or not refn:
        return

    ref_docs = [
        {"reference_doc": "Lab Prescription"},
        {"reference_doc": "Radiology Procedure Prescription"},
        {"reference_doc": "Procedure Prescription"},
        {"reference_doc": "Therapy Plan Detail"},
    ]

    for ref_doc in ref_docs:
        if refd == ref_doc.get("reference_doc"):
            return frappe.get_cached_value(ref_doc.get("reference_doc"), refn, "department_hsu")

    if refd == "Patient Encounter":
        return frappe.get_cached_value("Patient Encounter", refn, "healthcare_service_unit")
    elif refd == "Patient Appointment":
        return frappe.get_cached_value("Patient Appointment", refn, "service_unit")
    elif refd == "Drug Prescription":
        return frappe.get_cached_value("Drug Prescription", refn, "healthcare_service_unit")
    elif refd == "Inpatient Consultancy":
        healthcare_service_unit = frappe.get_cached_value(
            "Practitioner Service Unit Schedule",
            {"parent": item.get("healthcare_practitioner")},
            "service_unit",
        )
        if not healthcare_service_unit:
            service_unit_details = frappe.get_all(
                "Practitioner Availability",
                filters={"practitioner": item.get("healthcare_practitioner")},
                fields=["service_unit"],
                order_by="from_date desc",
            )
            if len(service_unit_details) > 0:
                healthcare_service_unit = service_unit_details[0].service_unit
        return healthcare_service_unit
    elif refd == "Inpatient Occupancy":
        return frappe.get_cached_value("Inpatient Occupancy", refn, "service_unit")
    elif refd == "Healthcare Service Order":
        order_doctype, order, order_group, billing_item, company = frappe.get_cached_value(
            refd,
            refn,
            [
                "order_doctype",
                "order",
                "order_group",
                "billing_item",
                "company",
            ],
        )
        if order_doctype in [
            "Lab Test Template",
            "Radiology Examination Template",
            "Clinical Procedure Template",
            "Therapy Plan Template",
        ]:
            comapny_option = get_template_company_option(order, company)
            return comapny_option.service_unit

        elif order_doctype == "Medication":
            if not order_group:
                return
            prescriptions = frappe.get_all(
                "Drug Prescription",
                filters={
                    "parent": order_group,
                    "parentfield": "drug_prescription",
                    "drug_code": billing_item,
                },
                fields=["name", "healthcare_service_unit"],
            )
            if len(prescriptions) > 0:
                return prescriptions[0].healthcare_service_unit


def get_restricted_LRPT(doc):
    if doc.doctype == "Lab Test":
        template = doc.template
    elif doc.doctype == "Radiology Examination":
        template = doc.radiology_examination_template
    elif doc.doctype == "Clinical Procedure":
        template = doc.procedure_template
    elif doc.doctype == "Therapy Plan":
        template = doc.therapy_plan_template
    else:
        frappe.msgprint(_("Unknown Doctype " + doc.doctype + " found in get_restricted_LRPT. Setup may be missing."))
    is_restricted = 0
    if not template:
        return is_restricted
    if doc.ref_doctype and doc.ref_docname and doc.ref_doctype == "Patient Encounter":
        insurance_subscription = frappe.get_cached_value("Patient Encounter", doc.ref_docname, "insurance_subscription")
        if insurance_subscription:
            healthcare_insurance_coverage_plan = frappe.get_cached_value(
                "Healthcare Insurance Subscription",
                insurance_subscription,
                "healthcare_insurance_coverage_plan",
            )
            if healthcare_insurance_coverage_plan:
                insurance_coverages = frappe.get_all(
                    "Healthcare Service Insurance Coverage",
                    filters={
                        "healthcare_service_template": template,
                        "healthcare_insurance_coverage_plan": healthcare_insurance_coverage_plan,
                    },
                    fields=["name", "approval_mandatory_for_claim"],
                )
                if len(insurance_coverages) > 0:
                    is_restricted = insurance_coverages[0].approval_mandatory_for_claim
    return is_restricted


# Sales Invoice Dialog Box for Healthcare Services
@frappe.whitelist()
def set_healthcare_services(doc, checked_values):
    import json

    doc = frappe.get_cached_doc(json.loads(doc))
    checked_values = json.loads(checked_values)
    doc.items = []

    for checked_item in checked_values:
        item_line = doc.append("items", {})
        item_line.item_code = checked_item["item"]
        item_line.qty = 1
        item_line.allow_over_sell = 1

        if checked_item["qty"]:
            item_line.qty = checked_item["qty"]

        if checked_item["rate"]:
            item_line.rate = checked_item["rate"]
        else:
            item_line.rate = get_item_price(checked_item["item"], doc.selling_price_list, doc.company)
        item_line.amount = float(item_line.rate) * float(item_line.qty)

        if checked_item["dt"]:
            item_line.reference_dt = checked_item["dt"]

        if checked_item["dn"]:
            item_line.reference_dn = checked_item["dn"]

        if checked_item["description"]:
            item_line.description = checked_item["description"]

        if checked_item["service_request"]:
            item_line.service_request = checked_item["service_request"]

        if checked_item["dt"] not in [
            "Inpatient Occupancy",
            "Inpatient Consultancy",
        ]:
            parent_encounter = frappe.get_cached_value(
                checked_item["dt"],
                checked_item["dn"],
                "parent",
            )
            item_line.healthcare_practitioner, company = frappe.get_cached_value(
                "Patient Encounter",
                parent_encounter,
                ["practitioner", "company"],
            )

            if checked_item["dt"] == "Drug Prescription":
                item_line.healthcare_service_unit = frappe.get_cached_value(
                    checked_item["dt"],
                    checked_item["dn"],
                    "healthcare_service_unit",
                )

            else:
                childs_map = get_childs_map()
                map_obj = childs_map.get(checked_item["dt"])
                service_item = frappe.get_cached_value(
                    checked_item["dt"],
                    checked_item["dn"],
                    map_obj.get("item"),
                )
                comapny_option = get_template_company_option(service_item, company)
                item_line.healthcare_service_unit = comapny_option.service_unit

        if item_line.healthcare_service_unit:
            item_line.warehouse = get_warehouse_from_service_unit(item_line.healthcare_service_unit)

    doc.set_missing_values(for_validate=True)
    doc.save()
    return doc.name


# create LRPMT docs for Cash inpatient
def inpatient_billing(encounter_doc, method):
    if encounter_doc.insurance_subscription:  # IPD/OPD insurance
        return

    if not encounter_doc.inpatient_record:  # OPD cash or insurance
        return

    # SHM Rock: 207
    child_tables_list = [
        {
            "table_field": "lab_test_prescription",
            "item_field": "lab_test_code",
            "doctype": "Lab Test Template",
        },
        {
            "table_field": "radiology_procedure_prescription",
            "item_field": "radiology_examination_template",
            "doctype": "Radiology Examination Template",
        },
        {
            "table_field": "procedure_prescription",
            "item_field": "procedure",
            "doctype": "Clinical Procedure Template",
        },
    ]
    for child_table_field in child_tables_list:
        if encounter_doc.get(child_table_field.get("table_field")):
            child_table = encounter_doc.get(child_table_field.get("table_field"))
            for child in child_table:
                is_disabled = frappe.get_cached_value(
                    child_table_field.get("doctype"),
                    child.get(child_table_field.get("item_field")),
                    "disabled",
                )
                if is_disabled == 1:
                    frappe.throw(
                        _(f"{child_table_field.get('doctype')}: <b>{child.get(child_table_field.get('item_field'))}</b> selected at Row#: {child.idx} is <b>disabled</b>. Please select an enabled item."))

                if child.is_cancelled or child.is_not_available_inhouse or child.hms_tz_is_limit_exceeded:
                    continue

                if child.doctype == "Lab Prescription":
                    create_individual_lab_test(encounter_doc, child)

                elif child.doctype == "Radiology Procedure Prescription":
                    create_individual_radiology_examination(encounter_doc, child)

                elif child.doctype == "Procedure Prescription":
                    create_individual_procedure_prescription(encounter_doc, child)

    create_therapy_plan(enc_doc=encounter_doc)
    create_delivery_note(encounter_doc, method)


# create LRPMT docs for Cash OPD and Insurance (OPD & IPD) patient
@frappe.whitelist()
def create_healthcare_docs(reference_encounter, encounter_list=[], method="event"):
    if len(encounter_list) == 0:
        encounter_list = frappe.db.get_all(
            "Patient Encounter",
            filters={"reference_encounter": reference_encounter},
            pluck="name"
        )

    for encounter in encounter_list:
        encounter_doc = frappe.get_cached_doc("Patient Encounter", encounter)

        create_lrp_docs(encounter_doc)
        create_therapy_plan(enc_doc=encounter_doc)
        create_delivery_note(encounter_doc, method)

    if method == "from_button":
        frappe.msgprint(
            _(f"The {len(encounter_list)} patient encounters were processed for creating pending healthcare docs.")
        )


def create_lrp_docs(encounter_doc):
    if encounter_doc.docstatus != 1:
        frappe.msgprint(
            _("Cannot process Patient Encounter that is not submitted! Please submit" " and try again."),
            alert=True,
        )
        return

    if not encounter_doc.appointment:
        frappe.msgprint(
            _("Patient Encounter does not have patient appointment number! Request" " for support with this message."),
            alert=True,
        )
        return

    if (
        not encounter_doc.insurance_subscription
        and not encounter_doc.inpatient_record
        and not encounter_doc.healthcare_package_order
    ):
        return

    child_tables_list = [
        "lab_test_prescription",
        "radiology_procedure_prescription",
        "procedure_prescription",
    ]
    for child_table_field in child_tables_list:
        if encounter_doc.get(child_table_field):
            child_table = encounter_doc.get(child_table_field)

            for child in child_table:
                if encounter_doc.insurance_subscription and child.prescribe == 1:
                    continue

                if child.is_cancelled or child.is_not_available_inhouse or child.hms_tz_is_limit_exceeded:
                    continue

                if child.doctype == "Lab Prescription":
                    create_individual_lab_test(encounter_doc, child)

                elif child.doctype == "Radiology Procedure Prescription":
                    create_individual_radiology_examination(encounter_doc, child)

                elif child.doctype == "Procedure Prescription":
                    create_individual_procedure_prescription(encounter_doc, child)


def create_individual_lab_test(source_doc, encounter_child, hsr_child=None):
    if encounter_child.lab_test_created == 1 or encounter_child.is_not_available_inhouse:
        return

    insurance_subscription = ""
    insurance_coverage_plan = ""
    insurance_company = ""
    prescribe = 0
    if hsr_child:
        if hsr_child.payment_type == "Insurance":
            # consider insurance details from HSR
            insurance_subscription = hsr_child.insurance_subscription
            insurance_coverage_plan = hsr_child.payor_plan
            insurance_company = hsr_child.insurance_company
        else:
            prescribe = 1

    elif encounter_child and encounter_child.prescribe == 0:
        # consider insurance details from encounter
        insurance_subscription = source_doc.insurance_subscription
        insurance_coverage_plan = source_doc.insurance_coverage_plan
        insurance_company = source_doc.insurance_company
    elif encounter_child and encounter_child.prescribe == 1:
        prescribe = 1

    patient_sex = frappe.get_cached_value("Patient", source_doc.patient, "sex")

    doc = frappe.new_doc("Lab Test")
    doc.patient = source_doc.patient
    doc.patient_sex = patient_sex
    doc.appointment = source_doc.appointment
    doc.company = source_doc.company
    doc.template = encounter_child.lab_test_code
    doc.practitioner = source_doc.practitioner
    doc.source = source_doc.source

    if prescribe == 1:
        doc.prescribe = 1
    else:
        doc.insurance_subscription = insurance_subscription
        doc.hms_tz_insurance_coverage_plan = insurance_coverage_plan
        doc.insurance_company = insurance_company

    doc.ref_doctype = source_doc.doctype
    doc.ref_docname = source_doc.name
    doc.hms_tz_ref_childname = encounter_child.name
    doc.is_restricted = encounter_child.is_restricted
    doc.invoiced = 1
    doc.service_comment = (
        (encounter_child.medical_code or "No ICD Code") + " : " + (encounter_child.lab_test_comment or "No Comment")
    )

    doc.save(ignore_permissions=True)
    if doc.get("name"):
        frappe.msgprint(
            _(f"Lab Test: <b>{doc.name}</b> for <b>{encounter_child.lab_test_code}</b> created successfully.")
        )

        encounter_child.lab_test_created = 1
        encounter_child.delivered_quantity = 1
        encounter_child.lab_test = doc.name
        encounter_child.db_update()

        if hsr_child:
            hsrp = DocType("Healthcare Service Request Payment")
            (
                frappe.qb.update(hsrp)
                .set(hsrp.lrpmt_doc_created, 1)
                .set(hsrp.lrpmt_doctype, doc.doctype)
                .set(hsrp.lrpmt_docname, doc.name)
                .set(hsrp.lrpmt_status, "Draft")
                .where((hsrp.ref_docname == hsr_child.ref_docname) & (hsrp.request_id == hsr_child.request_id))
            ).run()


def create_individual_radiology_examination(source_doc, encounter_child, hsr_child=None):
    if encounter_child.radiology_examination_created == 1 or encounter_child.is_not_available_inhouse:
        return

    insurance_subscription = ""
    insurance_coverage_plan = ""
    insurance_company = ""
    prescribe = 0
    if hsr_child:
        if hsr_child.payment_type == "Insurance":
            # consider insurance details from HSR
            insurance_subscription = hsr_child.insurance_subscription
            insurance_coverage_plan = hsr_child.payor_plan
            insurance_company = hsr_child.insurance_company
        else:
            prescribe = 1

    elif encounter_child and encounter_child.prescribe == 0:
        # consider insurance details from encounter
        insurance_subscription = source_doc.insurance_subscription
        insurance_coverage_plan = source_doc.insurance_coverage_plan
        insurance_company = source_doc.insurance_company
    elif encounter_child and encounter_child.prescribe == 1:
        prescribe = 1

    patient_sex = frappe.get_cached_value("Patient", source_doc.patient, "sex")

    doc = frappe.new_doc("Radiology Examination")
    doc.patient = source_doc.patient
    doc.hms_tz_patient_sex = patient_sex
    doc.hms_tz_patient_age = source_doc.patient_age
    doc.appointment = source_doc.appointment
    doc.company = source_doc.company
    doc.radiology_examination_template = encounter_child.radiology_examination_template
    doc.practitioner = source_doc.practitioner
    doc.source = source_doc.source
    if prescribe == 1:
        doc.prescribe = 1
    else:
        doc.insurance_subscription = insurance_subscription
        doc.hms_tz_insurance_coverage_plan = insurance_coverage_plan
        doc.insurance_company = insurance_company

    doc.medical_department = frappe.get_cached_value(
        "Radiology Examination Template",
        encounter_child.radiology_examination_template,
        "medical_department",
    )
    doc.ref_doctype = source_doc.doctype
    doc.ref_docname = source_doc.name
    doc.hms_tz_ref_childname = encounter_child.name
    doc.is_restricted = encounter_child.is_restricted
    doc.invoiced = 1
    doc.service_comment = (
        (encounter_child.medical_code or "No ICD Code")
        + " : "
        + (encounter_child.radiology_test_comment or "No Comment")
    )

    doc.save(ignore_permissions=True)
    if doc.get("name"):
        frappe.msgprint(
            _(f"Radiology Examination: <b>{doc.name}</b> for <b>{encounter_child.radiology_examination_template}</b> created successfully."))

        encounter_child.radiology_examination_created = 1
        encounter_child.delivered_quantity = 1
        encounter_child.radiology_examination = doc.name
        encounter_child.db_update()

        if hsr_child:
            hsrp = DocType("Healthcare Service Request Payment")
            (
                frappe.qb.update(hsrp)
                .set(hsrp.lrpmt_doc_created, 1)
                .set(hsrp.lrpmt_doctype, doc.doctype)
                .set(hsrp.lrpmt_docname, doc.name)
                .set(hsrp.lrpmt_status, "Draft")
                .where((hsrp.ref_docname == hsr_child.ref_docname) & (hsrp.request_id == hsr_child.request_id))
            ).run()


def create_individual_procedure_prescription(source_doc, encounter_child, hsr_child=None):
    if encounter_child.procedure_created == 1 or encounter_child.is_not_available_inhouse:
        return

    insurance_subscription = ""
    insurance_coverage_plan = ""
    insurance_company = ""
    prescribe = 0
    if hsr_child:
        if hsr_child.payment_type == "Insurance":
            # consider insurance details from HSR
            insurance_subscription = hsr_child.insurance_subscription
            insurance_coverage_plan = hsr_child.payor_plan
            insurance_company = hsr_child.insurance_company
        else:
            prescribe = 1

    elif encounter_child and encounter_child.prescribe == 0:
        # consider insurance details from encounter
        insurance_subscription = source_doc.insurance_subscription
        insurance_coverage_plan = source_doc.insurance_coverage_plan
        insurance_company = source_doc.insurance_company
    elif encounter_child and encounter_child.prescribe == 1:
        prescribe = 1

    patient_sex = frappe.get_cached_value("Patient", source_doc.patient, "sex")

    doc = frappe.new_doc("Clinical Procedure")
    doc.patient = source_doc.patient
    doc.appointment = source_doc.appointment
    doc.company = source_doc.company
    doc.procedure_template = encounter_child.procedure
    doc.practitioner = source_doc.practitioner
    doc.source = source_doc.source
    if prescribe == 1:
        doc.prescribe = 1
    else:
        doc.insurance_subscription = insurance_subscription
        doc.hms_tz_insurance_coverage_plan = insurance_coverage_plan
        doc.insurance_company = insurance_company
    doc.patient_sex = patient_sex
    doc.patient_age = source_doc.patient_age
    doc.medical_department = frappe.get_cached_value(
        "Clinical Procedure Template",
        encounter_child.procedure,
        "medical_department",
    )
    doc.ref_doctype = source_doc.doctype
    doc.ref_docname = source_doc.name
    doc.hms_tz_ref_childname = encounter_child.name
    doc.is_restricted = encounter_child.is_restricted
    doc.invoiced = 1
    doc.service_comment = (
        (encounter_child.medical_code or "No ICD Code") + " : " + (encounter_child.comments or "No Comment")
    )

    doc.save(ignore_permissions=True)
    if doc.get("name"):
        url = get_url_to_form(doc.doctype, doc.name)
        frappe.msgprint(
            f"Clinical Procedure: <a href='{url}'><strong>{doc.name}</strong></a> for <b>{encounter_child.procedure}</b> created successfully"
        )

        encounter_child.procedure_created = 1
        encounter_child.delivered_quantity = 1
        encounter_child.clinical_procedure = doc.name
        encounter_child.db_update()

        if hsr_child:
            hsrp = DocType("Healthcare Service Request Payment")
            (
                frappe.qb.update(hsrp)
                .set(hsrp.lrpmt_doc_created, 1)
                .set(hsrp.lrpmt_doctype, doc.doctype)
                .set(hsrp.lrpmt_docname, doc.name)
                .set(hsrp.lrpmt_status, "Draft")
                .where((hsrp.ref_docname == hsr_child.ref_docname) & (hsrp.request_id == hsr_child.request_id))
            ).run()


def create_therapy_plan(enc_doc=None, invoice_therapy_dict=[]):
    therapies = []
    encounter_ids = []
    patient_encounter_docs = []

    if not enc_doc and len(invoice_therapy_dict) == 0:
        return

    if len(invoice_therapy_dict) > 0:
        # These invoice_therapy_dict comes from sales invoice items
        for row in invoice_therapy_dict:
            therapy_child = frappe.get_cached_doc("Therapy Plan Detail", row.reference_dn)
            if therapy_child.is_cancelled == 1:
                frappe.throw(
                    f"Item: {frappe.bold(therapy_child.therapy_type)} RowNo#: {frappe.bold(row.idx)} is already cancelled,\
                      Please confirm cancellation of this item on Patient Encounter and remove this item from sales invoice"
                )

            if therapy_child.parent not in encounter_ids:
                encounter_ids.append(therapy_child.parent)
                enc_doc = frappe.get_cached_doc("Patient Encounter", therapy_child.parent)
                patient_encounter_docs.append(enc_doc)

            if (
                therapy_child.therapy_plan_created
                or therapy_child.is_not_available_inhouse
                or therapy_child.hms_tz_is_limit_exceeded
            ):
                continue

            therapy_child.invoiced = 1
            therapy_child.sales_invoice_number = row.parent
            therapy_child.save(ignore_permissions=True)
            therapies.append(therapy_child)

            row.hms_tz_is_lrp_item_created = 1
            row.db_update()

    elif len(enc_doc.therapies) > 0:
        if enc_doc.docstatus != 1:
            frappe.msgprint(
                _("Cannot process Patient Encounter that is not submitted! Please submit" " and try again."),
                alert=True,
            )
            return

        if not enc_doc.appointment:
            frappe.msgprint(
                _(
                    "Patient Encounter does not have patient appointment number! Request"
                    " for support with this message."
                ),
                alert=True,
            )
            return

        if not enc_doc.insurance_subscription and not enc_doc.inpatient_record:
            return

        patient_encounter_docs.append(enc_doc)
        for row in enc_doc.therapies:
            if (
                row.is_cancelled
                or row.hms_tz_is_limit_exceeded
                or row.is_not_available_inhouse
                or row.therapy_plan_created
            ):
                continue

            # ignore uncovered therapies for insurance patients
            if enc_doc.insurance_subscription and row.prescribe == 1:
                continue

            # ignore therapies that won't be paid by cash
            if not enc_doc.insurance_subscription and row.prescribe == 0:
                continue

            is_disabled = frappe.get_cached_value("Therapy Type", row.therapy_type, "disabled")
            if is_disabled == 1:
                frappe.throw(
                    _(f"Therapy Type: <b>{row.therapy_type}</b> selected at Row#: {row.idx} is <b>disabled</b>. Please select an enabled item."))

            therapies.append(row)

    if len(therapies) == 0:
        return

    create_plan(patient_encounter_docs, therapies)


def create_plan(patient_encounter_docs, therapies, therapy_map={}):
    for encounter_doc in patient_encounter_docs:
        item_counts = 0
        patient_sex = frappe.get_cached_value("Patient", encounter_doc.patient, "sex")

        doc = frappe.new_doc("Therapy Plan")
        doc.patient = encounter_doc.patient
        doc.company = encounter_doc.company
        doc.start_date = encounter_doc.encounter_date
        doc.hms_tz_appointment = encounter_doc.appointment
        doc.hms_tz_patient_age = encounter_doc.patient_age
        doc.hms_tz_patient_sex = patient_sex
        doc.ref_doctype = encounter_doc.doctype
        doc.ref_docname = encounter_doc.name

        hsr_child = None
        for entry in therapies:
            if entry.parent == encounter_doc.name:
                item_counts += 1

                if therapy_map:
                    if not hsr_child:
                        hsr_child = therapy_map.get(entry.name)

                doc.append(
                    "therapy_plan_details",
                    {
                        "therapy_type": entry.therapy_type,
                        "prescribe": entry.prescribe or 0,
                        "is_restricted": entry.is_restricted or 0,
                        "hms_tz_ref_childname": entry.name,
                        "no_of_sessions": entry.no_of_sessions - entry.sessions_cancelled,
                        "department_hsu": entry.department_hsu,
                    },
                )
        if item_counts == 0:
            continue

        if hsr_child and hsr_child.payment_type == "Insurance":
            # consider insurance details from HSR
            doc.hms_tz_insurance_coverage_plan = hsr_child.payor_plan
            doc.insurance_company = hsr_child.insurance_company
        else:
            doc.hms_tz_insurance_coverage_plan = encounter_doc.insurance_coverage_plan
            doc.insurance_company = encounter_doc.insurance_company

        doc.save(ignore_permissions=True)
        if doc.get("name"):
            # April 09, 2024
            # stopping updating therapy plan on encounter,
            # since single encounter may have multiple therapy plans,
            # this may happen when insurance patient pay cash for some
            # therapies and insurance for other therapies

            # encounter_doc.db_set("therapy_plan", doc.name)
            for entry in therapies:
                if entry.parent == encounter_doc.name:
                    entry.therapy_plan_created = 1
                    entry.delivered_quantity = entry.no_of_sessions - entry.sessions_cancelled
                    entry.db_update()

                    if therapy_map:
                        therapy_child = therapy_map.get(entry.name)
                        if therapy_child:
                            hsrp = DocType("Healthcare Service Request Payment")
                            (
                                frappe.qb.update(hsrp)
                                .set(hsrp.lrpmt_doc_created, 1)
                                .set(hsrp.lrpmt_doctype, doc.doctype)
                                .set(hsrp.lrpmt_docname, doc.name)
                                .set(hsrp.lrpmt_status, "Draft")
                                .where(
                                    (hsrp.ref_docname == therapy_child.ref_docname)
                                    & (hsrp.request_id == therapy_child.request_id)
                                )
                            ).run()

            frappe.msgprint(
                _(f"Therapy Plan {frappe.bold(doc.name)} created successfully."),
                alert=True,
            )


def create_delivery_note(encounter_doc, method):
    if not encounter_doc.appointment:
        return

    if (
        not encounter_doc.insurance_subscription
        and not encounter_doc.inpatient_record
        and not encounter_doc.healthcare_package_order
    ):
        return

    # Create list of warehouses to process delivery notes by warehouses
    warehouses = []
    for line in encounter_doc.drug_prescription:
        if encounter_doc.insurance_subscription and line.prescribe:
            continue

        if (
            line.drug_prescription_created
            or line.is_not_available_inhouse
            or line.is_cancelled
            or line.hms_tz_is_limit_exceeded
        ):
            continue

        item_code = frappe.get_cached_value("Medication", line.drug_code, "item")
        if not item_code:
            frappe.throw(
                _(f"The Item Code for {line.drug_code} is not found!<br>Please request administrator to set item code in {line.drug_code}."))

        is_stock = frappe.get_cached_value("Item", item_code, "is_stock_item")
        if not is_stock:
            continue

        warehouse = get_warehouse_from_service_unit(line.healthcare_service_unit)
        if warehouse and warehouse not in warehouses:
            warehouses.append(warehouse)

    # apply discount if it is available on Heathcare Insurance Company
    discount_percent = 0
    if encounter_doc.insurance_company and "NHIF" not in encounter_doc.insurance_company:
        discount_percent = get_discount_percent(encounter_doc.insurance_company)

    # Process list of warehouses
    for element in warehouses:
        items = []
        for row in encounter_doc.drug_prescription:
            if (
                row.drug_prescription_created
                or row.is_not_available_inhouse
                or row.is_cancelled
                or row.hms_tz_is_limit_exceeded
            ):
                continue

            if encounter_doc.insurance_subscription and row.prescribe:
                continue

            warehouse = get_warehouse_from_service_unit(row.healthcare_service_unit)

            if element != warehouse:
                continue

            item_code = frappe.get_cached_value("Medication", row.drug_code, "item")
            if not item_code:
                frappe.throw(
                    _(f"The Item Code for {row.drug_code} is not found!<br>Please request administrator to set item code in {row.drug_code}."))

            is_stock, item_name = frappe.get_cached_value("Item", item_code, ["is_stock_item", "item_name"])
            if not is_stock:
                continue

            item = frappe.new_doc("Delivery Note Item")
            item.item_code = item_code
            item.item_name = item_name
            item.warehouse = warehouse
            item.is_restricted = row.is_restricted
            item.qty = row.quantity or 1
            item.medical_code = row.medical_code

            if row.prescribe:
                item.rate = row.amount
                item.price_list_rate = row.amount
            else:
                item.rate = row.amount - (row.amount * (discount_percent / 100))
                item.price_list_rate = row.amount
                if discount_percent > 0:
                    item.discount_percentage = discount_percent
                    item.hms_tz_is_discount_applied = 1

            item.reference_doctype = row.doctype
            item.reference_name = row.name
            item.healthcare_service_unit = row.healthcare_service_unit
            item.healthcare_practitioner = encounter_doc.practitioner

            item.description = ", <br>".join(
                [
                    "frequency: " + str(row.get("dosage") or "No Prescription Dosage"),
                    "period: " + str(row.get("period") or "No Prescription Period"),
                    "dosage_form: " + str(row.get("dosage_form") or ""),
                    "interval: " + str(row.get("interval") or ""),
                    "interval_uom: " + str(row.get("interval_uom") or ""),
                    "medical_code: " + str(row.get("medical_code") or "No medical code"),
                    "Doctor's comment: " + (row.get("comment") or "Take medication as per dosage."),
                ]
            )
            items.append(item)
            row.drug_prescription_created = 1
            row.db_update()

        if len(items) == 0:
            continue

        authorization_number = ""
        encounter_customer = ""
        insurance_coverage_plan = ""
        if (
            not encounter_doc.insurance_subscription
            and encounter_doc.inpatient_record
            or (encounter_doc.mode_of_payment and encounter_doc.healthcare_package_order)
        ):
            encounter_customer = frappe.get_cached_value("Patient", encounter_doc.patient, "customer")
            insurance_coverage_plan = ""

        elif not encounter_customer:
            encounter_customer = frappe.get_cached_value(
                "Healthcare Insurance Company",
                encounter_doc.insurance_company,
                "customer",
            )
            insurance_coverage_plan = encounter_doc.insurance_coverage_plan
            authorization_number = frappe.get_cached_value(
                "Patient Appointment",
                encounter_doc.appointment,
                "authorization_number",
            )

        doc = frappe.get_doc(
            dict(
                doctype="Delivery Note",
                posting_date=nowdate(),
                posting_time=nowtime(),
                set_warehouse=element,
                company=encounter_doc.company,
                customer=encounter_customer,
                currency=frappe.get_cached_value("Company", encounter_doc.company, "default_currency"),
                items=items,
                coverage_plan_name=insurance_coverage_plan,
                reference_doctype=encounter_doc.doctype,
                reference_name=encounter_doc.name,
                authorization_number=authorization_number,
                patient=encounter_doc.patient,
                patient_name=encounter_doc.patient_name,
                healthcare_service_unit=encounter_doc.healthcare_service_unit,
                healthcare_practitioner=encounter_doc.practitioner,
            )
        )
        doc.flags.ignore_permissions = True
        doc.set_missing_values()
        doc.insert(ignore_permissions=True)
        doc.reload()

        if doc.get("name"):
            # update drug prescription for report purpose
            for d in encounter_doc.drug_prescription:
                for item in doc.items:
                    if d.name == item.reference_name:
                        frappe.db.set_value(
                            "Drug Prescription",
                            item.reference_name,
                            {
                                "dn_detail": item.name,
                                "delivery_note": doc.name,
                                "drug_prescription_created": 1,
                            },
                            update_modified=False,
                        )

            frappe.msgprint(_(f"Pharmacy Dispensing/Delivery Note {frappe.bold(doc.name)} created successfully."))


@frappe.whitelist()
def create_delivery_notes_from_hsr(encounter_doc, medications):
    """
    Create delivery notes for items from Healthcare Service Request Payment child table

    Args:
        encounter_doc: Patient Encounter document
        medications: List of medication items

    # The function will:
    1. Group items by warehouse
    2. Create delivery notes for each warehouse
    3. Update drug_prescription_created and lrpmt_doc_created fields
    """

    warehouses_map = {}

    for row in medications:
        if row.lrpmt_doc_created == 1 or row.is_cancelled == 1:
            continue

        item_code = frappe.get_cached_value("Medication", row.service_name, "item")
        if not item_code:
            frappe.throw(
                _(
                    f"The Item Code for {row.service_name} is not found!<br>Please request administrator \
                        to set item code in {row.service_name}."
                ),
            )

        is_stock = frappe.get_cached_value("Item", item_code, "is_stock_item")
        if not is_stock:
            frappe.throw(
                _(
                    f"The Item Code for {row.service_name} is not a stock item!<br>Please request administrator \
                        to set item code in {row.service_name}."
                ),
            )

        row.item_code = item_code

        warehouse = get_warehouse_from_service_unit(row.department_hsu)

        if warehouse not in warehouses_map:
            warehouses_map[warehouse] = []

        warehouses_map[warehouse].append(row)

    # Apply discount if available on Healthcare Insurance Company
    discount_percent = 0
    if row.insurance_company and "NHIF" not in row.insurance_company:
        discount_percent = get_discount_percent(row.insurance_company)

    # Process each warehouse and create delivery notes
    for warehouse, drugs in warehouses_map.items():
        items = []

        for row in drugs:
            if not row.item_code:
                item_code = frappe.get_cached_value("Medication", row.service_name, "item")
                row.item_code = item_code

            item_name = frappe.get_cached_value("Item", row.item_code, "item_name")

            item = frappe.new_doc("Delivery Note Item")
            item.item_code = row.item_code
            item.item_name = item_name
            item.warehouse = warehouse
            item.is_restricted = row.is_restricted
            item.qty = row.qty

            # Set rate and apply discount if needed
            if row.payment_type == "Cash":
                item.rate = row.amount
                item.price_list_rate = row.amount
            else:
                item.rate = row.amount - (row.amount * (discount_percent / 100))
                item.price_list_rate = row.amount
                if discount_percent > 0:
                    item.discount_percentage = discount_percent
                    item.hms_tz_is_discount_applied = 1

            item.reference_doctype = row.ref_doctype
            item.reference_name = row.ref_docname
            item.healthcare_service_unit = row.department_hsu
            item.healthcare_practitioner = encounter_doc.practitioner

            drug_doc = frappe.get_cached_doc(row.ref_doctype, row.ref_docname)
            item.description = ", <br>".join(
                [
                    "frequency: " + str(drug_doc.get("dosage") or "No Prescription Dosage"),
                    "period: " + str(drug_doc.get("period") or "No Prescription Period"),
                    "dosage_form: " + str(drug_doc.get("dosage_form") or ""),
                    "interval: " + str(drug_doc.get("interval") or ""),
                    "interval_uom: " + str(drug_doc.get("interval_uom") or ""),
                    "medical_code: " + str(drug_doc.get("medical_code") or "No medical code"),
                    "Doctor's comment: " + (drug_doc.get("comment") or "Take medication as per dosage."),
                ]
            )

            items.append(item)

        if len(items) == 0:
            continue

        customer = ""
        insurance_coverage_plan = ""
        authorization_number = ""

        if encounter_doc.insurance_company:
            customer = frappe.get_cached_value(
                "Healthcare Insurance Company",
                encounter_doc.insurance_company,
                "customer",
            )
            insurance_coverage_plan = encounter_doc.insurance_coverage_plan
            authorization_number = frappe.get_cached_value(
                "Patient Appointment",
                encounter_doc.appointment,
                "authorization_number",
            )
        else:
            customer = frappe.get_cached_value("Patient", encounter_doc.patient, "customer")

        doc = frappe.get_doc(
            dict(
                doctype="Delivery Note",
                posting_date=nowdate(),
                posting_time=nowtime(),
                set_warehouse=warehouse,
                company=encounter_doc.company,
                customer=customer,
                currency=frappe.get_cached_value("Company", encounter_doc.company, "default_currency"),
                items=items,
                healthcare_service_unit=encounter_doc.healthcare_service_unit,
                healthcare_practitioner=encounter_doc.practitioner,
                coverage_plan_name=insurance_coverage_plan,
                reference_doctype=encounter_doc.doctype,
                reference_name=encounter_doc.name,
                authorization_number=authorization_number,
                patient=encounter_doc.patient,
                patient_name=encounter_doc.patient_name,
            )
        )

        doc.flags.ignore_permissions = True
        doc.set_missing_values()
        doc.insert(ignore_permissions=True)
        doc.reload()

        if doc.get("name"):
            hsrp = DocType("Healthcare Service Request Payment")
            dp = DocType("Drug Prescription")
            hre = DocType("Hospital Revenue Entry")

            for item in doc.items:
                (
                    frappe.qb.update(hsrp)
                    .set(hsrp.lrpmt_doc_created, 1)
                    .set(hsrp.lrpmt_doctype, doc.doctype)
                    .set(hsrp.lrpmt_docname, doc.name)
                    .set(hsrp.lrpmt_status, "Draft")
                    .set(hsrp.dn_detail, item.name)
                    .where(hsrp.ref_docname == item.reference_name)
                ).run()

                (
                    frappe.qb.update(dp)
                    .set(dp.drug_prescription_created, 1)
                    .set(dp.delivery_note, doc.name)
                    .set(dp.dn_detail, item.name)
                    .where(dp.name == item.reference_name)
                ).run()

                (
                    frappe.qb.update(hre)
                    .set(hre.lrpmt_doctype, doc.doctype)
                    .set(hre.lrpmt_docname, doc.name)
                    .where(hre.ref_docname == item.reference_name)
                ).run()

            frappe.msgprint(_(f"Pharmacy Dispensing/Delivery Note {frappe.bold(doc.name)} created successfully."))


def msgThrow(msg, method="throw", alert=True):
    if method in ["before_submit", "on_submit", "throw"]:
        frappe.throw(msg)
    else:
        frappe.msgprint(msg, alert=alert)


def msgPrint(msg, method="throw", alert=False):
    if method == "validate":
        frappe.msgprint(msg, alert=True)
    else:
        frappe.msgprint(msg, alert=alert)


def get_approval_number_from_LRPMT(ref_doctype=None, ref_docname=None, dn_detail=None):
    if dn_detail:
        return frappe.get_cached_value("Delivery Note Item", dn_detail, "approval_number")

    if not ref_doctype or not ref_docname:
        return None

    return frappe.get_cached_value(ref_doctype, ref_docname, "approval_number")


def set_uninvoiced_so_closed():
    pass

    uninvoiced_so_list = frappe.get_list(
        "Sales Order",
        fields=("name"),
        filters={
            "status": ("in", ["To Bill", "To Deliver and Bill"]),
            "docstatus": 1,
            "creation": ("<", now_datetime() - timedelta(hours=3)),
        },
    )
    for so in uninvoiced_so_list:
        so_doc = frappe.get_cached_doc("Sales Order", so.name)
        so_doc.update_status("Closed")


def validate_hsu_healthcare_template(doc):
    doctypes = [
        "Lab Test Template",
        "Therapy Type",
        "Radiology Examination Template",
        "Clinical Procedure Template",
    ]
    if doc.doctype not in doctypes:
        return
    companys = frappe.get_all("Company", filters={"domain": "Healthcare"})
    companys = [i.name for i in companys]
    for company in companys:
        row = next(
            (d for d in doc.company_options if d.get("company") == company),
            None,
        )
        if not row:
            frappe.msgprint(_(f"Please set Healthcare Service Unit for company {company}"))


@frappe.whitelist()
def get_template_company_option(template=None, company=None, method=None):
    exist = frappe.db.exists("Healthcare Company Option", {"company": company, "parent": template})
    if exist:
        doc = frappe.get_cached_doc(
            "Healthcare Company Option",
            {"company": company, "parent": template},
        )
        return doc
    else:
        msgThrow(
            _(f"No company option found for template: {frappe.bold(template)} and company: {frappe.bold(company)}"),
            method=method,
        )


def delete_or_cancel_draft_document():
    """
    A routine to
        1. Cancel open appointments after every 7 days,
        2. Delete draft vital signs after every 7 days and
        3. Cancel draft delivery note after every 2 days
    this routine runs every day on 2:30am at night
    """

    before_7_days_date = add_to_date(nowdate(), days=-7, as_string=False)
    before_2_days_date = add_to_date(nowdate(), days=-2, as_string=False)

    appointments = frappe.db.sql(
        f"""
        SELECT name FROM `tabPatient Appointment`
        WHERE status = "Open" AND appointment_date < '{before_7_days_date}'
    """,
        as_dict=1,
    )

    for app_doc in appointments:
        try:
            doc = frappe.get_cached_doc("Patient Appointment", app_doc.name)
            doc.status = "Cancelled"
            doc.save(ignore_permissions=True)

        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                str("Error in cancelling draft appointment"),
            )

    vital_docs = frappe.db.sql(
        f"""
        SELECT name FROM `tabVital Signs`
        WHERE docstatus = 0 AND signs_date < '{before_7_days_date}'
    """,
        as_dict=1,
    )

    for vs_doc in vital_docs:
        try:
            doc = frappe.get_cached_doc("Vital Signs", vs_doc.name)
            doc.delete()

        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                str("Error in deleting draft vital signs"),
            )
        frappe.db.commit()

    delivery_documents = frappe.db.sql(
        f"""
        SELECT name FROM `tabDelivery Note`
        WHERE docstatus = 0
        AND workflow_state != "Not Serviced"
        AND posting_date < '{before_2_days_date}'
    """,
        as_dict=1,
    )

    for delivery_note in delivery_documents:
        delivery_note_doc = frappe.get_cached_doc("Delivery Note", delivery_note.name)
        try:
            return_quatity_or_cancel_delivery_note_via_lrpmt_returns(delivery_note_doc, "Backend")

        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                str(
                    f"Error for Return or Cancel Delivery Note: {frappe.bold(delivery_note_doc.name)} Via LRPMT Returns"
                ),
            )

        frappe.db.commit()


@frappe.whitelist()
def return_quatity_or_cancel_delivery_note_via_lrpmt_returns(source_doc, method):
    """
    Return Quantiies to stock from submitted delivery note and/or
    Cancel draft delivery note if all items was not serviced
    """

    source_doc = frappe.get_cached_doc(frappe.parse_json(source_doc))

    status = ""
    if source_doc.docstatus == 1:
        status = "Submitted"
    else:
        status = "Draft"

    drug_items = []

    for dni_item in source_doc.items:
        drug_items.append(
            {
                "drug_name": dni_item.item_code,
                "quantity_prescribed": dni_item.qty,
                "quantity_to_return": dni_item.qty,
                "reason": "Not Serviced",
                "drug_condition": "Good",
                "encounter_no": source_doc.reference_name,
                "delivery_note_no": source_doc.name,
                "status": status,
                "dn_detail": dni_item.name,
                "child_name": dni_item.reference_name,
            }
        )

    target_doc = frappe.get_doc(
        dict(
            doctype="LRPMT Returns",
            patient=source_doc.patient,
            patient_name=source_doc.patient_name,
            appointment=source_doc.hms_tz_appointment_no,
            company=source_doc.company,
            drug_items=drug_items,
        )
    )

    target_doc.insert()
    target_doc.reload()

    if method == "From Front End":
        if source_doc.docstatus == 1:
            return target_doc.name

        else:
            target_doc.submit()
            url = get_url_to_form(target_doc.doctype, target_doc.name)
            frappe.msgprint(f"LRPMT Returns: <a href='{url}'>{frappe.bold(target_doc.name)}</a> is submitted")

            return True

    else:
        target_doc.submit()


def create_invoiced_items_if_not_created():
    """create pending LRP item(s) after submission of sales invoice"""

    from frappe.query_builder import DocType as dt

    si = dt("Sales Invoice")
    sii = dt("Sales Invoice Item")

    si_invoices = (
        frappe.qb.from_(si)
        .inner_join(sii)
        .on(si.name == sii.parent)
        .select(si.name.as_("name"))
        .where(
            si.patient.isnotnull()
            & (si.docstatus == 1)
            & (si.posting_date == nowdate())
            & (sii.hms_tz_is_lrp_item_created == 0)
        )
    ).run(as_dict=1)

    for invoice in si_invoices:
        si_doc = frappe.get_cached_doc("Sales Invoice", invoice.name)

        therapy_items = []

        for item in si_doc.items:
            if item.reference_dt in [
                "Lab Prescription",
                "Radiology Procedure Prescription",
                "Procedure Prescription",
            ]:
                if item.hms_tz_is_lrp_item_created == 1:
                    continue

                try:
                    child = frappe.get_cached_doc(item.reference_dt, item.reference_dn)
                    patient_encounter_doc = frappe.get_cached_doc("Patient Encounter", child.parent)

                    if child.doctype == "Lab Prescription":
                        ltt_doc = frappe.get_cached_doc("Lab Test Template", child.lab_test_code)

                        lab_doc = frappe.get_doc(
                            {
                                "doctype": "Lab Test",
                                "patient": patient_encounter_doc.patient,
                                "patient_sex": patient_encounter_doc.patient_sex,
                                "company": patient_encounter_doc.company,
                                "template": ltt_doc.name,
                                "practitioner": patient_encounter_doc.practitioner,
                                "source": patient_encounter_doc.source,
                                "prescribe": child.prescribe,
                                "insurance_subscription": (
                                    patient_encounter_doc.insurance_subscription
                                    if patient_encounter_doc.insurance_subscription
                                    else ""
                                ),
                                "appointment": patient_encounter_doc.appointment,
                                "ref_doctype": patient_encounter_doc.doctype,
                                "ref_docname": patient_encounter_doc.name,
                                "hms_tz_ref_childname": child.name,
                                "invoiced": 1,
                                "prescribe": 1,
                                "service_comment": child.medical_code
                                or "No ICD Code" + " : " + child.lab_test_comment
                                or "No Comment",
                            }
                        )
                        lab_doc.insert(ignore_permissions=True, ignore_mandatory=True)
                        if lab_doc.name:
                            child.lab_test_created = 1
                            child.invoiced = 1
                            child.sales_invoice_number = item.parent
                            child.db_update()

                    elif child.doctype == "Radiology Procedure Prescription":
                        radiology_doc = frappe.get_doc(
                            {
                                "doctype": "Radiology Examination",
                                "patient": patient_encounter_doc.patient,
                                "company": patient_encounter_doc.company,
                                "radiology_examination_template": child.radiology_examination_template,
                                "practitioner": patient_encounter_doc.practitioner,
                                "source": patient_encounter_doc.source,
                                "prescribe": child.prescribe,
                                "insurance_subscription": (
                                    patient_encounter_doc.insurance_subscription
                                    if patient_encounter_doc.insurance_subscription
                                    else ""
                                ),
                                "medical_department": frappe.get_cached_value(
                                    "Radiology Examination Template",
                                    child.radiology_examination_template,
                                    "medical_department",
                                ),
                                "appointment": patient_encounter_doc.appointment,
                                "ref_doctype": patient_encounter_doc.doctype,
                                "ref_docname": patient_encounter_doc.name,
                                "hms_tz_ref_childname": child.name,
                                "invoiced": 1,
                                "prescribe": 1,
                                "service_comment": child.medical_code
                                or "No ICD Code" + " : " + child.radiology_test_comment
                                or "No Comment",
                            }
                        )
                        radiology_doc.insert(ignore_permissions=True, ignore_mandatory=True)
                        if radiology_doc.name:
                            child.radiology_examination_created = 1
                            child.invoiced = 1
                            child.sales_invoice_number = item.parent
                            child.db_update()

                    elif child.doctype == "Procedure Prescription":
                        procedure_doc = frappe.get_doc(
                            {
                                "doctype": "Clinical Procedure",
                                "patient": patient_encounter_doc.patient,
                                "patient_sex": patient_encounter_doc.patient_sex,
                                "company": patient_encounter_doc.company,
                                "procedure_template": child.procedure,
                                "practitioner": patient_encounter_doc.practitioner,
                                "source": patient_encounter_doc.source,
                                "prescribe": child.prescribe,
                                "insurance_subscription": patient_encounter_doc.insurance_subscription,
                                "medical_department": frappe.get_cached_value(
                                    "Clinical Procedure Template",
                                    child.procedure,
                                    "medical_department",
                                ),
                                "appointment": patient_encounter_doc.appointment,
                                "ref_doctype": patient_encounter_doc.doctype,
                                "ref_docname": patient_encounter_doc.name,
                                "hms_tz_ref_childname": child.name,
                                "invoiced": 1,
                                "prescribe": 1,
                                "service_comment": child.medical_code
                                or "No ICD Code" + " : " + child.comments
                                or "No Comment",
                            }
                        )
                        procedure_doc.insert(ignore_permissions=True, ignore_mandatory=True)
                        if procedure_doc.name:
                            child.procedure_created = 1
                            child.invoiced = 1
                            child.sales_invoice_number = item.parent
                            child.db_update()

                    item.hms_tz_is_lrp_item_created = 1
                    item.db_update()
                except Exception:
                    traceback = frappe.get_traceback()
                    frappe.log_error(traceback)

            elif item.reference_dt == "Therapy Plan Detail":
                if item.hms_tz_is_lrp_item_created == 1:
                    continue

                therapy_items.append(item)

        create_therapy_plan(invoice_therapy_dict=therapy_items)

        frappe.db.commit()


@frappe.whitelist()
def auto_submit_nhif_patient_claim(setting_dict=None):
    """Routine to submit patient claims and will be triggered:
    1. Every 00:01 am at night by cron job
    2. By a button called 'Auto Submit Patient Claim' which is on Company NHIF settings
    """
    company_setting_detail = []

    if not setting_dict:
        company_setting_detail = frappe.get_all(
            "Company NHIF Settings",
            filters={"enable": 1, "enable_auto_submit_of_claims": 1},
            fields=["company", "submit_claim_year", "submit_claim_month"],
        )
    else:
        company_setting_detail.append(frappe._dict(json.loads(setting_dict)))

    if len(company_setting_detail) == 0:
        return

    for detail in company_setting_detail:
        frappe.enqueue(
            method=enqueue_auto_sending_of_patient_claims,
            queue="long",
            timeout=1000000,
            is_async=True,
            setting_obj=detail,
        )


def enqueue_auto_sending_of_patient_claims(setting_obj):
    from hms_tz.nhif.doctype.nhif_response_log.nhif_response_log import add_log

    patient_claims = frappe.get_all(
        "NHIF Patient Claim",
        filters={
            "company": setting_obj.company,
            "claim_month": setting_obj.submit_claim_month,
            "claim_year": setting_obj.submit_claim_year,
            "is_ready_for_auto_submission": 1,
            "docstatus": 0,
        },
    )

    if len(patient_claims) == 0:
        return

    success_count = 0
    failed_count = 0
    for claim in patient_claims:
        doc = frappe.get_cached_doc("NHIF Patient Claim", claim.name)
        try:
            doc.submit()
            doc.reload()
            if doc.docstatus == 1:
                success_count += 1
        except BaseException:
            failed_count += 1

    description = f"CLAIM'S AUTO SUBMISSION SUMMARY\n\n\ncompany: {setting_obj.company}\n\nTotal Claims Prepared for auto submit: {len(patient_claims)}\
        \n\nTotal claims Submitted: {success_count}\n\nTotal Claims failed: {failed_count}"
    add_log(
        request_type="AutoSubmitFolios",
        request_url="",
        request_header="",
        request_body="",
        response_data=description,
        status_code="Summary",
    )
    frappe.db.commit()


def auto_finalize_patient_encounters():
    """Auto finalize patient encounters after a number of days set in company settings

    IPD encounters will only be finalized if the inpatient record is discharged

    This routine runs every day at 3:00am at night
    """

    def finalize_encounter(encounter_list):
        for encounter in encounter_list:
            try:
                if (
                    encounter.inpatient_record
                    and frappe.get_cached_value(
                        "Inpatient Record",
                        encounter.inpatient_record,
                        "status",
                    )
                    != "Discharged"
                ):
                    continue

                else:
                    frappe.set_value(
                        "Patient Encounter",
                        encounter.name,
                        {
                            "finalized": 1,
                            "encounter_type": "Final",
                        },
                    )

                    reference_encounters = frappe.get_all(
                        "Patient Encounter",
                        {
                            "docstatus": 1,
                            "reference_encounter": encounter.reference_encounter,
                        },
                        ["name", "finalized"],
                    )
                    if len(reference_encounters) > 0:
                        for ref_encounter in reference_encounters:
                            if ref_encounter.finalized == 1:
                                continue

                            frappe.set_value(
                                "Patient Encounter",
                                ref_encounter,
                                {
                                    "finalized": 1,
                                },
                            )

            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    f"Error in finalizing encounter: {encounter.name}",
                )
                continue

    companies = frappe.get_all(
        "Company NHIF Settings",
        {"auto_finalize_patient_encounter": 1},
        ["company", "valid_days_to_auto_finalize_encounter"],
    )

    for row in companies:
        if row.valid_days_to_auto_finalize_encounter == 0:
            continue

        date = add_days(nowdate(), -row.valid_days_to_auto_finalize_encounter)
        encounters = frappe.get_all(
            "Patient Encounter",
            {
                "docstatus": 1,
                "duplicated": 0,
                "finalized": 0,
                "encounter_date": ["<=", date],
                "company": row.company,
            },
            ["name", "reference_encounter", "inpatient_record"],
            order_by="modified desc",
            limit=100,
        )
        for encounter_batch in create_batch(encounters, 100):
            finalize_encounter(encounter_batch)
            frappe.db.commit()


def validate_nhif_patient_claim_status(doctype_name, company, appointment, insurance_company=None, caller=None):
    """Stop Change/Cancel/Return of LRPMT Items After Claim Submission

    This is to ensure same LRPMT items on patient encounter and on NHIF patient claim,
    if the claim is submitted, then the user should not be able to change/cancel/return LRPMT items
    because items on Patient Encounter and items on NHIF patient claim will not match
    """
    if (
        frappe.get_cached_value(
            "Company NHIF Settings",
            company,
            "stop_change_of_lrpmt_items_after_claim_submission",
        )
        == 0
    ):
        return

    claim_no = None
    if not insurance_company and appointment:
        insurance_company, claim_no = frappe.get_cached_value(
            "Patient Appointment",
            appointment,
            ["insurance_company", "nhif_patient_claim"],
        )
    if insurance_company and "NHIF" in insurance_company:
        if not claim_no:
            claim_no = frappe.get_cached_value("Patient Appointment", appointment, "nhif_patient_claim")

        claim_status = frappe.get_cached_value("NHIF Patient Claim", claim_no, "docstatus")
        if claim_status == 1:
            claim_url = get_url_to_form("NHIF Patient Claim", claim_no)
            app_url = get_url_to_form("Patient Appointment", appointment)
            msg = f"""<div style="  text-align: justify; border: 1px solid #ccc; background-color: #f9f9f9; padding: 10px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); margin: 10px;">
                    NHIF Patient Claim: <a href='{claim_url}'><b>{claim_no}</b></a> for this Appointment: <a href='{app_url}'><b>{appointment}</b></a> is already submitted.<br><br>
                    Please stop Duplicating/Editing/Submitting this <b>{doctype_name}</b> to avoid making changes on items whose Claim is already submitted
                </div>"""

            if caller:
                frappe.msgprint(msg)
                return True
            else:
                frappe.throw(
                    msg,
                    title="<b>NHIF Patient Claim Already Submitted",
                    exc=frappe.ValidationError,
                )


def enqueue_auto_create_nhif_patient_claims():
    frappe.enqueue(
        method=auto_create_nhif_patient_claims,
        job_name="auto_create_nhif_patient_claims",
        queue="default",
        timeout=100000,
        is_async=True,
    )


def auto_create_nhif_patient_claims():
    """Auto create NHIF patient claims after a number of days set in company settings

    This routine runs every day at 01: 30am at night
    """

    pa = DocType("Patient Appointment")
    pe = DocType("Patient Encounter")
    ip = DocType("Inpatient Record")

    def get_appointments(appointment_date):
        appointments = (
            frappe.qb.from_(pa)
            .inner_join(pe)
            .on(pa.name == pe.appointment)
            .select(
                pa.name.as_("appointment"),
            )
            .where(
                (pa.status == "Closed")
                # (pa.insurance_company.like("NHIF"))
                & (pa.insurance_company == "NHIF")
                & (pa.company == "Shree Hindu Mandal Hospital - Dar es Salaam")
                & (pa.appointment_date == appointment_date)
                & (pa.nhif_patient_claim.isnull() | (pa.nhif_patient_claim == ""))
                & (pe.docstatus == 1)
                & (pe.duplicated == 0)
            )
        ).run(as_dict=True)

        appointment_ids = [i.appointment for i in appointments]
        return appointment_ids

    def get_ongoiong_inpatients():
        inpatient_appointments = (
            frappe.qb.from_(ip)
            .select(ip.patient_appointment)
            .where(
                # (ip.insurance_company.like("NHIF"))
                (ip.insurance_company == "NHIF")
                & (ip.company == "Shree Hindu Mandal Hospital - Dar es Salaam")
                & (ip.patient_appointment.isnotnull())
                & (ip.status != "Discharged")
            )
        ).run(as_dict=True)

        ongoing_inpatients = [i.patient_appointment for i in inpatient_appointments]

        return ongoing_inpatients

    def get_discharged_inpatients(discharge_date):
        inpatient_appointments = (
            frappe.qb.from_(ip)
            .inner_join(pa)
            .on(ip.patient_appointment == pa.name)
            .inner_join(pe)
            .on(ip.patient_appointment == pe.appointment)
            .select(ip.patient_appointment)
            .where(
                # (ip.insurance_company.like("NHIF"))
                (ip.insurance_company == "NHIF")
                & (ip.company == "Shree Hindu Mandal Hospital - Dar es Salaam")
                & (ip.patient_appointment.isnotnull())
                & (ip.status == "Discharged")
                & (ip.discharge_date == discharge_date)
                & (pa.status == "Closed")
                & (pa.nhif_patient_claim.isnull() | (pa.nhif_patient_claim == ""))
                & (pe.docstatus == 1)
                & (pe.duplicated == 0)
            )
        ).run(as_dict=True)

        discharged_appointments = [i.patient_appointment for i in inpatient_appointments]

        return discharged_appointments

    def create_claims(appointment_ids):
        for appointment in appointment_ids:
            try:
                doc = frappe.new_doc("NHIF Patient Claim")
                doc.patient_appointment = appointment
                doc.save(ignore_permissions=True)
                doc.reload()

            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    f"Error in creating NHIF Patient Claim for appointment: {appointment}",
                )
                continue

    before_1_day = add_days(nowdate(), -1)
    appointment_names = get_appointments(before_1_day)
    ongoing_inpatients = get_ongoiong_inpatients()
    discharged_appointments = get_discharged_inpatients(before_1_day)
    appointment_ids = list(
        set(list(set(appointment_names) - set(ongoing_inpatients)) + list(set(discharged_appointments)))
    )

    create_claims(appointment_ids)
