"""TROCA-DE-PLAYER-01 — a escolha à mão SOBREPÕE a fila de chegada (29/08/2026).

Palavra dela, hoje:

> "o nosso layout é pra permitir a TROCA DO PLAYER de cada controle. Medimos
> isso na época do lightbar e mapeamos isso. No novo layout temos uma seção pra
> isso e ELA TEM QUE FUNCIONAR."

**As duas regras convivem, e a distinção é o assunto deste arquivo.** A regra
AUTOMÁTICA — quem vira jogador 1 quando os controles chegam — é a fila de
chegada (D-30, ``_ordem_do_momento_locked``) e é decisão medida dela: com o
número colado à identidade, o controle branco era sempre o player 3 mesmo
SOZINHO na mesa. Ela não muda. O que este arquivo prova é a outra metade, na
forma que ela já fixou para o microfone
(``D-O-MICROFONE-A-MAQUINA-DA-O-PADRAO-O-PERFIL-SOBREPOE``): **a máquina dá o
padrão, a escolha sobrepõe.**

POR QUE A SUÍTE DE 25/07 NÃO VIA NADA DISSO
--------------------------------------------
``test_player01_um_numero_de_jogador.py`` tem 36 testes, todos verdes antes
desta cura, e **nenhum injeta relógio** — as 12 chamadas de ``sync_connected``
montam a mesa numa olhada só, então os três controles caem na MESMA onda de
chegada e o lugar gravado volta a ser o desempate. A suíte provava o mecanismo
exatamente no único caso em que ele já funcionava. A mesa dela — quatro
DualSense no rádio, ligados um a um — não é esse caso.

**Toda régua daqui liga o relógio.** É a diferença entre medir um instante e
medir um comportamento: sem tempo injetado, nem o congelamento da ordem
(``JANELA_MESA_ESTAVEL_SEC``) nem as ondas separadas
(``JANELA_DE_ONDA_SEC``) acontecem, e são justamente eles que desfaziam a
escolha dela segundos depois.

O QUE ESTAVA QUEBRADO, medido em 29/08 antes da cura
-----------------------------------------------------
Três DualSense ligados um a um (ondas 1, 2, 3), pedindo o 1 para o último::

    changed devolvido : {C: 1, A: 2, B: 3}   <- TRÊS: era rodízio, não troca
    rank gravado      : {A: 2, B: 3, C: 1}   <- o comando escreveu
    NA TELA           : {A: 1, B: 2, C: 3}   <- não se mexeu
    rank 4,0 s depois : {A: 1, B: 2, C: 3}   <- o congelamento APAGOU

E o falso sucesso puro, com o gravado dizendo ``A=1, B=2`` e ela ligando o B
primeiro (tela ``B=1, A=2``): pedir o 1 para o A devolvia
``{"ok": true, "changed": {}}`` e nada se movia.

A MORDIDA
---------
Cada teste diz, na docstring, com QUE cura arrancada ele reprova. Os números
das duas pontas estão no documento da sprint
(``docs/process/sprints/2026-08-29-TROCA-DE-PLAYER-01-a-secao-que-da-o-numero.md``).

Herméticos: ``config_dir`` em tmp, âncora fixa, relógio injetado, e MACs
sempre na faixa forjada ``aa:bb:cc:*`` com os octetos 4 e 5 zerados (máscara
da casa). Nenhum byte vai para aparelho: o registro de identidade é memória
mais um JSON.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`, pelo mesmo motivo do
# arquivo irmão — `importorskip` aceita o stub que outro arquivo planta.
exigir_gi_real("troca de player 01")

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import external_identity as ei_mod
from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod
from hefesto_dualsense4unix.daemon.subsystems.identity import (
    JANELA_DE_ONDA_SEC,
    JANELA_MESA_ESTAVEL_SEC,
    ControllerIdentityRegistry,
    make_auto_output_provider,
)
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController

#: A mesa desta régua — quatro MACs forjados, octetos 4 e 5 zerados (máscara
#: da casa). Os apelidos são os do mockup só para a leitura ficar humana; o
#: mecanismo não conhece cor de plástico nenhuma.
COSMIC = "aabbcc000001"
BLUE = "aabbcc000002"
PURPLE = "aabbcc000003"
WHITE = "aabbcc000004"

BOOT = "boot-teste-troca-de-player"


@dataclass
class _FakeDaemon:
    display_authority: str = "daemon"
    identity_registry: Any = None
    external_registry: Any = None


class _Relogio:
    """Relógio injetável — o instrumento que a suíte de 25/07 não tinha.

    ``anda`` é a única forma de o tempo passar aqui: nenhum ``sleep``, nenhuma
    régua dependente de máquina rápida ou lenta.
    """

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def anda(self, segundos: float) -> None:
        self.t += segundos


@pytest.fixture
def config_isolado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """``config_dir`` em tmp + âncora fixa (os dois registros dividem o arquivo)."""
    from hefesto_dualsense4unix.utils import xdg_paths

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    monkeypatch.setattr(id_mod, "_read_boot_id", lambda: BOOT)
    monkeypatch.setattr(ei_mod, "_read_boot_id", lambda: BOOT)
    return tmp_path


def _servidor(tmp_path: Path, ds: ControllerIdentityRegistry) -> IpcServer:
    """O CAMINHO PÚBLICO: o mesmo ``IpcServer`` que o botão da tela chama.

    Entrar pelo ``_set_number_locked`` direto passaria com a cura arrancada
    pela metade — o alinhamento e a aplicação moram no handler.
    """
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    daemon = _FakeDaemon(identity_registry=ds, external_registry=None)
    return IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=tmp_path / "troca.sock",
        daemon=daemon,
    )


def _mesa_um_a_um(
    ds: ControllerIdentityRegistry, relogio: _Relogio, uniqs: list[str]
) -> None:
    """Liga os controles UM A UM — cada um na sua própria onda de chegada.

    É a mesa dela, e é a que a suíte antiga nunca montou: entre um controle e
    o seguinte passa mais que :data:`JANELA_DE_ONDA_SEC`, então a casa os vê
    chegar em momentos DIFERENTES e a fila do momento manda sozinha.
    """
    ligados: list[str] = []
    for uniq in uniqs:
        ligados.append(uniq)
        ds.sync_connected(list(ligados))
        relogio.anda(JANELA_DE_ONDA_SEC + 0.1)


def _fila_no_disco(tmp: Path) -> dict[str, int]:
    """Endereço → lugar gravado, lido do ``controllers.json`` (schema 3)."""
    dados = json.loads((tmp / "controllers.json").read_text(encoding="utf-8"))
    return {
        str(e["addr"]): int(e["rank"])
        for e in dados[id_mod.ORDER_FIELD]
        if isinstance(e, dict) and e.get("kind") == id_mod.KIND_DUALSENSE
    }


class TestAEscolhaChegaNaTela:
    """A troca acontece — e acontece na mesa que chegou em ondas diferentes."""

    @pytest.mark.asyncio
    async def test_a_troca_move_a_tela_com_chegadas_separadas(
        self, config_isolado: Path
    ) -> None:
        """Três ligados um a um; o 1 vai para o último. A TELA SE MEXE.

        REPROVA COM A CURA ARRANCADA: tire o ``escolha_da_mao`` do
        ``_set_number_locked`` (volte a chamar ``compact``) e a tela fica em
        ``{Cosmic: 1, Blue: 2, Purple: 3}`` — o comando escreve o lugar
        gravado, mas quem pinta a tela é a fila do momento, que não foi
        tocada. Medido antes da cura: ``NA TELA`` idêntico antes e depois.
        """
        relogio = _Relogio()
        ds = ControllerIdentityRegistry(clock=relogio)
        _mesa_um_a_um(ds, relogio, [COSMIC, BLUE, PURPLE])

        assert ds.numeros_da_mesa() == {COSMIC: 1, BLUE: 2, PURPLE: 3}
        # A prova de que a mesa é MESMO a de ondas separadas — sem isto o
        # teste degradaria para o caso fácil da suíte de 25/07 sem avisar.
        assert ds.snapshot_chegada() == {COSMIC: 1, BLUE: 2, PURPLE: 3}

        server = _servidor(config_isolado, ds)
        resposta = await server._handle_identity_number_set(
            {"uniq": PURPLE, "number": 1}
        )

        assert resposta["ok"] is True
        assert ds.numeros_da_mesa() == {PURPLE: 1, BLUE: 2, COSMIC: 3}

    @pytest.mark.asyncio
    async def test_os_dois_trocam_e_o_do_meio_nao_se_mexe(
        self, config_isolado: Path
    ) -> None:
        """TROCA, não rodízio — a palavra dela de 28/08.

        Quatro na mesa, o 1 para o último. A troca mexe em DOIS; o rodízio
        mexeria em quatro.

        REPROVA COM A CURA ARRANCADA: devolva o ``pop``+``insert`` e o Blue
        vira 3 e o Purple vira 4 — ``changed`` sai com quatro chaves em vez
        de duas.
        """
        relogio = _Relogio()
        ds = ControllerIdentityRegistry(clock=relogio)
        _mesa_um_a_um(ds, relogio, [COSMIC, BLUE, PURPLE, WHITE])
        assert ds.numeros_da_mesa() == {COSMIC: 1, BLUE: 2, PURPLE: 3, WHITE: 4}

        server = _servidor(config_isolado, ds)
        resposta = await server._handle_identity_number_set(
            {"uniq": WHITE, "number": 1}
        )

        assert ds.numeros_da_mesa() == {WHITE: 1, BLUE: 2, PURPLE: 3, COSMIC: 4}
        # Exatamente DOIS mudaram de lugar. É esta linha que separa troca de
        # rodízio, e ela é a única que o mockup promete em dezessete lugares.
        assert set(resposta["changed"]) == {WHITE, COSMIC}

    @pytest.mark.asyncio
    async def test_o_gravado_em_desacordo_com_a_tela_nao_devolve_ok_a_toa(
        self, config_isolado: Path
    ) -> None:
        """O falso sucesso: ``ok:true`` com ``changed`` vazio e nada movido.

        Reboot com a fila gravada ``Cosmic=1, Blue=2``; ela liga o **Blue**
        primeiro, então a tela mostra ``Blue=1, Cosmic=2``. Pedir o 1 para o
        Cosmic tem de MOVER.

        REPROVA COM A CURA ARRANCADA: tire o ``alinhar_gravado_com_a_tela`` e
        o plano é calculado sobre o lugar GRAVADO, onde o Cosmic já é o
        primeiro — medido em 29/08, ``changed`` volta ``set()`` e o
        ``if changed:`` do handler pula a repintura inteira.

        **A linha que morde é a do ``changed``, e a ordem das três importa.**
        Com só o alinhamento arrancado, a última asserção passa por acidente:
        o ``escolha_da_mao`` realinha as ondas mesmo quando nenhum lugar
        mudou, e a tela acaba certa por efeito colateral — com o daemon
        calado, sem repintar LED nenhum. Com as DUAS curas fora (o código de
        antes desta sprint), medido: ``changed: {}`` **e** a tela parada em
        ``{Blue: 1, Cosmic: 2}``.
        """
        relogio = _Relogio()
        ds = ControllerIdentityRegistry(clock=relogio)
        ds.load()
        ds._ordem = {COSMIC: 1, BLUE: 2}  # o que atravessou o reboot
        _mesa_um_a_um(ds, relogio, [BLUE, COSMIC])

        assert ds.numeros_da_mesa() == {BLUE: 1, COSMIC: 2}

        server = _servidor(config_isolado, ds)
        resposta = await server._handle_identity_number_set(
            {"uniq": COSMIC, "number": 1}
        )

        assert resposta["ok"] is True
        assert set(resposta["changed"]) == {COSMIC, BLUE}
        assert ds.numeros_da_mesa() == {COSMIC: 1, BLUE: 2}


class TestAEscolhaSobreviveAoTempo:
    """A metade que os testes verdes não viam: a escolha desfeita segundos depois."""

    @pytest.mark.asyncio
    async def test_a_troca_sobrevive_ao_congelamento_da_ordem(
        self, config_isolado: Path
    ) -> None:
        """A mesa fica estável e o congelamento roda — a escolha FICA.

        ``_congelar_locked`` reescreve os lugares gravados a partir das ondas
        de chegada. Antes da cura ele não sabia que houvera escolha à mão e
        passava por cima dela: a escolha durava menos que os
        :data:`JANELA_MESA_ESTAVEL_SEC` = 4,0 s.

        REPROVA COM A CURA ARRANCADA: sem a redistribuição das ondas em
        ``escolha_da_mao``, a mesa volta a ``{Cosmic: 1, Blue: 2, Purple: 3}``
        aqui. Medido antes da cura: ``rank`` depois do congelamento igual ao
        de antes do comando.
        """
        relogio = _Relogio()
        ds = ControllerIdentityRegistry(clock=relogio)
        _mesa_um_a_um(ds, relogio, [COSMIC, BLUE, PURPLE])

        server = _servidor(config_isolado, ds)
        await server._handle_identity_number_set({"uniq": PURPLE, "number": 1})
        escolhido = ds.numeros_da_mesa()
        assert escolhido == {PURPLE: 1, BLUE: 2, COSMIC: 3}

        # A mesa se mexe (alguém pisca no rádio) e volta a assentar: é este o
        # gatilho do congelamento, e ele roda sem que ninguém peça.
        ds.mark_disconnected(BLUE)
        ds.sync_connected([COSMIC, BLUE, PURPLE])
        relogio.anda(JANELA_MESA_ESTAVEL_SEC + 0.1)
        ds.numeros_da_mesa()  # o tique lento: é aqui que a foto é tirada

        assert ds.mesa_congelada() is True
        assert ds.numeros_da_mesa() == escolhido

    @pytest.mark.asyncio
    async def test_a_troca_chega_ao_disco_e_fica_la(
        self, config_isolado: Path
    ) -> None:
        """O ``controllers.json`` guarda a escolha, e o congelamento não a desfaz.

        O campo ``order`` é o dono ÚNICO do número de jogador
        (``utils/maquina.py``), então a escolha só existe de verdade quando
        está gravada ali.

        REPROVA COM A CURA ARRANCADA: sem ``escolha_da_mao``, o arquivo até
        recebe os lugares novos (o ``compact`` grava), mas o congelamento
        seguinte os reescreve a partir das ondas e o disco volta ao que era.
        """
        relogio = _Relogio()
        ds = ControllerIdentityRegistry(clock=relogio)
        _mesa_um_a_um(ds, relogio, [COSMIC, BLUE, PURPLE])

        server = _servidor(config_isolado, ds)
        await server._handle_identity_number_set({"uniq": PURPLE, "number": 1})
        assert _fila_no_disco(config_isolado) == {PURPLE: 1, BLUE: 2, COSMIC: 3}

        ds.mark_disconnected(BLUE)
        ds.sync_connected([COSMIC, BLUE, PURPLE])
        relogio.anda(JANELA_MESA_ESTAVEL_SEC + 0.1)
        ds.numeros_da_mesa()
        ds.sync_connected([COSMIC, BLUE, PURPLE])  # o tique lento salva

        assert _fila_no_disco(config_isolado) == {PURPLE: 1, BLUE: 2, COSMIC: 3}

    @pytest.mark.asyncio
    async def test_a_escolha_sobrevive_ao_replug_do_controle_trocado(
        self, config_isolado: Path
    ) -> None:
        """O controle escolhido cai e volta — e volta com o número dela.

        É a promessa D2/R-15 (``mark_disconnected`` preserva a marca de
        chegada) aplicada à escolha à mão: sem ela, a volta seria lida como
        chegada nova e mandaria o controle para o fim da fila — o defeito de
        ORDEM DE WAKE que a auditoria de 23/07 arrancou.

        REPROVA COM A CURA ARRANCADA: sem a redistribuição das ondas, o
        Purple volta com a onda 3 que tinha e a tela devolve o 3 a ele.
        """
        relogio = _Relogio()
        ds = ControllerIdentityRegistry(clock=relogio)
        _mesa_um_a_um(ds, relogio, [COSMIC, BLUE, PURPLE])

        server = _servidor(config_isolado, ds)
        await server._handle_identity_number_set({"uniq": PURPLE, "number": 1})

        ds.mark_disconnected(PURPLE)
        relogio.anda(JANELA_DE_ONDA_SEC + 0.1)
        assert ds.numeros_da_mesa() == {BLUE: 1, COSMIC: 2}
        ds.sync_connected([COSMIC, BLUE, PURPLE])
        relogio.anda(JANELA_MESA_ESTAVEL_SEC + 0.1)
        ds.numeros_da_mesa()

        assert ds.numeros_da_mesa() == {PURPLE: 1, BLUE: 2, COSMIC: 3}

    @pytest.mark.asyncio
    async def test_quem_chega_depois_da_escolha_vai_para_o_fim(
        self, config_isolado: Path
    ) -> None:
        """A escolha não sequestra a fila: o quarto controle nasce jogador 4.

        A redistribuição das ondas usa o conjunto que os presentes JÁ têm —
        nenhuma onda nova é inventada, então quem conecta depois continua com
        a onda mais alta e cai no fim. É o que mantém a regra automática
        intacta debaixo da escolha.

        REPROVA se alguém trocar a redistribuição por "carimbar ondas novas":
        o White nasceria no meio da mesa.
        """
        relogio = _Relogio()
        ds = ControllerIdentityRegistry(clock=relogio)
        _mesa_um_a_um(ds, relogio, [COSMIC, BLUE, PURPLE])

        server = _servidor(config_isolado, ds)
        await server._handle_identity_number_set({"uniq": PURPLE, "number": 1})

        relogio.anda(JANELA_DE_ONDA_SEC + 0.1)
        ds.sync_connected([COSMIC, BLUE, PURPLE, WHITE])

        assert ds.numeros_da_mesa() == {
            PURPLE: 1,
            BLUE: 2,
            COSMIC: 3,
            WHITE: 4,
        }


class TestOComandoRecusadoNaoEscreve:
    """A recusa não toca o disco — a promessa que a própria cura quase comeu."""

    @pytest.mark.asyncio
    async def test_numero_fora_da_mesa_nao_grava_o_controllers_json(
        self, config_isolado: Path
    ) -> None:
        """Pedir um número que não existe recusa E NÃO ESCREVE.

        A docstring do ``_set_number_locked`` promete *"Erros (todos ANTES de
        qualquer escrita)"*, e a promessa é a que separa um comando recusado
        de um comando aplicado: quem recusa não mexe no arquivo dela.

        REPROVA COM A CURA ARRANCADA: ponha o
        ``alinhar_gravado_com_a_tela`` de volta ANTES das duas recusas (como
        esta sprint o escreveu primeiro) e o arquivo nasce do nada numa
        chamada recusada. Medido em 29/08: ``controllers.json`` inexistente
        antes, ``{Blue: 1, Cosmic: 2}`` depois de um
        ``{"ok": false, "reason": "numero_fora_da_mesa"}``.

        A mesa é a do desacordo de propósito — gravado ``Cosmic=1, Blue=2``,
        ela ligando o Blue primeiro. É só nela que o alinhamento tem algo a
        escrever; numa mesa já alinhada o teste passaria sem medir nada.
        """
        relogio = _Relogio()
        ds = ControllerIdentityRegistry(clock=relogio)
        ds.load()
        ds._ordem = {COSMIC: 1, BLUE: 2}
        _mesa_um_a_um(ds, relogio, [BLUE, COSMIC])
        arquivo = config_isolado / "controllers.json"
        assert not arquivo.exists()

        server = _servidor(config_isolado, ds)
        resposta = await server._handle_identity_number_set(
            {"uniq": COSMIC, "number": 9}
        )

        assert resposta == {
            "ok": False,
            "reason": "numero_fora_da_mesa",
            "max": 2,
        }
        assert not arquivo.exists()

    @pytest.mark.asyncio
    async def test_alvo_ausente_nao_grava_o_controllers_json(
        self, config_isolado: Path
    ) -> None:
        """O alvo que não está na mesa recusa E NÃO ESCREVE — mesma razão."""
        relogio = _Relogio()
        ds = ControllerIdentityRegistry(clock=relogio)
        ds.load()
        ds._ordem = {COSMIC: 1, BLUE: 2}
        _mesa_um_a_um(ds, relogio, [BLUE, COSMIC])
        arquivo = config_isolado / "controllers.json"
        assert not arquivo.exists()

        server = _servidor(config_isolado, ds)
        resposta = await server._handle_identity_number_set(
            {"uniq": WHITE, "number": 1}
        )

        assert resposta == {"ok": False, "reason": "controle_ausente"}
        assert not arquivo.exists()


class TestACorSegueONumero:
    """A cor da barra segue o número — e SÓ quando não há escolha à mão."""

    @pytest.mark.asyncio
    async def test_a_cor_acompanha_a_troca(self, config_isolado: Path) -> None:
        """Depois da troca, o Purple acende o azul do 1 e o Cosmic o verde do 3.

        A cor não é copiada em lugar nenhum: ela é DERIVADA do número, por
        ``player_slot_color`` dentro do provider automático. Provar isto aqui
        é provar que a barra não precisa de um segundo dono para acompanhar.

        REPROVA COM A CURA ARRANCADA: sem a troca chegando à tela, as cores
        ficam onde estavam (Cosmic azul, Purple verde).
        """
        relogio = _Relogio()
        ds = ControllerIdentityRegistry(clock=relogio)
        _mesa_um_a_um(ds, relogio, [COSMIC, BLUE, PURPLE])
        provider = make_auto_output_provider(ds)

        assert provider(COSMIC).led == (0, 0, 255)  # o azul do jogador 1
        assert provider(PURPLE).led == (0, 255, 0)  # o verde do jogador 3

        server = _servidor(config_isolado, ds)
        await server._handle_identity_number_set({"uniq": PURPLE, "number": 1})

        assert provider(PURPLE).led == (0, 0, 255)
        assert provider(COSMIC).led == (0, 255, 0)

    @pytest.mark.asyncio
    async def test_a_escolha_de_cor_a_mao_vence_a_cor_do_numero(
        self, config_isolado: Path
    ) -> None:
        """O caderno do mockup: *"sem escolha à mão ela é a cor do número"*.

        Com escolha à mão, a troca de número NÃO repinta o controle — o
        override por-uniq está ACIMA da camada automática no merge por campo
        (``_merged_desired_for_key``). O vizinho, que não tem escolha, segue o
        número normalmente: é o mesmo merge decidindo os dois casos.

        Não é mordida da cura desta sprint — é a prova de que a cura não
        atropelou a precedência que já existia. Se um dia ela reprovar, o
        defeito é a troca ter passado a escrever cor, que é o que ela nunca
        pode fazer.
        """
        from hefesto_dualsense4unix.core.backend_pydualsense import (
            PyDualSenseController,
            _DesiredOutput,
        )

        relogio = _Relogio()
        ds = ControllerIdentityRegistry(clock=relogio)
        _mesa_um_a_um(ds, relogio, [COSMIC, BLUE, PURPLE])

        # O merge REAL do backend, sem aparelho: o método é o mesmo que o
        # daemon chama antes de cada escrita de LED.
        backend = object.__new__(PyDualSenseController)
        backend._key_to_uniq = lambda k: k
        backend._desired_default = _DesiredOutput()
        backend._assentar_mesa_locked = lambda: None
        backend._auto_output_provider = make_auto_output_provider(ds)
        backend._desired_coop_by_uniq = {}
        backend._scaled_led = lambda uniq, resolvido: resolvido
        backend._game_output_by_uniq = {}
        backend._game_wins = lambda: False
        backend._desired_by_uniq = {PURPLE: _DesiredOutput(led=(128, 0, 255))}

        server = _servidor(config_isolado, ds)
        await server._handle_identity_number_set({"uniq": PURPLE, "number": 1})

        assert ds.numeros_da_mesa()[PURPLE] == 1
        # O Purple é o jogador 1 e continua roxo: a escolha dela manda.
        assert backend._merged_desired_for_key(PURPLE).led == (128, 0, 255)
        # O Cosmic não tem escolha à mão: caiu para o 3 e virou verde.
        assert backend._merged_desired_for_key(COSMIC).led == (0, 255, 0)
