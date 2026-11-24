import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.hms_tz.doctype.setup_status.foundation import get_insurance_accounts
from hms_tz.tests.test_standard_records import add_insurance_accounts

INSURER = "_Test Naming Insurer"


def new_insurer(name=INSURER, company="_Test Company"):
	add_insurance_accounts(company)
	return frappe.get_doc(
		{
			"doctype": "Healthcare Insurance Company",
			"insurance_company_name": name,
			"company": company,
			**get_insurance_accounts(company),
		}
	)


class TestInsuranceCompanyName(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Healthcare Insurance Company", {"insurance_company_name": ["like", f"{INSURER}%"]})

	def test_a_new_insurer_is_named_with_its_company_abbreviation(self):
		self.assertEqual(new_insurer().insert().name, f"{INSURER} - _TC")
		self.assertEqual(new_insurer(company="_Test Company 1").insert().name, f"{INSURER} - _TC1")

	def test_a_name_that_already_ends_with_the_abbreviation_is_kept(self):
		self.assertEqual(new_insurer(f"{INSURER} - _TC").insert().name, f"{INSURER} - _TC")

	def test_a_second_insurer_with_the_same_name_is_refused(self):
		new_insurer().insert()
		with self.assertRaisesRegex(frappe.DuplicateEntryError, "already has an insurance company named"):
			new_insurer().insert()

	def test_an_insurer_needs_a_company_for_its_name(self):
		insurer = new_insurer()
		insurer.company = None
		with self.assertRaisesRegex(frappe.ValidationError, "Set the Company"):
			insurer.autoname()

	def test_an_explicit_name_is_kept(self):
		self.assertEqual(new_insurer().insert(set_name=f"{INSURER} Standard").name, f"{INSURER} Standard")

	def test_editing_an_existing_insurer_keeps_its_name(self):
		insurer = new_insurer().insert(set_name=f"{INSURER} HIC-0001")
		insurer.insurance_company_name = f"{INSURER} Renamed"
		insurer.save()
		self.assertEqual(insurer.name, f"{INSURER} HIC-0001")
		self.assertTrue(frappe.db.exists("Healthcare Insurance Company", f"{INSURER} HIC-0001"))
