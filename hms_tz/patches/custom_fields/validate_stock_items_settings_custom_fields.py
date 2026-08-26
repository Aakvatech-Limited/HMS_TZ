from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Healthcare Settings": [
			{
				"fieldname": "only_alert_if_less_stock_of_drug_item_for_cash_in_pe",
				"label": "Only Alert if Less/Zero Stock for Cash in Patient Encounter",
				"fieldtype": "Check",
				"insert_after": "enable_auto_quantity_calculation",
				"description": "If ticked, doctors will be alerted only if the drug item is less/zero stock for Cash Patients in patient encounter",
			},
			{
				"fieldname": "stop_encounter_if_less_stock_of_drug_item_for_cash_in_pe",
				"label": "Stop Encounter if Less/Zero Stock for Cash in Patient Encounter",
				"fieldtype": "Check",
				"insert_after": "only_alert_if_less_stock_of_drug_item_for_cash_in_pe",
				"description": "If ticked, doctors can't submit Patient Encounter if the drug item is less/zero stock for Cash Patients",
			},
			{
				"fieldname": "only_alert_if_less_stock_of_drug_item_for_insurance_in_pe",
				"label": "Only Alert if Less/Zero Stock for Insurance in Patient Encounter",
				"fieldtype": "Check",
				"insert_after": "stop_encounter_if_less_stock_of_drug_item_for_cash_in_pe",
				"description": "If ticked, doctors will be alerted only if the drug item is less/zero stock for Insurance Patients in patient encounter",
			},
			{
				"fieldname": "stop_encounter_if_less_stock_of_drug_item_for_insurance_in_pe",
				"label": "Stop Encounter if Less/Zero Stock for Insurance in Patient Encounter",
				"fieldtype": "Check",
				"insert_after": "only_alert_if_less_stock_of_drug_item_for_insurance_in_pe",
				"description": "If ticked, doctors can't submit Patient Encounter if the drug item is less/zero stock for Insurance Patients",
			},
		]
	}

	create_custom_fields(fields, update=True)
