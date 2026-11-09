# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif import utils
from hms_tz.nhif.nhif_api import approval

COMPANY = "_Test US Company"
APPOINTMENT = "_Test US Visit"
CARD_NO = "110900292954"
DIALYSIS = "_Test US Dialysis"
DRUG = "_Test US Erythropoietin"
CODES = {DIALYSIS: "6234", DRUG: "11291"}
UNISSUED = [
	{
		"CardNo": CARD_NO,
		"ItemCode": "11291",
		"ItemName": "Erythropoietin",
		"QuantityRequested": 4,
		"QuantityIssued": 3,
		"QuantityRemains": 1,
		"ApprovalReferenceNo": "580625628084",
		"ApprovalStatus": "Approved",
	},
	{
		"CardNo": CARD_NO,
		"ItemCode": "6234",
		"ItemName": "Haemodialysis per session (Maximum 12 sessions per month)",
		"QuantityRequested": 12,
		"QuantityIssued": 2,
		"QuantityRemains": 10,
		"ApprovalReferenceNo": "901626062560",
		"ApprovalStatus": "Approved",
	},
]


def insert(doctype, name, **values):
	doc = frappe.new_doc(doctype)
	doc.update({"name": name, **values})
	doc.db_insert()
	return doc


def insert_procedure(name, **values):
	defaults = {
		"company": COMPANY,
		"procedure_template": DIALYSIS,
		"appointment": APPOINTMENT,
		"is_restricted": 1,
	}
	insert("Clinical Procedure", name, **{**defaults, **values})


def nhif_response(status_code=200, data=None):
	return MagicMock(status_code=status_code, json=MagicMock(return_value=data), text=str(data))


