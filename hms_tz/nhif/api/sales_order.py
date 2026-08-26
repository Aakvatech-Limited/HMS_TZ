import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.query_builder.functions import CombineDatetime
from frappe.utils import nowdate

from hms_tz.nhif.api.healthcare_utils import msgThrow


def validate(doc, method):
	for item in doc.items:
		validate_stock_item(item, doc.set_warehouse, method)


def before_submit(doc, method):
	if doc.med_change_request_status == "Pending":
		frappe.throw(
			f"This sales order has pending medication change request. \
                Please inform the doctor: <b>{doc.healthcare_practitioner}</b> \
                    to approve the request."
		)

	for item in doc.items:
		validate_stock_item(item, doc.set_warehouse, method)


def create_sales_order(doc, method):
	if doc.mode_of_payment and doc.inpatient_record:
		return

	company_details = frappe.get_cached_value(
		"HMS TZ Setting",
		doc.company,
		[
			"auto_create_sales_order_from_encounter",
			"sales_order_opd_pharmacy",
			"sales_order_ipd_pharmacy",
		],
		as_dict=True,
	)
	if not company_details or company_details.auto_create_sales_order_from_encounter == 0:
		return

	if not company_details.sales_order_opd_pharmacy and not company_details.sales_order_ipd_pharmacy:
		frappe.throw(
			f"Please set Sales Order OPD Pharmacy or \
                Sales Order IPD Pharmacy in Company: {doc.company}"
		)

	warehouse = ""
	if doc.inpatient_record:
		warehouse = company_details.sales_order_ipd_pharmacy
	else:
		warehouse = company_details.sales_order_opd_pharmacy

	drug_items, lrpt_items = get_items_from_encounter(doc, warehouse)
	if len(drug_items) > 0:
		drug_order_name = create_sales_order_from_encounter(
			doc, drug_items, warehouse, allow_md_change_request=True
		)
		if drug_order_name:
			frappe.msgprint("<b>Sales Order for Drug Items created Successfully</b>")

	if len(lrpt_items) > 0:
		lrpt_order_name = create_sales_order_from_encounter(doc, lrpt_items, warehouse)
		if lrpt_order_name:
			frappe.msgprint(
				"<b>Sales Order for Lab/Radiology/Procedure/Therapy \
                    Items created Successfully</b>"
			)


def get_items_from_encounter(doc, warehouse):
	drug_items = []
	lrpt_items = []
	for field in get_childs_map():
		for row in doc.get(field.get("table")):
			if row.prescribe == 0 or row.is_not_available_inhouse == 1 or row.is_cancelled == 1:
				continue

			item_code = frappe.get_cached_value(
				field.get("template"), row.get(field.get("item_field")), "item"
			)
			if not item_code:
				frappe.throw(
					_(
						f"The Item Code for {row.get(field.get('item_field'))} \
                        is not found!<br> Please request administrator to set \
                        item code in {row.get(field.get('item_field'))}."
					)
				)

			item_name, item_description = frappe.get_cached_value(
				"Item", item_code, ["item_name", "description"]
			)

			new_row = {
				"item_code": item_code,
				"item_name": item_name,
				"description": item_description,
				"qty": 1,
				"delivery_date": nowdate(),
				"warehouse": warehouse,
				"reference_dt": row.get("doctype"),
				"reference_dn": row.get("name"),
				"healthcare_practitioner": doc.get("practitioner"),
				"healthcare_service_unit": doc.get("healthcare_service_unit"),
			}
			if row.doctype == "Drug Prescription":
				dosage_info = ", <br>".join(
					[
						"frequency: " + str(row.get("dosage") or "No Prescription Dosage"),
						"period: " + str(row.get("period") or "No Prescription Period"),
						"dosage_form: " + str(row.get("dosage_form") or ""),
						"interval: " + str(row.get("interval") or ""),
						"interval_uom: " + str(row.get("interval_uom") or ""),
						"medical_code: " + str(row.get("medical_code") or "No medical code"),
						"Doctor's comment: " + (row.get("comment") or "Take medication as per dosage."),
					]
				)
				new_row.update(
					{
						"dosage_info": dosage_info,
						"qty": row.quantity - row.quantity_returned,
					}
				)
				drug_items.append(new_row)

			else:
				if row.doctype == "Therapy Plan Detail":
					new_row.update(
						{
							"qty": row.no_of_sessions - row.sessions_cancelled,
						}
					)
				lrpt_items.append(new_row)

	return drug_items, lrpt_items


