import json

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.doctype.nhif_stg.nhif_stg import get_moh_stg, validate_moh_stg

COMPANY = "Wind Power LLC"
MEDICATION = "_Test STG Medication"


def set_stg_settings(show=1, enforce=0):
	frappe.db.set_value(
		"HMS TZ Setting",
		COMPANY,
		{"show_stg_on_patient_encounter": show, "enforce_stg_on_patient_encounter": enforce},
	)
	frappe.clear_document_cache("HMS TZ Setting", COMPANY)


def add_stg(code_value, stg_type, service_type, service_name, disabled=0):
	frappe.get_doc(
		doctype="NHIF STG",
		stg_type=stg_type,
		code=code_value.split(" ")[1],
		code_value=code_value,
		item_code="STG",
		service_type=service_type,
		service_name=service_name,
		disabled=disabled,
	).insert()


def get_lab_row(lab):
	"""A lab is a template name, or (template name, diagnosis code) for its medical_code."""
	if isinstance(lab, str):
		return {"lab_test_code": lab}
	return {"lab_test_code": lab[0], "medical_code": f"{lab[1]}\n Demo definition"}


def make_encounter(preliminary=(), final=(), labs=(), drugs=(), insurance_company="NHIF"):
	return frappe.get_doc(
		{
			"doctype": "Patient Encounter",
			"company": COMPANY,
			"insurance_company": insurance_company,
			"patient_encounter_preliminary_diagnosis": [{"code_value": code} for code in preliminary],
			"patient_encounter_final_diagnosis": [{"code_value": code} for code in final],
			"lab_test_prescription": [get_lab_row(lab) for lab in labs],
			"drug_prescription": [{"drug_code": drug} for drug in drugs],
		}
	)


class TestNHIFSTGEncounter(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.db.delete("NHIF STG")
		if not frappe.db.exists("HMS TZ Setting", COMPANY):
			frappe.get_doc(
				doctype="HMS TZ Setting", name=COMPANY, company=COMPANY, facility_code="T1"
			).db_insert()

		frappe.get_doc(doctype="Code System", code_system="ICD-10", uri="http://test.local/icd").insert(
			ignore_if_duplicate=True
		)
		for code in ("ZSE1", "ZSE2", "ZSE3", "ZS4.1"):
			frappe.get_doc(doctype="Code Value", code_system="ICD-10", code_value=code).insert(
				ignore_if_duplicate=True
			)

		cls.lab_in_stg, cls.lab_not_in_stg = frappe.get_all("Lab Test Template", pluck="name", limit=2)
		cls.drug_item = frappe.get_all("Item", pluck="name", limit=1)[0]
		if not frappe.db.exists("Medication", MEDICATION):
			frappe.get_doc(
				doctype="Medication", name=MEDICATION, generic_name=MEDICATION, item=cls.drug_item
			).db_insert()

		add_stg("ICD-10 ZSE1", "Diagnosis", "Lab Test Template", cls.lab_in_stg)
		add_stg("ICD-10 ZSE2", "Treatment", "Medication", MEDICATION)
		add_stg("ICD-10 ZSE3", "Diagnosis", "Lab Test Template", cls.lab_not_in_stg, disabled=1)
		add_stg("ICD-10 ZS4.1", "Diagnosis", "Lab Test Template", cls.lab_in_stg)

	def setUp(self):
		set_stg_settings(show=1, enforce=0)

	def test_lists_stg_of_preliminary_and_final_diagnoses(self):
		encounter = make_encounter(
			preliminary=["ICD-10 ZSE1"],
			final=["ICD-10 ZSE2"],
			labs=[self.lab_in_stg, self.lab_not_in_stg],
		)

		data = get_moh_stg(json.dumps(encounter.as_dict(), default=str))

		self.assertEqual(
			[(row.code_value, row.stg_type, row.service_name) for row in data["stg"]],
			[
				("ICD-10 ZSE1", "Diagnosis", self.lab_in_stg),
				("ICD-10 ZSE2", "Treatment", MEDICATION),
			],
		)
		self.assertEqual(data["not_in_stg"], [self.lab_not_in_stg])
		self.assertEqual(data["codes_not_in_stg"], [])

	def test_matches_stg_by_exact_code_value_only(self):
		encounter = make_encounter()
		encounter.append(
			"patient_encounter_final_diagnosis",
			{"code_value": "ICD-10 ZS41", "code": "ZS41", "definition": "Demo adenoids"},
		)

		data = get_moh_stg(json.dumps(encounter.as_dict(), default=str))

		self.assertEqual(data["stg"], [])
		self.assertEqual(data["codes_not_in_stg"], ["ICD-10 ZS41"])

	def test_no_diagnosis_lists_every_selected_service_as_not_in_stg(self):
		data = get_moh_stg(json.dumps(make_encounter(labs=[self.lab_in_stg]).as_dict(), default=str))

		self.assertEqual(data, {"stg": [], "codes_not_in_stg": [], "not_in_stg": [self.lab_in_stg]})

	def test_service_of_code_without_stg_is_listed_as_not_in_stg(self):
		encounter = make_encounter(final=["ICD-10 ZSE3"], labs=[(self.lab_not_in_stg, "ICD-10 ZSE3")])

		data = get_moh_stg(json.dumps(encounter.as_dict(), default=str))

		self.assertEqual(data["stg"], [])
		self.assertEqual(data["codes_not_in_stg"], ["ICD-10 ZSE3"])
		self.assertEqual(data["not_in_stg"], [self.lab_not_in_stg])

	def test_shown_for_every_patient_and_hidden_when_setting_is_off(self):
		encounter = make_encounter(final=["ICD-10 ZSE1"], insurance_company="Jubilee Insurance")
		self.assertEqual(len(get_moh_stg(json.dumps(encounter.as_dict(), default=str))["stg"]), 1)

		encounter = make_encounter(final=["ICD-10 ZSE1"], insurance_company=None)
		self.assertEqual(len(get_moh_stg(json.dumps(encounter.as_dict(), default=str))["stg"]), 1)

		set_stg_settings(show=0)
		self.assertIsNone(get_moh_stg(json.dumps(encounter.as_dict(), default=str)))

	def test_enforce_blocks_submit_for_service_not_in_stg(self):
		set_stg_settings(show=1, enforce=1)
		encounter = make_encounter(final=["ICD-10 ZSE1"], labs=[self.lab_in_stg, self.lab_not_in_stg])

		with self.assertRaisesRegex(frappe.ValidationError, "not in the MOH STG"):
			validate_moh_stg(encounter)

	def test_enforce_allows_services_in_stg_including_drug_through_medication(self):
		set_stg_settings(show=1, enforce=1)
		encounter = make_encounter(
			preliminary=["ICD-10 ZSE1"], final=["ICD-10 ZSE2"], labs=[self.lab_in_stg], drugs=[self.drug_item]
		)

		validate_moh_stg(encounter)

	def test_enforce_blocks_service_whose_code_has_no_stg(self):
		set_stg_settings(show=1, enforce=1)
		encounter = make_encounter(final=["ICD-10 ZSE3"], labs=[(self.lab_not_in_stg, "ICD-10 ZSE3")])

		with self.assertRaisesRegex(frappe.ValidationError, "not in the MOH STG"):
			validate_moh_stg(encounter)

	def test_no_enforce_allows_service_not_in_stg(self):
		validate_moh_stg(make_encounter(final=["ICD-10 ZSE1"], labs=[self.lab_not_in_stg]))
