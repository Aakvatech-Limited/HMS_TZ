"""Insurance card checks, subscription lookup and authorization for the appointments page."""

import re

import frappe
import requests
from frappe import _
from frappe.query_builder import Criterion, DocType
from frappe.utils import cint

from hms_tz.api.provider_reply import provider_call
from hms_tz.jubilee.api.api import get_authorization_number, get_member_card_detials
from hms_tz.nhif.api.patient import check_card_number, set_card_type
from hms_tz.nhif.api.patient_appointment import change_visit_type, validate_patient_can_book
from hms_tz.nhif.nhif_api.verification import (
	authorize_patient,
	get_card_details_by_card_no,
	get_card_details_by_national_id,
)

SUBSCRIPTION_FIELDS = [
	"name",
	"patient",
	"patient_name",
	"insurance_company",
	"healthcare_insurance_coverage_plan",
	"coverage_plan_name",
	"coverage_plan_card_number",
	"mobile_number",
	"company",
	"gender",
	"card_type_name",
]
PATIENT_FIELDS = ["name", "patient_name", "sex", "dob", "mobile"]
NATIONAL_ID_CARD_TYPE = "NIDA ID"

# Rows one patient search may return.
MAX_PATIENT_SEARCH_ROWS = 100


@frappe.whitelist()
def get_insurance_api_settings(company):
	"""Which provider APIs HMS TZ Setting turns on for the company."""
	settings = (
		frappe.db.get_value(
			"HMS TZ Setting", company, ["enable_nhif_api", "enable_jubilee_api"], as_dict=True
		)
		or {}
	)
	return {
		"enable_nhif_api": bool(settings.get("enable_nhif_api")),
		"enable_jubilee_api": bool(settings.get("enable_jubilee_api")),
	}


@frappe.whitelist()
def check_card(company, provider, card_no=None, card_type=None):
	"""Look the card up with the provider and match it to records already in HMS."""
	frappe.has_permission("Patient Appointment", "create", throw=True)
	with provider_call(provider):
		card = fetch_card(company, provider, card_no, card_type)
	card_numbers = card_numbers_of(card)
	subscription = find_subscription(*card_numbers)
	patient = subscription["patient"] if subscription else find_patient(*card_numbers)
	return {
		"card": card,
		"patient": get_patient(patient) if patient else None,
		"subscription": subscription,
		"coverage_plan": suggest_coverage_plan(company, provider, card),
	}


@frappe.whitelist()
def search_subscriptions(provider="", txt="", patient=""):
	"""Active subscriptions, of the provider and patient when given, matching ID, patient, card no or mobile."""
	frappe.has_permission("Healthcare Insurance Subscription", "read", throw=True)
	his = DocType("Healthcare Insurance Subscription")
	query = active_subscriptions().limit(20)
	if provider:
		query = query.where(provider_condition(his, provider))
	if patient:
		query = query.where(his.patient == patient)
	if txt:
		pattern = f"%{txt}%"
		query = query.where(
			Criterion.any(
				[
					his.name.like(pattern),
					his.patient_name.like(pattern),
					his.coverage_plan_card_number.like(pattern),
					his.mobile_number.like(pattern),
				]
			)
		)
	return query.orderby(his.patient_name).run(as_dict=True)


@frappe.whitelist()
def get_subscription(name):
	frappe.has_permission("Healthcare Insurance Subscription", "read", doc=name, throw=True)
	return frappe.db.get_value("Healthcare Insurance Subscription", name, SUBSCRIPTION_FIELDS, as_dict=True)


@frappe.whitelist()
def get_patient(name):
	frappe.has_permission("Patient", "read", doc=name, throw=True)
	return frappe.db.get_value("Patient", name, PATIENT_FIELDS, as_dict=True)


@frappe.whitelist()
def search_patients(txt="", page_length=20):
	"""Active patients whose ID, name, mobile or card no contains the text, with details to tell them apart.

	The search page asks for one row more than it shows, to tell the user that more patients match.
	"""
	pattern = f"%{txt}%"
	or_filters = [
		["name", "like", pattern],
		["patient_name", "like", pattern],
		["mobile", "like", pattern],
		["card_no", "like", pattern],
		["insurance_card_detail", "like", pattern],
	]
	international_mobile = get_international_mobile(txt)
	if international_mobile:
		or_filters.append(["mobile", "like", f"%{international_mobile}%"])
	return frappe.get_list(
		"Patient",
		fields=["name as value", "patient_name", "sex", "mobile", "card_no"],
		filters={"status": "Active"},
		or_filters=or_filters,
		order_by="modified desc",
		limit=min(cint(page_length) or 20, MAX_PATIENT_SEARCH_ROWS),
	)


