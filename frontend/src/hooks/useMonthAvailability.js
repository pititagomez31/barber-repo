import { useEffect, useState } from "react";
import {
  format,
  startOfMonth,
  endOfMonth,
  eachDayOfInterval,
  addDays,
  startOfToday,
  isSameDay,
} from "date-fns";
import { api } from "@/lib/api";

/**
 * Consulta en paralelo la disponibilidad de todos los días del mes visible.
 * Devuelve un Set con las fechas (formato "yyyy-MM-dd") que tienen al menos 1 slot libre.
 */
export default function useMonthAvailability(month, serviceId) {
  const [availableDays, setAvailableDays] = useState(new Set());
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!month || !serviceId) {
      setAvailableDays(new Set());
      return;
    }

    let cancelled = false;

    const fetchAll = async () => {
      setLoading(true);
      try {
        const hoy = startOfToday();
        const hasta = addDays(hoy, 60);

        // Normalizar el mes visible al día 1 sin hora
        const mesNormalizado = startOfMonth(new Date(month));
        const primerDiaMes = startOfMonth(mesNormalizado);
        const ultimoDiaMes = endOfMonth(mesNormalizado);

        // Rango a consultar: intersección [hoy, hoy+60] con el mes visible
        const desde = primerDiaMes < hoy ? hoy : primerDiaMes;
        const hastaFinal = ultimoDiaMes > hasta ? hasta : ultimoDiaMes;

        if (desde > hastaFinal) {
          if (!cancelled) {
            setAvailableDays(new Set());
            setLoading(false);
          }
          return;
        }

        const dias = eachDayOfInterval({ start: desde, end: hastaFinal });

        // DEBUG: ver qué días vamos a consultar
        console.log("[useMonthAvailability] Consultando días:", dias.length, "serviceId:", serviceId);

        const resultados = await Promise.allSettled(
          dias.map(async (d) => {
            // IMPORTANTE: usar las partes locales de la fecha para evitar desfase por TZ
            const y = d.getFullYear();
            const m = String(d.getMonth() + 1).padStart(2, "0");
            const day = String(d.getDate()).padStart(2, "0");
            const dateStr = `${y}-${m}-${day}`;

            try {
              const r = await api.get(`/availability?service_id=${serviceId}&date=${dateStr}`);
              const slots = Array.isArray(r.data?.slots)
                ? r.data.slots
                : Array.isArray(r.data)
                  ? r.data
                  : [];
              return { date: dateStr, slots };
            } catch (err) {
              return { date: dateStr, slots: [] };
            }
          })
        );

        if (cancelled) return;

        const set = new Set();
        resultados.forEach((r) => {
          if (r.status === "fulfilled" && r.value.slots.length > 0) {
            set.add(r.value.date);
          }
        });

        // DEBUG: ver el set resultante
        console.log("[useMonthAvailability] Días con disponibilidad:", Array.from(set));

        setAvailableDays(set);
      } catch (e) {
        console.error("[useMonthAvailability] Error:", e);
        if (!cancelled) setAvailableDays(new Set());
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchAll();
    return () => {
      cancelled = true;
    };
  }, [month, serviceId]);

  return { availableDays, loading };
}
