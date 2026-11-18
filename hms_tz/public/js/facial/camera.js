const CAMERA_ERRORS = {
  NotAllowedError:
    "Camera access is blocked. Allow the camera for this site in the browser address bar, then click Try Again.",
  NotFoundError: "No camera found. Connect a camera, then click Try Again.",
  NotReadableError:
    "Another application is using the camera. Close it, then click Try Again.",
  NotSupported:
    "This browser cannot open the camera on this page. Use HTTPS or localhost.",
};

/**
 * Opens a camera into a video element and captures a square face photo,
 * for desk and Vue dialogs. Errors come back as messages through onError.
 */
export class FaceCamera {
  constructor({ onError }) {
    this.onError = onError;
    this.stream = null;
    this.deviceId = "";
  }

  /** Lists cameras and starts the first one; returns the cameras, or [] after reporting why not. */
  async open(video) {
    if (!navigator.mediaDevices) {
      this.reportError({ name: "NotSupported" });
      return [];
    }
    const cameras = await this.listCameras();
    if (!cameras.length) {
      this.reportError({ name: "NotFoundError" });
      return [];
    }
    if (!(await this.start(video, cameras[0].deviceId))) return [];
    // Browsers give camera labels only after access is allowed
    return this.listCameras();
  }

  /** Returns true when the camera is streaming into the video element. */
  async start(video, deviceId) {
    this.stop();
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: {
          deviceId: deviceId ? { exact: deviceId } : undefined,
          width: { ideal: 720 },
          height: { ideal: 720 },
          facingMode: "user",
        },
      });
    } catch (error) {
      this.reportError(error);
      return false;
    }
    video.srcObject = this.stream;
    this.deviceId =
      this.stream.getVideoTracks()[0]?.getSettings().deviceId || deviceId;
    return true;
  }

  stop() {
    for (const track of this.stream?.getTracks() || []) track.stop();
    this.stream = null;
  }

  async listCameras() {
    const devices = await navigator.mediaDevices
      .enumerateDevices()
      .catch(() => []);
    return devices.filter((device) => device.kind === "videoinput");
  }

  /** Centre square of the current frame as { image, result: { Data, fpCode } }. */
  capture(video) {
    const size = Math.min(video.videoWidth, video.videoHeight);
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const x = (video.videoWidth - size) / 2;
    const y = (video.videoHeight - size) / 2;
    canvas
      .getContext("2d")
      .drawImage(video, x, y, size, size, 0, 0, size, size);
    const image = canvas.toDataURL("image/jpeg", 0.9);
    return { image, result: { Data: image.split(",")[1], fpCode: "FACE" } };
  }

  reportError(error) {
    const message = CAMERA_ERRORS[error.name]
      ? __(CAMERA_ERRORS[error.name])
      : __("The camera did not start: {0}", [error.message]);
    console.error("Face camera:", error);
    this.onError?.(message);
  }
}
