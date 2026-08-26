import json

import frappe
import requests
from frappe import _
from frappe.core.utils import html2text
from frappe.query_builder import DocType
from frappe.utils import date_diff, get_datetime, get_fullname, get_url_to_form, now_datetime, nowdate
from pypika.terms import Not

from hms_tz.hms_tz.doctype.inpatient_record.inpatient_record import admit_patient as local_admit_patient
from hms_tz.nhif.api.healthcare_utils import get_item_rate
from hms_tz.nhif.api.inpatient_record import get_last_encounter
from hms_tz.nhif.doctype.nhif_response_log.nhif_response_log import add_log
from hms_tz.nhif.nhif_api.referral import get_disease_code
from hms_tz.nhif.nhif_api.verification import get_poc_reference_no


@frappe.whitelist()
def get_admission_types(company=None, caller=None):
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

	url = f"{settings_doc.nhifservice_url}/api/Admissions/GetAdmissionTypes"
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	r = requests.request("Get", url, headers=headers, timeout=60)
	if r.status_code != 200:
		add_log(
			request_type="GetAdmissionTypes",
			request_url=url,
			request_header=headers,
			request_body="",
			response_data=r.text,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype="Healthcare Admission Type",
		)

	else:
		data = json.loads(r.text)
		add_log(
			request_type="GetAdmissionTypes",
			request_url=url,
			request_header=headers,
			request_body="",
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype="Healthcare Admission Type",
		)

		if len(data) == 0:
			return

		for row in data:
			admission = frappe.get_cached_value(
				"Healthcare Admission Type",
				{"admission_type_name": row["AdmissionTypeName"]},
				"name",
			)
			if admission:
				has_changed = False
				doc = frappe.get_cached_doc("Healthcare Admission Type", admission)

				if doc.admission_type_name != row["AdmissionTypeName"]:
					doc.admission_type_name = row["AdmissionTypeName"]
					has_changed = True

				if doc.alias != row["Alias"]:
					doc.alias = row["Alias"]
					has_changed = True

				if doc.admission_type_id != row["AdmissionTypeID"]:
					doc.admission_type_id = row["AdmissionTypeID"]
					has_changed = True

				if has_changed:
					doc.save(ignore_permissions=True)

			else:
				doc = frappe.new_doc("Healthcare Admission Type")
				doc.admission_type_name = row["AdmissionTypeName"]
				doc.alias = row["Alias"]
				doc.admission_type_id = row["AdmissionTypeID"]

				doc.save(ignore_permissions=True)

		if company and caller == "Front End":
			frappe.msgprint(
				"successfully fetched Admission Types",
				alert=True,
				indicator="green",
			)


@frappe.whitelist()
def get_discharge_types(company=None, caller=None):
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

	url = f"{settings_doc.nhifservice_url}/api/Admissions/GetDischargeTypes"
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	r = requests.request("Get", url, headers=headers, timeout=60)
	if r.status_code != 200:
		add_log(
			request_type="GetDischargeTypes",
			request_url=url,
			request_header=headers,
			request_body="",
			response_data=r.text,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype="Healthcare Discharge Type",
		)

	else:
		data = json.loads(r.text)
		add_log(
			request_type="GetDischargeTypes",
			request_url=url,
			request_header=headers,
			request_body="",
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype="Healthcare Discharge Type",
		)

		if len(data) == 0:
			return

		for row in data:
			discharge_type = frappe.get_cached_value(
				"Healthcare Discharge Type",
				{"discharge_type_name": row["DischargeTypeName"]},
				"name",
			)
			if discharge_type:
				has_changed = False
				doc = frappe.get_cached_doc("Healthcare Discharge Type", discharge_type)

				if doc.discharge_type_name != row["DischargeTypeName"]:
					doc.discharge_type_name = row["DischargeTypeName"]
					has_changed = True

				if doc.alias != row["Alias"]:
					doc.alias = row["Alias"]
					has_changed = True

				if doc.discharge_type_id != row["DischargeTypeID"]:
					doc.discharge_type_id = row["DischargeTypeID"]
					has_changed = True

				if has_changed:
					doc.save(ignore_permissions=True)

			else:
				doc = frappe.new_doc("Healthcare Discharge Type")
				doc.discharge_type_name = row["DischargeTypeName"]
				doc.alias = row["Alias"]
				doc.discharge_type_id = row["DischargeTypeID"]

				doc.save(ignore_permissions=True)

		if company and caller == "Front End":
			frappe.msgprint(
				"successfully fetched Discharge Types",
				alert=True,
				indicator="green",
			)


