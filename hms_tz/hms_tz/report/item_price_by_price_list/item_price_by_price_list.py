# Copyright (c) 2023, Aakvatech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
import pandas as pd
from frappe import _


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
    item_code_condition = ""
    price_list_condition = ""
    values = {}

    if filters.get("item_code"):
        item_code_condition = " AND ip.item_code = %(item_code)s"
        values["item_code"] = filters["item_code"]

    if filters.get("price_list"):
        price_list_condition = " AND ip.price_list = %(price_list)s"
        values["price_list"] = filters["price_list"]

    return frappe.db.sql(
        """
        SELECT DISTINCT temp.lab_test_name as template_name,
                temp.lab_test_code as item_code,
                IF(temp.disabled = 0, "Active", "Disabled") as status,
                temp.lab_test_group as item_group,
                IF(ip.price_list IS NULL, "NO PRICE", ip.price_list) as price_list,
                IF(ip.price_list IS NULL, 0, ip.price_list_rate) as price_list_rate,
                IF(ip.price_list IS NULL, "2020-01-01", ip.valid_from) as valid_from
        FROM `tabLab Test Template` temp LEFT JOIN `tabItem Price` ip ON temp.item = ip.item_code
        WHERE 1=1 {item_code_condition} {price_list_condition}
        UNION
        SELECT DISTINCT temp.name as template_name,
                temp.item_code as item_code,
                IF(temp.disabled = 0, "Active", "Disabled") as status,
                temp.item_group as item_group,
                IF(ip.price_list IS NULL, "NO PRICE", ip.price_list) as price_list,
                IF(ip.price_list IS NULL, 0, ip.price_list_rate) as price_list_rate,
                IF(ip.price_list IS NULL, "2020-01-01", ip.valid_from) as valid_from
        FROM `tabRadiology Examination Template` temp LEFT JOIN `tabItem Price` ip ON temp.item = ip.item_code
        WHERE 1=1 {item_code_condition} {price_list_condition}
        UNION
        SELECT DISTINCT temp.medication_name as template_name,
                temp.item_code as item_code,
                IF(temp.disabled = 0, "Active", "Disabled") as status,
                temp.item_group as item_group,
                IF(ip.price_list IS NULL, "NO PRICE", ip.price_list) as price_list,
                IF(ip.price_list IS NULL, 0, ip.price_list_rate) as price_list_rate,
                IF(ip.price_list IS NULL, "2020-01-01", ip.valid_from) as valid_from
        FROM `tabMedication` temp LEFT JOIN `tabItem Price` ip ON temp.item = ip.item_code
        WHERE 1=1 {item_code_condition} {price_list_condition}
        UNION
        SELECT DISTINCT temp.therapy_type as template_name,
                temp.item_code as item_code,
                IF(temp.disabled = 0, "Active", "Disabled") as status,
                temp.item_group as item_group,
                IF(ip.price_list IS NULL, "NO PRICE", ip.price_list) as price_list,
                IF(ip.price_list IS NULL, 0, ip.price_list_rate) as price_list_rate,
                IF(ip.price_list IS NULL, "2020-01-01", ip.valid_from) as valid_from
        FROM `tabTherapy Type` temp LEFT JOIN `tabItem Price` ip ON temp.item = ip.item_code
        WHERE 1=1 {item_code_condition} {price_list_condition}
        UNION
        SELECT DISTINCT temp.template as template_name,
                temp.item_code as item_code,
                IF(temp.disabled = 0, "Active", "Disabled") as status,
                temp.item_group as item_group,
                IF(ip.price_list IS NULL, "NO PRICE", ip.price_list) as price_list,
                IF(ip.price_list IS NULL, 0, ip.price_list_rate) as price_list_rate,
                IF(ip.price_list IS NULL, "2020-01-01", ip.valid_from) as valid_from
        FROM `tabClinical Procedure Template` temp LEFT JOIN `tabItem Price` ip ON temp.item = ip.item_code
        WHERE 1=1 {item_code_condition} {price_list_condition}
        UNION
        SELECT DISTINCT temp.service_unit_type as template_name,
                temp.item_code as item_code,
                IF(temp.disabled = 0, "Active", "Disabled") as status,
                temp.item_group as item_group,
                IF(ip.price_list IS NULL, "NO PRICE", ip.price_list) as price_list,
                IF(ip.price_list IS NULL, 0, ip.price_list_rate) as price_list_rate,
                IF(ip.price_list IS NULL, "2020-01-01", ip.valid_from) as valid_from
        FROM `tabHealthcare Service Unit Type` temp LEFT JOIN `tabItem Price` ip ON temp.item = ip.item_code
        WHERE 1=1 {item_code_condition} {price_list_condition}
        ORDER BY item_group, template_name ASC
    """.format(
            item_code_condition=item_code_condition,
            price_list_condition=price_list_condition,
        ),
        values,
        as_dict=1,
    )
