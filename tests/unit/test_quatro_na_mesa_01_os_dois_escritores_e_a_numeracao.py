"""QUATRO-NA-MESA-01 — os dois escritores de ``_connected`` e a numeração.

**O que só quebra quando são quatro.** A sprint nomeia quatro defeitos; a
ROTA CORRIGIDA de 06/09/2026 manda executar os DOIS que estão provados no
código e são de agente (1 e 2) e deixar os outros dois — corridas de relógio
de jogo e cache de sysfs — para a MESA-DE-QUATRO-01.

## Defeito 1 — ``_connected`` era escrito por uma LEITURA

``_connected`` decide quem CONTA para a numeração 1..N
(``ControllerIdentityRegistry._numeros_da_mesa_locked``), e tinha dois
escritores em cadências diferentes:

- o **tique lento** (``sync_connected``, ~2,0 s pelo ``lifecycle``)
  SUBSTITUI o conjunto pelo que o backend reporta conectado;
- a **leitura de cor** (``make_auto_output_provider`` →
  ``numero_da_lampada`` → ``slot_for(assign=True)``) ADICIONAVA — e ela roda a
  **10 Hz** enquanto a aba Status está aberta (``resolved_led_for``).

**Medido nesta árvore, 06/09/2026, com quatro endereços na mesa e o terceiro
marcado ausente pelo tique** — uma única leitura de cor do ausente:

    apos tique sem o 3o: {1º: 1, 2º: 2, 4º: 3}
    provider(ausente) -> _DesiredOutput(led=(0,255,0), player_leds=…)
    numeros da mesa DEPOIS: {1º: 1, 2º: 2, 3º: 3, 4º: 4}

O quarto foi de **3 para 4** e a lightbar dele de **verde para rosa** por
causa de uma consulta — e o tique o traz de volta a 3 dois segundos depois,
sem parar, enquanto o controle bounça no rádio. É a frase dela: *"quando um
controle pisca, os outros trocam de cor e de número sozinhos, e voltam"*.

A cura NÃO é chamar ``mark_disconnected`` (ele está sem chamador de produção
**de propósito** — R-15/D2: o lugar na fila sobrevive ao disconnect). O
defeito é a leitura ter efeito colateral sobre quem está na mesa. O provider
passou a chamar ``numero_da_lampada(autoridade_de_presenca=False)``: ele
continua ATRIBUINDO lugar na fila (R-14 §1) e continua apresentando um
endereço que ESTREIA (D1 — a cor nasce certa no tique do hotplug), mas quem
READMITE um ausente é só o tique.

## Defeito 2 — dois espaços de numeração pintavam a barra

O aceite, e a sprint é explícita: **não se escreve contra o sysfs.**
``/sys/class/leds`` mostra o número do KERNEL (medido em 25/07), o Pro
Nintendo acende TRÊS LEDs para dizer "Jogador 3" e o DualSense usa o padrão
PS5 — três leituras diferentes, nenhuma casando com o que ela vê. Um teste
que leia o sysfs passa com a colisão de pé. Então mede-se **o que o daemon
AFIRMA**: o ``player_slot`` que o handler IPC publica
(``_player_slot_for`` → ``slot_for(assign=False)``) e o ``player_leds`` que a
camada automática resolve — os dois, com quatro entradas.

A trava anti-duplicata já é ESTRUTURAL desde 27/08 (``_numeros_da_mesa_locked``
nasce de um ``zip`` estritamente crescente). O que faltava era ela ser
ALCANÇÁVEL: com a autoadmissão do defeito 1, a tabela mudava debaixo de quem
já tinha lido. :class:`TestNenhumInstanteComDoisNoMesmoJogador` é a régua que
tranca as duas metades juntas.

## A mordida desta régua

:class:`TestAReguaSabeRecusar` exercita o caminho PRÉ-CURA, que continua
alcançável de propósito (``autoridade_de_presenca=True`` é o default, porque
o tique também usa este caminho) e exige que as mesmas asserções REPROVEM.
Régua que só sabe passar não é régua — e o dublê daqui sabe recusar.

Nenhum endereço real: faixa forjada ``aa:bb:cc:…`` com os octetos 4 e 5
zerados, a mesma allowlist de ``tests/unit/test_anonimato_de_fixtures.py``. A
mesa de quatro reproduz a ORDEM da mesa dela; os bytes, não.
"""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.led_control import (
    player_led_pattern,
    player_slot_color,
)
from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod
from hefesto_dualsense4unix.daemon.subsystems.identity import (
    ControllerIdentityRegistry,
    make_auto_output_provider,
)
from tests.unit.test_backend_multi_controller import _FakeHandle, _null_evdev

