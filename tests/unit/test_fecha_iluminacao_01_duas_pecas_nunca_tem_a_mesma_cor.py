"""FECHA-ILUMINACAO-01 — a cor única, e a prosa do botão que morreu.

`D-DUAS-PECAS-NUNCA-TEM-A-MESMA-COR` (`docs/data/decisoes-dela.csv:56`) é
**regra do produto, sempre**, e até 08/09/2026 não existia uma linha dela em
`src/`. A mesa dela provava: dois dos quatro DualSense guardavam no perfil as
cores dos slots **1 e 2**, e hoje eles são o **2 e o 4** — o número de outro dia
fossilizado no arquivo, com o rank 1 e o rank 2 acendendo o MESMO `#0000FF`.

**A RÉGUA CONTA CORES, NÃO CLIQUES**, e a razão é o defeito: ele não apaga cor
nenhuma, ele põe duas no mesmo lugar. Uma régua que contasse escritas ficaria
verde com a colisão viva — foi o que
`test_a_aba_04_iluminacao_fecha_as_linhas.py:307` fez o tempo todo, medindo o
instante da ESCRITA de um gesto só enquanto a colisão nascia depois, quando os
números giram.
"""
from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.led_control import (
    cores_sem_colisao,
    player_slot_color,
)

RAIZ = Path(__file__).resolve().parents[2]
PAGINAS = RAIZ / "src/hefesto_dualsense4unix/interface/paginas"
BANCADA = RAIZ / "mockup"

#: A FORMA da mesa dela, medida em 08/09/2026 no `controllers.json` e no
#: `personalizado.json`: quatro controles, `auto_player_colors: true`, global
#: `[40,80,180]`, e override de cor em exatamente DOIS — os ranks 2 e 4,
#: guardando as cores dos slots **1 e 2**.
#:
#: OS ENDEREÇOS SÃO FORJADOS (`aa:bb:cc`), e não os dela mascarados: o que esta
#: régua mede é o PADRÃO — quem tem override e que cor ele guarda —, e a
#: identidade não entra na conta. Máscara não é anonimato em fixture
#: versionada; `test_anonimato_de_fixtures.py` reprova o MAC derivado de real
#: mesmo com os octetos 4 e 5 zerados, e está certo.
RANK_DELA = {
    "aabbcc000001": 1,
    "aabbcc000002": 2,
    "aabbcc000003": 3,
    "aabbcc000004": 4,
}
OVERRIDE_DELA = {
    "aabbcc000002": (0, 0, 255),  # a cor do slot 1, no controle que hoje é o 2
    "aabbcc000004": (255, 0, 0),  # a cor do slot 2, no controle que hoje é o 4
}


def _backend(
    ranks: dict[str, int],
    overrides: dict[str, tuple[int, int, int]] | None = None,
    *,
    auto: bool = True,
    com_numero: bool = True,
    global_: tuple[int, int, int] = (40, 80, 180),
) -> bp.PyDualSenseController:
    """Um backend com a mesa posta — sem tocar em hardware nem em disco.

    `__new__` em vez do construtor de propósito: o que se mede aqui é o
    RESOLVEDOR, e abrir handles de verdade traria o `pydualsense` para dentro
    de uma régua que não fala com aparelho nenhum.
    """
    inst = bp.PyDualSenseController.__new__(bp.PyDualSenseController)
    inst._io_lock = threading.RLock()
    inst._handles = dict.fromkeys(ranks)
    inst._desired_default = bp._DesiredOutput(led=global_)
    inst._desired_by_uniq = {
        u: bp._DesiredOutput(led=c) for u, c in (overrides or {}).items()
    }
    inst._desired_coop_by_uniq = {}
    inst._game_output_by_uniq = {}
    inst._led_scale_by_uniq = {}
    inst._mesa_apresentada = frozenset()
    inst._game_authority_provider = None

    def provider(uniq: str) -> bp._DesiredOutput | None:
        slot = ranks.get(uniq)
        if slot is None or not auto:
            return None
        return bp._DesiredOutput(led=player_slot_color(slot))

    if com_numero:
        provider.numero_do_slot = ranks.get  # type: ignore[attr-defined]
    inst._auto_output_provider = provider
    return inst


def _cores(inst: bp.PyDualSenseController, ranks: dict[str, int]) -> list[Any]:
    """As cores resolvidas, na ordem do número — pelo LEITOR PÚBLICO.

    `resolved_led_for` é a fonte do `lightbar_source == "desired"` do
    `state_full` (`daemon/ipc_handlers.py`), então medir por ele é medir a
    mesma coisa que a TELA mostra e que o reassert escreve no fio.
    """
    return [
        inst.resolved_led_for(u)
        for u, _ in sorted(ranks.items(), key=lambda kv: kv[1])
    ]


