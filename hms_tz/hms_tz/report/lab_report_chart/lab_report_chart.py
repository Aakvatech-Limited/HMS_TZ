# Copyright (c) 2013, Aakvatech and contributors
# For license information, please see license.txt

import frappe
import pandas as pd
from frappe import _, msgprint
from frappe.query_builder import DocType
from frappe.query_builder.functions import DateFormat


def execute(filters=None):
	columns = get_columns(filters)
	data = []

	lab_details = get_lab_results(filters)
	if not lab_details:
		msgprint(
			frappe.bold(
				"No Record Found for Filters You Specified, Please Choose Different Filters and Try Again..!! "
			)
		)
	else:
		lab_colnames = [key for key in lab_details[0].keys()]
		df = pd.DataFrame.from_records(lab_details, columns=lab_colnames)

		pvt = pd.pivot_table(
			df,
			values="result_value",
			index="lab_test_name",
			columns="result_date",
			fill_value=" ",
			aggfunc="first",
		)

		columns += pvt.columns.values.tolist()
		data += pvt.reset_index().values.tolist()
	return columns, data


def get_columns(filters):
	columns = [
		{
			"fieldname": "lab_test_name",
			"fieldtype": "Data",
			"label": _("Lab Test Name"),
		}
	]
	return columns


def get_lab_results(filters):
	lab_test = DocType("Lab Test")
	result_tables = (
		(DocType("Normal Test Result"), "result_value"),
		(DocType("Descriptive Test Result"), "result_value"),
		(DocType("Organism Test Result"), "colony_population"),
		(DocType("Sensitivity Test Result"), "antibiotic_sensitivity"),
	)
	criteria = get_lab_test_criteria(lab_test, filters)

	queries = [
		frappe.qb.from_(lab_test)
		.inner_join(result_table)
		.on(lab_test.name == result_table.parent)
		.select(
			lab_test.lab_test_name.as_("lab_test_name"),
			DateFormat(lab_test.result_date, "%Y-%m-%d").as_("result_date"),
			result_table[result_field].as_("result_value"),
		)
		.where(criteria)
		for result_table, result_field in result_tables
	]

	query = queries[0]
	for part in queries[1:]:
		query = query.union(part)

	return query.run(as_dict=True)


def get_lab_test_criteria(lab_test, filters):
	template = DocType("Lab Test Template")
	grouped_tests = (
		frappe.qb.from_(template)
		.select(template.lab_test_name)
		.where(template.lab_test_template_type == "Grouped")
	)
	criteria = (
		(lab_test.docstatus == 1)
		& lab_test.lab_test_name.notin(grouped_tests)
		& (lab_test.status == "Completed")
	)

	if filters.get("patient"):
		criteria &= lab_test.patient == filters.get("patient")

	if filters.get("from_date"):
		criteria &= lab_test.result_date >= filters.get("from_date")

	if filters.get("to_date"):
		criteria &= lab_test.result_date <= filters.get("to_date")

	if filters.get("department"):
		criteria &= lab_test.department == filters.get("department")

	return criteria
