import { FINGERPRINT_DRIVER_DOWNLOADS } from "./drivers.js";
import { FINGER_CODES, FingerprintScanner } from "./scanner.js";

/**
 * Desk fingerprint dialog. Resolves with { Data, fpCode }, or null when cancelled.
 * The scan starts as soon as a finger is selected.
 */
export class Fingerprint {
  constructor(opts = {}) {
    this.label = opts.label || "Send Request";
    this.devices = [];
    this.result = null;
    this.scanner = new FingerprintScanner({
      onSample: ({ result }) => this.accept(result),
      onError: (message) => this.showScanError(message),
    });

    return new Promise((resolve) => {
      this.resolve = resolve;
      this.showDialog();
      this.loadDevices();
    });
  }

  showDialog() {
    this.dialog = new frappe.ui.Dialog({
      title: __("Scan Fingerprint"),
      fields: [
        // Full width, so the driver links are not squeezed beside the empty finger column
        {
          fieldtype: "HTML",
          fieldname: "device_status",
          options: this.statusHTML("orange", __("Scanning for devices...")),
        },
        { fieldtype: "Section Break", fieldname: "section_break_device" },
        {
          fieldtype: "Select",
          label: __("Select Device"),
          fieldname: "device",
          options: [],
          reqd: 1,
          onchange: () => this.dialog.set_value("finger", ""),
        },
        { fieldtype: "Column Break", fieldname: "column_break_1" },
        {
          fieldtype: "Select",
          label: __("Select Finger to Scan"),
          fieldname: "finger",
          options: FINGER_CODES.map(({ label, value }) => ({
            label: __(label),
            value,
          })),
          reqd: 1,
          onchange: () => this.scan(),
        },
        { fieldtype: "Section Break", fieldname: "section_break_1" },
        { fieldtype: "HTML", fieldname: "fingerprint" },
      ],
      secondary_action_label: __("Cancel"),
      secondary_action: () => this.dialog.hide(),
    });

    this.dialog.$wrapper.one("hidden.bs.modal", () => this.close());
    this.dialog.show();
  }

  async loadDevices() {
    this.devices = await this.scanner.findDevices();
    const hasDevices = this.devices.length > 0;
    for (const field of ["device", "finger", "fingerprint"]) {
      this.dialog.set_df_property(field, "hidden", hasDevices ? 0 : 1);
    }
    if (!hasDevices) {
      this.setStatus(this.noDeviceHTML());
      return;
    }
    this.dialog.set_df_property(
      "device",
      "options",
      this.devices.map(({ name }) => ({ label: name, value: name }))
    );
    this.dialog.set_value("device", this.devices[0].name);
    this.setStatus(this.statusHTML("green", __("Device Connected")));
  }

  scan() {
    const finger = this.dialog.get_value("finger");
    const device = this.devices.find(
      ({ name }) => name === this.dialog.get_value("device")
    );
    if (!finger || !device) return;

    this.setFingerprintArea(
      `<span>${__("Place a finger on the device")}</span>`
    );
    this.scanner.scan(device, finger);
  }

  accept(result) {
    this.result = result;
    this.dialog.hide();
  }

  showScanError(message) {
    frappe.show_alert({ message, indicator: "red" }, 7);
    this.setFingerprintArea(
      `<button type="button" class="btn btn-default btn-sm hms-scan-again">${__(
        "Scan Again"
      )}</button>`
    );
    this.dialog.$wrapper
      .find(".hms-scan-again")
      .on("click", () => this.scan());
  }

  async close() {
    await this.scanner.destroy();
    this.dialog.$wrapper.remove();
    this.resolve(this.result);
  }

  setStatus(html) {
    this.dialog.get_field("device_status").$wrapper.html(html);
  }

  setFingerprintArea(content) {
    this.dialog.get_field("fingerprint").$wrapper.html(
      `<div style="width: 100px; height: 100px; border: 1px solid black; display: flex;
        justify-content: center; align-items: center; text-align: center; margin-left: 200px;">
        ${content}
      </div>`
    );
  }

  statusHTML(color, text) {
    return `<div style="color: ${color}; padding: 5px;">${text}</div>`;
  }

  noDeviceHTML() {
    const links = FINGERPRINT_DRIVER_DOWNLOADS.map(
      ({ label, url }) => `<li style="margin: 5px 0;">
        <a href="${url}" target="_blank" rel="noopener" style="color: blue; font-weight: bold;">${label}</a>
      </li>`
    ).join("");
    return `<div style="padding: 5px; line-height: 1.6;">
        <strong>${__("No Device Connected.")}</strong><br>
        ${__("Please download and install drivers:")}
      </div>
      <ul style="margin: 10px 0; padding-left: 40px;">${links}</ul>
      <div style="padding: 0 15px 15px; font-size: 12px; color: #666;">
        ${__(
          "After installation, restart your browser and ensure services are running."
        )}
      </div>`;
  }
}

window.Fingerprint = Fingerprint;
