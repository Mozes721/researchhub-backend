from rest_framework.permissions import BasePermission

from researchhub.settings import LAMBDA_IPS
from utils.http import RequestMethods, get_client_ip


class UserIsAdminOfProject(BasePermission):
    message = "Permission Denied: requestor is not admin of the project"

    def has_permission(self, request, view):
        method = request.method
        if method == RequestMethods.DELETE or method == RequestMethods.POST:
            return True
        return False

    def has_object_permission(self, request, view, obj):
        requestor = request.user
        return obj.get_is_user_admin(requestor)


class PDFUploadsS3CallBack(BasePermission):
    message = "Permission Denied: Endpoint restricted to S3 Lambda trigger"

    def has_permission(self, request, view):
        client_ip = get_client_ip(request)
        if client_ip not in LAMBDA_IPS:
            return False
        return True
