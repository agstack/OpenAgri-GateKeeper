# from django.http import JsonResponse, HttpResponse
# from django.conf import settings
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.decorators import api_view, permission_classes
#
# import requests
#
# @api_view(['GET', 'POST', 'PUT', 'DELETE'])
# @permission_classes([IsAuthenticated])
# def reverse_proxy(request, path):
#
#     provider_api = None
#     for open_agri_entity, resource_provider_id in settings.REVERSE_PROXY_MAPPING.items():
#         if open_agri_entity in path:
#             provider_api = settings.AVAILABLE_SERVICES.get(resource_provider_id, {}).get('api')
#     if provider_api is None:
#         return JsonResponse({'error': 'No service can provide this resource.'}, status=405)
#
#     url = f"{provider_api}{path}"
#     method = request.method
#
#     # Forward the request headers and body
#     headers = {key: value for key, value in request.headers.items() if key != 'Host'}
#     data = request.body
#
#     # Forward the request based on the HTTP method
#     if method == 'POST':
#         response = requests.post(url, headers=headers, data=data)
#     elif method == 'GET':
#         response = requests.get(url, headers=headers, params=request.GET)
#     elif method == 'PUT':
#         response = requests.put(url, headers=headers, data=data)
#     elif method == 'DELETE':
#         response = requests.delete(url, headers=headers, data=data)
#     else:
#         return JsonResponse({'error': 'Method not supported'}, status=405)
#
#     # Create a Django response object with the same status code and content
#     return HttpResponse(
#         response.content,
#         status=response.status_code,
#         content_type=response.headers.get('Content-Type', 'application/json')
#     )
