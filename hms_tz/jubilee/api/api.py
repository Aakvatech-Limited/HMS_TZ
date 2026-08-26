import json

import frappe
import requests
from erpnext import get_default_company
from frappe import _
from frappe.utils import now_datetime, nowdate, nowtime

from hms_tz.hms_tz.doctype.healthcare_service_request.healthcare_service_request import (
	get_childs_map,
	get_item_rate,
	get_item_refcode,
)
from hms_tz.jubilee.api.preauthorization import get_preauth_entities, get_source_from_approval_request
from hms_tz.jubilee.doctype.jubilee_response_log.jubilee_response_log import add_jubilee_log


@frappe.whitelist()
def get_member_card_detials(card_no, insurance_provider=None):
	if not card_no or insurance_provider != "Jubilee":
		return

	company = get_default_company() or frappe.defaults.get_user_default("Company")

	if not company:
		frappe.throw(_("No companies found to connect to Jubilee"))

	setting_doc = frappe.get_cached_doc("HMS TZ Setting", company)

	token = setting_doc.get_jubilee_token()
	headers = {"Authorization": "Bearer " + token}
	url = f"{setting_doc.jubilee_url}/jubileeapi/Getcarddetails?MemberNo={str(card_no)}"

	r = requests.get(url, headers=headers, timeout=60)
	r.raise_for_status()

	data = json.loads(r.text)

	if data.get("Status") == "OK":
		add_jubilee_log(
			request_type="GetCardDetails",
			request_url=url,
			request_header=headers,
			response_data=data,
			status_code=r.status_code,
			company=company,
			ref_doctype="Patient",
			card_no=card_no,
		)
		frappe.msgprint(_(data["Status"]), alert=True)
		return data
	else:
		add_jubilee_log(
			request_type="GetCardDetails",
			request_url=url,
			request_header=headers,
			response_data=data,
			status_code=r.status_code,
			company=company,
			ref_doctype="Patient",
			card_no=card_no,
		)

		frappe.msgprint(
			title="Jubilee API Error",
			msg=f"Failed to Fetch card details<br><br>Status Code: {r.status_code}<br>Jubilee Response: <b>{data.get('Description')}<b>",
			indicator="red",
		)

		return "Error"


@frappe.whitelist()
def create_jubilee_subscription(patient_id, card_no, insurance_provider):
	if not insurance_provider or insurance_provider != "Jubilee":
		return

	subscription_list = frappe.get_list(
		"Healthcare Insurance Subscription",
		filters={
			"patient": patient_id,
			"is_active": 1,
			"insurance_company": ["like", "%Jubilee%"],
		},
	)
	if len(subscription_list) > 0:
		frappe.msgprint(
			_("Existing Patient HIS was found. Create the Healthcare Insurance Subscription manually!")
		)
		return

	plan_filters = {
		"is_active": 1,
		"insurance_company": ["like", "%Jubilee%"],
	}

	company = get_default_company() or frappe.defaults.get_user_default("Company")
	if company:
		plan_filters["company"] = company

	# Assumed that company is filtered based on user permissions
	plan = frappe.db.get_list(
		"Healthcare Insurance Coverage Plan",
		filters=plan_filters,
		fields=["name", "insurance_company", "company"],
	)

	if not plan or len(plan) == 0:
		frappe.msgprint(_("No active Healthcare Insurance Coverage Plan found for Jubilee"))
		return

	if len(plan) > 1:
		frappe.msgprint(
			_(
				"Multiple active Healthcare Insurance Coverage Plan found for Jubilee,\
                    <br><br>please create the healthcare Insurance Subscription manually"
			)
		)
		return

	frappe.flags.auto_his = True
	sub_doc = frappe.new_doc("Healthcare Insurance Subscription")
	sub_doc.patient = patient_id
	sub_doc.insurance_company = plan[0].insurance_company
	sub_doc.healthcare_insurance_coverage_plan = plan[0].name
	sub_doc.coverage_plan_card_number = card_no
	sub_doc.save(ignore_permissions=True)
	sub_doc.submit()
	frappe.msgprint(
		_(f"<h3>AUTO</h3> Healthcare Insurance Subscription: {sub_doc.name} is created for {plan[0].name}")
	)


