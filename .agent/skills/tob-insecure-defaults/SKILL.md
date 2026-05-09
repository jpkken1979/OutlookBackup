---
name: tob-insecure-defaults
type: feature
description: "Detecta configuraciones inseguras por defecto en código. Plugin de Trail of Bits para identificar defaults peligrosos en crypto, auth, TLS, CORS, headers y más."
---

# Trail of Bits: Insecure Defaults Detection

Detecta configuraciones por defecto inseguras en código fuente.

## Categorías de Detección

### Criptografía
- Algoritmos débiles (MD5, SHA1 para hashing de passwords)
- Claves de cifrado cortas (< 2048 bits RSA, < 256 bits EC)
- Modos de cifrado inseguros (ECB mode)
- IVs/nonces estáticos o predecibles
- PRNG no criptográficos para seguridad

### Autenticación
- Passwords por defecto o vacíos
- Tokens/secrets hardcodeados
- Session timeout excesivo o ausente
- Falta de rate limiting en login
- Cookies sin flags `Secure`, `HttpOnly`, `SameSite`

### TLS/SSL
- Versiones TLS obsoletas (< 1.2)
- Cipher suites débiles
- Verificación de certificados deshabilitada
- `verify=False` en requests HTTP

### CORS
- `Access-Control-Allow-Origin: *` en APIs autenticadas
- Credentials con wildcard origin
- Methods/headers demasiado permisivos

### HTTP Headers
- Falta de `Content-Security-Policy`
- Falta de `X-Frame-Options`
- Falta de `Strict-Transport-Security`
- `X-Powered-By` expuesto

### Database
- Conexiones sin TLS
- Usuarios con permisos excesivos
- Debug mode habilitado en producción
- Logging de queries con datos sensibles

## Patterns por Lenguaje

### Python
```python
# ❌ INSECURO — verify deshabilitado
requests.get(url, verify=False)

# ❌ INSECURO — debug en producción
app = Flask(__name__)
app.run(debug=True, host="0.0.0.0")

# ❌ INSECURO — secret key hardcodeada
app.secret_key = "my-secret-key"

# ❌ INSECURO — CORS wildcard
CORS(app, origins="*", supports_credentials=True)

# ❌ INSECURO — hash débil para passwords
hashlib.md5(password.encode()).hexdigest()

# ✅ SEGURO
requests.get(url, verify=True)
app.run(debug=False, host="127.0.0.1")
app.secret_key = os.environ["SECRET_KEY"]
CORS(app, origins=["https://myapp.com"])
bcrypt.hashpw(password.encode(), bcrypt.gensalt())
```

### JavaScript/TypeScript
```typescript
// ❌ INSECURO — CORS wildcard
app.use(cors({ origin: "*", credentials: true }));

// ❌ INSECURO — JWT sin expiración
jwt.sign(payload, secret);  // sin { expiresIn }

// ❌ INSECURO — eval
eval(userInput);

// ✅ SEGURO
app.use(cors({ origin: "https://myapp.com" }));
jwt.sign(payload, secret, { expiresIn: "1h" });
```

### Docker
```dockerfile
# ❌ INSECURO — ejecutar como root
USER root

# ❌ INSECURO — latest tag
FROM node:latest

# ✅ SEGURO
FROM node:20-slim
RUN adduser --disabled-password appuser
USER appuser
```

## Checklist de Auditoría

- [ ] Crypto: algoritmos y longitudes de clave apropiadas
- [ ] Auth: sin credentials hardcodeados, timeouts configurados
- [ ] TLS: versión >= 1.2, verificación habilitada
- [ ] CORS: origins restrictivos, sin wildcard + credentials
- [ ] Headers: CSP, HSTS, X-Frame-Options presentes
- [ ] DB: conexiones cifradas, permisos mínimos
- [ ] Docker: no root, imagen base pinned
- [ ] Logging: sin datos sensibles en logs

## Integración con CI

```bash
# Usar con semgrep para detección automatizada
semgrep --config p/security-audit --config p/owasp-top-ten .
```

## Recursos

- [Trail of Bits Blog](https://blog.trailofbits.com/)
- [OWASP Security Misconfiguration](https://owasp.org/Top10/A05_2021-Security_Misconfiguration/)
- [CWE-1188: Insecure Default Initialization](https://cwe.mitre.org/data/definitions/1188.html)
