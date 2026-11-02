import frappe

from hms_tz.patches.custom_fields.create_custom_fields import load_json

JSON_FILES = [
	"12_lab_test.json",
	"13_radiologuy_examination.json",
	"14_clinical_procedure.json",
	"16_therapy_session.json",
	"17_delivery_note.json",
]
FIELDNAMES = ("issue_service", "get_poc_reference_no")


def get_button_fields():
	return [field for file in JSON_FILES for field in load_json(file) if field["fieldname"] in FIELDNAMES]


def execute():
	"""Copy the buttons' depends_on from the custom field JSON, so a used reference hides the button on live sites."""
	fields = get_button_fields()
	for field in fields:
		frappe.db.set_value(
			"Custom Field",
			{"dt": field["dt"], "fieldname": field["fieldname"]},
			"depends_on",
			field["depends_on"],
		)

	for doctype in {field["dt"] for field in fields}:
		frappe.clear_cache(doctype=doctype)
