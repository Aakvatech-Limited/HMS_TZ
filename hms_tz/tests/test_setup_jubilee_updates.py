from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.api.setup_records import (
	download_records_template,
	get_company_records,
	get_record_child_rows,
	get_screen_fields,
	import_company_records,
	save_company_record,
)
from hms_tz.hms_tz.setup_screens.jubilee_update import JubileeUpdate

SCREEN = "jubilee_updates"
COMPANY = "_Test Company"
OTHER_COMPANY = "_Test Company 1"


class TestSetupJubileeUpdates(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Jubilee Update", {"company": ["in", [COMPANY, OTHER_COMPANY]]})
		frappe.delete_doc_if_exists("Setup Status", COMPANY)
		frappe.delete_doc_if_exists("HMS TZ Setting", COMPANY)
		frappe.db.set_single_value(
			"Healthcare Settings", {"collect_registration_fee": 0, "enable_free_follow_ups": 0}
		)
		frappe.get_doc({"doctype": "HMS TZ Setting", "company": COMPANY, "facility_code": "TEST"}).insert()
		self.log = self.create_log()
		self.older = self.create_update(COMPANY, "2026-01-01 08:00:00", rows=3)
		self.newer = self.create_update(COMPANY, "2026-02-01 08:00:00", rows=1)
		self.foreign = self.create_update(OTHER_COMPANY, "2026-03-01 08:00:00", rows=1)

	def create_log(self):
		log = frappe.get_doc({"doctype": "Jubilee Response Log", "request_type": "GetPricePackage"})
		return log.insert(ignore_mandatory=True).name

	def create_update(self, company, timestamp, rows):
		update = frappe.get_doc(
			{
				"doctype": "Jubilee Update",
				"company": company,
				"timestamp": timestamp,
				"current_log": self.log,
				"previous_log": self.log,
				"price_package": [
					{"itemcode": f"ITEM-{index}", "itemname": f"Item {index}", "itemprice": 100 * index}
					for index in range(1, rows + 1)
				],
			}
		)
		return update.insert().name

	def test_screen_is_read_only_with_child_rows(self):
		screen = get_screen_fields(SCREEN)
		fields = [field["fieldname"] for field in screen["fields"]]
		self.assertEqual(
			(screen["is_read_only"], screen["has_add_actions"], screen["has_child_rows"]), (1, 0, 1)
		)
		self.assertEqual(fields, ["current_log", "timestamp", "previous_log", "user_id"])

	def test_list_shows_the_company_updates_latest_first(self):
		names = [record.name for record in get_company_records(SCREEN, COMPANY)["records"]]
		self.assertEqual(names, [self.newer, self.older])

	def test_view_shows_child_rows_in_pages(self):
		page = get_record_child_rows(SCREEN, COMPANY, self.older)
		self.assertEqual([row.itemcode for row in page["rows"]], ["ITEM-1", "ITEM-2", "ITEM-3"])
		self.assertEqual(page["total"], 3)
		self.assertEqual([field["fieldname"] for field in page["fields"]], list(JubileeUpdate.child_fields))
		with patch.object(JubileeUpdate, "child_page_length", 2):
			second = get_record_child_rows(SCREEN, COMPANY, self.older, start=2)
		self.assertEqual(([row.itemcode for row in second["rows"]], second["total"]), (["ITEM-3"], 3))

	def test_another_company_update_is_not_viewed(self):
		with self.assertRaisesRegex(frappe.ValidationError, "is not one of the Jubilee updates of"):
			get_record_child_rows(SCREEN, COMPANY, self.foreign)

	def test_updates_are_never_changed_added_or_imported(self):
		with self.assertRaisesRegex(frappe.ValidationError, "are not changed on this screen"):
			save_company_record(SCREEN, COMPANY, frappe.as_json({"user_id": "x"}), name=self.older)
		with self.assertRaisesRegex(frappe.ValidationError, "are not changed on this screen"):
			save_company_record(SCREEN, COMPANY, frappe.as_json({"user_id": "x"}))
		with self.assertRaisesRegex(frappe.ValidationError, "are not added on this screen"):
			import_company_records(SCREEN, COMPANY, "/private/files/jubilee_updates.csv")
		with self.assertRaisesRegex(frappe.ValidationError, "are not added on this screen"):
			download_records_template(SCREEN, COMPANY)
		self.assertIsNone(frappe.db.get_value("Jubilee Update", self.older, "user_id"))