@frappe.whitelist()
def get_ward_types(company=None, caller=None):
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

	url = f"{settings_doc.nhifservice_url}/api/Admissions/GetWardTypes"
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	r = requests.request("Get", url, headers=headers, timeout=60)
	if r.status_code != 200:
		add_log(
			request_type="GetWardTypes",
			request_url=url,
			request_header=headers,
			request_body="",
			response_data=r.text,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype="Healthcare Ward Type",
		)

	else:
		data = json.loads(r.text)
		add_log(
			request_type="GetWardTypes",
			request_url=url,
			request_header=headers,
			request_body="",
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype="Healthcare Ward Type",
		)

		if len(data) == 0:
			return

		for row in data:
			ward_type = frappe.get_cached_value(
				"Healthcare Ward Type",
				{"ward_type_name": row["WardTypeName"]},
				"name",
			)
			if ward_type:
				has_changed = False
				doc = frappe.get_cached_doc("Healthcare Ward Type", ward_type)

				if doc.ward_type_name != row["WardTypeName"]:
					doc.ward_type_name = row["WardTypeName"]
					has_changed = True

				if doc.alias != row["Alias"]:
					doc.alias = row["Alias"]
					has_changed = True

				if doc.ward_type_id != row["WardTypeID"]:
					doc.ward_type_id = row["WardTypeID"]
					has_changed = True

				if doc.notification_required_after != row["NotificationRequiredAfter"]:
					doc.notification_required_after = row["NotificationRequiredAfter"]
					has_changed = True

				if doc.item_code != row["ItemCode"]:
					doc.item_code = row["ItemCode"]
					has_changed = True

				if has_changed:
					doc.save(ignore_permissions=True)

			else:
				doc = frappe.new_doc("Healthcare Ward Type")
				doc.ward_type_name = row["WardTypeName"]
				doc.alias = row["Alias"]
				doc.ward_type_id = row["WardTypeID"]
				doc.notification_required_after = row["NotificationRequiredAfter"]
				doc.item_code = row["ItemCode"]

				doc.save(ignore_permissions=True)

		if company and caller == "Front End":
			frappe.msgprint(
				"successfully fetched Ward Types",
				alert=True,
				indicator="green",
			)


@frappe.whitelist()
def get_room_types(company=None, caller=None):
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

	url = f"{settings_doc.nhifservice_url}/api/Admissions/GetRoomTypes"
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	r = requests.request("Get", url, headers=headers, timeout=60)
	if r.status_code != 200:
		add_log(
			request_type="GetRoomTypes",
			request_url=url,
			request_header=headers,
			request_body="",
			response_data=r.text,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype="Healthcare Room Type",
		)

	else:
		data = json.loads(r.text)
		add_log(
			request_type="GetRoomTypes",
			request_url=url,
			request_header=headers,
			request_body="",
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype="Healthcare Room Type",
		)

		if len(data) == 0:
			return

		for row in data:
			room_type = frappe.get_cached_value(
				"Healthcare Room Type",
				{"room_type_name": row["RoomTypeName"]},
				"name",
			)
			if room_type:
				has_changed = False
				doc = frappe.get_cached_doc("Healthcare Room Type", room_type)

				if doc.room_type_name != row["RoomTypeName"]:
					doc.room_type_name = row["RoomTypeName"]
					has_changed = True

				if doc.alias != row["Alias"]:
					doc.alias = row["Alias"]
					has_changed = True

				if doc.room_type_id != row["RoomTypeID"]:
					doc.room_type_id = row["RoomTypeID"]
					has_changed = True

				if has_changed:
					doc.save(ignore_permissions=True)

			else:
				doc = frappe.new_doc("Healthcare Room Type")
				doc.room_type_name = row["RoomTypeName"]
				doc.alias = row["Alias"]
				doc.room_type_id = row["RoomTypeID"]

				doc.save(ignore_permissions=True)

		if company and caller == "Front End":
			frappe.msgprint(
				"successfully fetched Room Types",
				alert=True,
				indicator="green",
			)


