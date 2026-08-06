# Copyright (c) 2024, Aakvatech and contributors
# For license information, please see license.txt

import calendar
import json
import os
import uuid
from datetime import datetime

import frappe
import requests
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import DocType
from frappe.utils import (
    cint,
    date_diff,
    get_datetime,
    get_fullname,
    get_time,
    get_url_to_form,
    getdate,
    now_datetime,
    nowdate,
    nowtime,
    time_diff_in_seconds,
    unique,
)
from frappe.utils.pdf import get_pdf
from pypdf import PdfWriter

from hms_tz.hms_tz.doctype.insurance_folio_counter.insurance_folio_counter import get_or_create_folio_counter
from hms_tz.jubilee.doctype.jubilee_response_log.jubilee_response_log import add_jubilee_log
from hms_tz.nhif.api.healthcare_utils import to_base64
from hms_tz.nhif.api.patient_encounter import finalized_encounter

pa = DocType("Patient Appointment")
pe = DocType("Patient Encounter")
ct = DocType("Codification Table")
hsr = DocType("Healthcare Service Request")


class JubileePatientClaim(Document):
    def before_insert(self):
        if frappe.db.exists(
            {
                "doctype": "Jubilee Patient Claim",
                "patient": self.patient,
                "patient_appointment": self.patient_appointment,
                "cardno": self.cardno,
                "docstatus": 0,
            }
        ):
            frappe.throw(
                f"Jubilee Patient Claim is already exist for patient: #<b>{self.patient}</b> with appointment: #<b>{self.patient_appointment}</b>"
            )

        self.validate_appointment_info()
        self.validate_multiple_appointments_per_authorization_no("before_insert")

    def after_insert(self):
        self.set_folio_count()

        items = []
        for row in self.jubilee_patient_claim_item:
            new_row = row.as_dict()
            for fieldname in [
                "name",
                "owner",
                "creation",
                "modified",
                "modified_by",
                "docstatus",
            ]:
                new_row[fieldname] = None

            items.append(new_row)

        if len(items) > 0:
            frappe.set_value(
                self.doctype, self.name, "original_jubilee_patient_claim_item", items
            )
            self.reload()

    def before_save(self):
        if not self.allow_changes:
            encounter_list = self.get_patient_encounters()
            opd_encounters = [row for row in encounter_list if not row.inpatient_record]
            inpatient_ids = [row.inpatient_record for row in encounter_list if row.inpatient_record]
            final_encounter = [row.encounter for row in encounter_list if row.encounter_type == "Final"]

            if len(final_encounter) == 0 and len(inpatient_ids) == 0:
                # Do not auto finalize the encounter if patient is inpatient because JPC will always be created during patient admission
                # because Jubilee API involves only the services provided before the admission

                last_encounter = encounter_list[-1].encounter
                finalized_encounter(last_encounter)

            self.set_claim_values(opd_encounters)

        self.calculate_totals()

        if not self.is_new():
            self.update_original_patient_claim()

            frappe.qb.update(pa).set(pa.jubilee_patient_claim, self.name).where(
                pa.name == self.patient_appointment
            ).run()

    def validate(self):
        self.validate_appointment_info()

    def on_trash(self):
        # check if claim number exist in appointment record
        jubilee_patient_claim = frappe.db.get_value(
            "Patient Appointment",
            self.patient_appointment,
            "jubilee_patient_claim",
        )
        if jubilee_patient_claim == self.name:
            frappe.qb.update(pa).set(pa.jubilee_patient_claim, "").where(pa.name == self.patient_appointment).run()

    def before_submit(self):
        if not self.allow_changes:
            self.db_set("allow_changes", 1)

        start_datetime = now_datetime()

        self.validate_multiple_appointments_per_authorization_no()

        self.validate_item_status()

        if not self.patient_signature:
            get_missing_patient_signature(self)

        # self.validate_submit_date()

        if self.bypass_sending_to_jubilee == 0:
            self.send_jubilee_claim()

        end_datetime = now_datetime()
        time_in_seconds = time_diff_in_seconds(str(end_datetime), str(start_datetime))
        frappe.msgprint(
            "Total time to complete the process in seconds = " + str(time_in_seconds)
        )

    def on_submit(self):
        pass

    def get_patient_encounters(self):
        appointments = []
        if self.hms_tz_claim_appointment_list:
            appointments = json.loads(self.hms_tz_claim_appointment_list)
        else:
            appointments = [self.patient_appointment]

        patient_encounters = (
            frappe.qb.from_(pe)
            .left_join(hsr)
            .on(
                (hsr.docstatus == 1)
                & (hsr.source_docname == pe.name)
                & (hsr.source_doctype == "Patient Encounter")
            )
            .select(
                pe.practitioner,
                pe.encounter_date,
                pe.encounter_type,
                pe.inpatient_record,
                pe.name.as_("encounter"),
                hsr.name.as_("service_request")
            )
            .where(
                (pe.docstatus == 1)
                & (pe.appointment.isin(appointments))
            )
            .orderby(pe.creation)
        ).run(as_dict=True)

        if len(patient_encounters) == 0:
            frappe.throw(_("There are no submitted encounters for this application"))

        return patient_encounters

    def set_claim_values(self, encounter_list):
        self.provider_id = frappe.get_cached_value(
            "HMS TZ Setting",
            self.company,
            "jubilee_provider_id",
        )
        self.folio_id = uuid.uuid1()
        self.posting_date = nowdate()
        self.serial_no = cint(self.name[-9:])
        self.item_crt_by = get_fullname(frappe.session.user)
        self.attendance_date, self.attendance_time = frappe.get_cached_value(
            "Patient Appointment",
            self.patient_appointment,
            ["appointment_date", "appointment_time"],
        )
        self.claim_year = int(self.attendance_date.strftime("%Y"))
        self.claim_month = int(self.attendance_date.strftime("%m"))
        self.patient_type_code = "OUT"

        if not self.date_of_birth:
            self.date_of_birth = frappe.get_cached_value("Patient", self.patient, "dob")

            if not self.date_of_birth:
                frappe.throw(_(f"Date of Birth is not set for Patient: {self.patient}"))

        dob_datetime = datetime.combine(self.date_of_birth, datetime.min.time())
        age_delta = datetime.now() - dob_datetime
        self.patient_age = age_delta.days // 365

        # Do not set inpatient values because JPC will always be created during or before patient admission
        # self.set_inpatient_values(encounter_list)

        self.set_practitioner_values(encounter_list)
        self.set_patient_claim_disease(encounter_list)
        self.set_patient_claim_item(encounter_list)

    def set_practitioner_values(self, encounter_list):
        self.practitioners = []

        practitioners = list(set([d.practitioner for d in encounter_list if d.practitioner]))

        practitioner_details = frappe.db.get_all(
            "Healthcare Practitioner",
            {"name": ["in", practitioners]},
            ["name", "tz_mct_code", "nhif_physician_qualification"],
        )

        for practitioner in practitioner_details:
            if not practitioner.tz_mct_code:
                frappe.throw(_(f"There is no TZ MCT Code for Practitioner: {practitioner.name}"))

            self.append(
                "practitioners",
                {
                    "practitioner": practitioner.name,
                    "mct_code": practitioner.tz_mct_code,
                    "qualification": practitioner.nhif_physician_qualification
                }
            )

    def set_inpatient_values(self, encounter_list):
        inpatient_record = list(set([h.inpatient_record for h in encounter_list if h.inpatient_record]))
        self.inpatient_record = inpatient_record[0] if inpatient_record else None

        # Reset values for every validate
        self.patient_type_code = "OUT"
        self.date_admitted = None
        self.admitted_time = None
        self.date_discharge = None
        self.discharge_time = None
        if self.inpatient_record:
            (
                discharge_date,
                scheduled_date,
                admitted_datetime,
                time_created,
            ) = frappe.get_cached_value(
                "Inpatient Record",
                self.inpatient_record,
                [
                    "discharge_date",
                    "scheduled_date",
                    "admitted_datetime",
                    "creation",
                ],
            )

            if getdate(scheduled_date) < getdate(admitted_datetime):
                self.date_admitted = scheduled_date
                self.admitted_time = get_time(get_datetime(time_created))
            else:
                self.date_admitted = getdate(admitted_datetime)
                self.admitted_time = get_time(get_datetime(admitted_datetime))

            # If the patient is same day discharged then consider it as Outpatient
            if self.date_admitted == getdate(discharge_date):
                self.patient_type_code = "OUT"
                self.date_admitted = None
                self.admitted_time = None
            else:
                self.patient_type_code = "IN"
                self.date_discharge = discharge_date

                # the time a claim is created will be treated as discharge time
                # because there is no field of discharge time on Inpatient Record
                self.discharge_time = nowtime()

        if self.date_discharge:
            self.claim_year = int(self.date_discharge.strftime("%Y"))
            self.claim_month = int(self.date_discharge.strftime("%m"))
        else:
            self.claim_year = int(self.attendance_date.strftime("%Y"))
            self.claim_month = int(self.attendance_date.strftime("%m"))

    def set_patient_claim_disease(self, encounter_list):
        self.jubilee_patient_claim_disease = []
        encounter_ids = [d.encounter for d in encounter_list if d.encounter]

        diagnosis_list = (
            frappe.qb.from_(ct)
            .inner_join(pe)
            .on(pe.name == ct.parent)
            .select(
                ct.name,
                ct.parent,
                ct.code,
                ct.code_value,
                ct.definition,
                ct.modified_by,
                ct.modified,
                ct.parentfield,
                pe.practitioner,
            )
            .where(
                (ct.parenttype == "Patient Encounter")
                & (ct.parent.isin(encounter_ids))
            )
            .groupby(ct.code_value, ct.parentfield)
            .orderby(ct.parentfield, order=frappe.qb.desc)
        ).run(as_dict=True)

        for row in diagnosis_list:
            new_row = self.append("jubilee_patient_claim_disease", {})
            if row.parentfield == "patient_encounter_preliminary_diagnosis":
                new_row.status = "Provisional"
            elif row.parentfield == "patient_encounter_final_diagnosis":
                new_row.status = "Final"
            new_row.medical_code = row.code_value

            # Convert the ICD code of CDC to NHIF
            if row.code and len(row.code) > 3 and "." not in row.code:
                new_row.disease_code = row.code[:3] + "." + (row.code[3:4] or "0")
            elif row.code and len(row.code) <= 5 and "." in row.code:
                new_row.disease_code = row.code
            else:
                new_row.disease_code = row.code[:3]

            new_row.description = row.definition[0:139]
            new_row.item_crt_by = row.practitioner
            new_row.date_created = row.modified

    def set_patient_claim_item(self, encounter_list):
        service_requests = []
        self.clinical_notes = ""
        self.jubilee_patient_claim_item = []

        self.add_appointment_claim_item()

        if not self.inpatient_record:
            for d in encounter_list:
                self.set_clinical_notes(d.encounter)

                if not d.get("service_request"):
                    continue

                if d.get("service_request") in service_requests:
                    continue

                service_requests.append(d.get("service_request"))
                service_request_doc = frappe.get_doc("Healthcare Service Request", d.get("service_request"))
                for row in service_request_doc.get("payments"):
                    self.add_LRPMT_claim_item(row, d)

        else:
            # With Jubilee, Inpatient Items are posted manually to Jubilee CMS Portal
            return
            dates = []
            occupancy_list = []
            record_doc = frappe.get_doc("Inpatient Record", self.inpatient_record)

            for occupancy in record_doc.inpatient_occupancies:
                if not occupancy.is_confirmed:
                    continue

                self.add_occupancy_claim_item(occupancy, record_doc.admission_encounter)

                checkin_date = occupancy.check_in.strftime("%Y-%m-%d")
                # Add only in occupancy once a day.
                if checkin_date not in dates:
                    dates.append(checkin_date)
                    occupancy_list.append(occupancy)

            for occupancy in occupancy_list:
                if not occupancy.is_confirmed:
                    continue

                checkin_date = occupancy.check_in.strftime("%Y-%m-%d")

                if occupancy.is_consultancy_chargeable:
                    for row_item in record_doc.inpatient_consultancy:
                        self.add_consultancy_claim_item(row_item, checkin_date)

                for d in encounter_list:
                    if str(d.encounter_date) != checkin_date:
                        continue

                    # allow clinical notes to be added to the claim even if the
                    # service is not chargeable and encounters will be ignored
                    self.set_clinical_notes(d.encounter)

                    if not d.get("service_request"):
                        continue

                    if d.get("service_request") in service_requests:
                        continue

                    service_requests.append(d.get("service_request"))
                    service_request_doc = frappe.get_doc("Healthcare Service Request", d.get("service_request"))
                    for row in service_request_doc.get("payments"):
                        self.add_LRPMT_claim_item(row, d)

    def add_LRPMT_claim_item(self, hsr_row, d):
        if hsr_row.is_cancelled:
            return

        if not hsr_row.insurance_company or "Jubilee" not in hsr_row.insurance_company:
            return

        if hsr_row.percent_covered == 0:
            return

        new_row = self.append("jubilee_patient_claim_item", {})
        new_row.item_name = hsr_row.service_name
        new_row.item_code = hsr_row.item_code
        new_row.item_quantity = (hsr_row.qty or 0) - (hsr_row.qty_returned or 0)
        new_row.unit_price = hsr_row.rate
        new_row.amount_claimed = hsr_row.amount
        new_row.status = get_LRPMT_status(hsr_row)
        new_row.ref_doctype = hsr_row.ref_doctype
        new_row.ref_docname = hsr_row.ref_docname
        new_row.date_created = hsr_row.creation
        new_row.patient_encounter = d.encounter
        new_row.item_crt_by = d.practitioner
        # new_row.approval_ref_no = get_approval_number_from_LRPMT(
        #     hsr_row.lrpmt_doctype,
        #     hsr_row.lrpmt_docname,
        #     hsr_row.dn_detail
        # )

    def add_occupancy_claim_item(self, occupancy, admission_encounter):
        service_unit_type = frappe.get_cached_value(
            "Healthcare Service Unit",
            occupancy.service_unit,
            "service_unit_type",
        )

        (
            is_service_chargeable,
            is_consultancy_chargeable,
            item,
        ) = frappe.get_cached_value(
            "Healthcare Service Unit Type",
            service_unit_type,
            [
                "is_service_chargeable",
                "is_consultancy_chargeable",
                "item",
            ],
        )

        # update occupancy object
        occupancy.update(
            {
                "service_unit_type": service_unit_type,
                "is_service_chargeable": is_service_chargeable,
                "is_consultancy_chargeable": is_consultancy_chargeable,
            }
        )

        new_row = self.append("jubilee_patient_claim_item", {})
        new_row.item_name = occupancy.service_unit
        new_row.item_code = get_jubilee_refcode(item, self.company)
        new_row.item_quantity = 1
        new_row.unit_price = occupancy.amount
        new_row.amount_claimed = occupancy.amount
        new_row.approval_ref_no = ""
        new_row.patient_encounter = admission_encounter
        new_row.ref_doctype = occupancy.doctype
        new_row.ref_docname = occupancy.name
        new_row.date_created = occupancy.modified
        new_row.item_crt_by = get_fullname(occupancy.modified_by)

    def add_consultancy_claim_item(self, consultancy, checkin_date):
        if consultancy.is_confirmed and str(consultancy.date) == checkin_date and consultancy.rate:
            new_row = self.append("jubilee_patient_claim_item", {})
            new_row.item_name = consultancy.consultation_item
            new_row.item_code = get_jubilee_refcode(consultancy.consultation_item, self.company)
            new_row.item_quantity = 1
            new_row.unit_price = consultancy.rate
            new_row.amount_claimed = consultancy.rate
            new_row.approval_ref_no = ""
            new_row.patient_encounter = consultancy.encounter
            new_row.ref_doctype = consultancy.doctype
            new_row.ref_docname = consultancy.name
            new_row.date_created = consultancy.modified
            new_row.item_crt_by = get_fullname(consultancy.modified_by)

    def add_appointment_claim_item(self):
        patient_appointment_list = []
        if not self.hms_tz_claim_appointment_list:
            patient_appointment_list.append(self.patient_appointment)
        else:
            patient_appointment_list = json.loads(self.hms_tz_claim_appointment_list)

        for appointment_no in patient_appointment_list:
            appointment_doc = frappe.get_cached_doc("Patient Appointment", appointment_no)

            # SHM Rock: 202
            if appointment_doc.has_no_consultation_charges == 1:
                continue

            if not appointment_doc.follow_up:
                new_row = self.append("jubilee_patient_claim_item", {})
                new_row.item_name = appointment_doc.billing_item
                new_row.item_code = get_jubilee_refcode(appointment_doc.billing_item, self.company)
                new_row.item_quantity = 1
                new_row.unit_price = appointment_doc.paid_amount
                new_row.amount_claimed = appointment_doc.paid_amount
                new_row.approval_ref_no = ""
                new_row.ref_doctype = appointment_doc.doctype
                new_row.ref_docname = appointment_doc.name
                new_row.date_created = appointment_doc.modified
                new_row.item_crt_by = get_fullname(appointment_doc.modified_by)

    def set_clinical_notes(self, encounter):
        if not self.clinical_notes:
            patient_name = f"Patient: <b>{self.patient_name}</b>,"
            date_of_birth = f"Date of Birth: <b>{self.date_of_birth}</b>,"
            gender = f"Gender: <b>{self.gender}</b>,"
            years = (
                f"Age: <b>{(date_diff(nowdate(), self.date_of_birth))//365} years</b>,"
            )
            self.clinical_notes = (
                " ".join([patient_name, gender, date_of_birth, years]) + "<br>"
            )

        encounter_doc = frappe.get_doc("Patient Encounter", encounter)

        department = frappe.get_cached_value("Healthcare Practitioner", encounter_doc.practitioner, "department")
        self.clinical_notes += f"<br>PractitionerName: <i>{encounter_doc.practitioner_name},</i> Speciality: <i>{department},\
            </i> DateofService: <i>{encounter_doc.encounter_date} {encounter_doc.encounter_time}</i> <br>"
        self.clinical_notes += encounter_doc.examination_detail or ""

        #Lab Tests
        if len(encounter_doc.get("lab_test_prescription")) > 0:
            self.clinical_notes += "<br>Lab Test(s): <br>"
            for row in encounter_doc.get("lab_test_prescription"):
                if row.get("is_cancelled") == 1:
                    continue

                serv_info = ""
                if row.medical_code:
                    serv_info  += f", Medical Code: {row.medical_code}"

                self.clinical_notes += f"Lab Test Name: <b>{row.lab_test_name}</b> {serv_info} <br>"
                result = self.get_lab_results(row)
                if result:
                    self.clinical_notes += result

        #Radiology
        if len(encounter_doc.get("radiology_procedure_prescription")) > 0:
            self.clinical_notes += "<br>Radiology: <br>"
            for row in encounter_doc.get("radiology_procedure_prescription"):
                if row.get("is_cancelled") == 1:
                    continue

                serv_info = ""
                if row.medical_code:
                    serv_info += f", Medical Code: {row.medical_code}"

                self.clinical_notes += f"Radiology Name: <b>{row.radiology_procedure_name}</b> {serv_info} <br>"
                radiology_report = self.get_radiology_results(row)
                if radiology_report:
                    self.clinical_notes += radiology_report

        #Clinical Procedures
        if len(encounter_doc.get("procedure_prescription")) > 0:
            self.clinical_notes += "<br>Procedure(s): <br>"
            for row in encounter_doc.get("procedure_prescription"):
                if row.get("is_cancelled") == 1:
                    continue

                serv_info = ""
                if row.medical_code:
                    serv_info += f", Medical Code: {row.medical_code}"

                self.clinical_notes += f"Procedure: <b>{row.procedure_name}</b> {serv_info}<br>"
                procedure_notes = self.get_procedure_notes(row)
                if procedure_notes:
                    self.clinical_notes += procedure_notes

        #Medications
        if len(encounter_doc.get("drug_prescription")) > 0:
            self.clinical_notes += "<br>Medication(s): <br>"
            for row in encounter_doc.get("drug_prescription"):
                if row.get("is_cancelled") == 1:
                    continue

                med_info = ""
                if row.medical_code:
                    med_info += f", Medical Code: {row.medical_code}"

                if row.dosage:
                    med_info += f", Dosage: {row.dosage}"

                if row.period:
                    med_info += f", Period: {row.period}"

                if row.dosage_form:
                    med_info += f", Dosage Form: {row.dosage_form}"

                self.clinical_notes += f"Drug: <b>{row.drug_code}</b> {med_info} <br>"

        #Therapies
        if len(encounter_doc.get("therapies")) > 0:
            self.clinical_notes += "<br>Therapies: <br>"
            for row in encounter_doc.get("therapies"):
                if row.get("is_cancelled") == 1:
                    continue

                serv_info = ""
                if row.medical_code:
                    serv_info += f", Medical Code: {row.medical_code}"
                self.clinical_notes += f"Therapy: <b>{row.therapy_type}</b> {serv_info} <br>"

    def calculate_totals(self):
        self.total_amount = 0
        for item in self.jubilee_patient_claim_item:
            item.amount_claimed = item.unit_price * item.item_quantity
            self.total_amount += item.amount_claimed

    @frappe.whitelist()
    def get_appointments(self):
        appointment_list = frappe.db.get_all(
            "Jubilee Patient Claim",
            filters={
                "patient": self.patient,
                "authorization_no": self.authorization_no,
                "cardno": self.cardno,
            },
            fields=["patient_appointment", "hms_tz_claim_appointment_list"],
        )
        if len(appointment_list) == 1:
            frappe.throw(
                _(
                    f"<p style='text-align: center; font-size: 12pt; background-color: #FFD700;'>\
                    <strong>This Authorization no: {frappe.bold(self.authorization_no)} \
                    as used only once on <br> Jubilee Patient Claim: {frappe.bold(self.name)} </strong>\
                    </p>"
                )
            )

        app_list = []
        for app_name in appointment_list:
            if app_name["hms_tz_claim_appointment_list"]:
                app_numbers = json.loads(app_name["hms_tz_claim_appointment_list"])
                app_list += app_numbers

                for d in app_numbers:
                    frappe.qb.update(pa).set(pa.jubilee_patient_claim, self.name).where(
                        pa.name == d
                    ).run()
            else:
                app_list.append(app_name["patient_appointment"])
                frappe.qb.update(pa).set(pa.jubilee_patient_claim, self.name).where(
                    pa.name == app_name["patient_appointment"]
                ).run()

        app_list = list(set(app_list))
        self.allow_changes = 0
        self.hms_tz_claim_appointment_list = json.dumps(app_list)

        self.save(ignore_permissions=True)

    def validate_appointment_info(self):
        appointment_details = frappe.db.get_value(
            "Patient Appointment",
            self.patient_appointment,
            ["authorization_number", "coverage_plan_card_number"],
            as_dict=1,
        )

        if self.authorization_no != appointment_details.authorization_number:
            url = get_url_to_form("Patient Appointment", self.patient_appointment)
            frappe.throw(
                _(
                    f"Authorization Number: <b>{self.authorization_no}</b> of this Claim is not same to \
                  Authorization Number: <b>{appointment_details.authorization_number}</b> on Patient Appointment: <a href='{url}'><b>{self.patient_appointment}</b></a><br><br>\
                  <b>Please rectify before creating this Claim</b>"
                )
            )
        if self.cardno != appointment_details.coverage_plan_card_number:
            url = get_url_to_form("Patient Appointment", self.patient_appointment)
            frappe.throw(
                _(
                    f"Card Number: <b>{self.cardno}</b> of this Claim is not same to \
                  Card Number: <b>{appointment_details.coverage_plan_card_number}</b> on Patient Appointment: <a href='{url}'><b>{self.patient_appointment}</b></a><br><br>\
                  <b>Please rectify before creating this Claim</b>"
                )
            )

    def validate_multiple_appointments_per_authorization_no(self, caller=None):
        """Validate if patient gets multiple appointments with same authorization number"""

        # Check if there are multiple claims with same authorization number
        claim_details = frappe.db.get_all(
            "Jubilee Patient Claim",
            filters={
                "patient": self.patient,
                "authorization_no": self.authorization_no,
                "cardno": self.cardno,
                "docstatus": 0,
            },
            fields=["name", "patient", "patient_name", "hms_tz_claim_appointment_list"],
        )
        claim_name_list = ""
        merged_appointments = []
        for claim in claim_details:
            url = get_url_to_form("Jubilee Patient Claim", claim["name"])
            claim_name_list += f"<a href='{url}'><b>{claim['name']}</b> </a> , "
            if claim["hms_tz_claim_appointment_list"]:
                merged_appointments += json.loads(
                    claim["hms_tz_claim_appointment_list"]
                )

        if len(claim_details) > 1 and not caller:
            frappe.throw(
                f"<p style='text-align: justify; font-size: 14px;'>\
                This Authorization Number: <b>{self.authorization_no}</b> \
                has used multiple times in Jubilee Patient Claim: {claim_name_list}. \
                Please merge these <b>{len(claim_details)}</b> claims to Proceed</p>"
            )

        # Check if there are multiple patient appointments with same authorization number
        appointment_documents = frappe.db.get_all(
            "Patient Appointment",
            filters={
                "patient": self.patient,
                "authorization_number": self.authorization_no,
                "coverage_plan_card_number": self.cardno,
                "status": ["!=", "Cancelled"],
            },
            pluck="name",
        )

        if len(appointment_documents) > 1:
            self.validate_hold_card_status(
                appointment_documents, claim_details, merged_appointments, caller
            )
        elif caller:
            frappe.msgprint("Release Patient Card", 20, alert=True)

    def validate_hold_card_status(
        self, appointment_documents, claim_details, merged_appointments, caller=None
    ):
        msg = f"<p style='text-align: justify; font-size: 14px'>Patient: <b>{self.patient}</b>-<b>{self.patient_name}</b> has multiple appointments: <br>"

        # check if there is any merging done before
        reqd_throw_count = 0
        for appointment in appointment_documents:
            url = get_url_to_form("Patient Appointment", appointment)
            msg += f"<a href='{url}'><b>{appointment}</b></a> , "

            if merged_appointments:
                for app in unique(merged_appointments):
                    if appointment == app:
                        reqd_throw_count += 1

        if caller:
            unique_claims_appointments = 0
            if len(unique(merged_appointments)) < len(claim_details):
                unique_claims_appointments = len(claim_details)
            else:
                unique_claims_appointments = len(unique(merged_appointments))

            if (len(appointment_documents) - 1) == unique_claims_appointments:
                frappe.msgprint("<strong>Release Patient Card</strong>", 20, alert=True)
                frappe.msgprint("<strong>Release Patient Card</strong>")
            else:
                msg += f"<br> with same authorization no: <b>{self.authorization_no}</b><br><br>\
					Please <strong>Hold patient card</strong> until claims for all <b>{len(appointment_documents)}</b> appointments to be created.</p>"
                frappe.msgprint("<strong>Please Hold Card</strong>", 20, alert=True)
                frappe.msgprint(str(msg))

            return

        msg += f"<br> with same authorization no: <b>{self.authorization_no}</b><br><br> Please consider <strong>merging of claims</strong>\
			if Claims for all <b>{len(appointment_documents)}</b> appointments have already been created</p>"

        if reqd_throw_count < len(appointment_documents):
            frappe.throw(msg)

    def validate_item_status(self):
        for row in self.jubilee_patient_claim_item:
            if row.status == "Draft":
                frappe.throw(
                    f"Item: {frappe.bold(row.item_name)}, doctype: {frappe.bold(row.ref_doctype)}. \
                    RowNo: {frappe.bold(row.idx)} is in <strong>Draft</strong>,\
                    please contact relevant department for clarification"
                )

    def validate_submit_date(self):
        submit_claim_month, submit_claim_year = frappe.get_cached_value(
            "HMS TZ Setting",
            self.company,
            ["submit_claim_month", "submit_claim_year"],
        )

        if not (submit_claim_month or submit_claim_year):
            frappe.msgprint(
                frappe.bold(
                    "Submit Claim Month or Submit Claim Year not found,\
                    please inform IT department to set it on HMS TZ Setting"
                ),
                alert=True,
            )

        if (
            self.claim_month != submit_claim_month
            or self.claim_year != submit_claim_year
        ):
            frappe.throw(
                f"Claim Month: {frappe.bold(calendar.month_name[self.claim_month])} or Claim Year: {frappe.bold(self.claim_year)} \
                of this document is not same to Submit Claim Month: {frappe.bold(calendar.month_name[submit_claim_month])} \
                or Submit Claim Year: {frappe.bold(submit_claim_year)} on HMS TZ Setting"
            )

    def get_lab_results(self, row):
        if not row.lab_test:
            return

        lab_test_doc = frappe.get_cached_doc("Lab Test", row.lab_test)
        if lab_test_doc.workflow_state == "Lab Test Requested":
            return

        result = ""

        if lab_test_doc.normal_test_items:
            result += '<div align="center"><i><u><b>Normal Test Results</b></u></i></div>'
            result += '<table border="1" cellpadding="5" cellspacing="0" width="90%" align="center">'
            result += '<tr bgcolor="#CCCCCC"><th>Test Name</th><th>Result</th><th>UOM</th></tr>'

            for item in lab_test_doc.normal_test_items:
                result += f'<tr><td>{item.lab_test_name}</td>'
                result += f'<td>{item.result_value}</td>'
                result += f'<td>{item.lab_test_uom or ""}</td></tr>'

            result += '</table><br>'

        # Descriptive test items table
        if lab_test_doc.descriptive_test_items:
            result += '<div align="center"><i><u><b>Descriptive Test Results</b></u></i></div>'
            result += '<table border="1" cellpadding="5" cellspacing="0" width="90%" align="center">'
            result += '<tr bgcolor="#CCCCCC"><th>Test Particulars</th><th>Result</th></tr>'

            for item in lab_test_doc.descriptive_test_items:
                result += f'<tr><td>{item.lab_test_particulars}</td>'
                result += f'<td>{item.result_value}</td></tr>'

            result += '</table><br>'

        # Sensitivity test items table
        if lab_test_doc.sensitivity_test_items:
            result += '<div align="center"><i><u><b>Sensitivity Test Results</b></u></i></div>'
            result += '<table border="1" cellpadding="5" cellspacing="0" width="90%" align="center">'
            result += '<tr bgcolor="#CCCCCC"><th>Antibiotic</th><th>Sensitivity</th></tr>'

            for item in lab_test_doc.sensitivity_test_items:
                result += f'<tr><td>{item.antibiotic}</td>'
                result += f'<td>{item.antibiotic_sensitivity}</td></tr>'

            result += '</table><br>'

        # Custom result
        if lab_test_doc.custom_result:
            result += '<div align="center"><i><u><b>Custom Result</b></u></i></div>'
            result += '<table border="1" cellpadding="5" cellspacing="0" width="90%" align="center">'
            result += f'<tr><td>{lab_test_doc.custom_result}</td></tr>'
            result += '</table><br>'

        return result

    def get_radiology_results(self, row):
        if not row.radiology_examination:
            return

        radiology_report = frappe.get_cached_value(
            "Radiology Examination",
            row.radiology_examination,
            "radiology_report_details"
        )
        result = ""
        if radiology_report:
            result += f"<div align='center'><i><u><b>Radiology Report</b></u></i></div>"
            result += f"<table border='1' cellpadding='5' cellspacing='0' width='90%' align='center'>"
            result += f"<tr><td>{radiology_report}</td></tr>"
            result += f"</table><br>"

        return result

    def get_procedure_notes(self, row):
        if not row.clinical_procedure:
            return

        notes = frappe.get_cached_value("Clinical Procedure", row.clinical_procedure, "procedure_notes") or ""
        result = ""
        if notes:
            result += f"<div align='center'><i><u><b>Procedure Notes</b></u></i></div>"
            result += f"<table border='1' cellpadding='5' cellspacing='0' width='90%' align='center'>"
            result += f"<tr><td>{notes}</td></tr>"
            result += f"</table><br>"

        return result

    def set_folio_count(self):
        if cint(self.folio_no) != 0:
            return

        self.folio_no = get_or_create_folio_counter(self, "Jubilee")
        self.db_set("folio_no", self.folio_no)

    @frappe.whitelist()
    def send_jubilee_claim(self):
        json_data, json_data_wo_files = self.get_payload()
        setting_doc = frappe.get_cached_doc("HMS TZ Setting", self.company)
        token = setting_doc.get_jubilee_token()

        headers = {
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        }
        url = str(setting_doc.jubilee_url) + "/jubileeapi/SendClaim"

        r = None
        try:
            r = requests.post(url, headers=headers, data=json_data, timeout=300)

            if r.status_code != 200:
                frappe.throw(
                    f"Jubilee Server responded with HTTP status code: {r.status_code}<br><br>{str(r.text) if r.text else str(r)}"
                )
            else:
                # Jubilee server sometimes prepends PHP debug HTML warnings
                # before the JSON body. Extract only the JSON part.
                raw = r.text or ""
                json_start = raw.find('{"')
                if json_start == -1:
                    frappe.throw(
                        f"Jubilee returned an unreadable response:<br><br>{raw}"
                    )

                data = json.loads(raw[json_start:])
                if data.get("status") == "ERROR" or data.get("Status") == "ERROR":
                    frappe.throw(
                        data.get("description") or data.get("Description") or str(data)
                    )

                else:
                    frappe.msgprint(str(data.get("description") or data.get("Description") or ""))
                    if data:
                        add_jubilee_log(
                            request_type="SubmitClaim",
                            request_url=url,
                            request_header=headers,
                            request_body=json_data_wo_files,
                            response_data=data,
                            status_code=r.status_code,
                            ref_doctype=self.doctype,
                            ref_docname=self.name,
                            company=self.company,
                        )

                        self.submission_id = data.get("submissionID")

                    frappe.msgprint(
                        _("The claim has been sent successfully"), alert=True
                    )

        except Exception:
            add_jubilee_log(
                request_type="SubmitClaim",
                request_url=url,
                request_header=headers,
                request_body=json_data,
                response_data=(r.text if str(r) else "NO RESPONSE r. Timeout???"),
                status_code=(
                    r.status_code if str(r) else "NO STATUS CODE r. Timeout???"
                ),
                ref_doctype=self.doctype,
                ref_docname=self.name,
                company=self.company,
            )
            self.add_comment(
                comment_type="Comment",
                text=r.text if str(r) else "NO RESPONSE",
            )
            frappe.db.commit()

            frappe.throw(
                "This folio was NOT submitted due to the error above!. \
                Please retry after resolving the problem. "
                + str(now_datetime())
            )

    def get_payload(self):
        folio_data = frappe._dict()
        folio_data.entities = []
        entities = frappe._dict()
        entities.FolioID = self.folio_id
        entities.ClaimYear = self.claim_year
        entities.ClaimMonth = self.claim_month
        entities.FolioNo = self.folio_no
        entities.SerialNo = self.serial_no
        entities.CardNo = self.cardno.strip()
        entities.BillNo = self.name
        entities.FirstName = self.first_name
        entities.LastName = self.last_name
        entities.Gender = self.gender
        entities.DateOfBirth = str(self.date_of_birth)
        entities.Age = self.patient_age
        entities.TelephoneNo = self.telephone_no
        entities.PatientFileNo = self.patient
        entities.AuthorizationNo = self.authorization_no
        entities.AttendanceDate = str(self.attendance_date)
        entities.PatientTypeCode = self.patient_type_code
        if self.patient_type_code == "IN":
            entities.DateAdmitted = (
                str(self.date_admitted) + " " + str(self.admitted_time)
            )
            entities.DateDischarged = (
                str(self.date_discharge) + " " + str(self.discharge_time)
            )
        entities.PractitionerNo = ", ".join([d.mct_code for d in self.practitioners if d.mct_code]),
        # entities.PractitionerName = self.practitioner_name
        entities.ProviderID = self.provider_id
        entities.ClinicalNotes = self.clinical_notes
        entities.AmountClaimed = self.total_amount
        entities.DelayReason = self.delayreason
        entities.LateSubmissionReason = self.delayreason
        entities.LateAuthorizationReason = get_appointment_remarks(
            self.patient_appointment
        )
        entities.EmergencyAuthorizationReason = get_appointment_remarks(
            self.patient_appointment
        )
        entities.CreatedBy = self.item_crt_by
        entities.DateCreated = str(self.posting_date)
        entities.LastModifiedBy = get_fullname(frappe.session.user)
        entities.LastModified = str(now_datetime())
        entities.PatientFile = generate_pdf(self)
        entities.ClaimFile = get_claim_pdf_file(self)

        entities.FolioDiseases = []
        for disease in self.jubilee_patient_claim_disease:
            FolioDisease = frappe._dict()
            FolioDisease.DiseaseCode = disease.disease_code
            FolioDisease.Remarks = disease.description or ""
            FolioDisease.Status = disease.status
            FolioDisease.CreatedBy = disease.item_crt_by
            FolioDisease.DateCreated = str(disease.date_created)
            FolioDisease.LastModifiedBy = disease.item_crt_by
            FolioDisease.LastModified = str(disease.date_created)
            entities.FolioDiseases.append(FolioDisease)

        entities.FolioItems = []
        for item in self.jubilee_patient_claim_item:
            FolioItem = frappe._dict()
            FolioItem.ItemCode = item.item_code
            FolioItem.OtherDetails = "Treated"
            FolioItem.ItemQuantity = item.item_quantity
            FolioItem.UnitPrice = item.unit_price
            FolioItem.AmountClaimed = item.amount_claimed
            FolioItem.ApprovalRefNo = item.approval_ref_no or ""
            FolioItem.CreatedBy = item.item_crt_by
            FolioItem.DateCreated = str(item.date_created)
            FolioItem.LastModifiedBy = item.item_crt_by
            FolioItem.LastModified = str(item.date_created)
            entities.FolioItems.append(FolioItem)

        folio_data.entities.append(entities)
        jsonStr = json.dumps(folio_data)

        # Strip off the patient file
        folio_data.entities[0].PatientFile = "Stripped off"
        folio_data.entities[0].ClaimFile = "Stripped off"
        jsonStr_wo_files = json.dumps(folio_data)
        return jsonStr, jsonStr_wo_files

    def update_original_patient_claim(self):
        """Update original patient claim incase merging if done for this claim"""

        ref_docnames = []
        for item in self.original_jubilee_patient_claim_item:
            if item.ref_docname:
                d = item.ref_docname.split(",")
                ref_docnames.extend(d)

        # appends to original_jubilee_patient_claim_item
        for row in self.jubilee_patient_claim_item:  # nosemgrep
            if row.ref_docname not in ref_docnames:
                new_row = row.as_dict()
                for fieldname in [
                    "name",
                    "owner",
                    "creation",
                    "modified",
                    "modified_by",
                    "docstatus",
                ]:
                    new_row[fieldname] = None

                self.append("original_jubilee_patient_claim_item", new_row)

    @frappe.whitelist()
    def reconcile_repeated_items(self):
        def reconcile_items(claim_items):
            unique_items = []
            repeated_items = []
            unique_refcodes = []

            for row in claim_items:
                if row.item_code not in unique_refcodes:
                    unique_refcodes.append(row.item_code)
                    unique_items.append(row)
                else:
                    repeated_items.append(row)

            if len(repeated_items) > 0:
                items = []
                for item in unique_items:
                    ref_docnames = []
                    ref_encounters = []

                    for d in repeated_items:
                        if item.item_code == d.item_code:
                            item.item_quantity += d.item_quantity
                            item.amount_claimed += d.amount_claimed

                            if d.approval_ref_no:
                                approval_ref_no = None
                                if item.approval_ref_no:
                                    approval_ref_no = (
                                        str(item.approval_ref_no)
                                        + ","
                                        + str(d.approval_ref_no)
                                    )
                                else:
                                    approval_ref_no = d.approval_ref_no

                                item.approval_ref_no = approval_ref_no

                            if d.patient_encounter:
                                ref_encounters.append(d.patient_encounter)
                            if d.ref_docname:
                                ref_docnames.append(d.ref_docname)

                            if item.status != "Submitted" and d.status == "Submitted":
                                item.status = "Submitted"

                    if item.patient_encounter:
                        ref_encounters.append(item.patient_encounter)
                    if item.ref_docname:
                        ref_docnames.append(item.ref_docname)

                    if len(ref_encounters) > 0:
                        item.patient_encounter = ",".join(set(ref_encounters))

                    if len(ref_docnames) > 0:
                        item.ref_docname = ",".join(set(ref_docnames))

                    items.append(item)

                for record in repeated_items:
                    frappe.delete_doc(
                        record.doctype,
                        record.name,
                        force=True,
                        ignore_permissions=True,
                        ignore_on_trash=True,
                        delete_permanently=True,
                    )
                return items

            else:
                return unique_items

        self.allow_changes = 1
        self.jubilee_patient_claim_item = reconcile_items(
            self.jubilee_patient_claim_item
        )
        self.original_jubilee_patient_claim_item = reconcile_items(
            self.original_jubilee_patient_claim_item
        )

        self.save(ignore_permissions=True)
        return True


