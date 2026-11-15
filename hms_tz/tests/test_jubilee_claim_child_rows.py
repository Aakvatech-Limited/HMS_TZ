# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.jubilee.doctype.jubilee_patient_claim.jubilee_patient_claim import JubileePatientClaim

# What the encounters currently produce; tests change it between saves
SOURCE = {}

real_get_cached_value = frappe.get_cached_value


def fake_get_cached_value(doctype, name, fieldname, *args, **kwargs):
	if doctype == "HMS TZ Setting":
		return "_TEST-PROVIDER"
	if doctype == "Patient Appointment" and isinstance(fieldname, list | tuple):
		return frappe.utils.getdate("2026-11-01"), "08:00:00"
	return real_get_cached_value(doctype, name, fieldname, *args, **kwargs)


def set_practitioner_values(self, encounter_list):
	self.practitioners = []
	for practitioner in SOURCE["practitioners"]:
		self.append("practitioners", {"practitioner": practitioner, "mct_code": f"MCT-{practitioner}"})


def set_patient_claim_disease(self, encounter_list):
	self.jubilee_patient_claim_disease = []
	for medical_code, status in SOURCE["diseases"]:
		self.append(
			"jubilee_patient_claim_disease",
			{"medical_code": medical_code, "status": status, "disease_code": medical_code[:3]},
		)


def set_patient_claim_item(self, encounter_list):
	self.jubilee_patient_claim_item = []
	for ref_docname, item_code, quantity in SOURCE["items"]:
		self.append(
			"jubilee_patient_claim_item",
			{
				"ref_doctype": "Lab Prescription",
				"ref_docname": ref_docname,
				"item_code": item_code,
				"item_name": f"Item {item_code}",
				"item_quantity": quantity,
				"unit_price": 1000,
				"amount_claimed": 1000 * quantity,
				"status": "Submitted",
			},
		)


# Claim methods that read encounters, appointments and settings, replaced so the test drives the rows
PATCHES = [
	patch("frappe.get_cached_value", new=fake_get_cached_value),
	patch.object(
		JubileePatientClaim,
		"get_patient_encounters",
		new=lambda self: [frappe._dict(encounter="_ENC-1", encounter_type="Final", inpatient_record=None)],
	),
	patch.object(JubileePatientClaim, "set_practitioner_values", new=set_practitioner_values),
	patch.object(JubileePatientClaim, "set_patient_claim_disease", new=set_patient_claim_disease),
	patch.object(JubileePatientClaim, "set_patient_claim_item", new=set_patient_claim_item),
	patch.object(JubileePatientClaim, "validate_appointment_info", new=lambda self: None),
	patch.object(
		JubileePatientClaim,
		"validate_multiple_appointments_per_authorization_no",
		new=lambda self, caller=None: None,
	),
	patch(
		"hms_tz.jubilee.doctype.jubilee_patient_claim.jubilee_patient_claim.get_or_create_folio_counter",
		new=lambda doc, provider: 772,
	),
]


