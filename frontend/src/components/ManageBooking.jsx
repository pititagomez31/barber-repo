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
  const [form, setForm] = useState({ code: "", phone: "" });
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
      setAppt(null); setForm({ code: "", phone: "" });
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
    <div id={id} data-testid="manage-section" className="border border-[#2A2A32] rounded-lg bg-[#1A1A1E]">
      <button onClick={() => setOpen(!open)} data-testid="manage-toggle" className="w-full flex items-center justify-between gap-3 p-4 text-left">
        <span className="text-sm"><span className="text-[#D4B77A] font-semibold">¿Ya tienes una reserva?</span> <span className="text-neutral-400">Modifícala o cancélala con tu código</span></span>
        <ChevronRight className={`h-4 w-4 text-[#D4B77A] shrink-0 transition-transform ${open ? "rotate-90" : ""}`} />
      </button>
      {open && (
        <div className="px-4 pb-5 space-y-3">
          {!appt ? (
            <div className="space-y-3">
              <Input data-testid="manage-code" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} className="bg-[#14141A] border-[#2A2A32] h-12 font-mono" placeholder="Código de reserva (8 caracteres)" />
              <Input data-testid="manage-phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="bg-[#14141A] border-[#2A2A32] h-12" placeholder="Teléfono con el que reservaste" />
              <Button data-testid="manage-search" onClick={buscar} disabled={busy} className="w-full h-11 bg-[#D4B77A] hover:bg-[#C2A366] text-[#14141A] font-semibold">
                {busy ? "Buscando…" : "Buscar mi cita"}
              </Button>
            </div>
          ) : (
            <div className="space-y-3" data-testid="manage-detail">
              <div className="rounded-md border border-[#2A2A32] bg-[#14141A] p-4 text-sm space-y-1.5">
                <p className="flex justify-between"><span className="text-neutral-500">Servicio</span><span>{appt.service_name}</span></p>
                <p className="flex justify-between"><span className="text-neutral-500">Fecha</span><span>{appt.date}</span></p>
                <p className="flex justify-between"><span className="text-neutral-500">Hora</span><span>{appt.start} – {appt.end}</span></p>
                <p className="flex justify-between"><span className="text-neutral-500">Cliente</span><span>{appt.client_name}</span></p>
              </div>
              {mode !== "edit" ? (
                <div className="flex gap-2">
                  <Button data-testid="manage-edit-btn" onClick={() => setMode("edit")} variant="outline" className="flex-1 h-11 border-[#D4B77A]/40 bg-transparent text-[#D4B77A] hover:bg-[#D4B77A]/10">Cambiar día u hora</Button>
                  <Button data-testid="manage-cancel-btn" onClick={cancelar} disabled={busy} variant="outline" className="flex-1 h-11 border-red-400/50 bg-transparent text-red-400 hover:bg-red-400/10">Cancelar cita</Button>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="flex justify-center">
                    <div className="bg-[#14141A] border border-[#2A2A32] rounded-lg p-3">
                      <Calendar mode="single" selected={mDate} onSelect={setMDate} locale={es} fromDate={startOfToday()} toDate={addDays(startOfToday(), 365)} className="[--rdp-accent-color:#D4B77A]" />
                    </div>
                  </div>
                  {mDate && (
                    mSlots.length === 0 ? (
                      <p className="text-neutral-500 text-sm text-center" data-testid="manage-no-slots">No hay huecos libres ese día.</p>
                    ) : (
                      <div className="grid grid-cols-4 gap-2">
                        {mSlots.map((t) => (
                          <button key={t} data-testid={`manage-slot-${t}`} onClick={() => modificar(t)} disabled={busy} className="py-2.5 rounded-md border border-[#2A2A32] bg-[#14141A] text-sm hover:border-[#D4B77A]/50">
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
    </div>
  );
}
