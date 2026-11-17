# Cajas, deudas y patrimonio

Todas las rutas usan el prefijo `/api/v1` y requieren `Authorization: Bearer <token>`.
Los registros pertenecen al usuario autenticado. No se acepta `user_id` del cliente.
Incluso un superadmin solo accede a sus propios datos financieros. Un registro ajeno
responde `404`. Las respuestas usan el sobre `ApiResponse` del proyecto.

Los importes se reciben como números o cadenas decimales, con un máximo de 18
dígitos y 2 decimales. Las respuestas los representan como cadenas para conservar
su precisión. La moneda es un código de tres letras mayúsculas, por defecto `PEN`.
Los resúmenes separan las monedas; no convierten ni suman soles con dólares.
Todas las listas admiten `page` y `page_size` (máximo 100).

## Cajas (`tills`)

Una caja representa una cuenta de banco, Yape, PayPal, efectivo, etc. Es permanente:
no tiene cierre, desactivación ni eliminación. Su moneda y saldo inicial quedan
fijos al crearla. Se puede cambiar su nombre y descripción.

| Método | Ruta | Uso |
| --- | --- | --- |
| POST / GET | `/tills` | Crear / listar cajas propias |
| GET / PATCH | `/tills/{id}` | Consultar / editar nombre y descripción |
| GET | `/tills/{id}/balance` | Saldo inicial, entradas, salidas y saldo disponible |
| GET | `/tills/summary` | Totales de todas las cajas, agrupados por moneda |
| POST / GET | `/tills/{id}/concepts` | Crear / listar conceptos de la caja |
| POST / GET | `/tills/{id}/movements` | Registrar / listar movimientos |

Crear una caja:

```json
{"name": "Yape", "currency": "PEN", "opening_balance": "150.00"}
```

Crear conceptos en esa caja:

```json
{"name": "Sueldo", "direction": "income"}
```

```json
{"name": "Alquiler", "direction": "expense"}
```

El tipo de movimiento se obtiene del concepto; el cliente no lo envía. Cada
concepto pertenece a una sola caja. No se repite nombre y dirección dentro de ella.

```json
{
  "concept_id": "<uuid del concepto>",
  "amount": "100.50",
  "occurred_on": "2026-11-16",
  "description": "Pago recibido"
}
```

`occurred_on` es opcional y usa la fecha del servidor si se omite. Los importes de
los movimientos siempre son positivos. El historial no se edita ni elimina.
La lista permite `direction`, `concept_id`, `date_from` y `date_to` inclusivas.

El saldo es `opening_balance + total_income - total_expense`. El resumen incluye
`net_savings = total_income - total_expense`, que puede ser negativo. El saldo
inicial no se cuenta como ingreso. Por ahora se permiten saldos negativos.

## Deudas y obligaciones (`debts`)

Registran alquiler, jardinería, nana u otros compromisos de pago. La frecuencia
puede ser `once`, `daily`, `weekly`, `monthly` o `yearly`. `interval` determina
cada cuántas unidades se repite: por ejemplo, `monthly` con `interval: 3` es trimestral.
Una deuda recurrente continúa sin límite hasta que el usuario la desactiva.

| Método | Ruta | Uso |
| --- | --- | --- |
| POST / GET | `/debts` | Crear / listar obligaciones propias |
| GET / PATCH | `/debts/{id}` | Consultar / actualizar obligación |
| POST / GET | `/debts/{id}/payments` | Pagar vencimiento / consultar historial |

```json
{
  "name": "Alquiler de casa",
  "amount": "1200.00",
  "currency": "PEN",
  "frequency": "monthly",
  "interval": 1,
  "first_due_date": "2026-11-30"
}
```

La consulta devuelve `next_due_date`. La lista se filtra con `is_active` y
`due_before` (inclusive). Se pueden editar `name`, `description`, `amount` e
`is_active`; las condiciones de recurrencia y moneda quedan fijas. Los cambios
de importe afectan a pagos futuros; el historial conserva los importes pagados.

Para pagar, envía el vencimiento pendiente y una caja con concepto de salida:

```json
{
  "till_id": "<uuid de tu caja>",
  "concept_id": "<uuid de un concepto expense de esa caja>",
  "due_date": "2026-11-30",
  "paid_on": "2026-11-30"
}
```

El pago registra el importe completo de la obligación. Caja y deuda deben tener
la misma moneda. `paid_on` es opcional y usa la fecha del servidor si se omite.
El pago, el movimiento de salida y el siguiente vencimiento se guardan en una
misma transacción. Repetir el mismo vencimiento responde `409` y no duplica gastos.

La renovación se realiza al registrar el pago. Un vencimiento atrasado permanece
pendiente; no se omiten cuotas. Los meses cortos respetan el día original: una
deuda del 31 de enero vence el 28 de febrero y luego el 31 de marzo. Una deuda
`once` queda completada e inactiva al pagarla.

Crear una obligación no genera una salida ni mueve dinero automáticamente.
No se conectan cuentas bancarias ni se realizan cargos reales. No hay pagos parciales
ni proceso en segundo plano en esta primera versión.

## Patrimonio (`inheritance`)

El nombre del módulo se conserva; contiene los bienes que el usuario declara a
su nombre. Cada bien tiene su valor actual y su estimación de valor de mercado,
ingresados por el usuario. No se realiza una tasación automática.

| Método | Ruta | Uso |
| --- | --- | --- |
| POST / GET | `/inheritance` | Crear / listar bienes propios |
| GET / PATCH / DELETE | `/inheritance/{id}` | Consultar / actualizar / eliminar bien |
| GET | `/inheritance/summary` | Cantidad y valores totales por moneda |

```json
{
  "name": "Departamento",
  "asset_type": "property",
  "currency": "PEN",
  "current_value": "250000.00",
  "market_value": "280000.00"
}
```

`asset_type` admite `property` (inmueble), `vehicle` (vehículo) y `other` (otro).
Con `other` se debe especificar `other_type`, por ejemplo `"Joyas"`.
Ambos valores deben ser no negativos. La lista permite filtrar por `asset_type`.
Se pueden actualizar nombre, descripción, tipo, detalle del tipo y ambos valores.
La moneda del bien queda fija. Registrar o actualizar bienes no crea movimientos
en las cajas. El resumen muestra patrimonio bruto declarado, sin restar deudas.

## Base de datos

Aplicar las migraciones antes de iniciar la API:

```powershell
alembic upgrade head
```

La revisión `a7d92c5e1048` crea `tills`, `till_concepts`, `till_movements`, `debts`,
`debt_payments` e `inheritance_assets`, después de la migración de documento y avatar.
Las rutas también están documentadas en `/docs`.

Los seis modelos financieros heredan de `Base` los permisos `read`, `create`,
`update` y `delete`. `alembic upgrade head` sincroniza esos 24 permisos en el
catálogo, incluso si todas las migraciones ya estaban aplicadas. No hace falta
generar otra revisión. La sincronización conserva permisos y asignaciones existentes.
El catálogo no agrega endpoints: las cajas siguen sin cierre ni eliminación.
Las rutas financieras mantienen la autenticación y la validación del propietario;
esta sincronización no asigna permisos automáticamente a los perfiles.
