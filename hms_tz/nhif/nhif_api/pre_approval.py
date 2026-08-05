import json

import frappe
import requests
from frappe.core.utils import html2text
from frappe.utils import nowdate

from hms_tz.hms_tz.doctype.healthcare_service_request.healthcare_service_request import (
    get_childs_map,
    get_item_rate,
    get_item_refcode,
)
from hms_tz.nhif.doctype.nhif_response_log.nhif_response_log import add_log
from hms_tz.nhif.nhif_api.referral import get_disease_code


@frappe.whitelist()
def get_service_preapproval(
    ref_doctype,
    ref_docname,
    authorization_no=None,
    settings_doc=None,
):
    # source doc can be either Patient Encounter or Medication Change Request
    source_doc = frappe.get_doc(ref_doctype, ref_docname)

    insurance_company = source_doc.get("insurance_company") or ""
    if "NHIF" not in insurance_company:
        frappe.throw(
            f"Cannot request NHIF pre-approval: {ref_doctype} {ref_docname} "
            f"belongs to insurance company '{insurance_company}', not NHIF"
        )

    if not settings_doc:
        settings_doc = frappe.get_cached_doc("HMS TZ Setting", source_doc.company)

    services, service_map, diseases = get_services(source_doc)
    if len(services) == 0:
        frappe.msgprint("No service(s) to request an Pre-Approvals")
        return False

    first_name, last_name, dob, patient_sex = frappe.get_cached_value(
        "Patient", source_doc.patient, ["first_name", "last_name", "dob", "sex"]
    )

    practitioner = source_doc.get("practitioner") or source_doc.get("healthcare_practitioner")
    mct_code, mobile = frappe.get_cached_value(
        "Healthcare Practitioner",
        practitioner,
        ["tz_mct_code", "mobile_phone"],
    )
    if not authorization_no:
        authorization_no = frappe.get_cached_value(
            "Patient Appointment",
            source_doc.appointment,
            "authorization_number",
        )

    notes = ""
    if source_doc.doctype == "Patient Encounter":
        notes = source_doc.get("examination_detail")
    else:
        notes = frappe.get_cached_value(
            "Patient Encounter",
            source_doc.get("patient_encounter"),
            "examination_detail",
        )

    clinical_notes = html2text(notes).lstrip('\n')

    payload = {
        "authorizationNo": authorization_no,
        "firstName": first_name,
        "lastName": last_name,
        "gender": patient_sex,
        "dateOfBirth": str(dob),
        "patientFileNo": source_doc.patient,
        "clinicalNotes": clinical_notes,
        "practitionerNo": mct_code,
        "practitionersRemarks": "",
        "telephoneNo": mobile,
        "facilityCode": settings_doc.facility_code,
        "diseases": diseases,
        "requestedServices": services,
    }
    payload = json.dumps(payload)

    url = f"{settings_doc.nhifservice_url}/api/PreApprovals/RequestServices"

    token = settings_doc.get_nhif_token()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    r = requests.request("Post", url, data=payload, headers=headers, timeout=60)
    if r.status_code != 200:
        add_log(
            request_type="RequestServices",
            request_url=url,
            request_header=headers,
            request_body=payload,
            response_data=r.text,
            status_code=r.status_code,
            company=settings_doc.name,
            ref_doctype=ref_doctype,
            ref_docname=ref_docname,
        )

        source_doc.add_comment(
            comment_type="Comment",
            text=f"Pre-approval request Failed..!<br><br>Status Code: {r.status_code}<br>NHIF Response: <b>{r.text}<b>",
        )
        frappe.db.commit()

        frappe.throw(
            title="NHIF API Error",
            msg=f"Pre-approval failed<br><br>Status Code: {r.status_code}<br>NHIF Response: <b>{r.text}<b>"
        )
    else:
        data = json.loads(r.text)
        add_log(
            request_type="RequestServices",
            request_url=url,
            request_header=headers,
            request_body=payload,
            response_data=data,
            status_code=r.status_code,
            company=settings_doc.name,
            ref_doctype=ref_doctype,
            ref_docname=ref_docname,
        )

        rejected_count = 0
        msg = "Pre-Approval request were rejected for the following services:<hr>\
            <table class='table table-condensed table-bordered'><tr><th>Service Type</th><th>Service</th><th>Status</th><th>Reason</th></tr>"

        for child in get_childs_map():
            if not source_doc.get(child.get("table")):
                continue

            for row in source_doc.get(child.get("table")):
                ref_code = service_map.get((row.doctype, row.name, row.get(child.get("item"))))
                if not ref_code:
                    continue

                for d in data.get("services"):
                    if d.get("itemCode") == ref_code:
                        row.preapproval_status = d.get("status")
                        row.preapproval_no = data.get("requestNo") if d.get("status") != "REJECTED" else ""
                        row.rejection_reason_code = d.get("rejectionReasonCode")
                        row.rejection_details = d.get("rejectionDetails")
                        row.preapproval_cancel_remarks = ""
                        row.db_update()
                        row.reload()

                        if d.get("status") == "REJECTED":
                            rejected_count += 1
                            msg += f"<tr>\
                                <td>{row.doctype.split(' ')[0]}</td>\
                                <td>{row.get(child.get('item'))}</td>\
                                <td style='color: red'>{d.get('status')}</td>\
                                <td>{d.get('rejectionDetails')}</td>\
                            </tr>"

        source_doc.db_update()
        source_doc.db_update_all()
        source_doc.reload()

        source_doc.add_comment(
            comment_type="Comment",
            text=f"Pre-approval request sent successful!<br>RequestID: <b>{data.get('requestID')}</b><br>",
        )
        if rejected_count > 0:
            msg += "</table>"
            frappe.msgprint(msg, title="Pre-Approval Status", indicator="red")
        else:
            frappe.msgprint(
                "<b>Pre-Approval request were successful for all services</b>",
                title="Pre-Approval Status",
                indicator="green",
            )

        return True


