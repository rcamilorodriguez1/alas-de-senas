// Progreso de la importación guardado en el navegador (para continuar tras apagar o cerrar).
import { describe, expect, it } from "vitest";
import { createProgressStore, MemoryProgressStore } from "./import-progress";

const session = { source: "LSC-54", license: "CC BY-NC 4.0", faceFeatures: false, total: 3 };

describe("MemoryProgressStore", () => {
  it("sin importación guardada devuelve null", async () => {
    expect(await new MemoryProgressStore().load()).toBeNull();
  });

  it("guarda la sesión y cada resultado; start borra lo anterior", async () => {
    const store = new MemoryProgressStore();
    await store.start(session);
    await store.add({ item: "a.mp4", sample: null, reason: "x" });
    await store.add({ item: "b.mp4", sample: null, reason: "y" });
    expect(await store.load()).toEqual({
      session,
      outcomes: [
        { item: "a.mp4", sample: null, reason: "x" },
        { item: "b.mp4", sample: null, reason: "y" },
      ],
    });
    await store.start({ ...session, total: 9 });
    expect((await store.load())?.outcomes).toEqual([]);
  });

  it("el mismo archivo dos veces se guarda una sola vez (el último resultado)", async () => {
    const store = new MemoryProgressStore();
    await store.start(session);
    await store.add({ item: "a.mp4", sample: null, reason: "x" });
    await store.add({ item: "a.mp4", sample: null, reason: "z" });
    expect((await store.load())?.outcomes).toEqual([{ item: "a.mp4", sample: null, reason: "z" }]);
  });

  it("clear borra todo", async () => {
    const store = new MemoryProgressStore();
    await store.start(session);
    await store.clear();
    expect(await store.load()).toBeNull();
  });
});

describe("createProgressStore", () => {
  it("sin IndexedDB (navegador privado o pruebas) usa memoria y no falla", async () => {
    const store = createProgressStore(undefined);
    expect(store).toBeInstanceOf(MemoryProgressStore);
    await store.start(session);
    expect((await store.load())?.session).toEqual(session);
  });
});
