import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.patches import trim_nhif_patient_claim_versions
from hms_tz.patches.trim_nhif_patient_claim_versions import drop_re_added_rows, is_redundant


def item(name, **values):
	return {"name": name, "item_code": "1001", "item_quantity": 1, "unit_price": 1000, **values}


def disease(name, **values):
	return {"name": name, "codification_table": "CT-1", "disease_code": "A09", **values}


def version(**diff):
	return json.dumps(diff)


class TestTrimNHIFPatientClaimVersions(FrappeTestCase):
	def test_second_save_on_create_is_redundant(self):
		data = version(
			added=[
				["nhif_patient_claim_item", item("new-1", folio_item_id="uuid-2")],
				["nhif_patient_claim_disease", disease("new-2", folio_disease_id="uuid-4")],
				["original_nhif_patient_claim_item", item("orig-1")],
			],
			removed=[
				["nhif_patient_claim_item", item("old-1", folio_item_id="uuid-1", __unsaved=1)],
				["nhif_patient_claim_disease", disease("old-2", folio_disease_id="uuid-3")],
			],
			changed=[
				["serial_no", "600026", 600026],
				["folio_no", 0, 771],
				["signed_amount", 0.0, None],
			],
		)
		self.assertTrue(is_redundant(data))

	def test_discharge_time_posting_date_and_saving_user_are_kept(self):
		for change in (
			["discharge_time", "15:51:16", "15:51:17"],
			["posting_date", "2026-11-13", "2026-11-14"],
			["item_crt_by", "A", "B"],
		):
			self.assertFalse(is_redundant(version(changed=[change])))

	def test_changed_quantity_is_kept(self):
		data = version(
			added=[["nhif_patient_claim_item", item("new-1", item_quantity=3)]],
			removed=[["nhif_patient_claim_item", item("old-1")]],
		)
		self.assertFalse(is_redundant(data))

	def test_removed_item_is_kept(self):
		self.assertFalse(is_redundant(version(removed=[["nhif_patient_claim_item", item("old-1")]])))

	def test_added_item_is_kept(self):
		self.assertFalse(is_redundant(version(added=[["nhif_patient_claim_item", item("new-1")]])))

	def test_signature_and_submission_are_kept(self):
		self.assertFalse(
			is_redundant(version(changed=[["patient_signature", None, "data:image/png;base64,xx"]]))
		)
		self.assertFalse(is_redundant(version(changed=[["docstatus", 0, 1]])))

	def test_row_change_is_kept(self):
		data = version(
			row_changed=[["nhif_patient_claim_item", 1, "row-1", [["status", "Draft", "Submitted"]]]]
		)
		self.assertFalse(is_redundant(data))

	def test_mixed_keeps_real_changes_and_drops_re_added_rows(self):
		changed = [["total_amount", "676,891", "661,891"]]
		data = version(
			added=[
				["nhif_patient_claim_item", item("new-1", folio_item_id="uuid-2")],
				["nhif_patient_claim_item", item("new-3", item_code="1003")],
			],
			removed=[["nhif_patient_claim_item", item("old-1", folio_item_id="uuid-1")]],
			changed=changed,
		)
		trimmed = json.loads(drop_re_added_rows(data))
		self.assertEqual(trimmed["changed"], changed)
		self.assertEqual(trimmed["added"], [["nhif_patient_claim_item", item("new-3", item_code="1003")]])
		self.assertEqual(trimmed["removed"], [])

	def test_compact_format(self):
		data = version(
			added=[["nhif_patient_claim_item", item("new-1")]],
			removed=[["nhif_patient_claim_item", item("old-1")]],
			changed=[],
		)
		self.assertNotIn(" ", drop_re_added_rows(data))

	def test_nothing_to_drop(self):
		self.assertIsNone(drop_re_added_rows(version(changed=[["docstatus", 0, 1]])))


class TestTrimVersionsJob(FrappeTestCase):
	"""The batch walk: keyset paging across Versions of one claim, chaining, rerun."""

	SNAPSHOT = version(added=[["original_nhif_patient_claim_item", item("orig-1")]])
	CHURN = version(
		added=[["nhif_patient_claim_item", item("new-1")]],
		removed=[["nhif_patient_claim_item", item("old-1")]],
	)
	REAL = version(changed=[["docstatus", 0, 1]])
	MIXED = version(
		added=[["nhif_patient_claim_item", item("new-1")]],
		removed=[["nhif_patient_claim_item", item("old-1")]],
		changed=[["delayreason", None, "24"]],
	)

	def setUp(self):
		# docnames sort after "ZZTEST", so the walk skips any other claim Versions on the site
		self.data = {
			"zzc-1": ("ZZTEST-NPC-1", self.SNAPSHOT),
			"zzc-2": ("ZZTEST-NPC-1", self.MIXED),
			"zzc-3": ("ZZTEST-NPC-1", self.REAL),  # first job ends after the next row: a page boundary
			"zzc-4": ("ZZTEST-NPC-2", self.SNAPSHOT),
			"zzc-5": ("ZZTEST-NPC-2", self.CHURN),
			"zzc-6": ("ZZTEST-NPC-3", self.REAL),
		}
		for name, (docname, data) in self.data.items():
			frappe.get_doc(
				{"doctype": "Version", "ref_doctype": "NHIF Patient Claim", "docname": docname, "data": data}
			).insert(ignore_permissions=True, set_name=name)

	def tearDown(self):
		frappe.db.rollback()

	def run_chain(self):
		"""Run the job and every job it queues; return the cursors it queued."""
		queued = []
		with (
			patch.object(trim_nhif_patient_claim_versions, "BATCH_SIZE", 2),
			patch.object(trim_nhif_patient_claim_versions, "BATCHES_PER_JOB", 2),
			patch.object(
				trim_nhif_patient_claim_versions, "enqueue_next", side_effect=lambda *a: queued.append(a)
			),
			patch.object(frappe.db, "commit"),
		):
			trim_nhif_patient_claim_versions.trim_versions("ZZTEST", "")
			for cursor in queued:  # grows while the chain runs
				trim_nhif_patient_claim_versions.trim_versions(*cursor)
		return queued

	def remaining(self):
		return dict(
			frappe.get_all(
				"Version", filters={"name": ("like", "zzc-%")}, fields=["name", "data"], as_list=True
			)
		)

	def test_walk_deletes_trims_and_chains(self):
		self.assertEqual(self.run_chain(), [("ZZTEST-NPC-2", "zzc-4")])

		remaining = self.remaining()
		self.assertEqual(sorted(remaining), ["zzc-2", "zzc-3", "zzc-6"])
		self.assertEqual(remaining["zzc-2"], drop_re_added_rows(self.MIXED))
		self.assertEqual(remaining["zzc-3"], self.REAL)
		self.assertEqual(remaining["zzc-6"], self.REAL)

	def test_rerun_changes_nothing(self):
		self.run_chain()
		before = self.remaining()
		with patch.object(frappe.db, "set_value") as set_value:
			self.run_chain()
		set_value.assert_not_called()
		self.assertEqual(self.remaining(), before)
