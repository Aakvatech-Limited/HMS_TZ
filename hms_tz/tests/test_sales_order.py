# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.api import sales_order

COMPANY = "_Test SO Company"
STORE_A = "_Test SO Store A"
STORE_B = "_Test SO Store B"
SERVICE_UNIT_WAREHOUSE = {"_Test SO Pharmacy A": STORE_A, "_Test SO Pharmacy B": STORE_B}


def make_drug_row(name, service_unit):
	return frappe._dict(
		{
			"doctype": "Drug Prescription",
			"name": name,
			"drug_code": name,
			"healthcare_service_unit": service_unit,
			"prescribe": 1,
			"is_not_available_inhouse": 0,
			"is_cancelled": 0,
			"quantity": 2,
			"quantity_returned": 0,
		}
	)


def make_encounter(drug_rows):
	encounter = frappe._dict(
		{
			"name": "_Test SO PE",
			"company": COMPANY,
			"practitioner": None,
			"healthcare_service_unit": None,
			"drug_prescription": drug_rows,
		}
	)
	for field in sales_order.get_childs_map():
		encounter.setdefault(field["table"], [])
	return encounter


def get_cached_value(doctype, name, fieldname, *args, **kwargs):
	if fieldname == "item":
		return name
	return name, name


def get_warehouse_from_service_unit(service_unit):
	if service_unit not in SERVICE_UNIT_WAREHOUSE:
		frappe.throw(f"Warehouse is missing in Healthcare Service Unit {service_unit}")
	return SERVICE_UNIT_WAREHOUSE[service_unit]


@patch.object(sales_order, "get_warehouse_from_service_unit", get_warehouse_from_service_unit)
@patch.object(sales_order.frappe, "get_cached_value", get_cached_value)
class TestSalesOrderWarehouse(FrappeTestCase):
	def get_drug_items(self, *service_units):
		rows = [make_drug_row(f"_Test SO Drug {index}", unit) for index, unit in enumerate(service_units)]
		drug_items, _ = sales_order.get_items_from_encounter(make_encounter(rows))
		return drug_items

	def test_drug_rows_take_their_service_unit_warehouse(self):
		drug_items = self.get_drug_items("_Test SO Pharmacy A", "_Test SO Pharmacy B")
		self.assertEqual([item["warehouse"] for item in drug_items], [STORE_A, STORE_B])

	def test_service_unit_without_warehouse_throws(self):
		with self.assertRaises(frappe.ValidationError):
			self.get_drug_items("_Test SO Pharmacy Without Warehouse")


class TestSalesOrderSetWarehouse(FrappeTestCase):
	def create_order(self, warehouses):
		items = [
			{"item_code": f"_Test SO Drug {index}", "warehouse": w} for index, w in enumerate(warehouses)
		]
		order = MagicMock()
		with (
			patch.object(sales_order.frappe, "get_cached_value", return_value="_Test Price List"),
			patch.object(sales_order.frappe, "new_doc", return_value=order),
		):
			sales_order.create_sales_order_from_encounter(make_encounter([]), items)
		return order.update.call_args.args[0]

	def test_one_warehouse_sets_header_warehouse(self):
		self.assertEqual(self.create_order([STORE_A, STORE_A])["set_warehouse"], STORE_A)

	def test_mixed_warehouses_leave_header_warehouse_empty(self):
		self.assertIsNone(self.create_order([STORE_A, STORE_B])["set_warehouse"])

	def test_items_without_warehouse_leave_header_warehouse_empty(self):
		self.assertIsNone(self.create_order([None])["set_warehouse"])


class TestSalesOrderStockCheck(FrappeTestCase):
	def make_order(self):
		return SimpleNamespace(
			med_change_request_status="",
			set_warehouse=None,
			items=[
				frappe._dict(item_code="_Test SO Drug A", qty=2, warehouse=STORE_A, idx=1),
				frappe._dict(item_code="_Test SO Drug B", qty=2, warehouse=STORE_B, idx=2),
			],
		)

	@patch.object(sales_order.frappe, "get_cached_value", return_value=1)
	def test_each_row_is_checked_in_its_own_warehouse(self, _):
		with patch.object(sales_order, "get_stock_availability", return_value=5) as stock:
			sales_order.before_submit(self.make_order(), "before_submit")

		self.assertEqual(
			[call.args for call in stock.call_args_list],
			[("_Test SO Drug A", STORE_A), ("_Test SO Drug B", STORE_B)],
		)

	@patch.object(sales_order.frappe, "get_cached_value", return_value=1)
	def test_short_stock_names_the_row_warehouse(self, _):
		stock = {("_Test SO Drug A", STORE_A): 5, ("_Test SO Drug B", STORE_B): 0}
		with (
			patch.object(sales_order, "get_stock_availability", side_effect=lambda *key: stock[key]),
			self.assertRaisesRegex(frappe.ValidationError, STORE_B),
		):
			sales_order.before_submit(self.make_order(), "before_submit")
