import math

from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import JSONField
from django.db import models, transaction
from django.db.models import Count, Q, Avg
from django_elasticsearch_dsl_drf.wrappers import dict_to_obj
from django.db.models.functions import Extract

from manubot.cite.doi import get_doi_csl_item

from paper.utils import (
    MANUBOT_PAPER_TYPES,
    populate_metadata_from_manubot_url,
    populate_metadata_from_manubot_pdf_url,
    populate_pdf_url_from_journal_url,
    populate_metadata_from_pdf,
    populate_metadata_from_crossref
)
from .tasks import (
    celery_extract_figures,
    celery_extract_pdf_preview,
    celery_extract_meta_data,
    celery_extract_twitter_comments
)
from researchhub.lib import CREATED_LOCATIONS
from researchhub.settings import TESTING
from summary.models import Summary
from hub.models import Hub
from purchase.models import Purchase

from utils.http import check_url_contains_pdf
from utils.arxiv import Arxiv
from utils.crossref import Crossref
from utils.semantic_scholar import SemanticScholar

HOT_SCORE_WEIGHT = 5
HELP_TEXT_IS_PUBLIC = (
    'Hides the paper from the public.'
)
HELP_TEXT_IS_REMOVED = (
    'Hides the paper because it is not allowed.'
)


class Paper(models.Model):
    CREATED_LOCATION_PROGRESS = CREATED_LOCATIONS['PROGRESS']
    CREATED_LOCATION_CHOICES = [
        (CREATED_LOCATION_PROGRESS, 'Progress')
    ]

    uploaded_date = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_date = models.DateTimeField(auto_now=True)
    is_public = models.BooleanField(
        default=True,
        help_text=HELP_TEXT_IS_PUBLIC
    )
    is_removed = models.BooleanField(
        default=False,
        help_text=HELP_TEXT_IS_REMOVED
    )
    score = models.IntegerField(default=0, db_index=True)
    discussion_count = models.IntegerField(default=0, db_index=True)
    hot_score = models.IntegerField(default=0, db_index=True)

    # Moderators are obsolete, in favor of super mods on the user
    moderators = models.ManyToManyField(
        'user.User',
        related_name='moderated_papers',
        blank=True
    )
    authors = models.ManyToManyField(
        'user.Author',
        related_name='authored_papers',
        blank=True
    )
    hubs = models.ManyToManyField(
        'hub.Hub',
        related_name='papers',
        blank=True
    )
    summary = models.ForeignKey(
        Summary,
        blank=True,
        null=True,
        related_name='papers',
        on_delete=models.SET_NULL
    )
    file = models.FileField(
        max_length=512,
        upload_to='uploads/papers/%Y/%m/%d',
        default=None,
        null=True,
        blank=True
    )
    file_created_location = models.CharField(
        choices=CREATED_LOCATION_CHOICES,
        max_length=255,
        default=None,
        null=True,
        blank=True
    )
    retrieved_from_external_source = models.BooleanField(default=False)
    external_source = models.CharField(
        max_length=255,
        default=None,
        null=True,
        blank=True
    )

    # User generated
    title = models.CharField(max_length=1024)  # User generated title
    tagline = models.CharField(
        max_length=255,
        default=None,
        null=True,
        blank=True
    )
    uploaded_by = models.ForeignKey(
        'user.User',
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )

    # Metadata
    doi = models.CharField(
        max_length=255,
        default=None,
        null=True,
        blank=True,
        unique=True
    )
    alternate_ids = JSONField(default=dict)
    paper_title = models.CharField(  # Official paper title
        max_length=1024,
        default=None,
        null=True,
        blank=True
    )
    paper_publish_date = models.DateField(null=True)
    raw_authors = JSONField(blank=True, null=True)
    abstract = models.TextField(
        default=None,
        null=True,
        blank=True
    )
    publication_type = models.CharField(
        max_length=255,
        default=None,
        null=True,
        blank=True
    )
    references = models.ManyToManyField(
        'self',
        symmetrical=False,
        related_name='referenced_by',
        blank=True
    )
    # Can be the url entered by users during upload (seed URL)
    url = models.URLField(
        max_length=1024,
        default=None,
        null=True,
        blank=True,
        unique=True
    )
    pdf_url = models.URLField(
        max_length=1024,
        default=None,
        null=True,
        blank=True
    )
    pdf_license = models.CharField(
        max_length=255,
        default=None,
        null=True,
        blank=True
    )
    pdf_license_url = models.URLField(
        max_length=1024,
        default=None,
        null=True,
        blank=True
    )
    csl_item = JSONField(
        default=None,
        null=True,
        blank=True,
        help_text='bibliographic metadata as a single '
                  'Citation Styles Language JSON item.'
    )
    oa_pdf_location = JSONField(
        default=None,
        null=True,
        blank=True,
        help_text='PDF availability in Unpaywall OA Location format.'
    )

    purchases = GenericRelation(
        'purchase.Purchase',
        object_id_field='object_id',
        content_type_field='content_type',
        related_query_name='paper'
    )
    slug = models.SlugField(max_length=1024)

    class Meta:
        ordering = ['-paper_publish_date']

    def __str__(self):
        if self.title and self.uploaded_by:
            return '{} - {}'.format(self.title, self.uploaded_by)
        elif self.title:
            return self.title
        else:
            return 'titleless paper'

    @property
    def is_hidden(self):
        return (not self.is_public) or self.is_removed

    @property
    def owners(self):
        mods = list(self.moderators.all())
        authors = list(self.authors.all())
        return mods + authors

    @property
    def users_to_notify(self):
        users = list(self.moderators.all())
        paper_authors = self.authors.all()
        for author in paper_authors:
            if (
                author.user
                and author.user.emailrecipient.paper_subscription.threads
                and not author.user.emailrecipient.paper_subscription.none
            ):
                users.append(author.user)
        return users

    @property
    def children(self):
        return self.threads.all()

    @classmethod
    def create_manubot_paper(cls, doi):
        csl_item = get_doi_csl_item(doi)
        return Paper.create_from_csl_item(
            csl_item,
            doi=doi,
            externally_sourced=True,
            is_public=False
        )

    @classmethod
    def create_crossref_paper(cls, identifier):
        return Crossref(id=identifier).create_paper()

    @classmethod
    def create_from_csl_item(
        cls,
        csl_item,
        doi=None,
        externally_sourced=False,
        is_public=None
    ):
        """
        Create a paper object from a CSL_Item.
        This may be useful if we want to auto-populate the paper
        database at some point.
        """
        from manubot.cite.csl_item import CSL_Item

        if not isinstance(csl_item, CSL_Item):
            csl_item = CSL_Item(csl_item)

        if csl_item['type'] not in MANUBOT_PAPER_TYPES:
            return None

        is_public = True
        external_source = None
        if externally_sourced is True:
            is_public = False
            external_source = 'manubot'

        if 'DOI' in csl_item:
            doi = csl_item['DOI'].lower()

        paper_publish_date = csl_item.get_date('issued', fill=True)

        paper = cls(
            abstract=csl_item.get('abstract', None),
            doi=doi,
            is_public=is_public,
            title=csl_item.get('title', None),
            paper_title=csl_item.get('title', None),
            url=csl_item.get('URL', None),
            csl_item=csl_item,
            external_source=external_source,
            retrieved_from_external_source=externally_sourced,
            paper_publish_date=paper_publish_date
        )
        paper.save()
        return paper

    @property
    def authors_indexing(self):
        '''Authors for Elasticsearch indexing.'''
        return [self.get_full_name(author) for author in self.authors.all()]

    @property
    def discussion_count_indexing(self):
        '''Number of discussions.'''
        return self.get_discussion_count()

    @property
    def hubs_indexing(self):
        return [hub.name for hub in self.hubs.all()]

    @property
    def score_indexing(self):
        '''Score for Elasticsearch indexing.'''
        return self.calculate_score()

    @property
    def summary_indexing(self):
        if self.summary:
            return self.summary.summary_plain_text
        return ''

    @property
    def votes_indexing(self):
        all_votes = self.votes.all()
        if len(all_votes) > 0:
            return [self.get_vote_for_index(vote) for vote in all_votes]
        return {}

    def calculate_hot_score(self):
        N = 1572080689
        boosts = self.purchases.filter(
            paid_status=Purchase.PAID,
            amount__gt=0
        )
        boost_exists = boosts.exists()

        if self.score >= 0 or boost_exists:
            ALGO_START_UNIX = 1575199677
            if boost_exists:
                uploaded_date = boosts.first().created_date.timestamp()
                avg_hrs = (
                    uploaded_date -
                    ALGO_START_UNIX
                ) / 3600

                boost_amount = sum(
                    map(int, boosts.values_list(
                        'amount',
                        flat=True
                    ))
                )
                boost_amount = 4 * math.log(boost_amount, 10)
            else:
                boost_amount = 0
                uploaded_date = self.uploaded_date.timestamp()
                vote_avg_epoch = self.votes.aggregate(
                    avg=Avg(
                        Extract('created_date', 'epoch'),
                        output_field=models.IntegerField()
                    )
                )['avg']

                avg_hrs = (
                    vote_avg_epoch - ALGO_START_UNIX
                ) / 3600

            avg_hrs /= 100
            score = self.score

            hot_score = math.log(max(abs(score), 1), 10)
            seconds = (uploaded_date - N) / 45000
            discussion_score = math.log(max(self.discussion_count, 1), 10)
            hot_score = (
                boost_amount + avg_hrs + hot_score + seconds + discussion_score
            ) * 1000

            self.hot_score = hot_score
        else:
            self.hot_score = 0

        self.save()

    def get_full_name(self, author_or_user):
        return f'{author_or_user.first_name} {author_or_user.last_name}'

    def get_discussion_count(self):
        thread_count = self.threads.aggregate(
            discussion_count=Count(
                1,
                filter=Q(
                    is_removed=False,
                    created_by__isnull=False,
                    source='researchhub'
                )
            )
        )['discussion_count']
        comment_count = self.threads.aggregate(
            discussion_count=Count(
                'comments',
                filter=Q(
                    comments__is_removed=False,
                    comments__created_by__isnull=False,
                    source='researchhub'
                )
            )
        )['discussion_count']
        reply_count = self.threads.aggregate(
            discussion_count=Count(
                'comments__replies',
                filter=Q(
                    comments__replies__is_removed=False,
                    comments__replies__created_by__isnull=False,
                    source='researchhub'
                )
            )
        )['discussion_count']
        return thread_count + comment_count + reply_count

    def extract_figures(self, use_celery=True):
        if TESTING:
            return

        if use_celery:
            celery_extract_figures.apply_async(
                (self.id,),
                priority=3,
                countdown=10,
            )
        else:
            celery_extract_figures(self.id)

    def extract_pdf_preview(self, use_celery=True):
        if TESTING:
            return

        if use_celery:
            celery_extract_pdf_preview.apply_async(
                (self.id,),
                priority=3,
                countdown=10,
            )
        else:
            celery_extract_pdf_preview(self.id)

    def extract_meta_data(
        self,
        title=None,
        check_title=False,
        use_celery=True
    ):
        if TESTING:
            return

        if title is None and self.paper_title:
            title = self.paper_title
        elif title is None and self.title:
            title = self.title
        elif title is None:
            return

        if use_celery:
            celery_extract_meta_data.apply_async(
                (self.id, title, check_title),
                priority=1,
                countdown=10,
            )
        else:
            celery_extract_meta_data(self.id, title, check_title)

    def extract_twitter_comments(
        self,
        use_celery=True
    ):
        if TESTING:
            return

        if use_celery:
            celery_extract_twitter_comments.apply_async(
                (self.id,),
                priority=5,
                countdown=10,
            )
        else:
            celery_extract_twitter_comments(self.id)

    def calculate_score(self):
        upvotes = self.votes.filter(vote_type=Vote.UPVOTE).count()
        downvotes = self.votes.filter(vote_type=Vote.DOWNVOTE).count()
        score = upvotes - downvotes
        return score

    def get_vote_for_index(self, vote):
        wrapper = dict_to_obj({
            'vote_type': vote.vote_type,
            'updated_date': vote.updated_date,
        })

        return wrapper

    def update_summary(self, summary):
        self.summary = summary
        self.save()

    def add_references(self):
        ss_id = self.doi
        ss_id_type = SemanticScholar.ID_TYPES['doi']
        # TODO: Modify this to try all availble alternate id keys
        if (ss_id is None) and (self.alternate_ids != {}):
            ss_id = self.alternate_ids['arxiv']
            ss_id_type = SemanticScholar.ID_TYPES['arxiv']
        if ss_id is not None:
            semantic_paper = SemanticScholar(ss_id, id_type=ss_id_type)
            references = semantic_paper.references
            referenced_by = semantic_paper.referenced_by

            if self.references.count() < 1:
                self.add_or_create_reference_papers(references, 'references')

            if self.referenced_by.count() < 1:
                self.add_or_create_reference_papers(
                    referenced_by,
                    'referenced_by'
                )

    def add_or_create_reference_papers(self, reference_list, reference_field):
        arxiv_ids = []
        dois = []
        for ref in reference_list:
            if ref['doi'] is not None:
                dois.append(ref['doi'])
            elif ref['arxivId'] is not None:
                arxiv_ids.append('arXiv:' + ref['arxivId'])
            else:
                pass

        arxiv_id_set = set(arxiv_ids)
        doi_set = set(dois)

        existing_papers = Paper.objects.filter(
            Q(doi__in=dois) | Q(alternate_ids__arxiv__in=arxiv_ids)
        )

        if reference_field == 'referenced_by':
            for existing_paper in existing_papers:
                existing_paper.references.add(self)
        else:
            self.references.add(*existing_papers)

        arxiv_id_hits = set(
            existing_papers.filter(
                doi__isnull=True
            ).values_list('alternate_ids__arxiv', flat=True)
        )
        arxiv_id_misses = arxiv_id_set.difference(arxiv_id_hits)
        self._create_reference_papers_from_arxiv_misses(
            arxiv_id_misses,
            reference_field
        )

        doi_hits = set(existing_papers.values_list('doi', flat=True))
        doi_misses = doi_set.difference(doi_hits)
        self._create_reference_papers_from_doi_misses(
            doi_misses,
            reference_field
        )

        self.save()

    def _create_reference_papers_from_arxiv_misses(
        self,
        id_list,
        reference_field
    ):
        id_count = len(id_list)
        for idx, current_id in enumerate(id_list):
            print(
                f'Creating paper from arxiv miss: {idx + 1} / {id_count}'
            )
            arxiv_paper = Arxiv(id=current_id)
            arxiv_paper.create_paper()
            arxiv_paper.add_hubs()

    def _create_reference_papers_from_doi_misses(
        self,
        id_list,
        reference_field
    ):
        id_count = len(id_list)

        for idx, current_id in enumerate(id_list):
            print(
                f'Creating paper from doi miss: {idx + 1} / {id_count}'
            )

            if not current_id:
                continue

            new_paper = None
            hubs = []

            # NOTE: Each metadata provider gives us incomplete data.
            # Semantic Scholar gives hub identifiers but publish date
            # (only offers year).
            # Manubot lacks hub identifiers and is slow.
            # Crossref lacks the paper abstract and may give a partial publish
            # date.
            #
            # Here I first create the paper with Semantic Scholar because it
            # gives the most complete data for our current frontend views and
            # it is faster than Manubot.

            crossref_paper = Crossref(id=current_id)

            semantic_paper = SemanticScholar(
                current_id,
                id_type=SemanticScholar.ID_TYPES['doi']
            )
            if semantic_paper is not None:
                if semantic_paper.hub_candidates is not None:
                    HUB_INSTANCE = 0
                    hubs = [
                        Hub.objects.get_or_create(
                            name=hub_name.lower()
                        )[HUB_INSTANCE]
                        for hub_name
                        in semantic_paper.hub_candidates
                    ]
                # TODO: Restructure this to not use transaction atomic?
                try:
                    print('Trying semantic scholar')
                    with transaction.atomic():
                        new_paper = semantic_paper.create_paper()
                        new_paper.paper_publish_date = (
                            crossref_paper.paper_publish_date
                        )
                except Exception as e:
                    print(
                        f'Error creating semantic paper: {e}',
                        'Falling back...'
                    )
                    try:
                        print('Trying manubot')
                        new_paper = Paper.create_manubot_paper(current_id)
                    except Exception as e:
                        print(
                            f'Error creating manubot paper: {e}',
                            'Falling back...'
                        )
                        try:
                            print('Trying crossref')
                            with transaction.atomic():
                                new_paper = crossref_paper.create_paper()
                                new_paper.abstract = semantic_paper.abstract
                        except Exception as e:
                            print(
                                f'Error creating crossref paper: {e}',
                            )

            if new_paper is not None:
                new_paper.hubs.add(*hubs)

                if reference_field == 'referenced_by':
                    new_paper.references.add(self)
                else:
                    self.references.add(new_paper)
                try:
                    new_paper.save()
                except Exception as e:
                    print(f'Error saving reference paper: {e}')
            else:
                print('No new paper')

    def get_promoted_score(self):
        purchases = self.purchases.filter(
            paid_status=Purchase.PAID,
        )
        if purchases.exists():
            base_score = self.score
            boost_score = sum(
                map(int, purchases.values_list('amount', flat=True))
            )
            return base_score + boost_score
        return False


