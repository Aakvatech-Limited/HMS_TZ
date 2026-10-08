# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.model.base_document import BaseDocument
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from hms_tz.nhif.nhif_api import pre_approval

COMPANY = "_Test PA Company"
INSURANCE_COMPANY = "NHIF"
PATIENT = "_Test PA Patient"
PRACTITIONER = "_Test PA Practitioner"
INPATIENT_RECORD = "_Test PA IP"
ENCOUNTER = "_Test PA PE"
SERVICE_UNIT_TYPE = "_Test PA Bed Type"
SERVICE_UNIT = "_Test PA Bed"
BED_CODE = "BED01"
BED_RATE = 50000
OPEN_BED_AMOUNT = 45000


def insert(doctype, name, **values):
	doc = frappe.new_doc(doctype)
	doc.update({"name": name, **values})
	doc.db_insert()


def insert_occupancy(name, **values):
	insert(
		"Inpatient Occupancy",
		name,
		parent=INPATIENT_RECORD,
		parenttype="Inpatient Record",
		parentfield="inpatient_occupancies",
		service_unit=SERVICE_UNIT,
		**values,
	)


def get_occupancy(name):
	return frappe.db.get_value(
		"Inpatient Occupancy",
		name,
		["preapproval_status", "preapproval_no", "rejection_details", "preapproval_cancel_remarks"],
		as_dict=True,
	)


def nhif_response(body):
	return MagicMock(status_code=200, text=json.dumps(body))


def bed_service(effective_date, end_date, unit_price):
	return {
		"itemCode": BED_CODE,
		"usage": "",
		"effectiveDate": effective_date,
		"endDate": end_date,
		"quantityRequested": 1,
		"unitPrice": unit_price,
		"remarks": "",
	}


def make_settings():
	return MagicMock(
		facility_code="F001",
		nhifservice_url="https://nhif.test",
		get_nhif_token=MagicMock(return_value="token"),
	)


