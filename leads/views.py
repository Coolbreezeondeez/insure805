import json
import re
from pathlib import Path

from django.conf import settings
from django.core.mail import send_mail
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

SITE_HTML_PATH = Path(settings.BASE_DIR) / "site" / "index.html"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ZIP_RE = re.compile(r"^\d{5}$")


@ensure_csrf_cookie
def index(request):
    """Serve the landing page as a plain file (not a Django template) so
    the CSS/JS inside it is never touched by the template engine. The
    ensure_csrf_cookie decorator sets the csrftoken cookie on page load so
    the contact form's JS can read it and attach it to the POST below."""
    html = SITE_HTML_PATH.read_text(encoding="utf-8")
    return HttpResponse(html, content_type="text/html; charset=utf-8")


@require_POST
def submit_lead(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponseBadRequest("Invalid request body")

    first = (data.get("first") or "").strip()
    last = (data.get("last") or "").strip()
    phone = (data.get("phone") or "").strip()
    email = (data.get("email") or "").strip()
    zip_code = (data.get("zip") or "").strip()
    situation = (data.get("situation") or "").strip()

    errors = {}
    if not first:
        errors["first"] = "First name is required."
    if not last:
        errors["last"] = "Last name is required."
    if not phone:
        errors["phone"] = "Phone is required."
    if not email or not EMAIL_RE.match(email):
        errors["email"] = "A valid email is required."
    if not zip_code or not ZIP_RE.match(zip_code):
        errors["zip"] = "A valid 5-digit ZIP code is required."

    if errors:
        return JsonResponse({"ok": False, "errors": errors}, status=400)

    subject = f"New insure805.com lead: {first} {last}"
    body = (
        f"New quote request from insure805.com\n\n"
        f"Name: {first} {last}\n"
        f"Phone: {phone}\n"
        f"Email: {email}\n"
        f"ZIP: {zip_code}\n"
        f"Situation: {situation or '(not specified)'}\n"
    )

    if settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[settings.LEAD_NOTIFY_TO],
            fail_silently=False,
        )
    else:
        # Email isn't configured yet (missing env vars) — log instead of
        # silently dropping the lead, and still tell the visitor it worked
        # only if email actually sent. Fail loudly here so Ben notices in
        # the Render logs rather than losing real leads.
        return JsonResponse(
            {"ok": False, "errors": {"__all__": "Email is not configured on the server."}},
            status=500,
        )

    return JsonResponse({"ok": True})
