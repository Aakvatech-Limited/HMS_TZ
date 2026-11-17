<template>
  <Dialog
    :model-value="show"
    @update:model-value="(value) => !value && cancel()"
    :options="{ title, size: 'lg' }"
    class="z-[1100]"
  >
    <template #body-content>
      <div v-if="method === 'FACIAL'" class="flex flex-col gap-3">
        <div v-if="cameraError" class="flex flex-col items-center gap-3 py-6">
          <FeatherIcon name="camera-off" class="h-8 w-8 text-red-500" />
          <p class="text-center text-sm text-gray-800">{{ cameraError }}</p>
          <Button variant="subtle" @click="openFacial">Try again</Button>
        </div>
        <template v-else>
          <div>
            <FieldLabel label="Camera" />
            <Select
              :options="cameraOptions"
              :model-value="selectedCamera"
              @update:model-value="startCamera"
            />
          </div>
          <div
            class="relative mx-auto h-72 w-72 overflow-hidden rounded-lg bg-gray-100"
          >
            <div
              v-if="!stream && !photo"
              class="absolute inset-0 flex items-center justify-center gap-2 text-sm text-gray-600"
            >
              <LoadingIndicator class="h-4 w-4" />
              Starting the camera...
            </div>
            <video
              v-show="!photo"
              ref="video"
              autoplay
              playsinline
              muted
              class="h-full w-full object-cover"
            ></video>
            <img
              v-if="photo"
              :src="photo"
              alt="Captured face"
              class="h-full w-full object-cover"
            />
          </div>
          <div class="flex justify-center gap-2">
            <Button
              v-if="!photo"
              variant="subtle"
              :disabled="!stream"
              @click="capturePhoto"
            >
              Capture
            </Button>
            <Button v-else variant="subtle" @click="photo = ''">Retake</Button>
          </div>
        </template>
      </div>

      <div
        v-else-if="scanner.searching.value"
        class="flex items-center justify-center gap-2 py-10 text-sm text-gray-600"
      >
        <LoadingIndicator class="h-4 w-4" />
        Looking for fingerprint readers...
      </div>

      <div
        v-else-if="!deviceOptions.length"
        class="flex flex-col gap-3 rounded-lg border border-orange-200 bg-orange-50 p-4 text-sm"
      >
        <p class="font-semibold text-gray-900">No fingerprint reader found</p>
        <p class="text-gray-700">
          Connect the reader, or download and install the driver for your
          reader:
        </p>
        <ul class="list-disc pl-6">
          <li v-for="driver in FINGERPRINT_DRIVER_DOWNLOADS" :key="driver.url">
            <a
              :href="driver.url"
              target="_blank"
              rel="noopener"
              class="font-medium text-blue-600 underline"
              >{{ driver.label }}</a
            >
          </li>
        </ul>
        <p class="text-xs text-gray-600">
          After installation, restart your browser and make sure the driver
          service is running.
        </p>
        <div>
          <Button variant="subtle" @click="openFingerprint">
            <template #prefix>
              <FeatherIcon name="refresh-cw" class="h-4 w-4" />
            </template>
            Search again
          </Button>
        </div>
      </div>

      <div v-else class="flex flex-col gap-3">
        <p class="flex items-center gap-1 text-sm text-green-700">
          <FeatherIcon name="check-circle" class="h-4 w-4" />
          Reader connected
        </p>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <FieldLabel label="Device" />
            <Select :options="deviceOptions" v-model="selectedDevice" />
          </div>
          <div>
            <FieldLabel label="Finger" />
            <Select
              :options="FINGER_CODES"
              v-model="finger"
              placeholder="Select finger"
            />
          </div>
        </div>
        <div
          class="mx-auto flex h-36 w-28 items-center justify-center rounded border border-gray-300 text-center text-xs text-gray-500"
        >
          <img
            v-if="fingerprintImage"
            :src="fingerprintImage"
            alt="Fingerprint"
            class="h-full w-full"
          />
          <span v-else-if="scanner.scanning.value"
            >Place the finger on the reader</span
          >
          <span v-else>No scan yet</span>
        </div>
        <div class="flex justify-center">
          <Button
            variant="subtle"
            :loading="scanner.scanning.value"
            :disabled="!selectedDevice || !finger || scanner.scanning.value"
            @click="scan"
          >
            Scan
          </Button>
        </div>
      </div>
    </template>
    <template #actions>
      <div class="flex justify-end gap-2">
        <Button variant="subtle" @click="cancel">Cancel</Button>
        <Button variant="solid" :disabled="!captured" @click="confirm"
          >Use capture</Button
        >
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useToast } from "@/composables/useToast";
import {
  FINGER_CODES,
  useFingerprintScanner,
} from "@/composables/useFingerprintScanner";
import { FINGERPRINT_DRIVER_DOWNLOADS } from "@desk/fingerprint/drivers.js";
import FieldLabel from "./FieldLabel.vue";

