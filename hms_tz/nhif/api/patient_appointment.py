# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt


import json

import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from frappe.utils import cint, date_diff, nowdate, nowtime
from healthcare.healthcare.doctype.healthcare_settings.healthcare_settings import get_receivable_account

from hms_tz.hms_tz.doctype.patient.patient import create_customer
from hms_tz.hms_tz.doctype.patient_appointment.patient_appointment import get_appointment_item
from hms_tz.nhif.api.healthcare_utils import get_discount_percent, get_item_rate, get_mop_amount


def before_insert(doc, method):
	validate_disabled_patient(doc.patient, doc.patient_name)

	if doc.inpatient_record:
		frappe.throw(
			_(
				"You cannot create an appointment for a patient already admitted.<br>First <b>discharge the patient</b> and then create the appointment."
			)
		)

	patient_doc = frappe.get_cached_doc("Patient", doc.patient)
	if not patient_doc.customer:
		create_customer(patient_doc)


def validate_disabled_patient(patient, patient_name):
	if frappe.get_cached_value("Patient", patient, "status") == "Disabled":
		frappe.throw(_(f"The patient <b>{patient}-{patient_name}</b> is disabled. Cannot proceed further."))


@frappe.whitelist()
def get_insurance_amount(
	insurance_subscription,
	billing_item,
	company,
	insurance_company,
	has_no_consultation_charges=False,
):
	# SHM Rock: 202
	if cint(has_no_consultation_charges) == 1:
		return 0, 0

	item_price = get_item_rate(billing_item, company, insurance_subscription, insurance_company)

	discount_percent = 0
	if insurance_company and "NHIF" not in insurance_company:
		discount_percent = get_discount_percent(insurance_company)

		amount = item_price - (item_price * (discount_percent / 100))

		return amount, discount_percent

	return item_price, discount_percent


@frappe.whitelist()
def get_cash_amount(
	billing_item,
	mop=None,
	company=None,
	patient=None,
	has_no_consultation_charges=False,
):
	if cint(has_no_consultation_charges) == 1:
		return 0

	return get_mop_amount(billing_item, mop, company, patient)


