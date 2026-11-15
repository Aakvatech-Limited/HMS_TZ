"""Move inline Signature field values into the signature store (hms_tz/signatures.py).

Not in patches.txt: run it by hand, in a quiet hour, e.g. in screen:

    bench --site SITE execute hms_tz.patches.move_signatures_to_store.audit    # fix what it lists first
    bench --site SITE execute hms_tz.patches.move_signatures_to_store.enable   # new saves store signatures
    bench --site SITE execute hms_tz.patches.move_signatures_to_store.estimate
    bench --site SITE execute hms_tz.patches.move_signatures_to_store.execute
    bench --site SITE execute hms_tz.patches.move_signatures_to_store.verify

- Re-runnable: a run only picks up values still inline. If replicas fall behind, throttle it with
  `--kwargs "{'pause': 0.2}"` (seconds between batches of 200 rows).
- Writes no Versions and doesn't change `modified`: the documents keep the same images.
- Small binlog: each UPDATE checks the old value by its MD5 instead of the value itself, so a
  replicated statement is ~150 bytes, not the image.
- Tables don't shrink by themselves: afterwards rebuild them on each server
  (`ALTER TABLE ... FORCE, ALGORITHM=INPLACE, LOCK=NONE`, with `sql_log_bin=0` where replicas rebuild
  on their own).
- The database now needs private/files/hms_signatures: sync it wherever the database goes (replicas,
  backups, copies), then run `verify` there.
- Files no document points to any more (re-drawn or deleted signatures) can be removed with `prune`.
- Undo with `disable`, then `restore`. Unlike `execute`, `restore` writes the images into the binlog.
"""

import os
import re
import time
from hashlib import md5

import frappe
from frappe.installer import update_site_config
from frappe.query_builder import CustomFunction
from frappe.query_builder.functions import Count, Sum
from frappe.utils import get_files_path

from hms_tz import signatures
from hms_tz.signatures import POINTER, get_path, get_signature_fields, is_enabled, resolve_signature, store

BATCH_SIZE = 200
MD5 = CustomFunction("MD5", ["value"])
POINTER_IN_TEXT = re.compile(r"sig:[0-9a-f]{64}\.(?:png|jpg|txt)")
LENGTH = CustomFunction("LENGTH", ["value"])


def get_columns(stored=True):
	"""(doctype, fieldname) of Signature fields: those stored (see signatures.APPS), or all of them."""
	doctypes = set(frappe.get_all("DocField", {"fieldtype": "Signature"}, pluck="parent"))
	doctypes.update(frappe.get_all("Custom Field", {"fieldtype": "Signature"}, pluck="dt"))
	return [
		(doctype, fieldname)
		for doctype in sorted(doctypes)
		if frappe.db.exists("DocType", doctype)
		for fieldname in get_signature_fields(frappe.get_meta(doctype), stored=stored)
		if frappe.db.has_column(doctype, fieldname)
	]


# Customisations stored in the database, and their fields holding code or templates
CUSTOMISATIONS = {
	"Print Format": ["html", "format_data"],
	"Letter Head": ["content", "footer"],
	"Server Script": ["script"],
	"Client Script": ["script"],
	"Report": ["query", "report_script", "javascript"],
	"Notification": ["message", "condition", "subject"],
	"Email Template": ["response", "response_html", "subject"],
}


def audit():
	"""Print customisations in the database that mention a stored signature field. Review them first.

	`doc.<field>` in a print format of the same doctype is fine (before_print puts the image back), but
	a signature read from the database (`frappe.db.get_value` of another document, a report query, a
	notification's `doc.<field>`) is a pointer now and must go through `resolve_signature()`.
	"""
	fieldnames = {fieldname for _doctype, fieldname in get_columns()}
	found = []
	for doctype, fields in CUSTOMISATIONS.items():
		columns = [field for field in fields if frappe.db.has_column(doctype, field)]
		for row in frappe.get_all(doctype, fields=["name", *columns]):
			text = " ".join(row.get(column) or "" for column in columns)
			if mentioned := sorted(fieldname for fieldname in fieldnames if fieldname in text):
				found.append((doctype, row.name, mentioned))

	for doctype, name, mentioned in found:
		print(f"{doctype} {name}: {', '.join(mentioned)}")
	print(f"{len(found)} to review")
	return found


def enable(force=False):
	"""Turn the store on (site config `hms_tz_signature_store`), if `audit` lists nothing left to review.

	Pass `--kwargs "{'force': 1}"` once the listed customisations are fixed or known to be fine.
	"""
	if (found := audit()) and not force:
		frappe.throw(f"Review the {len(found)} customisations above first, then run with force=1")
	update_site_config("hms_tz_signature_store", 1)
	print("Signature store on")


def disable():
	"""Turn the store off. Stored signatures keep being shown; new saves keep images inline."""
	update_site_config("hms_tz_signature_store", 0)
	print("Signature store off")