def get_international_mobile(txt):
	"""The 255 form of a local mobile typed as 07..., also part of one; mobiles are stored as 255XXXXXXXXX."""
	digits = re.sub(r"[\s-]", "", txt or "")
	if re.fullmatch(r"0\d{3,9}", digits):
		return f"255{digits[1:]}"
	return None


@frappe.whitelist()
def create_insurance_subscription(subscription_data):
	"""Insert and submit a subscription; an appointment accepts only submitted ones."""
	card_type = subscription_data.pop("card_type", None)
	doc = frappe.new_doc("Healthcare Insurance Subscription")
	doc.update(subscription_data)
	if card_type:
		set_card_type(doc, card_type)
	doc.check_permission("create")
	doc.insert(ignore_permissions=True)
	doc.submit()
	return get_subscription(doc.name)


@frappe.whitelist()
def authorize_jubilee_appointment(appointment, appointment_type=None):
	"""Request the Jubilee authorization no for a saved appointment and store it on it, with a visit type changed in Edit."""
	doc = get_appointment_to_authorize(appointment)
	change_visit_type(doc, appointment_type)
	validate_patient_can_book(doc.patient)
	card_no = frappe.db.get_value(
		"Healthcare Insurance Subscription", doc.insurance_subscription, "coverage_plan_card_number"
	)
	with provider_call("Jubilee"):
		data = get_authorization_number(doc.company, card_no, doc.name, doc.insurance_subscription)
	if not data or not data.get("AuthorizationNo"):
		return None

	doc.authorization_number = data["AuthorizationNo"]
	doc.save(ignore_permissions=True)
	return doc.authorization_number


@frappe.whitelist()
def authorize_jubilee_patient(company, card_no, insurance_subscription):
	"""Jubilee authorization for the appointments page, before the appointment exists."""
	frappe.has_permission("Patient Appointment", "create", throw=True)
	validate_subscription_patient_can_book(insurance_subscription)
	with provider_call("Jubilee"):
		data = get_authorization_number(company, card_no, None, insurance_subscription)
		if not data or not data.get("AuthorizationNo"):
			frappe.throw(_("Jubilee did not authorize the patient"))
	return {
		"authorization_number": data["AuthorizationNo"],
		"status": data.get("Status"),
		"description": data.get("Description"),
	}


def validate_subscription_patient_can_book(insurance_subscription):
	"""Local checks that would refuse the appointment run before the provider is asked for an authorization."""
	validate_patient_can_book(
		frappe.db.get_value("Healthcare Insurance Subscription", insurance_subscription, "patient")
	)


def link_jubilee_benefits(appointment):
	"""Benefits Jubilee returned for the authorization no before the appointment existed now belong to it."""
	benefit = DocType("Jubilee Benefit")
	(
		frappe.qb.update(benefit)
		.set(benefit.appointment, appointment.name)
		.set(benefit.patient, appointment.patient)
		.where(benefit.authorization_no == appointment.authorization_number)
		.where(benefit.appointment.isnull() | (benefit.appointment == ""))
		.run()
	)


@frappe.whitelist()
def authorize_nhif_patient(
	insurance_subscription,
	appointment_type,
	company,
	card_no,
	fingerprint,
	fpcode,
	biometric_method,
	practitioner,
	referral_no="",
	remarks="",
	ref_docname=None,
):
	"""NHIF authorization for the appointments page; a reply without an authorization no raises NHIF's reply."""
	frappe.has_permission("Patient Appointment", "create", throw=True)
	validate_subscription_patient_can_book(insurance_subscription)
	try:
		with provider_call("NHIF"):
			data = authorize_patient(
				insurance_subscription=insurance_subscription,
				appointment_type=appointment_type,
				company=company,
				card_no=card_no,
				# NHIF authorizes by card no and card type; FEA5-69 drops this parameter.
				national_id="",
				fingerprint=fingerprint,
				fpcode=fpcode,
				biometric_method=biometric_method,
				practitioner=practitioner,
				referral_no=referral_no,
				remarks=remarks,
				ref_docname=ref_docname,
			)
			# NHIF may give an authorization no without ACCEPTED and ask the patient to visit its office.
			if not isinstance(data, dict) or not data.get("authorizationNo"):
				frappe.throw(_("NHIF did not authorize the patient"))
	except requests.exceptions.Timeout:
		# NHIF may still have authorized the patient, so a blind retry could authorize twice.
		frappe.throw(
			_(
				"NHIF did not reply within a minute. NHIF may still have authorized the patient: check the NHIF portal before you try again, and enter the authorization no if there is one."
			),
			title=_("NHIF did not reply"),
		)
	return data


