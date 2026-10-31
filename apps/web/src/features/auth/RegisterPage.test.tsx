import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useSessionStore } from "../../lib/session-store";
import {
  bearer,
  errorBody,
  jsonResponse,
  makeAuth,
  makeUser,
  mockFetch,
} from "../../test/http";
import { RegisterPage } from "./RegisterPage";

const BYTES_MESSAGE =
  "La contraseña debe tener entre 8 y 72 bytes (las tildes y la ñ cuentan doble).";
const POLICY_MESSAGE = "Debes aceptar la política de tratamiento de datos.";
const POLICY_LABEL = /Acepto la política de tratamiento de datos/;

function renderRegister() {
  const router = createMemoryRouter(
    [
      { path: "/registro", element: <RegisterPage /> },
      { path: "/aprender", element: <p>Ruta de aprendizaje</p> },
      { path: "/ingresar", element: <p>Página de ingreso</p> },
      { path: "/privacidad", element: <p>Política de privacidad</p> },
    ],
    { initialEntries: ["/registro"] },
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

interface FormValues {
  name?: string;
  email?: string;
  password?: string;
  goal?: string;
  accept?: boolean;
}

async function fillAndSubmit({
  name = "Ana",
  email = "ana@example.com",
  password = "secreta123",
  goal,
  accept = true,
}: FormValues = {}) {
  const user = userEvent.setup();
  if (name !== "") await user.type(screen.getByLabelText("Nombre"), name);
  if (email !== "") await user.type(screen.getByLabelText("Correo"), email);
  if (password !== "") await user.type(screen.getByLabelText("Contraseña"), password);
  if (goal !== undefined) await user.selectOptions(screen.getByLabelText("Meta diaria"), goal);
  if (accept) await user.click(screen.getByRole("checkbox", { name: POLICY_LABEL }));
  await user.click(screen.getByRole("button", { name: "Crear cuenta" }));
  return user;
}

const okRegister = () => jsonResponse(201, makeAuth("token-registro", makeUser({ name: "Ana" })));

beforeEach(() => {
  useSessionStore.setState(useSessionStore.getInitialState(), true);
  useSessionStore.getState().clearSession();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RegisterPage: estructura (R2.1)", () => {
  it("tiene Nombre, Correo, Contraseña, Meta diaria, la casilla de datos y los enlaces", () => {
    mockFetch(okRegister);
    renderRegister();
    expect(screen.getByLabelText("Nombre")).toBeInTheDocument();
    expect(screen.getByLabelText("Correo")).toBeInTheDocument();
    expect(screen.getByLabelText("Contraseña")).toHaveAttribute("type", "password");
    expect(screen.getByRole("checkbox", { name: POLICY_LABEL })).not.toBeChecked();
    expect(screen.getByRole("button", { name: "Crear cuenta" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ya tengo una cuenta" })).toHaveAttribute(
      "href",
      "/ingresar",
    );
    const hrefs = screen.getAllByRole("link").map((link) => link.getAttribute("href"));
    expect(hrefs).toContain("/privacidad");
  });

  it("«Meta diaria» ofrece 5, 10, 15 y 20 minutos y por defecto es 10", () => {
    mockFetch(okRegister);
    renderRegister();
    const select = screen.getByLabelText("Meta diaria");
    expect(select).toHaveValue("10");
    const values = within(select)
      .getAllByRole("option")
      .map((option) => option.getAttribute("value"));
    expect(values).toEqual(["5", "10", "15", "20"]);
  });
});

describe("RegisterPage: validación en el cliente", () => {
  it("contraseña de 8 bytes con ñ («ñññ» + «aa», 5 caracteres) es válida y se envía", async () => {
    const http = mockFetch(okRegister);
    renderRegister();
    await fillAndSubmit({ password: "ñññaa" });
    await waitFor(() => expect(http.to("/api/auth/register", "POST")).toHaveLength(1));
    expect(screen.queryByText(BYTES_MESSAGE)).not.toBeInTheDocument();
  });

  it("contraseña de 72 bytes (36 «ñ») es válida", async () => {
    const http = mockFetch(okRegister);
    renderRegister();
    await fillAndSubmit({ password: "ñ".repeat(36) });
    await waitFor(() => expect(http.to("/api/auth/register", "POST")).toHaveLength(1));
  });

  it("contraseña de 73 bytes (36 «ñ» + «a», solo 37 caracteres) se rechaza con el mensaje de bytes", async () => {
    const http = mockFetch(okRegister);
    renderRegister();
    await fillAndSubmit({ password: "ñ".repeat(36) + "a" });
    expect(await screen.findByText(BYTES_MESSAGE)).toBeInTheDocument();
    expect(http.requests).toHaveLength(0);
  });

  it("contraseña de 7 bytes se rechaza con el mensaje de bytes", async () => {
    const http = mockFetch(okRegister);
    renderRegister();
    await fillAndSubmit({ password: "abcdefg" });
    expect(await screen.findByText(BYTES_MESSAGE)).toBeInTheDocument();
    expect(http.requests).toHaveLength(0);
  });

  it("«ñña» tiene 3 caracteres y 5 bytes: también se rechaza", async () => {
    const http = mockFetch(okRegister);
    renderRegister();
    await fillAndSubmit({ password: "ñña" });
    expect(await screen.findByText(BYTES_MESSAGE)).toBeInTheDocument();
    expect(http.requests).toHaveLength(0);
  });

  it("sin marcar la casilla muestra «Debes aceptar la política de tratamiento de datos.» y no envía", async () => {
    const http = mockFetch(okRegister);
    renderRegister();
    await fillAndSubmit({ accept: false });
    expect(await screen.findByText(POLICY_MESSAGE)).toBeInTheDocument();
    expect(http.requests).toHaveLength(0);
  });

  it("un correo inválido muestra «Correo no válido» y no envía", async () => {
    const http = mockFetch(okRegister);
    renderRegister();
    await fillAndSubmit({ email: "ana.example.com" });
    expect(await screen.findByText("Correo no válido")).toBeInTheDocument();
    expect(http.requests).toHaveLength(0);
  });
});

describe("RegisterPage: errores del servidor junto a su campo", () => {
  it("muestra los errores por campo (fields) del servidor junto al campo correspondiente", async () => {
    mockFetch(() =>
      jsonResponse(
        422,
        errorBody(422, "VALIDATION_ERROR", "Revisa los datos.", {
          email: "Correo no válido",
        }),
      ),
    );
    renderRegister();
    await fillAndSubmit({ email: "ana@example.com" });
    expect(await screen.findByText("Correo no válido")).toBeInTheDocument();
    expect(screen.getByLabelText("Correo")).toHaveAccessibleDescription(
      expect.stringContaining("Correo no válido"),
    );
  });

  it("muestra el error de servidor del campo nombre junto al nombre", async () => {
    mockFetch(() =>
      jsonResponse(
        422,
        errorBody(422, "VALIDATION_ERROR", "Revisa los datos.", {
          name: "Escribe tu nombre",
        }),
      ),
    );
    renderRegister();
    await fillAndSubmit({ name: "Ana" });
    expect(await screen.findByText("Escribe tu nombre")).toBeInTheDocument();
    expect(screen.getByLabelText("Nombre")).toHaveAccessibleDescription(
      expect.stringContaining("Escribe tu nombre"),
    );
  });

  it("R2.3: 409 EMAIL_TAKEN → «Ya existe una cuenta con este correo» junto al correo, sin navegar", async () => {
    mockFetch(() =>
      jsonResponse(409, errorBody(409, "EMAIL_TAKEN", "Ya existe una cuenta con este correo")),
    );
    const router = renderRegister();
    await fillAndSubmit();
    expect(await screen.findByText("Ya existe una cuenta con este correo")).toBeInTheDocument();
    expect(screen.getByLabelText("Correo")).toHaveAccessibleDescription(
      expect.stringContaining("Ya existe una cuenta con este correo"),
    );
    expect(router.state.location.pathname).toBe("/registro");
    expect(useSessionStore.getState().status).toBe("anonymous");
  });
});

describe("RegisterPage: éxito", () => {
  it("envía {name, email, password, dailyGoalMinutes: número, acceptedDataPolicy: true} y va a /aprender", async () => {
    const http = mockFetch(okRegister);
    const router = renderRegister();
    await fillAndSubmit({
      name: "Ana",
      email: "ana@example.com",
      password: "ñññaa",
      goal: "15",
    });
    await waitFor(() => expect(router.state.location.pathname).toBe("/aprender"));
    const request = http.to("/api/auth/register", "POST")[0];
    expect(request.body).toEqual({
      name: "Ana",
      email: "ana@example.com",
      password: "ñññaa",
      dailyGoalMinutes: 15,
      acceptedDataPolicy: true,
    });
    expect(bearer(request)).toBeNull();
    expect(useSessionStore.getState().status).toBe("authenticated");
    expect(useSessionStore.getState().accessToken).toBe("token-registro");
  });

  it("si no se cambia la meta, envía dailyGoalMinutes: 10", async () => {
    const http = mockFetch(okRegister);
    renderRegister();
    await fillAndSubmit();
    await waitFor(() => expect(http.to("/api/auth/register", "POST")).toHaveLength(1));
    expect(http.to("/api/auth/register")[0].body).toMatchObject({ dailyGoalMinutes: 10 });
  });
});
