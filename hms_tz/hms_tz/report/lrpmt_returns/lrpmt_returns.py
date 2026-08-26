# Copyright (c) 2023, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	columns = [
		{
			"fieldname": "modified",
			"fieldtype": "Data",
			"label": _("Date"),
			"width": "115px",
		},
		{
			"fieldname": "encounter_no",
			"fieldtype": "Link",
			"label": _("Encounter Number"),
			"width": "115px",
		},
		{
			"fieldname": "reference_docname",
			"fieldtype": "Dynamic Link",
			"label": _("Reference Docname"),
			"width": "140px",
		},
		{
			"fieldname": "reference_doctype",
			"fieldtype": "Link",
			"label": _("Reference Doctype"),
			"width": "140px",
		},
		{
			"fieldname": "item_name",
			"fieldtype": "Data",
			"label": _("Item Name"),
			"width": "115px",
		},
		{
			"fieldname": "practitioner_name",
			"fieldtype": "Data",
			"label": _("Practitioner Name"),
			"width": "115px",
		},
		{
			"fieldname": "quantity_prescribed",
			"fieldtype": "Data",
			"label": _("Quantity Prescribed"),
			"width": "115px",
		},
		{
			"fieldname": "quantity_to_return",
			"fieldtype": "Data",
			"label": _("Quantity Returned"),
			"width": "115px",
		},
		{
			"fieldname": "reason",
			"fieldtype": "Data",
			"label": _("Reason"),
			"width": "115px",
		},
		{
			"fieldname": "drug_condition",
			"fieldtype": "Data",
			"label": _("Condition"),
			"width": "115px",
		},
	]
	return columns


def get_data(filters):
	conditions_item_return, conditions_medication_return = set_conditions(filters)
	return frappe.db.sql(
		f"""
        SELECT
            CAST(lr.modified AS DATE) AS modified,
            ir.encounter_no,
            ir.reference_docname,
            ir.reference_doctype,
            ir.item_name as item_name,
            pa.practitioner_name,
            ir.quantity as quantity_prescribed,
            0 as quantity_to_return,
            ir.reason,
            null as drug_condition
        FROM
            `tabLRPMT Returns` lr
        INNER JOIN
            `tabItem Return` ir ON lr.name = ir.parent
        INNER JOIN
            `tabPatient Encounter` pa ON pa.name = ir.encounter_no
        WHERE
            lr.docstatus = 1
            AND {conditions_item_return}

        UNION

        SELECT
            CAST(lr.modified AS DATE) AS modified,
            mr.encounter_no,
            mr.delivery_note_no as reference_docname,
            'Delivery Note' as reference_doctype,
            mr.drug_name as item_name,
            pa.practitioner_name,
            mr.quantity_prescribed,
            mr.quantity_to_return,
            mr.reason,
            mr.drug_condition

        FROM
            `tabLRPMT Returns` lr
        INNER JOIN
            `tabMedication Return` mr ON lr.name = mr.parent
        INNER JOIN
            `tabPatient Encounter` pa ON pa.name = mr.encounter_no
        WHERE
            lr.docstatus = 1
            AND {conditions_medication_return}
        """,
		filters,
		as_dict=True,
	)


def set_conditions(filters):
	conditions_item_return = ""
	conditions_medication_return = ""

	if filters.get("from_date") and filters.get("to_date"):
		conditions_item_return += " lr.modified  BETWEEN %(from_date)s AND %(to_date)s"
		conditions_medication_return += " lr.modified  BETWEEN %(from_date)s AND %(to_date)s"
	if filters.get("practitioner_name"):
		conditions_item_return += " AND pa.practitioner_name =  %(practitioner_name)s"
		conditions_medication_return += " AND pa.practitioner_name =  %(practitioner_name)s"
	if filters.get("reference_doctype"):
		conditions_item_return += " AND ir.reference_doctype =  %(reference_doctype)s"
		conditions_medication_return += " AND %(reference_doctype)s = 'Delivery Note'"
	if filters.get("item"):
		conditions_item_return += " AND ir.item_name =  %(item)s"
		conditions_medication_return += " AND mr.drug_name =  %(item)s"
	if filters.get("reason"):
		conditions_item_return += " AND ir.reason =  %(reason)s"
		conditions_medication_return += " AND mr.reason =  %(reason)s"
	if filters.get("item_condition"):
		# conditions_item_return += " AND ir.item_condition =  %(item_condition)s"
		conditions_medication_return += " AND mr.drug_condition =  %(item_condition)s"

	return conditions_item_return, conditions_medication_return