# --- a mesa de quatro, mascarada --------------------------------------------

#: Os quatro na ordem da fila. O TERCEIRO é o que pisca no rádio — de
#: propósito no meio, para que uma readmissão indevida mexa no número do
#: quarto (o degrau que o defeito 1 produz) sem mexer nos dois da frente.
KEYS = (
    "AA:BB:CC:00:00:01",
    "AA:BB:CC:00:00:02",
    "AA:BB:CC:00:00:03",
    "AA:BB:CC:00:00:04",
)
UNIQS = tuple(k.replace(":", "").lower() for k in KEYS)
PRIMEIRO, SEGUNDO, QUE_PISCA, QUARTO = UNIQS

#: Os que continuam na mesa enquanto o terceiro pisca — os "MACs vivos" do
#: aceite, cujo slot tem de ser ESTÁVEL.
VIVOS = (PRIMEIRO, SEGUNDO, QUARTO)

BOOT = "boot-teste-quatro-na-mesa-01"

#: A aba Status resolve a 10 Hz (``ipc_handlers``: *"o `state_full` roda a
#: 10 Hz"*). Oito segundos de aba aberta = 80 leituras — a mesma ordem de
#: grandeza da janela de ≤30 s em que o handle sobrevive ao piscar do rádio.
LEITURAS_DE_OITO_SEGUNDOS = 80


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
    """`config_dir` em tmp — nenhum teste daqui toca o `controllers.json` dela."""
    from hefesto_dualsense4unix.utils import xdg_paths

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    monkeypatch.setattr(id_mod, "_read_boot_id", lambda: BOOT)
    return tmp_path


def mesa_de_quatro(relogio: Relogio) -> ControllerIdentityRegistry:
    """Os quatro na mesa, cada um na SUA onda — a fila do momento é 1, 2, 3, 4.

    Um de cada vez, com intervalo maior que `JANELA_DE_ONDA_SEC`, porque é
    assim que ela pareia. Com todos na mesma onda o desempate seria o gravado
    e o cenário ficaria indistinguível de um empate — que é outro caso.
    """
    reg = ControllerIdentityRegistry(clock=relogio)
    na_mesa: list[str] = []
    for uniq in UNIQS:
        na_mesa.append(uniq)
        reg.sync_connected(list(na_mesa))
        relogio.avancar(id_mod.JANELA_DE_ONDA_SEC * 2)
    return reg


def o_tique_viu_tres(reg: ControllerIdentityRegistry) -> None:
    """O batimento de 2 s: o terceiro piscou no rádio e saiu do `connected`.

    É o `_sync_identity_registry` do `lifecycle`, que filtra por
    `info.get("connected")` do `describe_controllers` — e o handle do que
    piscou CONTINUA aberto (o `connect()` só o recolhe em ≤30 s). É essa
    diferença entre "tem handle" e "está conectado" que abre a janela.
    """
    reg.sync_connected([PRIMEIRO, SEGUNDO, QUARTO])


