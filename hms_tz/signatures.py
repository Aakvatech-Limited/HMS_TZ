"""Signature fields stored once on disk, referenced from documents.

A Signature field holds a `data:image/png;base64,...` image of 10-20 KB. The same signature gets copied
onto many rows (a practitioner's, fetched onto every encounter), so most of that is duplicated.

With the store on, a save writes each distinct signature once, to `private/files/hms_signatures/<ab>/<sha256>.<ext>`,
and keeps the pointer `sig:<sha256>.<ext>` in the column. The file is named by the hash of the signature,
so it is never changed or removed: a re-drawn signature gets a new file, and documents keep the one they
were signed with even if the master changes or is deleted. Files are kept in subfolders by the first two
characters of the hash, so no folder gets too large to list or sync.

- Writing pointers is behind the site config flag `hms_tz_signature_store`, for doctypes of APPS.
- Code reading a signature from the database directly (e.g. a print format using frappe.db.get_value
  for a practitioner's signature) must call `resolve_signature()`; move_signatures_to_store.audit
  lists such customisations on a site.
- Reading pointers always works, so turning the flag off never breaks documents already stored:
  `onload` and `before_print` put the images back on the document, `resolve_signature()` does it for
  one value (API payloads, print formats that read a master), and the Signature control resolves
  pointers in the browser (public/js/signature/signature_control.js).
- The files are part of the data now: back up and sync `private/files/hms_signatures` with the database.

Existing values are moved by hms_tz/patches/move_signatures_to_store.py, run by hand.
"""

import os
import re
from base64 import b64decode, b64encode
from hashlib import sha256

import frappe
from frappe import _
from frappe.utils import cint, get_files_path

# Apps whose doctypes have their Signature fields stored. At some sites healthcare doctypes are
# moved into the Hms Tz module, so both apps are listed.
APPS = {"hms_tz", "healthcare"}
FOLDER = "hms_signatures"
POINTER = re.compile(r"^sig:([0-9a-f]{64})\.(png|jpg|txt)$")
INLINE = re.compile(r"^data:\s*([\w.+/-]*)\s*;base64,(.*)$", re.IGNORECASE | re.DOTALL)
# Images stored as image files (smaller than base64); anything else is kept as is in a .txt file
EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/jpg": "jpg"}
MIME_TYPES = {"png": "image/png", "jpg": "image/jpeg"}


def is_enabled():
	return bool(cint(frappe.conf.get("hms_tz_signature_store")))


def is_pointer(value):
	return bool(value) and bool(POINTER.match(value.strip()))


def is_inline(value):
	return bool(value) and value.lstrip()[:5].lower() == "data:"


def store(value):
	"""Write a signature to the store and return its pointer; writing the same signature again is a no-op.

	The file is written before the transaction commits and is kept on rollback: an unused file is
	harmless, a committed pointer without a file would lose the signature.
	"""
	value = value.strip()
	digest = sha256(value.encode()).hexdigest()
	extension, content = get_file_content(value)
	path = get_path(digest, extension)

	if not os.path.exists(path):
		os.makedirs(os.path.dirname(path), exist_ok=True)
		# write then rename, so a reader never sees half a file; fsync first, so that after a crash the
		# rename can't be on disk without the content
		tmp_path = f"{path}.{frappe.generate_hash(length=8)}.tmp"
		try:
			with open(tmp_path, "wb") as f:
				f.write(content)
				f.flush()
				os.fsync(f.fileno())
			os.replace(tmp_path, path)
		finally:
			if os.path.exists(tmp_path):
				os.remove(tmp_path)

	return f"sig:{digest}.{extension}"


def get_value_to_save(value):
	"""The value to save for a Signature field: its pointer if the store is on, else as it is.

	For code saving a signature without validate (e.g. db_set); saves through validate get it from dehydrate.
	"""
	return store(value) if is_enabled() and is_inline(value) else value


def resolve_signature(value):
	"""The image for a Signature field value: the stored file for a pointer, anything else unchanged.

	Raises if the file of a pointer is missing: a document must not leave the system (print, NHIF)
	without its signature.
	"""
	if not is_pointer(value):
		return value or ""

	digest, extension = POINTER.match(value.strip()).groups()
	path = get_path(digest, extension)
	if not os.path.exists(path):
		frappe.throw(
			_("Signature file {0} is missing from the signature store").format(os.path.basename(path)),
			frappe.DoesNotExistError,
		)

	with open(path, "rb") as f:
		content = f.read()

	if extension == "txt":
		return content.decode()
	return f"data:{MIME_TYPES[extension]};base64,{b64encode(content).decode()}"


def get_file_content(value):
	"""(extension, bytes) to store: png/jpg images decoded, anything else as is."""
	match = INLINE.match(value)
	if match and (extension := EXTENSIONS.get(match.group(1).lower())):
		try:
			if content := b64decode(match.group(2), validate=False):
				return extension, content
		except ValueError:
			pass

	return "txt", value.encode()


def get_path(digest, extension):
	# in subfolders by the first two characters of the hash (like git objects): 256 folders, so none gets
	# too large to list, back up or sync
	return get_files_path(FOLDER, digest[:2], f"{digest}.{extension}", is_private=True)


