import frappe

DOCTYPE = "NHIF Patient Claim"

PROPERTY_SETTERS = [
	"NHIF Patient Claim-main-make_attachments_public",
	"NHIF Patient Claim-authorization_no-read_only_depends_on",
	"NHIF Patient Claim-authorization_no-permlevel",
	"NHIF Patient Claim-main-field_order",
	"NHIF Patient Claim-patient_appointment-read_only_depends_on",
	"NHIF Patient Claim-cardno-read_only",
	"NHIF Patient Claim-date_admitted-read_only",
	"NHIF Patient Claim-attendance_date-fetch_if_empty",
	"NHIF Patient Claim-attendance_date-read_only",
]

CUSTOM_FIELDS = [
	"NHIF Patient Claim-hms_tz_appointment_string",
	"NHIF Patient Claim-custom_section_break_qvxel",
	# now standard fields in nhif_patient_claim.json; deleting a Custom Field keeps the column and its data
	"NHIF Patient Claim-how_likely_would_you_recommend_our_services_to_others",
	"NHIF Patient Claim-internal_form_number",
	"NHIF Patient Claim-unsubmittable_claim",
]


def get_custom_column_breaks():
	return frappe.get_all(
		"Custom Field",
		filters={"dt": DOCTYPE, "fieldtype": "Column Break", "fieldname": ["like", "custom_column_break%"]},
		pluck="name",
	)


def execute():
	"""Drop NHIF Patient Claim property setters and custom fields that the DocType JSON now owns."""
	custom_fields = CUSTOM_FIELDS + get_custom_column_breaks()
	for doctype, names in (("Property Setter", PROPERTY_SETTERS), ("Custom Field", custom_fields)):
		for name in names:
			if frappe.db.exists(doctype, name):
				frappe.delete_doc(doctype, name, ignore_permissions=True, force=True)

	frappe.clear_cache(doctype=DOCTYPE)