@frappe.whitelist()
def get_authorization_number(
	company,
	card_no,
	appointment_no,
	insurance_subscription,
	insurance_provider="Jubilee",
):
	if insurance_provider != "Jubilee":
		return

	if not company:
		frappe.throw(_("Company is required to get authorization number"))

	setting_doc = frappe.get_cached_doc("HMS TZ Setting", company)

	if not setting_doc.enable_jubilee_api:
		frappe.throw(f"HMS TZ Setting for company: {company} does not have Jubilee API enabled.")

	if not card_no:
		frappe.msgprint(
			_(f"Please set Card No in Healthcare Insurance Subscription {insurance_subscription}")
		)
		return

	token = setting_doc.get_jubilee_token()
	headers = {"Content-Type": "application/json", "Authorization": "Bearer " + token}
	url = f"{setting_doc.jubilee_url}/jubileeapi/CheckVerification?MemberNo={str(card_no)}"

	r = requests.get(url, headers=headers, timeout=60)

	if r.status_code != 200:
		data = json.loads(r.text) if r.text else {}
		add_jubilee_log(
			request_type="AuthorizeCard",
			request_url=url,
			request_header=headers,
			response_data=data,
			status_code=r.status_code,
			ref_doctype="Patient Appointment",
			ref_docname=appointment_no,
			company=company,
			card_no=card_no,
		)
		frappe.throw(
			_(
				f"Failed to Authorize Card<br><br>Status Code: {r.status_code}<br>Jubilee Response: <b>{data.get('Description')}<b>"
			)
		)
	else:
		data = json.loads(r.text)
		add_jubilee_log(
			request_type="AuthorizeCard",
			request_url=url,
			request_header=headers,
			response_data=data,
			status_code=r.status_code,
			ref_doctype="Patient Appointment",
			ref_docname=appointment_no,
			company=company,
			card_no=card_no,
			authorization_no=data.get("AuthorizationNo", ""),
		)

		if not data.get("AuthorizationNo"):
			frappe.throw(title=data.get("Status"), msg=data["Description"])

		elif data.get("AuthorizationNo") and "OK" not in data.get("Status"):
			frappe.msgprint(title=data.get("Status"), msg=data["Description"])

		# Auto-create Jubilee Benefit records from the authorization response
		if data.get("Benefits"):
			patient = frappe.db.get_value("Patient Appointment", appointment_no, "patient")
			create_jubilee_benefits(
				card_no=card_no,
				authorization_data=data,
				appointment_no=appointment_no,
				company=company,
				patient=patient,
			)

		frappe.msgprint(_(data["Description"]), alert=True)
		return data


def create_jubilee_benefits(
	card_no: str,
	authorization_data: dict,
	appointment_no: str,
	company: str,
	patient: str | None = None,
):
	"""Create Jubilee Benefit records from the AuthorizeCard response.

	Each benefit in the response's 'Benefits' array is saved as a separate
	Jubilee Benefit document. Records are NOT deleted on re-authorization,
	since different authorization numbers and appointments are expected.
	"""
	benefits = authorization_data.get("Benefits", [])
	if not benefits:
		return

	authorization_no = authorization_data.get("AuthorizationNo", "")

	values = []
	fields = [
		"name",
		"creation",
		"owner",
		"modified",
		"modified_by",
		"benefit_code",
		"benefit_name",
		"benefit_balance",
		"card_no",
		"patient",
		"appointment",
		"authorization_no",
		"company",
		"posting_date",
		"posting_time",
	]
	for benefit in benefits:
		jb_name = frappe.generate_hash(length=10)
		row = (
			jb_name,
			now_datetime(),
			frappe.session.user,
			now_datetime(),
			frappe.session.user,
			benefit.get("BenefitCode"),
			benefit.get("BenefitName"),
			benefit.get("BenefitBalance"),
			card_no,
			patient,
			appointment_no,
			authorization_no,
			company,
			nowdate(),
			nowtime(),
		)
		values.append(row)

	if len(values) > 0:
		frappe.db.bulk_insert("Jubilee Benefit", fields=fields, values=values, ignore_duplicates=True)