@frappe.whitelist()
def admit_patient(
	admission_type: str,
	service_unit: str,
	date_admitted: str,
	fingerprint: str,
	fpcode: str,
	biometric_method: str,
	ref_doctype: str,
	ref_docname: str,
):
	doc = frappe.get_cached_doc("Inpatient Record", ref_docname)
	mct_code = frappe.get_cached_value(
		"Healthcare Practitioner",
		doc.primary_practitioner,
		"tz_mct_code",
	)

	authorization_no = frappe.get_cached_value(
		"Patient Appointment",
		doc.patient_appointment,
		"authorization_number",
	)

	admission_type_id = frappe.get_cached_value(
		"Healthcare Admission Type", admission_type, "admission_type_id"
	)

	service_unit_type = doc.admission_service_unit_type
	ward_type, item_code = frappe.get_cached_value(
		"Healthcare Service Unit Type",
		service_unit_type,
		["ward_type", "item_code"],
	)
	if not ward_type:
		url = get_url_to_form("Healthcare Service Unit Type", service_unit_type)
		frappe.throw(
			f"Please select 'Ward Type' on Service Unit Type: <a href='{url}'><b>{service_unit_type}</b></a>"
		)

	ward_type_id = frappe.get_cached_value("Healthcare Ward Type", ward_type, "ward_type_id")

	room_type = frappe.get_cached_value("Healthcare Service Unit", service_unit, "room_type")
	if not room_type:
		url = get_url_to_form("Healthcare Service Unit", service_unit)
		frappe.throw(f"Please select 'Room Type' for Service Unit: <a href='{url}'><b>{service_unit}</b></a>")

	room_type_id = frappe.get_cached_value("Healthcare Room Type", room_type, "room_type_id")

	bed_charge = get_item_rate(item_code, doc.company, doc.insurance_subscription)

	admission_encounter_doc = frappe.get_cached_doc("Patient Encounter", doc.admission_encounter)
	clinical_notes = html2text(admission_encounter_doc.examination_detail).lstrip("\n")

	diagnosis_at_admission = []
	for row in admission_encounter_doc.patient_encounter_final_diagnosis:
		disease_code = get_disease_code(row.code)
		diagnosis_at_admission.append(disease_code)

	if len(diagnosis_at_admission) == 0:
		for row in admission_encounter_doc.patient_encounter_preliminary_diagnosis:
			disease_code = get_disease_code(row.code)
			diagnosis_at_admission.append(disease_code)

	payload = {
		"authorizationNo": authorization_no,
		"fullName": doc.patient_name,
		"gender": doc.gender,
		"dateOfBirth": str(doc.dob),
		"admissionTypeID": admission_type_id,
		"wardTypeID": ward_type_id,
		"roomTypeID": room_type_id,
		"chargesPerDay": bed_charge,
		"practitionerNo": mct_code,
		"diagnosisAtAdmission": ", ".join(diagnosis_at_admission),
		"practitionersRemarks": str(clinical_notes) or "",
		"dateAdmitted": get_datetime(date_admitted).isoformat(),
		"createdBy": admission_encounter_doc.practitioner,
	}

	payload = json.dumps(payload)

	settings_doc = frappe.get_cached_doc("HMS TZ Setting", doc.company)

	token = settings_doc.get_nhif_token()

	url = f"{settings_doc.nhifservice_url}/api/Admissions/AdmitPatient"
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	r = requests.request("Post", url, data=payload, headers=headers, timeout=60)
	if r.status_code != 200:
		add_log(
			request_type="AdmitPatient",
			request_url=url,
			request_header=headers,
			request_body=payload,
			response_data=r.text,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype=ref_doctype,
			ref_docname=ref_docname,
		)
		data = json.loads(r.text) if r.text else {}
		doc.add_comment(
			comment_type="Comment",
			text=f"NHIF Admission failed<br><br>Status Code: {r.status_code}<br>NHIF Response: <b>{data.get('message') or r.text}<b>",
		)
		frappe.db.commit()

		frappe.throw(
			title="NHIF API Error",
			msg=f"Failed to Admit Patient<br><br>Status Code: {r.status_code}<br>NHIF Response: <b>{r.text}</b>",
		)

	else:
		data = json.loads(r.text)
		add_log(
			request_type="AdmitPatient",
			request_url=url,
			request_header=headers,
			request_body=payload,
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype=ref_doctype,
			ref_docname=ref_docname,
		)

		doc.add_comment(
			comment_type="Comment",
			text=f"NHIF Admission Successful<br><br>Status Code: {r.status_code}<br>AdmissionNo: <b>{data.get('AdmissionNo')}<b>",
		)

		point_of_care_name = ""
		if ward_type == "Normal Ward":
			point_of_care_name = "Normal Ward Admission"
		elif ward_type == "HDU":
			point_of_care_name = "HDU Admission"
		elif ward_type == "ICU":
			point_of_care_name = "ICU Admission"

		reference_data = get_poc_reference_no(
			point_of_care_name,
			doc.primary_practitioner,
			fingerprint,
			fpcode,
			biometric_method,
			settings_doc.name,
			appointment_id=doc.patient_appointment,
			authorization_no=authorization_no,
			settings_doc=settings_doc,
			practitioner_no=mct_code,
			ref_doctype=ref_doctype,
			ref_docname=ref_docname,
		)

		admission_no = data.get("AdmissionNo")
		poc_reference_no = reference_data.get("ReferenceNo") if reference_data else ""

		if not admission_no:
			frappe.throw(
				_("Cannot admit NHIF patient without an Admission Number from NHIF."),
				title=_("Admission Number Missing"),
			)

		local_admit_patient(
			doc,
			service_unit,
			date_admitted,
			admission_no=admission_no,
			admission_type=admission_type,
			poc_reference_no=poc_reference_no,
		)

		return {
			"admission_no": admission_no,
			"poc_reference_no": poc_reference_no,
			"admitted": True,
		}


