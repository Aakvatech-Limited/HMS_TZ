import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.csvutils import to_csv

from hms_tz.api.setup_records import (
	get_company_records,
	get_screen_fields,
	import_company_records,
	save_company_record,
)
from hms_tz.hms_tz.doctype.setup_status.foundation import get_insurance_accounts
from hms_tz.hms_tz.doctype.setup_status.setup_status import get_setup_status
from hms_tz.tests.test_standard_records import add_insurance_accounts

SCREEN = "insurance_companies"
COMPANY = "_Test Company"
INSURER = "_Test Setup Insurer"
STEP = "Healthcare Insurance Company"
ACCOUNT_FIELDS = (
	"billed_but_not_claimed_account",
	"approved_claim_receivable_account",
	"rejected_claims_account",
)


class TestSetupInsuranceCompanies(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Healthcare Insurance Company", {"insurance_company_name": ["like", f"{INSURER}%"]})
		frappe.delete_doc_if_exists("Setup Status", COMPANY)
		frappe.delete_doc_if_exists("HMS TZ Setting", COMPANY)
		frappe.db.set_single_value(
			"Healthcare Settings", {"collect_registration_fee": 0, "enable_free_follow_ups": 0}
		)
		frappe.get_doc({"doctype": "HMS TZ Setting", "company": COMPANY, "facility_code": "TEST"}).insert()
		add_insurance_accounts(COMPANY)
		self.accounts = get_insurance_accounts(COMPANY)
		self.labels = {field["fieldname"]: field["label"] for field in get_screen_fields(SCREEN)["fields"]}
		get_company_records(SCREEN, COMPANY)

	def insurer_values(self, name=INSURER, **values):
		return {"insurance_company_name": name, **self.accounts, **values}

	def save(self, values, name=None):
		return save_company_record(SCREEN, COMPANY, frappe.as_json(values), name=name)

	def insurer_names(self):
		records = get_company_records(SCREEN, COMPANY)["records"]
		return {record.insurance_company_name for record in records}

	def upload(self, *rows):
		header = [self.labels[fieldname] for fieldname in ("insurance_company_name", *ACCOUNT_FIELDS)]
		content = to_csv([header, *[list(row) for row in rows]])
		file = frappe.get_doc(
			{"doctype": "File", "file_name": "insurers.csv", "content": content, "is_private": 1}
		)
		return file.insert().file_url

	def test_insurer_fields_hold_the_accounts_and_insurer_settings(self):
		screen = get_screen_fields(SCREEN)
		fields = {field["fieldname"]: field for field in screen["fields"]}
		self.assertEqual(screen["plural_label"], "insurance companies")
		for fieldname in ACCOUNT_FIELDS:
			self.assertEqual(fields[fieldname]["reqd"], 1)
			self.assertIn("eval: doc.company", fields[fieldname]["link_filters"])
		for fieldname in ("default_price_list", "no_of_days_for_follow_up", "disabled"):
			self.assertIn(fieldname, fields)
		self.assertNotIn("company", fields)
		self.assertNotIn("facility_code", fields)

	def test_a_new_insurer_gets_the_company_and_a_customer_and_ticks_the_step(self):
		name = self.save(self.insurer_values(no_of_days_for_follow_up=7))
		insurer = frappe.get_doc("Healthcare Insurance Company", name)
		self.assertEqual((insurer.company, insurer.no_of_days_for_follow_up), (COMPANY, 7))
		self.assertTrue(insurer.customer)
		self.assertTrue(get_setup_status(COMPANY).get_step(STEP).completed)
		self.assertIn(INSURER, self.insurer_names())

	def test_an_insurer_can_be_switched_off_and_on_again(self):
		name = self.save(self.insurer_values())
		self.save(self.insurer_values(disabled=1, company="_Test Company 1"), name=name)
		insurer = frappe.get_doc("Healthcare Insurance Company", name)
		self.assertEqual((insurer.disabled, insurer.company), (1, COMPANY))
		self.save(self.insurer_values(disabled=0), name=name)
		self.assertEqual(frappe.db.get_value("Healthcare Insurance Company", name, "disabled"), 0)

	def test_an_insurer_needs_its_accounts(self):
		with self.assertRaisesRegex(frappe.ValidationError, self.labels["rejected_claims_account"]):
			self.save(self.insurer_values(rejected_claims_account=None))

	def test_another_company_insurer_is_not_changed(self):
		other = frappe.db.get_value("Healthcare Insurance Company", {"company": ["!=", COMPANY]})
		self.assertTrue(other)
		with self.assertRaisesRegex(frappe.ValidationError, "is not one of the insurance companies of"):
			self.save(self.insurer_values(), name=other)

	def test_insurers_stay_locked_until_settings_are_complete(self):
		frappe.db.set_value("HMS TZ Setting", COMPANY, "enable_nhif_api", 1)
		self.assertFalse(get_company_records(SCREEN, COMPANY)["settings_complete"])
		with self.assertRaises(frappe.ValidationError):
			self.save(self.insurer_values())

	def test_import_adds_insurers_reports_bad_rows_and_changes_them_again(self):
		accounts = [self.accounts[fieldname] for fieldname in ACCOUNT_FIELDS]
		rows = [(f"{INSURER} A", *accounts), (f"{INSURER} B", "No Such Account", *accounts[1:])]
		result = import_company_records(SCREEN, COMPANY, self.upload(*rows))
		self.assertEqual(result["added"], 1)
		self.assertEqual([error["row"] for error in result["errors"]], [3])
		self.assertIn("No Such Account", result["errors"][0]["message"])
		result = import_company_records(SCREEN, COMPANY, self.upload(rows[0]))
		self.assertEqual((result["added"], result["changed"], result["errors"]), (0, 1, []))
		self.assertEqual(
			frappe.db.count("Healthcare Insurance Company", {"insurance_company_name": f"{INSURER} A"}), 1
		)
