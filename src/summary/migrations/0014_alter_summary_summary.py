# Generated by Django 4.1 on 2022-11-11 00:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("summary", "0013_merge_20201119_0123"),
    ]

    operations = [
        migrations.AlterField(
            model_name="summary",
            name="summary",
            field=models.JSONField(default=None, null=True),
        ),
    ]
