# Copyright (c) 2026, Aakvatech and contributors
# For license information, please see license.txt

import math
from datetime import datetime
from datetime import timedelta as td

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, flt, now_datetime, nowdate, nowtime, time_diff_in_seconds, to_timedelta

from hms_tz.nhif.api.medical_record import create_medical_record, delete_medical_record, update_medical_record


class NurseRecord(Document):
    def before_insert(self):
        if self.appointment:
            insurance = frappe.get_cached_value(
                "Patient Appointment",
                self.appointment,
                "insurance_company"
            )
            if insurance:
                self.payment_type = 'Insurance'
            else:
                self.payment_type = 'Cash'

    def before_save(self):
        insurance = frappe.get_cached_value(
            "Patient Appointment",
            self.appointment,
            "insurance_company"
        )
        if insurance:
            self.payment_type = 'Insurance'
        else:
            self.payment_type = 'Cash'

        self.set_missing_values()
        self.validate_no_duplicate()
        self.validate_room_and_ward_fields()
        self.set_status_on_save()
        self.set_previous_notes()

    def before_submit(self):
        self.status = "Completed"

    def on_submit(self):
        create_medical_record(self)

    def on_cancel(self):
        delete_medical_record(self)

    def on_update_after_submit(self):
        update_medical_record(self)

    def set_missing_values(self):
        """Auto-set default values for missing fields."""
        if not self.posting_date:
            self.posting_date = nowdate()
            self.posting_time = nowtime()

        if self.patient and not self.inpatient_record:
            self.inpatient_record = frappe.db.get_value(
                "Patient", self.patient, "inpatient_record"
            )

        if (
            self.appointment
            and self.payment_type == "Insurance"
            and not self.insurance_subscription
        ):
            appt_details = frappe.db.get_value(
                "Patient Appointment",
                self.appointment,
                [
                    "insurance_subscription",
                    "coverage_plan_name",
                    "insurance_company",
                ],
                as_dict=True,
            )
            if appt_details:
                self.insurance_subscription = appt_details.insurance_subscription
                self.insurance_coverage_plan = appt_details.coverage_plan_name
                self.insurance_company = appt_details.insurance_company

        if self.payment_type == "Cash" and self.insurance_subscription:
            self.insurance_subscription = ""
            self.insurance_coverage_plan = ""
            self.insurance_company = ""

    def validate_no_duplicate(self):
        """Prevent duplicate nurse records for the same patient + nurse + date."""
        filters = {
            "patient": self.patient,
            "nurse": self.nurse,
            "posting_date": self.posting_date,
            "docstatus": ["!=", 2],
        }
        if not self.is_new():
            filters["name"] = ["!=", self.name]

        existing = frappe.db.exists("Nurse Record", filters)
        if existing:
            frappe.throw(
                _(
                    "A Nurse Record already exists for patient {0} with nurse"
                    " {1} on {2}: {3}"
                ).format(self.patient, self.nurse, self.posting_date, existing)
            )

    def validate_room_and_ward_fields(self):
        """Validate service unit fields.

        Rules:
        - If room is set but ward is missing: OK
        - If ward is set but room is missing: OK
        - If BOTH are missing: throw validation error
        """
        if not self.room and not self.ward:
            frappe.throw(
                _(
                    "Please set at least one of Room or Ward."
                )
            )

    def set_status_on_save(self):
        """Auto-update status based on content."""
        if self.status == "Open" and (
            self.care_plans or self.nursing_notes or self.observations
        ):
            self.status = "In Progress"

    def set_previous_notes(self):
        """Copy nursing_notes from the most recent previous Nurse Record for this patient."""

        if not self.is_new() or not self.patient:
            return

        nurse_details = frappe.db.get_value(
            "Nurse Record",
            filters={
                "patient": self.patient,
                "docstatus": ["!=", 2],
                "name": ["!=", self.name or ""],
            },
            fieldname=["nursing_notes", "previous_notes", "posting_date", "posting_time"],
            order_by="posting_date desc, creation desc",
            as_dict=True
        )

        if not nurse_details:
            return

        nurse_info = ""
        if nurse_details.nursing_notes:
            nurse_info = f"""
            Nurse: <b>{nurse_details.nurse}</b>: Date: <b>{str(nurse_details.posting_date)} {str(nurse_details.posting_time)}</b><br>{nurse_details.nursing_notes}
            """
        self.previous_notes = nurse_info + "\n\n" + (nurse_details.previous_notes or "")


