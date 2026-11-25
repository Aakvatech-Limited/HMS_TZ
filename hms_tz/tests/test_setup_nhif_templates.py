from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.api.setup_records import (
	download_records_template,
	get_company_records,
	get_screen,
	get_screen_fields,
	save_company_record,
)
from hms_tz.hms_tz.doctype.nhif_template_mapping.nhif_template_mapping import (
	accept_proposals,
	classify_new_nhif_items,
)
from hms_tz.tests.setup_template_helpers import COMPANY
from hms_tz.tests.test_nhif_templates import (
	add_nhif_item,
	delete_nhif_test_data,
	get_codes,
	get_mapping,
	prepare_nhif_company,
)

SCREEN = "nhif_templates"


class TestSetupNHIFTemplates(FrappeTestCase):
	def setUp(self):
		delete_nhif_test_data()
		prepare_nhif_company()
		add_nhif_item("T-XR", "X-Ray Left Femur AP and Lateral", 5, 11)
		add_nhif_item("T-BED", "Admission Charges for Premium Wards", 2, 8)
		add_nhif_item("T-ODD", "Qwerty Zxcvb Plorp", 7, 8)
		classify_new_nhif_items(COMPANY)

	def tearDown(self):
		delete_nhif_test_data()

	def save(self, name, **values):
		return save_company_record(SCREEN, COMPANY, frappe.as_json(values), name=name)

	def test_only_the_decision_fields_are_editable_and_nothing_is_added(self):
		screen = get_screen_fields(SCREEN)
		fields = {field["fieldname"]: field for field in screen["fields"]}
		editable = sorted(name for name, field in fields.items() if not field.get("read_only"))
		self.assertEqual(editable, ["medication_class", "modality_type", "proposed_doctype", "sub_kind"])
		self.assertEqual((screen["has_add_actions"], screen["is_read_only"]), (0, 0))
		with self.assertRaisesRegex(frappe.ValidationError, "are not added on this screen"):
			self.save(None, proposed_doctype="Item Only")
		with self.assertRaisesRegex(frappe.ValidationError, "are not added on this screen"):
			download_records_template(SCREEN, COMPANY)

	def test_list_filters_by_status_and_part_of_the_name(self):
		review = get_company_records(SCREEN, COMPANY, frappe.as_json({"status": "Review"}))["records"]
		self.assertEqual(sorted(record.name for record in review), ["T-BED", "T-ODD"])
		named = get_company_records(SCREEN, COMPANY, frappe.as_json({"nhif_item_name": "femur"}))["records"]
		self.assertEqual([record.name for record in named], ["T-XR"])

	def test_saving_confirms_the_decision_and_creates_its_records(self):
		self.save("T-ODD", proposed_doctype="Clinical Procedure Template", status="Created", nhif_code="X")
		mapping = get_mapping("T-ODD")
		self.assertEqual((mapping.status, mapping.method, mapping.nhif_code), ("Created", "Manual", "T-ODD"))
		self.assertEqual(mapping.confirmed_by, frappe.session.user)
		item = frappe.db.get_value("Clinical Procedure Template", "Qwerty Zxcvb Plorp", "item")
		self.assertEqual(get_codes(item), ["T-ODD"])
		with self.assertRaisesRegex(frappe.ValidationError, "can no longer be changed"):
			self.save("T-ODD", proposed_doctype="Ignore")

	def test_ignore_creates_nothing_and_can_be_decided_again(self):
		self.save("T-BED", proposed_doctype="Ignore")
		mapping = get_mapping("T-BED")
		self.assertEqual((mapping.status, mapping.created_records), ("Ignored", []))
		self.save("T-BED", proposed_doctype="Item Only")
		self.assertEqual(get_mapping("T-BED").status, "Created")
		self.assertEqual(get_codes("Admission Charges for Premium Wards"), ["T-BED"])

	def test_actions_accept_open_proposals_per_doctype(self):
		screen = get_screen(SCREEN, COMPANY)
		groups = {group["label"]: group["actions"] for group in screen.action_groups}
		accept = {action["key"]: action["label"] for action in groups["Accept proposals"]}
		self.assertEqual(accept["accept:Bed Item"], "Bed Item (1)")
		action = screen.get_action("accept:Bed Item")
		self.assertEqual((action["kwargs"], action["doctype"]), ({"proposed_doctype": "Bed Item"}, "Item"))
		self.assertEqual(
			[action["key"] for action in groups["NHIF codes"]],
			["classify_nhif_codes", "retry_failed_nhif_templates"],
		)
		with self.assertRaisesRegex(frappe.ValidationError, "is not an action of the NHIF templates screen"):
			screen.get_action("accept:Ignore")

	def test_an_accept_action_that_ran_stays_listed_with_its_run(self):
		screen = get_screen(SCREEN, COMPANY)
		accept_proposals(COMPANY, "Bed Item")
		with patch.object(type(screen), "action_runs", {"accept:Bed Item": {"status": "Done"}}):
			labels = [action["label"] for action in screen.action_groups[0]["actions"]]
		self.assertIn("Bed Item (0)", labels)
