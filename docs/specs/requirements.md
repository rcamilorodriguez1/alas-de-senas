# Requisitos — Alas de Señas

> **Spec-Driven Development · documento 1 de 3** (`requirements.md` → `design.md` → `tasks.md`).
> Describe **qué** debe hacer el sistema. Los criterios de aceptación usan el formato **EARS** en español:
> - **CUANDO** <evento> **ENTONCES** el sistema **DEBERÁ** <respuesta>
> - **MIENTRAS** <estado> el sistema **DEBERÁ** <respuesta>
> - **SI** <condición no deseada> **ENTONCES** el sistema **DEBERÁ** <respuesta>
> - El sistema **DEBERÁ** <requisito permanente>
>
> El detalle técnico completo está en `docs/especificacion.md` (especificación v3.3: backend, contenido y entrenamiento en Python; interfaz en React/TypeScript). Si hay contradicción, este archivo define el *qué* y la especificación define el *cómo*.

## Introducción

Alas de Señas es una plataforma web gamificada para aprender Lengua de Señas Colombiana (LSC), estilo Duolingo, con la mascota Tomi (un colibrí). Alcance de esta entrega: módulos 1 a 3 con contenido completo, Módulo 4 como «Próximamente», solo navegador de portátil o PC (ancho ≥ 1024 px).

## Glosario

| Término | Significado |
|---|---|
| Ruta | Módulos → nodos → lecciones (4 módulos × 4 nodos × 4 lecciones). |
| Lección | Aprende (L1), Reconoce (L2), Practica (L3), Reto final (L4). |
| Sesión de lección | Un intento de completar una lección; el servidor evalúa cada respuesta. |
| Día local | Fecha calendario en la zona horaria `America/Bogota`. |
| Slug | Identificador de la seña en minúsculas, sin tildes, con guiones (`buenos-dias`). |
| Vidas | Hasta 5 ❤️; se pierden con errores en lecciones Reconoce, Practica y Reto final. |
| Sesión de repaso | Ronda de preguntas sobre las señas vencidas, evaluada por el servidor. |

---

## Requisito 1 — Módulo introductorio

**Historia de usuario:** Como visitante, quiero ver unas señas básicas antes de registrarme, para entender de qué se trata la plataforma.

**Criterios de aceptación**
1. CUANDO un visitante sin sesión entra por primera vez a `/` ENTONCES el sistema DEBERÁ redirigirlo a `/bienvenida`, cuyo contenido se obtiene de un endpoint público.
2. El sistema DEBERÁ mostrar 6 tarjetas, cada una con el video en bucle de una seña, su palabra y un mensaje de Tomi.
3. CUANDO el visitante termina las tarjetas ENTONCES el sistema DEBERÁ mostrar un mini-quiz de 3 preguntas (video → elegir significado) con retroalimentación inmediata.
4. CUANDO termina el mini-quiz ENTONCES el sistema DEBERÁ guardar en el navegador que el intro fue completado y mostrar la pantalla de registro.
5. El sistema DEBERÁ mostrar en todo momento un botón «Ya tengo cuenta» que lleve a `/ingresar`.
6. CUANDO un usuario se registra habiendo completado el intro ENTONCES el sistema DEBERÁ otorgarle el logro «Primer aleteo» una sola vez.

## Requisito 2 — Registro e inicio de sesión

**Historia de usuario:** Como aprendiz, quiero crear una cuenta e iniciar sesión, para guardar mi progreso.

**Criterios de aceptación**
1. El registro DEBERÁ pedir nombre, correo, contraseña (8 a 72 bytes en UTF-8: unos 8 a 72 caracteres; las letras con tilde o ñ cuentan doble), meta diaria (5, 10, 15 o 20 minutos) y la aceptación obligatoria de la política de tratamiento de datos (Ley 1581 de 2012).
2. El sistema DEBERÁ guardar el correo sin espacios al inicio o al final y en minúsculas.
3. SI el correo ya está registrado ENTONCES el sistema DEBERÁ mostrar «Ya existe una cuenta con este correo».
4. SI las credenciales son incorrectas ENTONCES el sistema DEBERÁ mostrar «Correo o contraseña incorrectos», sin indicar cuál de los dos falló.
5. SI hay más de 5 intentos de inicio de sesión por minuto para el mismo correo desde la misma IP ENTONCES el sistema DEBERÁ rechazar los siguientes con el mensaje «Demasiados intentos, espera un minuto».
6. CUANDO el usuario recarga la página con una sesión válida ENTONCES el sistema DEBERÁ restaurarla sin mostrar el formulario de inicio de sesión.
7. CUANDO el usuario cierra sesión ENTONCES el sistema DEBERÁ invalidar su token de renovación.
8. El sistema DEBERÁ guardar las contraseñas cifradas y nunca en texto plano.

