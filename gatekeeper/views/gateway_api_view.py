# import logging
# import re
# import requests
#
# from django.http import JsonResponse, HttpResponse
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.views import APIView
#
# from urllib.parse import urljoin
#
# from aegis.models import RegisteredService
# from aegis.utils.service_utils import match_endpoint, check_service_health
#
# logger = logging.getLogger(__name__)
#
#
# class GatewayAPIView(APIView):
#     permission_classes = [IsAuthenticated]
#
#     def get(self, request, path=None, *args, **kwargs):
#         return self.handle_request(request, path, "GET")
#
#     def post(self, request, path=None, *args, **kwargs):
#         return self.handle_request(request, path, "POST")
#
#     def handle_request(self, request, path, method):
#         logger.info(f"Handling {method} request for path: {path}")
#
#         # Step 1: Match registered service
#         for service in RegisteredService.objects.filter(status=1):  # Only check active services
#             if match_endpoint(path, f"{service.service_name}/{service.version}/{service.endpoint}"):
#                 registered_service = service
#                 break
#         else:
#             return JsonResponse({"error": "Service not available or endpoint not registered."}, status=404)
#
#         # Step 2: Validate service health
#         base_url = registered_service.base_url.rstrip("/")
#         logger.info(f"Base URL: {base_url}")
#
#         if not check_service_health(base_url):
#             logger.warning(f"Service health check failed for {base_url}")
#             return JsonResponse(
#                 {"error": f"Service {registered_service.service_name} is temporarily unavailable."},
#                 status=503
#             )
#
#         # Step 3: Construct backend URL
#         backend_url = registered_service.service_url
#         backend_url = self.construct_backend_url(
#             registered_service.endpoint, path, base_url, registered_service.service_name, registered_service.version
#         )
#         logger.info(f"Constructed backend URL: {backend_url}")
#         headers = {"Authorization": request.headers.get("Authorization")}
#         print("backend_url: ", backend_url)
#
#         try:
#             if method == "GET":
#                 response = requests.get(backend_url, headers=headers, params=request.GET, timeout=10)
#             elif method == "POST":
#                 response = requests.post(backend_url, headers=headers, json=request.data, timeout=10)
#             else:
#                 return JsonResponse({"error": f"Method {method} not supported."}, status=405)
#
#             return HttpResponse(
#                 response.content,
#                 status=response.status_code,
#                 content_type=response.headers.get("Content-Type", "application/json")
#             )
#         except requests.RequestException as e:
#             return JsonResponse({"error": f"Failed to connect to the backend service: {str(e)}"}, status=502)
#
#     def construct_backend_url(self, endpoint_template, path, base_url, service_name, version):
#         """
#         Construct the backend URL by replacing placeholders in the registered endpoint
#         with actual values from the incoming request path.
#         """
#         # Split both the incoming path and registered endpoint into segments
#         incoming_segments = path.strip("/").split("/")
#         registered_segments = f"{service_name}/{version}/{endpoint_template}".strip("/").split("/")
#
#         # Map placeholders to actual values
#         replacement_map = {}
#         for reg_seg, inc_seg in zip(registered_segments, incoming_segments):
#             if reg_seg.startswith("{") and reg_seg.endswith("}"):
#                 key = reg_seg.strip("{}")
#                 replacement_map[key] = inc_seg
#
#         # Replace placeholders in the endpoint with actual values
#         for placeholder, value in replacement_map.items():
#             endpoint_template = endpoint_template.replace(f"{{{placeholder}}}", value)
#
#         # Construct the full URL including service name and version
#         final_endpoint = f"{service_name}/{version}/{endpoint_template.lstrip('/')}"
#         return f"{base_url.rstrip('/')}/{final_endpoint.lstrip('/')}"
#
