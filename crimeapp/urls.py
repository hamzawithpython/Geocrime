from django.urls import path
from . import views

urlpatterns = [
    path('', views.google_route_view, name='route'),
    path("api/custom-route/", views.get_custom_route, name="custom_route"),
    path("about/", views.about, name="about"),
    path("disclaimer/", views.disclaimer, name="disclaimer"),
    path("help/", views.help, name="help"),
    path("contact/", views.contact, name="contact"),
    path("privacy/", views.privacy, name="privacy"),
    path("terms/", views.terms, name="terms"),
]
