"""As lâmpadas esperam a cor — APARELHO-NAO-SE-CONTRADIZ-01, PARTE 1.

DECISÃO DELA, 20/09/2026, verbatim: *"As lâmpadas esperam a cor"*. A razão é
do produto, e não do código: **o aparelho nunca se contradiz consigo mesmo.**

## O que foi medido, com os quatro DualSense na mesa dela

Ela desligou o P3 (Cosmic Red) e olhou o P4 (Galactic Purple)::

    23:56:17.747  controller_disconnected reason=alvo_sumiu
          ~4 s    AS LÂMPADAS do aparelho mudam para três   ← vistas por ela
    23:56:47.765  numeracao_da_mesa_mudou arma o gatilho     +30,0 s
    23:56:49.284  gatilho_da_cor_escrito: rosa → verde       +31,5 s

Por **27 segundos** o mesmo controle mostrava três lâmpadas de Player 3 e a
barra do Player 4. A palavra dela, confirmando a predição: *"Rosa e só verde
meio minuto depois"*.

## O que esta régua mede, e onde ela MORDE

A cura não está em nenhuma das rotas de escrita — está ANTES delas, no número.
``numero_da_lampada`` passou a responder pela tabela LIBERADA
(``_numeros_das_lampadas_locked``), e é ela que alimenta os DOIS campos da
camada automática, a cor e o número. Não há caminho em que um avance sem o
outro.

A MORDIDA é :class:`TestAMordida`, e ela é literal: com a cura arrancada — isto
é, com ``numero_da_lampada`` voltando a responder pela mesa de agora — as
asserções de :class:`TestOAparelhoNaoSeContradiz` REPROVAM. Régua que passa com
a cura arrancada não mede nada.

E há a metade que prova o que JÁ funcionava: a TELA continua se refazendo na
hora (``numeros_da_mesa`` não espera nada), a estreia não espera, e a tabela
vazia responde exatamente como antes desta sprint.

Nenhum endereço real: faixa forjada ``aa:bb:cc:…`` com os octetos 4 e 5
zerados, a mesma allowlist de ``tests/unit/test_anonimato_de_fixtures.py``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod
from hefesto_dualsense4unix.daemon.subsystems.identity import (
    ControllerIdentityRegistry,
)

#: A mesa de quatro, na ordem em que ela os liga.
PRIMEIRO = "aa:bb:cc:00:00:01"
SEGUNDO = "aa:bb:cc:00:00:02"
TERCEIRO = "aa:bb:cc:00:00:03"
QUARTO = "aa:bb:cc:00:00:04"
UNIQS = (PRIMEIRO, SEGUNDO, TERCEIRO, QUARTO)

#: O que sobra quando o P3 sai — o gesto exato da medição de 20/09.
SOBRAM = (PRIMEIRO, SEGUNDO, QUARTO)

BOOT = "boot-teste-as-lampadas-esperam-a-cor"


class Relogio:
    """Relógio monotônico de mentira — as ondas de chegada sem `sleep`."""

    def __init__(self, inicio: float = 1000.0) -> None:
        self.agora = inicio

    def __call__(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos


@pytest.fixture
def config_isolado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`config_dir` em tmp — nada aqui toca o `controllers.json` dela."""
    from hefesto_dualsense4unix.utils import xdg_paths

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    monkeypatch.setattr(id_mod, "_read_boot_id", lambda: BOOT)
    return tmp_path


def mesa_de_quatro(relogio: Relogio) -> ControllerIdentityRegistry:
    """Os quatro na mesa, cada um na SUA onda — a fila do momento é 1, 2, 3, 4."""
    reg = ControllerIdentityRegistry(clock=relogio)
    na_mesa: list[str] = []
    for uniq in UNIQS:
        na_mesa.append(uniq)
        reg.sync_connected(list(na_mesa))
        relogio.avancar(id_mod.JANELA_DE_ONDA_SEC * 2)
    return reg


