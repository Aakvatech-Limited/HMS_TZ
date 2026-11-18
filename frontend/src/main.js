import { createApp } from "vue";
import { createPinia } from "pinia";
import Toast from "vue-toastification";
import "vue-toastification/dist/index.css";
import "./assets/toast.css";
import "./shims/translate.js";

import App from "./App.vue";
import router from "./router";
import { initSocket } from "./socket";

import {
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  Checkbox,
  DatePicker,
  Dialog,
  Dropdown,
  ErrorMessage,
  FeatherIcon,
  FormControl,
  Input,
  LoadingIndicator,
  LoadingText,
  Popover,
  Select,
  TextInput,
  TextEditor,
  Tooltip,
  frappeRequest,
  pageMetaPlugin,
  resourcesPlugin,
  setConfig,
} from "frappe-ui";

import "./index.css";

const globalComponents = {
  // Basic UI Components
  Alert,
  Avatar,
  Badge,
  Button,
  Card,

  // Form Components
  Checkbox,
  DatePicker,
  FormControl,
  Input,
  Select,
  TextInput,
  TextEditor,

  // Layout & Navigation
  Dialog,
  Dropdown,
  Popover,
  Tooltip,

  // Icons & Indicators
  FeatherIcon,
  LoadingIndicator,
  LoadingText,

  // Utility Components
  ErrorMessage,
};

const app = createApp(App);
const pinia = createPinia();

setConfig("resourceFetcher", frappeRequest);

app.use(pinia);
app.use(router);
app.use(resourcesPlugin);
app.use(pageMetaPlugin);
app.use(Toast, {
  position: "bottom-right",
  timeout: 6000,
  closeOnClick: true,
  pauseOnFocusLoss: true,
  pauseOnHover: true,
  draggable: true,
  draggablePercent: 0.6,
  showCloseButtonOnHover: false,
  hideProgressBar: true,
  closeButton: "button",
  icon: true,
  rtl: false,
  newestOnTop: true,
  filterBeforeCreate: (toast, toasts) => {
    // Prevent duplicate toasts
    if (toasts.filter((t) => t.content === toast.content).length !== 0) {
      return false;
    }
    return toast;
  },
});

const socket = initSocket();
app.config.globalProperties.$socket = socket;

for (const key in globalComponents) {
  app.component(key, globalComponents[key]);
}

app.mount("#app");
