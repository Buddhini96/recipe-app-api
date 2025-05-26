"""
Tests for recipe API.
"""

from decimal import Decimal

import os
import tempfile
from PIL import Image

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Recipe, Tag, Ingredient
from recipe.serializers import RecipeSerializer, RecipeDetailSerializer


RECIPE_URL = reverse('recipe:recipe-list')

def  image_upload_url(recipe_id):
    """Create and retuen an image upload url"""
    return reverse('recipe:recipe-upload-image', args=[recipe_id])

def detail_url(recipe_id):
    """Create and return a recipe detail URL."""
    return reverse('recipe:recipe-detail' , args=[recipe_id])

def create_user(params):
    """Create and return a new user"""
    user = get_user_model().objects.create_user(**params)
    return user

def create_recipe(user, **params):
    """create and return a sample recipe."""
    defaults = {
        'title': 'Sample recipe title',
        'time_minutes': 22,
        'price': Decimal("5.25"),
        'description': "Sample description",
        'link': "http://example.com/recipe.pdf"
    }

    defaults.update(params)

    recipe = Recipe.objects.create(user=user, **defaults)
    return recipe

class PublicRecipeAPITests(TestCase):
    """Test unauthenticated API requests."""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test auth is required to call API"""
        res = self.client.get(RECIPE_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

class PrivateRecipeAPITests(TestCase):
    """Test authenticated API requests."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user({'email':"test@example.com", 'password':"testpass123"})
        self.client.force_authenticate(self.user)

    def test_retrive_recipes(self):
        """Test retrieving a list of recipes."""
        create_recipe(user=self.user)
        create_recipe(user=self.user) 

        res = self.client.get(RECIPE_URL)
        recipes = Recipe.objects.all().order_by('-id')
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_retrive_recipes_limited_to_user(self):
        """Test retrieving a list of recipes for authenticated users."""
        other_user = create_user({"email":"test2@example.com",
            "password": "test123"})

        create_recipe(user=self.user)
        create_recipe(user=other_user) 

        res = self.client.get(RECIPE_URL)
        recipes = Recipe.objects.filter(user=self.user)

        serializer = RecipeSerializer(recipes, many=True)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_get_recipe_detail(self):
        """Test get recipe detail."""
        recipe = create_recipe(user=self.user)
        url = detail_url(recipe.id)
        res = self.client.get(url)

        serializer = RecipeDetailSerializer(recipe)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_create_recipe(self):
        payload = {
            'title': 'Sample recipe',
            'time_minutes': 30,
            'price': Decimal("5.99"),
            'description': "Sample description",
            'link': "http://example.com/recipe.pdf"
        }
        res = self.client.post(RECIPE_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipe = Recipe.objects.get(id=res.data['id'])

        for k,v in payload.items():
            self.assertEqual(getattr(recipe, k), v)

        self.assertEqual(recipe.user, self.user)

    def test_partial_updates(self):
        """Test partial updates of a recipe"""
        original_link = "https://example.com/recipe.pdf"
        recipe = create_recipe(
            user = self.user,
            title = 'Brownies',
            link= original_link
        )

        payload = {
            'title': 'Chocolate Brownies'
        }

        url = detail_url(recipe_id=recipe.id)
        res = self.client.patch(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        recipe.refresh_from_db()
        self.assertEqual(recipe.title, payload['title'])
        self.assertEqual(recipe.user, self.user)
        self.assertEqual(recipe.link, original_link)

    def test_full_update(self):
        "Test full update of a recipe."
        recipe = create_recipe(
            user = self.user,
            title = 'Chocolate Coffee Brownies',
            link= "https://example.com/brownie_recipe.pdf",
            description = "Sample Description",
        )

        payload = {            
            'title': 'New recipe title',
            'link': "https://example.com/brownie_recipe.pdf",
            'description': 'New description',
            'time_minutes': 10,
            'price': Decimal('2.50'),
            }
        
        url = detail_url(recipe_id=recipe.id)
        res = self.client.put(url, payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        recipe.refresh_from_db()

        for k, v in payload.items():
            self.assertEqual(getattr(recipe, k), v)

        self.assertEqual(recipe.user, self.user)


    def test_update_user_returns_error(self):
        """Test changing the recipe user results in an error"""
        new_user = create_user({"email": "bedirisi@example.com",
                                "password": "django123"})
        recipe = create_recipe(user=self.user)

        url = detail_url(recipe.id)

        payload = {
            "user": new_user.id
        }
        
        res = self.client.patch(url, payload)
        recipe.refresh_from_db()

        self.assertEqual(recipe.user, self.user) #status code 200

    
    def test_delete_recipe(self):
        """Test delete recipe successful"""
        recipe = create_recipe(self.user)

        url = detail_url(recipe_id=recipe.id)

        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Recipe.objects.all().filter(id=recipe.id).exists())

    def test_recipe_other_users_recipe_delete_error(self):
        """Test trying yo delete another users recipe gives error."""

        new_user = create_user({"email": "bedirisi@example.com",
                                "password": "django123"})
        recipe = create_recipe(user=new_user)

        url = detail_url(recipe.id)
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Recipe.objects.all().filter(id=recipe.id).exists())

    def test_create_recipe_with_new_tags(self):
        """Test creating a recipe with new tags"""
        payload = {
            'title': 'Sample Tag recipe',
            'time_minutes': 30,
            'price': Decimal("5.99"),
            'link': "http://example.com/recipe.pdf",
            'tags': [{'name': "Thai"}, {"name": "Dinner"}]
        }

        res = self.client.post(RECIPE_URL, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]
        self.assertEqual(recipe.tags.count(), 2)

        for tag in payload['tags']:
            self.assertTrue(recipe.tags.filter(name=tag["name"], user=self.user,).exists())

    def test_create_recipe_with_exisiting_tag(self):
        """Test creating a recipe with existing tag"""
        tag_indian = Tag.objects.create(user=self.user, name="Indian")
        payload = {
            'title': 'Sample Tag recipe',
            'time_minutes': 60,
            'price': Decimal("5.99"),
            'link': "http://example.com/recipe.pdf",
            'tags': [{'name': "Indian"}, {"name": "Breakfast"}]
        }
        res = self.client.post(RECIPE_URL, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]
        self.assertEqual(recipe.tags.count(), 2)
        self.assertIn(tag_indian, recipe.tags.all())
        for tag in payload['tags']:
            self.assertTrue(recipe.tags.filter(name=tag["name"], user=self.user,).exists())

    def test_create_tag_on_update(self):
        """Test creatign tag when updating a recipe."""
        recipe = create_recipe(user=self.user)
        payload = {'tags': [{'name': 'Lunch'}]}

        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        new_tag = Tag.objects.get(user=self.user, name='Lunch')
        self.assertIn(new_tag, recipe.tags.all())

    def test_update_recipe_assign_tag(self):
        """Test assiging existing tag when updating a recipe."""

        tag_breakfast = Tag.objects.create(user=self.user, name="Breakfast")
        recipe = create_recipe(user=self.user)
        recipe.tags.add(tag_breakfast)

        tag_lunch = Tag.objects.create(user=self.user, name="Lunch")
        payload = {'tags': [{'name': 'Lunch'}]}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(tag_lunch, recipe.tags.all())
        self.assertNotIn(tag_breakfast, recipe.tags.all())

    def test_clear_recipe_tags(self):

        """Test clearing a recipes tags."""
        tag = Tag.objects.create(user=self.user, name='Dessert')
        recipe = create_recipe(user=self.user)
        recipe.tags.add(tag)

        payload = {'tags': []}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.tags.count(), 0)

    def test_create_recipe_with_new_ingredients(self):
        """Test creating a recipe with new ingredients"""
        payload = {
            'title': 'Cookie',
            'time_minutes': 30,
            'price': Decimal("5.99"),
            'link': "http://example.com/recipe.pdf",
            'ingredients': [{'name': "Flour"}, {"name": "Butter"}]
        }

        res = self.client.post(RECIPE_URL, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]
        self.assertEqual(recipe.ingredients.count(), 2)

        for ingredients in payload['ingredients']:
            self.assertTrue(recipe.ingredients.filter(name=ingredients["name"], user=self.user,).exists())

    def test_create_recipe_with_exisiting_tag(self):
        """Test creating a recipe with existing ingredient"""
        ingredient = Ingredient.objects.create(user=self.user, name="Vanila")
        payload = {
            'title': 'Butter',
            'time_minutes': 60,
            'price': Decimal("5.99"),
            'link': "http://example.com/recipe.pdf",
            'ingredients': [{'name': "Egg"}, {"name": "Vanila"}]
        }
        res = self.client.post(RECIPE_URL, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]
        self.assertEqual(recipe.ingredients.count(), 2)
        self.assertIn(ingredient, recipe.ingredients.all())
        for ingredient in payload['ingredients']:
            self.assertTrue(recipe.ingredients.filter(name=ingredient["name"], user=self.user,).exists())

    def test_create_ingredient_on_update(self):
        """Test creatign ingredient when updating a recipe."""
        recipe = create_recipe(user=self.user)
        payload = {'ingredients': [{'name': 'Salt'}]}

        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        new_ingredient = Ingredient.objects.get(user=self.user, name='Salt')
        self.assertIn(new_ingredient, recipe.ingredients.all())

    def test_update_recipe_assign_ingredient(self):
        """Test assiging existing ingredient when updating a recipe."""

        ingredient_ginger = Ingredient.objects.create(user=self.user, name="Ginger")
        recipe = create_recipe(user=self.user)
        recipe.ingredients.add(ingredient_ginger)

        ingredient_chillie = Ingredient.objects.create(user=self.user, name="Chillie")
        payload = {'ingredients': [{'name': 'Chillie'}]}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(ingredient_chillie, recipe.ingredients.all())
        self.assertNotIn(ingredient_ginger, recipe.ingredients.all())

    def test_clear_recipe_ingredients(self):

        """Test clearing a recipes ingredients."""
        ingredient = Ingredient.objects.create(user=self.user, name='Cardamon')
        recipe = create_recipe(user=self.user)
        recipe.ingredients.add(ingredient)

        payload = {'ingredients': []}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.ingredients.count(), 0)

    def test_filter_by_tags(self):
        """Test filtering recipes by tags."""
        tag1 = Tag.objects.create(user=self.user, name='Vegan')
        tag2 = Tag.objects.create(user=self.user, name='Vegetarian')
        recipe1 = create_recipe(user=self.user, title="pasta")
        recipe2 = create_recipe(user=self.user, title="Macarroni")
        recipe3 = create_recipe(user=self.user, title="Gnocchi")
        recipe1.tags.add(tag1)
        recipe2.tags.add(tag2)

        params = {'tags': f'{tag1.id},{tag2.id}'}

        res = self.client.get(RECIPE_URL, params)

        s1 = RecipeSerializer(recipe1)
        s2 = RecipeSerializer(recipe2)
        s3 = RecipeSerializer(recipe3)

        self.assertIn(s1.data, res.data)
        self.assertIn(s2.data, res.data)
        self.assertNotIn(s3.data, res.data)

    def test_filter_by_ingredients(self):
        """Test filtering recipes by ingredients."""
        ingredient1 = Ingredient.objects.create(user=self.user, name='Onion')
        ingredient2 = Ingredient.objects.create(user=self.user, name='Mushroom')
        recipe1 = create_recipe(user=self.user, title="Pizza")
        recipe2 = create_recipe(user=self.user, title="Burger")
        recipe3 = create_recipe(user=self.user, title="Shawarma")
        recipe1.ingredients.add(ingredient1)
        recipe2.ingredients.add(ingredient2)

        params = {'ingredients': f'{ingredient1.id},{ingredient2.id}'}

        res = self.client.get(RECIPE_URL, params)

        s1 = RecipeSerializer(recipe1)
        s2 = RecipeSerializer(recipe2)
        s3 = RecipeSerializer(recipe3)

        self.assertIn(s1.data, res.data)
        self.assertIn(s2.data, res.data)
        self.assertNotIn(s3.data, res.data)


class ImageUploadTests(TestCase):
    """Tests for the image upload url"""

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user("test@example.com", "testpass123")
        self.client.force_authenticate(self.user)
        self.recipe = create_recipe(user=self.user)

    def tearDown(self):
        self.recipe.image.delete()

    def test_upload_image(self):
        """Test uploading image to a recipe"""
        url = image_upload_url(self.recipe.id)

        with tempfile.NamedTemporaryFile(suffix='.jpg') as image_file:
            img = Image.new('RGB', (10, 10))
            img.save(image_file, format='JPEG')
            image_file.seek(0)
            payload = {'image': image_file}

            res = self.client.post(url, payload, format='multipart')

        self.recipe.refresh_from_db()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('image', res.data)
        self.assertTrue(os.path.exists(self.recipe.image.path))

    def test_upload_image_bad_request(self):
        """Test uploading invalid  image to a recipe"""
        url = image_upload_url(self.recipe.id)
        payload = {'image': "non_image_file"}
        res = self.client.post(url, payload, format='multipart')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)









    