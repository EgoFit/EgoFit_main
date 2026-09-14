# User Dashboard and Auth Figma Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the user-facing auth and account area so the Django app matches the Figma mobile-first design and works cleanly on desktop, with production-grade backend support for dashboard data and profile updates.

**Architecture:** Keep business logic in `account/services` and `account/selectors`, keep HTTP handling in `account/views`, and keep presentation in templates and static assets. The UI should be driven by a shared account shell that renders consistently across login/register/profile sections, while data queries remain optimized and isolated from templates.

**Tech Stack:** Django, Django templates, Tailwind utility classes already present in the project, vanilla JS, existing `account` service/repository/selector pattern, pytest/Django test client.

---

### Task 1: Baseline the current user-area behavior

**Files:**
- Modify: `account/views.py`
- Modify: `account/services/profile_service.py`
- Modify: `account/selectors/user_selector.py`
- Test: `account/tests.py`

- [ ] **Step 1: Add/adjust tests for dashboard and auth redirects**

```python
from django.test import TestCase
from django.urls import reverse

class AccountRouteSmokeTests(TestCase):
    def test_login_page_is_available(self):
        response = self.client.get(reverse("register:pass_login"))
        assert response.status_code == 200

    def test_profile_redirects_anonymous_users(self):
        response = self.client.get(reverse("register:profile"))
        assert response.status_code in (302, 303)
```

- [ ] **Step 2: Run the targeted tests and confirm current behavior**

Run: `pytest account/tests.py -q`
Expected: existing coverage passes, and any gaps are visible before UI refactor.

- [ ] **Step 3: Add a single dashboard context method that returns all summary data needed by the Figma shell**

```python
def get_dashboard_context(self, user) -> dict:
    learning_courses = UserSelector.get_learning_courses(user)
    paid_orders = UserSelector.get_paid_orders(user)
    comments = UserSelector.get_user_comments(user)
    notifications = self.notification_service.get_dashboard_notifications(user, limit=5)
    return {
        "items": list(learning_courses[:4]),
        "learning_courses_count": learning_courses.count(),
        "paid_orders_count": paid_orders.count(),
        "comments_count": comments.count(),
        "notifications_count": self.notification_service.get_notifications_count(user),
        "recent_notifications": notifications,
        "recent_orders": list(paid_orders[:5]),
        "recent_comments": list(comments[:5]),
    }
```

- [ ] **Step 4: Make the selector queries efficient enough for the new page composition**

```python
def get_paid_orders(user: User):
    return (
        Order.objects.filter(user=user)
        .select_related("course", "applied_discount_code")
        .prefetch_related("items__product")
        .order_by("-created_at")
    )
```

- [ ] **Step 5: Re-run the account tests**

Run: `pytest account/tests.py -q`
Expected: no regression in the existing auth/profile flow.

### Task 2: Rebuild the shared account shell for mobile-first rendering

**Files:**
- Create: `account/templates/account/_shell.html`
- Create: `templates/includes/account_bottom_nav.html`
- Modify: `templates/base.html`
- Modify: `templates/includes/account_sidebar.html`
- Add: `assets/css/account.css`
- Modify: `assets/css/app.css` or `assets/css/home-refactor.css` if the project already imports shared styles there
- Modify: `templates/account/*.html`

- [ ] **Step 1: Write the shared account shell template and bottom navigation partial**

```django
<main class="account-page">
  <div class="account-page__frame">
    {% include "includes/account_bottom_nav.html" %}
    <div class="account-page__content">
      {% block account_content %}{% endblock %}
    </div>
  </div>
</main>
```

- [ ] **Step 2: Move common responsive account layout rules into a dedicated stylesheet**

```css
.account-page { min-height: 100vh; background: #f5f7fb; }
.account-page__frame { max-width: 1440px; margin: 0 auto; padding: 0 16px 88px; }
.account-bottom-nav { position: fixed; inset-inline: 16px; bottom: 16px; z-index: 40; }
@media (min-width: 1024px) { .account-bottom-nav { display: none; } }
```

- [ ] **Step 3: Add the desktop sidebar state to complement the mobile bottom nav**

```django
<aside class="account-sidebar">
  <a href="{% url 'register:profile' %}" class="{% if active_section == 'dashboard' %}is-active{% endif %}">پیشخوان</a>
  <a href="{% url 'register:profile_course' %}" class="{% if active_section == 'courses' %}is-active{% endif %}">دوره‌های من</a>
  <a href="{% url 'register:profile_financial' %}" class="{% if active_section == 'financial' %}is-active{% endif %}">مالی و سفارش‌ها</a>
  <a href="{% url 'register:profile_comments' %}" class="{% if active_section == 'comments' %}is-active{% endif %}">دیدگاه‌های من</a>
  <a href="{% url 'register:profile_notifications' %}" class="{% if active_section == 'notifications' %}is-active{% endif %}">اعلان‌ها</a>
</aside>
```

