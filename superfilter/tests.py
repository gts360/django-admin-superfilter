import json

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase

from appagent.models import OperationVIN, TypeZoneOp, Zone
from superfilter.admin import SuperFilterAdminMixin
from superfilter.logic import (
    SuperFilterField,
    apply_rules,
    get_custom_superfilter_map,
    list_filterable_fields,
    parse_rules,
    resolve_model_field,
    serialize_fields,
)
from superfilter.models import SavedSuperFilter
from appagent.admin import PassagesFictifField


class _DummyQueryset:
    def __init__(self):
        self.last_q = None

    def filter(self, q):
        self.last_q = q
        return self

    def exclude(self, q):
        self.last_q = q
        return self

    def distinct(self):
        return self


class _DummyAdmin(admin.ModelAdmin):
    model = OperationVIN
    list_display = ("VIN", "carlog_plateforme_nom", "etat_op", "agent_affecte__carlog_employe_nom")


class _DummySuperfilterAdmin(SuperFilterAdminMixin):
    model = OperationVIN
    list_display = ("VIN", "carlog_plateforme_nom", "agent_affecte__carlog_employe_nom")


class _DummySuperfilterAdminCustomFields(SuperFilterAdminMixin):
    model = OperationVIN
    list_display = ("VIN", "carlog_plateforme_nom")
    superfilter_fields = ("etat", "date_creation")


class _CustomFieldAdmin(SuperFilterAdminMixin):
    model = OperationVIN
    superfilter_fields = ('VIN', PassagesFictifField)


