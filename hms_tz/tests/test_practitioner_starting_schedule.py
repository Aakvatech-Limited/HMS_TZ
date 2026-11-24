from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.hms_tz.standard_records.standard_records import StandardRecords, load_records
from hms_tz.nhif.api.practitioner import CONSULTATION_ROOM_TYPE, before_insert
from hms_tz.tests.test_standard_records import FakeProgress

COMPANY = "_Test Company 1"
STANDARD_STARTING_SCHEDULE = "Weekdays 08:00 - 17:00"
OTHER_SCHEDULE = "24 Hours"


def add_room(name, room_type=CONSULTATION_ROOM_TYPE):
	return (
		frappe.get_doc(
			{
				"doctype": "Healthcare Service Unit",
				"healthcare_service_unit_name": f"{name} {frappe.generate_hash(length=6)}",
				"company": COMPANY,
				"parent_healthcare_service_unit": frappe.db.get_value(
					"Healthcare Service Unit", {"company": COMPANY, "is_group": 1}
				),
				"room_type": room_type,
			}
		)
		.insert(ignore_permissions=True, ignore_mandatory=True)
		.name
	)


def new_practitioner(schedules=None):
	doc = frappe.new_doc("Healthcare Practitioner")
	doc.hms_tz_company = COMPANY
	for schedule in schedules or []:
		doc.append("practitioner_schedules", schedule)
	before_insert(doc)
	return [(row.schedule, row.service_unit) for row in doc.practitioner_schedules]


class TestPractitionerStartingSchedule(FrappeTestCase):
	def setUp(self):
		records = StandardRecords(COMPANY, FakeProgress())
		records.create("Practitioner Schedule")
		records.create("Healthcare Room Type")
		frappe.db.set_value("Healthcare Service Unit", {"company": COMPANY, "is_group": 0}, "disabled", 1)

	def test_one_standard_schedule_is_the_starting_schedule(self):
		rows = load_records("practitioner_schedules.json")
		starting = [row["schedule_name"] for row in rows if row.get("default")]
		self.assertEqual(starting, [STANDARD_STARTING_SCHEDULE])

	def test_the_hook_runs_on_practitioner_insert(self):
		hooks = frappe.get_hooks("doc_events")["Healthcare Practitioner"]["before_insert"]
		self.assertIn("hms_tz.nhif.api.practitioner.before_insert", hooks)

	def test_one_consultation_room_is_linked_with_the_weekdays_schedule(self):
		room = add_room("_Test Consultation One")
		add_room("_Test Ward Bed", room_type="General")
		self.assertEqual(new_practitioner(), [(STANDARD_STARTING_SCHEDULE, room)])

	def test_several_consultation_rooms_link_no_room(self):
		add_room("_Test Consultation One")
		add_room("_Test Consultation Two")
		self.assertEqual(new_practitioner(), [(STANDARD_STARTING_SCHEDULE, None)])

	def test_a_disabled_consultation_room_does_not_count(self):
		room = add_room("_Test Consultation One")
		frappe.db.set_value("Healthcare Service Unit", add_room("_Test Consultation Two"), "disabled", 1)
		self.assertEqual(new_practitioner(), [(STANDARD_STARTING_SCHEDULE, room)])

	def test_no_schedule_is_linked_before_setup_creates_it(self):
		missing = [{"schedule_name": "_Test Missing Schedule", "default": 1}]
		with patch("hms_tz.nhif.api.practitioner.load_records", return_value=missing):
			self.assertEqual(new_practitioner(), [])

	def test_entered_schedules_and_rooms_are_kept(self):
		room = add_room("_Test Consultation One")
		entered_room = add_room("_Test Ward Bed", room_type="General")
		rows = new_practitioner(
			[
				{"schedule": OTHER_SCHEDULE, "service_unit": entered_room},
				{"schedule": "Weekdays and Saturday"},
			]
		)
		self.assertEqual(rows, [(OTHER_SCHEDULE, entered_room), ("Weekdays and Saturday", room)])
