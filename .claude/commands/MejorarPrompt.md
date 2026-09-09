Mejora inmediatamente la petición del usuario antes de ejecutarla.

Reglas:

1. Conserva intención, idioma, restricciones y nivel técnico; elimina ambigüedad,
   repetición y requisitos contradictorios.
2. Infiere detalles seguros desde el repositorio y declara los supuestos relevantes.
   No conviertas la mejora en un cuestionario previo.
3. Formula como máximo tres preguntas sólo si falta una decisión que cambiaría
   materialmente la arquitectura, los permisos, el costo o el resultado.
4. Si la petición consiste en crear, mejorar o diseñar una skill, usa
   `$skill-architect`: busca duplicados, genera la Creation Brief y transforma la
   idea en una skill probada.
5. Muestra primero `Prompt mejorado`. Si el usuario también pidió implementar o
   ejecutar, continúa de forma autónoma usando esa versión; no esperes una segunda
   confirmación salvo ante una decisión irreversible.
6. No inventes credenciales, resultados, estado saludable ni validaciones.

Petición original:

`$ARGUMENTS`
