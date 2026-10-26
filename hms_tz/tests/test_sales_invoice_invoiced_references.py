from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_months, get_first_day, today

from hms_tz.nhif.api.healthcare_utils import INVOICED_FIELDS
from hms_tz.nhif.api.sales_invoice import (
	NO_SERVICE_DOCTYPES,
	before_submit,
	create_healthcare_docs,
	on_submit,
	set_invoiced_references,
)
from hms_tz.patches import set_missing_invoiced_references
from hms_tz.patches.set_missing_invoiced_references import (
	get_uninvoiced_references,
	set_month_invoiced_references,
)

INVOICE = "_Test Invoiced References"
RETURN_INVOICE = "_Test Invoiced References Return"
POSTING_DATE = "2026-06-15"
SALES_INVOICE = "hms_tz.nhif.api.sales_invoice"


def make_reference(doctype, **values):
	row = frappe.get_doc(doctype=doctype, name=frappe.generate_hash(), parent="_Test Parent", **values)
	row.db_insert()

	return row


def make_invoice(name, references, **values):
	invoice = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"name": name,
			"docstatus": 1,
			"posting_date": POSTING_DATE,
			"items": [{"reference_dt": row.doctype, "reference_dn": row.name} for row in references],
			**values,
		}
	)
	invoice.db_insert()
	for item in invoice.items:
		item.parent = invoice.name
		item.name = frappe.generate_hash()
		item.db_insert()

	return invoice


def get_invoiced(row):
	return frappe.db.get_value(
		row.doctype, row.name, [INVOICED_FIELDS[row.doctype], "sales_invoice_number"], as_dict=True
	)


class TestInvoiceSubmit(FrappeTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_submit_marks_every_reference_doctype_and_queues_services(self):
		references = [make_reference(doctype) for doctype in INVOICED_FIELDS]
		invoice = make_invoice(INVOICE, references, is_return=0)

		with patch("frappe.enqueue") as enqueue:
			on_submit(invoice, "on_submit")

		for row in references:
			self.assertEqual(list(get_invoiced(row).values()), [1, INVOICE], row.doctype)

		for item in invoice.items:
			is_created = frappe.db.get_value(item.doctype, item.name, "hms_tz_is_lrp_item_created")
			self.assertEqual(is_created, int(item.reference_dt in NO_SERVICE_DOCTYPES), item.reference_dt)

		enqueue.assert_called_once()
		self.assertEqual(enqueue.call_args.kwargs["invoice"], INVOICE)
		self.assertTrue(enqueue.call_args.kwargs["deduplicate"])

	def test_return_unmarks_rows_before_and_after_healthcare_submit(self):
		references = [make_reference(doctype) for doctype in INVOICED_FIELDS]
		appointment = make_reference("Patient Appointment", invoiced=1, ref_sales_invoice=INVOICE)
		make_invoice(INVOICE, references, is_return=0)
		set_invoiced_references(frappe.get_doc("Sales Invoice", INVOICE), INVOICE)
		credit_note = make_invoice(RETURN_INVOICE, [*references, appointment], is_return=1)

		before_submit(credit_note, "before_submit")

		for row in references:
			self.assertEqual(list(get_invoiced(row).values()), [0, ""], row.doctype)

		# healthcare's on_submit marks the returned rows as invoiced again
		set_invoiced_references(credit_note, RETURN_INVOICE)
		with patch("frappe.enqueue") as enqueue:
			on_submit(credit_note, "on_submit")

		for row in references:
			self.assertEqual(list(get_invoiced(row).values()), [0, ""], row.doctype)

		self.assertEqual(
			frappe.db.get_value(appointment.doctype, appointment.name, ["invoiced", "ref_sales_invoice"]),
			(0, ""),
		)
		enqueue.assert_not_called()

	def test_services_job_skips_items_already_created(self):
		lab = make_reference("Lab Prescription")
		invoice = make_invoice(INVOICE, [lab])
		invoice.items[0].hms_tz_is_lrp_item_created = 1

		with patch(f"{SALES_INVOICE}.create_individual_lab_test") as create_lab_test:
			create_healthcare_docs(invoice)

		create_lab_test.assert_not_called()

	def test_services_job_ignores_draft_invoice(self):
		invoice = make_invoice(INVOICE, [make_reference("Lab Prescription")], docstatus=0)

		with patch(f"{SALES_INVOICE}.create_individual_lab_test") as create_lab_test:
			create_healthcare_docs(invoice)

		create_lab_test.assert_not_called()


class TestSetMissingInvoicedReferences(FrappeTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_marks_rows_of_submitted_invoices_in_the_month(self):
		consultancy = make_reference("Inpatient Consultancy")
		occupancy = make_reference("Inpatient Occupancy")
		make_invoice(INVOICE, [consultancy, occupancy], is_return=0)

		set_month_invoiced_references(POSTING_DATE)

		self.assertEqual(list(get_invoiced(consultancy).values()), [1, INVOICE])
		self.assertEqual(list(get_invoiced(occupancy).values()), [1, INVOICE])

	def test_skips_rows_outside_the_month_draft_or_returned(self):
		next_month = make_reference("Inpatient Occupancy")
		make_invoice("_Test Next Month", [next_month], is_return=0, posting_date="2026-07-01")
		draft = make_reference("Inpatient Occupancy")
		make_invoice("_Test Draft", [draft], is_return=0, docstatus=0)
		returned = make_reference("Inpatient Occupancy")
		make_invoice(INVOICE, [returned], is_return=0)
		make_invoice(RETURN_INVOICE, [returned], is_return=1, return_against=INVOICE)

		rows = get_uninvoiced_references("Inpatient Occupancy", "2026-06-01", "2026-06-30")

		self.assertEqual(rows, [])

	def test_reinvoiced_row_after_return_is_marked(self):
		lab = make_reference("Lab Prescription")
		make_invoice("_Test First", [lab], is_return=0)
		make_invoice(RETURN_INVOICE, [lab], is_return=1, return_against="_Test First")
		make_invoice(INVOICE, [lab], is_return=0)

		set_month_invoiced_references(POSTING_DATE)

		self.assertEqual(list(get_invoiced(lab).values()), [1, INVOICE])

	def test_patch_queues_one_job_per_month_from_june_2026(self):
		with patch("frappe.enqueue") as enqueue:
			set_missing_invoiced_references.execute()

		months = [call.kwargs["month_start"] for call in enqueue.call_args_list]
		self.assertEqual(months[0], "2026-06-01")
		self.assertEqual(months[-1], str(get_first_day(today())))
		self.assertEqual(months, [str(add_months("2026-06-01", index)) for index in range(len(months))])
