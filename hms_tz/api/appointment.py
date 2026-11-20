import frappe
from frappe import _
from frappe.core.doctype.user_permission.user_permission import get_user_permissions
from frappe.query_builder import DocType
from frappe.utils import cint, get_datetime, get_time, getdate, now_datetime

from hms_tz.api.appointment_insurance import link_jubilee_benefits
from hms_tz.nhif.api.patient_appointment import (
	add_cancel_comment,
	change_visit_type,
	get_cash_amount,
	get_consulting_charge_item,
	validate_cancellable,
	validate_cash_billing,
	validate_patient_can_book,
)

DEFAULT_SLOT_DURATION = 10


@frappe.whitelist()
def get_user_companies():
	"""Companies the user may book for, and the one to select first.

	Read from the user's Company user permissions, not from Company read access: a receptionist
	restricted to one company usually has no permission on the Company doctype itself.
	"""
	permitted = [
		permission.get("doc")
		for permission in get_user_permissions().get("Company", [])
		if permission.get("applicable_for") in (None, "", "Patient Appointment")
	]
	companies = permitted or frappe.get_all("Company", pluck="name", order_by="name asc")
	default_company = frappe.defaults.get_user_default("Company")
	if default_company not in companies:
		default_company = companies[0] if companies else None

	return {
		"companies": companies,
		"default_company": default_company,
		"slot_durations": get_slot_durations(companies),
	}


def get_slot_durations(companies):
	"""Appointment grid slot minutes per company, from HMS TZ Setting; companies without one get the default."""
	configured = dict(
		frappe.get_all(
			"HMS TZ Setting",
			filters={"name": ["in", companies]},
			fields=["name", "appointment_slot_duration"],
			as_list=True,
		)
	)
	return {company: configured.get(company) or DEFAULT_SLOT_DURATION for company in companies}


@frappe.whitelist()
def search_visit_types(txt=""):
	"""Enabled Appointment Types whose name contains the text."""
	return frappe.get_list(
		"Appointment Type",
		fields=["name as value"],
		filters={"name": ["like", f"%{txt}%"], "disabled": 0},
		order_by="name asc",
		limit=20,
	)


@frappe.whitelist()
def create_appointment(appointment_data):
	"""
	Create a new appointment with the provided data.
	"""

	appointment_doc = frappe.new_doc("Patient Appointment")
	appointment_doc.update(appointment_data)
	# Checks the role and the user's company permission before ignore_permissions saves.
	appointment_doc.check_permission("create")
	validate_not_in_past(appointment_doc.appointment_date, appointment_doc.appointment_time)
	validate_active_practitioner(appointment_doc.practitioner)

	appointment_doc.billing_item = get_consulting_charge_item(
		appointment_doc.appointment_type, appointment_doc.practitioner
	)
	if appointment_doc.payment_mode == "Cash":
		appointment_doc.mode_of_payment = get_cash_mode_of_payment()
		if appointment_doc.billing_item:
			appointment_doc.paid_amount = get_cash_amount(
				appointment_doc.billing_item,
				mop=appointment_doc.mode_of_payment,
				company=appointment_doc.company,
				patient=appointment_doc.patient,
			)
		# Checked on validate, after free follow-ups and visit types without charges set the amount to 0.
		appointment_doc.flags.validate_cash_billing = True

	appointment_doc.insert(ignore_permissions=True)
	# Reload so an unset duration (None) becomes the stored 0; set_only_once compares them on save.
	appointment_doc.reload()
	if appointment_doc.insurance_subscription and appointment_doc.authorization_number:
		link_jubilee_benefits(appointment_doc)
		# make_next_doc creates the vital signs only on a save after insert, as the desk does.
		appointment_doc.save(ignore_permissions=True)
		appointment_doc.reload()

	return appointment_doc.as_dict()


