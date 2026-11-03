import json

import frappe
import requests
from frappe.model.naming import make_autoname
from frappe.utils import now_datetime
from frappe.utils.background_jobs import enqueue

from hms_tz.api.insurance import get_insurance_items
from hms_tz.nhif.doctype.nhif_response_log.nhif_response_log import add_log

STG_SERVICE_TYPES = (
	"Lab Test Template",
	"Radiology Examination Template",
	"Clinical Procedure Template",
	"Medication",
	"Therapy Type",
)
STG_TYPE_LISTS = {"Diagnosis": "Diagnoses", "Treatment": "Treatments"}


@frappe.whitelist()
def enqueue_get_diseases(company):
	enqueue(
		method=get_diseases,
		job_name="get_diseases",
		queue="default",
		timeout=1800,
		is_async=True,
		company=company,
	)
	frappe.msgprint("Fetch Diseases via background job", alert=True)


@frappe.whitelist()
def enqueue_get_stg_records(company):
	frappe.has_permission("NHIF STG", "create", throw=True)
	enqueue(
		method=get_stg_records,
		job_name="get_stg_records",
		queue="long",
		timeout=3600,
		is_async=True,
		company=company,
	)
	frappe.msgprint("Fetch STG records via background job", alert=True)


@frappe.whitelist()
def get_points_of_care(company=None, caller=None):
	if not company:
		settings = frappe.db.get_all(
			"HMS TZ Setting",
			filters={"enable_nhif_api": 1},
			fields=["company"],
		)
		company = settings[0].company

	if not company:
		return

	settings_doc = frappe.get_cached_doc("HMS TZ Setting", company)

	token = settings_doc.get_nhif_token()

	url = f"{settings_doc.nhifservice_url}/api/Reference/GetPointsOfCare"
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	r = requests.request("Get", url, headers=headers, timeout=60)
	if r.status_code != 200:
		add_log(
			request_type="GetPointsOfCare",
			request_url=url,
			request_header=headers,
			request_body="",
			response_data=r.text,
			status_code=r.status_code,
			company=settings_doc.name,
		)

	else:
		data = json.loads(r.text)
		add_log(
			request_type="GetPointsOfCare",
			request_url=url,
			request_header=headers,
			request_body="",
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
		)

		for poc in data:
			try:
				if frappe.db.exists(
					"Healthcare Points of Care",
					poc.get("PointOfCareName"),
					cache=True,
				):
					has_changed = False
					hpc_doc = frappe.get_cached_doc("Healthcare Points of Care", poc.get("PointOfCareName"))

					if hpc_doc.point_of_care_id != str(poc.get("PointOfCareID")):
						has_changed = True
						hpc_doc.point_of_care_id = poc.get("PointOfCareID")

					if hpc_doc.point_of_care_code != str(poc.get("PointOfCareCode")):
						has_changed = True
						hpc_doc.point_of_care_code = poc.get("PointOfCareCode")

					if has_changed:
						hpc_doc.save(ignore_permissions=True)

				else:
					hpc_doc = frappe.new_doc("Healthcare Points of Care")
					hpc_doc.point_of_care_name = poc.get("PointOfCareName")
					hpc_doc.point_of_care_id = poc.get("PointOfCareID")
					hpc_doc.point_of_care_code = poc.get("PointOfCareCode")
					hpc_doc.save(ignore_permissions=True)
					hpc_doc.reload()
			except Exception:
				traceback = frappe.get_traceback()
				frappe.log_error(title="GetPointsOfCare", message=traceback)

		if company and caller == "Front End":
			frappe.msgprint(
				"successfully fetched Points of Care",
				alert=True,
				indicator="green",
			)


def get_diseases(company=None):
	if not company:
		settings = frappe.db.get_all(
			"HMS TZ Setting",
			filters={"enable_nhif_api": 1},
			fields=["company"],
		)
		company = settings[0].company

	if not company:
		return

	settings_doc = frappe.get_cached_doc("HMS TZ Setting", company)

	token = settings_doc.get_nhif_token()

	url = f"{settings_doc.nhif_claim_url}/api/Reference/GetDiseases"
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	r = requests.request("Get", url, headers=headers, timeout=180)
	if r.status_code != 200:
		add_log(
			request_type="GetDiseases",
			request_url=url,
			request_header=headers,
			request_body="",
			response_data=r.text,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype="Code Value",
		)

	else:
		data = json.loads(r.text)
		add_log(
			request_type="GetDiseases",
			request_url=url,
			request_header=headers,
			request_body="",
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype="Code Value",
		)

		if len(data) == 0:
			return

		medical_code_standards = [row["ICDVersionCode"] for row in data if row.get("ICDVersionCode")]
		medical_code_standards = list(set(medical_code_standards))
		for code in medical_code_standards:
			if not frappe.db.exists("Code System", code):
				mcs_doc = frappe.new_doc("Code System")
				mcs_doc.code_system = code
				mcs_doc.save(ignore_permissions=True)
				mcs_doc.reload()

		for disease in data:
			if not disease.get("ICDVersionCode") or not disease.get("DiseaseCode"):
				continue

			try:
				if frappe.db.exists(
					"Code Value",
					{
						"code_value": disease.get("DiseaseCode"),
						"code_system": disease.get("ICDVersionCode"),
					},
					cache=True,
				):
					update_medical_code(disease)
				else:
					create_medical_code(disease)
			except Exception as e:
				traceback = frappe.get_traceback()
				frappe.log_error(
					title=f"Disease: {disease.get('DiseaseCode')} {disease.get('ICDVersionCode')}",
					message=f"Error: <b>{e}</b>\n\n<br>{traceback}",
					reference_doctype="Code Value",
				)


