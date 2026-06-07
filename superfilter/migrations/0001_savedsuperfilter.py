from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SavedSuperFilter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('app_label', models.CharField(max_length=100)),
                ('model_name', models.CharField(max_length=100)),
                ('name', models.CharField(max_length=120)),
                ('rules', models.JSONField(blank=True, default=list)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='saved_superfilters', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Filtre enregistré',
                'verbose_name_plural': 'Filtres enregistrés',
                'ordering': ['-updated_at', '-id'],
                'unique_together': {('user', 'app_label', 'model_name', 'name')},
            },
        ),
    ]

