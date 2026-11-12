"""Small JSON-Schema-subset validator. Standard library only.

Supported keywords: $ref (local $defs), type, enum, pattern, format=date, minLength,
minItems, items, required, properties, additionalProperties=false, oneOf, x-hint.
The schema document (schema.json, next to this file) is the single source of truth
for record shapes; do not duplicate shape checks elsewhere.
"""
import datetime
import json
import os
import re

_TYPES = {"string": str, "object": dict, "array": list, "boolean": bool, "null": type(None)}
_SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.json")


def is_date(s):
    try:
        datetime.date.fromisoformat(s)
        return len(s) == 10
    except (ValueError, TypeError):
        return False


def _is_type(v, t):
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    return isinstance(v, _TYPES[t])


class Schema:
    def __init__(self, doc=None):
        if doc is None:
            with open(_SCHEMA_PATH, encoding="utf-8") as f:
                doc = json.load(f)
        self.defs = doc["$defs"]

    def validate(self, value, def_name):
        """Return a list of error strings (empty list means valid)."""
        return self._v(value, {"$ref": "#/$defs/" + def_name}, "$")

    def _v(self, v, s, p):
        if "$ref" in s:
            name = s["$ref"].rsplit("/", 1)[-1]
            if name not in self.defs:
                return ["%s: schema error, unknown $ref %s" % (p, name)]
            return self._v(v, self.defs[name], p)
        errs = []
        t = s.get("type")
        if t is not None:
            ts = t if isinstance(t, list) else [t]
            if not any(_is_type(v, x) for x in ts):
                return ["%s: expected %s, got %s" % (p, " or ".join(ts), type(v).__name__)]
        if "enum" in s and v not in s["enum"]:
            errs.append("%s: %r is not one of %s" % (p, v, s["enum"]))
        if isinstance(v, str):
            if "pattern" in s and not re.match(s["pattern"], v):
                errs.append("%s: %r does not match pattern %s" % (p, v, s["pattern"]))
            if s.get("format") == "date" and not is_date(v):
                errs.append("%s: %r is not a YYYY-MM-DD date" % (p, v))
            if len(v) < s.get("minLength", 0):
                errs.append("%s: must not be empty" % p)
        if isinstance(v, list):
            if len(v) < s.get("minItems", 0):
                errs.append("%s: needs at least %d item(s)" % (p, s["minItems"]))
            if "items" in s:
                for i, item in enumerate(v):
                    errs += self._v(item, s["items"], "%s[%d]" % (p, i))
        if isinstance(v, dict):
            for k in s.get("required", []):
                if k not in v:
                    errs.append("%s: missing required field %r" % (p, k))
            props = s.get("properties", {})
            for k, sub in props.items():
                if k in v:
                    errs += self._v(v[k], sub, "%s.%s" % (p, k))
            if s.get("additionalProperties") is False:
                for k in v:
                    if k not in props:
                        errs.append("%s: unexpected field %r" % (p, k))
        if "oneOf" in s:
            results = [self._v(v, sub, p) for sub in s["oneOf"]]
            if sum(1 for r in results if not r) != 1:
                # Report the branch whose required keys are present, else the hint.
                shown = False
                if isinstance(v, dict):
                    for sub, r in zip(s["oneOf"], results):
                        req = sub.get("required", [])
                        if req and all(k in v for k in req) and r:
                            errs += r
                            shown = True
                            break
                if not shown:
                    errs.append("%s: %s" % (p, s.get("x-hint", "does not match any allowed form")))
        return errs
