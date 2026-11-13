<template>
  <Dialog
    :model-value="show"
    @update:model-value="(value) => !value && cancel()"
    :options="{ title, size: 'lg' }"
    class="z-[1100]"
  >
    <template #body-content>
      <div v-if="method === 'FACIAL'" class="flex flex-col gap-3">
        <div>
          <FieldLabel label="Camera" />
          <Select
            :options="cameraOptions"
            :model-value="selectedCamera"
            @update:model-value="startCamera"
          />
        </div>
        <div class="mx-auto h-72 w-72 overflow-hidden rounded-lg bg-gray-100">
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
        <p v-if="cameraError" class="text-sm text-red-600">
          {{ cameraError }}
        </p>
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
      </div>

      <div v-else class="flex flex-col gap-3">
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <FieldLabel label="Device" />
            <Select
              :options="deviceOptions"
              v-model="selectedDevice"
              :placeholder="
                deviceOptions.length ? 'Select device' : 'No reader found'
              "
            />
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
  } catch (error) {
    cameraError.value = `Camera not available: ${error.message}`;
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

const openFacial = async () => {
  photo.value = "";
  const devices = await navigator.mediaDevices
    .enumerateDevices()
    .catch(() => []);
  cameras.value = devices.filter((device) => device.kind === "videoinput");
  await startCamera(cameras.value[0]?.deviceId || "");
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