## Requisito 3 — Ruta de aprendizaje y desbloqueo

**Historia de usuario:** Como aprendiz, quiero ver mi ruta de módulos y nodos, para saber qué sigue y qué he logrado.

**Criterios de aceptación**
1. El sistema DEBERÁ mostrar los módulos en orden, cada uno con sus 4 nodos y su porcentaje de avance. El alfabeto manual DEBERÁ enseñarse en dos nodos (A–M y N–Z) para que ninguna lección sea demasiado larga.
2. CUANDO un usuario nuevo abre la ruta ENTONCES solo la lección M1-N1-L1 DEBERÁ estar disponible.
3. CUANDO el usuario aprueba una lección ENTONCES la siguiente lección en el orden global DEBERÁ quedar disponible.
4. Una lección DEBERÁ considerarse aprobada con ≥ 60 % de aciertos, o ≥ 70 % si es Reto final.
5. CUANDO el usuario obtiene 100 % en un Reto final ENTONCES el nodo DEBERÁ mostrarse como dorado.
6. MIENTRAS un módulo no esté publicado el sistema DEBERÁ mostrarlo con el sello «Próximamente», sin bloquear otros módulos ni contarlo en los porcentajes.
7. CUANDO se agrega contenido nuevo al currículo ENTONCES las lecciones que el usuario ya aprobó DEBERÁN seguir aprobadas.
8. SI el usuario intenta abrir una lección bloqueada ENTONCES el sistema DEBERÁ rechazarla y mostrar «Esta lección aún está bloqueada».

## Requisito 4 — Lecciones y actividades

**Historia de usuario:** Como aprendiz, quiero lecciones cortas con video y ejercicios, para aprender cada seña paso a paso.

**Criterios de aceptación**
1. Cada lección DEBERÁ mostrarse como una tarjeta en columna con encabezado (módulo, nodo, lección, tipo, XP estimado, barra de progreso) y las actividades: 1. Observa la seña, 2. Selecciona el significado, 3. Produce la seña, 4. Usa lo aprendido.
2. Las actividades DEBERÁN habilitarse en secuencia; las completadas DEBERÁN mostrar ✔ y las pendientes 🔒.
3. El reproductor DEBERÁ permitir reproducir, pausar, repetir y cambiar entre velocidad normal y lenta (0,5x).
4. El sistema NO DEBERÁ enviar al navegador la respuesta correcta de un ejercicio antes de que el usuario responda, ni identificadores que permitan deducirla (las opciones usan tokens opacos y los videos rutas que no contienen la palabra).
5. CUANDO el usuario pulsa «Comprobar respuesta» ENTONCES el sistema DEBERÁ indicar si es correcta, marcar la opción correcta y mostrar un mensaje de Tomi.
6. SI el usuario responde de nuevo un ejercicio ya respondido ENTONCES el sistema DEBERÁ conservar la evaluación del primer intento.
7. Las actividades «Produce la seña» y «Observa la seña» NO DEBERÁN sumar ni restar puntaje.
8. MIENTRAS la cámara no esté disponible o la seña no sea reconocible por el modelo, «Produce la seña» DEBERÁ ofrecer autoevaluación («Sí, me salió» / «Necesito repasar»).
9. CUANDO el usuario termina todos los ejercicios ENTONCES el sistema DEBERÁ calcular el resultado en el servidor y mostrar la celebración con puntaje, XP, néctar, racha y logros nuevos.
10. SI la solicitud de completar se envía más de una vez ENTONCES el sistema DEBERÁ devolver el mismo resultado sin otorgar recompensas de nuevo.
10a. SI se intenta completar una lección con ejercicios sin responder ENTONCES el sistema DEBERÁ rechazarlo con «Responde todos los ejercicios para terminar la lección».
10b. SI la sesión tiene más de 24 horas o el contenido de la lección cambió ENTONCES el sistema DEBERÁ indicar que la lección debe empezar de nuevo.
10c. Cada lección DEBERÁ tener al menos 4 ejercicios con puntaje.
11. CUANDO el usuario intenta salir con respuestas dadas ENTONCES el sistema DEBERÁ pedir confirmación.
12. SI un video no carga ENTONCES el sistema DEBERÁ mostrar «No pudimos cargar este video» con un botón para reintentar.
13. En pantallas de 1366×768 el video, la pregunta y el botón «Comprobar respuesta» DEBERÁN ser visibles sin desplazarse.
14. El sistema DEBERÁ permitir elegir opciones con las teclas 1 a 4 y comprobar/continuar con Enter.

