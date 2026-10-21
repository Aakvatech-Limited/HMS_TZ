import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.hms_tz.doctype.practitioner_availability.practitioner_availability import (
	WEEKDAYS,
	validate_event_overlap,
)

MONDAY = "2026-01-05"
TUESDAY = "2026-01-06"


def make_event(days=(), from_date=MONDAY):
	"""Unsaved event; repeats every day when `days` is given, else a single event on `from_date`."""
	event = frappe.get_doc(
		doctype="Practitioner Availability",
		name=frappe.generate_hash(),
		practitioner="_Test Overlap Practitioner",
		present=1,
		from_date=from_date,
		to_date=from_date,
		from_time="09:00:00",
		to_time="10:00:00",
	)
	event.update({day: int(day in days) for day in WEEKDAYS})
	if days:
		event.update({"repeat_this_event": 1, "repeat_on": "Every Day", "repeat_till": "2026-12-31"})
	return event


class TestPractitionerAvailabilityOverlap(FrappeTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_every_day_events_on_other_days_do_not_overlap(self):
		make_event(days=("monday", "wednesday")).db_insert()

		validate_event_overlap(make_event(days=("tuesday", "thursday")))

	def test_every_day_events_sharing_a_day_overlap(self):
		make_event(days=("monday", "wednesday")).db_insert()

		with self.assertRaises(frappe.ValidationError):
			validate_event_overlap(make_event(days=("wednesday", "friday")))

	def test_single_event_on_a_repeating_day_overlaps(self):
		make_event(days=WEEKDAYS).db_insert()

		with self.assertRaises(frappe.ValidationError):
			validate_event_overlap(make_event(from_date=TUESDAY))

	def test_single_event_on_another_day_does_not_overlap(self):
		make_event(days=("monday",)).db_insert()

		validate_event_overlap(make_event(from_date=TUESDAY))
