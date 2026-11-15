from unittest.mock import patch

import frappe
from frappe.model.document import Document
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.api.patient_encounter import after_insert, set_new_encounter_values, set_patient_age
from hms_tz.patches import delete_duplicate_patient_encounter_versions as patch_module
from hms_tz.tests.utils import insert

ENCOUNTER = "_Test DS Encounter"


def insert_version(name, data, creation, docname=ENCOUNTER):
	insert("Version", name, ref_doctype="Patient Encounter", docname=docname, data=data, creation=creation)


class TestEncounterDoubleSave(FrappeTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_new_encounter_values_are_set_before_the_first_save(self):
		doc = frappe.new_doc("Patient Encounter")
		doc.update({"patient_age": "30 Year(s)", "encounter_type": "Initial", "poc_reference_no": None})

		with patch("hms_tz.nhif.api.patient_encounter.set_price_list") as set_price_list:
			set_new_encounter_values(doc, "before_save")

		self.assertEqual(doc.poc_reference_no, "")
		set_price_list.assert_called_once_with(doc)

	def test_saved_encounter_values_are_left_alone(self):
		doc = frappe.new_doc("Patient Encounter")
		doc.update({"encounter_type": "Initial", "poc_reference_no": "POC-1"})

		with patch.object(Document, "is_new", return_value=False):
			set_new_encounter_values(doc, "before_save")

		self.assertEqual(doc.poc_reference_no, "POC-1")

	def test_after_insert_doesnt_save_the_encounter_again(self):
		doc = frappe.new_doc("Patient Encounter")
		doc.encounter_type = "Ongoing"

		with patch.object(Document, "save") as save:
			after_insert(doc, "after_insert")

		save.assert_not_called()

	def test_fetched_age_is_kept(self):
		doc = frappe.new_doc("Patient Encounter")
		doc.update({"patient": "_Test Patient", "patient_age": "30 Year(s)"})

		with patch("hms_tz.nhif.api.patient_encounter.calculate_patient_age") as calculate:
			set_patient_age(doc, "before_validate")

		calculate.assert_not_called()
		self.assertEqual(doc.patient_age, "30 Year(s)")

	def test_age_is_computed_when_not_fetched(self):
		doc = frappe.new_doc("Patient Encounter")
		doc.patient = "_Test Patient"

		with patch(
			"hms_tz.nhif.api.patient_encounter.calculate_patient_age", return_value="5 Year(s) 1 Month(s)"
		):
			set_patient_age(doc, "before_validate")

		self.assertEqual(doc.patient_age, "5 Year(s) 1 Month(s)")

	def test_missing_dob_warns_only_on_insert(self):
		doc = frappe.new_doc("Patient Encounter")
		doc.patient = "_Test Patient"

		with (
			patch.object(frappe, "get_cached_value", return_value=None),
			patch.object(frappe, "msgprint") as msgprint,
		):
			set_patient_age(doc, "before_validate")
			msgprint.assert_called_once()

			msgprint.reset_mock()
			with patch.object(Document, "is_new", return_value=False):
				set_patient_age(doc, "before_validate")
			msgprint.assert_not_called()

		self.assertIsNone(doc.patient_age)

	def test_only_back_to_back_duplicates_are_deleted(self):
		insert_version("_Test DS V1", '{"changed": [["a", null, ""]]}', "2026-11-01 08:00:00")
		insert_version(
			"_Test DS V2", '{"changed": [["a", null, ""]]}', "2026-11-01 08:00:01"
		)  # the duplicate
		insert_version("_Test DS V3", '{"changed": [["b", 1, 2]]}', "2026-11-01 09:00:00")
		insert_version("_Test DS V4", '{"changed": [["b", 2, 1]]}', "2026-11-01 09:30:00")
		insert_version("_Test DS V5", '{"changed": [["b", 1, 2]]}', "2026-11-01 10:00:00")  # a real repeat
		insert_version("_Test DS V6", '{"changed": [["b", 1, 2]]}', "2026-11-01 10:10:00")  # too late
		insert_version(
			"_Test DS V7", '{"changed": [["a", null, ""]]}', "2026-11-01 08:00:01", "_Test DS Other"
		)

		with patch.object(frappe.db, "commit"), patch.object(patch_module, "enqueue_next") as enqueue_next:
			patch_module.delete_duplicates("_Test DS")

		enqueue_next.assert_not_called()
		remaining = frappe.get_all("Version", filters={"name": ["like", "_Test DS V%"]}, pluck="name")
		self.assertEqual(
			sorted(remaining),
			["_Test DS V1", "_Test DS V3", "_Test DS V4", "_Test DS V5", "_Test DS V6", "_Test DS V7"],
		)
