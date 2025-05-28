from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('crime-map/', views.crime_map, name='crime_map'),
    path('map-input/', views.map_with_input, name='map_with_input'),
    path('route/', views.route_view, name='route_view'),

]
