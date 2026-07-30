# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt
import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import DocType
from frappe.utils import flt, fmt_money, get_link_to_form

from hms_tz.nhif.api.healthcare_utils import *

UNRESOLVED_PREAUTH_STATUSES = ("", "ERROR", "PENDING")


class HealthcareServiceRequest(Document):
    def before_insert(self):
        self.get_percent_covered()

    def before_save(self):
        self.set_request_id()
        self.set_service_price_rate()

    def validate(self):
        self.validate_duplicate()

    def before_submit(self):
        self.validate_approval_status()
        self.validate_approved_amount()
        self.validate_service_percentage()

    def on_submit(self):
        if self.source_doctype == "Patient Encounter":
            self.create_healthcare_service_docs()

    def validate_duplicate(self):
        if not self.source_doctype and not self.source_docname:
            return

        hsr = DocType("Healthcare Service Request")
        hsr_dupl = (
            frappe.qb.from_(hsr)
            .select(hsr.name)
            .where(
                (hsr.name != self.name)
                & (hsr.source_doctype == self.source_doctype)
                & (hsr.source_docname == self.source_docname)
            )
        ).run(as_dict=True)

        if len(hsr_dupl) > 0:
            url = get_link_to_form(self.doctype, hsr_dupl[0].name)
            frappe.throw(
                f"Another Healthcare Service Request with the same Source Docname: <b>{self.source_docname}</b> already exists: <a href='{url}'><b>{hsr_dupl[0].name}</b></a>"
            )

    def set_request_id(self):
        for row in self.services:
            for d in self.payments:
                if row.service_name == d.service_name and row.name != d.request_id:
                    d.request_id = row.name
                    if not d.ref_docname:
                        d.ref_docname = row.ref_docname
                    if not d.ref_doctype:
                        d.ref_doctype = row.ref_doctype
                    if not d.department_hsu:
                        d.department_hsu = row.department_hsu

    @frappe.whitelist()
    def get_services(self):
        return set([d.service_name for d in self.services])

    def set_service_price_rate(self):
        for row in self.payments:
            if not row.service_name:
                continue

            if not row.price_list:
                frappe.throw(f"Please select price list on payment table, row: {row.idx}")

            item_rate_details = self.get_service_rate(row)

            row.rate = item_rate_details.get("item_rate")
            row.discount_applied = 1 if item_rate_details.get("discount_percent") > 0 else 0
            row.amount = ((row.percent_covered / 100) * row.rate) * row.qty

    @frappe.whitelist()
    def get_service_rate(self, row_obj):
        if isinstance(row_obj, str):
            row_obj = json.loads(row_obj)
        elif isinstance(row_obj, dict):
            row_obj = json.loads(json.dumps(row_obj))
        elif isinstance(row_obj, object):
            row_obj = row_obj.as_dict()

        row = frappe._dict(row_obj)

        if not row.service_type:
            row.service_type = self.get_service_type(row.service_name, row.request_id)

        item = frappe.get_cached_value(row.service_type, row.service_name, "item")
        if not item:
            frappe.throw(
                f"Item code for {row.service_type}: {row.service_name} was not found.<br>Please set the item code to proceed..."
            )

        item_rate = 0
        discount_percent = 0

        if row.payment_type == "Cash" and row.price_list:
            item_rate = get_item_price(item, row.price_list, self.company)

        elif row.payment_type == "Insurance":
            if not row.insurance_subscription:
                frappe.throw("Insurance Subscription is required to get the item rate")

            item_price_rate, price_list = get_item_rate(
                item,
                self.company,
                row.insurance_subscription,
                row.insurance_company,
                for_service_request=True,
            )

            row.price_list = price_list

            # apply discount if it is available on Heathcare Insurance Company
            if row.insurance_company and "NHIF" not in row.insurance_company:
                discount_percent = get_discount_percent(row.insurance_company)

            item_rate = item_price_rate - (item_price_rate * (discount_percent / 100))

        return {"item_rate": item_rate, "discount_percent": discount_percent}

    @frappe.whitelist()
    def get_coverage_plan(self, insurance_subscription):
        plan = frappe.get_cached_value(
            "Healthcare Insurance Subscription",
            insurance_subscription,
            "healthcare_insurance_coverage_plan",
        )
        if not plan:
            frappe.throw(f"Insurance Coverage Plan is not set for Insurance Subscription: {insurance_subscription}")

        return plan

    @frappe.whitelist()
    def get_percent_covered(self, item_obj=None):
        def get_percent(item, years_of_insurance):
            scheme_id = frappe.get_cached_value(
                "Healthcare Insurance Coverage Plan",
                item.payor_plan,
                "nhif_scheme_id",
            )

            percent_details = frappe.get_cached_value(
                "NHIF Co-Payment Item",
                {
                    "itemcode": item.item_code,
                    "schemeid": scheme_id,
                    "yearno": years_of_insurance,
                },
                ["percentcovered", "name"], as_dict=True
            )

            return percent_details

        if item_obj:
            if isinstance(item_obj, str):
                item_obj = json.loads(item_obj)
            elif isinstance(item_obj, dict):
                item_obj = json.loads(json.dumps(item_obj))
            elif isinstance(item_obj, object):
                item_obj = item_obj.as_dict()

            item = frappe._dict(item_obj)

            if item.has_copayment == 0:
                return 100

            if not item.service_name:
                return 100

            if "NHIF" not in item.insurance_company:
                return 100

            percent_details = get_percent(item, self.years_of_insurance)
            if not percent_details:
                return 100

            return percent_details.percentcovered or 0

        else:
            has_copayment = False
            for item in self.payments:
                if not item.service_name:
                    item.percent_covered = 100
                    continue

                if item.insurance_company and "NHIF" not in item.insurance_company:
                    item.percent_covered = 100
                    continue

                if item.has_copayment == 0:
                    item.percent_covered = 100
                    continue

                percent_details = get_percent(item, self.years_of_insurance)
                if not percent_details:
                    item.percent_covered = 100
                    continue

                item.percent_covered = percent_details.percentcovered or 0

                if item.percent_covered < 100 and not has_copayment:
                    has_copayment = True

            self.has_copayment = 1 if has_copayment else 0

    def get_service_type(self, service_name, request_id=None):
        service_type = ""
        if request_id:
            service_type = frappe.get_cached_value("Healthcare Service Request Item", request_id, "service_type")

        else:
            for d in self.services:
                if service_name == d.service_name:
                    service_type = d.service_type
                    break

        return service_type

    def validate_service_percentage(self):
        service_payment_map = self.get_service_payment_map()

        for key, value in service_payment_map.items():
            percent_covered = 0
            service_type, service_name, ref_docname = key

            for d in value:
                if d.percent_covered:
                    percent_covered += d.percent_covered

            if percent_covered < 100:
                frappe.throw(
                    _(f"Total percent covered for {service_type} - {service_name} is less than 100%. Please check the payment table."))

    def get_service_payment_map(self):
        service_payment_map = {}
        for d in self.payments:
            service_payment_map.setdefault((d.service_type, d.service_name, d.ref_docname), []).append(d)

        return service_payment_map

    def validate_approval_status(self):
        """Block submission while an insurer Approval is still unresolved.

        A rejected Approval does not block: the billing team moves the
        rejected services to cash payment rows and submits.
        """
        if not self.requires_approval:
            return

        if not self.submission_id:
            frappe.throw(
                _(
                    f"Approval has not been sent to {self.insurance_company} for this Service Request."
                    "<br>Please send it before submitting."
                )
            )

        if (self.approval_status or "").upper() in UNRESOLVED_PREAUTH_STATUSES:
            frappe.throw(
                _(
                    f"Pre-authorization status from {self.insurance_company} is "
                    f"<b>{self.approval_status or 'not yet received'}</b>.<br>"
                    "Please click <b>Get Pre-Auth Status</b> and wait for a resolved "
                    "response before submitting."
                )
            )

    def validate_approved_amount(self):
        """Block submission when the Jubilee insurance rows, across every Service
        Request on this appointment, exceed the approved amount."""

        if not self.requires_approval:
            return

        from hms_tz.jubilee.api.preauthorization import get_jubilee_payment_rows

        total_amount = sum(flt(row.amount) for row in get_jubilee_payment_rows(self.appointment))

        if total_amount > flt(self.approved_amount):
            frappe.throw(
                _(
                    f"Total amount of Jubilee services <b>{fmt_money(total_amount)}</b> exceeds "
                    f"the approved amount <b>{fmt_money(self.approved_amount)}</b>.<br>"
                    "Please move the extra services to cash payment or cancel them before submitting."
                )
            )

    @frappe.whitelist()
    def send_approval_request(self):
        """Send this Approval Request to the insurer."""
        from hms_tz.jubilee.api.preauthorization import send_service_request_preauthorization

        result = send_service_request_preauthorization(self.name)
        self.reload()

        return result

    @frappe.whitelist()
    def get_approval_status(self):
        """Fetch this Service Request's pre-authorization status from the insurer."""
        from hms_tz.jubilee.api.preauthorization import get_service_request_preauth_status

        result = get_service_request_preauth_status(self.name)
        self.reload()

        return result

    def create_healthcare_service_docs(self):
        """
        Create healthcare service documents based on the Healthcare Service Request
        For medications, automatically create delivery notes
        """
        medications = []
        therapies = []
        therapy_map = {}

        encounter_doc = None
        if self.source_doctype == "Patient Encounter":
            encounter_doc = frappe.get_cached_doc(self.source_doctype, self.source_docname)

        service_payment_map = self.get_service_payment_map()

        for key, values in service_payment_map.items():
            service_type, service_name, ref_docname = key

            is_cancelled = False
            lrpmt_doc_created = False
            has_pending_cash_payment = False

            for d in values:
                if d.is_cancelled == 1:
                    is_cancelled = True

                if d.lrpmt_doc_created == 1:
                    lrpmt_doc_created = True

                if d.payment_type == "Cash" and d.invoiced == 0:
                    has_pending_cash_payment = True

                    # Early exit if all flags are True (no need to check
                    # further)
                if is_cancelled and lrpmt_doc_created and has_pending_cash_payment:
                    break

            if is_cancelled:
                continue

            if lrpmt_doc_created:
                continue

            if has_pending_cash_payment:
                continue

            if service_type == "Lab Test Template":
                lab_service = self.get_sorted_service(values)
                if not lab_service:
                    continue
                encounter_child = frappe.get_cached_doc(lab_service.ref_doctype, lab_service.ref_docname)
                create_individual_lab_test(encounter_doc, encounter_child, lab_service)

            elif service_type == "Radiology Examination Template":
                radiology_service = self.get_sorted_service(values)
                if not radiology_service:
                    continue
                encounter_child = frappe.get_cached_doc(
                    radiology_service.ref_doctype,
                    radiology_service.ref_docname,
                )
                create_individual_radiology_examination(encounter_doc, encounter_child, radiology_service)

            elif service_type == "Clinical Procedure Template":
                procedure_service = self.get_sorted_service(values)
                if not procedure_service:
                    continue
                encounter_child = frappe.get_cached_doc(
                    procedure_service.ref_doctype,
                    procedure_service.ref_docname,
                )
                create_individual_procedure_prescription(encounter_doc, encounter_child, procedure_service)

            elif service_type == "Medication":
                medication_service = self.get_sorted_service(values)
                if not medication_service:
                    continue
                medications.append(medication_service)

            elif service_type == "Therapy Type":
                therapy_service = self.get_sorted_service(values)
                if not therapy_service:
                    continue

                therapy_map[therapy_service.ref_docname] = therapy_service

                therapy = frappe.get_cached_doc(therapy_service.ref_doctype, therapy_service.ref_docname)
                therapies.append(therapy)

        # Create delivery notes for medications
        if len(medications) > 0:
            create_delivery_notes_from_hsr(encounter_doc, medications)

        # Create therapy plan for therapies
        if len(therapies) > 0 and therapy_map:
            create_plan(
                patient_encounter_docs=[encounter_doc],
                therapies=therapies,
                therapy_map=therapy_map,
            )

    def get_sorted_service(self, services):
        """
        Sort the services by insurance company
        This is important for NHIF, as we need to create a service document for the first service and not for all of them
        """

        def sort_key(service):
            insurance_company = service.insurance_company or ""
            # NHIF comes first (value 0), other insurance companies next (value
            # 1), cash last (value 2)
            if "NHIF" in insurance_company.upper():
                return (0, insurance_company)
            elif insurance_company:  # Other insurance companies
                return (1, insurance_company)
            else:  # Cash payment (empty or None insurance_company)
                return (2, insurance_company)

        service = None
        if len(services) == 1:
            service = services[0]

        elif len(services) > 1:
            # remove items with amount 0
            filtered_services = [d for d in services if d.amount > 0]
            if len(filtered_services) == 0:
                return frappe._dict()
            # sort the services by insurance company
            services = sorted(filtered_services, key=sort_key)
            service = services[0]

        return service


