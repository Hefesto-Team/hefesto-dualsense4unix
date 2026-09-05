"""O `title` PRÓPRIO da fita da aba 06 tem de sobreviver ao tique.

MEDIDO EM 05/09/2026, no DOM vivo: o arquivo publicado traz

    <div class="fita inerte" title="Não se aplica: mouse, teclado e gestos
    saem de um controle só — o do Player 1 — e o que eles fazem é do perfil.">

e o piloto — que troca o BLOCO INTEIRO da fita a cada tique — emitia a casca
genérica de `monta.fita()`. No primeiro tique a frase da 06 dava lugar a *"Esta
aba não usa o controle escolhido aqui — os cards são leitura."*, que diz menos e
é menos verdadeira: a razão de a 06 não escolher controle não é os cards serem
leitura, é o mouse sair de um controle só.

A resposta estava DIGITADA DUAS VEZES — `aba06.py` no arquivo, e nada no piloto.
Agora há um dono: `monta.TITULOS_DA_FITA`, consultado pelos dois.
"""
from __future__ import annotations

import sys
from pathlib import Path

_INTERFACE = (Path(__file__).resolve().parents[2] / "src"
              / "hefesto_dualsense4unix" / "interface")
if str(_INTERFACE) not in sys.path:
    sys.path.insert(0, str(_INTERFACE))

import monta

from hefesto_dualsense4unix.interface import hefesto_vivo

#: Uma mesa mínima, no formato que `_fita` recebe do tique.
MESA = [{"pref": "p1", "jogador": 1, "nome": "DualSense", "via": "USB",
         "cor": "", "uniq": "aabbcc000001"}]

TRECHO_DA_06 = "mouse, teclado e gestos saem de um controle só"
GENERICO = "Esta aba não usa o controle escolhido aqui"


class TestOTituloDaFitaSobreviveAoTique:
    def test_a_06_mantem_a_frase_dela(self) -> None:
        html = hefesto_vivo._fita(MESA, "06-navegacao.html")
        assert TRECHO_DA_06 in html, (
            "o piloto emitiu a casca genérica na aba 06: a frase própria dela "
            "dura um tique e some. O dono é `monta.TITULOS_DA_FITA`."
        )
        assert GENERICO not in html

    def test_as_outras_abas_de_leitura_ficam_no_generico(self) -> None:
        """A cura não pode ter dado a frase da 06 a quem não é a 06."""
        for pagina in ("05-vibracao.html", "09-sistema.html", "10-perfis.html"):
            html = hefesto_vivo._fita(MESA, pagina)
            assert GENERICO in html, pagina
            assert TRECHO_DA_06 not in html, pagina

    def test_as_abas_que_escolhem_seguem_com_o_titulo_de_quem_escolhe(self) -> None:
        html = hefesto_vivo._fita(MESA, "02-controles.html")
        assert "vai para o controle escolhido aqui" in html
        assert "inerte" not in html

    def test_o_arquivo_publicado_e_o_piloto_dizem_a_mesma_frase(self) -> None:
        """A dona é uma só, e é isto que prova que ela é uma só.

        Se alguém reescrever o `title` no `aba06.py` sem passar pela tabela, o
        arquivo publicado e a tela viva voltam a divergir — e a divergência dura
        um tique, que é o tempo de ninguém ver.
        """
        publicado = (_INTERFACE / "paginas" / "06-navegacao.html").read_text(
            encoding="utf-8")
        titulo = monta.TITULOS_DA_FITA["06-navegacao.html"]
        assert f'title="{titulo}"' in publicado

    def test_a_casca_devolve_nada_para_quem_nao_tem_frase_propria(self) -> None:
        assert monta.casca_da_fita("06-navegacao.html")
        assert monta.casca_da_fita("09-sistema.html") is None
        assert monta.casca_da_fita("01-jogar.html") is None


#: A GUARDA DE `a_fita_escolhe` PARAVA A BANCADA JUNTO COM O TYPO — 05/09/2026.
#: Ela nasceu no mesmo dia para impedir que um nome errado respondesse *"esta
#: aba é leitura"* em silêncio, e parava TUDO que não fosse uma das dez. Oito
#: testes que geram página própria (`98-prova-da-ressalva`, `97-botao-cinza`)
#: morreram na coleta. Bancada não é aba errada: é outra coisa.
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
