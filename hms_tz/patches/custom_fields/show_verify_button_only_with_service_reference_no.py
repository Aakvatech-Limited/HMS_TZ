import frappe

from hms_tz.patches.custom_fields.create_custom_fields import load_json

JSON_FILES = [
	"12_lab_test.json",
	"13_radiologuy_examination.json",
	"14_clinical_procedure.json",
	"16_therapy_session.json",
	"18_delivery_note_item.json",
]


def get_verify_button_fields():
	return [
		field
		for file in JSON_FILES
		for field in load_json(file)
		if field["fieldname"] == "verify_approval_no"
	]


def execute():
	"""The verify button now checks the service reference no, so show it only once one is issued."""
	fields = get_verify_button_fields()
	for field in fields:
		frappe.db.set_value(
			"Custom Field",
			{"dt": field["dt"], "fieldname": field["fieldname"]},
			"depends_on",
			field["depends_on"],
		)
		frappe.clear_cache(doctype=field["dt"])
