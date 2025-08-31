from django.db import models

class UserDetail(models.Model):
    VISIBILITY_CHOICES = [
        ('public', 'Public'),
        ('private', 'Private'),
    ]
    username = models.CharField(primary_key=True,max_length=100,unique=True)
    firstname = models.CharField(max_length=100)
    lastname = models.CharField(max_length=100)
    penname = models.CharField(max_length=100)
    instagram = models.CharField(max_length=100)
    snapchat = models.CharField(max_length=100)
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default='public')
    phone = models.CharField(max_length=100)
    edu_details = models.JSONField()