class TestAMesaDela:
    """Os quatro DualSense dela, com o disco dela."""

    def test_as_quatro_cores_saem_distintas_e_na_cor_do_numero(self) -> None:
        """A cura, medida no leitor público.

        **A MORDIDA:** arranque `_com_cor_unica_locked` (devolva `r.saida`) e
        esta linha reprova com `3 de 4` — dois `#0000FF`, o rank 1 e o rank 2.
        Medido assim em 08/09/2026 antes da cura.
        """
        inst = _backend(RANK_DELA, OVERRIDE_DELA)

        cores = _cores(inst, RANK_DELA)

        assert len(set(cores)) == 4, (
            f"duas peças ficaram da mesma cor: {[_hexa(c) for c in cores]}")
        assert cores == [player_slot_color(n) for n in (1, 2, 3, 4)], (
            "as cores saíram distintas, mas não são as dos números de hoje — "
            "o fóssil deslocou para o lugar errado")

    def test_o_mesmo_estado_da_sempre_a_mesma_resposta(self) -> None:
        """Determinismo, e ele não é zelo: é o que impede a barra de piscar.

        Medido nesta casa em 05/09/2026 — devolver o endereço da fita fez a
        tela repintar 80 vezes em 80 tiques porque o valor tinha um segundo
        dono. Um passe que respondesse diferente na segunda volta faria a
        lightbar dela trocar de cor a cada batimento do reassert.
        """
        inst = _backend(RANK_DELA, OVERRIDE_DELA)

        assert _cores(inst, RANK_DELA) == _cores(inst, RANK_DELA)

    def test_a_ordem_de_hotplug_nao_muda_a_resposta(self) -> None:
        """Quem religa primeiro não rouba a cor do vizinho.

        `_handles` é ordem de HOTPLUG. Se o passe lesse dela, a mesa inteira
        trocaria de cor a cada religada — o mesmo defeito que o
        `_assentar_mesa_locked` fechou no NÚMERO, de volta na COR. Por isso a
        mesa se resolve na ordem do NÚMERO.
        """
        inst = _backend(RANK_DELA, OVERRIDE_DELA)
        esperado = _cores(inst, RANK_DELA)

        de_tras = _backend(RANK_DELA, OVERRIDE_DELA)
        de_tras._handles = dict.fromkeys(reversed(list(RANK_DELA)))

        assert _cores(de_tras, RANK_DELA) == esperado


class TestOQueNaoSeDesloca:
    """O limite do resolvedor — e ele custou três testes vermelhos."""

    def test_o_broadcast_dela_sobrevive(self) -> None:
        """`led.set` sem `uniq` grava a MESMA cor em todos, de propósito.

        No disco isso é indistinguível de duas escolhas que colidiram, porque
        `ControllerOverrides.leds` não guarda procedência. Um passe que
        deslocasse toda repetição desfaria o "pinta os dois de verde" dela no
        tique seguinte — é o que `test_led_set_broadcast.py` mede, e foi ele
        que derrubou a primeira versão desta regra.
        """
        ranks = {"aabbcc0000d1": 1, "aabbcc0000d2": 2}
        verde = (0, 255, 0)
        inst = _backend(ranks, dict.fromkeys(ranks, verde))

        assert _cores(inst, ranks) == [verde, verde]

    def test_a_cor_propria_que_nao_e_de_ninguem_fica(self) -> None:
        """Uma escolha de verdade sobrevive — só o fóssil se desloca."""
        ranks = {"aabbcc0000d1": 1, "aabbcc0000d2": 2}
        roxo = (90, 20, 140)
        inst = _backend(ranks, {"aabbcc0000d2": roxo})

        assert _cores(inst, ranks) == [player_slot_color(1), roxo]

    def test_a_barra_apagada_nao_e_colisao(self) -> None:
        """Preto é AUSÊNCIA de cor, não identidade.

        Deslocar uma barra apagada acenderia um controle que ela mandou
        apagar — e duas apagadas não são duas peças confundíveis: "as duas
        estão desligadas" é uma resposta.
        """
        ranks = {"aabbcc0000d1": 1, "aabbcc0000d2": 2}
        inst = _backend(ranks, dict.fromkeys(ranks, (0, 0, 0)))

        assert _cores(inst, ranks) == [(0, 0, 0), (0, 0, 0)]

    def test_o_jogo_pinta_por_cima_da_regra(self) -> None:
        """A camada GAME fica ACIMA do passe, como já fica acima do brilho.

        Deslocar a cor que o jogo pediu seria mentir sobre o que ele pediu —
        é a mesma razão do R-20 item 2. Aqui os dois pedem o fóssil azul; o
        que tem sessão de jogo mantém a cor do jogo.
        """
        inst = _backend(RANK_DELA, OVERRIDE_DELA)
        inst._game_authority_provider = lambda: "game"
        inst._game_output_by_uniq = {
            "aabbcc000002": bp._DesiredOutput(led=(0, 0, 255))
        }

        assert inst.resolved_led_for("aabbcc000002") == (0, 0, 255)


