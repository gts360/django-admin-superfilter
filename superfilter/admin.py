from django.contrib import admin
from django.contrib.admin.views.main import ChangeList
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.http import JsonResponse
from django.urls import path

from superfilter.logic import (
    apply_rules,
    get_custom_superfilter_map,
    list_filterable_fields,
    parse_rules,
    resolve_model_field,
    serialize_fields,
)
from superfilter.models import SavedSuperFilter


class SuperFilterChangeList(ChangeList):
    superfilter_param_name = "sf"
    superfilter_columns_param_name = "sfc"

    def get_filters_params(self, params=None):
        lookup_params = super().get_filters_params(params)
        lookup_params.pop(self.superfilter_param_name, None)
        lookup_params.pop(self.superfilter_columns_param_name, None)
        return lookup_params


class SuperFilterAdminMixin:
    superfilter_param_name = "sf"
    superfilter_columns_param_name = "sfc"
    superfilter_fields = None
    superfilter_page_size = 25
    superfilter_all_limit = 2000

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Monkey patch get_list_display as overriding does not catch
        # The case where subclass does not relay on super().get_list_display() and respect it.
        self._orig_get_list_display = self.get_list_display
        self.get_list_display = self.patched_get_list_display

        self._orig_get_queryset = self.get_queryset
        self.get_queryset = self.patched_get_queryset

    class Media:
        css = {
            "all": (
                "admin/css/vendor/select2/select2.min.css",
                "superfilter/superfilter.css",
            )
        }
        js = (
            "admin/js/vendor/select2/select2.full.min.js",
            "superfilter/superfilter.js",
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "superfilter/meta/",
                self.admin_site.admin_view(self.superfilter_meta_view),
                name=f"{self.opts.app_label}_{self.opts.model_name}_superfilter_meta",
            ),
            path(
                "superfilter/fk-options/",
                self.admin_site.admin_view(self.superfilter_fk_options_view),
                name=f"{self.opts.app_label}_{self.opts.model_name}_superfilter_fk_options",
            ),
            path(
                "superfilter/save/",
                self.admin_site.admin_view(self.superfilter_save_view),
                name=f"{self.opts.app_label}_{self.opts.model_name}_superfilter_save",
            ),
            path(
                "superfilter/delete/<int:pk>/",
                self.admin_site.admin_view(self.superfilter_delete_view),
                name=f"{self.opts.app_label}_{self.opts.model_name}_superfilter_delete",
            ),
        ]
        return custom_urls + urls

    def get_superfilter_default_list_display(self, request):
        return list(self._orig_get_list_display(request))

    @staticmethod
    def _colname(coldef):
        # Extract string id of column (as list_display supports also callables and uses __name__ to identify them)
        return coldef.__name__ if hasattr(coldef, '__name__') else str(coldef)

    def _normalize_selected_columns(self, requested_columns, available_columns):
        available = { self._colname(col): col for col in available_columns }
        selected = [str(col) for col in (requested_columns or []) if str(col) in available]
        if not selected:
            return available_columns
        ordered = []
        seen = set()
        for col in selected:
            if col not in seen:
                ordered.append(available[col])
                seen.add(col)
        return ordered or available_columns

    def parse_superfilter_columns(self, raw_columns):
        if not raw_columns:
            return None
        if isinstance(raw_columns, (list, tuple)):
            return [str(item) for item in raw_columns]
        raw_columns = str(raw_columns).strip()
        if not raw_columns:
            return None
        try:
            import json
            parsed = json.loads(raw_columns)
        except Exception:
            return None
        if not isinstance(parsed, list):
            return None
        return [str(item) for item in parsed]

    def get_superfilter_selected_columns(self, request):
        available_columns = self.get_superfilter_default_list_display(request)
        requested = self.parse_superfilter_columns(request.GET.get(self.superfilter_columns_param_name))
        if requested is not None:
            return self._normalize_selected_columns(requested, available_columns)

        return list(available_columns)

    def patched_get_list_display(self, request):
        return list(self.get_superfilter_selected_columns(request))

    def get_superfilter_source_fields(self, request):
        source_fields = self.superfilter_fields
        if source_fields is None:
            source_fields = self.get_superfilter_default_list_display(request)
        return source_fields

    def get_superfilter_fields(self, request):
        return list_filterable_fields(self, request, source_fields=self.get_superfilter_source_fields(request))

    def get_superfilter_custom_fields(self, request):
        return get_custom_superfilter_map(self, request, source_fields=self.get_superfilter_source_fields(request))

    def get_superfilter_allowed_field_paths(self, request):
        return {f.path for f in self.get_superfilter_fields(request)}

    def _serialize_column_options(self, request):
        return [
            {
                'path': self._colname(item),
                'label': self.get_column_label(item),
            }
            for item in self.get_superfilter_default_list_display(request)
        ]

    def get_column_label(self, item):
        if item == '__str__':
            return str(self.model._meta.verbose_name).capitalize()
        if hasattr(item, 'short_description'):
            return item.short_description
        try:
            return str(self.get_changelist_instance_label(item))
        except Exception:
            return str(item).replace('_', ' ').capitalize()

    def get_changelist_instance_label(self, item):
        if callable(item):
            return getattr(item, 'short_description', None) or getattr(item, '__name__', str(item))
        if hasattr(self, item):
            attr = getattr(self, item)
            return getattr(attr, 'short_description', None) or item
        try:
            field = self.model._meta.get_field(item)
            return str(field.verbose_name).capitalize()
        except Exception:
            return item

    def _get_saved_filters_payload(self, request):
        if not getattr(request, 'user', None) or not request.user.is_authenticated:
            return []
        return list(
            SavedSuperFilter.objects.filter(
                user=request.user,
                app_label=self.opts.app_label,
                model_name=self.opts.model_name,
            ).order_by('-created_at', '-id').values('id', 'name', 'rules', 'columns', 'updated_at', 'created_at')
        )

    def superfilter_meta_view(self, request):
        fields = self.get_superfilter_fields(request)
        return JsonResponse(
            {
                "param": self.superfilter_param_name,
                "columnsParam": self.superfilter_columns_param_name,
                "fields": serialize_fields(fields),
                "rules": parse_rules(request.GET.get(self.superfilter_param_name)),
                "columns": self._serialize_column_options(request),
                "selectedColumns": [self._colname(col) for col in self.get_superfilter_selected_columns(request)],
                "fkOptionsUrl": "superfilter/fk-options/",
                "saveUrl": "superfilter/save/",
                "deleteUrlTemplate": "superfilter/delete/__ID__/",
                "savedFilters": self._get_saved_filters_payload(request),
            }
        )

    def _resolve_related_model_for_path(self, path: str):
        field = resolve_model_field(self.model, path)
        related_model = getattr(field, "related_model", None)
        if not related_model:
            raise FieldDoesNotExist(f"'{path}' is not a relation field")
        return related_model

    def _get_related_queryset(self, request, related_model, term: str):
        qs = related_model._default_manager.all()
        related_admin = self.admin_site._registry.get(related_model)
        if related_admin and term:
            qs, _ = related_admin.get_search_results(request, qs, term)
        elif term:
            text_fields = [
                f.name
                for f in related_model._meta.get_fields()
                if isinstance(f, (models.CharField, models.TextField)) and not f.many_to_many and not f.one_to_many
            ]
            if text_fields:
                query = models.Q()
                for field_name in text_fields[:3]:
                    query |= models.Q(**{f"{field_name}__icontains": term})
                qs = qs.filter(query)
            elif term.isdigit():
                qs = qs.filter(pk=int(term))
        return qs.order_by("pk")

    def superfilter_fk_options_view(self, request):
        allowed_paths = self.get_superfilter_allowed_field_paths(request)
        path = request.GET.get("field", "")
        term = request.GET.get("q", "").strip()
        page = int(request.GET.get("page", "1") or "1")
        all_values = request.GET.get("all") == "1"

        if path not in allowed_paths:
            return JsonResponse({"results": [], "pagination": {"more": False}}, status=400)

        try:
            related_model = self._resolve_related_model_for_path(path)
        except FieldDoesNotExist:
            return JsonResponse({"results": [], "pagination": {"more": False}}, status=400)

        qs = self._get_related_queryset(request, related_model, term)

        if all_values:
            rows = list(qs[: self.superfilter_all_limit + 1])
            truncated = len(rows) > self.superfilter_all_limit
            rows = rows[: self.superfilter_all_limit]
            return JsonResponse(
                {
                    "results": [{"id": str(obj.pk), "text": str(obj)} for obj in rows],
                    "pagination": {"more": False},
                    "truncated": truncated,
                }
            )

        start = max(page - 1, 0) * self.superfilter_page_size
        stop = start + self.superfilter_page_size + 1
        rows = list(qs[start:stop])
        more = len(rows) > self.superfilter_page_size
        rows = rows[: self.superfilter_page_size]

        return JsonResponse(
            {
                "results": [{"id": str(obj.pk), "text": str(obj)} for obj in rows],
                "pagination": {"more": more},
            }
        )

    def superfilter_save_view(self, request):
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=403)

        name = (request.POST.get('name') or '').strip()
        if not name:
            return JsonResponse({'error': 'Nom requis'}, status=400)

        rules = parse_rules(request.POST.get(self.superfilter_param_name))
        columns = self._normalize_selected_columns(
            self.parse_superfilter_columns(request.POST.get(self.superfilter_columns_param_name)),
            self.get_superfilter_default_list_display(request),
        )
        saved_filter, _ = SavedSuperFilter.objects.update_or_create(
            user=request.user,
            app_label=self.opts.app_label,
            model_name=self.opts.model_name,
            name=name,
            defaults={'rules': rules, 'columns': columns},
        )
        return JsonResponse(
            {
                'savedFilter': {
                    'id': saved_filter.id,
                    'name': saved_filter.name,
                    'rules': saved_filter.rules,
                    'columns': saved_filter.columns,
                    'updated_at': saved_filter.updated_at,
                    'created_at': saved_filter.created_at,
                },
                'savedFilters': self._get_saved_filters_payload(request),
            }
        )

    def superfilter_delete_view(self, request, pk):
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=403)

        deleted, _ = SavedSuperFilter.objects.filter(
            pk=pk,
            user=request.user,
            app_label=self.opts.app_label,
            model_name=self.opts.model_name,
        ).delete()
        if not deleted:
            return JsonResponse({'error': 'Filtre introuvable'}, status=404)
        return JsonResponse({'savedFilters': self._get_saved_filters_payload(request)})

    def patched_get_queryset(self, request):
        qs = self._orig_get_queryset(request)
        rules = parse_rules(request.GET.get(self.superfilter_param_name))
        if not rules:
            return qs
        return apply_rules(request,
            qs,
            self.model,
            self.get_superfilter_allowed_field_paths(request),
            rules,
            custom_fields=self.get_superfilter_custom_fields(request),
        )

    def get_changelist(self, request, **kwargs):
        base_class = SuperFilterChangeList
        param_name = self.superfilter_param_name
        columns_param_name = self.superfilter_columns_param_name

        class _ModelSuperFilterChangeList(base_class):
            superfilter_param_name = param_name
            superfilter_columns_param_name = columns_param_name

        return _ModelSuperFilterChangeList
