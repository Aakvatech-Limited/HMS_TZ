import frappe
from frappe import _
from frappe.core.doctype.data_import.exporter import Exporter
from frappe.core.doctype.data_import.importer import ImportFile
from frappe.utils import cint, strip_html

from hms_tz.api.setup import FIELD_KEYS, get_company_setup, is_missing
from hms_tz.hms_tz.doctype.setup_status.setup_status import complete_setup_step, get_setup_status

ROOM_DOCTYPE = "Healthcare Service Unit"

# Fields asked on the rooms screen besides the DocType's required ones, with their screen rules.
ROOM_EXTRA_FIELDS = {
	"service_unit_type": {
		"reqd": 1,
		"link_filters": [["Healthcare Service Unit Type", "disabled", "=", 0]],
	},
	"warehouse": {
		"link_filters": [
			["Warehouse", "company", "=", "eval: doc.company"],
			["Warehouse", "is_group", "=", 0],
		],
	},
	"disabled": {},
}


@frappe.whitelist()
def get_room_fields():
	"""Room screen fields in form order: the required Healthcare Service Unit fields and ROOM_EXTRA_FIELDS."""
	frappe.has_permission(ROOM_DOCTYPE, "read", throw=True)
	meta = frappe.get_meta(ROOM_DOCTYPE)
	fields = []
	for docfield in meta.fields:
		if docfield.fieldname == "company" or not (docfield.reqd or docfield.fieldname in ROOM_EXTRA_FIELDS):
			continue
		field = {key: docfield.get(key) for key in FIELD_KEYS}
		field.update(ROOM_EXTRA_FIELDS.get(docfield.fieldname, {}))
		field.update(doctype=ROOM_DOCTYPE, is_title=docfield.fieldname == meta.title_field)
		if isinstance(field["link_filters"], list):
			field["link_filters"] = frappe.as_json(field["link_filters"], indent=None)
		fields.append(field)
	return fields


@frappe.whitelist()
def get_company_rooms(company):
	"""The company's rooms and whether its settings are complete, which unlocks adding rooms."""
	frappe.has_permission(ROOM_DOCTYPE, "read", throw=True)
	setup = get_company_setup(company)
	rooms = frappe.get_all(
		ROOM_DOCTYPE,
		filters={"company": company, "is_group": 0},
		fields=["name", *[field["fieldname"] for field in get_room_fields()]],
		order_by="healthcare_service_unit_name asc",
	)
	return {"setting": setup["setting"], "settings_complete": setup["settings_complete"], "rooms": rooms}


@frappe.whitelist(methods=["POST"])
def save_room(company, values, name=None):
	"""Add a room under the company's root group, or change one; the settings must be complete first."""
	setting = get_unlocked_setting(company)
	name = save_company_room(company, frappe.parse_json(values), name)
	complete_setup_step(setting, ROOM_DOCTYPE)
	return name


@frappe.whitelist()
def download_rooms_template(company, sample_rooms="0", file_type="Excel"):
	"""Frappe's import template with the room fields and, as samples, "all" or that many of the company's rooms."""
	frappe.has_permission(ROOM_DOCTYPE, "read", throw=True)
	exporter = Exporter(
		ROOM_DOCTYPE,
		export_fields={ROOM_DOCTYPE: [field["fieldname"] for field in get_room_fields()]},
		export_data=sample_rooms == "all" or cint(sample_rooms) > 0,
		export_filters={"company": company, "is_group": 0},
		export_page_length=None if sample_rooms == "all" else cint(sample_rooms),
		file_type=file_type,
	)
	exporter.build_response()


@frappe.whitelist(methods=["POST"])
def import_rooms(company, file_url):
	"""Add or change rooms from a filled template, matched by room name; a failed row is reported and skipped."""
	setting = get_unlocked_setting(company)
	import_file = ImportFile(ROOM_DOCTYPE, file_url, import_type="Insert or Update Records")
	result = {"added": 0, "changed": 0, "errors": []}
	for payload in import_file.get_payloads_for_import():
		import_room_row(company, payload, result)
	if result["added"] or result["changed"]:
		complete_setup_step(setting, ROOM_DOCTYPE)
	return result


def import_room_row(company, payload, result):
	frappe.db.savepoint("room_import_row")
	try:
		name = get_room_name(company, payload.doc)
		save_company_room(company, payload.doc, name)
		result["changed" if name else "added"] += 1
	except frappe.ValidationError as error:
		frappe.db.rollback(save_point="room_import_row")
		result["errors"].append({"row": payload.rows[0].row_number, "message": strip_html(str(error))})
	finally:
		frappe.clear_messages()


def get_room_name(company, values):
	"""The existing room with this room name, so a re-import changes it instead of adding a duplicate."""
	title_field = frappe.get_meta(ROOM_DOCTYPE).title_field
	if not values.get(title_field):
		return None
	room = frappe.new_doc(ROOM_DOCTYPE, company=company, **{title_field: values[title_field]})
	room.autoname()
	return room.name if frappe.db.exists(ROOM_DOCTYPE, room.name) else None


def get_unlocked_setting(company):
	"""The company's HMS TZ Setting once its settings page is complete; rooms stay locked before that."""
	setting = frappe.db.get_value("HMS TZ Setting", {"company": company})
	if not setting:
		frappe.throw(_("Create the HMS TZ Setting of {0} before adding rooms.").format(company))
	get_setup_status(setting).validate_settings_complete()
	return setting


def save_company_room(company, values, name=None):
	fields = get_room_fields()
	room = frappe.get_doc(ROOM_DOCTYPE, name) if name else new_room(company)
	if room.company != company or room.is_group:
		frappe.throw(_("{0} is not a room of {1}.").format(name, company))
	# The title field sets the document name, so it is fixed once the room exists.
	title_field = frappe.get_meta(ROOM_DOCTYPE).title_field
	editable = [field["fieldname"] for field in fields if not (name and field["fieldname"] == title_field)]
	room.update({fieldname: values.get(fieldname) for fieldname in editable})
	validate_required(fields, room)
	validate_warehouse(room)
	room.save()
	return room.name


def new_room(company):
	root = frappe.db.get_value(
		ROOM_DOCTYPE, {"company": company, "is_group": 1, "parent_healthcare_service_unit": ("is", "not set")}
	)
	return frappe.get_doc(
		{"doctype": ROOM_DOCTYPE, "company": company, "parent_healthcare_service_unit": root}
	)


def validate_required(fields, room):
	missing = [field["label"] for field in fields if is_missing(field, room.as_dict())]
	if missing:
		frappe.throw(_("Fill in {0} before saving the room.").format(", ".join(missing)))


def validate_warehouse(room):
	"""The stock location must belong to the room's company; the screen filters it, an import does not."""
	warehouse_company = room.warehouse and frappe.db.get_value("Warehouse", room.warehouse, "company")
	if warehouse_company and warehouse_company != room.company:
		frappe.throw(
			_("Warehouse {0} belongs to {1}, not {2}.").format(
				room.warehouse, warehouse_company, room.company
			)
		)
