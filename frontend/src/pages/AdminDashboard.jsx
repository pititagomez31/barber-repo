import { useEffect, useState } from "react";
import { api, WEEKDAYS, fmtDate, prettyDate } from "@/lib/api";
import MonthCalendar from "@/components/MonthCalendar";
import { toast } from "sonner";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { CalendarDays, Clock, Trash2, Phone, Star, Info } from "lucide-react";

/* ------------------------------------------------------------------ */
/* Agenda                                                             */
/* ------------------------------------------------------------------ */
function AgendaPanel() {
  const [anchor, setAnchor] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState(fmtDate(new Date()));
  const [appts, setAppts] = useState([]);

  const load = () => {
    if (!selectedDate) return;
    api.get("/appointments", { params: { date: selectedDate } }).then((r) => setAppts(r.data));
  };
  useEffect(load, [selectedDate]);

  const remove = async (id) => {
    await api.delete(`/appointments/${id}`);
    toast.success("Cita eliminada");
    load();
  };

  return (
    <div className="grid lg:grid-cols-2 gap-8">
      <div className="p-5 rounded-2xl border border-[var(--bs-line)] bg-[var(--bs-card)]">
        <MonthCalendar anchor={anchor} onAnchorChange={setAnchor} selected={selectedDate} onSelect={setSelectedDate} />
      </div>
      <div>
        <h3 className="display text-2xl mb-1">{prettyDate(selectedDate)}</h3>
        <p className="text-sm text-[var(--bs-muted)] mb-4">{appts.length} cita(s)</p>
        <div className="space-y-3" data-testid="agenda-list">
          {appts.length === 0 && (
            <p className="text-[var(--bs-muted)]" data-testid="agenda-empty">Sin citas este día.</p>
          )}
          {appts.map((a) => (
            <div
              key={a.id}
              data-testid={`appt-${a.id}`}
              className="flex items-center justify-between p-4 rounded-xl border border-[var(--bs-line)] bg-[var(--bs-bg-2)]"
            >
              <div>
                <div className="flex items-center gap-2 font-bold">
                  <span className="text-[var(--bs-gold)]">{a.time}</span>
                  {a.service_name}
                </div>
                <div className="text-sm text-[var(--bs-muted)] flex items-center gap-3 mt-1">
                  <span>{a.client_name}</span>
                  <span className="flex items-center gap-1"><Phone size={12} />{a.client_phone}</span>
                </div>
              </div>
              <button
                onClick={() => remove(a.id)}
                data-testid={`delete-appt-${a.id}`}
                className="p-2 rounded-lg hover:bg-[#2a1717] text-[var(--bs-muted)] hover:text-red-400 transition-colors"
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Schedule (base weekly + date overrides)                            */
/* ------------------------------------------------------------------ */
function SchedulePanel() {
  const [days, setDays] = useState(null);
  const [saving, setSaving] = useState(false);

  // overrides
  const [anchor, setAnchor] = useState(new Date());
  const [overrides, setOverrides] = useState([]);
  const [dialogDate, setDialogDate] = useState(null);
  const [ov, setOv] = useState({ enabled: true, start: "10:00", end: "20:00", reason: "" });
  const [existing, setExisting] = useState(false);

  const loadBase = () => api.get("/working-hours").then((r) => setDays(r.data.days));

  const loadOverrides = () => {
    const y = anchor.getFullYear();
    const m = anchor.getMonth();
    const from = fmtDate(new Date(y, m, 1));
    const to = fmtDate(new Date(y, m + 1, 0));
    api.get("/schedule-overrides", { params: { from_date: from, to_date: to } })
      .then((r) => setOverrides(r.data));
  };

  useEffect(() => { loadBase(); }, []);
  useEffect(() => { loadOverrides(); }, [anchor]);

  const saveBase = async () => {
    setSaving(true);
    try {
      await api.put("/working-hours", { days });
      toast.success("Horario base guardado");
    } finally {
      setSaving(false);
    }
  };

  const updateDay = (key, patch) =>
    setDays({ ...days, [key]: { ...days[key], ...patch } });

  const openDate = async (ds) => {
    setDialogDate(ds);
    try {
      const r = await api.get(`/schedule-overrides/${ds}`);
      setOv({ enabled: r.data.enabled, start: r.data.start, end: r.data.end, reason: r.data.reason || "" });
      setExisting(true);
    } catch {
      setOv({ enabled: true, start: "10:00", end: "20:00", reason: "" });
      setExisting(false);
    }
  };

  const saveOverride = async () => {
    await api.post("/schedule-overrides", { date: dialogDate, ...ov });
    toast.success("Excepción guardada");
    setDialogDate(null);
    loadOverrides();
  };

  const deleteOverride = async () => {
    await api.delete(`/schedule-overrides/${dialogDate}`);
    toast.success("Excepción eliminada · vuelve al horario base");
    setDialogDate(null);
    loadOverrides();
  };

  const markedDates = new Set(overrides.map((o) => o.date));
  const offDates = new Set(overrides.filter((o) => !o.enabled).map((o) => o.date));

  if (!days) return <p className="text-[var(--bs-muted)]">Cargando…</p>;

  return (
    <div className="space-y-10">
      {/* Section A */}
      <section data-testid="base-schedule-section">
        <h3 className="display text-2xl">Horario semanal base</h3>
        <p className="text-sm text-[var(--bs-muted)] flex items-center gap-2 mt-1 mb-5">
          <Info size={14} className="text-[var(--bs-gold)]" />
          Este es tu horario habitual. Para cambiar un día concreto, usa la sección de abajo.
        </p>
        <div className="space-y-2">
          {WEEKDAYS.map((w) => {
            const cfg = days[w.key];
            return (
              <div
                key={w.key}
                data-testid={`base-day-${w.key}`}
                className="flex flex-wrap items-center gap-4 p-3 rounded-xl border border-[var(--bs-line)] bg-[var(--bs-card)]"
              >
                <div className="w-28 font-bold">{w.label}</div>
                <Switch
                  data-testid={`base-switch-${w.key}`}
                  checked={cfg.enabled}
                  onCheckedChange={(v) => updateDay(w.key, { enabled: v })}
                />
                <span className="text-sm text-[var(--bs-muted)] w-16">
                  {cfg.enabled ? "Abierto" : "Cerrado"}
                </span>
                <Input
                  type="time"
                  disabled={!cfg.enabled}
                  data-testid={`base-start-${w.key}`}
                  value={cfg.start}
                  onChange={(e) => updateDay(w.key, { start: e.target.value })}
                  className="w-32 bg-[var(--bs-bg-2)] border-[var(--bs-line)]"
                />
                <span className="text-[var(--bs-muted)]">—</span>
                <Input
                  type="time"
                  disabled={!cfg.enabled}
                  data-testid={`base-end-${w.key}`}
                  value={cfg.end}
                  onChange={(e) => updateDay(w.key, { end: e.target.value })}
                  className="w-32 bg-[var(--bs-bg-2)] border-[var(--bs-line)]"
                />
              </div>
            );
          })}
        </div>
        <Button
          className="mt-4 bg-[var(--bs-gold)] text-[var(--bs-bg)] hover:bg-[var(--bs-gold-2)] font-bold"
          onClick={saveBase}
          disabled={saving}
          data-testid="save-base-btn"
        >
          Guardar horario base
        </Button>
      </section>

      {/* Section B */}
      <section data-testid="overrides-section">
        <h3 className="display text-2xl">Excepciones por fecha</h3>
        <p className="text-sm text-[var(--bs-muted)] flex items-center gap-2 mt-1 mb-5">
          <Star size={14} className="text-[var(--bs-gold)]" />
          Haz clic en un día para cambiar solo esa fecha. Los días con punto dorado ya tienen excepción.
        </p>
        <div className="max-w-md p-5 rounded-2xl border border-[var(--bs-line)] bg-[var(--bs-card)]">
          <MonthCalendar
            anchor={anchor}
            onAnchorChange={setAnchor}
            selected={null}
            onSelect={openDate}
            markedDates={markedDates}
            offDates={offDates}
          />
        </div>
      </section>

      {/* Override dialog */}
      <Dialog open={!!dialogDate} onOpenChange={(o) => !o && setDialogDate(null)}>
        <DialogContent data-testid="override-dialog" className="bg-[var(--bs-card)] border-[var(--bs-line)] text-[var(--bs-cream)]">
          <DialogHeader>
            <DialogTitle className="display text-2xl">
              {dialogDate && prettyDate(dialogDate)}
            </DialogTitle>
          </DialogHeader>
          <DialogDescription className="sr-only">Configura el horario de esta fecha específica</DialogDescription>
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <Switch
                data-testid="override-enabled"
                checked={ov.enabled}
                onCheckedChange={(v) => setOv({ ...ov, enabled: v })}
              />
              <span className="font-semibold">
                {ov.enabled ? "Trabajas este día" : "Cerrado este día"}
              </span>
            </div>
            {ov.enabled && (
              <div className="flex items-center gap-3">
                <div>
                  <Label className="text-xs mb-1 block">Inicio</Label>
                  <Input
                    type="time"
                    data-testid="override-start"
                    value={ov.start}
                    onChange={(e) => setOv({ ...ov, start: e.target.value })}
                    className="w-32 bg-[var(--bs-bg-2)] border-[var(--bs-line)]"
                  />
                </div>
                <span className="text-[var(--bs-muted)] mt-5">—</span>
                <div>
                  <Label className="text-xs mb-1 block">Fin</Label>
                  <Input
                    type="time"
                    data-testid="override-end"
                    value={ov.end}
                    onChange={(e) => setOv({ ...ov, end: e.target.value })}
                    className="w-32 bg-[var(--bs-bg-2)] border-[var(--bs-line)]"
                  />
                </div>
              </div>
            )}
            <div>
              <Label className="text-xs mb-1 block">Motivo (opcional)</Label>
              <Input
                data-testid="override-reason"
                placeholder="Ej: Empiezo antes"
                value={ov.reason}
                onChange={(e) => setOv({ ...ov, reason: e.target.value })}
                className="bg-[var(--bs-bg-2)] border-[var(--bs-line)]"
              />
            </div>
          </div>
          <DialogFooter className="flex-col sm:flex-row gap-2">
            {existing && (
              <Button
                variant="outline"
                onClick={deleteOverride}
                data-testid="delete-override-btn"
                className="border-red-500/40 text-red-400 hover:bg-[#2a1717] hover:text-red-300 w-full sm:w-auto"
              >
                <Trash2 size={15} className="mr-1" /> Eliminar (volver al base)
              </Button>
            )}
            <Button
              onClick={saveOverride}
              data-testid="save-override-btn"
              className="bg-[var(--bs-gold)] text-[var(--bs-bg)] hover:bg-[var(--bs-gold-2)] font-bold w-full sm:w-auto"
            >
              Guardar excepción
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ------------------------------------------------------------------ */
export default function AdminDashboard() {
  return (
    <div className="max-w-5xl mx-auto px-5 py-10">
      <div className="mb-8">
        <div className="eyebrow">PANEL DEL BARBERO</div>
        <h1 className="display text-5xl mt-2">Tu día a día</h1>
      </div>
      <Tabs defaultValue="agenda">
        <TabsList className="bg-[var(--bs-card)] border border-[var(--bs-line)]">
          <TabsTrigger value="agenda" data-testid="tab-agenda" className="data-[state=active]:bg-[var(--bs-gold)] data-[state=active]:text-[var(--bs-bg)]">
            <CalendarDays size={15} className="mr-1" /> Agenda
          </TabsTrigger>
          <TabsTrigger value="horario" data-testid="tab-horario" className="data-[state=active]:bg-[var(--bs-gold)] data-[state=active]:text-[var(--bs-bg)]">
            <Clock size={15} className="mr-1" /> Horario
          </TabsTrigger>
        </TabsList>
        <TabsContent value="agenda" className="mt-6">
          <AgendaPanel />
        </TabsContent>
        <TabsContent value="horario" className="mt-6">
          <SchedulePanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}
