from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.patches import drop_stored_previous_encounter_details as patch_module
from hms_tz.tests.utils import insert

ENCOUNTERS = ["_Test DP Encounter 1", "_Test DP Encounter 2", "_Test DP Encounter 3"]


def insert_previous_drug(
	name, parent, parenttype="Patient Encounter", parentfield="previous_drug_prescription"
):
	insert(
		"Previous Drug Prescription",
		name,
		parent=parent,
		parenttype=parenttype,
		parentfield=parentfield,
		drug_code="_Test DP Drug",
	)


class TestDropStoredPreviousEncounterDetails(FrappeTestCase):
	def setUp(self):
		for name, notes in zip(ENCOUNTERS, ["\nold notes", "", None], strict=True):
			insert("Patient Encounter", name, hms_tz_previous_examination_detail=notes)

	def tearDown(self):
		frappe.db.rollback()

	def test_table_with_only_encounter_rows_is_truncated(self):
		if frappe.db.exists("Previous Drug Prescription", {"parenttype": ["!=", "Patient Encounter"]}):
			self.skipTest("site has Previous Drug Prescription rows of other parents")
		insert_previous_drug("_Test DP Encounter Row", ENCOUNTERS[0])

		with patch.object(frappe.db, "truncate") as truncate:
			patch_module.drop_rows("Previous Drug Prescription", "previous_drug_prescription")

		truncate.assert_called_once_with("Previous Drug Prescription")

	def test_rows_of_other_parents_are_kept(self):
		insert_previous_drug("_Test DP Encounter Row", ENCOUNTERS[0])
		insert_previous_drug("_Test DP Inpatient Row", "_Test DP IP", parenttype="Inpatient Record")

		with patch.object(frappe.db, "commit"):
			patch_module.drop_rows("Previous Drug Prescription", "previous_drug_prescription")

		self.assertFalse(frappe.db.exists("Previous Drug Prescription", "_Test DP Encounter Row"))
		self.assertTrue(frappe.db.exists("Previous Drug Prescription", "_Test DP Inpatient Row"))

	def test_previous_notes_are_cleared(self):
		with (
			patch.object(frappe.db, "commit"),
			patch.object(patch_module, "BATCH_SIZE", 1),
			patch.object(patch_module, "enqueue_next") as enqueue_next,
		):
			patch_module.clear_previous_notes("_Test DP")

		enqueue_next.assert_not_called()
		self.assertEqual(
			frappe.get_all(
				"Patient Encounter",
				filters={"name": ["in", ENCOUNTERS]},
				pluck="hms_tz_previous_examination_detail",
				order_by="name",
			),
			[None, "", None],
		)

	def test_next_run_is_queued_after_the_batches(self):
		with (
			patch.object(frappe.db, "commit"),
			patch.object(patch_module, "BATCH_SIZE", 1),
			patch.object(patch_module, "BATCHES_PER_JOB", 1),
			patch.object(patch_module, "enqueue_next") as enqueue_next,
		):
			patch_module.clear_previous_notes("_Test DP")

		enqueue_next.assert_called_once_with(ENCOUNTERS[0])