@frappe.whitelist()
def create_service_request(doc_obj=None, data=None):
    doc = None
    services = []

    if not doc_obj and not data:
        frappe.throw("Please provide a valid document object or data")

    if data:
        data = json.loads(data)
        doc = frappe.get_doc(data.get("source_doctype"), data.get("source_docname"))
    else:
        doc = doc_obj

    if doc.doctype == "Patient Encounter":
        services += get_encounter_services(doc)

    if len(services) == 0:
        return

    hsr = frappe.new_doc("Healthcare Service Request")
    hsr.patient = doc.patient
    hsr.appointment = doc.appointment
    hsr.company = doc.company
    hsr.practitioner = doc.practitioner
    hsr.source_doctype = doc.doctype
    hsr.source_docname = doc.name
    payment_type = "Cash" if not doc.insurance_subscription else "Insurance"
    hsr.payment_type = payment_type

    if doc.insurance_subscription:
        hsr.insurance_subscription = doc.insurance_subscription
        hsr.insurance_company = doc.insurance_company

    authorization_number, years_of_insurance = frappe.get_cached_value(
        "Patient Appointment",
        doc.appointment,
        ["authorization_number", "years_of_insurance"],
    )
    for d in services:
        hsr.append("services", d)

        ref_code = get_item_refcode(
            d.get("service_type"),
            d.get("service_name"),
            doc.company,
            doc.insurance_company
        )
        new_row = {
            "item_code": ref_code,
            "rate": d.get("rate"),
            "payment_type": payment_type,
            "price_list": d.get("price_list"),
            "insurance_subscription": doc.insurance_subscription,
            "insurance_company": doc.insurance_company,
            "payor_plan": doc.insurance_coverage_plan,
            "authorization_number": authorization_number,
            "years_of_insurance": years_of_insurance,
        }

        new_row.update(d.copy())
        hsr.append("payments", new_row)

    hsr.insert(ignore_permissions=True)
    hsr.reload()

    hsr.run_method("before_save")
    hsr.db_update_all()
    hsr.reload()

    if set_approval_state(hsr, doc.get("jubilee_procedure")):
        return hsr.name

    if hsr.has_copayment == 1:
        frappe.msgprint(
            _(
                "<h4 style='background-color:LightCoral; text-align:center;'>Copayment Items detected</h4><br>Please Inform patient to pass through Billing Team.</h4>"
            ),
            alert=True,
        )
        frappe.msgprint(
            title=_("<b>Copayment Notice</b>"),
            msg=_("<h4 style='background-color:LightCoral; text-align:center;'>Copayment Items detected</h4><br>Please Inform patient to pass through Billing Team.</h4>")
        )

    else:
        hsr.submit()

    return hsr.name