## Requisito 5 — Gamificación

**Historia de usuario:** Como aprendiz, quiero ganar puntos, mantener una racha y desbloquear logros, para motivarme a practicar cada día.

**Criterios de aceptación**
1. CUANDO el usuario aprueba una lección ENTONCES el sistema DEBERÁ otorgar XP = base (10, o 20 en el reto) + bono de precisión (0–5) + bono perfecto (5 si obtuvo 100 %).
2. SI la lección ya había sido aprobada antes ENTONCES el XP DEBERÁ ser la mitad (redondeada hacia arriba).
3. SI el usuario no aprueba ENTONCES DEBERÁ recibir 0 XP, pero la lección DEBERÁ contar como actividad del día.
4. El sistema DEBERÁ otorgar 5 de néctar por lección aprobada y 10 adicionales la primera vez que aprueba el reto de un nodo.
5. La racha DEBERÁ aumentar en 1 el primer día local en que el usuario completa al menos una lección o una sesión de repaso, si el día local anterior también tuvo actividad.
6. CUANDO el usuario completa varias lecciones el mismo día local ENTONCES la racha DEBERÁ aumentar como máximo una vez.
7. SI el usuario no tuvo actividad uno o más días y tiene protectores suficientes ENTONCES el sistema DEBERÁ consumir un protector por día perdido y conservar la racha.
8. SI no tiene protectores suficientes ENTONCES la racha DEBERÁ reiniciarse a 1 en la siguiente actividad.
9. El usuario DEBERÁ poder comprar un protector de racha por 50 de néctar, con un máximo de 2 guardados; SI no le alcanza ENTONCES el sistema DEBERÁ mostrar «No tienes suficiente néctar».
10. El sistema DEBERÁ otorgar cada logro una sola vez, incluso ante solicitudes simultáneas.
11. El sistema DEBERÁ mostrar una barra de meta diaria con los minutos de práctica del día local.
12. Tomi DEBERÁ reaccionar con un estado de ánimo acorde (alegre, celebrando, triste suave, pensando, dormido) y nunca DEBERÁ regañar.
13. El usuario DEBERÁ tener hasta 5 vidas. CUANDO falla por primera vez un ejercicio con puntaje en una lección Reconoce, Practica o Reto final ENTONCES DEBERÁ perder 1 vida; las lecciones Aprende y el repaso NO DEBERÁN quitar vidas.
14. El sistema DEBERÁ recuperar 1 vida cada 4 horas hasta 5, sin depender de tareas programadas; también DEBERÁ dar 1 vida al completar un repaso con ≥ 80 % y permitir recargar las 5 por 30 de néctar.
15. SI el usuario no tiene vidas ENTONCES el sistema DEBERÁ impedirle empezar lecciones Reconoce, Practica o Reto final, indicarle cuándo recupera la siguiente y ofrecerle repasar, recargar o hacer lecciones Aprende. MIENTRAS haya una lección empezada, DEBERÁ poder terminarla aunque se quede sin vidas.
16. Las vidas NO DEBERÁN afectar el XP, el puntaje ni la aprobación, y DEBERÁ ser posible desactivarlas por configuración.

## Requisito 6 — Seguimiento del progreso y repaso

**Historia de usuario:** Como aprendiz, quiero ver mi avance y repasar lo que olvido, para no perder lo aprendido.

