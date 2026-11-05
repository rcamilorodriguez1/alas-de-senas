import { Camera, FileVideo, Hand, type LucideIcon } from "lucide-react";
import { Link } from "react-router";
import { AppLayout } from "../../components/layout/AppLayout";
import { useSessionStore } from "../../lib/session-store";

const TOOLS: { to: string; title: string; description: string; icon: LucideIcon }[] = [
  {
    to: "/admin/gestos",
    title: "Colector de gestos",
    description:
      "Graba al equipo haciendo señas con movimiento (cuenta regresiva y 2 s) para entrenar el modelo de gestos. Muestra los cuadros por segundo.",
    icon: Camera,
  },
  {
    to: "/admin/importar",
    title: "Importar dataset",
    description:
      "Procesa en este navegador videos o fotos de datasets externos (p. ej. LSC-54) con el mismo método de la cámara.",
    icon: FileVideo,
  },
  {
    to: "/admin/dataset",
    title: "Colector del alfabeto",
    description: "Graba muestras de letras y números estáticos para el modelo del alfabeto.",
    icon: Hand,
  },
];

/** Sección «Administración» (D-030): solo ADMIN; reúne las herramientas de datos de la cámara. */
export function AdminPage() {
  const isAdmin = useSessionStore((state) => state.user?.role === "ADMIN");
  return (
    <AppLayout>
      <h1 className="font-display text-3xl font-extrabold">Administración</h1>
      {!isAdmin ? (
        <p role="alert" className="mt-4">
          Esta página es solo para administradores.
        </p>
      ) : (
        <>
          <p className="mt-2 text-[#45606A]">
            Herramientas para preparar los datos de la cámara. Solo se guardan números, nunca imágenes ni videos.
          </p>
          <ul className="mt-6 grid gap-4">
            {TOOLS.map(({ to, title, description, icon: Icon }) => (
              <li key={to}>
                <Link
                  to={to}
                  className="flex items-start gap-4 rounded-2xl bg-white p-5 shadow transition hover:bg-emerald-50 focus-visible:outline-2 focus-visible:outline-[#047857]"
                >
                  <Icon aria-hidden="true" size={28} className="mt-1 shrink-0 text-[#047857]" />
                  <span>
                    <span className="block font-display text-xl font-extrabold">{title}</span>
                    <span className="mt-1 block text-[#45606A]">{description}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </AppLayout>
  );
}
