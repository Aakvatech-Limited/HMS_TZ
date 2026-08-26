from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Patient Encounter": [
			{
				"fieldname": "hms_tz_reuse_lab_items",
				"label": "Reuse Lab Items",
				"fieldtype": "Button",
				"insert_after": "sb_test_prescription",
				"depends_on": "eval: doc.docstatus == 0",
			},
			{
				"fieldname": "lab_bundle",
				"label": "Lab Bundle",
				"fieldtype": "Link",
				"insert_after": "hms_tz_reuse_lab_items",
				"options": "Lab Bundle",
				"depends_on": "eval: doc.docstatus == 0",
			},
			{
				"fieldname": "get_lab_bundle_items",
				"label": "Get Lab Bundle Items",
				"fieldtype": "Button",
				"insert_after": "lab_bundle",
				"depends_on": "eval: doc.docstatus == 0",
			},
			{
				"fieldname": "hms_tz_reuse_radiology_items",
				"label": "Reuse Radiology Items",
				"fieldtype": "Button",
				"insert_after": "radiology_procedures_section",
				"depends_on": "eval: doc.docstatus == 0",
			},
			{
				"fieldname": "section_break_52",
				"label": "",
				"fieldtype": "Section Break",
				"insert_after": "previous_radiology_procedure_prescription",
			},
			{
				"fieldname": "hms_tz_reuse_procedure_items",
				"label": "Reuse Procedure Items",
				"fieldtype": "Button",
				"insert_after": "sb_procedures",
				"depends_on": "eval: doc.docstatus == 0",
			},
			{
				"fieldname": "hms_tz_reuse_drug_items",
				"label": "Reuse Drug Items",
				"fieldtype": "Button",
				"insert_after": "default_healthcare_service_unit",
				"depends_on": "eval: doc.docstatus == 0",
			},
			{
				"fieldname": "hms_tz_reuse_therapy_items",
				"label": "Reuse Therapy Items",
				"fieldtype": "Button",
				"insert_after": "therapy_plan",
				"depends_on": "eval: doc.docstatus == 0",
			},
		],
	}

	create_custom_fields(fields, update=True)
