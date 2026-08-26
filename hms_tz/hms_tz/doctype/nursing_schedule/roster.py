# Copyright (c) 2026, Aakvatech Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_to_date, getdate, today


@frappe.whitelist()
def get_roster_data(
	company: str,
	start_date: str,
	end_date: str,
	department: str = None,
	designation: str = None,
	branch: str = None,
) -> dict:
	"""Return nurses and their existing assignments for the given company and date range.

	Returns:
	    dict with keys:
	    - nurses: list of {name, practitioner_name, employee}
	    - assignments: list of {name, nurse, nurse_name, assignment_date,
	      assign_based_on, ward, room, shift_type, shift_start_time, shift_end_time}
	    - nurse_leave_dates: dict mapping nurse name → list of leave date strings
	"""
	if not company or not start_date or not end_date:
		frappe.throw(_("Company, Start Date, and End Date are required."))

	hp = frappe.qb.DocType("Healthcare Practitioner")
	emp = frappe.qb.DocType("Employee")

	query = (
		frappe.qb.from_(hp)
		.inner_join(emp)
		.on(hp.employee == emp.name)
		.select(hp.name, hp.practitioner_name, hp.employee)
		.where(hp.practitioner_role == "Nurse")
		.where(hp.hms_tz_company == company)
		.where(hp.status == "Active")
		.orderby(hp.practitioner_name)
	)

	if department:
		query = query.where(emp.department == department)
	if designation:
		query = query.where(emp.designation == designation)
	if branch:
		query = query.where(emp.branch == branch)

	nurses = query.run(as_dict=True)

	# Build employee → nurse mapping for leave lookups
	employee_nurse_map = {}
	employee_ids = []
	for n in nurses:
		if n.employee:
			employee_nurse_map[n.employee] = n.name
			employee_ids.append(n.employee)

	# Query approved leaves overlapping the roster date range
	nurse_leave_dates: dict[str, list[str]] = {}
	roster_start = getdate(start_date)
	roster_end = getdate(end_date)

	if employee_ids:
		leaves = frappe.db.get_all(
			"Leave Application",
			filters={
				"employee": ["in", employee_ids],
				"status": "Approved",
				"from_date": ["<=", end_date],
				"to_date": [">=", start_date],
			},
			fields=["employee", "from_date", "to_date"],
		)

		for leave in leaves:
			nurse_name = employee_nurse_map.get(leave.employee)
			if not nurse_name:
				continue

			overlap_start = max(getdate(leave.from_date), roster_start)
			overlap_end = min(getdate(leave.to_date), roster_end)

			if nurse_name not in nurse_leave_dates:
				nurse_leave_dates[nurse_name] = []

			current = overlap_start
			while current <= overlap_end:
				date_str = current.strftime("%Y-%m-%d")
				if date_str not in nurse_leave_dates[nurse_name]:
					nurse_leave_dates[nurse_name].append(date_str)
				current = add_to_date(current, days=1)

	nurse_names = [n.name for n in nurses]

	# Get assignments from Nursing Schedule
	assignments = []
	if nurse_names:
		assignments = frappe.db.get_all(
			"Nursing Schedule",
			filters={
				"nurse": ["in", nurse_names],
				"assignment_date": ["between", [start_date, end_date]],
				"docstatus": ["!=", 2],
			},
			fields=[
				"name",
				"nurse",
				"nurse_name",
				"assignment_date",
				"assign_based_on",
				"ward",
				"room",
				"shift_type",
				"shift_start_time",
				"shift_end_time",
			],
			order_by="assignment_date asc, shift_start_time asc",
		)

	return {
		"nurses": nurses,
		"assignments": assignments,
		"nurse_leave_dates": nurse_leave_dates,
	}


