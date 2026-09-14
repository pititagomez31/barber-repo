import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { format, addDays, startOfWeek, addMinutes, parseISO } from "date-fns";
import { es } from "date-fns/locale";
import { Scissors, LogOut, Calendar as CalIcon, Users, Settings, Ban, Plus, Trash2, Edit, X, ChevronLeft, ChevronRight, Phone, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/context/AuthContext";
import { api, formatErr } from "@/lib/api";

const DAY_LABELS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

export default function AdminDashboard() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [tab, setTab] = useState("agenda");

  const handleLogout = () => { logout(); nav("/admin/login"); };

  return (
    <div className="min-h-screen bg-[#14141A] text-neutral-100" data-testid="admin-dashboard">
      <header className="glass border-b border-white/5 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-5 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <Scissors className="h-5 w-5 text-[#D4B77A]" />
            <span className="font-display text-lg">Panel <span className="text-[#D4B77A]">Barbero</span></span>
          </Link>
          <div className="flex items-center gap-3">
            <span className="hidden sm:block text-xs text-neutral-500">{user?.email}</span>
            <Button data-testid="admin-logout" size="sm" variant="outline" onClick={handleLogout} className="border-white/10 bg-transparent hover:bg-white/5">
              <LogOut className="h-4 w-4 mr-1" /> Salir
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-5 py-8">
        <Tabs value={tab} onValueChange={setTab}>
          <div className="overflow-x-auto -mx-5 px-5 pb-1">
            <TabsList className="bg-[#1A1A1E] border border-[#2A2A32] p-1 h-auto w-max min-w-full">
            <TabsTrigger data-testid="tab-agenda" value="agenda" className="data-[state=active]:bg-[#D4B77A] data-[state=active]:text-[#14141A] px-4 py-2">
              <CalIcon className="h-4 w-4 mr-2" /> Agenda
            </TabsTrigger>
            <TabsTrigger data-testid="tab-services" value="services" className="data-[state=active]:bg-[#D4B77A] data-[state=active]:text-[#14141A] px-4 py-2">
              <Scissors className="h-4 w-4 mr-2" /> Servicios
            </TabsTrigger>
            <TabsTrigger data-testid="tab-schedule" value="schedule" className="data-[state=active]:bg-[#D4B77A] data-[state=active]:text-[#14141A] px-4 py-2">
              <Settings className="h-4 w-4 mr-2" /> Horario
            </TabsTrigger>
            <TabsTrigger data-testid="tab-blockers" value="blockers" className="data-[state=active]:bg-[#D4B77A] data-[state=active]:text-[#14141A] px-4 py-2">
              <Ban className="h-4 w-4 mr-2" /> Bloqueos
            </TabsTrigger>
            <TabsTrigger data-testid="tab-clients" value="clients" className="data-[state=active]:bg-[#D4B77A] data-[state=active]:text-[#14141A] px-4 py-2">
              <Users className="h-4 w-4 mr-2" /> Clientes
            </TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="agenda" className="mt-6"><AgendaPanel /></TabsContent>
          <TabsContent value="services" className="mt-6"><ServicesPanel /></TabsContent>
          <TabsContent value="schedule" className="mt-6"><SchedulePanel /></TabsContent>
          <TabsContent value="blockers" className="mt-6"><BlockersPanel /></TabsContent>
          <TabsContent value="clients" className="mt-6"><ClientsPanel /></TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

/* ---------------- Agenda ---------------- */
function AgendaPanel() {
  const [view, setView] = useState("day"); // day | week | month
  const [anchor, setAnchor] = useState(new Date());
  const [appts, setAppts] = useState([]);
  const [forceOpen, setForceOpen] = useState(false);
  const [forceSaving, setForceSaving] = useState(false);
  const [forceServices, setForceServices] = useState([]);
  const [forceForm, setForceForm] = useState({ service_id: "", date: "", start: "", client_name: "", client_phone: "" });

  const range = useMemo(() => {
    if (view === "day") return { from: anchor, to: anchor };
    if (view === "week") {
      const start = startOfWeek(anchor, { weekStartsOn: 1 });
      return { from: start, to: addDays(start, 6) };
    }
    const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
    const last = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0);
    return { from: first, to: last };
  }, [view, anchor]);

  const load = () => {
    api.get(`/appointments?from_date=${format(range.from, "yyyy-MM-dd")}&to_date=${format(range.to, "yyyy-MM-dd")}`)
      .then((r) => setAppts(r.data))
      .catch((e) => toast.error(formatErr(e)));
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [range.from, range.to]);

  const cancel = async (id) => {
    if (!window.confirm("¿Cancelar esta cita?")) return;
    try {
      await api.post(`/appointments/${id}/admin-cancel`);
      toast.success("Cita cancelada");
      load();
    } catch (e) { toast.error(formatErr(e)); }
  };

  const confirmar = async (id) => {
    try {
      await api.put(`/appointments/${id}/confirmar`);
      toast.success("Cita confirmada");
      load();
    } catch (e) { toast.error(formatErr(e)); }
  };

  const recordatorio = async (id) => {
    try {
      const { data } = await api.post(`/appointments/${id}/recordatorio`);
      if (data?.sent) toast.success("Recordatorio enviado por WhatsApp");
      else toast.error("No se pudo enviar (revisa el token de WhatsApp en Railway)");
    } catch (e) { toast.error(formatErr(e)); }
  };

  const openForce = async () => {
    try {
      const { data } = await api.get("/services");
      setForceServices(Array.isArray(data) ? data.filter((s) => s.active) : []);
    } catch (e) { /* si falla, el select saldrá vacío */ }
    setForceForm({ service_id: "", date: format(anchor, "yyyy-MM-dd"), start: "", client_name: "", client_phone: "" });
    setForceOpen(true);
  };

  const submitForce = async () => {
    if (!forceForm.service_id || !forceForm.date || !forceForm.start || !forceForm.client_name.trim() || !forceForm.client_phone.trim())
      return toast.error("Completa servicio, fecha, hora, nombre y teléfono");
    setForceSaving(true);
    try {
      await api.post("/admin/appointments/force", forceForm);
      toast.success("Cita forzada creada y confirmación enviada");
      setForceOpen(false);
      load();
    } catch (e) { toast.error(formatErr(e)); }
    setForceSaving(false);
  };

  const shift = (dir) => {
    if (view === "day") setAnchor(addDays(anchor, dir));
    else if (view === "week") setAnchor(addDays(anchor, dir * 7));
    else setAnchor(new Date(anchor.getFullYear(), anchor.getMonth() + dir, 1));
  };

  const grouped = useMemo(() => {
    const g = {};
    appts.filter(a => a.status !== "cancelled").forEach(a => { (g[a.date] ||= []).push(a); });
    Object.values(g).forEach(list => list.sort((a, b) => a.start.localeCompare(b.start)));
    return g;
  }, [appts]);

  const daysToShow = useMemo(() => {
    if (view === "day") return [format(anchor, "yyyy-MM-dd")];
    if (view === "week") {
      const start = startOfWeek(anchor, { weekStartsOn: 1 });
      return Array.from({ length: 7 }, (_, i) => format(addDays(start, i), "yyyy-MM-dd"));
    }
    const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
    const last = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0);
    return Array.from({ length: last.getDate() }, (_, i) => format(new Date(first.getFullYear(), first.getMonth(), i + 1), "yyyy-MM-dd"));
  }, [view, anchor]);

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3 justify-between mb-6">
        <div className="flex items-center gap-2">
          <Button size="icon" variant="outline" onClick={() => shift(-1)} className="border-white/10 bg-transparent" data-testid="agenda-prev"><ChevronLeft className="h-4 w-4" /></Button>
          <div className="font-display text-2xl tracking-tight" data-testid="agenda-title">
            {view === "day" && format(anchor, "EEEE d 'de' MMMM", { locale: es })}
            {view === "week" && `Semana del ${format(range.from, "d MMM", { locale: es })}`}
            {view === "month" && format(anchor, "MMMM yyyy", { locale: es })}
          </div>
          <Button size="icon" variant="outline" onClick={() => shift(1)} className="border-white/10 bg-transparent" data-testid="agenda-next"><ChevronRight className="h-4 w-4" /></Button>
          <Button size="sm" variant="outline" onClick={() => setAnchor(new Date())} className="border-white/10 bg-transparent ml-2" data-testid="agenda-today">Hoy</Button>
          <Button size="sm" onClick={openForce} className="bg-[#D4B77A] hover:bg-[#C2A366] text-[#14141A] ml-2" data-testid="force-appt-btn"><Plus className="h-4 w-4 mr-1" /> Forzar cita</Button>
        </div>
        <div className="flex gap-1 bg-[#1A1A1E] border border-[#2A2A32] rounded-md p-1">
          {["day", "week", "month"].map((v) => (
            <button key={v} data-testid={`agenda-view-${v}`} onClick={() => setView(v)}
              className={`px-3 py-1.5 text-xs rounded ${view === v ? "bg-[#D4B77A] text-[#14141A]" : "text-neutral-400 hover:text-neutral-200"}`}>
              {v === "day" ? "Día" : v === "week" ? "Semana" : "Mes"}
            </button>
          ))}
        </div>
      </div>

      {daysToShow.length === 0 ? null : (
        <div className={`grid gap-4 ${view === "week" ? "md:grid-cols-7" : view === "month" ? "grid-cols-2 md:grid-cols-4 lg:grid-cols-7" : "grid-cols-1"}`} data-testid="agenda-grid">
          {daysToShow.map((d) => {
            const list = grouped[d] || [];
            return (
              <div key={d} className="bg-[#1A1A1E] border border-[#2A2A32] rounded-lg p-3 min-h-[120px]" data-testid={`agenda-day-${d}`}>
                <p className="text-xs tracking-overline uppercase text-neutral-500 mb-2">{format(parseISO(d), "EEE d MMM", { locale: es })}</p>
                {list.length === 0 && <p className="text-xs text-neutral-600">Sin citas</p>}
                <div className="space-y-2">
                  {list.map((a) => (
                    <div key={a.id} className="bg-[#14141A] border border-[#2A2A32] rounded-md p-2.5 text-xs group hover:border-[#D4B77A]/40" data-testid={`appt-${a.id}`}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[#D4B77A] font-semibold">{a.start} – {a.end}</span>
                        <button onClick={() => cancel(a.id)} className="opacity-0 group-hover:opacity-100 text-neutral-500 hover:text-red-400" data-testid={`cancel-${a.id}`}><X className="h-3 w-3" /></button>
                      </div>
                      <p className="text-neutral-200 font-medium">{a.client_name}</p>
                      {a.booker_name && <p className="text-[10px] text-neutral-500 italic">reservado por {a.booker_name}</p>}
                      <p className="text-neutral-500">{a.service_name}</p>
                      <span className="text-neutral-500 flex items-center gap-1 mt-1"><Phone className="h-3 w-3" />{a.client_phone}</span>
                      <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                        <span data-testid={`estado-${a.id}`} className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${a.confirmado ? "bg-green-500/15 text-green-400" : "bg-yellow-500/15 text-yellow-400"}`}>
                          {a.confirmado ? "Confirmada" : "Pendiente"}
                        </span>
                        {!a.confirmado && (
                          <button data-testid={`confirmar-${a.id}`} onClick={() => confirmar(a.id)} className="text-[10px] px-1.5 py-0.5 rounded border border-[#D4B77A]/40 text-[#D4B77A] hover:bg-[#D4B77A] hover:text-[#14141A]">
                            Confirmar
                          </button>
                        )}
                        <button data-testid={`recordatorio-${a.id}`} onClick={() => recordatorio(a.id)} className="text-[10px] px-1.5 py-0.5 rounded border border-[#25D366]/40 text-[#25D366] hover:bg-[#25D366] hover:text-white">
                          Recordatorio
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <Dialog open={forceOpen} onOpenChange={setForceOpen}>
        <DialogContent className="bg-[#1A1A1E] border-[#2A2A32] text-neutral-100">
          <DialogHeader><DialogTitle className="font-display">Forzar cita manual</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <DialogDescription className="text-xs text-neutral-500">Se crea aunque el horario esté ocupado o fuera de agenda. El cliente recibe la confirmación por WhatsApp.</DialogDescription>
            <div>
              <Label>Servicio</Label>
              <select data-testid="force-service" value={forceForm.service_id} onChange={(e) => setForceForm({ ...forceForm, service_id: e.target.value })} className="w-full mt-1 h-10 px-3 rounded-md bg-[#14141A] border border-[#2A2A32] text-sm">
                <option value="">Elige servicio…</option>
                {forceServices.map((s) => <option key={s.id} value={s.id}>{s.name} · {s.duration_min} min</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Fecha</Label><Input data-testid="force-date" type="date" value={forceForm.date} onChange={(e) => setForceForm({ ...forceForm, date: e.target.value })} className="bg-[#14141A] border-[#2A2A32] mt-1" /></div>
              <div><Label>Hora</Label><Input data-testid="force-start" type="time" value={forceForm.start} onChange={(e) => setForceForm({ ...forceForm, start: e.target.value })} className="bg-[#14141A] border-[#2A2A32] mt-1" /></div>
            </div>
            <div><Label>Nombre del cliente</Label><Input data-testid="force-name" value={forceForm.client_name} onChange={(e) => setForceForm({ ...forceForm, client_name: e.target.value })} className="bg-[#14141A] border-[#2A2A32] mt-1" /></div>
            <div><Label>Teléfono (WhatsApp)</Label><Input data-testid="force-phone" value={forceForm.client_phone} onChange={(e) => setForceForm({ ...forceForm, client_phone: e.target.value })} className="bg-[#14141A] border-[#2A2A32] mt-1" placeholder="346..." /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setForceOpen(false)} className="border-white/10 bg-transparent">Cancelar</Button>
            <Button onClick={submitForce} disabled={forceSaving} data-testid="force-submit" className="bg-[#D4B77A] hover:bg-[#C2A366] text-[#14141A]">{forceSaving ? "Guardando…" : "Forzar cita"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ---------------- Services ---------------- */
function ServicesPanel() {
  const [items, setItems] = useState([]);
  const [editing, setEditing] = useState(null);
  const empty = { name: "", description: "", price_eur: 0, duration_min: 30, active: true };

  const load = () => api.get("/services?all=true").then((r) => setItems(r.data));
  useEffect(() => { load(); }, []);

  const save = async () => {
    try {
      if (editing.id) await api.put(`/services/${editing.id}`, editing);
      else await api.post("/services", editing);
      toast.success("Guardado");
      setEditing(null); load();
    } catch (e) { toast.error(formatErr(e)); }
  };
  const remove = async (id) => {
    if (!window.confirm("¿Eliminar servicio?")) return;
    await api.delete(`/services/${id}`);
    toast.success("Eliminado"); load();
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="font-display text-2xl tracking-tight">Servicios</h2>
        <Button data-testid="add-service-btn" onClick={() => setEditing({ ...empty })} className="bg-[#D4B77A] hover:bg-[#C2A366] text-[#14141A]"><Plus className="h-4 w-4 mr-1" /> Nuevo servicio</Button>
      </div>
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {items.map((s) => (
          <Card key={s.id} className="bg-[#1A1A1E] border-[#2A2A32]" data-testid={`svc-${s.id}`}>
            <CardContent className="p-5">
              <div className="flex justify-between mb-3">
                <p className="font-display text-lg">{s.name}</p>
                <span className="text-[#D4B77A] font-semibold">{s.price_eur}€</span>
              </div>
              <p className="text-sm text-neutral-400 mb-3">{s.description}</p>
              <div className="flex items-center gap-3 text-xs text-neutral-500 mb-4">
                <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{s.duration_min} min</span>
                <Badge variant={s.active ? "default" : "secondary"} className={s.active ? "bg-[#D4B77A]/15 text-[#D4B77A] hover:bg-[#D4B77A]/15" : ""}>
                  {s.active ? "Activo" : "Inactivo"}
                </Badge>
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => setEditing({ ...s })} className="flex-1 border-white/10 bg-transparent" data-testid={`edit-svc-${s.id}`}><Edit className="h-3 w-3 mr-1" /> Editar</Button>
                <Button size="sm" variant="outline" onClick={() => remove(s.id)} className="border-red-900/40 bg-transparent text-red-400 hover:bg-red-950/30" data-testid={`del-svc-${s.id}`}><Trash2 className="h-3 w-3" /></Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="bg-[#1A1A1E] border-[#2A2A32] text-neutral-100">
          <DialogHeader><DialogTitle className="font-display">{editing?.id ? "Editar" : "Nuevo"} servicio</DialogTitle></DialogHeader>
          {editing && (
            <div className="space-y-4">
              <div><Label>Nombre</Label><Input data-testid="svc-form-name" value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} className="bg-[#14141A] border-[#2A2A32] mt-1" /></div>
              <div><Label>Descripción</Label><Textarea data-testid="svc-form-desc" value={editing.description} onChange={(e) => setEditing({ ...editing, description: e.target.value })} className="bg-[#14141A] border-[#2A2A32] mt-1" /></div>
              <div className="grid grid-cols-2 gap-3">
                <div><Label>Precio (€)</Label><Input data-testid="svc-form-price" type="number" step="0.5" value={editing.price_eur} onChange={(e) => setEditing({ ...editing, price_eur: parseFloat(e.target.value) || 0 })} className="bg-[#14141A] border-[#2A2A32] mt-1" /></div>
                <div><Label>Duración (min)</Label><Input data-testid="svc-form-dur" type="number" step="5" value={editing.duration_min} onChange={(e) => setEditing({ ...editing, duration_min: parseInt(e.target.value) || 0 })} className="bg-[#14141A] border-[#2A2A32] mt-1" /></div>
              </div>
              <label className="flex items-center gap-3"><Switch data-testid="svc-form-active" checked={editing.active} onCheckedChange={(v) => setEditing({ ...editing, active: v })} /> <span className="text-sm">Activo</span></label>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditing(null)} className="border-white/10 bg-transparent">Cancelar</Button>
            <Button onClick={save} data-testid="svc-form-save" className="bg-[#D4B77A] hover:bg-[#C2A366] text-[#14141A]">Guardar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ---------------- Schedule ---------------- */
function SchedulePanel() {
  const [days, setDays] = useState(null);

  // Excepciones por fecha
  const [month, setMonth] = useState(() => { const n = new Date(); return new Date(n.getFullYear(), n.getMonth(), 1); });
  const [overrides, setOverrides] = useState([]);
  const [dlgDate, setDlgDate] = useState(null);
  const [ovr, setOvr] = useState({ enabled: true, start: "10:00", end: "20:00", reason: "" });
  const [ovrExists, setOvrExists] = useState(false);
  const [ovrSaving, setOvrSaving] = useState(false);

  useEffect(() => { api.get("/working-hours").then((r) => setDays(r.data.days)); }, []);

  const loadOverrides = () => {
    const from = format(month, "yyyy-MM-dd");
    const to = format(new Date(month.getFullYear(), month.getMonth() + 1, 0), "yyyy-MM-dd");
    api.get(`/schedule-overrides?from_date=${from}&to_date=${to}`)
      .then((r) => setOverrides(Array.isArray(r.data) ? r.data : []))
      .catch((e) => toast.error(formatErr(e)));
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadOverrides(); }, [month]);

  const overrideMap = useMemo(() => {
    const m = {};
    overrides.forEach((o) => { m[o.date] = o; });
    return m;
  }, [overrides]);

  const save = async () => {
    try {
      await api.put("/working-hours", { days });
      toast.success("Horario base guardado");
    } catch (e) { toast.error(formatErr(e)); }
  };

  const openDay = async (dateStr) => {
    setDlgDate(dateStr);
    const existing = overrideMap[dateStr];
    if (existing) {
      setOvr({ enabled: existing.enabled, start: existing.start, end: existing.end, reason: existing.reason || "" });
      setOvrExists(true);
    } else {
      const wd = String((parseISO(dateStr).getDay() + 6) % 7);
      const base = (days && days[wd]) || { start: "10:00", end: "20:00" };
      setOvr({ enabled: true, start: base.start, end: base.end, reason: "" });
      setOvrExists(false);
    }
  };

  const saveOverride = async () => {
    if (ovr.enabled && ovr.start >= ovr.end) return toast.error("La hora de fin debe ser posterior a la de inicio");
    setOvrSaving(true);
    try {
      await api.post("/schedule-overrides", { date: dlgDate, ...ovr });
      toast.success("Excepción guardada · solo afecta a ese día");
      setDlgDate(null);
      loadOverrides();
    } catch (e) { toast.error(formatErr(e)); }
    setOvrSaving(false);
  };

  const deleteOverride = async () => {
    setOvrSaving(true);
    try {
      await api.delete(`/schedule-overrides/${dlgDate}`);
      toast.success("Excepción eliminada · vuelve al horario base");
      setDlgDate(null);
      loadOverrides();
    } catch (e) { toast.error(formatErr(e)); }
    setOvrSaving(false);
  };

  // Grid del mes (Lun a Dom)
  const monthCells = useMemo(() => {
    const first = new Date(month.getFullYear(), month.getMonth(), 1);
    const lead = (first.getDay() + 6) % 7; // 0 = Lun
    const total = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
    const cells = [];
    for (let i = 0; i < lead; i++) cells.push(null);
    for (let d = 1; d <= total; d++) cells.push(format(new Date(month.getFullYear(), month.getMonth(), d), "yyyy-MM-dd"));
    return cells;
  }, [month]);

  const todayStr = format(new Date(), "yyyy-MM-dd");

  if (!days) return <p className="text-neutral-500">Cargando…</p>;

  return (
    <div className="space-y-12">
      {/* Sección A: Horario semanal base */}
      <section data-testid="base-schedule-section">
        <h2 className="font-display text-2xl tracking-tight mb-2">Horario semanal base</h2>
        <p className="text-sm text-neutral-400 mb-6 max-w-2xl">
          Este es tu horario habitual. Para cambiar un día concreto (por ejemplo un miércoles suelto), usa la sección <span className="text-[#D4B77A]">Excepciones por fecha</span> de abajo.
        </p>
        <div className="space-y-2 max-w-2xl">
          {DAY_LABELS.map((lbl, idx) => {
            const key = String(idx);
            const d = days[key];
            return (
              <div key={key} className="flex items-center gap-4 bg-[#1A1A1E] border border-[#2A2A32] rounded-md p-4" data-testid={`sched-row-${idx}`}>
                <div className="w-16 font-medium">{lbl}</div>
                <Switch data-testid={`sched-enabled-${idx}`} checked={d.enabled} onCheckedChange={(v) => setDays({ ...days, [key]: { ...d, enabled: v } })} />
                <Input data-testid={`sched-start-${idx}`} type="time" value={d.start} onChange={(e) => setDays({ ...days, [key]: { ...d, start: e.target.value } })} disabled={!d.enabled} className="w-32 bg-[#14141A] border-[#2A2A32]" />
                <span className="text-neutral-500">–</span>
                <Input data-testid={`sched-end-${idx}`} type="time" value={d.end} onChange={(e) => setDays({ ...days, [key]: { ...d, end: e.target.value } })} disabled={!d.enabled} className="w-32 bg-[#14141A] border-[#2A2A32]" />
              </div>
            );
          })}
        </div>
        <Button data-testid="sched-save" onClick={save} className="mt-6 bg-[#D4B77A] hover:bg-[#C2A366] text-[#14141A]">Guardar horario base</Button>
      </section>

      {/* Sección B: Excepciones por fecha */}
      <section data-testid="overrides-section">
        <h2 className="font-display text-2xl tracking-tight mb-2">Excepciones por fecha</h2>
        <p className="text-sm text-neutral-400 mb-4 max-w-2xl">
          Cambia el horario de un día concreto sin tocar el resto. Haz clic en un día del calendario.
          Los días con <span className="inline-block h-2 w-2 rounded-full bg-[#D4B77A] align-middle mx-1" /> punto dorado ya tienen una excepción.
        </p>

        <div className="max-w-md bg-[#1A1A1E] border border-[#2A2A32] rounded-lg p-4">
          <div className="flex items-center justify-between mb-4">
            <Button size="icon" variant="outline" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))} className="border-white/10 bg-transparent h-8 w-8" data-testid="sched-ovr-prev"><ChevronLeft className="h-4 w-4" /></Button>
            <span className="font-display text-lg capitalize" data-testid="sched-ovr-title">{format(month, "MMMM yyyy", { locale: es })}</span>
            <Button size="icon" variant="outline" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))} className="border-white/10 bg-transparent h-8 w-8" data-testid="sched-ovr-next"><ChevronRight className="h-4 w-4" /></Button>
          </div>
          <div className="grid grid-cols-7 gap-1.5 mb-1.5">
            {DAY_LABELS.map((l) => <div key={l} className="text-center text-[10px] uppercase tracking-wide text-neutral-500 py-1">{l}</div>)}
          </div>
          <div className="grid grid-cols-7 gap-1.5">
            {monthCells.map((ds, i) => {
              if (!ds) return <div key={`e${i}`} />;
              const o = overrideMap[ds];
              const isToday = ds === todayStr;
              const dayNum = parseInt(ds.slice(-2), 10);
              return (
                <button
                  key={ds}
                  data-testid={`sched-ovr-day-${ds}`}
                  onClick={() => openDay(ds)}
                  className={`relative aspect-square rounded-md text-sm font-medium border transition-colors flex items-center justify-center
                    ${o ? (o.enabled ? "border-[#D4B77A]/60 bg-[#D4B77A]/10 text-[#D4B77A]" : "border-red-500/50 bg-red-500/10 text-red-400")
                        : "border-[#2A2A32] bg-[#14141A] text-neutral-300 hover:border-[#D4B77A]/40"}
                    ${isToday ? "ring-1 ring-[#D4B77A]/70" : ""}`}
                >
                  {dayNum}
                  {o && <span className={`absolute bottom-1 h-1.5 w-1.5 rounded-full ${o.enabled ? "bg-[#D4B77A]" : "bg-red-400"}`} />}
                </button>
              );
            })}
          </div>
          <div className="flex items-center gap-4 mt-4 text-[11px] text-neutral-500">
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-[#D4B77A]" /> Horario especial</span>
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-red-400" /> Cerrado</span>
          </div>
        </div>
      </section>

      {/* Dialog excepción */}
      <Dialog open={!!dlgDate} onOpenChange={(o) => !o && setDlgDate(null)}>
        <DialogContent className="bg-[#1A1A1E] border-[#2A2A32] text-neutral-100">
          <DialogHeader>
            <DialogTitle className="font-display capitalize">
              {dlgDate && format(parseISO(dlgDate), "EEEE d 'de' MMMM yyyy", { locale: es })}
            </DialogTitle>
          </DialogHeader>
          <DialogDescription className="text-xs text-neutral-500 -mt-1">
            Esta configuración solo afecta a este día. El resto de {dlgDate && format(parseISO(dlgDate), "EEEE", { locale: es })}s siguen con el horario base.
          </DialogDescription>
          <div className="space-y-4">
            <label className="flex items-center gap-3">
              <Switch data-testid="ovr-enabled" checked={ovr.enabled} onCheckedChange={(v) => setOvr({ ...ovr, enabled: v })} />
              <span className="text-sm">{ovr.enabled ? "Trabajas este día" : "Cerrado este día"}</span>
            </label>
            {ovr.enabled && (
              <div className="grid grid-cols-2 gap-3">
                <div><Label>Hora inicio</Label><Input data-testid="ovr-start" type="time" value={ovr.start} onChange={(e) => setOvr({ ...ovr, start: e.target.value })} className="bg-[#14141A] border-[#2A2A32] mt-1" /></div>
                <div><Label>Hora fin</Label><Input data-testid="ovr-end" type="time" value={ovr.end} onChange={(e) => setOvr({ ...ovr, end: e.target.value })} className="bg-[#14141A] border-[#2A2A32] mt-1" /></div>
              </div>
            )}
            <div><Label>Motivo (opcional)</Label><Input data-testid="ovr-reason" value={ovr.reason} onChange={(e) => setOvr({ ...ovr, reason: e.target.value })} className="bg-[#14141A] border-[#2A2A32] mt-1" placeholder="Ej: Empiezo antes, evento…" /></div>
          </div>
          <DialogFooter className="gap-2">
            {ovrExists && (
              <Button variant="outline" onClick={deleteOverride} disabled={ovrSaving} data-testid="ovr-delete" className="border-red-900/40 bg-transparent text-red-400 hover:bg-red-950/30 mr-auto">
                <Trash2 className="h-4 w-4 mr-1" /> Eliminar (volver al base)
              </Button>
            )}
            <Button variant="outline" onClick={() => setDlgDate(null)} className="border-white/10 bg-transparent">Cancelar</Button>
            <Button onClick={saveOverride} disabled={ovrSaving} data-testid="ovr-save" className="bg-[#D4B77A] hover:bg-[#C2A366] text-[#14141A]">{ovrSaving ? "Guardando…" : "Guardar excepción"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ---------------- Blockers ---------------- */
function BlockersPanel() {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ date: "", start: "", end: "", reason: "", fullDay: true });
  const load = () => api.get("/blockers").then((r) => setItems(Array.isArray(r.data) ? r.data : [])).catch((e) => toast.error(formatErr(e)));
  useEffect(() => { load(); }, []);

  const add = async () => {
    if (!form.date) return toast.error("Elige una fecha");
    const payload = { date: form.date, reason: form.reason, start: form.fullDay ? null : form.start, end: form.fullDay ? null : form.end };
    try {
      await api.post("/blockers", payload);
      toast.success("Bloqueo añadido");
      setForm({ date: "", start: "", end: "", reason: "", fullDay: true });
      load();
    } catch (e) { toast.error(formatErr(e)); }
  };
  const remove = async (id) => { await api.delete(`/blockers/${id}`); load(); };

  return (
    <div>
      <h2 className="font-display text-2xl tracking-tight mb-6">Bloqueos y vacaciones</h2>
      <div className="grid md:grid-cols-2 gap-8">
        <Card className="bg-[#1A1A1E] border-[#2A2A32]">
          <CardContent className="p-6 space-y-4">
            <p className="tracking-overline uppercase text-xs text-[#D4B77A]">Nuevo bloqueo</p>
            <div><Label>Fecha</Label><Input data-testid="blk-date" type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} className="bg-[#14141A] border-[#2A2A32] mt-1" /></div>
            <label className="flex items-center gap-3"><Switch data-testid="blk-fullday" checked={form.fullDay} onCheckedChange={(v) => setForm({ ...form, fullDay: v })} /> <span className="text-sm">Todo el día</span></label>
            {!form.fullDay && (
              <div className="grid grid-cols-2 gap-3">
                <div><Label>Desde</Label><Input data-testid="blk-start" type="time" value={form.start} onChange={(e) => setForm({ ...form, start: e.target.value })} className="bg-[#14141A] border-[#2A2A32] mt-1" /></div>
                <div><Label>Hasta</Label><Input data-testid="blk-end" type="time" value={form.end} onChange={(e) => setForm({ ...form, end: e.target.value })} className="bg-[#14141A] border-[#2A2A32] mt-1" /></div>
              </div>
            )}
            <div><Label>Motivo (opcional)</Label><Input data-testid="blk-reason" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} className="bg-[#14141A] border-[#2A2A32] mt-1" placeholder="Vacaciones, personal…" /></div>
            <Button data-testid="blk-add" onClick={add} className="w-full bg-[#D4B77A] hover:bg-[#C2A366] text-[#14141A]">Añadir bloqueo</Button>
          </CardContent>
        </Card>

        <div className="space-y-2">
          <p className="tracking-overline uppercase text-xs text-neutral-500 mb-3">Existentes</p>
          {items.length === 0 && <p className="text-neutral-600 text-sm">Ninguno.</p>}
          {items.map((b) => (
            <div key={b.id} className="flex items-center justify-between bg-[#1A1A1E] border border-[#2A2A32] rounded-md p-3" data-testid={`blk-item-${b.id}`}>
              <div>
                <p className="text-sm text-[#D4B77A] font-semibold">{b.date}</p>
                <p className="text-xs text-neutral-400">{b.start && b.end ? `${b.start} – ${b.end}` : "Todo el día"} {b.reason && `· ${b.reason}`}</p>
              </div>
              <Button size="icon" variant="outline" onClick={() => remove(b.id)} className="border-red-900/40 bg-transparent text-red-400 h-8 w-8" data-testid={`blk-del-${b.id}`}><Trash2 className="h-3 w-3" /></Button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ---------------- Clients ---------------- */
function ClientsPanel() {
  const [items, setItems] = useState([]);
  const [detail, setDetail] = useState(null);
  useEffect(() => { api.get("/clients").then((r) => setItems(r.data)).catch(() => {}); }, []);
  const openDetail = async (c) => {
    try {
      const { data } = await api.get(`/clients/${c.id}/appointments`);
      setDetail(data);
    } catch (e) { toast.error(formatErr(e)); }
  };
  const removeClient = async (c) => {
    if (!window.confirm(`¿Eliminar a ${c.name}? Esta acción no se puede deshacer.`)) return;
    try {
      await api.delete(`/clients/${c.id}`);
      setItems((prev) => prev.filter((x) => x.id !== c.id));
      toast.success("Cliente eliminado");
    } catch (e) { toast.error(formatErr(e)); }
  };
  return (
    <div>
      <h2 className="font-display text-2xl tracking-tight mb-6">Clientes ({items.length})</h2>
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
        {items.map((c) => (
          <div key={c.id} className="relative text-left bg-[#1A1A1E] border border-[#2A2A32] rounded-md p-4 hover:border-[#D4B77A]/40" data-testid={`client-${c.id}`}>
            <button onClick={() => openDetail(c)} className="w-full text-left">
              <p className="font-medium">{c.name} {c.nickname && <span className="text-neutral-500 text-sm">&ldquo;{c.nickname}&rdquo;</span>}</p>
              <p className="text-xs text-neutral-500 mt-1">{c.phone}</p>
              <p className="text-xs text-[#D4B77A] mt-2">{c.appointments_count} cita{c.appointments_count === 1 ? "" : "s"}</p>
            </button>
            <button data-testid={`client-delete-${c.id}`} onClick={() => removeClient(c)} className="absolute top-3 right-3 text-[10px] px-2 py-1 rounded border border-red-400/50 text-red-400 hover:bg-red-400 hover:text-[#14141A] transition-colors">
              Eliminar
            </button>
          </div>
        ))}
        {items.length === 0 && <p className="text-neutral-600 text-sm">Aún no hay clientes.</p>}
      </div>
      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="bg-[#1A1A1E] border-[#2A2A32] text-neutral-100 max-w-lg">
          <DialogHeader><DialogTitle className="font-display">{detail?.client?.name}</DialogTitle></DialogHeader>
          {detail && (
            <div className="space-y-2 max-h-[400px] overflow-auto">
              <p className="text-sm text-neutral-500">{detail.client.phone}</p>
              <p className="tracking-overline uppercase text-xs text-neutral-500 mt-4">Historial</p>
              {detail.appointments.length === 0 && <p className="text-sm text-neutral-500">Sin citas.</p>}
              {detail.appointments.map((a) => (
                <div key={a.id} className="bg-[#14141A] border border-[#2A2A32] rounded p-3 text-sm">
                  <div className="flex justify-between">
                    <span className="text-[#D4B77A]">{a.date} {a.start}</span>
                    <span className={a.status === "cancelled" ? "text-red-400" : "text-neutral-400"}>{a.status}</span>
                  </div>
                  <p className="text-neutral-400">{a.service_name} · {a.price_eur}€</p>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
