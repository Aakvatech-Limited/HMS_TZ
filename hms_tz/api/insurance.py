import frappe
from frappe.query_builder import DocType
from frappe.query_builder.terms import ValueWrapper
from frappe.utils import flt


def delete_price_package(doctype_name, company):
	jpp = DocType(doctype_name)
	frappe.qb.from_(jpp).delete().where(jpp.company == company).run()


def delete_hsic_data(coverage_plans):
	if len(coverage_plans) == 0:
		return

	hsic = DocType("Healthcare Service Insurance Coverage")
	frappe.qb.from_(hsic).delete().where(
		(hsic.is_auto_generated == 1) & (hsic.healthcare_insurance_coverage_plan.isin(coverage_plans))
	).run()


def get_insurance_items(insurance_customer_name, for_prices=False):
	services = []

	if for_prices:
		services += get_consultations(insurance_customer_name)

	services += get_labs(insurance_customer_name)
	services += get_radiologies(insurance_customer_name)
	services += get_procedure(insurance_customer_name)
	services += get_medications(insurance_customer_name)
	services += get_therapy_types(insurance_customer_name)
	services += get_service_unit_types(insurance_customer_name)

	service_map = {}
	for service in services:
		service_map.setdefault(service["ref_code"], []).append(service)

	return service_map


def get_consultations(insurance_customer_name):
	consultation_items = []

	it = DocType("Item")
	icd = DocType("Item Customer Detail")
	at = DocType("Appointment Type")
	hp = DocType("Healthcare Practitioner")

	practitioner_services = (
		frappe.qb.from_(hp).select(hp.op_consulting_charge_item, hp.inpatient_visit_charge_item).distinct()
	).run(as_dict=True)

	for row in practitioner_services:
		for field in row:
			if row[field]:
				consultation_items.append(row[field])

	appointment_services = (
		frappe.qb.from_(at)
		.select(
			at.assistant_md_followup_item,
			at.gp_followup_item,
			at.specialist_followup_item,
			at.super_specialist_followup_item,
			at.assistant_md_fasttrack_item,
			at.gp_fasttrack_item,
			at.specialist_fasttrack_item,
			at.super_specialist_fasttrack_item,
		)
		.distinct()
	).run(as_dict=True)

	for row in appointment_services:
		for field in row:
			if row[field]:
				consultation_items.append(row[field])

	consultation_query = (
		frappe.qb.from_(icd)
		.inner_join(it)
		.on(icd.parent == it.name)
		.select(
			icd.ref_code,
			it.name.as_("service_name"),
			ValueWrapper("Consulation Charges").as_("service_type"),
		)
		.where(
			(icd.customer_name == insurance_customer_name)
			& ((icd.ref_code.isnotnull()) & (icd.ref_code != ""))
			& (it.name.isin(consultation_items))
			# & (it.disabled == 0)
		)
	)

	consultation_data = consultation_query.run(as_dict=True)

	return consultation_data


def get_labs(insurance_customer_name):
	icd = DocType("Item Customer Detail")
	ltt = DocType("Lab Test Template")

	lab_query = (
		frappe.qb.from_(icd)
		.inner_join(ltt)
		.on(icd.parent == ltt.item)
		.select(
			icd.ref_code,
			ltt.name.as_("service_name"),
			ValueWrapper("Lab Test Template").as_("service_type"),
		)
		.where(
			(icd.customer_name == insurance_customer_name)
			& ((icd.ref_code.isnotnull()) & (icd.ref_code != ""))
			# & (ltt.disabled == 0)
		)
	)
	lab_data = lab_query.run(as_dict=True)

	return lab_data


def get_radiologies(insurance_customer_name):
	icd = DocType("Item Customer Detail")
	ret = DocType("Radiology Examination Template")

	rad_query = (
		frappe.qb.from_(icd)
		.inner_join(ret)
		.on(icd.parent == ret.item)
		.select(
			icd.ref_code,
			ret.name.as_("service_name"),
			ValueWrapper("Radiology Examination Template").as_("service_type"),
		)
		.where(
			(icd.customer_name == insurance_customer_name)
			& ((icd.ref_code.isnotnull()) & (icd.ref_code != ""))
			# & (ret.disabled == 0)
		)
	)

	rad_data = rad_query.run(as_dict=True)

	return rad_data


