from django.contrib import messages
from django.contrib.auth import login
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .decorators import role_required
from .forms import AdminUserForm, PreacherSignupForm, TeamManageForm
from .models import Role, Team, User


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = PreacherSignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        role, _ = Role.objects.get_or_create(slug="preacher", defaults={"name": "مبلغ"})
        user.roles.add(role)
        login(request, user)
        messages.success(request, "ثبت‌نام انجام شد. نقش اولیه شما مبلغ است.")
        return redirect("dashboard")
    return render(request, "accounts/signup.html", {"form": form})


@role_required("admin")
def user_list(request):
    query = request.GET.get("q", "").strip()
    users = User.objects.prefetch_related("roles").order_by("-date_joined")
    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(mobile__icontains=query)
            | Q(email__icontains=query)
        )
    return render(request, "accounts/user_list.html", {"users": users, "q": query})


@role_required("admin")
def user_create(request):
    form = AdminUserForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "کاربر ایجاد شد.")
        return redirect("user_list")
    return render(request, "accounts/user_form.html", {"form": form, "title": "ایجاد کاربر"})


@role_required("admin")
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = AdminUserForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "اطلاعات کاربر ذخیره شد.")
        return redirect("user_list")
    return render(request, "accounts/user_form.html", {"form": form, "title": "ویرایش کاربر", "target": user})


@role_required("admin")
def team_list(request):
    teams = Team.objects.select_related("owner").prefetch_related("memberships__user").order_by("name")
    return render(request, "accounts/team_list.html", {"teams": teams})


@role_required("admin")
def team_create(request):
    form = TeamManageForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "گروه کاری ایجاد شد.")
        return redirect("team_list")
    return render(request, "accounts/team_form.html", {"form": form, "title": "ایجاد گروه کاری"})


@role_required("admin")
def team_edit(request, pk):
    team = get_object_or_404(Team, pk=pk)
    form = TeamManageForm(request.POST or None, instance=team)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "گروه کاری و اعضای آن ذخیره شد.")
        return redirect("team_list")
    return render(request, "accounts/team_form.html", {"form": form, "title": "ویرایش گروه کاری", "team": team})
