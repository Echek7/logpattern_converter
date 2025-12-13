# logpattern_converter/converter.py
"""
LogPattern Converter Core (consolidado).
Provee funciones para:
 - parsear patrones/regex simples desde archivos o strings
 - normalizar formatos (espacios, escapes, anclas)
 - transformar patrones a un formato objetivo (JSON-friendly)
 - validar patrones básicos
 - convertir archivos de logs aplicando patrones simples (ej. extraer campos)

Diseño: API pública ligera y testeable.
"""

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
    """
    Representa un patrón parseado y normalizado.
    - name: identificador del patrón
    - raw: texto original
    - normalized: patrón regular expression listo para compilar
    - groups: lista de nombres de captura (si se detectan)
    """
    name: str
    raw: str
    normalized: str
    groups: List[str]


def parse_patterns(text: str) -> List[PatternSpec]:
    """
    Parse a simple patterns file where each line is:
      NAME ::= REGEX
    Comments start with '#'.
    Returns list of PatternSpec (raw not modified yet).
    """
    specs: List[PatternSpec] = []
    for i, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "::=" not in line:
            logger.debug("Skipping malformed line %d: %s", i, line)
            continue
        name, expr = line.split("::=", 1)
        name = name.strip()
        expr = expr.strip()
        normalized = normalize_pattern(expr)
        groups = extract_group_names(normalized)
        specs.append(PatternSpec(name=name, raw=expr, normalized=normalized, groups=groups))
    return specs


def normalize_pattern(expr: str) -> str:
    """
    Normalizes a pattern string:
      - strip leading/trailing whitespace
      - convert common placeholders like %TIMESTAMP% to a generic regex
      - ensure raw string escapes are handled
    This is opinionated but conservative.
    """
    s = expr.strip()
    # example replacements (extendable)
    replacements = {
        "%TIMESTAMP%": r"(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)",
        "%INT%": r"(?P<int>\d+)",
        "%WORD%": r"(?P<word>\w+)",
        "%GREEDY%": r"(?P<g>.*)",
    }
    for k, v in replacements.items():
        s = s.replace(k, v)
    # unify quoting: if user forgot escapes for backslashes, keep them
    return s


_GROUP_NAME_RE = re.compile(r"\?P<(?P<name>[A-Za-z_][A-Za-z0-9_]*)>")


def extract_group_names(pattern: str) -> List[str]:
    """Return list of named capturing groups in the regex."""
    return [m.group("name") for m in _GROUP_NAME_RE.finditer(pattern)]


def validate_pattern(pattern: str) -> bool:
    """Attempt to compile the pattern. Returns True if valid."""
    try:
        re.compile(pattern)
        return True
    except re.error as e:
        logger.debug("Invalid pattern: %s (%s)", pattern, e)
        return False


def transform_pattern(pattern: str, to_format: str = "json") -> Dict[str, Any]:
    """
    Transform the pattern into a JSON-friendly dictionary describing fields.
    Example output:
      {
        "pattern": "<normalized regex>",
        "fields": ["timestamp", "level", "message"]
      }
    """
    fields = extract_group_names(pattern)
    return {"pattern": pattern, "fields": fields}


def convert_line(line: str, compiled: Pattern, fields: List[str]) -> Optional[Dict[str, str]]:
    """
    Apply compiled regex to a single line and return dict of fields if matched.
    """
    m = compiled.search(line)
    if not m:
        return None
    out = {}
    for f in fields:
        out[f] = m.groupdict().get(f, "")
    return out


def convert_file(path: str | pathlib.Path, pattern_spec: PatternSpec, out_path: Optional[str | pathlib.Path] = None,
                 *, output_format: str = "json") -> Dict[str, Any]:
    """
    Convert a text file applying the pattern_spec. Writes output if out_path provided.
    Returns a result summary:
      {"processed": N, "matched": M, "samples": [ ... ]}
    """
    p = pathlib.Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Input file not found: {p}")
    if not validate_pattern(pattern_spec.normalized):
        raise ValueError("PatternSpec.normalized is not a valid regex")

    compiled = re.compile(pattern_spec.normalized)
    processed = 0
    matched = 0
    samples: List[Dict[str, str]] = []

    with p.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
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


# CLI helper
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
    # treat first arg as patterns file and second as input log file
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
