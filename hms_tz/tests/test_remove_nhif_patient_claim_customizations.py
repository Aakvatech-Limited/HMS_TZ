# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.patches.remove_nhif_patient_claim_customizations import (
	CUSTOM_FIELDS,
	DOCTYPE,
	PROPERTY_SETTERS,
	execute,
)

MOVED_FIELDS = (
	"how_likely_would_you_recommend_our_services_to_others",
	"internal_form_number",
	"unsubmittable_claim",
)
COLUMN_BREAKS = ("7hfoo", "f0pzn", "psqsj", "cffd2", "zz999")


def insert_live_site_rows():
	"""Insert the rows as they exist on live sites, bypassing validation against the new standard fields."""
	for name in PROPERTY_SETTERS:
		field_name, prop = name.removeprefix(f"{DOCTYPE}-").split("-")
		frappe.get_doc(
			doctype="Property Setter",
			name=name,
			doc_type=DOCTYPE,
			doctype_or_field="DocType" if field_name == "main" else "DocField",
			field_name=None if field_name == "main" else field_name,
			property=prop,
			value="1",
		).db_insert()

	for name in CUSTOM_FIELDS:
		fieldname = name.removeprefix(f"{DOCTYPE}-")
		frappe.get_doc(
			doctype="Custom Field", name=name, dt=DOCTYPE, fieldname=fieldname, fieldtype="Data"
		).db_insert()

	for suffix in COLUMN_BREAKS:
		frappe.get_doc(
			doctype="Custom Field",
			name=f"{DOCTYPE}-custom_column_break_{suffix}",
			dt=DOCTYPE,
			fieldname=f"custom_column_break_{suffix}",
			fieldtype="Column Break",
		).db_insert()


class TestRemoveNhifPatientClaimCustomizations(FrappeTestCase):
	def test_patch_removes_existing_rows(self):
		insert_live_site_rows()

		execute()

		for name in PROPERTY_SETTERS:
			self.assertFalse(frappe.db.exists("Property Setter", name), name)
		for name in CUSTOM_FIELDS:
			self.assertFalse(frappe.db.exists("Custom Field", name), name)
		for suffix in COLUMN_BREAKS:
			name = f"{DOCTYPE}-custom_column_break_{suffix}"
			self.assertFalse(frappe.db.exists("Custom Field", name), name)

	def test_patch_passes_when_rows_are_missing(self):
		execute()
		execute()

	def test_moved_fields_stay_standard_with_their_columns(self):
		insert_live_site_rows()

		execute()

		meta = frappe.get_meta(DOCTYPE)
		for fieldname in MOVED_FIELDS:
			field = meta.get_field(fieldname)
			self.assertTrue(field and not field.get("is_custom_field"), fieldname)
			self.assertTrue(frappe.db.has_column(DOCTYPE, fieldname), fieldname)

	def test_json_keeps_make_attachments_public(self):
		execute()

		self.assertTrue(frappe.get_meta(DOCTYPE).make_attachments_public)
