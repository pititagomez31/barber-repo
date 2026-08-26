import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Scissors, Clock, Star, MapPin, Phone, ChevronRight, Award } from "lucide-react";
import Navbar from "@/components/Navbar";
import FloatingContact from "@/components/FloatingContact";
import StickyBookCTA from "@/components/StickyBookCTA";
import Footer from "@/components/Footer";
import { api } from "@/lib/api";

const HERO_IMG = "https://customer-assets-39nsmqrw.emergentagent.net/job_studio-citas/artifacts/mbci8sqh_WhatsApp%20Image%202026-08-24%20at%209.32.06%20PM%20%281%29.jpeg";
const GAL1 = "https://customer-assets-39nsmqrw.emergentagent.net/job_studio-citas/artifacts/1rosdehm_WhatsApp%20Image%202026-08-24%20at%209.31.59%20PM%20%281%29.jpeg";
const GAL2 = "https://customer-assets-39nsmqrw.emergentagent.net/job_studio-citas/artifacts/73nx1fl0_WhatsApp%20Image%202026-08-24%20at%209.32.06%20PM%20%282%29.jpeg";
const GAL3 = "https://customer-assets-39nsmqrw.emergentagent.net/job_studio-citas/artifacts/fxk3r3ka_WhatsApp%20Image%202026-08-24%20at%209.32.06%20PM.jpeg";
const GAL4 = "https://customer-assets-39nsmqrw.emergentagent.net/job_studio-citas/artifacts/modeqpqu_WhatsApp%20Image%202026-08-24%20at%209.31.59%20PM%20%282%29.jpeg";

const TESTIMONIALS = [
  { name: "Carlos M.", text: "El mejor corte que me han hecho en Tenerife. Ambiente top y trato de 10.", rating: 5 },
  { name: "Javi R.", text: "Puntual, limpio y currante. Salí como nuevo. Ya soy fijo.", rating: 5 },
  { name: "Adrián P.", text: "Barba perfecta, sin prisas. Se nota el mimo en cada detalle.", rating: 5 },
];

