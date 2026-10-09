from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Role, Team, TeamMembership, User


class BootstrapFormMixin:
    def style(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxSelectMultiple):
                widget.attrs["class"] = "role-checkboxes"
            elif isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "form-check-input"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs["class"] = "form-select"
            else:
                widget.attrs["class"] = "form-control"


class PreacherSignupForm(BootstrapFormMixin, UserCreationForm):
    class Meta:
        model = User
        fields = (
            "username", "first_name", "last_name", "mobile", "email",
            "expertise", "preaching_field", "password1", "password2",
        )
        labels = {
            "username": "نام کاربری", "first_name": "نام", "last_name": "نام خانوادگی",
            "mobile": "شماره همراه", "email": "ایمیل", "expertise": "تخصص",
            "preaching_field": "حوزه فعالیت تبلیغی",
        }
        widgets = {
            "expertise": forms.Textarea(attrs={"rows": 2, "placeholder": "تخصص‌ها و زمینه‌های علمی"}),
            "preaching_field": forms.Textarea(attrs={"rows": 2, "placeholder": "زمینه‌ها و مخاطبان فعالیت تبلیغی"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "رمز عبور"
        self.fields["password2"].label = "تکرار رمز عبور"
        self.fields["username"].widget.attrs.update({"autocomplete": "username", "placeholder": "نام کاربری انگلیسی"})
        self.fields["mobile"].widget.attrs.update({"inputmode": "tel", "placeholder": "09xxxxxxxxx"})
        self.fields["email"].widget.attrs.update({"dir": "ltr", "placeholder": "name@example.com"})
        self.fields["password1"].widget.attrs["autocomplete"] = "new-password"
        self.fields["password2"].widget.attrs["autocomplete"] = "new-password"
        self.style()


class AdminUserForm(BootstrapFormMixin, forms.ModelForm):
    password = forms.CharField(label="رمز عبور جدید", required=False, widget=forms.PasswordInput)
    roles = forms.ModelMultipleChoiceField(
        label="نقش‌ها", queryset=Role.objects.all(), required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = User
        fields = (
            "username", "first_name", "last_name", "email", "mobile",
            "expertise", "preaching_field", "roles", "is_enabled", "is_staff",
        )
        widgets = {
            "expertise": forms.Textarea(attrs={"rows": 2}),
            "preaching_field": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields["password"].required = True
            self.fields["password"].label = "رمز عبور"
        self.fields["email"].widget.attrs["dir"] = "ltr"
        self.style()

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)
        elif not user.pk:
            user.set_unusable_password()
        if commit:
            user.save()
            self.save_m2m()
        return user


class TeamManageForm(BootstrapFormMixin, forms.ModelForm):
    members = forms.ModelMultipleChoiceField(
        label="اعضای گروه",
        queryset=User.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-select select2", "data-placeholder": "اعضا را انتخاب کنید"}),
    )

    class Meta:
        model = Team
        fields = ("name", "description", "owner", "is_active")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        enabled_users = User.objects.filter(is_enabled=True).order_by("first_name", "last_name", "username")
        self.fields["owner"].queryset = enabled_users
        self.fields["members"].queryset = enabled_users
        if self.instance and self.instance.pk:
            self.fields["members"].initial = self.instance.memberships.filter(is_active=True).values_list("user_id", flat=True)
        self.style()
        self.fields["members"].widget.attrs["class"] = "form-select select2"

    def save(self, commit=True):
        team = super().save(commit=commit)
        if commit:
            selected = set(self.cleaned_data.get("members", User.objects.none()).values_list("pk", flat=True))
            selected.add(team.owner_id)
            TeamMembership.objects.filter(team=team).exclude(user_id__in=selected).update(is_active=False)
            for user_id in selected:
                membership, _ = TeamMembership.objects.get_or_create(
                    team=team,
                    user_id=user_id,
                    defaults={"role": "manager" if user_id == team.owner_id else "member", "is_active": True},
                )
                changed = False
                if not membership.is_active:
                    membership.is_active = True; changed = True
                desired_role = "manager" if user_id == team.owner_id else membership.role
                if membership.role != desired_role:
                    membership.role = desired_role; changed = True
                if changed:
                    membership.save(update_fields=["is_active", "role"])
        return team
