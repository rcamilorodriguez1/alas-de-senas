# 🎨 Alas de Señas — Mockups de interfaz

> Wireframes de baja/media fidelidad para implementar con **React + Tailwind + shadcn/ui**. Acompaña a `docs/especificacion.md`. Mobile-first: cada pantalla incluye versión escritorio y notas para móvil.

## 0. Guía visual

| Token | Valor | Uso |
|---|---|---|
| `primary` | `#10B981` verde esmeralda | Botones principales, nodos completados |
| `secondary` | `#06B6D4` turquesa | Enlaces, progreso |
| `accent` | `#7C3AED` morado | Logros, módulo actual |
| `nectar` | `#FACC15` amarillo | Néctar, nodos dorados |
| `flower` | `#EC4899` fucsia | Racha 🔥, favoritos |
| `locked` | `#CBD5E1` gris | Contenido bloqueado |
| `bg` | `#F8FAFC` | Fondo |
| `text` | `#0F172A` | Texto |

- Tipografía: **Nunito** (títulos, 700–800) · **Inter** (texto, 400–600).
- Bordes redondeados `rounded-2xl`; botones con sombra inferior "3D" estilo Duolingo (`border-b-4`).
- Tomi (colibrí): verde esmeralda con garganta fucsia y alas turquesa, animado con Lottie.

---

## 1. Módulo introductorio (antes del login)

```
┌──────────────────────────────────────────────────────────────┐
│  🐦 Alas de Señas                          [Ya tengo cuenta] │
├──────────────────────────────────────────────────────────────┤
│                    ● ● ● ○ ○ ○   (paso 3 de 6)               │
│                                                              │
│        ┌──────────────────────────────────┐                  │
│        │                                  │                  │
│        │      [ IMAGEN / GIF DE LA        │                  │
│        │        SEÑA "GRACIAS" ]          │                  │
│        │                                  │                  │
│        └──────────────────────────────────┘                  │
│                     GRACIAS                                  │
│     Mano abierta desde el mentón hacia adelante.             │
│                                                              │
│   (\  🐦  "¡Esta la vas a usar todos los días!"  )           │
│                                                              │
│        [ ← Anterior ]              [ Siguiente → ]           │
└──────────────────────────────────────────────────────────────┘
```
- Tras 6 tarjetas → mini-quiz (3 preguntas tipo "¿Qué significa esta seña?") → pantalla de logro "¡Primer aleteo! +10 XP" → **Login/Registro**.

---

## 2. Login / Registro

### 2.1 Escritorio
```
┌───────────────────────────────────────┬───────────────────────────────────────┐
│                                       │                                       │
│        ░░░░  Fondo degradado  ░░░░    │          Bienvenido de nuevo 👋       │
│        verde → turquesa               │                                       │
│                                       │   Correo electrónico                  │
│              🐦  (Tomi animado         │   ┌─────────────────────────────────┐ │
│                   volando)            │   │ camilo@correo.com               │ │
│                                       │   └─────────────────────────────────┘ │
│           ALAS DE SEÑAS               │   Contraseña                          │
│   "Aprende Lengua de Señas            │   ┌───────────────────────────── 👁 ┐ │
│    Colombiana a tu ritmo"             │   │ ••••••••                        │ │
│                                       │   └─────────────────────────────────┘ │
│   ✅ Módulo intro completado           │                    ¿Olvidaste tu      │
│   ✨ +10 XP te esperan al entrar       │                     contraseña?       │
│                                       │                                       │
│                                       │   ┌─────────────────────────────────┐ │
│                                       │   │        INICIAR SESIÓN           │ │
│                                       │   └─────────────────────────────────┘ │
│                                       │   ──────────────  o  ──────────────   │
│                                       │   ┌─────────────────────────────────┐ │
│                                       │   │  G  Continuar con Google        │ │
│                                       │   └─────────────────────────────────┘ │
│                                       │                                       │
│                                       │   ¿No tienes cuenta? Crear cuenta     │
└───────────────────────────────────────┴───────────────────────────────────────┘
```