@frappe.whitelist()
def invoice_appointment(name, mops=[]):
	"""create sales invoice for appointment

	args:
	    name (str): The name of the appointment.
	    mops (list): List of mode of payments.
	"""

	appointment_doc = frappe.get_cached_doc("Patient Appointment", name)
	if appointment_doc.billing_item:
		if appointment_doc.mode_of_payment:
			appointment_doc.paid_amount = get_cash_amount(
				appointment_doc.billing_item,
				appointment_doc.mode_of_payment,
				appointment_doc.company,
				appointment_doc.patient,
				appointment_doc.has_no_consultation_charges,
			)
		else:
			# TODO to be removed since on creating sales invoice we don't need
			# insurance amount
			appointment_doc.paid_amount, discount_percent = get_insurance_amount(
				appointment_doc.insurance_subscription,
				appointment_doc.billing_item,
				appointment_doc.company,
				appointment_doc.insurance_company,
				appointment_doc.has_no_consultation_charges,
			)
			if discount_percent > 0:
				appointment_doc.hms_tz_is_discount_applied = 1

		appointment_doc.save()
		appointment_doc.reload()
		appointment_doc.clear_cache()

	set_follow_up(appointment_doc, "invoice_appointment")
	automate_invoicing = frappe.db.get_single_value("Healthcare Settings", "automate_appointment_invoicing")

	if (
		not automate_invoicing
		and not appointment_doc.insurance_subscription
		and appointment_doc.mode_of_payment
		and not appointment_doc.invoiced
		and not appointment_doc.ref_sales_invoice
		and not appointment_doc.follow_up
	):
		sales_invoice = frappe.new_doc("Sales Invoice")
		sales_invoice.patient = appointment_doc.patient
		sales_invoice.customer = frappe.get_cached_value("Patient", appointment_doc.patient, "customer")
		sales_invoice.appointment = appointment_doc.name
		sales_invoice.set_posting_time = 1
		sales_invoice.posting_date = appointment_doc.appointment_date
		sales_invoice.due_date = appointment_doc.appointment_date
		sales_invoice.company = appointment_doc.company
		sales_invoice.debit_to = get_receivable_account(appointment_doc.company)
		sales_invoice.healthcare_service_unit = appointment_doc.service_unit
		sales_invoice.healthcare_practitioner = appointment_doc.practitioner

		item = sales_invoice.append("items", {})
		item = get_appointment_item(appointment_doc, item)
		item.rate = appointment_doc.paid_amount
		item.amount = appointment_doc.paid_amount

		# Add payments if payment details are supplied else proceed to create
		# invoice as Unpaid
		if appointment_doc.mode_of_payment and appointment_doc.paid_amount:
			sales_invoice.is_pos = 1

			if len(mops) > 0:
				for mop in mops:
					if mop.get("amount", 0) > 0:
						new_row = {"mode_of_payment": mop.get("mode_of_payment"), "amount": mop.get("amount")}

						if mop.get("payment_reference"):
							new_row["payment_reference"] = mop.get("payment_reference")

						sales_invoice.append("payments", new_row)

			else:
				payment = sales_invoice.append("payments", {})
				payment.mode_of_payment = appointment_doc.mode_of_payment
				payment.amount = appointment_doc.paid_amount

		sales_invoice.set_taxes()
		sales_invoice.set_missing_values(for_validate=True)
		sales_invoice.flags.ignore_mandatory = True
		sales_invoice.save(ignore_permissions=True)
		sales_invoice.calculate_taxes_and_totals()
		sales_invoice.submit()
		frappe.msgprint(_(f"Sales Invoice {sales_invoice.name} created"))

		appointment_doc.ref_sales_invoice = sales_invoice.name
		appointment_doc.invoiced = 1

		if len(mops) > 0 and appointment_doc.mode_of_payment != mops[0].get("mode_of_payment"):
			appointment_doc.mode_of_payment = mops[0].get("mode_of_payment")

		appointment_doc.db_update()

		appointment_doc.reload()
		appointment_doc.clear_cache()
		make_next_doc(appointment_doc, "validate", from_hook=False)

		# If there are multiple modes of payment, return the appointment details
		if len(mops) > 0:
			return appointment_doc.as_dict()

		return "true"


@frappe.whitelist()
def get_consulting_charge_item(
	appointment_type,
	practitioner,
	inpatient_record=None,
	insurance_company=None,
	insurance_subscription=None,
	apply_fasttrack_charge=False,
):
	charge_item = ""
	app_type_details = get_visit_type_details(appointment_type)

	field_name = "inpatient_visit_charge_item" if inpatient_record else "op_consulting_charge_item"
	cons_item = frappe.get_cached_value("Healthcare Practitioner", practitioner, field_name)

	charge_item = cons_item

	if insurance_company and "NHIF" in insurance_company:
		if validate_schemes_for_fasttrack_and_followups(
			insurance_subscription,
			appointment_type,
		):
			if "Assistant Medical Officer" in cons_item:
				charge_item = app_type_details.get("assistant_md_followup_item")
			elif "General Practitioner" in cons_item:
				charge_item = app_type_details.get("gp_followup_item")
			elif "Super Specialist" in cons_item:
				charge_item = app_type_details.get("super_specialist_followup_item")
			elif "Specialist" in cons_item:
				charge_item = app_type_details.get("specialist_followup_item")

		elif validate_schemes_for_fasttrack_and_followups(
			insurance_subscription,
			appointment_type,
			apply_fasttrack_charge=apply_fasttrack_charge,
		):
			if "Assistant Medical Officer" in cons_item:
				charge_item = app_type_details.get("assistant_md_fasttrack_item")
			elif "General Practitioner" in cons_item:
				charge_item = app_type_details.get("gp_fasttrack_item")
			elif "Super Specialist" in cons_item:
				charge_item = app_type_details.get("super_specialist_fasttrack_item")
			elif "Specialist" in cons_item:
				charge_item = app_type_details.get("specialist_fasttrack_item")

	return charge_item


