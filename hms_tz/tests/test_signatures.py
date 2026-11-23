import os
import shutil
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz import signatures
from hms_tz.patches import move_signatures_to_store as migration
from hms_tz.signatures import dehydrate, get_signature, hydrate, is_pointer, resolve_signature, store
from hms_tz.tests.utils import insert

PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
OTHER_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
SVG = "data:image/svg+xml;base64,PHN2Zy8+"
CLAIM = "NHIF Patient Claim"


class TestSignatures(FrappeTestCase):
	def setUp(self):
		# keep test files apart from real ones
		folder = f"hms_signatures_test_{frappe.generate_hash(length=6)}"
		self.folder = frappe.utils.get_files_path(folder, is_private=True)
		for patcher in [
			patch.object(signatures, "FOLDER", folder),
			patch.dict(frappe.conf, {"hms_tz_signature_store": 1}),
			patch.object(frappe.db, "commit"),
		]:
			patcher.start()
			self.addCleanup(patcher.stop)

	def tearDown(self):
		frappe.db.rollback()
		shutil.rmtree(self.folder, ignore_errors=True)

	def path(self, pointer):
		return signatures.get_path(*signatures.POINTER.match(pointer).groups())

	def test_image_is_stored_once_as_an_image_file(self):
		pointer = store(PNG)

		self.assertTrue(is_pointer(pointer))
		self.assertEqual(store(PNG), pointer)
		self.assertTrue(pointer.endswith(".png"))
		self.assertEqual(os.path.basename(os.path.dirname(self.path(pointer))), pointer[4:6])
		self.assertEqual(resolve_signature(pointer), PNG)
		self.assertEqual(len(os.listdir(os.path.dirname(self.path(pointer)))), 1)

	def test_other_formats_are_kept_as_they_are(self):
		pointer = store(SVG)

		self.assertTrue(pointer.endswith(".txt"))
		self.assertEqual(resolve_signature(pointer), SVG)

	def test_value_to_save_is_a_pointer_only_with_the_flag(self):
		self.assertTrue(is_pointer(signatures.get_value_to_save(PNG)))
		with patch.dict(frappe.conf, {"hms_tz_signature_store": 0}):
			self.assertEqual(signatures.get_value_to_save(PNG), PNG)

	def test_values_that_are_not_pointers_are_returned_unchanged(self):
		self.assertEqual(resolve_signature(PNG), PNG)
		self.assertEqual(resolve_signature(None), "")

	def test_missing_file_stops_print_but_not_the_form(self):
		pointer = store(PNG)
		os.remove(self.path(pointer))
		self.assertRaises(frappe.DoesNotExistError, resolve_signature, pointer)

		doc = frappe.new_doc(CLAIM)
		doc.patient_signature = pointer
		self.assertRaises(frappe.DoesNotExistError, hydrate, doc, "before_print")

		with patch.object(frappe, "log_error") as log_error:
			hydrate(doc, "onload")
		self.assertEqual(doc.patient_signature, pointer)
		log_error.assert_called_once()

	def test_signature_can_be_cleared(self):
		doc = frappe.new_doc(CLAIM)
		doc._doc_before_save = frappe._dict(doctype=CLAIM, patient_signature=store(PNG))
		doc.patient_signature = ""

		dehydrate(doc)

		self.assertEqual(doc.patient_signature, "")

	def test_saves_store_signatures_only_with_the_flag(self):
		doc = frappe.new_doc(CLAIM)
		doc.patient_signature = PNG

		with patch.dict(frappe.conf, {"hms_tz_signature_store": 0}):
			dehydrate(doc)
		self.assertEqual(doc.patient_signature, PNG)

		dehydrate(doc)
		self.assertTrue(is_pointer(doc.patient_signature))

		hydrate(doc, "onload")
		self.assertEqual(doc.patient_signature, PNG)

	def test_unchanged_signature_keeps_its_pointer(self):
		pointer = store(PNG)
		doc = frappe.new_doc(CLAIM)
		doc._doc_before_save = frappe._dict(doctype=CLAIM, patient_signature=pointer)
		doc.patient_signature = PNG  # as the form got it on load

		with patch.object(signatures, "store") as store_again:
			dehydrate(doc)

		self.assertEqual(doc.patient_signature, pointer)
		store_again.assert_not_called()

	def test_unchanged_signature_stored_from_other_text_keeps_its_pointer(self):
		pointer = store(PNG.replace("image/png", "image/PNG"))  # resolves as image/png
		doc = frappe.new_doc(CLAIM)
		doc._doc_before_save = frappe._dict(doctype=CLAIM, patient_signature=pointer)
		doc.patient_signature = resolve_signature(pointer)

		dehydrate(doc)

		self.assertEqual(doc.patient_signature, pointer)

	def test_signature_saved_inline_is_stored_without_a_version_change(self):
		doc = frappe.new_doc(CLAIM)
		doc._doc_before_save = frappe.new_doc(CLAIM)
		doc._doc_before_save.patient_signature = PNG
		doc.patient_signature = PNG

		dehydrate(doc)

		self.assertTrue(is_pointer(doc.patient_signature))
		self.assertEqual(doc._doc_before_save.patient_signature, doc.patient_signature)

	def test_doctypes_of_other_apps_are_left_alone(self):
		if not frappe.db.exists("DocType", "Contract"):
			self.skipTest("no Contract doctype")
		doc = frappe.new_doc("Contract")
		doc.signee_company = PNG

		dehydrate(doc)

		self.assertEqual(doc.signee_company, PNG)

		# but a pointer copied there (fetch_from) is still shown
		doc.signee_company = store(PNG)
		hydrate(doc, "before_print")
		self.assertEqual(doc.signee_company, PNG)

	def test_signature_is_readable_with_its_document(self):
		pointer = store(PNG)
		insert(CLAIM, "_Test Sig Claim", patient_signature=pointer)

		self.assertEqual(get_signature(pointer, CLAIM, "patient_signature", name="_Test Sig Claim"), PNG)
		# another document's signature can't be read through this one
		self.assertRaises(
			frappe.PermissionError,
			get_signature,
			store(OTHER_PNG),
			CLAIM,
			"patient_signature",
			name="_Test Sig Claim",
		)
		with patch.object(frappe, "has_permission", side_effect=frappe.PermissionError):
			self.assertRaises(
				frappe.PermissionError,
				get_signature,
				pointer,
				CLAIM,
				"patient_signature",
				name="_Test Sig Claim",
			)

	def test_signature_with_a_missing_file_reads_as_none(self):
		pointer = store(PNG)
		insert(CLAIM, "_Test Sig Claim", patient_signature=pointer)
		os.remove(self.path(pointer))

		self.assertIsNone(get_signature(pointer, CLAIM, "patient_signature", name="_Test Sig Claim"))

	def test_fetched_signature_is_readable_with_its_source(self):
		field = frappe.get_meta("Patient Encounter").get_field("healthcare_practitioner_signature")
		if not field or field.fetch_from != "practitioner.doctors_signature":
			self.skipTest("no fetched practitioner signature on Patient Encounter")
		pointer = store(PNG)
		insert(
			"Healthcare Practitioner", "_Test Sig Practitioner", first_name="Test", doctors_signature=pointer
		)

		image = get_signature(
			pointer,
			"Patient Encounter",
			"healthcare_practitioner_signature",
			source_name="_Test Sig Practitioner",
		)

		self.assertEqual(image, PNG)
		with patch.object(frappe, "has_permission", side_effect=frappe.PermissionError):
			self.assertRaises(
				frappe.PermissionError,
				get_signature,
				pointer,
				"Patient Encounter",
				"healthcare_practitioner_signature",
				source_name="_Test Sig Practitioner",
			)

	def test_migration_moves_inline_values_and_restore_puts_them_back(self):
		insert(CLAIM, "_Test Sig Claim 1", patient_signature=PNG)
		insert(CLAIM, "_Test Sig Claim 2", patient_signature=OTHER_PNG)
		insert(CLAIM, "_Test Sig Claim 3", patient_signature=store(PNG))

		migration.move_column(CLAIM, "patient_signature")

		values = self.get_claim_signatures()
		self.assertTrue(all(is_pointer(value) for value in values))
		self.assertEqual(values[0], values[2])
		self.assertEqual(migration.verify(), [])

		with patch.dict(frappe.conf, {"hms_tz_signature_store": 0}):
			migration.restore()
		self.assertEqual(self.get_claim_signatures(), [PNG, OTHER_PNG, PNG])

	def test_migration_leaves_values_changed_meanwhile(self):
		insert(CLAIM, "_Test Sig Claim 1", patient_signature=PNG)

		def store_while_user_signs_again(value):
			frappe.db.set_value(CLAIM, "_Test Sig Claim 1", "patient_signature", OTHER_PNG)
			return store(value)

		with patch.object(migration, "store", store_while_user_signs_again):
			migration.move_column(CLAIM, "patient_signature")

		self.assertEqual(self.get_claim_signatures(), [OTHER_PNG])

	def test_audit_lists_customisations_reading_signatures(self):
		insert(
			"Client Script",
			"_Test Sig Script",
			dt=CLAIM,
			script="frappe.db.get_value('Patient', frm.doc.patient, 'patient_signature')",
		)

		found = migration.audit()

		self.assertIn(("Client Script", "_Test Sig Script", ["patient_signature"]), found)

	def test_audit_lists_print_formats_reading_signatures(self):
		insert(
			"Print Format",
			"_Test Sig Print Format",
			doc_type=CLAIM,
			custom_format=1,
			html="""<img src="{{ frappe.db.get_value('Healthcare Practitioner', p, 'doctors_signature') }}">""",
		)

		found = migration.audit()

		self.assertIn(("Print Format", "_Test Sig Print Format", ["doctors_signature"]), found)

	def test_enable_needs_the_audit_reviewed(self):
		with (
			patch.object(migration, "audit", return_value=[("Client Script", "x", ["patient_signature"])]),
			patch.object(migration, "update_site_config") as update_site_config,
		):
			self.assertRaises(frappe.ValidationError, migration.enable)
			update_site_config.assert_not_called()

			migration.enable(force=True)
			update_site_config.assert_called_once_with("hms_tz_signature_store", 1)

	def test_prune_deletes_old_unused_files_only(self):
		in_document, in_deleted_document, unused, new = (store(f"{PNG[:-2]}{i}==") for i in "ABCD")
		insert(CLAIM, "_Test Sig Claim 1", patient_signature=in_document)
		insert(
			"Deleted Document",
			"_Test Sig Deleted",
			deleted_doctype=CLAIM,
			data=f'{{"patient_signature": "{in_deleted_document}"}}',
		)
		for pointer in (in_document, in_deleted_document, unused):
			os.utime(self.path(pointer), (0, 0))

		self.assertEqual(migration.prune(), [unused[4:]])
		self.assertTrue(os.path.exists(self.path(unused)))

		migration.prune(delete=True)
		self.assertFalse(os.path.exists(self.path(unused)))
		for pointer in (in_document, in_deleted_document, new):
			self.assertTrue(os.path.exists(self.path(pointer)))

	def test_verify_reports_missing_files(self):
		pointer = store(PNG)
		insert(CLAIM, "_Test Sig Claim 1", patient_signature=pointer)
		os.remove(self.path(pointer))

		missing = migration.verify()

		self.assertIn((CLAIM, "_Test Sig Claim 1", "patient_signature", pointer), missing)

	def get_claim_signatures(self):
		return frappe.get_all(
			CLAIM,
			filters={"name": ["like", "_Test Sig Claim%"]},
			pluck="patient_signature",
			order_by="name",
		)
