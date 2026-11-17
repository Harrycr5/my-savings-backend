# FastAPI Starter

Base reutilizable con usuarios, perfiles, permisos y sesiones. Python 3.12+ y PostgreSQL.
Comandos para **PowerShell**, desde la raíz del proyecto.

## 1. Preparar el entorno — solo la primera vez

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

Edita `.env`:

- `DATABASE_URL`: tu usuario, contraseña y nombre de base de PostgreSQL.
- `JWT_SECRET_KEY`: pega la clave que generó el último comando.
- `CORS_ORIGINS`: los orígenes de tu frontend, por ejemplo `["http://localhost:5173"]`.
- Mantén `DEBUG=false`.

## 2. Crear la base de datos

En pgAdmin, crea la base indicada en `DATABASE_URL`. Por ejemplo:

```sql
CREATE DATABASE my_savings;
```

PostgreSQL debe estar encendido. Alembic crea las tablas, no la base de datos.

## 3. Crear las tablas y los permisos

```powershell
python -m alembic upgrade head
```

Este paso va **antes de arrancar la API**. También crea el perfil predeterminado y
sincroniza los permisos. Puedes repetirlo: solo aplica las migraciones pendientes.

## 4. Crear tu superadmin — solo la primera vez

```powershell
python -m scripts.create_superadmin
```

Introduce sus datos y una contraseña de al menos 12 caracteres. El superadmin se crea
con `is_admin=true` y tiene acceso completo. Si ya existe, no necesitas crearlo nuevamente.

## 5. Arrancar la API

```powershell
python -m uvicorn app.main:app --reload
```

Abre **http://127.0.0.1:8000/docs** y entra desde **Authorize**.
Para detenerla: `Ctrl+C`.

## Para trabajar otro día

```powershell
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

## Después de actualizar el código

Detén la API y ejecuta, con el entorno activado:

```powershell
python -m pip install -r requirements-dev.txt
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

Conserva tu `.env`. Si aparece una tabla nueva, aplica su migración antes de usarla.

## Cuando agregues o cambies modelos

```powershell
python -m alembic revision --autogenerate -m "describe el cambio"
python -m alembic upgrade head
```

Revisa la migración generada antes de aplicarla. Los modelos del módulo deben estar
en `models.py` y su carpeta debe tener `__init__.py`. Los permisos se sincronizan con el upgrade.

## Pruebas

```powershell
python -m pytest -q
```

Las pruebas locales usan una base en memoria. GitHub Actions también prueba con PostgreSQL,
incluidas las migraciones y la renovación concurrente de tokens.

## Contraseñas y filtros

- `POST /auth/change-password`: con sesión, envía `current_password` y `new_password`.
- `POST /auth/forgot-password`: envía `email` para recibir un código de 6 dígitos.
- `POST /auth/reset-password`: envía `email`, `code` y `new_password`.

Todas las rutas llevan el prefijo `/api/v1`. La contraseña nueva requiere 12 caracteres.
Después del cambio se cierran las sesiones y debes iniciar sesión nuevamente.
Para recibir códigos, configura `SMTP_HOST`, `SMTP_FROM_EMAIL`, `SMTP_USERNAME` y
`SMTP_PASSWORD` en `.env` según tu proveedor. Puerto 587 usa STARTTLS; para 465,
usa `SMTP_USE_TLS=true`. Sin configurar SMTP, recuperación devuelve 503.

Los listados muestran sus filtros en Swagger: `search` es común a usuarios, perfiles
y permisos. Usuarios también admite `name`, `last_name`, `email`, `username`,
`profile_id`, `is_active` e `is_admin`. El frontend envía los filtros como parámetros
query; el backend valida y aplica los mismos filtros al listado y a su total.

Nombres, apellidos, descripciones y usernames nuevos se guardan en mayúsculas.
El login por username no distingue mayúsculas de minúsculas y admite cuentas antiguas.
Los correos, códigos y contraseñas conservan su formato; la contraseña sí distingue mayúsculas.

Redis queda para después; sesiones y códigos de recuperación usan PostgreSQL.
