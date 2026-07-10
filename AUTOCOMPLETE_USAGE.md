# AutoComplete URL Support in SuperFilter

## Overview

SuperFilter now supports custom Django autocomplete URLs via the `SuperFilterField` class with the `autocomplete_url` parameter. This allows you to use any Django autocomplete endpoint (from `django-autocomplete-light` or custom implementations) instead of relying on fixed choice lists.

## Basic Usage

### Simple AutoComplete Field

```python
from django.contrib import admin
from superfilter.admin import SuperFilterAdminMixin
from superfilter.logic import SuperFilterField
from myapp.models import MyModel

class MyModelAdmin(SuperFilterAdminMixin, admin.ModelAdmin):
    superfilter_fields = [
        # Use autocomplete instead of FK choices
        SuperFilterField(
            path='related_field',
            label='Related Field',
            autocomplete_url='/admin/api/select2/person/'  # Your autocomplete URL
        ),
        'other_field',
    ]

admin.site.register(MyModel, MyModelAdmin)
```

## Parameters

### SuperFilterField Constructor

```python
SuperFilterField(
    path: str,              # Field path to filter on
    label: str,            # Display label in the filter UI
    kind: str = None,      # Optional: 'autocomplete' (auto-detected if autocomplete_url provided)
    input_field: Field = None,  # Optional: Django field for custom filtering logic
    autocomplete_url: str = None  # Autocomplete endpoint URL
)
```

## Autocomplete URL Endpoint Requirements

Your autocomplete URL endpoint should accept the following query parameters and return data in Select2 format:

### Request Parameters

- `q` (string): Search term for filtering results
- `page` (integer): Page number for pagination (1-based)
- `initialValue` (string, "true"): Special parameter to fetch initial values without search term

### Response Format

The endpoint should return JSON in Select2 format:

```json
{
  "results": [
    {"id": "1", "text": "Item 1"},
    {"id": "2", "text": "Item 2"}
  ],
  "pagination": {
    "more": false
  }
}
```

### Example: Using django-autocomplete-light

```python
# urls.py
from django.urls import path
from dal import views as dal_views
from myapp.models import Person

urlpatterns = [
    path(
        'admin/select2/person/',
        dal_views.BaseQuerySetSequenceView.as_view(
            queryset=Person.objects.all(),
            paginate_by=25,
            create_field='name',  # Allow creating new items
        ),
        name='person-autocomplete',
    ),
]
```

### Example: Custom Autocomplete Endpoint

```python
# views.py
from django.http import JsonResponse
from django.views import View
from myapp.models import Person

class PersonAutocompleteView(View):
    def get(self, request):
        term = request.GET.get('q', '').strip()
        page = int(request.GET.get('page', 1))
        initial_value = request.GET.get('initialValue') == 'true'
        page_size = 25
        
        # Filter queryset
        qs = Person.objects.all()
        if term and not initial_value:
            qs = qs.filter(name__icontains=term)
        
        # Paginate
        start = (page - 1) * page_size
        stop = start + page_size + 1
        results = list(qs[start:stop])
        
        has_more = len(results) > page_size
        results = results[:page_size]
        
        return JsonResponse({
            'results': [
                {'id': str(obj.id), 'text': str(obj)}
                for obj in results
            ],
            'pagination': {'more': has_more}
        })

# urls.py
from django.urls import path
from .views import PersonAutocompleteView

urlpatterns = [
    path('api/select2/person/', PersonAutocompleteView.as_view(), name='person-autocomplete'),
]
```

## How It Works

1. **Initial Load**: When the filter UI loads, the autocomplete URL is sent to the frontend along with other field metadata.

2. **Search**: When a user types in the autocomplete field, JavaScript sends a request to `superfilter/autocomplete/` with:
   - `field`: The filter field path
   - `q`: The search term
   - `page`: The page number

3. **Proxy**: The `superfilter_autocomplete_view` method acts as a proxy:
   - Validates that the field is allowed
   - Retrieves the custom `SuperFilterField` configuration
   - Gets the autocomplete URL from that field
   - Forwards the request (with `initialValue` support) to the actual autocomplete endpoint
   - Returns results to the frontend in Select2 format

