import frappe
from frappe import _
from frappe.query_builder import DocType


def execute(filters):
    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    columns = [
        {
            "fieldname": "nhif_patient_claim",
            "label": _("NHIF Patient Claim"),
            "fieldtype": "Link",
            "options": "NHIF Patient Claim",
            "width": 130,
        },
        {
            "fieldname": "patient",
            "label": _("Patient"),
            "fieldtype": "Data",
            "width": 100,
        },
        {
            "fieldname": "patient_name",
            "label": _("Patient Name"),
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "fieldname": "gender",
            "label": _("Gender"),
            "fieldtype": "Data",
            "width": 100,
        },
        {
            "fieldname": "patient_appointment",
            "label": _("Patient Appointment"),
            "fieldtype": "Link",
            "options": "Patient Appointment",
            "width": 150,
        },
        {
            "fieldname": "appointment_date",
            "label": _("Appointment Date"),
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "fieldname": "practitioner",
            "label": _("Practitioner"),
            "fieldtype": "Link",
            "options": "Healthcare Practitioner",
            "width": 150,
        },
        {
            "fieldname": "service_type",
            "label": _("Service Type"),
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "fieldname": "service_name",
            "label": _("Service Name"),
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "fieldname": "qty",
            "label": _("Qty"),
            "fieldtype": "Int",
            "width": 70,
        },
        {
            "fieldname": "unit_price",
            "label": _("Unit Price"),
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "fieldname": "amount_claimed",
            "label": _("Amount Claimed"),
            "fieldtype": "Currency",
            "width": 130,
        },
        {
            "fieldname": "admitted_date",
            "label": _("Admitted Date"),
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "fieldname": "discharge_date",
            "label": _("Discharge Date"),
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "fieldname": "folio_no",
            "label": _("Folio No"),
            "fieldtype": "Data",
            "width": 120,
        },
    ]
    return columns


def process_merged_items(raw_data):
    """
    Add practitioner information without altering the original claim item
    quantity or amount. When ref_docname contains multiple values, all
    matching practitioners are shown in a single cell.
    """
    processed_data = []

    for row in raw_data:
        ref_docname_list = [
            name.strip()
            for name in str(row.get("ref_docname") or "").split(",")
            if name.strip()
        ]
        ref_doctype = row.get("service_type")
        coverage_plan_name = row.get("coverage_plan_name") or ""
        item_code = row.get("item_code") or ""
        practitioners_map = get_practitioners_batch(
            ref_docname_list, ref_doctype, coverage_plan_name, item_code
        )

        practitioners = []
        for ref_docname in ref_docname_list:
            for practitioner in practitioners_map.get(ref_docname, []):
                if practitioner and practitioner not in practitioners:
                    practitioners.append(practitioner)

        row["practitioner"] = ", ".join(practitioners) if practitioners else None
        row.pop("ref_docname", None)
        row.pop("item_code", None)
        row.pop("coverage_plan_name", None)
        processed_data.append(row)

    return processed_data


def get_practitioners_batch(ref_docname_list, ref_doctype, coverage_plan_name, item_code):
    """
    Fetch practitioners for multiple ref_docnames without altering claim values.
    Returns a dict keyed by ref_docname with a list of practitioner names.
    """
    if not ref_docname_list:
        return {}

    hsr = DocType("Healthcare Service Request")
    hsrp = DocType("Healthcare Service Request Payment")

    results = (
        frappe.qb.from_(hsrp)
        .inner_join(hsr)
        .on(hsrp.parent == hsr.name)
        .select(
            hsrp.ref_docname,
            hsr.practitioner,
        )
        .where(
            (hsrp.ref_docname.isin(ref_docname_list))
            & (hsrp.ref_doctype == ref_doctype)
            & (hsrp.payor_plan == coverage_plan_name)
            & (hsrp.item_code == item_code)
        )
        .run(as_dict=True)
    )

    details_map = {}
    for r in results:
        if not r.get("practitioner"):
            continue
        practitioners = details_map.setdefault(r.ref_docname, [])
        if r.practitioner not in practitioners:
            practitioners.append(r.practitioner)

    # For Patient Appointment, batch fetch practitioners from the appointments
    if ref_doctype == "Patient Appointment":
        pa = DocType("Patient Appointment")
        pa_results = (
            frappe.qb.from_(pa)
            .select(pa.name, pa.practitioner)
            .where(pa.name.isin(ref_docname_list))
            .run(as_dict=True)
        )
        pa_map = {r.name: r.practitioner for r in pa_results}
        for name in ref_docname_list:
            practitioner = pa_map.get(name)
            if not practitioner:
                continue
            practitioners = details_map.setdefault(name, [])
            if practitioner not in practitioners:
                practitioners.append(practitioner)

    # Fill defaults for any ref_docnames not found
    for name in ref_docname_list:
        if name not in details_map:
            details_map[name] = []

    return details_map


