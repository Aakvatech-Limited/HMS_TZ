"""Insurance card checks, subscription lookup and authorization for the appointments page."""

import frappe
from frappe import _
from frappe.query_builder import Criterion, DocType

from hms_tz.jubilee.api.api import get_authorization_number, get_member_card_detials
from hms_tz.nhif.api.patient import check_card_number, check_national_id
from hms_tz.nhif.nhif_api.verification import (
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
	"national_id",
	"mobile_number",
	"company",
]
PATIENT_FIELDS = ["name", "patient_name", "sex", "dob", "mobile"]


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
def check_card(company, provider, card_no=None, national_id=None):
	"""Look the card up with the provider and match it to records already in HMS."""
	frappe.has_permission("Patient Appointment", "create", throw=True)
	card = fetch_card(company, provider, card_no, national_id)
	subscription = find_subscription(card["card_no"], card["national_id"])
	patient = subscription["patient"] if subscription else find_patient(card["card_no"], card["national_id"])
	return {
		"card": card,
		"patient": get_patient(patient) if patient else None,
		"subscription": subscription,
		"coverage_plan": suggest_coverage_plan(company, provider, card),
	}


@frappe.whitelist()
def search_subscriptions(provider, txt=""):
	"""Active subscriptions of the provider whose ID, patient, card no or mobile contains the text."""
	frappe.has_permission("Healthcare Insurance Subscription", "read", throw=True)
	his = DocType("Healthcare Insurance Subscription")
	query = active_subscriptions().where(provider_condition(his, provider)).limit(20)
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
def create_insurance_subscription(subscription_data):
	"""Insert and submit a subscription; an appointment accepts only submitted ones."""
	doc = frappe.new_doc("Healthcare Insurance Subscription")
	doc.update(subscription_data)
	doc.check_permission("create")
	doc.insert(ignore_permissions=True)
	doc.submit()
	return get_subscription(doc.name)


@frappe.whitelist()
def authorize_jubilee_appointment(appointment):
	"""Request the Jubilee authorization no for a saved appointment and store it on it."""
	doc = frappe.get_doc("Patient Appointment", appointment)
	doc.check_permission("write")
	card_no = frappe.db.get_value(
		"Healthcare Insurance Subscription", doc.insurance_subscription, "coverage_plan_card_number"
	)
	data = get_authorization_number(doc.company, card_no, doc.name, doc.insurance_subscription)
	if not data or not data.get("AuthorizationNo"):
		return None

	doc.authorization_number = data["AuthorizationNo"]
	doc.save(ignore_permissions=True)
	return doc.authorization_number


def fetch_card(company, provider, card_no, national_id):
	if provider == "NHIF":
		return fetch_nhif_card(company, card_no, national_id)
	if provider == "Jubilee":
		return fetch_jubilee_card(company, card_no)
	frappe.throw(_("Card check is only available for NHIF and Jubilee"))


def fetch_nhif_card(company, card_no, national_id):
	settings = frappe.get_cached_doc("HMS TZ Setting", company)
	if not settings.enable_nhif_api:
		frappe.throw(_("Enable NHIF API in HMS TZ Setting for {0}").format(company))
	if card_no:
		data = get_card_details_by_card_no(company, card_no, "Patient Appointment", settings_doc=settings)
	elif national_id:
		data = get_card_details_by_national_id(
			company, national_id, "Patient Appointment", settings_doc=settings
		)
	else:
		frappe.throw(_("Enter the card no or the National ID"))
	if not isinstance(data, dict):
		frappe.throw(_("NHIF did not return the card details"))

	return {
		"provider": "NHIF",
		"card_no": data.get("CardNo") or card_no or "",
		"national_id": data.get("CHNationalID") or national_id or "",
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
		"national_id": "",
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


def find_subscription(card_no, national_id):
	his = DocType("Healthcare Insurance Subscription")
	for field, value in ((his.coverage_plan_card_number, card_no), (his.national_id, national_id)):
		if not value:
			continue
		rows = active_subscriptions().where(field == value).limit(1).run(as_dict=True)
		if rows:
			return rows[0]
	return None


def find_patient(card_no, national_id):
	return (
		(card_no and check_card_number(card_no)) or (national_id and check_national_id(national_id)) or None
	)


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
