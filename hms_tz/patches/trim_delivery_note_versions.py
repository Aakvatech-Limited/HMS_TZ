import json
from collections import Counter

import frappe

BATCH_SIZE = 500
BATCHES_PER_JOB = 40

# Bookkeeping, fields set by code, and stock levels recomputed on every save: no user information.
IGNORED_ROW_FIELDS = {
	"name",
	"idx",
	"creation",
	"modified",
	"owner",
	"modified_by",
	"parent",
	"parentfield",
	"parenttype",
	"docstatus",
	"__islocal",
	"__unsaved",
	"original_item",
	"original_stock_uom_qty",
	"actual_qty",
	"company_total_stock",
}


def execute():
	"""Delete Delivery Note Versions that hold no user change, and drop the re-added item rows from the rest.

	Before the original items fix, after_insert saved every Delivery Note a second time and each save
	re-inserted all item rows, so most Delivery Note Versions only list the snapshot and re-added rows.
	"""
	enqueue_next()


def enqueue_next(docname="", name=""):
	frappe.enqueue(
		"hms_tz.patches.trim_delivery_note_versions.trim_versions",
		queue="long",
		timeout=3600,
		job_id=f"trim_delivery_note_versions:{docname}:{name}",
		deduplicate=True,
		enqueue_after_commit=True,
		docname=docname,
		name=name,
	)


def trim_versions(docname="", name=""):
	"""Walk the Delivery Note Versions in index order, a batch at a time, then queue the next run."""
	version = frappe.qb.DocType("Version")
	for _ in range(BATCHES_PER_JOB):
		rows = (
			frappe.qb.from_(version)
			.select(version.name, version.docname, version.data)
			.where(
				(version.ref_doctype == "Delivery Note")
				& ((version.docname > docname) | ((version.docname == docname) & (version.name > name)))
			)
			.orderby(version.docname)
			.orderby(version.name)
			.limit(BATCH_SIZE)
		).run(as_dict=True)
		if not rows:
			return

		manual_time = set(
			frappe.get_all(
				"Delivery Note",
				filters={"name": ("in", {row.docname for row in rows}), "set_posting_time": 1},
				pluck="name",
			)
		)
		redundant = []
		for row in rows:
			if is_redundant(row.data, row.docname not in manual_time):
				redundant.append(row.name)
			elif (data := drop_re_added_rows(row.data)) is not None:
				frappe.db.set_value("Version", row.name, "data", data, update_modified=False)
		if redundant:
			frappe.qb.from_(version).delete().where(version.name.isin(redundant)).run()
		frappe.db.commit()

		docname, name = rows[-1].docname, rows[-1].name

	enqueue_next(docname, name)


def is_redundant(data, auto_posting_time=True):
	"""True when the Version records no user change: only re-added item rows, the original items
	snapshot, recomputed stock levels, empty-to-zero changes, or posting time that the draft set
	itself (`auto_posting_time`: the Delivery Note doesn't have Edit Posting Date and Time)."""
	diff = json.loads(data or "{}")
	added = Counter(get_row_key(table, row) for table, row in diff.get("added") or [])
	removed = Counter(get_row_key(table, row) for table, row in diff.get("removed") or [])
	if removed - added or has_field_changes(diff, auto_posting_time):
		return False
	return all(table == "hms_tz_original_items" for table, _ in added - removed)


def drop_re_added_rows(data):
	"""The Version data without item rows that were only removed and added back (same values, new
	names), in Frappe's compact Version format. None if there are none; other changes are kept as is."""
	diff = json.loads(data or "{}")
	added, removed = diff.get("added") or [], diff.get("removed") or []
	re_added = Counter(get_row_key(table, row) for table, row in added) & Counter(
		get_row_key(table, row) for table, row in removed
	)
	if not re_added:
		return None
	diff["added"] = drop_rows(added, re_added)
	diff["removed"] = drop_rows(removed, re_added)
	return frappe.as_json(diff, indent=None, separators=(",", ":"))


def drop_rows(rows, to_drop):
	to_drop = Counter(to_drop)
	kept = []
	for table, row in rows:
		key = get_row_key(table, row)
		if to_drop[key]:
			to_drop[key] -= 1
		else:
			kept.append([table, row])
	return kept


def get_row_key(table, row):
	values = {key: value for key, value in row.items() if key not in IGNORED_ROW_FIELDS}
	return table, json.dumps(values, sort_keys=True, default=str)


def has_field_changes(diff, auto_posting_time):
	ignored = {"posting_time"} if auto_posting_time else set()
	changes = [change for change in diff.get("changed") or [] if change[0] not in ignored]
	for _table, _idx, _name, row_changes in diff.get("row_changed") or []:
		changes += [change for change in row_changes if change[0] not in IGNORED_ROW_FIELDS]
	return any(not is_same(old, new) for _field, old, new in changes)


def is_same(old, new):
	try:
		return float(old or 0) == float(new or 0)
	except (TypeError, ValueError):
		return (old or "") == (new or "")
