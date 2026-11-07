# Calendario infinito — día de la semana

Aplicación **Django** para obtener el día de la semana de fechas escritas en distintos idiomas, incluyendo años extraordinariamente grandes (de hasta 10 000 cifras) que no caben en `datetime`.

## Características

- Entradas como `14 de febrero de 2011`, `14-3-2015`, `14/3/2015`, `2015-03-14`, `March 14, 2015`, `14 mars 2015`, `14 марта 2015`, `2015年3月14日`, `١٤ مارس ٢٠١٥`.
- Meses en cientos de idiomas, según los datos CLDR de Babel. Resultados localizados mediante el mismo conjunto de datos.
- Detección automática aproximada del idioma de la fecha textual. El idioma del resultado se puede fijar escribiendo cualquier código local de Babel (por ejemplo `es`, `en`, `gl`, `ca`, `pt_BR`, `zh_Hans`). Sin mes textual se utiliza `Accept-Language` del navegador y, si no existe, español.
- Orden numérico configurable: DMY, MDY o YMD. Para fechas ambiguas se utiliza **DMY por defecto**, salvo la configuración `en_US`, en cuyo caso MDY. Las fechas con año al principio de al menos cuatro cifras se reconocen automáticamente como YMD. Las fechas con año de dos cifras siguen el pivote 00–68 → 2000–2068; 69–99 → 1969–1999.
- Calendario **gregoriano proléptico** (aunque no se usase históricamente en un país concreto), desde el año 1. No se admite año 0 ni años negativos. No es un calendario juliano.
- **Sin base de datos ni almacenamiento de fechas**. Formularios con protección CSRF; salida HTML escapada.

La descripción «cualquier formato/idioma» se entiende como una aspiración de compatibilidad amplia, no como una garantía sobre cualquier oración o convención local imaginable. Se validan los días y los años bisiestos, y una fecha ilegible genera un error descriptivo.

## Ejecución sin Docker

Requisitos: **Python 3.11–3.13**.

```bash
git clone https://github.com/rodrigosambadesaa/dia-de-la-semana.git
cd dia-de-la-semana
python -m venv .venv
source .venv/bin/activate             # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
DJANGO_DEBUG=1 python manage.py runserver   # Windows PowerShell: $env:DJANGO_DEBUG='1'; python manage.py runserver
```

Abrir http://127.0.0.1:8000/. Para ejecutar sin depuración con Gunicorn (Linux/macOS):

```bash
export DJANGO_SECRET_KEY='sustituir-por-una-clave-aleatoria-segura'
python manage.py collectstatic --noinput
gunicorn calendar_site.wsgi:application --bind 127.0.0.1:8000
```

## Ejecución con Docker

```bash
docker compose up --build -d
# Abrir http://127.0.0.1:8000/
docker compose down
```

La configuración de Compose vincula el puerto exclusivamente a **localhost**. Para una implementación pública real, configure una clave secreta segura (`DJANGO_SECRET_KEY`), los dominios permitidos (`DJANGO_ALLOWED_HOSTS`), HTTPS y un proxy inverso. La aplicación no tiene cuentas de usuario ni base de datos. La imagen funciona como usuario no privilegiado.

## Pruebas

```bash
pip install -r requirements-dev.txt
ruff check .
DJANGO_DEBUG=1 python manage.py check
DJANGO_DEBUG=1 python manage.py test
```

GitHub Actions ejecuta pruebas en Python 3.11, 3.12 y 3.13, realiza el lint y compila/arranca la imagen Docker con comprobación HTTP.

## Cómo se calculan los años enormes

El calendario gregoriano repite su patrón de días semanales cada **400 años** (= 146 097 días, exactamente 20 871 semanas). Por ello se calcula el año **módulo 400** directamente a partir de sus cifras, sin convertirlo a un entero de tamaño limitado. Esta regla es exacta para cualquier año positivo dentro del calendario gregoriano proléptico, sea `2015`, `100000000000000000000` o un número de 10 000 cifras. El tamaño máximo de entrada es una medida práctica contra abuso de recursos del servidor, no un límite matemático.