def numeros_das_lampadas(reg: ControllerIdentityRegistry) -> dict[str, int | None]:
    """O que cada controle da mesa pode MOSTRAR agora, pelo dono da resposta."""
    return {u: reg.numero_da_lampada(u, assign=False) for u in UNIQS}


@pytest.mark.usefixtures("config_isolado")
class TestOAparelhoNaoSeContradiz:
    """O número do aparelho não anda sem a cor — a decisão dela de 20/09."""

    def test_o_gatilho_ainda_nao_disparou_e_o_numero_nao_se_mexe(self) -> None:
        """P3 sai; até a liberação, o P4 continua sendo o jogador 4.

        É o cenário medido, e é a metade que custou 27 segundos.
        """
        relogio = Relogio()
        reg = mesa_de_quatro(relogio)
        assert reg.liberar_as_lampadas() is True  # a mesa estreia liberada
        assert numeros_das_lampadas(reg)[QUARTO] == 4

        reg.sync_connected(list(SOBRAM))  # o tique de 2 s viu o P3 sair

        assert numeros_das_lampadas(reg)[QUARTO] == 4, (
            "as lâmpadas do P4 andaram sem a cor — é a contradição de 20/09")
        assert numeros_das_lampadas(reg)[TERCEIRO] is None, (
            "quem saiu da mesa não acende número nenhum")

    def test_a_liberacao_move_os_dois_no_mesmo_instante(self) -> None:
        """`liberar_as_lampadas` é o instante único — e é o do gatilho da cor."""
        relogio = Relogio()
        reg = mesa_de_quatro(relogio)
        reg.liberar_as_lampadas()
        reg.sync_connected(list(SOBRAM))

        assert reg.liberar_as_lampadas() is True
        assert numeros_das_lampadas(reg)[QUARTO] == 3, (
            "a liberação não chegou ao número que o aparelho mostra")
        # E ela é idempotente: sem mesa nova, não há o que soltar.
        assert reg.liberar_as_lampadas() is False

    def test_a_cor_e_o_numero_saem_do_mesmo_slot(self) -> None:
        """A camada automática resolve os dois campos com UM número.

        É esta linha que torna a contradição impossível por construção: fossem
        dois números, a cura seria uma corrida entre duas rotas de escrita.
        """
        from hefesto_dualsense4unix.core.led_control import (
            player_led_pattern,
            player_slot_color,
        )

        relogio = Relogio()
        reg = mesa_de_quatro(relogio)
        reg.liberar_as_lampadas()
        reg.sync_connected(list(SOBRAM))

        provider = id_mod.make_auto_output_provider(reg)
        saida = provider(QUARTO)
        assert saida is not None
        assert saida.player_leds == player_led_pattern(4)
        assert saida.led == player_slot_color(4)

        reg.liberar_as_lampadas()
        saida = provider(QUARTO)
        assert saida is not None
        assert saida.player_leds == player_led_pattern(3)
        assert saida.led == player_slot_color(3)


