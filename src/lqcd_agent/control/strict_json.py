"""Strict JSON and immutable validation values for the 0.4 control boundary."""
from dataclasses import dataclass
import hashlib
import json
import math


class ControlIntegrityError(ValueError):
    """A failed proof, never permission to repair or publish a Run outcome."""

    code = "control_integrity_failure"


def require(condition, message):
    if not condition:
        raise ControlIntegrityError(message)


def closed(value, fields):
    require(type(value) is dict and set(value) == set(fields), "Non-closed object")
    return value


def text(value, *, nullable=False):
    require((nullable and value is None) or (type(value) is str and bool(value)), "Invalid text")
    return value


def number(value, *, integer=False, minimum=0):
    kind = type(value)
    require((kind is int) if integer else (kind is int or kind is float), "Invalid number type")
    require(abs(value) <= 2**53 - 1 and (kind is int or math.isfinite(value)) and value >= minimum,
            "Non-finite, overflowing or out-of-range number")
    return value


def digest_value(value, *, nullable=False):
    require((nullable and value is None) or
            (type(value) is str and len(value) == 64 and
             value.strip("0123456789abcdef") == ""), "Invalid digest")
    return value


def _json_value(value):
    kind = type(value)
    if value is None or kind is str or kind is bool:
        return
    if kind is int:
        number(value, minimum=-(2**53 - 1))
    elif kind is float:
        require(math.isfinite(value), "Non-finite JSON number")
    elif kind is list:
        for item in value:
            _json_value(item)
    elif kind is dict:
        require(all(type(key) is str for key in value), "Non-string JSON key")
        for item in value.values():
            _json_value(item)
    else:
        raise ControlIntegrityError("Non-JSON value")


def canonical_bytes(value):
    try:
        _json_value(value)
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, UnicodeError, RecursionError, OverflowError) as error:
        raise ControlIntegrityError("Invalid canonical JSON") from error


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "Duplicate JSON key")
        value[key] = item
    return value


def loads(data, *, canonical=True):
    require(type(data) in (str, bytes), "JSON input must be text or bytes")
    try:
        value = json.loads(data, object_pairs_hook=_pairs,
                           parse_constant=lambda _: require(False, "Non-finite JSON"))
        encoded = canonical_bytes(value)
        if canonical:
            require(encoded == (data.encode("utf-8") if isinstance(data, str) else data),
                    "Non-canonical JSON encoding")
        return value
    except (ValueError, UnicodeError, OverflowError, RecursionError) as error:
        raise ControlIntegrityError(str(error)) from error


@dataclass(frozen=True)
class ValidatedValue:
    """An immutable canonical snapshot; callers receive detached decoded copies."""

    canonical: bytes

    @classmethod
    def from_value(cls, value):
        return cls(canonical_bytes(value))

    @property
    def value(self):
        return loads(self.canonical)

    @property
    def digest(self):
        return hashlib.sha256(self.canonical).hexdigest()
