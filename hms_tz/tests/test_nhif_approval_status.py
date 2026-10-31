# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.api import delivery_note
from hms_tz.nhif.nhif_api import approval_status

COMPANY = "_Test AS Company"
APPOINTMENT = "_Test AS Appointment"
DAY_1 = "2026-10-28"
DAY_2 = "2026-10-29"
CODES = {
	"_Test AS Denture": "6424",
	"_Test AS Dialysis": "5001",
	"_Test AS Xray": "7001",
	"_Test AS Drug": "11107",
}


def insert(doctype, name, **values):
	doc = frappe.new_doc(doctype)
	doc.update({"name": name, **values})
	doc.db_insert()


def insert_request(
	ref_docname, preapproval_no, sent_at, services, ref_doctype="Patient Encounter", statuses=None
):
	"""Log a pre-approval request the way `get_service_preapproval` does."""
	insert(
		"NHIF Response Log",
		f"_Test AS Log {preapproval_no}",
		request_type="RequestServices",
		ref_doctype=ref_doctype,
		ref_docname=ref_docname,
		status_code="200",
		timestamp=sent_at,
		request_body=json.dumps(
			{
				"requestedServices": [
					{"itemCode": code, "quantityRequested": quantity} for code, quantity in services.items()
				]
			}
		),
		response_data=str(
			{
				"requestNo": preapproval_no,
				"services": [
					{"itemCode": code, "status": status} for code, status in (statuses or {}).items()
				],
			}
		),
	)


def insert_procedures(encounter, preapproval_no, template, count, prefix):
	for number in range(1, count + 1):
		row_name = f"{prefix} Row {number}"
		insert(
			"Procedure Prescription",
			row_name,
			parent=encounter,
			parenttype="Patient Encounter",
			parentfield="procedure_prescription",
			procedure=template,
			preapproval_no=preapproval_no,
		)
		insert(
			"Clinical Procedure",
			f"{prefix} {number}",
			appointment=APPOINTMENT,
			procedure_template=template,
			is_restricted=1,
			hms_tz_ref_childname=row_name,
			creation=f"{DAY_2} 09:00:{number:02d}",
		)


def approval_line(
	item_code, reference_no, service_date, approval_date, requested, approved, status="Approved"
):
	return {
		"ItemCode": item_code,
		"ReferenceNo": reference_no,
		"ServiceDate": f"{service_date}T00:00:00",
		"ApprovalDate": approval_date,
		"QuantityRequested": requested,
		"QuantityApproved": approved,
		"ApprovalStatus": status,
		"ServiceAuthorizationID": f"SA-{reference_no}",
		"AuthorizedItemID": f"AI-{reference_no}",
	}


def get_approval(doctype, name):
	return frappe.db.get_value(
		doctype, name, ["approval_number", "service_authorization_id", "authorized_item_id"], as_dict=True
	)


