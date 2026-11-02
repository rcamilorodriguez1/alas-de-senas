import { useQueryClient } from "@tanstack/react-query";
import { Camera, Download, LogOut, ShieldCheck, Trash2 } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { AppLayout } from "../../components/layout/AppLayout";
import { ApiError, logout } from "../../lib/api";
import { useSessionStore } from "../../lib/session-store";
import { streakLabel, useAchievements, useStats } from "../gamification/gamification-api";
import { useProgressSummary } from "../progress/progress-api";
import { removeAvatar, uploadAvatar } from "./avatar-api";
import { AvatarImage } from "./AvatarImage";
import { deleteAccount, downloadMyData, updateMe } from "./profile-api";

const GOALS = [5, 10, 15, 20] as const;
const CONFIRM_WORD = "ELIMINAR";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-emerald-50 p-3">
      <p className="text-sm font-semibold text-[#45606A]">{label}</p>
      <p className="font-display text-xl font-extrabold">{value}</p>
    </div>
  );
}

/** Sección 1: datos editables (PATCH /me: nombre, meta diaria y mano dominante). */
function ProfileForm() {
  const user = useSessionStore((state) => state.user);
  const queryClient = useQueryClient();
  const [name, setName] = useState(user?.name ?? "");
  const [goal, setGoal] = useState(user?.dailyGoalMinutes ?? 10);
  const [hand, setHand] = useState(user?.dominantHand === "left" ? "left" : "right");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    setMessage(null);
    try {
      await updateMe({
        name: name.trim(),
        dailyGoalMinutes: goal as 5 | 10 | 15 | 20,
        dominantHand: hand as "left" | "right",
      });
      await queryClient.invalidateQueries({ queryKey: ["gamification"] });
      setMessage({ ok: true, text: "Cambios guardados." });
    } catch (error) {
      setMessage({ ok: false, text: error instanceof ApiError ? error.message : "No pudimos guardar los cambios." });
    } finally {
      setSaving(false);
    }
  };

  return (
    <section aria-labelledby="tus-datos" className="rounded-2xl bg-white p-5 shadow">
      <h2 id="tus-datos" className="font-display text-xl font-extrabold">
        Tus datos
      </h2>
      <form onSubmit={(event) => void onSubmit(event)} className="mt-3 grid gap-4">
        <label className="grid gap-1 font-semibold">
          Nombre
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
            maxLength={80}
            className="rounded-xl border border-slate-300 px-3 py-2 font-normal"
          />
        </label>
        <fieldset className="grid gap-2">
          <legend className="font-semibold">Meta diaria</legend>
          <div className="flex flex-wrap gap-2">
            {GOALS.map((minutes) => (
              <label
                key={minutes}
                className={`cursor-pointer rounded-xl border-2 px-4 py-2 font-semibold ${
                  goal === minutes ? "border-[#047857] bg-emerald-50" : "border-slate-300"
                }`}
              >
                <input
                  type="radio"
                  name="meta"
                  value={minutes}
                  checked={goal === minutes}
                  onChange={() => setGoal(minutes)}
                  className="sr-only"
                />
                {minutes} min
              </label>
            ))}
          </div>
        </fieldset>
        <fieldset className="grid gap-2">
          <legend className="font-semibold">Mano dominante</legend>
          <p className="text-sm text-[#45606A]">Con la que haces las señas. La cámara reconoce las dos manos.</p>
          <div className="flex gap-2">
            {(["right", "left"] as const).map((side) => (
              <label
                key={side}
                className={`cursor-pointer rounded-xl border-2 px-4 py-2 font-semibold ${
                  hand === side ? "border-[#047857] bg-emerald-50" : "border-slate-300"
                }`}
              >
                <input
                  type="radio"
                  name="mano"
                  value={side}
                  checked={hand === side}
                  onChange={() => setHand(side)}
                  className="sr-only"
                />
                {side === "right" ? "Derecha" : "Izquierda"}
              </label>
            ))}
          </div>
        </fieldset>
        <div className="flex items-center gap-3">
          <button
            type="submit"
            aria-disabled={saving}
            className="rounded-xl border-b-4 border-emerald-950 bg-[#047857] px-5 py-2 font-display font-bold text-white aria-disabled:opacity-60"
          >
            Guardar cambios
          </button>
          <p role="status" className={`font-semibold ${message?.ok ? "text-[#047857]" : "text-red-700"}`}>
            {message?.text}
          </p>
        </div>
      </form>
    </section>
  );
}

