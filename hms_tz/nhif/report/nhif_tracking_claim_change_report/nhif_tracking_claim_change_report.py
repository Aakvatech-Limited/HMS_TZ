# Copyright (c) 2023, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	parameters = get_conditions(filters)
	items = frappe.get_all("NHIF Tracking Claim Change", filters=parameters, fields=["*"])
	items_removed = 0
	amount_for_items_removed = 0
	items_amount_changed = 0
	amount_for_items_amount_changed = 0
	items_replaced = 0
	amount_for_items_replaced = 0
	items_cancelled = 0
	amount_for_items_cancelled = 0
	items_unconfirmed = 0
	amount_for_items_unconfirmed = 0

	total_current_amount = 0
	total_previous_amount = 0
	total_amount_changed = 0

	data = []
	for item in items:
		if item.status == "Item Removed":
			items_removed += 1
			amount_for_items_removed += item.current_amount

		elif item.status == "Amount Changed":
			items_amount_changed += 1
			amount_for_items_amount_changed += item.previous_amount - item.current_amount

		elif item.status == "Item Replaced":
			items_replaced += 1
			amount_for_items_replaced += item.current_amount

		elif item.status == "Item Cancelled":
			items_cancelled += 1
			amount_for_items_cancelled += item.current_amount

		elif item.status == "Item Unconfirmed":
			items_unconfirmed += 1
			amount_for_items_unconfirmed += item.current_amount

		item.update(
			{
				"posting_datetime": str(item.posting_date) + " " + str(item.posting_time),
			}
		)
		data.append(item)

		total_previous_amount += item.previous_amount
		total_current_amount += item.current_amount
		total_amount_changed += item.amount_changed

	data.extend(
		[
			{
				"item_name": "Total",
				"previous_amount": total_previous_amount,
				"current_amount": total_current_amount,
				"amount_changed": total_amount_changed,
			},
		]
	)

	columns = get_columns(filters)

	dashboard = get_report_dashboards(
		amount_for_items_removed,
		amount_for_items_amount_changed,
		amount_for_items_replaced,
		amount_for_items_cancelled,
		amount_for_items_unconfirmed,
	)
	report_summary = get_report_summary(
		items_removed,
		items_amount_changed,
		items_replaced,
		items_cancelled,
		items_unconfirmed,
	)

	return columns, data, None, dashboard, report_summary


def get_report_summary(
	items_removed,
	items_amount_changed,
	items_replaced,
	items_cancelled,
	items_unconfirmed,
):
	total_amount_count = (
		items_removed + items_amount_changed + items_replaced + items_cancelled + items_unconfirmed
	)

	return [
		{
			"value": items_removed,
			"label": _("Items Removed"),
			"datatype": "Int",
		},
		{
			"value": items_cancelled,
			"label": _("Items Cancelled"),
			"datatype": "Int",
		},
		{
			"value": items_replaced,
			"label": _("Items Replaced"),
			"datatype": "Int",
		},
		{
			"value": items_unconfirmed,
			"label": _("Items Unconfirmed"),
			"datatype": "Int",
		},
		{
			"value": items_amount_changed,
			"label": _("Item's Amount Changed"),
			"datatype": "Int",
		},
		{
			"value": total_amount_count,
			"label": _("Total Count"),
			"datatype": "Int",
		},
	]


def get_report_dashboards(
	amount_for_items_removed,
	amount_for_items_amount_changed,
	amount_for_items_replaced,
	amount_for_items_cancelled,
	amount_for_items_unconfirmed,
):
	return {
		"data": {
			"labels": [
				"Items Removed",
				"Items Cancelled",
				"Items Replaced",
				"Items Unconfirmed",
				"Items Amount Changed",
			],
			"datasets": [
				{
					"name": _("Amount"),
					"values": [
						amount_for_items_removed,
						amount_for_items_cancelled,
						amount_for_items_replaced,
						amount_for_items_unconfirmed,
						amount_for_items_amount_changed,
					],
				},
			],
		},
		"type": "bar",
		"fieldtype": "Currency",
		"colors": ["blue"],
		"height": 800,
	}


def get_conditions(filters):
	parameters = {}
	if filters.get("company"):
		parameters["company"] = filters.get("company")
	if filters.get("claim_month"):
		parameters["claim_month"] = filters.get("claim_month")
	if filters.get("claim_year"):
		parameters["claim_year"] = filters.get("claim_year")
	if filters.get("status"):
		parameters["status"] = filters.get("status")
	if filters.get("nhif_patient_claim"):
		parameters["nhif_patient_claim"] = filters.get("nhif_patient_claim")
	if filters.get("claim_submitted_by"):
		parameters["edited_by"] = filters.get("claim_submitted_by")

	return parameters


def get_columns(filters):
	columns = [
		{
			"fieldname": "posting_datetime",
			"label": "Date",
			"fieldtype": "Datetime",
			"width": 160,
		},
		{
			"fieldname": "item_code",
			"label": "Item Code",
			"fieldtype": "Data",
			"width": 60,
		},
		{
			"fieldname": "item_name",
			"label": "Item Name",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"fieldname": "quantity",
			"label": "Qty",
			"fieldtype": "Int",
			"width": 40,
		},
		{
			"fieldname": "previous_amount",
			"label": "Previous Amount",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"fieldname": "current_amount",
			"label": "Current Amount",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"fieldname": "amount_changed",
			"label": "Amount Changed",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"fieldname": "status",
			"label": "Status",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"fieldname": "nhif_patient_claim",
			"label": "NHIF Patient Claim",
			"fieldtype": "Link",
			"options": "NHIF Patient Claim",
			"width": 150,
		},
		{
			"fieldname": "patient_appointment",
			"label": "Patient Appointment",
			"fieldtype": "Link",
			"options": "Patient Appointment",
			"width": 150,
		},
		{
			"fieldname": "patient_encounter",
			"label": "Patient Encounter",
			"fieldtype": "Link",
			"options": "Patient Encounter",
			"width": 150,
		},
		{
			"fieldname": "lrpmt_return",
			"label": "LRPMT Return",
			"fieldtype": "Link",
			"options": "LRPMT Returns",
			"width": 150,
		},
		{
			"fieldname": "medication_change_request",
			"label": "Medication Change Request",
			"fieldtype": "Link",
			"options": "Medication Change Request",
			"width": 150,
		},
		{
			"fieldname": "edited_by",
			"label": "Claim Submitted By",
			"fieldtype": "Data",
			"width": 150,
		},
		# {"fieldname": "comment", "label": "Comment", "fieldtype": "Data", "width": 200},
	]

	return columns
