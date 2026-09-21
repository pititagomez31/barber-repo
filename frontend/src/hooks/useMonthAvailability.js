import { useEffect, useState } from "react";
import { eachDayOfInterval, addMonths, startOfToday } from "date-fns";
import { api } from "@/lib/api";

/**
 * Consulta la disponibilidad de los próximos 6 meses (desde hoy).
 * Devuelve un Set con las fechas "yyyy-MM-dd" que tienen al menos 1 slot libre.
 * Se consulta UNA VEZ al montar (o cuando cambia el serviceId) — no por mes visible.
 */
export default function useMonthAvailability(month, serviceId) {
  const [availableDays, setAvailableDays] = useState(new Set());
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!serviceId) {
      setAvailableDays(new Set());
      return;
    }

    let cancelled = false;

    const fetchAll = async () => {
      setLoading(true);
      try {
        const hoy = startOfToday();
        const hasta = addMonths(hoy, 6); // próximos 6 meses
        const dias = eachDayOfInterval({ start: hoy, end: hasta });

        console.log("[useMonthAvailability] Consultando", dias.length, "días (6 meses) para serviceId:", serviceId);

        const resultados = await Promise.allSettled(
          dias.map(async (d) => {
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
            } catch {
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

        console.log("[useMonthAvailability] Días con disponibilidad:", set.size, "de", dias.length);
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
  }, [serviceId]); // ⚠️ OJO: quitamos `month` de las deps — solo se consulta 1 vez

  return { availableDays, loading };
}
