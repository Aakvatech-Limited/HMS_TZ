from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.api import appointment_insurance
from hms_tz.tests.utils import insert

COMPANY = "_Test Insurance Clinic"
COMPANY_WITHOUT_API = "_Test Insurance Clinic No API"
# Subscriptions belong to another branch: a card must work at every company of the same site.
SUBSCRIPTION_COMPANY = "_Test Insurance HQ Hospital"
NHIF_COMPANY = "_Test NHIF Insurance"
JUBILEE_COMPANY = "_Test Jubilee Insurance"
NHIF_PLAN = "_Test NHIF Plan"
JUBILEE_PLAN = "_Test Jubilee Plan"
CARD_HOLDER = "_Test Card Holder"
NID_HOLDER = "_Test NID Holder"
JUBILEE_HOLDER = "_Test Jubilee Holder"
NHIF_SUBSCRIPTION = "_Test NHIF HIS"
JUBILEE_SUBSCRIPTION = "_Test Jubilee HIS"

NHIF_CARD = {
	"CardNo": "101",
	"CHNationalID": "NID1",
	"FirstName": "Card",
	"MiddleName": "",
	"LastName": "Holder",
	"FullName": "Card Holder",
	"Gender": "Male",
	"DateOfBirth": "1990-01-01T00:00:00",
	"MembershipNo": "M1",
	"ProductCode": "P1",
	"SchemeID": "SCH1",
	"SchemeName": "Standard",
	"EmployerName": "Employer",
	"MemberPicture": "",
}


def insert_company(name, abbr, enable_nhif_api):
	insert("Company", name, company_name=name, abbr=abbr, default_currency="TZS")
	insert(
		"HMS TZ Setting",
		name,
		company=name,
		facility_code="F1",
		enable_nhif_api=enable_nhif_api,
		enable_jubilee_api=0,
	)


def insert_plan(name, insurance_company, scheme_id=None):
	insert("Healthcare Insurance Company", insurance_company, insurance_company_name=insurance_company)
	insert(
		"Healthcare Insurance Coverage Plan",
		name,
		coverage_plan_name=name,
		insurance_company=insurance_company,
		is_active=1,
		nhif_scheme_id=scheme_id,
		company=COMPANY,
	)


def insert_patient(name, **values):
	insert(
		"Patient",
		name,
		first_name=name.split()[1],
		last_name=name.split()[2],
		patient_name=name.replace("_Test ", ""),
		sex="Male",
		dob="1990-01-01",
		status="Active",
		**values,
	)


def insert_subscription(name, patient, insurance_company, plan, card_no, national_id=""):
	insert(
		"Healthcare Insurance Subscription",
		name,
		docstatus=1,
		is_active=1,
		patient=patient,
		patient_name=frappe.db.get_value("Patient", patient, "patient_name"),
		insurance_company=insurance_company,
		healthcare_insurance_coverage_plan=plan,
		coverage_plan_card_number=card_no,
		national_id=national_id,
		mobile_number="255712000001",
		company=SUBSCRIPTION_COMPANY,
	)


