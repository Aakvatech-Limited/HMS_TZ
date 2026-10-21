# Copyright (c) 2013, Aakvatech and contributors
# For license information, please see license.txt

import frappe
import numpy as np
import pandas as pd
from frappe import _, msgprint
from frappe.query_builder import DocType
from frappe.query_builder.functions import Count, Date, DateFormat


def execute(filters=None):
	columns = get_columns()
	data = []

	occupancy_details = get_service_unit_details(filters)
	if not occupancy_details:
		msgprint(
			frappe.bold("No Service Unit Record For the Filters You Set, Please Set Different Filters..!!")
		)
	else:
		occupancy_colnames = [key for key in occupancy_details[0].keys()]
		df = pd.DataFrame.from_records(occupancy_details, columns=occupancy_colnames)

		pv_table = pd.pivot_table(
			df,
			index=["bed"],
			columns=["date"],
			values="count",
			fill_value=" ",
			aggfunc=np.size,
			margins=True,
		)

		columns += pv_table.columns.values.tolist()

		data += pv_table.reset_index().values.tolist()

	return columns, data


def get_columns():
	columns = [
		{
			"fieldname": "bed",
			"fieldtype": "Link",
			"label": _("Beds"),
			"options": "Healthcare Service Unit",
		}
	]
	return columns


def get_service_unit_details(filters):
	if not filters.get("from_date"):
		frappe.throw(_("From Date is required"))

	occupancy = DocType("Inpatient Occupancy")
	check_in_date = Date(occupancy.check_in)

	query = (
		frappe.qb.from_(occupancy)
		.select(
			occupancy.service_unit.as_("bed"),
			DateFormat(check_in_date, "%Y-%m-%d").as_("date"),
			Count("*").as_("count"),
		)
		.groupby(occupancy.service_unit, check_in_date)
	)

	query = query.where(check_in_date >= filters.get("from_date"))
	if filters.get("to_date"):
		query = query.where(check_in_date <= filters.get("to_date"))

	return query.run(as_dict=True)