def get_jubilee_refcode(item_code, company):
    jubilee_cust_name = frappe.get_cached_value("HMS TZ Setting", company, "jubilee_customer_name")

    code_list = frappe.db.get_all(
        "Item Customer Detail",
        filters={"parent": item_code, "customer_name": jubilee_cust_name},
        fields=["ref_code"],
    )
    if len(code_list) == 0:
        frappe.throw(_(f"Item: {item_code} has not Jubilee Code Reference"))

    ref_code = code_list[0].ref_code
    if not ref_code:
        frappe.throw(_(f"Item: {item_code} has not Jubilee Code Reference"))

    return ref_code


def get_LRPMT_status(row):
    status = row.lrpmt_status
    if status == "Draft" and row.lrpmt_doctype == "Lab Test":
        lab_workflow_state = frappe.get_cached_value(
            "Lab Test",
            row.lrpmt_docname,
            "workflow_state",
        )
        if lab_workflow_state and lab_workflow_state != "Lab Test Requested":
            status = "Submitted"

    if not status:
        status = "Draft"

    return status


def get_missing_patient_signature(doc):
    if doc.patient:
        signature = frappe.get_cached_value("Patient", doc.patient, "patient_signature")
        if not signature:
            frappe.throw(_("Patient signature is required"))

        doc.patient_signature = signature