@frappe.whitelist()
def create_vital(appointment):
	appointment_doc = frappe.get_cached_doc("Patient Appointment", appointment)
	make_vital(appointment_doc, "patient_appointment")
	appointment_doc.save()
	appointment_doc.reload()


def make_vital(appointment_doc, method):
	if appointment_doc.insurance_subscription and not appointment_doc.authorization_number:
		frappe.msgprint(
			_(
				"Authorization number not set to proceed to create vitals for this appointment. Please get the authorization number first and then try again."
			),
			alert=True,
		)
		return
	if appointment_doc.insurance_subscription and appointment_doc.billing_item:
		appointment_doc.paid_amount, discount_percent = get_insurance_amount(
			appointment_doc.insurance_subscription,
			appointment_doc.billing_item,
			appointment_doc.company,
			appointment_doc.insurance_company,
			appointment_doc.has_no_consultation_charges,
		)
		if discount_percent > 0:
			appointment_doc.hms_tz_is_discount_applied = 1
			frappe.msgprint(
				f"Discount of {frappe.bold(discount_percent)} is applied to this Patient: {frappe.bold(appointment_doc.patient)}",
				alert=True,
			)

	validate_has_no_consultation(appointment_doc, method)

	if (not appointment_doc.ref_vital_signs) and (
		appointment_doc.invoiced
		or (appointment_doc.insurance_subscription and appointment_doc.authorization_number)
		or method == "patient_appointment"
	):
		vital_doc = frappe.get_doc(
			dict(
				doctype="Vital Signs",
				patient=appointment_doc.patient,
				appointment=appointment_doc.name,
				company=appointment_doc.company,
			)
		)
		vital_doc.flags.ignore_permissions = True
		vital_doc.flags.ignore_mandatory = True
		vital_doc.save()
		appointment_doc.ref_vital_signs = vital_doc.name
		appointment_doc.db_update()
		frappe.msgprint(_(f"Vital Signs {vital_doc.name} created"))


def make_encounter(doc, method):
	if doc.is_new():
		return

	_date = ""
	if doc.doctype == "Vital Signs":
		if not doc.appointment or doc.inpatient_record:
			return
		if frappe.get_cached_value("Patient Appointment", doc.appointment, "status") == "Cancelled":
			frappe.throw("<b>Appointment is already cancelled</b>")
		source_name = doc.appointment
		_date = doc.signs_date

		# ignore if called from nurse record and clinical procedure's vital sign creation
		if doc.flags.get("ignore_create_encounter"):
			return

	elif doc.doctype == "Patient Appointment":
		if (
			(not doc.authorization_number and not doc.mode_of_payment)
			or doc.ref_patient_encounter
			or doc.status == "Cancelled"
		):
			return

		if doc.insurance_subscription and doc.billing_item and doc.paid_amount <= 0:
			doc.paid_amount, discount_percent = get_insurance_amount(
				doc.insurance_subscription,
				doc.billing_item,
				doc.company,
				doc.insurance_company,
				doc.has_no_consultation_charges,
			)
			if discount_percent > 0:
				doc.hms_tz_is_discount_applied = 1

		source_name = doc.name
		_date = doc.appointment_date

	target_doc = None
	encounter_doc = get_mapped_doc(
		"Patient Appointment",
		source_name,
		{
			"Patient Appointment": {
				"doctype": "Patient Encounter",
				"field_map": [
					["appointment", "name"],
					["patient", "patient"],
					["practitioner", "practitioner"],
					["medical_department", "department"],
					["patient_sex", "patient_sex"],
					["invoiced", "invoiced"],
					["company", "company"],
					["appointment_type", "appointment_type"],
				],
			}
		},
		target_doc,
		ignore_permissions=True,
	)
	encounter_doc.encounter_date = _date
	encounter_doc.encounter_time = nowtime()
	encounter_doc.encounter_category = "Appointment"
	encounter_doc.poc_reference_no = ""

	encounter_doc.save(ignore_permissions=True)
	frappe.msgprint(_(f"Patient Encounter {encounter_doc.name} created"))

	if doc.doctype == "Patient Appointment":
		doc.ref_patient_encounter = encounter_doc.name
		doc.db_update()

		if doc.healthcare_package_order:
			return encounter_doc.name