@frappe.whitelist()
def authorize_nhif_appointment(
	appointment, fingerprint, fpcode, biometric_method, referral_no="", remarks="", appointment_type=None
):
	"""NHIF authorization of a saved appointment; stores the reply on it as the desk Get Authorization Number does.

	A visit type changed in Edit is applied first, so NHIF authorizes the new one.
	"""
	doc = get_appointment_to_authorize(appointment)
	change_visit_type(doc, appointment_type)
	method = biometric_method.upper()
	if method == "NONE" and not remarks:
		frappe.throw(_("Remarks are required when the patient is not verified by biometrics"))

	data = authorize_nhif_patient(
		insurance_subscription=doc.insurance_subscription,
		appointment_type=doc.appointment_type,
		company=doc.company,
		card_no=doc.coverage_plan_card_number or "",
		fingerprint=fingerprint,
		fpcode=fpcode,
		biometric_method=method,
		practitioner=doc.practitioner,
		referral_no=referral_no,
		remarks=remarks,
		ref_docname=doc.name,
	)
	doc.update(
		{
			"authorization_number": data["authorizationNo"],
			"coverage_plan_name": data.get("coveragePlanName"),
			"nhif_employer_name": data.get("employerName"),
			"fpcode": data.get("fpCode"),
			"poc_reference_no": data.get("ReferenceNo"),
			"years_of_insurance": cint(data.get("serviceYear")),
			"biometric_method": method,
			"require_fingerprint": cint(method == "FINGERPRINT"),
			"require_facial_recognation": cint(method == "FACIAL"),
			"referral_no": referral_no,
			"remarks": remarks,
		}
	)
	doc.save(ignore_permissions=True)
	return {
		"authorization_number": doc.authorization_number,
		"authorization_status": data.get("authorizationStatus"),
		"remarks": data.get("remarks"),
	}


def get_appointment_to_authorize(appointment):
	"""The appointment, if the user may write it and it still needs an authorization no."""
	doc = frappe.get_doc("Patient Appointment", appointment)
	doc.check_permission("write")
	validate_can_authorize(doc)
	return doc


def validate_can_authorize(doc):
	"""Only an insurance appointment that is not cancelled and has no authorization no yet."""
	if doc.status == "Cancelled":
		frappe.throw(_("Appointment {0} is cancelled").format(doc.name))
	if not doc.insurance_subscription:
		frappe.throw(_("Appointment {0} is not an insurance appointment").format(doc.name))
	if doc.authorization_number:
		frappe.throw(_("Appointment {0} is already authorized").format(doc.name))


def fetch_card(company, provider, card_no, card_type):
	if provider == "NHIF":
		return fetch_nhif_card(company, card_no, card_type)
	if provider == "Jubilee":
		return fetch_jubilee_card(company, card_no)
	frappe.throw(_("Card check is only available for NHIF and Jubilee"))


