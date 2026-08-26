# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


from frappe.model.document import Document

from hms_tz.hms_tz.utils import create_item_from_doc, on_trash_doc_having_item_reference, update_item_from_doc


class RadiologyExaminationTemplate(Document):
	def validate(self):
		update_item_from_doc(self, self.procedure_name)

	def after_insert(self):
		create_item_from_doc(self, self.procedure_name)

	def on_trash(self):
		on_trash_doc_having_item_reference(self)
