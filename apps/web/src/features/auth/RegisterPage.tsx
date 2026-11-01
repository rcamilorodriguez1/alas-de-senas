import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router";
import { isIntroCompleted } from "../intro/intro-storage";
import { ApiError, register as registerAccount } from "../../lib/api";
import { AuthLayout, FieldError, buttonClass, inputClass } from "./AuthLayout";
import {
  DAILY_GOALS,
  registerSchema,
  type RegisterFormInput,
  type RegisterValues,
} from "./schemas";

const SERVER_FIELDS = ["name", "email", "password", "dailyGoalMinutes", "acceptedDataPolicy"] as const;
type ServerField = (typeof SERVER_FIELDS)[number];

function isServerField(name: string): name is ServerField {
  return SERVER_FIELDS.some((field) => field === name);
}

export function RegisterPage() {
  const navigate = useNavigate();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register: field,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormInput, unknown, RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { dailyGoalMinutes: 10, acceptedDataPolicy: false },
  });

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null);
    try {
      await registerAccount({ ...values, acceptedDataPolicy: true, introCompleted: isIntroCompleted() });
      await navigate("/aprender", { replace: true });
    } catch (error) {
      if (!(error instanceof ApiError)) {
        setServerError("No pudimos conectarnos. Intenta de nuevo.");
        return;
      }
      if (error.code === "EMAIL_TAKEN") {
        setError("email", { message: error.message });
        return;
      }
      let shown = false;
      for (const [name, message] of Object.entries(error.fields ?? {})) {
        if (isServerField(name)) {
          setError(name, { message });
          shown = true;
        }
      }
      if (!shown) setServerError(error.message);
    }
  });

  return (
    <AuthLayout title="Crear cuenta">
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        <div>
          <label className="block">
          <span className="font-semibold">Nombre</span>
          <input
            autoComplete="name"
            className={inputClass}
            aria-invalid={errors.name ? true : undefined}
            aria-describedby="register-name-error"
            {...field("name")}
          />
        </label>
          <FieldError id="register-name-error" message={errors.name?.message} />
        </div>
        <div>
          <label className="block">
          <span className="font-semibold">Correo</span>
          <input
            type="email"
            autoComplete="email"
            className={inputClass}
            aria-invalid={errors.email ? true : undefined}
            aria-describedby="register-email-error"
            {...field("email")}
          />
        </label>
          <FieldError id="register-email-error" message={errors.email?.message} />
        </div>
        <div>
          <label className="block">
          <span className="font-semibold">Contraseña</span>
          <input
            type="password"
            autoComplete="new-password"
            className={inputClass}
            aria-invalid={errors.password ? true : undefined}
            aria-describedby="register-password-error"
            {...field("password")}
          />
        </label>
          <FieldError id="register-password-error" message={errors.password?.message} />
        </div>
        <div>
          <label className="block">
          <span className="font-semibold">Meta diaria</span>
          <select className={inputClass} {...field("dailyGoalMinutes")}>
            {DAILY_GOALS.map((goal) => (
              <option key={goal} value={goal}>
                {goal} minutos
              </option>
            ))}
          </select>
        </label>
          <FieldError id="register-goal-error" message={errors.dailyGoalMinutes?.message} />
        </div>
        <div>
          <label className="flex items-start gap-3">
            <input
              type="checkbox"
              className="mt-1 h-5 w-5 accent-tomi-600"
              aria-invalid={errors.acceptedDataPolicy ? true : undefined}
              aria-describedby="register-policy-error"
              {...field("acceptedDataPolicy")}
            />
            <span>
              Acepto la política de tratamiento de datos (Ley 1581 de 2012).{" "}
              <Link to="/privacidad" className="text-tomi-600 underline">
                Leer la política
              </Link>
            </span>
          </label>
          <FieldError id="register-policy-error" message={errors.acceptedDataPolicy?.message} />
        </div>
        {serverError && (
          <p role="alert" className="rounded-xl bg-red-50 p-3 text-red-800">
            {serverError}
          </p>
        )}
        <button type="submit" className={buttonClass} disabled={isSubmitting}>
          Crear cuenta
        </button>
      </form>
      <p className="mt-6 text-center">
        <Link to="/ingresar" className="font-semibold text-tomi-600 underline">
          Ya tengo una cuenta
        </Link>
      </p>
    </AuthLayout>
  );
}
