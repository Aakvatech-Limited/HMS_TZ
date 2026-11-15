# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.jubilee.doctype.jubilee_patient_claim import jubilee_patient_claim
from hms_tz.nhif.doctype.nhif_patient_claim import nhif_patient_claim


class TestClaimFolioNumber(FrappeTestCase):
	def test_folio_number_is_set_once_without_a_separate_write(self):
		for doctype, module in (
			("NHIF Patient Claim", nhif_patient_claim),
			("Jubilee Patient Claim", jubilee_patient_claim),
		):
			with self.subTest(doctype=doctype):
				claim = frappe.new_doc(doctype)
				with (
					patch.object(module, "get_or_create_folio_counter", return_value=12) as counter,
					patch.object(type(claim), "db_set") as db_set,
				):
					claim.set_folio_count()
					claim.set_folio_count()

				self.assertEqual(claim.folio_no, 12)
				counter.assert_called_once()
				db_set.assert_not_called()
