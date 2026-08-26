from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Lab Test Template": [
			{
				"fieldname": "hms_tz_lab_test_prescription_settings",
				"label": "Lab Test Prescription Settings",
				"fieldtype": "Section Break",
				"insert_after": "sample_details",
				"collapsible": 1,
			},
			{
				"fieldname": "hms_tz_validate_prescription_days_for_insurance",
				"label": "Validate Prescription Days for Insurance",
				"fieldtype": "Check",
				"insert_after": "hms_tz_lab_test_prescription_settings",
			},
			{
				"fieldname": "hms_tz_validate_prescription_days_for_cash",
				"label": "Validate Prescription Days for Cash",
				"fieldtype": "Check",
				"insert_after": "hms_tz_validate_prescription_days_for_insurance",
			},
			{
				"fieldname": "hms_tz_lab_prescription_cb",
				"fieldtype": "Column Break",
				"insert_after": "hms_tz_validate_prescription_days_for_cash",
			},
			{
				"fieldname": "hms_tz_insurance_min_no_of_days_for_prescription",
				"label": "Insurance Minimum No of Days for Prescription",
				"fieldtype": "Int",
				"insert_after": "hms_tz_lab_prescription_cb",
				"depends_on": "eval: doc.hms_tz_validate_prescription_days_for_insurance",
				"mandatory_depends_on": "eval: doc.hms_tz_validate_prescription_days_for_insurance",
			},
			{
				"fieldname": "hms_tz_cash_min_no_of_days_for_prescription",
				"label": "Cash Minimum No of Days for Prescription",
				"fieldtype": "Int",
				"insert_after": "hms_tz_insurance_min_no_of_days_for_prescription",
				"depends_on": "eval: doc.hms_tz_validate_prescription_days_for_cash",
				"mandatory_depends_on": "eval: doc.hms_tz_validate_prescription_days_for_cash",
			},
		],
		"Radiology Examination Template": [
			{
				"fieldname": "hms_tz_radiology_examination_prescription_settings",
				"label": "Radiology Examination Prescription Settings",
				"fieldtype": "Section Break",
				"insert_after": "company_options",
				"collapsible": 1,
			},
			{
				"fieldname": "hms_tz_validate_prescription_days_for_insurance",
				"label": "Validate Prescription Days for Insurance",
				"fieldtype": "Check",
				"insert_after": "hms_tz_radiology_examination_prescription_settings",
			},
			{
				"fieldname": "hms_tz_validate_prescription_days_for_cash",
				"label": "Validate Prescription Days for Cash",
				"fieldtype": "Check",
				"insert_after": "hms_tz_validate_prescription_days_for_insurance",
			},
			{
				"fieldname": "hms_tz_radiology_examination_prescription_cb",
				"fieldtype": "Column Break",
				"insert_after": "hms_tz_validate_prescription_days_for_cash",
			},
			{
				"fieldname": "hms_tz_insurance_min_no_of_days_for_prescription",
				"label": "Insurance Minimum No of Days for Prescription",
				"fieldtype": "Int",
				"insert_after": "hms_tz_radiology_examination_prescription_cb",
				"depends_on": "eval: doc.hms_tz_validate_prescription_days_for_insurance",
				"mandatory_depends_on": "eval: doc.hms_tz_validate_prescription_days_for_insurance",
			},
			{
				"fieldname": "hms_tz_cash_min_no_of_days_for_prescription",
				"label": "Cash Minimum No of Days for Prescription",
				"fieldtype": "Int",
				"insert_after": "hms_tz_insurance_min_no_of_days_for_prescription",
				"depends_on": "eval: doc.hms_tz_validate_prescription_days_for_cash",
				"mandatory_depends_on": "eval: doc.hms_tz_validate_prescription_days_for_cash",
			},
		],
		"Clinical Procedure Template": [
			{
				"fieldname": "hms_tz_clinical_procedure_settings",
				"label": "Clinical Procedure Settings",
				"fieldtype": "Section Break",
				"insert_after": "company_options",
				"collapsible": 1,
			},
			{
				"fieldname": "hms_tz_validate_prescription_days_for_insurance",
				"label": "Validate Prescription Days for Insurance",
				"fieldtype": "Check",
				"insert_after": "hms_tz_clinical_procedure_settings",
			},
			{
				"fieldname": "hms_tz_validate_prescription_days_for_cash",
				"label": "Validate Prescription Days for Cash",
				"fieldtype": "Check",
				"insert_after": "hms_tz_validate_prescription_days_for_insurance",
			},
			{
				"fieldname": "hms_tz_clinical_procedure_cb",
				"fieldtype": "Column Break",
				"insert_after": "hms_tz_validate_prescription_days_for_cash",
			},
			{
				"fieldname": "hms_tz_insurance_min_no_of_days_for_prescription",
				"label": "Insurance Minimum No of Days for Prescription",
				"fieldtype": "Int",
				"insert_after": "hms_tz_clinical_procedure_cb",
				"depends_on": "eval: doc.hms_tz_validate_prescription_days_for_insurance",
				"mandatory_depends_on": "eval: doc.hms_tz_validate_prescription_days_for_insurance",
			},
			{
				"fieldname": "hms_tz_cash_min_no_of_days_for_prescription",
				"label": "Cash Minimum No of Days for Prescription",
				"fieldtype": "Int",
				"insert_after": "hms_tz_insurance_min_no_of_days_for_prescription",
				"depends_on": "eval: doc.hms_tz_validate_prescription_days_for_cash",
				"mandatory_depends_on": "eval: doc.hms_tz_validate_prescription_days_for_cash",
			},
		],
		"Medication": [
			{
				"fieldname": "hms_tz_drug_issuing_configuration",
				"label": "Drug Issuing Configuration",
				"fieldtype": "Section Break",
				"insert_after": "default_interval_uom",
				"collapsible": 1,
			},
			{
				"fieldname": "hms_tz_validate_prescription_days_for_insurance",
				"label": "Validate Prescription Days for Insurance",
				"fieldtype": "Check",
				"insert_after": "hms_tz_drug_issuing_configuration",
			},
			{
				"fieldname": "hms_tz_validate_prescription_days_for_cash",
				"label": "Validate Prescription Days for Cash",
				"fieldtype": "Check",
				"insert_after": "hms_tz_validate_prescription_days_for_insurance",
			},
			{
				"fieldname": "hms_tz_drug_issuing_cb",
				"fieldtype": "Column Break",
				"insert_after": "hms_tz_validate_prescription_days_for_cash",
			},
			{
				"fieldname": "hms_tz_insurance_min_no_of_days_for_prescription",
				"label": "Insurance Minimum No of Days for Prescription",
				"fieldtype": "Int",
				"insert_after": "hms_tz_drug_issuing_cb",
				"depends_on": "eval: doc.hms_tz_validate_prescription_days_for_insurance",
				"mandatory_depends_on": "eval: doc.hms_tz_validate_prescription_days_for_insurance",
			},
			{
				"fieldname": "hms_tz_cash_min_no_of_days_for_prescription",
				"label": "Cash Minimum No of Days for Prescription",
				"fieldtype": "Int",
				"insert_after": "hms_tz_insurance_min_no_of_days_for_prescription",
				"depends_on": "eval: doc.hms_tz_validate_prescription_days_for_cash",
				"mandatory_depends_on": "eval: doc.hms_tz_validate_prescription_days_for_cash",
			},
		],
		"Therapy Type": [
			{
				"fieldname": "hms_tz_therapy_plan_settings",
				"label": "Therapy Plan Settings",
				"fieldtype": "Section Break",
				"insert_after": "company_options",
				"collapsible": 1,
			},
			{
				"fieldname": "hms_tz_validate_prescription_days_for_insurance",
				"label": "Validate Prescription Days for Insurance",
				"fieldtype": "Check",
				"insert_after": "hms_tz_therapy_plan_settings",
			},
			{
				"fieldname": "hms_tz_validate_prescription_days_for_cash",
				"label": "Validate Prescription Days for Cash",
				"fieldtype": "Check",
				"insert_after": "hms_tz_validate_prescription_days_for_insurance",
			},
			{
				"fieldname": "hms_tz_therapy_plan_cb",
				"fieldtype": "Column Break",
				"insert_after": "hms_tz_validate_prescription_days_for_cash",
			},
			{
				"fieldname": "hms_tz_insurance_min_no_of_days_for_prescription",
				"label": "Insurance Minimum No of Days for Prescription",
				"fieldtype": "Int",
				"insert_after": "hms_tz_therapy_plan_cb",
				"depends_on": "eval: doc.hms_tz_validate_prescription_days_for_insurance",
				"mandatory_depends_on": "eval: doc.hms_tz_validate_prescription_days_for_insurance",
			},
			{
				"fieldname": "hms_tz_cash_min_no_of_days_for_prescription",
				"label": "Cash Minimum No of Days for Prescription",
				"fieldtype": "Int",
				"insert_after": "hms_tz_insurance_min_no_of_days_for_prescription",
				"depends_on": "eval: doc.hms_tz_validate_prescription_days_for_cash",
				"mandatory_depends_on": "eval: doc.hms_tz_validate_prescription_days_for_cash",
			},
		],
	}

	create_custom_fields(fields, update=True)
