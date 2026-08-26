from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Healthcare Settings": [
			{
				"fieldname": "allow_practitioner_to_take_other_encounters",
				"label": "Allow Practitioners to Take Other's Encounters",
				"fieldtype": "Check",
				"insert_after": "stop_encounter_if_less_stock_of_drug_item_for_insurance_in_pe",
				"description": "If checked, practitioner will be able to take or to submit encounters of other practitioners",
			}
		]
	}

	create_custom_fields(fields, update=True)
