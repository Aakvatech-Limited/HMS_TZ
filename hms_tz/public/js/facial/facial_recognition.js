import { FaceCamera } from "./camera.js";

/**
 * Desk face capture dialog. Resolves with { Data, fpCode: "FACE" }, or null when cancelled.
 */
class FacialRecognition {
  constructor(opts = {}) {
    this.label = opts.label || "Authorize";
    this.result = null;
    this.camera = new FaceCamera({
      onError: (message) => this.showCameraError(message),
    });

    return new Promise((resolve) => {
      this.resolve = resolve;
      this.showDialog();
      this.open();
    });
  }

  showDialog() {
    addStyles();
    this.dialog = new frappe.ui.Dialog({
      title: __("Patient Face Capture"),
      fields: [
        {
          fieldname: "face_capture_section",
          fieldtype: "HTML",
          options: this.captureHTML(),
        },
      ],
      size: "large",
      primary_action_label: __(this.label),
      primary_action: () => this.accept(),
    });
    this.dialog.disable_primary_action();
    this.dialog.$wrapper.one("hidden.bs.modal", () => this.close());
    this.dialog.show();
    this.bindControls();
  }

  async open() {
    this.find("#face-camera-error").hide();
    this.find(".face-capture-controls").show();
    const cameras = await this.camera.open(this.video);
    if (!cameras.length) return;
    this.find("#camera-select")
      .html(
        cameras
          .map(
            (device, index) =>
              `<option value="${device.deviceId}">${
                device.label || `Camera ${index + 1}`
              }</option>`
          )
          .join("")
      )
      .val(this.camera.deviceId);
  }

  bindControls() {
    this.video = this.find("#face-camera")[0];
    this.find("#camera-select").on("change", (event) =>
      this.camera.start(this.video, event.target.value)
    );
    this.find("#capture-btn").on("click", () => this.capture());
    this.find("#retake-btn").on("click", () => this.retake());
    this.find("#camera-try-again").on("click", () => this.open());
    const showZoom = () => this.result && this.showZoomMode();
    this.find("#zoom-preview-btn").on("click", showZoom);
    this.find("#face-preview").on("click", showZoom);
  }

  capture() {
    const { image, result } = this.camera.capture(this.video);
    this.result = result;
    this.find("#face-preview").attr("src", image).show();
    this.togglePreview(true);
    this.dialog.enable_primary_action();
  }

  retake() {
    this.result = null;
    this.togglePreview(false);
    this.dialog.disable_primary_action();
  }

  togglePreview(hasPhoto) {
    this.find("#face-preview-area").toggle(!hasPhoto);
    this.find("#photo-preview-container").toggle(hasPhoto);
    this.find("#zoom-preview-btn").toggle(hasPhoto);
    this.find("#capture-btn").toggle(!hasPhoto);
  }

  accept() {
    if (!this.result) {
      frappe.msgprint(__("Please capture a face photo first."));
      return;
    }
    this.dialog.hide();
  }

  close() {
    this.camera.stop();
    this.dialog.$wrapper.remove();
    this.resolve(this.result);
  }

  showCameraError(message) {
    this.find(".face-capture-controls").hide();
    this.find("#face-camera-error").show().find(".message").text(message);
  }

  showZoomMode() {
    const $zoomMode = $(`
      <div class="zoom-mode">
        <img src="${this.find("#face-preview").attr(
          "src"
        )}" alt="Patient Face" />
        <div class="zoom-controls">
          <button class="btn btn-default zoom-close-btn">
            <i class="fa fa-times"></i> ${__("Close")}
          </button>
          <button class="btn btn-primary zoom-authorize-btn">
            <i class="fa fa-check"></i> ${__("Authorize")}
          </button>
        </div>
      </div>
    `).appendTo("body");

    $zoomMode.find(".zoom-close-btn").on("click", () => $zoomMode.remove());
    $zoomMode.find(".zoom-authorize-btn").on("click", () => {
      $zoomMode.remove();
      this.accept();
    });
    $zoomMode.on(
      "click",
      (event) => event.target === $zoomMode[0] && $zoomMode.remove()
    );
  }

  find(selector) {
    return this.dialog.$wrapper.find(selector);
  }