@frappe.whitelist()
def enqueue_get_jubilee_procedures(company: str):
	frappe.enqueue(
		method="hms_tz.jubilee.api.api.get_procedure_list",
		company=company,
		queue="default",
		at_front=True,
	)
	frappe.msgprint(_("Procedure list will be synced in the background"), alert=True)
	return


def get_procedure_list(company: str | None = None):
	"""Fetch procedure list from Jubilee API and sync to Jubilee Procedure DocType."""

	if not company:
		company = get_default_company()

	if not company:
		company = frappe.defaults.get_user_default("Company")

	if not company:
		hms_tz_records = frappe.get_list(
			"HMS TZ Setting",
			fields=["company"],
			filters={"enable_jubilee_api": 1},
			limit=1,
		)
		if len(hms_tz_records) > 0:
			company = hms_tz_records[0].company

	if not company:
		frappe.throw(_("No companies found to connect to Jubilee"))

	setting_doc = frappe.get_cached_doc("HMS TZ Setting", company)

	if not setting_doc.enable_jubilee_api:
		frappe.throw(_(f"HMS TZ Setting for company: {company} does not have Jubilee API enabled."))

	token = setting_doc.get_jubilee_token()
	headers = {"Authorization": "Bearer " + token}
	url = f"{setting_doc.jubilee_url}/jubileeapi/GetProcedureList"

	r = requests.get(url, headers=headers, timeout=60)

	data = json.loads(r.text) if r.text else {}

	if r.status_code != 200 or data.get("Status") != "OK":
		add_jubilee_log(
			request_type="GetProcedureList",
			request_url=url,
			request_header=headers,
			response_data=data,
			status_code=r.status_code,
			company=company,
			ref_doctype="Jubilee Procedure",
		)
		frappe.throw(
			title="Jubilee API Error",
			msg=_(
				f"Failed to fetch procedure list<br><br>"
				f"Status Code: {r.status_code}<br>"
				f"Jubilee Response: <b>{data.get('Description')}</b>"
			),
		)

	add_jubilee_log(
		request_type="GetProcedureList",
		request_url=url,
		request_header=headers,
		response_data=data,
		status_code=r.status_code,
		company=company,
		ref_doctype="Jubilee Procedure",
	)

	procedures = data.get("Description", [])
	if procedures:
		_sync_procedures(procedures, company)

	frappe.msgprint(
		_(f"Successfully synced {len(procedures)} procedures from Jubilee"),
		alert=True,
	)

	return data


def _sync_procedures(procedures: list[dict], company: str):
	"""Delete existing Jubilee Procedure records for the company and bulk-insert fresh data."""

	frappe.db.delete("Jubilee Procedure", filters={"disabled": 0})

	fields = [
		"name",
		"procedure_code",
		"procedure_name",
		"creation",
		"owner",
		"modified",
		"modified_by",
	]
	values = []

	user = frappe.session.user
	timestamp = now_datetime()

	for row in procedures:
		values.append(
			(
				row.get("ProcedureCode"),
				row.get("ProcedureCode"),
				row.get("ProcedureName"),
				timestamp,
				user,
				timestamp,
				user,
			)
		)

	if values:
		frappe.db.bulk_insert(
			"Jubilee Procedure",
			fields=fields,
			values=values,
			ignore_duplicates=True,
		)


