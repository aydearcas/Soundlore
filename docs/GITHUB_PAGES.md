# Publicar Music Thesaurus en GitHub Pages

El visor es un sitio estático. El repositorio ya incluye sus datos JSON y un flujo
de GitHub Actions que los valida y publica. No hace falta contratar un servidor,
configurar claves ni instalar dependencias para el primer despliegue.

## 1. Crear y subir el repositorio

1. Crea un repositorio en GitHub, por ejemplo `music-thesaurus`. Puedes usar otro nombre.
2. Usa `main` como rama principal. El flujo también contempla `master`.
3. Sube **el contenido** de `music-thesaurus-github` a la raíz del repositorio.
   Deben verse `README.md`, `.github/`, `build/`, `concepts/`, `genres/`, `sources/`
   y `viewer/` directamente, sin una carpeta contenedora adicional.
4. Incluye la carpeta oculta `.github` y los archivos `.gitignore` y `.gitattributes`.
   En el Explorador de Windows puedes mostrar los elementos ocultos. GitHub Desktop
   permite añadir la carpeta completa sin omitir estos archivos.

No subas `dist/`, entornos virtuales ni cachés de Python: `.gitignore` los excluye
si utilizas Git o GitHub Desktop. La web de subida manual no aplica `.gitignore`.

## 2. Activar Pages

1. En el repositorio, abre **Settings → Pages**.
2. En **Build and deployment → Source**, selecciona **GitHub Actions**.
3. Abre la pestaña **Actions** y el flujo **Publish Music Thesaurus to GitHub Pages**.
4. Si la primera ejecución falló porque Pages aún no estaba activado, pulsa
   **Re-run all jobs**, o **Run workflow** en la rama `main`.
5. Cuando termine, el despliegue mostrará la URL. Para un repositorio normal será
   `https://TU_USUARIO.github.io/NOMBRE_DEL_REPOSITORIO/`.

El sitio abre directamente el visor; no necesitas añadir `/viewer/` a esa URL.
Las rutas de datos son relativas y funcionan aunque cambies el nombre del repositorio.

Documentación oficial:
[flujos personalizados de GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

## Probarlo en tu ordenador

Con Python 3.10 o posterior, desde la raíz del proyecto:

```sh
python build/package.py
python -m http.server 8000 --directory dist
```

Abre [http://localhost:8000/](http://localhost:8000/). Detén el servidor con Ctrl+C.
Para simular la ruta de un repositorio, también puedes servir la carpeta superior
y abrir `/music-thesaurus-github/viewer/`.

No abras `index.html` directamente con doble clic: el visor necesita HTTP para
cargar los archivos JSON.

## Actualizar el contenido

- Cambios en la interfaz: edita `viewer/index.html`, prueba y sube el archivo.
- Cambios en conceptos o perfiles: edita `concepts/*.txt` o `genres/profiles_*.txt`
  y reconstruye los datos:

```sh
python -m venv .venv
```

Activa el entorno en PowerShell con `.venv\Scripts\Activate.ps1`, o en macOS/Linux
con `source .venv/bin/activate`. Después:

```sh
python -m pip install -r requirements.txt
python build/package.py --rebuild
```

Sube los archivos fuente modificados y los JSON actualizados de `build/` y `viewer/`
que Git no excluya. `--rebuild` vuelve a generar el mapa, por lo que necesita las
dependencias y puede tardar. El despliegue normal usa los JSON ya incluidos;
no vuelve a calcular la taxonomía ni el mapa en GitHub.

Cada subida a `main` o `master` publica una nueva versión. Los pull requests
ejecutan la validación sin publicar. El directorio `sources/` contiene referencias
y debe conservarse sin cambios durante estas tareas.

## Si aparece un error

- **404 al abrir la web:** comprueba que Pages use GitHub Actions y que el último
  despliegue haya terminado correctamente. Usa la URL que muestra Pages.
- **No aparece el flujo:** comprueba que exista `.github/workflows/pages.yml`
  en la raíz del repositorio y que Actions esté habilitado.
- **No cargan los datos:** comprueba que los seis JSON de `viewer/` estén subidos;
  ejecuta `python build/validate_site.py` para validar sus referencias.
- **Falla Configure Pages:** activa Pages en Settings y vuelve a ejecutar el flujo.