**Criterios de aceptación**
1. El sistema DEBERÁ mostrar el porcentaje de avance global y por módulo, el XP total, la racha y las señas aprendidas.
2. El sistema DEBERÁ mostrar un historial paginado (20 por página) con fecha, lección, puntaje y XP.
3. El sistema DEBERÁ mostrar los resultados por unidad: puntaje promedio y precisión por módulo y nodo.
4. CUANDO el usuario falla una seña o elige «Necesito repasar» ENTONCES la seña DEBERÁ programarse para repaso al día siguiente.
5. CUANDO acierta una seña ENTONCES su próximo repaso DEBERÁ espaciarse según los intervalos 1, 2, 4, 7, 15 y 30 días.
6. El sistema DEBERÁ ofrecer una sesión de repaso de hasta 15 señas pendientes; el repaso NO DEBERÁ otorgar XP.
7. El servidor DEBERÁ evaluar cada respuesta del repaso igual que en las lecciones (sin revelar la respuesta antes); el cliente NO DEBERÁ poder declarar sus propios aciertos.
8. SI no hay señas pendientes ENTONCES el sistema NO DEBERÁ iniciar un repaso (así no se puede repetir para inflar la racha o ganar vidas).

## Requisito 7 — Diccionario

**Historia de usuario:** Como aprendiz o visitante, quiero buscar una palabra y ver cómo se dice en LSC.

**Criterios de aceptación**
1. CUANDO el usuario busca una palabra ENTONCES el sistema DEBERÁ encontrarla sin importar mayúsculas, tildes ni signos (`GRACÍAS` → «Gracias»), conservando la diferencia entre `n` y `ñ`.
2. SI no hay resultados ENTONCES el sistema DEBERÁ sugerir palabras parecidas (por ejemplo, `grasias` → «Gracias»).
3. El sistema DEBERÁ permitir filtrar por categoría y DEBERÁ mostrar solo categorías que tengan señas.
4. La ficha DEBERÁ mostrar video con controles, significado, categoría, cómo se hace (o «Descripción en revisión»), ejemplo de uso y una práctica rápida.
5. La ficha DEBERÁ enlazar a la lección donde se enseña la seña; SI esa lección está bloqueada ENTONCES DEBERÁ indicarlo.
6. MIENTRAS el usuario tenga sesión, DEBERÁ poder guardar y quitar favoritos, y verlos en una sección propia.
7. El diccionario DEBERÁ ser accesible sin iniciar sesión (los favoritos requieren sesión).

## Requisito 8 — Reconocimiento por cámara (beta)

**Historia de usuario:** Como aprendiz, quiero hacer una seña frente a la cámara y saber si la estoy haciendo bien.

**Criterios de aceptación**
1. CUANDO el usuario activa la cámara ENTONCES el sistema DEBERÁ mostrar el video en espejo con los puntos de la mano dibujados encima.
2. El sistema DEBERÁ mostrar la seña detectada y su nivel de confianza solo si la confianza es ≥ 0,70 y la clase no es «NINGUNA».
3. El sistema NO DEBERÁ enviar ni guardar imágenes o video de la cámara; DEBERÁ mostrar el aviso «Tu video no sale de tu dispositivo».
3a. El reconocimiento del alfabeto DEBERÁ usarse solo con letras estáticas; las letras con movimiento DEBERÁN usar autoevaluación. Qué letras tienen movimiento DEBERÁ estar indicado en el contenido y confirmado por el intérprete.
4. SI el permiso de cámara es denegado, no hay cámara o está ocupada ENTONCES el sistema DEBERÁ mostrar un mensaje específico y ofrecer autoevaluación.
5. CUANDO el usuario sale de la pantalla de cámara ENTONCES el sistema DEBERÁ apagar la cámara.
6. MIENTRAS no exista un modelo entrenado, el sistema DEBERÁ funcionar en modo simulado sin errores.
7. Un administrador DEBERÁ poder recolectar muestras por letra (incluida «NINGUNA»), y exportarlas desde el navegador; el modelo DEBERÁ entrenarse con un script de Python a partir de esas muestras y exportarse a un formato que el navegador cargue.
8. Desde la primera semana, una prueba automática DEBERÁ comprobar que un modelo convertido desde Python carga en el navegador y da la misma salida (tolerancia 0,0001).