def update_insurance_subscription(insurance_subscription, data):
	subscription_doc = frappe.get_cached_doc("Healthcare Insurance Subscription", insurance_subscription)

	if subscription_doc.hms_tz_scheme_id == data["schemeID"]:
		return data

	filters = {
		"nhif_scheme_id": data["schemeID"],
		"is_active": 1,
	}

	if subscription_doc.company:
		filters["company"] = subscription_doc.company

	plan_list = frappe.db.get_list(
		"Healthcare Insurance Coverage Plan",
		filters=filters,
		fields=["name", "insurance_company", "coverage_plan_name"],
	)

	plan = plan_list[0] if len(plan_list) == 1 else None

	if plan:
		data["coveragePlanName"] = plan.name
		subscription_doc.insurance_company = plan.insurance_company
		subscription_doc.healthcare_insurance_coverage_plan = plan.name
		subscription_doc.coverage_plan_name = plan.coverage_plan_name

	subscription_doc.hms_tz_scheme_id = data.get("schemeID")
	subscription_doc.hms_tz_scheme_name = data.get("schemeName")

	subscription_doc.save(ignore_permissions=True)

	return data


@frappe.whitelist()
def send_vfd(invoice_name):
	if "vfd_tz" not in frappe.get_installed_apps():
		frappe.msgprint(_("VFD App Not installed"), alert=True)
		msg = {"enqueue": False}
		return msg
	else:
		from vfd_tz.vfd_tz.api.sales_invoice import enqueue_posting_vfd_invoice

		enqueue_posting_vfd_invoice(invoice_name)
		pos_profile_name = frappe.get_cached_value("Sales Invoice", invoice_name, "pos_profile")
		pos_profile = frappe.get_cached_doc("POS Profile", pos_profile_name)
		msg = {"enqueue": True, "pos_rofile": pos_profile}
		return msg


@frappe.whitelist()
def get_previous_appointment(patient, filters=None):
	the_filters = {"patient": patient, "follow_up": 0, "healthcare_package_order": ""}
	if filters:
		# when the function is called from frontend
		if isinstance(filters, str):
			filters = json.loads(filters)
		the_filters.update(filters)
	appointments = frappe.get_all(
		"Patient Appointment",
		filters=the_filters,
		fields=["appointment_date", "practitioner_name", "name"],
		order_by="appointment_date desc",
	)
	if len(appointments):
		return appointments[0]


def set_follow_up(appointment_doc, method):
	if appointment_doc.healthcare_package_order:
		return

	filters = {
		"name": ["!=", appointment_doc.name],
		"department": appointment_doc.department,
		"status": ["in", ["Open", "Closed"]],
	}
	if appointment_doc.insurance_subscription:
		filters["insurance_subscription"] = appointment_doc.insurance_subscription
	else:
		filters["mode_of_payment"] = ["!=", ""]
		filters["invoiced"] = 1

	appointment = get_previous_appointment(appointment_doc.patient, filters)
	if appointment and appointment_doc.appointment_date:
		diff = date_diff(appointment_doc.appointment_date, appointment.appointment_date)
		if appointment_doc.mode_of_payment:
			valid_days = cint(
				frappe.get_cached_value("Healthcare Settings", "Healthcare Settings", "valid_days")
			)
		else:
			valid_days = cint(
				frappe.get_cached_value(
					"Healthcare Insurance Coverage Plan",
					{"coverage_plan_name": appointment_doc.coverage_plan_name},
					"no_of_days_for_follow_up",
				)
			)
			if valid_days == 0:
				valid_days = cint(
					frappe.get_cached_value(
						"Healthcare Insurance Company",
						appointment_doc.insurance_company,
						"no_of_days_for_follow_up",
					)
				)
		if diff <= valid_days:
			appointment_doc.follow_up = 1
			if (
				appointment_doc.follow_up
				and appointment_doc.insurance_subscription
				and not appointment_doc.authorization_number
			):
				return
			appointment_doc.invoiced = 1
			appointment_doc.paid_amount = 0
			frappe.msgprint(
				_(
					"Previous appointment found valid for free follow-up.<br>Skipping invoice for this appointment!"
				),
				alert=True,
			)
		else:
			appointment_doc.follow_up = 0
			# frappe.msgprint(_("This appointment requires to be paid for!"), alert=True)