/** Sección 2: resumen (datos que ya existen en otras páginas). */
function Summary() {
  const { data: stats } = useStats();
  const { data: progress } = useProgressSummary();
  const { data: achievements } = useAchievements();
  const unlocked = achievements?.filter((a) => a.unlockedAt !== null).length;
  return (
    <section aria-labelledby="resumen" className="rounded-2xl bg-white p-5 shadow">
      <h2 id="resumen" className="font-display text-xl font-extrabold">
        Tu resumen
      </h2>
      <div className="mt-3 grid grid-cols-2 gap-3 lg:grid-cols-3">
        <Stat label="XP total" value={stats ? String(stats.totalXp) : "—"} />
        <Stat label="Racha actual" value={stats ? streakLabel(stats.streak.current) : "—"} />
        <Stat label="Racha más larga" value={stats ? streakLabel(stats.streak.longest) : "—"} />
        <Stat label="Néctar" value={stats ? String(stats.nectar) : "—"} />
        <Stat label="Señas aprendidas" value={progress ? String(progress.signsLearned) : "—"} />
        <Stat
          label="Logros"
          value={achievements && unlocked !== undefined ? `${unlocked} de ${achievements.length}` : "—"}
        />
      </div>
      <p className="mt-3 flex gap-4 text-sm font-semibold">
        <Link to="/progreso" className="text-[#047857] underline">
          Ver mi progreso
        </Link>
        <Link to="/logros" className="text-[#047857] underline">
          Ver mis logros
        </Link>
      </p>
    </section>
  );
}

/** Sección 4: privacidad y cuenta (Ley 1581 de 2012: acceso y supresión, D-022). */
function PrivacyAndAccount() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [downloading, setDownloading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [password, setPassword] = useState("");
  const [word, setWord] = useState("");
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const download = async () => {
    if (downloading) return;
    setDownloading(true);
    setNotice(null);
    try {
      await downloadMyData();
      setNotice("Listo: se descargó el archivo con tus datos.");
    } catch {
      setNotice("No pudimos preparar tus datos. Intenta de nuevo.");
    } finally {
      setDownloading(false);
    }
  };

  const remove = async (event: FormEvent) => {
    event.preventDefault();
    if (deleting || word !== CONFIRM_WORD || !password) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteAccount(password);
      queryClient.clear();
      await navigate("/bienvenida", { replace: true });
    } catch (error) {
      setDeleteError(error instanceof ApiError ? error.message : "No pudimos eliminar la cuenta. Intenta de nuevo.");
      setDeleting(false);
    }
  };

  const onLogout = async () => {
    await logout();
    await navigate("/ingresar", { replace: true });
  };

  return (
    <section aria-labelledby="privacidad-cuenta" className="rounded-2xl bg-white p-5 shadow">
      <h2 id="privacidad-cuenta" className="font-display text-xl font-extrabold">
        Privacidad y cuenta
      </h2>
      <p className="mt-2 flex items-center gap-2 text-sm text-[#45606A]">
        <ShieldCheck aria-hidden="true" size={18} />
        Tus datos se tratan según la Ley 1581 de 2012.{" "}
        <Link to="/privacidad" className="font-semibold text-[#047857] underline">
          Política de tratamiento de datos
        </Link>
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => void download()}
          aria-disabled={downloading}
          className="inline-flex items-center gap-2 rounded-xl border border-[#047857] px-4 py-2 font-semibold text-[#047857] aria-disabled:opacity-60"
        >
          <Download aria-hidden="true" size={18} />
          Descargar mis datos
        </button>
        <button
          type="button"
          onClick={() => void onLogout()}
          className="inline-flex items-center gap-2 rounded-xl border border-slate-300 px-4 py-2 font-semibold"
        >
          <LogOut aria-hidden="true" size={18} />
          Cerrar sesión
        </button>
      </div>
      <p role="status" className="mt-2 text-sm font-semibold">
        {notice}
      </p>

      <div className="mt-5 rounded-xl border border-red-200 bg-red-50 p-4">
        <h3 className="font-display font-extrabold text-red-800">Eliminar mi cuenta</h3>
        <p className="mt-1 text-sm text-red-900">
          Se borran para siempre tu progreso, rachas, logros, favoritos y repasos. No se puede deshacer.
        </p>
        {!confirming ? (
          <button
            type="button"
            onClick={() => setConfirming(true)}
            className="mt-3 inline-flex items-center gap-2 rounded-xl border border-red-300 bg-white px-4 py-2 font-semibold text-red-800"
          >
            <Trash2 aria-hidden="true" size={18} />
            Quiero eliminar mi cuenta
          </button>
        ) : (
          <form onSubmit={(event) => void remove(event)} className="mt-3 grid gap-3">
            <label className="grid gap-1 text-sm font-semibold">
              Escribe {CONFIRM_WORD} para confirmar
              <input
                value={word}
                onChange={(event) => setWord(event.target.value)}
                autoComplete="off"
                className="rounded-xl border border-red-300 bg-white px-3 py-2 font-normal"
              />
            </label>
            <label className="grid gap-1 text-sm font-semibold">
              Tu contraseña
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                className="rounded-xl border border-red-300 bg-white px-3 py-2 font-normal"
              />
            </label>
            {deleteError && (
              <p role="alert" className="text-sm font-semibold text-red-800">
                {deleteError}
              </p>
            )}
            <div className="flex gap-2">
              <button
                type="submit"
                aria-disabled={deleting || word !== CONFIRM_WORD || !password}
                className="rounded-xl bg-red-700 px-4 py-2 font-bold text-white aria-disabled:opacity-50"
              >
                Eliminar definitivamente
              </button>
              <button
                type="button"
                onClick={() => {
                  setConfirming(false);
                  setPassword("");
                  setWord("");
                  setDeleteError(null);
                }}
                className="rounded-xl border border-slate-300 bg-white px-4 py-2 font-semibold"
              >
                Cancelar
              </button>
            </div>
          </form>
        )}
      </div>
    </section>
  );
}

