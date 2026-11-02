import { AppLayout } from "../components/layout/AppLayout";

// Señas con video del dataset LSC-54 (D-018). Si se reemplaza un video por uno propio, quitarlo aquí.
const LSC54_SIGNS = [
  "Hola",
  "Buenos días",
  "Buenas tardes",
  "Buenas noches",
  "¿Cómo estás?",
  "Adiós",
  "Gracias",
  "Por favor",
  "De nada",
  "Sí",
  "No",
  "Perdón",
  "Números del 1 al 10",
];

/** Créditos y licencias de los videos de terceros (atribución exigida por CC BY-NC 4.0). */
export function CreditsPage() {
  return (
    <AppLayout>
      <h1 className="font-display text-3xl font-extrabold">Créditos</h1>
      <section aria-labelledby="videos-lsc54" className="mt-6 rounded-2xl bg-white p-5 shadow">
        <h2 id="videos-lsc54" className="font-display text-xl font-extrabold">
          Videos de señas: LSC-54
        </h2>
        <p className="mt-2">
          Los videos de estas señas provienen del conjunto de datos <strong>LSC-54</strong> de la Universidad de La
          Sabana: Mora-Zarate, Garzón-Castro y Castellanos-Rivillas (2025), «LSC-54: A landmark-based dataset for
          Colombian Sign Language», <em>Data in Brief</em> 63, 112145.{" "}
          <a
            href="https://doi.org/10.1016/j.dib.2025.112145"
            className="font-semibold text-[#047857] underline"
            target="_blank"
            rel="noreferrer"
          >
            doi.org/10.1016/j.dib.2025.112145
          </a>
          . Datos:{" "}
          <a
            href="https://doi.org/10.57760/sciencedb.25639"
            className="font-semibold text-[#047857] underline"
            target="_blank"
            rel="noreferrer"
          >
            doi.org/10.57760/sciencedb.25639
          </a>
          .
        </p>
        <p className="mt-2">
          Licencia{" "}
          <a
            href="https://creativecommons.org/licenses/by-nc/4.0/deed.es"
            className="font-semibold text-[#047857] underline"
            target="_blank"
            rel="noreferrer"
          >
            CC BY-NC 4.0
          </a>
          : uso no comercial con atribución. Cambios: se tomó una grabación por seña, se recortó el audio y se
          convirtió a MP4 de 720p. Los rostros vienen pixelados en el original.
        </p>
        <ul className="mt-3 flex flex-wrap gap-2">
          {LSC54_SIGNS.map((sign) => (
            <li key={sign} className="rounded-full bg-emerald-50 px-3 py-1 text-sm font-semibold">
              {sign}
            </li>
          ))}
        </ul>
      </section>
      <section aria-labelledby="modelo-camara" className="mt-6 rounded-2xl bg-white p-5 shadow">
        <h2 id="modelo-camara" className="font-display text-xl font-extrabold">
          Modelo de la cámara: LSC70 y LSC-54
        </h2>
        <p className="mt-2">
          El reconocimiento del alfabeto y los números se entrenó con los puntos de la mano extraídos (en el
          navegador) de fotos de <strong>LSC70</strong> — Universidad del Cauca, «The dynamic Colombian sign language
          dataset for basic conversation LSC70», <em>Data in Brief</em> (2025),{" "}
          <a
            href="https://doi.org/10.17632/9ssyn8tff5.2"
            className="font-semibold text-[#047857] underline"
            target="_blank"
            rel="noreferrer"
          >
            doi.org/10.17632/9ssyn8tff5.2
          </a>{" "}
          (licencia{" "}
          <a
            href="https://creativecommons.org/licenses/by/4.0/deed.es"
            className="font-semibold text-[#047857] underline"
            target="_blank"
            rel="noreferrer"
          >
            CC BY 4.0
          </a>
          ) — y de videos de <strong>LSC-54</strong> (números y señas sin número). No se guardan ni se publican esas
          fotos o videos: solo el modelo entrenado.
        </p>
      </section>
      <section aria-labelledby="proyecto" className="mt-6 rounded-2xl bg-white p-5 shadow">
        <h2 id="proyecto" className="font-display text-xl font-extrabold">
          Alas de Señas
        </h2>
        <p className="mt-2">
          Proyecto académico de Ingeniería de Sistemas. Las demás señas usan videos propios o un video provisional «en
          preparación» mientras se graban.
        </p>
      </section>
    </AppLayout>
  );
}
