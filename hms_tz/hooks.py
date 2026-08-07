# -*- coding: utf-8 -*-
from __future__ import unicode_literals

app_name = "hms_tz"
app_title = "HMS TZ"
app_publisher = "Aakvatech"
app_description = "HMS TZ"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "info@aakvatech.com"
app_license = "MIT"


# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/hms_tz/css/hms_tz.css"
# app_include_js = "/assets/hms_tz/js/hms_tz.js"
app_include_js = "hms_tz.bundle.js"

# include js, css files in header of web template
# web_include_css = "/assets/hms_tz/css/hms_tz.css"
# web_include_js = "/assets/hms_tz/js/hms_tz.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "hms_tz/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Patient Appointment": "nhif/api/patient_appointment.js",
    "Patient": "nhif/api/patient.js",
    "Sales Order": "nhif/api/sales_order.js",
    "Sales Invoice": "nhif/api/sales_invoice.js",
    "Patient Encounter": "nhif/api/patient_encounter.js",
    "Lab Test": "nhif/api/lab_test.js",
    "Healthcare Service Order": "nhif/api/service_order.js",
    "Healthcare Insurance Company": "nhif/api/insurance_company.js",
    "Vital Signs": "nhif/api/vital_signs.js",
    "Healthcare Insurance Subscription": "nhif/api/insurance_subscription.js",
    "Inpatient Record": "nhif/api/inpatient_record.js",
    "Healthcare Service Unit": "nhif/api/service_unit.js",
    "Therapy Plan": "nhif/api/therapy_plan.js",
    "Therapy Session": "nhif/api/therapy_session.js",
    "Clinical Procedure": "nhif/api/clinical_procedure.js",
    "Medical Department": "nhif/api/medical_department.js",
    "Delivery Note": "nhif/api/delivery_note.js",
    "Radiology Examination": "nhif/api/radiology_examination.js",
}
# csf_tz.nhif.api.patient_appointment
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}

doctype_list_js = {
    "Therapy Plan": ["nhif/api/therapy_plan_list.js"],
    "Custom Field": "hms_tz/patches/custom_fields/custom_field.js",
    "Property Setter": "hms_tz/patches/property_setter/property_setter.js",
}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "hms_tz.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "hms_tz.install.before_install"
after_install = "hms_tz.install.after_install"


after_migrate = [
    "hms_tz.patches.custom_fields.create_custom_fields.execute",
    "hms_tz.patches.property_setter.create_property_setters.execute",
]


# Login
# -----
# on_login = "hms_tz.api.login.before_login"


# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "hms_tz.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Patient Appointment": {
        "before_insert": "hms_tz.nhif.api.patient_appointment.before_insert",
        "validate": "hms_tz.nhif.api.patient_appointment.make_next_doc",
    },
    "Vital Signs": {
        "on_submit": "hms_tz.nhif.api.patient_appointment.make_encounter",
    },
    "Patient": {
        "validate": "hms_tz.nhif.api.patient.validate",
        "after_insert": "hms_tz.nhif.api.patient.after_insert",
    },
    # "Healthcare Insurance Claim": {
    #     "before_insert": [
    #         "hms_tz.nhif.api.insurance_claim.set_patient_encounter",
    #         "hms_tz.nhif.api.insurance_claim.set_price",
    #     ]
    # },
    "Patient Encounter": {
        "before_submit": "hms_tz.nhif.api.patient_encounter.before_submit",
        "before_save": "hms_tz.nhif.api.patient_encounter.on_submit_validation",
        "on_trash": "hms_tz.nhif.api.patient_encounter.on_trash",
        "on_submit": [
            "hms_tz.nhif.api.patient_encounter.on_submit",
            "hms_tz.nhif.api.sales_order.create_sales_order",
        ],
        "before_insert": "hms_tz.nhif.api.patient_encounter.before_insert",
        "after_insert": "hms_tz.nhif.api.patient_encounter.after_insert",
    },
    "Healthcare Service Order": {
        "before_insert": "hms_tz.nhif.api.service_order.set_missing_values",
    },
    "Sales Invoice": {
        "before_submit": "hms_tz.nhif.api.sales_invoice.before_submit",
        "on_submit": "hms_tz.nhif.api.sales_invoice.on_submit",
        "validate": "hms_tz.nhif.api.sales_invoice.validate",
    },
    "Healthcare Insurance Subscription": {
        "before_insert": "hms_tz.nhif.api.insurance_subscription.before_insert",
        "on_submit": "hms_tz.nhif.api.insurance_subscription.on_submit",
        "before_cancel": "hms_tz.nhif.api.insurance_subscription.on_cancel",
        "on_update_after_submit": "hms_tz.nhif.api.insurance_subscription.on_update_after_submit",
        "validate": "hms_tz.nhif.api.insurance_subscription.validate",
    },
    "Practitioner Availability": {
        "validate": "hms_tz.nhif.api.practitioner_availability.validate",
        "on_trash": "hms_tz.nhif.api.practitioner_availability.on_trash",
    },
    "Lab Test": {
        "onload": "hms_tz.nhif.api.lab_test.onload",
        "before_submit": "hms_tz.nhif.api.lab_test.before_submit",
        "on_submit": "hms_tz.nhif.api.lab_test.on_submit",
        "after_insert": "hms_tz.nhif.api.lab_test.after_insert",
        "on_trash": "hms_tz.nhif.api.lab_test.on_trash",
        "on_cancel": "hms_tz.nhif.api.lab_test.on_cancel",
        "validate": "hms_tz.nhif.api.lab_test.validate",
    },
    "Radiology Examination": {
        "after_insert": "hms_tz.nhif.api.radiology_examination.after_insert",
        "onload": "hms_tz.nhif.api.radiology_examination.onload",
        "before_submit": "hms_tz.nhif.api.radiology_examination.before_submit",
        "on_submit": "hms_tz.nhif.api.radiology_examination.on_submit",
        "on_cancel": "hms_tz.nhif.api.radiology_examination.on_cancel",
    },
    "Clinical Procedure": {
        "after_insert": "hms_tz.nhif.api.clinical_procedure.after_insert",
        "before_save": "hms_tz.nhif.api.clinical_procedure.before_save",
        "onload": "hms_tz.nhif.api.clinical_procedure.onload",
        "before_submit": "hms_tz.nhif.api.clinical_procedure.before_submit",
        "on_submit": "hms_tz.nhif.api.clinical_procedure.on_submit",
        "on_update_after_submit": "hms_tz.nhif.api.clinical_procedure.on_update_after_submit",
    },
    "Delivery Note": {
        "validate": "hms_tz.nhif.api.delivery_note.validate",
        "onload": "hms_tz.nhif.api.delivery_note.onload",
        "after_insert": "hms_tz.nhif.api.delivery_note.after_insert",
        "before_submit": "hms_tz.nhif.api.delivery_note.before_submit",
        "on_submit": [
            "hms_tz.nhif.api.delivery_note.on_submit",
            "hms_tz.hms_tz.doctype.nurse_record.nurse_record.create_imo_from_delivery_note",
        ],
        "on_cancel": "hms_tz.nhif.api.delivery_note.on_cancel",
    },
    "Inpatient Record": {
        "validate": "hms_tz.nhif.api.inpatient_record.validate",
        "before_insert": "hms_tz.nhif.api.inpatient_record.before_insert",
        "before_save": "hms_tz.nhif.api.inpatient_record.before_save",
        "after_insert": "hms_tz.nhif.api.inpatient_record.after_insert",
    },
    "Prescription Dosage": {
        "before_insert": "hms_tz.nhif.api.prescription_dosage.before_insert",
    },
    "Sales Order": {
        "validate": "hms_tz.nhif.api.sales_order.validate",
        "before_submit": "hms_tz.nhif.api.sales_order.before_submit",
    },
    "Therapy Plan": {
        "before_insert": "hms_tz.nhif.api.therapy_plan.before_insert",
        "after_insert": "hms_tz.nhif.api.therapy_plan.after_insert",
        "validate": "hms_tz.nhif.api.therapy_plan.validate",
    },
    "Therapy Session": {
        "before_insert": "hms_tz.nhif.api.therapy_session.before_insert",
        "after_insert": "hms_tz.nhif.api.therapy_session.after_insert",
        "before_submit": "hms_tz.nhif.api.therapy_session.before_submit",
        "on_submit": "hms_tz.nhif.api.therapy_session.on_submit",
    },
    "Patient Medical Record": {
        "before_insert": "hms_tz.nhif.api.medical_record.before_insert",
    },
}

