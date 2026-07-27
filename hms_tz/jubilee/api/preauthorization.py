# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt
"""Jubilee pre-authorization driven by Healthcare Service Request.

The payload builder is shared with Jubilee Approval Request: each source is
normalized by an adapter, then one builder turns the normalized source into the
Jubilee `entities` dict.
"""

import json

import frappe
import requests
from frappe import _
from frappe.query_builder import DocType
from frappe.utils import date_diff, flt, get_fullname, get_link_to_form, getdate, nowdate

from hms_tz.jubilee.doctype.jubilee_response_log.jubilee_response_log import add_jubilee_log

ct = DocType("Codification Table")
pe = DocType("Patient Encounter")


def get_normalized_disease_code(code):
    """Convert a CDC ICD code to the NHIF/Jubilee dotted form."""
    if not code:
        return ""

    if len(code) > 3 and "." not in code:
        return code[:3] + "." + (code[3:4] or "0")

    if len(code) <= 5 and "." in code:
        return code

    return code[:3]


def get_encounter_diseases(encounter_names):
    """Diagnosis rows for the given encounters, shaped for insurer payloads."""
    if not encounter_names:
        return []

    diagnosis_list = (
        frappe.qb.from_(ct)
        .join(pe)
        .on(ct.parent == pe.name)
        .select(
            ct.code_value,
            ct.code_value.as_("medical_code"),
            ct.code.as_("code"),
            ct.definition,
            ct.modified,
            ct.parentfield,
            pe.practitioner,
        )
        .where((ct.parenttype == "Patient Encounter") & (ct.parent.isin(encounter_names)))
        .groupby(ct.code_value, ct.parentfield)
        .orderby(ct.parentfield, order=frappe.qb.desc)
    ).run(as_dict=True)

    diseases = []
    for row in diagnosis_list:
        status = ""
        if row.parentfield == "patient_encounter_preliminary_diagnosis":
            status = "Provisional"
        elif row.parentfield == "patient_encounter_final_diagnosis":
            status = "Final"

        diseases.append(
            frappe._dict({
                "medical_code": row.code_value,
                "status": status,
                "disease_code": get_normalized_disease_code(row.code),
                "description": (row.definition or "")[:139],
                "created_by": row.practitioner,
                "date_created": row.modified,
            })
        )

    return diseases


def get_practitioner_qualification_id(practitioner):
    """NHIF Physician Qualification ID for the practitioner."""
    qualification = frappe.get_cached_value(
        "Healthcare Practitioner", practitioner, "nhif_physician_qualification"
    )
    if not qualification:
        frappe.throw(
            _(
                f"Practitioner {practitioner} has no Physician Qualification, "
                "Set it on Healthcare Practitioner master."
            )
        )

    qualification_id = frappe.get_cached_value(
        "NHIF Physician Qualification", qualification, "physicianqualificationid"
    )

    return qualification_id or ""


