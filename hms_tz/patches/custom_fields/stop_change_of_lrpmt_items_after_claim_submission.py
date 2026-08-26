from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Company": [
			{
				"fieldname": "stop_change_of_lrpmt_items_after_claim_submission",
				"label": "Stop Change/Cancel/Return of LRPMT Items After Claim Submission",
				"fieldtype": "Check",
				"insert_after": "hms_tz_settings_sb",
				"default": 1,
				"description": "If checked, user will not be able to Change/Cancel/Return LRPMT items after NHIF Claim submission.",
			}
		]
	}

	create_custom_fields(fields, update=True)
