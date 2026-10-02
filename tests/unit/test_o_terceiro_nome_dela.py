"""O-TERCEIRO-NOME-DELA-01 — «Tudo na TV e Nada no Controle»."""

from __future__ import annotations

import pathlib
import re

import pytest

from hefesto_dualsense4unix.app.audio_saida import (
    BYTE_NADA_NO_CONTROLE,
    BYTE_SONS_DO_JOGO,
    BYTE_TODO_O_SOM_DO_PC,
    botao_da_rota_aceso,
)
from hefesto_dualsense4unix.app.widgets.controller_card import (
    CANAL_NADA_NO_CONTROLE,
    ROTA_DO_CANAL,
)

PUBLICADO = pathlib.Path(
    "src/hefesto_dualsense4unix/interface/paginas/02-controles.html")
BANCADA = pathlib.Path("mockup/02-controles.html")
PACOTE = pathlib.Path(
    "src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py")

MESA = 4
NOME_DELA = "Tudo no PC e Nada no Controle"
NOME_DO_QUARTO = "Tudo no Controle e Nada no PC"
NOME_DE_ONTEM = "Tudo na TV e Nada no Controle"

def _a_02_esta_em_trabalho() -> bool:
    """A aba 02 está declarada em trabalho no `mockup/DIVERGENCIAS.md`?"""
    import importlib.util
    import sys

    alvo = pathlib.Path("scripts/check_o_desenho_aprovado.py").resolve()
    spec = importlib.util.spec_from_file_location("check_desenho_do_terceiro", alvo)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_desenho_do_terceiro"] = mod
    spec.loader.exec_module(mod)
    return "02-controles.html" in mod.declaradas()


@pytest.mark.parametrize("alvo", [PUBLICADO, BANCADA], ids=["publicado", "mockup"])
class TestOsQuatroNomesNaTela:
    """**O PUBLICADO SÓ FICA ATRÁS ENQUANTO A 02 ESTIVER DECLARADA EM"""

    def _corpo(self, alvo: pathlib.Path) -> str:
        if alvo == PUBLICADO and _a_02_esta_em_trabalho():
            pytest.skip("a 02 está declarada em trabalho: o publicado é o "
                        "desenho de ontem até quem coordena publicar")
        return alvo.read_text(encoding="utf-8")

    def test_o_terceiro_diz_o_nome_dela(self, alvo: pathlib.Path) -> None:
        """MORDIDA: devolva «Tudo na TV e Nada no Controle» ao terceiro botão."""
        vistos = re.findall(r'data-rota="nada"[^>]*>([^<]*)</button>',
                            self._corpo(alvo))
        assert vistos == [NOME_DELA] * MESA, (
            f"o terceiro botão diz {sorted(set(vistos)) or '[]'} e a palavra "
            f"dela é {NOME_DELA!r}")
        assert NOME_DE_ONTEM not in vistos

    def test_o_quarto_voltou_com_o_nome_do_espelho(self, alvo: pathlib.Path) -> None:
        """**ESTA TRAVA INVERTEU DE SENTIDO em 24/09.** De 21 a 23/09 ela"""
        vistos = re.findall(r'data-rota="pc"[^>]*>([^<]*)</button>',
                            self._corpo(alvo))
        assert vistos == [NOME_DO_QUARTO] * MESA, (
            f"o quarto botão diz {sorted(set(vistos)) or '[]'} e o nome dele é "
            f"{NOME_DO_QUARTO!r}")

    def test_a_fileira_tem_quatro(self, alvo: pathlib.Path) -> None:
        """**A régua que impede a cura de passar do ponto.** Quatro respostas"""
        assert len(re.findall(r'data-gesto="rota"', self._corpo(alvo))) == 4 * MESA

    def test_a_ordem_e_a_escala_dela(self, alvo: pathlib.Path) -> None:
        """Pouco · tudo · nada · só aqui, em todos os cartões."""
        ordem = re.findall(r'data-gesto="rota" data-rota="([a-z]+)"',
                           self._corpo(alvo))
        assert ordem == ["jogo", "junto", "nada", "pc"] * MESA, ordem


