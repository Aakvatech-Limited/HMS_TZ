import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.csvutils import to_csv

from hms_tz.api.rooms import (
	download_rooms_template,
	get_company_rooms,
	get_room_fields,
	import_rooms,
	save_room,
)
from hms_tz.hms_tz.doctype.setup_status.setup_status import get_setup_status

COMPANY = "_Test Company"
UNIT_TYPE = "_Test Setup Room Type"
ROOM = "_Test Setup Room"


class TestSetupRooms(FrappeTestCase):
	def setUp(self):
		for name in (ROOM, f"{ROOM} A", f"{ROOM} B", f"{ROOM} C"):
			frappe.delete_doc_if_exists("Healthcare Service Unit", f"{name} - _TC")
		frappe.delete_doc_if_exists("Setup Status", COMPANY)
		frappe.delete_doc_if_exists("HMS TZ Setting", COMPANY)
		frappe.db.set_single_value(
			"Healthcare Settings", {"collect_registration_fee": 0, "enable_free_follow_ups": 0}
		)
		frappe.get_doc({"doctype": "HMS TZ Setting", "company": COMPANY, "facility_code": "TEST"}).insert()
		if not frappe.db.exists("Healthcare Service Unit Type", UNIT_TYPE):
			unit_type = frappe.get_doc(
				{
					"doctype": "Healthcare Service Unit Type",
					"service_unit_type": UNIT_TYPE,
					"allow_appointments": 1,
				}
			)
			unit_type.insert(ignore_mandatory=True)
		self.room_type = frappe.get_all("Healthcare Room Type", pluck="name", limit=1)[0]

	def room_values(self, **values):
		return {
			"healthcare_service_unit_name": ROOM,
			"room_type": self.room_type,
			"service_unit_type": UNIT_TYPE,
			**values,
		}

	def test_room_fields_are_the_required_ones_plus_type_and_warehouse(self):
		fields = {field["fieldname"]: field for field in get_room_fields()}
		self.assertIn("healthcare_service_unit_name", fields)
		self.assertIn("room_type", fields)
		self.assertEqual(fields["service_unit_type"]["reqd"], 1)
		self.assertIn("eval: doc.company", fields["warehouse"]["link_filters"])
		self.assertNotIn("company", fields)

	def test_rooms_stay_locked_until_settings_are_complete(self):
		frappe.db.set_value("HMS TZ Setting", COMPANY, "enable_nhif_api", 1)
		self.assertFalse(get_company_rooms(COMPANY)["settings_complete"])
		with self.assertRaises(frappe.ValidationError):
			save_room(COMPANY, self.room_values())

	def test_new_room_goes_under_the_company_root_and_ticks_the_step(self):
		get_company_rooms(COMPANY)
		name = save_room(COMPANY, self.room_values(company="_Test Company 1", is_group=1))
		room = frappe.get_doc("Healthcare Service Unit", name)
		self.assertEqual((room.company, room.is_group), (COMPANY, 0))
		self.assertEqual(room.parent_healthcare_service_unit, "All Healthcare Service Units - _TC")
		self.assertTrue(get_setup_status(COMPANY).get_step("Healthcare Service Unit").completed)
		self.assertIn(name, [row.name for row in get_company_rooms(COMPANY)["rooms"]])

	def test_changing_a_room_keeps_its_name(self):
		get_company_rooms(COMPANY)
		name = save_room(COMPANY, self.room_values())
		unit_name = frappe.db.get_value("Healthcare Service Unit", name, "healthcare_service_unit_name")
		save_room(COMPANY, self.room_values(healthcare_service_unit_name="Renamed", disabled=1), name=name)
		room = frappe.get_doc("Healthcare Service Unit", name)
		self.assertEqual((room.healthcare_service_unit_name, room.disabled), (unit_name, 1))

	def test_overlapping_type_needs_a_capacity(self):
		overlap_type = "_Test Setup Overlap Type"
		if not frappe.db.exists("Healthcare Service Unit Type", overlap_type):
			values = {"service_unit_type": overlap_type, "allow_appointments": 1, "overlap_appointments": 1}
			frappe.get_doc({"doctype": "Healthcare Service Unit Type", **values}).insert(
				ignore_mandatory=True
			)
		get_company_rooms(COMPANY)
		with self.assertRaisesRegex(frappe.ValidationError, "Capacity"):
			save_room(COMPANY, self.room_values(service_unit_type=overlap_type))
		name = save_room(
			COMPANY, self.room_values(service_unit_type=overlap_type, total_service_unit_capacity=3)
		)
		self.assertEqual(
			frappe.db.get_value("Healthcare Service Unit", name, "total_service_unit_capacity"), 3
		)

	def test_room_needs_a_service_unit_type(self):
		get_company_rooms(COMPANY)
		with self.assertRaises(frappe.ValidationError):
			save_room(COMPANY, self.room_values(service_unit_type=None))

	def upload(self, *rows):
		header = ["Service Unit", "Service Unit Type", "Room Type", "Warehouse"]
		content = to_csv([header, *[list(row) for row in rows]])
		file = frappe.get_doc(
			{"doctype": "File", "file_name": "rooms.csv", "content": content, "is_private": 1}
		)
		return file.insert().file_url

	def room_names(self):
		return {room.name for room in get_company_rooms(COMPANY)["rooms"]}

	def get_template_rooms(self, sample_rooms):
		download_rooms_template(COMPANY, sample_rooms=sample_rooms, file_type="CSV")
		header, *rows = [line for line in frappe.response["result"].splitlines() if line]
		self.assertIn("Service Unit Type", header)
		return rows

	def test_template_holds_only_the_asked_number_of_sample_rooms(self):
		get_company_rooms(COMPANY)
		for name in (f"{ROOM} A", f"{ROOM} B", f"{ROOM} C"):
			save_room(COMPANY, self.room_values(healthcare_service_unit_name=name))
		self.assertEqual(self.get_template_rooms("0"), [])
		self.assertEqual(len(self.get_template_rooms("2")), 2)
		self.assertGreaterEqual(len(self.get_template_rooms("all")), 3)

	def test_valid_import_adds_every_row(self):
		get_company_rooms(COMPANY)
		file_url = self.upload(
			(f"{ROOM} A", UNIT_TYPE, self.room_type, "_Test Warehouse - _TC"),
			(f"{ROOM} B", UNIT_TYPE, self.room_type, ""),
		)
		result = import_rooms(COMPANY, file_url)
		self.assertEqual((result["added"], result["changed"], result["errors"]), (2, 0, []))
		self.assertTrue({f"{ROOM} A - _TC", f"{ROOM} B - _TC"} <= self.room_names())
		self.assertTrue(get_setup_status(COMPANY).get_step("Healthcare Service Unit").completed)

	def test_invalid_rows_are_reported_and_the_rest_imported(self):
		get_company_rooms(COMPANY)
		file_url = self.upload(
			(f"{ROOM} A", "No Such Type", self.room_type, ""),
			(f"{ROOM} B", UNIT_TYPE, self.room_type, "_Test Warehouse 2 - _TC1"),
			(f"{ROOM} C", UNIT_TYPE, self.room_type, "No Such Warehouse"),
			(ROOM, UNIT_TYPE, self.room_type, ""),
		)
		result = import_rooms(COMPANY, file_url)
		self.assertEqual(result["added"], 1)
		self.assertEqual([error["row"] for error in result["errors"]], [2, 3, 4])
		self.assertIn("No Such Type", result["errors"][0]["message"])
		self.assertIn("_Test Company 1", result["errors"][1]["message"])
		self.assertIn("No Such Warehouse", result["errors"][2]["message"])
		self.assertNotIn(f"{ROOM} A - _TC", self.room_names())

	def test_repeated_import_changes_rooms_instead_of_adding_them(self):
		get_company_rooms(COMPANY)
		rows = [(f"{ROOM} A", UNIT_TYPE, self.room_type, ""), (f"{ROOM} B", UNIT_TYPE, self.room_type, "")]
		import_rooms(COMPANY, self.upload(*rows))
		rooms_after_first_import = self.room_names()
		rows[0] = (f"{ROOM} A", UNIT_TYPE, self.room_type, "_Test Warehouse - _TC")
		result = import_rooms(COMPANY, self.upload(*rows))
		self.assertEqual((result["added"], result["changed"], result["errors"]), (0, 2, []))
		self.assertEqual(self.room_names(), rooms_after_first_import)
		self.assertEqual(
			frappe.db.get_value("Healthcare Service Unit", f"{ROOM} A - _TC", "warehouse"),
			"_Test Warehouse - _TC",
		)

	def test_import_stays_locked_until_settings_are_complete(self):
		frappe.db.set_value("HMS TZ Setting", COMPANY, "enable_nhif_api", 1)
		get_company_rooms(COMPANY)
		with self.assertRaises(frappe.ValidationError):
			import_rooms(COMPANY, self.upload((f"{ROOM} A", UNIT_TYPE, self.room_type, "")))
