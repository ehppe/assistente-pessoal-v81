from unittest import TestCase
from pathlib import Path
from pedido_lembrete import pedido_de_agendamento

class Correcao73(TestCase):
    def test_lembretes_pessoais_interceptados(self):
        for texto in ('me lembre amanha do almoco','me avisa as 12','crie um lembrete para amanha','agende um almoco','lembre-me de pagar','lembrete para amanha'):
            self.assertTrue(pedido_de_agendamento(texto),texto)

    def test_consultas_nao_interceptadas(self):
        for texto in ('qual o proximo jogo do corinthians','meus lembretes','que dia e hoje','o que e uma agenda'):
            self.assertFalse(pedido_de_agendamento(texto),texto)

    def test_acpi_nao_consultado(self):
        fonte=(Path(__file__).parents[1]/'util.py').read_text()
        self.assertNotIn('MSAcpi_ThermalZoneTemperature',fonte)
