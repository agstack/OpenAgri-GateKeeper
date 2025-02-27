from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin


class ForceAppendSlashMiddleware(MiddlewareMixin):
    def process_request(self, request):
        """
        Redirect requests without a trailing slash to the same URL with a trailing slash.
        Avoids modifying static/media files.
        """
        if request.path.startswith(('/static/', '/media/')):
            return None  # Don't modify static file requests

        if not request.path.endswith('/') and '.' not in request.path.split('/')[-1]:
            return redirect(request.path + '/', permanent=True)  # Redirect with trailing slash

        return None