def update_medical_code(disease):
	has_changed = False
	medical_code_id = f"{disease.get('ICDVersionCode')} {disease.get('DiseaseCode')}"
	mc_doc = frappe.get_cached_doc("Code Value", medical_code_id)

	# if mc_doc.code_system != disease.get("ICDVersionCode"):
	#     has_changed = True
	#     mc_doc.code_system = disease.get("ICDVersionCode")

	if mc_doc.definition != disease.get("DiseaseName"):
		has_changed = True
		mc_doc.definition = disease.get("DiseaseName")

	if disease.get("IsNonSpecific") and mc_doc.is_non_specific != disease.get("IsNonSpecific"):
		has_changed = True
		mc_doc.is_non_specific = disease.get("IsNonSpecific")

	# if mc_doc.disabled == 1:
	#     has_changed = True
	#     mc_doc.disabled = 0

	if has_changed:
		mc_doc.save(ignore_permissions=True)


def create_medical_code(disease):
	mc_doc = frappe.new_doc("Code Value")
	mc_doc.code_value = disease.get("DiseaseCode")
	mc_doc.code_system = disease.get("ICDVersionCode")
	mc_doc.definition = disease.get("DiseaseName")
	mc_doc.is_non_specific = disease.get("IsNonSpecific")
	mc_doc.save(ignore_permissions=True)


def get_stg_records(company=None):
	if not company:
		settings = frappe.db.get_all(
			"HMS TZ Setting",
			filters={"enable_nhif_api": 1},
			fields=["company"],
		)
		company = settings[0].company

	settings_doc = frappe.get_cached_doc("HMS TZ Setting", company)
	token = settings_doc.get_nhif_token()

	url = f"{settings_doc.nhif_claim_url}/api/Reference/GetSTGTreatments"
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	r = requests.request("Get", url, headers=headers, timeout=180)
	add_log(
		request_type="GetSTGTreatments",
		request_url=url,
		request_header=headers,
		request_body="",
		response_data=r.text,
		status_code=r.status_code,
		company=settings_doc.name,
		ref_doctype="NHIF STG",
	)
	if r.status_code != 200:
		return

	sync_stg_records(json.loads(r.text), settings_doc.nhif_customer_name)


def sync_stg_records(stg_data, nhif_customer):
	stg_entries = dict.fromkeys(get_stg_entries(stg_data))
	if not stg_entries:
		frappe.log_error(
			title="NHIF STG: empty GetSTGTreatments response",
			message="No STG records were returned, so no NHIF STG was created or disabled.",
			reference_doctype="NHIF STG",
		)
		return

	# Disabling many removed STGs can pass the per-transaction write limit; reruns skip finished rows.
	auto_commit = frappe.db.auto_commit_on_many_writes
	frappe.db.auto_commit_on_many_writes = True
	try:
		create_stg_records(stg_entries, nhif_customer)
		disable_removed_stg_records(stg_entries)
	finally:
		frappe.db.auto_commit_on_many_writes = auto_commit


def get_stg_entries(stg_data):
	"""Yield (stg_type, code, item_code) for each Diagnoses and Treatments row."""
	for disease in stg_data:
		for stg_type, list_key in STG_TYPE_LISTS.items():
			for row in disease.get(list_key) or []:
				yield (stg_type, disease.get("DiseaseCode"), row.get("ItemCode"))


def create_stg_records(stg_entries, nhif_customer):
	"""Create NHIF STG rows for STG item codes that map to a service template and do not exist yet."""
	service_map = get_insurance_items(nhif_customer)
	code_value_map = {
		row.code_value: row.name
		for row in frappe.get_all(
			"Code Value",
			filters={"code_system": ["like", "ICD%"]},
			fields=["name", "code_value"],
		)
	}
	existing_keys = {
		tuple(row)
		for row in frappe.get_all(
			"NHIF STG",
			fields=["stg_type", "code", "item_code", "service_type", "service_name"],
			as_list=True,
		)
	}

	values = []
	for stg_type, code, item_code in stg_entries:
		for service in service_map.get(item_code, []):
			key = (stg_type, code, item_code, service.service_type, service.service_name)
			if service.service_type not in STG_SERVICE_TYPES or key in existing_keys:
				continue

			existing_keys.add(key)
			values.append(
				(
					make_autoname(key="hash"),
					now_datetime(),
					frappe.session.user,
					*key,
					code_value_map.get(code),
				)
			)

	frappe.db.bulk_insert(
		"NHIF STG",
		fields=[
			"name",
			"creation",
			"owner",
			"stg_type",
			"code",
			"item_code",
			"service_type",
			"service_name",
			"code_value",
		],
		values=values,
		ignore_duplicates=True,
	)


def disable_removed_stg_records(stg_entries):
	"""Disable enabled NHIF STG rows whose STG entry is no longer in the MoH list."""
	for row in frappe.get_all(
		"NHIF STG",
		filters={"disabled": 0},
		fields=["name", "stg_type", "code", "item_code"],
	):
		if (row.stg_type, row.code, row.item_code) in stg_entries:
			continue

		doc = frappe.get_doc("NHIF STG", row.name)
		doc.db_set("disabled", 1)
		doc.add_comment(
			"Comment",
			text=f"Disabled: MoH removed {row.stg_type} item code {row.item_code} for disease code {row.code} from the STG list.",
		)
