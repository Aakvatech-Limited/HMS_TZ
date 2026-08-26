# Copyright (c) 2026, Aakvatech and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import random_string


class SurgicalSpecimen(Document):
	def before_insert(self):
		self.generate_barcode()

	def generate_barcode(self):
		"""Auto-generate a unique barcode for the specimen."""
		if not self.barcode:
			self.barcode = f"SPEC-{random_string(10).upper()}"