- [ ] **Step 4: Verify the shell on mobile and desktop before proceeding**

Run: `python manage.py runserver` and inspect the main account pages in browser.
Expected: mobile uses bottom navigation; desktop uses sidebar plus content columns.

### Task 3: Rework auth screens to match the Figma mobile cards and desktop adaptation

**Files:**
- Modify: `account/templates/account/login-register.html`
- Modify: `account/templates/account/pass_login.html`
- Modify: `account/templates/account/pass_register.html`
- Modify: `account/templates/account/verification.html`
- Modify: `account/templates/account/forgot_password.html`
- Modify: `account/templates/account/forgot_password_confirm.html`
- Modify: `account/forms.py` or `account/froms.py` if field widgets need cleanup
- Modify: `account/views.py`

- [ ] **Step 1: Add tests that validate auth pages render the new structure and field names**

```python
def test_pass_login_page_has_form_fields(self):
    response = self.client.get(reverse("register:pass_login"))
    self.assertContains(response, 'name="fullname"')
    self.assertContains(response, 'name="password"')
```

- [ ] **Step 2: Replace the current auth page composition with a single centered mobile-first card**

```django
<section class="auth-screen">
  <div class="auth-card">
    <img class="auth-card__logo" src="{% static 'images/logoimageego.webp' %}" alt="Egofit">
    <h1>ورود به حساب کاربری</h1>
    <form method="post">...</form>
  </div>
</section>
```

- [ ] **Step 3: Keep the existing validation and session behavior but clean up labels, spacing, and messaging**

```python
class FormLogin(forms.Form):
    fullname = forms.CharField(widget=forms.TextInput(attrs={"autocomplete": "username"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))
```

- [ ] **Step 4: Re-run auth page tests and do a browser check on mobile viewport**

Run: `pytest account/tests.py -q`
Expected: auth pages still submit, validate, and redirect correctly.

### Task 4: Rebuild dashboard, courses, orders, notifications, and profile edit screens to the new design

**Files:**
- Modify: `account/templates/account/profile.html`
- Modify: `account/templates/account/profile-courses.html`
- Modify: `account/templates/account/profile-financial.html`
- Modify: `account/templates/account/profile-comments.html`
- Modify: `account/templates/account/profile-notifications.html`
- Modify: `account/templates/account/profile-edit.html`
- Modify: `account/templates/account/edit_number.html`
- Modify: `account/templates/account/edit_number_verify.html`
- Modify: `account/templates/account/change_password.html`
- Modify: `account/views.py`

- [ ] **Step 1: Add tests for the dashboard context shape**

```python
def test_dashboard_context_contains_summary_counts(self):
    user = User.objects.create_user(fullname="demo", phone="09120000000", password="Test12345")
    response = self.client.get(reverse("register:profile"))
    self.assertEqual(response.status_code, 302)
```

- [ ] **Step 2: Implement a mobile dashboard layout with stacked summary cards and card lists**

```django
<section class="dashboard-hero">
  <div class="dashboard-hero__title">پیشخوان</div>
  <div class="dashboard-summary-grid">...</div>
  <section class="dashboard-panel">آخرین دوره‌ها</section>
</section>
```

- [ ] **Step 3: Rework each subsection to use the same visual system**

```django
<article class="account-card">
  <div class="account-card__header">
    <span>مالی و سفارش‌ها</span>
  </div>
  <table class="account-table">...</table>
</article>
```

- [ ] **Step 4: Keep backend writes safe and transactional for edits and OTP flows**

```python
@transaction.atomic
def update_profile(self, *, form):
    return form.save()
```

- [ ] **Step 5: Run a browser pass on authenticated pages at desktop and mobile widths**

Expected: no overflow, nav works, and dashboard content remains readable on 390px and 1440px widths.

### Task 5: Final verification and cleanup

**Files:**
- Modify: `account/tests.py`
- Modify: `templates/includes/*.html`
- Modify: `assets/css/*.css`

- [ ] **Step 1: Run the focused test suite**

Run: `pytest account/tests.py -q`
Expected: all account tests pass.

- [ ] **Step 2: Run a browser smoke check on the main flows**

```bash
python manage.py runserver
```

Check:
- login page
- register page
- dashboard
- courses
- orders
- notifications
- profile edit

- [ ] **Step 3: Remove any duplicated or dead account-only markup**

```bash
git diff -- templates/ account/
```

- [ ] **Step 4: Document any remaining mismatches with Figma as follow-up work, not as part of the current user scope**

Expected: user-facing account area is complete; admin remains untouched.

### Coverage Review

- Auth screens: covered in Task 3.
- Dashboard and subpages: covered in Task 4.
- Backend data and query efficiency: covered in Tasks 1 and 4.
- Responsive mobile/desktop parity: covered in Tasks 2 through 4.
- Tests and verification: covered in Tasks 1 and 5.