class TestAppointmentInsurance(FrappeTestCase):
	def setUp(self):
		insert_company(COMPANY, "_TIC", enable_nhif_api=1)
		insert_company(COMPANY_WITHOUT_API, "_TIN", enable_nhif_api=0)
		insert_plan(NHIF_PLAN, NHIF_COMPANY, scheme_id="SCH1")
		insert_plan(JUBILEE_PLAN, JUBILEE_COMPANY)
		insert_patient(CARD_HOLDER, insurance_card_detail="101, ", national_id="NID1")
		insert_patient(NID_HOLDER, national_id="NID2")
		insert_patient(JUBILEE_HOLDER, insurance_card_detail="JUB1, ")
		insert_subscription(NHIF_SUBSCRIPTION, CARD_HOLDER, NHIF_COMPANY, NHIF_PLAN, "101", "NID1")
		insert_subscription(JUBILEE_SUBSCRIPTION, JUBILEE_HOLDER, JUBILEE_COMPANY, JUBILEE_PLAN, "JUB1")

	def tearDown(self):
		frappe.db.rollback()

	def test_api_settings_follow_hms_tz_setting(self):
		self.assertEqual(
			appointment_insurance.get_insurance_api_settings(COMPANY),
			{"enable_nhif_api": True, "enable_jubilee_api": False},
		)
		self.assertEqual(
			appointment_insurance.get_insurance_api_settings("_Test Missing Clinic"),
			{"enable_nhif_api": False, "enable_jubilee_api": False},
		)

	def test_check_card_matches_subscription_and_patient_by_card_no(self):
		with patch.object(appointment_insurance, "get_card_details_by_card_no", return_value=NHIF_CARD):
			result = appointment_insurance.check_card(COMPANY, "NHIF", card_no="101")

		self.assertEqual(result["patient"]["name"], CARD_HOLDER)
		self.assertEqual(result["subscription"]["name"], NHIF_SUBSCRIPTION)
		self.assertEqual(result["coverage_plan"]["name"], NHIF_PLAN)
		self.assertEqual(result["card"]["first_name"], "Card")
		self.assertEqual(result["card"]["dob"], "1990-01-01")
		self.assertEqual(result["card"]["scheme_id"], "SCH1")

	def test_check_card_by_national_id_finds_patient_without_subscription(self):
		card = {**NHIF_CARD, "CardNo": "303", "CHNationalID": "NID2", "SchemeID": "SCH9"}
		with patch.object(appointment_insurance, "get_card_details_by_national_id", return_value=card):
			result = appointment_insurance.check_card(COMPANY, "NHIF", national_id="NID2")

		self.assertEqual(result["patient"]["name"], NID_HOLDER)
		self.assertIsNone(result["subscription"])
		self.assertIsNone(result["coverage_plan"])
		self.assertEqual(result["card"]["card_no"], "303")

	def test_check_card_unknown_card_has_no_patient(self):
		card = {**NHIF_CARD, "CardNo": "404", "CHNationalID": "NID4"}
		with patch.object(appointment_insurance, "get_card_details_by_card_no", return_value=card):
			result = appointment_insurance.check_card(COMPANY, "NHIF", card_no="404")

		self.assertIsNone(result["patient"])
		self.assertIsNone(result["subscription"])

	def test_check_card_needs_the_provider_api_enabled(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Enable NHIF API"):
			appointment_insurance.check_card(COMPANY_WITHOUT_API, "NHIF", card_no="101")
		with self.assertRaisesRegex(frappe.ValidationError, "Enable Jubilee API"):
			appointment_insurance.check_card(COMPANY, "Jubilee", card_no="JUB1")
		with self.assertRaisesRegex(frappe.ValidationError, "only available"):
			appointment_insurance.check_card(COMPANY, "Other", card_no="1")

	def test_check_card_rejects_a_failed_lookup(self):
		with (
			patch.object(appointment_insurance, "get_card_details_by_card_no", return_value="Error"),
			self.assertRaisesRegex(frappe.ValidationError, "did not return"),
		):
			appointment_insurance.check_card(COMPANY, "NHIF", card_no="101")

	def test_search_subscriptions_filters_by_provider_and_text(self):
		names = lambda rows: [row.name for row in rows]  # noqa: E731

		self.assertEqual(
			names(appointment_insurance.search_subscriptions("NHIF", "101")), [NHIF_SUBSCRIPTION]
		)
		self.assertEqual(
			names(appointment_insurance.search_subscriptions("NHIF", "Holder")), [NHIF_SUBSCRIPTION]
		)
		self.assertEqual(
			names(appointment_insurance.search_subscriptions("Jubilee", "JUB1")), [JUBILEE_SUBSCRIPTION]
		)
		self.assertEqual(names(appointment_insurance.search_subscriptions("NHIF", "JUB1")), [])
		self.assertNotIn(NHIF_SUBSCRIPTION, names(appointment_insurance.search_subscriptions("Other")))

	def test_create_insurance_subscription_submits_it(self):
		subscription = appointment_insurance.create_insurance_subscription(
			{
				"patient": NID_HOLDER,
				"insurance_company": NHIF_COMPANY,
				"healthcare_insurance_coverage_plan": NHIF_PLAN,
				"coverage_plan_card_number": "303",
				"national_id": "NID2",
				"company": COMPANY,
			}
		)

		self.assertEqual(subscription["patient"], NID_HOLDER)
		self.assertEqual(
			frappe.db.get_value("Healthcare Insurance Subscription", subscription["name"], "docstatus"), 1
		)
		self.assertEqual(appointment_insurance.find_subscription("303", "")["name"], subscription["name"])
