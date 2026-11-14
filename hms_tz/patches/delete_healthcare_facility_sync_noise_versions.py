import json

import frappe

DOCTYPE = "Healthcare Facility"

# the facility sync re-saved every facility because the API sends these untyped
ZERO_OR_NULL_FIELDS = {"percent_sent", "has_eclaims", "send_amount_to_msd"}


def execute():
	frappe.enqueue(delete_noise_versions, queue="long", timeout=3600, enqueue_after_commit=True)


def delete_noise_versions():
	version = frappe.qb.DocType("Version")

	# one facility at a time keeps every query on the (ref_doctype, docname) index
	for docname in frappe.get_all(DOCTYPE, pluck="name"):
		versions = (
			frappe.qb.from_(version)
			.select(version.name, version.data)
			.where((version.ref_doctype == DOCTYPE) & (version.docname == docname))
			.run(as_dict=True)
		)

		if noise := [v.name for v in versions if is_noise(json.loads(v.data))]:
			frappe.db.delete("Version", {"name": ("in", noise)})
			frappe.db.commit()


def is_noise(data):
	if any(value for key, value in data.items() if key != "changed"):
		return False

	return bool(data.get("changed")) and all(is_noise_change(*change) for change in data["changed"])


def is_noise_change(fieldname, old, new):
	if fieldname == "classification_id":
		return str(old) == str(new)

	return fieldname in ZERO_OR_NULL_FIELDS and not old and not new