const props = defineProps({
  show: { type: Boolean, default: false },
  method: { type: String, default: "FINGERPRINT" },
});
const emit = defineEmits(["update:show", "captured"]);

const { showError } = useToast();
const scanner = useFingerprintScanner({ onError: showError });

const video = ref(null);
const stream = ref(null);
const cameras = ref([]);
const selectedCamera = ref("");
const cameraError = ref("");
const photo = ref("");

const selectedDevice = ref("");
const finger = ref("");
const fingerprintImage = ref("");
const fingerprintData = ref("");

const CAMERA_ERRORS = {
  NotAllowedError:
    "Camera access is blocked. Allow the camera for this site in the browser address bar, then click Try again.",
  NotFoundError: "No camera found. Connect a camera, then click Try again.",
  NotReadableError:
    "Another application is using the camera. Close it, then click Try again.",
  NotSupported:
    "This browser cannot open the camera on this page. Use HTTPS or localhost.",
};

const title = computed(() =>
  props.method === "FACIAL"
    ? "Capture the patient's face"
    : "Scan the patient's fingerprint"
);
const cameraOptions = computed(() =>
  cameras.value.map((camera, index) => ({
    label: camera.label || `Camera ${index + 1}`,
    value: camera.deviceId,
  }))
);
const deviceOptions = computed(() =>
  scanner.devices.value.map((device) => ({
    label: device.name,
    value: device.name,
  }))
);
const captured = computed(() =>
  props.method === "FACIAL"
    ? Boolean(photo.value)
    : Boolean(fingerprintData.value)
);

const startCamera = async (deviceId) => {
  stopCamera();
  selectedCamera.value = deviceId;
  cameraError.value = "";
  try {
    stream.value = await navigator.mediaDevices.getUserMedia({
      video: {
        deviceId: deviceId ? { exact: deviceId } : undefined,
        width: { ideal: 720 },
        height: { ideal: 720 },
        facingMode: "user",
      },
    });
    video.value.srcObject = stream.value;
    cameras.value = await listCameras();
    selectedCamera.value =
      stream.value.getVideoTracks()[0]?.getSettings().deviceId || deviceId;
  } catch (error) {
    cameraError.value =
      CAMERA_ERRORS[error.name] ||
      `The camera did not start: ${error.message}`;
  }
};

const stopCamera = () => {
  for (const track of stream.value?.getTracks() || []) track.stop();
  stream.value = null;
};

const capturePhoto = () => {
  const size = Math.min(video.value.videoWidth, video.value.videoHeight);
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const x = (video.value.videoWidth - size) / 2;
  const y = (video.value.videoHeight - size) / 2;
  canvas
    .getContext("2d")
    .drawImage(video.value, x, y, size, size, 0, 0, size, size);
  photo.value = canvas.toDataURL("image/jpeg", 0.9);
};

// Browsers give camera labels only after access is allowed, so the list is read again once the camera starts.
const listCameras = async () => {
  const devices = await navigator.mediaDevices
    .enumerateDevices()
    .catch(() => []);
  return devices.filter((device) => device.kind === "videoinput");
};

const openFacial = async () => {
  photo.value = "";
  cameraError.value = "";
  if (!navigator.mediaDevices) {
    cameraError.value = CAMERA_ERRORS.NotSupported;
    return;
  }
  cameras.value = await listCameras();
  if (!cameras.value.length) {
    cameraError.value = CAMERA_ERRORS.NotFoundError;
    return;
  }
  await startCamera(cameras.value[0].deviceId);
};

const openFingerprint = async () => {
  fingerprintImage.value = "";
  fingerprintData.value = "";
  finger.value = "";
  await scanner.enumerateDevices();
  selectedDevice.value = scanner.devices.value[0]?.name || "";
};

const scan = () => {
  const device = scanner.devices.value.find(
    (item) => item.name === selectedDevice.value
  );
  fingerprintImage.value = "";
  fingerprintData.value = "";
  scanner.scan(device, ({ data, image }) => {
    fingerprintData.value = data;
    fingerprintImage.value = image;
  });
};

const close = async () => {
  stopCamera();
  await scanner.destroy();
  emit("update:show", false);
};

const cancel = async () => {
  await close();
  emit("captured", null);
};

const confirm = async () => {
  const result =
    props.method === "FACIAL"
      ? { Data: photo.value.split(",")[1], fpCode: "FACE" }
      : { Data: fingerprintData.value, fpCode: finger.value };
  await close();
  emit("captured", result);
};

watch(
  () => props.show,
  (show) => {
    if (!show) return;
    if (props.method === "FACIAL") openFacial();
    else openFingerprint();
  }
);

onBeforeUnmount(() => {
  stopCamera();
  scanner.destroy();
});
</script>