class MetadataRetrievalAttempt(models.Model):
    CROSSREF_DOI = 'CROSSREF_DOI'
    CROSSREF_QUERY = 'CROSSREF_QUERY'
    MANUBOT_DOI = 'MANUBOT_DOI'
    MANUBOT_PDF_URL = 'MANUBOT_PDF_URL'
    MANUBOT_URL = 'MANUBOT_URL'
    PARSE_PDF = 'PARSE_PDF'
    PDF_FROM_URL = 'PDF_FROM_URL'

    METHOD_CHOICES = [
        (CROSSREF_DOI, CROSSREF_DOI),
        (CROSSREF_QUERY, CROSSREF_QUERY),
        (MANUBOT_DOI, MANUBOT_DOI),
        (MANUBOT_PDF_URL, MANUBOT_PDF_URL),
        (MANUBOT_URL, MANUBOT_URL),
        (PARSE_PDF, PARSE_PDF),
        (PDF_FROM_URL, PDF_FROM_URL)
    ]

    POPULATE_METADATA_METHODS = {
        MANUBOT_URL: populate_metadata_from_manubot_url,
        MANUBOT_PDF_URL: populate_metadata_from_manubot_pdf_url,
        PDF_FROM_URL: populate_pdf_url_from_journal_url,
        PARSE_PDF: populate_metadata_from_pdf,
        CROSSREF_QUERY: populate_metadata_from_crossref,
    }

    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now_add=True)
    paper = models.ForeignKey(
        Paper,
        on_delete=models.CASCADE,
        related_name='metadata_retrieval_attempts'
    )
    method = models.CharField(
        choices=METHOD_CHOICES,
        max_length=125
    )

    @classmethod
    def get_url_method_priority_list(cls, url):
        """
        Evaluates the url and returns the methods in the order they should be
        attempted to retrieve metadata.
        """
        methods = []
        if check_url_contains_pdf(url):
            methods.append(cls.MANUBOT_PDF_URL)
            # TODO: Create util functions for these methods
            methods.append(cls.PARSE_PDF)
            methods.append(cls.CROSSREF_QUERY)
        else:
            methods.append(cls.PDF_FROM_URL)
            # methods.append(cls.MANUBOT_PDF_URL)
            methods.append(cls.MANUBOT_URL)
        return methods


