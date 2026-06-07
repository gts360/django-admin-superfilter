# Superfilter

Generic, modern advanced filter for Django admin changelists.

## What it does

- **Modern search-bar UI**: Displays as a clean search bar at the top of changelist.
- **Filter badges/tags**: Each active filter shows as a blue badge with label, value summary, and remove button.
- **+ button dropdown**: Click the `+` button to see a dropdown list of all available filterable columns.
- **Interactive popup modal**: Select a column to open a modern popup where you configure the operator and value.
- **Type-aware operators**: Different field types have different operator sets (text, numeric, boolean, FK).
- **Model-field only**: Uses only real model fields from `list_display` (computed methods/callables are ignored).
- **Relation traversal**: Supports deep field paths like `agent_affecte__carlog_employe_nom`.
- **Single query parameter**: All filters serialized as JSON in the `sf` URL parameter.

## Supported operators

- **All fields**: `set`, `not_set`
- **Text fields**: `eq`, `neq`, `contains`, `not_contains`
- **Numeric/date fields**: `eq`, `neq`, `gt`, `lt`, `gte`, `lte`
- **Boolean fields**: `true`, `false`, `empty` (NULL)
- **Foreign key/relation fields**: `in`, `not_in`

## Frontend features

- **Search-bar design**: Clean, modern, Material Design-inspired palette (blues)
- **Badge tags**: Each filter visualized as an inline badge with:
  - Field label
  - Value summary (count for FK, truncated text, etc.)
  - Remove (✕) button
- **Dropdown column menu**: Click `+` to see all filterable columns with field path hints
- **Interactive modal popup**:
  - Slide-up animation on open
  - Operator selector dropdown
  - Dynamic value editor (text input, multi-select FK picker, or none)
  - "Tout selectionner" and "Vider" buttons for FK fields
  - Dark overlay to focus attention
- **Smooth animations**: Fade-in badges, slide-down dropdown, slide-up modal
- **Responsive design**: Works on mobile and tablet
- **Action buttons**: "Appliquer" (Apply) and "Réinitialiser" (Reset)

## Frontend stack

- `django.jQuery` from Django admin (native to all Django installs)
- Admin Select2 AJAX (`admin/js/vendor/select2/select2.full.min.js`)
- Custom CSS and JS in `superfilter/static/superfilter/`

## Backend stack

- Python type introspection (`django.db.models` field types)
- Safe field path resolution with traversal support
- Query builder that generates `Q` objects per rule
- JSON rule serialization/parsing

## Installation & Usage

```python
from superfilter.admin import SuperFilterAdminMixin

@admin.register(MyModel)
class MyModelAdmin(SuperFilterAdminMixin, admin.ModelAdmin):
    list_display = ("code", "name", "owner", "owner__username", "is_active")
```

**Key points:**
- Place `SuperFilterAdminMixin` first in the MRO to ensure proper `get_queryset` chaining.
- Only model fields in `list_display` are filterable.
- Deep relations like `owner__username` work as long as they resolve to a real field.
- Computed callables in `list_display` (e.g., `admin.display` decorated methods) are automatically skipped.

## Customization

On the mixin, you can override:
- `superfilter_param_name`: URL query parameter name (default: `sf`)
- `superfilter_page_size`: FK options per page in AJAX (default: `25`)
- `superfilter_all_limit`: Max FK options when loading "all" (default: `2000`)

Example:
```python
class MyAdmin(SuperFilterAdminMixin, admin.ModelAdmin):
    superfilter_all_limit = 5000
```

## Semantics

- **"Renseigne" / `set`**: Field has a value (not null, not empty string, not false).
- **"Vide" / `not_set`**: Field is empty (null, empty string, or false).
- **Boolean "Vide" / `empty`**: Null only (distinct from `false`).
- **FK "Dans" / `in`**: Selected IDs are included.
- **FK "Pas dans" / `not_in`**: Selected IDs are excluded.
- **Text "Contient"**: Case-insensitive substring match (`icontains`).

## URL parameter format

The `sf` parameter is a JSON array of rule objects:

```json
[
  { "field": "name", "op": "contains", "value": "test" },
  { "field": "agent__id", "op": "in", "value": [1, 2, 3] },
  { "field": "is_active", "op": "true", "value": null }
]
```

Each rule is applied as an AND condition (`Q` objects connected with `&`).

## Testing

```bash
python manage.py test superfilter
```

Runs logic tests for field introspection, traversal, and operator rule generation.