def get_procedure(insurance_customer_name):
	icd = DocType("Item Customer Detail")
	cpt = DocType("Clinical Procedure Template")

	procedure_query = (
		frappe.qb.from_(icd)
		.inner_join(cpt)
		.on(icd.parent == cpt.item)
		.select(
			icd.ref_code,
			cpt.name.as_("service_name"),
			ValueWrapper("Clinical Procedure Template").as_("service_type"),
		)
		.where(
			(icd.customer_name == insurance_customer_name)
			& ((icd.ref_code.isnotnull()) & (icd.ref_code != ""))
			# & (cpt.disabled == 0)
		)
	)

	procedure_data = procedure_query.run(as_dict=True)

	return procedure_data


def get_medications(insurance_customer_name):
	icd = DocType("Item Customer Detail")
	med = DocType("Medication")

	medication_query = (
		frappe.qb.from_(icd)
		.inner_join(med)
		.on(icd.parent == med.item)
		.select(
			icd.ref_code,
			med.name.as_("service_name"),
			ValueWrapper("Medication").as_("service_type"),
		)
		.where(
			(icd.customer_name == insurance_customer_name)
			& ((icd.ref_code.isnotnull()) & (icd.ref_code != ""))
			# & (med.disabled == 0)
		)
	)

	medication_data = medication_query.run(as_dict=True)

	return medication_data


def get_therapy_types(insurance_customer_name):
	icd = DocType("Item Customer Detail")
	tt = DocType("Therapy Type")

	therapy_query = (
		frappe.qb.from_(icd)
		.inner_join(tt)
		.on(icd.parent == tt.item)
		.select(
			icd.ref_code,
			tt.name.as_("service_name"),
			ValueWrapper("Therapy Type").as_("service_type"),
		)
		.where(
			(icd.customer_name == insurance_customer_name)
			& ((icd.ref_code.isnotnull()) & (icd.ref_code != ""))
			# & (tt.disabled == 0)
		)
	)

	therapy_data = therapy_query.run(as_dict=True)

	return therapy_data


def get_service_unit_types(insurance_customer_name):
	icd = DocType("Item Customer Detail")
	hsut = DocType("Healthcare Service Unit Type")

	service_unit_query = (
		frappe.qb.from_(icd)
		.inner_join(hsut)
		.on(icd.parent == hsut.item)
		.select(
			icd.ref_code,
			hsut.name.as_("service_name"),
			ValueWrapper("Healthcare Service Unit Type").as_("service_type"),
		)
		.where(
			(icd.customer_name == insurance_customer_name)
			& ((icd.ref_code.isnotnull()) & (icd.ref_code != ""))
			# & (hsut.disabled == 0)
		)
	)

	service_unit_data = service_unit_query.run(as_dict=True)

	return service_unit_data


def get_packages_for_price_list(doctype_name, company, insurance_customer_name, item=None):
	# it = DocType("Item")
	pp = DocType(doctype_name)
	icd = DocType("Item Customer Detail")

	item_query = (
		frappe.qb.from_(icd)
		# .inner_join(it)
		# .on(icd.parent == it.name)
		.inner_join(pp)
		.on(icd.ref_code == pp.itemcode)
		.select(
			icd.ref_code,
			icd.parent.as_("erp_item"),
			pp.itemcode,
			pp.itemname,
		)
		.where(
			(pp.company == company)
			& (icd.customer_name == insurance_customer_name)
			& ((icd.ref_code.isnotnull()) & (icd.ref_code != ""))
			# & (it.disabled == 0)
		)
		# .groupby(icd.ref_code, icd.parent)
	)
	if doctype_name == "NHIF Price Package":
		item_query = item_query.select(
			pp.unitprice.as_("unitprice"),
			pp.schemeid,
		)

		item_query
	elif doctype_name == "Jubilee Price Package":
		item_query = item_query.select(
			pp.itemprice.as_("unitprice"),
		)

		# pp.itemcode,
		# pp.itemname,
		# pp.schemeid,
		# pp.packageid,
		# pp.pricecode,
		# pp.unitprice,
		# pp.isrestricted,
		# pp.hascopayment,
		# pp.strength,
		# pp.dosage,

	if item:
		item_query = item_query.where(icd.parent == item)

	item_data = item_query.run(as_dict=True)

	return item_data