class TestNHIFUnissuedServices(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		insert("Company", COMPANY, company_name=COMPANY, abbr="_TUS", default_currency="TZS")
		if not frappe.db.exists("Healthcare Insurance Company", "NHIF"):
			insert("Healthcare Insurance Company", "NHIF", insurance_company_name="NHIF")
		insert(
			"Patient Appointment",
			APPOINTMENT,
			company=COMPANY,
			insurance_company="NHIF",
			coverage_plan_card_number=CARD_NO,
		)
		insert("Patient Appointment", "_Test US Cash Visit", company=COMPANY)
		insert("Clinical Procedure Template", DIALYSIS, template=DIALYSIS, item="_Test US Dialysis Item")
		insert("Medication", DRUG)
		insert(
			"Item Customer Detail",
			"_Test US Dialysis Code",
			parent="_Test US Dialysis Item",
			parenttype="Item",
			parentfield="customer_items",
			customer_name="_Test US NHIF Customer",
			ref_code="6234",
		)

	def setUp(self):
		frappe.db.savepoint("unissued_services_test")
		self.addCleanup(frappe.db.rollback, save_point="unissued_services_test")
		settings = MagicMock(
			enable_nhif_api=1,
			nhifservice_url="https://nhif.test",
			nhif_customer_name="_Test US NHIF Customer",
			get_nhif_token=MagicMock(return_value="t"),
		)
		get_cached_doc = frappe.get_cached_doc
		patches = [
			patch.object(
				approval.frappe,
				"get_cached_doc",
				side_effect=lambda doctype, *args: settings
				if doctype == "HMS TZ Setting"
				else get_cached_doc(doctype, *args),
			),
			patch.object(approval, "add_log"),
			patch.object(
				utils,
				"get_item_refcode",
				side_effect=lambda doctype, name, *args: CODES[name],
			),
			patch.object(approval.requests, "request", return_value=nhif_response(data=UNISSUED)),
		]
		for patcher in patches:
			patcher.start()
			self.addCleanup(patcher.stop)

	def test_line_of_the_service_template_can_be_used(self):
		insert_procedure("_Test US Procedure")

		lines = approval.get_unissued_services("Clinical Procedure", "_Test US Procedure")

		self.assertIn(f"GetUnIssuedServices?cardNo={CARD_NO}", approval.requests.request.call_args.args[1])
		self.assertEqual(lines[0]["targets"], [])
		self.assertEqual(
			lines[1]["targets"],
			[{"doctype": "Clinical Procedure", "name": "_Test US Procedure", "label": DIALYSIS}],
		)
		self.assertEqual(lines[1]["ApprovalReferenceNo"], "901626062560")

	def test_service_with_approval_number_or_submitted_has_no_target(self):
		insert_procedure("_Test US Numbered", approval_number="TYPED-1")
		insert_procedure("_Test US Submitted", docstatus=1)

		for name in ("_Test US Numbered", "_Test US Submitted"):
			lines = approval.get_unissued_services("Clinical Procedure", name)
			self.assertEqual([line["targets"] for line in lines], [[], []])

	def test_delivery_note_lists_each_matching_item(self):
		insert("Drug Prescription", "_Test US Drug Row", drug_code=DRUG)
		insert("Delivery Note", "_Test US DN", company=COMPANY, hms_tz_appointment_no=APPOINTMENT)
		for idx, approval_number in ((1, None), (2, "TYPED-2")):
			insert(
				"Delivery Note Item",
				f"_Test US DN Item {idx}",
				parent="_Test US DN",
				parenttype="Delivery Note",
				parentfield="items",
				idx=idx,
				item_name="Erythropoietin 4000IU",
				is_restricted=1,
				approval_number=approval_number,
				reference_doctype="Drug Prescription",
				reference_name="_Test US Drug Row",
			)

		lines = approval.get_unissued_services("Delivery Note", "_Test US DN")

		self.assertEqual(
			lines[0]["targets"],
			[
				{
					"doctype": "Delivery Note Item",
					"name": "_Test US DN Item 1",
					"label": "Row 1: Erythropoietin 4000IU",
				}
			],
		)

	def test_visit_without_nhif_is_refused(self):
		insert_procedure("_Test US Cash", appointment="_Test US Cash Visit")

		self.assertRaises(
			frappe.ValidationError, approval.get_unissued_services, "Clinical Procedure", "_Test US Cash"
		)
		approval.requests.request.assert_not_called()

	def test_other_doctype_is_refused(self):
		self.assertRaises(frappe.ValidationError, approval.get_unissued_services, "User", "Administrator")

	def test_nhif_error_is_logged_and_shown(self):
		insert_procedure("_Test US Procedure")
		approval.requests.request.return_value = nhif_response(500, "Server error")

		self.assertRaises(
			frappe.ValidationError, approval.get_unissued_services, "Clinical Procedure", "_Test US Procedure"
		)
		self.assertEqual(approval.add_log.call_args.kwargs["status_code"], 500)

	def test_line_shows_our_service_name(self):
		insert_procedure("_Test US Procedure")

		lines = approval.get_unissued_services("Clinical Procedure", "_Test US Procedure")

		self.assertEqual([line["service_name"] for line in lines], ["Erythropoietin", DIALYSIS])

	def test_not_serviced_service_has_no_target(self):
		states = {
			"_Test US Not Serviced": "Not Serviced",
			"_Test US Submitted NS": "Submitted but Not Serviced",
		}
		for name, state in states.items():
			insert_procedure(name, workflow_state=state)

			lines = approval.get_unissued_services("Clinical Procedure", name)

			self.assertEqual([line["targets"] for line in lines], [[], []])

	def test_lines_are_logged_once_for_the_issue_to_count(self):
		insert_procedure("_Test US Procedure")

		for _call in range(2):
			approval.get_unissued_services("Clinical Procedure", "_Test US Procedure")

		logs = frappe.get_all(
			"Insurance Approval Log",
			filters={"card_no": CARD_NO},
			fields=["reference_no", "service_name", "qty_approved", "qty_issued"],
			order_by="reference_no",
		)
		self.assertEqual(
			[tuple(log.values()) for log in logs],
			[("580625628084", None, 4, 3), ("901626062560", DIALYSIS, 12, 2)],
		)
