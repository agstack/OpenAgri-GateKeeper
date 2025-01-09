from aegis.models import RequestLog


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def process_request(self, request):
        # This method should log the body before any other processing consumes it
        body = request.body.decode('utf-8') if request.body else ''
        request.logged_body = body  # Store it on request if needed later

    def __call__(self, request):
        # Access the stored body
        body = getattr(request, 'logged_body', '')

        # Ensure user_agent is never None
        user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')

        # Log request data
        response = self.get_response(request)

        RequestLog.objects.create(
            user=getattr(request, 'user', None) if getattr(request, 'user',
                                                           None) and request.user.is_authenticated else None,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=user_agent,
            path=request.path,
            query_string=request.META.get('QUERY_STRING'),
            body=body,
            method=request.method,
            response_status=response.status_code
        )
        return response
