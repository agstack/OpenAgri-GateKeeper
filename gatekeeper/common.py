from django.shortcuts import redirect


def custom_page_not_found_view(request, exception):
    return redirect('login')
