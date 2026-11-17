from collections import defaultdict

import frappe
from frappe.query_builder import CustomFunction
from frappe.utils import time_diff_in_seconds

ENCOUNTERS_PER_BATCH = 200
BATCHES_PER_JOB = 40
MD5 = CustomFunction("MD5", ["value"])


def execute():
	"""Delete the duplicate Version written when a new Patient Encounter was saved twice.

	after_insert used to save the encounter again: that save wrote a Version, and the insert wrote the
	same one again. A Version is deleted only if the one before it, for the same encounter, holds the
	same data and was written within seconds of it.
	"""
	enqueue_next()


def enqueue_next(docname=""):
	frappe.enqueue(
		"hms_tz.patches.delete_duplicate_patient_encounter_versions.delete_duplicates",
		queue="long",
		timeout=3600,
		job_id=f"delete_duplicate_patient_encounter_versions:{docname}",
		deduplicate=True,
		enqueue_after_commit=True,
		docname=docname,
	)


def delete_duplicates(docname=""):
	"""Walk the encounters with Versions in name order, a batch at a time, then queue the next run."""
	version = frappe.qb.DocType("Version")
	for _ in range(BATCHES_PER_JOB):
		docnames = (
			frappe.qb.from_(version)
			.select(version.docname)
			.where((version.ref_doctype == "Patient Encounter") & (version.docname > docname))
			.groupby(version.docname)
			.orderby(version.docname)
			.limit(ENCOUNTERS_PER_BATCH)
		).run(pluck=True)
		if not docnames:
			return

		versions = (
			frappe.qb.from_(version)
			.select(version.name, version.docname, version.creation, MD5(version.data).as_("hash"))
			.where((version.ref_doctype == "Patient Encounter") & version.docname.isin(docnames))
			.orderby(version.creation)
		).run(as_dict=True)
		if duplicates := get_duplicates(versions):
			frappe.qb.from_(version).delete().where(version.name.isin(duplicates)).run()
		frappe.db.commit()

		docname = docnames[-1]

	enqueue_next(docname)


def get_duplicates(versions):
	"""Names of Versions repeating the one before them (same encounter, same data, within 5 seconds)."""
	by_encounter = defaultdict(list)
	for version in versions:
		by_encounter[version.docname].append(version)

	return [
		version.name
		for encounter_versions in by_encounter.values()
		for previous, version in zip(encounter_versions, encounter_versions[1:], strict=False)
		if version.hash == previous.hash and time_diff_in_seconds(version.creation, previous.creation) <= 5
	]