class TestOAtoMudouParaCaberNoNome:
    def test_nada_no_controle_e_o_byte_zero(self) -> None:
        """Estéreo para o FONE, com o alto-falante do controle fora do"""
        assert ROTA_DO_CANAL[CANAL_NADA_NO_CONTROLE] == 0
        assert BYTE_NADA_NO_CONTROLE == 0
        assert BYTE_SONS_DO_JOGO == 2 and BYTE_TODO_O_SOM_DO_PC == 3

    def test_o_gesto_devolve_a_tv_e_cala_o_controle(self) -> None:
        """O nome tem DOIS lados e o ato faz os dois."""
        fonte = PACOTE.read_text(encoding="utf-8")
        i = fonte.index("if qual == ROTA_NADA_NO_CONTROLE:")
        ramo = fonte[i : fonte.index("if qual == ROTA_OUVIR_JUNTO:", i)]
        assert "devolver_o_som_do_pc(de=uniq" in ramo, "o PC não recebe de volta"
        assert "CANAL_NADA_NO_CONTROLE" in ramo, "o byte do controle não é escrito"
        assert "speaker_set(" in ramo, "o byte não chega ao aparelho"

    def test_o_terceiro_apaga_o_mix(self) -> None:
        """Os três são UM estado."""
        fonte = PACOTE.read_text(encoding="utf-8")
        i = fonte.index("if qual == ROTA_NADA_NO_CONTROLE:")
        ramo = fonte[i : fonte.index("if qual == ROTA_OUVIR_JUNTO:", i)]
        assert '"sfx"' in ramo and '"mix"' in ramo

    def test_ele_nao_toca_som_de_confirmacao(self) -> None:
        """Os outros dois tocam para responder *"por onde ele sai agora"*."""
        fonte = PACOTE.read_text(encoding="utf-8")
        i = fonte.index("if qual == ROTA_NADA_NO_CONTROLE:")
        ramo = fonte[i : fonte.index("if qual == ROTA_OUVIR_JUNTO:", i)]
        assert "_confirmar_com_som" not in ramo


class TestAPinturaAcendeOTerceiro:
    """*A cura escrita e nunca ligada* — e aqui ela tem precedente exato: em"""

    @pytest.mark.parametrize(
        ("byte", "esperado"),
        [(0, "nada"), (2, "jogo"), (3, "pc"), (1, ""), (None, "")],
    )
    def test_cada_byte_acende_o_seu(self, byte, esperado) -> None:
        """MORDIDA: tire o ramo do `BYTE_NADA_NO_CONTROLE`. O 0 volta a apagar"""
        assert botao_da_rota_aceso(byte, "sink-do-p1", "sink-do-p1") == esperado

    def test_o_zero_acende_mesmo_com_a_saida_padrao_em_outro_lugar(self) -> None:
        """«Nada no Controle» é afirmação sobre o que SAI do plástico, e o"""
        assert botao_da_rota_aceso(0, "sink-do-p1", "a-televisao") == "nada"
        assert botao_da_rota_aceso(3, "sink-do-p1", "a-televisao") == ""

    def test_o_terceiro_vence_o_mix_esquecido(self) -> None:
        """Com a rota em 0 o alto-falante está fora do caminho: um `mix`"""
        fonte = PACOTE.read_text(encoding="utf-8")
        i = fonte.index("def aceso_da_fileira")
        corpo = fonte[i : fonte.index("\ndef ", i + 10)]
        assert "aceso in (ROTA_TUDO_NO_CONTROLE, ROTA_NADA_NO_CONTROLE)" in corpo


def test_a_capacidade_velha_nao_foi_apagada() -> None:
    """**§7 da sprint: não apague a `rota=3`.**"""
    from hefesto_dualsense4unix.app.widgets.controller_card import (
        CANAL_TODO_O_PC,
    )

    assert ROTA_DO_CANAL[CANAL_TODO_O_PC] == 3
    fonte = PACOTE.read_text(encoding="utf-8")
    assert '"pc"' in fonte, "o gesto deixou de aceitar `pc` — a capacidade sumiu"
