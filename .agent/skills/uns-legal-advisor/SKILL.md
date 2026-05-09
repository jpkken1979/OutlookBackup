---
name: uns-legal-advisor
type: feature
description: "Asesoría legal especializada en regulaciones laborales japonesas para sistemas de dispatch (派遣). Cubre la Ley de Trabajo Temporal (派遣法), límites de horas 36協定, reglas de rotación de visas, compliance de empleados extranjeros, y regulaciones específicas de UNS-Kikaku. Use cuando verificando cumplimiento laboral, validando contratos de dispatch, calculando límites de horas, onboarding de trabajadores, o determinando regularidad legal de procesos de empleo."
source: uns
user-invocable: true
---

# UNS Legal Advisor: Asesoría Laboral Japonesa

Referencia completa de regulaciones laborales japonesas con enfoque en sistemas de dispatch (派遣) y consideraciones específicas de UNS-Kikaku.

## Marco Regulatorio Japonés

### 1. 派遣法 (Ley de Trabajo Temporal)

Define los derechos, limitaciones y obligaciones para trabajadores temporales (haken workers).

#### Límites de Plazo

| Tipo | Límite | Renovables | Notas |
|------|--------|-----------|-------|
| Acuerdo general | 3 años | Sí, hasta 6 años máximo | Para la mayoría de puestos |
| Pos. específicas | 1 año | Sí, indefinidamente | Ej: IT, contabilidad |
| Trabajador 60+ años | 5 años | Sí | Extensión para jubilados |

**Regla crítica**: Después de 3 años en el mismo rol, empresa debe:
- Ofrecer posición permanente, O
- Transferir a rol diferente, O
- Cesar contrato

### 2. 36協定 (36 Kyotei: Horas Extraordinarias)

Acuerdo colectivo que permite horas extras. SIN este acuerdo = NO horas extras permitidas.

#### Límites Mensuales

```
Máximo: 45 horas/mes en promedio
Máximo pico: 100 horas/mes (con aprobación especial)

Cálculo anual:
- Total máximo: 540 horas/año
- Promedio: 45 horas/mes

Ejemplo válido:
- Enero: 30 hrs | Febrero: 45 hrs | Marzo: 60 hrs | Abril-Dic: 45 hrs c/u
- Promedio: (30+45+60+45*9)/12 = 44.6 hrs (✓ cumple)

Ejemplo inválido:
- Enero-Diciembre: 50 hrs/mes
- Promedio: 50 hrs/mes (✗ excede 45 hrs)
```

#### Monitoreo 36協定

- [ ] 36協定 documento firmado y registrado
- [ ] Límite promedio 45 hrs/mes verificado mensualmente
- [ ] Alertas si trabajador se aproxima a 100 hrs/mes
- [ ] Auditoría trimestral de cumplimiento
- [ ] Revisión anual del acuerdo

### 3. 給与 (Remuneración) - Requisitos

```
Componentes de nómina (payroll):
- Sueldo base (必須: obligatorio)
- Bonificación (任意: opcional, pero si aplica todos deben recibir igual%)
- Horas extras: Mínimo 25% extra de tarifa horaria
- Ajustes por impuestos/seguros (自動 deducción)

Prohibido:
- ✗ Retener salario sin causa legal
- ✗ Pagar en especie sin acuerdo explícito
- ✗ Penalidades por uniforme, equipamiento
```

### 4. Extranjeros: Regulaciones Especiales

#### Visa Temporal de Trabajo (派遣 Specific)

```
Tipo: Haken Worker (dispatch contract worker)
Duración: Renovable, típicamente 1-3 años
Cambio de empleador: Requiere nuevo sponsor + aprobación migración

Límite crítico - 90 días:
- Si contrato termina con < 30 días aviso
- O trabajador es sin documentos
- → Multas ~300,000 yen para empleador
```

#### Puntos de Compliance para Extranjeros

- [ ] Visa válida y tipo correcto (trabajo temporal)
- [ ] Registro de impuestos (tax number asignado)
- [ ] Seguro nacional (Kokumin Kenko Hoken) - trabajador paga ~10%
- [ ] Fondo de pensiones (Kokumin Nenkin) - trabajador paga ~16,000 yen/mes
- [ ] Residencia registrada (Juki Net - dirección)
- [ ] No trabajar > 20 hrs/semana si estudiante (regla especial)
- [ ] Cambios de domicilio reportados en 14 días

### 5. Rotación de Trabajadores (UNS Policy)

