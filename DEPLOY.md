# Despliegue de la plataforma

El proyecto de Vercel usa la raíz del repositorio. Compila Angular y sirve la interfaz y `/api` desde el mismo dominio con Flask. Flask lee y guarda los datos mediante la Data API del esquema `inmobiliaria` de Supabase.

## Preparar Supabase

1. Activa **Enable Data API** en Supabase.
2. Ejecuta [data_api.sql](backend/migrations/data_api.sql) en el **SQL Editor** del proyecto nuevo. El SQL crea las tablas y limita el acceso al esquema y a la función de importación a `service_role`.
3. En la configuración de la Data API, agrega `inmobiliaria` a **Exposed schemas**.
4. Guarda `SUPABASE_URL` y `SUPABASE_SECRET_KEY` en `backend/.env`. El siguiente comando copia las tablas, las relaciones, el historial y los documentos almacenados en SQLite. Ejecuta la copia cuando se hayan terminado las ediciones en la base local.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
python -m migrations.importar_data_api --sqlite instance/conciliacion.db
```

La importación verifica las cantidades por tabla en una transacción y requiere tablas vacías.

Si el proyecto de Supabase ya tiene los datos, continúa ejecutando [data_api_operaciones.sql](backend/migrations/data_api_operaciones.sql) en su **SQL Editor**. Esta segunda migración instala las funciones de lectura, escritura y descarga y conserva los registros existentes. Aplícala también en el proyecto de prueba que use Vercel Preview.

Flask usa una copia temporal de los datos en memoria para ejecutar cada solicitud de conciliación y guarda sus cambios en Supabase en una transacción. Si otra escritura cambió la revisión, la API devuelve HTTP 409. Actualiza la vista y vuelve a intentar la operación. Los binarios se consultan al descargar cada archivo.

## Configurar Vercel

1. Importa el repositorio privado o vincula el directorio raíz con Vercel CLI. Usa el preset **Flask** y deja los comandos de instalación y compilación en sus valores del repositorio. La compilación está comprobada con Python 3.12 y Node.js 22.
2. Configura estas variables en Vercel para cada entorno que vayas a usar.

   | Variable | Valor |
   | --- | --- |
   | `SUPABASE_URL` | URL HTTPS del proyecto Supabase. Usa un proyecto de prueba para Preview. |
   | `SUPABASE_SECRET_KEY` | Clave secreta del proyecto de Supabase para Flask. |
   | `APP_USERNAME` | Nombre de usuario para el acceso privado por HTTPS. |
   | `APP_PASSWORD` | Contraseña larga, única y compartida solo con los usuarios autorizados. |

3. Despliega desde la raíz. Abre `/api/health` para verificar el proceso Flask. Después abre la página principal, ingresa las credenciales y confirma que cargan los centros de costo, los gastos y las facturas. Prueba también la importación y descarga de un documento en Preview.

La base SQLite, sus respaldos, la carpeta de documentos locales y los archivos de entorno se excluyen del despliegue de código. Los datos existentes se transfieren únicamente mediante la importación a PostgreSQL.

Vercel Functions limita el cuerpo de las solicitudes y de las respuestas ordinarias a 4,5 MB. El límite aplica a las cargas multipart e incluye sus campos y encabezados. Los documentos actuales caben dentro del límite. [Límites de Vercel Functions](https://vercel.com/docs/functions/limitations)

## Desarrollo local

Desde `backend/`, ejecuta `python run.py` con la configuración SQLite habitual. Desde `frontend/`, ejecuta `npm start`. El proxy de Angular envía `/api` a Flask en el puerto 5001.

Para probar la Data API desde Flask local, agrega `USE_DATA_API=true` al `.env` y configura la URL y la clave del proyecto de prueba.
