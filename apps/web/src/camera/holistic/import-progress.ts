// Progreso de /admin/importar guardado en el navegador (D-044): si se apaga el equipo o se cierra la
// pestaña, al volver a elegir los mismos archivos se salta lo ya procesado. Nada sale del equipo.
// IndexedDB (no localStorage): un dataset completo pesa decenas de MB. Si no hay IndexedDB (ventana
// privada, pruebas), se usa memoria: la página funciona igual, solo que sin poder continuar después.
import type { SavedOutcome } from "./import-plan";

export interface ImportSession {
  source: string;
  license: string;
  faceFeatures: boolean;
  /** Cuántos archivos importables tenía la selección. */
  total: number;
}

export interface SavedProgress {
  session: ImportSession;
  outcomes: SavedOutcome[];
}

export interface ProgressStore {
  load(): Promise<SavedProgress | null>;
  /** Empieza una importación nueva: borra los resultados anteriores. */
  start(session: ImportSession): Promise<void>;
  add(outcome: SavedOutcome): Promise<void>;
  clear(): Promise<void>;
}

export class MemoryProgressStore implements ProgressStore {
  private session: ImportSession | null = null;
  private readonly outcomes = new Map<string, SavedOutcome>();

  async load(): Promise<SavedProgress | null> {
    return this.session ? { session: this.session, outcomes: [...this.outcomes.values()] } : null;
  }

  async start(session: ImportSession): Promise<void> {
    this.session = session;
    this.outcomes.clear();
  }

  async add(outcome: SavedOutcome): Promise<void> {
    this.outcomes.delete(outcome.item); // el último resultado del archivo queda al final
    this.outcomes.set(outcome.item, outcome);
  }

  async clear(): Promise<void> {
    this.session = null;
    this.outcomes.clear();
  }
}

const DB_NAME = "alas-importar";
const SESSION = "sesion";
const OUTCOMES = "resultados";
const SESSION_KEY = "actual";

function request<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error ?? new Error("IndexedDB falló."));
  });
}

function done(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error ?? new Error("IndexedDB falló."));
    tx.onabort = () => reject(tx.error ?? new Error("IndexedDB canceló la operación."));
  });
}

function isSession(value: unknown): value is ImportSession {
  return typeof value === "object" && value !== null && "source" in value && "total" in value;
}

function isOutcome(value: unknown): value is SavedOutcome {
  return typeof value === "object" && value !== null && "item" in value && "sample" in value;
}

export class IndexedDbProgressStore implements ProgressStore {
  private db: Promise<IDBDatabase> | null = null;

  constructor(private readonly factory: IDBFactory) {}

  private open(): Promise<IDBDatabase> {
    this.db ??= new Promise((resolve, reject) => {
      const req = this.factory.open(DB_NAME, 1);
      req.onupgradeneeded = () => {
        req.result.createObjectStore(SESSION);
        req.result.createObjectStore(OUTCOMES, { keyPath: "item" });
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error ?? new Error("No se pudo abrir IndexedDB."));
    });
    return this.db;
  }

  async load(): Promise<SavedProgress | null> {
    const db = await this.open();
    const tx = db.transaction([SESSION, OUTCOMES], "readonly");
    const session: unknown = await request(tx.objectStore(SESSION).get(SESSION_KEY));
    const outcomes: unknown[] = await request(tx.objectStore(OUTCOMES).getAll());
    return isSession(session) ? { session, outcomes: outcomes.filter(isOutcome) } : null;
  }

  async start(session: ImportSession): Promise<void> {
    const db = await this.open();
    const tx = db.transaction([SESSION, OUTCOMES], "readwrite");
    tx.objectStore(OUTCOMES).clear();
    tx.objectStore(SESSION).put(session, SESSION_KEY);
    await done(tx);
  }

  async add(outcome: SavedOutcome): Promise<void> {
    const db = await this.open();
    const tx = db.transaction(OUTCOMES, "readwrite");
    tx.objectStore(OUTCOMES).put(outcome);
    await done(tx);
  }

  async clear(): Promise<void> {
    const db = await this.open();
    const tx = db.transaction([SESSION, OUTCOMES], "readwrite");
    tx.objectStore(SESSION).clear();
    tx.objectStore(OUTCOMES).clear();
    await done(tx);
  }
}

/** IndexedDB si el navegador lo tiene; si no, memoria (sin poder continuar tras cerrar). */
export function createProgressStore(factory: IDBFactory | undefined): ProgressStore {
  return factory ? new IndexedDbProgressStore(factory) : new MemoryProgressStore();
}

export const progressStore: ProgressStore = createProgressStore(
  typeof indexedDB === "undefined" ? undefined : indexedDB,
);
