# SuperFilter AutoComplete Example

This example demonstrates how to set up SuperFilter with custom autocomplete URLs.

## Project Setup

### 1. Install dependencies

```bash
pip install django-autocomplete-light
# or your custom autocomplete implementation
```

### 2. Create your models

```python
# myapp/models.py
from django.db import models

class Company(models.Model):
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name

class Employee(models.Model):
    name = models.CharField(max_length=200)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    department = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.company.name})"
```

### 3. Create AutoComplete Views

#### Option A: Using django-autocomplete-light

```python
# myapp/autocomplete_views.py
from dal import autocomplete
from .models import Company, Employee

class CompanyAutocomplete(autocomplete.Select2QuerySetView):
    model = Company
    
    def get_queryset(self):
        qs = Company.objects.all()
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs

class EmployeeAutocomplete(autocomplete.Select2QuerySetView):
    model = Employee
    
    def get_queryset(self):
        qs = Employee.objects.all()
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs
```

```python
# myapp/urls.py
from django.urls import path
from .autocomplete_views import CompanyAutocomplete, EmployeeAutocomplete

app_name = 'myapp'

urlpatterns = [
    path(
        'company-autocomplete/',
        CompanyAutocomplete.as_view(),
        name='company-autocomplete',
    ),
    path(
        'employee-autocomplete/',
        EmployeeAutocomplete.as_view(),
        name='employee-autocomplete',
    ),
]
```

#### Option B: Custom Autocomplete View

```python
# myapp/views.py
from django.http import JsonResponse
from django.views import View
from django.db.models import Q
from .models import Company, Employee

class BaseAutocompleteView(View):
    """Base autocomplete view with pagination support"""
    model = None
    search_fields = ['name']
    page_size = 25
    
    def get(self, request):
        term = request.GET.get('q', '').strip()
        page = int(request.GET.get('page', 1))
        initial_value = request.GET.get('initialValue') == 'true'
        
        # Get queryset
        qs = self.model.objects.all()
        
        # Apply search
        if term and not initial_value:
            q_objects = Q()
            for field in self.search_fields:
                q_objects |= Q(**{f"{field}__icontains": term})
            qs = qs.filter(q_objects)
        
        # Order by relevance if searching
        if term:
            qs = qs.order_by('name')
        else:
            qs = qs.order_by('pk')
        
        # Paginate
        start = (page - 1) * self.page_size
        stop = start + self.page_size + 1
        results = list(qs[start:stop])
        
        has_more = len(results) > self.page_size
        results = results[:self.page_size]
        
        return JsonResponse({
            'results': [
                {'id': str(obj.pk), 'text': str(obj)}
                for obj in results
            ],
            'pagination': {'more': has_more}
        })

class CompanyAutocompleteView(BaseAutocompleteView):
    model = Company
    search_fields = ['name']

class EmployeeAutocompleteView(BaseAutocompleteView):
    model = Employee
    search_fields = ['name', 'department']

# myapp/urls.py
from django.urls import path
from .views import CompanyAutocompleteView, EmployeeAutocompleteView

app_name = 'myapp'

urlpatterns = [
    path(
        'api/autocomplete/company/',
        CompanyAutocompleteView.as_view(),
        name='company-autocomplete',
    ),
    path(
        'api/autocomplete/employee/',
        EmployeeAutocompleteView.as_view(),
        name='employee-autocomplete',
    ),
]
```

### 4. Configure Admin with SuperFilter

```python
# myapp/admin.py
from django.contrib import admin
from django.urls import reverse
from superfilter.admin import SuperFilterAdminMixin
from superfilter.logic import SuperFilterField
from .models import Company, Employee

@admin.register(Company)
class CompanyAdmin(SuperFilterAdminMixin, admin.ModelAdmin):
    list_display = ['id', 'name', 'created_at']
    search_fields = ['name']
    list_per_page = 25
    
    # Configure SuperFilter
    superfilter_fields = [
        'name',
        'created_at',
    ]

@admin.register(Employee)
class EmployeeAdmin(SuperFilterAdminMixin, admin.ModelAdmin):
    list_display = ['id', 'name', 'company', 'department', 'created_at']
    search_fields = ['name', 'department']
    list_filter = ['company', 'department']
    list_per_page = 25
    
    # Configure SuperFilter with autocomplete
    superfilter_fields = [
        'name',
        'department',
        'created_at',
        # Use autocomplete URL for company field
        SuperFilterField(
            path='company',
            label='Company (Autocomplete)',
            autocomplete_url='/myapp/api/autocomplete/company/',
        ),
    ]
```

### 5. Update main URLs

```python
# myproject/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('myapp/', include('myapp.urls')),
]
```

