"""Make Inpatient Record.patient_appointment unique.

One Patient Appointment has one Inpatient Record. A double click on Order
Admission could create two records from one encounter. The encounter keeps a
link to the second record only, and the first record is an orphan that the
billing reports count again.
"""

import frappe
from frappe.query_builder import DocType
from frappe.query_builder.functions import Count


def execute():
	custom_field = frappe.db.get_value(
		"Custom Field", {"dt": "Inpatient Record", "fieldname": "patient_appointment"}, "name"
	)
	if not custom_field:
		return

	custom_field = frappe.get_doc("Custom Field", custom_field)
	if custom_field.unique:
		return

	inpatient_record = DocType("Inpatient Record")
	frappe.qb.update(inpatient_record).set(inpatient_record.patient_appointment, None).where(
		inpatient_record.patient_appointment == ""
	).run()

	for appointment in get_duplicated_appointments():
		delete_orphan_records(appointment)

	remaining = get_duplicated_appointments()
	if remaining:
		frappe.throw(
			f"Patient Appointments with more than one Inpatient Record: {', '.join(remaining)}. "
			"Keep one Inpatient Record for each appointment, then run the migration again."
		)

	custom_field.unique = 1
	custom_field.save(ignore_permissions=True)


def get_duplicated_appointments() -> list[str]:
	inpatient_record = DocType("Inpatient Record")
	return (
		frappe.qb.from_(inpatient_record)
		.select(inpatient_record.patient_appointment)
		.where(inpatient_record.patient_appointment.isnotnull())
		.groupby(inpatient_record.patient_appointment)
		.having(Count("*") > 1)
	).run(pluck=True)


def delete_orphan_records(appointment: str):
	"""Delete records of a double-submitted admission order.

	A record is an orphan when its admission encounter links to another record of
	the same appointment, no encounter links to it, and the patient was never admitted.
	"""
	records = frappe.get_all(
		"Inpatient Record",
		filters={"patient_appointment": appointment},
		fields=["name", "status", "admission_encounter"],
	)
	names = {record.name for record in records}

	for record in records:
		kept_record = frappe.db.get_value("Patient Encounter", record.admission_encounter, "inpatient_record")
		if not is_orphan(record, kept_record, names):
			continue

		frappe.delete_doc("Inpatient Record", record.name, ignore_permissions=True)
		print(f"Deleted orphan Inpatient Record {record.name}, kept {kept_record} for {appointment}")


def is_orphan(record: dict, kept_record: str | None, names: set[str]) -> bool:
	return (
		record.status == "Admission Scheduled"
		and kept_record in names
		and kept_record != record.name
		and not frappe.db.exists("Patient Encounter", {"inpatient_record": record.name})
		and not frappe.db.exists("Inpatient Occupancy", {"parent": record.name})
		and not frappe.db.exists("Patient", {"inpatient_record": record.name})
	)