@frappe.whitelist()
def discharge_patient(discharge_type, ref_doctype, ref_docname):
	doc = frappe.get_cached_doc("Inpatient Record", ref_docname)
	mct_code = frappe.get_cached_value("Healthcare Practitioner", doc.discharge_practitioner, "tz_mct_code")

	discharge_type_id = frappe.get_cached_value(
		"Healthcare Discharge Type", discharge_type, "discharge_type_id"
	)

	referred_to_facility_code = ""
	if "Refferal" in discharge_type:
		filters = {
			"patient": doc.patient,
			"appointment": doc.patient_appointment,
			"source_facility": doc.company,
			"referral_type": "Treatment",
			"referral_no": ("is", "set"),
		}
		referred_to_facility_code = frappe.get_cached_value(
			"Healthcare Referral", filters, "referred_facility_code"
		)
		if not referred_to_facility_code:
			frappe.throw(
				title="Missing Referral",
				msg=f"""<p style="margin-left: 20px; margin-bottom: 0;">Discharge Type: <b>{discharge_type}</b></p><div style="border-left: 4px solid #ffc107; background-color: #fff3cd; padding: 15px; border-radius: 10px; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1); margin: 10px;">\
                    <p class="text-center"><i>Please create a Referral for Patient: <b>{doc.patient}</b> with Refferal Type as <b>Treatment</b> before Discharging.</i></p>\
                    </div>""",
			)

	discharge_encounter_doc = frappe.get_cached_doc("Patient Encounter", doc.discharge_encounter)
	clinical_notes = html2text(discharge_encounter_doc.examination_detail).lstrip("\n")

	diagnosis_at_discharge = []
	for row in discharge_encounter_doc.patient_encounter_final_diagnosis:
		disease_code = get_disease_code(row.code)
		diagnosis_at_discharge.append(disease_code)

	if len(diagnosis_at_discharge) == 0:
		for row in discharge_encounter_doc.patient_encounter_preliminary_diagnosis:
			disease_code = get_disease_code(row.code)
			diagnosis_at_discharge.append(disease_code)

	payload = {
		"admissionNo": doc.admission_no,
		"practitionerNo": mct_code,
		"practitionersRemarks": clinical_notes or "",
		"dischargeTypeID": discharge_type_id,
		"dateDischarged": get_datetime(now_datetime()).isoformat(),
		"diagnosisAtDischarge": ", ".join(diagnosis_at_discharge),
		"referredToFacilityCode": referred_to_facility_code,
		"createdBy": get_fullname(frappe.session.user),
	}

	payload = json.dumps(payload)

	settings_doc = frappe.get_cached_doc("HMS TZ Setting", doc.company)

	token = settings_doc.get_nhif_token()

	url = f"{settings_doc.nhifservice_url}/api/Admissions/DishargePatient"
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	r = requests.request("Post", url, data=payload, headers=headers, timeout=60)
	if r.status_code != 200:
		add_log(
			request_type="DishargePatient",
			request_url=url,
			request_header=headers,
			request_body=payload,
			response_data=r.text,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype=ref_doctype,
			ref_docname=ref_docname,
		)
		doc.add_comment(
			comment_type="Comment",
			text=f"NHIF Discharge failed<br><br>Status Code: {r.status_code}<br>NHIF Response: <b>{r.text}<b>",
		)
		frappe.db.commit()
		frappe.throw(
			title="NHIF API Error",
			msg=f"Failed to Discharge Patient<br><br>Status Code: {r.status_code}<br>NHIF Response: <b>{r.text}</b>",
		)

	else:
		data = json.loads(r.text)
		add_log(
			request_type="DishargePatient",
			request_url=url,
			request_header=headers,
			request_body=payload,
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype=ref_doctype,
			ref_docname=ref_docname,
		)
		doc.add_comment(
			comment_type="Comment",
			text=f"NHIF Discharge Successful<br><br>Status Code: {r.status_code}<br>AdmissionID: <b>{data.get('AdmissionID')}<b>",
		)

		return data


