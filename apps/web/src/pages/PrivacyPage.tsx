import { Link } from "react-router";

/** Política de tratamiento de datos (Ley 1581 de 2012). Pública: la enlaza el registro. */
export function PrivacyPage() {
  return (
    <main className="min-h-screen bg-[#F5FAF7] px-4 py-8 font-sans text-[#0E2A2F]">
      <article className="mx-auto max-w-3xl rounded-2xl bg-white p-8 shadow">
        <h1 className="font-display text-3xl font-extrabold">Política de tratamiento de datos</h1>
        <p className="mt-2 text-sm text-[#45606A]">
          Alas de Señas es un proyecto académico de Ingeniería de Sistemas. Esta política sigue la Ley 1581 de 2012
          (protección de datos personales en Colombia).
        </p>
        {/* Debe coincidir con DATA_POLICY_VERSION (apps/api/app/core/privacy.py, D-037). */}
        <p className="mt-1 text-sm text-[#45606A]">Versión del 6 de noviembre de 2026.</p>
        <h2 className="mt-6 font-display text-xl font-extrabold">Qué datos guardamos</h2>
        <ul className="mt-2 list-disc space-y-1 pl-6">
          <li>Tu nombre, tu correo y una versión cifrada de tu contraseña (nunca la contraseña).</li>
          <li>Tu meta diaria y tu mano dominante.</li>
          <li>La fecha en que aceptaste esta política y la versión que aceptaste.</li>
          <li>Tu progreso: lecciones, puntajes, XP, racha, néctar, vidas, logros, repasos y favoritos.</li>
        </ul>
        <h2 className="mt-6 font-display text-xl font-extrabold">Qué no guardamos</h2>
        <p className="mt-2">
          La cámara funciona solo en tu navegador: tu video y tus imágenes no salen de tu dispositivo. Del
          reconocimiento solo se guarda si fue correcto y su confianza, para el logro «Ojo de colibrí».
        </p>
        <h2 className="mt-6 font-display text-xl font-extrabold">Para qué los usamos</h2>
        <p className="mt-2">
          Solo para que puedas aprender, guardar tu avance y ver tus logros. No los vendemos ni los compartimos.
        </p>
        <h2 className="mt-6 font-display text-xl font-extrabold">Tus derechos</h2>
        <p className="mt-2">
          Puedes conocer, actualizar y suprimir tus datos en cualquier momento desde tu{" "}
          <Link to="/perfil" className="font-semibold text-[#047857] underline">
            perfil
          </Link>
          : editar tus datos, descargarlos en un archivo o eliminar tu cuenta con todo su contenido.
        </p>
        <p className="mt-8">
          <Link to="/" className="font-semibold text-[#047857] underline">
            Volver a Alas de Señas
          </Link>
        </p>
      </article>
    </main>
  );
}
