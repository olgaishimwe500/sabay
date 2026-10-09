from django.shortcuts import render


def index(request):
    return render(request, "chat/index.html")


def basic(request):
    return render(request, "chat/basic.html")


def room(request, room_name):
    return render(request, "chat/room.html", {"room_name": room_name})
