# Regla: seguridad del repositorio

- Nunca hardcodear, imprimir o documentar secrets, tokens o claves privadas.
- No añadir nuevos secretos al historial Git.
- `.env` es una excepción histórica intencional de este repo privado: no mostrar
  su contenido, copiarlo ni cambiar su política durante una tarea ajena. Sacarlo
  de Git requiere plan de migración, rotación y aprobación del propietario.
- Validar y normalizar entradas externas.
- Resolver y comprobar paths antes de I/O sensible, incluidos symlinks y reparse
  points.
- Evitar `shell=True` y concatenación de comandos con datos no confiables.
- Sanitizar errores que crucen límites de confianza.
- Aplicar autenticación, CORS y rate limiting según la exposición real.

## Tauri

- Validar inputs de comandos Rust y respuestas enviadas al renderer.
- Mantener capabilities y acceso filesystem en mínimo privilegio.
- No reintroducir instrucciones Electron/preload: Nexus activo es Tauri 2.

Antes de tocar credenciales, certificados, auth o distribución, leer la guía del
dominio y registrar PASS/SKIP sin revelar valores sensibles.
