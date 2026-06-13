# django-admin-superfilter

Advanced, modern filtering for Django admin changelists, with saved filters and selectable columns.

## Features

- Search-bar style filter UI injected into Django admin changelists
- Type-aware filtering for text, numeric, boolean, choice, date, datetime and relation fields
- Field path traversal such as `author__email`
- Saved filters per authenticated user
- Column selection and ordering persisted with saved filters
- AJAX-backed relation picker using Django admin Select2 assets
- Support for custom filter fields via `SuperFilterField`
- Single JSON query parameter for rules (`sf`) and one for visible columns (`sfc`)
- Works without templates overrides

## Requirements

- Python 3.10+
- Django 4.0+

## Installation

Install the package:

```bash
pip install django-admin-superfilter
```

Add the app to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "superfilter",
]
```

Run migrations:

```bash
python manage.py migrate
```

## Quick start

```python
from django.contrib import admin
from superfilter.admin import SuperFilterAdminMixin

from .models import Bird


@admin.register(Bird)
class BirdAdmin(SuperFilterAdminMixin, admin.ModelAdmin):
    list_display = ("species", "location", "count")
    search_fields = ("species",)
```

Important:

- Put `SuperFilterAdminMixin` before `admin.ModelAdmin` in the MRO.
- By default, filterable fields come from `list_display`.
- Non-model entries in `list_display` are ignored.
- Traversed model fields like `location__city__name` are supported.

## What appears in the UI

The package adds a search-bar-like control above the changelist with:

- an add-filter button
- filter badges for current rules
- an Apply button
- a split menu with Save
- a Reset button
- a Columns toggle button
- a collapsible column chooser
- saved filter chips

Saved filters store both:

- the active filter rules
- the selected column list and order

## Supported field kinds and operators

### All fields

- `set`
- `not_set`

### Text-like fields

Text-like fields include `CharField`, `TextField`, `EmailField`, `SlugField`, `URLField`, `UUIDField`.

Operators:

- `set`
- `not_set`
- `eq`
- `neq`
- `contains`
- `not_contains`
- `in`
- `not_in`

### Numeric fields

Operators:

- `set`
- `not_set`
- `eq`
- `neq`
- `gt`
- `lt`
- `gte`
- `lte`

### Boolean fields

Operators:

- `set`
- `not_set`
- `true`
- `false`

### Choice fields

Operators:

- `set`
- `not_set`
- `in`
- `not_in`

### Foreign key / relation fields

Operators:

- `set`
- `not_set`
- `in`
- `not_in`

### Date and datetime fields

Operators:

- `set`
- `not_set`
- `eq`
- `before`
- `after`
- `between`

## Semantics

- `set` means the field is considered populated
- `not_set` means the field is empty
- For text fields, empty means `NULL` or empty string
- For boolean fields, `set` / `not_set` only target `NULL` vs non-`NULL`
- `contains` uses `icontains`
- `not_contains` negates `icontains`
- `between` on date/datetime expects exactly two values
- Relation filters use selected related object primary keys

## Configuration

`SuperFilterAdminMixin` exposes a few attributes:

- `superfilter_param_name = "sf"`
- `superfilter_columns_param_name = "sfc"`
- `superfilter_fields = None`
- `superfilter_page_size = 25`
- `superfilter_all_limit = 2000`

Example:

```python
class BirdAdmin(SuperFilterAdminMixin, admin.ModelAdmin):
    list_display = ("species", "location", "count")
    superfilter_page_size = 50
    superfilter_all_limit = 5000
```

## Restricting filterable fields

By default, filterable fields are taken from `list_display`.

To expose a different set of fields, use `superfilter_fields`:

```python
class BirdAdmin(SuperFilterAdminMixin, admin.ModelAdmin):
    list_display = ("species", "location", "count")
    superfilter_fields = ("species", "count", "location__city")
```

This only affects filterable fields. Column selection still uses `list_display`.

## Custom filter fields

You can plug in custom fields that do not map directly to a Django model field.

Create a subclass of `SuperFilterField`:

```python
from django.db.models import Q
from superfilter.logic import SuperFilterField


class HasLargeCountField(SuperFilterField):
    path = "has_large_count"
    label = "Large count"
    kind = "choice"
    choices = [
        {"value": "yes", "label": "Yes"},
        {"value": "no", "label": "No"},
    ]

    def apply_rule(self, queryset, rule):
        values = set(rule.get("value") or [])
        if "yes" in values and "no" not in values:
            return queryset.filter(count__gte=100)
        if "no" in values and "yes" not in values:
            return queryset.filter(count__lt=100)
        return queryset
```

Register it in `superfilter_fields`:

```python
class BirdAdmin(SuperFilterAdminMixin, admin.ModelAdmin):
    list_display = ("species", "location", "count")
    superfilter_fields = ("species", HasLargeCountField)
```

## Saved filters

Saved filters are stored in the `SavedSuperFilter` model and are scoped by:

- user
- app label
- model name
- saved filter name

Notes:

- saving requires an authenticated user
- saved filters are private to the user

## URL format

Rules are sent in the `sf` query parameter as JSON:

```json
[
  {"field": "species", "op": "contains", "value": "owl"},
  {"field": "location", "op": "in", "value": [1, 2]},
  {"field": "count", "op": "gte", "value": 10}
]
```

Columns are sent in the `sfc` query parameter as JSON:

```json
["location", "species", "count"]
```

## Relation option loading

For relation filters, the package exposes an admin endpoint that:

- reuses the related admin's `get_search_results()` when available
- otherwise falls back to searching up to three text fields
- otherwise falls back to PK search for numeric terms

## Static assets

The mixin injects:

- `admin/css/vendor/select2/select2.min.css`
- `admin/js/vendor/select2/select2.full.min.js`
- `superfilter/superfilter.css`
- `superfilter/superfilter.js`

No custom template override is required.

## Limitations

- Filtering ignores callable/computed `list_display` entries unless implemented as `SuperFilterField`
- Column selection only works on entries present in `list_display`
- The package ships with admin-focused frontend assets and is not intended for non-admin pages

## Example project

A runnable sample project is available in:

- `examples/sampleapp/`

Run it with:

```bash
cd examples/sampleapp
python manage.py migrate
python manage.py runserver
```

## Development

Run tests from the repository root:

```bash
python manage.py test superfilter
```

Or use the sample project:

```bash
cd examples/sampleapp
python manage.py test
```

## License

MIT. See `LICENCE.md`.