@frappe.whitelist()
def verify_jubilee_services(
	source_doctype,
	source_docname,
	benefit_code,
):
	"""Send a VerifyItems request to Jubilee API for items on a Patient Encounter.

	Collects all eligible items from the encounter's child tables (lab tests,
	radiology, procedures, medications, therapies), resolves each item's Jubilee
	ref_code, and posts to /jubileeapi/VerifyItems.

	Args:
	    source_doctype: The doctype of the source document.
	    source_docname: The name of the source document.
	    benefit_code: Jubilee BenefitCode selected by the practitioner from
	        the Jubilee Benefit records (e.g. '7905').

	Returns:
	    dict: The parsed Jubilee API response on success, or None on error.
	"""
	if not benefit_code:
		frappe.throw(_("Please select a Jubilee Benefit before verifying services"))

	source_doc = frappe.get_doc(source_doctype, source_docname)

	insurance_company = source_doc.get("insurance_company") or ""
	if "Jubilee" not in insurance_company:
		frappe.throw(
			_(
				"Cannot verify Jubilee services: {0} {1} belongs to insurance company '{2}', not Jubilee"
			).format(source_doctype, source_docname, insurance_company)
		)

	services, service_map, total_amount = get_services(source_doc)
	if not services:
		frappe.msgprint(_("No service(s) found to verify"), indicator="orange")
		return False

	card_no, visit_date = frappe.get_cached_value(
		"Patient Appointment",
		source_doc.appointment,
		["coverage_plan_card_number", "appointment_date"],
	)
	if not card_no:
		frappe.throw(_("Coverage Plan Card Number is not set on the Patient Appointment"))

	setting_doc = frappe.get_cached_doc("HMS TZ Setting", source_doc.company)
	if not setting_doc.enable_jubilee_api:
		frappe.throw(_("Please Enable Jubilee API to proceed.."))

	payload = {
		"BenefitCode": benefit_code,
		"MemberNo": card_no.strip(),
		"ProcedureId": source_doc.jubilee_procedure,
		"VerifyItems": json.dumps(services),
		"Amount": str(total_amount),
		"VisitDate": str(visit_date),
	}

	token = setting_doc.get_jubilee_token()
	url = f"{setting_doc.jubilee_url}/jubileeapi/VerifyItems"
	headers = {"Authorization": f"Bearer {token}"}

	r = requests.post(url, data=payload, headers=headers, timeout=120)

	data = json.loads(r.text) if r.text else {}

	add_jubilee_log(
		request_type="VerifyItems",
		request_url=url,
		request_header=headers,
		request_body=payload,
		response_data=data,
		status_code=r.status_code,
		company=source_doc.company,
		ref_doctype=source_doctype,
		ref_docname=source_docname,
		card_no=card_no,
	)

	if r.status_code != 200 or data.get("Status") == "ERROR":
		description = data.get("Description", r.text or "Unknown error")

		source_doc.add_comment(
			comment_type="Comment",
			text=(
				f"Jubilee VerifyItems request failed<br><br>"
				f"Status Code: {r.status_code}<br>"
				f"Jubilee Response: <b>{description}</b>"
			),
		)

		if (
			"Pre-Authorization" in description
			or "Pre-Auth" in description
			or "Prior Authorization" in description
			or "Preauthorization" in description
		):
			return {
				"action": "PreAuthRequired",
				"description": description,
				"source_doctype": source_doctype,
				"source_docname": source_docname,
				"benefit_code": benefit_code,
			}

		frappe.msgprint(
			title="Jubilee Verification Error",
			msg=(
				f"Item verification failed<br><br>"
				f"Status Code: {r.status_code}<br>"
				f"Jubilee Response: <b>{description}</b>"
			),
		)

		return "Error"

	verified_items = data.get("VerifiedItems", [])
	verified_map = {str(v.get("ItemId")): v for v in verified_items}

	status = data.get("Status", "")

	for (child_doctype, child_name, _item_name), ref_code in service_map.items():
		if str(ref_code) not in verified_map:
			continue

		frappe.db.set_value(
			child_doctype,
			child_name,
			{
				"preapproval_status": status,
			},
			update_modified=False,
		)

	source_doc.add_comment(
		comment_type="Comment",
		text=(
			f"Jubilee VerifyItems successful<br>"
			f"Description: <b>{data.get('Description')}</b><br>"
			f"Items Verified: <b>{len(verified_items)}</b>"
		),
	)
	return True


