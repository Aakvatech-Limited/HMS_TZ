import json
from unittest.mock import Mock, patch

import frappe
from frappe.model.document import Document
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from hms_tz.api import appointment as appointment_api
from hms_tz.api import appointment_insurance
from hms_tz.api.provider_reply import ProviderReplyError
from hms_tz.hms_tz.doctype.patient_appointment import patient_appointment
from hms_tz.jubilee.api.api import create_jubilee_benefits
from hms_tz.nhif.api import patient_appointment as nhif_appointment
from hms_tz.nhif.nhif_api import verification
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
REFERRAL_VISIT = "_Test Insurance Referral Visit"
NHIF_CARD_TYPE = "_Test NHIF Beneficiary Card"
NIDA_CARD_TYPE = appointment_insurance.NATIONAL_ID_CARD_TYPE
HMS_TZ_SETTING = "hms_tz.hms_tz.doctype.hms_tz_setting.hms_tz_setting.HMSTZSetting"
AUTHORIZE_ARGS = {
	"appointment_type": VISIT_TYPE,
	"company": COMPANY,
	"card_no": "101",
	"national_id": "NID1",
	"fingerprint": "face-jpeg",
	"fpcode": "FACE",
	"biometric_method": "FACIAL",
	"practitioner": PRACTITIONER,
}

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
	# Sites may already have the card type; tearDown's rollback brings their row back.
	frappe.db.delete("Healthcare Card Verifier", name)
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

	def call_nhif(self, function, reply_status, reply_text, **kwargs):
		"""Calls `function` against a mocked NHIF reply; returns the ProviderReplyError payload."""
		nhif_reply = Mock(status_code=reply_status, text=reply_text)
		frappe.local.message_log = []
		with (
			patch.object(verification.requests, "request", return_value=nhif_reply),
			patch(f"{HMS_TZ_SETTING}.get_nhif_token", return_value="token"),
			patch.object(frappe.db, "commit"),
			self.assertRaises(ProviderReplyError) as raised,
		):
			function(**kwargs)
		# The page gets the report once, as the raised error.
		self.assertEqual(len(frappe.local.message_log), 1)
		return json.loads(str(raised.exception))

	def test_authorize_nhif_patient_raises_the_nhif_api_error(self):
		reply_text = '{"title": "Bad Request", "status": 400, "message": "Use a test card.", "traceId": "T1"}'
		reply = self.call_nhif(
			appointment_insurance.authorize_nhif_patient,
			400,
			reply_text,
			**{**AUTHORIZE_ARGS, "insurance_subscription": NHIF_SUBSCRIPTION},
		)

		self.assertEqual(reply["title"], "NHIF API Error")
		self.assertIn("Failed to AuthorizePatient", reply["message"])
		self.assertIn("Status Code: 400", reply["message"])
		self.assertIn("NHIF Response: <b>Use a test card.", reply["message"])

	def test_authorize_nhif_patient_raises_a_rejected_reply(self):
		reply_text = '{"authorizationStatus": "REJECTED", "remarks": "Card is inactive"}'
		reply = self.call_nhif(
			appointment_insurance.authorize_nhif_patient,
			200,
			reply_text,
			**{**AUTHORIZE_ARGS, "insurance_subscription": NHIF_SUBSCRIPTION},
		)

		self.assertEqual(reply, {"title": "REJECTED", "message": "Card is inactive"})

	def test_authorize_nhif_patient_keeps_an_authorization_no_without_accepted(self):
		pending = {"authorizationStatus": "PENDING", "authorizationNo": "A2", "remarks": "Visit NHIF office"}
		with patch.object(appointment_insurance, "authorize_patient", return_value=pending):
			result = appointment_insurance.authorize_nhif_patient(
				**{**AUTHORIZE_ARGS, "insurance_subscription": NHIF_SUBSCRIPTION}
			)

		self.assertEqual(result, pending)

	def test_check_card_raises_the_nhif_api_error(self):
		reply = self.call_nhif(
			appointment_insurance.check_card,
			404,
			'{"reasonPhrase": "Card not found"}',
			company=COMPANY,
			provider="NHIF",
			card_no="999",
			card_type=NHIF_CARD_TYPE,
		)

		self.assertEqual(reply["title"], "NHIF API Error")
		self.assertIn("Failed to Fetch card details", reply["message"])
		self.assertIn("Status Code: 404", reply["message"])
		self.assertIn("NHIF Response: <b>Card not found", reply["message"])

	def test_local_validation_is_not_a_provider_reply(self):
		with self.assertRaises(frappe.ValidationError) as raised:
			appointment_insurance.check_card(
				COMPANY_WITHOUT_API, "NHIF", card_no="101", card_type=NHIF_CARD_TYPE
			)
		self.assertNotIsInstance(raised.exception, ProviderReplyError)

	def test_authorize_nhif_patient_returns_the_authorization(self):
		accepted = {"authorizationStatus": "ACCEPTED", "authorizationNo": "A1"}
		with patch.object(appointment_insurance, "authorize_patient", return_value=accepted) as authorize:
			result = appointment_insurance.authorize_nhif_patient(
				**{**AUTHORIZE_ARGS, "insurance_subscription": NHIF_SUBSCRIPTION}
			)

		self.assertEqual(result, accepted)
		self.assertEqual(authorize.call_args.kwargs["biometric_method"], "FACIAL")

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

	def test_search_subscriptions_filters_by_provider_and_patient(self):
		names = lambda provider, patient: [  # noqa: E731
			row.name for row in appointment_insurance.search_subscriptions(provider, patient=patient)
		]

		self.assertEqual(names("NHIF", CARD_HOLDER), [NHIF_SUBSCRIPTION])
		self.assertEqual(names("Jubilee", CARD_HOLDER), [])
		self.assertEqual(names("Jubilee", JUBILEE_HOLDER), [JUBILEE_SUBSCRIPTION])
		self.assertEqual(names("NHIF", JUBILEE_HOLDER), [])
		self.assertEqual(names("Other", JUBILEE_HOLDER), [])

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

	def test_search_patients_finds_a_mobile_typed_in_local_form(self):
		frappe.db.set_value("Patient", CARD_HOLDER, "mobile", "255799887731")
		values = lambda txt: [row.value for row in appointment_insurance.search_patients(txt)]  # noqa: E731

		for txt in ("0799887731", "079988", "0799 887 731", "255799887731", "799887731"):
			self.assertEqual(values(txt), [CARD_HOLDER], txt)

	def test_international_mobile_of_local_numbers_only(self):
		self.assertEqual(appointment_insurance.get_international_mobile("0712345601"), "255712345601")
		self.assertEqual(appointment_insurance.get_international_mobile("0712-345"), "255712345")
		for txt in ("071", "255712345601", "Mohamed", "", None, "07123456789"):
			self.assertIsNone(appointment_insurance.get_international_mobile(txt), txt)

	def test_search_patients_returns_page_length_rows(self):
		for name in (CARD_HOLDER, JUBILEE_HOLDER, NID_HOLDER):
			frappe.db.set_value("Patient", name, {"status": "Active", "mobile": "_Test Page 7731"})

		self.assertEqual(len(appointment_insurance.search_patients("_Test Page 7731", page_length=2)), 2)
		self.assertEqual(len(appointment_insurance.search_patients("_Test Page 7731", page_length=3)), 3)

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
		self.assertEqual(subscription["card_type_name"], NIDA_CARD_TYPE)


