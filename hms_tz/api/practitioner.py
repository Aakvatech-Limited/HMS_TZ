import frappe
from erpnext.setup.doctype.employee.employee import is_holiday
from frappe import _
from frappe.query_builder import DocType
from frappe.utils import get_abbr, get_time, getdate, nowdate

# Only doctors take appointments; nurses, lab technicians and claim reviewers are practitioners too.
APPOINTMENT_PRACTITIONER_ROLE = "Doctor"

# Values of the Practitioner Status filter on the Appointments page.
PRACTITIONER_STATUSES = {"Active": ["Active"], "Disabled": ["Disabled"], "All": ["Active", "Disabled"]}


@frappe.whitelist()
def get_practioner_list(company, date=None, status="Active"):
	"""Grid columns for a company and date: doctors with the given status, and everyone who has appointments.

	An active doctor on holiday or leave is hidden unless they have appointments on the date. A practitioner
	with appointments always gets a column, so every appointment the user can read is on the page; columns of
	practitioners who cannot take a new booking that day are not available. Disabled practitioners are listed
	only for their records.
	"""
	date = getdate(date or nowdate())
	booked = get_booked_practitioners(company, date)
	doctors = get_practitioners(company, status)
	listed = {doctor.name for doctor in doctors}

	columns = []
	for doctor in doctors:
		is_available = doctor.status == "Active" and check_practitioner_employee_availability(
			doctor.name, date, employee=doctor.employee, user_id=doctor.user_id
		)
		if is_available or doctor.status != "Active" or doctor.name in booked:
			columns.append(get_column(doctor, bool(is_available)))
	for practitioner in get_practitioners_by_name(booked - listed, status):
		columns.append(get_column(practitioner, False))
	columns.sort(key=lambda column: column["name"])

	return {
		"practitioners": columns,
		"total_count": len(columns),
		"date": date,
		"company": company,
	}


def get_column(practitioner, is_available):
	return {
		"name": practitioner.name,
		"department": practitioner.department or "General",
		"billing_item": practitioner.op_consulting_charge_item,
		"inpatient_billing_item": practitioner.inpatient_visit_charge_item,
		"avatar": get_abbr(practitioner.practitioner_name) or "P",
		"status": practitioner.status,
		"is_available": is_available,
		"mobile_phone": practitioner.mobile_phone,
		"image": practitioner.image,
	}


def get_booked_practitioners(company, date):
	"""Practitioners of the appointments on the date that the user may read, as the List view shows them."""
	return set(
		frappe.get_list(
			"Patient Appointment",
			filters={"company": company, "appointment_date": date},
			pluck="practitioner",
			distinct=True,
		)
	)


@frappe.whitelist()
def search_practitioners(txt=""):
	"""Active doctors whose ID, name, department or MCT code contains the text, with NHIF details."""
	pattern = f"%{txt}%"
	return frappe.get_list(
		"Healthcare Practitioner",
		fields=[
			"name as value",
			"practitioner_name",
			"department",
			"nhif_physician_qualification",
			"tz_mct_code",
		],
		filters={"status": "Active", "practitioner_role": APPOINTMENT_PRACTITIONER_ROLE},
		or_filters=[
			["name", "like", pattern],
			["practitioner_name", "like", pattern],
			["department", "like", pattern],
			["tz_mct_code", "like", pattern],
		],
		order_by="practitioner_name asc",
		limit=20,
	)


PRACTITIONER_COLUMN_FIELDS = [
	"name",
	"practitioner_name",
	"department",
	"op_consulting_charge_item",
	"inpatient_visit_charge_item",
	"mobile_phone",
	"image",
	"status",
	"employee",
	"user_id",
]


def get_practitioners(company, status="Active"):
	"""Doctors of the company with the given filter status that the user may read, after user permissions."""
	return frappe.get_list(
		"Healthcare Practitioner",
		filters={
			"status": ["in", get_statuses(status)],
			"hms_tz_company": company,
			"practitioner_role": APPOINTMENT_PRACTITIONER_ROLE,
		},
		fields=PRACTITIONER_COLUMN_FIELDS,
		order_by="name asc",
	)


def get_practitioners_by_name(names, status="Active"):
	"""The named practitioners with the filter status, of any role or company, for their booked appointments."""
	if not names:
		return []
	return frappe.get_list(
		"Healthcare Practitioner",
		filters={"name": ["in", list(names)], "status": ["in", get_statuses(status)]},
		fields=PRACTITIONER_COLUMN_FIELDS,
	)


def get_statuses(status):
	if status not in PRACTITIONER_STATUSES:
		frappe.throw(_("Practitioner status must be one of {0}").format(", ".join(PRACTITIONER_STATUSES)))
	return PRACTITIONER_STATUSES[status]


def check_practitioner_employee_availability(practitioner, date, employee=None, user_id=None):
	"""
	Check if practitioner is available based on employee status
	Returns False if on holiday or leave
	"""
	try:
		if not employee:
			employee = frappe.get_cached_value("Employee", {"user_id": user_id}, "name")

		if not employee:
			return True

		# Check holiday
		if is_holiday(employee, date):
			return False

		# Check leave status
		if "hrms" in frappe.get_installed_apps():
			la = DocType("Leave Application")

			leave_records = (
				frappe.qb.from_(la)
				.select(la.name)
				.where(
					(la.employee == employee)
					& (la.docstatus == 1)
					& (la.from_date <= date)
					& (la.to_date >= date)
				)
			).run(as_dict=True)

			if len(leave_records) > 0:
				return False

	except Exception:
		return False