def get_data(filters):
    npc = DocType("NHIF Patient Claim")
    npci = DocType("NHIF Patient Claim Item")

    data_query = (
        frappe.qb.from_(npc)
        .inner_join(npci)
        .on(npc.name == npci.parent)
        .select(
            npc.name.as_("nhif_patient_claim"),
            npc.patient.as_("patient"),
            npc.patient_name.as_("patient_name"),
            npc.patient_appointment.as_("patient_appointment"),
            npci.ref_doctype.as_("service_type"),
            npci.item_name.as_("service_name"),
            npc.gender.as_("gender"),
            npci.item_quantity.as_("qty"),
            npci.unit_price.as_("unit_price"),
            npci.amount_claimed.as_("amount_claimed"),
            npc.attendance_date.as_("appointment_date"),
            npc.date_admitted.as_("admitted_date"),
            npc.date_discharge.as_("discharge_date"),
            npc.folio_no.as_("folio_no"),
            npci.ref_docname.as_("ref_docname"),
            npci.item_code.as_("item_code"),
            npc.coverage_plan_name.as_("coverage_plan_name"),
        )
        .where(
            (npc.company == filters.get("company"))
            & (npc.claim_month == filters.get("claim_month"))
            & (npc.claim_year == filters.get("claim_year"))
        )
    )

    if filters.get("drafts_unclaimable") == 1:
        data_query = data_query.where(npc.docstatus == 0)
    else:
        data_query = data_query.where(npc.docstatus == 1)

    raw_data = data_query.run(as_dict=True)

    # Process data to handle merged items and add practitioner information
    processed_data = process_merged_items(raw_data)

    return processed_data


# SELECT
#     npc.name AS "NHIF Patient Claim:Link/NHIF Patient Claim:",
#     npc.patient AS "Patient:Link/Patient:150",
#     npc.patient_name AS "Patient Name:Data:",
#     npc.patient_appointment AS "Patient Appointment:Link/Patient Appointment:150",
#     npci.ref_doctype AS "Service Type:Data:",
#     npci.item_name,
#     npc.gender AS "Gender::",
#     npc.attendance_date AS "Appointment Date:Date:",
#     npc.date_discharge AS "Discharge Date:Date:",
#    SUM(npci.amount_claimed) AS "Amount Claimed:Currency:",
#    SUM(npci.item_quantity) AS "Total Quantity:Int:",
#    npc.folio_no AS "Folio No::"
# FROM `tabNHIF Patient Claim` npc
# INNER JOIN `tabNHIF Patient Claim Item` npci ON npc.name = npci.parent
# WHERE npc.docstatus = 1
#   AND npc.claim_month = %(claim_month)s
#   AND npc.claim_year = %(claim_year)s
#   AND npc.company = %(company)s
# GROUP BY npc.patient, npc.patient_appointment, npci.ref_doctype,
# npci.item_name, npc.gender,npc.attendance_date, npc.date_discharge


# "filters": [
#     {
#         "fieldname": "claim_month",
#         "fieldtype": "Int",
#         "label": "Claim Month",
#         "mandatory": 1,
#         "wildcard_filter": 0
#     },
#     {
#         "fieldname": "claim_year",
#         "fieldtype": "Int",
#         "label": "Claim Year",
#         "mandatory": 1,
#         "wildcard_filter": 0
#     },
#     {
#         "fieldname": "company",
#         "fieldtype": "Link",
#         "label": "Company",
#         "mandatory": 1,
#         "options": "Company",
#         "wildcard_filter": 0
#     }
# ],
# "query": "SELECT\n    npc.name AS \"NHIF Patient Claim:Link/NHIF Patient Claim:\",\n    npc.patient AS \"Patient:Link/Patient:150\",\n    npc.patient_name AS \"Patient Name:Data:\",\n    npc.patient_appointment AS \"Patient Appointment:Link/Patient Appointment:150\",\n    npci.ref_doctype AS \"Service Type:Data:\",\n    npci.item_name,\n    npc.gender AS \"Gender::\",\n    npc.attendance_date AS \"Appointment Date:Date:\",\n    npc.date_discharge AS \"Discharge Date:Date:\",\n   SUM(npci.amount_claimed) AS \"Amount Claimed:Currency:\",\n   SUM(npci.item_quantity) AS \"Total Quantity:Int:\",\n   npc.folio_no AS \"Folio No::\"\nFROM `tabNHIF Patient Claim` npc\nINNER JOIN `tabNHIF Patient Claim Item` npci ON npc.name = npci.parent\nWHERE npc.docstatus = 1\n  AND npc.claim_month = %(claim_month)s\n  AND npc.claim_year = %(claim_year)s\n  AND npc.company = %(company)s\nGROUP BY npc.patient, npc.patient_appointment, npci.ref_doctype, npci.item_name, npc.gender,npc.attendance_date, npc.date_discharge",
