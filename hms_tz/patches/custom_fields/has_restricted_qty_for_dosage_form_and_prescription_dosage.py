from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Dosage Form": [
			{
				"fieldname": "has_restricted_qty",
				"fieldtype": "Check",
				"label": "Has Restricted Qty",
				"insert_after": "dosage_form",
				"description": "if ticked, medication with this Dosage Form will undergo prescription dosage filtering on Patient Encounter.",
			}
		],
		"Prescription Dosage": [
			{
				"fieldname": "has_restricted_qty",
				"fieldtype": "Check",
				"label": "Has Restricted Qty",
				"insert_after": "dosage",
				"description": "if ticked, this Prescription Dosage will be filtered in when Quantity's restricted Medication is selected on Patient Encounter.",
			}
		],
	}

	create_custom_fields(fields, update=True)
