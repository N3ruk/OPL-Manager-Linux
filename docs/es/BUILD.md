# Construcción y pruebas

[English](../BUILD.md) · [Inicio](../../README_ES.md)

## Requisitos

Para AppImage: Linux x86_64, Python 3.10+, `bwrap` con user namespaces, `tar`, `dpkg-deb` e Internet para la primera descarga. No se usa sudo del anfitrión ni pip global. `packaging/prepare_rootfs.py` crea una raíz Ubuntu Base 22.04 aislada e instala allí las bibliotecas. El archivo oficial se verifica por SHA256.

```sh
python3 packaging/prepare_rootfs.py
python3 packaging/build.py
```

`dist/` recibe DEB, AppImage, fuentes y `SHA256SUMS`. Ambos formatos usan el mismo runtime de aplicación incluido. Solo se empaquetan archivos públicos; se excluyen notas locales y paquetes antiguos.

## Dependencias

El DEB amd64 incluye todas las dependencias de la aplicación y solo declara `libc6 (>= 2.35)` del sistema. APT comprueba ese requisito; no necesita paquetes Python/Qt de la distribución. Instala en `/opt/opl-manager-linux`, con comando en `/usr/bin`, icono y menú.

AppImage incluye CPython 3.12.16, PyQt6 6.7.1, Qt 6.7.3, Pillow 11.3.0, LZ4, bibliotecas gráficas auxiliares, certificados y fuentes DejaVu. Descargas fijadas en `packaging/toolchain-lock.json` y `packaging/requirements-appimage.txt`; un hash incorrecto detiene la construcción. Las bibliotecas se resuelven contra Ubuntu 22.04, no contra el host. glibc, kernel, servidor gráfico y controladores GPU son del sistema. Las bibliotecas son dinámicas y sustituibles al extraer. Requiere glibc 2.35+ y admite ejecución sin FUSE.

## Comprobar

```sh
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen ./dist/OPL-Manager-Linux-1.0.0-x86_64.AppImage --appimage-extract-and-run --self-test
./dist/OPL-Manager-Linux-1.0.0-x86_64.AppImage --appimage-extract-and-run --version
(cd dist && sha256sum -c SHA256SUMS)
```

`--self-test` utiliza una biblioteca sintética temporal para identificación ISO, índices, LZ4, Pillow, VMC y temas Qt. No abre tu biblioteca ni contacta PS2/servidores de arte. Offscreen comprueba Qt sin escritorio visible; Xvfb comprueba además el plugin X11. GitHub Actions instala/prueba/purga el DEB en su runner desechable, nunca en tu estación.

[Licencias](../../THIRD_PARTY.md). Se fijan los runtimes, pero APT y las fechas de archivos pueden evolucionar; no se promete identidad binaria entre construcciones de fechas distintas.
