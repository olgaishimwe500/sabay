from django.shortcuts import render


def home(request):
    """Render the default landing page."""
    return render(request, "home.html")