@frappe.whitelist()
def validate_new_patient_cash_booking(practitioner, appointment_type, company):
	"""Refuses a cash booking that cannot be billed before the dialog creates a new patient.

	A new patient has no earlier visit, so only a visit type without cash charges makes the booking free.
	"""
	frappe.has_permission("Patient Appointment", "create", throw=True)
	booking = frappe._dict(
		practitioner=practitioner,
		billing_item=get_consulting_charge_item(appointment_type, practitioner),
		invoiced=cint(
			frappe.get_cached_value(
				"Appointment Type", appointment_type, "has_no_consultation_charges_for_cash"
			)
		),
		mode_of_payment=get_cash_mode_of_payment(),
	)
	if booking.billing_item and not booking.invoiced:
		booking.paid_amount = get_cash_amount(
			booking.billing_item, mop=booking.mode_of_payment, company=company
		)
	validate_cash_billing(booking)


def get_cash_mode_of_payment():
	"""The user's Cash mode of payment, else their first one."""
	mops = get_mode_of_payment()
	return next((mop for mop in mops if mop.type == "Cash"), mops[0]).mode_of_payment


@frappe.whitelist()
def update_appointment(
	appointment_id,
	practitioner,
	appointment_time,
	appointment_type,
	authorization_number=None,
	referral_no=None,
	remarks=None,
	biometric_method=None,
):
	"""Save the changed values of an open or scheduled appointment; a blank authorization no keeps the saved one."""
	appointment_doc = frappe.get_doc("Patient Appointment", appointment_id)
	appointment_doc.check_permission("write")
	validate_editable(appointment_doc)
	validate_active_practitioner(appointment_doc.practitioner)

	values = {
		"practitioner": practitioner,
		"appointment_type": appointment_type,
		"authorization_number": (authorization_number or "").strip() or None,
		"referral_no": referral_no,
		"remarks": remarks,
		"biometric_method": biometric_method,
	}
	changes = {
		fieldname: value
		for fieldname, value in values.items()
		if value is not None and value != (appointment_doc.get(fieldname) or "")
	}
	if "practitioner" in changes:
		validate_active_practitioner(practitioner)
		validate_practitioner_level(
			appointment_doc.practitioner, practitioner, appointment_doc.inpatient_record
		)
	if "authorization_number" in changes and not appointment_doc.insurance_subscription:
		frappe.throw(_("Appointment {0} is not an insurance appointment").format(appointment_doc.name))

	new_appointment_time = get_time(appointment_time)
	if get_time(appointment_doc.appointment_time) != new_appointment_time:
		validate_not_in_past(appointment_doc.appointment_date, new_appointment_time)
		changes["appointment_time"] = new_appointment_time

	# Checked against the saved appointment, before a typed authorization no is applied.
	visit_type = changes.pop("appointment_type", None)
	if not changes and not visit_type:
		return False

	change_visit_type(appointment_doc, visit_type)
	if changes:
		appointment_doc.update(changes)
		appointment_doc.save(ignore_permissions=True)
	return True


def validate_editable(appointment_doc):
	"""Closed and cancelled appointments are read only."""
	if appointment_doc.status in ("Closed", "Cancelled"):
		frappe.throw(
			_("Appointment {0} is {1} and cannot be edited").format(
				appointment_doc.name, appointment_doc.status
			)
		)


@frappe.whitelist()
def check_patient_can_book(patient):
	"""Refuses an admitted or disabled patient before the dialog creates a subscription, authorization or appointment."""
	frappe.has_permission("Patient Appointment", "create", throw=True)
	validate_patient_can_book(patient)


def validate_active_practitioner(practitioner):
	"""Appointments of a disabled practitioner are kept as records and cannot be added or changed."""
	if frappe.db.get_value("Healthcare Practitioner", practitioner, "status") == "Disabled":
		frappe.throw(
			_("Practitioner {0} is disabled, so appointments cannot be added or changed for them").format(
				practitioner
			)
		)


@frappe.whitelist()
def cancel_appointment(appointment_id):
	"""
	Cancel an existing appointment.
	"""

	appointment_doc = frappe.get_doc("Patient Appointment", appointment_id)
	appointment_doc.check_permission("write")
	if appointment_doc.status == "Cancelled":
		frappe.throw(f"Appointment {appointment_id} is already cancelled.")

	validate_cancellable(appointment_doc)
	appointment_doc.status = "Cancelled"
	appointment_doc.save(ignore_permissions=True)
	appointment_doc.reload()

	add_cancel_comment(appointment_doc.name)

	# If the appointment has an associated event, update the event status
	if appointment_doc.get("event"):
		event_doc = frappe.get_doc("Event", appointment_doc.event)
		event_doc.status = "Cancelled"
		event_doc.save(ignore_permissions=True)

	# cancel fee validity
	fee_validity = frappe.db.get_value("Fee Validity", {"patient_appointment": appointment_doc.name})
	if fee_validity:
		frappe.db.set_value("Fee Validity", fee_validity, "status", "Cancelled")

	return True


