# logpattern_converter/__main__.py (safe stdout for Windows consoles)
from __future__ import annotations
import argparse
import json
import pathlib
import sys

try:
    from .license_client import activate_license
except Exception:
    def activate_license(key: str, server_url: str = None) -> dict:
        return {"success": False, "error": "license_client missing"}

from .converter import parse_patterns, PatternSpec, convert_file

def _print_json_safe(obj):
    """
    Imprime JSON de forma segura en consolas Windows que usan cp1252:
    escribe bytes UTF-8 directos en stdout.buffer; si no existe, usa ensure_ascii=True.
    """
    try:
        data = json.dumps(obj, indent=2, ensure_ascii=False)
        # write as utf-8 bytes to avoid UnicodeEncodeError in Windows consoles
        try:
            sys.stdout.buffer.write((data + "\n").encode("utf-8"))
            sys.stdout.buffer.flush()
            return
        except Exception:
            pass
        # fallback
        print(json.dumps(obj, indent=2, ensure_ascii=True))
    except Exception as e:
        print({"success": False, "error": "print_failed", "detail": str(e)})

def cmd_activar(args):
    key = args.key
    # mensaje corto antes de la llamada
    sys.stdout.buffer.write((f"Activando licencia: {key}\n").encode("utf-8"))
    sys.stdout.buffer.flush()
    res = activate_license(key)
    _print_json_safe(res)

def load_patterns_file(path: str) -> list[PatternSpec]:
    txt = pathlib.Path(path).read_text(encoding="utf-8")
    specs = parse_patterns(txt)
    return specs

def cmd_convertir(args):
    patterns_file = args.patterns
    input_file = args.input
    out_file = args.out

    specs = load_patterns_file(patterns_file)
    if not specs:
        print("No se encontraron patrones en", patterns_file)
        sys.exit(2)
    spec = specs[0]
    sys.stdout.buffer.write((f"Usando patrón: {spec.name}\n").encode("utf-8"))
    sys.stdout.buffer.flush()
    res = convert_file(input_file, spec, out_path=out_file if out_file else None)
    _print_json_safe(res)

def cmd_info(args):
    print("LogPattern Converter — CLI")
    print("Instalado en:", sys.executable)

def main(argv=None):
    parser = argparse.ArgumentParser(prog="logconv")
    sub = parser.add_subparsers(dest="cmd")

    p_act = sub.add_parser("activar", help="Activar licencia")
    p_act.add_argument("key", help="Clave de activación")
    p_act.set_defaults(func=cmd_activar)

    p_conv = sub.add_parser("convertir", help="Convertir un archivo con un patrón")
    p_conv.add_argument("patterns", help="Archivo de patrones (NAME ::= REGEX)")
    p_conv.add_argument("input", help="Archivo de log a convertir")
    p_conv.add_argument("--out", "-o", help="Archivo de salida (JSON)")
    p_conv.set_defaults(func=cmd_convertir)

    p_info = sub.add_parser("info", help="Info")
    p_info.set_defaults(func=cmd_info)

    args = parser.parse_args(argv)
    if not getattr(args, "cmd", None):
        parser.print_help()
        sys.exit(0)
    args.func(args)

if __name__ == "__main__":
    main()
