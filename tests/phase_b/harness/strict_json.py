"""Strict JSON primitives and stable acceptance diagnostics."""
import hashlib
import json
import math
import ast
from pathlib import Path, PurePosixPath


class Invalid(ValueError):
    def __init__(self, object_id, field_path, category="invalid_input"):
        self.error = {"category": category, "object_id": object_id, "field_path": field_path}
        super().__init__(f"{category}:{object_id}:{field_path}")


def require(condition, object_id, field_path, category="invalid_input"):
    if not condition:
        raise Invalid(object_id, field_path, category)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "json", key)
        result[key] = value
    return result


def _constant(value):
    raise Invalid("json", value)


def _float(value):
    result = float(value)
    require(math.isfinite(result), "json", "number")
    return result


def loads(raw):
    try:
        return json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_float)
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise Invalid("json", "syntax") from exc


def read(path):
    return loads(Path(path).read_bytes())


def canonical(value):
    try:
        return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode()
    except (TypeError, ValueError, RecursionError, UnicodeError) as exc:
        raise Invalid("json", "canonical") from exc


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    return sha(canonical(value))


def keys(value, expected, obj):
    require(type(value) is dict and set(value) == set(expected), obj, "fields")


def strings(value, obj, field, *, nonempty=True, ordered=True):
    require(type(value) is list and (bool(value) or not nonempty), obj, field)
    require(all(type(x) is str and x and x.strip() == x for x in value), obj, field)
    require(len(value) == len(set(value)), obj, field)
    if ordered:
        require(value == sorted(value), obj, field)
    return value


def text(value, obj, field):
    require(type(value) is str and bool(value.strip()), obj, field)


def path_in(root, relative, *, exists=True):
    require(type(relative) is str and bool(relative) and "\\" not in relative, "path", "relative")
    p = PurePosixPath(relative)
    require(not p.is_absolute() and ".." not in p.parts and str(p) == relative, "path", "normalized_relative")
    root = Path(root).resolve()
    target = root.joinpath(*p.parts)
    require(target.resolve().is_relative_to(root), "path", "containment")
    if exists:
        require(target.is_file(), "path", "required_file")
    return target


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical(value))


def callable_ref(root, reference):
    text(reference, "callable", "reference")
    relative, separator, qualified = reference.partition(":")
    require(separator and qualified and relative.endswith(".py"), "callable", "reference")
    path = path_in(root, relative)
    try:
        nodes = ast.parse(path.read_bytes()).body
    except (SyntaxError, UnicodeError) as exc:
        raise Invalid("callable", "source") from exc
    found = None
    for name in qualified.split("."):
        found = next((n for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                      and n.name == name), None)
        require(found is not None, "callable", "qualified_name")
        nodes = found.body
    require(isinstance(found, (ast.FunctionDef, ast.AsyncFunctionDef)), "callable", "function")
    return path
