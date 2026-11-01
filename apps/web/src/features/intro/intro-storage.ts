// Marca de «intro completado» en el navegador (R1.4). No es un dato sensible: solo decide si `/`
// lleva a la bienvenida y se envía al registrarse para el logro «Primer aleteo».
const KEY = "alas.introCompleted";

export function isIntroCompleted(): boolean {
  try {
    return window.localStorage.getItem(KEY) === "1";
  } catch {
    return false; // navegador sin almacenamiento: se vuelve a mostrar la bienvenida
  }
}

export function markIntroCompleted(): void {
  try {
    window.localStorage.setItem(KEY, "1");
  } catch {
    // Sin almacenamiento el intro funciona igual; solo no se recuerda.
  }
}
