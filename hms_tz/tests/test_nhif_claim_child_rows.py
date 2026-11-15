# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.doctype.nhif_patient_claim.nhif_patient_claim import NHIFPatientClaim

# What the encounters currently produce; tests change it between saves
SOURCE = {}

real_get_cached_value = frappe.get_cached_value


def fake_get_cached_value(doctype, name, fieldname, *args, **kwargs):
	if doctype == "HMS TZ Setting":
		return "_TEST-FACILITY"
	if doctype == "Patient Appointment" and isinstance(fieldname, list | tuple):
		return frappe.utils.getdate("2026-11-01"), "08:00:00"
	if doctype == "Code Value":
		return "A09"
	return real_get_cached_value(doctype, name, fieldname, *args, **kwargs)


def set_practitioner_values(self, encounter_list):
	self.practitioners = []
	for practitioner in SOURCE["practitioners"]:
		self.append("practitioners", {"practitioner": practitioner, "mct_code": f"MCT-{practitioner}"})


def set_patient_claim_disease(self, encounter_list):
	self.nhif_patient_claim_disease = []
	for codification_table, code in SOURCE["diseases"]:
		self.append(
			"nhif_patient_claim_disease",
			{
				"patient_encounter": "_ENC-1",
				"codification_table": codification_table,
				"disease_code": code,
				"status": "Final",
			},
		)


def set_patient_claim_item(self, encounter_list):
	self.nhif_patient_claim_item = []
	for ref_docname, item_code, quantity in SOURCE["items"]:
		self.append(
			"nhif_patient_claim_item",
			{
				"ref_doctype": "Lab Prescription",
				"ref_docname": ref_docname,
				"item_code": item_code,
				"item_name": f"Item {item_code}",
				"item_quantity": quantity,
				"unit_price": 1000,
				"percent_covered": 100,
				"status": "Submitted",
			},
		)


# Claim methods that read encounters, appointments and settings, replaced so the test drives the rows
PATCHES = [
	patch("frappe.get_cached_value", new=fake_get_cached_value),
	patch.object(
		NHIFPatientClaim,
		"get_patient_encounters",
		new=lambda self: [
			frappe._dict(encounter="_ENC-1", encounter_type="Final", main_diagnosis_code="A09")
		],
	),
	patch.object(NHIFPatientClaim, "set_practitioner_values", new=set_practitioner_values),
	patch.object(NHIFPatientClaim, "set_inpatient_values", new=lambda self, encounter_list: None),
	patch.object(NHIFPatientClaim, "set_patient_claim_disease", new=set_patient_claim_disease),
	patch.object(NHIFPatientClaim, "set_patient_claim_item", new=set_patient_claim_item),
	patch.object(NHIFPatientClaim, "validate_appointment_info", new=lambda self: None),
	patch.object(
		NHIFPatientClaim,
		"validate_multiple_appointments_per_authorization_no",
		new=lambda self, caller=None: None,
	),
	patch(
		"hms_tz.nhif.doctype.nhif_patient_claim.nhif_patient_claim.get_or_create_folio_counter",
		new=lambda doc, provider: 771,
	),
]