def get_signature_fields(meta, stored=True):
	"""Signature fields of a doctype, custom fields included; with `stored`, only those whose values are stored.

	Values are stored for doctypes of APPS, but pointers are read on any Signature field, as copying
	a value (fetch_from, code) copies a pointer too.
	"""
	if meta.issingle or meta.is_virtual:
		return []
	if stored and frappe.local.module_app.get(frappe.scrub(meta.module or "")) not in APPS:
		return []
	return [df.fieldname for df in meta.get("fields", {"fieldtype": "Signature"})]


def get_docs(doc):
	"""The document and its child rows."""
	return [doc, *doc.get_all_children()]


def dehydrate(doc, method=None):
	"""Store inline signatures and keep their pointers on the document.

	Runs on validate (after fetch_from) and before_update_after_submit (the form sends back the images
	it was given on load, and must not change a submitted document).
	"""
	if not is_enabled():
		return

	doc_before_save = doc.get_doc_before_save()
	for d in get_docs(doc):
		for fieldname in get_signature_fields(d.meta):
			if not is_inline(value := d.get(fieldname)):
				continue

			saved = get_saved_row(doc_before_save, d)
			saved_value = saved.get(fieldname) if saved else None
			if is_unchanged(saved_value, value):
				# the image the form got on load: keep its pointer
				d.set(fieldname, saved_value)
				continue

			pointer = store(value)
			d.set(fieldname, pointer)
			if saved_value == value:
				# saved inline before the store was on: not a change, so keep it out of the Version
				saved.set(fieldname, pointer)


def get_saved_row(doc_before_save, d):
	"""The saved version of a document or child row, if any."""
	if not doc_before_save or d.doctype == doc_before_save.doctype:
		return doc_before_save
	return next((row for row in doc_before_save.get(d.parentfield) or [] if row.name == d.name), None)


def is_unchanged(saved_value, value):
	"""Whether `value` is the image of the saved pointer."""
	if not is_pointer(saved_value):
		return False
	if sha256(value.strip().encode()).hexdigest() == POINTER.match(saved_value.strip()).group(1):
		return True  # the text it was stored from
	try:  # the same image written differently, e.g. as resolve_signature rebuilds it
		return resolve_signature(saved_value) == value.strip()
	except frappe.DoesNotExistError:
		return False


def hydrate(doc, method=None, *args):
	"""Put the images back on a document that is shown or printed, never saved.

	A missing file stops a print, but not the form: it opens with the pointer left as it is (so a save
	keeps it, and restoring the file restores the signature), and the loss is logged.
	"""
	for d in get_docs(doc):
		for fieldname in get_signature_fields(d.meta, stored=False):
			if not is_pointer(value := d.get(fieldname)):
				continue
			if method == "before_print":
				d.set(fieldname, resolve_signature(value))
				continue
			try:
				d.set(fieldname, resolve_signature(value))
			except frappe.DoesNotExistError:
				frappe.clear_last_message()
				frappe.log_error(f"Signature missing: {d.doctype} {d.name} {fieldname}", value)


@frappe.whitelist()
def get_signature(
	pointer: str, doctype: str, fieldname: str, name: str | None = None, source_name: str | None = None
):
	"""The image of a pointer, for the Signature control, if the user may read a document holding it;
	None if its file is missing.

	A signature is as readable as the document field it is in. So the pointer must be the value of
	`fieldname` in document `name`, or, for a value fetched in the form (fetch_from, e.g. a new
	encounter's practitioner signature), in the document it is fetched from, `source_name`.
	"""
	if not is_pointer(pointer):
		frappe.throw(_("Not a signature pointer"), frappe.ValidationError)

	meta = frappe.get_meta(doctype)
	if fieldname not in get_signature_fields(meta, stored=False):
		raise frappe.PermissionError

	fetch_from = meta.get_field(fieldname).fetch_from
	if not (name and holds(doctype, name, fieldname, pointer)) and not (
		source_name and fetch_from and holds_fetched(meta, fetch_from, source_name, pointer)
	):
		raise frappe.PermissionError

	try:
		return resolve_signature(pointer)
	except frappe.DoesNotExistError:
		frappe.clear_last_message()  # the control says so, without retrying
		return None


def holds_fetched(meta, fetch_from, source_name, pointer):
	"""Whether the document a field fetches from holds `pointer`; raises if the user may not read it."""
	link_fieldname, source_fieldname = fetch_from.split(".", 1)
	source_doctype = meta.get_options(link_fieldname)
	return bool(source_doctype) and holds(source_doctype, source_name, source_fieldname, pointer)


def holds(doctype, name, fieldname, pointer):
	"""Whether field `fieldname` of a document holds `pointer`; raises if the user may not read it."""
	meta = frappe.get_meta(doctype)
	fields = [fieldname, "parent", "parenttype"] if meta.istable else [fieldname]
	values = frappe.db.get_value(doctype, name, fields, as_dict=True)
	if not values or (values[fieldname] or "").strip() != pointer.strip():
		return False

	# child rows are as readable as their parent
	if meta.istable:
		frappe.has_permission(values.parenttype, "read", doc=values.parent, throw=True)
	else:
		frappe.has_permission(doctype, "read", doc=name, throw=True)

	if fieldname not in meta.get_permitted_fieldnames(parenttype=values.get("parenttype")):
		raise frappe.PermissionError
	return True
