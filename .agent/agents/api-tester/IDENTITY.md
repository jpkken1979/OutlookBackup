# api-tester

- **Tier:** quality
- **Description:** Prueba endpoints API y reporta status, latencia y errores

## Capacidades

- Acepta URL directa o auto-detecta desde código del proyecto
- Prueba endpoints comunes: /, /health, /v1/, /api/, etc.
- Mide tiempo de respuesta por endpoint
- Verifica status codes, content-type y headers CORS
- Genera reporte con status, latencia y errores via LLM

## Uso

```bash
python scripts/main.py "test http://127.0.0.1:4747"
python scripts/main.py "probar API del proyecto"
```

## Herramientas requeridas (opcionales)

- Ninguna externa — usa `urllib` de la stdlib de Python

Si no se proporciona URL y no se detecta ninguna en el código, reporta error descriptivo.
