from unittest.mock import patch

import frappe
from frappe.model.document import Document
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.api.patient_encounter import (
	PREVIOUS_TABLES,
	duplicate_encounter,
	keep_saved_previous_details,
	set_previous_details,
)
from hms_tz.tests.utils import insert

ROOT = "_Test PD Root"
SECOND = "_Test PD Second"
THIRD = "_Test PD Third"


def insert_encounter(name, from_encounter=None, docstatus=1, notes=None):
	insert(
		"Patient Encounter",
		name,
		docstatus=docstatus,
		encounter_type="Initial" if not from_encounter else "Ongoing",
		reference_encounter=ROOT,
		from_encounter=from_encounter,
		examination_detail=notes,
		creation=frappe.utils.now(),
	)


def insert_row(doctype, parent, parentfield, idx, **values):
	insert(
		doctype,
		f"{parent}-{parentfield}-{idx}",
		parent=parent,
		parenttype="Patient Encounter",
		parentfield=parentfield,
		idx=idx,
		**values,
	)


def get_previous_drugs(doc):
	return [row.drug_code for row in doc.previous_drug_prescription]


class TestEncounterPreviousDetails(FrappeTestCase):
	def setUp(self):
		insert_encounter(ROOT, notes="root notes")
		insert_encounter(SECOND, from_encounter=ROOT, notes="second notes")
		insert_encounter(THIRD, from_encounter=SECOND, docstatus=0)
		insert_row("Drug Prescription", ROOT, "drug_prescription", 1, drug_code="_Test PD Drug 1")
		insert_row("Drug Prescription", ROOT, "drug_prescription", 2, drug_code="_Test PD Drug 2")
		insert_row("Drug Prescription", SECOND, "drug_prescription", 1, drug_code="_Test PD Drug 3")
		insert_row("Lab Prescription", ROOT, "lab_test_prescription", 1, lab_test_code="_Test PD Lab")

	def tearDown(self):
		frappe.db.rollback()

	def test_previous_details_come_from_the_chain(self):
		doc = frappe.get_doc("Patient Encounter", THIRD)
		set_previous_details(doc)

		self.assertEqual(get_previous_drugs(doc), ["_Test PD Drug 1", "_Test PD Drug 2", "_Test PD Drug 3"])
		self.assertEqual([row.lab_test_code for row in doc.previous_lab_prescription], ["_Test PD Lab"])
		# same text the old copy built: previous notes + "\n" + notes, one link at a time
		self.assertEqual(doc.hms_tz_previous_examination_detail, "\nroot notes\nsecond notes")

	def test_first_encounter_has_no_previous_details(self):
		doc = frappe.get_doc("Patient Encounter", ROOT)
		set_previous_details(doc)

		self.assertEqual(get_previous_drugs(doc), [])
		self.assertFalse(doc.hms_tz_previous_examination_detail)

	def test_previous_details_are_not_saved(self):
		doc = frappe.get_doc("Patient Encounter", THIRD)
		doc._doc_before_save = frappe.get_doc("Patient Encounter", THIRD)
		set_previous_details(doc)

		keep_saved_previous_details(doc, "before_validate")

		for previous_table in PREVIOUS_TABLES.values():
			self.assertEqual(doc.get(previous_table), [])
		self.assertFalse(doc.hms_tz_previous_examination_detail)

	def test_stored_previous_details_are_kept(self):
		# encounters duplicated before this change still have copies stored
		insert_row(
			"Previous Drug Prescription", THIRD, "previous_drug_prescription", 1, drug_code="_Test PD Drug 1"
		)
		frappe.db.set_value("Patient Encounter", THIRD, "hms_tz_previous_examination_detail", "stored notes")
		doc = frappe.get_doc("Patient Encounter", THIRD)
		doc._doc_before_save = frappe.get_doc("Patient Encounter", THIRD)
		set_previous_details(doc)

		keep_saved_previous_details(doc, "before_update_after_submit")

		self.assertEqual(get_previous_drugs(doc), ["_Test PD Drug 1"])
		self.assertEqual(doc.hms_tz_previous_examination_detail, "stored notes")

	def test_duplicate_copies_no_previous_details(self):
		saved = []
		with (
			patch.object(Document, "save", lambda doc, **kwargs: saved.append(doc)),
			patch("frappe.msgprint"),
		):
			duplicate_encounter(SECOND)

		(doc,) = saved
		self.assertEqual(doc.from_encounter, SECOND)
		self.assertEqual(doc.reference_encounter, ROOT)
		self.assertFalse(doc.hms_tz_previous_examination_detail)
		self.assertFalse(doc.examination_detail)
		for table, previous_table in PREVIOUS_TABLES.items():
			self.assertEqual(doc.get(table), [])
			self.assertEqual(doc.get(previous_table), [])
