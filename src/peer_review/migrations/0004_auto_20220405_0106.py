# Generated by Django 2.2 on 2022-04-05 01:06

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('peer_review', '0003_auto_20220403_2007'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='peerreviewrequest',
            options={'ordering': ['-created_date']},
        ),
        migrations.AddField(
            model_name='peerreviewrequest',
            name='created_date',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='peerreviewrequest',
            name='updated_date',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