def backend_com_os_quatro() -> PyDualSenseController:
    """Backend com os quatro handles abertos, na ordem da fila."""
    inst = PyDualSenseController(evdev_reader=_null_evdev())
    inst._handles = {key: _FakeHandle() for key in KEYS}  # type: ignore[assignment]
    inst._primary_key = KEYS[0]
    return inst


class DaemonDeMentira:
    """O mínimo que `_player_slot_for` consulta — só o registro."""

    def __init__(self, registry: ControllerIdentityRegistry) -> None:
        self.identity_registry = registry


def player_slot_publicado(reg: ControllerIdentityRegistry, uniq: str) -> int | None:
    """O que o daemon AFIRMA sobre `uniq` — o campo `player_slot` do IPC.

    Mesma consulta de `ipc_handlers.IpcHandlersMixin._player_slot_for`:
    `slot_for(assign=False)`, defensiva e só-leitura. É contra ISTO que o
    aceite do defeito 2 se escreve — nunca contra `/sys/class/leds`, que
    mostra o número do KERNEL (medido em 25/07).
    """
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    handlers = IpcHandlersMixin.__new__(IpcHandlersMixin)
    handlers.daemon = DaemonDeMentira(reg)  # type: ignore[attr-defined]
    return handlers._player_slot_for(uniq)


class TestOSegundoEscritorDeConnected:
    """Defeito 1 — uma consulta de cor não decide quem está na mesa."""

    def test_a_leitura_de_cor_nao_readmite_o_ausente(self, config_isolado: Path) -> None:
        """O ACEITE, literal: `slot_for` do provider não muda `_connected`."""
        reg = mesa_de_quatro(Relogio())
        provider = make_auto_output_provider(reg)
        o_tique_viu_tres(reg)
        antes = reg.snapshot_connected()

        for _ in range(LEITURAS_DE_OITO_SEGUNDOS):
            provider(QUE_PISCA)

        assert reg.snapshot_connected() == antes
        assert QUE_PISCA not in reg.snapshot_connected()

    def test_o_ausente_fica_sem_opiniao_em_vez_de_acender(
        self, config_isolado: Path
    ) -> None:
        """Ausente não acende número (contrato de `numero_da_lampada`, 27/08).

        `None` = sem opinião: o controle segue com o que já tinha até o
        próximo batimento, em vez de acender um número que outro está
        acendendo. Era isso que a autoadmissão tornava inalcançável.
        """
        reg = mesa_de_quatro(Relogio())
        provider = make_auto_output_provider(reg)
        o_tique_viu_tres(reg)

        assert provider(QUE_PISCA) is None
        # `assign=False` é a leitura pura; o default (`assign=True`) é do
        # TIQUE e continua podendo readmitir — é por ele que o link que volta
        # entra de novo na mesa.
        assert reg.numero_da_lampada(QUE_PISCA, assign=False) is None

    def test_a_leitura_nao_mexe_o_numero_dos_outros(
        self, config_isolado: Path
    ) -> None:
        """O sintoma dela: oito segundos de aba Status, zero mudança nos vivos.

        Antes da cura, a PRIMEIRA leitura já empurrava o quarto de 3 para 4 e
        a lightbar dele de verde para rosa.
        """
        reg = mesa_de_quatro(Relogio())
        provider = make_auto_output_provider(reg)
        o_tique_viu_tres(reg)
        esperado = {uniq: reg.numero_da_lampada(uniq) for uniq in VIVOS}
        assert esperado == {PRIMEIRO: 1, SEGUNDO: 2, QUARTO: 3}

        for _ in range(LEITURAS_DE_OITO_SEGUNDOS):
            provider(QUE_PISCA)
            for uniq in VIVOS:
                provider(uniq)
            assert {u: reg.numero_da_lampada(u) for u in VIVOS} == esperado

        saida = provider(QUARTO)
        assert saida is not None
        assert saida.led == player_slot_color(3)
        assert saida.player_leds == player_led_pattern(3)

    def test_a_aba_status_a_10_hz_nao_mexe_a_mesa(self, config_isolado: Path) -> None:
        """O caminho REAL da aba: `resolved_led_for`, pelo backend de verdade.

        `_lightbar_for_uniq` cai aqui quando o nó de sysfs do controle some —
        que é exatamente o que acontece com quem piscou no rádio.
        """
        reg = mesa_de_quatro(Relogio())
        inst = backend_com_os_quatro()
        inst.set_auto_output_provider(make_auto_output_provider(reg))
        o_tique_viu_tres(reg)
        antes = reg.snapshot_connected()
        cor_do_quarto = inst.resolved_led_for(QUARTO)

        for _ in range(LEITURAS_DE_OITO_SEGUNDOS):
            inst.resolved_led_for(QUE_PISCA)

        assert reg.snapshot_connected() == antes
        assert inst.resolved_led_for(QUARTO) == cor_do_quarto

    def test_o_tique_continua_sendo_o_dono(self, config_isolado: Path) -> None:
        """Tirar e pôr na mesa continua funcionando — pelo caminho certo."""
        reg = mesa_de_quatro(Relogio())
        provider = make_auto_output_provider(reg)
        o_tique_viu_tres(reg)
        assert provider(QUE_PISCA) is None

        reg.sync_connected(list(UNIQS))  # o link voltou e o tique viu

        saida = provider(QUE_PISCA)
        assert saida is not None
        assert saida.player_leds == player_led_pattern(3)  # D2: o número é dele
        assert reg.numero_da_lampada(QUARTO) == 4

    def test_a_estreia_ainda_entra_na_mesa(self, config_isolado: Path) -> None:
        """D1 continua de pé: quem ESTREIA nasce numerado no tique do hotplug.

        A cura separa dois atos que estavam colados. Apresentar um endereço
        que a casa nunca viu é identidade (R-14 §1) e continua acontecendo na
        primeira consulta; RESSUSCITAR quem o tique já declarou ausente é o
        que deixou de acontecer.
        """
        reg = ControllerIdentityRegistry(clock=Relogio())
        provider = make_auto_output_provider(reg)

        primeiro = provider(PRIMEIRO)
        assert primeiro is not None and primeiro.led == player_slot_color(1)
        segundo = provider(SEGUNDO)
        assert segundo is not None and segundo.led == player_slot_color(2)
        assert reg.snapshot_connected() == {PRIMEIRO, SEGUNDO}

    def test_o_vpad_continua_fora_de_tudo(self, config_isolado: Path) -> None:
        """D9: o MAC forjado do vpad nunca entra na mesa, com cura ou sem."""
        reg = mesa_de_quatro(Relogio())
        provider = make_auto_output_provider(reg)
        antes = reg.snapshot_connected()

        assert provider("02:fe:00:00:00:01") is None
        assert reg.snapshot_connected() == antes


