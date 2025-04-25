# aegis/views/api/service_registry_views.py

import json
import logging
import re
import requests

from django.core.exceptions import ValidationError
from django.db import IntegrityError, DatabaseError
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from aegis.models import RegisteredService
from aegis.utils.service_utils import match_endpoint


class RegisterServiceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Validate required fields
        required_fields = ["base_url", "service_name", "endpoint"]
        missing_fields = [field for field in required_fields if not request.data.get(field)]

        if missing_fields:
            return JsonResponse(
                {"error": f"Missing required fields: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        base_url = request.data.get("base_url").strip()
        service_name = request.data.get("service_name").strip()
        endpoint = request.data.get("endpoint").strip()
        methods = request.data.get("methods", ["GET", "POST"])
        params = request.data.get("params", "")

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

        if not isinstance(params, str):
            return JsonResponse(
                {"error": "Params should be a string representing query parameters."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate base_url
        if len(base_url) > 100:
            return JsonResponse(
                {"error": "Base URL must not exceed 100 characters."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not re.match(r"^(http|https)://[a-zA-Z0-9]([a-zA-Z0-9._]*[a-zA-Z0-9])?:[0-9]{1,5}/$", base_url):
            return JsonResponse(
                {
                    "error": "Base URL must follow the format 'http://baseurl:port/' or 'https://baseurl:port/'. "
                             "The base URL name must only contain alphanumeric characters, dots (.), or underscores (_), "
                             "and must start and end with an alphanumeric character. The port number must be 1-5 digits."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate service_name
        if not re.match(r"^[a-zA-Z0-9]([a-zA-Z0-9_]*[a-zA-Z0-9])?$", service_name) or len(service_name) >= 30:
            return JsonResponse(
                {"error": "Service name must only contain alphanumeric characters and underscores. "
                          "It cannot start or end with an underscore, and must be less than 30 characters long."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate endpoint
        if endpoint.startswith("/") or endpoint.startswith("\\"):
            return JsonResponse(
                {"error": "Endpoint must not start with a forward or backward slash."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(endpoint) > 100:
            return JsonResponse(
                {"error": "Endpoint must not exceed 100 characters."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Ensure consistent formatting (always include trailing slash for endpoint)
        endpoint = endpoint.rstrip('/') + '/'  # Ensure trailing slash for endpoint

        # Construct service_url
        if params:
            params = params.strip()  # Remove unnecessary leading/trailing spaces
            key_value_pairs = [pair.strip() for pair in params.split('&') if '=' in pair]  # Split and validate
            query_string = f"?{'&'.join(key_value_pairs)}" if key_value_pairs else ""
        else:
            query_string = ""

        # Final service_url
        service_url = f"http://127.0.0.1:8001/api/proxy/{service_name}/{endpoint}{query_string}"

        try:
            # Check for existing services with the same base_url and endpoint
            existing_services = RegisteredService.objects.filter(
                base_url=base_url,
                status__in=[1, 0]  # Active or inactive services
            )

            for existing_service in existing_services:
                if match_endpoint(endpoint, existing_service.endpoint):
                    # Update the existing service with new data
                    existing_service.base_url = base_url
                    existing_service.service_name = service_name
                    existing_service.endpoint = endpoint
                    existing_service.methods = list(set(existing_service.methods).union(methods))  # Merge methods
                    existing_service.params = params  # Update params
                    existing_service.comments = request.data.get("comments", existing_service.comments)  # Update comments
                    existing_service.service_url = service_url  # Update the service URL
                    existing_service.save()

                    return JsonResponse(
                        {"success": True, "message": "Service updated successfully.",
                         "service_id": existing_service.id},
                        status=status.HTTP_200_OK
                    )

            # If no existing endpoint combination, create a new entry
            service = RegisteredService.objects.create(
                base_url=base_url,
                service_name=service_name,
                endpoint=endpoint,
                methods=methods,
                params=params,
                comments=request.data.get("comments", None),
                service_url=service_url
            )
            return JsonResponse(
                {"success": True, "message": "Service registered successfully", "service_id": service.id},
                status=status.HTTP_201_CREATED
            )

        except (IntegrityError, DatabaseError) as db_error:
            logging.error(f"Database error: {str(db_error)}")
            return JsonResponse(
                # {"error": f"Database error: {str(db_error)}"},
                {"error": "A database error has occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except ValidationError as val_error:
            logging.error(f"Validation error: {str(val_error)}")
            return JsonResponse(
                # {"error": f"Validation error: {str(val_error)}"},
                {"error": "A validation error has occurred."},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return JsonResponse(
                # {"error": f"Unexpected error: {str(e)}"},
                {"error": "An unexpected error has occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ServiceDirectoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Get query parameters for filtering
            service_name = request.query_params.get("service_name", "").strip() or None
            endpoint = request.query_params.get("endpoint", "").strip() or None
            method = request.query_params.get("method", "").strip() or None

            filters = {}
            if service_name:
                filters["service_name__icontains"] = service_name
            if endpoint:
                filters["endpoint__icontains"] = endpoint
            if method:
                filters["methods__icontains"] = method

            # Query the database with filters (active services only)
            services_query = RegisteredService.active_objects.filter(**filters)

            # Only fetch specific fields to optimise the query
            services = services_query.only(
                "base_url", "service_name", "endpoint", "methods", "params", "comments"
            ).values("base_url", "service_name", "endpoint", "methods", "params", "comments")

            return JsonResponse(list(services), safe=False, status=status.HTTP_200_OK)

        except DatabaseError as db_error:
            logging.error(f"Database error: {str(db_error)}")
            return JsonResponse(
                # {"error": f"Database error: {str(db_error)}"},
                {"error": "A database error has occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return JsonResponse(
                # {"error": f"Unexpected error: {str(e)}"},
                {"error": "An unexpected error has occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DeleteServiceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        base_url = request.query_params.get("base_url")
        service_name = request.query_params.get("service_name")
        endpoint = request.query_params.get("endpoint")
        method = request.query_params.get("method")

        if not service_name or not endpoint or not base_url:
            return JsonResponse(
                {"error": "Base URL, service name, and endpoint are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            service = RegisteredService.objects.filter(
                base_url=base_url, service_name=service_name, endpoint=endpoint, status__in=[1, 0]
            ).first()

            if not service:
                return JsonResponse(
                    {"error": "Service with this base URL, name, and endpoint does not exist or is already deleted."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # If no method is provided, mark the service as deleted
            if not method:
                service.status = 2
                service.deleted_at = timezone.now()
                service.save()
                return JsonResponse(
                    {"success": True, "message": "Base URL, service and endpoint deleted successfully."},
                    status=status.HTTP_200_OK
                )

            # Check if the provided method exists for the service
            if method not in service.methods:
                return JsonResponse(
                    {"error": f"Method '{method}' does not exist for this endpoint."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Remove the method from the service
            updated_methods = [m for m in service.methods if m != method]
            service.methods = updated_methods
            service.save()

            return JsonResponse(
                {"success": True, "message": f"Method '{method}' removed from the service."},
                status=status.HTTP_200_OK
            )

        except DatabaseError as db_error:
            logging.error(f"Database error: {str(db_error)}")
            return JsonResponse(
                # {"error": f"Database error: {str(db_error)}"},
                {"error": "A database error has occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return JsonResponse(
                # {"error": f"Unexpected error: {str(e)}"},
                {"error": "An unexpected error has occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class NewReverseProxyAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def dispatch(self, request, *args, **kwargs):
        # Check if the path ends with a slash; if not, redirect to the normalized path
        path = kwargs.get('path', '')
        if not path.endswith('/'):
            # Normalize the URL by adding a trailing slash
            new_path = f"{path}/"
            # Redirect to the new path
            return HttpResponseRedirect(reverse('new_reverse_proxy', kwargs={'path': new_path}))

        return super().dispatch(request, *args, **kwargs)

    def dispatch_request(self, request, path):
        try:
            print(f"Incoming path: {path}")

            # Parse the path to determine service and endpoint
            path_parts = path.split('/')
            service_name = path_parts[0] if len(path_parts) > 0 else None
            endpoint = '/'.join(path_parts[1:]) if len(path_parts) > 1 else None

            if service_name:
                print(f"Service Name: {service_name}")
                print(f"Endpoint After Removing Service Name: {endpoint}")

            if not service_name or not endpoint:
                return JsonResponse({'error': 'Invalid path format.'}, status=400)

            # Query the database for matching service and endpoint pattern
            services = RegisteredService.objects.filter(service_name=service_name, status=1)

            service_entry = None
            # Filter by service name
            for service in services.filter():
                # Ensure service.endpoint is valid
                if not service.endpoint:
                    continue

                # Check if the stored endpoint has placeholders
                if '{' in service.endpoint and '}' in service.endpoint:
                    # Convert placeholders to a regex pattern
                    pattern = re.sub(r"\{[^\}]+\}", r"[^/]+", service.endpoint)

                    # Match the incoming endpoint to the regex pattern
                    if re.fullmatch(pattern, endpoint):
                        service_entry = service
                        break
                else:
                    # Direct match for endpoints without placeholders
                    if service.endpoint.strip('/') == endpoint.strip('/'):
                        service_entry = service
                        break

                # Ensure endpoint is a valid string before matching
                if endpoint is None or not isinstance(endpoint, str):
                    print(f"Invalid endpoint in request: {endpoint}")
                    continue

            if not service_entry:
                return JsonResponse({'error': 'No service can provide this resource.'}, status=404)

            # Replace placeholders in the stored endpoint with actual values from the request
            resolved_endpoint = service_entry.endpoint
            for part, placeholder in zip(endpoint.split('/'), resolved_endpoint.split('/')):
                if placeholder.startswith("{") and placeholder.endswith("}"):
                    resolved_endpoint = resolved_endpoint.replace(placeholder, part)

            # Check if the method is supported
            if request.method not in service_entry.methods:
                return JsonResponse(
                    {'error': f"Method {request.method} not allowed for this endpoint."},
                    status=405
                )

            # Resolve placeholders if present
            resolved_endpoint = service_entry.endpoint
            if '{' in resolved_endpoint and '}' in resolved_endpoint:
                resolved_endpoint_parts = resolved_endpoint.split('/')
                incoming_parts = endpoint.split('/')

                # Replace placeholders with actual values from the request path
                resolved_endpoint = '/'.join(
                    incoming if placeholder.startswith("{") and placeholder.endswith("}") else placeholder
                    for placeholder, incoming in zip(resolved_endpoint_parts, incoming_parts)
                )

            # Construct the target service URL
            print("service_entry.base_url: ", service_entry.base_url)
            url = f"{service_entry.base_url}{resolved_endpoint.lstrip('/')}"
            query_string = request.META.get('QUERY_STRING', '')

            if query_string:
                url = f"{url}?{query_string}"

            print(f"Forwarding request to: {url}")

            headers = {key: value for key, value in request.headers.items() if key.lower() != 'host'}

            data = None
            json_data = None

            try:
                json_data = request.data
            except Exception as e:
                # Fallback to raw body if something goes wrong (e.g., invalid JSON)
                try:
                    data = request.body
                except Exception as e2:
                    return JsonResponse({
                        'error': f'Failed to parse request body.',
                        'detail': str(e2),
                        'original_error': str(e)
                    }, status=status.HTTP_400_BAD_REQUEST)

            # Forward the request based on the HTTP method
            if request.method == 'GET':
                response = requests.get(url, headers=headers, params=request.GET)
            elif request.method == 'POST':
                response = requests.post(
                    url, headers=headers,
                    json=json_data if json_data is not None else None,
                    data=None if json_data is not None else data
                )
            elif request.method == 'PUT':
                response = requests.put(
                    url, headers=headers,
                    json=json_data if json_data is not None else None,
                    data=None if json_data is not None else data
                )
            elif request.method == 'DELETE':
                response = requests.delete(
                    url, headers=headers,
                    json=json_data if json_data is not None else None,
                    data=None if json_data is not None else data
                )
            elif request.method == 'PATCH':
                response = requests.patch(
                    url, headers=headers,
                    json=json_data if json_data is not None else None,
                    data=None if json_data is not None else data
                )
            else:
                return JsonResponse({'error': 'Unsupported HTTP method.'}, status=405)

            # Return the response from the proxied service
            return HttpResponse(
                response.content,
                status=response.status_code,
                content_type=response.headers.get('Content-Type', 'application/json')
            )

        except Exception as e:
            return JsonResponse({'error': f"Internal server error: {str(e)}"}, status=500)

    def get(self, request, path):
        return self.dispatch_request(request, path)

    def post(self, request, path):
        return self.dispatch_request(request, path)

    def put(self, request, path):
        return self.dispatch_request(request, path)

    def delete(self, request, path):
        return self.dispatch_request(request, path)

    def patch(self, request, path):
        return self.dispatch_request(request, path)

