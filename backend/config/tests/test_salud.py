from django.test import TestCase
from rest_framework.test import APIClient


class SaludTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()

    def test_salud_responde_json_y_db(self) -> None:
        response = self.client.get("/api/salud/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["estado"], "ok")
        self.assertTrue(data["base_datos"])
