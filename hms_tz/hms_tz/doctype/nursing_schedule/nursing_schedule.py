# Copyright (c) 2026, Aakvatech Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate


class NursingSchedule(Document):
	def validate(self):
		self.validate_assignment_fields()
		self.set_shift_times()
		self.validate_no_duplicate()

	def on_submit(self):
		self.create_shift_assignment()

	def on_update_after_submit(self):
		self.update_shift_assignment()

	def on_cancel(self):
		self.cancel_shift_assignment()

	def validate_assignment_fields(self):
		"""Ensure the correct location field is filled based on assign_based_on."""
		if self.assign_based_on == "Room" and not self.room:
			frappe.throw(
				_("Room is required when assigning based on Room."),
				title=_("Missing Field"),
			)
		if self.assign_based_on == "Ward" and not self.ward:
			frappe.throw(
				_("Ward is required when assigning based on Ward."),
				title=_("Missing Field"),
			)

	def set_shift_times(self):
		"""Auto-fill shift start/end times from the linked Shift Type."""
		if self.shift_type:
			shift = frappe.get_cached_value(
				"Shift Type",
				self.shift_type,
				["start_time", "end_time"],
				as_dict=True,
			)
			if shift:
				self.shift_start_time = shift.start_time
				self.shift_end_time = shift.end_time

	def validate_no_duplicate(self):
		"""Prevent duplicate: same nurse + same date + same shift type."""
		filters = {
			"nurse": self.nurse,
			"assignment_date": self.assignment_date,
			"shift_type": self.shift_type,
			"name": ["!=", self.name],
			"docstatus": ["!=", 2],
		}

		existing = frappe.db.exists("Nursing Schedule", filters)
		if existing:
			frappe.throw(
				msg=_(
					f"Nurse {self.nurse_name} already has a {self.shift_type} shift on {str(self.assignment_date)} ({existing})."
				),
				title=_("Duplicate Assignment"),
			)

	def _is_auto_shift_enabled(self) -> bool:
		"""Check if auto Shift Assignment creation is enabled for this company."""

		return bool(
			frappe.db.get_value(
				"HMS TZ Setting",
				self.company,
				"auto_create_shift_assignment_from_nursing_roster",
			)
		)

	def _get_employee(self) -> str | None:
		"""Get the Employee linked to this nurse (Healthcare Practitioner)."""

		return frappe.db.get_value("Healthcare Practitioner", self.nurse, "employee")

	def create_shift_assignment(self):
		"""Create and submit a Shift Assignment when this Nursing Schedule is submitted."""
		if not self._is_auto_shift_enabled():
			return

		employee = self._get_employee()
		if not employee:
			frappe.msgprint(
				_(f"Shift Assignment not created: Nurse {self.nurse_name} has no linked Employee."),
				alert=True,
				indicator="orange",
			)
			return

		sa = frappe.new_doc("Shift Assignment")
		sa.employee = employee
		sa.shift_type = self.shift_type
		sa.company = self.company
		sa.start_date = self.assignment_date
		sa.end_date = self.assignment_date
		sa.insert(ignore_permissions=True)
		sa.submit()

		self.db_set("shift_assignment", sa.name, update_modified=False)

	def update_shift_assignment(self):
		"""Update the linked Shift Assignment if key fields changed."""

		if not self.shift_assignment:
			return

		if not frappe.db.exists("Shift Assignment", self.shift_assignment):
			return

		sa = frappe.get_doc("Shift Assignment", self.shift_assignment)
		if sa.docstatus != 1:
			return

		needs_save = False

		if str(sa.start_date) != str(self.assignment_date):
			sa.start_date = self.assignment_date
			sa.end_date = self.assignment_date
			needs_save = True

		if sa.shift_type != self.shift_type:
			sa.shift_type = self.shift_type
			needs_save = True

		if needs_save:
			sa.db_update()

	def cancel_shift_assignment(self):
		"""Cancel the linked Shift Assignment when this Nursing Schedule is cancelled."""
		if not self.shift_assignment:
			return

		if not frappe.db.exists("Shift Assignment", self.shift_assignment):
			return

		sa = frappe.get_doc("Shift Assignment", self.shift_assignment)
		if sa.docstatus == 1:
			sa.flags.ignore_permissions = True
			sa.cancel()