@frappe.whitelist()
def save_roster_assignments(
	company: str,
	start_date: str,
	end_date: str,
	assignments: list | str,
) -> dict:
	"""Batch-save roster assignments as individual Nursing Schedule records.

	Each assignment dict should have:
	- nurse: str
	- assignment_date: str (YYYY-MM-DD)
	- assign_based_on: str (Ward / Room)
	- ward: str (optional)
	- room: str (optional)
	- shift_type: str
	- shift_start_time: str (optional — auto-filled from shift_type)
	- shift_end_time: str (optional — auto-filled from shift_type)
	- existing_name: str (optional — for editing/removing existing records)
	- action: str (add / edit / remove)
	"""
	import json

	if isinstance(assignments, str):
		assignments = json.loads(assignments)

	if not assignments:
		return {"message": _("No assignments to save.")}

	today_date = getdate(today())
	created = 0
	updated = 0
	removed = 0

	for assignment in assignments:
		action = assignment.get("action", "add")
		existing_name = assignment.get("existing_name")
		assignment_date = getdate(assignment.get("assignment_date"))

		# Block modifications to past-date assignments
		if assignment_date < today_date:
			frappe.msgprint(
				_("Cannot modify assignment for {0} — date has already passed.").format(
					frappe.bold(str(assignment_date))
				),
				alert=True,
			)
			continue

		if action == "remove" and existing_name:
			doc = frappe.get_doc("Nursing Schedule", existing_name)
			if doc.docstatus == 1:
				doc.cancel()
			frappe.delete_doc("Nursing Schedule", existing_name, force=True)
			removed += 1
			continue

		if action == "edit" and existing_name:
			update_values = {
				"assign_based_on": assignment.get("assign_based_on", ""),
				"shift_type": assignment.get("shift_type", ""),
				"shift_start_time": assignment.get("shift_start_time", ""),
				"shift_end_time": assignment.get("shift_end_time", ""),
			}
			if assignment.get("assign_based_on") == "Ward":
				update_values["ward"] = assignment.get("ward", "")
				update_values["room"] = ""
			else:
				update_values["room"] = assignment.get("room", "")
				update_values["ward"] = ""

			frappe.db.set_value(
				"Nursing Schedule",
				existing_name,
				update_values,
				update_modified=True,
			)
			updated += 1
			continue

		# action == "add" — create and submit a new individual record
		# Check for duplicate (same nurse + date + shift)
		existing = frappe.db.exists(
			"Nursing Schedule",
			{
				"nurse": assignment.get("nurse"),
				"assignment_date": assignment.get("assignment_date"),
				"shift_type": assignment.get("shift_type"),
				"docstatus": ["!=", 2],
			},
		)
		if existing:
			frappe.msgprint(
				_(
					f"Nurse {assignment.get('nurse')} already has a {assignment.get('shift_type')} shift on {assignment.get('assignment_date')}. Skipping."
				),
				alert=True,
			)
			continue

		doc = frappe.new_doc("Nursing Schedule")
		doc.company = company
		doc.nurse = assignment.get("nurse")
		doc.assignment_date = assignment.get("assignment_date")
		doc.assign_based_on = assignment.get("assign_based_on", "Ward")
		doc.ward = assignment.get("ward", "")
		doc.room = assignment.get("room", "")
		doc.shift_type = assignment.get("shift_type", "")
		doc.shift_start_time = assignment.get("shift_start_time", "")
		doc.shift_end_time = assignment.get("shift_end_time", "")
		doc.insert(ignore_permissions=False)
		doc.submit()
		created += 1

	frappe.db.commit()

	parts = []
	if created:
		parts.append(_("{0} created").format(created))
	if updated:
		parts.append(_("{0} updated").format(updated))
	if removed:
		parts.append(_("{0} removed").format(removed))

	return {
		"message": _(f"Roster saved: {', '.join(parts) if parts else 'No changes made.'}"),
	}


@frappe.whitelist()
def get_service_options(company: str) -> dict:
	"""Return wards (service unit types), rooms (service units), and shift types."""
	wards = frappe.db.get_all(
		"Healthcare Service Unit Type",
		filters={"disabled": 0},
		fields=["name"],
		order_by="name asc",
	)

	rooms = frappe.db.get_all(
		"Healthcare Service Unit",
		filters={"is_group": 0, "disabled": 0, "company": company},
		fields=["name", "service_unit_type"],
		order_by="name asc",
	)

	shift_types = frappe.db.get_all(
		"Shift Type",
		fields=["name", "start_time", "end_time"],
		order_by="name asc",
	)

	return {
		"wards": [s.name for s in wards],
		"rooms": [{"name": s.name, "type": s.service_unit_type} for s in rooms],
		"shift_types": [
			{"name": s.name, "start_time": str(s.start_time or ""), "end_time": str(s.end_time or "")}
			for s in shift_types
		],
	}
