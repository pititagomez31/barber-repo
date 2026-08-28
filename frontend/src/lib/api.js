import axios from "axios";

// Sanitize BACKEND_URL. If the user pasted the whole line into Railway
// (eg. "REACT_APP_BACKEND_URL=https://xxx"), extract only the http(s) URL.
function normalizeBackendUrl(raw) {
  if (!raw || typeof raw !== "string") return "";
  const match = raw.match(/https?:\/\/[^\s"']+/i);
  const cleaned = match ? match[0] : raw.trim();
  return cleaned.replace(/\/+$/, ""); // no trailing slash
}

const BACKEND_URL = normalizeBackendUrl(process.env.REACT_APP_BACKEND_URL);
export const API = `${BACKEND_URL}/api`;

if (!BACKEND_URL || !/^https?:\/\//i.test(BACKEND_URL)) {
  // eslint-disable-next-line no-console
  console.error(
    "[+58 BarberStudio] REACT_APP_BACKEND_URL no está bien configurada:",
    process.env.REACT_APP_BACKEND_URL
  );
}

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem("58barber_token");
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

export function formatErr(e) {
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x.msg || JSON.stringify(x)).join(" ");
  return e?.message || "Error inesperado";
}
