"""Serliazers for recipe APIs."""

from rest_framework import serializers
from core.models import Recipe, Tag, Ingredient


class IngredientSerialzier(serializers.ModelSerializer):
    """Serializers for ingredients."""

    class Meta:
        model = Ingredient
        fields = ["id", "name"]
        read_only_fields = ["id"]


class TagSerializer(serializers.ModelSerializer):
    """Serializer for Tags."""

    class Meta:
        model = Tag
        fields = ["id", "name"]
        read_only_fields = ["id"]


class RecipeSerializer(serializers.ModelSerializer):
    """Serlializer for recipes."""

    tags = TagSerializer(many=True, required=False)
    ingredients = IngredientSerialzier(many=True, required=False)

    class Meta:
        model = Recipe
        fields = [
            "id",
            "title",
            "time_minutes",
            "price",
            "link",
            "tags",
            "ingredients",
            "image",
        ]
        read_only_fields = ["id"]

    def _get_or_create_ingredients(self, ingredients, recipe):
        """Handle getting or creating ingredients as needed."""
        auth_user = self.context["request"].user
        for ingredient in ingredients:
            ingredient_obj, created = Ingredient.objects.get_or_create(
                user=auth_user,
                **ingredient,
            )
            recipe.ingredients.add(ingredient_obj)

    def _get_or_create_tags(self, tags, recipe):
        """Handle getting or creating tags as needed."""
        # bcz we're inside serializer
        auth_user = self.context["request"].user
        for tag in tags:
            tag_obj, created = Tag.objects.get_or_create(
                user=auth_user,
                **tag,
            )
            recipe.tags.add(tag_obj)

    # by default nested serializer are read only ,
    # so we have to manually define create method
    def create(self, validated_data):
        """Create a recipe."""
        tags = validated_data.pop("tags", [])
        ingredients = validated_data.pop("ingredients", [])

        recipe = Recipe.objects.create(**validated_data)
        self._get_or_create_ingredients(ingredients, recipe)
        self._get_or_create_tags(tags, recipe)
        return recipe

    def update(self, instance, validated_data):
        """Update recipe."""
        tags = validated_data.pop("tags", None)
        ingredients = validated_data.pop("ingredients", None)
        if tags is not None:
            instance.tags.clear()
            self._get_or_create_tags(tags, instance)

        if ingredients is not None:
            instance.ingredients.clear()
            self._get_or_create_ingredients(ingredients, instance)

        for attr, value in validated_data.items():
            # it takes the instance and assigns the value provided here
            setattr(instance, attr, value)

        instance.save()
        return instance


class RecipeDetailSerializer(RecipeSerializer):
    """Serializer for recipe detail view."""

    class Meta(RecipeSerializer.Meta):
        fields = RecipeSerializer.Meta.fields + ["description"]


class RecipeImageSerializer(serializers.ModelSerializer):
    """Serializers for uplaoding image to recipes."""

    class Meta:
        model = Recipe
        fields = ["id", "image"]
        read_only_fields = ["id"]
        extra_kwargs = {"image": {"required": "True"}}
