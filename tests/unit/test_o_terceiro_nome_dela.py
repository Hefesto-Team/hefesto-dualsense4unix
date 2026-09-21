"""O-TERCEIRO-NOME-DELA-01 — «Tudo na TV e Nada no Controle».

**DECISÃO DELA, 20/09/2026**, perguntada com as duas leituras na mão:

    "O nome está certo, mude o ato."

O terceiro botão da fileira do alto-falante fazia o OPOSTO do nome que ela
escreveu: mandava todo o som do PC para o alto-falante daquele controle
(`rota = 3` mais `pactl set-default-sink`) e calava a televisão. Ela leu as
duas e decidiu pelo nome.

A ESCALA QUE ELA DESENHOU, lendo os três nomes juntos:

    Efeitos do Jogo                            só o que o jogo endereçar
    Efeitos do Jogo e Áudio da TV no Controle  tudo da máquina (`mix`)
    Tudo na TV e Nada no Controle              nada

**Pouco · tudo · nada** — três respostas que se excluem, que é o que uma
fileira de botões deve ser.
"""

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
NOME_DELA = "Tudo na TV e Nada no Controle"


@pytest.mark.parametrize("alvo", [PUBLICADO, BANCADA], ids=["publicado", "mockup"])
class TestOsTresNomesNaTela:
    def test_o_terceiro_diz_o_nome_dela(self, alvo: pathlib.Path) -> None:
        """MORDIDA: devolva «Só no controle» ao terceiro botão."""
        corpo = alvo.read_text(encoding="utf-8")
        vistos = re.findall(r'data-rota="nada"[^>]*>([^<]*)</button>', corpo)
        assert vistos == [NOME_DELA] * MESA, (
            f"o terceiro botão diz {sorted(set(vistos)) or '[]'} e a palavra "
            f"dela é {NOME_DELA!r}")

    def test_o_valor_velho_saiu_da_fileira(self, alvo: pathlib.Path) -> None:
        """`pc` continua existindo no gesto, no perfil e no IPC — **fora da
        fileira**. Deixá-lo na tela com o rótulo novo seria a mentira que esta
        sprint existe para matar: o nome dizendo «nada» e o clique mandando
        tudo.

        MORDIDA: devolva `data-rota="pc"` ao terceiro botão.
        """
        corpo = alvo.read_text(encoding="utf-8")
        assert 'data-rota="pc"' not in corpo, (
            "o `pc` voltou à fileira — o botão promete «nada no controle» e "
            "manda todo o som do PC para ele")

    def test_a_fileira_continua_com_tres(self, alvo: pathlib.Path) -> None:
        """**A régua que impede a cura de passar do ponto.**

        Trocar o ato não podia custar um botão: são três respostas que se
        excluem, e com duas a pergunta muda.
        """
        corpo = alvo.read_text(encoding="utf-8")
        assert len(re.findall(r'data-gesto="rota"', corpo)) == 3 * MESA


