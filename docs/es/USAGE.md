# Uso y resolución de problemas

[English](../USAGE.md) · [Inicio](../../README_ES.md)

## Bibliotecas y archivos

Selecciona la raíz OPL o DVD/CD/POPS. La aplicación utiliza la raíz común, respeta carpetas en minúsculas y ofrece crear DVD/CD/ART/CFG/CHT/VMC/POPS si faltan. Las imágenes sueltas se catalogan, pero no se mueven. Revisa los avisos antes de renombrar, convertir o indexar.

El nombre clásico permite hasta 32 bytes de título. Los nombres modernos evitan esa restricción, pero los índices siguen teniendo límites de nombre. Se rechazan colisiones y rutas inseguras. VCD obtiene el ID del nombre, sin inspección interna. UL se lee desde `ul.cfg`; las partes incompletas o ambiguas no se pueden verificar con huellas.

## Índices automáticos

Abrir, restaurar y actualizar mantiene atómicamente cada `games.bin` de CD/DVD existente, independientemente de los filtros visibles. **OPL legacy · 92bytes/juego** guarda 64 bytes de nombre. El perfil manual de 160 bytes de nombre genera registros de 188 bytes; el siguiente ciclo automático vuelve a 92. Utiliza el formato que corresponda a tu cargador.

No hay cabecera. Se guarda el nombre real, ID verificado, extensión exacta, tipo de medio/nombre y tamaño físico en MiB. No incluye VCD/UL. Las carpetas vacías reciben índices vacíos; los idénticos no se reescriben. ID sin verificar o nombres excesivos impiden publicar una lista incompleta. Cada archivo es atómico, pero no ambos conjuntamente: los errores indican lo ya guardado. Un servidor con una imagen abierta puede necesitar reabrirla; esta aplicación no lo controla.

```sh
./opl-manager-linux --library '/ruta/OPL' --generate-games-bin
./opl-manager-linux --library '/ruta/OPL' --generate-games-bin --index-name-bytes 160
```

## Arte, CFG y VMC

La vista previa no escribe ART. Elige una alternativa y descárgala explícitamente. El lote omite arte existente salvo sustitución seleccionada. Se informa de los tipos ausentes. Tamaños PNG: COV 140×200, COV2 242×344, ICO 64×64, LAB 18×240, LGO 300×125, BG 640×480 y SCR/SCR2 250×188; indexado hasta 256 colores.

CFG sincroniza controles y texto. Conserva claves desconocidas, comentarios y valores personalizados; guarda CRLF, copia `.bak` y detecta cambios externos. CHT es un editor de texto, no un asistente completo POPStarter. Las VMC se formatean con páginas de 512 bytes sin ECC/spare, de 8–64 MiB, sin sobrescribir tarjetas. Asigna la tarjeta a una ranura y guarda CFG.

## Conversión y huellas

ISO/ZSO conserva el original, comprueba destinos y solo publica resultados completos. Cancelar elimina temporales. CRC32/MD5/SHA-1/SHA-256 identifica archivos, no certifica la calidad del volcado. Conserva copia de los metadatos importantes antes de editarlos intencionadamente.

## Problemas y desinstalación

- Sin FUSE: añade `--appimage-extract-and-run`.
- Sin escritorio: la GUI requiere sesión gráfica. `QT_QPA_PLATFORM=offscreen` sirve para pruebas, no uso interactivo.
- Dependencias DEB ausentes: instala mediante APT en una distribución compatible.
- Arte no disponible: revisa red, servicio y existencia de imágenes para ese ID. La biblioteca funciona sin Internet.
- Índice rechazado: revisa avisos de ID, nombre y permisos; no trunques nombres para ocultarlo.
- Reiniciar preferencias: cierra la app y edita o elimina `~/.config/opl-manager-linux/settings.json`.
- Retirar DEB: `sudo apt purge opl-manager-linux`. AppImage: borra su archivo. No se eliminan tus juegos ni datos de biblioteca.
