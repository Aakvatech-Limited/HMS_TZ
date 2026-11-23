import frappe
from frappe import _

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
	setting = frappe.db.get_value("HMS TZ Setting", {"company": company})
	if not setting:
		frappe.throw(_("Create the HMS TZ Setting of {0} before adding rooms.").format(company))
	get_setup_status(setting).validate_settings_complete()

	fields = get_room_fields()
	values = frappe.parse_json(values)
	room = frappe.get_doc(ROOM_DOCTYPE, name) if name else new_room(company)
	if room.company != company or room.is_group:
		frappe.throw(_("{0} is not a room of {1}.").format(name, company))
	# The title field sets the document name, so it is fixed once the room exists.
	title_field = frappe.get_meta(ROOM_DOCTYPE).title_field
	editable = [field["fieldname"] for field in fields if not (name and field["fieldname"] == title_field)]
	room.update({fieldname: values.get(fieldname) for fieldname in editable})
	validate_required(fields, room)
	room.save()
	complete_setup_step(setting, ROOM_DOCTYPE)
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