@frappe.whitelist()
def transfer_patient(
	service_unit_type,
	service_unit,
	date_transferred,
	fingerprint,
	fpcode,
	biometric_method,
	ref_doctype,
	ref_docname,
):
	doc = frappe.get_cached_doc("Inpatient Record", ref_docname)

	# find the last encounter to find the practitioner from the last encounter
	last_encounter = get_last_encounter(doc.patient, doc.name)
	practitioner, notes = frappe.get_cached_value(
		"Patient Encounter", last_encounter, ["practitioner", "examination_detail"]
	)
	mct_code = frappe.get_cached_value("Healthcare Practitioner", practitioner, "tz_mct_code")
	clinical_notes = html2text(notes).lstrip("\n")

	ward_type, item_code = frappe.get_cached_value(
		"Healthcare Service Unit Type",
		service_unit_type,
		["ward_type", "item_code"],
	)
	if not ward_type:
		url = get_url_to_form("Healthcare Service Unit Type", service_unit_type)
		frappe.throw(
			f"Please select 'Ward Type' on Service Unit Type: <a href='{url}'><b>{service_unit_type}</b></a>"
		)

	ward_type_id = frappe.get_cached_value("Healthcare Ward Type", ward_type, "ward_type_id")

	room_type = frappe.get_cached_value("Healthcare Service Unit", service_unit, "room_type")
	if not room_type:
		url = get_url_to_form("Healthcare Service Unit", service_unit)
		frappe.throw(f"Please select 'Room Type' for Service Unit: <a href='{url}'><b>{service_unit}</b></a>")

	room_type_id = frappe.get_cached_value("Healthcare Room Type", room_type, "room_type_id")

	bed_charge = get_item_rate(item_code, doc.company, doc.insurance_subscription)

	payload = {
		"admissionNo": doc.admission_no,
		"practitionerNo": mct_code,
		"practitionersRemarks": clinical_notes or "",
		"wardTypeID": ward_type_id,
		"roomTypeID": room_type_id,
		"chargesPerDay": bed_charge,
		"dateTransferred": get_datetime(date_transferred).isoformat(),
		"createdBy": get_fullname(frappe.session.user),
	}

	payload = json.dumps(payload)

	settings_doc = frappe.get_cached_doc("HMS TZ Setting", doc.company)

	token = settings_doc.get_nhif_token()

	url = f"{settings_doc.nhifservice_url}/api/Admissions/TransferPatient"
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	r = requests.request("Post", url, data=payload, headers=headers, timeout=60)
	if r.status_code != 200:
		add_log(
			request_type="TransferPatient",
			request_url=url,
			request_header=headers,
			request_body=payload,
			response_data=r.text,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype=ref_doctype,
			ref_docname=ref_docname,
		)
		doc.add_comment(
			comment_type="Comment",
			text=f"NHIF Transfer failed<br><br>Status Code: {r.status_code}<br>NHIF Response: <b>{r.text}<b>",
		)
		frappe.db.commit()

		frappe.throw(
			title="NHIF API Error",
			msg=f"Failed to Transfer Patient<br><br>Status Code: {r.status_code}<br>NHIF Response: <b>{r.text}</b>",
		)
	else:
		data = json.loads(r.text)
		add_log(
			request_type="TransferPatient",
			request_url=url,
			request_header=headers,
			request_body=payload,
			response_data=data,
			status_code=r.status_code,
			company=settings_doc.name,
			ref_doctype=ref_doctype,
			ref_docname=ref_docname,
		)

		doc.add_comment(
			comment_type="Comment",
			text=f"NHIF Transfer Successful<br><br>Status Code: {r.status_code}<br>AdmissionID: <b>{data.get('AdmissionID')}<b>",
		)

		point_of_care_name = ""
		if ward_type == "Normal Ward":
			point_of_care_name = "Normal Ward Admission"
		elif ward_type == "HDU":
			point_of_care_name = "HDU Admission"
		elif ward_type == "ICU":
			point_of_care_name = "ICU Admission"

		reference_data = get_poc_reference_no(
			point_of_care_name,
			practitioner,
			fingerprint,
			fpcode,
			biometric_method,
			settings_doc.name,
			appointment_id=doc.patient_appointment,
			authorization_no="",
			settings_doc=settings_doc,
			practitioner_no=mct_code,
			ref_doctype=ref_doctype,
			ref_docname=ref_docname,
		)

		return {
			"poc_reference_no": reference_data.get("ReferenceNo") if reference_data else "",
		}