def fetch_nhif_card(company, card_no, card_type):
	"""A NIDA card type looks the number up as a National ID, any other type as a card no.

	The typed number is the card no for either type. A NIDA lookup also gives the member's own NHIF card no.
	"""
	settings = frappe.get_cached_doc("HMS TZ Setting", company)
	if not settings.enable_nhif_api:
		frappe.throw(_("Enable NHIF API in HMS TZ Setting for {0}").format(company))
	if not card_type:
		frappe.throw(_("Select the card type"))
	if not card_no:
		frappe.throw(_("Enter the card no"))

	is_national_id = card_type == NATIONAL_ID_CARD_TYPE
	lookup = get_card_details_by_national_id if is_national_id else get_card_details_by_card_no
	data = lookup(company, card_no, "Patient Appointment", settings_doc=settings)
	if not isinstance(data, dict):
		frappe.throw(_("NHIF did not return the card details"))

	return {
		"provider": "NHIF",
		"card_no": card_no,
		"nhif_card_no": data.get("CardNo") or "",
		"first_name": data.get("FirstName") or "",
		"middle_name": data.get("MiddleName") or "",
		"last_name": data.get("LastName") or "",
		"full_name": data.get("FullName") or "",
		"sex": data.get("Gender") or "",
		"dob": (data.get("DateOfBirth") or "")[:10],
		"mobile": "",
		"membership_no": data.get("MembershipNo") or "",
		"product_code": data.get("ProductCode") or "",
		"scheme_id": data.get("SchemeID") or "",
		"scheme_name": data.get("SchemeName") or "",
		"employer_name": data.get("EmployerName") or "",
		"picture": data.get("MemberPicture") or "",
	}


def fetch_jubilee_card(company, card_no):
	if not frappe.db.get_value("HMS TZ Setting", company, "enable_jubilee_api"):
		frappe.throw(_("Enable Jubilee API in HMS TZ Setting for {0}").format(company))
	if not card_no:
		frappe.throw(_("Enter the Jubilee member no"))
	data = get_member_card_detials(card_no, "Jubilee")
	if not isinstance(data, dict):
		frappe.throw(_("Jubilee did not return the card details"))

	info = data.get("Description") or {}
	return {
		"provider": "Jubilee",
		"card_no": card_no,
		"first_name": info.get("FirstName") or "",
		"middle_name": info.get("MiddleName") or "",
		"last_name": info.get("LastName") or "",
		"full_name": info.get("MemberName") or "",
		"sex": info.get("Gender") or "",
		"dob": (info.get("Dob") or "")[:10],
		"mobile": info.get("Phone") or "",
		"membership_no": info.get("PrincipleMemberNo") or "",
		"product_code": "",
		"scheme_id": "",
		"scheme_name": "",
		"employer_name": info.get("Company") or "",
		"picture": "",
	}


def active_subscriptions():
	"""Submitted, active subscriptions of any company: one card serves the patient at every branch."""
	his = DocType("Healthcare Insurance Subscription")
	return (
		frappe.qb.from_(his)
		.select(*[getattr(his, field) for field in SUBSCRIPTION_FIELDS])
		.where((his.docstatus == 1) & (his.is_active == 1))
	)


def provider_condition(his, provider):
	if provider in ("NHIF", "Jubilee"):
		return his.insurance_company.like(f"%{provider}%")
	return his.insurance_company.not_like("%NHIF%") & his.insurance_company.not_like("%Jubilee%")


def card_numbers_of(card):
	"""The card numbers that identify this member: the typed one and, after a NIDA lookup, the NHIF card no.

	NHIF's CHNationalID is the card holder's NIDA number, shared by every dependent, so it never matches a patient.
	"""
	return list(dict.fromkeys(number for number in (card["card_no"], card.get("nhif_card_no")) if number))


def find_subscription(*card_numbers):
	"""An active subscription with one of the card numbers, in their order."""
	his = DocType("Healthcare Insurance Subscription")
	for card_no in card_numbers:
		rows = (
			active_subscriptions().where(his.coverage_plan_card_number == card_no).limit(1).run(as_dict=True)
		)
		if rows:
			return rows[0]
	return None


def find_patient(*card_numbers):
	"""The patient with one of the card numbers, in their order."""
	for card_no in card_numbers:
		patient = check_card_number(card_no)
		if patient:
			return patient
	return None


def suggest_coverage_plan(company, provider, card):
	"""The one active plan for the card's scheme (NHIF) or for the provider (Jubilee)."""
	filters = {"is_active": 1, "company": company}
	if provider == "NHIF":
		if not card.get("scheme_id"):
			return None
		filters["nhif_scheme_id"] = card["scheme_id"]
	else:
		filters["insurance_company"] = ["like", "%Jubilee%"]
	plans = frappe.get_all(
		"Healthcare Insurance Coverage Plan",
		filters=filters,
		fields=["name", "insurance_company"],
		limit=2,
	)
	return plans[0] if len(plans) == 1 else None