def save_without_validation(doc, *args, **kwargs):
	doc.db_update()


@patch.object(Document, "save", new=save_without_validation)
class TestAuthorizeSavedAppointment(FrappeTestCase):
	def setUp(self):
		TestAppointmentInsurance.setUp(self)

	def tearDown(self):
		frappe.db.rollback()

	def insert_appointment(self, name, company=COMPANY, subscription=NHIF_SUBSCRIPTION, **values):
		insurance_company = {NHIF_SUBSCRIPTION: NHIF_COMPANY, JUBILEE_SUBSCRIPTION: JUBILEE_COMPANY}
		insert(
			"Patient Appointment",
			name,
			company=company,
			patient=CARD_HOLDER,
			practitioner=PRACTITIONER,
			appointment_type=VISIT_TYPE,
			insurance_subscription=subscription,
			insurance_company=insurance_company.get(subscription, ""),
			coverage_plan_card_number="101",
			appointment_time="10:00:00",
			**{"status": "Open", **values},
		)
		return name

	def update_with_number(self, appointment, authorization_number, **values):
		return appointment_api.update_appointment(
			appointment, PRACTITIONER, "10:00:00", VISIT_TYPE, authorization_number, **values
		)

	def test_update_saves_a_number_copied_from_the_portal_even_with_the_api_enabled(self):
		appointment = self.insert_appointment("_Test Auth Portal")

		self.assertTrue(self.update_with_number(appointment, " AUTH-9 ", referral_no="R-1", remarks="Portal"))
		self.assertEqual(
			frappe.db.get_value(
				"Patient Appointment", appointment, ["authorization_number", "referral_no", "remarks"]
			),
			("AUTH-9", "R-1", "Portal"),
		)

	def test_update_without_a_number_keeps_the_number_and_saves_the_other_values(self):
		appointment = self.insert_appointment(
			"_Test Auth Blank",
			authorization_number="A0",
			referral_no="R-0",
			remarks="Old",
			biometric_method="FINGERPRINT",
		)

		self.assertTrue(
			self.update_with_number(
				appointment, "  ", referral_no="R-1", remarks="New", biometric_method="NONE"
			)
		)
		self.assertEqual(
			frappe.db.get_value(
				"Patient Appointment",
				appointment,
				["authorization_number", "referral_no", "remarks", "biometric_method"],
			),
			("A0", "R-1", "New", "NONE"),
		)

	def test_update_corrects_a_saved_number(self):
		appointment = self.insert_appointment("_Test Auth Fix", authorization_number="A0")

		self.assertTrue(self.update_with_number(appointment, "A1"))
		self.assertEqual(
			frappe.db.get_value("Patient Appointment", appointment, "authorization_number"), "A1"
		)

	def test_update_without_changes_returns_false(self):
		appointment = self.insert_appointment("_Test Auth Same", referral_no="R-0")

		self.assertFalse(self.update_with_number(appointment, None, referral_no="R-0", remarks=""))

	def test_update_rejects_closed_cancelled_and_cash_appointments(self):
		cases = {
			"is Closed and cannot be edited": self.insert_appointment("_Test Auth Closed", status="Closed"),
			"is Cancelled and cannot be edited": self.insert_appointment(
				"_Test Auth Cancelled", status="Cancelled"
			),
			"not an insurance appointment": self.insert_appointment("_Test Auth Cash", subscription=""),
		}
		for message, appointment in cases.items():
			with self.subTest(message):
				with self.assertRaisesRegex(frappe.ValidationError, message):
					self.update_with_number(appointment, "AUTH-9")

	def test_only_open_insurance_appointments_without_a_number_can_be_authorized(self):
		cases = {
			"not an insurance appointment": self.insert_appointment("_Test Auth Cash", subscription=""),
			"already authorized": self.insert_appointment("_Test Auth Done", authorization_number="A0"),
			"is cancelled": self.insert_appointment("_Test Auth Cancelled", status="Cancelled"),
		}
		for message, appointment in cases.items():
			with self.subTest(message):
				with self.assertRaisesRegex(frappe.ValidationError, message):
					appointment_insurance.authorize_jubilee_appointment(appointment)

	def test_nhif_number_is_stored_when_the_status_is_not_accepted(self):
		appointment = self.insert_appointment("_Test Auth NHIF Pending")
		pending = {"authorizationStatus": "PENDING", "authorizationNo": "A2", "remarks": "Visit NHIF office"}
		with patch.object(appointment_insurance, "authorize_patient", return_value=pending):
			result = appointment_insurance.authorize_nhif_appointment(
				appointment, "image", "R1", "FINGERPRINT"
			)

		self.assertEqual(result["authorization_status"], "PENDING")
		self.assertEqual(
			frappe.db.get_value("Patient Appointment", appointment, "authorization_number"), "A2"
		)

	@patch.object(
		nhif_appointment, "get_consulting_charge_item", new=lambda visit_type, *args: f"Item {visit_type}"
	)
	def test_update_changes_the_visit_type_before_authorization(self):
		appointment = self.insert_appointment("_Test Visit Type Change")

		with patch.object(nhif_appointment, "publish_grid_update") as publish:
			self.assertTrue(
				appointment_api.update_appointment(appointment, PRACTITIONER, "10:00:00", REFERRAL_VISIT)
			)
		self.assertEqual(
			frappe.db.get_value("Patient Appointment", appointment, ["appointment_type", "billing_item"]),
			(REFERRAL_VISIT, f"Item {REFERRAL_VISIT}"),
		)
		publish.assert_called_once()
		self.assertTrue(
			frappe.db.exists(
				"Comment",
				{
					"reference_name": appointment,
					"comment_type": "Info",
					"content": f"Visit type changed from {VISIT_TYPE} to {REFERRAL_VISIT}",
				},
			)
		)

	@patch.object(
		nhif_appointment, "get_consulting_charge_item", new=lambda visit_type, *args: f"Item {visit_type}"
	)
	def test_changed_visit_type_passes_the_checks_of_a_later_save(self):
		doc = frappe.get_doc("Patient Appointment", self.insert_appointment("_Test Visit Type Later Save"))

		nhif_appointment.change_visit_type(doc, REFERRAL_VISIT)
		doc.load_doc_before_save()
		doc.validate_set_only_once()
		# The save's timestamp check compares these.
		self.assertEqual(frappe.db.get_value("Patient Appointment", doc.name, "modified"), doc.modified)

	def test_update_keeps_the_visit_type_after_authorization_or_invoice(self):
		authorized = self.insert_appointment("_Test Visit Type Authorized", authorization_number="A1")
		invoiced = self.insert_appointment("_Test Visit Type Invoiced", invoiced=1)

		for appointment in (authorized, invoiced):
			with self.assertRaisesRegex(
				frappe.ValidationError, "cannot change after it is authorized or invoiced"
			):
				appointment_api.update_appointment(appointment, PRACTITIONER, "10:00:00", REFERRAL_VISIT)

	@patch.object(
		nhif_appointment, "get_consulting_charge_item", new=lambda visit_type, *args: f"Item {visit_type}"
	)
	def test_nhif_authorization_uses_a_visit_type_changed_in_edit(self):
		appointment = self.insert_appointment("_Test Auth New Visit Type")
		reply = {"authorizationStatus": "ACCEPTED", "authorizationNo": "A2", "remarks": "Successful"}
		with patch.object(appointment_insurance, "authorize_patient", return_value=reply) as authorize:
			appointment_insurance.authorize_nhif_appointment(
				appointment, "", "", "NONE", remarks="Referred", appointment_type=REFERRAL_VISIT
			)

		self.assertEqual(authorize.call_args.kwargs["appointment_type"], REFERRAL_VISIT)
		self.assertEqual(
			frappe.db.get_value(
				"Patient Appointment",
				appointment,
				["appointment_type", "billing_item", "authorization_number"],
			),
			(REFERRAL_VISIT, f"Item {REFERRAL_VISIT}", "A2"),
		)

	def test_nhif_authorization_is_stored_on_the_appointment(self):
		appointment = self.insert_appointment("_Test Auth NHIF")
		reply = {
			"authorizationStatus": "ACCEPTED",
			"authorizationNo": "A1",
			"remarks": "Successful",
			"coveragePlanName": NHIF_PLAN,
			"employerName": "Employer",
			"fpCode": "R1",
			"ReferenceNo": "POC1",
			"serviceYear": "3",
		}
		with patch.object(appointment_insurance, "authorize_patient", return_value=reply) as authorize:
			result = appointment_insurance.authorize_nhif_appointment(
				appointment, "image", "R1", "fingerprint", referral_no="R-1", remarks="Walk in"
			)

		self.assertEqual(
			result,
			{"authorization_number": "A1", "authorization_status": "ACCEPTED", "remarks": "Successful"},
		)
		self.assertEqual(authorize.call_args.kwargs["ref_docname"], appointment)
		self.assertEqual(authorize.call_args.kwargs["card_no"], "101")
		self.assertEqual(
			frappe.db.get_value(
				"Patient Appointment",
				appointment,
				[
					"authorization_number",
					"poc_reference_no",
					"years_of_insurance",
					"biometric_method",
					"require_fingerprint",
					"referral_no",
				],
			),
			("A1", "POC1", 3, "FINGERPRINT", 1, "R-1"),
		)

	def test_nhif_authorization_without_biometrics_needs_remarks(self):
		appointment = self.insert_appointment("_Test Auth NHIF None")

		with (
			patch.object(appointment_insurance, "authorize_patient") as authorize,
			self.assertRaisesRegex(frappe.ValidationError, "Remarks are required"),
		):
			appointment_insurance.authorize_nhif_appointment(appointment, "", "", "NONE")
		authorize.assert_not_called()

	def test_jubilee_authorization_is_stored_on_the_appointment(self):
		frappe.db.set_value("Healthcare Insurance Subscription", JUBILEE_SUBSCRIPTION, "patient", CARD_HOLDER)
		appointment = self.insert_appointment("_Test Auth Jubilee", subscription=JUBILEE_SUBSCRIPTION)

		with patch.object(
			appointment_insurance, "get_authorization_number", return_value={"AuthorizationNo": "J1"}
		):
			self.assertEqual(appointment_insurance.authorize_jubilee_appointment(appointment), "J1")
		self.assertEqual(
			frappe.db.get_value("Patient Appointment", appointment, "authorization_number"), "J1"
		)

	def test_jubilee_patient_authorization_returns_the_number(self):
		reply = {"AuthorizationNo": "J2", "Status": "OK", "Description": "Authorized"}
		with patch.object(appointment_insurance, "get_authorization_number", return_value=reply) as authorize:
			result = appointment_insurance.authorize_jubilee_patient(COMPANY, "JUB1", JUBILEE_SUBSCRIPTION)

		self.assertEqual(result, {"authorization_number": "J2", "status": "OK", "description": "Authorized"})
		authorize.assert_called_once_with(COMPANY, "JUB1", None, JUBILEE_SUBSCRIPTION)

	def test_jubilee_patient_authorization_without_a_number_fails(self):
		with (
			patch.object(
				appointment_insurance, "get_authorization_number", return_value={"Status": "Failed"}
			),
			self.assertRaisesRegex(frappe.ValidationError, "Jubilee did not authorize the patient"),
		):
			appointment_insurance.authorize_jubilee_patient(COMPANY, "JUB1", JUBILEE_SUBSCRIPTION)

	def test_benefits_of_an_authorization_before_create_join_the_appointment(self):
		benefit = {"BenefitCode": "OUT", "BenefitName": "Outpatient", "BenefitBalance": "1000"}
		for authorization_no in ("J3", "J4"):
			create_jubilee_benefits(
				"JUB1", {"AuthorizationNo": authorization_no, "Benefits": [benefit]}, None, COMPANY
			)
		appointment = self.insert_appointment(
			"_Test Auth Jubilee Benefits", subscription=JUBILEE_SUBSCRIPTION, authorization_number="J3"
		)

		appointment_insurance.link_jubilee_benefits(frappe.get_doc("Patient Appointment", appointment))

		linked = frappe.get_all(
			"Jubilee Benefit",
			filters={"authorization_no": ("in", ["J3", "J4"])},
			fields=["authorization_no", "appointment", "patient"],
			order_by="authorization_no",
		)
		self.assertEqual(
			[tuple(row.values()) for row in linked],
			[("J3", appointment, CARD_HOLDER), ("J4", None, None)],
		)