const MAX_UPLOAD_MB = 15;

/** Foto de perfil (D-023): se elige un archivo, se recorta en el navegador y se sube. */
function PhotoPicker() {
  const user = useSessionStore((state) => state.user);
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const hasPhoto = Boolean(user?.avatarUpdatedAt);

  const onFile = async (file: File | undefined) => {
    if (!file || busy) return;
    setMessage(null);
    if (!/^image\/(jpeg|png|webp)$/.test(file.type)) {
      setMessage({ ok: false, text: "Usa una imagen JPG, PNG o WebP." });
      return;
    }
    if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
      setMessage({ ok: false, text: `La imagen pesa más de ${MAX_UPLOAD_MB} MB.` });
      return;
    }
    setBusy(true);
    try {
      await uploadAvatar(file);
      setMessage({ ok: true, text: "Foto actualizada." });
    } catch (error) {
      setMessage({ ok: false, text: error instanceof ApiError ? error.message : "No pudimos usar esa imagen." });
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  };

  const onRemove = async () => {
    if (busy) return;
    setBusy(true);
    setMessage(null);
    try {
      await removeAvatar();
      setMessage({ ok: true, text: "Quitamos tu foto." });
    } catch {
      setMessage({ ok: false, text: "No pudimos quitar la foto." });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-4">
      <AvatarImage size={96} label={hasPhoto ? "Tu foto de perfil" : "Sin foto de perfil (se muestra Tomi)"} />
      <div>
        <h1 className="font-display text-3xl font-extrabold">Perfil</h1>
        <p className="text-[#45606A]">{user?.email}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          <label
            className={`inline-flex cursor-pointer items-center gap-2 rounded-xl border border-[#047857] px-3 py-1.5 text-sm font-semibold text-[#047857] focus-within:ring-2 focus-within:ring-[#047857] ${
              busy ? "opacity-60" : ""
            }`}
          >
            <Camera aria-hidden="true" size={16} />
            {hasPhoto ? "Cambiar foto" : "Subir foto"}
            <input
              ref={input}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              disabled={busy}
              onChange={(event) => void onFile(event.target.files?.[0])}
              className="sr-only"
            />
          </label>
          {hasPhoto && (
            <button
              type="button"
              onClick={() => void onRemove()}
              aria-disabled={busy}
              className="rounded-xl border border-slate-300 px-3 py-1.5 text-sm font-semibold aria-disabled:opacity-60"
            >
              Quitar foto
            </button>
          )}
        </div>
        <p role="status" className={`mt-1 text-sm font-semibold ${message?.ok ? "text-[#047857]" : "text-red-700"}`}>
          {message?.text}
        </p>
      </div>
    </div>
  );
}

export function ProfilePage() {
  return (
    <AppLayout>
      <PhotoPicker />
      <div className="mt-6 grid gap-6">
        <ProfileForm />
        <Summary />
        <PrivacyAndAccount />
      </div>
    </AppLayout>
  );
}
