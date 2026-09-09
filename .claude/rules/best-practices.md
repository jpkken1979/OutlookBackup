# Regla: buenas prácticas

- Entender contrato, consumidores y tests antes de modificar.
- Mantener cambios estrechos, reversibles y verificables.
- No duplicar capacidades del runtime, Nexus o broker.
- Usar tipos precisos en APIs nuevas; no inventarlos para silenciar checks.
- Validar entradas, paths y payloads en los límites.
- No introducir datos falsos o fallback silencioso en producción.
- Corregir generadores y plantillas antes que sus copias.

## Verificación

- Probar comportamiento y regresiones, no detalles accidentales.
- Ejecutar primero el gate estrecho y después la suite de la superficie.
- Leer cobertura y umbrales de `.github/workflows/`; no asumir un porcentaje
  universal por módulo.
- Revisar el diff completo y preservar cambios ajenos.

## Seguridad

- No imprimir ni añadir secretos nuevos al historial.
- Evitar shell construida con datos no confiables.
- Sanitizar errores expuestos y aplicar permisos mínimos.
- Respetar la excepción histórica de `.env` de este repositorio sin mostrar su
  contenido; cualquier migración exige rotación y decisión del propietario.
