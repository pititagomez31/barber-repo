import { useEffect, useState } from "react";
import { api, prettyDate } from "@/lib/api";
import MonthCalendar from "@/components/MonthCalendar";
import { toast } from "sonner";
import { Scissors, Clock, Phone, User, CheckCircle2 } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

export default function Booking() {
  const [services, setServices] = useState([]);
  const [serviceId, setServiceId] = useState(null);
  const [anchor, setAnchor] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState(null);
  const [slots, setSlots] = useState([]);
  const [schedule, setSchedule] = useState(null);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [slot, setSlot] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState({ client_name: "", client_phone: "" });
  const [confirmed, setConfirmed] = useState(null);

  useEffect(() => {
    api.get("/services").then((r) => {
      setServices(r.data);
      if (r.data.length) setServiceId(r.data[0].id);
    });
  }, []);

  useEffect(() => {
    if (!serviceId || !selectedDate) return;
    setLoadingSlots(true);
    setSlot(null);
    api
      .get("/availability", { params: { service_id: serviceId, date: selectedDate } })
      .then((r) => {
        setSlots(r.data.slots);
        setSchedule(r.data.schedule);
      })
      .catch(() => toast.error("No se pudo cargar la disponibilidad"))
      .finally(() => setLoadingSlots(false));
  }, [serviceId, selectedDate]);

  const activeService = services.find((s) => s.id === serviceId);

  const book = async () => {
    if (!form.client_name || !form.client_phone) {
      toast.error("Completa tu nombre y teléfono");
      return;
    }
    try {
      await api.post("/appointments", {
        service_id: serviceId,
        date: selectedDate,
        time: slot,
        ...form,
      });
      setDialogOpen(false);
      setConfirmed({ date: selectedDate, time: slot, service: activeService?.name });
      setForm({ client_name: "", client_phone: "" });
      // refresh slots
      const r = await api.get("/availability", { params: { service_id: serviceId, date: selectedDate } });
      setSlots(r.data.slots);
      setSlot(null);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "No se pudo reservar");
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-5 py-10">
      <div className="mb-10">
        <div className="eyebrow" data-testid="booking-eyebrow">RESERVA TU CITA</div>
        <h1 className="display text-5xl sm:text-6xl mt-2">
          Elige tu <span style={{ color: "var(--bs-gold)" }}>estilo</span>
        </h1>
        <p className="text-[var(--bs-muted)] mt-3 max-w-lg">
          Selecciona un servicio, escoge el día y reserva en segundos. Sin llamadas, sin esperas.
        </p>
      </div>

      <div className="grid lg:grid-cols-2 gap-8">
        {/* Left: service + calendar */}
        <div className="space-y-8">
          <div>
            <h2 className="text-lg font-bold mb-3">1. Servicio</h2>
            <div className="grid sm:grid-cols-2 gap-3" data-testid="services-list">
              {services.map((s) => (
                <button
                  key={s.id}
                  data-testid={`service-${s.id}`}
                  onClick={() => setServiceId(s.id)}
                  className={
                    "text-left p-4 rounded-2xl border transition-all " +
                    (serviceId === s.id
                      ? "border-[var(--bs-gold)] bg-[#221d13]"
                      : "border-[var(--bs-line)] bg-[var(--bs-card)] hover:border-[var(--bs-gold)]")
                  }
                >
                  <div className="flex items-center gap-2 font-bold">
                    <Scissors size={16} className="text-[var(--bs-gold)]" />
                    {s.name}
                  </div>
                  <div className="text-sm text-[var(--bs-muted)] mt-1 flex items-center gap-3">
                    <span className="flex items-center gap-1"><Clock size={13} />{s.duration_min} min</span>
                    <span>${s.price}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="p-5 rounded-2xl border border-[var(--bs-line)] bg-[var(--bs-card)]">
            <h2 className="text-lg font-bold mb-4">2. Fecha</h2>
            <MonthCalendar
              anchor={anchor}
              onAnchorChange={setAnchor}
              selected={selectedDate}
              onSelect={setSelectedDate}
              disablePast
            />
          </div>
        </div>

        {/* Right: slots */}
        <div className="p-6 rounded-2xl border border-[var(--bs-line)] bg-[var(--bs-card)] h-fit lg:sticky lg:top-24">
          <h2 className="text-lg font-bold mb-1">3. Hora disponible</h2>
          {!selectedDate && (
            <p className="text-[var(--bs-muted)]" data-testid="pick-date-hint">
              Elige una fecha para ver los horarios.
            </p>
          )}
          {selectedDate && (
            <>
              <p className="text-[var(--bs-gold)] font-semibold mb-1" data-testid="selected-date-label">
                {prettyDate(selectedDate)}
              </p>
              {schedule?.source === "override" && (
                <p className="text-xs text-[var(--bs-muted)] mb-3" data-testid="override-note">
                  ⭐ Horario especial{schedule.reason ? `: ${schedule.reason}` : ""}
                </p>
              )}
              {loadingSlots ? (
                <p className="text-[var(--bs-muted)] mt-4">Cargando…</p>
              ) : slots.length === 0 ? (
                <p className="text-[var(--bs-muted)] mt-4" data-testid="no-slots">
                  No hay horarios disponibles este día.
                </p>
              ) : (
                <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 mt-4" data-testid="slots-grid">
                  {slots.map((t) => (
                    <button
                      key={t}
                      data-testid={`slot-${t}`}
                      className={"slot-btn" + (slot === t ? " selected" : "")}
                      onClick={() => setSlot(t)}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              )}
              <Button
                className="w-full mt-6 bg-[var(--bs-gold)] text-[var(--bs-bg)] hover:bg-[var(--bs-gold-2)] font-bold h-11"
                disabled={!slot}
                data-testid="continue-booking-btn"
                onClick={() => setDialogOpen(true)}
              >
                Reservar {slot || ""}
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Booking dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent data-testid="booking-dialog" className="bg-[var(--bs-card)] border-[var(--bs-line)] text-[var(--bs-cream)]">
          <DialogHeader>
            <DialogTitle className="display text-2xl">Confirma tu cita</DialogTitle>
          </DialogHeader>
          <DialogDescription className="sr-only">Formulario para confirmar la reserva</DialogDescription>
          <div className="text-sm text-[var(--bs-muted)] -mt-2">
            {activeService?.name} · {selectedDate && prettyDate(selectedDate)} · {slot}
          </div>
          <div className="space-y-3 mt-2">
            <div>
              <Label className="text-xs flex items-center gap-1 mb-1"><User size={12} />Nombre</Label>
              <Input
                data-testid="input-name"
                value={form.client_name}
                onChange={(e) => setForm({ ...form, client_name: e.target.value })}
                className="bg-[var(--bs-bg-2)] border-[var(--bs-line)]"
              />
            </div>
            <div>
              <Label className="text-xs flex items-center gap-1 mb-1"><Phone size={12} />Teléfono</Label>
              <Input
                data-testid="input-phone"
                value={form.client_phone}
                onChange={(e) => setForm({ ...form, client_phone: e.target.value })}
                className="bg-[var(--bs-bg-2)] border-[var(--bs-line)]"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              className="bg-[var(--bs-gold)] text-[var(--bs-bg)] hover:bg-[var(--bs-gold-2)] font-bold w-full"
              onClick={book}
              data-testid="confirm-booking-btn"
            >
              Confirmar reserva
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Success dialog */}
      <Dialog open={!!confirmed} onOpenChange={() => setConfirmed(null)}>
        <DialogContent data-testid="success-dialog" className="bg-[var(--bs-card)] border-[var(--bs-line)] text-[var(--bs-cream)] text-center">
          <div className="flex flex-col items-center py-4">
            <CheckCircle2 size={54} className="text-[var(--bs-gold)] mb-3" />
            <DialogTitle className="display text-3xl mb-1">¡Cita confirmada!</DialogTitle>
            <DialogDescription className="sr-only">Tu cita ha sido confirmada</DialogDescription>
            {confirmed && (
              <p className="text-[var(--bs-muted)]">
                {confirmed.service}<br />
                {prettyDate(confirmed.date)} a las {confirmed.time}
              </p>
            )}
            <Button
              className="mt-5 bg-[var(--bs-gold)] text-[var(--bs-bg)] hover:bg-[var(--bs-gold-2)] font-bold"
              onClick={() => setConfirmed(null)}
              data-testid="success-close-btn"
            >
              Listo
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
