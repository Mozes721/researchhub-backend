from django.core.validators import FileExtensionValidator
from django.db import models
from jsonschema import validate

from citation.constants import CITATION_TYPE_CHOICES
from citation.related_models.citation_project_model import CitationProject
from researchhub_document.models import ResearchhubUnifiedDocument
from user.models import Organization
from utils.models import DefaultAuthenticatedModel


class CitationEntry(DefaultAuthenticatedModel):

    """--- MODEL FIELDS ---"""

    attachment = models.FileField(
        blank=True,
        default=None,
        max_length=1024,
        null=True,
        upload_to="uploads/citation_entry/attachment/%Y/%m/%d",
        validators=[FileExtensionValidator(["pdf"])],
    )
    citation_type = models.CharField(max_length=32, choices=CITATION_TYPE_CHOICES)
    checksum = models.CharField(max_length=16)
    doi = models.CharField(max_length=255, default=None, null=True, blank=True)
    organization = models.ForeignKey(
        Organization, related_name="created_citations", on_delete=models.CASCADE
    )
    unified_doc = models.ForeignKey(
        ResearchhubUnifiedDocument,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="citation_entries",
    )
    project = models.ForeignKey(
        CitationProject,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="citations",
        related_query_name="citations",
    )
    fields = models.JSONField()

    """--- METHODS ---"""

    def is_user_allowed_to_edit(self, user):
        belonging_project = self.project
        if belonging_project is None:
            org_permissions = self.organization.permissions
            return org_permissions.has_editor_user(
                user
            ) or org_permissions.has_admin_user(user)
        else:
            project_permissions = belonging_project.permissions
            return project_permissions.has_editor_user(
                user
            ) or project_permissions.has_admin_user(user)
