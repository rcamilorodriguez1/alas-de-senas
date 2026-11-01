import type { RouteObject } from "react-router";
import { LoginPage } from "../features/auth/LoginPage";
import { AchievementsPage } from "../features/gamification/AchievementsPage";
import { RegisterPage } from "../features/auth/RegisterPage";
import { LearnPage } from "../features/learn/LearnPage";
import { LessonPage } from "../features/lesson/LessonPage";
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
  {
    path: "/leccion/:lessonId",
    element: (
      <RequireAuth>
        <LessonPage />
      </RequireAuth>
    ),
  },
  {
    path: "/logros",
    element: (
      <RequireAuth>
        <AchievementsPage />
      </RequireAuth>
    ),
  },
  { path: "*", element: <NotFoundPage /> },
];
