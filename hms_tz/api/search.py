import frappe
from frappe.permissions import get_doctypes_with_read
from frappe.utils import add_days, today

from hms_tz.api.appointment_insurance import search_patients

PATIENT_ROWS = 5
APPOINTMENT_ROWS = 10
RECENT_DAYS = 30
APPOINTMENT_FIELDS = [
	"name",
	"patient",
	"patient_name",
	"practitioner_name",
	"appointment_date",
	"appointment_time",
	"status",
	"company",
]


@frappe.whitelist()
def get_permitted_doctypes():
	"""Return doctypes the current user has read permission to, for search navigation.

	Uses Frappe's built-in permission check (get_doctypes_with_read) which
	respects Role Permissions and User Permissions for frappe.session.user.
	Child table (istable) doctypes are excluded since users don't navigate to them.
	"""
	permitted = get_doctypes_with_read()

	result = []
	for dt_name in permitted:
		try:
			meta = frappe.get_meta(dt_name)
		except Exception:
			continue

		# Skip child table doctypes — not directly navigable
		if meta.istable:
			continue

		slug = frappe.scrub(dt_name).replace("_", "-")
		description = dt_name if meta.issingle else f"{dt_name} List"

		result.append(
			{
				"label": dt_name,
				"description": description,
				"route": f"/app/{slug}",
				"type": "page",
			}
		)

	result.sort(key=lambda x: x["label"])
	return result


@frappe.whitelist()
def search_patients_and_appointments(txt):
	"""Patients matching the text as the booking dialog finds them (ID, name, mobile also as 07..., card no),
	and their appointments from RECENT_DAYS ago on. get_list keeps both to what the user may read."""
	patients = search_patients(txt, page_length=PATIENT_ROWS)
	if not patients:
		return {"patients": [], "appointments": []}
	appointments = frappe.get_list(
		"Patient Appointment",
		fields=APPOINTMENT_FIELDS,
		filters={
			"patient": ["in", [patient.value for patient in patients]],
			"appointment_date": [">=", add_days(today(), -RECENT_DAYS)],
		},
		order_by="appointment_date desc, appointment_time desc",
		limit=APPOINTMENT_ROWS,
	)
	return {"patients": patients, "appointments": appointments}