4. **Initial Values**: When clicking "Select All", the frontend sends `initialValue=true` to fetch all available values without search filtering.

## Advanced Usage

### Custom Filtering with input_field

You can combine `autocomplete_url` with `input_field` for advanced filtering:

```python
SuperFilterField(
    path='person__company',
    label='Company',
    autocomplete_url='/api/autocomplete/company/',
    input_field=models.ForeignKey(Company, on_delete=models.CASCADE),
)
```

### Absolute vs Relative URLs

Both absolute and relative URLs are supported:

```python
# Relative URL (recommended)
SuperFilterField(
    path='person',
    label='Person',
    autocomplete_url='/admin/autocomplete/person/'
)

# Absolute URL
SuperFilterField(
    path='person',
    label='Person',
    autocomplete_url='https://api.example.com/autocomplete/person/'
)
```

Relative URLs are automatically converted to absolute URLs using the request's base URL.

## Filtering Operations

Autocomplete fields support the following filter operations:

- `set`: Field is set (not null/empty)
- `not_set`: Field is not set (null/empty)
- `in`: Value is in the selected list
- `not_in`: Value is not in the selected list

These are automatically applied to the Django ORM query using `__in` lookups.

## Error Handling

If there's an issue fetching from the autocomplete endpoint:

- A 500 error is logged with details about the URL and error
- An empty results list is returned to prevent UI breakage
- The user can continue using the filter UI

## Performance Considerations

### Pagination

Always implement pagination in your autocomplete endpoint to handle large datasets:

```python
page_size = 25  # Adjust based on your needs
start = (page - 1) * page_size
results = qs[start:start + page_size + 1]
has_more = len(results) > page_size
```

### Search Optimization

- Use database-level search where possible (`.filter(name__icontains=term)`)
- Consider indexed search for large datasets
- Use appropriate query timeouts (default: 10 seconds)

### Caching

Consider caching autocomplete results for frequently accessed data:

```python
from django.views.decorators.cache import cache_page

@cache_page(5 * 60)  # 5 minutes
def autocomplete_view(request):
    # Your view logic
    pass
```

## Troubleshooting

### Autocomplete not appearing

1. Check that `autocomplete_url` is set on the `SuperFilterField`
2. Verify the URL is accessible and returns proper JSON format
3. Check browser console for JavaScript errors
4. Verify the field is included in `superfilter_fields`

### Results not loading

1. Test the autocomplete endpoint directly in browser
2. Check server logs for errors from the endpoint
3. Verify the endpoint returns data in the correct Select2 format
4. Check Django admin logs for the proxy view errors

### Initial Values not loading

1. Ensure your endpoint handles the `initialValue` query parameter
2. Check that results are returned for `initialValue=true` requests
3. Verify pagination works when `initialValue=true`

## Browser Compatibility

- Requires JavaScript enabled
- Requires jQuery and Select2 (included by default in Django admin)
- Works with all modern browsers

## Requirements

Optional but recommended for easier implementation:
- `django-autocomplete-light`: For built-in autocomplete endpoints
- `requests`: Required by the proxy view (already a common dependency)

The `requests` library is imported dynamically; if not available, the proxy view returns a 500 error.

## Migration from Choice Fields

To migrate from static choice fields to autocomplete:

**Before:**
```python
class MyFieldAdmin(SuperFilterAdminMixin, admin.ModelAdmin):
    superfilter_fields = ['category']  # Uses field choices
```

**After:**
```python
class MyFieldAdmin(SuperFilterAdminMixin, admin.ModelAdmin):
    superfilter_fields = [
        SuperFilterField(
            path='category',
            label='Category',
            autocomplete_url='/api/autocomplete/categories/'
        ),
    ]
```

## See Also

- [SuperFilter Documentation](./README.md)
- [django-autocomplete-light Documentation](https://django-autocomplete-light.readthedocs.io/)
- [Select2 Documentation](https://select2.org/)
