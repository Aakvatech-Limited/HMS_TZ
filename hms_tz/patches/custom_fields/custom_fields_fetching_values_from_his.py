from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Patient Appointment": [
			{
				"fieldname": "nhif_employer_name",
				"fieldtype": "Data",
				"label": "NHIF Employer Name",
				"insert_after": "coverage_plan_card_number",
				"read_only": 1,
				"bold": 1,
				"translatable": 1,
			}
		],
		"Healthcare Insurance Subscription": [
			{
				"fieldname": "coverage_plan_name",
				"fieldtype": "Data",
				"insert_after": "healthcare_insurance_coverage_plan",
				"label": "Coverage Plan Name",
				"fetch_from": "healthcare_insurance_coverage_plan.coverage_plan_name",
				"allow_on_submit": 1,
				"read_only": 1,
				"translatable": 1,
			},
			{
				"fieldname": "coverage_plan_card_number",
				"fieldtype": "Data",
				"insert_after": "coverage_plan_name",
				"label": "Coverage Plan Card Number",
				"allow_on_submit": 1,
				"in_list_view": 1,
				"reqd": 1,
				"translatable": 1,
			},
			{
				"label": "Product Code",
				"fieldname": "hms_tz_product_code",
				"insert_after": "hms_tz_scheme_section_break",
				"fieldtype": "Data",
				"allow_on_submit": 1,
				"read_only": 1,
				"translatable": 1,
			},
			{
				"label": "Product Name",
				"fieldname": "hms_tz_product_name",
				"insert_after": "hms_tz_product_code",
				"fieldtype": "Data",
				"allow_on_submit": 1,
				"read_only": 1,
				"translatable": 1,
			},
			{
				"label": "SchemeId",
				"fieldname": "hms_tz_scheme_id",
				"insert_after": "hms_tz_scheme_column_break",
				"fieldtype": "Data",
				"allow_on_submit": 1,
				"read_only": 1,
				"translatable": 1,
			},
			{
				"label": "Scheme Name",
				"fieldname": "hms_tz_scheme_name",
				"insert_after": "hms_tz_scheme_id",
				"fieldtype": "Data",
				"allow_on_submit": 1,
				"read_only": 1,
				"translatable": 1,
			},
		],
		"Radiology Examination": [
			{
				"fieldname": "hms_tz_insurance_coverage_plan",
				"fieldtype": "Data",
				"insert_after": "insurance_subscription",
				"label": "Insurance Coverage Plan",
				"translatable": 1,
				"fetch_if_empty": 1,
				"fetch_from": "insurance_subscription.healthcare_insurance_coverage_plan",
				"read_only": 1,
			},
		],
		"Lab Test": [
			{
				"fieldname": "hms_tz_insurance_coverage_plan",
				"fieldtype": "Data",
				"insert_after": "insurance_subscription",
				"label": "Insurance Coverage Plan",
				"translatable": 1,
				"fetch_if_empty": 1,
				"fetch_from": "insurance_subscription.healthcare_insurance_coverage_plan",
				"read_only": 1,
			},
		],
	}
	create_custom_fields(fields, update=True)