class TestNHIFClaimChildRows(FrappeTestCase):
	def setUp(self):
		for patcher in PATCHES:
			patcher.start()
			self.addCleanup(patcher.stop)

		SOURCE.update(
			practitioners=["_PRAC-1", "_PRAC-2"],
			diseases=[("_CT-1", "A09"), ("_CT-2", "B50")],
			items=[("_LP-1", "1001", 1), ("_LP-2", "1002", 2), ("_LP-3", "1003", 1)],
		)
		self.claim = frappe.new_doc("NHIF Patient Claim")
		self.claim.update(
			{
				"patient": "_Test Claim Rows Patient",
				"patient_appointment": "_TEST-CLAIM-ROWS-APP",
				"authorization_no": "_TEST-CLAIM-ROWS-AUTH",
				"cardno": "_TEST-CLAIM-ROWS-CARD",
				"naming_series": "NPC-",
			}
		)
		self.claim.flags.ignore_links = True
		self.claim.insert(
			ignore_permissions=True, set_name="NPC-990000001"
		)  # serial_no reads the last 9 digits

	def tearDown(self):
		frappe.db.rollback()

	def save(self):
		claim = frappe.get_doc("NHIF Patient Claim", self.claim.name)
		claim.flags.ignore_links = True
		# Frappe skips Versions in tests unless asked
		claim.save(ignore_permissions=True, ignore_version=False)
		return claim

	def versions(self):
		return [
			json.loads(data)
			for data in frappe.get_all(
				"Version",
				filters={"ref_doctype": "NHIF Patient Claim", "docname": self.claim.name},
				order_by="creation",
				pluck="data",
			)
		]

	def test_create_snapshots_items_without_a_second_save(self):
		claim = frappe.get_doc("NHIF Patient Claim", self.claim.name)
		self.assertEqual(
			[
				(row.ref_docname, row.item_quantity, row.amount_claimed)
				for row in claim.original_nhif_patient_claim_item
			],
			[("_LP-1", 1, 1000), ("_LP-2", 2, 2000), ("_LP-3", 1, 1000)],
		)
		# a second save from after_insert would bump modified
		self.assertEqual(claim.modified, claim.creation)
		self.assertEqual(claim.folio_no, 771)
		self.assertEqual(
			{row.claim_status for row in claim.original_nhif_patient_claim_item}, {"Pending Response"}
		)

	def test_unchanged_save_keeps_every_row(self):
		before = frappe.get_doc("NHIF Patient Claim", self.claim.name)
		after = self.save()
		for table in ["practitioners", "nhif_patient_claim_disease", "nhif_patient_claim_item"]:
			self.assertEqual([row.name for row in after.get(table)], [row.name for row in before.get(table)])
		self.assertEqual(self.versions(), [])

	def test_changed_items_update_in_place(self):
		before = frappe.get_doc("NHIF Patient Claim", self.claim.name)
		names = {row.ref_docname: row.name for row in before.nhif_patient_claim_item}

		SOURCE["items"] = [("_LP-1", "1001", 1), ("_LP-3", "1003", 5), ("_LP-4", "1004", 1)]
		after = self.save()

		self.assertEqual(
			[row.ref_docname for row in after.nhif_patient_claim_item], ["_LP-1", "_LP-3", "_LP-4"]
		)
		self.assertEqual([row.idx for row in after.nhif_patient_claim_item], [1, 2, 3])
		self.assertEqual(after.nhif_patient_claim_item[0].name, names["_LP-1"])
		self.assertEqual(after.nhif_patient_claim_item[1].name, names["_LP-3"])
		self.assertEqual(after.nhif_patient_claim_item[1].amount_claimed, 5000)
		self.assertFalse(frappe.db.exists("NHIF Patient Claim Item", names["_LP-2"]))

		version = self.versions()[-1]
		self.assertEqual([row[1]["ref_docname"] for row in version["removed"]], ["_LP-2"])
		self.assertEqual(
			[row[1]["ref_docname"] for row in version["added"] if row[0] == "nhif_patient_claim_item"],
			["_LP-4"],
		)
		self.assertEqual(
			sorted(
				{
					change[0]
					for row in version["row_changed"]
					if row[0] == "nhif_patient_claim_item"
					for change in row[3]
				}
			),
			["amount_claimed", "item_quantity"],
		)

	def test_new_item_is_still_added_to_original_items(self):
		SOURCE["items"].append(("_LP-4", "1004", 1))
		after = self.save()
		self.assertEqual(
			[row.ref_docname for row in after.original_nhif_patient_claim_item],
			["_LP-1", "_LP-2", "_LP-3", "_LP-4"],
		)

	def test_repeated_keys_keep_both_rows(self):
		SOURCE["items"].append(("_LP-1", "1001", 1))
		claim = self.save()
		first_names = [row.name for row in claim.nhif_patient_claim_item]
		again = self.save()
		self.assertEqual([row.name for row in again.nhif_patient_claim_item], first_names)
		self.assertEqual(len(set(first_names)), 4)

	def test_removed_disease_and_practitioner_rows_are_deleted(self):
		before = frappe.get_doc("NHIF Patient Claim", self.claim.name)
		SOURCE["diseases"] = [("_CT-2", "B50")]
		SOURCE["practitioners"] = ["_PRAC-2"]
		after = self.save()
		self.assertEqual(
			[row.name for row in after.nhif_patient_claim_disease],
			[before.nhif_patient_claim_disease[1].name],
		)
		self.assertEqual([row.name for row in after.practitioners], [before.practitioners[1].name])
		self.assertEqual(after.nhif_patient_claim_disease[0].idx, 1)
