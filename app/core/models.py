"""
Database models.
"""

import uuid
import os

from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractBaseUser,BaseUserManager,PermissionsMixin


def recipe_image_file_path(instance,filename):
    """Generate file path for new recipe image."""
    ext = os.path.splitext(filename)[1]
    filename = f'{uuid.uuid4()}{ext}'
    
    #to generate file path for dynamic operating system
    return os.path.join('uploads','recipe',filename)


# models.py
class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        """Creates and saves a User with proper password hashing"""
        if not email:
            raise ValueError('Users must have an email address')
        
        user = self.model(
            email=self.normalize_email(email),
            **extra_fields
        )
        user.set_password(password)  # This hashes the password
        user.save(using=self._db)
        return user
    
    def create_superuser(self,email,password=None):
        """Create and return a new superuser."""
        user = self.create_user(email,password)
        user.is_staff=True
        user.is_superuser=True
        user.save(using=self._db)
        
        return user

class User(AbstractBaseUser,PermissionsMixin):
    """User in the system."""
    email= models.EmailField(max_length=255,unique=True)
    name= models.CharField(max_length=255)
    is_active= models.BooleanField(default=True)
    is_staff=models.BooleanField(default=False)
    
    #assigning Usermanager to user
    objects=UserManager()
    
    USERNAME_FIELD= 'email'
    
class Recipe(models.Model):
    """Recipe object."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    title=models.CharField(max_length=255)
    #textfield can have multiple lines of text
    description=models.TextField(blank= True)
    time_minutes=models.IntegerField()
    price=models.DecimalField(max_digits=5,decimal_places=2,blank=True)
    link=models.CharField(max_length=255,blank=True)
    tags=models.ManyToManyField('Tag')
    ingredients=models.ManyToManyField('Ingredient')
    image=models.ImageField(null = True, upload_to=recipe_image_file_path)
    
    def __str__(self):
        return self.title
    
class Tag(models.Model):
    """Tag for flitering recipes."""
    name=models.CharField(max_length=255)
    user=models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    
    def __str__(self):
        return self.name
    
class Ingredient(models.Model):
    """Ingredient for recipes."""
    name=models.CharField(max_length=255)
    user=models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    
    def __str__(self):
        return self.name