def create_sales_order_from_encounter(doc, items, warehouse, allow_md_change_request=False):
	price_list = frappe.get_cached_value("Mode of Payment", doc.get("mode_of_payment"), "price_list")
	if not price_list:
		price_list = frappe.get_cached_value(
			"Mode of Payment",
			doc.get("encounter_mode_of_payment"),
			"price_list",
		)
	if not price_list:
		price_list = frappe.get_cached_value("Company", doc.get("company"), "default_price_list")
	if not price_list:
		frappe.throw("Please set Price List in Mode of Payment or Company")

	mobile = frappe.get_cached_value("Patient", doc.get("patient"), "mobile")
	customer = frappe.get_cached_value("Patient", doc.get("patient"), "customer")
	order_doc = frappe.new_doc("Sales Order")
	order_doc.update(
		{
			"company": doc.get("company"),
			"customer": customer,
			"patient": doc.get("patient"),
			"patient_name": doc.get("patient_name"),
			"patient_mobile_number": mobile,
			"transaction_date": nowdate(),
			"delivery_date": nowdate(),
			"set_warehouse": warehouse,
			"selling_price_list": price_list,
			"patient_encounter": doc.name,
			"allow_med_change_request": allow_md_change_request,
			"items": items,
			"healthcare_service_unit": doc.get("healthcare_service_unit"),
			"healthcare_practitioner": doc.get("practitioner"),
			# "department": doc.get("medical_department"),
		}
	)
	order_doc.save(ignore_permissions=True)
	order_doc.reload()
	return order_doc.name


def get_childs_map():
	return [
		{
			"table": "lab_test_prescription",
			"template": "Lab Test Template",
			"item_field": "lab_test_code",
		},
		{
			"table": "radiology_procedure_prescription",
			"template": "Radiology Examination Template",
			"item_field": "radiology_examination_template",
		},
		{
			"table": "procedure_prescription",
			"template": "Clinical Procedure Template",
			"item_field": "procedure",
		},
		{
			"table": "drug_prescription",
			"template": "Medication",
			"item_field": "drug_code",
		},
		{
			"table": "therapies",
			"template": "Therapy Type",
			"item_field": "therapy_type",
		},
	]


def validate_stock_item(item, warehouse, method):
	if frappe.get_cached_value("Item", item.item_code, "is_stock_item") == 1:
		stock_qty = get_stock_availability(item.item_code, warehouse)
		if float(item.qty) > float(stock_qty):
			msgThrow(
				(
					f"Available quantity for item: \
                    <h4 style='background-color:LightCoral'>\
                    {item.item_code} is {stock_qty}</h4>In {warehouse}."
				),
				method,
			)

	elif item.reference_dt == "Drug Prescription":
		msgThrow(
			(
				f"Item: <b>{item.item_code}</b> RowNo: \
                <b>{item.idx}</b> is not a stock item, \
                delivery note cannot be create for this Item"
			),
			method,
		)


def get_stock_availability(item_code, warehouse):
	sle = DocType("Stock Ledger Entry")
	latest_sle = (
		frappe.qb.from_(sle)
		.select(
			sle.qty_after_transaction.as_("actual_qty"),
			sle.posting_date,
			sle.posting_time,
			sle.name,
		)
		.where(
			(sle.item_code == item_code)
			& (sle.warehouse == warehouse)
			& (sle.is_cancelled == 0)
			& (sle.docstatus < 2)
		)
		.orderby(
			CombineDatetime(sle.posting_date, sle.posting_time),
			order=frappe.qb.desc,
		)
		.limit(1)
	).run(as_dict=True)

	sle_qty = latest_sle[0].actual_qty or 0 if latest_sle else 0
	return sle_qty
