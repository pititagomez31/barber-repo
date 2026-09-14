import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });

export const WEEKDAYS = [
  { key: "0", label: "Lunes", short: "Lun" },
  { key: "1", label: "Martes", short: "Mar" },
  { key: "2", label: "Miércoles", short: "Mié" },
  { key: "3", label: "Jueves", short: "Jue" },
  { key: "4", label: "Viernes", short: "Vie" },
  { key: "5", label: "Sábado", short: "Sáb" },
  { key: "6", label: "Domingo", short: "Dom" },
];

// JS getDay(): Sun=0..Sat=6  ->  our key Mon=0..Sun=6
export const jsDayToKey = (jsDay) => String((jsDay + 6) % 7);

export const fmtDate = (d) => {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
};

export const MONTHS = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

export const prettyDate = (dateStr) => {
  const [y, m, d] = dateStr.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  const wd = WEEKDAYS[jsDayToKey(dt.getDay())].label;
  return `${wd} ${d} de ${MONTHS[m - 1]}`;
};