def send_overstay_nofication():
	settings = frappe.db.get_all("HMS TZ Setting", filters={"enable_nhif_api": 1}, fields=["company"])
	if len(settings) == 0:
		return

	for d in settings:
		ip_records = get_inpatient_records(d.company)

		settings_doc = frappe.get_cached_doc("HMS TZ Setting", d.company)

		token = settings_doc.get_nhif_token()

		url = f"{settings_doc.nhifservice_url}/api/Admissions/SendOverstayNotification"
		headers = {
			"Content-Type": "application/json",
			"Authorization": f"Bearer {token}",
		}

		for row in ip_records:
			inpatient_doc = frappe.get_cached_doc("Inpatient Record", row.inpatient_id)
			inpatient_occupancies = inpatient_doc.get("inpatient_occupancies")
			if len(inpatient_occupancies) == 0:
				continue

			last_bed = inpatient_occupancies[-1]
			notification_days = get_notification_days_per_ward(last_bed.service_unit)

			if inpatient_doc.get("last_overstay_date") and notification_days:
				days_diff = date_diff(inpatient_doc.get("last_overstay_date"), nowdate())
				if days_diff and days_diff <= notification_days:
					continue

			notes = frappe.db.get_value(
				"Patient Encounter",
				{"inpatient_record": inpatient_doc.name, "duplicated": 0},
				"examination_detail",
			)
			clinical_notes = html2text(notes).lstrip("\n") if notes else ""

			payload = {
				"admissionNo": inpatient_doc.admission_no,
				"practitionerNo": row.tz_mct_code,
				"practitionersRemarks": clinical_notes or "",
				"createdBy": get_fullname(inpatient_doc.owner),
			}

			payload = json.dumps(payload)

			r = requests.request("Post", url, data=payload, headers=headers, timeout=60)
			if r.status_code != 200:
				add_log(
					request_type="SendOverstayNotification",
					request_url=url,
					request_header=headers,
					request_body=payload,
					response_data=r.text,
					status_code=r.status_code,
					company=settings_doc.name,
					ref_doctype=inpatient_doc.doctype,
					ref_docname=inpatient_doc.name,
				)

				inpatient_doc.add_comment(
					comment_type="Comment",
					text=f"NHIF Overstay Notification failed<br><br>Status Code: {r.status_code}<br>NHIF Response: <b>{r.text}<b>",
				)
				continue

			else:
				data = json.loads(r.text)
				add_log(
					request_type="SendOverstayNotification",
					request_url=url,
					request_header=headers,
					request_body=payload,
					response_data=data,
					status_code=r.status_code,
					company=settings_doc.name,
					ref_doctype=inpatient_doc.doctype,
					ref_docname=inpatient_doc.name,
				)

				frappe.db.set_value(
					inpatient_doc.doctype,
					inpatient_doc.name,
					"last_overstay_date",
					nowdate(),
				)

				inpatient_doc.add_comment(
					comment_type="Comment",
					text=f"NHIF Overstay Notification Successful<br><br>Status Code: {r.status_code}<br><b>{data}<b>",
				)