def get_services(doc, preapproval_no=None):
	"""Collect items from source child tables for Jubilee VerifyItems.

	Iterates through all child tables (lab tests, radiology, procedures,
	medications, therapies), skips cancelled/prescribed/restricted rows,
	and builds the VerifyItems JSON array and a mapping of
	(child_doctype, child_name, item_name) -> ref_code for post-response updates.

	Args:
	    doc: The source document object.
	    preapproval_no: The preapproval number to filter by.

	Returns:
	    tuple: (services list, service_map dict)
	"""
	services = []
	service_map = {}
	total_amount = 0

	for child in get_childs_map():
		if not doc.get(child.get("table")):
			continue

		for row in doc.get(child.get("table")):
			if not row.get(child.get("item")):
				continue

			if preapproval_no and row.preapproval_no == preapproval_no:
				services.append(row.get(child.get("item")))

				continue

			if (
				row.get("prescribe")
				or row.get("is_not_available_inhouse")
				or row.get("is_cancelled")
				or row.get("is_restricted")
				or row.get("preapproval_no")
				or row.get("preapproval_status") == "OK"
			):
				continue

			ref_code = get_item_refcode(
				child.get("doctype"), row.get(child.get("item")), doc.company, doc.insurance_company
			)

			item_code = frappe.get_cached_value(child.get("doctype"), row.get(child.get("item")), "item")
			if not item_code:
				frappe.throw(
					_(
						f"Item code for {row.get(child.get('item'))} set in row {row.idx} was not found.<br>Please set the item code in {child.get('doctype')}."
					)
				)

			item_rate = get_item_rate(
				item_code,
				doc.company,
				doc.insurance_subscription,
				doc.insurance_company,
			)

			services.append(
				{
					"ItemId": str(ref_code),
					"ItemQuantity": row.get("quantity") or 1,
					"ItemPrice": item_rate,
				}
			)

			total_amount += item_rate * (row.get("quantity") or 1)

			service_map[row.get("doctype"), row.get("name"), row.get(child.get("item"))] = ref_code

	return services, service_map, total_amount


def send_preauthorization(approval_request_name, request_type="SendPreauthorization", submission_id=None):
	"""Build and send the SendPreauthorization payload to the Jubilee API.

	Args:
	    approval_request_name: Name of the Jubilee Approval Request document.

	Returns:
	    dict: Result with status, submission_id, and description.
	"""
	jar_doc = frappe.get_doc("Jubilee Approval Request", approval_request_name)

	setting_doc = frappe.get_cached_doc("HMS TZ Setting", jar_doc.company)
	if not setting_doc.enable_jubilee_api:
		frappe.throw(_("Jubilee API is not enabled for this company"))

	entities = get_preauth_entities(get_source_from_approval_request(jar_doc))
	payload = json.dumps({"entities": [entities]})

	token = setting_doc.get_jubilee_token()

	url = ""
	request_type = ""
	if jar_doc.submission_id:
		request_type = "UpdatePreauthorization"
		url = f"{setting_doc.jubilee_url}/jubileeapi/UpdatePreauthorization"
	else:
		request_type = "SendPreauthorization"
		url = f"{setting_doc.jubilee_url}/jubileeapi/SendPreauthorization"

	headers = {
		"Authorization": f"Bearer {token}",
		"Content-Type": "application/json",
	}

	result = {"status": "ERROR", "submission_id": "", "description": ""}
	r = None

	try:
		r = requests.post(url, headers=headers, data=payload, timeout=120)
		data = json.loads(r.text) if r.text else {}

		add_jubilee_log(
			request_type=request_type,
			request_url=url,
			request_header=headers,
			request_body=payload,
			response_data=data,
			status_code=r.status_code,
			company=jar_doc.company,
			ref_doctype="Jubilee Approval Request",
			ref_docname=jar_doc.name,
			card_no=jar_doc.card_no,
		)

		status = data.get("Status") or data.get("status") or ""
		description = data.get("Description") or data.get("description") or ""
		submission_id = str(data.get("SubmissionID") or data.get("submissionId") or "")

		frappe.db.set_value(
			"Jubilee Approval Request",
			jar_doc.name,
			{
				"preauth_status": status,
				"preauth_description": description,
				"submission_id": submission_id,
			},
		)

		result.update(
			{
				"status": status,
				"submission_id": submission_id,
				"description": description,
				"service_request": jar_doc.name,
			}
		)

	except Exception:
		error_text = r.text if r and r.text else "NO RESPONSE — Timeout?"
		error_status = r.status_code if r else "NO STATUS CODE"

		add_jubilee_log(
			request_type=request_type,
			request_url=url,
			request_header=headers,
			request_body=payload,
			response_data=error_text,
			status_code=error_status,
			company=jar_doc.company,
			ref_doctype="Jubilee Approval Request",
			ref_docname=jar_doc.name,
			card_no=jar_doc.card_no,
		)

		frappe.db.set_value(
			"Jubilee Approval Request",
			jar_doc.name,
			{
				"preauth_status": "ERROR",
				"preauth_description": str(error_text),
			},
		)
		result["description"] = str(error_text)

	return result


