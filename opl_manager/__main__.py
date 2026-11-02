import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(prog='opl-manager-linux', description='OPL Manager Linux')
    from . import __version__
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('--self-test', action='store_true', help='Run isolated packaged checks without accessing your library')
    parser.add_argument('--library', type=Path)
    parser.add_argument('--generate-games-bin', action='store_true', help='Generar los índices DVD/CD sin abrir la interfaz')
    parser.add_argument('--index-name-bytes', type=int, choices=(64, 160), default=64)
    args = parser.parse_args()
    if args.self_test:
        from .self_test import run
        return run()
    if args.generate_games_bin:
        if args.library is None:
            parser.error('--generate-games-bin requiere --library')
        from .games_index import generate_indexes
        try:
            result = generate_indexes(args.library, args.index_name_bytes)
        except (ValueError, OSError) as error:
            parser.exit(1, f'{error}\n')
        for path, count in result.files.items():
            print(f'{path}: {count} juegos ({path.stat().st_size} bytes)')
        return 0
    from .ui import main as gui_main
    return gui_main()


raise SystemExit(main())
