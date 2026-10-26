"""Mark rows billed by a submitted Sales Invoice as invoiced.

A Sales Invoice with many items could time out on submit after it was saved,
so some rows it billed kept invoiced = 0 and stayed in the IPD Billing Report.
"""

from collections import defaultdict

import frappe
from frappe.query_builder import DocType
from frappe.utils import add_months, get_first_day, get_last_day, getdate, today
from pypika.terms import ExistsCriterion

from hms_tz.nhif.api.healthcare_utils import INVOICED_FIELDS
from hms_tz.nhif.api.sales_invoice import set_references_invoiced

START_DATE = "2026-06-01"


def execute():
	month_start = getdate(START_DATE)
	while month_start <= getdate(today()):
		frappe.enqueue(
			"hms_tz.patches.set_missing_invoiced_references.set_month_invoiced_references",
			queue="long",
			job_id=f"set_missing_invoiced_references::{month_start}",
			deduplicate=True,
			month_start=str(month_start),
		)
		month_start = add_months(month_start, 1)


def set_month_invoiced_references(month_start: str):
	from_date, to_date = get_first_day(month_start), get_last_day(month_start)
	for reference_dt in INVOICED_FIELDS:
		names_by_invoice = defaultdict(list)
		for row in get_uninvoiced_references(reference_dt, from_date, to_date):
			names_by_invoice[row.invoice].append(row.name)

		for invoice, names in names_by_invoice.items():
			set_references_invoiced(reference_dt, names, invoice)


def get_uninvoiced_references(reference_dt: str, from_date, to_date) -> list[dict]:
	"""Rows that a submitted invoice in the date range bills, still not invoiced and not returned."""
	reference = DocType(reference_dt)
	invoice = DocType("Sales Invoice")
	item = DocType("Sales Invoice Item")
	return_invoice = DocType("Sales Invoice").as_("return_invoice")
	return_item = DocType("Sales Invoice Item").as_("return_item")

	returned = (
		frappe.qb.from_(return_item)
		.inner_join(return_invoice)
		.on(return_invoice.name == return_item.parent)
		.select(return_item.name)
		.where(return_invoice.docstatus == 1)
		.where(return_invoice.return_against == invoice.name)
		.where(return_item.reference_dn == item.reference_dn)
	)

	return (
		frappe.qb.from_(item)
		.inner_join(invoice)
		.on(invoice.name == item.parent)
		.inner_join(reference)
		.on(reference.name == item.reference_dn)
		.select(invoice.name.as_("invoice"), reference.name)
		.where(invoice.docstatus == 1)
		.where(invoice.is_return == 0)
		.where(invoice.posting_date[from_date:to_date])
		.where(item.reference_dt == reference_dt)
		.where(reference[INVOICED_FIELDS[reference_dt]] == 0)
		.where(ExistsCriterion(returned).negate())
	).run(as_dict=True)
