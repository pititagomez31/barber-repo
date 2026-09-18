import { useEffect, useState } from "react";
import { toast } from "sonner";
import { format, addDays, startOfToday } from "date-fns";
import { es } from "date-fns/locale";
import { ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Calendar } from "@/components/ui/calendar";
import { api, formatErr } from "@/lib/api";

export default function ManageBooking({ id = "gestionar", defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const [form, setForm] = useState({ code: "", phone: "", phone2: "" });
  const [appt, setAppt] = useState(null);
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState("");
  const [mDate, setMDate] = useState(null);
  const [mSlots, setMSlots] = useState([]);

  useEffect(() => {
    if (typeof window !== "undefined" && window.location.hash === `#${id}`) {
      setOpen(true);
      setTimeout(() => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" }), 400);
    }
  }, [id]);

  useEffect(() => {
    if (mode === "edit" && appt && mDate) {
      const ds = format(mDate, "yyyy-MM-dd");
      api.get(`/availability?service_id=${appt.service_id}&date=${ds}`)
        .then((r) => setMSlots(Array.isArray(r.data?.slots) ? r.data.slots : []))
        .catch(() => setMSlots([]));
    }
  }, [mode, appt, mDate]);

  const buscar = async () => {
    if (form.code.trim().length < 6 || !form.phone.trim()) return toast.error("Introduce el código y el teléfono");
    if (form.phone.trim() !== form.phone2.trim()) return toast.error("Los teléfonos no coinciden. Revísalos e inténtalo de nuevo");
    setBusy(true);
    try {
      const { data } = await api.post("/appointments/gestionar", { code: form.code.trim(), phone: form.phone.trim() });
      setAppt(data); setMode(""); setMDate(null);
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(false); }
  };

  const cancelar = async () => {
    if (!window.confirm("¿Seguro que quieres cancelar esta cita?")) return;
    setBusy(true);
    try {
      await api.post(`/appointments/${appt.id}/cancel?phone=${encodeURIComponent(form.phone.trim())}`);
      toast.success("Cita cancelada");
      setAppt(null); setForm({ code: "", phone: "", phone2: "" });
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(false); }
  };

  const modificar = async (t) => {
    setBusy(true);
    try {
      const { data } = await api.post(`/appointments/${appt.id}/modificar`, {
        phone: form.phone.trim(), date: format(mDate, "yyyy-MM-dd"), start: t,
      });
      setAppt(data); setMode(""); setMDate(null);
      toast.success("Cita movida correctamente");
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(false); }
  };

  return (
    <section id={id} className="scroll-mt-24">
      <button
        onClick={() => setOpen(!open)}
        data-testid="manage-toggle"
        className="w-full flex items-center justify-between gap-3 p-4 text-left"
      >
        ¿Ya tienes una reserva? Modifícala o cancélala con tu código
        <ChevronRight className={`h-5 w-5 shrink-0 text-[#D4B77A] transition-transform ${open ? "rotate-90" : ""}`} />
      </button>

      {open && (
        <div className="px-4 pb-4">
          {!appt ? (
            <div className="space-y-3">
              <div className="space-y-3">
                <Input
                  value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value })}
                  className="bg-[#14141A] border-[#2A2A32] h-12 font-mono"
                  placeholder="Código de reserva (8 caracteres)"
                  maxLength={8}
                />
                <Input
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  inputMode="tel"
                  className="bg-[#14141A] border-[#2A2A32] h-12"
                  placeholder="Tu teléfono"
                />
                <Input
                  value={form.phone2}
                  onChange={(e) => setForm({ ...form, phone2: e.target.value })}
                  inputMode="tel"
                  className="bg-[#14141A] border-[#2A2A32] h-12"
                  placeholder="Confirma tu teléfono (ej. 600303030)"
                />
                <Button
                  onClick={buscar}
                  disabled={busy}
                  className="w-full h-12 bg-[#D4B77A] text-black font-medium hover:bg-[#e2c98f]"
                >
                  {busy ? "Buscando…" : "Buscar mi cita"}
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="rounded-lg border border-[#2A2A32] bg-[#14141A] divide-y divide-[#2A2A32]">
                <div className="flex justify-between gap-3 p-3 text-sm">
                  <span className="text-neutral-500">Servicio</span>
                  <span>{appt.service_name}</span>
                </div>
                <div className="flex justify-between gap-3 p-3 text-sm">
                  <span className="text-neutral-500">Fecha</span>
                  <span>{appt.date}</span>
                </div>
                <div className="flex justify-between gap-3 p-3 text-sm">
                  <span className="text-neutral-500">Hora</span>
                  <span>{appt.start} – {appt.end}</span>
                </div>
                <div className="flex justify-between gap-3 p-3 text-sm">
                  <span className="text-neutral-500">Cliente</span>
                  <span>{appt.client_name}</span>
                </div>
              </div>

              {mode !== "edit" ? (
                <div className="flex gap-3">
                  <Button
                    onClick={() => setMode("edit")}
                    variant="outline"
                    className="flex-1 h-11 border-[#D4B77A]/40 bg-transparent text-[#D4B77A] hover:bg-[#D4B77A]/10"
                  >
                    Cambiar día u hora
                  </Button>
                  <Button onClick={cancelar} disabled={busy} variant="outline" className="flex-1 h-11 border-red-500/40 bg-transparent text-red-400 hover:bg-red-500/10">
                    Cancelar cita
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="flex justify-center">
                    <Calendar
                      mode="single"
                      selected={mDate}
                      onSelect={setMDate}
                      disabled={(d) => d < startOfToday() || d > addDays(startOfToday(), 60)}
                      locale={es}
                    />
                  </div>

                  {mDate && (
                    mSlots.length === 0 ? (
                      <p className="text-sm text-neutral-500 text-center py-2">No hay huecos libres ese día.</p>
                    ) : (
                      <div className="grid grid-cols-4 gap-2">
                        {mSlots.map((t) => (
                          <button
                            key={t}
                            onClick={() => modificar(t)}
                            disabled={busy}
                            className="py-2.5 rounded-md border border-[#2A2A32] bg-[#14141A] text-sm hover:border-[#D4B77A]/50"
                          >
                            {t}
                          </button>
                        ))}
                      </div>
                    )
                  )}
                  <button onClick={() => { setMode(""); setMDate(null); }} className="text-xs text-neutral-500 underline">← Volver</button>
                </div>
              )}
              <button onClick={() => { setAppt(null); setMode(""); setMDate(null); }} className="text-xs text-neutral-500 underline" data-testid="manage-reset">← Buscar otra cita</button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
