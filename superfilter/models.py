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
