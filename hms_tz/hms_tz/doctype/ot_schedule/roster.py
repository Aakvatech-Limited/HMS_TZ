# Copyright (c) 2026, Aakvatech and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.utils import getdate, today


@frappe.whitelist()
def get_ot_roster_data(company: str, start_date: str, end_date: str) -> dict:
	"""Return theater rooms and scheduled surgeries for the given company and date range.

	Returns:
	    dict with keys:
	    - theater_rooms: list of {name, service_unit_type}
	    - schedules: list of OT Schedule records with team members
	"""
	if not company or not start_date or not end_date:
		frappe.throw(_("Company, Start Date, and End Date are required."))

	# Get theater rooms (Healthcare Service Units that are not groups)
	theater_rooms = get_theater_rooms(company)

	# Get all OT Schedules in the date range
	schedules = frappe.db.get_all(
		"OT Schedule",
		filters={
			"company": company,
			"date": ["between", [start_date, end_date]],
			"docstatus": ["!=", 2],
		},
		fields=[
			"name",
			"patient",
			"patient_name",
			"procedure_template",
			"theater_room",
			"date",
			"start_time",
			"estimated_duration",
			"end_time",
			"priority",
			"status",
			"notes",
		],
		order_by="date asc, start_time asc",
	)

	# Attach team members for each schedule, sorted by role
	schedule_names = [s.name for s in schedules]
	team_members = {}
	role_order = {"Surgeon": 1, "Assistant Surgeon": 2, "Anesthetist": 3, "Nurse": 4}
	if schedule_names:
		members = frappe.db.get_all(
			"OT Schedule Team",
			filters={"parent": ["in", schedule_names]},
			fields=["parent", "role", "practitioner", "practitioner_name", "user_id"],
			order_by="idx asc",
		)
		for m in members:
			team_members.setdefault(m.parent, []).append(m)

	for s in schedules:
		team = team_members.get(s.name, [])
		team.sort(key=lambda m: role_order.get(m.role, 99))
		s["team"] = team

	return {
		"theater_rooms": theater_rooms,
		"schedules": schedules,
	}


@frappe.whitelist()
def save_ot_schedule(schedule_data: str | dict) -> dict:
	"""Create a new OT Schedule from the roster dialog.

	schedule_data should contain:
	- patient, procedure_template, theater_room, date, start_time
	- estimated_duration, priority, notes, company
	- team: list of {role, practitioner}
	"""
	if isinstance(schedule_data, str):
		schedule_data = json.loads(schedule_data)

	doc = frappe.new_doc("OT Schedule")
	doc.patient = schedule_data.get("patient")
	doc.procedure_template = schedule_data.get("procedure_template")
	doc.theater_room = schedule_data.get("theater_room")
	doc.date = schedule_data.get("date")
	doc.start_time = schedule_data.get("start_time")
	doc.estimated_duration = schedule_data.get("estimated_duration")
	doc.priority = schedule_data.get("priority", "Elective")
	doc.notes = schedule_data.get("notes", "")
	doc.company = schedule_data.get("company")

	# Add team members
	for member in schedule_data.get("team", []):
		doc.append(
			"surgical_team",
			{
				"role": member.get("role"),
				"practitioner": member.get("practitioner"),
			},
		)

	doc.insert(ignore_permissions=False)
	doc.submit()
	frappe.db.commit()

	return {"name": doc.name, "message": _("OT Schedule {0} created.").format(doc.name)}


@frappe.whitelist()
def cancel_ot_schedule(name: str) -> dict:
	"""Cancel an OT Schedule. Only future-dated schedules can be cancelled."""
	doc = frappe.get_doc("OT Schedule", name)
	today_date = getdate(today())

	if getdate(doc.date) < today_date:
		frappe.throw(_("Cannot cancel past-dated schedules."))

	if doc.status in ("Cancelled", "Completed"):
		frappe.throw(_("Schedule is already {0}.").format(doc.status))

	if doc.docstatus == 1:
		doc.db_set("status", "Cancelled")
		doc.cancel()
	else:
		doc.db_set("status", "Cancelled")

	frappe.db.commit()
	return {"message": _("OT Schedule {0} cancelled.").format(name)}


@frappe.whitelist()
def remove_ot_schedule(name: str) -> dict:
	"""Remove (cancel + delete) an OT Schedule. Only future-dated schedules."""
	doc = frappe.get_doc("OT Schedule", name)
	today_date = getdate(today())

	if getdate(doc.date) < today_date:
		frappe.throw(_("Cannot remove past-dated schedules."))

	if doc.docstatus == 1:
		doc.cancel()

	frappe.delete_doc("OT Schedule", name, force=True)
	frappe.db.commit()
	return {"message": _("OT Schedule {0} removed.").format(name)}


@frappe.whitelist()
def postpone_ot_schedule(name: str) -> dict:
	"""Postpone an OT Schedule. Only future-dated scheduled entries can be postponed."""
	doc = frappe.get_doc("OT Schedule", name)
	today_date = getdate(today())

	if getdate(doc.date) < today_date:
		frappe.throw(_("Cannot postpone past-dated schedules."))

	if doc.status in ("Cancelled", "Completed", "Postponed"):
		frappe.throw(_("Schedule is already {0}.").format(doc.status))

	doc.db_set("status", "Postponed")
	frappe.db.commit()
	return {"message": _("OT Schedule {0} postponed.").format(name)}


@frappe.whitelist()
def search_patients(search_text: str = "", limit: int = 20) -> list:
	"""Search for active patients by name or patient ID.

	Searches across patient_name (with TRIM to handle data-entry whitespace)
	and the patient ID (name field). Returns up to `limit` results.
	"""
	if not search_text or not search_text.strip():
		# Return a reasonable set of recent/active patients when no search term given
		return frappe.db.get_all(
			"Patient",
			filters={"status": "Active"},
			fields=["name", "patient_name"],
			order_by="patient_name asc",
			limit_page_length=limit,
		)

	term = f"%{search_text.strip()}%"

	# Use raw SQL so we can apply TRIM() and search across both name and patient_name
	results = frappe.db.sql(
		"""
        SELECT name, patient_name
        FROM `tabPatient`
        WHERE
            status = 'Active'
            AND (
                TRIM(patient_name) LIKE %(term)s
                OR name LIKE %(term)s
            )
        ORDER BY TRIM(patient_name) ASC
        LIMIT %(limit)s
        """,
		{"term": term, "limit": int(limit)},
		as_dict=True,
	)
	return results


@frappe.whitelist()
def get_theater_rooms(company: str) -> list:
	"""Return theater rooms for the company."""
	hsu = frappe.qb.DocType("Healthcare Service Unit")
	return (
		frappe.qb.from_(hsu)
		.select(hsu.name, hsu.healthcare_service_unit_name, hsu.service_unit_type)
		.where(hsu.company == company)
		.where(hsu.is_group == 0)
		.where(hsu.disabled == 0)
		.where((hsu.name.like("%theater%")) | (hsu.name.like("%theatre%")))
		.orderby(hsu.name)
		.run(as_dict=True)
	)
