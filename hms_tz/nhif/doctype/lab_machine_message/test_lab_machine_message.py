# Copyright (c) 2021, Aakvatech and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.doctype.lab_machine_message.lab_machine_message import get_hl7_field

RESULT = "\n".join(
	[
		"MSH|^~\\&|Mindray|BC-5380|||20261114101500||ORU^R01|1|P|2.3.1",
		"PID|1||PAT1",
		"PV1|1",
		"OBR|1||LT-0001|00001^Automated Count^99MRC",
		"OBX|1|NM|6690-2^WBC^LN||7.2|10*3/uL|||||F",
	]
)
QUERY = "\n".join(
	[
		"MSH|^~\\&|Mindray|BS-230|||20261114101500||QRY^Q02|1|P|2.3.1",
		"QRD|20261114101500|R|D|1|||RD|S1|OTH|||T",
		"QRF||||||RCT|COR|ALL||",
	]
)


class TestLabMachineMessage(FrappeTestCase):
	def test_result_fields(self):
		doc = frappe.get_doc({"doctype": "Lab Machine Message", "message": RESULT})
		doc.set_missing_fields()
		self.assertEqual(doc.machine_make, "Mindray")
		self.assertEqual(doc.machine_model, "BC-5380")
		self.assertEqual(doc.lab_test_name, "LT-0001")

	def test_short_message_does_not_raise(self):
		doc = frappe.get_doc({"doctype": "Lab Machine Message", "message": QUERY})
		doc.set_missing_fields()
		self.assertEqual(doc.machine_model, "BS-230")
		self.assertIsNone(doc.lab_test_name)
		self.assertIsNone(doc.sample_collection)

	def test_get_hl7_field(self):
		lines = ["A|B|C", "X"]
		self.assertEqual(get_hl7_field(lines, 0, 2), "C")
		self.assertIsNone(get_hl7_field(lines, 0, 3))
		self.assertIsNone(get_hl7_field(lines, 1, 1))
		self.assertIsNone(get_hl7_field(lines, 5, 0))
