import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	properties = [
		{
			"doctype": "Healthcare Insurance Subscription",
			"fieldname": "insurance_company",
			"property": "allow_on_submit",
			"property_type": "Check",
			"value": 1,
		},
		{
			"doctype": "Healthcare Insurance Subscription",
			"fieldname": "insurance_company_name",
			"property": "allow_on_submit",
			"property_type": "Check",
			"value": 1,
		},
		{
			"doctype": "Healthcare Insurance Subscription",
			"fieldname": "insurance_company_customer",
			"property": "allow_on_submit",
			"property_type": "Check",
			"value": 1,
		},
		{
			"doctype": "Healthcare Insurance Subscription",
			"fieldname": "healthcare_insurance_coverage_plan",
			"property": "allow_on_submit",
			"property_type": "Check",
			"value": 1,
		},
		{
			"doctype": "Lab test",
			"fieldname": "insurance_company",
			"property": "fetch_if_empty",
			"property_type": "Check",
			"value": 1,
		},
		{
			"doctype": "Radiology Examination",
			"fieldname": "insurance_company",
			"property": "fetch_if_empty",
			"property_type": "Check",
			"value": 1,
		},
		{
			"doctype": "Clinical Procedure",
			"fieldname": "insurance_company",
			"property": "fetch_if_empty",
			"value": 1,
		},
		{
			"doctype": "Patient Encounter",
			"fieldname": "insurance_company",
			"property": "fetch_if_empty",
			"property_type": "Check",
			"value": 1,
		},
		{
			"doctype": "Patient Appointment",
			"fieldname": "insurance_company",
			"property": "fetch_if_empty",
			"value": 1,
		},
		{
			"doctype": "Patient Appointment",
			"fieldname": "coverage_plan_name",
			"property": "fetch_if_empty",
			"value": 1,
		},
		{
			"doctype": "Inpatient Record",
			"fieldname": "insurance_company",
			"property": "fetch_if_empty",
			"property_type": "Check",
			"value": 1,
		},
		{
			"doctype": "Healthcare Service Order",
			"fieldname": "insurance_company",
			"property": "fetch_if_empty",
			"property_type": "Check",
			"value": 1,
		},
		{
			"doctype": "Radiology Examination",
			"fieldname": "hms_tz_insurance_coverage_plan",
			"property": "fetch_if_empty",
			"property_type": "Check",
			"value": 1,
		},
	]

	for property in properties:
		make_property_setter(
			property.get("doctype"),
			property.get("fieldname"),
			property.get("property"),
			property.get("value"),
			property.get("property_type"),
			for_doctype=False,
			validate_fields_for_doctype=False,
		)
	frappe.db.commit()
