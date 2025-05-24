from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('crime-map/', views.crime_map, name='crime_map'),
]
