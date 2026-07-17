import json
import re
import urllib.request
import urllib.error
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

SITE_HTML_PATH = Path(settings.BASE_DIR) / "site" / "index.html"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ZIP_RE = re.compile(r"^\d{5}$")


def send_via_resend(subject, body):
    """Send an email through Resend's HTTP API. Raises on failure so the
    caller can decide how to respond to the visitor."""
    payload = json.dumps({
        "from": settings.LEAD_FROM_EMAIL,
        "to": [settings.LEAD_NOTIFY_TO],
        "subject": subject,
        "text": body,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status


def sitemap_xml(request):
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://insure805.com/</loc>
    <changefreq>monthly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>"""
    return HttpResponse(xml, content_type="application/xml")


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "Sitemap: https://insure805.com/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


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

    if not settings.RESEND_API_KEY:
        # Email isn't configured yet (missing env var) — fail loudly here
        # so Ben notices in the Render logs rather than silently losing
        # real leads.
        return JsonResponse(
            {"ok": False, "errors": {"__all__": "Email is not configured on the server."}},
            status=500,
        )

    try:
        send_via_resend(subject, body)
    except (urllib.error.URLError, urllib.error.HTTPError):
        return JsonResponse(
            {"ok": False, "errors": {"__all__": "Email delivery failed."}},
            status=502,
        )

    return JsonResponse({"ok": True})