### 2.2 Registro (pestaña "Crear cuenta")
```
┌───────────────────────────────────────┐
│          Crea tu cuenta 🐦            │
│  Nombre        [ Camilo            ]  │
│  Correo        [ camilo@correo.com ]  │
│  Contraseña    [ ••••••••       👁 ]  │
│                ▓▓▓▓▓░░ Segura         │
│                                       │
│  ¿Cuánto quieres practicar al día?    │
│  ( 5 min ) (●10 min) ( 15 ) ( 20 )    │
│                                       │
│  ☐ Acepto la política de tratamiento  │
│    de datos (Ley 1581 de 2012)        │
│                                       │
│  [         CREAR CUENTA          ]    │
│  ¿Ya tienes cuenta? Inicia sesión     │
└───────────────────────────────────────┘
```

### 2.3 Móvil y estados
- Móvil: el panel izquierdo se reduce a un encabezado con Tomi y el logo; el formulario ocupa el ancho completo.
- Errores en rojo bajo el campo ("Correo o contraseña incorrectos"); botón con spinner durante la carga; Tomi en modo `thinking` mientras carga y `sad` si hay error.

---

## 3. Pantalla principal (ruta de aprendizaje con todo el sistema)

### 3.1 Escritorio — layout de 3 columnas
```
┌────────────────┬──────────────────────────────────────────────┬─────────────────────────┐
│ 🐦 ALAS DE     │  🔥 5   ⭐ 1.240 XP   🌸 85 néctar   👤 Camilo ▾ │                         │
│    SEÑAS       ├──────────────────────────────────────────────┤  ┌───────────────────┐  │
│                │ ┌──────────────────────────────────────────┐ │  │ 🔥 Racha: 5 días   │  │
│ 🏠 Aprender ◀  │ │ MÓDULO 1 · Fundamentos de la LSC         │ │  │ L M M J V S D     │  │
│ 📖 Diccionario │ │ Saludos, cortesía y alfabeto  ▓▓▓▓░░ 62% │ │  │ ✔ ✔ ✔ ✔ ✔ ○ ○     │  │
│ 📷 Cámara beta │ └──────────────────────────────────────────┘ │  └───────────────────┘  │
│ 🔁 Repasar (8) │                                              │  ┌───────────────────┐  │
│ 📊 Progreso    │          Nodo 1 · Saludos                    │  │ 🎯 Meta diaria     │  │
│ 🏆 Logros      │               ( ✔ )  ← dorado ⭐              │  │ ▓▓▓▓▓▓░░ 7/10 min │  │
│ 🛍 Tienda      │                 │                            │  └───────────────────┘  │
│ ⚙ Perfil      │          Nodo 2 · Presentaciones              │  ┌───────────────────┐  │
│                │        ( 1 ✔ )─( 2 ✔ )─( 3 ▶ )─( 4 🔒 )      │  │ 🔁 Señas por       │  │
│                │                   ▲                          │  │    repasar: 8      │  │
│                │         ┌─────────────────────┐              │  │ [ REPASAR AHORA ]  │  │
│                │         │ Lección 3 · Practica│              │  └───────────────────┘  │
│                │         │ 3 señas · cámara 📷 │              │  ┌───────────────────┐  │
│                │         │ [  EMPEZAR  +15 XP ]│              │  │ 🏆 Próximo logro   │  │
│                │         └─────────────────────┘              │  │ "Aleteo constante"│  │
│                │                 │                            │  │ Racha de 7 días   │  │
│                │          Nodo 3 · Cortesía     ( 🔒 )         │  │ ▓▓▓▓▓░░ 5/7       │  │
│                │                 │                            │  └───────────────────┘  │
│                │          Nodo 4 · Alfabeto     ( 🔒 )         │                         │
│                │                                              │   (\ 🐦                 │
│                │  ┌──────────────────────────────────────────┐ │   "¡Solo te faltan 3    │
│                │  │ MÓDULO 2 · Personas y vida cotidiana 🔒  │ │    minutos para tu      │
│                │  │ Completa el Módulo 1 para desbloquear    │ │    meta, Camilo!"       │
│                │  └──────────────────────────────────────────┘ │                         │
│                │  MÓDULO 3 🔒   ·   MÓDULO 4 🔒                │                         │
└────────────────┴──────────────────────────────────────────────┴─────────────────────────┘
```

