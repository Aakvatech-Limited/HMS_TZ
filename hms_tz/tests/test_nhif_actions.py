from contextlib import ExitStack
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.hms_tz.doctype.setup_status.setup_status import get_setup_status
from hms_tz.nhif.nhif_api import price_package
from hms_tz.tests.test_standard_records import create_for

COMPANY = "_Test Company"
FACILITY = "TESTFAC"
SERVICE = "_Test NHIF Lab Service"
PLAN = "Healthcare Insurance Coverage Plan"


def get_plan(scheme_id):
	return frappe.db.get_value(PLAN, {"company": COMPANY, "nhif_scheme_id": scheme_id})


def add_package(scheme_id, item_code="NHIF-ITEM-1"):
	frappe.get_doc(
		{
			"doctype": "NHIF Price Package",
			"company": COMPANY,
			"facilitycode": FACILITY,
			"schemeid": scheme_id,
			"itemcode": item_code,
			"itemname": item_code,
			"unitprice": 5000,
		}
	).insert(ignore_permissions=True)


class TestNhifActions(FrappeTestCase):
	def setUp(self):
		frappe.delete_doc_if_exists("Setup Status", COMPANY)
		frappe.delete_doc_if_exists("HMS TZ Setting", COMPANY)
		frappe.db.set_single_value(
			"Healthcare Settings", {"collect_registration_fee": 0, "enable_free_follow_ups": 0}
		)
		frappe.get_doc({"doctype": "HMS TZ Setting", "company": COMPANY, "facility_code": FACILITY}).insert()
		create_for(COMPANY)
		frappe.db.delete("NHIF Price Package", {"company": COMPANY})
		frappe.db.set_value(PLAN, {"company": COMPANY}, "price_list", None)
		self.standard, self.student = "1001", "1005"
		self.patches = ExitStack()
		self.patches.enter_context(patch.object(frappe.db, "commit"))
		self.patches.enter_context(patch.object(price_package, "sleep"))
		self.addCleanup(self.patches.close)

	def coverage_plans(self):
		rows = frappe.get_all(
			"Healthcare Service Insurance Coverage",
			filters={"healthcare_service_template": SERVICE, "company": COMPANY},
			pluck="healthcare_insurance_coverage_plan",
		)
		return set(rows)

	def test_prices_set_each_scheme_price_list_on_its_plan(self):
		add_package(self.standard)
		add_package(self.student)
		with patch.object(price_package, "get_packages_for_price_list", return_value=[]):
			price_package.process_nhif_prices(COMPANY, FACILITY)
		for scheme_id in (self.standard, self.student):
			price_list = frappe.db.get_value(PLAN, get_plan(scheme_id), "price_list")
			self.assertEqual(price_list, f"NHIF-{scheme_id}-{FACILITY}")
			self.assertTrue(frappe.db.exists("Price List", price_list))
		self.assertIsNone(frappe.db.get_value(PLAN, get_plan("1002"), "price_list"))

	def test_coverages_go_only_to_the_plan_of_the_package_scheme(self):
		add_package(self.standard)
		services = {"NHIF-ITEM-1": [{"service_type": "Lab Test Template", "service_name": SERVICE}]}
		with patch.object(price_package, "get_insurance_items", return_value=services):
			price_package.process_nhif_coverages(COMPANY, FACILITY)
		self.assertEqual(self.coverage_plans(), {get_plan(self.standard)})

	def status(self):
		status = get_setup_status(COMPANY)
		return (status.nhif_prices_processed, status.nhif_coverages_processed)

	def test_each_processing_job_ticks_only_its_own_field(self):
		with patch.object(price_package, "process_nhif_prices") as prices:
			price_package.run_nhif_prices(COMPANY, FACILITY)
		prices.assert_called_once_with(COMPANY, FACILITY)
		self.assertEqual(self.status(), (1, 0))
		with patch.object(price_package, "process_nhif_coverages") as coverages:
			price_package.run_nhif_coverages(COMPANY, FACILITY)
		coverages.assert_called_once_with(COMPANY, FACILITY)
		self.assertEqual(self.status(), (1, 1))

	def test_a_failed_coverage_run_does_not_tick(self):
		with patch.object(price_package, "process_nhif_coverages", side_effect=frappe.ValidationError):
			with self.assertRaises(frappe.ValidationError):
				price_package.run_nhif_coverages(COMPANY, FACILITY)
		self.assertEqual(self.status(), (0, 0))

	def test_process_records_queues_a_prices_job_and_a_coverages_job(self):
		with patch.object(price_package, "enqueue") as enqueue:
			price_package.process_nhif_records(COMPANY)
		methods = [call.kwargs["method"] for call in enqueue.call_args_list]
		self.assertEqual(methods, [price_package.run_nhif_prices, price_package.run_nhif_coverages])
		for call in enqueue.call_args_list:
			self.assertEqual((call.kwargs["company"], call.kwargs["facility_code"]), (COMPANY, FACILITY))
