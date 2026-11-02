"""Raw OPL base_game_info_t caches: 92-byte Windows sample / 188-byte recent OPL.

One games.bin per CD/DVD directory, little-endian, no header or record count.
"""
from dataclasses import dataclass
from pathlib import Path
import re
import struct

from .core import Game, atomic_bytes, cancelled, directory, require_id, scan_library

PROFILES = {64: 'OPL legacy · 92bytes/juego',
            160: 'OPL reciente · 188 bytes/juego'}
LEGACY_NAME = re.compile(r'^([A-Za-z]{4}_\d{3}\.\d{2})\.(.+)$')


def record_struct(name_bytes=64):
    if name_bytes not in PROFILES:
        raise ValueError('El tamaño del nombre debe ser 64 o 160 bytes.')
    return struct.Struct(f'<{name_bytes + 1}s13s5sBBB2xI')


def encode_game(game: Game, name_bytes=64) -> bytes:
    layout = record_struct(name_bytes)
    if game.path.parent.name.upper() not in ('CD', 'DVD') or game.kind not in ('ISO', 'ZSO'):
        raise ValueError('Solo se indexan ISO/ZSO dentro de DVD o CD.')
    if game.id_source != 'SYSTEM.CNF':
        raise ValueError('No se ha podido comprobar el ID en SYSTEM.CNF.')
    startup = require_id(game.game_id).encode('ascii')
    name = game.path.stem
    legacy = LEGACY_NAME.fullmatch(name)
    fmt = 2
    if legacy:
        if legacy[1] != game.game_id:
            raise ValueError('El ID del nombre no coincide exactamente con el ID del disco; renombra primero el juego.')
        name = legacy[2]
        fmt = 1
    encoded = name.encode('utf-8')
    if not encoded or b'\0' in encoded or len(encoded) > name_bytes:
        raise ValueError(f'El nombre necesita {len(encoded)} bytes; este perfil admite {name_bytes}. No se truncará.')
    extension = game.path.suffix.encode('ascii')
    size_mb = game.path.stat().st_size >> 20
    media = 0x12 if game.path.parent.name.upper() == 'CD' else 0x14
    return layout.pack(encoded, startup, extension, 1, media, fmt, size_mb)


@dataclass
class IndexResult:
    files: dict[Path, int]
    name_bytes: int

    @property
    def count(self):
        return sum(self.files.values())


def generate_indexes(root: Path, name_bytes=64, progress=None, cancel=None, *, scanned=None) -> IndexResult:
    """Rescan everything, validate, then publish each index atomically.

    Existing CD/DVD directories only. Selecting CD/DVD targets that folder
    alone. Empty folders get an empty index to clear stale entries. Validation
    and cancellation precede all writes; ISO/ZSO files are never modified.
    """
    record_struct(name_bytes)
    root = Path(root).resolve(strict=True)
    if root.name.upper() in ('CD', 'DVD'):
        folders = [root]
    else:
        folders = [directory(root, name) for name in ('DVD', 'CD')
                   if directory(root, name).is_dir()]
    if not folders:
        raise ValueError('Selecciona la raíz OPL con DVD/CD, o la propia carpeta DVD o CD. No se moverán juegos.')
    games, warnings = scanned if scanned is not None else scan_library(root, progress, cancel)
    if warnings:
        raise ValueError('No se ha podido leer toda la biblioteca:\n' + '\n'.join(warnings))
    planned = {folder / 'games.bin': [] for folder in folders}
    errors = []
    for game in games:
        cancelled(cancel)
        target = game.path.parent / 'games.bin'
        if target not in planned or game.kind not in ('ISO', 'ZSO'):
            continue
        try:
            planned[target].append(encode_game(game, name_bytes))
        except (ValueError, OSError) as error:
            errors.append(f'{game.path.name}: {error}')
    if errors:
        raise ValueError('No se ha generado ningún índice. Corrige estos juegos:\n' + '\n'.join(errors))
    for target in planned:
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise ValueError(f'El destino no es un archivo normal: {target}')
    cancelled(cancel)
    saved = {}
    # A short non-cancellable commit phase; each file is replaced atomically.
    for target, records in planned.items():
        try:
            content = b''.join(records)
            if not target.exists() or target.read_bytes() != content:
                atomic_bytes(target, content)
        except OSError as error:
            previous = ', '.join(str(p) for p in saved) or 'ninguno'
            raise OSError(f'No se pudo escribir {target}. Índices ya guardados: {previous}. {error}') from error
        saved[target] = len(records)
    return IndexResult(saved, name_bytes)
