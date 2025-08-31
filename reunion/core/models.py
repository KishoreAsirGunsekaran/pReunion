from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q

User = get_user_model()

class FriendRequest(models.Model):
    """
    Represents a friend request (similar to Instagram's follow request).
    A user sends a request to another user, who must accept before they become friends.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]

    sender = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='sent_requests',
        help_text="User who sent the friend request"
    )
    receiver = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='received_requests',
        help_text="User who received the friend request"
    )
    status = models.CharField(
        max_length=10, 
        choices=STATUS_CHOICES, 
        default='pending',
        help_text="Current status of the friend request",
        db_index=True  
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)  
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('sender', 'receiver')
        ordering = ['-created_at']
        verbose_name = "Friend Request"
        verbose_name_plural = "Friend Requests"
        constraints = [
            
            models.CheckConstraint(
                check=~Q(sender=models.F('receiver')),
                name='cannot_send_request_to_self'
            ),
        ]
        
        indexes = [
            models.Index(fields=['sender', 'status'], name='fr_sender_status_idx'),
            models.Index(fields=['receiver', 'status'], name='fr_receiver_status_idx'),
        ]

    def __str__(self):
        return f"{self.sender.username} → {self.receiver.username} ({self.get_status_display()})"

    def accept(self):
        """Accept the friend request and create a friendship."""
        from django.db import transaction
        
        if self.status == 'pending':
            
            with transaction.atomic():
                
                if not Friend.objects.filter(
                    (Q(user1=self.sender, user2=self.receiver) | 
                    Q(user1=self.receiver, user2=self.sender))
                ).exists():
                    
                    Friend.objects.create(
                        user1=self.sender,
                        user2=self.receiver
                    )
                
                
                self.status = 'accepted'
                self.save(update_fields=['status', 'updated_at'])
            return True
        return False

    def reject(self):
        """Reject the friend request."""
        if self.status == 'pending':
            self.status = 'rejected'
            self.save(update_fields=['status', 'updated_at'])
            return True
        return False
    
    def cancel(self):
        """Cancel a pending request (can only be done by sender)."""
        if self.status == 'pending':
            self.delete()
            return True
        return False


class FriendManager(models.Manager):
    def are_friends(self, user1, user2):
        """Check if two users are friends."""
        return self.filter(
            (Q(user1=user1, user2=user2) | 
             Q(user1=user2, user2=user1))
        ).exists()
    
    def get_friend_list(self, user):
        """Get all friends of a user with optimized query."""
        user_friends = (
            self.filter(Q(user1=user) | Q(user2=user))
            .select_related('user1', 'user2')
        )
        friend_ids = []
        
        for friendship in user_friends:
            if friendship.user1 == user:
                friend_ids.append(friendship.user2.id)
            else:
                friend_ids.append(friendship.user1.id)
        
        return User.objects.filter(id__in=friend_ids)


class Friend(models.Model):
    """
    Represents a friendship between two users.
    In Instagram terms, this is like two users following each other.
    """
    user1 = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='friendships1',
        db_index=True  
    )
    user2 = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='friendships2',
        db_index=True  
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)  
    
    
    objects = FriendManager()
    
    class Meta:
        unique_together = ('user1', 'user2')
        ordering = ['-created_at']
        verbose_name = "Friendship"
        verbose_name_plural = "Friendships"
        constraints = [
            
            models.CheckConstraint(
                check=~Q(user1=models.F('user2')),
                name='cannot_be_friends_with_self'
            ),
        ]
        
        indexes = [
            models.Index(fields=['user1', 'user2'], name='friendship_users_idx'),
            models.Index(fields=['created_at'], name='friendship_date_idx'),
        ]
    
    def __str__(self):
        return f"{self.user1.username} and {self.user2.username} are friends"
    
    def save(self, *args, **kwargs):
        
        
        if self.user1.id > self.user2.id:
            self.user1, self.user2 = self.user2, self.user1
        super().save(*args, **kwargs)