@frappe.whitelist()
def get_vital_signs(patient, appointment=None):
    """Fetch vital signs for a patient's episode (from appointment to current).

    Returns vital signs data for rendering charts and table in the Nurse Record.
    """
    filters = {
        "patient": patient,
        "docstatus": 1,
    }
    if appointment:
        filters["appointment"] = appointment

    vitals = frappe.db.get_all(
        "Vital Signs",
        filters=filters,
        fields=[
            "name",
            "signs_date",
            "signs_time",
            "temperature",
            "pulse",
            "respiratory_rate",
            "bp_systolic",
            "bp_diastolic",
            "bp",
            "oxygen_saturation_spo2",
            "rbg",
            "weight",
            "height_in_cm",
            "bmi",
            "vital_signs_note",
        ],
        order_by="signs_date asc, signs_time asc",
        limit_page_length=0,
    )

    return vitals


@frappe.whitelist()
def create_vital_signs(patient, nurse_record, **kwargs):
    """Create a Vital Signs record from the Nurse Record dialog.

    Args:
        patient: Patient ID
        nurse_record: Nurse Record name for linking
        **kwargs: Vital signs field values (temperature, pulse, bp_systolic, etc.)
    """
    nr = frappe.get_doc("Nurse Record", nurse_record)
    vs = frappe.new_doc("Vital Signs")
    vs.patient = patient
    vs.appointment = nr.appointment
    vs.inpatient_record = nr.inpatient_record
    vs.company = nr.company
    vs.signs_date = nowdate()

    # Set vital sign values from kwargs
    vital_fields = [
        "temperature",
        "pulse",
        "respiratory_rate",
        "bp_systolic",
        "bp_diastolic",
        "oxygen_saturation_spo2",
        "rbg",
        "weight",
        "height_in_cm",
        "tongue",
        "abdomen",
        "reflexes",
        "vital_signs_note",
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
def get_pending_medications(patient, inpatient_record):
    """Fetch pending (not completed) IMO entries for a patient.

    Returns entries for today and any overdue from previous days,
    excluding entries with administration_status = 'Held' separately.
    """
    today = nowdate()

    imo_list = frappe.db.get_all(
        "Inpatient Medication Order",
        filters={
            "patient": patient,
            "inpatient_record": inpatient_record,
            "docstatus": 1,
            "status": ["in", ["Pending", "In Process"]],
        },
        fields=["name"],
        pluck="name",
    )

    if not imo_list:
        return []

    entries = frappe.db.get_all(
        "Inpatient Medication Order Entry",
        filters={
            "parent": ["in", imo_list],
            "is_completed": 0,
            "date": ["<=", today],
        },
        fields=[
            "name", "drug", "drug_name", "dosage", "dosage_form", "dose_uom",
            "date", "time", "instructions", "parent",
            "administration_status",
        ],
        order_by="date asc, time asc",
    )

    return entries


@frappe.whitelist()
def update_medication_status(
    imo_entry_name, status, notes=None, nurse_record=None
):
    """Update IMO Entry with administration status and related fields.

    Args:
        imo_entry_name: Name of the Inpatient Medication Order Entry
        status: One of 'Administered', 'Skipped', 'Refused', 'Held'
        notes: Optional notes/reason
        nurse_record: Optional Nurse Record name for context
    """
    valid_statuses = ["Administered", "Skipped", "Refused", "Held"]
    if status not in valid_statuses:
        frappe.throw(_("Invalid status: {0}").format(status))

    imo_entry = frappe.db.get_value(
        "Inpatient Medication Order Entry",
        imo_entry_name,
        ["parent", "drug", "date", "time"],
        as_dict=True,
    )

    if not imo_entry or not imo_entry.parent:
        frappe.throw(_("IMO Entry {0} not found or has no parent.").format(imo_entry_name))

    now = now_datetime()

    # Update IMO Entry custom fields
    update_fields = {
        "administration_status": status,
        "administered_time": now,
        "administered_by": frappe.session.user,
    }
    if notes:
        update_fields["administration_notes"] = notes

    # For Administered, Skipped, Refused → mark as completed (resolved)
    # For Held → keep as not completed (stays in pending)
    if status in ("Administered", "Skipped", "Refused"):
        update_fields["is_completed"] = 1

    for field, value in update_fields.items():
        frappe.db.set_value(
            "Inpatient Medication Order Entry",
            imo_entry_name,
            field,
            value,
            update_modified=False,
        )

    # Update parent IMO completed count and status
    if status in ("Administered", "Skipped", "Refused"):
        imo = frappe.get_doc("Inpatient Medication Order", imo_entry.parent)
        completed = cint(imo.completed_orders) + 1
        frappe.db.set_value(
            "Inpatient Medication Order",
            imo.name,
            "completed_orders",
            completed,
            update_modified=False,
        )
        imo.reload()
        imo.set_status()

    # Recalculate remaining schedules if administered late (> 60 min delta)
    if status == "Administered":
        scheduled_time = imo_entry.time
        actual_time = now.time()

        delta_seconds = abs(
            time_diff_in_seconds(str(actual_time), str(scheduled_time))
        )
        if delta_seconds > 3600:
            recalculate_remaining_schedules(
                imo_entry.parent,
                imo_entry.drug,
                imo_entry.date,
                scheduled_time,
                actual_time,
            )

    return {"status": "success", "administration_status": status}


def recalculate_remaining_schedules(
    imo_name, drug, reference_date, scheduled_time, actual_time
):
    """Recalculate remaining scheduled doses for the same drug on the same day.

    If the administered time differs from the scheduled time, shift all remaining
    pending entries for that drug on that day forward by the same delta.

    Args:
        imo_name: Inpatient Medication Order name
        drug: Item code of the drug
        reference_date: The date of the administered dose
        scheduled_time: Originally scheduled time
        actual_time: Time medication was actually administered
    """

    # Calculate the time delta
    scheduled_td = to_timedelta(str(scheduled_time))
    actual_td = to_timedelta(str(actual_time))
    delta = actual_td - scheduled_td  # positive = late, negative = early

    # Get remaining pending entries for the same drug on the same day
    remaining = frappe.db.get_all(
        "Inpatient Medication Order Entry",
        filters={
            "parent": imo_name,
            "drug": drug,
            "date": reference_date,
            "is_completed": 0,
        },
        fields=["name", "time"],
        order_by="time asc",
    )

    if not remaining:
        return

    for entry in remaining:
        old_time = to_timedelta(str(entry.time))
        new_time = old_time + delta

        # Clamp to same day (don't go past midnight or before 00:00)
        total_seconds = new_time.total_seconds()
        if total_seconds < 0:
            total_seconds = 0
        elif total_seconds >= 86400:  # 24 hours
            total_seconds = 86399  # 23:59:59

        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        new_time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        frappe.db.set_value(
            "Inpatient Medication Order Entry",
            entry.name,
            "time",
            new_time_str,
            update_modified=False,
        )


@frappe.whitelist()
def get_completed_medications(patient, inpatient_record):
    """Fetch all completed medication entries for the history section.

    Returns a list of dicts with drug_name, dosage, date, time, status, etc.
    """
    imo_list = frappe.db.get_all(
        "Inpatient Medication Order",
        filters={
            "patient": patient,
            "inpatient_record": inpatient_record,
            "docstatus": 1,
        },
        fields=["name"],
    )

    if not imo_list:
        return []

    imo_names = [imo.name for imo in imo_list]

    entries = frappe.db.get_all(
        "Inpatient Medication Order Entry",
        filters={
            "parent": ["in", imo_names],
            "is_completed": 1,
        },
        fields=[
            "name", "drug", "drug_name", "dosage", "dosage_form", "dose_uom",
            "date", "time", "parent",
            "administration_status", "administered_time",
            "administered_by", "administration_notes",
        ],
        order_by="date desc, time desc",
        limit_page_length=50,
    )

    return entries


@frappe.whitelist()
def get_medication_progress(patient, inpatient_record):
    """Returns aggregated data for the medication progress chart.

    Groups by drug_name and counts: total, completed, pending.
    """
    imo_list = frappe.db.get_all(
        "Inpatient Medication Order",
        filters={
            "patient": patient,
            "inpatient_record": inpatient_record,
            "docstatus": 1,
        },
        fields=["name"],
    )

    if not imo_list:
        return []

    imo_names = [imo.name for imo in imo_list]

    entries = frappe.db.get_all(
        "Inpatient Medication Order Entry",
        filters={
            "parent": ["in", imo_names],
        },
        fields=["drug_name", "is_completed"],
        limit_page_length=0,
    )

    # Aggregate by drug_name
    progress = {}
    for entry in entries:
        name = entry.drug_name or "Unknown"
        if name not in progress:
            progress[name] = {"drug_name": name, "total": 0, "completed": 0, "pending": 0}
        progress[name]["total"] += 1
        if entry.is_completed:
            progress[name]["completed"] += 1
        else:
            progress[name]["pending"] += 1

    return list(progress.values())


@frappe.whitelist()
def get_upcoming_medications(nurse, within_minutes=60):
    """Check upcoming medications for ALL patients assigned to this nurse.

    Returns list of {patient, patient_name, drug_name, scheduled_time, nurse_record_name}.
    This is used for the dashboard alert banner showing all patients under the nurse.
    """
    today = nowdate()
    now = now_datetime()

    cutoff_time = (now + td(minutes=cint(within_minutes))).time()
    current_time = now.time()

    # Fetch nurse records from today and yesterday (covers overnight shifts)
    nurse_records = frappe.db.get_all(
        "Nurse Record",
        filters={
            "nurse": nurse,
            "posting_date": ["in", [today, add_days(today, -1)]],
            "status": ["in", ["Open", "In Progress"]],
            "docstatus": ["!=", 2],
        },
        fields=[
            "name", "patient", "patient_name", "inpatient_record",
            "posting_date", "shift_start_time", "shift_end_time",
        ],
    )

    if not nurse_records:
        return []

    # Filter to only nurse records whose shift covers the current time
    active_records = []
    for nr in nurse_records:
        if not nr.inpatient_record:
            continue

        shift_start = to_timedelta(nr.shift_start_time) if nr.shift_start_time else None
        shift_end = to_timedelta(nr.shift_end_time) if nr.shift_end_time else None

        if not shift_start or not shift_end:
            # No shift times defined — include it (backward compat)
            active_records.append(nr)
            continue

        posting = str(nr.posting_date)

        shift_start_str = str(shift_start).split(".")[0]
        shift_end_str = str(shift_end).split(".")[0]

        # Build shift start/end datetimes
        shift_start_dt = datetime.strptime(
            f"{posting} {shift_start_str}", "%Y-%m-%d %H:%M:%S"
        )

        if shift_end <= shift_start:
            # Overnight shift — shift_end is on the next day
            next_day = add_days(posting, 1)
            shift_end_dt = datetime.strptime(
                f"{next_day} {shift_end_str}", "%Y-%m-%d %H:%M:%S"
            )
        else:
            shift_end_dt = datetime.strptime(
                f"{posting} {shift_end_str}", "%Y-%m-%d %H:%M:%S"
            )

        if shift_start_dt <= now <= shift_end_dt:
            active_records.append(nr)

    results = []
    for nr in active_records:
        # Get pending IMO entries for this patient due within the window
        imo_list = frappe.db.get_all(
            "Inpatient Medication Order",
            filters={
                "patient": nr.patient,
                "inpatient_record": nr.inpatient_record,
                "docstatus": 1,
                "status": ["in", ["Pending", "In Process"]],
            },
            fields=["name"],
            pluck="name",
        )

        if not imo_list:
            continue

        upcoming = frappe.db.get_all(
            "Inpatient Medication Order Entry",
            filters=[
                ["parent", "in", imo_list],
                ["is_completed", "=", 0],
                ["date", "=", today],
                ["time", ">=", str(current_time)],
                ["time", "<=", str(cutoff_time)],
            ],
            fields=["drug_name", "drug", "time", "dosage", "dosage_form", "dose_uom"],
        )

        for med in upcoming:
            # Format time as HH:MM (zero-padded)
            t = med.time
            if hasattr(t, "strftime"):
                formatted_time = t.strftime("%H:%M")
            else:
                formatted_time = str(t).zfill(8)[:5]

            results.append({
                "patient": nr.patient,
                "patient_name": nr.patient_name,
                "drug_name": med.drug_name,
                "dosage": med.dosage,
                "dose_uom": med.dose_uom or "",
                "dosage_form": med.dosage_form or "",
                "scheduled_time": formatted_time,
                "nurse_record_name": nr.name,
            })

    return results


def create_imo_from_delivery_note(doc, method):
    """On submit of Delivery Note, create Dispensed Medication records.

    Creates one Dispensed Medication record per drug dispensed, to be picked
    up by nurses for scheduling in Inpatient Medication Orders.

    Only runs for admitted patients (those with an active inpatient_record).

    Args:
        doc: Delivery Note document
        method: Hook method name (on_submit)
    """

    if not frappe.db.get_value(
        "HMS TZ Setting", doc.company, "auto_create_imo_from_delivery_note"
    ):
        return

    if not doc.patient:
        return

    if doc.get("reference_doctype") != "Patient Encounter":
        return

    encounter_name = doc.get("reference_name")
    if not encounter_name:
        return

    inpatient_record = frappe.db.get_value(
        "Patient", doc.patient, "inpatient_record"
    )
    if not inpatient_record:
        return

    appointment = frappe.db.get_value(
        "Patient Encounter", encounter_name, "appointment"
    )

    created_count = 0
    for item in doc.items:
        ref_dt = item.get("reference_doctype")
        ref_dn = item.get("reference_name")

        if ref_dt != "Drug Prescription" or not ref_dn:
            continue

        dp = frappe.get_doc("Drug Prescription", ref_dn)

        try:
            dm = frappe.new_doc("Dispensed Medication")
            dm.patient = doc.patient
            dm.appointment = appointment or ""
            dm.company = doc.company
            dm.inpatient_record = inpatient_record
            dm.posting_date = doc.posting_date or nowdate()
            dm.delivery_note = doc.name
            dm.patient_encounter = encounter_name
            dm.drug_prescription = ref_dn
            dm.drug = dp.get("drug_code")
            dm.drug_name = dp.get("drug_name") or ""
            dm.dosage_form = dp.get("dosage_form") or ""
            dm.prescribed_dosage = dp.get("dosage") or ""
            dm.prescribed_period = dp.get("period") or ""
            dm.qty_dispensed = item.qty or 0
            dm.insert(ignore_permissions=True)
            created_count += 1
        except Exception:
            frappe.log_error(
                title="Dispensed Medication Creation Error",
                message=frappe.get_traceback(),
                reference_doctype="Delivery Note",
                reference_name=doc.name,
            )

    if created_count:
        frappe.msgprint(
            _(
                "{0} Dispensed Medication record(s) created from Delivery Note {1}. "
                "Nurses can now schedule medication administration."
            ).format(created_count, frappe.bold(doc.name)),
            alert=True,
        )


@frappe.whitelist()
def get_dispensed_medications(patient, inpatient_record):
    """Fetch all unscheduled Dispensed Medication records for a patient.

    Args:
        patient: Patient ID
        inpatient_record: Inpatient Record name

    Returns:
        list[dict]: Dispensed Medication records awaiting nurse scheduling.
    """
    data = frappe.get_all(
        "Dispensed Medication",
        filters={
            "patient": patient,
            "inpatient_record": inpatient_record,
        },
        fields=[
            "name",
            "drug",
            "drug_name",
            "dosage_form",
            "prescribed_dosage",
            "prescribed_period",
            "qty_dispensed",
            "dose_uom",
            "posting_date",
            "delivery_note",
            "patient_encounter",
        ],
        order_by="posting_date asc, creation asc",
    )

    return data

@frappe.whitelist()
def create_medication_schedule(
    dispensed_medication,
    total_administrable_qty,
    dose_per_administration,
    dose_uom,
    start_date,
    start_time,
    interval_hours,
):
    """Create medication schedule entries in an IMO from nurse input.

    This function:
    1. Calculates the total number of doses from qty and dose.
    2. Finds or creates a submitted IMO for the encounter.
    3. Appends schedule entries to the IMO.
    4. Deletes the Dispensed Medication record.

    Args:
        dispensed_medication: Name of the Dispensed Medication record
        total_administrable_qty: Total usable qty in dose_uom
        dose_per_administration: Amount per dose
        dose_uom: Unit of measurement (ml, mg, Tablet, etc.)
        start_date: Schedule start date
        start_time: Schedule start time (HH:MM or HH:MM:SS)
        interval_hours: Hours between doses

    Returns:
        dict: Result with status, imo_name, total_doses, end_date
    """
    dm = frappe.get_doc("Dispensed Medication", dispensed_medication)

    total_administrable_qty = flt(total_administrable_qty)
    dose_per_administration = flt(dose_per_administration)
    interval_hours = cint(interval_hours)

    if dose_per_administration <= 0:
        frappe.throw(_("Dose per administration must be greater than zero."))

    if interval_hours <= 0:
        frappe.throw(_("Interval hours must be greater than zero."))

    if total_administrable_qty <= 0:
        frappe.throw(_("Total administrable quantity must be greater than zero."))

    total_doses = math.floor(total_administrable_qty / dose_per_administration)
    if total_doses <= 0:
        frappe.throw(
            _("Cannot create a schedule: total quantity ({0}) is less than "
              "one dose ({1}).").format(total_administrable_qty, dose_per_administration)
        )

    # Generate all schedule entries
    entries = _generate_schedule_entries(
        drug=dm.drug,
        drug_name=dm.drug_name,
        dosage_form=dm.dosage_form,
        dose_per_administration=dose_per_administration,
        dose_uom=dose_uom,
        start_date=start_date,
        start_time=start_time,
        interval_hours=interval_hours,
        total_doses=total_doses,
        drug_prescription=dm.drug_prescription,
    )

    # Find or create IMO for this encounter
    encounter_name = dm.patient_encounter
    imo_name = frappe.db.get_value(
        "Inpatient Medication Order",
        {"patient_encounter": encounter_name, "docstatus": 1},
        "name",
    )

    if imo_name:
        # Append to existing submitted IMO
        imo = frappe.get_doc("Inpatient Medication Order", imo_name)
        for entry in entries:
            imo.append("medication_orders", entry)

        imo.total_orders = len(imo.medication_orders)
        # Recalculate end_date from the last entry
        if imo.medication_orders:
            imo.end_date = max(str(e.date) for e in imo.medication_orders)

        imo.flags.ignore_validate_update_after_submit = True
        imo.set_total_orders()
        imo.set_status()
        imo.save(ignore_permissions=True)
    else:
        # Create new IMO and submit it
        imo = frappe.new_doc("Inpatient Medication Order")
        imo.patient = dm.patient
        imo.patient_name = frappe.db.get_value(
            "Patient", dm.patient, "patient_name"
        ) or ""
        imo.inpatient_record = dm.inpatient_record
        imo.patient_encounter = encounter_name
        imo.company = dm.company
        imo.start_date = start_date

        for entry in entries:
            imo.append("medication_orders", entry)

        imo.total_orders = len(entries)
        imo.end_date = entries[-1]["date"] if entries else start_date

        imo.insert(ignore_permissions=True)
        imo.set_status()
        imo.submit()
        imo_name = imo.name

    end_date = entries[-1]["date"] if entries else start_date
    remainder = total_administrable_qty - (total_doses * dose_per_administration)

    # Delete the Dispensed Medication record — it has been scheduled
    frappe.delete_doc(
        "Dispensed Medication", dispensed_medication, ignore_permissions=True
    )

    return {
        "status": "success",
        "imo_name": imo_name,
        "total_doses": total_doses,
        "end_date": end_date,
        "remainder": remainder,
    }


def _generate_schedule_entries(
    drug,
    drug_name,
    dosage_form,
    dose_per_administration,
    dose_uom,
    start_date,
    start_time,
    interval_hours,
    total_doses,
    drug_prescription="",
):
    """Generate IMO Entry rows for a medication schedule.

    Args:
        drug: Item code
        drug_name: Item name
        dosage_form: Dosage Form name
        dose_per_administration: Amount per dose
        dose_uom: Unit of measurement
        start_date: Start date string (YYYY-MM-DD)
        start_time: Start time string (HH:MM or HH:MM:SS)
        interval_hours: Hours between doses
        total_doses: Total number of dose entries to create
        drug_prescription: Reference Drug Prescription name

    Returns:
        list[dict]: Schedule entries ready to append to IMO.
    """
    from datetime import datetime, timedelta

    # Parse start datetime
    if len(start_time) == 5:
        start_time += ":00"

    start_dt = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M:%S")
    interval = timedelta(hours=interval_hours)

    entries = []
    current_dt = start_dt

    for _ in range(total_doses):
        entry_date = current_dt.strftime("%Y-%m-%d")
        entry_time = current_dt.strftime("%H:%M:00")

        entries.append({
            "drug": drug,
            "drug_name": drug_name,
            "dosage": dose_per_administration,
            "dosage_form": dosage_form,
            "date": entry_date,
            "time": entry_time,
            "dose_uom": dose_uom,
            "interval_hours": interval_hours,
            "ref_doctype": "Drug Prescription",
            "ref_docname": drug_prescription,
        })

        current_dt += interval

    return entries