def get_inpatient_records(company):
	ip = DocType("Inpatient Record")
	pe = DocType("Patient Encounter")
	hp = DocType("Healthcare Practitioner")

	ip_records = (
		frappe.qb.from_(ip)
		.inner_join(pe)
		.on(pe.inpatient_record == ip.name)
		.inner_join(hp)
		.on(pe.practitioner == hp.name)
		.select(
			ip.name.as_("inpatient_id"),
			ip.admission_no,
			ip.owner,
			ip.admission_instruction,
			pe.practitioner,
			hp.tz_mct_code,
		)
		.where(
			Not(ip.status.isin(["Admission Scheduled", "Discharged"]))
			& (ip.company == company)
			& (ip.insurance_company.isnotnull() & ip.insurance_company != "")
			& (ip.insurance_company.like("NHIF"))
			& (ip.admission_no.isnotnull() & ip.admission_no != "")
			& (pe.appointment == ip.patient_appointment)
			& (pe.company == company)
			& (pe.duplicated == 0)
		)
	).run(as_dict=True)

	return ip_records


def get_notification_days_per_ward(service_unit):
	hsu = DocType("Healthcare Service Unit")
	hsut = DocType("Healthcare Service Unit Type")
	hwt = DocType("Healthcare Ward Type")

	hwt_data = (
		frappe.qb.from_(hsu)
		.inner_join(hsut)
		.on(hsu.service_unit_type == hsut.name)
		.inner_join(hwt)
		.on(hsut.ward_type == hwt.name)
		.select(hwt.notification_required_after)
		.where(hsu.name == service_unit)
	).run(as_dict=True)

	return hwt_data[0].notification_required_after if len(hwt_data) > 0 else None
