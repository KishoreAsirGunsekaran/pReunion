from django.shortcuts import render, get_object_or_404
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from .models import FriendRequest, Friend
from .serializers import (
    FriendRequestSerializer,
    FriendSerializer,
    FriendListSerializer,
    UserBasicSerializer,
    UserDetailSearchSerializer
)
from django.contrib.auth import get_user_model
from django.db.models import Q
from postauth.models import UserDetail
import json
from rapidfuzz import fuzz

User = get_user_model()


class FriendRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for handling friend requests (Instagram-style follow requests)"""
    
    queryset = FriendRequest.objects.all()
    serializer_class = FriendRequestSerializer
    permission_classes = [IsAuthenticated]  
    
    def get_queryset(self):
        """
        Filter requests to only show those related to the current user.
        By default, only show pending requests.
        """
        user = self.request.user
        
        
        if self.action in ['sent', 'received', 'history']:
            return FriendRequest.objects.filter(
                Q(sender=user) | Q(receiver=user)
            ).select_related('sender', 'receiver')  
        
        
        return FriendRequest.objects.filter(
            (Q(sender=user) | Q(receiver=user)) & 
            Q(status='pending')
        ).select_related('sender', 'receiver')  
    
    def get_serializer_context(self):
        """Add request to serializer context"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def perform_create(self, serializer):
        """Override create to automatically set the sender to the current user"""
        serializer.save(sender=self.request.user)
    
    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """Accept a friend request"""
        friend_request = self.get_object()
        
        
        if friend_request.receiver != request.user:
            return Response(
                {"detail": "You can only accept requests sent to you."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        
        if friend_request.accept():
            return Response(
                {"detail": "Friend request accepted."},
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"detail": "This request cannot be accepted."},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a friend request"""
        friend_request = self.get_object()
        
        
        if friend_request.receiver != request.user:
            return Response(
                {"detail": "You can only reject requests sent to you."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        
        if friend_request.reject():
            return Response(
                {"detail": "Friend request rejected."},
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"detail": "This request cannot be rejected."},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a friend request (sender only)"""
        friend_request = self.get_object()
        
        
        if friend_request.sender != request.user:
            return Response(
                {"detail": "You can only cancel requests you sent."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        
        if friend_request.cancel():
            return Response(
                {"detail": "Friend request canceled."},
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"detail": "This request cannot be canceled."},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def sent(self, request):
        """Get all friend requests sent by the current user"""
        sent_requests = FriendRequest.objects.filter(sender=request.user)
        serializer = self.get_serializer(sent_requests, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def received(self, request):
        """Get all friend requests received by the current user"""
        received_requests = FriendRequest.objects.filter(receiver=request.user)
        serializer = self.get_serializer(received_requests, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def history(self, request):
        """Get all friend requests including accepted/rejected ones"""
        user = request.user
        all_requests = FriendRequest.objects.filter(
            Q(sender=user) | Q(receiver=user)
        )
        serializer = self.get_serializer(all_requests, many=True)
        return Response(serializer.data)


class FriendViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing friendships (Instagram-style mutual follows)"""
    
    serializer_class = FriendSerializer
    permission_classes = [IsAuthenticated]  
    
    def get_queryset(self):
        """Filter friendships to only show those related to the current user"""
        user = self.request.user
        return Friend.objects.filter(Q(user1=user) | Q(user2=user))
    
    @action(detail=False, methods=['get'])
    def my_friends(self, request):
        """Get all friends of the current user with pagination"""
        user = request.user
        
        
        page_size = request.query_params.get('page_size', 20)
        page = request.query_params.get('page', 1)
        
        try:
            page_size = int(page_size)
            page = int(page)
        except ValueError:
            page_size = 20
            page = 1
            
        
        page_size = min(page_size, 100)
        
        
        friends = Friend.objects.get_friend_list(user)
        
        
        total_count = friends.count()
        
        
        start = (page - 1) * page_size
        end = start + page_size
        
        
        paginated_friends = friends[start:end]
        
        
        serialized_friends = UserBasicSerializer(paginated_friends, many=True).data
        
        
        response_data = {
            'id': user.id,
            'username': user.username,
            'friends': serialized_friends,
            'pagination': {
                'total_friends': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': (total_count + page_size - 1) // page_size
            }
        }
        
        return Response(response_data)
    
    @action(detail=False, methods=['delete'])
    def unfriend(self, request):
        """Remove a friendship with another user"""
        friend_id = request.query_params.get('user_id')
        if not friend_id:
            return Response(
                {"detail": "user_id parameter is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            friend = User.objects.get(pk=friend_id)
            friendship = Friend.objects.filter(
                (Q(user1=request.user, user2=friend) | 
                 Q(user1=friend, user2=request.user))
            ).first()
            
            if not friendship:
                return Response(
                    {"detail": "You are not friends with this user."},
                    status=status.HTTP_404_NOT_FOUND
                )
                
            friendship.delete()
            return Response(
                {"detail": "Friend removed successfully."},
                status=status.HTTP_200_OK
            )
            
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND
            )


class MemorySearchView(APIView):
    """API endpoint for searching people from memory based on various criteria"""
    
    
    
    def get(self, request):
        """
        Search for people using partial name, school, branch, batch years, and optional fuzzy matching
        """
        
        name = request.query_params.get('name')
        edu_type = request.query_params.get('edu_type')
        education = request.query_params.get('education')
        department = request.query_params.get('department')
        batch_start = request.query_params.get('batch_start')
        batch_end = request.query_params.get('batch_end')
        fuzzy = request.query_params.get('fuzzy', 'false').lower() == 'true'

        
        if not name:
            return Response(
                {"detail": "name parameter is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        
        queryset = UserDetail.objects.all()
        
        
        try:
            if batch_start:
                batch_start = int(batch_start)
            if batch_end:
                batch_end = int(batch_end)
        except ValueError:
            return Response(
                {"detail": "batch_start and batch_end must be integers."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        
        
        if not fuzzy:
            
            queryset = queryset.filter(
                Q(firstname__icontains=name) | 
                Q(lastname__icontains=name) |
                Q(penname__icontains=name)
            )
        
        
        
        results = list(queryset)
        
        
        if fuzzy:
            fuzzy_results = []
            threshold = 70  
            
            for user in results:
                
                first_ratio = fuzz.partial_ratio(name.lower(), user.firstname.lower())
                last_ratio = fuzz.partial_ratio(name.lower(), user.lastname.lower())
                pen_ratio = fuzz.partial_ratio(name.lower(), user.penname.lower())
                
                
                if first_ratio >= threshold or last_ratio >= threshold or pen_ratio >= threshold:
                    fuzzy_results.append(user)
            
            results = fuzzy_results
        
        
        if edu_type and education:
            filtered_results = []
            for user in results:
                edu_details = user.edu_details
                match = None
                if edu_type in edu_details:
                    edu_info = edu_details[edu_type]
                    if edu_type == 'school' and isinstance(edu_info, dict):
                        for school_name, year in edu_info.items():
                            if education.lower() in school_name.lower():
                                match = {"edu_type": edu_type, "education": school_name, "year": year}
                                break
                    elif edu_type in ['undergraduate', 'postgraduate'] and isinstance(edu_info, dict):
                        uni = edu_info.get('university', '')
                        dept = edu_info.get('department', '')
                        year = edu_info.get('year', '')
                        # Check for education and department match
                        education_match = education.lower() in uni.lower() or education.lower() in dept.lower()
                        department_match = True
                        if department:
                            department_match = department.lower() in dept.lower()
                        if education_match and department_match:
                            # Parse year range
                            start, end = None, None
                            if year:
                                parts = year.split('-')
                                if len(parts) == 2:
                                    start = parts[0].strip()
                                    end = parts[1].strip()
                            # Only include if batch_start and batch_end are within the user's year range
                            include = True
                            if batch_start and start:
                                include = include and (str(batch_start) == start)
                            if batch_end and end:
                                include = include and (str(batch_end) == end)
                            if include:
                                match = {
                                    "edu_type": edu_type,
                                    "education": uni if education.lower() in uni.lower() else dept,
                                    "department": dept,
                                    "year": year,
                                    "start_year": start,
                                    "end_year": end
                                }
                    elif isinstance(edu_info, str):
                        if education.lower() in edu_info.lower():
                            match = {"edu_type": edu_type, "education": edu_info, "year": None}
                if match:
                    filtered_results.append({
                        "username": user.username,
                        "firstname": user.firstname,
                        "lastname": user.lastname,
                        "penname": user.penname,
                        "edu": match
                    })
            return Response(filtered_results)
        else:
            
            basic_results = []
            for user in results:
                basic_results.append({
                    "username": user.username,
                    "firstname": user.firstname,
                    "lastname": user.lastname,
                    "penname": user.penname
                })
            return Response(basic_results)
