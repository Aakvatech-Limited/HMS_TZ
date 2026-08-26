from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Patient Encounter": [
				{
					"fieldname": "section_break_28",
					"fieldtype": "Section Break",
					"insert_after": "claim_status",
					"label": "Diagnosis Actions",
					"depends_on": "eval:doc.docstatus==0",
				},
				{
					"fieldname": "hms_tz_reuse_diagnosis_cb",
					"fieldtype": "Column Break",
					"insert_after": "hms_tz_add_chronic_diagnosis",
				},
				{
					"fieldname": "hms_tz_reuse_previous_diagnosis",
					"label": "Reuse Previous Diagnosis",
					"fieldtype": "Button",
					"insert_after": "hms_tz_reuse_diagnosis_cb",
					"depends_on": "eval:doc.docstatus==0",
				},
				{
					"fieldname": "hms_tz_section_break",
					"fieldtype": "Section Break",
					"insert_after": "hms_tz_reuse_previous_diagnosis",
					"label": "PRELIMINARY DIAGNOSIS",
				},
			]
		},
		update=True,
	)
