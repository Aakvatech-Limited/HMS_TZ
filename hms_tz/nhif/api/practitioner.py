import frappe

from hms_tz.hms_tz.standard_records.standard_records import load_records

CONSULTATION_ROOM_TYPE = "Consultation"


def before_insert(doc, method=None):
	"""Link the standard starting schedule and the company's only consultation room to a new practitioner.

	Schedules and rooms the user entered are kept; only an empty room is filled.
	"""
	room = get_only_consultation_room(doc.hms_tz_company)
	if doc.practitioner_schedules:
		for row in doc.practitioner_schedules:
			row.service_unit = row.service_unit or room
		return
	schedule = get_starting_schedule()
	if schedule:
		doc.append("practitioner_schedules", {"schedule": schedule, "service_unit": room})


def get_starting_schedule():
	"""The standard schedule marked default, once the setup runner has created it."""
	row = next(row for row in load_records("practitioner_schedules.json") if row.get("default"))
	return frappe.db.exists("Practitioner Schedule", row["schedule_name"])


def get_only_consultation_room(company):
	"""The company's consultation room when it has exactly one, otherwise None."""
	if not company:
		return None
	rooms = frappe.get_all(
		"Healthcare Service Unit",
		filters={"company": company, "is_group": 0, "disabled": 0, "room_type": CONSULTATION_ROOM_TYPE},
		pluck="name",
		limit=2,
	)
	return rooms[0] if len(rooms) == 1 else None
