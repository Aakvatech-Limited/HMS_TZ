// Signature fields can hold a pointer to the signature store (sig:<sha256>.<ext>) instead of the image,
// see hms_tz/signatures.py. Forms get images on load, but values set in the browser arrive as pointers,
// e.g. fetch_from when picking a practitioner on an encounter. Show their image, keep the pointer as the value.

const is_pointer = (value) =>
  /^sig:[0-9a-f]{64}\.(png|jpg|txt)$/.test(value || "");

frappe.ui.form.ControlSignature = class ControlSignature extends (
  frappe.ui.form.ControlSignature
) {
  get_value() {
    return this.drawing ?? super.get_value();
  }

  load_pad() {
    const pointer = this.get_value();
    if (!is_pointer(pointer)) return super.load_pad();

    // load_pad runs on every refresh: fetch each pointer's image once
    this.images ??= {};
    this.images[pointer] ??= this.get_image(pointer);
    this.images[pointer].then((image) => {
      if (!image || this.get_value() !== pointer) return;
      // draw the image, but leave the pointer as the field value
      this.drawing = image;
      try {
        super.load_pad();
      } finally {
        this.drawing = null;
      }
    });
  }

  get_image(pointer) {
    const { doc = {}, df } = this;
    const link_field = df.fetch_from?.split(".")[0];
    return frappe
      .xcall("hms_tz.signatures.get_signature", {
        pointer,
        doctype: doc.doctype || df.parent,
        fieldname: df.fieldname,
        // the server checks the user may read this field of the document, or of the one it's fetched from
        name: doc.__islocal ? null : doc.name,
        source_name: link_field ? doc[link_field] : null,
      })
      .then((image) => {
        if (!image) {
          frappe.show_alert({
            message: __("This signature is missing from the signature store"),
            indicator: "red",
          });
        }
        return image;
      })
      .catch(() => {
        delete this.images[pointer]; // retry on the next refresh
      });
  }
};
