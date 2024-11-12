# aegis/views/api/service_registry_views.py

from django.core.exceptions import ValidationError
from django.db import IntegrityError, DatabaseError
from django.http import JsonResponse
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from aegis.models import RegisteredService


class RegisterServiceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        service_name = request.data.get("service_name").strip()
        endpoint = request.data.get("endpoint").strip()
        methods = request.data.get("methods", ["GET", "POST"])
        params = request.data.get("params", {})

        if not service_name or not endpoint:
            return JsonResponse(
                {"error": "Service name and endpoint are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not isinstance(methods, list) or not all(isinstance(m, str) for m in methods):
            return JsonResponse(
                {"error": "Methods should be a list of strings."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:

            existing_endpoint = RegisteredService.objects.filter(
                endpoint=endpoint, status__in=[1, 0]
            ).first()

            if existing_endpoint:
                existing_methods = set(existing_endpoint.methods)
                requested_methods = set(methods)

                if requested_methods.issubset(existing_methods):
                    return JsonResponse(
                        {"error": "A service with this endpoint and methods already exists."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                else:
                    updated_methods = list(existing_methods.union(requested_methods))
                    existing_endpoint.methods = updated_methods
                    existing_endpoint.service_name = service_name
                    existing_endpoint.params = params
                    existing_endpoint.save()
                    return JsonResponse(
                        {"success": True, "message": "Service updated successfully with new methods.",
                         "service_id": existing_endpoint.id},
                        status=status.HTTP_200_OK
                    )

            service = RegisteredService.objects.create(
                service_name=service_name,
                endpoint=endpoint,
                methods=methods,
                params=params,
            )
            return JsonResponse(
                {"success": True, "message": "Service registered successfully", "service_id": service.id},
                status=status.HTTP_201_CREATED
            )

        except (IntegrityError, DatabaseError) as db_error:
            return JsonResponse(
                {"error": f"Database error: {str(db_error)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except ValidationError as val_error:
            return JsonResponse(
                {"error": f"Validation error: {str(val_error)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return JsonResponse(
                {"error": f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ServiceDirectoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            services = RegisteredService.active_objects.only("service_name", "endpoint", "methods", "params").values(
                "service_name", "endpoint", "methods", "params"
            )
            return JsonResponse(list(services), safe=False, status=status.HTTP_200_OK)

        except DatabaseError as db_error:
            return JsonResponse(
                {"error": f"Database error: {str(db_error)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return JsonResponse(
                {"error": f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DeleteServiceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        service_name = request.query_params.get("service_name")
        endpoint = request.query_params.get("endpoint")
        method = request.query_params.get("method")

        if not service_name or not endpoint:
            return JsonResponse(
                {"error": "Service name and endpoint are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            service = RegisteredService.objects.filter(service_name=service_name, endpoint=endpoint, status__in=[1, 0]).first()

            if not service:
                return JsonResponse(
                    {"error": "Service with this name and endpoint does not exist or is already deleted."},
                    status=status.HTTP_404_NOT_FOUND
                )

            if not method:
                service.status = 2
                service.deleted_at = timezone.now()
                service.save()
                return JsonResponse(
                    {"success": True, "message": "Service and endpoint deleted successfully."},
                    status=status.HTTP_200_OK
                )

            if method not in service.methods:
                return JsonResponse(
                    {"error": f"Method '{method}' does not exist for this endpoint."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            updated_methods = [m for m in service.methods if m != method]
            service.methods = updated_methods
            service.save()

            return JsonResponse(
                {"success": True, "message": f"Method '{method}' removed from the service."},
                status=status.HTTP_200_OK
            )

        except DatabaseError as db_error:
            return JsonResponse(
                {"error": f"Database error: {str(db_error)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return JsonResponse(
                {"error": f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
