from django.urls import path
from leads import views

urlpatterns = [
    path("", views.index, name="index"),
    path("leads/submit/", views.submit_lead, name="submit_lead"),
    path("sitemap.xml", views.sitemap_xml, name="sitemap"),
    path("robots.txt", views.robots_txt, name="robots"),
]