def handle_insurance_prices(itp, package, price_list, currency):
	item_price_list = fetch_item_prices(itp, price_list, package, currency)

	if len(item_price_list) > 0:
		for price in item_price_list:
			if flt(price.price_list_rate) != flt(package.unitprice):
				# delete Item Price if no package.unitprice or it is 0
				if not flt(package.unitprice) or flt(package.unitprice) == 0:
					frappe.qb.from_(itp).delete().where(itp.name == price.name).run()
					print(f"Deleted the item {package.get('erp_item')} from {price_list}")
				else:
					# update Item Price with the new price
					frappe.qb.update(itp).set(itp.price_list_rate, flt(package.unitprice)).where(
						itp.name == price.name
					).run()

					out = frappe.get_doc(
						{
							"doctype": "Comment",
							"comment_type": "Comment",
							"comment_email": frappe.session.user,
							"comment_by": frappe.session.user,
							"content": f"Updated Item Price for <b>{package.get('erp_item')}</b> for \
                                <b>{price_list}</b> from <b>{price.price_list_rate}</b> to \
                                    <b>{flt(package.unitprice)}</b>",
							"reference_doctype": "Item Price",
							"reference_name": price.name,
						}
					).insert(ignore_permissions=True)

					print(f"Updated the item {package.get('erp_item')} from {price_list}")
	else:
		item_price_doc = frappe.new_doc("Item Price")
		item_price_doc.update(
			{
				"item_code": package.get("erp_item"),
				"price_list": price_list,
				"currency": currency,
				"price_list_rate": flt(package.unitprice),
				"buying": 0,
				"selling": 1,
			}
		)
		item_price_doc.insert(ignore_permissions=True)

		print(f"Create item price for {package.get('erp_item')} for {price_list}")


def fetch_item_prices(itp, price_list, package, currency):
	item_prices = (
		frappe.qb.from_(itp)
		.select(itp.name, itp.item_code, itp.price_list_rate)
		.where(
			(itp.selling == 1)
			& (itp.price_list == price_list)
			& (itp.item_code == package.get("erp_item"))
			& (itp.currency == currency)
		)
	).run(as_dict=True)

	return item_prices


def create_insurance_price_list(company, price_list, currency, insurance_provider, schemeid=None):
	if not frappe.db.exists("Price List", price_list):
		price_list_doc = frappe.new_doc("Price List")
		price_list_doc.price_list_name = price_list
		price_list_doc.currency = currency
		price_list_doc.buying = 0
		price_list_doc.selling = 1
		price_list_doc.save(ignore_permissions=True)

	# set price list to a coverage plan
	filters = {
		"company": company,
	}
	if insurance_provider == "NHIF" and schemeid:
		filters["nhif_scheme_id"] = schemeid
	elif insurance_provider == "Jubilee":
		filters["insurance_company"] = ["like", "%Jubilee%"]

	plan_details = frappe.get_cached_value(
		"Healthcare Insurance Coverage Plan", filters, ["name", "price_list"], as_dict=True
	)

	if plan_details:
		if plan_details.price_list != price_list:
			frappe.db.set_value(
				"Healthcare Insurance Coverage Plan",
				plan_details.name,
				"price_list",
				price_list,
			)

			out = frappe.get_doc(
				{
					"doctype": "Comment",
					"comment_type": "Comment",
					"comment_email": frappe.session.user,
					"comment_by": frappe.session.user,
					"content": f"Created and Attached Price List {price_list} for {company}",
					"reference_doctype": "Healthcare Insurance Coverage Plan",
					"reference_name": plan_details.name,
				}
			).insert(ignore_permissions=True)
