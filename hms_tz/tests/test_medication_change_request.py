# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.background_jobs import create_job_id, get_redis_conn
from rq import Queue
from rq.utils import as_text, current_timestamp

from hms_tz.nhif.api import delivery_note
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


NHIF_VALUES = {
	"approval_number": "_Test APPROVAL-1",
	"approval_date": "2026-11-01",
	"approval_status": "APPROVED",
	"approved_qty": 2,
	"service_authorization_id": "_Test AUTH-1",
	"authorized_item_id": "_Test ITEM-1",
	"service_reference_no": "_Test SRN-1",
}


def get_medication_or_item_value(doctype, name, fieldnames):
	return (f"{name} Item", "Nos") if doctype == "Medication" else (1, name)


@patch.object(mcr, "get_warehouse_from_service_unit", get_warehouse_from_service_unit)
@patch.object(mcr.frappe, "get_cached_value", get_medication_or_item_value)
class TestMedicationChangeRequestDeliveryNote(FrappeTestCase):
	def update_delivery_note(self, *drug_codes):
		dn_doc = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"name": "_Test MCR DN-1",
				"set_warehouse": STORE_A,
				"items": [{"item_code": "_Test MCR Drug A Item", "is_restricted": 1, **NHIF_VALUES}],
			}
		)
		dn_doc.save = MagicMock()
		dn_doc.reload = MagicMock()
		rows = [
			make_row(drug_code=code, name=code, prescribe=0, delivered_quantity=2, amount=10, is_restricted=1)
			for code in drug_codes
		]
		encounter = frappe._dict(drug_prescription=rows, insurance_subscription="_Test MCR Subscription")

		request = frappe.new_doc("Medication Change Request")
		request.delivery_note = dn_doc.name
		request.update_delivery_note_workflow = MagicMock()
		request.update_drug_prescription = MagicMock()
		get_doc = frappe.get_doc
		with patch.object(
			mcr.frappe,
			"get_doc",
			side_effect=lambda *args: dn_doc if args == ("Delivery Note", dn_doc.name) else get_doc(*args),
		):
			request.update_delivery_note(encounter)
		return dn_doc

	def test_kept_item_keeps_nhif_values(self):
		dn_doc = self.update_delivery_note("_Test MCR Drug A")

		item = dn_doc.items[0]
		self.assertEqual({fieldname: item.get(fieldname) for fieldname in NHIF_VALUES}, NHIF_VALUES)
		self.assertEqual(dn_doc.hms_tz_original_items[0].approval_number, NHIF_VALUES["approval_number"])

	def test_added_item_has_no_nhif_values(self):
		dn_doc = self.update_delivery_note("_Test MCR Drug A", "_Test MCR Drug B")

		self.assertEqual(dn_doc.items[0].service_reference_no, NHIF_VALUES["service_reference_no"])
		self.assertFalse(any(dn_doc.items[1].get(fieldname) for fieldname in NHIF_VALUES))

	def test_removed_item_values_are_not_moved(self):
		dn_doc = self.update_delivery_note("_Test MCR Drug B")

		self.assertEqual(len(dn_doc.items), 1)
		self.assertFalse(any(dn_doc.items[0].get(fieldname) for fieldname in NHIF_VALUES))


class TestDeliveryNotePendingMedicationChange(FrappeTestCase):
	def setUp(self):
		# private queue name, so a running worker cannot take the test jobs
		self.queue = Queue("hms-tz-test-mcr-hsr", connection=get_redis_conn())
		queue_patch = patch.object(mcr, "get_queue", return_value=self.queue)
		queue_patch.start()
		self.addCleanup(queue_patch.stop)
		self.addCleanup(self.clear_queue)

	def clear_queue(self):
		self.queue.empty()
		registry = self.queue.started_job_registry
		for job_id in self.queue.connection.zrange(registry.key, 0, -1):
			registry.remove(as_text(job_id), delete_job=True)

	def queue_job(self, job_id):
		return self.queue.enqueue_call("frappe.ping", job_id=create_job_id(job_id))

	def queue_request_job(self, delivery_note_name, request_name):
		return self.queue_job(mcr.get_hsr_update_job_prefix(delivery_note_name) + request_name)

	def start_job(self, job, score):
		self.queue.remove(job)
		self.queue.connection.zadd(self.queue.started_job_registry.key, {job.id: score})

	def validate(self, workflow_state="Changes Made"):
		delivery_note.validate_pending_medication_change_requests(
			frappe._dict(name="_Test MCR DN-1", workflow_state=workflow_state)
		)

	def test_queued_jobs_block_submit(self):
		self.queue_request_job("_Test MCR DN-1", "_Test MCR-1")
		self.queue_request_job("_Test MCR DN-1", "_Test MCR-2")

		with self.assertRaisesRegex(frappe.ValidationError, "_Test MCR-1.*_Test MCR-2"):
			self.validate()

	def test_running_job_blocks_submit(self):
		job = self.queue_request_job("_Test MCR DN-1", "_Test MCR-1")
		self.start_job(job, current_timestamp() + 60)

		with self.assertRaisesRegex(frappe.ValidationError, "_Test MCR-1"):
			self.validate()

	def test_expired_running_job_is_ignored(self):
		job = self.queue_request_job("_Test MCR DN-1", "_Test MCR-1")
		self.start_job(job, current_timestamp() - 10)
		self.validate()

	def test_job_of_other_delivery_note_is_ignored(self):
		self.queue_request_job("_Test MCR DN-10", "_Test MCR-1")
		self.validate()

	def test_draft_delivery_note_is_not_checked(self):
		self.queue_request_job("_Test MCR DN-1", "_Test MCR-1")
		self.validate(workflow_state="Draft")

	def test_no_pending_job_allows_submit(self):
		self.validate()

	def test_request_job_is_queued_after_commit_and_found_by_delivery_note(self):
		request = frappe.new_doc("Medication Change Request")
		request.name = "_Test MCR-1"
		request.delivery_note = "_Test MCR DN-1"
		with patch.object(mcr.frappe, "enqueue") as enqueue:
			request.update_hsr_and_hre()

		kwargs = enqueue.call_args.kwargs
		self.assertTrue(kwargs["enqueue_after_commit"])
		self.assertEqual(kwargs["queue"], mcr.HSR_UPDATE_QUEUE)
		self.queue_job(kwargs["job_id"])
		with self.assertRaisesRegex(frappe.ValidationError, "_Test MCR-1"):
			self.validate()