**Leyenda de nodos/lecciones:**
`( ✔ )` completado (verde) · `( ⭐ )` dorado (amarillo) · `( ▶ )` disponible/actual (morado, pulsando) · `( 🔒 )` bloqueado (gris).
Cada nodo se expande mostrando sus 4 lecciones: **1 Aprende · 2 Reconoce · 3 Practica · 4 Reto final**.

### 3.2 Móvil
```
┌──────────────────────────────┐
│ 🔥5   ⭐1.240   🌸85    👤    │
├──────────────────────────────┤
│ MÓDULO 1 · Fundamentos  62%  │
│ ▓▓▓▓▓▓░░░░                   │
│                              │
│          ( ⭐ ) Saludos       │
│              │               │
│       ( ▶ ) Presentaciones   │
│        1✔ 2✔ 3▶ 4🔒          │
│              │               │
│          ( 🔒 ) Cortesía      │
│              │               │
│          ( 🔒 ) Alfabeto      │
│                              │
│  🐦 "¡Vas volando!"           │
├──────────────────────────────┤
│ 🏠    📖    📷    📊    👤    │  ← barra inferior
└──────────────────────────────┘
```

---

## 4. Pantallas secundarias del sistema (referencia)

### 4.1 Pantalla de lección del nodo (diseño de actividades en columna)

> **Diseño oficial de la lección.** Una sola tarjeta centrada (máx. `max-w-2xl`), fondo blanco, borde gris suave `rounded-2xl`. Las actividades se apilan verticalmente y se separan con una línea `border-t`. Este formato reemplaza al estilo "una pregunta por pantalla".

```
┌──────────────────────────────────────────────────────────────┐
│ MÓDULO 1 · NODO 1 — LECCIÓN 2 · RECONOCE            +10 XP   │ ← etiqueta gris en mayúsculas; XP en verde
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░    Seña 1 de 3       │ ← barra de progreso verde
│ ┌──────────────────────────────────────────────────────────┐ │
│ │                                                          │ │
│ │        [ VIDEO DE PERSONA SEÑANTE · fondo azul ]         │ │
│ │                  (encuadre desde la cintura)             │ │
│ │                                                          │ │
│ │  ▶/⏸   🔁 Repetir    🐢 0.5x | 1x               ⛶        │ │ ← controles superpuestos abajo
│ └──────────────────────────────────────────────────────────┘ │
│                                                              │
│ Actividad 1. Observa la seña                          ✔      │
│ Reproduce el video; puedes pausarlo, repetirlo y             │
│ reducir su velocidad.                                        │
│ ──────────────────────────────────────────────────────────── │
│ Actividad 2. Selecciona el significado                       │
│ ¿Qué significa la seña que acabas de observar?               │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ ○  Buenos días                                           │ │
│ └──────────────────────────────────────────────────────────┘ │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ ●  Gracias                                   (seleccionada)│ │ ← borde verde al seleccionar
│ └──────────────────────────────────────────────────────────┘ │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ ○  ¿Cómo estás?                                          │ │
│ └──────────────────────────────────────────────────────────┘ │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ ○  Hasta luego                                           │ │
│ └──────────────────────────────────────────────────────────┘ │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │                  Comprobar respuesta                     │ │ ← gris deshabilitado hasta elegir
│ └──────────────────────────────────────────────────────────┘ │
│ ──────────────────────────────────────────────────────────── │
│ Actividad 3. Produce la seña                          🔒     │
│ Practica frente a la cámara y compara tu ejecución con       │
│ el video de referencia.                                      │
│ ──────────────────────────────────────────────────────────── │
│ Actividad 4. Usa lo aprendido                         🔒     │
│ Completa una conversación visual de dos o tres turnos,       │
│ aplicando las señas de la lección.                           │
└──────────────────────────────────────────────────────────────┘
```

