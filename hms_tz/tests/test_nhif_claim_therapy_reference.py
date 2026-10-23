import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.api.healthcare_utils import get_approval_number_from_LRPMT

PLAN = "_Test NHIF Therapy Plan"
CHILD = "_test_therapy_row"


def make_session(reference_no, creation, plan=PLAN, childname=CHILD, docstatus=1):
	frappe.get_doc(
		doctype="Therapy Session",
		name=frappe.generate_hash(),
		patient="_Test NHIF Patient",
		therapy_plan=plan,
		hms_tz_ref_childname=childname,
		service_reference_no=reference_no,
		docstatus=docstatus,
		creation=creation,
	).db_insert()


class TestNHIFClaimTherapyReference(FrappeTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_joins_session_references_in_creation_order(self):
		make_session("SR-2", "2026-01-06 10:00:00")
		make_session("SR-1", "2026-01-05 10:00:00")

		self.assertEqual(
			get_approval_number_from_LRPMT("Therapy Plan", PLAN, ref_childname=CHILD), "SR-1,SR-2"
		)

	def test_skips_cancelled_unissued_and_other_rows(self):
		make_session("SR-1", "2026-01-05 10:00:00")
		make_session("SR-CANCELLED", "2026-01-06 10:00:00", docstatus=2)
		make_session(None, "2026-01-07 10:00:00")
		make_session("SR-OTHER-ROW", "2026-01-08 10:00:00", childname="_other_row")
		make_session("SR-OTHER-PLAN", "2026-01-09 10:00:00", plan="_Other Plan")

		self.assertEqual(get_approval_number_from_LRPMT("Therapy Plan", PLAN, ref_childname=CHILD), "SR-1")

	def test_claim_item_gets_therapy_session_references(self):
		make_session("SR-1", "2026-01-05 10:00:00")
		make_session("SR-2", "2026-01-06 10:00:00")
		claim = frappe.new_doc("NHIF Patient Claim")
		hsr_row = frappe._dict(
			insurance_company="NHIF",
			percent_covered=100,
			service_name="Physiotherapy",
			qty=2,
			lrpmt_status="Submitted",
			lrpmt_doctype="Therapy Plan",
			lrpmt_docname=PLAN,
			ref_doctype="Therapy Plan Detail",
			ref_docname=CHILD,
		)

		claim.add_LRPMT_claim_item(hsr_row, frappe._dict())

		self.assertEqual(claim.nhif_patient_claim_item[0].approval_ref_no, "SR-1,SR-2")
