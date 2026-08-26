import frappe
from frappe import _
from frappe.query_builder import DocType

hsr = DocType("Healthcare Service Request")
hsrp = DocType("Healthcare Service Request Payment")
pa = DocType("Patient Appointment")
io = DocType("Inpatient Occupancy")
ic = DocType("Inpatient Consultancy")


def execute(filters):
	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns():
	columns = [
		{
			"fieldname": "nhif_patient_claim",
			"label": _("NHIF Patient Claim"),
			"fieldtype": "Link",
			"options": "NHIF Patient Claim",
			"width": 130,
		},
		{
			"fieldname": "patient",
			"label": _("Patient"),
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"fieldname": "patient_name",
			"label": _("Patient Name"),
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"fieldname": "gender",
			"label": _("Gender"),
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"fieldname": "patient_appointment",
			"label": _("Patient Appointment"),
			"fieldtype": "Link",
			"options": "Patient Appointment",
			"width": 150,
		},
		{
			"fieldname": "appointment_date",
			"label": _("Appointment Date"),
			"fieldtype": "Date",
			"width": 120,
		},
		{
			"fieldname": "practitioner",
			"label": _("Practitioner"),
			"fieldtype": "Link",
			"options": "Healthcare Practitioner",
			"width": 150,
		},
		{
			"fieldname": "service_type",
			"label": _("Service Type"),
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"fieldname": "service_name",
			"label": _("Service Name"),
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"fieldname": "qty",
			"label": _("Qty"),
			"fieldtype": "Int",
			"width": 70,
		},
		{
			"fieldname": "unit_price",
			"label": _("Unit Price"),
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"fieldname": "amount_claimed",
			"label": _("Amount Claimed"),
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"fieldname": "admitted_date",
			"label": _("Admitted Date"),
			"fieldtype": "Date",
			"width": 120,
		},
		{
			"fieldname": "discharge_date",
			"label": _("Discharge Date"),
			"fieldtype": "Date",
			"width": 120,
		},
		{
			"fieldname": "folio_no",
			"label": _("Folio No"),
			"fieldtype": "Data",
			"width": 120,
		},
	]
	return columns


def process_merged_items(raw_data):
	"""
	Process NHIF claim items to handle merged items and add practitioner information.
	When items are merged, ref_docname contains comma-separated values.
	This function splits such items into separate rows and fetches the actual quantity and
	amount for each item from the Healthcare Service Request.
	"""
	processed_data = []

	for row in raw_data:
		ref_docname_list = [
			name.strip() for name in str(row.get("ref_docname") or "").split(",") if name.strip()
		]
		ref_doclist = get_hsr_details_batch(
			ref_docname_list,
			row.get("service_type"),
			row.get("coverage_plan_name"),
			row.get("item_code"),
			row.get("patient_appointment"),
		)

		for ref_doc in ref_doclist:
			new_row = row.copy()
			new_row["qty"] = ref_doc.get("qty", 0)
			new_row["amount_claimed"] = ref_doc.get("amount", 0)
			new_row["practitioner"] = ref_doc.get("practitioner")
			new_row["patient_appointment"] = ref_doc.get("patient_appointment")
			new_row.pop("ref_docname", None)
			new_row.pop("item_code", None)
			new_row.pop("coverage_plan_name", None)
			processed_data.append(new_row)

	return processed_data


def get_hsr_details_batch(ref_docname_list, ref_doctype, coverage_plan_name, item_code, appointment):
	"""
	Fetch qty, amount, and practitioner for multiple ref_docnames in a single query
	by joining Healthcare Service Request Payment with its parent.
	Returns a list of dicts with qty, amount, practitioner, and patient_appointment.
	"""
	if not ref_docname_list:
		return []

	ref_doclist = []

	if ref_doctype == "Patient Appointment":
		pa_results = (
			frappe.qb.from_(pa)
			.select(pa.name, pa.paid_amount, pa.practitioner)
			.where(pa.name.isin(ref_docname_list))
			.run(as_dict=True)
		)
		for r in pa_results:
			ref_doclist.append(
				{
					"qty": 1,
					"amount": r.get("paid_amount", 0),
					"practitioner": r.get("practitioner"),
					"patient_appointment": r.name,
				}
			)
	elif ref_doctype == "Inpatient Occupancy":
		io_results = (
			frappe.qb.from_(io)
			.select(
				io.name,
				io.amount,
			)
			.where(io.name.isin(ref_docname_list))
			.run(as_dict=True)
		)
		for r in io_results:
			ref_doclist.append({"qty": 1, "amount": r.get("amount", 0), "patient_appointment": appointment})
	elif ref_doctype == "Inpatient Consultancy":
		ic_results = (
			frappe.qb.from_(ic)
			.select(ic.name, ic.rate, ic.healthcare_practitioner)
			.where(ic.name.isin(ref_docname_list))
			.run(as_dict=True)
		)
		for r in ic_results:
			ref_doclist.append(
				{
					"qty": 1,
					"amount": r.get("rate", 0),
					"practitioner": r.get("healthcare_practitioner"),
					"patient_appointment": appointment,
				}
			)
	else:
		results = (
			frappe.qb.from_(hsrp)
			.inner_join(hsr)
			.on(hsrp.parent == hsr.name)
			.select(
				hsrp.ref_docname,
				(hsrp.qty - hsrp.qty_returned).as_("qty"),
				hsrp.rate,
				hsr.practitioner,
				hsr.appointment,
			)
			.where(
				(hsrp.ref_docname.isin(ref_docname_list))
				& (hsrp.ref_doctype == ref_doctype)
				& (hsrp.payor_plan == coverage_plan_name)
				& (hsrp.item_code == item_code)
				& (hsr.docstatus == 1)
			)
			.run(as_dict=True)
		)

		for r in results:
			net_qty = r.get("qty", 0)
			ref_doclist.append(
				{
					"qty": net_qty,
					"amount": net_qty * r.get("rate", 0),
					"practitioner": r.get("practitioner"),
					"patient_appointment": r.get("appointment"),
				}
			)

	return ref_doclist


def get_data(filters):
	npc = DocType("NHIF Patient Claim")
	npci = DocType("NHIF Patient Claim Item")

	data_query = (
		frappe.qb.from_(npc)
		.inner_join(npci)
		.on(npc.name == npci.parent)
		.select(
			npc.name.as_("nhif_patient_claim"),
			npc.patient.as_("patient"),
			npc.patient_name.as_("patient_name"),
			npc.patient_appointment.as_("patient_appointment"),
			npci.ref_doctype.as_("service_type"),
			npci.item_name.as_("service_name"),
			npc.gender.as_("gender"),
			npci.item_quantity.as_("qty"),
			npci.unit_price.as_("unit_price"),
			npci.amount_claimed.as_("amount_claimed"),
			npc.attendance_date.as_("appointment_date"),
			npc.date_admitted.as_("admitted_date"),
			npc.date_discharge.as_("discharge_date"),
			npc.folio_no.as_("folio_no"),
			npci.ref_docname.as_("ref_docname"),
			npci.item_code.as_("item_code"),
			npc.coverage_plan_name.as_("coverage_plan_name"),
		)
		.where(
			(npc.company == filters.get("company"))
			& (npc.claim_month == filters.get("claim_month"))
			& (npc.claim_year == filters.get("claim_year"))
		)
	)

	if filters.get("drafts_unclaimable") == 1:
		data_query = data_query.where(npc.docstatus == 0)
	else:
		data_query = data_query.where(npc.docstatus == 1)

	raw_data = data_query.run(as_dict=True)

	processed_data = process_merged_items(raw_data)

	return processed_data
