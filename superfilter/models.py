from django.conf import settings
from django.db import models


class SavedSuperFilter(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE, related_name='saved_superfilters')
    app_label = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    name = models.CharField(max_length=120)
    rules = models.JSONField(default=list, blank=True)
    columns = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Filtre enregistré'
        verbose_name_plural = 'Filtres enregistrés'
        ordering = ['-created_at', '-id']
        unique_together = [('user', 'app_label', 'model_name', 'name')]

    def __str__(self):
        return self.name


class SuperFilterExportLock(models.Model):
    hostname = models.CharField(max_length=255, db_index=True)
    token = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        models.SET_NULL,
        related_name='superfilter_export_locks',
        null=True,
        blank=True,
    )
    app_label = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Verrou export superfilter'
        verbose_name_plural = 'Verrous export superfilter'
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f"{self.hostname}:{self.token}"
