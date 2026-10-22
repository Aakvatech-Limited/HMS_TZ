import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.report.itemwise_hospital_revenue.itemwise_hospital_revenue import (
	get_insurance_ipd_beds_data,
)

COMPANY = "_Test IWR Company"
INPATIENT_RECORD = "_Test IWR Inpatient Record"
SERVICE_UNIT_TYPE = "_Test IWR Bed Type"
SERVICE_UNIT = "_Test IWR Bed"


def insert(doctype, name, **values):
	doc = frappe.new_doc(doctype)
	doc.update({"name": name, **values})
	doc.db_insert()


def insert_bed(check_in):
	insert(
		"Inpatient Occupancy",
		frappe.generate_hash(),
		parent=INPATIENT_RECORD,
		parenttype="Inpatient Record",
		parentfield="inpatient_occupancies",
		service_unit=SERVICE_UNIT,
		check_in=check_in,
		amount=30000,
		is_confirmed=1,
	)


class TestItemwiseHospitalRevenue(FrappeTestCase):
	def setUp(self):
		insert(
			"Inpatient Record",
			INPATIENT_RECORD,
			company=COMPANY,
			insurance_coverage_plan="_Test IWR Plan",
		)
		insert("Healthcare Service Unit Type", SERVICE_UNIT_TYPE, item_group="Services")
		insert("Healthcare Service Unit", SERVICE_UNIT, service_unit_type=SERVICE_UNIT_TYPE)

	def tearDown(self):
		frappe.db.rollback()

	def test_insurance_bed_later_on_to_date_is_included(self):
		insert_bed("2026-01-06 10:00:00")
		insert_bed("2026-01-07 00:00:00")
		filters = frappe._dict(company=COMPANY, from_date="2026-01-06", to_date="2026-01-06")

		beds = get_insurance_ipd_beds_data(filters, appoints=[])

		self.assertEqual([str(bed.date) for bed in beds], ["2026-01-06"])
