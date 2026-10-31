import type { RouteObject } from "react-router";
import { LoginPage } from "../features/auth/LoginPage";
import { RegisterPage } from "../features/auth/RegisterPage";
import { LearnPage } from "../pages/LearnPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { RootRedirect } from "../pages/RootRedirect";
import { GuestOnly, RequireAuth } from "./guards";

export const appRoutes: RouteObject[] = [
  { path: "/", element: <RootRedirect /> },
  {
    path: "/ingresar",
    element: (
      <GuestOnly>
        <LoginPage />
      </GuestOnly>
    ),
  },
  {
    path: "/registro",
    element: (
      <GuestOnly>
        <RegisterPage />
      </GuestOnly>
    ),
  },
  {
    path: "/aprender",
    element: (
      <RequireAuth>
        <LearnPage />
      </RequireAuth>
    ),
  },
  { path: "*", element: <NotFoundPage /> },
];
