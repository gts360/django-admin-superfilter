from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('superfilter', '0001_savedsuperfilter'),
    ]

    operations = [
        migrations.AddField(
            model_name='savedsuperfilter',
            name='columns',
            field=models.JSONField(blank=True, default=list),
        ),
    ]

