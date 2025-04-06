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
    
    def setUp(self):
        self.client = APIClient()
    
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
        """Test generates token for valid credentials."""
        user_details = {
            'name': 'Test Name',
            'email': 'test@example.com',
            'password': 'test-user-password123',
        }
        user = create_user(**user_details)
        
        # Debug print
        print(f"User exists: {get_user_model().objects.filter(email=user_details['email']).exists()}")
        print(f"Password matches: {user.check_password(user_details['password'])}")
        
        payload = {
            'email': user_details['email'],
            'password': user_details['password'],
        }
        res = self.client.post(TOKEN_URL, payload)
    
        # Debug print
        print(f"Response data: {res.data}")
        
        self.assertIn('token', res.data)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
    def test_create_token_bad_credentials(self):
        """Test returns error if credentials invalid."""
        create_user(email='test@example.com', password='goodpass')
        
        payload = {'email': 'test@example.com', 'password': 'baddpass'}
        res = self.client.post(TOKEN_URL, payload)  
        
        self.assertNotIn('token', res.data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        
    def test_create_token_blank_password(self):
        """Test posting a blank password returns an error."""
        payload = {'email': 'test@example.com', 'password': ''}
        res = self.client.post(TOKEN_URL, payload)  
        
        self.assertNotIn('token', res.data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)