class TestOsBuracosQueOAutomaticoNaoFechava:
    """Os estados em que "o automático nunca colide" era FALSO."""

    def test_dois_controles_acima_do_oito_nao_ficam_os_dois_brancos(self) -> None:
        """`player_slot_color(slot)` devolve BRANCO para todo slot ≥ 9.

        O irmão `player_led_pattern` tem `_PLAYER_LED_OVERFLOW` documentado
        como *"só colide consigo mesmo"*; a cor não tinha essa garantia, e a
        docstring dela não a reivindicava. Dois controles em 9 e 10 recebiam a
        MESMA cor pela camada automática.
        """
        ranks = {"aabbcc0000d1": 9, "aabbcc0000d2": 10}
        inst = _backend(ranks)

        cores = _cores(inst, ranks)

        assert len(set(cores)) == 2, f"os dois ficaram brancos: {cores}"

    def test_quem_nao_tem_numero_nao_fica_igual_a_quem_tem(self) -> None:
        """O provider devolve `None` para quem não está na mesa.

        Aí o controle cai no `_desired_default`, o global do perfil — e com a
        cor global igual à de alguém, os dois ficam iguais. O passe alcança
        este estado porque a cor global é COMPARADA, mesmo não sendo
        deslocável.
        """
        ranks = {"aabbcc0000d1": 1, "aabbcc0000d2": 2}
        # o `bb` some da mesa do provider, mas continua com handle aberto
        inst = _backend({"aabbcc0000d1": 1}, {"aabbcc0000d1": (0, 0, 255)})
        inst._handles = dict.fromkeys(ranks)
        inst._desired_by_uniq["aabbcc0000d2"] = bp._DesiredOutput(led=(0, 0, 255))

        assert len(set(_cores(inst, ranks))) == 2


class TestARecusaComAMesaCheia:
    """Oito tons em uso: recusa, não gira."""

    def test_com_os_oito_tomados_a_cor_pedida_fica_como_esta(self) -> None:
        """Girar com a mesa cheia trocaria a cor de todo mundo a cada tique.

        A régua é sobre `cores_sem_colisao` direto porque a mesa de nove só
        existe com externos numerados junto (R-24), e o que se mede aqui é a
        REGRA, não a fiação.
        """
        mesa = [
            (f"u{n}", player_slot_color(n), player_slot_color(n))
            for n in range(1, 9)
        ]
        # o nono pede a cor do primeiro, e não sobra tom livre
        mesa.append(("u9", player_slot_color(1), None))

        saida = cores_sem_colisao(mesa)

        assert saida["u9"] == player_slot_color(1), (
            "com as oito tomadas a regra tem de RECUSAR, não girar")
        assert saida["u1"] == player_slot_color(1), "girou e tirou a cor do dono"


class TestOGestoDaAba:
    """A metade que o resolvedor não pode cumprir — e mora no gesto."""

    def test_escolher_o_tom_do_vizinho_desloca_e_diz_o_que_fez(self) -> None:
        """*"O segundo desloca para o tom vizinho e a tela diz o que fez."*

        **A MORDIDA:** faça `_sem_repetir_a_cor_do_vizinho` devolver
        `(rgb, None)` na primeira linha e as duas asserções reprovam — a cor
        sai repetida e o recado some.
        """
        from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

        ctx = _CtxDeMentira()
        alvo, recado = a04._sem_repetir_a_cor_do_vizinho(
            ctx, "aabbcc0000d1", player_slot_color(2))

        assert alvo != player_slot_color(2), "ficou com o tom que o vizinho tem"
        assert recado and "P2" in recado, f"a tela não disse o que fez: {recado}"

    def test_o_tom_livre_passa_calado(self) -> None:
        """Sem colisão não há frase — recado sobre nada é ruído."""
        from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

        alvo, recado = a04._sem_repetir_a_cor_do_vizinho(
            _CtxDeMentira(), "aabbcc0000d1", (90, 20, 140))

        assert alvo == (90, 20, 140)
        assert recado is None

    def test_o_seletor_livre_alcanca_o_hexa_exato_do_vizinho(self) -> None:
        """O `<input type="color">` não está preso aos oito tons da guia.

        Ele manda um hexa qualquer, inclusive o EXATO de outra coluna — e é
        por isso que a guarda não pode viver só na guia de tons.
        """
        from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

        alvo, recado = a04._sem_repetir_a_cor_do_vizinho(
            _CtxDeMentira(), "aabbcc0000d1", (255, 0, 0))

        assert alvo != (255, 0, 0)
        assert recado is not None


