from contextlib import contextmanager

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.hms_tz.utils import make_item_price

ITEM = "_Test LRPMT Template Item"
ITEM_GROUP = "Laboratory"
RATE_FIELDS = {
	"Lab Test Template": "lab_test_rate",
	"Clinical Procedure Template": "rate",
	"Therapy Type": "rate",
	"Medication": "rate",
	"Radiology Examination Template": "rate",
}


def make_template(doctype, item_disabled=0, **values):
	frappe.get_doc(
		doctype="Item",
		item_code=ITEM,
		item_name=ITEM,
		item_group=ITEM_GROUP,
		stock_uom="Unit",
		is_stock_item=0,
		disabled=item_disabled,
	).insert()
	make_item_price(ITEM, "Standard Selling", 50)

	template = frappe.new_doc(doctype)
	template.update(
		{
			"name": ITEM,
			"item": ITEM,
			"lab_test_code": ITEM,
			"item_group": ITEM_GROUP,
			"lab_test_group": ITEM_GROUP,
			"stock_uom": "Unit",
			**values,
		}
	)
	template.db_insert()
	return frappe.get_doc(doctype, ITEM)


def save(template, **values):
	template.update({"change_in_item": 1, RATE_FIELDS[template.doctype]: 100, **values})
	template.flags.ignore_mandatory = True
	template.flags.ignore_links = True
	template.save()


def item_disabled():
	return frappe.db.get_value("Item", ITEM, "disabled")


@contextmanager
def rolled_back():
	try:
		yield
	finally:
		frappe.db.rollback()


class TestLRPMTTemplateItemDisabled(FrappeTestCase):
	def test_template_save_never_disables_item(self):
		for doctype in RATE_FIELDS:
			for is_billable in (0, 1):
				with self.subTest(doctype=doctype, is_billable=is_billable), rolled_back():
					template = make_template(doctype, is_billable=is_billable)

					save(template)
					self.assertEqual(item_disabled(), 0)

					save(template, disabled=1)
					self.assertEqual(item_disabled(), 0)

	def test_template_save_keeps_manually_disabled_item(self):
		for doctype in RATE_FIELDS:
			with self.subTest(doctype=doctype), rolled_back():
				template = make_template(doctype, item_disabled=1, is_billable=1)

				save(template)
				self.assertEqual(item_disabled(), 1)
