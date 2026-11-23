import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.api.rooms import get_company_rooms, get_room_fields, save_room
from hms_tz.hms_tz.doctype.setup_status.setup_status import get_setup_status

COMPANY = "_Test Company"
UNIT_TYPE = "_Test Setup Room Type"
ROOM = "_Test Setup Room"


class TestSetupRooms(FrappeTestCase):
	def setUp(self):
		frappe.delete_doc_if_exists("Healthcare Service Unit", f"{ROOM} - _TC")
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

	def test_room_needs_a_service_unit_type(self):
		get_company_rooms(COMPANY)
		with self.assertRaises(frappe.ValidationError):
			save_room(COMPANY, self.room_values(service_unit_type=None))