def set_approval_state(hsr, jubilee_procedure):
    """Stamp pre-auth request fields from the active flag.

    Returns True when a pre-authorization is pending, in which case the request
    must stay in draft until the insurer responds and the billing team agrees
    the payment split with the patient.
    """
    approval = frappe.flags.get("hsr_requires_approval") or {}
    if not approval:
        return False

    hsr.requires_approval = 1
    hsr.jubilee_benefit = approval.get("jubilee_benefit")
    hsr.benefit_code = approval.get("benefit_code")
    hsr.benefit_name = frappe.db.get_value(
        "Jubilee Benefit", approval.get("jubilee_benefit"), "benefit_name"
    )
    hsr.jubilee_procedure = jubilee_procedure
    hsr.db_update()

    return True


def get_encounter_services(doc):
    services = []

    childs_map = get_childs_map()
    for child in childs_map:
        if len(doc.get(child["table"])) == 0:
            continue

        for row in doc.get(child["table"]):
            if (
                row.prescribe == 1 or
                row.is_cancelled == 1 or
                row.is_not_available_inhouse == 1 or
                row.get(child["service_created"]) == 1
            ):
                continue

            entry = {
                "service_type": child["doctype"],
                "service_name": row.get(child["item"]),
                "qty": row.get("quantity") or 1,
                "is_restricted": row.get("is_restricted"),
                "has_copayment": row.get("has_copayment"),
                "ref_doctype": row.doctype,
                "ref_docname": row.name,
                "department_hsu": row.get("department_hsu") or row.get("healthcare_service_unit"),
            }
            new_row = set_service_amounts(
                entry,
                doc.company,
                doc.insurance_company,
                doc.insurance_subscription,
            )
            services.append(new_row)

    return services


