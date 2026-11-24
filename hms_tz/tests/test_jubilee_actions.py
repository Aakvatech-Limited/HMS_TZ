from contextlib import ExitStack
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.hms_tz.doctype.setup_status import setup_status
from hms_tz.hms_tz.doctype.setup_status.setup_status import get_setup_status
from hms_tz.jubilee.api import price_package
from hms_tz.tests.test_standard_records import create_for

COMPANY = "_Test Company"
SERVICE = "_Test Jubilee Lab Service"
PLAN = "Healthcare Insurance Coverage Plan"
JUBILEE_PLAN = "Jubilee Insurance - _TC"


class TestJubileeActions(FrappeTestCase):
	def setUp(self):
		frappe.delete_doc_if_exists("Setup Status", COMPANY)
		frappe.delete_doc_if_exists("HMS TZ Setting", COMPANY)
		frappe.db.set_single_value(
			"Healthcare Settings", {"collect_registration_fee": 0, "enable_free_follow_ups": 0}
		)
		frappe.get_doc({"doctype": "HMS TZ Setting", "company": COMPANY, "facility_code": "TEST"}).insert()
		create_for(COMPANY)
		frappe.db.delete("Jubilee Price Package", {"company": COMPANY})
		frappe.db.set_value(PLAN, {"company": COMPANY}, "price_list", None)
		self.patches = ExitStack()
		self.patches.enter_context(patch.object(frappe.db, "commit"))
		self.patches.enter_context(patch.object(price_package, "sleep"))
		self.addCleanup(self.patches.close)

	def status(self):
		status = get_setup_status(COMPANY)
		return (status.jubilee_prices_processed, status.jubilee_coverages_processed)

	def test_prices_set_the_company_jubilee_price_list_on_its_jubilee_plan(self):
		with patch.object(price_package, "get_packages_for_price_list", return_value=[]):
			price_package.process_jubilee_prices(COMPANY)
		self.assertEqual(frappe.db.get_value(PLAN, JUBILEE_PLAN, "price_list"), "Jubilee _TC")
		self.assertTrue(frappe.db.exists("Price List", "Jubilee _TC"))
		self.assertIsNone(frappe.db.get_value(PLAN, "NHIF - Standard - _TC", "price_list"))

	def test_coverages_go_only_to_the_company_jubilee_plans(self):
		frappe.get_doc(
			{"doctype": "Jubilee Price Package", "company": COMPANY, "itemcode": "JUB-1", "itemprice": 5000}
		).insert(ignore_permissions=True)
		services = {"JUB-1": [{"service_type": "Lab Test Template", "service_name": SERVICE}]}
		with patch.object(price_package, "get_insurance_items", return_value=services):
			price_package.process_jubilee_coverages(COMPANY)
		plans = frappe.get_all(
			"Healthcare Service Insurance Coverage",
			filters={"healthcare_service_template": SERVICE},
			pluck="healthcare_insurance_coverage_plan",
		)
		self.assertEqual(set(plans), {JUBILEE_PLAN})

	def test_each_processing_job_ticks_only_its_own_field(self):
		with patch.object(price_package, "process_jubilee_prices") as prices:
			price_package.run_jubilee_prices(COMPANY)
		prices.assert_called_once_with(COMPANY)
		self.assertEqual(self.status(), (1, 0))
		with patch.object(price_package, "process_jubilee_coverages") as coverages:
			price_package.run_jubilee_coverages(COMPANY)
		coverages.assert_called_once_with(COMPANY)
		self.assertEqual(self.status(), (1, 1))

	def test_a_tick_survives_a_setup_status_read_before_a_parallel_save(self):
		stale = get_setup_status(COMPANY)
		stale.modified = "2000-01-01 00:00:00"
		with patch.object(setup_status, "get_setup_status", return_value=stale):
			with patch.object(price_package, "process_jubilee_coverages"):
				price_package.run_jubilee_coverages(COMPANY)
		self.assertEqual(self.status(), (0, 1))

	def test_a_failed_coverage_run_does_not_tick(self):
		with patch.object(price_package, "process_jubilee_coverages", side_effect=frappe.ValidationError):
			with self.assertRaises(frappe.ValidationError):
				price_package.run_jubilee_coverages(COMPANY)
		self.assertEqual(self.status(), (0, 0))

	def test_process_records_queues_a_prices_job_and_a_coverages_job(self):
		with patch.object(price_package, "enqueue") as enqueue:
			price_package.process_jubilee_records(COMPANY)
		methods = [call.kwargs["method"] for call in enqueue.call_args_list]
		self.assertEqual(methods, [price_package.run_jubilee_prices, price_package.run_jubilee_coverages])
		self.assertTrue(all(call.kwargs["company"] == COMPANY for call in enqueue.call_args_list))
