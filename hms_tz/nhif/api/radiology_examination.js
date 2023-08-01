frappe.ui.form.on("Radiology Examination", {
    onload: (frm) => {
        if (frm.doc.patient) {
            frm.add_custom_button(__('Patient History'), () => {
                frappe.route_options = { 'patient': frm.doc.patient };
                frappe.set_route('tz-patient-history');
            });
        }
    },

    approval_number: (frm) => {
        // 2023-07-13
        // stop this validation for now
        return
        frm.fields_dict.approval_number.$input.focusout(() => {
            if (frm.doc.approval_number != "" && frm.doc.approval_number != undefined) {
                frappe.call({
                    method: "hms_tz.nhif.api.healthcare_utils.varify_service_approval_number_for_LRPM", 
                    args: {
                    patient: frm.doc.patient,
                    company: frm.doc.company,
                    approval_number: frm.doc.approval_number,
                    template: "Radiology Examination Template",
                        item: frm.doc.radiology_examination_template,
                    },
                    freeze: true,
                    freeze_message: __("Verifying Approval Number..."),
                }).then(r => {
                    if (r.message) {
                        frappe.show_alert({
                            message: __("<h4 class='text-center' style='background-color: #D3D3D3; font-weight: bold;'>\
                                Approval Number is Valid</h4>"),
                            indicator: "green"
                        }, 10);
                        let data = r.message;
                        frm.set_value("approval_type", "NHIF");
                        frm.set_value("approval_status", "Verified");
                        frm.set_value("authorized_item_id", data.AuthorizedItemID);
                        frm.set_value("service_authorization_id", data.ServiceAuthorizationID);
                        
                    } else {
                        frm.set_value("approval_number", "");
                        frappe.show_alert({
                            message: __("<h4 class='text-center' style='background-color: #D3D3D3; font-weight: bold;'>\
                                Approval Number is not Valid</h4>"),
                            indicator: "Red"
                        }, 10);
                    }
                });
            }
        });
    }
})