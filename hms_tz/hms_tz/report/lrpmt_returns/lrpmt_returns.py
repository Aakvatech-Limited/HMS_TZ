# Copyright (c) 2023, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.query_builder.functions import Cast_, Date
from frappe.query_builder.terms import ParameterizedValueWrapper

ITEM_TEMPLATE_DOCTYPES = (
	"Lab Test Template",
	"Radiology Examination Template",
	"Clinical Procedure Template",
)


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
	returns = DocType("LRPMT Returns")
	encounter = DocType("Patient Encounter")
	query = get_item_return_query(returns, encounter, filters).union_all(
		get_medication_return_query(returns, encounter, filters)
	)
	return query.run(as_dict=True)


def get_item_return_query(returns, encounter, filters):
	item_return = DocType("Item Return")
	criteria = get_return_criteria(returns, encounter, filters)

	if filters.get("reference_doctype"):
		criteria &= item_return.reference_doctype == filters.get("reference_doctype")

	if filters.get("item"):
		criteria &= item_return.item_name.isin(get_item_return_names(filters.get("item")))

	if filters.get("reason"):
		criteria &= item_return.reason == filters.get("reason")

	return (
		frappe.qb.from_(returns)
		.inner_join(item_return)
		.on(returns.name == item_return.parent)
		.inner_join(encounter)
		.on(encounter.name == item_return.encounter_no)
		.select(
			Cast_(returns.modified, "DATE").as_("modified"),
			item_return.encounter_no,
			item_return.reference_docname,
			item_return.reference_doctype,
			item_return.item_name.as_("item_name"),
			encounter.practitioner_name,
			item_return.quantity.as_("quantity_prescribed"),
			ParameterizedValueWrapper(0).as_("quantity_to_return"),
			item_return.reason,
			ParameterizedValueWrapper(None).as_("drug_condition"),
		)
		.where(criteria)
	)


def get_item_return_names(item: str) -> list[str]:
	"""Item Return stores the template name, so match templates billed with this item."""
	names = [item]
	for doctype in ITEM_TEMPLATE_DOCTYPES:
		names += frappe.get_all(doctype, filters={"item": item}, pluck="name")

	return names


def get_medication_return_query(returns, encounter, filters):
	medication_return = DocType("Medication Return")
	criteria = get_return_criteria(returns, encounter, filters)

	if filters.get("reference_doctype"):
		criteria &= ParameterizedValueWrapper(filters.get("reference_doctype")) == "Delivery Note"

	if filters.get("item"):
		criteria &= medication_return.drug_name == filters.get("item")

	if filters.get("reason"):
		criteria &= medication_return.reason == filters.get("reason")

	if filters.get("item_condition"):
		criteria &= medication_return.drug_condition == filters.get("item_condition")

	return (
		frappe.qb.from_(returns)
		.inner_join(medication_return)
		.on(returns.name == medication_return.parent)
		.inner_join(encounter)
		.on(encounter.name == medication_return.encounter_no)
		.select(
			Cast_(returns.modified, "DATE").as_("modified"),
			medication_return.encounter_no,
			medication_return.delivery_note_no.as_("reference_docname"),
			ParameterizedValueWrapper("Delivery Note").as_("reference_doctype"),
			medication_return.drug_name.as_("item_name"),
			encounter.practitioner_name,
			medication_return.quantity_prescribed,
			medication_return.quantity_to_return,
			medication_return.reason,
			medication_return.drug_condition,
		)
		.where(criteria)
	)


def get_return_criteria(returns, encounter, filters):
	criteria = returns.docstatus == 1

	if filters.get("from_date") and filters.get("to_date"):
		criteria &= Date(returns.modified).between(filters.get("from_date"), filters.get("to_date"))

	if filters.get("practitioner"):
		criteria &= encounter.practitioner == filters.get("practitioner")

	return criteria
