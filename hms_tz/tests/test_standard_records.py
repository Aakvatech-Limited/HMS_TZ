import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.hms_tz.standard_records.standard_records import (
	INSURERS_FILE,
	PLANS_FILE,
	STANDARD_RECORDS,
	StandardRecords,
	get_schedule_values,
	get_standard_record_steps,
	load_records,
)


class FakeProgress:
	def __init__(self):
		self.total = self.done = self.added = 0

	def set_total(self, total):
		self.total = total

	def advance(self, count=1, added=0):
		self.done += count
		self.added += added


def create_for(company):
	"""Run every standard group the way the setup runner does; return each group's result and progress."""
	results = {}
	for group in STANDARD_RECORDS:
		progress = FakeProgress()
		result = StandardRecords(company, progress).create(group["doctype"])
		results[group["doctype"]] = (result, progress.done, progress.total, progress.added)
	return results


class TestStandardRecordFiles(FrappeTestCase):
	def test_nhif_plans_have_unique_names_and_scheme_ids_without_a_branch(self):
		nhif = [plan for plan in load_records(PLANS_FILE) if plan["insurance_company"] == "NHIF Insurance"]
		self.assertTrue(nhif)
		self.assertEqual(len({plan["coverage_plan_name"] for plan in nhif}), len(nhif))
		self.assertEqual(len({plan["nhif_scheme_id"] for plan in nhif}), len(nhif))
		self.assertFalse([plan for plan in nhif if "Mwanza" in plan["coverage_plan_name"]])

	def test_every_nhif_plan_scheme_is_a_standard_nhif_scheme(self):
		schemes = {row["scheme_id"] for row in load_records("nhif_schemes.json")}
		plan_schemes = {
			plan["nhif_scheme_id"] for plan in load_records(PLANS_FILE) if plan.get("nhif_scheme_id")
		}
		self.assertEqual(plan_schemes - schemes, set())

	def test_other_insurers_have_one_plan_without_scheme_id(self):
		others = [plan for plan in load_records(PLANS_FILE) if plan["insurance_company"] != "NHIF Insurance"]
		self.assertEqual(len(others), 5)
		self.assertFalse([plan for plan in others if plan.get("nhif_scheme_id")])

	def test_every_plan_belongs_to_a_listed_insurer(self):
		insurers = {row["insurance_company_name"] for row in load_records(INSURERS_FILE)}
		self.assertEqual(len(insurers), 6)
		self.assertTrue({plan["insurance_company"] for plan in load_records(PLANS_FILE)} <= insurers)

	def test_service_unit_types_use_standard_ward_types(self):
		ward_types = {row["ward_type_name"] for row in load_records("ward_types.json")}
		used = {row["ward_type"] for row in load_records("service_unit_types.json")}
		self.assertEqual(used - ward_types, set())

	def test_direct_cash_visit_type_id_is_one(self):
		visits = {row["appointment_type"]: row for row in load_records("visit_types.json")}
		self.assertEqual(visits["Direct Cash"]["visit_type_id"], "1")

	def test_schedule_hours_become_hourly_time_slots(self):
		values = get_schedule_values(
			{
				"schedule_name": "Test",
				"slot_minutes": 60,
				"hours": [{"days": ["Monday", "Saturday"], "from_time": "08:00:00", "to_time": "10:30:00"}],
			}
		)
		slots = [(slot["day"], str(slot["from_time"]), str(slot["to_time"])) for slot in values["time_slots"]]
		self.assertEqual(
			slots[:3],
			[
				("Monday", "08:00:00", "09:00:00"),
				("Monday", "09:00:00", "10:00:00"),
				("Monday", "10:00:00", "10:30:00"),
			],
		)
		self.assertEqual(len(slots), 6)


