import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.patches import trim_delivery_note_versions
from hms_tz.patches.trim_delivery_note_versions import drop_re_added_rows, is_redundant


def item(name, **values):
	return {"name": name, "item_code": "PARA", "qty": 2, "rate": 100, **values}


def version(**diff):
	return json.dumps(diff)


class TestTrimDeliveryNoteVersions(FrappeTestCase):
	def test_snapshot_on_create_is_redundant(self):
		data = version(
			added=[["items", item("new-1", original_item="PARA")], ["hms_tz_original_items", item("orig-1")]],
			removed=[["items", item("old-1", __unsaved=1)]],
		)
		self.assertTrue(is_redundant(data))

	def test_rows_re_added_with_new_stock_levels_are_redundant(self):
		data = version(
			added=[["items", item("new-1", actual_qty=40)]],
			removed=[["items", item("old-1", actual_qty=55)]],
			changed=[["posting_time", "10:01:00", "10:05:00"], ["discount_amount", None, 0]],
		)
		self.assertTrue(is_redundant(data))

	def test_changed_quantity_is_kept(self):
		data = version(added=[["items", item("new-1", qty=3)]], removed=[["items", item("old-1")]])
		self.assertFalse(is_redundant(data))

	def test_real_change_with_re_added_rows_is_kept(self):
		data = version(
			added=[["items", item("new-1")]],
			removed=[["items", item("old-1")]],
			changed=[["workflow_state", "Draft", "Approved"]],
		)
		self.assertFalse(is_redundant(data))

	def test_out_of_stock_flag_is_kept(self):
		data = version(
			row_changed=[["hms_tz_original_items", 1, "orig-1", [["hms_tz_is_out_of_stock", 0, 1]]]]
		)
		self.assertFalse(is_redundant(data))

	def test_removed_item_is_kept(self):
		self.assertFalse(is_redundant(version(removed=[["items", item("old-1")]])))

	def test_edited_posting_time_is_kept(self):
		data = version(changed=[["posting_time", "10:01:00", "08:00:00"]])
		self.assertTrue(is_redundant(data, auto_posting_time=True))
		self.assertFalse(is_redundant(data, auto_posting_time=False))

	def test_mixed_keeps_real_changes_and_drops_re_added_rows(self):
		changed = [["workflow_state", "Draft", "Approved"]]
		row_changed = [["items", 2, "row-2", [["qty", 1, 2]]]]
		data = version(
			added=[["items", item("new-1")], ["items", item("new-3", item_code="AMOX")]],
			removed=[["items", item("old-1")]],
			changed=changed,
			row_changed=row_changed,
		)
		trimmed = json.loads(drop_re_added_rows(data))
		self.assertEqual(trimmed["changed"], changed)
		self.assertEqual(trimmed["row_changed"], row_changed)
		self.assertEqual(trimmed["added"], [["items", item("new-3", item_code="AMOX")]])
		self.assertEqual(trimmed["removed"], [])

	def test_compact_format(self):
		data = version(added=[["items", item("new-1")]], removed=[["items", item("old-1")]], changed=[])
		self.assertNotIn(" ", drop_re_added_rows(data))

	def test_nothing_to_drop(self):
		self.assertIsNone(drop_re_added_rows(version(changed=[["workflow_state", "Draft", "Approved"]])))


class TestTrimVersionsJob(FrappeTestCase):
	"""The batch walk: keyset paging across Versions of one Delivery Note, chaining, rerun."""

	SNAPSHOT = version(added=[["hms_tz_original_items", item("orig-1")]])
	CHURN = version(added=[["items", item("new-1")]], removed=[["items", item("old-1")]])
	REAL = version(changed=[["workflow_state", "Draft", "Approved"]])
	MIXED = version(
		added=[["items", item("new-1")]],
		removed=[["items", item("old-1")]],
		changed=[["workflow_state", "Draft", "Approved"]],
	)

	def setUp(self):
		# docnames sort after "ZZTEST", so the walk skips any other Delivery Note Versions on the site
		self.data = {
			"zzv-1": ("ZZTEST-DN-1", self.SNAPSHOT),
			"zzv-2": ("ZZTEST-DN-1", self.MIXED),
			"zzv-3": ("ZZTEST-DN-1", self.REAL),  # first job ends after the next row: a page boundary
			"zzv-4": ("ZZTEST-DN-2", self.SNAPSHOT),
			"zzv-5": ("ZZTEST-DN-2", self.CHURN),
			"zzv-6": ("ZZTEST-DN-3", self.REAL),
		}
		for name, (docname, data) in self.data.items():
			frappe.get_doc(
				{"doctype": "Version", "ref_doctype": "Delivery Note", "docname": docname, "data": data}
			).insert(ignore_permissions=True, set_name=name)

	def tearDown(self):
		frappe.db.rollback()

	def run_chain(self):
		"""Run the job and every job it queues; return the cursors it queued."""
		queued = []
		with (
			patch.object(trim_delivery_note_versions, "BATCH_SIZE", 2),
			patch.object(trim_delivery_note_versions, "BATCHES_PER_JOB", 2),
			patch.object(
				trim_delivery_note_versions, "enqueue_next", side_effect=lambda *a: queued.append(a)
			),
			patch.object(frappe.db, "commit"),
		):
			trim_delivery_note_versions.trim_versions("ZZTEST", "")
			for cursor in queued:  # grows while the chain runs
				trim_delivery_note_versions.trim_versions(*cursor)
		return queued

	def remaining(self):
		return dict(
			frappe.get_all(
				"Version", filters={"name": ("like", "zzv-%")}, fields=["name", "data"], as_list=True
			)
		)

	def test_walk_deletes_trims_and_chains(self):
		self.assertEqual(self.run_chain(), [("ZZTEST-DN-2", "zzv-4")])

		remaining = self.remaining()
		self.assertEqual(sorted(remaining), ["zzv-2", "zzv-3", "zzv-6"])
		self.assertEqual(remaining["zzv-2"], drop_re_added_rows(self.MIXED))
		self.assertEqual(remaining["zzv-3"], self.REAL)
		self.assertEqual(remaining["zzv-6"], self.REAL)

	def test_rerun_changes_nothing(self):
		self.run_chain()
		before = self.remaining()
		with patch.object(frappe.db, "set_value") as set_value:
			self.run_chain()
		set_value.assert_not_called()
		self.assertEqual(self.remaining(), before)