@frappe.whitelist()
def get_preauthorization_status(approval_request_name):
	"""Fetch the status of a previously submitted pre-authorization request from Jubilee.

	Calls GET /jubileeapi/getPreauthorizationStatus?submissionID=<id>

	Args:
	    approval_request_name: Name of the Jubilee Approval Request document.
	        Its submission_id field is used as the submissionID query parameter.

	Returns:
	    dict: {
	        "status": "OK" | "ERROR",
	        "description": <dict with full details on OK, or error string on ERROR>,
	        "service_request": <jar_doc.name>,
	    }
	"""
	jar_doc = frappe.get_doc("Jubilee Approval Request", approval_request_name)

	if not jar_doc.submission_id:
		frappe.throw(
			_(
				"Cannot check status: this Service Request has no Submission ID. "
				"Please send the pre-authorization first."
			)
		)

	setting_doc = frappe.get_cached_doc("HMS TZ Setting", jar_doc.company)
	if not setting_doc.enable_jubilee_api:
		frappe.throw(_("Jubilee API is not enabled for this company"))

	token = setting_doc.get_jubilee_token()
	url = f"{setting_doc.jubilee_url}/jubileeapi/getPreauthorizationStatus"
	headers = {
		"Authorization": f"Bearer {token}",
		"Content-Type": "application/json",
	}
	params = {"submissionID": jar_doc.submission_id}

	result = {"status": "ERROR", "description": "", "service_request": jar_doc.name}
	r = None

	try:
		r = requests.get(url, headers=headers, params=params, timeout=60)
		data = json.loads(r.text) if r.text else {}

		add_jubilee_log(
			request_type="getPreauthorizationStatus",
			request_url=url,
			request_header=headers,
			request_body=str(params),
			response_data=data,
			status_code=r.status_code,
			company=jar_doc.company,
			ref_doctype="Jubilee Approval Request",
			ref_docname=jar_doc.name,
			card_no=jar_doc.card_no,
		)

		status = data.get("Status") or data.get("status") or "ERROR"
		description = data.get("Description") or data.get("description") or ""

		if status == "ERROR":
			frappe.throw(_(description))
		else:
			preauth_status = description.get("PreauthorizationStatus") or ""
			preauth_description = description.get("details") or ""
			frappe.db.set_value(
				"Jubilee Approval Request",
				jar_doc.name,
				{
					"preauth_status": preauth_status,
					"preauth_description": preauth_description,
				},
			)

		result.update({"status": status, "description": preauth_description or preauth_status})

	except Exception:
		error_text = r.text if r and r.text else "NO RESPONSE — Timeout or connection error"
		error_status = r.status_code if r else "NO STATUS CODE"

		add_jubilee_log(
			request_type="getPreauthorizationStatus",
			request_url=url,
			request_header=headers,
			request_body=str(params),
			response_data=error_text,
			status_code=error_status,
			company=jar_doc.company,
			ref_doctype="Jubilee Approval Request",
			ref_docname=jar_doc.name,
			card_no=jar_doc.card_no,
		)

		result["description"] = str(error_text)

	return result


