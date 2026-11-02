# Verificación · 1.0.0

[English](../VERIFICATION.md)

Las regresiones usan imágenes sintéticas y bibliotecas temporales. Cubren identificación, escritura/renombrado seguro, índices, conversión/cancelación, validación de arte, conservación CFG, formato VMC, lotes y persistencia de temas.

La comprobación de paquetes incluye versiones, selección de fuentes públicas, metadatos/dependencias DEB, paquetes extraídos y `--self-test`. La AppImage se comprueba en un espacio de usuario Ubuntu 22.04 aislado y con pantalla virtual X11, no solo con Python/Qt de la estación. Los resultados CI están en Actions del repositorio.

Las pruebas automatizadas no acreditan compatibilidad física PS2. No se ha validado ningún juego, VMC ni cargador en una PS2 física como parte de esta publicación. La disponibilidad de arte depende del servicio y del juego/tipo. Es un cliente Linux independiente, no una afirmación de paridad total con Windows.

## Comprobaciones de publicación — 2026-11-02

- **100 pruebas superadas** en Ubuntu 22.04 aislado.
- AppImage normal, sin FUSE, versión y autocomprobación correctas.
- AppImage probada en Ubuntu Base 22.04 limpio sin Python/Qt instalados.
- Ventana/temas Qt comprobados en offscreen y X11/Xvfb.
- DEB autónomo instalado, versión y autocomprobación correctas en Ubuntu Base sin Python/Qt. El lanzador desactiva la escritura de bytecode para no dejar caché del runtime en `/opt` al retirar el paquete.
- Datos temporales; ningún paquete de prueba instalado en la estación anfitriona.