class TestATempestadeDeStateFull:
    """A mordida do enunciado: 2 s e 10 Hz em threads CONCORRENTES.

    Um controle marcado `connected: False` pelo tique; o `state_full`
    resolvendo cor a 10 Hz do outro lado. A asserção é a do aceite: **o slot
    de cada MAC vivo é estável** — nem um instante em que a numeração deles
    dependa de quem leu por último.
    """

    def test_o_slot_de_cada_mac_vivo_e_estavel(self, config_isolado: Path) -> None:
        reg = mesa_de_quatro(Relogio())
        provider = make_auto_output_provider(reg)
        o_tique_viu_tres(reg)

        parar = threading.Event()
        vistos: dict[str, set[int | None]] = {uniq: set() for uniq in VIVOS}
        explodiu: list[BaseException] = []

        def o_tique() -> None:
            try:
                while not parar.is_set():
                    # O batimento continua substituindo o conjunto inteiro,
                    # sempre com o mesmo trio: quem piscou segue fora.
                    reg.sync_connected([PRIMEIRO, SEGUNDO, QUARTO])
            except BaseException as exc:  # a thread não pode morrer calada
                explodiu.append(exc)

        def a_aba_status() -> None:
            try:
                for _ in range(2000):
                    provider(QUE_PISCA)
                    for uniq in VIVOS:
                        provider(uniq)
                        vistos[uniq].add(reg.numero_da_lampada(uniq))
            except BaseException as exc:  # a thread não pode morrer calada
                explodiu.append(exc)
            finally:
                parar.set()

        threads = [
            threading.Thread(target=o_tique, daemon=True),
            threading.Thread(target=a_aba_status, daemon=True),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not explodiu, explodiu
        assert not any(t.is_alive() for t in threads)
        assert vistos == {PRIMEIRO: {1}, SEGUNDO: {2}, QUARTO: {3}}


class TestNenhumInstanteComDoisNoMesmoJogador:
    """Defeito 2 — o aceite contra o que o daemon AFIRMA, não contra o sysfs."""

    def test_o_player_slot_publicado_nunca_repete(self, config_isolado: Path) -> None:
        """Quatro entradas, oito segundos de aba: `player_slot` é injetor.

        É o campo que o `state_full` publica por controle, e é ele que a
        sprint manda medir — `/sys/class/leds` responde sobre o número do
        KERNEL e passaria com a colisão de pé.
        """
        reg = mesa_de_quatro(Relogio())
        provider = make_auto_output_provider(reg)
        o_tique_viu_tres(reg)

        for _ in range(LEITURAS_DE_OITO_SEGUNDOS):
            for uniq in UNIQS:
                provider(uniq)
            publicados = [player_slot_publicado(reg, uniq) for uniq in VIVOS]
            assert len(set(publicados)) == len(publicados), publicados

    def test_nenhum_instante_com_dois_padroes_iguais(
        self, config_isolado: Path
    ) -> None:
        """A queixa histórica: dois controles acesos como jogador 2.

        A camada automática resolve o padrão de player-LED de todos os quatro
        handles num LOTE (é a forma de `enviar_gatilho_da_cor` e do
        `reassert_resolved_outputs`). Nenhuma amostra pode ter duas chaves com
        o mesmo padrão — e `None` (sem opinião) não conta como padrão.
        """
        reg = mesa_de_quatro(Relogio())
        inst = backend_com_os_quatro()
        inst.set_auto_output_provider(make_auto_output_provider(reg))
        o_tique_viu_tres(reg)

        for _ in range(LEITURAS_DE_OITO_SEGUNDOS):
            lote = [
                inst._merged_desired_for_key(key).player_leds for key in inst._handles
            ]
            acesos = [p for p in lote if p is not None]
            assert len(set(acesos)) == len(acesos), lote

    def test_a_geometria_de_27_08_nao_colide_mais_por_construcao(
        self, config_isolado: Path
    ) -> None:
        """A cena do journal dela, e é a única que produz a colisão.

        Quem piscou tem de ser o **PRIMEIRO da fila** e resolver por
        **ÚLTIMO** no lote: os três primeiros são numerados com a mesa de
        três (1, 2, 3) e o quarto, ao ser resolvido, entraria na mesa e — por
        ser o primeiro da fila de chegada — sairia com o número 1. Dois
        "jogador 1", ninguém no 4, e assim ficava por 28 minutos, porque a
        lâmpada só é reescrita quando algo acontece.

        **MEDIDO nesta árvore em 06/09/2026** com o defeito 2 reintroduzido
        (o provider voltando a chamar `slot_for`, como antes de 27/08) E o
        `_assentar_mesa_locked` do backend neutralizado::

            AA:BB:CC:00:00:02  (F, F, T, F, F)   -> jogador 1
            AA:BB:CC:00:00:03  (F, T, F, T, F)   -> jogador 2
            AA:BB:CC:00:00:04  (T, F, T, F, T)   -> jogador 3
            AA:BB:CC:00:00:01  (F, F, T, F, F)   -> jogador 1   <- COLISÃO

        Com a cura de hoje a colisão é impossível **sem depender do
        assentamento**: uma leitura não move a mesa, então os quatro do lote
        leem a mesma tabela por construção, e quem o tique tem como ausente
        fica sem opinião em vez de tomar o número de um presente.
        """
        reg = mesa_de_quatro(Relogio())
        inst = backend_com_os_quatro()
        inst.set_auto_output_provider(make_auto_output_provider(reg))

        # O primeiro da fila caiu do rádio; o handle dele voltou ANTES do
        # próximo batimento, e por isso no FIM do dict de handles.
        reg.sync_connected(list(UNIQS[1:]))
        voltou = inst._handles.pop(KEYS[0])
        inst._handles[KEYS[0]] = voltou

        lote = {
            key: inst._merged_desired_for_key(key).player_leds
            for key in inst._handles
        }
        acesos = [p for p in lote.values() if p is not None]
        assert len(set(acesos)) == len(acesos), lote
        assert lote[KEYS[0]] is None  # ausente não toma número de presente

        reg.sync_connected(list(UNIQS))  # o tique viu o link de volta
        lote = {
            key: inst._merged_desired_for_key(key).player_leds
            for key in inst._handles
        }
        assert set(lote.values()) == {player_led_pattern(n) for n in (1, 2, 3, 4)}
        assert lote[KEYS[0]] == player_led_pattern(1)  # D2: o 1 é dele

    def test_com_o_tique_completo_a_mesa_fecha_1_a_4(
        self, config_isolado: Path
    ) -> None:
        """Não basta não repetir: com os quatro na mesa, o conjunto é 1..4."""
        reg = mesa_de_quatro(Relogio())
        inst = backend_com_os_quatro()
        inst.set_auto_output_provider(make_auto_output_provider(reg))

        lote = {
            key: inst._merged_desired_for_key(key).player_leds
            for key in inst._handles
        }
        assert set(lote.values()) == {player_led_pattern(n) for n in (1, 2, 3, 4)}
        assert [player_slot_publicado(reg, uniq) for uniq in UNIQS] == [1, 2, 3, 4]


class TestAReguaSabeRecusar:
    """A mordida da mordida: com a cura arrancada, tudo aqui REPROVA.

    O caminho pré-cura continua alcançável de propósito —
    `autoridade_de_presenca=True` é o default, porque é por ele que o tique e
    os rótulos passam. Chamá-lo do lugar do provider é reproduzir o defeito 1
    exatamente como ele estava, sem comentar linha nenhuma do produto.
    """

    @staticmethod
    def _provider_pre_cura(reg: ControllerIdentityRegistry):
        """O provider como era: `numero_da_lampada` COM autoridade de presença."""

        def provider(uniq: str) -> int | None:
            return reg.numero_da_lampada(uniq)  # o default readmite

        return provider

    def test_o_caminho_pre_cura_readmite_o_ausente(
        self, config_isolado: Path
    ) -> None:
        reg = mesa_de_quatro(Relogio())
        provider = self._provider_pre_cura(reg)
        o_tique_viu_tres(reg)
        assert QUE_PISCA not in reg.snapshot_connected()

        provider(QUE_PISCA)

        # A régua de cima reprovaria aqui — e é este o defeito medido.
        assert QUE_PISCA in reg.snapshot_connected()

    def test_o_caminho_pre_cura_mexe_o_numero_do_quarto(
        self, config_isolado: Path
    ) -> None:
        """O degrau medido: uma leitura, e o quarto vai de 3 para 4."""
        reg = mesa_de_quatro(Relogio())
        provider = self._provider_pre_cura(reg)
        o_tique_viu_tres(reg)
        assert reg.numero_da_lampada(QUARTO) == 3

        provider(QUE_PISCA)

        assert reg.numero_da_lampada(QUARTO) == 4
        assert player_slot_color(3) != player_slot_color(4)
