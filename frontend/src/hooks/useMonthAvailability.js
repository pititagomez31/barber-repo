import { useEffect, useState } from "react";
import { format, startOfMonth, endOfMonth, eachDayOfInterval, addDays, startOfToday } from "date-fns";
import { api } from "@/lib/api";

// Comprueba, para cada día del mes visible, si hay al menos 1 slot libre
export default function useMonthAvailability(month, serviceId) {
  const [availableDays, setAvailableDays] = useState(new Set());
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!month || !serviceId) return;
    let cancelled = false;

    const fetchAll = async () => {
      setLoading(true);
      const hoy = startOfToday();
      const desde = month < hoy ? hoy : month;
      const hasta = addDays(hoy, 60); // mismo límite que ya usas
      const dias = eachDayOfInterval({
        start: startOfMonth(desde) < desde ? desde : startOfMonth(desde),
        end: endOfMonth(desde) > hasta ? hasta : endOfMonth(desde),
      });

      const resultados = await Promise.allSettled(
        dias.map((d) =>
          api
            .get(`/availability?service_id=${serviceId}&date=${format(d, "yyyy-MM-dd")}`)
            .then((r) => ({ date: format(d, "yyyy-MM-dd"), slots: r.data?.slots || [] }))
        )
      );

      if (cancelled) return;

      const set = new Set();
      resultados.forEach((r) => {
        if (r.status === "fulfilled" && r.value.slots.length > 0) {
          set.add(r.value.date);
        }
      });

      setAvailableDays(set);
      setLoading(false);
    };

    fetchAll();
    return () => { cancelled = true; };
  }, [month, serviceId]);

  return { availableDays, loading };
}
