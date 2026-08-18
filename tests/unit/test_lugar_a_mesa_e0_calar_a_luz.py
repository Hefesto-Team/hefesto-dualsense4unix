"""E0 da LUGAR-À-MESA-01 — *"calar a luz até a entrega existir"*.

**DECISÃO DELA, 07/08/2026** (resposta 12 do painel,
`docs/process/2026-08-07-DECISOES-DELA-as-onze-respostas-do-painel.md`):
enquanto o controle externo **não for jogador de verdade dentro do jogo**, o
Hefesto **para de acender número de jogador nele**.

Ela sabia o preço e o aceitou: a casa tem registrado que *ela distingue os
controles pela COR da luz e pelo LED de jogador* (`app/actions/home_actions.py:13`).
Ela escolheu perder o próprio instrumento para o produto parar de afirmar o que
não cumpre. As opções "manter" e "manter com cor diferente" foram recusadas
explicitamente — não há meio termo a procurar aqui.

---

## O que este arquivo mede, e por que são DUAS baterias

**`TestCalarALuzAteAEntregaExistir`** mede o comportamento ENTREGUE: com o
interruptor no valor com que ele sai de fábrica (`False`), o tick faz **zero
escritas** de LED.

E mede, em teste próprio, **a escolha de desenho**: calar é *não escrever*, não
*apagar*. Os dois eram defensáveis, e o efeito no plástico é diferente:

- **não escrever** deixa o padrão que o firmware/kernel põe ali sozinho. O
  plástico fica EXATAMENTE como ficaria com o Hefesto desinstalado — e isso é
  falseável: pare o daemon e a luz não muda;
- **apagar** seria a nossa mão, no mesmo nó, dizendo *"este controle não tem
  jogador"* — que é outra afirmação, feita pelo produto, sob o critério dela de
  que *o produto não pode AFIRMAR jogador*. Na lightbar do 8BitDo em modo DS4
  seria pior: acesa é o sinal de "ligado", e apagá-la trocaria uma mentira por
  outra ("sem bateria").

`test_calar_e_nao_escrever_e_nao_apagar` é o teste que separa as duas: sob a
implementação "apagar" ele reprova.

**`TestACapacidadeNaoFoiEnterrada`** mede que o `core/external_leds.py`
continua inteiro, exportado e FUNCIONANDO, e que **o caminho de volta é uma
linha** — trocar `EXTERNAL_PLAYER_LED_ENABLED` para `True` devolve a luz no
mesmo tick, contra o mesmo sysfs. Um "calar" que apagasse o código custaria a
leva inteira para desfazer; este é o portão que impede isso.

Hermético: nenhum nó real é tocado. O sysfs de LED é uma árvore em `tmp_path`
(`LEDS_ROOT` monkeypatchado), a enumeração é dublê, e os endereços são da faixa
forjada `aa:bb:cc:*` — o portão de anonimato manda.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import evdev_reader as er_mod
from hefesto_dualsense4unix.core import external_leds as leds_mod
from hefesto_dualsense4unix.daemon.subsystems import external_identity as ei_mod
from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod
from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
    ExternalIdentityRegistry,
    ExternalLedSync,
)

#: Endereços da faixa FORJADA (check_test_data.sh). Nenhum aparelho real.
MAC_PRO = "aa:bb:cc:00:be:01"
MAC_8BITDO = "aa:bb:cc:00:be:02"

#: Instância HID sintética do Pro — só um prefixo de nome de nó no sysfs falso.
INST_PRO = "0003:AABB:CC01.0001"

BOOT = "boot-e0-calar-a-luz"


@pytest.fixture(autouse=True)
def _hermetico(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """config_dir em tmp + boot_id fixo (o registro grava no disco)."""
    from hefesto_dualsense4unix.utils import xdg_paths

    alvo = tmp_path / "config"

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    monkeypatch.setattr(ei_mod, "_read_boot_id", lambda: BOOT)
    monkeypatch.setattr(id_mod, "_read_boot_id", lambda: BOOT)


def _entry(uniq: str, hidraw: str, path: str) -> dict[str, Any]:
    """Uma linha do inventário de externos, no formato que o tick consome."""
    return {
        "name": "Pro Controller",
        "vid": "057e",
        "pid": "2009",
        "bus": "bluetooth",
        "uniq": uniq,
        "driver": "nintendo",
        "evdev_path": path,
        "hidraw": hidraw,
    }


def _mesa() -> list[dict[str, Any]]:
    """A mesa da queixa: um Pro Controller e um 8BitDo, os dois externos."""
    return [
        _entry(MAC_PRO, "/dev/hidraw7", "/dev/input/event261"),
        _entry(MAC_8BITDO, "/dev/hidraw2", "/dev/input/event262"),
    ]


def _sync(
    monkeypatch: pytest.MonkeyPatch,
    inventario: list[dict[str, Any]],
    *,
    ds_slots: dict[str, int] | None = None,
) -> ExternalLedSync:
    monkeypatch.setattr(
        er_mod, "discover_external_gamepads", lambda: [dict(e) for e in inventario]
    )
    daemon = SimpleNamespace(
        identity_registry=SimpleNamespace(snapshot=lambda: dict(ds_slots or {}))
    )
    return ExternalLedSync(daemon, ExternalIdentityRegistry())


# --- o sysfs de LED falso ----------------------------------------------------


def _barra_nintendo(raiz: Path, inst: str, acesos: tuple[int, ...]) -> None:
    """Cria a barra de player do hid-nintendo com ``acesos`` verdes ligados.

    É o hardware que a decisão dela cala: quatro verdes (``:green:player-1..4``)
    mais o azul do 5º (``:blue:player-5``, o bit "+5" do R-25).
    """
    for i in range(1, 5):
        no = raiz / f"{inst}:green:player-{i}" / "brightness"
        no.parent.mkdir(parents=True, exist_ok=True)
        no.write_text("1" if i in acesos else "0", encoding="ascii")
    azul = raiz / f"{inst}:blue:player-5" / "brightness"
    azul.parent.mkdir(parents=True, exist_ok=True)
    azul.write_text("0", encoding="ascii")


def _retrato(raiz: Path) -> dict[str, str]:
    """Todo ``brightness`` da árvore, por caminho relativo — a foto do plástico."""
    return {
        str(p.relative_to(raiz)): p.read_text(encoding="ascii")
        for p in sorted(raiz.rglob("brightness"))
    }


@pytest.fixture()
def sysfs_de_led(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """``LEDS_ROOT`` numa árvore de ``tmp_path``, com a barra do Pro montada.

    Estado inicial: **verdes 1 e 2 acesos** — o padrão que a medição de 06/08
    às 22h40 leu na barra do Pro Controller dela. O tick calado não pode
    encostar nele.
    """
    raiz = tmp_path / "leds"
    raiz.mkdir()
    _barra_nintendo(raiz, INST_PRO, acesos=(1, 2))
    monkeypatch.setattr(leds_mod, "LEDS_ROOT", str(raiz))
    # A resolução real leria `/sys/class/hidraw/...` da máquina; aqui o hidraw
    # do Pro resolve para a instância sintética e o resto do caminho
    # (`resolve_external_leds` -> glob -> `write_player_number`) roda de verdade.
    monkeypatch.setattr(
        leds_mod,
        "hid_instance_for_hidraw",
        lambda dev: INST_PRO if dev == "/dev/hidraw7" else None,
    )
    monkeypatch.setattr(leds_mod, "_hid_device_dir", lambda _dev: None)
    return raiz


@pytest.fixture()
def escritas_de_led(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int]]:
    """Espia `apply_player_number` SEM ligar o interruptor.

    Diferente da fixture homônima de `test_external_identity.py`, que liga a
    luz de propósito para seguir medindo a maquinaria: esta mede o produto
    **como ele é entregue**.
    """
    escritas: list[tuple[str, int]] = []
    monkeypatch.setattr(
        leds_mod,
        "apply_player_number",
        lambda hidraw, slot, *a, **k: (escritas.append((hidraw, slot)), True)[1],
    )
    return escritas


class _LoggerEspiao:
    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict[str, Any]]] = []

    def info(self, evento: str, **kw: Any) -> None:
        self.eventos.append((evento, kw))

    def debug(self, *_a: Any, **_kw: Any) -> None: ...

    def warning(self, *_a: Any, **_kw: Any) -> None: ...

    def error(self, *_a: Any, **_kw: Any) -> None: ...


# --- bateria 1: o comportamento ENTREGUE -------------------------------------


class TestCalarALuzAteAEntregaExistir:
    """Com o interruptor como sai de fábrica, o produto não afirma jogador."""

    def test_o_interruptor_e_entregue_desligado(self) -> None:
        """Portão anti-recaída: a luz volta com a ENTREGA, não com a vontade.

        Se alguém trocar `EXTERNAL_PLAYER_LED_ENABLED` para `True`, este teste
        reprova e obriga a leitura do motivo. A condição de volta é objetiva e
        está escrita na constante: a `E3` da LUGAR-À-MESA-01 — o externo virar
        jogador de verdade —, que ela autorizou só depois da `MASCARA-01`.
        Quando isso acontecer, este teste é atualizado **de propósito**, com a
        entrega na mão.
        """
        assert ei_mod.EXTERNAL_PLAYER_LED_ENABLED is False

    def test_tick_nao_acende_numero_em_externo_nenhum(
        self, monkeypatch: pytest.MonkeyPatch, escritas_de_led: list[tuple[str, int]]
    ) -> None:
        """A mesa da queixa (Pro + 8BitDo) atravessa dez ticks sem UMA escrita.

        Era daqui que saíam os `external_led_written slot=2` (Pro) e `slot=3`
        (8BitDo) do journal dela, com o `coop status` dizendo "1 jogador" no
        mesmo instante.
        """
        espiao = _LoggerEspiao()
        monkeypatch.setattr(ei_mod, "logger", espiao)
        sync = _sync(monkeypatch, _mesa(), ds_slots={"ds1": 1})

        for i in range(10):
            sync.tick(now=float(i * 10))

        assert escritas_de_led == []
        assert [ev for ev, _ in espiao.eventos if ev == "external_led_written"] == []

    def test_calar_e_nao_escrever_e_nao_apagar(
        self, monkeypatch: pytest.MonkeyPatch, sysfs_de_led: Path
    ) -> None:
        """A ESCOLHA de desenho, medida: o plástico fica byte a byte intocado.

        Sem dublê de `apply_player_number` — o caminho real (`resolve_external_leds`
        -> `write_player_number`) está armado contra o sysfs falso, então
        qualquer escrita apareceria aqui. O tick calado não escreve **nada**:
        nem o número, nem o zero.

        É este teste que separa as duas leituras de "calar". Sob a
        implementação "apagar" o retrato de depois viria com todos os nós em
        `0` e ele reprovaria — que é exatamente o ponto: apagar também é o
        produto falando sobre o jogador do controle.
        """
        antes = _retrato(sysfs_de_led)
        assert antes[f"{INST_PRO}:green:player-2/brightness"] == "1", (
            "a montagem do sysfs falso tem de começar com a barra ACESA, "
            "senão o teste não distingue 'não escrever' de 'apagar'"
        )

        sync = _sync(monkeypatch, _mesa())
        for i in range(3):
            sync.tick(now=float(i * 10))

        assert _retrato(sysfs_de_led) == antes

    def test_a_atribuicao_de_slot_continua_rodando(
        self, monkeypatch: pytest.MonkeyPatch, escritas_de_led: list[tuple[str, int]]
    ) -> None:
        """R-14: numerar é IDENTIDADE; o interruptor governa só a APARÊNCIA.

        O gate mora DEPOIS do `slot_for`, de propósito. Se subisse para antes,
        o externo pararia de receber lugar na fila — e a fila é o que a GUI, a
        CLI e o `coop status` leem para dizer quem está na mesa. Calar a luz
        não pode calar o registro.
        """
        sync = _sync(monkeypatch, _mesa())
        sync.tick(now=0.0)

        assert escritas_de_led == []
        # `snapshot()` é key -> LUGAR NA FILA (não o número exibido).
        fila = sync._registry.snapshot()
        assert fila.get(MAC_PRO.replace(":", "")) == 1
        assert fila.get(MAC_8BITDO.replace(":", "")) == 2

    def test_o_enable_imu_nao_foi_calado_junto(
        self, monkeypatch: pytest.MonkeyPatch, escritas_de_led: list[tuple[str, int]]
    ) -> None:
        """GYRO-02 não é "a luz" — e continua saindo no mesmo tick.

        O enable-IMU roda no `finally` do tick, e o gate da E0 é um `return`
        DENTRO do `try`. Se alguém puser o gate antes do `try` (ou trocar o
        `return` por um caminho que pule o `finally`), o Nintendo Pro real
        perde o giroscópio junto com a luz — um dano colateral que a decisão
        dela não pede.
        """
        imu: list[str] = []
        monkeypatch.setattr(
            leds_mod, "enable_imu", lambda dev, **kw: (imu.append(dev), True)[1]
        )
        monkeypatch.setattr(ei_mod, "NINTENDO_REAL_OUI", "aabbcc")
        sync = _sync(
            monkeypatch,
            [dict(_entry(MAC_PRO, "/dev/hidraw7", "/dev/input/event261"), bus="usb")],
        )

        sync.tick(now=0.0)

        assert escritas_de_led == []
        assert imu == ["/dev/hidraw7"], "calar a luz não pode calar a IMU"


# --- bateria 2: a capacidade continua lá, viva, esperando a entrega ----------


class TestACapacidadeNaoFoiEnterrada:
    """Calar é desligar o CHAMADOR. O que acende a luz continua inteiro."""

    def test_as_funcoes_que_acendem_continuam_exportadas(self) -> None:
        """As três seguem no módulo E no `__all__` — API pública, não resto.

        Se a E0 tivesse apagado o código, desfazer custaria a leva inteira:
        `write_player_number` carrega a cura MEDIDA do R-25 (o azul como bit
        "+5", que impediu o slot 7 de acender o mesmo padrão do 4), e
        `write_lightbar_slot` carrega a paleta do slot. Nada disso se
        reescreve de memória.
        """
        for nome in ("write_player_number", "write_lightbar_slot", "apply_player_number"):
            assert callable(getattr(leds_mod, nome, None)), f"{nome} sumiu do módulo"
            assert nome in leds_mod.__all__, f"{nome} saiu do __all__"

    def test_write_player_number_continua_acendendo_o_padrao_do_r25(
        self, tmp_path: Path
    ) -> None:
        """Chamada direta: o slot 7 ainda é "azul + 2 verdes", não "4 verdes"."""
        raiz = tmp_path / "leds"
        raiz.mkdir()
        _barra_nintendo(raiz, INST_PRO, acesos=())

        assert leds_mod.write_player_number(INST_PRO, 7, str(raiz)) is True

        assert _retrato(raiz) == {
            f"{INST_PRO}:green:player-1/brightness": "1",
            f"{INST_PRO}:green:player-2/brightness": "1",
            f"{INST_PRO}:green:player-3/brightness": "0",
            f"{INST_PRO}:green:player-4/brightness": "0",
            f"{INST_PRO}:blue:player-5/brightness": "1",
        }

    def test_write_lightbar_slot_continua_pintando_a_cor_do_slot(
        self, tmp_path: Path
    ) -> None:
        """Chamada direta: a lightbar do 8BitDo em modo DS4 ainda sabe a cor."""
        from hefesto_dualsense4unix.core.led_control import player_slot_color

        raiz = tmp_path / "leds"
        for canal in ("red", "green", "blue", "global"):
            no = raiz / f"input99:{canal}" / "brightness"
            no.parent.mkdir(parents=True, exist_ok=True)
            no.write_text("0", encoding="ascii")

        assert leds_mod.write_lightbar_slot("input99", 2, str(raiz)) is True

        r, g, b = player_slot_color(2)
        lido = _retrato(raiz)
        assert (
            lido["input99:red/brightness"],
            lido["input99:green/brightness"],
            lido["input99:blue/brightness"],
        ) == (str(r), str(g), str(b))
        assert lido["input99:global/brightness"] == "1"

    def test_uma_linha_devolve_a_luz_no_mesmo_tick(
        self, monkeypatch: pytest.MonkeyPatch, sysfs_de_led: Path
    ) -> None:
        """O caminho de volta, medido de ponta a ponta.

        MESMA mesa, MESMO sysfs falso do teste que prova o silêncio — muda só
        o interruptor. A barra do Pro **sai** do padrão de entrada (verdes 1 e
        2) e passa a exibir a posição que o registro atribuiu, pelo caminho
        real (`apply_player_number` -> `resolve_external_leds` ->
        `write_player_number`). O retrato de depois é DIFERENTE do de antes de
        propósito: se fossem iguais, o teste passaria mesmo sem escrita nenhuma
        e não provaria nada.

        É isto que "não enterrar a capacidade" quer dizer: quando a `E3`
        existir, a luz volta trocando uma constante — nenhum código a
        reescrever.
        """
        monkeypatch.setattr(ei_mod, "EXTERNAL_PLAYER_LED_ENABLED", True)
        sync = _sync(monkeypatch, _mesa())

        sync.tick(now=0.0)

        # Sem DualSense na mesa, o Pro é o primeiro presente -> posição 1.
        assert _retrato(sysfs_de_led) == {
            f"{INST_PRO}:green:player-1/brightness": "1",
            f"{INST_PRO}:green:player-2/brightness": "0",
            f"{INST_PRO}:green:player-3/brightness": "0",
            f"{INST_PRO}:green:player-4/brightness": "0",
            f"{INST_PRO}:blue:player-5/brightness": "0",
        }
