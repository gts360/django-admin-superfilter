# SuperFilter AutoComplete - Quick Start Guide

## Installation & Setup (5 minutes)

### 1. Update SuperFilter

Ensure you have the latest version with autocomplete support:

```bash
pip install --upgrade django-admin-superfilter
```

### 2. Create an Autocomplete Endpoint

Create a simple view that returns data in Select2 format:

```python
# myapp/views.py
from django.http import JsonResponse
from django.views import View
from .models import Category

class CategoryAutocomplete(View):
    def get(self, request):
        q = request.GET.get('q', '').strip()
        qs = Category.objects.all()
        
        if q:
            qs = qs.filter(name__icontains=q)
        
        results = [{'id': str(obj.id), 'text': obj.name} for obj in qs[:25]]
        return JsonResponse({
            'results': results,
            'pagination': {'more': len(qs) > 25}
        })
```

### 3. Register the URL

```python
# myapp/urls.py
from django.urls import path
from .views import CategoryAutocomplete

urlpatterns = [
    path('autocomplete/category/', CategoryAutocomplete.as_view()),
]
```

### 4. Update Django Admin

```python
# myapp/admin.py
from django.contrib import admin
from superfilter.admin import SuperFilterAdminMixin
from superfilter.logic import SuperFilterField
from .models import Product

@admin.register(Product)
class ProductAdmin(SuperFilterAdminMixin, admin.ModelAdmin):
    list_display = ['name', 'category', 'price']
    
    # Enable SuperFilter with autocomplete
    superfilter_fields = [
        'name',
        'price',
        # Use autocomplete instead of FK dropdown
        SuperFilterField(
            path='category',
            label='Category',
            autocomplete_url='/myapp/autocomplete/category/',
        ),
    ]
```

### 5. Done!

Visit `/admin/myapp/product/` and start filtering with autocomplete!

## Key Points

✅ **URL Format**: Can be relative (`/path/`) or absolute (`https://...`)  
✅ **Search**: Type to filter results  
✅ **Select All**: Click button to load all categories  
✅ **Pagination**: Automatically handled  
✅ **Multi-select**: Use `in` and `not_in` operators  

## Testing

Test your autocomplete endpoint directly:

```bash
# Search with term
curl "http://localhost:8000/myapp/autocomplete/category/?q=tech"

# Fetch all (for Select All button)
curl "http://localhost:8000/myapp/autocomplete/category/?initialValue=true"
```

Expected response:

```json
{
  "results": [
    {"id": "1", "text": "Technology"},
    {"id": "2", "text": "Tech Gadgets"}
  ],
  "pagination": {
    "more": false
  }
}
```

## Common Issues

| Issue | Solution |
|-------|----------|
| Autocomplete not appearing | Verify `autocomplete_url` is set and field is in `superfilter_fields` |
| Results not loading | Test endpoint directly, check Django logs |
| "Select All" doesn't work | Ensure endpoint handles `initialValue=true` parameter |
| 404 on autocomplete URL | Check URL is registered in urls.py and app is in INSTALLED_APPS |

## Advanced Topics

### Using django-autocomplete-light

If you prefer, you can use `django-autocomplete-light`:

```bash
pip install django-autocomplete-light
```

```python
# myapp/autocomplete.py
from dal import autocomplete
from .models import Category

class CategoryAutocomplete(autocomplete.Select2QuerySetView):
    model = Category
    search_fields = ['name']
```

```python
# urls.py
from django.urls import path
from .autocomplete import CategoryAutocomplete

urlpatterns = [
    path('autocomplete/category/', CategoryAutocomplete.as_view()),
]
```

### Caching Autocomplete Results

```python
from django.views.decorators.cache import cache_page
from django.views.decorators.http import condition

class CategoryAutocomplete(View):
    def get(self, request):
        # Cache for 5 minutes
        return self._get_cached(request)
    
    @cache_page(5 * 60)
    def _get_cached(self, request):
        # Implementation
        pass
```

### Custom Field Formatting

Return additional data for formatting:

```python
results = [{
    'id': str(obj.id),
    'text': obj.name,
    'description': obj.description,  # Extra data
} for obj in qs[:25]]
```

### Dependent Autocomplete Fields

Chain multiple autocomplete fields:

```python
SuperFilterField(
    path='product__category',
    label='Category',
    autocomplete_url='/api/autocomplete/category/',
),
SuperFilterField(
    path='product',
    label='Product',
    # Add category ID if available
    autocomplete_url='/api/autocomplete/product/',
),
```

## Documentation

- **Full docs**: [AUTOCOMPLETE_USAGE.md](./AUTOCOMPLETE_USAGE.md)
- **Examples**: [AUTOCOMPLETE_EXAMPLES.md](./AUTOCOMPLETE_EXAMPLES.md)
- **Implementation details**: [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md)

## API Reference

### SuperFilterField

```python
SuperFilterField(
    path='field_name',              # Django model field path
    label='Display Label',           # Label shown in filter UI
    autocomplete_url='/api/auto/',   # Autocomplete endpoint URL
    kind='autocomplete',             # Auto-detected if autocomplete_url set
    input_field=None,                # Optional custom field for filtering
)
```

### Autocomplete Endpoint

**Request Query Parameters:**
- `q`: Search term
- `page`: Page number (1-based)
- `initialValue=true`: Request all values

**Response Format:**
```json
{
  "results": [
    {"id": "value", "text": "Display Text"}
  ],
  "pagination": {"more": false}
}
```

## Performance Tips

1. **Add database indexes** to search fields
2. **Use pagination** - always implement page parameter
3. **Limit results** - return max 25-50 per page
4. **Cache where possible** - use Django's caching
5. **Test directly** - curl the endpoint to verify performance

## Next Steps

- Read [AUTOCOMPLETE_USAGE.md](./AUTOCOMPLETE_USAGE.md) for complete documentation
- Check [AUTOCOMPLETE_EXAMPLES.md](./AUTOCOMPLETE_EXAMPLES.md) for more examples
- Review [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md) for technical details

---

**Need help?** Check the documentation files or test your autocomplete endpoint directly with curl.
