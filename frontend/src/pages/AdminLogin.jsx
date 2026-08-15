import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import { Scissors, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { useAuth } from "@/context/AuthContext";
import { formatErr } from "@/lib/api";

export default function AdminLogin() {
  const nav = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      toast.success("Sesión iniciada");
      nav("/admin");
    } catch (err) {
      toast.error(formatErr(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#14141A] text-neutral-100 noise-bg grid place-items-center px-6" data-testid="admin-login-page">
      <div className="w-full max-w-md">
        <Link to="/" className="flex items-center gap-2 justify-center mb-8">
          <Scissors className="h-5 w-5 text-[#D4B77A]" />
          <span className="font-display text-xl">+58 <span className="text-[#D4B77A]">BarberStudio</span></span>
        </Link>
        <Card className="bg-[#1A1A1E] border-[#2A2A32] neumo">
          <CardContent className="p-8">
            <div className="h-12 w-12 rounded-full bg-[#D4B77A]/15 grid place-items-center mb-5">
              <Lock className="h-5 w-5 text-[#D4B77A]" />
            </div>
            <p className="tracking-overline uppercase text-xs text-[#D4B77A] mb-2">Panel del barbero</p>
            <h1 className="font-display text-3xl tracking-tight">Iniciar sesión</h1>
            <p className="text-sm text-neutral-500 mt-2">Solo para el barbero.</p>

            <form onSubmit={onSubmit} className="mt-8 space-y-5">
              <div>
                <Label className="text-xs tracking-overline uppercase text-neutral-500">Email</Label>
                <Input data-testid="admin-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="mt-2 h-12 bg-[#14141A] border-[#2A2A32]" placeholder="tu@email.com" />
              </div>
              <div>
                <Label className="text-xs tracking-overline uppercase text-neutral-500">Contraseña</Label>
                <Input data-testid="admin-password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="mt-2 h-12 bg-[#14141A] border-[#2A2A32]" placeholder="••••••••" />
              </div>
              <Button data-testid="admin-login-submit" type="submit" disabled={loading} className="w-full h-12 bg-[#D4B77A] hover:bg-[#C2A366] text-[#14141A] font-semibold btn-shine">
                {loading ? "Entrando…" : "Entrar"}
              </Button>
            </form>
          </CardContent>
        </Card>
        <Link to="/" className="block text-center text-sm text-neutral-500 hover:text-[#D4B77A] mt-6" data-testid="admin-back-home">← Volver a la web</Link>
      </div>
    </div>
  );
}
