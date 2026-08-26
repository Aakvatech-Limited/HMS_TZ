import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

# Mosaic Tasks:
# https://worklog.aakvatech.com/Mosaic/Task/bc9f4be72c
# https://worklog.aakvatech.com/Mosaic/Task/e3a9d255e2


def execute():
	properties = [
		{
			"doctype": "Patient Encounter Symptom",
			"fieldname": "complaint",
			"property": "reqd",
			"property_type": "Check",
			"value": 0,
		},
		{
			"doctype": "Patient Encounter",
			"fieldname": "diet_recommendation_section",
			"property": "hidden",
			"property_type": "Check",
			"value": 1,
		},
		{
			"doctype": "Patient Encounter",
			"fieldname": "symptoms_and_signs",
			"property": "label",
			"property_type": "Data",
			"value": "Chief Complaints",
		},
		{
			"doctype": "Patient Encounter",
			"fieldname": "symptoms_and_signs",
			"property": "collapsible",
			"property_type": "Check",
			"value": 1,
		},
		{
			"doctype": "Patient Encounter",
			"fieldname": "section_break_28",
			"property": "label",
			"property_type": "Data",
			"value": "Diagnosis Actions",
		},
		{
			"doctype": "Codification Table",
			"fieldname": "medical_code_standard",
			"property": "reqd",
			"property_type": "Check",
			"value": 0,
		},
		{
			"doctype": "Codification Table",
			"fieldname": "medical_code_standard",
			"property": "hidden",
			"property_type": "Check",
			"value": 1,
		},
		{
			"doctype": "Codification Table",
			"fieldname": "medical_code_standard",
			"property": "allow_on_submit",
			"property_type": "Check",
			"value": 1,
		},
		{
			"doctype": "Clinical Procedure",
			"fieldname": "status",
			"property": "allow_on_submit",
			"property_type": "Check",
			"value": 1,
		},
		{
			"doctype": "Lab Prescription",
			"fieldname": "amount",
			"property": "label",
			"property_type": "Data",
			"value": "Item Rate",
		},
		{
			"doctype": "Radiology Procedure Prescription",
			"fieldname": "amount",
			"property": "label",
			"property_type": "Data",
			"value": "Item Rate",
		},
		{
			"doctype": "Procedure Prescription",
			"fieldname": "amount",
			"property": "label",
			"property_type": "Data",
			"value": "Item Rate",
		},
		{
			"doctype": "Drug Prescription",
			"fieldname": "amount",
			"property": "label",
			"property_type": "Data",
			"value": "Item Rate",
		},
		{
			"doctype": "Therapy Plan Detail",
			"fieldname": "amount",
			"property": "label",
			"property_type": "Data",
			"value": "Item Rate",
		},
		{
			"doctype": "Inpatient Occupancy",
			"fieldname": "amount",
			"property": "label",
			"property_type": "Data",
			"value": "Item Rate",
		},
		{
			"doctype": "Inpatient Consultancy",
			"fieldname": "rate",
			"property": "label",
			"property_type": "Data",
			"value": "Item Rate",
		},
		{
			"doctype": "Patient Appointment",
			"fieldname": "paid_amount",
			"property": "label",
			"property_type": "Data",
			"value": "Item Rate",
		},
		{
			"doctype": "Delivery Note Item",
			"fieldname": "rate",
			"property": "label",
			"property_type": "Data",
			"value": "Item Rate",
		},
		{
			"doctype": "Sales Order Item",
			"fieldname": "rate",
			"property": "label",
			"property_type": "Data",
			"value": "Item Rate",
		},
		{
			"doctype": "Radiology Examination",
			"fieldname": "appointment",
			"property": "fetch_from",
			"property_type": "Small Text",
			"value": "ref_docname.appointment",
		},
		{
			"doctype": "Radiology Examination",
			"fieldname": "appointment",
			"property": "fetch_if_empty",
			"property_type": "Check",
			"value": 1,
		},
		{
			"doctype": "Clinical Procedure",
			"fieldname": "appointment",
			"property": "fetch_from",
			"property_type": "Small Text",
			"value": "ref_docname.appointment",
		},
		{
			"doctype": "Clinical Procedure",
			"fieldname": "appointment",
			"property": "fetch_if_empty",
			"property_type": "Check",
			"value": 1,
		},
		{
			"doctype": "NHIF Patient Claim",
			"property": "make_attachments_public",
			"property_type": "Check",
			"value": 1,
		},
		{
			"doctype": "Patient",
			"fieldname": "dob",
			"property": "reqd",
			"property_type": "Check",
			"value": 1,
		},
		{
			"doctype": "Patient Appointment",
			"fieldname": "appointment_type",
			"property": "default",
			"property_type": "Small Text",
			"value": "",
		},
	]

	for property in properties:
		if property.get("doctype") == "NHIF Patient Claim":
			property["for_doctype"] = True
		else:
			property["for_doctype"] = False

		make_property_setter(
			property.get("doctype"),
			property.get("fieldname"),
			property.get("property"),
			property.get("value"),
			property.get("property_type"),
			for_doctype=property.get("for_doctype"),
			validate_fields_for_doctype=False,
		)
	frappe.db.commit()