class TestNHIFPreApprovalBeds(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		insert("Healthcare Service Unit Type", SERVICE_UNIT_TYPE, item="_Test PA Bed Item")
		insert("Healthcare Service Unit", SERVICE_UNIT, service_unit_type=SERVICE_UNIT_TYPE)
		insert("Patient", PATIENT, first_name="Test", last_name="Patient", dob="1990-01-01", sex="Male")
		insert("Healthcare Practitioner", PRACTITIONER, tz_mct_code="MCT1", mobile_phone="0700000000")
		insert("Inpatient Record", INPATIENT_RECORD, patient=PATIENT, company=COMPANY)
		insert(
			"Patient Encounter",
			ENCOUNTER,
			patient=PATIENT,
			practitioner=PRACTITIONER,
			company=COMPANY,
			insurance_company=INSURANCE_COMPANY,
			inpatient_record=INPATIENT_RECORD,
			examination_detail="<p>Admitted</p>",
		)
		today = nowdate()
		yesterday = add_days(today, -1)
		insert_occupancy(
			"_Test PA Approved Bed", idx=1, check_in=f"{add_days(today, -2)} 10:00:00", preapproval_no="OLD-1"
		)
		insert_occupancy(
			"_Test PA Yesterday Bed", idx=2, check_in=f"{yesterday} 00:00:00", check_out=f"{today} 00:00:00"
		)
		insert_occupancy(
			"_Test PA Transfer Bed", idx=3, check_in=f"{today} 00:00:00", check_out=f"{today} 10:00:00"
		)
		insert_occupancy("_Test PA Today Bed", idx=4, check_in=f"{today} 10:00:00", amount=OPEN_BED_AMOUNT)

	def setUp(self):
		frappe.db.savepoint("pre_approval_test")
		self.addCleanup(frappe.db.rollback, save_point="pre_approval_test")
		for mocked in [
			patch.object(pre_approval, "get_item_refcode", return_value=BED_CODE),
			patch.object(pre_approval, "get_item_rate", return_value=BED_RATE),
			patch.object(pre_approval, "add_log"),
		]:
			mocked.start()
			self.addCleanup(mocked.stop)

	def make_encounter(self, **values):
		doc = frappe.new_doc("Patient Encounter")
		doc.update(
			{
				"company": COMPANY,
				"insurance_company": INSURANCE_COMPANY,
				"inpatient_record": INPATIENT_RECORD,
				**values,
			}
		)
		return doc

	def test_missing_bed_amount_is_priced_and_stored(self):
		pre_approval.get_services(self.make_encounter())
		self.assertEqual(
			frappe.db.get_value("Inpatient Occupancy", "_Test PA Transfer Bed", "amount"), BED_RATE
		)

	def test_only_todays_beds_without_preapproval_no_are_requested(self):
		services, requested_rows, diseases = pre_approval.get_services(self.make_encounter())

		self.assertEqual(
			services,
			[
				bed_service(nowdate(), nowdate(), BED_RATE),
				bed_service(nowdate(), nowdate(), OPEN_BED_AMOUNT),
			],
		)
		self.assertEqual(
			[(row.name, template_name) for row, template_name, _ref_code in requested_rows],
			[("_Test PA Transfer Bed", SERVICE_UNIT_TYPE), ("_Test PA Today Bed", SERVICE_UNIT_TYPE)],
		)
		self.assertEqual(diseases, [])

	def test_disease_code_has_no_standard_prefix_or_space(self):
		row = frappe._dict(medical_code="ICD-10 Z22.0", parentfield="lab_test_prescription")
		self.assertEqual(pre_approval.get_disease_row(row), {"diseaseCode": "Z22.0", "status": "Preliminary"})

	def test_encounter_without_inpatient_record_has_no_beds(self):
		services, _requested_rows, _diseases = pre_approval.get_services(
			self.make_encounter(inpatient_record=None)
		)
		self.assertEqual(services, [])

	def test_cancel_lookup_finds_bed_by_preapproval_no(self):
		services, _requested_rows, _diseases = pre_approval.get_services(self.make_encounter(), "OLD-1")
		self.assertIn(SERVICE_UNIT_TYPE, services)

	@patch.object(pre_approval.requests, "request")
	def test_accepted_response_updates_bed_rows(self, request):
		request.return_value = nhif_response(
			{
				"requestNo": "PA-1",
				"requestID": "R1",
				"services": [{"itemCode": BED_CODE, "status": "ACCEPTED"}],
			}
		)

		result = pre_approval.get_service_preapproval(
			"Patient Encounter", ENCOUNTER, authorization_no="AUTH1", settings_doc=make_settings()
		)

		self.assertTrue(result)
		payload = json.loads(request.call_args.kwargs["data"])
		self.assertEqual(len(payload["requestedServices"]), 2)
		for name in ["_Test PA Transfer Bed", "_Test PA Today Bed"]:
			bed = get_occupancy(name)
			self.assertEqual((bed.preapproval_no, bed.preapproval_status), ("PA-1", "ACCEPTED"))
		self.assertEqual(get_occupancy("_Test PA Approved Bed").preapproval_no, "OLD-1")
		self.assertFalse(get_occupancy("_Test PA Yesterday Bed").preapproval_no)

	@patch.object(pre_approval.requests, "request")
	def test_rejected_response_clears_bed_preapproval_no(self, request):
		request.return_value = nhif_response(
			{
				"requestNo": "PA-2",
				"requestID": "R2",
				"services": [{"itemCode": BED_CODE, "status": "REJECTED", "rejectionDetails": "Not covered"}],
			}
		)

		pre_approval.get_service_preapproval(
			"Patient Encounter", ENCOUNTER, authorization_no="AUTH1", settings_doc=make_settings()
		)

		bed = get_occupancy("_Test PA Transfer Bed")
		self.assertEqual(bed.preapproval_status, "REJECTED")
		self.assertFalse(bed.preapproval_no)
		self.assertEqual(bed.rejection_details, "Not covered")

	@patch.object(pre_approval.requests, "request")
	def test_cancel_preapproval_cancels_bed_rows(self, request):
		request.return_value = nhif_response([])

		result = pre_approval.cancel_preapproval(
			"Patient Encounter", ENCOUNTER, "OLD-1", "Wrong bed", settings_doc=make_settings()
		)

		self.assertTrue(result)
		bed = get_occupancy("_Test PA Approved Bed")
		self.assertEqual(bed.preapproval_status, "Cancelled")
		self.assertFalse(bed.preapproval_no)
		self.assertEqual(bed.preapproval_cancel_remarks, "Wrong bed")

	@patch.object(pre_approval.requests, "request")
	def test_beds_sharing_item_code_are_updated_once_each(self, request):
		request.return_value = nhif_response(
			{
				"requestNo": "PA-3",
				"requestID": "R3",
				"services": [{"itemCode": BED_CODE, "status": "ACCEPTED"}] * 2,
			}
		)
		db_update = BaseDocument.db_update
		updated = []

		def count_db_update(row, *args, **kwargs):
			updated.append(row.name)
			return db_update(row, *args, **kwargs)

		with patch.object(BaseDocument, "db_update", autospec=True, side_effect=count_db_update):
			pre_approval.get_service_preapproval(
				"Patient Encounter", ENCOUNTER, authorization_no="AUTH1", settings_doc=make_settings()
			)

		self.assertEqual(
			sorted(name for name in updated if name.startswith("_Test PA") and "Bed" in name),
			["_Test PA Today Bed", "_Test PA Transfer Bed"],
		)