## Usage in Admin

1. Navigate to the Employee admin change list
2. You'll see the SuperFilter UI with a "Company (Autocomplete)" filter
3. Click to add a filter and select the Company field
4. Type to search for companies
5. Results will autocomplete as you type
6. Click "Select All" to load all available companies
7. The filter will be applied to the queryset

## Advanced Usage

### Combining Multiple Fields

```python
@admin.register(Employee)
class EmployeeAdmin(SuperFilterAdminMixin, admin.ModelAdmin):
    list_display = ['id', 'name', 'company', 'department', 'created_at']
    
    superfilter_fields = [
        # Static fields
        'name',
        'department',
        'created_at',
        
        # Autocomplete fields
        SuperFilterField(
            path='company',
            label='Company',
            autocomplete_url='/myapp/api/autocomplete/company/',
        ),
        SuperFilterField(
            path='manager',
            label='Manager',
            autocomplete_url='/myapp/api/autocomplete/employee/',
        ),
    ]
```

### Custom Filtering Logic

```python
from django.db import models

class ManagerField(SuperFilterField):
    """Custom field that only shows managers"""
    
    def __init__(self):
        super().__init__(
            path='manager',
            label='Manager',
            autocomplete_url='/myapp/api/autocomplete/employee/?is_manager=true',
        )
    
    def apply_rule(self, queryset, rule):
        # Optional: Custom filtering logic
        return super().apply_rule(queryset, rule)

@admin.register(Employee)
class EmployeeAdmin(SuperFilterAdminMixin, admin.ModelAdmin):
    superfilter_fields = [
        'name',
        ManagerField(),
    ]
```

### Relative vs Absolute URLs

```python
# Relative URL (recommended - auto-resolves to request origin)
SuperFilterField(
    path='company',
    label='Company',
    autocomplete_url='/myapp/api/autocomplete/company/',
)

# Absolute URL
SuperFilterField(
    path='company',
    label='Company',
    autocomplete_url='https://api.example.com/autocomplete/company/',
)

# Using Django reverse
from django.urls import reverse

SuperFilterField(
    path='company',
    label='Company',
    autocomplete_url=reverse('myapp:company-autocomplete'),
)
```

## Testing

### Test the autocomplete endpoint directly

```bash
# In your browser or with curl
curl "http://localhost:8000/myapp/api/autocomplete/company/?q=acme&page=1"

# Or
curl "http://localhost:8000/myapp/api/autocomplete/company/?initialValue=true&page=1"
```

### Expected response

```json
{
  "results": [
    {"id": "1", "text": "Acme Corporation"},
    {"id": "2", "text": "Acme Industries"}
  ],
  "pagination": {
    "more": false
  }
}
```

### Test through Django admin

1. Go to `/admin/myapp/employee/`
2. Open browser DevTools (F12)
3. Go to Network tab
4. Add a filter with the Company autocomplete field
5. Watch the requests to `/superfilter/autocomplete/`
6. Type to see `q` parameter changes
7. Click "Select All" to see `initialValue=true`

## Troubleshooting

### "No results" when searching

1. Check the autocomplete endpoint directly:
   ```bash
   curl "http://localhost:8000/myapp/api/autocomplete/company/?q=test"
   ```

2. Verify search_fields are correct in your autocomplete view

3. Check database for test data

### Autocomplete URL showing 404

1. Verify the URL is correctly registered in urls.py
2. Check that the app is included in INSTALLED_APPS
3. Run `python manage.py collectstatic` if serving static files

### Ajax errors in browser console

1. Check Django logs for the proxy view errors
2. Verify CSRF token is being sent (Select2 handles this)
3. Check that requests library is installed:
   ```bash
   pip install requests
   ```

## Performance Tips

1. **Index search fields**: Add database indexes to fields used in search
   ```python
   class Company(models.Model):
       name = models.CharField(max_length=200, db_index=True)
   ```

2. **Limit initial result set**: Don't load all results on page load
   ```python
   class CompanyAutocomplete(BaseAutocompleteView):
       def get(self, request):
           # Only return results if there's a search term
           if not request.GET.get('q'):
               return JsonResponse({
                   'results': [],
                   'pagination': {'more': False}
               })
           # ... rest of the logic
   ```

3. **Use pagination**: Always paginate results, don't return all at once

4. **Cache heavily accessed data**: Use Django's caching framework

## See Also

- [AUTOCOMPLETE_USAGE.md](./AUTOCOMPLETE_USAGE.md) - Detailed documentation
- [README.md](./README.md) - SuperFilter main documentation
- [django-autocomplete-light](https://django-autocomplete-light.readthedocs.io/)
