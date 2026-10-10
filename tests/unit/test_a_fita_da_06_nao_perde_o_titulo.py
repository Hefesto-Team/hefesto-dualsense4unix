"""A fita de leitura não tem balão: nem a da 06 nem as outras seis.

O `title` PRÓPRIO da 06 («Não se aplica: mouse, teclado e gestos…») existia desde
a cura de 03/09. Em 09/10/2026 o usuário escolheu, na sessão dos desenhos, que o balão da
fita sai das sete abas (O-SELECIONAR-ACENDE-QUEM-ESTA-ESCOLHIDO-01, opção a): com
os quatro acesos, a frase ficaria de pé ao lado de uma fita que diz «todos». O
arquivo mantém o nome e passa a guardar o inverso: o balão não volta no tique.
"""
from __future__ import annotations

import sys
from pathlib import Path

_INTERFACE = (Path(__file__).resolve().parents[2] / "src"
              / "hefesto_dualsense4unix" / "interface")

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.hefesto_vivo`, que carrega o GTK")

if str(_INTERFACE) not in sys.path:
    sys.path.insert(0, str(_INTERFACE))

import monta

from hefesto_dualsense4unix.interface import hefesto_vivo

MESA = [{"pref": "p1", "jogador": 1, "nome": "DualSense", "via": "USB",
         "cor": "", "uniq": "aabbcc000001"}]

TRECHO_DA_06 = "mouse, teclado e gestos saem de um controle só"
GENERICO = "Esta aba não usa o controle escolhido aqui"
ESCOLHE = "vai para o controle escolhido aqui"


class TestAFitaDeLeituraNaoTemBalao:
    def test_a_06_nao_tem_mais_a_frase_dela(self) -> None:
        html = hefesto_vivo._fita(MESA, "06-navegacao.html")
        assert TRECHO_DA_06 not in html and GENERICO not in html
        assert 'class="fita inerte">' in html, html[:120]

    def test_as_outras_abas_de_leitura_tambem_nao(self) -> None:
        for pagina in ("03-gatilhos.html", "05-vibracao.html", "09-sistema.html",
                       "10-perfis.html"):
            html = hefesto_vivo._fita(MESA, pagina)
            assert GENERICO not in html and TRECHO_DA_06 not in html, pagina
            assert 'class="fita inerte">' in html, pagina

    def test_as_abas_que_escolhem_seguem_com_o_titulo_de_quem_escolhe(self) -> None:
        html = hefesto_vivo._fita(MESA, "02-controles.html")
        assert ESCOLHE in html
        assert "inerte" not in html

    def test_o_desenho_e_o_piloto_dizem_o_mesmo(self) -> None:
        """O arquivo do desenho de cada aba de leitura não traz o balão."""
        for pagina in ("03-gatilhos", "04-iluminacao", "05-vibracao", "06-navegacao",
                       "07-lancadores", "09-sistema", "10-perfis"):
            desenho = (_INTERFACE.parents[2] / "mockup" / f"{pagina}.html").read_text(
                encoding="utf-8")
            assert GENERICO not in desenho and TRECHO_DA_06 not in desenho, pagina

    def test_o_dono_dos_balaoes_saiu(self) -> None:
        assert not hasattr(monta, "TITULOS_DA_FITA")
        assert not hasattr(monta, "casca_da_fita")


class TestAGuardaSeparaOTypoDaBancada:
    def test_o_typo_de_uma_das_dez_ainda_para(self) -> None:
        import pytest

        with pytest.raises(SystemExit):
            monta.a_fita_escolhe("03-gatihos")

    def test_a_bancada_com_numero_de_fora_passa_e_nao_escolhe(self) -> None:
        assert monta.a_fita_escolhe("98-prova-da-ressalva") is False
        assert monta.a_fita_escolhe("97-botao-cinza.html") is False

    def test_as_dez_continuam_respondendo_o_que_respondiam(self) -> None:
        assert monta.a_fita_escolhe("01-jogar") is True
        assert monta.a_fita_escolhe("02-controles.html") is True
        assert monta.a_fita_escolhe("08-conexoes") is True
        for leitura in ("03-gatilhos", "04-iluminacao", "05-vibracao",
                        "06-navegacao", "07-lancadores", "09-sistema",
                        "10-perfis"):
            assert monta.a_fita_escolhe(leitura) is False, leitura