class TestOAtoMudouParaCaberNoNome:
    def test_nada_no_controle_e_o_byte_zero(self) -> None:
        """Estéreo para o FONE, com o alto-falante do controle fora do
        caminho — a tradução literal do nome dela na camada 2.

        MORDIDA: troque por 3 (o byte do «todo o som do PC»).
        """
        assert ROTA_DO_CANAL[CANAL_NADA_NO_CONTROLE] == 0
        assert BYTE_NADA_NO_CONTROLE == 0
        # e os outros dois não se mexeram
        assert BYTE_SONS_DO_JOGO == 2 and BYTE_TODO_O_SOM_DO_PC == 3

    def test_o_gesto_devolve_a_tv_e_cala_o_controle(self) -> None:
        """O nome tem DOIS lados e o ato faz os dois.

        MORDIDA: tire o `devolver_o_som_do_pc()` do ramo. O alto-falante cala
        e o som do PC fica preso onde estava — «Nada no Controle» sem o «Tudo
        na TV», que é meia promessa.
        """
        fonte = PACOTE.read_text(encoding="utf-8")
        i = fonte.index("if qual == ROTA_NADA_NO_CONTROLE:")
        ramo = fonte[i : fonte.index("if qual == ROTA_OUVIR_JUNTO:", i)]
        assert "devolver_o_som_do_pc()" in ramo, "a televisão não recebe de volta"
        assert "CANAL_NADA_NO_CONTROLE" in ramo, "o byte do controle não é escrito"
        assert "speaker_set(" in ramo, "o byte não chega ao aparelho"

    def test_o_terceiro_apaga_o_mix(self) -> None:
        """Os três são UM estado.

        Deixar o `mix` de pé embaixo de «Nada no Controle» faria o controle
        continuar ouvindo o PC com a tela dizendo que não.

        MORDIDA: tire o ramo do `mix`.
        """
        fonte = PACOTE.read_text(encoding="utf-8")
        i = fonte.index("if qual == ROTA_NADA_NO_CONTROLE:")
        ramo = fonte[i : fonte.index("if qual == ROTA_OUVIR_JUNTO:", i)]
        assert '"sfx"' in ramo and '"mix"' in ramo

    def test_ele_nao_toca_som_de_confirmacao(self) -> None:
        """Os outros dois tocam para responder *"por onde ele sai agora"*.

        Este promete o CONTRÁRIO — tocar aqui seria o botão desmentindo a si
        mesmo no instante do clique.

        MORDIDA: acrescente `_confirmar_com_som(ctx, uniq)` ao ramo.
        """
        fonte = PACOTE.read_text(encoding="utf-8")
        i = fonte.index("if qual == ROTA_NADA_NO_CONTROLE:")
        ramo = fonte[i : fonte.index("if qual == ROTA_OUVIR_JUNTO:", i)]
        assert "_confirmar_com_som" not in ramo


class TestAPinturaAcendeOTerceiro:
    """*A cura escrita e nunca ligada* — e aqui ela tem precedente exato: em
    10/09 o botão do meio nasceu sem nunca acender, e ela clicava, o perfil
    gravava, e a fileira acendia o botão de antes.
    """

    @pytest.mark.parametrize(
        ("byte", "esperado"),
        [(0, "nada"), (2, "jogo"), (3, "pc"), (1, ""), (None, "")],
    )
    def test_cada_byte_acende_o_seu(self, byte, esperado) -> None:
        """MORDIDA: tire o ramo do `BYTE_NADA_NO_CONTROLE`. O 0 volta a apagar
        os três, e o botão novo não acende NUNCA.
        """
        assert botao_da_rota_aceso(byte, "sink-do-p1", "sink-do-p1") == esperado

    def test_o_zero_acende_mesmo_com_a_saida_padrao_em_outro_lugar(self) -> None:
        """«Nada no Controle» é afirmação sobre o que SAI do plástico, e o
        plástico obedece ao byte. Só o «pc» depende da camada 1.
        """
        assert botao_da_rota_aceso(0, "sink-do-p1", "a-televisao") == "nada"
        assert botao_da_rota_aceso(3, "sink-do-p1", "a-televisao") == ""

    def test_o_terceiro_vence_o_mix_esquecido(self) -> None:
        """Com a rota em 0 o alto-falante está fora do caminho: um `mix`
        esquecido no perfil acenderia «No controle e na TV» sobre um controle
        que não toca nada.

        MORDIDA: tire `ROTA_NADA_NO_CONTROLE` da condição de `aceso_da_fileira`.
        """
        fonte = PACOTE.read_text(encoding="utf-8")
        i = fonte.index("def aceso_da_fileira")
        corpo = fonte[i : fonte.index("\ndef ", i + 10)]
        assert 'aceso in ("pc", ROTA_NADA_NO_CONTROLE)' in corpo


def test_a_capacidade_velha_nao_foi_apagada() -> None:
    """**§7 da sprint: não apague a `rota=3`.**

    Doze arquivos a referenciam, e uma delas é a planilha de ensaios. O que
    ela perdeu foi o BOTÃO; o caminho continua por IPC e por perfil, e a
    pergunta de se ele volta a ter porta na tela é dela.

    MORDIDA: apague `CANAL_TODO_O_PC` do `ROTA_DO_CANAL`.
    """
    from hefesto_dualsense4unix.app.widgets.controller_card import (
        CANAL_TODO_O_PC,
    )

    assert ROTA_DO_CANAL[CANAL_TODO_O_PC] == 3
    fonte = PACOTE.read_text(encoding="utf-8")
    assert '"pc"' in fonte, "o gesto deixou de aceitar `pc` — a capacidade sumiu"