## Requisito 9 — Gestión de contenido

**Historia de usuario:** Como integrante del equipo de contenido, quiero cargar señas y videos sin programar.

**Criterios de aceptación**
1. El contenido DEBERÁ definirse en `content/curriculum.json`, `content/signs.csv`, `content/conversations.yaml` y `content/intro.json`.
2. CUANDO una seña no tiene video grabado ENTONCES el sistema DEBERÁ generar un video de relleno con la palabra escrita y la etiqueta «Video en preparación».
3. CUANDO se copia un video con el nombre del slug a `content/videos/raw/` y se ejecuta `alas content all` ENTONCES el sistema DEBERÁ normalizarlo y mostrarlo en la aplicación en lugar del de relleno, sin que el navegador siga mostrando la versión anterior guardada en caché.
4. SI el nombre de un video no coincide con ningún slug ENTONCES el sistema DEBERÁ indicar el slug más parecido.
5. SI el CSV tiene una codificación incorrecta (por ejemplo, «Ã¡») ENTONCES el sistema DEBERÁ rechazarlo con instrucciones para guardarlo como UTF-8.
6. SI un nodo no tiene la cantidad de señas permitida (5–9; números 5–10; alfabeto 12–16) ENTONCES la validación DEBERÁ fallar con un mensaje claro.
7. CUANDO se ejecuta la carga dos veces ENTONCES el resultado DEBERÁ ser el mismo, sin duplicar datos ni borrar el progreso de los usuarios.
8. Los ejercicios DEBERÁN generarse automáticamente y de forma determinista a partir del contenido, solo para los módulos publicados.
9. El nodo de alfabeto DEBERÁ incluir ejercicios de deletreo (ver la secuencia de letras y elegir la palabra) usando solo letras ya enseñadas.
10. El despliegue DEBERÁ incluir los videos procesados y saber cuáles son de relleno sin depender de archivos locales.
11. Si el alfabeto incluye dígrafos (CH, LL, RR), el sistema DEBERÁ soportarlos sin cambios de código.
12. CUANDO para una seña se copian una imagen (`slug.jpg`) o una secuencia de 2 a 4 imágenes (`slug__1.jpg`, `slug__2.jpg`…) en lugar de un video ENTONCES el sistema DEBERÁ convertirlas en un clip con el mismo formato que los videos, de modo que el resto de la aplicación funcione igual; SI la seña también tiene video ENTONCES DEBERÁ usarse el video.
13. MIENTRAS una seña se muestre con imágenes, el reproductor DEBERÁ indicarlo con la etiqueta «Secuencia de imágenes» y no ofrecer la velocidad lenta.

## Requisito 10 — Requisitos no funcionales

1. **Plataforma:** el sistema DEBERÁ funcionar en Chrome, Edge y Firefox en pantallas de 1280×720 a 1920×1080. SI el ancho es menor a 1024 px ENTONCES DEBERÁ mostrar el aviso «Alas de Señas está pensada por ahora para portátil o computador».
2. **Idioma:** todos los textos visibles DEBERÁN estar en español de Colombia.
3. **Rendimiento:** la carga inicial DEBERÁ tomar menos de 3 s en una conexión normal; las rutas de cámara y administración DEBERÁN cargarse solo cuando se visiten.
4. **Seguridad:** el token de acceso DEBERÁ vivir solo en memoria; el de renovación, en una cookie httpOnly del mismo origen, rotada en cada uso.
5. **Accesibilidad:** contraste AA, navegación por teclado, texto alternativo en videos, ícono + texto en estados bloqueados, respeto de «movimiento reducido».
6. **Calidad:** las reglas de negocio DEBERÁN tener cobertura de pruebas ≥ 95 %; el flujo principal DEBERÁ tener una prueba de extremo a extremo.
7. **Privacidad:** cumplimiento de la Ley 1581 de 2012.
8. **Integración continua:** CUANDO se sube código a GitHub ENTONCES las verificaciones de calidad DEBERÁN ejecutarse automáticamente.
9. **Demostración:** un comando DEBERÁ crear, con fechas relativas al día actual, un usuario de demostración con el módulo 1 completo, racha activa y repaso pendiente; NO DEBERÁ ejecutarse en producción sin autorización explícita.