class SuperfilterLogicTests(SimpleTestCase):
    databases = {'default'}

    def setUp(self):
        self.request = RequestFactory().get("/admin/appagent/operationvin/")

    def test_parse_rules_invalid_json(self):
        self.assertEqual(parse_rules("{not-valid"), [])

    def test_resolve_model_field_supports_traversal(self):
        field = resolve_model_field(OperationVIN, "agent_affecte__carlog_employe_nom")
        self.assertEqual(field.name, "carlog_employe_nom")

    def test_list_filterable_fields_ignores_computed_entries(self):
        admin_instance = _DummyAdmin(OperationVIN, admin.site)
        paths = {item.path for item in list_filterable_fields(admin_instance, self.request)}
        self.assertIn("VIN", paths)
        self.assertIn("carlog_plateforme_nom", paths)
        self.assertIn("agent_affecte__carlog_employe_nom", paths)
        self.assertNotIn("etat_op", paths)

    def test_custom_superfilter_field_in_source_fields_is_exposed(self):
        admin_instance = _CustomFieldAdmin(OperationVIN, admin.site)
        fields = admin_instance.get_superfilter_fields(self.request)
        by_path = {field.path: field for field in fields}
        self.assertIn('passages_fictifs', by_path)
        self.assertEqual(by_path['passages_fictifs'].kind, 'choice')

    def test_get_custom_superfilter_map_returns_custom_field(self):
        admin_instance = _CustomFieldAdmin(OperationVIN, admin.site)
        custom_map = admin_instance.get_superfilter_custom_fields(self.request)
        self.assertIn('passages_fictifs', custom_map)
        self.assertIsInstance(custom_map['passages_fictifs'], SuperFilterField)

    def test_apply_rules_handles_boolean_empty(self):
        qs = _DummyQueryset()
        allowed = {"agent_affecte__droit_mouvement"}
        apply_rules(qs, OperationVIN, allowed, [{"field": "agent_affecte__droit_mouvement", "op": "empty", "value": None}])
        self.assertIsNotNone(qs.last_q)

    def test_apply_rules_handles_fk_in(self):
        qs = _DummyQueryset()
        allowed = {"agent_affecte"}
        apply_rules(qs, OperationVIN, allowed, [{"field": "agent_affecte", "op": "in", "value": [1, 2, 3]}])
        self.assertIsNotNone(qs.last_q)

    def test_passages_fictif_field_apply_in(self):
        fictif_zone = Zone.objects.create(carlog_zone_id=9001, carlog_plateforme_id=1, nom='ZF1', fictif=True)
        qs = _DummyQueryset()
        field = PassagesFictifField()
        result = field.apply_rule(qs, {'field': 'passages_fictifs', 'op': 'in', 'value': [str(fictif_zone.pk)]})
        self.assertIs(result, qs)
        self.assertIsNotNone(qs.last_q)

    def test_changelist_ignores_superfilter_param(self):
        admin_instance = _DummySuperfilterAdmin(OperationVIN, admin.site)
        request = RequestFactory().get(
            "/admin/appagent/operationvin/",
            {"sf": "[]", "sfc": json.dumps(["VIN"]), "carlog_plateforme_nom__exact": "P1"},
        )

        changelist_cls = admin_instance.get_changelist(request)
        changelist = changelist_cls.__new__(changelist_cls)
        changelist.params = {"sf": "[]", "sfc": json.dumps(["VIN"]), "carlog_plateforme_nom__exact": "P1"}
        changelist.filter_params = {"sf": ["[]"], "sfc": [json.dumps(["VIN"])], "carlog_plateforme_nom__exact": ["P1"]}

        params = changelist.get_filters_params()
        self.assertNotIn("sf", params)
        self.assertNotIn("sfc", params)
        self.assertEqual(params.get("carlog_plateforme_nom__exact"), ["P1"])

    def test_meta_view_returns_rules_from_sf(self):
        admin_instance = _DummySuperfilterAdmin(OperationVIN, admin.site)
        sf_value = json.dumps([
            {"field": "VIN", "op": "contains", "value": "ABC"}
        ])
        request = RequestFactory().get(
            "/admin/appagent/operationvin/superfilter/meta/",
            {"sf": sf_value},
        )

        response = admin_instance.superfilter_meta_view(request)
        payload = json.loads(response.content)

        self.assertEqual(payload.get("param"), "sf")
        self.assertEqual(payload.get("rules"), [{"field": "VIN", "op": "contains", "value": "ABC"}])
        self.assertTrue(payload.get("columns"))
        self.assertTrue(payload.get("selectedColumns"))

    def test_superfilter_fields_override_list_display(self):
        admin_instance = _DummySuperfilterAdminCustomFields(OperationVIN, admin.site)
        fields = admin_instance.get_superfilter_fields(self.request)
        paths = {f.path for f in fields}
        self.assertEqual(paths, {"etat", "date_creation"})

    def test_choice_and_date_metadata(self):
        admin_instance = _DummySuperfilterAdminCustomFields(OperationVIN, admin.site)
        payload = serialize_fields(admin_instance.get_superfilter_fields(self.request))
        by_path = {item["path"]: item for item in payload}

        self.assertEqual(by_path["etat"]["kind"], "choice")
        self.assertIn("in", by_path["etat"]["operators"])
        self.assertNotIn("eq", by_path["etat"]["operators"])
        self.assertTrue(by_path["etat"]["choices"])

        self.assertEqual(by_path["date_creation"]["kind"], "datetime")
        self.assertIn("between", by_path["date_creation"]["operators"])
        self.assertEqual(by_path["date_creation"]["inputType"], "datetime-local")

    def test_apply_rules_handles_choice_in(self):
        qs = _DummyQueryset()
        allowed = {"etat"}
        apply_rules(qs, OperationVIN, allowed, [{"field": "etat", "op": "in", "value": ["ATT", "AFF"]}])
        self.assertIsNotNone(qs.last_q)

    def test_apply_rules_handles_date_between(self):
        qs = _DummyQueryset()
        allowed = {"date_creation"}
        apply_rules(
            qs,
            OperationVIN,
            allowed,
            [{"field": "date_creation", "op": "between", "value": ["2026-01-01T00:00", "2026-12-31T23:59"]}],
        )
        self.assertIsNotNone(qs.last_q)

    def test_apply_rules_text_in(self):
        qs = _DummyQueryset()
        allowed = {"VIN"}
        apply_rules(qs, OperationVIN, allowed, [{"field": "VIN", "op": "in", "value": ["VF1234", "WDB5678"]}])
        self.assertIsNotNone(qs.last_q)

    def test_apply_rules_text_not_in(self):
        qs = _DummyQueryset()
        allowed = {"VIN"}
        apply_rules(qs, OperationVIN, allowed, [{"field": "VIN", "op": "not_in", "value": ["VF1234"]}])
        self.assertIsNotNone(qs.last_q)


class SuperfilterSavedFilterTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = get_user_model().objects.create_user(username='sfuser', password='testpass')
        self.admin_instance = _DummySuperfilterAdmin(OperationVIN, admin.site)

    def test_meta_view_returns_saved_filters(self):
        SavedSuperFilter.objects.create(
            user=self.user,
            app_label='appagent',
            model_name='operationvin',
            name='Mon filtre',
            rules=[{'field': 'VIN', 'op': 'contains', 'value': 'ABC'}],
            columns=['VIN', 'carlog_plateforme_nom'],
        )
        request = self.factory.get('/admin/appagent/operationvin/superfilter/meta/')
        request.user = self.user

        response = self.admin_instance.superfilter_meta_view(request)
        payload = json.loads(response.content)
        self.assertEqual(len(payload['savedFilters']), 1)
        self.assertEqual(payload['savedFilters'][0]['name'], 'Mon filtre')
        self.assertEqual(payload['savedFilters'][0]['columns'], ['VIN', 'carlog_plateforme_nom'])

    def test_meta_view_orders_saved_filters_by_created_most_recent_first(self):
        SavedSuperFilter.objects.create(
            user=self.user,
            app_label='appagent',
            model_name='operationvin',
            name='Ancien',
            rules=[],
        )
        SavedSuperFilter.objects.create(
            user=self.user,
            app_label='appagent',
            model_name='operationvin',
            name='Récent',
            rules=[],
        )
        request = self.factory.get('/admin/appagent/operationvin/superfilter/meta/')
        request.user = self.user

        response = self.admin_instance.superfilter_meta_view(request)
        payload = json.loads(response.content)
        self.assertEqual([item['name'] for item in payload['savedFilters'][:2]], ['Récent', 'Ancien'])

    def test_save_view_creates_saved_filter(self):
        request = self.factory.post(
            '/admin/appagent/operationvin/superfilter/save/',
            {
                'name': 'Important',
                'sf': json.dumps([{'field': 'VIN', 'op': 'contains', 'value': 'ABC'}]),
                'sfc': json.dumps(['carlog_plateforme_nom', 'VIN']),
            },
        )
        request.user = self.user

        response = self.admin_instance.superfilter_save_view(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['savedFilter']['name'], 'Important')
        self.assertEqual(payload['savedFilter']['columns'], ['carlog_plateforme_nom', 'VIN'])
        self.assertEqual(len(payload['savedFilters']), 1)
        self.assertTrue(SavedSuperFilter.objects.filter(user=self.user, name='Important').exists())

    def test_delete_view_removes_saved_filter(self):
        saved_filter = SavedSuperFilter.objects.create(
            user=self.user,
            app_label='appagent',
            model_name='operationvin',
            name='À supprimer',
            rules=[],
        )
        request = self.factory.post(f'/admin/appagent/operationvin/superfilter/delete/{saved_filter.pk}/')
        request.user = self.user

        response = self.admin_instance.superfilter_delete_view(request, saved_filter.pk)
        payload = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['savedFilters'], [])
        self.assertFalse(SavedSuperFilter.objects.filter(pk=saved_filter.pk).exists())

    def test_get_list_display_uses_selected_columns_order(self):
        request = self.factory.get('/admin/appagent/operationvin/', {'sfc': json.dumps(['carlog_plateforme_nom', 'VIN'])})
        request.user = self.user
        self.assertEqual(self.admin_instance.get_list_display(request), ('carlog_plateforme_nom', 'VIN'))

    def test_get_list_display_uses_saved_columns_when_no_querystring(self):
        SavedSuperFilter.objects.create(
            user=self.user,
            app_label='appagent',
            model_name='operationvin',
            name='Colonnes',
            rules=[],
            columns=['agent_affecte__carlog_employe_nom', 'VIN'],
        )
        request = self.factory.get('/admin/appagent/operationvin/')
        request.user = self.user
        self.assertEqual(self.admin_instance.get_list_display(request), ('agent_affecte__carlog_employe_nom', 'VIN'))