#### Estados de la Actividad 2 (después de "Comprobar respuesta")
```
✔ Correcta:                                   ✖ Incorrecta:
┌─────────────────────────────────────┐       ┌─────────────────────────────────────┐
│ ●  Gracias                      ✔   │ verde │ ●  Hasta luego                  ✖   │ rojo
└─────────────────────────────────────┘       └─────────────────────────────────────┘
🐦 "¡Exacto! Así se dice gracias."            ┌─────────────────────────────────────┐
[        Continuar        ] (verde)           │ ○  Gracias                      ✔   │ verde (respuesta correcta)
                                              └─────────────────────────────────────┘
                                              🐦 "Casi. Mira de nuevo el movimiento
                                                  desde el mentón."  [Ver otra vez 🔁]
```

#### Actividad 3 expandida — Produce la seña
```
│ Actividad 3. Produce la seña                                 │
│ ┌──────────────────────────┐  ┌──────────────────────────┐   │
│ │  [ VIDEO DE REFERENCIA ]  │  │  [ TU CÁMARA + puntos    │   │
│ │       (en bucle)          │  │    de la mano ]          │   │
│ └──────────────────────────┘  └──────────────────────────┘   │
│ Resultado: GRACIAS ✔   Confianza ▓▓▓▓▓▓▓▓░ 84%               │
│ [ 📷 Activar cámara ]   [ Saltar: autoevaluarme ]             │
│ 🔒 Tu video no sale de tu dispositivo.                        │
```
- Sin cámara o con la seña no soportada por el modelo → **autoevaluación**: "¿Te salió igual al video?" `[Sí, me salió]` `[Necesito repasar]` (marca la seña para repaso).

#### Actividad 4 expandida — Usa lo aprendido (conversación visual)
```
│ Actividad 4. Usa lo aprendido                                │
│  ┌──────────────────┐                                        │
│  │ 🎥 Persona A:     │  (video: "¡Hola! ¿Cómo estás?")        │ ← burbuja izquierda
│  └──────────────────┘                                        │
│                         Tu respuesta:                        │
│                  ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│                  │ 🎥 Bien,  │ │ 🎥 Adiós  │ │ 🎥 Por    │      │ ← opciones en video
│                  │  gracias │ │          │ │  favor   │      │
│                  └──────────┘ └──────────┘ └──────────┘      │
│  Turno 1 de 3                                                │
```
- 2–3 turnos estilo chat; las respuestas elegidas aparecen como burbujas a la derecha.

#### Reglas de comportamiento
- Las actividades se **habilitan en secuencia**: la siguiente se activa (se quita el 🔒 y se hace scroll suave hacia ella) al completar la anterior. Las completadas muestran ✔.
- Cuando la lección tiene 2–3 señas, la tarjeta se repite por seña ("Seña 1 de 3"); la barra de progreso avanza por actividad completada.
- La Actividad 4 aparece **una sola vez al final** de la lección (no por cada seña) y usa todas las señas de la lección.
- "+10 XP" en el encabezado es el XP **estimado** de la lección; el valor real lo devuelve el servidor en la celebración.
- Móvil: misma columna a ancho completo, video en 16:9, botón "Comprobar respuesta" fijo en la parte inferior (`sticky bottom-0`).

#### Actividades activas según el tipo de lección

| Lección | Act. 1 Observa | Act. 2 Selecciona | Act. 3 Produce | Act. 4 Usa lo aprendido |
|---|---|---|---|---|
| 1 · Aprende | ✅ + descripción y ejemplo de uso | ✅ 1 pregunta de verificación | ✅ solo autoevaluación (opcional) | ➖ |
| 2 · Reconoce | ✅ | ✅ video→significado y significado→video | ➖ | ✅ conversación de 2 turnos |
| 3 · Practica | ✅ | ✅ + juego de memoria | ✅ cámara o autoevaluación | ✅ |
| 4 · Reto final | ➖ (video solo al fallar) | ✅ ejercicios mezclados de todo el nodo | ✅ | ✅ situación comunicativa de 3 turnos |