def get_appointment_remarks(appointment):
    remarks = frappe.db.get_value(
        "Patient Appointment",
        {"name": appointment},
        "remarks",
    )

    return remarks or ""


def generate_pdf(doc):
    file_list = frappe.db.get_all(
        "File",
        filters={
            "attached_to_doctype": "Jubilee Patient Claim",
            "file_name": str(doc.name + ".pdf"),
        },
    )
    if file_list:
        patientfile = frappe.get_cached_doc("File", file_list[0].name)
        if patientfile:
            pdf = patientfile.get_content()
            return to_base64(pdf)

    data_list = []
    encounter_list = doc.get_patient_encounters()

    for i in encounter_list:
        if not i.encounter or i.inpatient_record:
            continue

        data_list.append(i.encounter)

    doctype = dict({"Patient Encounter": data_list})
    print_format = ""
    default_print_format = frappe.db.get_value(
        "Property Setter",
        dict(property="default_print_format", doc_type="Patient Encounter"),
        "value",
    )
    if default_print_format:
        print_format = default_print_format
    else:
        print_format = "Patient File"

    pdf = download_multi_pdf(
        doctype, doc.name, print_format=print_format, no_letterhead=1
    )
    if pdf:
        ret = frappe.get_doc(
            {
                "doctype": "File",
                "attached_to_doctype": "Jubilee Patient Claim",
                "attached_to_name": doc.name,
                "folder": "Home/Attachments",
                "file_name": doc.name + ".pdf",
                "file_url": "/private/files/" + doc.name + ".pdf",
                "content": pdf,
                "is_private": 1,
            }
        )
        ret.save(ignore_permissions=1)
        # ret.db_update()
        return to_base64(pdf)