def make_next_doc(doc, method, from_hook=True):
	validate_disabled_patient(doc.patient, doc.patient_name)
	validate_insurance_subscription(doc)
	check_multiple_appointments(doc)
	if doc.is_new():
		validate_has_no_consultation(doc, method)
		return

	if doc.insurance_subscription:
		is_active, his_patient, coverage_plan = frappe.get_cached_value(
			"Healthcare Insurance Subscription",
			doc.insurance_subscription,
			["is_active", "patient", "healthcare_insurance_coverage_plan"],
		)
		if not is_active:
			frappe.throw(
				_(
					"The Insurance Subscription is NOT ACTIVE. Please select the correct Insurance Subscription."
				)
			)

		if doc.patient != his_patient:
			frappe.throw(
				_(
					"Insurance Subscription belongs to another patient. Please select the correct Insurance Subscription."
				)
			)
		if "NHIF" not in doc.insurance_company and not doc.daily_limit:
			doc.daily_limit = frappe.get_cached_value(
				"Healthcare Insurance Coverage Plan",
				coverage_plan,
				"daily_limit",
			)

	if not doc.billing_item and doc.authorization_number:
		doc.billing_item = get_consulting_charge_item(
			doc.appointment_type,
			doc.practitioner,
			inpatient_record=doc.inpatient_record,
			insurance_company=doc.insurance_company,
			insurance_subscription=doc.insurance_subscription,
			apply_fasttrack_charge=doc.apply_fasttrack_charge,
		)
		if not doc.billing_item:
			frappe.throw(
				_(
					f"Billing item was not set from {doc.practitioner} for appointment type {doc.appointment_type}."
				)
			)
		else:
			frappe.msgprint(
				_(
					f"Billing item was set from {doc.practitioner} for appointment type {doc.appointment_type}."
				)
			)
	if from_hook:
		validate_has_no_consultation(doc, method)

	if not doc.patient_age:
		doc.patient_age = calculate_patient_age(doc.patient)
	# fix: followup appointments still require authorization number
	if doc.follow_up and doc.insurance_subscription and not doc.authorization_number:
		return
	# do not create vital sign or encounter if appointment is already cancelled
	if doc.status == "Cancelled":
		return

	# do not create vital sign or encounter if appointment is already invoiced
	if doc.mode_of_payment and not doc.invoiced:
		return

	if frappe.get_cached_value("Healthcare Practitioner", doc.practitioner, "bypass_vitals"):
		make_encounter(doc, method)
	else:
		make_vital(doc, method)


@frappe.whitelist()
def validate_insurance_company(insurance_company: str) -> str:
	if frappe.get_cached_value("Healthcare Insurance Company", insurance_company, "disabled"):
		frappe.msgprint(
			_(
				f"<b>Insurance Company: <strong>{insurance_company}</strong> is disabled, Please choose different insurance subscription</b>"
			)
		)
		return True
	return False


@frappe.whitelist()
def validate_insurance_subscription(doc):
	if not doc.insurance_subscription:
		return

	if (
		frappe.get_cached_value(
			"Healthcare Insurance Subscription",
			doc.insurance_subscription,
			"docstatus",
		)
		== 0
	):
		url = frappe.utils.get_link_to_form("Healthcare Insurance Subscription", doc.insurance_subscription)
		frappe.throw(
			_(
				f"Insurance Subscription: <strong>{doc.insurance_subscription}</strong> is on Draft<br>\
                Click here: <strong>{url}</strong> to submit Insurance Subscription"
			)
		)