@frappe.whitelist()
def cancel_preapproval(
    ref_doctype,
    ref_docname,
    preapproval_no,
    remarks,
    settings_doc=None,
):
    source_doc = frappe.get_cached_doc(ref_doctype, ref_docname)

    insurance_company = source_doc.get("insurance_company") or ""
    if "NHIF" not in insurance_company:
        frappe.throw(
            f"Cannot cancel NHIF pre-approval: {ref_doctype} {ref_docname} "
            f"belongs to insurance company '{insurance_company}', not NHIF"
        )

    services, service_map, diseases = get_services(source_doc, preapproval_no)
    if len(services) == 0:
        frappe.msgprint("No servuce(s) to cancel an Pre-Approvals")
        return False

    if not settings_doc:
        settings_doc = frappe.get_cached_doc("HMS TZ Setting", source_doc.company)

    url = f"{settings_doc.nhifservice_url}/api/PreApprovals/CancelRequest?requestNo={preapproval_no}&remarks={remarks}"

    token = settings_doc.get_nhif_token()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    r = requests.request("Post", url, headers=headers, timeout=60)
    if r.status_code != 200:
        add_log(
            request_type="CancelRequest",
            request_url=url,
            request_header=headers,
            request_body="",
            response_data=r.text,
            status_code=r.status_code,
            company=settings_doc.name,
            ref_doctype=ref_doctype,
            ref_docname=ref_docname,
        )

        source_doc.add_comment(
            comment_type="Comment",
            text=f"Cancel Pre-approval request Failed..!<br><br>Status Code: {r.status_code}<br>NHIF Response: <b>{r.text}<b>",
        )
        frappe.db.commit()

        frappe.msgprint(
            title="NHIF API Error",
            msg=f"Cancel Pre-approval failed<br><br>Status Code: {r.status_code}<br>NHIF Response: <b>{r.text}<b>",
            indicator="red",
        )
        return False

    else:
        data = json.loads(r.text)
        add_log(
            request_type="CancelRequest",
            request_url=url,
            request_header=headers,
            request_body="",
            response_data=data,
            status_code=r.status_code,
            company=settings_doc.name,
            ref_doctype=ref_doctype,
            ref_docname=ref_docname,
        )

        for child in get_childs_map():
            if not source_doc.get(child.get("table")):
                continue

            for row in source_doc.get(child.get("table")):
                if row.preapproval_no == preapproval_no:
                    row.preapproval_status = "Cancelled"
                    row.preapproval_no = ""
                    row.preapproval_cancel_remarks = remarks
                    row.db_update()
                    row.reload()

        source_doc.db_update()
        source_doc.db_update_all()
        source_doc.reload()

        request_ids = "<ul>"
        for row in data:
            request_ids += f"<li>{row.get('RequestedServiceID')} <br> {row.get('RequestID')}</li>"
        request_ids += "</ul>"

        source_doc.add_comment(
            comment_type="Comment",
            text=f"Pre-approval request canceled successfully!<br><br>Pre-Approval No: <b>{preapproval_no}</b><br><br>NHIF RequestID(s): {request_ids}",
        )

        return True


def get_services(doc, preapproval_no=None):
    diseases = []
    services = []
    service_map = {}

    for child in get_childs_map():
        if not doc.get(child.get("table")):
            continue

        for row in doc.get(child.get("table")):
            if not row.get(child.get("item")):
                continue

            if preapproval_no and row.preapproval_no == preapproval_no:
                services.append(row.get(child.get("item")))

                continue

            if (
                row.get("prescribe")
                or row.get("is_not_available_inhouse")
                or row.get("is_cancelled")
                # or row.get("is_restricted")
                or row.get("preapproval_status") == "Accepted"
            ):
                continue

            ref_code = get_item_refcode(
                child.get("doctype"),
                row.get(child.get("item")),
                doc.company,
                doc.insurance_company
            )
            item = frappe.get_cached_value(child.get("doctype"), row.get(child.get("item")), "item")
            item_rate = get_item_rate(
                item,
                doc.company,
                doc.insurance_subscription,
                doc.insurance_company
            )

            services.append(
                {
                    "itemCode": ref_code,
                    "usage": "",
                    "effectiveDate": str(nowdate()),
                    "endDate": str(nowdate()),
                    "quantityRequested": row.get("quantity") or 1,
                    "unitPrice": item_rate,
                    "remarks": "",
                }
            )

            service_map[row.get("doctype"), row.get("name"), row.get(child.get("item"))] = ref_code

            medical_code = row.get("medical_code") or ""
            disease_row = {"diseaseCode": get_disease_code(medical_code[6:])}
            if child.get("table") in [
                "lab_test_prescription",
                "radiology_procedure_prescription",
            ]:
                disease_row["status"] = "Preliminary"
            else:
                disease_row["status"] = "Final"

            diseases.append(disease_row)

    return services, service_map, diseases
