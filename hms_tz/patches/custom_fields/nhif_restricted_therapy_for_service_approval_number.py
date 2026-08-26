import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	if frappe.db.exists("Custom Field", "Therapy Plan-hms_tz_insurance_coverage_plan"):
		frappe.db.set_value(
			"Custom Field",
			"Therapy Plan-hms_tz_insurance_coverage_plan",
			"insert_after",
			"start_date",
		)

	create_custom_fields(get_fields(), update=True)
	frappe.clear_cache()


def get_fields():
	fields = {
		"Therapy Plan Detail": [
			{
				"fieldname": "is_restricted",
				"fieldtype": "Check",
				"label": "Is Restricted",
				"insert_after": "invoiced",
				"read_only": 1,
				"in_list_view": 1,
			},
			{
				"fieldname": "hms_tz_ref_childname",
				"fieldtype": "Data",
				"label": "Ref ChildName",
				"insert_after": "is_restricted",
				"read_only": 1,
			},
		],
		"Therapy Plan": [
			# {
			#     "fieldname": "is_restricted",
			#     "fieldtype": "Check",
			#     "label": "Is Restricted",
			#     "insert_after": "hms_tz_insurance_coverage_plan",
			#     "read_only": 1,
			# },
			{
				"fieldname": "insurance_company",
				"fieldtype": "Link",
				"label": "Insurance Company",
				"options": "Healthcare Insurance Company",
				"insert_after": "hms_tz_insurance_coverage_plan",
				"read_only": 1,
				"fetch_from": "ref_docname.insurance_company",
				"fetch_if_empty": 1,
			},
		],
		"Therapy Session": [
			{
				"fieldname": "hms_tz_insurance_coverage_plan",
				"fieldtype": "Data",
				"label": "Insurance Coverage Plan",
				"insert_after": "department",
				"fetch_from": "therapy_plan.hms_tz_insurance_coverage_plan",
				"fetch_if_empty": 1,
				"read_only": 1,
			},
			{
				"fieldname": "insurance_company",
				"fieldtype": "Link",
				"label": "Insurance Company",
				"options": "Healthcare Insurance Company",
				"insert_after": "hms_tz_insurance_coverage_plan",
				"fetch_from": "therapy_plan.insurance_company",
				"fetch_if_empty": 1,
				"read_only": 1,
			},
			{
				"fieldname": "is_restricted",
				"fieldtype": "Check",
				"label": "Is Restricted",
				"insert_after": "insurance_company",
				"read_only": 1,
			},
			{
				"fieldname": "approval_number",
				"fieldtype": "Data",
				"label": "Approval Number",
				"insert_after": "is_restricted",
				"depends_on": "eval: doc.is_restricted == 1",
				"mandatory_depends_on": "eval: doc.is_restricted == 1",
			},
			{
				"fieldname": "approval_type",
				"fieldtype": "Select",
				"label": "Approval Type",
				"options": "Local\nNHIF\nOther Insurance",
				"insert_after": "approval_number",
				"depends_on": "eval: doc.is_restricted == 1",
				"mandatory_depends_on": "eval: doc.is_restricted == 1",
			},
			{
				"fieldname": "ref_doctype",
				"fieldtype": "Link",
				"label": "Ref DocType",
				"options": "DocType",
				"insert_after": "total_counts_completed",
				"read_only": 1,
			},
			{
				"fieldname": "ref_docname",
				"fieldtype": "Dynamic Link",
				"label": "Ref DocName",
				"options": "ref_doctype",
				"insert_after": "ref_doctype",
				"read_only": 1,
			},
			{
				"fieldname": "hms_tz_ref_childname",
				"fieldtype": "Data",
				"label": "Ref ChildName",
				"insert_after": "ref_docname",
				"read_only": 1,
			},
		],
	}
	return fields
