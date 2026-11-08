from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class GunicornBindTests(SimpleTestCase):
    def test_la_unit_escucha_en_todas_las_interfaces(self) -> None:
        unit = Path(settings.BASE_DIR).parent / "deploy" / "cody.service.in"
        texto = unit.read_text(encoding="utf-8")
        self.assertIn("Environment=GUNICORN_BIND=0.0.0.0:8000\n", texto)
        self.assertNotIn("127.0.0.1:8000", texto)
