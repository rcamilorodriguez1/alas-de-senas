import { z } from "zod";

/** Validación en el cliente para responder rápido; la definitiva la hace el servidor (§3). */
export const EMAIL_MESSAGE = "Correo no válido";
export const PASSWORD_LENGTH_MESSAGE =
  "La contraseña debe tener entre 8 y 72 bytes (las tildes y la ñ cuentan doble).";
export const POLICY_MESSAGE = "Debes aceptar la política de tratamiento de datos.";
export const DAILY_GOALS = [5, 10, 15, 20] as const;

const encoder = new TextEncoder();

/** Bytes en UTF-8: bcrypt limita la contraseña a 72 bytes, no a 72 caracteres (B27). */
export function utf8Bytes(value: string): number {
  return encoder.encode(value).length;
}

const email = z.string().trim().toLowerCase().regex(/^[^@\s]+@[^@\s]+\.[^@\s]+$/, EMAIL_MESSAGE);

export const loginSchema = z.object({
  email,
  password: z.string().min(1, "Escribe tu contraseña"),
});

export const registerSchema = z.object({
  name: z.string().trim().min(1, "Escribe tu nombre.").max(80, "Máximo 80 caracteres."),
  email,
  password: z.string().refine((value) => {
    const size = utf8Bytes(value);
    return size >= 8 && size <= 72;
  }, PASSWORD_LENGTH_MESSAGE),
  dailyGoalMinutes: z.coerce
    .number()
    .pipe(
      z.union([z.literal(5), z.literal(10), z.literal(15), z.literal(20)], {
        error: "Elige una meta diaria.",
      }),
    ),
  acceptedDataPolicy: z.boolean().refine((value) => value, POLICY_MESSAGE),
});

export type LoginValues = z.infer<typeof loginSchema>;
export type RegisterFormInput = z.input<typeof registerSchema>;
export type RegisterValues = z.output<typeof registerSchema>;
