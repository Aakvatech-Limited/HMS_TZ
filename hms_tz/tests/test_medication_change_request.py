# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.doctype.medication_change_request import medication_change_request as mcr

STORE_A = "_Test MCR Store A"
STORE_B = "_Test MCR Store B"
SERVICE_UNIT_WAREHOUSE = {"_Test MCR Pharmacy A": STORE_A, "_Test MCR Pharmacy B": STORE_B}
STOCK = {("_Test MCR Item", STORE_A): 5}


def make_row(service_unit="_Test MCR Pharmacy A", quantity=2, **values):
	return frappe._dict(
		{
			"doctype": "Drug Prescription",
			"idx": 1,
			"drug_code": "_Test MCR Drug",
			"healthcare_service_unit": service_unit,
			"quantity": quantity,
			"quantity_returned": 0,
			"prescribe": 1,
			"is_not_available_inhouse": 0,
			"is_cancelled": 0,
			**values,
		}
	)


def get_warehouse_from_service_unit(service_unit):
	return SERVICE_UNIT_WAREHOUSE[service_unit]


@patch.object(mcr, "get_warehouse_from_service_unit", get_warehouse_from_service_unit)
@patch.object(mcr, "get_stock_availability", lambda item_code, warehouse: STOCK.get((item_code, warehouse)))
@patch.object(mcr, "get_item_info", return_value={"item_code": "_Test MCR Item", "is_stock": 1})
class TestMedicationChangeRequestStock(FrappeTestCase):
	def make_request(self, insurance_subscription=None):
		request = frappe.new_doc("Medication Change Request")
		request.company = "_Test MCR Company"
		request.insurance_subscription = insurance_subscription
		return request

	def test_cash_short_stock_throws_with_service_unit_warehouse(self, _):
		with self.assertRaisesRegex(frappe.ValidationError, STORE_B):
			self.make_request().validate_drug_quantity(make_row("_Test MCR Pharmacy B"))

	def test_cash_enough_stock_passes(self, _):
		self.make_request().validate_drug_quantity(make_row(quantity=5))

	def test_cash_check_uses_quantity_after_returns(self, _):
		self.make_request().validate_drug_quantity(make_row(quantity=7, quantity_returned=2))

	def test_not_available_inhouse_skips_stock_check(self, _):
		self.make_request().validate_drug_quantity(
			make_row("_Test MCR Pharmacy B", is_not_available_inhouse=1)
		)

	def test_missing_service_unit_throws(self, _):
		with self.assertRaisesRegex(frappe.ValidationError, "Healthcare Service Unit"):
			self.make_request().validate_drug_quantity(make_row(service_unit=None))

	def test_insurance_follows_healthcare_settings(self, _):
		row = make_row("_Test MCR Pharmacy B")
		with patch.object(mcr, "validate_stock_item") as validate_stock_item:
			self.make_request("_Test MCR Subscription").validate_drug_quantity(row)

		validate_stock_item.assert_called_once_with(
			row.drug_code,
			row.quantity,
			"_Test MCR Company",
			1,
			healthcare_service_unit="_Test MCR Pharmacy B",
			caller="Drug Prescription",
			method="validate",
		)


@patch.object(mcr, "get_warehouse_from_service_unit", get_warehouse_from_service_unit)
@patch.object(
	mcr.frappe,
	"get_cached_value",
	lambda doctype, name, fieldname: name if fieldname == "item" else (name, name),
)
class TestMedicationChangeRequestSalesOrder(FrappeTestCase):
	def update_sales_order(self, *service_units):
		order = SimpleNamespace(
			items=[frappe._dict(warehouse="_Test MCR Pharmacist Store")],
			set_warehouse="_Test MCR Pharmacist Store",
			save=MagicMock(),
			add_comment=MagicMock(),
			reload=MagicMock(),
		)
		order.append = lambda fieldname, row: order.items.append(frappe._dict(row))
		rows = [make_row(unit, drug_code=f"_Test MCR Drug {i}") for i, unit in enumerate(service_units)]
		encounter = frappe._dict(drug_prescription=rows)

		request = frappe.new_doc("Medication Change Request")
		request.sales_order = "_Test MCR SO"
		request.name = "_Test MCR"
		get_cached_doc = frappe.get_cached_doc
		with patch.object(
			mcr.frappe,
			"get_cached_doc",
			side_effect=lambda doctype, *args: order
			if doctype == "Sales Order"
			else get_cached_doc(doctype, *args),
		):
			request.update_sales_order(encounter)
		return order

	def test_items_reset_to_service_unit_warehouse(self):
		order = self.update_sales_order("_Test MCR Pharmacy A", "_Test MCR Pharmacy B")
		self.assertEqual([item.warehouse for item in order.items], [STORE_A, STORE_B])
		self.assertIsNone(order.set_warehouse)

	def test_one_warehouse_sets_header_warehouse(self):
		order = self.update_sales_order("_Test MCR Pharmacy A", "_Test MCR Pharmacy A")
		self.assertEqual(order.set_warehouse, STORE_A)
