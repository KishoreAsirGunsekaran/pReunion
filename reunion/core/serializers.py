from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import FriendRequest, Friend
from postauth.models import UserDetail

User = get_user_model()

class UserBasicSerializer(serializers.ModelSerializer):
    """Simple serializer for user details needed in friend operations"""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']


class FriendRequestSerializer(serializers.ModelSerializer):
    """Serializer for friend requests with user details"""
    
    sender = UserBasicSerializer(read_only=True)
    receiver = UserBasicSerializer(read_only=True)
    sender_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='sender',
        write_only=True,
        required=False,  
        default=None     
    )
    receiver_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='receiver',
        write_only=True
    )

    class Meta:
        model = FriendRequest
        fields = [
            'id', 'sender', 'receiver', 'sender_id', 'receiver_id',
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Validate that users can't send requests to themselves"""
        
        if 'sender' not in data:
            request = self.context.get('request')
            if request and hasattr(request, 'user'):
                data['sender'] = request.user
        
        sender = data.get('sender')
        receiver = data.get('receiver')
        
        if sender == receiver:
            raise serializers.ValidationError("You cannot send a friend request to yourself.")
            
        
        existing_request = FriendRequest.objects.filter(
            sender=sender, 
            receiver=receiver
        ).exists()
        
        if existing_request:
            raise serializers.ValidationError("A friend request already exists between these users.")
            
        
        if Friend.objects.are_friends(sender, receiver):
            raise serializers.ValidationError("These users are already friends.")
            
        return data


class FriendSerializer(serializers.ModelSerializer):
    """Serializer for friendships with user details"""
    
    user1 = UserBasicSerializer(read_only=True)
    user2 = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = Friend
        fields = ['id', 'user1', 'user2', 'created_at']
        read_only_fields = ['id', 'created_at']


class FriendListSerializer(serializers.ModelSerializer):
    """Serializer to display a user's friends"""
    
    friends = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'friends']
        
    def get_friends(self, obj):
        friends = Friend.objects.get_friend_list(obj)
        return UserBasicSerializer(friends, many=True).data


class UserDetailSearchSerializer(serializers.ModelSerializer):
    """Serializer for user details in memory search results"""
    
    class Meta:
        model = UserDetail
        fields = ['username', 'firstname', 'lastname', 'penname', 'phone', 'edu_details']