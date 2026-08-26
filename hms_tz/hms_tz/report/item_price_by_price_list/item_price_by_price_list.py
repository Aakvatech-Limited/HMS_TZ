# Copyright (c) 2023, Aakvatech and contributors
# For license information, please see license.txt


import frappe
import pandas as pd
from frappe import _
from frappe.query_builder import Case
from frappe.query_builder.functions import IfNull


def execute(filters=None):
	columns = get_columns()
	data = []
	item_prices = get_item_prices(filters)

	if item_prices:
		colnames = [key for key in item_prices[0].keys()]
		# frappe.msgprint("colnames are: " + str(colnames))

		df = pd.DataFrame.from_records(item_prices, columns=colnames)
		# frappe.msgprint("dataframe columns are is: " + str(df.columns.tolist()))

		pvt = pd.pivot_table(
			df,
			values="price_list_rate",
			index=["template_name", "item_code", "status", "item_group"],
			columns="price_list",
			fill_value=0,
		)
		# frappe.msgprint(str(pvt))

		data = pvt.reset_index().values.tolist()
		# frappe.msgprint("Data is: " + str(data))

		# columns += pvt.columns.values.tolist()
		for column_name in pvt.columns.values.tolist():
			# frappe.msgprint("Column is: " + str(column_name))
			columns += [{"label": _(column_name), "fieldtype": "Float", "precision": 2}]
		# frappe.msgprint("Columns are: " + str(columns))

	return columns, data


def get_columns():
	columns = [
		{
			"label": _("Template Name"),
			"fieldname": "template_name",
			"width": 250,
		},
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 250,
		},
		# {
		#     "label": _("Item Name"),
		#     "fieldname": "item_name",
		#     "width": 250
		# },
		{"label": _("Status"), "fieldname": "status", "width": 70},
		{"label": _("Item Group"), "fieldname": "item_group", "width": 150},
	]
	return columns


def get_item_prices(filters):
	"""Get item prices from various healthcare templates using query builder"""

	# Define the healthcare templates with their specific field mappings
	templates = [
		{
			"doctype": "Lab Test Template",
			"template_name_field": "lab_test_name",
			"item_code_field": "lab_test_code",
			"item_group_field": "lab_test_group",
		},
		{
			"doctype": "Radiology Examination Template",
			"template_name_field": "name",
			"item_code_field": "item_code",
			"item_group_field": "item_group",
		},
		{
			"doctype": "Medication",
			"template_name_field": "medication_name",
			"item_code_field": "item_code",
			"item_group_field": "item_group",
		},
		{
			"doctype": "Therapy Type",
			"template_name_field": "therapy_type",
			"item_code_field": "item_code",
			"item_group_field": "item_group",
		},
		{
			"doctype": "Clinical Procedure Template",
			"template_name_field": "template",
			"item_code_field": "item_code",
			"item_group_field": "item_group",
		},
		{
			"doctype": "Healthcare Service Unit Type",
			"template_name_field": "service_unit_type",
			"item_code_field": "item_code",
			"item_group_field": "item_group",
		},
	]

	queries = []

	for template_config in templates:
		query = build_template_query(template_config, filters)
		queries.append(query)

	# Union all queries
	final_query = queries[0]
	for query in queries[1:]:
		final_query = final_query.union(query)

	# Order by item_group and template_name
	final_query = final_query.orderby("item_group").orderby("template_name")

	return final_query.run(as_dict=True)


def build_template_query(template_config, filters):
	"""Build a query for a specific template doctype"""
	qb = frappe.qb

	# Get table references
	temp = qb.DocType(template_config["doctype"])
	ip = qb.DocType("Item Price")

	# Build the select query with LEFT JOIN
	query = (
		qb.from_(temp)
		.left_join(ip)
		.on(temp.item == ip.item_code)
		.select(
			temp[template_config.get("template_name_field")].as_("template_name"),
			temp[template_config.get("item_code_field")].as_("item_code"),
			Case().when(temp.disabled == 0, "Active").else_("Disabled").as_("status"),
			temp[template_config.get("item_group_field")].as_("item_group"),
			IfNull(ip.price_list, "NO PRICE").as_("price_list"),
			IfNull(ip.price_list_rate, 0).as_("price_list_rate"),
			IfNull(ip.valid_from, "2020-01-01").as_("valid_from"),
		)
		.distinct()
	)

	# Apply filters
	if filters.get("item_code"):
		query = query.where(ip.item_code == filters.get("item_code"))

	if filters.get("price_list"):
		query = query.where(ip.price_list == filters.get("price_list"))

	return query
