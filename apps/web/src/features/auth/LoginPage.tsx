import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router";
import { ApiError, login } from "../../lib/api";
import { safeReturnPath } from "../../lib/navigation";
import { AuthLayout, FieldError, buttonClass, inputClass } from "./AuthLayout";
import { loginSchema, type LoginValues } from "./schemas";

const TOO_MANY_MESSAGE = "Demasiados intentos, espera un minuto";

function loginErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return "No pudimos conectarnos. Intenta de nuevo.";
  if (error.code === "TOO_MANY_REQUESTS") return TOO_MANY_MESSAGE; // R2.5
  return error.message;
}

export function LoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register: field,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) });

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null);
    try {
      await login(values);
      await navigate(safeReturnPath(params.get("volver")), { replace: true });
    } catch (error) {
      setServerError(loginErrorMessage(error));
    }
  });

  return (
    <AuthLayout title="Ingresar">
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        <div>
          <label className="block">
          <span className="font-semibold">Correo</span>
          <input
            type="email"
            autoComplete="email"
            className={inputClass}
            aria-invalid={errors.email ? true : undefined}
            aria-describedby="login-email-error"
            {...field("email")}
          />
        </label>
          <FieldError id="login-email-error" message={errors.email?.message} />
        </div>
        <div>
          <label className="block">
          <span className="font-semibold">Contraseña</span>
          <input
            type="password"
            autoComplete="current-password"
            className={inputClass}
            aria-invalid={errors.password ? true : undefined}
            aria-describedby="login-password-error"
            {...field("password")}
          />
        </label>
          <FieldError id="login-password-error" message={errors.password?.message} />
        </div>
        {serverError && (
          <p role="alert" className="rounded-xl bg-red-50 p-3 text-red-800">
            {serverError}
          </p>
        )}
        <button type="submit" className={buttonClass} disabled={isSubmitting}>
          Ingresar
        </button>
      </form>
      <p className="mt-6 text-center">
        ¿No tienes cuenta?{" "}
        <Link to="/registro" className="font-semibold text-tomi-600 underline">
          Crear una cuenta
        </Link>
      </p>
    </AuthLayout>
  );
}