def calculate_patient_age(patient):
	dob = frappe.get_cached_value("Patient", patient, "dob")
	if not dob:
		frappe.msgprint(
			"<h4 style='background-color: LightCoral'>Please update date of birth for this patient</h4>"
		)
		return None
	diff = date_diff(nowdate(), dob)
	years = diff // 365
	months = (diff - (years * 365)) // 30
	return f"{years} Year(s) {months} Month(s)"


def check_multiple_appointments(doc):
	if doc.healthcare_package_order:
		return

	if (
		doc.coverage_plan_card_number
		and "NHIF" in doc.insurance_company
		and doc.appointment_type in ["Outpatient Visit", "Normal Visit"]
		and doc.department not in ["Eye", "Optometrist", "Physiotherapy"]
	):
		appointments = frappe.get_list(
			"Patient Appointment",
			filters={
				"patient": doc.patient,
				"coverage_plan_card_number": doc.coverage_plan_card_number,
				"appointment_date": frappe.utils.nowdate(),
				"status": ["!=", "Cancelled"],
				"name": ["!=", doc.name],
			},
			fields=["name", "department", "practitioner"],
		)

		if len(appointments) > 0:
			msg = f"Patient already has an appointment: <b>{appointments[0].name}</b> for Practitioner: <b>{appointments[0].practitioner}</b>. \
                <br>It is adviced to have only one appointment per day."
			frappe.msgprint(msg)
			frappe.msgprint(
				f"Patient already has an appointment for <b>{appointments[0].practitioner}</b>",
				alert=True,
			)


def validate_has_no_consultation(doc, method):
	set_follow_up(doc, method)

	# SHM Rock: 202
	if doc.appointment_type:
		# Helpdesk: https://support.aakvatech.com/helpdesk/tickets/239
		# NHIF introduce follow up item and its price, therefore not need to set has not consultation charges for NHIF patient
		# 2024-07-19

		if not (
			doc.insurance_company
			and "NHIF" in doc.insurance_company
			and "follow" in doc.appointment_type.lower()
			and validate_schemes_for_fasttrack_and_followups(doc.insurance_subscription, doc.appointment_type)
		):
			if doc.mode_of_payment:
				doc.has_no_consultation_charges = frappe.get_cached_value(
					"Appointment Type",
					doc.appointment_type,
					"has_no_consultation_charges_for_cash",
				)
			elif doc.insurance_subscription:
				doc.has_no_consultation_charges = frappe.get_cached_value(
					"Appointment Type",
					doc.appointment_type,
					"has_no_consultation_charges_for_insurance",
				)
			if doc.has_no_consultation_charges:
				if doc.paid_amount and doc.paid_amount > 0:
					doc.paid_amount = 0

				if not doc.invoiced:
					doc.invoiced = 1

				frappe.msgprint(
					_(f"This appointment type: <b>{doc.appointment_type}</b> has no consultation charges."),
					alert=True,
				)


@frappe.whitelist()
def validate_schemes_for_fasttrack_and_followups(
	insurance_subscription,
	appointment_type,
	apply_fasttrack_charge=False,
):
	plan_name = frappe.get_cached_value(
		"Healthcare Insurance Subscription",
		insurance_subscription,
		["healthcare_insurance_coverage_plan"],
	)

	type_info = get_visit_type_details(appointment_type)

	plan_info = frappe.get_cached_value(
		"Healthcare Insurance Coverage Plan",
		plan_name,
		["nhif_scheme_id", "has_followup_charges", "has_fasttrack_charges"],
		as_dict=True,
	)

	if not plan_info.nhif_scheme_id:
		return False

	if (
		"follow" in appointment_type.lower()
		and plan_info.has_followup_charges
		and type_info.get("has_followup_charges")
		and not apply_fasttrack_charge
	):
		return True

	elif (
		apply_fasttrack_charge and plan_info.has_fasttrack_charges and type_info.get("has_fasttrack_charges")
	):
		return True

	else:
		return False


@frappe.whitelist()
def get_visit_type_details(appointment_type):
	type_doc = frappe.get_cached_doc("Appointment Type", appointment_type)

	return type_doc.as_dict()