class TestNHIFApprovalStatus(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		insert("Patient Appointment", APPOINTMENT, company=COMPANY, insurance_company="NHIF")

	def setUp(self):
		getattr(frappe.local, "request_cache", {}).clear()
		frappe.db.savepoint("approval_status_test")
		self.addCleanup(frappe.db.rollback, save_point="approval_status_test")
		refcode = patch.object(
			approval_status, "get_service_item", side_effect=lambda doctype, name, *args: (CODES[name], None)
		)
		msgprint = patch.object(approval_status.frappe, "msgprint")
		refcode.start()
		self.msgprint = msgprint.start()
		self.addCleanup(refcode.stop)
		self.addCleanup(msgprint.stop)

	def update(self, lines, doctype="Clinical Procedure", name="_Test AS Procedure 1", dni_id=None):
		doc = frappe._dict(doctype=doctype, name=name, company=COMPANY)
		return approval_status.update_approval_status(doc, APPOINTMENT, lines, dni_id=dni_id)

	def test_one_approval_number_covers_approved_quantity(self):
		insert_request("_Test AS PE 1", "PA-1", f"{DAY_2} 11:59:00", {"6424": 8})
		insert_procedures("_Test AS PE 1", "PA-1", "_Test AS Denture", 8, "_Test AS Procedure")

		result = self.update(
			[
				approval_line("6424", "REF-7", DAY_2, f"{DAY_2}T16:28:17.403", 7, 7),
				approval_line("6424", "REF-1", DAY_2, f"{DAY_2}T12:07:12.413", 1, 1),
			]
		)

		self.assertEqual(result, {"status": "success", "reference_no": "REF-1"})
		numbers = [get_approval("Clinical Procedure", f"_Test AS Procedure {n}") for n in range(1, 9)]
		self.assertEqual([row.approval_number for row in numbers], ["REF-1"] + ["REF-7"] * 7)
		self.assertEqual(
			(numbers[3].service_authorization_id, numbers[3].authorized_item_id), ("SA-REF-7", "AI-REF-7")
		)

	def test_second_update_gives_no_extra_units(self):
		insert_request("_Test AS PE 1", "PA-1", f"{DAY_2} 11:59:00", {"6424": 3})
		insert_procedures("_Test AS PE 1", "PA-1", "_Test AS Denture", 3, "_Test AS Procedure")
		lines = [approval_line("6424", "REF-2", DAY_2, f"{DAY_2}T12:00:00", 3, 2)]

		self.update(lines)
		self.update(lines)

		self.assertFalse(get_approval("Clinical Procedure", "_Test AS Procedure 3").approval_number)
		self.assertEqual(frappe.db.count("Clinical Procedure", {"approval_number": "REF-2"}), 2)

	def test_approval_of_another_day_is_not_given(self):
		insert_request("_Test AS PE 1", "PA-1", f"{DAY_1} 10:00:00", {"5001": 2})
		insert_request("_Test AS PE 2", "PA-2", f"{DAY_2} 09:00:00", {"5001": 1})
		insert_procedures("_Test AS PE 1", "PA-1", "_Test AS Dialysis", 2, "_Test AS Day1")
		insert_procedures("_Test AS PE 2", "PA-2", "_Test AS Dialysis", 1, "_Test AS Day2")

		self.update(
			[approval_line("5001", "REF-D1", DAY_1, f"{DAY_2}T11:00:00", 2, 2)], name="_Test AS Day2 1"
		)

		self.assertEqual(get_approval("Clinical Procedure", "_Test AS Day1 1").approval_number, "REF-D1")
		self.assertEqual(get_approval("Clinical Procedure", "_Test AS Day1 2").approval_number, "REF-D1")
		self.assertFalse(get_approval("Clinical Procedure", "_Test AS Day2 1").approval_number)

	def test_approval_before_the_request_was_sent_is_not_given(self):
		insert_request("_Test AS PE 1", "PA-1", f"{DAY_2} 10:00:00", {"6424": 1})
		insert_request("_Test AS PE 2", "PA-2", f"{DAY_2} 13:00:00", {"6424": 1})
		insert_procedures("_Test AS PE 1", "PA-1", "_Test AS Denture", 1, "_Test AS First")
		insert_procedures("_Test AS PE 2", "PA-2", "_Test AS Denture", 1, "_Test AS Second")

		self.update(
			[
				approval_line("6424", "REF-B", DAY_2, f"{DAY_2}T15:00:00", 1, 1),
				approval_line("6424", "REF-A", DAY_2, f"{DAY_2}T12:07:00", 1, 1),
			]
		)

		self.assertEqual(get_approval("Clinical Procedure", "_Test AS First 1").approval_number, "REF-A")
		self.assertEqual(get_approval("Clinical Procedure", "_Test AS Second 1").approval_number, "REF-B")

	def test_service_without_preapproval_no_stays_open(self):
		insert_request("_Test AS PE 1", "PA-1", f"{DAY_2} 10:00:00", {"6424": 1})
		insert_procedures("_Test AS PE 1", "", "_Test AS Denture", 1, "_Test AS Procedure")

		self.update([approval_line("6424", "REF-1", DAY_2, f"{DAY_2}T12:00:00", 1, 1)])

		self.assertFalse(get_approval("Clinical Procedure", "_Test AS Procedure 1").approval_number)

	def test_pending_line_sets_ids_without_approval_number(self):
		insert_request("_Test AS PE 1", "PA-1", f"{DAY_2} 10:00:00", {"6424": 1})
		insert_procedures("_Test AS PE 1", "PA-1", "_Test AS Denture", 1, "_Test AS Procedure")

		self.update([approval_line("6424", "", DAY_2, None, 1, 0, status="Pending")])

		values = frappe.db.get_value(
			"Clinical Procedure",
			"_Test AS Procedure 1",
			["approval_number", "approval_status", "service_authorization_id"],
			as_dict=True,
		)
		self.assertEqual((values.approval_number, values.approval_status), (None, "Pending"))
		self.assertEqual(values.service_authorization_id, "SA-")

	def test_one_update_sets_other_doctypes_and_delivery_note(self):
		insert_request("_Test AS PE 1", "PA-1", f"{DAY_1} 10:00:00", {"7001": 1})
		insert_request("_Test AS PE 2", "PA-2", f"{DAY_2} 09:00:00", {"6424": 1, "11107": 14})
		insert_procedures("_Test AS PE 2", "PA-2", "_Test AS Denture", 1, "_Test AS Procedure")
		insert(
			"Radiology Procedure Prescription",
			"_Test AS Xray Row",
			parent="_Test AS PE 1",
			parenttype="Patient Encounter",
			parentfield="radiology_procedure_prescription",
			radiology_examination_template="_Test AS Xray",
			preapproval_no="PA-1",
		)
		insert(
			"Radiology Examination",
			"_Test AS Xray",
			appointment=APPOINTMENT,
			is_restricted=1,
			hms_tz_ref_childname="_Test AS Xray Row",
		)
		insert(
			"Drug Prescription",
			"_Test AS Drug Row",
			parent="_Test AS PE 2",
			parenttype="Patient Encounter",
			parentfield="drug_prescription",
			drug_code="_Test AS Drug",
			preapproval_no="PA-2",
		)
		insert("Delivery Note", "_Test AS DN", hms_tz_appointment_no=APPOINTMENT, company=COMPANY)
		insert(
			"Delivery Note Item",
			"_Test AS DNI",
			parent="_Test AS DN",
			parenttype="Delivery Note",
			parentfield="items",
			item_code="_Test AS Drug Item",
			qty=14,
			is_restricted=1,
			reference_doctype="Drug Prescription",
			reference_name="_Test AS Drug Row",
		)

		self.update(
			[
				approval_line("7001", "REF-X", DAY_1, f"{DAY_2}T08:00:00", 1, 1),
				approval_line("11107", "REF-M", DAY_2, f"{DAY_2}T10:00:00", 14, 10),
				approval_line("11107", "REF-M2", DAY_2, f"{DAY_2}T10:30:00", 14, 14),
			]
		)

		self.assertEqual(get_approval("Radiology Examination", "_Test AS Xray").approval_number, "REF-X")
		self.assertEqual(get_approval("Delivery Note Item", "_Test AS DNI").approval_number, "REF-M")
		self.assertFalse(get_approval("Clinical Procedure", "_Test AS Procedure 1").approval_number)
		self.assertEqual(frappe.db.get_value("Delivery Note Item", "_Test AS DNI", "approved_qty"), 10)
		messages = [call.args[0] for call in self.msgprint.call_args_list]
		self.assertFalse([message for message in messages if "Approved quantity" in message])

	def test_short_drug_approval_warns_only_on_delivery_note(self):
		insert_request("_Test AS PE 1", "PA-1", f"{DAY_2} 09:00:00", {"11107": 14})
		insert(
			"Drug Prescription",
			"_Test AS Drug Row",
			parent="_Test AS PE 1",
			parenttype="Patient Encounter",
			parentfield="drug_prescription",
			drug_code="_Test AS Drug",
			preapproval_no="PA-1",
		)
		insert("Delivery Note", "_Test AS DN", hms_tz_appointment_no=APPOINTMENT, company=COMPANY)
		insert(
			"Delivery Note Item",
			"_Test AS DNI",
			parent="_Test AS DN",
			parenttype="Delivery Note",
			parentfield="items",
			item_code="_Test AS Drug Item",
			qty=14,
			is_restricted=1,
			reference_doctype="Drug Prescription",
			reference_name="_Test AS Drug Row",
		)

		self.update(
			[approval_line("11107", "REF-M", DAY_2, f"{DAY_2}T10:00:00", 14, 10)],
			doctype="Delivery Note",
			name="_Test AS DN",
			dni_id="_Test AS DNI",
		)

		self.assertIn("Approved quantity for <b>_Test AS Drug Item", self.msgprint.call_args_list[0].args[0])

	def test_drug_preapproved_by_medication_change_request_gets_approval(self):
		insert("Medication Change Request", "_Test AS MCR", patient_encounter="_Test AS PE 1")
		insert_request(
			"_Test AS MCR",
			"PA-MCR",
			f"{DAY_2} 14:00:00",
			{"11107": 10},
			ref_doctype="Medication Change Request",
		)
		# on submit the change request copies its rows, with preapproval_no, into the encounter
		insert(
			"Drug Prescription",
			"_Test AS Drug Row",
			parent="_Test AS PE 1",
			parenttype="Patient Encounter",
			parentfield="drug_prescription",
			drug_code="_Test AS Drug",
			preapproval_no="PA-MCR",
		)
		insert("Delivery Note", "_Test AS DN", hms_tz_appointment_no=APPOINTMENT, company=COMPANY)
		insert(
			"Delivery Note Item",
			"_Test AS DNI",
			parent="_Test AS DN",
			parenttype="Delivery Note",
			parentfield="items",
			item_code="_Test AS Drug Item",
			qty=10,
			is_restricted=1,
			reference_doctype="Drug Prescription",
			reference_name="_Test AS Drug Row",
		)

		result = self.update(
			[approval_line("11107", "REF-MCR", DAY_2, f"{DAY_2}T15:00:00", 10, 10)],
			doctype="Delivery Note",
			name="_Test AS DN",
			dni_id="_Test AS DNI",
		)

		self.assertEqual(result["reference_no"], "REF-MCR")
		self.assertEqual(frappe.db.get_value("Delivery Note Item", "_Test AS DNI", "approved_qty"), 10)

	def insert_radiology(self, preapproval_no, preapproval_status):
		insert(
			"Radiology Procedure Prescription",
			"_Test AS Xray Row",
			parent="_Test AS PE 1",
			parenttype="Patient Encounter",
			parentfield="radiology_procedure_prescription",
			radiology_examination_template="_Test AS Xray",
			preapproval_no=preapproval_no,
			preapproval_status=preapproval_status,
		)
		insert(
			"Radiology Examination",
			"_Test AS Xray",
			appointment=APPOINTMENT,
			is_restricted=1,
			hms_tz_ref_childname="_Test AS Xray Row",
		)

	def test_row_rejected_as_pending_duplicate_gets_approval_of_earlier_request(self):
		insert_request(
			"_Test AS PE 1", "PA-1", f"{DAY_2} 10:00:00", {"7001": 1}, statuses={"7001": "WAIT_APPROVAL"}
		)
		insert_request(
			"_Test AS PE 1", "PA-2", f"{DAY_2} 10:05:00", {"7001": 1}, statuses={"7001": "REJECTED"}
		)
		self.insert_radiology("", "REJECTED")

		self.update([approval_line("7001", "REF-X", DAY_2, f"{DAY_2}T11:00:00", 1, 1)])

		self.assertEqual(get_approval("Radiology Examination", "_Test AS Xray").approval_number, "REF-X")

	def test_row_rejected_by_every_request_stays_open(self):
		insert_request(
			"_Test AS PE 1", "PA-1", f"{DAY_2} 10:00:00", {"7001": 1}, statuses={"7001": "REJECTED"}
		)
		self.insert_radiology("", "REJECTED")

		self.update([approval_line("7001", "REF-X", DAY_2, f"{DAY_2}T11:00:00", 1, 1)])

		self.assertFalse(get_approval("Radiology Examination", "_Test AS Xray").approval_number)


class TestDeliveryNoteApprovedQty(FrappeTestCase):
	def make_delivery_note(self, qty, approved_qty):
		doc = frappe.new_doc("Delivery Note")
		doc.company = COMPANY
		doc.append(
			"items",
			{
				"item_name": "Amoxycillin",
				"qty": qty,
				"is_restricted": 1,
				"approval_number": "REF-M",
				"approved_qty": approved_qty,
			},
		)
		return doc

	@patch.object(delivery_note, "validate_point_of_care")
	@patch.object(delivery_note, "validate_issued_services")
	def test_quantity_above_approved_qty_blocks_submit(self, *mocks):
		with self.assertRaises(frappe.ValidationError) as error:
			delivery_note.before_submit(self.make_delivery_note(14, 10), "before_submit")

		self.assertIn("Medication Change Request", str(error.exception))
		self.assertIn("paid by cash", str(error.exception))

	@patch.object(delivery_note, "validate_point_of_care")
	@patch.object(delivery_note, "validate_issued_services")
	def test_quantity_within_approved_qty_submits(self, *mocks):
		delivery_note.before_submit(self.make_delivery_note(10, 10), "before_submit")
		delivery_note.before_submit(self.make_delivery_note(14, 0), "before_submit")
