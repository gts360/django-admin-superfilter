from django.contrib import admin

from superfilter.admin import SuperFilterAdminMixin
from .models import Bird, City, Location


# Register your models here.

@admin.register(Bird)
class BirdAdmin(SuperFilterAdminMixin, admin.ModelAdmin):
    list_display = ('species', 'location', 'count')
    search_fields = ('species',)
    ordering = ('species',)

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'city')
    search_fields = ('name',)
    ordering = ('name',)

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('name', 'country')
    search_fields = ('name',)
    ordering = ('name',)