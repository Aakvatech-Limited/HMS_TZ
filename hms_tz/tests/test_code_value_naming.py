import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.nhif_api.reference import create_medical_code, update_medical_code


class TestCodeValueNaming(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.get_doc(doctype="Code System", code_system="_Test ICD", uri="http://test.local/icd").insert(
			ignore_if_duplicate=True
		)

	def test_name_is_code_system_then_code_value(self):
		code_value = frappe.get_doc(
			doctype="Code Value", code_system="_Test ICD", code_value="Z94.4"
		).insert()

		self.assertEqual(code_value.name, "_Test ICD Z94.4")

	def test_nhif_disease_sync_finds_created_code_value(self):
		disease = {"ICDVersionCode": "_Test ICD", "DiseaseCode": "Z94.5", "DiseaseName": "Old name"}
		create_medical_code(disease)

		update_medical_code({**disease, "DiseaseName": "New name"})

		self.assertEqual(frappe.db.get_value("Code Value", "_Test ICD Z94.5", "definition"), "New name")
