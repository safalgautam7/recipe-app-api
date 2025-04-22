"""Views for the recipe APIs."""
from rest_framework import viewsets,mixins
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from core.models import Recipe,Tag,Ingredient
from recipe import serializers


#by using MODELVIEWSET ,
# You're telling Django REST Framework (DRF):
# “Hey, I’m using a model, and I want all the standard CRUD actions — just wire them up for me.”

# Under the hood, ModelViewSet gives you:

# list() – GET /recipes/ 

# retrieve() – GET /recipes/<id>/

# create() – POST /recipes/

# update() – PUT /recipes/<id>/

# partial_update() – PATCH /recipes/<id>/

# destroy() – DELETE /recipes/<id>/

class RecipeViewSet(viewsets.ModelViewSet): 
    """View for manage recipe APIs."""
    
    serializer_class=serializers.RecipeDetailSerializer
    queryset=Recipe.objects.all()
    authentication_classes=[TokenAuthentication]
    permission_classes=[IsAuthenticated]
    
    def get_queryset(self):
        """Retrieve recipes for authenticated user."""
        return self.queryset.filter(user=self.request.user).order_by('-id')
    
    def get_serializer_class(self):
        """Return the serializer class for request."""
        if self.action=='list':
            return serializers.RecipeSerializer
        
        return self.serializer_class
    
    #when a new recipe is created , this method will be called as a part.
    #sets user value to the current authenticated user.
    def perform_create(self,serializer):
        """Create a new recipe."""
        serializer.save(user=self.request.user)


class BaseRecipeAttrViewSet(mixins.DestroyModelMixin,
                            mixins.UpdateModelMixin,
                            mixins.ListModelMixin,
                            viewsets.GenericViewSet):
    """Base viewset for recipe attributes."""
    authentication_classes=[TokenAuthentication]
    permission_classes=[IsAuthenticated]
    #to filter down to the user that created them 
    def get_queryset(self):
        """Filter queryset to authenticated user."""
        return self.queryset.filter(user=self.request.user).order_by('-name')


#mixins helps to modify the prebuilt method        
class TagViewSet(BaseRecipeAttrViewSet):
    """ Manage tags in the database."""
    serializer_class=serializers.TagSerializer
    queryset=Tag.objects.all()
    
    
    

class IngredientViewSet(BaseRecipeAttrViewSet):
    """Manage ingredients in the database."""
    serializer_class=serializers.IngredientSerialzier
    queryset=Ingredient.objects.all()
    
   