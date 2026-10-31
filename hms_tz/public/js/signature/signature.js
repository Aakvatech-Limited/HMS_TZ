/**
 * Signature Pad Class for HMS TZ
 * A reusable signature capture component that can be used across the application.
 *
 * Usage:
 *   const signature = await new Signature({ label: "Sign Document" });
 *   if (signature) {
 *     console.log(signature.Data); // Base64 PNG image data
 *   }
 *
 * Extra dialog fields passed as `fields` come back in `signature.values`.
 * Resolves with null when the dialog is closed without signing.
 */

export class Signature {
  constructor(opts = {}) {
    this.label = opts.label || "Sign";
    this.title = opts.title || __("Draw Signature");
    this.canvasWidth = opts.width || 500;
    this.canvasHeight = opts.height || 250;
    this.lineColor = opts.lineColor || "#000";
    this.lineWidth = opts.lineWidth || 3;
    this.backgroundColor = opts.backgroundColor || "#fff";
    this.extraFields = opts.fields || [];

    this.isDrawing = false;
    this.hasDrawn = false;
    this.result = null;

    return new Promise((resolve) => {
      this.resolve = resolve;
      this.showDialog();
    });
  }

  showDialog() {
    this.dialog = new frappe.ui.Dialog({
      title: this.title,
      static: true,
      fields: [
        ...this.extraFields,
        {
          fieldtype: "HTML",
          fieldname: "signature_container",
          options: this.getSignatureHTML(),
        },
      ],
      size: "large",
      primary_action_label: __(this.label),
      primary_action: (values) => this.submitSignature(values),
      secondary_action_label: __("Cancel"),
      secondary_action: () => this.dialog.hide(),
    });

    // Resolving before the modal is gone lets callers open the next one too early and leave the backdrop stuck
    this.dialog.$wrapper.one("hidden.bs.modal", () => {
      this.dialog.$wrapper.remove();
      this.resolve(this.result);
    });

    this.initCanvas();
    this.dialog.show();
  }

  getSignatureHTML() {
    return `
      <div class="signature-pad-container" style="text-align: center; padding: 10px;">
        <p style="margin-bottom: 15px; color: #666;">
          ${__(
            "Please draw your signature below using a pen, stylus, or mouse"
          )}
        </p>
        <div class="signature-canvas-wrapper" style="
          border: 2px solid #ccc;
          border-radius: 10px;
          background-color: ${this.backgroundColor};
          margin: 0 auto;
          display: inline-block;
          max-width: 100%;
          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        ">
          <canvas
            class="hms-signature-canvas"
            width="${this.canvasWidth}"
            height="${this.canvasHeight}"
            style="
              cursor: crosshair;
              touch-action: none;
              user-select: none;
              display: block;
              max-width: 100%;
              border-radius: 8px;
            "
          ></canvas>
        </div>
        <div style="margin-top: 15px;">
          <button type="button" class="btn btn-default btn-sm hms-clear-signature">
            <i class="fa fa-eraser"></i> ${__("Clear")}
          </button>
        </div>
        <p style="margin-top: 10px; font-size: 12px; color: #999;">
          <i class="fa fa-info-circle"></i> ${__(
            "Click and drag to draw your signature"
          )}
        </p>
      </div>
    `;
  }

  initCanvas() {
    const $body = this.dialog.$wrapper;
    this.canvas = $body.find(".hms-signature-canvas").get(0);
    this.ctx = this.canvas.getContext("2d");
    this.ctx.lineCap = "round";
    this.ctx.lineJoin = "round";
    this.ctx.strokeStyle = this.lineColor;
    this.ctx.lineWidth = this.lineWidth;
    this.clearCanvas();

    // Pointer events cover mouse, touch and USB pen pads with one code path
    this.canvas.addEventListener("pointerdown", (e) => this.startDrawing(e));
    this.canvas.addEventListener("pointermove", (e) => this.draw(e));
    this.canvas.addEventListener("pointerup", () => this.stopDrawing());
    this.canvas.addEventListener("pointercancel", () => this.stopDrawing());
    // Pen barrel buttons and long presses open the context menu mid-stroke
    this.canvas.addEventListener("contextmenu", (e) => e.preventDefault());

    $body.find(".hms-clear-signature").on("click", () => this.clearCanvas());
  }

  getCoordinates(e) {
    return {
      x: (e.clientX - this.rect.left) * this.scaleX,
      y: (e.clientY - this.rect.top) * this.scaleY,
    };
  }

  startDrawing(e) {
    e.preventDefault();
    this.canvas.setPointerCapture(e.pointerId);
    this.rect = this.canvas.getBoundingClientRect();
    this.scaleX = this.canvas.width / this.rect.width;
    this.scaleY = this.canvas.height / this.rect.height;
    this.isDrawing = true;
    this.hasDrawn = true;

    const { x, y } = this.getCoordinates(e);
    this.ctx.fillStyle = this.lineColor;
    this.ctx.beginPath();
    this.ctx.arc(x, y, this.lineWidth / 2, 0, Math.PI * 2);
    this.ctx.fill();
    this.ctx.beginPath();
    this.ctx.moveTo(x, y);
  }

  draw(e) {
    if (!this.isDrawing) return;
    e.preventDefault();

    // Pens report more points than the frame rate; coalesced events keep fast strokes smooth
    const coalesced = e.getCoalescedEvents?.() || [];
    let point;
    for (const event of coalesced.length ? coalesced : [e]) {
      point = this.getCoordinates(event);
      this.ctx.lineTo(point.x, point.y);
    }
    this.ctx.stroke();
    // Restart the path so each stroke() redraws only the new segments
    this.ctx.beginPath();
    this.ctx.moveTo(point.x, point.y);
  }

  stopDrawing() {
    this.isDrawing = false;
  }

  clearCanvas() {
    this.ctx.fillStyle = this.backgroundColor;
    this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    this.hasDrawn = false;
  }

  submitSignature(values) {
    if (!this.hasDrawn) {
      frappe.show_alert({
        message: __("Please draw your signature before proceeding."),
        indicator: "orange",
      });
      return;
    }

    this.result = {
      Data: this.canvas.toDataURL("image/png"),
      values,
      format: "png",
      timestamp: new Date().toISOString(),
    };
    this.dialog.hide();
  }
}

// Make Signature available globally
window.Signature = Signature;
