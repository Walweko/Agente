# 漫画 Translator — Agente de Traducción de Manga

Aplicación web local que busca manga en **MangaDex**, extrae el texto de los globos con OCR (NVIDIA Nemotron) y lo traduce al español con NVIDIA Riva, mostrando la comparativa original/traducido en el navegador.

---

## Requisitos

- Python 3.10 o superior
- Una cuenta en [build.nvidia.com](https://build.nvidia.com) para obtener la API key
- Conexión a internet (para MangaDex y las APIs de NVIDIA)

---

## Instalación

### 1. Clona 

```bash
git clone https://github.com/tu-usuario/manga-translator.git

```

O descarga el ZIP y extráelo en una carpeta.

### 2. Crea un entorno virtual (recomendado)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Instala las dependencias

```bash
pip install -r requirements.txt
```

### 4. Obtén tu API key de NVIDIA

1. Ve a [build.nvidia.com](https://build.nvidia.com) e inicia sesión (o crea una cuenta gratuita).
2. En tu perfil, ve a **API Keys** y genera una nueva key.
3. Cópiala — empieza con `nvapi-`.

### 5. Crea el archivo `.env`

El repositorio incluye `.env.example` como plantilla. Cópialo y renómbralo:

```bash
# macOS / Linux
cp .env.example .env

# Windows (PowerShell)
Copy-Item .env.example .env
```

Luego ábrelo y reemplaza el valor de la key:

```
NVIDIA_API_KEY=nvapi-tu-key-aqui
FLASK_PORT=5000
FLASK_DEBUG=false
```

> **Windows:** si el Explorador no te deja editar el archivo, ábrelo con:
> ```powershell
> notepad .env
> ```

---

## Estructura del proyecto

```
manga-translator/
├── App.py                  # Servidor Flask principal
├── requirements.txt        # Dependencias Python
├── .env.example            # Plantilla de configuración (sí se sube a GitHub)
├── .env                    # Tu API key real (NO subir a GitHub)
├── .gitignore
├── templates/
│   └── index.html          # Interfaz web
└── core/
    ├── __init__.py
    ├── mangadex.py         # Búsqueda y descarga de páginas
    ├── ocr.py              # Extracción de texto con Nemotron
    ├── translator.py       # Traducción con NVIDIA Riva
    └── image_processor.py  # Renderizado de la imagen traducida
```

---

## Uso

### Arrancar el servidor

```bash
python App.py
```

Verás en la consola:

```
[ENV] ✅  NVIDIA_API_KEY cargada: nvapi-abc123...
Servidor corriendo en http://localhost:5000
```

Si ves `⚠️ NVIDIA_API_KEY vacía`, revisa el paso 5.

### Usar la aplicación

1. Abre el navegador en `http://localhost:5000`
2. Busca un manga por título en inglés (ej: `naruto`, `one piece`)
3. Selecciona un capítulo de la lista
4. Navega entre páginas con las flechas
5. Pulsa **Traducir página** y espera ~15–30 segundos
6. Verás la comparativa original (EN) / traducido (ES)
7. Descarga la imagen traducida con el botón **Descargar**

---

## Cómo funciona

```
Usuario → MangaDex API → descarga página
                              ↓
                    NVIDIA Nemotron OCR
                    (detecta globos de texto)
                              ↓
                    NVIDIA Riva Translate
                    (EN → ES)
                              ↓
                    Pillow (renderiza texto
                    traducido sobre la imagen)
                              ↓
                    Navegador muestra comparativa
```

---

## Notas

- El contenido está limitado a manga con clasificación `safe` y `suggestive` según MangaDex.
- La API key gratuita de NVIDIA tiene un límite de uso mensual. Revisa tu consumo en [build.nvidia.com](https://build.nvidia.com).
- Este proyecto es educativo y no está afiliado con MangaDex ni NVIDIA.
- **Nunca subas tu `.env` a GitHub.** El `.gitignore` incluido ya lo protege.
