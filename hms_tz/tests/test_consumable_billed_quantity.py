import frappe
from frappe.query_builder import DocType
from frappe.tests.utils import FrappeTestCase

from hms_tz.hms_tz.doctype.consumable_item.consumable_item import get_billable_qty, get_billable_qty_column
from hms_tz.hms_tz.report.ipd_billing_report.ipd_billing_report import get_consumable_amount_query
from hms_tz.nhif.api.healthcare_utils import get_healthcare_services_to_invoice

RECORD = "_Test CBQ Consumable Record"
APPOINTMENT = "_Test CBQ Appointment"
ENCOUNTER = "_Test CBQ Encounter"
INPATIENT_RECORD = "_Test CBQ Inpatient Record"


def insert(doctype, name, **values):
	doc = frappe.new_doc(doctype)
	doc.update({"name": name, **values})
	doc.db_insert()


def insert_item(name, qty_requested, qty_dispensed=0, qty_used=0, is_billable=1, rate=100):
	insert(
		"Consumable Item",
		name,
		parent=RECORD,
		parenttype="Consumable Record",
		parentfield="items",
		item_code="_Test CBQ Item",
		qty_requested=qty_requested,
		qty_dispensed=qty_dispensed,
		qty_used=qty_used,
		rate=rate,
		amount=rate * (qty_used or qty_dispensed or qty_requested),
		payment_type="Cash",
		is_billable=is_billable,
	)


class TestConsumableBilledQuantity(FrappeTestCase):
	def setUp(self):
		insert(
			"Consumable Record",
			RECORD,
			docstatus=1,
			payment_type="Cash",
			appointment=APPOINTMENT,
			inpatient_record=INPATIENT_RECORD,
			posting_date="2026-01-05",
		)
		insert_item("_Test CBQ Requested", qty_requested=5)
		insert_item("_Test CBQ Dispensed", qty_requested=5, qty_dispensed=4)
		insert_item("_Test CBQ Used", qty_requested=5, qty_dispensed=4, qty_used=3)

	def tearDown(self):
		frappe.db.rollback()

	def test_billable_qty_prefers_used_then_dispensed_then_requested(self):
		item = frappe._dict(qty_requested=5, qty_dispensed=4, qty_used=0)
		self.assertEqual(get_billable_qty(item), 4)

		item.qty_used = 3
		self.assertEqual(get_billable_qty(item), 3)

	def test_query_column_matches_python_rule(self):
		consumable_item = DocType("Consumable Item")
		rows = (
			frappe.qb.from_(consumable_item)
			.select(consumable_item.name, get_billable_qty_column(consumable_item).as_("quantity"))
			.where(consumable_item.parent == RECORD)
		).run(as_dict=True)

		quantities = {row.name: row.quantity for row in rows}
		self.assertEqual(
			quantities, {"_Test CBQ Requested": 5, "_Test CBQ Dispensed": 4, "_Test CBQ Used": 3}
		)

	def test_invoice_uses_billable_qty(self):
		insert("Patient Encounter", ENCOUNTER, appointment=APPOINTMENT, docstatus=1)

		services = get_healthcare_services_to_invoice(
			patient_encounter_list=[frappe._dict(name=ENCOUNTER, inpatient_record=None)]
		)

		quantities = {row["reference_name"]: row["qty"] for row in services}
		self.assertEqual(
			quantities, {"_Test CBQ Requested": 5, "_Test CBQ Dispensed": 4, "_Test CBQ Used": 3}
		)

	def test_ipd_summary_ignores_non_billable_items(self):
		insert_item("_Test CBQ Free", qty_requested=10, is_billable=0)

		rows = get_consumable_amount_query(frappe._dict(inpatient_record=INPATIENT_RECORD)).run(as_dict=True)

		self.assertEqual(sum(row.consumable_amount for row in rows), 100 * (5 + 4 + 3))
