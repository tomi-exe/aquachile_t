from django.urls import path
from . import views

urlpatterns = [
    path('', views.scenario_list, name='scenario_list'),
    path('new/', views.scenario_new, name='scenario_new'),
    path('<int:scenario_id>/', views.scenario_detail, name='scenario_detail'),
]
