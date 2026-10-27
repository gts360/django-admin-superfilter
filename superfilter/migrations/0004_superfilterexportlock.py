from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('superfilter', '0003_alter_savedsuperfilter_options'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SuperFilterExportLock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hostname', models.CharField(db_index=True, max_length=255)),
                ('token', models.CharField(max_length=64, unique=True)),
                ('app_label', models.CharField(max_length=100)),
                ('model_name', models.CharField(max_length=100)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='superfilter_export_locks', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Verrou export superfilter',
                'verbose_name_plural': 'Verrous export superfilter',
                'ordering': ['-created_at', '-id'],
            },
        ),
    ]

