import type { RouteObject } from "react-router";
import { LoginPage } from "../features/auth/LoginPage";
import { DictionaryPage } from "../features/dictionary/DictionaryPage";
import { SignPage } from "../features/dictionary/SignPage";
import { AchievementsPage } from "../features/gamification/AchievementsPage";
import { ProgressPage } from "../features/progress/ProgressPage";
import { ReviewPage } from "../features/review/ReviewPage";
import { RegisterPage } from "../features/auth/RegisterPage";
import { LearnPage } from "../features/learn/LearnPage";
import { IntroPage } from "../features/intro/IntroPage";
import { LessonPage } from "../features/lesson/LessonPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { RootRedirect } from "../pages/RootRedirect";
import { GuestOnly, RequireAuth } from "./guards";

export const appRoutes: RouteObject[] = [
  { path: "/", element: <RootRedirect /> },
  {
    path: "/bienvenida",
    element: (
      <GuestOnly>
        <IntroPage />
      </GuestOnly>
    ),
  },
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
    path: "/progreso",
    element: (
      <RequireAuth>
        <ProgressPage />
      </RequireAuth>
    ),
  },
  {
    path: "/repaso",
    element: (
      <RequireAuth>
        <ReviewPage />
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
  // El diccionario se ve sin iniciar sesión (R7.7).
  { path: "/diccionario", element: <DictionaryPage /> },
  { path: "/diccionario/:slug", element: <SignPage /> },
  { path: "*", element: <NotFoundPage /> },
];