def create_nurse_records_for_admitted_patients():
	"""Background job (every 1 hour): auto-create Nurse Records for admitted patients.

	Logic:
	1. Get all Nursing Schedule records for today that haven't yet generated
	   a Nurse Record (nurse_record_created == 0).
	2. Get all Inpatient Records with status 'Admitted'.
	3. For each admitted patient, get the last service unit from the
	   inpatient_occupancies child table.
	4. Match nursing schedules by comparing:
	   - schedule.room == last occupancy service_unit, OR
	   - schedule.ward == service_unit_type of the last
	     occupancy's service unit
	5. Create a Nurse Record for each match if one doesn't already exist.
	6. Mark the Nursing Schedule's nurse_record_created checkbox.
	"""
	today = nowdate()

	# Get today's nursing schedules that haven't generated records
	schedules = frappe.db.get_all(
		"Nursing Schedule",
		filters={
			"assignment_date": today,
			"docstatus": 1,
			"nurse_record_created": 0,
		},
		fields=[
			"name",
			"nurse",
			"nurse_name",
			"company",
			"assign_based_on",
			"room",
			"ward",
			"shift_type",
			"shift_start_time",
			"shift_end_time",
		],
	)

	if not schedules:
		return

	# Get all admitted inpatient records
	admitted_records = frappe.db.get_all(
		"Inpatient Record",
		filters={"status": "Admitted"},
		fields=["name", "patient", "company", "patient_appointment"],
	)

	if not admitted_records:
		return

	for ip in admitted_records:
		# Get the last service unit from inpatient occupancies
		last_occupancy = frappe.db.get_value(
			"Inpatient Occupancy",
			filters={
				"parent": ip.name,
				"parenttype": "Inpatient Record",
				"left": 0,
			},
			fieldname="service_unit",
			order_by="check_in desc",
		)

		if not last_occupancy:
			continue

		# Get the service unit type of the last occupancy's service unit
		last_su_type = frappe.db.get_value(
			"Healthcare Service Unit",
			last_occupancy,
			"service_unit_type",
		)

		for schedule in schedules:
			# Only match schedules in the same company
			if schedule.company != ip.company:
				continue

			# Match by service_unit or service_unit_type
			matched = False
			if schedule.assign_based_on == "Room" and schedule.room:
				matched = schedule.room == last_occupancy
			elif schedule.assign_based_on == "Ward" and schedule.ward:
				matched = schedule.ward == last_su_type

			if not matched:
				continue

			# Check if a record already exists for this nurse + patient + shift
			existing = frappe.db.exists(
				"Nurse Record",
				{
					"patient": ip.patient,
					"nurse": schedule.nurse,
					"posting_date": today,
					"shift_type": schedule.shift_type,
					"docstatus": ["!=", 2],
				},
			)
			if existing:
				# Still mark the schedule as processed
				frappe.db.set_value(
					"Nursing Schedule",
					schedule.name,
					"nurse_record_created",
					1,
					update_modified=False,
				)
				continue

			try:
				nr = frappe.new_doc("Nurse Record")
				nr.appointment = ip.patient_appointment
				nr.patient = ip.patient
				nr.nurse = schedule.nurse
				nr.posting_date = today
				nr.company = ip.company
				nr.inpatient_record = ip.name
				nr.nurse_shift = schedule.shift_type
				nr.shift_start_time = schedule.shift_start_time
				nr.shift_end_time = schedule.shift_end_time

				insurance_details = frappe.get_cached_value(
					"Patient Appointment",
					ip.patient_appointment,
					["insurance_company", "coverage_plan_name", "insurance_subscription"],
					as_dict=True,
				)
				if insurance_details.insurance_company:
					nr.payment_type = "Insurance"
					nr.insurance_company = insurance_details.insurance_company
					nr.insurance_coverage_plan = insurance_details.coverage_plan_name
					nr.insurance_subscription = insurance_details.insurance_subscription
				else:
					nr.payment_type = "Cash"
					nr.insurance_company = ""
					nr.insurance_coverage_plan = ""
					nr.insurance_subscription = ""

				nr.room = last_occupancy if schedule.assign_based_on == "Room" else None
				nr.ward = last_su_type if schedule.assign_based_on == "Ward" else None
				nr.flags.ignore_validate = True
				nr.insert(ignore_permissions=True)

				# Mark the nursing schedule
				frappe.db.set_value(
					"Nursing Schedule",
					schedule.name,
					"nurse_record_created",
					1,
					update_modified=False,
				)

			except Exception:
				frappe.log_error(
					title="Nurse Record Auto-Creation Error",
					message=(
						f"Failed to create Nurse Record for patient"
						f" {ip.patient}, nurse {schedule.nurse},"
						f" schedule {schedule.name}"
					),
					reference_doctype="Nursing Schedule",
					reference_name=schedule.name,
				)
				frappe.db.rollback()
