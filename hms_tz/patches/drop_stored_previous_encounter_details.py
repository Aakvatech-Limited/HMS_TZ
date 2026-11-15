import frappe

from hms_tz.nhif.api.patient_encounter import PREVIOUS_TABLES

BATCH_SIZE = 500
BATCHES_PER_JOB = 40


def execute():
	"""Drop the previous encounter details that duplicated encounters used to store.

	They are derived from the duplicate chain on load now, so the stored copies are unused.
	"""
	meta = frappe.get_meta("Patient Encounter")
	for previous_table in PREVIOUS_TABLES.values():
		drop_rows(meta.get_options(previous_table), previous_table)

	enqueue_next()


def drop_rows(doctype, parentfield):
	table = frappe.qb.DocType(doctype)
	is_encounter_row = (table.parenttype == "Patient Encounter") & (table.parentfield == parentfield)
	if not frappe.qb.from_(table).select(table.name).where(~is_encounter_row).limit(1).run():
		frappe.db.truncate(doctype)
		return

	# also used by other parents (e.g. Inpatient Record): delete only the encounter rows
	while (
		names := frappe.qb.from_(table)
		.select(table.name)
		.where(is_encounter_row)
		.limit(10_000)
		.run(pluck=True)
	):
		frappe.qb.from_(table).delete().where(table.name.isin(names)).run()
		frappe.db.commit()


def enqueue_next(name=""):
	frappe.enqueue(
		"hms_tz.patches.drop_stored_previous_encounter_details.clear_previous_notes",
		queue="long",
		timeout=3600,
		job_id=f"drop_stored_previous_encounter_details:{name}",
		deduplicate=True,
		enqueue_after_commit=True,
		name=name,
	)


def clear_previous_notes(name=""):
	"""Clear the stored previous notes in name order, a batch at a time, then queue the next run."""
	encounter = frappe.qb.DocType("Patient Encounter")
	for _ in range(BATCHES_PER_JOB):
		names = (
			frappe.qb.from_(encounter)
			.select(encounter.name)
			.where((encounter.name > name) & (encounter.hms_tz_previous_examination_detail != ""))
			.orderby(encounter.name)
			.limit(BATCH_SIZE)
		).run(pluck=True)
		if not names:
			return

		frappe.qb.update(encounter).set(encounter.hms_tz_previous_examination_detail, None).where(
			encounter.name.isin(names)
		).run()
		frappe.db.commit()
		name = names[-1]

	enqueue_next(name)
