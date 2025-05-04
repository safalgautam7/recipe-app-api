"""Views for the recipe APIs."""

from drf_spectacular.utils import (
    extend_schema_view,
    extend_schema,
    OpenApiParameter,
    OpenApiTypes,
)
from rest_framework import viewsets, mixins, status

# action is a way to add new functionality to viewset default functionality
from rest_framework.decorators import action
from rest_framework.response import Response


from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from core.models import Recipe, Tag, Ingredient
from recipe import serializers


# by using MODELVIEWSET ,
# You're telling Django REST Framework (DRF):
# “Hey, I’m using a model, and
# I want all the standard CRUD actions — just wire them up for me.”

# Under the hood, ModelViewSet gives you:

# list() – GET /recipes/

# retrieve() – GET /recipes/<id>/

# create() – POST /recipes/

# update() – PUT /recipes/<id>/

# partial_update() – PATCH /recipes/<id>/

# destroy() – DELETE /recipes/<id>/


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                "tags",
                OpenApiTypes.STR,
                description="Comma separated list of tag IDs to filter.",
            ),
            OpenApiParameter(
                "Ingredients",
                OpenApiTypes.STR,
                description="Comma separated list of ingredient IDS to filter.",
            ),
        ]
    )
)
class RecipeViewSet(viewsets.ModelViewSet):
    """View for manage recipe APIs."""

    serializer_class = serializers.RecipeDetailSerializer
    queryset = Recipe.objects.all()
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _params_to_ints(self, qs):
        """convert a list of strings to integers."""
        return [int(str_id) for str_id in qs.split(",")]

    def get_queryset(self):
        """Retrieve recipes for authenticated user."""
        # parameters given in the urls is accessed through this method
        tags = self.request.query_params.get("tags")
        ingredients = self.request.query_params.get("ingredients")
        queryset = self.queryset
        if tags:
            tag_ids = self._params_to_ints(tags)
            queryset = queryset.filter(tags__id__in=tag_ids)
        if ingredients:
            ingredient_ids = self._params_to_ints(ingredients)
            queryset = queryset.filter(ingredients__id__in=ingredient_ids)

        return queryset.filter(user=self.request.user).order_by("-id").distinct()

    def get_serializer_class(self):
        """Return the serializer class for request."""
        if self.action == "list":
            return serializers.RecipeSerializer
        elif self.action == "upload_image":
            return serializers.RecipeImageSerializer

        return self.serializer_class

    # when a new recipe is created , this method will be called as a part.
    # sets user value to the current authenticated user.
    def perform_create(self, serializer):
        """Create a new recipe."""
        serializer.save(user=self.request.user)

    # detail = True means it is applied to only one recipe but not
    # all the recipes
    @action(methods=["POST"], detail=True, url_path="upload-image")
    def upload_image(self, request, pk=None):
        """Upload an image to recipe."""
        recipe = self.get_object()
        serializer = self.get_serializer(recipe, data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                "assigned_only",
                OpenApiTypes.INT,
                enum=[0, 1],
                description="Filter by items assgined to recipes.",
            )
        ]
    )
)
class BaseRecipeAttrViewSet(
    mixins.DestroyModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Base viewset for recipe attributes."""

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    # to filter down to the user that created them
    def get_queryset(self):
        """Filter queryset to authenticated user."""
        assigned_only = bool(int(self.request.query_params.get("assigned_only", 0)))
        queryset = self.queryset
        if assigned_only:
            queryset = queryset.filter(recipe__isnull=False)

        return queryset.filter(user=self.request.user).order_by("-name").distinct()


# mixins helps to modify the prebuilt method
class TagViewSet(BaseRecipeAttrViewSet):
    """Manage tags in the database."""

    serializer_class = serializers.TagSerializer
    queryset = Tag.objects.all()


class IngredientViewSet(BaseRecipeAttrViewSet):
    """Manage ingredients in the database."""

    serializer_class = serializers.IngredientSerialzier
    queryset = Ingredient.objects.all()
