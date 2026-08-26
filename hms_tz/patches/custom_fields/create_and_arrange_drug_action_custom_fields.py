from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Patient Encounter": [
			{
				"fieldname": "section_break_28",
				"fieldtype": "Section Break",
				"label": "Diagnosis Actions",
				"insert_after": "claim_status",
				"depends_on": "eval:doc.docstatus == 0",
			},
			{
				"fieldname": "hms_tz_convert_to_inpatient",
				"label": "Convert to Inpatient",
				"fieldtype": "Button",
				"insert_after": "medical_department",
				"depends_on": "eval:!doc.inpatient_record",
			},
			{
				"fieldname": "medication_action_sb",
				"label": "Medication Actions",
				"fieldtype": "Section Break",
				"insert_after": "previous_procedure_prescription",
				"collapsible": 1,
				"depends_on": "eval:doc.docstatus == 0",
			},
			{
				"fieldname": "get_chronic_medications",
				"label": "Get Chronic Medications",
				"fieldtype": "Button",
				"insert_after": "medication_action_sb",
				"depends_on": "eval:doc.docstatus == 0",
			},
			{
				"fieldname": "add_chronic_cb",
				"fieldtype": "Column Break",
				"insert_after": "get_chronic_medications",
			},
			{
				"fieldname": "add_chronic_medications",
				"label": "Add Chronic Medications",
				"fieldtype": "Button",
				"insert_after": "add_chronic_cb",
				"depends_on": "eval:doc.docstatus == 0",
			},
			{
				"fieldname": "reuse_previous_drug_cb",
				"fieldtype": "Column Break",
				"insert_after": "add_chronic_medications",
			},
			{
				"fieldname": "hms_tz_reuse_drug_items",
				"label": "Reuse Drug Items",
				"fieldtype": "Button",
				"insert_after": "reuse_previous_drug_cb",
				"depends_on": "eval:doc.docstatus == 0",
			},
			{
				"fieldname": "healthcare_service_unit_cb",
				"fieldtype": "Column Break",
				"insert_after": "hms_tz_reuse_drug_items",
			},
			{
				"fieldname": "default_healthcare_service_unit",
				"label": "Default Healthcare Service Unit",
				"fieldtype": "Link",
				"insert_after": "healthcare_service_unit_cb",
				"options": "Healthcare Service Unit",
				"depends_on": "eval:doc.docstatus == 0",
			},
		],
	}
	create_custom_fields(fields, update=True)
