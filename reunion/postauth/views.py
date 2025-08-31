from rest_framework import generics
from .models import UserDetail
from .serializers import UserDetailSerializer

class CreateUserDetailView(generics.ListCreateAPIView):
    queryset = UserDetail.objects.all()
    serializer_class = UserDetailSerializer