def download_multi_pdf(doctype, name, print_format=None, no_letterhead=0):
    output = PdfWriter()
    if isinstance(doctype, dict):
        for doctype_name in doctype:
            for doc_name in doctype[doctype_name]:
                try:
                    output = frappe.get_print(
                        doctype_name,
                        doc_name,
                        print_format,
                        as_pdf=True,
                        output=output,
                        no_letterhead=no_letterhead,
                    )
                except Exception:
                    frappe.log_error(
                        title="Jubilee Claim's PDF Error",
                        message=frappe.get_traceback(),
                        reference_doctype=doctype_name,
                        reference_name=doc_name,
                    )

    return read_multi_pdf(output)


def read_multi_pdf(output):
    fname = os.path.join("/tmp", f"frappe-pdf-{frappe.generate_hash()}.pdf")
    output.write(open(fname, "wb"))

    with open(fname, "rb") as fileobj:
        filedata = fileobj.read()

    return filedata


def get_claim_pdf_file(doc):
    file_list = frappe.db.get_all(
        "File",
        filters={
            "attached_to_doctype": "Jubilee Patient Claim",
            "file_name": str(doc.name + "-claim.pdf"),
        },
    )
    if file_list:
        for file in file_list:
            frappe.delete_doc("File", file.name, ignore_permissions=True, force=True)

    default_print_format = frappe.db.get_value(
        "Property Setter",
        dict(property="default_print_format", doc_type=doc.doctype),
        "value",
    )
    if default_print_format:
        print_format = default_print_format
    else:
        print_format = "Jubilee Form 2A & B"

    html = frappe.get_print(
        doc.doctype, doc.name, print_format, doc=None, no_letterhead=1
    )

    filename = f"""{doc.name.replace(" ", "-").replace("/", "-")}-claim"""
    pdf = get_pdf(html)
    if pdf:
        ret = frappe.get_doc(
            {
                "doctype": "File",
                "attached_to_doctype": doc.doctype,
                "attached_to_name": doc.name,
                "folder": "Home/Attachments",
                "file_name": filename + ".pdf",
                "file_url": "/private/files/" + filename + ".pdf",
                "content": pdf,
                "is_private": 1,
            }
        )
        ret.insert(ignore_permissions=True)
        ret.db_update()
        if not ret.name:
            frappe.throw("ret name not exist")
        base64_data = to_base64(pdf)
        return base64_data
    else:
        frappe.throw(_("Failed to generate pdf"))
