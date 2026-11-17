from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from hms_tz.api import appointment as appointment_api
from hms_tz.api import appointment_insurance
from hms_tz.hms_tz.doctype.patient_appointment import patient_appointment
from hms_tz.nhif.api import patient_appointment as nhif_appointment
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
CONSULTATION_ITEM = "_Test Insurance Consultation"
PRACTITIONER = "_Test Insurance Doctor"
VISIT_TYPE = "_Test Insurance Visit"
NHIF_CARD_TYPE = "_Test NHIF Beneficiary Card"
NIDA_CARD_TYPE = appointment_insurance.NATIONAL_ID_CARD_TYPE

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


def insert_card_type(name, card_type_id):
	insert(
		"Healthcare Card Verifier",
		name,
		card_type_name=name,
		card_type_id=card_type_id,
		verifier_id="NHIF",
		verifier_name="NHIF",
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
		insert_card_type(NHIF_CARD_TYPE, "NHIFCard")
		insert_card_type(NIDA_CARD_TYPE, "NationalID")
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
			result = appointment_insurance.check_card(
				COMPANY, "NHIF", card_no="101", card_type=NHIF_CARD_TYPE
			)

		self.assertEqual(result["patient"]["name"], CARD_HOLDER)
		self.assertEqual(result["subscription"]["name"], NHIF_SUBSCRIPTION)
		self.assertEqual(result["coverage_plan"]["name"], NHIF_PLAN)
		self.assertEqual(result["card"]["first_name"], "Card")
		self.assertEqual(result["card"]["dob"], "1990-01-01")
		self.assertEqual(result["card"]["scheme_id"], "SCH1")

	def test_check_card_with_nida_card_type_looks_up_the_national_id(self):
		card = {**NHIF_CARD, "CardNo": "303", "CHNationalID": "NID2", "SchemeID": "SCH9"}
		with (
			patch.object(appointment_insurance, "get_card_details_by_card_no") as by_card_no,
			patch.object(
				appointment_insurance, "get_card_details_by_national_id", return_value=card
			) as by_national_id,
		):
			result = appointment_insurance.check_card(
				COMPANY, "NHIF", card_no="NID2", card_type=NIDA_CARD_TYPE
			)

		by_card_no.assert_not_called()
		self.assertEqual(by_national_id.call_args.args[1], "NID2")

		self.assertEqual(result["patient"]["name"], NID_HOLDER)
		self.assertIsNone(result["subscription"])
		self.assertIsNone(result["coverage_plan"])
		self.assertEqual(result["card"]["card_no"], "303")

	def test_check_card_unknown_card_has_no_patient(self):
		card = {**NHIF_CARD, "CardNo": "404", "CHNationalID": "NID4"}
		with patch.object(appointment_insurance, "get_card_details_by_card_no", return_value=card):
			result = appointment_insurance.check_card(
				COMPANY, "NHIF", card_no="404", card_type=NHIF_CARD_TYPE
			)

		self.assertIsNone(result["patient"])
		self.assertIsNone(result["subscription"])

	def test_check_card_needs_the_provider_api_enabled(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Enable NHIF API"):
			appointment_insurance.check_card(
				COMPANY_WITHOUT_API, "NHIF", card_no="101", card_type=NHIF_CARD_TYPE
			)
		with self.assertRaisesRegex(frappe.ValidationError, "Enable Jubilee API"):
			appointment_insurance.check_card(COMPANY, "Jubilee", card_no="JUB1")
		with self.assertRaisesRegex(frappe.ValidationError, "only available"):
			appointment_insurance.check_card(COMPANY, "Other", card_no="1")

	def test_check_card_needs_the_nhif_card_type_and_number(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Select the card type"):
			appointment_insurance.check_card(COMPANY, "NHIF", card_no="101")
		with self.assertRaisesRegex(frappe.ValidationError, "Enter the card no"):
			appointment_insurance.check_card(COMPANY, "NHIF", card_type=NHIF_CARD_TYPE)

	def test_check_card_rejects_a_failed_lookup(self):
		with (
			patch.object(appointment_insurance, "get_card_details_by_card_no", return_value="Error"),
			self.assertRaisesRegex(frappe.ValidationError, "did not return"),
		):
			appointment_insurance.check_card(COMPANY, "NHIF", card_no="101", card_type=NHIF_CARD_TYPE)

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

	def test_search_subscriptions_filters_by_patient_without_provider(self):
		rows = appointment_insurance.search_subscriptions(patient=CARD_HOLDER)

		self.assertEqual([row.name for row in rows], [NHIF_SUBSCRIPTION])
		self.assertEqual(
			rows[0].gender,
			frappe.db.get_value("Healthcare Insurance Subscription", NHIF_SUBSCRIPTION, "gender"),
		)
		self.assertIn(
			JUBILEE_SUBSCRIPTION,
			[row.name for row in appointment_insurance.search_subscriptions(txt=JUBILEE_SUBSCRIPTION)],
		)

	def test_search_visit_types_hides_disabled_ones(self):
		insert("Appointment Type", VISIT_TYPE, appointment_type=VISIT_TYPE)
		insert("Appointment Type", f"{VISIT_TYPE} Old", appointment_type=f"{VISIT_TYPE} Old", disabled=1)

		rows = appointment_api.search_visit_types("Insurance Visit")

		self.assertEqual([row.value for row in rows], [VISIT_TYPE])

	def test_search_patients_matches_id_name_mobile_and_card_no(self):
		frappe.db.set_value("Patient", CARD_HOLDER, {"mobile": "_Test Mobile 7731", "card_no": "_TCARD7731"})
		frappe.db.set_value("Patient", JUBILEE_HOLDER, "insurance_card_detail", "_TJUB7731, ")
		frappe.db.set_value("Patient", NID_HOLDER, "status", "Disabled")
		values = lambda txt: [row.value for row in appointment_insurance.search_patients(txt)]  # noqa: E731

		for txt in (CARD_HOLDER, "Mobile 7731", "_TCARD7731"):
			self.assertEqual(values(txt), [CARD_HOLDER])
		self.assertEqual(values("_TJUB7731"), [JUBILEE_HOLDER])
		self.assertEqual(values(NID_HOLDER), [])

		row = appointment_insurance.search_patients("_TCARD7731")[0]
		self.assertEqual(
			(row.patient_name, row.sex, row.mobile, row.card_no),
			("Card Holder", "Male", "_Test Mobile 7731", "_TCARD7731"),
		)

	@patch.object(patient_appointment, "manage_fee_validity", new=lambda appointment: None)
	@patch.object(nhif_appointment, "get_insurance_amount", new=lambda *args, **kwargs: (0, 0))
	@patch.object(
		appointment_api, "get_consulting_charge_item", new=lambda *args, **kwargs: CONSULTATION_ITEM
	)
	def test_create_authorized_appointment_without_duration(self):
		"""The dialog sends no duration; the save after insert must not see it as changed."""
		insert("Item", CONSULTATION_ITEM, item_code=CONSULTATION_ITEM, item_name=CONSULTATION_ITEM)
		insert("Healthcare Practitioner", PRACTITIONER, first_name="Test", practitioner_name="Test Doctor")
		insert("Appointment Type", VISIT_TYPE, appointment_type=VISIT_TYPE)
		frappe.db.set_value("Patient", CARD_HOLDER, "customer", "_Test Customer")

		appointment = appointment_api.create_appointment(
			{
				"company": COMPANY,
				"practitioner": PRACTITIONER,
				"appointment_date": add_days(nowdate(), 1),
				"appointment_time": "10:00:00",
				"appointment_type": VISIT_TYPE,
				"patient": CARD_HOLDER,
				"payment_mode": "Insurance",
				"insurance_subscription": NHIF_SUBSCRIPTION,
				"authorization_number": "AUTH-1",
			}
		)

		self.assertEqual(appointment["authorization_number"], "AUTH-1")
		self.assertTrue(appointment["ref_vital_signs"])

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

	def test_create_insurance_subscription_copies_the_card_type(self):
		subscription = appointment_insurance.create_insurance_subscription(
			{
				"patient": NID_HOLDER,
				"insurance_company": NHIF_COMPANY,
				"healthcare_insurance_coverage_plan": NHIF_PLAN,
				"coverage_plan_card_number": "303",
				"company": COMPANY,
				"card_type": NIDA_CARD_TYPE,
			}
		)

		self.assertEqual(
			frappe.db.get_value(
				"Healthcare Insurance Subscription",
				subscription["name"],
				["verifier_id", "card_type_id", "card_type_name"],
			),
			("NHIF", "NationalID", NIDA_CARD_TYPE),
		)