  captureHTML() {
    return `
      <div class="face-capture-container">
        <div id="face-camera-error" class="alert alert-danger text-center" style="margin: 20px; display: none;">
          <i class="fa fa-camera" style="font-size: 24px;"></i><br><br>
          <span class="message"></span><br><br>
          <button id="camera-try-again" class="btn btn-default">${__(
            "Try Again"
          )}</button>
        </div>

        <div class="face-capture-controls">
          <div class="camera-selector">
            <select id="camera-select" class="form-control">
              <option value="">${__("Loading cameras...")}</option>
            </select>
          </div>

          <div class="face-preview-area" id="face-preview-area">
            <div class="face-guide"></div>
            <video id="face-camera" autoplay playsinline muted></video>
          </div>

          <div class="capture-controls">
            <button id="capture-btn" class="btn btn-sm btn-capture">
              <i class="fa fa-camera"></i> ${__("Capture")}
            </button>
          </div>

          <div class="photo-preview-container" id="photo-preview-container" style="display:none;">
            <div class="photo-preview">
              <img id="face-preview" style="display:none;"/>
              <div class="preview-overlay">
                <button id="zoom-preview-btn" class="btn btn-info btn-sm" style="display:none;">
                  <i class="fa fa-search-plus"></i> ${__("View Full Size")}
                </button>
              </div>
            </div>
            <div class="retake-controls" style="margin-top: 15px;">
              <button id="retake-btn" class="btn btn-default">
                <i class="fa fa-refresh"></i> ${__("Retake")}
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  }
}

function addStyles() {
  if (document.getElementById("hms-face-capture-styles")) return;
  $("<style>", { id: "hms-face-capture-styles" })
    .html(
      `
    .face-capture-container {
      text-align: center;
      max-width: 500px;
      margin: 0 auto;
      padding: 15px;
    }

    .camera-selector {
      margin-bottom: 20px;
    }

    .face-preview-area {
      position: relative;
      width: 350px;
      height: 350px;
      margin: 15px auto;
      border-radius: 50%;
      overflow: hidden;
      border: 3px solid #dfe3e8;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
      background-color: #f8f9fa;
    }

    .face-guide {
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      border-radius: 50%;
      border: 2px dashed rgba(255,255,255,0.5);
      pointer-events: none;
      z-index: 10;
    }

    #face-camera, #face-preview {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    .capture-controls {
      margin: 25px 0;
    }

    .btn-capture {
      background-color:rgb(42, 124, 161);
      color: white;
      border: none;
      font-size: 14px;
    }

    .btn-capture:hover {
      background-color:rgb(139, 206, 224);
      transform: translateY(-2px);
      box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }

    .btn-capture:active {
      transform: translateY(0);
    }

    .photo-preview-container {
      margin: 20px 0;
    }

    .photo-preview {
      position: relative;
      width: 350px;
      height: 350px;
      border-radius: 50%;
      overflow: hidden;
      margin: 0 auto;
      border: 3px solid #dfe3e8;
      box-shadow: 0 4px 15px rgba(0,0,0,0.1);
      background-color: #f8f9fa;
    }

    .photo-preview img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      cursor: pointer;
    }

    .preview-overlay {
      position: absolute;
      bottom: 10px;
      left: 50%;
      transform: translateX(-50%);
      z-index: 20;
    }

    .preview-overlay .btn {
      background-color: rgba(255, 255, 255, 0.9);
      border: 1px solid #dfe3e8;
      color: #333;
      font-size: 12px;
      padding: 5px 10px;
    }

    .retake-controls {
      text-align: center;
    }

    .retake-controls .btn {
      padding: 8px 20px;
      font-size: 14px;
      font-weight: bold;
      border-radius: 4px;
    }

    .zoom-mode {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background-color: rgba(0, 0, 0, 0.9);
      z-index: 1050;
      display: flex;
      justify-content: center;
      align-items: center;
      flex-direction: column;
    }

    .zoom-mode img {
      max-width: 90%;
      max-height: 70%;
      object-fit: contain;
      border-radius: 8px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    }

    .zoom-controls {
      margin-top: 30px;
      text-align: center;
    }

    .zoom-controls .btn {
      margin: 0 10px;
      min-width: 120px;
      padding: 10px 20px;
      font-size: 14px;
    }

    @media (max-width: 576px) {
      .face-preview-area, .photo-preview {
        width: 280px;
        height: 280px;
      }

      .btn-capture {
        padding: 8px 20px;
        font-size: 14px;
      }
    }
    `
    )
    .appendTo("head");
}

window.FacialRecognition = FacialRecognition;