class TestJubileeClaimChildRows(FrappeTestCase):
	def setUp(self):
		for patcher in PATCHES:
			patcher.start()
			self.addCleanup(patcher.stop)

		SOURCE.update(
			practitioners=["_PRAC-1", "_PRAC-2"],
			diseases=[("A09.0", "Provisional"), ("A09.0", "Final"), ("B50.9", "Final")],
			items=[("_LP-1", "1001", 1), ("_LP-2", "1002", 2), ("_LP-3", "1003", 1)],
		)
		self.claim = frappe.new_doc("Jubilee Patient Claim")
		self.claim.update(
			{
				"patient": "_Test Claim Rows Patient",
				"patient_appointment": "_TEST-CLAIM-ROWS-APP",
				"authorization_no": "_TEST-CLAIM-ROWS-AUTH",
				"cardno": "_TEST-CLAIM-ROWS-CARD",
				"date_of_birth": frappe.utils.getdate("1990-01-01"),
			}
		)
		self.claim.flags.ignore_links = True
		self.claim.insert(
			ignore_permissions=True, set_name="JPC-990000001"
		)  # serial_no reads the last 9 digits

	def tearDown(self):
		frappe.db.rollback()

	def save(self):
		claim = frappe.get_doc("Jubilee Patient Claim", self.claim.name)
		claim.flags.ignore_links = True
		# Frappe skips Versions in tests unless asked
		claim.save(ignore_permissions=True, ignore_version=False)
		return claim

	def versions(self):
		return [
			json.loads(data)
			for data in frappe.get_all(
				"Version",
				filters={"ref_doctype": "Jubilee Patient Claim", "docname": self.claim.name},
				order_by="creation",
				pluck="data",
			)
		]

	def test_create_snapshots_items_without_a_second_save(self):
		claim = frappe.get_doc("Jubilee Patient Claim", self.claim.name)
		self.assertEqual(
			[(row.ref_docname, row.item_quantity) for row in claim.original_jubilee_patient_claim_item],
			[("_LP-1", 1), ("_LP-2", 2), ("_LP-3", 1)],
		)
		# a second save from after_insert would bump modified
		self.assertEqual(claim.modified, claim.creation)
		self.assertEqual(claim.folio_no, 772)
		self.assertEqual(claim.serial_no, "990000001")

	def test_unchanged_save_keeps_every_row(self):
		before = frappe.get_doc("Jubilee Patient Claim", self.claim.name)
		after = self.save()
		for table in ["practitioners", "jubilee_patient_claim_disease", "jubilee_patient_claim_item"]:
			self.assertEqual([row.name for row in after.get(table)], [row.name for row in before.get(table)])
		# folio_id is regenerated on every draft save: the only change left
		(version,) = self.versions()
		self.assertEqual([change[0] for change in version["changed"]], ["folio_id"])
		self.assertFalse(version["added"] or version["removed"] or version["row_changed"])

	def test_changed_items_update_in_place(self):
		before = frappe.get_doc("Jubilee Patient Claim", self.claim.name)
		names = {row.ref_docname: row.name for row in before.jubilee_patient_claim_item}

		SOURCE["items"] = [("_LP-1", "1001", 1), ("_LP-3", "1003", 5), ("_LP-4", "1004", 1)]
		after = self.save()

		self.assertEqual(
			[row.ref_docname for row in after.jubilee_patient_claim_item], ["_LP-1", "_LP-3", "_LP-4"]
		)
		self.assertEqual([row.idx for row in after.jubilee_patient_claim_item], [1, 2, 3])
		self.assertEqual(after.jubilee_patient_claim_item[0].name, names["_LP-1"])
		self.assertEqual(after.jubilee_patient_claim_item[1].name, names["_LP-3"])
		self.assertEqual(after.jubilee_patient_claim_item[1].item_quantity, 5)
		self.assertFalse(frappe.db.exists("Jubilee Patient Claim Item", names["_LP-2"]))

		version = self.versions()[-1]
		self.assertEqual([row[1]["ref_docname"] for row in version["removed"]], ["_LP-2"])
		self.assertEqual(
			[row[1]["ref_docname"] for row in version["added"] if row[0] == "jubilee_patient_claim_item"],
			["_LP-4"],
		)

	def test_new_item_is_still_added_to_original_items(self):
		SOURCE["items"].append(("_LP-4", "1004", 1))
		after = self.save()
		self.assertEqual(
			[row.ref_docname for row in after.original_jubilee_patient_claim_item],
			["_LP-1", "_LP-2", "_LP-3", "_LP-4"],
		)

	def test_removed_disease_and_practitioner_rows_are_deleted(self):
		before = frappe.get_doc("Jubilee Patient Claim", self.claim.name)
		SOURCE["diseases"] = [("A09.0", "Final"), ("B50.9", "Final")]
		SOURCE["practitioners"] = ["_PRAC-2"]
		after = self.save()
		self.assertEqual(
			[row.name for row in after.jubilee_patient_claim_disease],
			[row.name for row in before.jubilee_patient_claim_disease[1:]],
		)
		self.assertEqual([row.name for row in after.practitioners], [before.practitioners[1].name])
		self.assertEqual([row.idx for row in after.jubilee_patient_claim_disease], [1, 2])
