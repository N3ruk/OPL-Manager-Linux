"""Library preparation and one-pass automatic classic OPL cache refresh."""
from pathlib import Path
from .core import directory, scan_library, cancelled
from .games_index import generate_indexes

OPL_FOLDERS = ('DVD', 'CD', 'ART', 'CFG', 'CHT', 'VMC', 'POPS')

def library_root(path):
    path = Path(path).resolve(strict=True)
    if not path.is_dir():
        raise ValueError('Selecciona una carpeta de biblioteca.')
    return path.parent if path.name.upper() in ('DVD', 'CD', 'POPS') else path

def missing_folders(root):
    return [name for name in OPL_FOLDERS if not directory(root, name).is_dir()]

def create_folders(root):
    # Validate conflicts before creating any directory. Respect existing spelling.
    missing = missing_folders(root)
    for name in missing:
        target = root / name
        if target.exists() or target.is_symlink():
            raise ValueError(f'No se puede crear la carpeta {target}: el nombre ya está ocupado.')
    for name in missing:
        (root / name).mkdir(exist_ok=True)
    return missing

def refresh_library(root, progress=None, cancel=None):
    games, warnings = scan_library(root, progress, cancel)
    cancelled(cancel)
    result = None
    index_error = ''
    if any(directory(root, name).is_dir() for name in ('CD', 'DVD')):
        try:
            result = generate_indexes(root, 64, progress, cancel, scanned=(games, warnings))
        except (ValueError, OSError) as error:
            index_error = str(error)
    return games, warnings, result, index_error
