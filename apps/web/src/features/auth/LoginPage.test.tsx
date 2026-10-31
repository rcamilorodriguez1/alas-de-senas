import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useSessionStore } from "../../lib/session-store";
import {
  bearer,
  deferred,
  errorBody,
  jsonResponse,
  makeAuth,
  makeUser,
  mockFetch,
} from "../../test/http";
import { LoginPage } from "./LoginPage";

function renderLogin(entry = "/ingresar") {
  const router = createMemoryRouter(
    [
      { path: "/ingresar", element: <LoginPage /> },
      { path: "/aprender", element: <p>Ruta de aprendizaje</p> },
      { path: "/leccion/:lessonId", element: <p>Pantalla de lección</p> },
      { path: "/registro", element: <p>Página de registro</p> },
    ],
    { initialEntries: [entry] },
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

async function fillAndSubmit(email: string, password: string) {
  const user = userEvent.setup();
  if (email !== "") await user.type(screen.getByLabelText("Correo"), email);
  if (password !== "") await user.type(screen.getByLabelText("Contraseña"), password);
  await user.click(screen.getByRole("button", { name: "Ingresar" }));
  return user;
}

const okLogin = () => jsonResponse(200, makeAuth("token-login", makeUser({ name: "Ana" })));

beforeEach(() => {
  useSessionStore.setState(useSessionStore.getInitialState(), true);
  useSessionStore.getState().clearSession();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("LoginPage: estructura", () => {
  it("tiene los campos «Correo» y «Contraseña», el botón «Ingresar» y el enlace a registro", () => {
    mockFetch(okLogin);
    renderLogin();
    expect(screen.getByLabelText("Correo")).toBeInTheDocument();
    const password = screen.getByLabelText("Contraseña");
    expect(password).toHaveAttribute("type", "password");
    expect(screen.getByRole("button", { name: "Ingresar" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Crear una cuenta" })).toHaveAttribute(
      "href",
      "/registro",
    );
  });
});

describe("LoginPage: validación en el cliente", () => {
  it("con todo vacío muestra «Correo no válido» y «Escribe tu contraseña» sin llamar a la API", async () => {
    const http = mockFetch(okLogin);
    renderLogin();
    await fillAndSubmit("", "");
    expect(await screen.findByText("Correo no válido")).toBeInTheDocument();
    expect(screen.getByText("Escribe tu contraseña")).toBeInTheDocument();
    expect(http.requests).toHaveLength(0);
  });

  it("con un correo inválido muestra «Correo no válido»", async () => {
    const http = mockFetch(okLogin);
    renderLogin();
    await fillAndSubmit("ana@", "secreta123");
    expect(await screen.findByText("Correo no válido")).toBeInTheDocument();
    expect(screen.queryByText("Escribe tu contraseña")).not.toBeInTheDocument();
    expect(http.requests).toHaveLength(0);
  });

  it("con la contraseña vacía muestra «Escribe tu contraseña»", async () => {
    const http = mockFetch(okLogin);
    renderLogin();
    await fillAndSubmit("ana@example.com", "");
    expect(await screen.findByText("Escribe tu contraseña")).toBeInTheDocument();
    expect(screen.queryByText("Correo no válido")).not.toBeInTheDocument();
    expect(http.requests).toHaveLength(0);
  });
});

describe("LoginPage: errores del servidor", () => {
  it("R2.4: 401 → «Correo o contraseña incorrectos» como alerta, sin abrir sesión ni navegar", async () => {
    const http = mockFetch(() =>
      jsonResponse(401, errorBody(401, "INVALID_CREDENTIALS", "Correo o contraseña incorrectos")),
    );
    const router = renderLogin();
    await fillAndSubmit("ana@example.com", "incorrecta");
    expect(await screen.findByRole("alert")).toHaveTextContent("Correo o contraseña incorrectos");
    expect(router.state.location.pathname).toBe("/ingresar");
    expect(useSessionStore.getState().status).toBe("anonymous");
    expect(http.to("/api/auth/refresh")).toHaveLength(0);
  });

  it("R2.5: 429 → «Demasiados intentos, espera un minuto»", async () => {
    mockFetch(() =>
      jsonResponse(
        429,
        errorBody(429, "TOO_MANY_REQUESTS", "Hiciste demasiadas peticiones. Espera un momento."),
      ),
    );
    renderLogin();
    await fillAndSubmit("ana@example.com", "secreta123");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Demasiados intentos, espera un minuto",
    );
  });
});

describe("LoginPage: éxito", () => {
  it("envía {email, password} sin Authorization, abre la sesión y va a /aprender", async () => {
    const http = mockFetch(okLogin);
    const router = renderLogin();
    await fillAndSubmit("ana@example.com", "secreta123");
    await waitFor(() => expect(router.state.location.pathname).toBe("/aprender"));
    const request = http.to("/api/auth/login", "POST")[0];
    expect(request.body).toEqual({ email: "ana@example.com", password: "secreta123" });
    expect(bearer(request)).toBeNull();
    expect(useSessionStore.getState().status).toBe("authenticated");
    expect(useSessionStore.getState().accessToken).toBe("token-login");
  });

  it("con ?volver=/leccion/... vuelve a esa ruta", async () => {
    mockFetch(okLogin);
    const router = renderLogin("/ingresar?volver=%2Fleccion%2FM1-N1-L2");
    await fillAndSubmit("ana@example.com", "secreta123");
    await waitFor(() => expect(router.state.location.pathname).toBe("/leccion/M1-N1-L2"));
    expect(screen.getByText("Pantalla de lección")).toBeInTheDocument();
  });

  it("ignora volver que empieza por «//» (redirección abierta) y va a /aprender", async () => {
    mockFetch(okLogin);
    const router = renderLogin("/ingresar?volver=%2F%2Fevil.example.com");
    await fillAndSubmit("ana@example.com", "secreta123");
    await waitFor(() => expect(router.state.location.pathname).toBe("/aprender"));
  });

  it("ignora volver con URL absoluta y va a /aprender", async () => {
    mockFetch(okLogin);
    const router = renderLogin("/ingresar?volver=https%3A%2F%2Fevil.example.com%2F");
    await fillAndSubmit("ana@example.com", "secreta123");
    await waitFor(() => expect(router.state.location.pathname).toBe("/aprender"));
  });

  it("doble envío: mientras se espera la respuesta, un segundo clic no repite el login", async () => {
    const gate = deferred<Response>();
    const http = mockFetch(() => gate.promise);
    const router = renderLogin();
    const user = await fillAndSubmit("ana@example.com", "secreta123");
    await waitFor(() => expect(http.to("/api/auth/login")).toHaveLength(1));
    await user.click(screen.getByRole("button", { name: "Ingresar" }));
    gate.resolve(okLogin());
    await waitFor(() => expect(router.state.location.pathname).toBe("/aprender"));
    expect(http.to("/api/auth/login")).toHaveLength(1);
  });
});