export default function Home() {
  const [services, setServices] = useState([]);
  const [business, setBusiness] = useState({});

  useEffect(() => {
    api.get("/services").then((r) => setServices(r.data)).catch(() => {});
    api.get("/business").then((r) => setBusiness(r.data)).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-[#14141A] text-neutral-100 pb-24 md:pb-0" data-testid="home-page">
      <Navbar />

      {/* HERO */}
      <section className="relative min-h-[88vh] flex items-center overflow-hidden noise-bg" data-testid="hero-section">
        <div className="absolute inset-0">
          <img src={HERO_IMG} alt="Barbero cortando el pelo" className="w-full h-full object-cover opacity-40" />
          <div className="absolute inset-0 bg-gradient-to-r from-[#14141A] via-[#14141A]/85 to-transparent md:to-[#14141A]/40" />
          <div className="absolute inset-0 bg-gradient-to-t from-[#14141A] via-transparent to-transparent" />
        </div>
        <div className="relative max-w-7xl mx-auto px-5 md:px-10 pt-28 pb-20 md:pt-32 md:pb-16 grid md:grid-cols-2 gap-10 items-center">
          <div className="fade-up">
            <p className="tracking-overline uppercase text-[10px] sm:text-xs text-[#D4B77A] mb-4" data-testid="hero-eyebrow">Tenerife · Heber</p>
            <h1 className="font-display text-5xl sm:text-6xl lg:text-8xl leading-[0.95] tracking-tight" data-testid="hero-title">
              El corte<br />
              que <span className="text-[#D4B77A]">te define</span>.
            </h1>
            <p className="mt-5 md:mt-6 text-neutral-300 max-w-md leading-relaxed text-sm md:text-base" data-testid="hero-subtitle">
              Cortes precisos, barba clásica y una experiencia sin prisas. Reserva tu hora en menos de 30 segundos.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link to="/reservar" className="flex-1 sm:flex-initial">
                <Button data-testid="hero-book-btn" className="w-full h-14 px-8 bg-[#D4B77A] hover:bg-[#C2A366] text-[#14141A] font-semibold text-base rounded-md btn-shine gold-glow">
                  RESERVAR CITA <ChevronRight className="ml-1 h-5 w-5" />
                </Button>
              </Link>
              <a href="#servicios" className="hidden sm:block">
                <Button data-testid="hero-services-btn" variant="outline" className="h-14 px-8 border-white/15 bg-transparent text-neutral-100 hover:bg-white/5 hover:text-[#D4B77A]">
                  Ver servicios
                </Button>
              </a>
            </div>
            <div className="mt-8 flex gap-5 sm:gap-8 text-xs sm:text-sm text-neutral-400 flex-wrap">
              <div className="flex items-center gap-2"><Award className="h-4 w-4 text-[#D4B77A]" /> +2000 cortes</div>
              <div className="flex items-center gap-2"><Star className="h-4 w-4 text-[#D4B77A]" /> 4.9 / 5</div>
              <div className="flex items-center gap-2"><Clock className="h-4 w-4 text-[#D4B77A]" /> Sin esperas</div>
            </div>
          </div>
        </div>
      </section>

      {/* SERVICIOS */}
      <section id="servicios" className="py-16 md:py-24 px-5 md:px-6" data-testid="services-section">
        <div className="max-w-7xl mx-auto">
          <div className="max-w-2xl mb-10 md:mb-14">
            <p className="tracking-overline uppercase text-[10px] sm:text-xs text-[#D4B77A] mb-3 md:mb-4">Servicios</p>
            <h2 className="font-display text-4xl md:text-6xl tracking-tight italic leading-[1.05]">Elige lo que<br />necesitas hoy.</h2>
            <p className="text-neutral-400 mt-4 text-sm md:text-base leading-relaxed">Duración honesta, sin sorpresas. Reserva la que necesites.</p>
          </div>
          <div className="grid grid-cols-3 gap-2.5 md:gap-5">
            {services.map((s, i) => (
              <Card key={s.id} data-testid={`service-card-${i}`} className="bg-[#1A1A1E] border border-[#2A2A32] hover-lift hover:border-[#D4B77A]/40 group">
                <CardContent className="p-3 md:p-8 flex flex-col items-center text-center h-full">
                  <div className="h-9 w-9 md:h-14 md:w-14 rounded-full border border-[#D4B77A]/30 grid place-items-center mb-2 md:mb-5 group-hover:border-[#D4B77A] transition-colors">
                    <Scissors className="h-4 w-4 md:h-6 md:w-6 text-[#D4B77A]" />
                  </div>
                  <h3 className="font-display italic text-sm sm:text-base md:text-3xl tracking-tight leading-tight min-h-[2.5rem] md:min-h-[3.75rem] flex items-center" data-testid={`service-name-${i}`}>{s.name}</h3>
                  <p className="text-[10px] md:text-xs text-neutral-500 tracking-overline uppercase mt-1.5 md:mt-3 flex items-center gap-1">
                    <Clock className="h-2.5 w-2.5 md:h-3 md:w-3" /> {s.duration_min} min
                  </p>
                  <Link to={`/reservar?service=${s.id}`} className="mt-3 md:mt-6 w-full mt-auto">
                    <Button data-testid={`service-book-${i}`} className="w-full h-8 md:h-11 px-2 text-[11px] md:text-sm bg-transparent border border-[#D4B77A]/40 text-[#D4B77A] hover:bg-[#D4B77A] hover:text-[#14141A]">
                      Reservar
                    </Button>
                  </Link>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* GALERÍA - bento */}
      <section id="galeria" className="py-16 md:py-24 px-5 md:px-6 bg-[#17171B]" data-testid="gallery-section">
        <div className="max-w-7xl mx-auto">
          <div className="mb-10 md:mb-14 max-w-2xl">
            <p className="tracking-overline uppercase text-[10px] sm:text-xs text-[#D4B77A] mb-3 md:mb-4">Nuestro trabajo</p>
            <h2 className="font-display text-4xl md:text-6xl tracking-tight italic leading-[1.05]">El estudio<br />& el arte.</h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 grid-rows-3 md:grid-rows-2 gap-3 md:gap-4 h-[500px] md:h-[520px]">
            <div className="col-span-2 row-span-2 relative overflow-hidden rounded-lg border border-[#2A2A32]" data-testid="gallery-item-0">
              <img src={GAL1} alt="Corte de Heber" className="w-full h-full object-cover hover:scale-105 transition-transform duration-700" />
            </div>
            <div className="col-span-2 relative overflow-hidden rounded-lg border border-[#2A2A32]" data-testid="gallery-item-1">
              <img src={GAL2} alt="Trabajo del barbero" className="w-full h-full object-cover hover:scale-105 transition-transform duration-700" />
            </div>
            <div className="col-span-1 relative overflow-hidden rounded-lg border border-[#2A2A32]" data-testid="gallery-item-2">
              <img src={GAL4} alt="Detalle de fade" className="w-full h-full object-cover hover:scale-105 transition-transform duration-700" />
            </div>
            <div className="col-span-1 relative overflow-hidden rounded-lg border border-[#2A2A32]" data-testid="gallery-item-3">
              <img src={GAL3} alt="Barba y navaja" className="w-full h-full object-cover hover:scale-105 transition-transform duration-700" />
            </div>
          </div>
        </div>
      </section>

      {/* SOBRE EL BARBERO */}
      <section id="sobre" className="py-16 md:py-24 px-5 md:px-6" data-testid="about-section">
        <div className="max-w-6xl mx-auto grid md:grid-cols-2 gap-8 md:gap-14 items-center">
          <div className="relative">
            <img src={GAL3} alt="Heber trabajando" className="w-full h-[380px] md:h-[520px] object-cover rounded-lg border border-[#2A2A32]" />
            <div className="absolute -bottom-4 -right-4 md:-bottom-6 md:-right-6 neumo px-5 py-3 md:px-6 md:py-4 rounded-lg">
              <div className="font-display italic text-2xl md:text-3xl text-[#D4B77A]">Heber</div>
              <div className="text-[10px] md:text-xs tracking-overline uppercase text-neutral-500">tu barbero</div>
            </div>
          </div>
          <div>
            <p className="tracking-overline uppercase text-[10px] sm:text-xs text-[#D4B77A] mb-3 md:mb-4">El barbero</p>
            <h2 className="font-display text-4xl md:text-6xl tracking-tight italic leading-[1.05]">Manos de tijera,<br />cabeza de estilo.</h2>
            <p className="text-neutral-400 mt-5 md:mt-6 leading-relaxed text-sm md:text-base">
              Soy <span className="text-[#D4B77A]">Heber</span>. Formado entre Venezuela y las Islas Canarias, mi obsesión es que salgas por la puerta con un corte que te haga sentir tú al 200%. Trabajo por cita para respetar tu tiempo — nada de esperas.
            </p>
            <ul className="mt-5 md:mt-6 space-y-2 text-sm text-neutral-300">
              <li>· Corte a tijera y máquina · Barba con navaja</li>
              <li>· Productos premium · Ambiente masculino y cuidado</li>
              <li>· Reserva online con confirmación por WhatsApp</li>
            </ul>
          </div>
        </div>
      </section>

      {/* OPINIONES */}
      <section id="opiniones" className="py-16 md:py-24 px-5 md:px-6 bg-[#17171B]" data-testid="testimonials-section">
        <div className="max-w-7xl mx-auto">
          <div className="mb-10 md:mb-14 max-w-2xl">
            <p className="tracking-overline uppercase text-[10px] sm:text-xs text-[#D4B77A] mb-3 md:mb-4">Opiniones</p>
            <h2 className="font-display text-4xl md:text-6xl tracking-tight italic leading-[1.05]">Lo que dicen los<br />que ya pasaron.</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6">
            {TESTIMONIALS.map((t, i) => (
              <Card key={i} data-testid={`testimonial-${i}`} className="bg-[#1A1A1E] border border-[#2A2A32] hover-lift">
                <CardContent className="p-6 md:p-7">
                  <div className="flex gap-1 mb-3 md:mb-4">
                    {[...Array(t.rating)].map((_, k) => <Star key={k} className="h-4 w-4 fill-[#D4B77A] text-[#D4B77A]" />)}
                  </div>
                  <p className="text-neutral-300 leading-relaxed text-sm md:text-base">&ldquo;{t.text}&rdquo;</p>
                  <p className="mt-4 md:mt-5 text-sm text-[#D4B77A] font-medium">— {t.name}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* UBICACIÓN */}
      <section id="ubicacion" className="py-16 md:py-24 px-5 md:px-6" data-testid="location-section">
        <div className="max-w-7xl mx-auto grid md:grid-cols-2 gap-8 md:gap-10 items-center">
          <div>
            <p className="tracking-overline uppercase text-[10px] sm:text-xs text-[#D4B77A] mb-3 md:mb-4">Ubicación</p>
            <h2 className="font-display text-4xl md:text-6xl tracking-tight italic leading-[1.05]">Fácil de encontrar.<br />Difícil de olvidar.</h2>
            <div className="mt-6 md:mt-8 space-y-3 md:space-y-4 text-neutral-300 text-sm md:text-base">
              <p className="flex gap-3"><MapPin className="h-5 w-5 text-[#D4B77A] mt-0.5 shrink-0" /> {business.address}</p>
              <p className="flex gap-3"><Phone className="h-5 w-5 text-[#D4B77A] shrink-0" /> {business.phone}</p>
              {business.reviews_url && (
                <a href={business.reviews_url} target="_blank" rel="noreferrer" className="flex gap-3 items-center hover:text-[#D4B77A]" data-testid="reviews-link">
                  <Star className="h-5 w-5 text-[#D4B77A] fill-[#D4B77A] shrink-0" /> Déjanos tu reseña en Google
                </a>
              )}
            </div>
            <div className="mt-6 md:mt-8 flex gap-3 flex-wrap">
              <a href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(business.address || "Tenerife")}`} target="_blank" rel="noreferrer" data-testid="open-maps-link" className="flex-1 sm:flex-initial">
                <Button className="w-full bg-transparent border border-[#D4B77A]/40 text-[#D4B77A] hover:bg-[#D4B77A] hover:text-[#14141A]">Abrir en Maps</Button>
              </a>
              {business.reviews_url && (
                <a href={business.reviews_url} target="_blank" rel="noreferrer" data-testid="reviews-btn" className="flex-1 sm:flex-initial">
                  <Button className="w-full bg-[#D4B77A] hover:bg-[#C2A366] text-[#14141A] font-semibold"><Star className="h-4 w-4 mr-1 fill-[#14141A]" />Escribir reseña</Button>
                </a>
              )}
            </div>
          </div>
          <div className="rounded-lg overflow-hidden border border-[#2A2A32] h-[280px] md:h-[420px]">
            <iframe
              title="Mapa Tenerife"
              src={`https://www.google.com/maps?q=${encodeURIComponent(business.address || "Tenerife, España")}&output=embed`}
              className="w-full h-full grayscale-[40%]"
              loading="lazy"
              data-testid="google-map"
            />
          </div>
        </div>
      </section>

      <Footer business={business} />
      <FloatingContact />
      <StickyBookCTA />
    </div>
  );
}