```
Política UNS de 90 días para visa:
Si trabajador ha completado visa de 3 años:
- Requiere salida de Japón por mínimo 3-6 meses
- Permite "reset" de contador de dispatch

Documentación requerida:
- Prueba de salida (pasaporte con sello)
- Prueba de residencia fuera de Japón
- Nueva solicitud de visa a inmigración
- Nuevo contrato de dispatch con nuevo sponsor (si aplica)

Timeline:
- Mes 1 (salida): Trabajador sale, recibe documentación
- Mes 2-3: Fuera de Japón
- Mes 4: Solicita visa de retorno
- Mes 5: Regresa, nuevo contrato inicia
```

## Validación de Compliance

### Checklist de Onboarding

```
Antes de iniciar trabajo:

Documentation:
- [ ] Visa válida y fotocopia en archivo
- [ ] Número de trabajador registrado
- [ ] Contrato firmado (ambas partes, fechado)
- [ ] 36協定 document explicado
- [ ] Hoja de derechos/obligaciones en idioma trabajador

Configuración Payroll:
- [ ] Tarifa horaria + clasificación en sistema
- [ ] Tasa horas extra (125% mínimo)
- [ ] Deducción impuestos configurada
- [ ] Seguro nacional deducido (si aplica)
- [ ] Depósito bancario configurado

Safety & Orientation:
- [ ] Briefing de safety (especialmente para extranjeros)
- [ ] Reglas de workplace (horas, descansos, conducta)
- [ ] Supervisor asignado
- [ ] Emergency contact registrado
```

### Escenarios Comunes: Decisión Rápida

| Escenario | Pregunta | Respuesta | Acción |
|-----------|----------|-----------|--------|
| Trabajador pide 6 más hrs/sem | ¿ Cumple 36協定? | Ver límite en tabla | Sí si < 100 hrs/mes |
| Terminación después 3 años | ¿Permanente ofrecido? | No | ✗ Ilegal, ofrecer o pagar indemnización |
| Extranjero quiere cambiar employer | ¿Visa permite? | Requiere nuevo sponsor | ✗ Debe tramitar con inmigración |
| Trabajador enfermo, falta día | ¿Se deduce salario? | Depende de contrato | Sí si especificado, de otro modo no |
| Bonus sin documentación previa | ¿Es obligatorio? | Depende de acuerdo previo | Recomendación: Documentar política de bonus |

## Resumen de Riesgos por Tipo

| Riesgo | Severidad | Penalidad | Prevención |
|--------|----------|-----------|------------|
| Exceder 36協定 | Crítica | 6 meses prisión + multa 300K yen | Monitoreo mensual automático |
| Terminar sin alternativa (3 años) | Alta | Demanda laboral + reparación | Documentar oferta de permanencia |
| Visa vencida trabajando | Muy alta | Deportación + multa 1M yen | Auditoría trimestral de documentos |
| No pagar horas extra | Alta | Multa 300K yen + salarios atrasados | Sistema de payroll con auditoria |
| Sin 36協定 pero con horas extra | Crítica | Multa + responsabilidad penal | 36協定 firmado mes 1, antes de horas extra |

## Disclaimers Obligatorios

Siempre incluir:

> ⚠️ **IMPORTANTE**: Esta asesoría es información educativa, NO constituye asesoramiento legal profesional. Para cuestiones legales críticas, consultar con:
> - 労務士 (Labor attorney / Sharoushi)
> - Asociación de derechos del trabajador
> - Gobierno local (Haken Hakken Center)
>
> Responsabilidad: La empresa/empleador es responsable final de compliance.

## Referencias Oficiales

Autoridades a contactar:

```
- 厚生労働省 (MHLW - Ministry of Health, Labour & Welfare): www.mhlw.go.jp
- 総務省 (SOUMU - General Affairs Ministry): www.soumu.go.jp (tax)
- ハローワーク (Hello Work): Oficina local de empleo
- Inmigración (入管): Trámites de visa
- 労基署 (Labor Standards Office): Denuncias/auditoria
```

## Uso en Agentes UNS

Cuando un agente necesita validar compliance:

```python
# Pseudocódigo
if request == "validate_dispatch_contract":
    check:
        - dispatch_contract_duration <= 3_years
        - horas_extras_acordadas in 36_kyotei
        - trabajador_extranjero → visa_valida
        - salario >= minimum_wage
    return compliance_status + required_actions
```

Ver `docs/knowledge/KNOWLEDGE_LEGAL_JP.md` para referencia exhaustiva y ejemplos de casos reales.

Co-Authored-By: UNS Legal Team