def set_service_amounts(row, company, insurance_company, insurance_subscription):
    # apply discount if it is available on Heathcare Insurance Company
    discount_percent = 0
    if insurance_company and "NHIF" not in insurance_company:
        discount_percent = get_discount_percent(insurance_company)

    item_rate = 0
    item = frappe.get_cached_value(row.get("service_type"), row.get("service_name"), "item")
    if not item:
        frappe.throw(
            f"Item code for {row.get('service_type')}: {row.get('service_name')} was not found.<br>Please set the item code to proceed..."
        )

    item_price_rate, price_list = get_item_rate(
        item,
        company,
        insurance_subscription,
        insurance_company,
        for_service_request=True,
    )

    item_rate = item_price_rate - (item_price_rate * (discount_percent / 100))

    if discount_percent > 0:
        row["discount_applied"] = 1

    row.update({
        "rate": item_rate,
        "amount": row.get("qty") * item_rate,
        "price_list": price_list,
    })

    return row


def get_item_refcode(
    service_type,
    service_name,
    company,
    insurance_company,
    insurance_customer_name=None
):
    ref_code = ""
    if not insurance_customer_name and company:
        if "NHIF" in insurance_company:
            insurance_customer_name = frappe.get_cached_value(
                "HMS TZ Setting", company, "nhif_customer_name"
            )
        elif "Jubilee" in insurance_company:
            insurance_customer_name = frappe.get_cached_value(
                "HMS TZ Setting", company, "jubilee_customer_name"
            )

    item = frappe.get_cached_value(service_type, service_name, "item")
    code_list = frappe.db.get_all(
        "Item Customer Detail",
        filters={"parent": item, "customer_name": insurance_customer_name},
        fields=["ref_code"],
    )
    if len(code_list) == 0:
        return ref_code

    ref_code = code_list[0].ref_code

    return ref_code


