"""
Tests for the user API.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status


CREATE_USER_URL = reverse('user:create')
TOKEN_URL = reverse('user:token')


def create_user(**params):
    """Create and return a new user."""
    return get_user_model().objects.create_user(**params)
    

class PublicUserApiTests(TestCase):
    """Test the public feature of the user API."""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Wait for db connection
        from django.db import connections
        connections['default'].ensure_connection()
    
    def test_create_user_success(self):
        """Test creating a user is successful."""
        payload = {
            'email': 'test@example.com',
            'password': 'testpass123',
            'name': 'Test Name',
        }
        res = self.client.post(CREATE_USER_URL, payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        user = get_user_model().objects.get(email=payload['email'])
        self.assertTrue(user.check_password(payload['password']))
        self.assertNotIn('password', res.data)

    def test_create_token_for_user(self):
        """Test complete auth flow"""
        # Clear any existing data
        get_user_model().objects.all().delete()
        
        # Create user through API
        user_data = {
            'email': 'test@example.com',
            'password': 'testpass123',
            'name': 'Test Name'
        }
        create_res = self.client.post(CREATE_USER_URL, user_data)
        self.assertEqual(create_res.status_code, 201)
        
        # Verify direct database access
        user = get_user_model().objects.get(email=user_data['email'])
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password(user_data['password']))
        
        # Get token
        token_res = self.client.post(TOKEN_URL, {
            'email': user_data['email'],
            'password': user_data['password']
        })
        
        self.assertEqual(token_res.status_code, 200)
        self.assertIn('token', token_res.data)

        
    def test_create_token_bad_credentials(self):
        """Test returns error if credentials invalid."""
        user=create_user(email='test@example.com', password='goodpass')
        payload = {'email': 'test@example.com', 'password': 'baddpass'}
        res = self.client.post(TOKEN_URL, payload)  
        
        self.assertNotIn('token', res.data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        
    def test_create_token_email_not_found(self):
        """Test error returned if user not found for given email."""
        payload = {'email': 'test@example.com', 'password': 'pass123'}

        res = self.client.post(TOKEN_URL, payload)
        
        self.assertNotIn('token', res.data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

 
        
    def test_create_token_blank_password(self):
        """Test posting a blank password returns an error."""
        payload = {'email': 'test@example.com', 'password': ''}
        res = self.client.post(TOKEN_URL, payload)  
        
        self.assertNotIn('token', res.data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)