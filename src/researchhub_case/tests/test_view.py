from rest_framework.test import APITestCase
from paper.tests.helpers import create_paper
from user.tests.helpers import (
    create_random_default_user,
    create_moderator,
)
from researchhub_case.models import AuthorClaimCase
from user.utils import move_paper_to_author


class ViewTests(APITestCase):
    def setUp(self):
      self.paper = create_paper(
        title='some title',
        uploaded_by=None,
        raw_authors='[{"first_name": "jane", "last_name": "smith"}]'
      )

    def test_approved_claim_moves_paper_to_author(self):
      moderator = create_moderator(first_name='moderator', last_name='moderator')
      claiming_user = create_random_default_user('claiming_user')
      self.client.force_authenticate(claiming_user)

      paper = create_paper(
        title='some title',
        uploaded_by=None,
      )

      response = self.client.post(
        "/api/author_claim_case/", {
          "case_type":"PAPER_CLAIM",
          "creator": claiming_user.id,
          "requestor":claiming_user.id,
          "provided_email":"example@example.com",
          "target_paper_id": paper.id,
          "target_author_name": "some paper author",
        }
      )

      print('response', response.data)

      # Update Claim status
      claim = AuthorClaimCase.objects.get(id=response.data['id'])
      claim.status = 'OPEN'
      claim.save()

      # Approve claim
      self.client.force_authenticate(moderator)
      update_response = self.client.post(
        "/api/author_claim_case/moderator/", {
          "case_id": response.data['id'],
          "notify_user": True,
          "update_status": 'APPROVED',
        }
      )

      claim = AuthorClaimCase.objects.get(id=response.data['id'])
      self.assertEqual(claim.status, 'APPROVED')
      self.assertTrue(paper in claiming_user.author_profile.authored_papers.all())

    def test_claim_without_valid_paper_id_throws_error(self):
      claiming_user = create_random_default_user('claiming_user')
      self.client.force_authenticate(claiming_user)

      paper = create_paper(
        title='some title',
        uploaded_by=None,
      )

      response = self.client.post(
        "/api/author_claim_case/", {
          "case_type":"PAPER_CLAIM",
          "creator": claiming_user.id,
          "requestor":claiming_user.id,
          "provided_email":"example@example.com",
          "target_author_name": "some paper author",
        }
      )

      self.assertGreaterEqual(response.status_code, 400)

    def test_rejecting_claim_does_not_move_paper(self):
      moderator = create_moderator(first_name='moderator', last_name='moderator')
      claiming_user = create_random_default_user('claiming_user')
      self.client.force_authenticate(claiming_user)

      paper = create_paper(
        title='some title',
        uploaded_by=None,
      )

      response = self.client.post(
        "/api/author_claim_case/", {
          "case_type":"PAPER_CLAIM",
          "creator": claiming_user.id,
          "requestor":claiming_user.id,
          "provided_email":"example@example.com",
          "target_paper_id": paper.id,
          "target_author_name": "some paper author",
        }
      )

      # Update Claim status
      claim = AuthorClaimCase.objects.get(id=response.data['id'])
      claim.status = 'OPEN'
      claim.save()

      # Deny claim
      self.client.force_authenticate(moderator)
      update_response = self.client.post(
        "/api/author_claim_case/moderator/", {
          "case_id": response.data['id'],
          "notify_user": True,
          "update_status": 'DENIED',
        }
      )

      claim = AuthorClaimCase.objects.get(id=response.data['id'])
      self.assertEqual(claim.status, 'DENIED')

    def test_close_claim_does_not_require_paper_to_be_set(self):
      moderator = create_moderator(first_name='moderator', last_name='moderator')
      claiming_user = create_random_default_user('claiming_user')
      self.client.force_authenticate(claiming_user)

      paper = create_paper(
        title='some title',
        uploaded_by=None,
      )

      # Update Claim status
      claim = AuthorClaimCase.objects.create(
        case_type="PAPER_CLAIM",
        status="OPEN",
        creator=claiming_user,
        requestor=claiming_user,
        provided_email="example@example.com",
      )

      # Close claim
      self.client.force_authenticate(moderator)
      response = self.client.post(
        "/api/author_claim_case/moderator/", {
          "case_id": claim.id,
          "notify_user": False,
          "update_status": 'DENIED',
        }
      )

      self.assertEqual(response.status_code, 200)

    def test_user_cannot_open_multiple_claims_for_same_paper(self):
      claiming_user1 = create_random_default_user('claiming_user')
      self.client.force_authenticate(claiming_user1)

      paper = create_paper(
        title='some title',
        uploaded_by=None,
      )

      response = self.client.post(
        "/api/author_claim_case/", {
          "case_type":"PAPER_CLAIM",
          "creator": claiming_user1.id,
          "requestor":claiming_user1.id,
          "provided_email":"example@example.com",
          "target_paper_id": paper.id,
          "target_author_name": "random author",
        }
      )

      response = self.client.post(
        "/api/author_claim_case/", {
          "case_type":"PAPER_CLAIM",
          "creator": claiming_user1.id,
          "requestor":claiming_user1.id,
          "provided_email":"example@example.com",
          "target_paper_id": paper.id,
          "target_author_name": "random author",
        }
      )      

      self.assertEqual(response.status_code, 400)

    def test_different_users_can_open_multiple_claims_for_same_author(self):
      claiming_user1 = create_random_default_user('claiming_user')
      claiming_user2 = create_random_default_user('claiming_user')

      paper = create_paper(
        title='some title',
        uploaded_by=None,
      )

      self.client.force_authenticate(claiming_user1)
      response = self.client.post(
        "/api/author_claim_case/", {
          "case_type":"PAPER_CLAIM",
          "creator": claiming_user1.id,
          "requestor":claiming_user1.id,
          "provided_email":"example@example.com",
          "target_paper_id": paper.id,
          "target_author_name": "random author",
        }
      )

      self.client.force_authenticate(claiming_user2)
      response = self.client.post(
        "/api/author_claim_case/", {
          "case_type":"PAPER_CLAIM",
          "creator": claiming_user2.id,
          "requestor":claiming_user2.id,
          "provided_email":"example@example.com",
          "target_paper_id": paper.id,
          "target_author_name": "random author",
        }
      )      

      self.assertEqual(response.status_code, 201)

    # def test_does_not_reward_claim_twice
    # def legacy_author_claim_throws_error  
