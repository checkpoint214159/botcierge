from django.contrib.auth import login
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import AddressForm, ProfileForm, RegisterForm
from .models import Address, CustomerProfile


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


@login_required
def profile(request):
    """S01b: customer edits phone, address and housing type."""
    obj, _ = CustomerProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=obj)
    return render(request, "accounts/profile.html", {"form": form})


def _safe_next(request):
    """Where to go after saving an address, e.g. back to the booking page. Only our own URLs."""
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return None


@login_required
def addresses(request):
    """S19: list saved addresses and add a new one."""
    if request.method == "POST":
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.customer = request.user  # owner comes from the session, never the form
            address.save()
            messages.success(request, f"Saved {address.label}.")
            return redirect(_safe_next(request) or "accounts:addresses")
    else:
        # first address: prefill from what the customer gave us at sign-up / on the old profile form
        profile = getattr(request.user, "profile", None)
        initial = {}
        if profile and not request.user.addresses.exists():
            initial = {"label": "Home", "line": profile.address, "postal_code": profile.postal_code}
        form = AddressForm(initial=initial)
    return render(request, "accounts/addresses.html", {
        "addresses": request.user.addresses.all(), "form": form, "next": _safe_next(request) or ""})


@login_required
def address_edit(request, pk):
    address = get_object_or_404(Address, pk=pk, customer=request.user)
    form = AddressForm(request.POST or None, instance=address)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Updated {address.label}.")
        return redirect(_safe_next(request) or "accounts:addresses")
    return render(request, "accounts/address_edit.html", {"form": form, "address": address,
                                                          "next": _safe_next(request) or ""})


@login_required
@require_POST
def address_delete(request, pk):
    address = get_object_or_404(Address, pk=pk, customer=request.user)
    was_default = address.is_default
    address.delete()  # plans using it lose their address (SET_NULL); orders keep their copied text
    if was_default:
        nxt = request.user.addresses.first()
        if nxt:
            nxt.is_default = True
            nxt.save()
    messages.info(request, f"Deleted {address.label}.")
    return redirect("accounts:addresses")


@login_required
@require_POST
def address_default(request, pk):
    address = get_object_or_404(Address, pk=pk, customer=request.user)
    address.is_default = True
    address.save()  # Address.save() clears the old default
    return redirect("accounts:addresses")