@frappe.whitelist()
def get_inpatient_admission_status(inpatient_record_name):
	"""Fetch inpatient admission status from Jubilee (endpoint 12 - getAdmissionStatus).

	Calls GET /jubileeapi/getAdmissionStatus?authorizationNo=<auth_no>

	The authorization number is read from the Insurance Subscription linked
	to the Inpatient Record (insurance_subscription.authorization_no).

	On success, persists fromDate, toDate, and approvedAmount onto the
	Inpatient Record so downstream processes can use them.

	Args:
	    inpatient_record_name: Name of the Inpatient Record document.

	Returns:
	    dict: {
	        "status": "OK" | "ERROR",
	        "description": <dict with admission details on OK, error string on ERROR>,
	        "inpatient_record": <inpatient_record_name>,
	    }
	"""
	inpatient_doc = frappe.get_doc("Inpatient Record", inpatient_record_name)

	authorization_no = frappe.db.get_value(
		"Patient Appointment",
		inpatient_doc.patient_appointment,
		"authorization_no",
	)

	if not authorization_no:
		frappe.throw(
			_(
				"Cannot check admission status: the linked Patient Appointment "
				"has no Authorization Number. Please ensure the patient is authorized first."
			)
		)

	setting_doc = frappe.get_cached_doc("HMS TZ Setting", inpatient_doc.company)
	if not setting_doc.enable_jubilee_api:
		frappe.throw(_("Jubilee API is not enabled for this company"))

	token = setting_doc.get_jubilee_token()
	url = f"{setting_doc.jubilee_url}/jubileeapi/getAdmissionStatus"
	headers = {
		"Authorization": f"Bearer {token}",
		"Content-Type": "application/json",
	}
	params = {"authorizationNo": authorization_no}

	result = {
		"status": "ERROR",
		"description": "",
		"inpatient_record": inpatient_record_name,
	}
	r = None

	try:
		r = requests.get(url, headers=headers, params=params, timeout=60)
		data = json.loads(r.text) if r.text else {}

		add_jubilee_log(
			request_type="getAdmissionStatus",
			request_url=url,
			request_header=headers,
			request_body=str(params),
			response_data=data,
			status_code=r.status_code,
			company=inpatient_doc.company,
			ref_doctype="Inpatient Record",
			ref_docname=inpatient_record_name,
			card_no=authorization_no,
		)

		status = data.get("Status") or data.get("status") or "ERROR"
		description = data.get("Description") or data.get("description") or ""

		if status == "ERROR":
			frappe.throw(_(str(description)))

		from_date = description.get("fromDate") or ""
		to_date = description.get("toDate") or ""
		description.get("approvedAmount") or 0

		update_fields = {}
		if from_date:
			update_fields["admitted_datetime"] = from_date
		if to_date:
			update_fields["expected_discharge"] = to_date

		# if update_fields:
		#     frappe.db.set_value("Inpatient Record", inpatient_record_name, update_fields)

		result.update({"status": status, "description": description})

	except Exception:
		error_text = r.text if r and r.text else "NO RESPONSE — Timeout or connection error"
		error_status = r.status_code if r else "NO STATUS CODE"

		add_jubilee_log(
			request_type="getAdmissionStatus",
			request_url=url,
			request_header=headers,
			request_body=str(params),
			response_data=error_text,
			status_code=error_status,
			company=inpatient_doc.company,
			ref_doctype="Inpatient Record",
			ref_docname=inpatient_record_name,
			card_no=authorization_no,
		)

		result["description"] = str(error_text)

	return result
