import { useEffect, useState } from "react";
import { Link, useSearchParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { format, addDays, startOfToday, startOfMonth, addMonths } from "date-fns";
import { es } from "date-fns/locale";
import { ChevronLeft, ChevronRight, Check, Scissors, Clock, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent } from "@/components/ui/card";
import { Calendar } from "@/components/ui/calendar";
import { api, formatErr } from "@/lib/api";
import ManageBooking from "@/components/ManageBooking";
import useMonthAvailability from "@/hooks/useMonthAvailability";

const STEPS = ["Servicios", "Día y hora", "Tus datos"];
const MAX_ITEMS = 3;

export default function Booking() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const preselect = params.get("service");

  const [step, setStep] = useState(0);
  const [services, setServices] = useState([]);
  const [business, setBusiness] = useState({});
  const [items, setItems] = useState([]); // citas a agendar: {serviceId, name, durationMin, priceEur, date, dateStr, time}
  const [schedIdx, setSchedIdx] = useState(0);
  const [date, setDate] = useState(null);
  const [slots, setSlots] = useState([]);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [time, setTime] = useState("");
  const [form, setForm] = useState({ name: "", nickname: "", phone: "", phone2: "", email: "", forOther: false, otherName: "", policy: false, whatsapp: false });
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(null); // array de citas creadas

  // Mes visible en el calendario (solo para navegación visual)
  const [visibleMonth, setVisibleMonth] = useState(startOfMonth(new Date()));

  const current = items[schedIdx];

  // Consulta disponibilidad de los próximos 6 meses (una sola vez por servicio)
  const { availableDays, loading: loadingAvailability } = useMonthAvailability(visibleMonth, current?.serviceId);

  useEffect(() => {
    api.get("/services").then((r) => setServices(Array.isArray(r.data) ? r.data : [])).catch(() => setServices([]));
    api.get("/business").then((r) => setBusiness(r.data || {})).catch(() => {});
  }, []);

  useEffect(() => {
    if (preselect && services.length && items.length === 0) {
      const s = services.find((x) => x.id === preselect);
      if (s) setItems([{ serviceId: s.id, name: s.name, durationMin: s.duration_min, priceEur: s.price_eur, date: null, dateStr: "", time: "" }]);
    }
  }, [preselect, services, items.length]);

  useEffect(() => {
    if (!current || !date) { setSlots([]); return; }
    const dateStr = format(date, "yyyy-MM-dd");
    setLoadingSlots(true);
    api.get(`/availability?service_id=${current.serviceId}&date=${dateStr}`)
      .then((r) => setSlots(Array.isArray(r.data?.slots) ? r.data.slots : []))
      .catch((e) => toast.error(formatErr(e)))
      .finally(() => setLoadingSlots(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current?.serviceId, date, schedIdx]);

  const addService = (s) => {
    if (items.length >= MAX_ITEMS) return toast.error(`Máximo ${MAX_ITEMS} citas por reserva`);
    setItems((prev) => [...prev, { serviceId: s.id, name: s.name, durationMin: s.duration_min, priceEur: s.price_eur, date: null, dateStr: "", time: "" }]);
  };
  const removeItem = (idx) => setItems((prev) => prev.filter((_, i) => i !== idx));
  const setGuest = (idx, field, val) => setItems((prev) => prev.map((it, i) => (i === idx ? { ...it, [field]: val } : it)));

  const countOf = (id) => items.filter((i) => i.serviceId === id).length;

  const loadItemIntoView = (list, idx) => {
    setSchedIdx(idx);
    setDate(list[idx]?.date || null);
    setTime(list[idx]?.time || "");
  };

  const pickTime = (t) => {
    if (!date) return;
    const dateStr = format(date, "yyyy-MM-dd");
    const upd = items.map((it, i) => (i === schedIdx ? { ...it, date, dateStr, time: t } : it));
    setItems(upd);
    if (schedIdx + 1 < upd.length) {
      toast.success(`Cita ${schedIdx + 1} lista · ahora la ${schedIdx + 2} de ${upd.length}`);
      loadItemIntoView(upd, schedIdx + 1);
    } else {
      setTime(t);
      setStep(2);
    }
  };

  const totalMin = items.reduce((acc, i) => acc + (i.durationMin || 0), 0);

  // Excluir las horas que ya ocupan las otras citas del carrito ese mismo día
  const toMin = (s) => parseInt(s.slice(0, 2)) * 60 + parseInt(s.slice(3));
  const dateStrNow = date ? format(date, "yyyy-MM-dd") : "";
  const visibleSlots = !current ? slots : slots.filter((t) => {
    const t0 = toMin(t);
    const t1 = t0 + current.durationMin;
    return !items.some((it, i) => {
      if (i === schedIdx || !it.time || it.dateStr !== dateStrNow) return false;
      const b0 = toMin(it.time);
      const b1 = b0 + it.durationMin;
      return !(t1 <= b0 || t0 >= b1);
    });
  });

  const goNext = () => {
    if (step === 0) {
      if (!items.length) return toast.error("Elige al menos un servicio");
      loadItemIntoView(items, 0);
    }
    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  };
  const goBack = () => {
    if (step === 2) {
      loadItemIntoView(items, items.length - 1);
      setStep(1);
      return;
    }
    if (step === 1 && schedIdx > 0) {
      const upd = items.map((it, i) => (i === schedIdx ? { ...it, date, dateStr: date ? format(date, "yyyy-MM-dd") : "", time } : it));
      setItems(upd);
      loadItemIntoView(upd, schedIdx - 1);
      return;
    }
    setStep(0);
  };

  const submit = async () => {
    if (!form.name.trim() || !form.phone.trim()) return toast.error("Rellena tu nombre y teléfono");
    if (!form.phone2.trim()) return toast.error("Confirma tu número de WhatsApp");
    if (form.phone.trim() !== form.phone2.trim()) return toast.error("Los teléfonos no coinciden. Revísalos para no perderte la confirmación por WhatsApp");
    if (form.forOther && !form.otherName.trim()) return toast.error("Escribe el nombre de la persona que viene");
    for (let i = 1; i < items.length; i++) {
      if (!(items[i].guestName || "").trim()) return toast.error(`Escribe el nombre de la persona de la cita ${i + 1}`);
    }
    if (!form.policy) return toast.error("Debes aceptar la política del 50%");
    if (!form.whatsapp) return toast.error("Debes aceptar recibir confirmaciones y recordatorios por WhatsApp");
    setSubmitting(true);
    const bookerName = form.name.trim();
    const guestName = form.otherName.trim();
    const payloadFor = (it, idx) => {
      const isExtra = idx > 0;
      const guest = (it.guestName || "").trim();
      const guestPhone = (it.guestPhone || "").trim();
      return {
        service_id: it.serviceId,
        date: it.dateStr,
        start: it.time,
        client_name: isExtra ? guest : form.forOther ? guestName : bookerName,
        client_nickname: isExtra ? "" : form.nickname.trim(),
        client_phone: isExtra && guestPhone ? guestPhone : form.phone.trim(),
        client_email: form.email.trim(),
        booker_name: isExtra ? bookerName : form.forOther ? bookerName : "",
        accepted_policy: true,
        opt_in_whatsapp: true,
      };
    };
    try {
      if (items.length > 1) {
        const { data } = await api.post("/appointments/batch", { items: items.map((it, idx) => payloadFor(it, idx)) });
        setDone(data);
        toast.success("¡Citas confirmadas!");
      } else {
        const { data } = await api.post("/appointments", payloadFor(items[0], 0));
        setDone([data]);
        toast.success("¡Cita confirmada!");
      }
    } catch (e) {
      toast.error(formatErr(e));
    }
    setSubmitting(false);
  };

  if (done) {
    const firstName = done[0].client_name.split(" ")[0];
    const plural = done.length > 1;
    const addAnother = () => {
      setItems([]); setSchedIdx(0); setDate(null); setTime("");
      setForm({ ...form, policy: false, whatsapp: false });
      setDone(null); setStep(0);
    };
    return (
      <div className="min-h-screen bg-[#14141A] text-neutral-100 noise-bg grid place-items-center px-6 py-16" data-testid="booking-success">
        <div className="max-w-lg w-full text-center fade-up">
          <div className="h-16 w-16 mx-auto rounded-full bg-[#D4B77A]/15 grid place-items-center mb-6">
            <Check className="h-8 w-8 text-[#D4B77A]" />
          </div>
          <p className="tracking-overline uppercase text-xs text-[#D4B77A] mb-3">{plural ? `${done.length} reservas confirmadas` : "Reserva confirmada"}</p>
          <h1 className="font-display text-4xl md:text-5xl tracking-tight">Nos vemos pronto, {firstName}.</h1>
          <div className="mt-8 space-y-3">
            {done.map((a, i) => (
              <Card key={a.id} data-testid={`success-item-${i}`} className="text-left bg-[#1A1A1E] border-[#2A2A32]">
                <CardContent className="p-5 space-y-2 text-sm">
                  <p className="flex justify-between"><span className="text-neutral-500">Servicio</span><span>{a.service_name}</span></p>
                  <p className="flex justify-between"><span className="text-neutral-500">Fecha</span><span>{a.date}</span></p>
                  <p className="flex justify-between"><span className="text-neutral-500">Hora</span><span>{a.start} – {a.end}</span></p>
                  <p className="flex justify-between border-t border-[#2A2A32] pt-2"><span className="text-neutral-500">Código</span><span className="font-mono text-xs">{a.id.slice(0, 8)}</span></p>
                </CardContent>
              </Card>
            ))}
          </div>
          <div className="mt-6 rounded-lg border border-[#25D366]/30 bg-[#25D366]/5 p-4 text-sm text-neutral-300" data-testid="whatsapp-auto-note">
            <p>Recibirás la <span className="text-[#25D366] font-semibold">confirmación por WhatsApp</span> automáticamente, y el barbero ya ha sido notificado. No necesitas hacer nada más.</p>
          </div>
          <Button onClick={addAnother} data-testid="add-another-btn" variant="outline" className="w-full mt-3 h-12 border-[#D4B77A]/40 bg-transparent text-[#D4B77A] hover:bg-[#D4B77A]/10 font-semibold">Añadir otra cita</Button>
          <Link to="/" className="block mt-3">
            <Button variant="outline" className="w-full border-white/10 bg-transparent hover:bg-white/5">Volver al inicio</Button>
          </Link>
          <p className="mt-6 text-xs text-neutral-500">Guarda tus códigos y teléfono por si necesitas cancelar (hasta 12h antes).</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#14141A] text-neutral-100 noise-bg pb-8" data-testid="booking-page">
      <div className="max-w-3xl mx-auto px-4 md:px-5 py-6 md:py-10">
        <button onClick={() => nav(-1)} className="text-neutral-400 hover:text-[#D4B77A] flex items-center gap-1 mb-5 md:mb-6 text-sm" data-testid="booking-back">
          <ChevronLeft className="h-4 w-4" /> Volver
        </button>

        <div className="flex items-center justify-between mb-8 md:mb-10" data-testid="booking-progress">
          {STEPS.map((label, i) => (
            <div key={label} className="flex-1 flex items-center">
              <div className={`h-8 w-8 shrink-0 rounded-full grid place-items-center text-xs font-semibold border ${i <= step ? "bg-[#D4B77A] text-[#14141A] border-[#D4B77A]" : "bg-transparent text-neutral-500 border-[#2A2A32]"}`}>{i + 1}</div>
              <div className="ml-2 hidden sm:block text-xs">
                <p className={`tracking-overline uppercase ${i <= step ? "text-[#D4B77A]" : "text-neutral-500"}`}>{label}</p>
              </div>
              {i < STEPS.length - 1 && <div className={`flex-1 h-px mx-2 md:mx-3 ${i < step ? "bg-[#D4B77A]" : "bg-[#2A2A32]"}`} />}
            </div>
          ))}
        </div>

        <h1 className="font-display text-3xl md:text-4xl tracking-tight italic mb-6 md:mb-8" data-testid="booking-step-title">
          {step === 0 && "Elige tus servicios"}
          {step === 1 && current && `Cita ${schedIdx + 1} de ${items.length}: día y hora`}
          {step === 2 && "Tus datos"}
        </h1>

        {step === 0 && (
          <div data-testid="step-services">
            <p className="text-sm text-neutral-400 mb-4">Pulsa los servicios que quieras — puedes añadir varios y agendarlos todos de una vez.</p>
            {items.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-5" data-testid="booking-cart">
                {items.map((it, i) => (
                  <span key={i} data-testid={`cart-chip-${i}`} className="inline-flex items-center gap-1.5 pl-3 pr-1.5 py-1.5 rounded-full bg-[#D4B77A]/10 border border-[#D4B77A]/40 text-xs text-[#D4B77A]">
                    <span className="font-semibold">{i + 1}.</span> {it.name}
                    <button onClick={() => removeItem(i)} data-testid={`cart-remove-${i}`} className="h-5 w-5 grid place-items-center rounded-full hover:bg-[#D4B77A]/20" aria-label="Quitar">
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
            <div className="grid grid-cols-3 gap-2 md:gap-3">
              {services.map((s) => {
                const n = countOf(s.id);
                return (
                  <button key={s.id} onClick={() => addService(s)} data-testid={`pick-service-${s.id}`}
                    className={`relative text-center p-3 md:p-6 rounded-lg border transition-colors flex flex-col items-center h-full ${n ? "border-[#D4B77A] bg-[#D4B77A]/5" : "border-[#2A2A32] bg-[#1A1A1E] hover:border-[#D4B77A]/40 active:border-[#D4B77A]/40"}`}>
                    {n > 0 && (
                      <span data-testid={`pick-count-${s.id}`} className="absolute top-2 right-2 h-5 min-w-[1.25rem] px-1 rounded-full bg-[#D4B77A] text-[#14141A] text-[10px] font-bold grid place-items-center">×{n}</span>
                    )}
                    <div className={`h-9 w-9 md:h-12 md:w-12 rounded-full border grid place-items-center mb-2 md:mb-3 ${n ? "border-[#D4B77A] bg-[#D4B77A]/10" : "border-[#D4B77A]/30"}`}>
                      <Scissors className="h-4 w-4 md:h-5 md:w-5 text-[#D4B77A]" />
                    </div>
                    <p className="font-display italic text-sm md:text-xl leading-tight min-h-[2.25rem] md:min-h-[3rem] flex items-center">{s.name}</p>
                    <p className="text-[10px] md:text-xs text-neutral-500 mt-1 md:mt-2 flex items-center gap-1"><Clock className="h-2.5 w-2.5 md:h-3 md:w-3" /> {s.duration_min} min</p>
                  </button>
                );
              })}
            </div>
            <div className="mt-8">
              <ManageBooking id="gestionar" />
            </div>
          </div>
        )}

        {step === 1 && current && (
          <div className="space-y-6">
            <div className="flex flex-wrap gap-2" data-testid="sched-progress">
              {items.map((it, i) => (
                <span key={i} className={`text-[11px] px-2.5 py-1 rounded-full border ${i === schedIdx ? "border-[#D4B77A] text-[#D4B77A]" : it.time ? "border-green-500/40 text-green-400" : "border-[#2A2A32] text-neutral-500"}`}>
                  {i + 1}. {it.name}{it.time ? ` · ${it.dateStr} ${it.time}` : ""}
                </span>
              ))}
            </div>
            <div className="flex justify-center" data-testid="step-date">
              <div className="bg-[#1A1A1E] border border-[#2A2A32] rounded-lg p-4 relative">
                {loadingAvailability && (
                  <div className="absolute top-2 right-2 text-[10px] text-[#D4B77A]/70 animate-pulse" data-testid="availability-loading">
                    cargando disponibilidad…
                  </div>
                )}
                <Calendar
                  mode="single"
                  selected={date}
                  onSelect={(d) => { setDate(d); setTime(""); }}
                  locale={es}
                  fromDate={startOfToday()}
                  toDate={addDays(startOfToday(), 365)}
                  onMonthChange={setVisibleMonth}
                  className="[--rdp-accent-color:#D4B77A]"
                  modifiers={{
                    diaDisponible: (d) => {
                      if (!d) return false;
                      const y = d.getFullYear();
                      const m = String(d.getMonth() + 1).padStart(2, "0");
                      const day = String(d.getDate()).padStart(2, "0");
                      const key = `${y}-${m}-${day}`;
                      return availableDays.has(key);
                    },
                    diaNoDisponible: (d) => {
                      if (!d) return false;
                      const y = d.getFullYear();
                      const m = String(d.getMonth() + 1).padStart(2, "0");
                      const day = String(d.getDate()).padStart(2, "0");
                      const key = `${y}-${m}-${day}`;
                      const hoy = startOfToday();
                      const max = addMonths(hoy, 6);
                      return d >= hoy && d <= max && !availableDays.has(key);
                    },
                  }}
                  modifiersClassNames={{
                    diaDisponible: "dia-disponible",
                    diaNoDisponible: "dia-no-disponible",
                  }}
                />
              </div>
            </div>
            <div data-testid="step-time">
              {!date ? (
                <p className="text-neutral-500 py-4 text-center text-sm">Elige un día para ver las horas disponibles.</p>
              ) : loadingSlots ? (
                <p className="text-neutral-500 py-8 text-center">Cargando horas…</p>
              ) : visibleSlots.length === 0 ? (
                <p className="text-neutral-500 py-8 text-center" data-testid="no-slots">No hay huecos libres ese día. Prueba otra fecha.</p>
              ) : (
                <div>
                  <p className="text-sm text-neutral-400 mb-3">
                    {format(date, "EEEE d 'de' MMMM", { locale: es })} · {current.name} ({current.durationMin} min)
                  </p>
                  <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-2">
                    {visibleSlots.map((t) => (
                      <button key={t} onClick={() => pickTime(t)} data-testid={`pick-time-${t}`}
                        className={`py-3.5 md:py-3 rounded-md border text-sm font-medium transition-colors ${time === t ? "bg-[#D4B77A] text-[#14141A] border-[#D4B77A]" : "bg-[#1A1A1E] border-[#2A2A32] hover:border-[#D4B77A]/50 active:border-[#D4B77A]/50"}`}>
                        {t}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-5" data-testid="step-details">
            <Card className="bg-[#1A1A1E] border-[#2A2A32]">
              <CardContent className="p-5 text-sm space-y-2">
                {items.map((it, i) => (
                  <div key={i} className="flex items-center justify-between gap-3" data-testid={`review-item-${i}`}>
                    <span className="text-neutral-500"><span className="text-[#D4B77A] font-semibold">Cita {i + 1}</span> · {it.name}</span>
                    <span className="flex items-center gap-2 shrink-0">
                      <span className="text-right">{it.dateStr} · {it.time} <span className="text-neutral-500">({it.durationMin} min)</span></span>
                      {items.length > 1 && (
                        <button onClick={() => removeItem(i)} data-testid={`review-remove-${i}`} aria-label={`Eliminar cita ${i + 1}`}
                          className="h-6 w-6 grid place-items-center rounded-full border border-red-400/60 text-red-400 hover:bg-red-400 hover:text-[#14141A] transition-colors">
                          <X className="h-3.5 w-3.5" />
                        </button>
                      )}
                    </span>
                  </div>
                ))}
                <p className="flex justify-between border-t border-[#2A2A32] pt-2 mt-1"><span className="text-neutral-500">Tiempo total</span><span data-testid="booking-total">{totalMin} min</span></p>
              </CardContent>
            </Card>
            {items.length > 1 && (
              <div className="space-y-4" data-testid="guests-section">
                <p className="text-xs tracking-overline uppercase text-neutral-500">¿Quién viene a cada cita?</p>
                {items.slice(1).map((it, k) => {
                  const i = k + 1;
                  return (
                    <Card key={i} data-testid={`guest-card-${i}`} className="bg-[#1A1A1E] border-[#2A2A32]">
                      <CardContent className="p-4 space-y-3">
                        <p className="text-sm"><span className="text-[#D4B77A] font-semibold">Cita {i + 1}</span> <span className="text-neutral-400">· {it.name} — {it.dateStr} · {it.time}</span></p>
                        <div>
                          <Label className="text-xs tracking-overline uppercase text-neutral-500">Nombre de la persona *</Label>
                          <Input data-testid={`guest-name-${i}`} value={it.guestName || ""} onChange={(e) => setGuest(i, "guestName", e.target.value)} className="mt-2 bg-[#14141A] border-[#2A2A32] h-12" placeholder="Nombre y apellido" />
                        </div>
                        <div>
                          <Label className="text-xs tracking-overline uppercase text-neutral-500">Su teléfono (opcional)</Label>
                          <Input data-testid={`guest-phone-${i}`} value={it.guestPhone || ""} onChange={(e) => setGuest(i, "guestPhone", e.target.value)} className="mt-2 bg-[#14141A] border-[#2A2A32] h-12" placeholder="Si lo dejas vacío se usa el tuyo" />
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            )}
            <div>
              <Label className="text-xs tracking-overline uppercase text-neutral-500">Tu nombre</Label>
              <Input data-testid="input-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-2 bg-[#1A1A1E] border-[#2A2A32] h-12" placeholder="Juan Pérez" />
            </div>
            <div>
              <Label className="text-xs tracking-overline uppercase text-neutral-500">Tu teléfono</Label>
              <Input
                data-testid="input-phone"
                value={form.phone}
                onChange={(e) => {
                  const soloNumeros = e.target.value.replace(/\D/g, "");
                  setForm({ ...form, phone: soloNumeros });
                }}
                className="mt-2 bg-[#1A1A1E] border-[#2A2A32] h-12"
                placeholder="600303030"
                inputMode="numeric"
              />
            </div>
            <div>
              <Label className="text-xs tracking-overline uppercase text-neutral-500">Confirma tu WhatsApp</Label>
              <Input
                data-testid="input-phone-confirm"
                value={form.phone2}
                onChange={(e) => {
                  const soloNumeros = e.target.value.replace(/\D/g, "");
                  setForm({ ...form, phone2: soloNumeros });
                }}
                className="mt-2 bg-[#1A1A1E] border-[#2A2A32] h-12"
                placeholder="Repite tu número"
                inputMode="numeric"
              />
              {form.phone2 && form.phone !== form.phone2 && (
                <p className="text-xs text-red-400 mt-1.5">Los números no coinciden</p>
              )}
            </div>
            <div>
              <Label className="text-xs tracking-overline uppercase text-neutral-500">Apodo (opcional)</Label>
              <Input data-testid="input-nickname" value={form.nickname} onChange={(e) => setForm({ ...form, nickname: e.target.value })} className="mt-2 bg-[#1A1A1E] border-[#2A2A32] h-12" placeholder="Juanito" />
            </div>
            <label className="flex items-start gap-3 p-4 rounded-md border border-[#2A2A32] bg-[#1A1A1E]" data-testid="forother-wrap">
              <Checkbox data-testid="input-forother" checked={form.forOther} onCheckedChange={(v) => setForm({ ...form, forOther: !!v })} className="mt-0.5 border-[#D4B77A] data-[state=checked]:bg-[#D4B77A] data-[state=checked]:text-[#14141A]" />
              <span className="text-sm text-neutral-300 leading-relaxed">La cita es para <strong className="text-[#D4B77A]">otra persona</strong> (ej: mi hijo, un amigo)</span>
            </label>
            {form.forOther && (
              <div data-testid="other-name-wrap" className="fade-up">
                <Label className="text-xs tracking-overline uppercase text-neutral-500">Nombre de quien viene</Label>
                <Input data-testid="input-other-name" value={form.otherName} onChange={(e) => setForm({ ...form, otherName: e.target.value })} className="mt-2 bg-[#1A1A1E] border-[#2A2A32] h-12" placeholder="Nombre y apellido" />
              </div>
            )}
            <label className="flex items-start gap-3 p-4 rounded-md border border-[#2A2A32] bg-[#1A1A1E]" data-testid="policy-checkbox-wrap">
              <Checkbox data-testid="input-policy" checked={form.policy} onCheckedChange={(v) => setForm({ ...form, policy: !!v })} className="mt-1 border-[#D4B77A] data-[state=checked]:bg-[#D4B77A] data-[state=checked]:text-[#14141A]" />
              <span className="text-sm text-neutral-300 leading-relaxed">
                Acepto la <strong className="text-[#D4B77A]">política del 50%</strong>: si no me presento sin avisar, el barbero podrá cobrarme el 50% del servicio en mi próxima visita o bloquear futuras reservas. Cancelaciones permitidas hasta 12h antes.
              </span>
            </label>
            <label className="flex items-start gap-3 p-4 rounded-md border border-[#2A2A32] bg-[#1A1A1E]" data-testid="whatsapp-optin-wrap">
              <Checkbox data-testid="input-whatsapp-optin" checked={form.whatsapp} onCheckedChange={(v) => setForm({ ...form, whatsapp: !!v })} className="mt-1 border-[#25D366] data-[state=checked]:bg-[#25D366] data-[state=checked]:text-[#14141A]" />
              <span className="text-sm text-neutral-300 leading-relaxed">
                Acepto recibir <strong className="text-[#25D366]">confirmaciones y recordatorios de mi cita a través de WhatsApp</strong>. Puedo darme de baja en cualquier momento respondiendo STOP.
              </span>
            </label>
            <p className="text-xs text-neutral-500 text-center">Máximo 6 citas activas por teléfono.</p>
          </div>
        )}

        <div className="mt-10 flex gap-3">
          {step > 0 && (
            <Button data-testid="booking-prev" variant="outline" className="border-white/10 bg-transparent hover:bg-white/5" onClick={goBack}>
              <ChevronLeft className="h-4 w-4 mr-1" /> Atrás
            </Button>
          )}
          {step === 0 && (
            <Button data-testid="booking-next" onClick={goNext} className="flex-1 h-12 bg-[#D4B77A] hover:bg-[#C2A366] text-[#14141A] font-semibold btn-shine">
              Siguiente <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          )}
          {step === 2 && (
            <Button data-testid="booking-submit" onClick={submit} disabled={submitting || !form.policy || !form.whatsapp || !form.phone2.trim() || form.phone.trim() !== form.phone2.trim()} className="flex-1 h-12 bg-[#D4B77A] hover:bg-[#C2A366] text-[#14141A] font-semibold btn-shine">
              {submitting ? "Reservando…" : items.length > 1 ? `Confirmar ${items.length} citas` : "Confirmar reserva"}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
