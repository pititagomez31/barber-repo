import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Scissors, ChevronLeft } from "lucide-react";
import Footer from "@/components/Footer";
import { api } from "@/lib/api";

const RESPONSABLE = {
  nombre: "+58 BarberStudio (Heber)",
  email: "info@58barberstudio.com",
  direccion: "Av. Los Majuelos 51 (dentro de Multitienda Veloz), Santa Cruz de Tenerife, España",
};

const CONTENT = {
  privacidad: {
    title: "Política de Privacidad y Tratamiento de Datos",
    updated: "Última actualización: junio de 2026",
    blocks: [
      ["1. Responsable del tratamiento", `El responsable del tratamiento de tus datos es ${RESPONSABLE.nombre}, con dirección en ${RESPONSABLE.direccion} y correo de contacto ${RESPONSABLE.email}. Cumplimos con el Reglamento (UE) 2016/679 (RGPD) y la Ley Orgánica 3/2018 (LOPDGDD).`],
      ["2. Datos que recogemos", "Recogemos los datos que nos facilitas al reservar una cita: nombre y apellidos, apodo (opcional), número de teléfono, correo electrónico (opcional) y el nombre de terceros cuando reservas para otra persona. No recogemos datos de categorías especiales."],
      ["3. Finalidad", "Utilizamos tus datos únicamente para: (a) gestionar y confirmar tus reservas; (b) enviarte confirmaciones y recordatorios de cita por WhatsApp o correo electrónico; (c) permitirte modificar o cancelar tu cita; y (d) mantener un historial de citas para la correcta prestación del servicio."],
      ["4. Legitimación", "La base legal es la ejecución de un contrato o de medidas precontractuales a petición tuya (la reserva) y tu consentimiento, que otorgas al enviar el formulario y aceptar esta política. Puedes retirar tu consentimiento en cualquier momento."],
      ["5. Conservación", "Conservamos tus datos mientras seas cliente y durante los plazos legalmente exigibles. Realizamos copias de seguridad diarias de las citas con fines exclusivos de restauración y continuidad del servicio. Cuando dejes de ser cliente, tus datos se bloquean y se eliminan una vez transcurridos los plazos legales."],
      ["6. Destinatarios", "No cedemos tus datos a terceros salvo obligación legal. Para el envío de mensajes utilizamos WhatsApp (Meta Platforms Ireland Ltd.) y proveedores de correo electrónico, que actúan como encargados del tratamiento con las debidas garantías."],
      ["7. Tus derechos", `Puedes ejercer tus derechos de acceso, rectificación, supresión, oposición, limitación y portabilidad escribiendo a ${RESPONSABLE.email}, indicando tu nombre y el derecho que deseas ejercer. También puedes reclamar ante la Agencia Española de Protección de Datos (www.aepd.es).`],
      ["8. Seguridad", "Aplicamos medidas técnicas y organizativas adecuadas para proteger tus datos frente a accesos no autorizados, pérdida o alteración."],
    ],
  },
  aviso: {
    title: "Aviso Legal",
    updated: "Última actualización: junio de 2026",
    blocks: [
      ["1. Datos identificativos", `Este sitio web es titularidad de ${RESPONSABLE.nombre}, con domicilio en ${RESPONSABLE.direccion} y correo electrónico de contacto ${RESPONSABLE.email}.`],
      ["2. Objeto", "El sitio web tiene por finalidad ofrecer información sobre los servicios de barbería y permitir la reserva, modificación y cancelación de citas online."],
      ["3. Condiciones de uso", "El acceso y uso de este sitio atribuye la condición de usuario e implica la aceptación de las presentes condiciones. El usuario se compromete a hacer un uso adecuado de los contenidos y a no emplearlos para actividades ilícitas."],
      ["4. Política de reservas", "Al reservar se requiere aceptar el compromiso del 50%: en caso de no presentarse sin avisar, el barbero podrá cobrar el 50% del servicio en la próxima visita o bloquear futuras reservas. Las cancelaciones y modificaciones se permiten hasta 12 horas antes de la cita."],
      ["5. Propiedad intelectual", "Todos los contenidos del sitio (textos, imágenes, logotipos y diseño) están protegidos por derechos de propiedad intelectual e industrial y son titularidad del responsable o de sus licenciantes. Queda prohibida su reproducción sin autorización."],
      ["6. Responsabilidad", "El titular no se hace responsable de los daños derivados de un uso indebido del sitio ni de la indisponibilidad temporal por causas técnicas."],
      ["7. Legislación aplicable", "Estas condiciones se rigen por la legislación española. Para cualquier controversia serán competentes los juzgados y tribunales del domicilio del titular."],
    ],
  },
  cookies: {
    title: "Política de Cookies",
    updated: "Última actualización: junio de 2026",
    blocks: [
      ["1. ¿Qué son las cookies?", "Las cookies son pequeños archivos que se almacenan en tu dispositivo al navegar. Permiten que la web funcione correctamente y recuerde ciertas preferencias."],
      ["2. Cookies que utilizamos", "Este sitio utiliza únicamente cookies y almacenamiento local de carácter técnico y estrictamente necesario para el funcionamiento (por ejemplo, para mantener la sesión del panel de administración). No utilizamos cookies publicitarias ni de seguimiento de terceros con fines de marketing."],
      ["3. Servicios de terceros", "Al mostrar el mapa de ubicación se utiliza Google Maps, que puede instalar sus propias cookies conforme a su política de privacidad. Te recomendamos revisarla en policies.google.com."],
      ["4. Gestión de cookies", "Puedes configurar tu navegador para bloquear o eliminar las cookies. Ten en cuenta que desactivar las cookies técnicas puede afectar al funcionamiento de algunas partes del sitio."],
      ["5. Consentimiento", "Al continuar navegando y utilizar el servicio de reservas aceptas el uso de las cookies técnicas descritas en esta política."],
    ],
  },
  terms: {
    title: "Condiciones del Servicio",
    updated: "Última actualización: junio de 2026",
    blocks: [
      ["1. Titular y aceptación", `Estas condiciones regulan el uso del sitio web de ${RESPONSABLE.nombre}, con domicilio en ${RESPONSABLE.direccion}. Al utilizar la web y realizar una reserva, aceptas estas condiciones de servicio.`],
      ["2. Servicio de reservas", "La web permite reservar, modificar y cancelar citas de barbería online. Al reservar aceptas la política del 50%: si no te presentas sin avisar, el barbero podrá cobrarte el 50% del servicio en tu próxima visita o bloquear futuras reservas. Las cancelaciones y modificaciones se permiten hasta 12 horas antes de la cita."],
      ["3. Comunicaciones por WhatsApp", "Si marcas la casilla de consentimiento en el formulario de reserva, aceptas recibir confirmaciones y recordatorios de tu cita a través de WhatsApp (servicio prestado por Meta Platforms Ireland Ltd.). Este consentimiento es voluntario y revocable: puedes darte de baja en cualquier momento respondiendo STOP o BAJA a cualquier mensaje, y reactivarlo respondiendo ALTA o realizando una nueva reserva."],
      ["4. Uso de tus datos", "Tus datos (nombre, teléfono y correo electrónico) se utilizan exclusivamente para gestionar tu cita y enviarte las comunicaciones que has aceptado. Consulta la Política de Privacidad para más detalle sobre el tratamiento de datos."],
      ["5. Responsabilidad y disponibilidad", "El titular no responde de la indisponibilidad temporal del servicio de reservas ni de los fallos de entrega de mensajes causados por terceros proveedores (WhatsApp/Meta, operadoras)."],
      ["6. Legislación aplicable", "Estas condiciones se rigen por la legislación española. Para cualquier controversia serán competentes los juzgados del domicilio del titular."],
    ],
  },
  "data-deletion": {
    title: "Eliminación de Datos Personales",
    updated: "Última actualización: junio de 2026",
    blocks: [
      ["1. Tu derecho de supresión", "Conforme al RGPD (Reglamento UE 2016/679), tienes derecho a solicitar la eliminación de tus datos personales de nuestros sistemas en cualquier momento."],
      ["2. Cómo solicitarlo", `Envía un correo a ${RESPONSABLE.email} con el asunto "Eliminación de datos", indicando tu nombre y el número de teléfono con el que reservaste. También puedes solicitarlo en persona en ${RESPONSABLE.direccion}.`],
      ["3. Qué eliminamos", "Borraremos tu nombre, número de teléfono, correo electrónico y tu historial de citas. Recibirás confirmación por correo una vez completado."],
      ["4. Baja de mensajes de WhatsApp", "Si solo quieres dejar de recibir mensajes de WhatsApp (sin eliminar tus datos), responde STOP o BAJA a cualquier mensaje que te hayamos enviado. Dejarás de recibir confirmaciones y recordatorios de inmediato. Puedes reactivarlos respondiendo ALTA."],
      ["5. Plazos", "Atendemos las solicitudes en un plazo máximo de 30 días. Los datos presentes en copias de seguridad se eliminan en el siguiente ciclo de rotación de backups y nunca se restauran para otros fines."],
    ],
  },
};

