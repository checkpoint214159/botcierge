from django.contrib.auth import login
from django.shortcuts import redirect, render

from .forms import RegisterForm


def register(request):
    """S01: customer sign-up. Creates a User plus a CustomerProfile."""
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("planner:start")
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {"form": form})

# TODO(S01b): profile page where the customer edits phone, address, housing type.