class _CtxDeMentira:
    """Dois controles na mesa: o `d1` (P1) e o `d2` (P2, vermelho aceso)."""

    def __init__(self) -> None:
        self.state: dict[str, Any] = {"active_profile": ""}
        self.conectados: list[dict[str, Any]] = [
            {"uniq": "aabbcc0000d1", "lightbar_rgb": [0, 0, 255],
             "player_slot": 1},
            {"uniq": "aabbcc0000d2", "lightbar_rgb": [255, 0, 0],
             "player_slot": 2},
        ]
        self.mesa: list[dict[str, Any]] = [
            {"uniq": "aabbcc0000d1", "jogador": 1, "nome": "DualSense"},
            {"uniq": "aabbcc0000d2", "jogador": 2, "nome": "DualSense"},
        ]


#: O NOME DO BOTÃO QUE MORREU. Ele saiu da aba no `2c228352` — o gesto foi
#: junto, e a página só conhece `apagar`, `auto-cores`, `brilho`, `cor`,
#: `player` e `reenviar`.
_BOTAO_MORTO = re.compile("autom" + "ático", re.I)


class TestAProsaDoBotaoQueMorreu:
    """*"Ainda temos 3 cantos falando sobre o automatico"* — palavra dela."""  # noqa-acento: citação literal dela

    @pytest.mark.parametrize("pasta", [PAGINAS, BANCADA])
    def test_a_pagina_04_nao_fala_do_botao_que_saiu(self, pasta: Path) -> None:
        """NAS DUAS LEITURAS, e a diferença entre elas é o ponto.

        `texto_visivel_no_produto` desconta o que a
        `interface/folha_da_casa.FOLHA_DA_CASA` esconde (`.nota`); a bancada é
        o que ela abre NO NAVEGADOR, sem folha nenhuma. Uma régua só do
        produto daria VERDE sobre as duas ocorrências da legenda — que é a
        assinatura de instrumento falso que esta casa persegue.

        **A MORDIDA:** devolva à dica do interruptor a frase que explicava o
        botão por coluna, ou à legenda o item que narrava a saída dele, e a
        linha correspondente reprova.
        """
        from hefesto_dualsense4unix.interface.frases_que_ela_baniu import (
            texto_visivel,
            texto_visivel_no_produto,
        )

        ler = texto_visivel if pasta is BANCADA else texto_visivel_no_produto
        texto = ler((pasta / "04-iluminacao.html").read_text(encoding="utf-8"))

        achados = _BOTAO_MORTO.findall(texto)

        assert achados == [], (
            f"{pasta.name}/04-iluminacao.html ainda fala do botão que saiu, "
            f"{len(achados)} vez(es)")

    def test_a_legenda_nao_narra_commit_nem_cita_decisao_dela(self) -> None:
        """A tela não é changelog — regra dela, 07/09/2026.

        *"O app tem que funcionar e não mostrar na tela que o app não presta.
        (...) o layout não informa os nossos defeitos."* A legenda citava a
        decisão dela de volta para ela (*"Deixa só lá o de cima mesmo o
        tongle"*) e narrava o commit que a executou.
        """
        from hefesto_dualsense4unix.interface.frases_que_ela_baniu import (
            texto_visivel,
        )

        texto = texto_visivel(
            (BANCADA / "04-iluminacao.html").read_text(encoding="utf-8"))

        for frase in ("O que mudou hoje", "Ainda aberto", "tongle",
                      "pedido seu", "decisão sua"):
            assert frase not in texto, f"a tela ainda narra: {frase!r}"


class TestORecadoQueMentia:
    """A frase do interruptor, e o comentário que a gerou."""

    def test_a_frase_nao_promete_o_que_o_produto_nao_faz(self) -> None:
        """*"Cada controle volta a acender a cor do número dele"* era FALSA.

        A camada automática está ABAIXO do override por-uniq no
        `_merged_desired_for_key`, então uma cor gravada continua vencendo —
        e dois dos quatro controles dela tinham uma. A frase de hoje diz as
        duas metades: quem não tem cor própria acende a do número, e duas
        nunca ficam iguais (que é a promessa que o passe agora cumpre).
        """
        from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao

        frase = a04_iluminacao._RECADO_DO_AUTOMATICO_VOLTOU

        assert "sem cor própria" in frase, (
            "a frase voltou a prometer a cor do número para TODO controle")
        assert "duas nunca ficam iguais" in frase


def _hexa(rgb: object) -> str:
    if not isinstance(rgb, tuple):
        return str(rgb)
    return "#" + "".join(f"{canal:02X}" for canal in rgb)