export default function Legal({ type = "privacidad" }) {
  const [business, setBusiness] = useState({});
  const data = CONTENT[type] || CONTENT.privacidad;

  useEffect(() => {
    api.get("/business").then((r) => setBusiness(r.data || {})).catch(() => {});
    window.scrollTo(0, 0);
  }, [type]);

  return (
    <div className="min-h-screen bg-[#14141A] text-neutral-100" data-testid={`legal-${type}`}>
      <header className="border-b border-white/5 py-5 px-5 md:px-10">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2" data-testid="legal-brand">
            <Scissors className="h-5 w-5 text-[#D4B77A]" />
            <span className="font-display text-xl tracking-tight">+58 <span className="text-[#D4B77A]">BarberStudio</span></span>
          </Link>
          <Link to="/" className="text-sm text-neutral-400 hover:text-[#D4B77A] flex items-center gap-1" data-testid="legal-back">
            <ChevronLeft className="h-4 w-4" /> Volver
          </Link>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-5 md:px-10 py-12 md:py-20">
        <p className="tracking-overline uppercase text-[10px] sm:text-xs text-[#D4B77A] mb-3">Legal</p>
        <h1 className="font-display text-4xl md:text-5xl tracking-tight italic mb-2" data-testid="legal-title">{data.title}</h1>
        <p className="text-neutral-500 text-sm mb-10">{data.updated}</p>
        <div className="space-y-8">
          {data.blocks.map(([h, p], i) => (
            <section key={i} data-testid={`legal-block-${i}`}>
              <h2 className="font-display text-lg md:text-xl text-neutral-100 mb-2">{h}</h2>
              <p className="text-neutral-400 text-sm md:text-base leading-relaxed">{p}</p>
            </section>
          ))}
        </div>
      </main>

      <Footer business={business} />
    </div>
  );
}
