# Copyright (c) 2026, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate, nowtime

from hms_tz.nhif.api.patient_encounter import validate_patient_balance_vs_patient_costs


class ConsumableRecord(Document):
	def before_save(self):
		self.set_inpatient_record()
		self.set_stock_item_flags()
		self.calculate_totals()

	def before_submit(self):
		self.validate_items()
		self.validate_cash_patient_deposit()

	def on_submit(self):
		self.try_create_delivery_note()

	def set_inpatient_record(self):
		"""Auto-set inpatient_record if patient has an active admission."""
		if not self.inpatient_record and self.patient:
			inpatient_record = frappe.db.get_value("Patient", self.patient, "inpatient_record")
			if inpatient_record:
				self.inpatient_record = inpatient_record

	def set_stock_item_flags(self):
		"""Set is_stock_item on each item row from Item master."""
		for item in self.items:
			if item.item_code:
				is_stock = frappe.get_cached_value("Item", item.item_code, "is_stock_item")
				item.is_stock_item = 1 if is_stock else 0

	def calculate_totals(self):
		"""Calculate amount per item and total amount."""
		total = 0
		for item in self.items:
			qty = flt(item.qty_used) or flt(item.qty_dispensed) or flt(item.qty_requested)
			item.amount = flt(qty * flt(item.rate))
			total += flt(item.amount)

		self.total_amount = total

	def validate_items(self):
		"""Validate that items exist and have required fields."""
		if not self.items or len(self.items) == 0:
			frappe.throw(_("Please add at least one consumable item"))

		for item in self.items:
			if not item.item_code:
				frappe.throw(_(f"Row {item.idx}: Item Code is required"))
			if not item.warehouse:
				frappe.throw(_(f"Row {item.idx}: Warehouse is required"))
			if flt(item.qty_requested) <= 0:
				frappe.throw(_(f"Row {item.idx}: Qty Requested must be greater than 0"))

	def validate_cash_patient_deposit(self):
		"""For cash patients, validate deposit balance including all patient costs."""
		if self.payment_type != "Cash":
			return

		if not self.inpatient_record:
			return

		validate_patient_balance_vs_patient_costs(
			patient=self.patient,
			patient_name=self.patient_name,
			appointment=self.appointment,
			inpatient_record=self.inpatient_record,
			company=self.company,
			caller="Consumable Record",
			exclude_consumable=self.name if not self.is_new() else None,
		)

	def try_create_delivery_note(self):
		"""Create Delivery Note if all payment conditions are met.

		- Full cash patient (self.payment_type == "Cash"):
		  Deposit already validated by validate_cash_patient_deposit,
		  so create DN immediately.
		- Insurance patient (self.payment_type == "Insurance"):
		  If any item-level cash co-pay items are uninvoiced,
		  hold DN until Sales Invoice is created and paid.
		"""
		if self.payment_type == "Insurance":
			# Check for uninvoiced cash co-pay items at the item level
			has_uninvoiced_cash = any(
				item.payment_type == "Cash" and not item.invoiced for item in self.items
			)

			if has_uninvoiced_cash:
				self.db_set("status", "Pending Payment")
				self.db_set("has_pending_payment", 1)
				frappe.msgprint(
					_(
						"Consumable Record submitted. Some items require cash payment."
						" Delivery Note will be created after a Sales Invoice is done."
					),
					alert=True,
				)
				return

		# Full cash patient (deposit validated) or insurance with all items covered
		self.db_set("has_pending_payment", 0)
		self._create_delivery_note()

	def _create_delivery_note(self):
		"""Internal method to create Delivery Note grouped by warehouse."""
		warehouses_map = {}

		for item in self.items:
			if not item.is_stock_item:
				continue

			warehouse = item.warehouse
			if not warehouse:
				frappe.throw(_(f"Row {item.idx}: Warehouse is required for stock item {item.item_code}"))

			if warehouse not in warehouses_map:
				warehouses_map[warehouse] = []
			warehouses_map[warehouse].append(item)

		if not warehouses_map:
			self.db_set("status", "Submitted")
			return

		# Determine customer
		customer = ""
		if self.insurance_company:
			customer = frappe.get_cached_value(
				"Healthcare Insurance Company", self.insurance_company, "customer"
			)
		if not customer:
			customer = frappe.get_cached_value("Patient", self.patient, "customer")

		if not customer:
			frappe.throw(_(f"Customer not found for patient {self.patient}"))

		company_currency = frappe.get_cached_value("Company", self.company, "default_currency")

		for warehouse, items in warehouses_map.items():
			dn_items = []
			for row in items:
				item_name = frappe.get_cached_value("Item", row.item_code, "item_name")
				dn_item = frappe.new_doc("Delivery Note Item")
				dn_item.item_code = row.item_code
				dn_item.item_name = item_name
				dn_item.warehouse = warehouse
				dn_item.qty = flt(row.qty_requested)
				dn_item.rate = flt(row.rate)
				dn_item.price_list_rate = flt(row.rate)
				dn_item.reference_doctype = row.doctype
				dn_item.reference_name = row.name
				if self.prescribed_by:
					dn_item.healthcare_practitioner = self.prescribed_by

				dn_items.append(dn_item)

			if not dn_items:
				continue

			dn_doc = frappe.get_doc(
				dict(
					doctype="Delivery Note",
					posting_date=nowdate(),
					posting_time=nowtime(),
					set_warehouse=warehouse,
					company=self.company,
					customer=customer,
					currency=company_currency,
					items=dn_items,
					patient=self.patient,
					patient_name=self.patient_name,
					coverage_plan_name=self.insurance_coverage_plan,
					reference_doctype=self.doctype,
					reference_name=self.name,
				)
			)

			dn_doc.flags.ignore_permissions = True
			dn_doc.set_missing_values()
			dn_doc.insert(ignore_permissions=True)

			if dn_doc.get("name"):
				self.db_set("delivery_note", dn_doc.name)
				self.db_set("status", "Submitted")
				frappe.msgprint(_(f"Delivery Note {dn_doc.name} created successfully (Draft)."))

	@frappe.whitelist()
	def update_status(self, status: str):
		self.db_set("status", status)

	def validate_quantities(self):
		"""Ensure qty_returned does not exceed qty_dispensed."""
		for item in self.items:
			if flt(item.qty_returned) > flt(item.qty_dispensed):
				frappe.throw(
					_(
						f"Row {item.idx}: Qty Returned ({item.qty_returned}) cannot exceed Qty Dispensed ({item.qty_dispensed})"
					)
				)
			if flt(item.qty_used) > flt(item.qty_dispensed):
				frappe.throw(
					_(
						f"Row {item.idx}: Qty Used ({item.qty_used}) cannot exceed Qty Dispensed ({item.qty_dispensed})"
					)
				)