@pytest.mark.usefixtures("config_isolado")
class TestOQueJaFuncionavaContinua:
    """A hipótese tem de explicar o que já funcionava — regra da casa."""

    def test_a_tela_nao_espera_nada(self) -> None:
        """`numeros_da_mesa` é a mesa de AGORA, e é ela que a tela lê.

        A decisão dela é sobre o APARELHO não se contradizer. A tela continua
        se refazendo em 0,2 s — e é por isso que o vão tela↔aparelho MUDA DE
        LUGAR em vez de sumir, o que a sprint declara.
        """
        relogio = Relogio()
        reg = mesa_de_quatro(relogio)
        reg.liberar_as_lampadas()
        reg.sync_connected(list(SOBRAM))

        assert reg.numeros_da_mesa() == {
            "aabbcc000001": 1, "aabbcc000002": 2, "aabbcc000004": 3}

    def test_sem_liberacao_nenhuma_a_resposta_e_a_de_sempre(self) -> None:
        """Tabela vazia = comportamento byte a byte igual ao de antes.

        Cobre o daemon recém-subido, o registro de teste e todo dublê sem
        gatilho: quem nunca liberou nada nunca congela nada.
        """
        relogio = Relogio()
        reg = mesa_de_quatro(relogio)
        reg.sync_connected(list(SOBRAM))
        assert numeros_das_lampadas(reg)[QUARTO] == 3

    def test_quem_estreia_nao_espera(self) -> None:
        """A cor nasce certa no tique do hotplug (D1) — a estreia não congela."""
        relogio = Relogio()
        reg = ControllerIdentityRegistry(clock=relogio)
        reg.sync_connected([PRIMEIRO])
        reg.liberar_as_lampadas()
        relogio.avancar(id_mod.JANELA_DE_ONDA_SEC * 2)

        reg.sync_connected([PRIMEIRO, SEGUNDO])
        assert reg.numero_da_lampada(SEGUNDO, assign=False) == 2, (
            "o que estreia tem de acender na hora — não há número velho a "
            "contradizer")

    def test_a_estreia_nunca_senta_no_colo_de_ninguem(self) -> None:
        """Congelar não pode ressuscitar a colisão de 27/08/2026.

        O caminho é real: o P1 sai, e um controle novo chega ANTES do gatilho.
        A mesa de agora daria a ele o número que outro ainda está congelado
        mostrando. A resposta certa é "sem opinião" até a liberação.
        """
        relogio = Relogio()
        reg = ControllerIdentityRegistry(clock=relogio)
        for uniq in (PRIMEIRO, SEGUNDO):
            reg.sync_connected([PRIMEIRO, SEGUNDO][: (1 if uniq == PRIMEIRO else 2)])
            relogio.avancar(id_mod.JANELA_DE_ONDA_SEC * 2)
        reg.liberar_as_lampadas()
        assert reg.numero_da_lampada(SEGUNDO, assign=False) == 2

        reg.sync_connected([SEGUNDO])            # o P1 saiu
        relogio.avancar(id_mod.JANELA_DE_ONDA_SEC * 2)
        reg.sync_connected([SEGUNDO, TERCEIRO])  # e o novo chegou antes do gatilho

        vistos = [n for n in numeros_das_lampadas(reg).values() if n is not None]
        assert len(vistos) == len(set(vistos)), (
            f"dois controles no mesmo jogador: {numeros_das_lampadas(reg)}")
        assert reg.numero_da_lampada(SEGUNDO, assign=False) == 2


@pytest.mark.usefixtures("config_isolado")
class TestAMordida:
    """Arranque a cura e veja a régua reprovar. Sem isto, ela não mede nada."""

    def test_o_caminho_pre_cura_deixa_a_lampada_andar_sozinha(self) -> None:
        """A cura arrancada = `numero_da_lampada` respondendo pela mesa de agora.

        É EXATAMENTE o código anterior a esta sprint (uma linha:
        ``_numeros_da_mesa_locked`` no lugar de ``_numeros_das_lampadas_locked``),
        e com ele a asserção do primeiro teste desta régua cai.
        """
        relogio = Relogio()
        reg = mesa_de_quatro(relogio)
        reg.liberar_as_lampadas()
        reg.sync_connected(list(SOBRAM))

        # Com a cura no lugar: o aparelho não se contradiz.
        assert reg.numero_da_lampada(QUARTO, assign=False) == 4

        # Com a cura ARRANCADA: o número anda sem a cor — a contradição de
        # 20/09 de volta, e a asserção acima reprovaria.
        sem_cura = reg._numeros_da_mesa_locked()  # é a mordida: o caminho velho
        assert sem_cura["aabbcc000004"] == 3, (
            "a mordida não reproduziu o mundo pré-cura: se os dois caminhos "
            "respondem igual, esta régua está medindo a si mesma")
