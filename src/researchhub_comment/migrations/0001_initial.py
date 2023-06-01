# Generated by Django 4.1 on 2023-06-01 11:50

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="EncryptComment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("encryption_key", models.CharField(max_length=44)),
            ],
        ),
        migrations.CreateModel(
            name="RhCommentThreadModel",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_date", models.DateTimeField(auto_now_add=True)),
                ("updated_date", models.DateTimeField(auto_now_add=True)),
                ("object_id", models.PositiveIntegerField()),
                (
                    "thread_type",
                    models.CharField(
                        choices=[
                            ("GENERIC_COMMENT", "GENERIC_COMMENT"),
                            ("INNER_CONTENT_COMMENT", "INNER_CONTENT_COMMENT"),
                            ("ANSWER", "ANSWER"),
                            ("REVIEW", "REVIEW"),
                            ("SUMMARY", "SUMMARY"),
                        ],
                        default="GENERIC_COMMENT",
                        max_length=144,
                    ),
                ),
                (
                    "thread_reference",
                    models.CharField(
                        blank=True,
                        help_text="A thread may need a special referencing tool. Use this field for such a case",
                        max_length=144,
                        null=True,
                    ),
                ),
                (
                    "content_type",
                    models.ForeignKey(
                        help_text='\n            Forms a contenttype - generic relation between "origin" model to target model\n            Target models should have its own (i.e. field_name = GenericRelation(OriginModel))\n        ',
                        on_delete=django.db.models.deletion.CASCADE,
                        to="contenttypes.contenttype",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="created_%(app_label)s_%(class)s",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        help_text="Last user to update the instance",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="updated_%(app_label)s_%(class)s",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="RhCommentModel",
            fields=[
                (
                    "encryptcomment_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="researchhub_comment.encryptcomment",
                    ),
                ),
                ("created_date", models.DateTimeField(auto_now_add=True)),
                ("updated_date", models.DateTimeField(auto_now=True)),
                ("is_public", models.BooleanField(default=True)),
                ("is_removed", models.BooleanField(default=False)),
                (
                    "is_removed_date",
                    models.DateTimeField(blank=True, default=None, null=True),
                ),
                ("score", models.IntegerField(default=0)),
                (
                    "context_title",
                    models.TextField(
                        blank=True,
                        help_text="\n            Provides a sumamry / headline to give context to the comment.\n            A commont use-case for this is for inline comments & citation comments\n        ",
                        null=True,
                    ),
                ),
                (
                    "comment_content_src",
                    models.FileField(
                        blank=True,
                        help_text="Src may be blank but never null upon saving.",
                        max_length=1024,
                        null=True,
                        upload_to="uploads/rh_comment/%Y/%m/%d/",
                    ),
                ),
                ("comment_content_json", models.JSONField(blank=True, null=True)),
                (
                    "comment_content_type",
                    models.CharField(
                        choices=[
                            ("CK_EDITOR", "CK_EDITOR"),
                            ("QUILL_EDITOR", "QUILL_EDITOR"),
                            ("TEXT", "TEXT"),
                        ],
                        default="QUILL_EDITOR",
                        max_length=144,
                    ),
                ),
                ("is_accepted_answer", models.BooleanField(null=True)),
                ("legacy_id", models.PositiveIntegerField(blank=True, null=True)),
                (
                    "legacy_model_type",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("LEGACY_COMMENT", "LEGACY_COMMENT"),
                            ("LEGACY_REPLY", "LEGACY_REPLY"),
                            ("LEGACY_THREAD", "LEGACY_THREAD"),
                        ],
                        max_length=144,
                        null=True,
                    ),
                ),
                ("anonymous", models.BooleanField(null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="created_%(app_label)s_%(class)s",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="children",
                        to="researchhub_comment.rhcommentmodel",
                    ),
                ),
                (
                    "thread",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rh_comments",
                        to="researchhub_comment.rhcommentthreadmodel",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        help_text="Last user to update the instance",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="updated_%(app_label)s_%(class)s",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("researchhub_comment.encryptcomment", models.Model),
        ),
    ]