# Scheduled Tasks
# ---------------

scheduler_events = {
    # 	"all": [
    # 		"hms_tz.tasks.all"
    # 	],
    # "cron": {"*/1 * * * *": ["hms_tz.nhif.api.service_order.real_auto_submit"]},
    "hourly": ["hms_tz.nhif.api.healthcare_utils.set_uninvoiced_so_closed"],
    "daily": ["hms_tz.nhif.api.inpatient_record.daily_update_inpatient_occupancies"],
    "cron": {
        # Routine for every 15 minutes: auto-create Nurse Records for admitted patients
        "*/15 * * * *": [
            "hms_tz.hms_tz.doctype.nursing_schedule.nursing_schedule.create_nurse_records_for_admitted_patients"
        ],
        # Routine for every day 00:01 am at night
        "1 0 * * *": ["hms_tz.nhif.api.healthcare_utils.auto_submit_nhif_patient_claim"],
        # Routine for every day 01:30am at night
        "30 1 * * *": [
            "hms_tz.nhif.api.healthcare_utils.enqueue_auto_create_nhif_patient_claims",
            "hms_tz.nhif.nhif_api.admission.send_overstay_nofication",
        ],
        # Routine for every day 2:30am at night
        "30 2 * * *": ["hms_tz.nhif.api.healthcare_utils.delete_or_cancel_draft_document"],
        # Routine for every 10min
        "*/10 * * * *": ["hms_tz.nhif.api.healthcare_utils.create_invoiced_items_if_not_created"],
        # Routine for every day every after 30min from 03:00am to 05:00am
        "*/30 3-4 * * *": ["hms_tz.nhif.api.healthcare_utils.auto_finalize_patient_encounters"],
        # Routine for every Saturday 01:00 am at night
        "0 1 * * 6": [
            "hms_tz.nhif.nhif_api.verification.get_visit_types",
            "hms_tz.nhif.nhif_api.verification.get_card_verifier",
            "hms_tz.nhif.nhif_api.reference.get_points_of_care",
            "hms_tz.nhif.nhif_api.reference.get_diseases",
            "hms_tz.nhif.nhif_api.price_package.get_nhif_schemes",
            # "hms_tz.nhif.nhif_api.price_package.get_nhif_products",
            "hms_tz.nhif.nhif_api.price_package.get_item_types",
            "hms_tz.nhif.nhif_api.admission.get_admission_types",
            "hms_tz.nhif.nhif_api.admission.get_discharge_types",
            "hms_tz.nhif.nhif_api.admission.get_ward_types",
            "hms_tz.nhif.nhif_api.admission.get_room_types",
            "hms_tz.nhif.nhif_api.facility.get_facilities",
            "hms_tz.nhif.nhif_api.approval.get_approval_services",
            "hms_tz.jubilee.api.api.get_procedure_list",
        ],
    },
    # 	"hourly": [
    # 		"hms_tz.tasks.hourly"
    # 	],
    # 	"weekly": [
    # 		"hms_tz.tasks.weekly"
    # 	]
    # 	"monthly": [
    # 		"hms_tz.tasks.monthly"
    # 	]
}

jinja = {
    "methods": [
        "hms_tz.nhif.api.healthcare_utils.get_item_rate",
    ]
}


# Testing
# -------

before_tests = "hms_tz.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "hms_tz.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "hms_tz.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

website_route_rules = [{'from_route': '/frontend/<path:app_path>', 'to_route': 'frontend'}, {'from_route': '/frontend/<path:app_path>', 'to_route': 'frontend'},]