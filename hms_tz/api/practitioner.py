import frappe
from erpnext.setup.doctype.employee.employee import is_holiday
from frappe.query_builder import DocType
from frappe.utils import get_abbr, get_time, getdate, nowdate


@frappe.whitelist()
def get_practioner_list(company, date=None):
	"""
	Get all available practitioners for a company on a specific date
	Filters out practitioners who are:
	- Not available based on schedules and availability
	- On leave or unavailable
	- Have no practitioner schedules

	Returns practitioners with their availability data
	"""

	if not date:
		date = nowdate()

	date = getdate(date)
	date.strftime("%A")

	available_practitioners = []

	practitioners = get_practitioners(company)

	for practitioner in practitioners:
		try:
			# Check employee availability (holidays, leaves)
			if not check_practitioner_employee_availability(
				practitioner.name, date, employee=practitioner.employee, user_id=practitioner.user_id
			):
				continue

			# Transform practitioner data to match frontend schema
			practitioner_data = {
				"name": practitioner.name,
				"department": practitioner.department or "General",
				"billing_item": practitioner.op_consulting_charge_item,
				"avatar": get_abbr(practitioner.practitioner_name) or "P",
				# get_practitioner_avatar(practitioner.practitioner_name),
				"is_available": True,
				"mobile_phone": practitioner.mobile_phone,
				"image": practitioner.image,
				# 'timeslots': [],
				# 'present_events': [],
			}

			available_practitioners.append(practitioner_data)

		except Exception:
			continue

	return {
		"practitioners": available_practitioners,
		"total_count": len(available_practitioners),
		"date": date,
		"company": company,
	}


def get_practitioners(company):
	"""
	Get all practitioners for a company, filtering by date and availability
	"""

	hp = DocType("Healthcare Practitioner")

	# Base query for practitioners
	practitioners = (
		frappe.qb.from_(hp)
		.select(
			hp.name,
			hp.practitioner_name,
			hp.department,
			hp.op_consulting_charge_item,
			hp.inpatient_visit_charge_item,
			hp.mobile_phone,
			hp.image,
			hp.status,
			hp.employee,
			hp.user_id,
		)
		.where((hp.status == "Active") & (hp.hms_tz_company == company))
		.orderby(hp.name)
	).run(as_dict=True)

	# TODO: check for schedules if configured on the practitioner master
	# use  inner join with Practitioner Schedule if needed

	return practitioners


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
