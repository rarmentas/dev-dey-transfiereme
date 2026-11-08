from django.test import SimpleTestCase

from ambito.clabe import clabe_es_valida

CLABE_OFICIAL = "012180015826225713"


class ClabeValidacionTests(SimpleTestCase):
    def test_clabe_oficial_documentada(self) -> None:
        self.assertTrue(clabe_es_valida(CLABE_OFICIAL))

    def test_checksum_invalido(self) -> None:
        mala = CLABE_OFICIAL[:-1] + ("0" if CLABE_OFICIAL[-1] != "0" else "1")
        self.assertFalse(clabe_es_valida(mala))

    def test_longitud_incorrecta(self) -> None:
        self.assertFalse(clabe_es_valida("123"))
        self.assertFalse(clabe_es_valida(CLABE_OFICIAL + "0"))

    def test_no_digitos(self) -> None:
        self.assertFalse(clabe_es_valida("01218001582622571a"))
