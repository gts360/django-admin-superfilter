import json
from dataclasses import dataclass, field as dataclass_field
from typing import Any

from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import models
from django.db.models import Q

TEXT_FIELDS = (
    models.CharField,
    models.TextField,
    models.EmailField,
    models.SlugField,
    models.URLField,
    models.UUIDField,
)

NUMERIC_FIELDS = (
    models.IntegerField,
    models.FloatField,
    models.DecimalField,
    models.AutoField,
    models.BigAutoField,
    models.SmallIntegerField,
    models.PositiveIntegerField,
    models.PositiveSmallIntegerField,
    models.BigIntegerField,
)

DATE_FIELDS = (
    models.DateField,
    models.DateTimeField,
    models.TimeField,
)


@dataclass
class FilterField:
    path: str
    label: str
    kind: str
    choices: list[dict[str, Any]] = dataclass_field(default_factory=list)
    input_type: str | None = None


class SuperFilterField:
    path: str
    label: str
    kind: str = 'all'
    choices: list[dict[str, Any]] | None = None
    input_type: str | None = None

    def __init__(self, path: str | None = None, label: str | None = None, kind: str | None = None):
        if path is not None:
            self.path = path
        if label is not None:
            self.label = label
        if kind is not None:
            self.kind = kind

    def to_filter_field(self) -> FilterField:
        return FilterField(
            path=self.path,
            label=self.label,
            kind=self.kind,
            choices=list(self.choices or []),
            input_type=self.input_type,
        )

    def apply_rule(self, queryset, rule: dict[str, Any]):
        raise ValidationError(f"Custom field '{self.path}' does not implement filtering")


OPERATORS_BY_KIND = {
    "all": ["set", "not_set"],
    "text": ["set", "not_set", "eq", "neq", "contains", "not_contains", "in", "not_in"],
    "numeric": ["set", "not_set", "eq", "neq", "gt", "lt", "gte", "lte"],
    "boolean": ["set", "not_set", "true", "false"],
    "fk": ["set", "not_set", "in", "not_in"],
    "choice": ["set", "not_set", "in", "not_in"],
    "date": ["set", "not_set", "eq", "before", "after", "between"],
    "datetime": ["set", "not_set", "eq", "before", "after", "between"],
}