class TestStandardRecordCreation(FrappeTestCase):
	def setUp(self):
		self.plans = load_records(PLANS_FILE)
		self.first_nhif_plan = next(plan for plan in self.plans if plan.get("nhif_scheme_id"))

	def test_each_group_is_its_own_runner_step(self):
		steps = get_standard_record_steps()
		self.assertEqual(
			[step["kwargs"]["doctype"] for step in steps], [group["doctype"] for group in STANDARD_RECORDS]
		)
		self.assertEqual(steps[0]["label"], "Ward types")
		self.assertFalse([step for step in steps if step["needs_rooms"]])

	def test_each_group_reports_its_size_and_full_progress(self):
		results = create_for("_Test Company")
		visits = len(load_records("visit_types.json"))
		self.assertEqual(results["Appointment Type"][0], f"{visits} visit types")
		self.assertEqual(
			results["Healthcare Insurance Coverage Plan"][0], f"{len(self.plans)} coverage plans"
		)
		for _result, done, total, _added in results.values():
			self.assertEqual(done, total)

	def test_company_records_carry_the_company_abbreviation(self):
		create_for("_Test Company")
		self.assertTrue(frappe.db.exists("Healthcare Insurance Company", "NHIF Insurance - _TC"))
		plan = frappe.db.get_value(
			"Healthcare Insurance Coverage Plan",
			f"{self.first_nhif_plan['coverage_plan_name']} - _TC",
			["insurance_company", "nhif_scheme_id", "company"],
			as_dict=True,
		)
		expected = {"insurance_company": "NHIF Insurance - _TC", "company": "_Test Company"}
		self.assertEqual(plan, {**expected, "nhif_scheme_id": self.first_nhif_plan["nhif_scheme_id"]})
		self.assertEqual(
			frappe.db.get_value("Healthcare Insurance Company", "Jubilee Insurance - _TC", "customer"),
			"Jubilee Insurance - _TC",
		)
		self.assertTrue(frappe.db.exists("Practitioner Schedule", "Weekdays and Saturday"))

	def test_running_again_adds_nothing(self):
		create_for("_Test Company")
		count = frappe.db.count("Healthcare Insurance Coverage Plan", {"company": "_Test Company"})
		results = create_for("_Test Company")
		self.assertEqual(
			frappe.db.count("Healthcare Insurance Coverage Plan", {"company": "_Test Company"}), count
		)
		self.assertEqual({doctype: result[3] for doctype, result in results.items() if result[3]}, {})

	def test_running_again_keeps_manual_edits_and_adds_back_deleted_records(self):
		create_for("_Test Company")
		frappe.db.set_value("Appointment Type", "Direct Cash", "visit_type_id", "99")
		frappe.delete_doc(
			"Healthcare Card Verifier", load_records("card_verifiers.json")[-1]["card_type_name"]
		)
		results = create_for("_Test Company")
		self.assertEqual(frappe.db.get_value("Appointment Type", "Direct Cash", "visit_type_id"), "99")
		self.assertEqual(
			{doctype: result[3] for doctype, result in results.items() if result[3]},
			{"Healthcare Card Verifier": 1},
		)

	def test_a_second_company_gets_its_own_insurers_and_plans(self):
		create_for("_Test Company")
		create_for("_Test Company 1")
		self.assertEqual(frappe.db.count("Healthcare Insurance Company", {"company": "_Test Company 1"}), 6)
		plan_name = f"{self.first_nhif_plan['coverage_plan_name']} - _TC1"
		self.assertTrue(frappe.db.exists("Healthcare Insurance Coverage Plan", plan_name))

	def test_missing_company_accounts_stop_the_insurers_step(self):
		frappe.db.set_value("Company", "_Test Company 2", "write_off_account", None)
		frappe.clear_document_cache("Company", "_Test Company 2")
		with self.assertRaises(frappe.ValidationError):
			StandardRecords("_Test Company 2", FakeProgress()).create("Healthcare Insurance Company")
		frappe.clear_document_cache("Company", "_Test Company 2")