def get_preauth_entities(source):
    """Build the Jubilee SendPreauthorization entities dict from a normalized source.

    Child rows arrive as `folio_items` and `folio_diseases`; `items` would
    shadow `dict.items` on the frappe._dict source.
    """
    entities = frappe._dict()

    entities.ClaimYear = source.claim_year
    entities.ClaimMonth = source.claim_month
    entities.CardNo = (source.card_no or "").strip()
    entities.FirstName = source.first_name or ""
    entities.LastName = source.last_name or ""
    entities.Gender = source.gender or ""
    entities.DateOfBirth = str(source.date_of_birth) if source.date_of_birth else ""
    entities.Age = (
        str(date_diff(nowdate(), source.date_of_birth) // 365) if source.date_of_birth else "0"
    )
    entities.TelephoneNo = source.telephone_no or ""
    entities.PatientFileNo = source.patient or ""
    entities.AuthorizationNo = source.authorization_no or ""
    entities.AttendanceDate = str(source.attendance_date) if source.attendance_date else ""
    entities.PatientTypeCode = source.patient_type_code or "OP"
    entities.DateAdmitted = str(source.admitted_date) if source.admitted_date else ""
    entities.DateDischarged = str(source.discharge_date) if source.discharge_date else ""
    entities.PractitionerNo = source.practitioner_no or ""
    entities.ProviderID = source.provider_id or ""
    entities.CreatedBy = get_fullname(frappe.session.user)
    entities.DateCreated = str(source.posting_date) if source.posting_date else str(nowdate())
    entities.LastModifiedBy = get_fullname(frappe.session.user)
    entities.LastModified = str(nowdate())
    entities.AmountClaimed = source.total_amount or 0
    entities.jubileeProcedure = source.jubilee_procedure
    entities.jubileeBenefits = source.benefit_code or ""
    entities.BillNo = source.bill_no

    if source.practitioner:
        entities.QualificationID = get_practitioner_qualification_id(source.practitioner)

    entities.FolioDiseases = [
        {
            "DiseaseCode": disease.disease_code or "",
            "Status": disease.status or "Provisional",
            "Remarks": disease.description or "",
            "CreatedBy": disease.created_by or get_fullname(frappe.session.user),
            "DateCreated": str(disease.date_created) if disease.date_created else str(nowdate()),
            "LastModifiedBy": get_fullname(frappe.session.user),
            "LastModified": str(nowdate()),
        }
        for disease in source.folio_diseases
    ]

    entities.FolioItems = [
        {
            "ItemCode": item.item_code or "",
            "OtherDetails": item.item_name or "",
            "ItemQuantity": item.item_quantity or 1,
            "UnitPrice": item.unit_price or 0,
            "AmountClaimed": item.amount_claimed or 0,
            "CreatedBy": item.created_by or get_fullname(frappe.session.user),
            "DateCreated": str(item.date_created) if item.date_created else str(nowdate()),
            "LastModifiedBy": get_fullname(frappe.session.user),
            "LastModified": str(nowdate()),
        }
        for item in source.folio_items
    ]

    return entities


def get_source_from_approval_request(jar_doc):
    """Normalize a Jubilee Approval Request into pre-auth source fields."""
    source = frappe._dict(jar_doc.as_dict())

    source.folio_diseases = [frappe._dict(row.as_dict()) for row in jar_doc.diseases]
    source.folio_items = [
        frappe._dict({
            "item_code": row.item_code,
            "item_name": row.item_name,
            "item_quantity": row.item_quantity,
            "unit_price": row.unit_price,
            "amount_claimed": row.amount_claimed,
            "created_by": row.created_by,
            "date_created": row.date_created,
        })
        for row in jar_doc.items
    ]

    return source


def get_source_encounters(hsr_doc):
    """Encounter names backing this Service Request."""
    if hsr_doc.source_doctype == "Patient Encounter":
        return [hsr_doc.source_docname]

    return []


def get_service_request_items(hsr_doc):
    """FolioItems source rows from the Jubilee payment rows of the HSR.

    A co-paid service can be split across several insurers, so the insurer is
    matched per row: only Jubilee's share is claimed from Jubilee.
    """
    items = []
    created_by = get_fullname(frappe.session.user)

    for row in hsr_doc.payments:
        if row.payment_type != "Insurance" or row.is_cancelled:
            continue

        if "Jubilee" not in (row.insurance_company or ""):
            continue

        if not row.item_code:
            frappe.throw(
                _(
                    f"Insurance item code is missing for <b>{row.service_name}</b> "
                    f"in payment row {row.idx}.<br>"
                    "Please set the Item Customer Detail ref code for this item."
                )
            )

        items.append(
            frappe._dict({
                "item_code": row.item_code,
                "item_name": row.service_name,
                "item_quantity": row.qty or 1,
                "unit_price": row.rate or 0,
                "amount_claimed": row.amount or 0,
                "created_by": created_by,
                "date_created": nowdate(),
            })
        )

    return items


def get_source_from_service_request(hsr_doc):
    """Normalize a Healthcare Service Request into pre-auth source fields.

    Patient demographics come from Patient and Patient Appointment; items come
    from the Jubilee payment rows, whose item_code already holds the insurer
    ref code. The claimed total is summed from those same rows, so it can never
    drift from what is actually sent.
    """
    appointment_doc = frappe.get_cached_doc("Patient Appointment", hsr_doc.appointment)
    patient_doc = frappe.get_cached_doc("Patient", hsr_doc.patient)
    posting = getdate(hsr_doc.posting_datetime)

    folio_items = get_service_request_items(hsr_doc)

    return frappe._dict({
        "claim_year": posting.year,
        "claim_month": posting.month,
        "card_no": hsr_doc.card_no or appointment_doc.coverage_plan_card_number or "",
        "first_name": patient_doc.first_name,
        "last_name": patient_doc.last_name or "",
        "gender": patient_doc.sex,
        "date_of_birth": patient_doc.dob,
        "telephone_no": patient_doc.mobile or "",
        "patient": hsr_doc.patient,
        "authorization_no": appointment_doc.authorization_number or "",
        "attendance_date": (
            f"{appointment_doc.appointment_date} {appointment_doc.appointment_time or '00:00:00'}"
        ),
        "patient_type_code": "OP",
        "admitted_date": None,
        "discharge_date": None,
        "practitioner": hsr_doc.practitioner,
        "practitioner_no": frappe.get_cached_value(
            "Healthcare Practitioner", hsr_doc.practitioner, "tz_mct_code"
        )
        or "",
        "provider_id": frappe.get_cached_value(
            "HMS TZ Setting", hsr_doc.company, "jubilee_provider_id"
        )
        or "",
        "posting_date": posting,
        "total_amount": sum(d.amount_claimed or 0 for d in folio_items),
        "jubilee_procedure": hsr_doc.jubilee_procedure or "",
        "benefit_code": hsr_doc.benefit_code or "",
        "bill_no": "".join(hsr_doc.name.split("-")[1:]),
        "folio_diseases": get_encounter_diseases(get_source_encounters(hsr_doc)),
        "folio_items": folio_items,
    })


def get_jubilee_setting(company):
    """HMS TZ Setting for the company, with the Jubilee API enabled."""
    setting_doc = frappe.get_cached_doc("HMS TZ Setting", company)
    if not setting_doc.enable_jubilee_api:
        frappe.throw(_("Jubilee API is not enabled for this company"))

    return setting_doc


def get_preauth_endpoint(setting_doc, submission_id=None):
    """Request type, url and headers for Send vs Update Preauthorization."""
    request_type = "UpdatePreauthorization" if submission_id else "SendPreauthorization"
    url = f"{setting_doc.jubilee_url}/jubileeapi/{request_type}"
    headers = {
        "Authorization": f"Bearer {setting_doc.get_jubilee_token()}",
        "Content-Type": "application/json",
    }

    return request_type, url, headers


def log_preauth(hsr_doc, request_type, url, headers, payload, response_data, status_code):
    """Record a Jubilee pre-auth exchange against the Service Request."""
    add_jubilee_log(
        request_type=request_type,
        request_url=url,
        request_header=headers,
        request_body=payload,
        response_data=response_data,
        status_code=status_code,
        company=hsr_doc.company,
        ref_doctype="Healthcare Service Request",
        ref_docname=hsr_doc.name,
        card_no=hsr_doc.card_no,
    )


def add_service_request_comment(hsr_doc, title, result):
    """Comment a Jubilee exchange on the Service Request, for the billing team."""
    lines = [f"{title}<br>Status: <b>{result.get('status') or 'ERROR'}</b>"]

    if result.get("submission_id"):
        lines.append(f"Submission ID: <b>{result['submission_id']}</b>")

    if result.get("description"):
        lines.append(f"Response: <b>{result['description']}</b>")

    hsr_doc.add_comment(comment_type="Comment", text="<br>".join(lines))


def send_service_request_preauthorization(service_request_name):
    """Send SendPreauthorization for a Healthcare Service Request and persist the result."""

    hsr_doc = frappe.get_doc("Healthcare Service Request", service_request_name)
    setting_doc = get_jubilee_setting(hsr_doc.company)

    entities = get_preauth_entities(get_source_from_service_request(hsr_doc))
    payload = json.dumps({"entities": [entities]})
    request_type, url, headers = get_preauth_endpoint(setting_doc, hsr_doc.submission_id)

    result = {"status": "ERROR", "submission_id": "", "description": ""}
    response = None

    try:
        response = requests.post(url, headers=headers, data=payload, timeout=120)
        data = json.loads(response.text) if response.text else {}
        log_preauth(hsr_doc, request_type, url, headers, payload, data, response.status_code)

        result.update({
            "status": data.get("Status") or data.get("status") or "",
            "description": data.get("Description") or data.get("description") or "",
            "submission_id": str(data.get("SubmissionID") or data.get("submissionId") or ""),
        })
    except Exception:
        error_text = response.text if response and response.text else "NO RESPONSE - Timeout?"
        log_preauth(
            hsr_doc,
            request_type,
            url,
            headers,
            payload,
            error_text,
            response.status_code if response else "NO STATUS CODE",
        )
        result["description"] = str(error_text)

    frappe.db.set_value(
        "Healthcare Service Request",
        hsr_doc.name,
        {
            "approval_status": result["status"] or "ERROR",
            "approval_description": str(result["description"])[:1000],
            "submission_id": result["submission_id"],
        },
        update_modified=False,
    )

    add_service_request_comment(hsr_doc, f"Jubilee {request_type} sent", result)

    return result


@frappe.whitelist()
def get_service_request_preauth_status(service_request_name):
    """Fetch and persist the pre-auth status for a Healthcare Service Request."""
    hsr_doc = frappe.get_doc("Healthcare Service Request", service_request_name)
    if not hsr_doc.submission_id:
        frappe.throw(
            _(
                "This Service Request has no Pre-Auth Submission ID. "
                "Please send the pre-authorization first."
            )
        )

    setting_doc = get_jubilee_setting(hsr_doc.company)
    url = f"{setting_doc.jubilee_url}/jubileeapi/getPreauthorizationStatus"
    headers = {
        "Authorization": f"Bearer {setting_doc.get_jubilee_token()}",
        "Content-Type": "application/json",
    }
    params = {"submissionID": hsr_doc.submission_id}

    result = {"status": "ERROR", "description": "", "service_request": hsr_doc.name}
    approval_status, approval_description, approved_amount = "", "", 0
    response = None

    try:
        response = requests.get(url, headers=headers, params=params, timeout=60)
        data = json.loads(response.text) if response.text else {}
        log_preauth(
            hsr_doc,
            "getPreauthorizationStatus",
            url,
            headers,
            str(params),
            data,
            response.status_code,
        )

        status = data.get("Status") or data.get("status") or "ERROR"
        description = data.get("Description") or data.get("description") or ""

        if isinstance(description, dict):
            approval_status = description.get("PreauthorizationStatus") or ""
            approval_description = str(description.get("details") or "")
            approved_amount = flt(description.get("approvedAmount") or 0)
        else:
            approval_status = status
            approval_description = str(description)

        result.update({"status": status, "description": approval_description or approval_status})
    except Exception:
        error_text = (
            response.text if response and response.text else "NO RESPONSE - Timeout or connection error"
        )
        log_preauth(
            hsr_doc,
            "getPreauthorizationStatus",
            url,
            headers,
            str(params),
            error_text,
            response.status_code if response else "NO STATUS CODE",
        )
        result["description"] = str(error_text)
        approval_status, approval_description = "ERROR", str(error_text)

    frappe.db.set_value(
        "Healthcare Service Request",
        hsr_doc.name,
        {
            "approval_status": approval_status,
            "approval_description": approval_description[:1000],
            "approved_amount": approved_amount,
        },
        update_modified=False,
    )

    add_service_request_comment(
        hsr_doc,
        "Jubilee approval status checked",
        {"status": approval_status, "description": approval_description},
    )

    return result


def get_benefit_record(appointment, benefit_code):
    """Jubilee Benefit record for the appointment and benefit code."""
    benefit = frappe.db.get_value(
        "Jubilee Benefit",
        {"appointment": appointment, "benefit_code": benefit_code},
        ["name", "benefit_name", "benefit_balance"],
        as_dict=True,
    )
    if not benefit:
        frappe.throw(
            _(
                f"No Jubilee Benefit found for benefit code <b>{benefit_code}</b> "
                f"on appointment <b>{appointment}</b>"
            )
        )

    return benefit


def validate_preauth_request(encounter_doc):
    """Guard the pre-auth request: Jubilee insurer, API enabled, not already sent."""
    if "Jubilee" not in (encounter_doc.insurance_company or ""):
        frappe.throw(_("Pre-authorization is only available for Jubilee insurance encounters"))

    get_jubilee_setting(encounter_doc.company)

    if not encounter_doc.jubilee_procedure:
        frappe.throw(_("Please select a Jubilee Procedure before requesting pre-authorization"))

    existing = frappe.db.get_value(
        "Healthcare Service Request",
        {"source_doctype": encounter_doc.doctype, "source_docname": encounter_doc.name},
        ["name", "submission_id"],
        as_dict=True,
    )
    if existing and existing.submission_id:
        link = get_link_to_form("Healthcare Service Request", existing.name)
        frappe.throw(
            _(
                f"Pre-authorization was already sent for this encounter: <b>{link}</b><br>"
                "Please use that Service Request to check the status or re-send."
            )
        )


def add_preauth_comment(encounter_doc, service_request_name, result):
    """Comment the pre-auth outcome on the encounter with a link to the HSR."""
    link = get_link_to_form("Healthcare Service Request", service_request_name)
    encounter_doc.add_comment(
        comment_type="Comment",
        text=(
            f"Jubilee Pre-Authorization request sent<br>"
            f"Service Request: <b>{link}</b><br>"
            f"Status: <b>{result.get('status') or 'ERROR'}</b><br>"
            f"Submission ID: <b>{result.get('submission_id') or 'N/A'}</b>"
        ),
    )


@frappe.whitelist()
def request_preauthorization(source_doctype, source_docname, benefit_code):
    """Submit the encounter, create a draft Service Request, and send the pre-auth.

    Called from the Patient Encounter pre-auth dialog. The encounter and the
    draft Service Request always survive an API failure so the billing team can
    retry the send from the Service Request.
    """
    if source_doctype != "Patient Encounter":
        frappe.throw(_("Pre-authorization can only be requested from a Patient Encounter"))

    if not benefit_code:
        frappe.throw(_("Jubilee Benefit is required to request pre-authorization"))

    encounter_doc = frappe.get_doc(source_doctype, source_docname)
    validate_preauth_request(encounter_doc)
    benefit = get_benefit_record(encounter_doc.appointment, benefit_code)

    frappe.flags.hsr_requires_approval = {
        "jubilee_benefit": benefit.name,
        "benefit_code": benefit_code,
    }
    try:
        if encounter_doc.docstatus == 0:
            encounter_doc.submit()

        service_request_name = frappe.db.get_value(
            "Healthcare Service Request",
            {"source_doctype": source_doctype, "source_docname": source_docname},
            "name",
        )

    finally:
        frappe.flags.hsr_requires_approval = None

    if not service_request_name:
        frappe.throw(
            _(
                "No Healthcare Service Request was created for this encounter. "
                "There may be no eligible insurance services to pre-authorize."
            )
        )

    # Persist the encounter submit and the draft Service Request before the
    # network call: a Jubilee timeout must not roll back work the patient is
    # already acting on.
    frappe.db.commit()

    result = send_service_request_preauthorization(service_request_name)
    add_preauth_comment(encounter_doc, service_request_name, result)
    result["service_request"] = service_request_name

    return result
