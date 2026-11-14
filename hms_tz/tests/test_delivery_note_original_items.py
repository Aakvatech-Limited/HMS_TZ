import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.api.delivery_note import check_item_for_out_of_stock, set_original_item


def make_delivery_note(*item_codes):
	delivery_note = frappe.new_doc("Delivery Note")
	for idx, item_code in enumerate(item_codes, 1):
		delivery_note.append(
			"items",
			{"name": f"row-{idx}", "item_code": item_code, "qty": 1, "stock_qty": 2, "amount": 10},
		)
	return delivery_note


class TestDeliveryNoteOriginalItems(FrappeTestCase):
	def test_snapshot_taken_once(self):
		delivery_note = make_delivery_note("A", "B")
		set_original_item(delivery_note)

		self.assertEqual([row.item_code for row in delivery_note.hms_tz_original_items], ["A", "B"])
		self.assertEqual(delivery_note.items[0].original_item, "A")
		self.assertEqual(delivery_note.items[0].original_stock_uom_qty, 2)

		delivery_note.items[0].item_code = "C"
		set_original_item(delivery_note)
		self.assertEqual([row.item_code for row in delivery_note.hms_tz_original_items], ["A", "B"])
		self.assertEqual(delivery_note.items[0].original_item, "A")

	def test_amendment_keeps_copied_snapshot(self):
		delivery_note = make_delivery_note("A", "B")
		delivery_note.append("hms_tz_original_items", {"item_code": "A"})
		delivery_note.append("hms_tz_original_items", {"item_code": "B"})
		delivery_note.items[1].original_item = "X"  # copied from the cancelled document
		set_original_item(delivery_note)

		self.assertEqual(len(delivery_note.hms_tz_original_items), 2)
		self.assertEqual(delivery_note.items[1].original_item, "X")

	def test_out_of_stock_keeps_row_identity(self):
		delivery_note = make_delivery_note("A", "B", "C")
		set_original_item(delivery_note)
		delivery_note.items[1].hms_tz_is_out_of_stock = 1

		check_item_for_out_of_stock(delivery_note)

		self.assertEqual([row.name for row in delivery_note.items], ["row-1", "row-3"])
		flags = {row.item_code: row.hms_tz_is_out_of_stock for row in delivery_note.hms_tz_original_items}
		self.assertEqual(flags, {"A": 0, "B": 1, "C": 0})
		self.assertEqual((delivery_note.total, delivery_note.total_qty), (20, 2))
