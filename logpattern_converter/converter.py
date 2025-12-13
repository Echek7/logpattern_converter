# logpattern_converter/converter.py (BOM-safe, filtra líneas vacías)
from __future__ import annotations
import re
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Pattern, Any
import logging
import pathlib

logger = logging.getLogger("logpattern_converter")
logger.setLevel(logging.INFO)

@dataclass
class PatternSpec:
    name: str
    raw: str
    normalized: str
    groups: List[str]

def parse_patterns(text: str) -> List[PatternSpec]:
    # eliminar BOM si existe al comienzo del texto
    if text and text[0] == "\ufeff":
        text = text.lstrip("\ufeff")
    specs: List[PatternSpec] = []
    for i, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "::=" not in line:
            logger.debug("Skipping malformed line %d: %s", i, line)
            continue
        name, expr = line.split("::=", 1)
        name = name.strip().lstrip("\ufeff")   # limpiar BOM accidental en el nombre
        expr = expr.strip().lstrip("\ufeff")
        normalized = normalize_pattern(expr)
        groups = extract_group_names(normalized)
        specs.append(PatternSpec(name=name, raw=expr, normalized=normalized, groups=groups))
    return specs

def normalize_pattern(expr: str) -> str:
    s = expr.strip()
    replacements = {
        "%TIMESTAMP%": r"(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)",
        "%INT%": r"(?P<int>\d+)",
        "%WORD%": r"(?P<word>\w+)",
        "%GREEDY%": r"(?P<g>.*)",
    }
    for k, v in replacements.items():
        s = s.replace(k, v)
    return s

_GROUP_NAME_RE = re.compile(r"\?P<(?P<name>[A-Za-z_][A-Za-z0-9_]*)>")

def extract_group_names(pattern: str) -> List[str]:
    return [m.group("name") for m in _GROUP_NAME_RE.finditer(pattern)]

def validate_pattern(pattern: str) -> bool:
    try:
        re.compile(pattern)
        return True
    except re.error as e:
        logger.debug("Invalid pattern: %s (%s)", pattern, e)
        return False

def transform_pattern(pattern: str, to_format: str = "json") -> Dict[str, Any]:
    fields = extract_group_names(pattern)
    return {"pattern": pattern, "fields": fields}

def convert_line(line: str, compiled: Pattern, fields: List[str]) -> Optional[Dict[str, str]]:
    m = compiled.search(line)
    if not m:
        return None
    out = {}
    for f in fields:
        out[f] = m.groupdict().get(f, "")
    return out

def convert_file(path: str | pathlib.Path, pattern_spec: PatternSpec, out_path: Optional[str | pathlib.Path] = None,
                 *, output_format: str = "json") -> Dict[str, Any]:
    p = pathlib.Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Input file not found: {p}")
    if not validate_pattern(pattern_spec.normalized):
        raise ValueError("PatternSpec.normalized is not a valid regex")

    compiled = re.compile(pattern_spec.normalized)
    processed = 0
    matched = 0
    samples: List[Dict[str, str]] = []

    # Lectura robusta: soportar \n literales, remover BOM y descartar líneas vacías
    with p.open("r", encoding="utf-8", errors="replace") as fh:
        raw = fh.read()
        if "\\n" in raw:
            raw = raw.replace("\\n", "\n")
        # eliminar BOM si apareciera
        if raw and raw[0] == "\ufeff":
            raw = raw.lstrip("\ufeff")
        # splitlines y filtrar líneas vacías (espacios considerados vacíos)
        lines = [ln for ln in raw.splitlines() if ln.strip() != ""]
        for line in lines:
            processed += 1
            res = convert_line(line, compiled, pattern_spec.groups)
            if res is not None:
                matched += 1
                if len(samples) < 20:
                    samples.append(res)

    result = {"pattern_name": pattern_spec.name, "processed": processed, "matched": matched, "samples": samples}
    if out_path:
        out = pathlib.Path(out_path)
        if output_format == "json":
            out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            out.write_text(str(result), encoding="utf-8")
    return result

def example_usage_cli():
    print("Usage example:")
    print("  python -m logpattern_converter.converter patterns.txt")
    print("  # where patterns.txt contains lines like:")
    print("  # ACCESS ::= (?P<ip>\\d+\\.\\d+\\.\\d+\\.\\d+) - - \\[(?P<time>.*?)\\] \"(?P<req>.*?)\"")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        example_usage_cli()
        sys.exit(1)
    patterns_file = sys.argv[1]
    input_file = sys.argv[2] if len(sys.argv) > 2 else None
    txt = pathlib.Path(patterns_file).read_text(encoding="utf-8")
    specs = parse_patterns(txt)
    if not specs:
        print("No patterns found.")
        sys.exit(1)
    spec = specs[0]
    if input_file:
        out = convert_file(input_file, spec, out_path=None)
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print("Parsed patterns:")
        for s in specs:
            print(json.dumps(asdict(s), indent=2, ensure_ascii=False))
