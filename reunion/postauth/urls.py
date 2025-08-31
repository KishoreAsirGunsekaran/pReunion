from django.urls import path
from .views import CreateUserDetailView

urlpatterns = [
    path('userdetail/',CreateUserDetailView.as_view(),name='postUserDetail')
]
