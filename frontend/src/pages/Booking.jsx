import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { format, addDays, startOfToday } from "date-fns";
import { es } from "date-fns/locale";
import { ChevronLeft, ChevronRight, Check, Scissors, Clock, Calendar as CalIcon, Phone } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent } from "@/components/ui/card";
import { Calendar } from "@/components/ui/calendar";
import { api, formatErr } from "@/lib/api";

const STEPS = ["Servicio", "Fecha", "Hora", "Tus datos"];

export default function Booking() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const preselect = params.get("service");

  const [step, setStep] = useState(0);
  const [services, setServices] = useState([]);
  const [business, setBusiness] = useState({});
  const [serviceId, setServiceId] = useState(preselect || "");
  const [date, setDate] = useState(null);
  const [slots, setSlots] = useState([]);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [time, setTime] = useState("");
  const [form, setForm] = useState({ name: "", nickname: "", phone: "", email: "", forOther: false, otherName: "", policy: false });
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(null); // appointment

  const service = useMemo(() => services.find((s) => s.id === serviceId), [services, serviceId]);

  useEffect(() => {
    api.get("/services").then((r) => setServices(Array.isArray(r.data) ? r.data : [])).catch(() => setServices([]));
    api.get("/business").then((r) => setBusiness(r.data || {})).catch(() => {});
  }, []);

  useEffect(() => {
    if (preselect && services.length && !serviceId) setServiceId(preselect);
  }, [preselect, services, serviceId]);

  useEffect(() => {
    if (!serviceId || !date) { setSlots([]); return; }
    const dateStr = format(date, "yyyy-MM-dd");
    setLoadingSlots(true);
    api.get(`/availability?service_id=${serviceId}&date=${dateStr}`)
      .then((r) => setSlots(Array.isArray(r.data?.slots) ? r.data.slots : []))
      .catch((e) => toast.error(formatErr(e)))
      .finally(() => setLoadingSlots(false));
  }, [serviceId, date]);

  const goNext = () => {
    if (step === 0 && !serviceId) return toast.error("Elige un servicio");
    if (step === 1 && !date) return toast.error("Elige una fecha");
    if (step === 2 && !time) return toast.error("Elige una hora");
    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  };
  const goBack = () => setStep((s) => Math.max(s - 1, 0));

  const submit = async () => {
    if (!form.name.trim() || !form.phone.trim()) return toast.error("Rellena tu nombre y teléfono");
    if (form.forOther && !form.otherName.trim()) return toast.error("Escribe el nombre de la persona que viene");
    if (!form.policy) return toast.error("Debes aceptar la política del 50%");
    setSubmitting(true);
    try {
      const bookerName = form.name.trim();
      const guestName = form.otherName.trim();
      const payload = {
        service_id: serviceId,
        date: format(date, "yyyy-MM-dd"),
        start: time,
        client_name: form.forOther ? guestName : bookerName,
        client_nickname: form.nickname.trim(),
        client_phone: form.phone.trim(),
        client_email: form.email.trim(),
        booker_name: form.forOther ? bookerName : "",
        accepted_policy: true,
      };
      const { data } = await api.post("/appointments", payload);
      setDone(data);
      toast.success("¡Cita confirmada!");
    } catch (e) {
      toast.error(formatErr(e));
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    const links = done.whatsapp_links || {};
    const fallbackWa = business.whatsapp
      ? `https://wa.me/${business.whatsapp}?text=${encodeURIComponent(`¡Hola +58 BarberStudio! Confirmo mi cita: ${done.date} a las ${done.start} · ${done.service_name}`)}`
      : null;
    const clienteUrl = links.cliente || fallbackWa;
    return (
      <div className="min-h-screen bg-[#14141A] text-neutral-100 noise-bg grid place-items-center px-6 py-16" data-testid="booking-success">
        <div className="max-w-lg w-full text-center fade-up">
          <div className="h-16 w-16 mx-auto rounded-full bg-[#D4B77A]/15 grid place-items-center mb-6">
            <Check className="h-8 w-8 text-[#D4B77A]" />
          </div>
          <p className="tracking-overline uppercase text-xs text-[#D4B77A] mb-3">Reserva confirmada</p>
          <h1 className="font-display text-4xl md:text-5xl tracking-tight">Nos vemos pronto, {done.client_name.split(" ")[0]}.</h1>
          <Card className="mt-8 text-left bg-[#1A1A1E] border-[#2A2A32]">
            <CardContent className="p-6 space-y-3 text-sm">
              <p className="flex justify-between"><span className="text-neutral-500">Servicio</span><span>{done.service_name}</span></p>
              <p className="flex justify-between"><span className="text-neutral-500">Fecha</span><span>{done.date}</span></p>
              <p className="flex justify-between"><span className="text-neutral-500">Hora</span><span>{done.start} – {done.end}</span></p>
              <p className="flex justify-between"><span className="text-neutral-500">Duración</span><span>{done.duration_min} min</span></p>
              <p className="flex justify-between border-t border-[#2A2A32] pt-3 mt-3"><span className="text-neutral-500">Código</span><span className="font-mono text-xs">{done.id.slice(0, 8)}</span></p>
            </CardContent>
          </Card>
          {clienteUrl && (
            <a href={clienteUrl} target="_blank" rel="noreferrer" className="block mt-6" data-testid="confirm-whatsapp-btn">
              <Button className="w-full h-12 bg-[#25D366] hover:bg-[#1EBE5D] text-white font-semibold">Confirmar mi cita por WhatsApp</Button>
            </a>
          )}
          {links.barbero && (
            <a href={links.barbero} target="_blank" rel="noreferrer" className="block mt-3" data-testid="notify-barber-btn">
              <Button variant="outline" className="w-full h-12 border-[#25D366]/50 bg-transparent text-[#25D366] hover:bg-[#25D366]/10 font-semibold">Notificar al barbero por WhatsApp</Button>
            </a>
          )}
          <Link to="/" className="block mt-4">
            <Button variant="outline" className="w-full border-white/10 bg-transparent hover:bg-white/5">Volver al inicio</Button>
          </Link>
          <p className="mt-6 text-xs text-neutral-500">Guarda tu código y teléfono por si necesitas cancelar (hasta 12h antes).</p>
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

        {/* Progress */}
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
          {step === 0 && "Elige tu servicio"}
          {step === 1 && "Elige el día"}
          {step === 2 && "Elige la hora"}
          {step === 3 && "Tus datos"}
        </h1>

        {/* Step content */}
        {step === 0 && (
          <div className="grid grid-cols-3 gap-2 md:gap-3" data-testid="step-services">
            {services.map((s) => (
              <button key={s.id} onClick={() => setServiceId(s.id)} data-testid={`pick-service-${s.id}`}
                className={`text-center p-3 md:p-6 rounded-lg border transition-colors flex flex-col items-center h-full ${serviceId === s.id ? "border-[#D4B77A] bg-[#D4B77A]/5" : "border-[#2A2A32] bg-[#1A1A1E] hover:border-[#D4B77A]/40 active:border-[#D4B77A]/40"}`}>
                <div className={`h-9 w-9 md:h-12 md:w-12 rounded-full border grid place-items-center mb-2 md:mb-3 ${serviceId === s.id ? "border-[#D4B77A] bg-[#D4B77A]/10" : "border-[#D4B77A]/30"}`}>
                  <Scissors className="h-4 w-4 md:h-5 md:w-5 text-[#D4B77A]" />
                </div>
                <p className="font-display italic text-sm md:text-xl leading-tight min-h-[2.25rem] md:min-h-[3rem] flex items-center">{s.name}</p>
                <p className="text-[10px] md:text-xs text-neutral-500 mt-1 md:mt-2 flex items-center gap-1"><Clock className="h-2.5 w-2.5 md:h-3 md:w-3" /> {s.duration_min} min</p>
              </button>
            ))}
          </div>
        )}

        {step === 1 && (
          <div className="flex justify-center" data-testid="step-date">
            <div className="bg-[#1A1A1E] border border-[#2A2A32] rounded-lg p-4">
              <Calendar
                mode="single"
                selected={date}
                onSelect={setDate}
                locale={es}
                fromDate={startOfToday()}
                toDate={addDays(startOfToday(), 60)}
                className="[--rdp-accent-color:#D4B77A]"
              />
            </div>
          </div>
        )}

        {step === 2 && (
          <div data-testid="step-time">
            <p className="text-sm text-neutral-400 mb-4">
              {date && `${format(date, "EEEE d 'de' MMMM", { locale: es })} · ${service?.name} (${service?.duration_min} min)`}
            </p>
            {loadingSlots ? (
              <p className="text-neutral-500 py-8 text-center">Cargando horas…</p>
            ) : slots.length === 0 ? (
              <p className="text-neutral-500 py-8 text-center" data-testid="no-slots">No hay huecos libres ese día. Prueba otra fecha.</p>
            ) : (
              <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-2">
                {slots.map((t) => (
                  <button key={t} onClick={() => setTime(t)} data-testid={`pick-time-${t}`}
                    className={`py-3.5 md:py-3 rounded-md border text-sm font-medium transition-colors ${time === t ? "bg-[#D4B77A] text-[#14141A] border-[#D4B77A]" : "bg-[#1A1A1E] border-[#2A2A32] hover:border-[#D4B77A]/50 active:border-[#D4B77A]/50"}`}>
                    {t}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {step === 3 && (
          <div className="space-y-5" data-testid="step-details">
            <Card className="bg-[#1A1A1E] border-[#2A2A32]">
              <CardContent className="p-5 text-sm space-y-2">
                <p className="flex justify-between"><span className="text-neutral-500">Servicio</span><span>{service?.name}</span></p>
                <p className="flex justify-between"><span className="text-neutral-500">Fecha</span><span>{date && format(date, "d MMM yyyy", { locale: es })}</span></p>
                <p className="flex justify-between"><span className="text-neutral-500">Hora</span><span>{time}</span></p>
                <p className="flex justify-between"><span className="text-neutral-500">Duración</span><span>{service?.duration_min} min</span></p>
              </CardContent>
            </Card>
            <div>
              <Label className="text-xs tracking-overline uppercase text-neutral-500">Tu nombre</Label>
              <Input data-testid="input-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-2 bg-[#1A1A1E] border-[#2A2A32] h-12" placeholder="Juan Pérez" />
            </div>
            <div>
              <Label className="text-xs tracking-overline uppercase text-neutral-500">Tu teléfono</Label>
              <Input data-testid="input-phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="mt-2 bg-[#1A1A1E] border-[#2A2A32] h-12" placeholder="+34 600 00 00 00" />
            </div>
            <div>
              <Label className="text-xs tracking-overline uppercase text-neutral-500">Tu email (opcional, para recordatorio)</Label>
              <Input data-testid="input-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="mt-2 bg-[#1A1A1E] border-[#2A2A32] h-12" placeholder="tu@email.com" />
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
            <p className="text-xs text-neutral-500 text-center">Máximo 2 citas activas por teléfono.</p>
          </div>
        )}

        {/* Nav */}
        <div className="mt-10 flex gap-3">
          {step > 0 && (
            <Button data-testid="booking-prev" variant="outline" className="border-white/10 bg-transparent hover:bg-white/5" onClick={goBack}>
              <ChevronLeft className="h-4 w-4 mr-1" /> Atrás
            </Button>
          )}
          {step < STEPS.length - 1 ? (
            <Button data-testid="booking-next" onClick={goNext} className="flex-1 h-12 bg-[#D4B77A] hover:bg-[#C2A366] text-[#14141A] font-semibold btn-shine">
              Siguiente <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          ) : (
            <Button data-testid="booking-submit" onClick={submit} disabled={submitting} className="flex-1 h-12 bg-[#D4B77A] hover:bg-[#C2A366] text-[#14141A] font-semibold btn-shine">
              {submitting ? "Reservando…" : "Confirmar reserva"}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
