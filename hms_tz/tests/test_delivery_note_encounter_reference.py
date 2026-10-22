import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.api.delivery_note import set_missing_values

ENCOUNTER = "_Test DNR Encounter"
APPOINTMENT = "_Test DNR Appointment"
PRACTITIONER = "_Test DNR Practitioner"
SALES_INVOICE = "_Test DNR Invoice"
DRUG_INVOICE_ITEM = "_Test DNR Drug Item"
LAB_INVOICE_ITEM = "_Test DNR Lab Item"


def insert(doctype, name, **values):
	doc = frappe.new_doc(doctype)
	doc.update({"name": name, **values})
	doc.db_insert()


def make_delivery_note(**values):
	delivery_note = frappe.new_doc("Delivery Note")
	delivery_note.update({"form_sales_invoice": SALES_INVOICE, **values})
	delivery_note.append("items", {"si_detail": LAB_INVOICE_ITEM})
	delivery_note.append("items", {"si_detail": DRUG_INVOICE_ITEM})
	return delivery_note


class TestDeliveryNoteEncounterReference(FrappeTestCase):
	def setUp(self):
		insert("Patient Encounter", ENCOUNTER, appointment=APPOINTMENT, practitioner=PRACTITIONER)
		invoice_item = {"parent": SALES_INVOICE, "parenttype": "Sales Invoice", "parentfield": "items"}
		insert("Sales Invoice Item", LAB_INVOICE_ITEM, reference_dt="Lab Prescription", **invoice_item)
		insert("Sales Invoice Item", DRUG_INVOICE_ITEM, reference_dt="Drug Prescription", **invoice_item)
		drug_prescription = frappe.generate_hash()
		insert(
			"Drug Prescription",
			drug_prescription,
			parent=ENCOUNTER,
			parenttype="Patient Encounter",
			parentfield="drug_prescription",
		)
		# set_value also clears the cached invoice item between tests
		frappe.db.set_value("Sales Invoice Item", DRUG_INVOICE_ITEM, "reference_dn", drug_prescription)

	def tearDown(self):
		frappe.db.rollback()

	def test_reference_is_set_when_appointment_and_practitioner_are_filled(self):
		delivery_note = make_delivery_note(
			hms_tz_appointment_no="_Test DNR Other Appointment", healthcare_practitioner="_Test DNR Other"
		)

		set_missing_values(delivery_note)

		self.assertEqual(delivery_note.reference_doctype, "Patient Encounter")
		self.assertEqual(delivery_note.reference_name, ENCOUNTER)
		self.assertEqual(delivery_note.hms_tz_appointment_no, "_Test DNR Other Appointment")
		self.assertEqual(delivery_note.healthcare_practitioner, "_Test DNR Other")

	def test_missing_appointment_and_practitioner_come_from_encounter(self):
		delivery_note = make_delivery_note()

		set_missing_values(delivery_note)

		self.assertEqual(delivery_note.reference_name, ENCOUNTER)
		self.assertEqual(delivery_note.hms_tz_appointment_no, APPOINTMENT)
		self.assertEqual(delivery_note.healthcare_practitioner, PRACTITIONER)

	def test_existing_reference_is_kept(self):
		delivery_note = make_delivery_note(
			reference_doctype="LRPMT Returns", reference_name="_Test DNR Return"
		)

		set_missing_values(delivery_note)

		self.assertEqual(delivery_note.reference_doctype, "LRPMT Returns")
		self.assertEqual(delivery_note.reference_name, "_Test DNR Return")
		self.assertEqual(delivery_note.hms_tz_appointment_no, APPOINTMENT)

	def test_deleted_prescription_is_skipped(self):
		frappe.db.delete("Drug Prescription", {"parent": ENCOUNTER})
		delivery_note = make_delivery_note()

		set_missing_values(delivery_note)

		self.assertFalse(delivery_note.reference_name)