### 4.2 Diccionario y ficha
```
┌──────────────────────────────────────────────────────────────────┐
│ 📖 Diccionario LSC                                               │
│ ┌──────────────────────────────────────────────┐  [❤ Favoritos] │
│ │ 🔍 gracias                                    │                │
│ └──────────────────────────────────────────────┘                │
│ (Todas)(Saludos)(Familia)(Números)(Alimentos)(Animales)          │
│ (Emociones)(Lugares)(Alfabeto)                                   │
├──────────────────────────────────────────────────────────────────┤
│ ┌───────────────────────────┐  GRACIAS                     ❤     │
│ │                           │  Categoría: Expresiones cotidianas │
│ │    [ VIDEO DE LA SEÑA ]   │                                   │
│ │                           │  Significado: expresión de        │
│ │ ▶ Reproducir ⏸ Pausar     │  agradecimiento.                  │
│ │ 🔁 Repetir   🐢 Lento      │  Cómo se hace: …                  │
│ └───────────────────────────┘  Ejemplo: al recibir ayuda.       │
│                                                                  │
│ [ ✍ Practicar esta seña ]   [ 📚 Ir a la lección: M1 · N3 ]       │
└──────────────────────────────────────────────────────────────────┘
```

### 4.3 Reconocimiento por cámara (beta)
```
┌──────────────────────────────────────────────────────────────────┐
│ 📷 Reconocimiento de señas  (beta)        Modo: [Libre ▾|Práctica]│
├────────────────────────────────────────┬─────────────────────────┤
│ ┌────────────────────────────────────┐ │ Seña detectada:         │
│ │                                    │ │                         │
│ │   [ VIDEO DE LA WEBCAM con puntos  │ │     ✋  "A"              │
│ │     de la mano dibujados encima ]  │ │                         │
│ │                                    │ │ Confianza               │
│ │                                    │ │ ▓▓▓▓▓▓▓▓▓░ 92%          │
│ └────────────────────────────────────┘ │                         │
│  [ ▶ Iniciar cámara ]  [ ⏹ Detener ]   │ 🐦 "¡Esa A te quedó     │
│  🔒 Tu video no sale de tu dispositivo.│     perfecta!"          │
└────────────────────────────────────────┴─────────────────────────┘
```

### 4.4 Progreso
```
┌──────────────────────────────────────────────────────────────────┐
│ 📊 Mi progreso                                                   │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│ │ 18%      │ │ 1.240 XP │ │ 🔥 5 días │ │ 34 señas │              │
│ │ avance   │ │ total    │ │ (máx 12) │ │ aprendidas│             │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘              │
│ XP últimos 7 días  ▁▃▅▂▇▆▄                                       │
│ Resultados por unidad                                            │
│  M1 Fundamentos   ▓▓▓▓▓▓░░░  62%  · precisión 88%                │
│  M2 Personas      ░░░░░░░░░   0%  🔒                              │
│ Historial                                                        │
│  26 oct · M1-N2-L2 Reconoce · 90 pts · +19 XP                    │
│  25 oct · M1-N2-L1 Aprende  · 100 pts · +20 XP                   │
│ Señas por repasar (8)  [ Hola ][ Adiós ][ Nombre ] …  [REPASAR]  │
└──────────────────────────────────────────────────────────────────┘
```

### 4.5 Celebración al terminar lección
```
┌───────────────────────────────────┐
│          🎉  🐦  🎉               │
│      ¡Lección completada!         │
│  ┌────────┐ ┌────────┐ ┌───────┐  │
│  │ +19 XP │ │  90 %  │ │ 🔥 6  │  │
│  └────────┘ └────────┘ └───────┘  │
│  🏆 Nuevo logro: Aleteo constante │
│  🌸 +5 néctar                     │
│  [        CONTINUAR         ]     │
└───────────────────────────────────┘
```

---

## 5. Notas de implementación de los mockups

- Componentes clave: `TopStatsBar`, `SideNav`, `BottomNav` (móvil), `ModuleSection`, `NodeBubble`, `LessonPopover`, `RightPanel` (racha, meta, repaso, próximo logro), `Mascot`, `SignVideoPlayer`, `CelebrationModal`.
- El camino de nodos usa un zigzag vertical (desplazamiento horizontal alterno con `translate-x`).
- Al hacer clic en un nodo disponible se abre `LessonPopover` con la lección actual y el botón "EMPEZAR".
- Animaciones con Framer Motion: nodo actual con pulso suave; celebración con confeti (`canvas-confetti`).
- Respetar `prefers-reduced-motion` y contraste AA en todos los estados (el gris de bloqueado debe acompañarse del ícono 🔒, no solo color).
