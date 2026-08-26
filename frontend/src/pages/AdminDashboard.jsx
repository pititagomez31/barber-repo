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
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
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
          <TabsList className="bg-[#1A1A1E] border border-[#2A2A32] p-1 h-auto">
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
  useEffect(load, [range.from, range.to]);

  const cancel = async (id) => {
    if (!window.confirm("¿Cancelar esta cita?")) return;
    try {
      await api.post(`/appointments/${id}/admin-cancel`);
      toast.success("Cita cancelada");
      load();
    } catch (e) { toast.error(formatErr(e)); }
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
                      <a href={`tel:${a.client_phone}`} className="text-neutral-500 hover:text-[#D4B77A] flex items-center gap-1 mt-1"><Phone className="h-3 w-3" />{a.client_phone}</a>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
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
  useEffect(() => { api.get("/working-hours").then((r) => setDays(r.data.days)); }, []);
  const save = async () => {
    try {
      await api.put("/working-hours", { days });
      toast.success("Horario guardado");
    } catch (e) { toast.error(formatErr(e)); }
  };
  if (!days) return <p className="text-neutral-500">Cargando…</p>;
  return (
    <div>
      <h2 className="font-display text-2xl tracking-tight mb-6">Horario laboral</h2>
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
      <Button data-testid="sched-save" onClick={save} className="mt-6 bg-[#D4B77A] hover:bg-[#C2A366] text-[#14141A]">Guardar horario</Button>
    </div>
  );
}

/* ---------------- Blockers ---------------- */
function BlockersPanel() {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ date: "", start: "", end: "", reason: "", fullDay: true });
  const load = () => api.get("/blockers").then((r) => setItems(r.data));
  useEffect(load, []);

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
  return (
    <div>
      <h2 className="font-display text-2xl tracking-tight mb-6">Clientes ({items.length})</h2>
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
        {items.map((c) => (
          <button key={c.id} onClick={() => openDetail(c)} className="text-left bg-[#1A1A1E] border border-[#2A2A32] rounded-md p-4 hover:border-[#D4B77A]/40" data-testid={`client-${c.id}`}>
            <p className="font-medium">{c.name} {c.nickname && <span className="text-neutral-500 text-sm">&ldquo;{c.nickname}&rdquo;</span>}</p>
            <p className="text-xs text-neutral-500 mt-1">{c.phone}</p>
            <p className="text-xs text-[#D4B77A] mt-2">{c.appointments_count} cita{c.appointments_count === 1 ? "" : "s"}</p>
          </button>
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