def get_childs_map():
    childs_map = [
        {
            "table": "lab_test_prescription",
            "doctype": "Lab Test Template",
            "item": "lab_test_code",
            "lrpmt_doctype": "Lab Test",
            "lrpmt_docname": "lab_test",
            "service_created": "lab_test_created",
        },
        {
            "table": "radiology_procedure_prescription",
            "doctype": "Radiology Examination Template",
            "item": "radiology_examination_template",
            "lrpmt_doctype": "Radiology Examination",
            "lrpmt_docname": "radiology_examination",
            "service_created": "radiology_examination_created",
        },
        {
            "table": "procedure_prescription",
            "doctype": "Clinical Procedure Template",
            "item": "procedure",
            "lrpmt_doctype": "Clinical Procedure",
            "lrpmt_docname": "clinical_procedure",
            "service_created": "procedure_created",
        },
        {
            "table": "drug_prescription",
            "doctype": "Medication",
            "item": "drug_code",
            "lrpmt_doctype": "Delivery Note Item",
            "lrpmt_docname": "dn_detail",
            "service_created": "drug_prescription_created",
        },
        {
            "table": "therapies",
            "doctype": "Therapy Type",
            "item": "therapy_type",
            "lrpmt_doctype": "Therapy Session",
            "lrpmt_docname": "",
            "service_created": "therapy_plan_created",
        },
    ]
    return childs_map
