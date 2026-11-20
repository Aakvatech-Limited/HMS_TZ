<template>
  <Dialog
    :model-value="show"
    @update:model-value="(value) => !value && cancel()"
    :options="{ title, size: 'lg' }"
    class="z-[1100]"
  >
    <template #body-content>
      <DialogErrorPanel
        v-if="dialogError"
        class="mb-3"
        :error="dialogError"
        @close="dialogError = null"
      />
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
              v-if="!cameraReady && !photo"
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
              :disabled="!cameraReady"
              @click="capturePhoto"
            >
              Capture
            </Button>
            <Button v-else variant="subtle" @click="retakePhoto"
              >Retake</Button
            >
          </div>
        </template>
      </div>

      <div
        v-else-if="searching"
        class="flex items-center justify-center gap-2 py-10 text-sm text-gray-600"
      >
        <LoadingIndicator class="h-4 w-4" />
        Looking for fingerprint readers...
      </div>

      <div v-else-if="!devices.length" class="text-sm text-gray-800">
        <!-- Same wording and look as the desk Fingerprint dialog -->
        <div class="p-1 leading-relaxed">
          <strong>No Device Connected.</strong><br />
          Please download and install drivers:
        </div>
        <ul class="my-2.5 list-disc pl-10">
          <li
            v-for="driver in FINGERPRINT_DRIVER_DOWNLOADS"
            :key="driver.url"
            class="my-1"
          >
            <a
              :href="driver.url"
              target="_blank"
              rel="noopener"
              class="font-bold"
              style="color: blue"
              >{{ driver.label }}</a
            >
          </li>
        </ul>
        <div class="px-4 pb-4 text-xs text-gray-600">
          After installation, restart your browser and ensure services are
          running.
        </div>
        <Button variant="subtle" class="ml-1" @click="openFingerprint">
          <template #prefix>
            <FeatherIcon name="refresh-cw" class="h-4 w-4" />
          </template>
          Search again
        </Button>
      </div>

      <div v-else class="flex flex-col gap-3">
        <p class="flex items-center gap-1 text-sm text-green-700">
          <FeatherIcon name="check-circle" class="h-4 w-4" />
          Device Connected
        </p>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <FieldLabel label="Select Device" />
            <Select :options="deviceOptions" v-model="selectedDevice" />
          </div>
          <div>
            <FieldLabel label="Select Finger to Scan" />
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
          <span v-else-if="scanning">Place the finger on the reader</span>
          <span v-else>Select a finger to start the scan</span>
        </div>
        <div v-if="finger && !scanning" class="flex justify-center">
          <Button variant="subtle" @click="scan">Scan again</Button>
        </div>
      </div>
    </template>
    <template #actions>
      <div class="flex justify-end gap-2">
        <Button variant="subtle" @click="cancel">Cancel</Button>
        <Button
          v-if="method === 'FACIAL'"
          variant="solid"
          :disabled="!captured"
          @click="confirm"
          >Use capture</Button
        >
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { useToast } from "@/composables/useToast";
import { provideDialogError } from "@/composables/dialogError";
import { FaceCamera } from "@desk/facial/camera.js";
import { FINGERPRINT_DRIVER_DOWNLOADS } from "@desk/fingerprint/drivers.js";
import {
  FINGER_CODES,
  FingerprintScanner,
} from "@desk/fingerprint/scanner.js";
import DialogErrorPanel from "../DialogErrorPanel.vue";
import FieldLabel from "./FieldLabel.vue";

const props = defineProps({
  show: { type: Boolean, default: false },
  method: { type: String, default: "FINGERPRINT" },
});
const emit = defineEmits(["update:show", "captured"]);

const dialogError = provideDialogError();
const { showError, clearError } = useToast(dialogError);

const video = ref(null);
const cameras = ref([]);
const selectedCamera = ref("");
const cameraReady = ref(false);
const cameraError = ref("");
const photo = ref("");

const devices = ref([]);
const searching = ref(false);
const scanning = ref(false);
const selectedDevice = ref("");
const finger = ref("");
const fingerprintImage = ref("");
const result = ref(null);

let camera = null;
let scanner = null;

const title = computed(() =>
  props.method === "FACIAL" ? "Capture the patient's face" : "Scan Fingerprint"
);
const cameraOptions = computed(() =>
  cameras.value.map((item, index) => ({
    label: item.label || `Camera ${index + 1}`,
    value: item.deviceId,
  }))
);
const deviceOptions = computed(() =>
  devices.value.map((device) => ({ label: device.name, value: device.name }))
);
const captured = computed(() => Boolean(result.value));

const openFacial = async () => {
  closeDevices();
  photo.value = "";
  result.value = null;
  cameraError.value = "";
  camera = new FaceCamera({
    onError: (message) => (cameraError.value = message),
  });
  // The video element renders with the dialog body, after show turns true
  await nextTick();
  cameras.value = await camera.open(video.value);
  cameraReady.value = Boolean(camera.stream);
  selectedCamera.value = camera.deviceId;
};

const startCamera = async (deviceId) => {
  cameraReady.value = await camera.start(video.value, deviceId);
  selectedCamera.value = camera.deviceId;
};

const capturePhoto = () => {
  const capture = camera.capture(video.value);
  photo.value = capture.image;
  result.value = capture.result;
};

const retakePhoto = () => {
  photo.value = "";
  result.value = null;
};

const openFingerprint = async () => {
  closeDevices();
  fingerprintImage.value = "";
  result.value = null;
  finger.value = "";
  scanner = new FingerprintScanner({
    // A scan goes straight on to the NHIF call, like the desk dialog
    onSample: ({ result: sample, image }) => {
      scanning.value = false;
      result.value = sample;
      fingerprintImage.value = image;
      confirm();
    },
    onError: (message) => {
      scanning.value = false;
      showError(message);
    },
  });
  searching.value = true;
  try {
    devices.value = await scanner.findDevices();
  } finally {
    searching.value = false;
  }
  selectedDevice.value = devices.value[0]?.name || "";
};

const scan = () => {
  const device = devices.value.find(
    (item) => item.name === selectedDevice.value
  );
  if (!device || !finger.value) return;
  fingerprintImage.value = "";
  result.value = null;
  scanning.value = true;
  clearError();
  scanner.scan(device, finger.value);
};

const closeDevices = () => {
  camera?.stop();
  cameraReady.value = false;
  scanner?.destroy();
  scanner = null;
  scanning.value = false;
};

const close = () => {
  closeDevices();
  emit("update:show", false);
};

const cancel = () => {
  close();
  emit("captured", null);
};

const confirm = () => {
  const capture = result.value;
  close();
  emit("captured", capture);
};

watch(selectedDevice, () => (finger.value = ""));
watch(finger, (value) => value && scan());

watch(
  () => props.show,
  (show) => {
    if (!show) return;
    clearError();
    if (props.method === "FACIAL") openFacial();
    else openFingerprint();
  }
);

onBeforeUnmount(closeDevices);
</script>
