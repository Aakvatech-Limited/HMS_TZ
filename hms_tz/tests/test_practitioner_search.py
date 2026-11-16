import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.api.practitioner import search_practitioners
from hms_tz.tests.utils import insert

ACTIVE = "_Test Search Practitioner"
DISABLED = "_Test Search Practitioner Old"


class TestPractitionerSearch(FrappeTestCase):
	def setUp(self):
		insert(
			"Healthcare Practitioner",
			ACTIVE,
			practitioner_name="Search Doctor",
			status="Active",
			department="_Test Search Department 7731",
			nhif_physician_qualification="_Test Qualification",
			tz_mct_code="_TMCT7731",
		)
		insert(
			"Healthcare Practitioner",
			DISABLED,
			practitioner_name="Search Doctor Old",
			status="Disabled",
			tz_mct_code="_TMCT7731-OLD",
		)

	def tearDown(self):
		frappe.db.rollback()

	def test_search_matches_name_department_and_mct_code_of_active_practitioners(self):
		for txt in (ACTIVE, "Search Department 7731", "_TMCT7731"):
			self.assertEqual([row.value for row in search_practitioners(txt)], [ACTIVE])

	def test_search_returns_department_and_nhif_details(self):
		row = search_practitioners("_TMCT7731")[0]

		self.assertEqual(
			(row.practitioner_name, row.department, row.nhif_physician_qualification, row.tz_mct_code),
			("Search Doctor", "_Test Search Department 7731", "_Test Qualification", "_TMCT7731"),
		)
