import frappe
import frappe.query_builder
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(get_fields(), update=True)
	frappe.clear_cache()

	meta = frappe.get_meta("Sales Order")
	if meta.get_field("patient_actual_name"):
		print("Renaming patient_actual_name to patient_name")
		so = frappe.qb.DocType("Sales Order")
		frappe.qb.update(so).set(so.patient_name, so.patient_actual_name).run()

		frappe.clear_cache()
		frappe.db.set_value(
			"Custom Field",
			"Sales Order-patient_actual_name",
			{
				"depends_on": "",
				"mandatory_depends_on": "",
				"hidden": 1,
				"read_only": 1,
			},
		)


def get_fields():
	return {
		"Sales Invoice Item": [
			{
				"fieldname": "dosage_info",
				"label": "Dosage Information",
				"fieldtype": "Small Text",
				"insert_after": "item_name",
				"red_only": 1,
				"bold": 1,
			},
		],
		"Sales Order": [
			{
				"fieldname": "patient",
				"label": "Patient",
				"fieldtype": "Link",
				"options": "Patient",
				"insert_after": "customer_name",
			},
			{
				"fieldname": "patient_name",
				"label": "Patient Actual Name",
				"fieldtype": "Data",
				"insert_after": "patient",
				"mandatory_depends_on": "eval: doc.customer == 'Cash Customer' ",
			},
			{
				"fieldname": "patient_mobile_number",
				"label": "Patient Mobile Number",
				"fieldtype": "Data",
				"insert_after": "patient_name",
				"depends_on": "eval: doc.customer == 'Cash Customer' ",
			},
			{
				"fieldname": "med_change_request_sb",
				"fieldtype": "Section Break",
				"label": "Medication Change Request",
				"insert_after": "ignore_pricing_rule",
				"depends_on": "eval: doc.allow_med_change_request == 1",
			},
			{
				"fieldname": "allow_med_change_request",
				"fieldtype": "Check",
				"label": "Allow Medication Change Request",
				"insert_after": "med_change_request_sb",
				"hidden": 1,
				"read_only": 1,
			},
			{
				"fieldname": "patient_encounter",
				"fieldtype": "Link",
				"label": "Patient Encounter",
				"options": "Patient Encounter",
				"insert_after": "allow_med_change_request",
				"read_only": 1,
			},
			{
				"fieldname": "med_change_request_status",
				"fieldtype": "Select",
				"label": "Medication Change Request Status",
				"options": "\nPending\nApproved",
				"insert_after": "patient_encounter",
				"read_only": 1,
			},
			{
				"fieldname": "med_change_request_cb",
				"fieldtype": "Column Break",
				"insert_after": "med_change_request_status",
			},
			{
				"fieldname": "med_change_request",
				"fieldtype": "Button",
				"label": "Medication Change Request",
				"insert_after": "med_change_request_cb",
				"depends_on": "eval: doc.docstatus == 0",
			},
			{
				"fieldname": "med_change_request_comment",
				"fieldtype": "Small Text",
				"label": "Comment",
				"insert_after": "med_change_request",
				"description": "comment indicates item(s) to be changed",
			},
		],
		"Sales Order Item": [
			{
				"fieldname": "dosage_info",
				"label": "Dosage Information",
				"fieldtype": "Small Text",
				"insert_after": "item_name",
				"red_only": 1,
				"bold": 1,
			},
			{
				"fieldname": "reference_dt",
				"label": "Reference DocType",
				"fieldtype": "Link",
				"options": "DocType",
				"insert_after": "blanket_order_rate",
				"read_only": 1,
			},
			{
				"fieldname": "reference_dn",
				"label": "Reference Name",
				"fieldtype": "Dynamic Link",
				"options": "reference_dt",
				"insert_after": "reference_dt",
				"read_only": 1,
			},
		],
	}
