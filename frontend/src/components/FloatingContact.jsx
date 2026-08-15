import { useEffect, useState } from "react";
import { MessageCircle, Instagram, Phone } from "lucide-react";
import { api } from "@/lib/api";

export default function FloatingContact() {
  const [b, setB] = useState({ whatsapp: "", instagram: "", phone: "" });
  useEffect(() => {
    api.get("/business").then((r) => setB(r.data)).catch(() => {});
  }, []);
  const waMsg = encodeURIComponent("¡Hola +58 BarberStudio! Me gustaría reservar una cita.");
  return (
    <div className="fixed right-4 bottom-24 md:bottom-8 z-40 flex flex-col gap-3" data-testid="floating-contact">
      <a data-testid="float-whatsapp" href={`https://wa.me/${b.whatsapp}?text=${waMsg}`} target="_blank" rel="noreferrer"
         className="h-12 w-12 grid place-items-center rounded-full bg-[#25D366] text-white shadow-lg hover:scale-105 transition-transform">
        <MessageCircle className="h-5 w-5" />
      </a>
      <a data-testid="float-instagram" href={`https://instagram.com/${b.instagram}`} target="_blank" rel="noreferrer"
         className="h-12 w-12 grid place-items-center rounded-full bg-gradient-to-br from-[#833AB4] via-[#E1306C] to-[#F77737] text-white shadow-lg hover:scale-105 transition-transform">
        <Instagram className="h-5 w-5" />
      </a>
      <a data-testid="float-phone" href={`tel:${b.phone}`}
         className="h-12 w-12 grid place-items-center rounded-full bg-[#1A1A1E] border border-[#D4B77A]/50 text-[#D4B77A] shadow-lg hover:scale-105 transition-transform">
        <Phone className="h-5 w-5" />
      </a>
    </div>
  );
}