class Figure(models.Model):
    FIGURE = 'FIGURE'
    PREVIEW = 'PREVIEW'
    FIGURE_TYPE_CHOICES = [
        (FIGURE, 'Figure'),
        (PREVIEW, 'Preview')
    ]

    CREATED_LOCATION_PROGRESS = CREATED_LOCATIONS['PROGRESS']
    CREATED_LOCATION_CHOICES = [
        (CREATED_LOCATION_PROGRESS, 'Progress')
    ]

    file = models.FileField(
        upload_to='uploads/figures/%Y/%m/%d',
        default=None,
        null=True,
        blank=True
    )
    paper = models.ForeignKey(
        Paper,
        on_delete=models.CASCADE,
        related_name='figures'
    )
    figure_type = models.CharField(choices=FIGURE_TYPE_CHOICES, max_length=16)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'user.User',
        on_delete=models.SET_NULL,
        related_name='figures',
        null=True
    )
    created_location = models.CharField(
        choices=CREATED_LOCATION_CHOICES,
        max_length=255,
        default=None,
        null=True,
        blank=True
    )


class Vote(models.Model):
    UPVOTE = 1
    DOWNVOTE = 2
    VOTE_TYPE_CHOICES = [
        (UPVOTE, 'Upvote'),
        (DOWNVOTE, 'Downvote'),
    ]
    paper = models.ForeignKey(
        Paper,
        on_delete=models.CASCADE,
        related_name='votes',
        related_query_name='vote'
    )
    created_by = models.ForeignKey(
        'user.User',
        on_delete=models.CASCADE,
        related_name='paper_votes',
        related_query_name='paper_vote'
    )
    created_date = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_date = models.DateTimeField(auto_now=True, db_index=True)
    vote_type = models.IntegerField(choices=VOTE_TYPE_CHOICES)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['paper', 'created_by'],
                name='unique_paper_vote'
            )
        ]

    def __str__(self):
        return '{} - {}'.format(self.created_by, self.vote_type)


class Flag(models.Model):
    paper = models.ForeignKey(
        Paper,
        on_delete=models.CASCADE,
        related_name='flags',
        related_query_name='flag'
    )
    created_by = models.ForeignKey(
        'user.User',
        on_delete=models.CASCADE,
        related_name='paper_flags',
        related_query_name='paper_flag'
    )
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['paper', 'created_by'],
                name='unique_paper_flag'
            )
        ]


class AdditionalFile(models.Model):
    file = models.FileField(
        max_length=1024,
        upload_to='uploads/paper_additional_files/%Y/%m/%d',
        default=None,
        null=True,
        blank=True
    )
    paper = models.ForeignKey(
        Paper,
        on_delete=models.CASCADE,
        related_name='additional_files',
        related_query_name='additional_file'
    )
    created_by = models.ForeignKey(
        'user.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='paper_additional_files',
        related_query_name='paper_additional_file'
    )
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
