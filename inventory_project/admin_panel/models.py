from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('ADMIN', 'Admin'),
        ('OWNER', 'Owner'),
        ('MANAGER', 'Manager'),
        ('STAFF', 'Staff'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    contact = models.CharField(max_length=15)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.user.email} - {self.role}"

