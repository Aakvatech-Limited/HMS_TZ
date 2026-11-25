from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.api.setup_records import (
	download_records_template,
	get_company_records,
	get_screen_fields,
	import_company_records,
	save_company_record,
)
from hms_tz.hms_tz.setup_screens.nhif_item import NHIFItem

SCREEN = "nhif_items"
COMPANY = "_Test Company"
ITEM_TYPE_ID = 9901
SERVICE_TYPE_ID = "9902"


class TestSetupNHIFItems(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("NHIF Item", {"itemcode": ["like", "TNHIF-%"]})
		frappe.db.delete("NHIF Item Type", {"item_type_id": ITEM_TYPE_ID})
		frappe.db.delete("NHIF Service Type", {"service_type_id": SERVICE_TYPE_ID})
		frappe.delete_doc_if_exists("Setup Status", COMPANY)
		frappe.delete_doc_if_exists("HMS TZ Setting", COMPANY)
		frappe.get_doc({"doctype": "HMS TZ Setting", "company": COMPANY, "facility_code": "TEST"}).insert()
		frappe.get_doc(
			{"doctype": "NHIF Item Type", "item_type_id": ITEM_TYPE_ID, "type_name": "Test Diagnostics"}
		).insert()
		frappe.get_doc(
			{
				"doctype": "NHIF Service Type",
				"service_type_id": SERVICE_TYPE_ID,
				"service_type_name": "Test Investigations",
			}
		).insert()
		self.xray = self.create_item("TNHIF-2", "X-Ray Chest PA", servicetypeid=int(SERVICE_TYPE_ID))
		self.blood = self.create_item("TNHIF-1", "Full Blood Picture", servicetypeid=int(SERVICE_TYPE_ID))
		self.other = self.create_item("TNHIF-3", "Paracetamol", itemtypeid=3, isactive=0)

	def create_item(self, itemcode, itemname, itemtypeid=ITEM_TYPE_ID, servicetypeid=None, isactive=1):
		item = frappe.get_doc(
			{
				"doctype": "NHIF Item",
				"itemcode": itemcode,
				"itemname": itemname,
				"itemtypeid": itemtypeid,
				"servicetypeid": servicetypeid,
				"isactive": isactive,
			}
		)
		return item.insert().name

	def get_codes(self, **list_filters):
		result = get_company_records(SCREEN, COMPANY, frappe.as_json(list_filters))
		return [record.itemcode for record in result["records"] if record.itemcode.startswith("TNHIF-")]

	def test_screen_is_read_only_with_type_names_after_their_ids(self):
		screen = get_screen_fields(SCREEN)
		fields = [field["fieldname"] for field in screen["fields"]]
		self.assertEqual(
			(screen["is_read_only"], screen["has_add_actions"], screen["title_field"]), (1, 0, "itemname")
		)
		self.assertEqual(fields[:3], ["itemcode", "itemtypeid", "item_type"])
		self.assertEqual(fields[fields.index("servicetypeid") + 1], "service_type")
		self.assertNotIn("item_type", NHIFItem(COMPANY).fieldnames)

	def test_list_is_ordered_by_code_with_type_names(self):
		records = get_company_records(SCREEN, COMPANY)["records"]
		blood = next(record for record in records if record.name == self.blood)
		self.assertEqual(self.get_codes(), ["TNHIF-1", "TNHIF-2", "TNHIF-3"])
		self.assertEqual((blood.item_type, blood.service_type), ("Test Diagnostics", "Test Investigations"))

	def test_text_filters_match_part_of_the_value_and_ids_match_exactly(self):
		self.assertEqual(self.get_codes(itemname="ray ch"), ["TNHIF-2"])
		self.assertEqual(self.get_codes(itemcode="TNHIF-"), ["TNHIF-1", "TNHIF-2", "TNHIF-3"])
		self.assertEqual(self.get_codes(itemtypeid=ITEM_TYPE_ID), ["TNHIF-1", "TNHIF-2"])
		self.assertEqual(self.get_codes(itemcode="TNHIF-", isactive=1), ["TNHIF-1", "TNHIF-2"])

	def test_list_shows_at_most_page_length_items(self):
		with patch.object(NHIFItem, "page_length", 2):
			result = get_company_records(SCREEN, COMPANY, frappe.as_json({"itemcode": "TNHIF-"}))
		self.assertEqual((len(result["records"]), result["has_more"]), (2, True))

	def test_items_are_never_changed_added_imported_or_templated(self):
		with self.assertRaisesRegex(frappe.ValidationError, "are not changed on this screen"):
			save_company_record(SCREEN, COMPANY, frappe.as_json({"itemname": "x"}), name=self.blood)
		with self.assertRaisesRegex(frappe.ValidationError, "are not changed on this screen"):
			save_company_record(SCREEN, COMPANY, frappe.as_json({"itemname": "x"}))
		with self.assertRaisesRegex(frappe.ValidationError, "are not added on this screen"):
			import_company_records(SCREEN, COMPANY, "/private/files/nhif_items.csv")
		with self.assertRaisesRegex(frappe.ValidationError, "are not added on this screen"):
			download_records_template(SCREEN, COMPANY)
		self.assertEqual(frappe.db.get_value("NHIF Item", self.blood, "itemname"), "Full Blood Picture")