def estimate():
	"""Print what `execute` would move. Reads every value once."""
	for doctype, fieldname in get_columns():
		table = frappe.qb.DocType(doctype)
		column = table[fieldname]
		rows, size, distinct = (
			frappe.qb.from_(table)
			.select(Count("*"), Sum(LENGTH(column)), Count(MD5(column)).distinct())
			.where(column.like("data:%"))
		).run()[0]
		print(f"{doctype}.{fieldname}: {rows} inline ({distinct} distinct), {(size or 0) / 2**20:.1f} MB")


def execute(pause=0):
	if not is_enabled():
		frappe.throw("Turn on hms_tz_signature_store first, or new saves keep writing images inline")

	for doctype, fieldname in get_columns():
		move_column(doctype, fieldname, pause)


def move_column(doctype, fieldname, pause=0):
	"""Store the inline values of one column, in batches by name."""
	table = frappe.qb.DocType(doctype)
	column = table[fieldname]
	moved = 0

	for name, value in get_rows(table, column, "data:%"):
		pointer = store(value)
		# only if unchanged since read; MD5 keeps the image out of the binlog
		frappe.qb.update(table).set(column, pointer).where(
			(table.name == name) & (MD5(column) == md5(value.encode()).hexdigest())
		).run()
		moved += 1
		if moved % BATCH_SIZE == 0:
			frappe.db.commit()
			time.sleep(pause)

	frappe.db.commit()
	print(f"{doctype}.{fieldname}: moved {moved}")
	return moved


def verify():
	"""Print pointers whose signature file is missing, e.g. on a replica or a restored backup."""
	missing = []
	for doctype, fieldname in get_columns(stored=False):
		table = frappe.qb.DocType(doctype)
		for name, value in get_rows(table, table[fieldname], "sig:%"):
			match = POINTER.match(value.strip())
			if not match or not os.path.exists(get_path(*match.groups())):
				missing.append((doctype, name, fieldname, value))

	for row in missing:
		print("missing:", *row)
	print(f"{len(missing)} missing")
	return missing


def prune(delete=False, min_age_days=1):
	"""List signature files no document points to, and delete them with `--kwargs "{'delete': 1}"`.

	A pointer counts if it is in any Signature field, or in a Deleted Document (so restoring it brings
	its signature back). Versions don't count: they only show the pointer, not the image. Files newer
	than `min_age_days` are kept, as a save may have written one without committing yet.
	"""
	in_use = get_pointers_in_use()
	cutoff = time.time() - min_age_days * 86400
	unused = [
		entry for entry in get_files() if f"sig:{entry.name}" not in in_use and entry.stat().st_mtime < cutoff
	]

	size = sum(entry.stat().st_size for entry in unused)
	if delete:
		for entry in unused:
			os.remove(entry.path)
	print(f"{len(unused)} unused files, {size / 2**20:.1f} MB{' deleted' if delete else ''}")
	return [entry.name for entry in unused]


def get_pointers_in_use():
	pointers = set()
	for doctype, fieldname in get_columns(stored=False):
		table = frappe.qb.DocType(doctype)
		pointers.update(value.strip() for _name, value in get_rows(table, table[fieldname], "sig:%"))

	deleted_document = frappe.qb.DocType("Deleted Document")
	for _name, data in get_rows(deleted_document, deleted_document.data, "%sig:%"):
		pointers.update(POINTER_IN_TEXT.findall(data))
	return pointers


def get_files():
	"""Files in the signature store (temporary ones included)."""
	folder = get_files_path(signatures.FOLDER, is_private=True)
	if not os.path.isdir(folder):
		return []
	return [
		entry
		for subfolder in os.scandir(folder)
		if subfolder.is_dir()
		for entry in os.scandir(subfolder.path)
		if entry.is_file()
	]


def restore():
	"""Put the images back inline."""
	if is_enabled():
		frappe.throw("Turn off hms_tz_signature_store first, or saves store the images again")

	for doctype, fieldname in get_columns(stored=False):
		table = frappe.qb.DocType(doctype)
		column = table[fieldname]
		restored = 0
		for name, pointer in get_rows(table, column, "sig:%"):
			frappe.qb.update(table).set(column, resolve_signature(pointer)).where(
				(table.name == name) & (column == pointer)
			).run()
			restored += 1
			if restored % BATCH_SIZE == 0:
				frappe.db.commit()
		frappe.db.commit()
		print(f"{doctype}.{fieldname}: restored {restored}")


def get_rows(table, column, pattern):
	"""(name, value) of rows whose value matches `pattern`, fetched in batches by name."""
	last_name = ""
	while rows := (
		frappe.qb.from_(table)
		.select(table.name, column)
		.where((table.name > last_name) & column.like(pattern))
		.orderby(table.name)
		.limit(BATCH_SIZE)
	).run():
		yield from rows
		last_name = rows[-1][0]
