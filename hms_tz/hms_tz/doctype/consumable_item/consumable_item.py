# Copyright (c) 2026, Aakvatech and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.query_builder.functions import Coalesce
from frappe.utils import flt
from pypika.functions import NullIf


class ConsumableItem(Document):
	pass


def get_billable_qty(item) -> float:
	"""Charged quantity of a Consumable Item: used, else dispensed, else requested.

	consumable_record.js calculates the row amount with the same rule.
	"""
	return flt(item.qty_used) or flt(item.qty_dispensed) or flt(item.qty_requested)


def get_billable_qty_column(consumable_item):
	"""Query form of get_billable_qty for a Consumable Item table."""
	return Coalesce(
		NullIf(consumable_item.qty_used, 0),
		NullIf(consumable_item.qty_dispensed, 0),
		consumable_item.qty_requested,
	)
