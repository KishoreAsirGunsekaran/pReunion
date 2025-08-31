from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FriendRequestViewSet, FriendViewSet, MemorySearchView


router = DefaultRouter()
router.register(r'reunite', FriendRequestViewSet, basename='friend-request')  # Friend requests
router.register(r'reunited', FriendViewSet, basename='friendship')  # Friends list

urlpatterns = [
    path('', include(router.urls)),
    path('memory-search/', MemorySearchView.as_view(), name='memory-search'),
]