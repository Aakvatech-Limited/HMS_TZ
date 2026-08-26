import frappe
from frappe.query_builder import DocType
from frappe.utils import get_time

from hms_tz.nhif.api.patient_appointment import get_cash_amount, get_consulting_charge_item


@frappe.whitelist()
def create_appointment(appointment_data):
	"""
	Create a new appointment with the provided data.
	"""

	# frappe.throw(str(appointment_data))
	appointment_doc = frappe.new_doc("Patient Appointment")
	appointment_doc.update(appointment_data)

	billing_item = get_consulting_charge_item(
		appointment_data.get("appointment_type"),
		appointment_data.get("practitioner"),
	)
	appointment_doc.billing_item = billing_item

	if appointment_data.get("payment_mode") == "Cash":
		mops = get_mode_of_payment()

		cash_mop = next((mop for mop in mops if mop.type == "Cash"), None)
		mode_of_payment = cash_mop.mode_of_payment if cash_mop else mops[0].mode_of_payment
		appointment_doc.mode_of_payment = mode_of_payment

		appointment_doc.paid_amount = get_cash_amount(
			billing_item,
			mop=mode_of_payment,
			company=appointment_data.get("company"),
			patient=appointment_data.get("patient"),
		)

	appointment_doc.save(ignore_permissions=True)
	appointment_doc.reload()

	return appointment_doc.as_dict()


@frappe.whitelist()
def update_appointment(appointment_id, practitioner, appointment_time, appointment_type):
	"""
	Update an existing appointment with the provided data.
	"""

	has_changed = False
	appointment_doc = frappe.get_cached_doc("Patient Appointment", appointment_id)
	if appointment_doc.practitioner != practitioner:
		validate_practitioner_level(
			appointment_doc.practitioner, practitioner, appointment_doc.inpatient_record
		)

		has_changed = True
		appointment_doc.practitioner = practitioner

	new_appointment_time = get_time(appointment_time)
	if get_time(appointment_doc.appointment_time) != new_appointment_time:
		has_changed = True
		appointment_doc.appointment_time = new_appointment_time

	if appointment_doc.appointment_type != appointment_type:
		has_changed = True
		appointment_doc.appointment_type = appointment_type

	if has_changed:
		appointment_doc.save(ignore_permissions=True)
		appointment_doc.reload()

		return True

	return False


@frappe.whitelist()
def cancel_appointment(appointment_id):
	"""
	Cancel an existing appointment.
	"""

	appointment_doc = frappe.get_cached_doc("Patient Appointment", appointment_id)
	if appointment_doc.status == "Cancelled":
		frappe.throw(f"Appointment {appointment_id} is already cancelled.")

	appointment_doc.status = "Cancelled"
	appointment_doc.save(ignore_permissions=True)
	appointment_doc.reload()

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
	if not appointment_doc:
		frappe.throw(f"Appointment {appointment_id} not found.")

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
