"""
test_copy_engine.py — testes da correcção de concordância da marca.

Correr com:  python -m unittest test_copy_engine -v

Origem (24/08/2026): 12 mensagens em 69 na fila de prospeção com o nome da
empresa partido — 9x "No o Hermes Research" (artigo duplicado), 2x "Na Hermes
Research" (feminino), 1x "fundada por Sabino Kalufele". A regra que não se
negoceia: aplicar a correcção duas vezes tem de dar o mesmo resultado que
aplicar uma (idempotência), e texto já correcto sai INTOCADO.
"""
import unittest

from copy_engine import corrigir_concordancia_marca


class TestCorrigirConcordanciaMarca(unittest.TestCase):
    # Os 4 casos exactos da ordem de 25/08 (Mestre).
    CASOS_ORDEM = [
        ("No Hermes Research", "No Hermes Research"),
        ("No o Hermes Research", "No Hermes Research"),
        ("Na Hermes Research", "No Hermes Research"),
        ("fundada por Sabino", "fundado por Sabino"),
    ]

    # Variantes observáveis do mesmo defeito (artigo/contração + duplicações).
    CASOS_EXTRA = [
        ("no o Hermes Research", "no Hermes Research"),
        ("No o o Hermes Research", "No Hermes Research"),
        ("Na o Hermes Research", "No Hermes Research"),
        ("na Hermes Research", "no Hermes Research"),
        ("a Hermes Research", "o Hermes Research"),
        ("A Hermes Research publica análises.", "O Hermes Research publica análises."),
        ("da Hermes Research", "do Hermes Research"),
        ("pela Hermes Research", "pelo Hermes Research"),
        ("à Hermes Research", "ao Hermes Research"),
        ("À Hermes Research", "Ao Hermes Research"),
        ("o o Hermes Research", "o Hermes Research"),
        (
            "A Hermes Research, fundada por Sabino Kalufele, analisa empresas.",
            "O Hermes Research, fundado por Sabino Kalufele, analisa empresas.",
        ),
        ("fundada por Sabino Kalufele", "fundado por Sabino Kalufele"),
    ]

    # Texto que NUNCA pode ser tocado — feminino legítimo sobre terceiros e
    # frases já correctas (o estrago original foi exactamente "corrigir" texto
    # que já cumpria a regra).
    CASOS_INTOCAVEIS = [
        "No Hermes Research encontro o rigor que procuro.",
        "o Hermes Research, fundado por Sabino Kalufele",
        "A Sonangol, fundada em 1976, é a maior empresa de Angola.",
        "uma empresa fundada por João Pereira",
        "A vossa gestora, fundada por Maria Silva, publica sobre alocação.",
        "Cada análise do Hermes Research cita a fonte exacta.",
    ]

    def test_casos_exactos_da_ordem(self):
        for entrada, esperado in self.CASOS_ORDEM:
            with self.subTest(entrada=entrada):
                self.assertEqual(corrigir_concordancia_marca(entrada), esperado)

    def test_variantes_do_mesmo_defeito(self):
        for entrada, esperado in self.CASOS_EXTRA:
            with self.subTest(entrada=entrada):
                self.assertEqual(corrigir_concordancia_marca(entrada), esperado)

    def test_texto_correcto_ou_de_terceiros_fica_intocado(self):
        for texto in self.CASOS_INTOCAVEIS:
            with self.subTest(texto=texto):
                self.assertEqual(corrigir_concordancia_marca(texto), texto)

    def test_idempotencia_aplicar_duas_vezes_e_igual_a_uma(self):
        todas = (
            [e for e, _ in self.CASOS_ORDEM]
            + [e for e, _ in self.CASOS_EXTRA]
            + list(self.CASOS_INTOCAVEIS)
        )
        for entrada in todas:
            with self.subTest(entrada=entrada):
                uma_vez = corrigir_concordancia_marca(entrada)
                self.assertEqual(corrigir_concordancia_marca(uma_vez), uma_vez)

    def test_mensagem_completa_realista(self):
        entrada = (
            "Olá Nivaldo,\n\nNo o Hermes Research fazemos análise fundamental "
            "de empresas, com destaque para a BODIVA. A Hermes Research, "
            "fundada por Sabino Kalufele, procura feedback de quem gere "
            "capital em Luanda. Faz sentido falarmos?"
        )
        esperado = (
            "Olá Nivaldo,\n\nNo Hermes Research fazemos análise fundamental "
            "de empresas, com destaque para a BODIVA. O Hermes Research, "
            "fundado por Sabino Kalufele, procura feedback de quem gere "
            "capital em Luanda. Faz sentido falarmos?"
        )
        self.assertEqual(corrigir_concordancia_marca(entrada), esperado)


if __name__ == "__main__":
    unittest.main()
