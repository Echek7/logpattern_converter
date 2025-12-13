# tests/test_converter.py
import tempfile
import pathlib
import json
from logpattern_converter.converter import parse_patterns, normalize_pattern, PatternSpec, convert_file

def test_parse_and_normalize():
    text = """
# comment
ACCESS ::= (?P<ip>\\d+\\.\\d+\\.\\d+\\.\\d+) - - \\[(?P<time>[^\\]]+)\\] "(?P<req>[^"]+)"
"""
    specs = parse_patterns(text)
    assert len(specs) == 1
    p = specs[0]
    assert p.name == "ACCESS"
    assert "ip" in p.groups
    assert p.normalized != ""

def test_convert_file_basic(tmp_path):
    # create input file with two lines
    content = '127.0.0.1 - - [2025-01-01T12:00:00Z] "GET /index HTTP/1.1"\\nno match line\\n'
    in_file = tmp_path / "in.log"
    in_file.write_text(content, encoding="utf-8")
    spec = PatternSpec(
        name="ACCESS",
        raw='(?P<ip>\\d+\\.\\d+\\.\\d+\\.\\d+) - - \\[(?P<time>[^\\]]+)\\] "(?P<req>[^"]+)"',
        normalized='(?P<ip>\\d+\\.\\d+\\.\\d+\\.\\d+) - - \\[(?P<time>[^\\]]+)\\] "(?P<req>[^"]+)"',
        groups=["ip","time","req"]
    )
    res = convert_file(str(in_file), spec)
    assert res["processed"] == 2
    assert res["matched"] == 1
    assert isinstance(res["samples"], list)