def parse_rules(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []

    try:
        rules = json.loads(raw)
    except json.JSONDecodeError:
        return []

    if not isinstance(rules, list):
        return []

    cleaned = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        field = str(rule.get("field", "")).strip()
        op = str(rule.get("op", "")).strip()
        value = rule.get("value")
        if not field or not op:
            continue
        cleaned.append({"field": field, "op": op, "value": value})
    return cleaned


def resolve_model_field(model: type[models.Model], path: str):
    current = model
    field = None
    chunks = path.split("__")

    for idx, chunk in enumerate(chunks):
        try:
            field = current._meta.get_field(chunk)
        except FieldDoesNotExist as exc:
            raise FieldDoesNotExist(f"Unknown field path '{path}'") from exc

        is_last = idx == len(chunks) - 1
        if is_last:
            break

        if not getattr(field, "is_relation", False):
            raise FieldDoesNotExist(f"Field '{chunk}' in '{path}' is not traversable")

        related_model = getattr(field, "related_model", None)
        if related_model is None:
            raise FieldDoesNotExist(f"Field '{chunk}' in '{path}' has no related model")
        current = related_model

    return field


def get_field_kind(field) -> str:
    if isinstance(field, (models.ForeignKey, models.OneToOneField, models.ManyToManyField)):
        return "fk"
    if isinstance(field, (models.ManyToOneRel, models.ManyToManyRel, models.OneToOneRel)):
        return "fk"
    if isinstance(field, models.BooleanField):
        return "boolean"
    if getattr(field, "choices", None):
        return "choice"
    if isinstance(field, models.DateTimeField):
        return "datetime"
    if isinstance(field, models.DateField):
        return "date"
    if isinstance(field, TEXT_FIELDS):
        return "text"
    if isinstance(field, NUMERIC_FIELDS):
        return "numeric"
    return "all"


def _serialize_choices(field) -> list[dict[str, Any]]:
    choices = []
    for raw_value, raw_label in getattr(field, "choices", ()):
        if raw_value in (None, ""):
            continue
        choices.append({"value": str(raw_value), "label": str(raw_label)})
    return choices


def _get_input_type(kind: str) -> str | None:
    if kind == "date":
        return "date"
    if kind == "datetime":
        return "datetime-local"
    return None


def _coerce_custom_field(item):
    if isinstance(item, SuperFilterField):
        return item
    if isinstance(item, type) and issubclass(item, SuperFilterField):
        return item()
    return None


def build_filter_field_from_item(model_admin, request, item):
    custom_field = _coerce_custom_field(item)
    if custom_field is not None:
        return custom_field.to_filter_field(), custom_field

    if not isinstance(item, str):
        return None, None

    try:
        field = resolve_model_field(model_admin.model, item)
    except FieldDoesNotExist:
        return None, None
    kind = get_field_kind(field)
    label = str(getattr(field, "verbose_name", item)).strip()
    return (
        FilterField(
            path=item,
            label=label,
            kind=kind,
            choices=_serialize_choices(field) if kind == "choice" else [],
            input_type=_get_input_type(kind),
        ),
        None,
    )


def list_filterable_fields(model_admin, request, source_fields=None) -> list[FilterField]:
    out: list[FilterField] = []
    for item in (source_fields if source_fields is not None else model_admin.get_list_display(request)):
        filter_field, _custom = build_filter_field_from_item(model_admin, request, item)
        if filter_field is not None:
            out.append(filter_field)
    return out


def get_custom_superfilter_map(model_admin, request, source_fields=None) -> dict[str, SuperFilterField]:
    out: dict[str, SuperFilterField] = {}
    for item in (source_fields if source_fields is not None else model_admin.get_list_display(request)):
        filter_field, custom_field = build_filter_field_from_item(model_admin, request, item)
        if filter_field is not None and custom_field is not None:
            out[filter_field.path] = custom_field
    return out


def serialize_fields(fields: list[FilterField]) -> list[dict[str, Any]]:
    return [
        {
            "path": f.path,
            "label": f.label,
            "kind": f.kind,
            "operators": OPERATORS_BY_KIND.get(f.kind, OPERATORS_BY_KIND["all"]),
            "choices": f.choices,
            "inputType": f.input_type,
        }
        for f in fields
    ]


def _parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    sval = str(value).strip().lower()
    if sval in {"1", "true", "yes", "on", "oui"}:
        return True
    if sval in {"0", "false", "no", "off", "non"}:
        return False
    return None


def _parse_value(field, value: Any):
    if isinstance(field, models.BooleanField):
        parsed = _parse_bool(value)
        if parsed is None:
            raise ValidationError("Invalid boolean value")
        return parsed
    return field.to_python(value)


def _q_set(path: str, field, is_set: bool) -> Q:
    if isinstance(field, models.BooleanField):
        return Q(**{f"{path}__isnull": not is_set})

    if isinstance(field, TEXT_FIELDS):
        empty_q = Q(**{f"{path}__isnull": True}) | Q(**{path: ""})
        return ~empty_q if is_set else empty_q

    null_q = Q(**{f"{path}__isnull": True})
    return ~null_q if is_set else null_q


def _q_for_rule(path: str, field, op: str, value: Any) -> Q:
    kind = get_field_kind(field)

    if op == "set":
        return _q_set(path, field, True)
    if op == "not_set":
        return _q_set(path, field, False)

    if kind == "boolean":
        if op == "true":
            return Q(**{path: True})
        if op == "false":
            return Q(**{path: False})
        if op == "empty":
            return Q(**{f"{path}__isnull": True})
        raise ValidationError(f"Operator '{op}' not allowed for boolean field '{path}'")

    if kind == "fk":
        if op not in {"in", "not_in"}:
            raise ValidationError(f"Operator '{op}' not allowed for relation field '{path}'")
        if not isinstance(value, list):
            raise ValidationError(f"Operator '{op}' requires a list value")

        selected = [v for v in value if str(v).strip() != ""]
        in_q = Q(**{f"{path}__in": selected})
        return ~in_q if op == "not_in" else in_q

    if kind in {"text", "all"} and op in {"in", "not_in"}:
        if not isinstance(value, list):
            raise ValidationError(f"Operator '{op}' requires a list value")
        selected = [str(v).strip() for v in value if str(v).strip() != ""]
        in_q = Q(**{f"{path}__in": selected})
        return ~in_q if op == "not_in" else in_q

    if kind == "choice":
        if op not in {"in", "not_in"}:
            raise ValidationError(f"Operator '{op}' not allowed for choice field '{path}'")
        if not isinstance(value, list):
            raise ValidationError(f"Operator '{op}' requires a list value")
        selected = [str(v) for v in value if str(v).strip() != ""]
        in_q = Q(**{f"{path}__in": selected})
        return ~in_q if op == "not_in" else in_q

    if kind in {"date", "datetime"}:
        if op == "eq":
            return Q(**{path: _parse_value(field, value)})
        if op == "before":
            return Q(**{f"{path}__lt": _parse_value(field, value)})
        if op == "after":
            return Q(**{f"{path}__gt": _parse_value(field, value)})
        if op == "between":
            if not isinstance(value, list) or len(value) != 2:
                raise ValidationError(f"Operator '{op}' requires exactly two values")
            low = _parse_value(field, value[0])
            high = _parse_value(field, value[1])
            return Q(**{f"{path}__gte": low, f"{path}__lte": high})
        raise ValidationError(f"Operator '{op}' not allowed for {kind} field '{path}'")

    if op == "eq":
        return Q(**{path: _parse_value(field, value)})
    if op == "neq":
        return ~Q(**{path: _parse_value(field, value)})
    if op == "contains":
        return Q(**{f"{path}__icontains": value})
    if op == "not_contains":
        return ~Q(**{f"{path}__icontains": value})
    if op == "gt":
        return Q(**{f"{path}__gt": _parse_value(field, value)})
    if op == "lt":
        return Q(**{f"{path}__lt": _parse_value(field, value)})
    if op == "gte":
        return Q(**{f"{path}__gte": _parse_value(field, value)})
    if op == "lte":
        return Q(**{f"{path}__lte": _parse_value(field, value)})

    raise ValidationError(f"Unknown operator '{op}'")


def apply_rules(queryset, model: type[models.Model], allowed_fields: set[str], rules: list[dict[str, Any]], custom_fields: dict[str, SuperFilterField] | None = None):
    custom_fields = custom_fields or {}
    qs = queryset
    q = Q()
    for rule in rules:
        path = rule.get("field")
        if path not in allowed_fields:
            continue

        custom_field = custom_fields.get(path)
        if custom_field is not None:
            try:
                qs = custom_field.apply_rule(qs, rule)
            except (ValidationError, TypeError, ValueError):
                continue
            continue

        try:
            field = resolve_model_field(model, path)
            q &= _q_for_rule(path, field, rule.get("op"), rule.get("value"))
        except (FieldDoesNotExist, ValidationError, TypeError, ValueError):
            continue

    return qs.filter(q)