@frappe.whitelist()
def get_mode_of_payment():
	"""
	Fetch mode of payment using user id from user permission
	"""

	user = frappe.session.user
	mp = DocType("Mode of Payment")
	up = DocType("User Permission")

	mp_data = (
		frappe.qb.from_(mp)
		.inner_join(up)
		.on(up.for_value == mp.name)
		.select(mp.name.as_("mode_of_payment"), mp.type.as_("type"))
		.where(
			(up.user == user) & (up.allow == "Mode of Payment")
			# & (mp.type == "Cash")
		)
	).run(as_dict=True)

	if len(mp_data) == 0:
		frappe.throw(f"No mode of payment found for user: {user}")

	return mp_data


@frappe.whitelist()
def get_appointment_details(appointment_id):
	"""
	Fetch details of a specific appointment with related patient and insurance data.
	"""
	appointment_doc = frappe.get_doc("Patient Appointment", appointment_id)
	appointment_doc.check_permission("read")

	# Get appointment data
	appointment_data = appointment_doc.as_dict()

	# Prepare the response structure
	response_data = {
		"Patient Appointment": appointment_data,
		"Patient": {},
		"Healthcare Insurance Subscription": {},
	}

	# Get patient data if patient is linked
	if appointment_data.get("patient"):
		try:
			patient_doc = frappe.get_doc("Patient", appointment_data["patient"])
			response_data["Patient"] = patient_doc.as_dict()
		except Exception as e:
			frappe.log_error(f"Error fetching patient data: {str(e)}")

	# Get insurance subscription data if linked
	if appointment_data.get("insurance_subscription"):
		try:
			insurance_doc = frappe.get_doc(
				"Healthcare Insurance Subscription", appointment_data["insurance_subscription"]
			)
			response_data["Healthcare Insurance Subscription"] = insurance_doc.as_dict()
		except Exception as e:
			frappe.log_error(f"Error fetching insurance subscription data: {str(e)}")

	return response_data


@frappe.whitelist()
def get_user_roles():
	"""
	Fetch user roles.
	"""

	user = frappe.session.user
	roles = frappe.get_roles(user)

	if not roles:
		frappe.throw(f"No roles found for user: {user}")

	return roles


def validate_not_in_past(appointment_date, appointment_time):
	"""Reject an appointment whose date and time are before now."""
	appointment_datetime = get_datetime(f"{getdate(appointment_date)} {get_time(appointment_time)}")
	if appointment_datetime < now_datetime():
		frappe.throw(
			_("Appointment time {0} is in the past. Choose a future date and time.").format(
				frappe.bold(appointment_datetime.strftime("%Y-%m-%d %H:%M"))
			),
			title=_("Past Appointment Time"),
		)


def validate_practitioner_level(current_practitioner, new_practitioner, inpatient_record=None):
	"""
	Validate if the practitioner level is valid for the appointment.
	"""

	field_name = "inpatient_visit_charge_item" if inpatient_record else "op_consulting_charge_item"

	cur_cons_item = frappe.get_cached_value("Healthcare Practitioner", current_practitioner, field_name)
	if not cur_cons_item:
		frappe.throw(
			f"Consulting charge item for practitioner {current_practitioner} is not set. <br>Please set it on the practitioner record."
		)

	new_cons_item = frappe.get_cached_value("Healthcare Practitioner", new_practitioner, field_name)
	if not new_cons_item:
		frappe.throw(
			f"Consulting charge item for practitioner {new_practitioner} is not set. <br>Please set it on the practitioner record."
		)

	if cur_cons_item != new_cons_item:
		frappe.throw(
			title="Consulting charge item mismatch:",
			msg=f"Cannot change practitioner from {current_practitioner}: {cur_cons_item} to {new_practitioner}: {new_cons_item}.",
		)

	return True
