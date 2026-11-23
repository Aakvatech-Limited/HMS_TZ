# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.api.setup_status import SETUP_DOCTYPES

SETTING = "_Test Setup Status Company"


class TestSetupStatus(FrappeTestCase):
	def setUp(self):
		if not frappe.db.exists("HMS TZ Setting", SETTING):
			frappe.get_doc({"doctype": "HMS TZ Setting", "company": SETTING, "facility_code": "TEST"}).insert(
				ignore_links=True
			)
		frappe.db.delete("Setup Status", SETTING)

	def new_status(self):
		return frappe.get_doc({"doctype": "Setup Status", "hms_tz_setting": SETTING})

	def test_status_is_named_after_its_setting(self):
		self.assertEqual(self.new_status().insert().name, SETTING)

	def test_new_status_lists_every_setup_doctype_unticked(self):
		status = self.new_status().insert()
		self.assertEqual(tuple(row.document_type for row in status.steps), SETUP_DOCTYPES)
		self.assertFalse(any(row.completed for row in status.steps))

	def test_listed_step_keeps_its_tick(self):
		status = self.new_status()
		status.append("steps", {"document_type": "Price List", "completed": 1})
		status.insert()
		price_list_rows = [row for row in status.steps if row.document_type == "Price List"]
		self.assertEqual([row.completed for row in price_list_rows], [1])

	def test_one_status_per_setting(self):
		self.new_status().insert()
		with self.assertRaises(frappe.DuplicateEntryError):
			self.new_status().insert()
