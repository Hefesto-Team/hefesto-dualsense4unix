"""O-BRILHO-DAS-LUZES-DE-NUMERO-01 — Fraco, Médio e Forte, do disco dela ao BIT.

A DECISÃO É DELA, 24/09/2026 (`D-2409-AS-LUZES-DE-NUMERO-TEM-TRES-BRILHOS`):
*"Fraco, Médio e Forte na linha LEDs, nascendo no Fraco"*. A razão que ela
escolheu: quem enxerga pouco não tinha como aumentar, e quem se incomoda com
luz não tinha como escolher.

O QUE O APARELHO FAZ JÁ ESTAVA MEDIDO (BRILHO-DE-HARDWARE-01, 09/09/2026, o
olho dela, os dois transportes): o `common[42]` muda as cinco lâmpadas de
numeração em três degraus (0 alto · 1 médio · 2 baixo), e SÓ com o `flag2` bit0
(`SET_PLAYER_LED_BRIGHTNESS`) ligado. O que esta régua prova é o PRODUTO: que o
report que ele monta para cada controle leva o bit e o degrau certos.

A RÉGUA PERGUNTA AO APARELHO DE MENTIRA, E NÃO AO TEXTO DO CÓDIGO. O controle é
um `_PinnedPyDualSense` nascido pelo `__init__` de produção, sem device, com o
`_escrever_conferindo` trocado por um fio que só GUARDA o quadro que sairia. O
que se lê é o quadro inteiro — o envelope (`0x02` do cabo, `0x31` do rádio),
o `flag2` e o `common[42]` — e, no cabo sem nó de LED, o fluxo que o
`report_thread` mandaria (`_build_common`). O nó de LED do kernel é um dublê
que guarda o número: ele é 0/1 por lâmpada e não carrega brilho nenhum.

A MATRIZ (a regra dela: nunca só um modo, uma rota, um transporte ou o P1):

* P1 a P4 na mesma mesa;
* USB e BT;
* com o nó de LED do kernel (o produto instalado) e sem ele;
* «Todos» (a seção global do perfil) e um controle só (o override dele, e o
  clique na coluna dele);
* o controle que chega DEPOIS do perfil aplicado (o hotplug).

AS MORDIDAS, arrancadas e devolvidas com md5 (a lista está no relatório da
sprint): tire o `brilho_das_luzes=` do `_pintar_por_hidraw_bt` no
`_write_partial_output` e o rádio reprova; tire o `_levar_o_brilho_das_luzes`
do `_write_partial_output` e o cabo reprova; tire o campo do `_OUTPUT_FIELDS`
e o merge o perde — o hotplug e o override reprovam; tire o
`player_led_brightness=` do `apply_output_defaults` do manager e o «Todos»
reprova.

O LAR É DE MENTIRA: o `conftest` desvia o `HOME` e os `XDG_*`, e o gesto grava
o perfil de verdade dentro dele.
"""
from __future__ import annotations

import pathlib
import sys
import typing
from typing import Any

import pytest

#: O PACOTE DA ABA MORA EM `interface/`, e é por lá que as réguas da 04 o
#: importam (`from pacotes import …`). Um segundo caminho de import faria o
#: `@gesto` registrar o mesmo botão duas vezes.
RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"), str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.core.controller import OutputSpec
from hefesto_dualsense4unix.core.led_control import (
    BRILHO_DAS_LUZES_PADRAO,
    BRILHOS_DAS_LUZES,
    degrau_do_brilho_das_luzes,
    player_led_pattern,
)

#: O degrau do firmware, invertido — 0 é o forte.
FORTE, MEDIO, FRACO = 0, 1, 2
BIT = rep.VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE

#: Quatro controles na mesa, P1 a P4 (endereços da faixa forjada da casa).
MACS = [f"AA:BB:CC:00:00:0{n}" for n in (1, 2, 3, 4)]
UNIQS = [m.replace(":", "").lower() for m in MACS]


class _NoDeLed:
    """A classe LED do kernel (a regra 77 instalada): guarda o número, e só."""

    def __init__(self) -> None:
        self.numeros: list[tuple[bool, ...]] = []
        self.indicator_dir = "/sys/class/leds/de-mentira"

    def writable(self) -> bool:
        return True

    def set_rgb(self, *_rgb: int, **_kw: Any) -> bool:
        return True

    def set_players(self, bits: tuple[bool, ...], **_kw: Any) -> bool:
        self.numeros.append(tuple(bits))
        return True

    def set_players_verified(self, bits: tuple[bool, ...]) -> bool:
        return self.set_players(bits)

    def invalidate_cache(self) -> None:
        return None


def _controle(transporte: str) -> Any:
    """O aparelho de mentira: o handle de produção com o fio trocado."""
    from pydualsense.enums import ConnectionType
    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

    h = bp._PinnedPyDualSense(b"/dev/hidraw-de-mentira", is_edge=False)
    h.audio, h.light = DSAudio(), DSLight()
    h.triggerL, h.triggerR = DSTrigger(), DSTrigger()
    h.conType = ConnectionType.BT if transporte == "bt" else ConnectionType.USB
    h.connected = True  # o que o `describe_controllers` lê para o «Todos» do IPC
    h.quadros = []
    h._escrever_conferindo = lambda quadro: h.quadros.append(bytes(quadro)) or len(quadro)
    return h


def _common(quadro: bytes) -> bytes:
    """O `common` de 47 bytes dentro do envelope de cada transporte."""
    inicio = 3 if quadro[0] == rep.BT_REPORT_ID else 1
    return quadro[inicio:inicio + rep.COMMON_LEN]


def _brilhos_no_fio(h: Any) -> list[int]:
    """Os degraus que SAÍRAM autorizados pelo bit, na ordem, deste controle."""
    return [c[42] for c in map(_common, h.quadros) if c[rep.COMMON_VALID_FLAG2] & BIT]


def _o_aparelho_fica_em(h: Any) -> int | None:
    """O degrau em que o firmware fica: o último autorizado que chegou a ele.

    Pelo fio avulso (o `0x02`/`0x31` que o Hefesto escreve) ou, no cabo sem nó
    de LED, pelo fluxo do `report_thread`. O firmware guarda o último degrau
    autorizado — um quadro sem o bit não o desfaz (medido em 09/09/2026).
    """
    fio = _brilhos_no_fio(h)
    fluxo = h._build_common(rumble_asserted=False)
    if not getattr(h, "_suppress_leds", True) and fluxo[rep.COMMON_VALID_FLAG2] & BIT:
        return fluxo[42]
    return fio[-1] if fio else None


def _numero(uniq: str) -> bp._DesiredOutput:
    """A camada automática: o número de cada um é a posição dele na mesa."""
    return bp._DesiredOutput(player_leds=player_led_pattern(UNIQS.index(uniq) + 1))


def _mesa(transporte: str, *, com_no: bool, quantos: int = 4) -> tuple[Any, list[Any]]:
    ctl = bp.PyDualSenseController()
    controles = [_controle(transporte) for _ in range(quantos)]
    ctl._handles = dict(zip(MACS, controles, strict=False))
    if com_no:
        ctl._sysfs = {mac: _NoDeLed() for mac in MACS[:quantos]}
    # A política de `_refresh_sysfs_leds`: o fluxo fica LED-neutro quando o
    # kernel é dono do nó, e no rádio sempre.
    for h in controles:
        h._suppress_leds = com_no or transporte == "bt"
    ctl.set_auto_output_provider(_numero)
    return ctl, controles


def _perfil(global_: str | None, **por_controle: str) -> Any:
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        LedsConfig,
        MatchAny,
        Profile,
    )

    leds = LedsConfig() if global_ is None else LedsConfig(player_led_brightness=global_)
    return Profile(
        name="Régua do brilho das luzes", match=MatchAny(), priority=1, leds=leds,
        controllers={
            UNIQS[int(p[1]) - 1]: ControllerOverrides(
                leds=LedsConfig(player_led_brightness=palavra))
            for p, palavra in por_controle.items()
        },
    )


def _aplicar(ctl: Any, perfil: Any) -> None:
    from hefesto_dualsense4unix.profiles.manager import ProfileManager

    ProfileManager(controller=ctl).apply(perfil, origin="manual")


MATRIZ = [
    pytest.param("usb", True, id="usb-com-no"),
    pytest.param("usb", False, id="usb-sem-no"),
    pytest.param("bt", True, id="bt-com-no"),
    pytest.param("bt", False, id="bt-sem-no"),
]


# ---------------------------------------------------------------------------
# 1. As três palavras têm UM dono
# ---------------------------------------------------------------------------
def test_as_tres_palavras_tem_um_dono_so() -> None:
    """O esquema, o degrau do firmware e a tela falam as MESMAS três palavras.

    O `Literal` do esquema e a tabela `BRILHOS_DAS_LUZES` são duas declarações
    — a do disco e a do aparelho —, e esta régua as trava juntas: uma palavra
    nova num lado só seria uma pílula que grava e não acende, ou que acende e
    o disco recusa.
    """
    from pacotes import a04_iluminacao as a04

    from hefesto_dualsense4unix.profiles.schema import LedsConfig

    campo = LedsConfig.model_fields["player_led_brightness"]
    assert typing.get_args(campo.annotation) == tuple(BRILHOS_DAS_LUZES)
    assert campo.default == BRILHO_DAS_LUZES_PADRAO == "fraco", (
        "todo perfil e todo controle nascem no Fraco — é a decisão dela")
    esperado = {"fraco": FRACO, "medio": MEDIO, "forte": FORTE}  # noqa-acento: chave ASCII
    assert esperado == BRILHOS_DAS_LUZES, (
        "o degrau do firmware é invertido: 0 é o forte e 2 o fraco (medido em "
        "09/09/2026)")
    assert degrau_do_brilho_das_luzes(None) == FRACO
    with pytest.raises(ValueError):
        degrau_do_brilho_das_luzes("máximo")
    assert set(a04.ROTULO_DO_BRILHO_DAS_LUZES) == set(BRILHOS_DAS_LUZES)
    assert list(a04.ROTULO_DO_BRILHO_DAS_LUZES.values()) == ["Fraco", "Médio", "Forte"]


def test_o_controle_nasce_no_fraco_com_o_bit() -> None:
    """Antes de qualquer perfil, o fluxo do cabo sem nó já leva o Fraco AUTORIZADO.

    É o de antes da decisão (o degrau baixo que a pydualsense mandava), agora
    com dono: o `_brilho_das_luzes` do handle, e não o `ledOption` herdado.
    """
    h = _controle("usb")
    h._suppress_leds = False
    c = h._build_common(rumble_asserted=False)
    assert c[rep.COMMON_VALID_FLAG2] & BIT and c[42] == FRACO


# ---------------------------------------------------------------------------
# 2. O report montado leva o bit e o degrau, nos quatro caminhos
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(("transporte", "com_no"), MATRIZ)
def test_o_todos_do_perfil_chega_ao_bit_de_p1_a_p4(transporte: str, com_no: bool) -> None:
    """«Todos»: a seção global do perfil acende o mesmo degrau nos quatro."""
    ctl, controles = _mesa(transporte, com_no=com_no)
    _aplicar(ctl, _perfil("forte"))
    for n, h in enumerate(controles, start=1):
        assert _o_aparelho_fica_em(h) == FORTE, (
            f"[{transporte}, {'com' if com_no else 'sem'} nó] o P{n} ficou em "
            f"{_o_aparelho_fica_em(h)} depois do «Todos» no Forte — o report "
            f"montado não levou o bit e o degrau")


@pytest.mark.parametrize(("transporte", "com_no"), MATRIZ)
def test_o_override_de_um_controle_so_muda_so_ele(transporte: str, com_no: bool) -> None:
    """Um controle só: o override do P3 no perfil vence o global SÓ no P3."""
    ctl, controles = _mesa(transporte, com_no=com_no)
    _aplicar(ctl, _perfil("medio", P3="forte"))  # noqa-acento: chave ASCII
    fica = [_o_aparelho_fica_em(h) for h in controles]
    assert fica == [MEDIO, MEDIO, FORTE, MEDIO], (
        f"[{transporte}, {'com' if com_no else 'sem'} nó] os quatro ficaram em "
        f"{fica}; o P3 tem override Forte e os outros seguem o Médio global")


@pytest.mark.parametrize(("transporte", "com_no"), MATRIZ)
def test_o_perfil_sem_o_campo_nasce_no_fraco(transporte: str, com_no: bool) -> None:
    """O perfil antigo (sem o campo) acende o Fraco — e autorizado, nos quatro."""
    ctl, controles = _mesa(transporte, com_no=com_no)
    _aplicar(ctl, _perfil(None))
    assert [_o_aparelho_fica_em(h) for h in controles] == [FRACO] * 4


@pytest.mark.parametrize(("transporte", "com_no"), MATRIZ)
def test_o_clique_no_p3_so_manda_no_p3(transporte: str, com_no: bool) -> None:
    """A pílula «Forte» da coluna do P3: a porta da usuária, SÓ naquele MAC.

    É a mesma porta do IPC `led.player_brightness_set` com `uniq`
    (`_apply_por_uniq` → `apply_output_for`). Os outros três não recebem um
    quadro sequer — um clique numa coluna não pode acender a de outro.
    """
    ctl, controles = _mesa(transporte, com_no=com_no)
    _aplicar(ctl, _perfil(None))
    antes = [len(h.quadros) for h in controles]
    fluxo_antes = [bytes(h._build_common(rumble_asserted=False)) for h in controles]
    assert ctl.apply_output_for(UNIQS[2], OutputSpec(player_led_brightness=FORTE)) \
        == "escreveu"
    assert _o_aparelho_fica_em(controles[2]) == FORTE
    for n in (0, 1, 3):
        h = controles[n]
        assert len(h.quadros) == antes[n], (
            f"o clique no P3 escreveu no P{n + 1}")
        assert bytes(h._build_common(rumble_asserted=False)) == fluxo_antes[n], (
            f"o clique no P3 mudou o fluxo do P{n + 1}")
        assert _o_aparelho_fica_em(h) == FRACO


@pytest.mark.parametrize(("transporte", "com_no"), MATRIZ)
def test_o_controle_que_chega_depois_recebe_o_brilho_dele(
        transporte: str, com_no: bool) -> None:
    """O perfil foi aplicado com três na mesa; o P4 chega depois, pelo hotplug.

    O override do P4 estava REGISTRADO no mapa em memória (o perfil publica os
    desconectados também), e o `_reapply_desired` do hotplug o leva ao aparelho
    — sem caminho próprio, porque o campo anda pelas camadas do número.
    """
    ctl, controles = _mesa(transporte, com_no=com_no, quantos=3)
    _aplicar(ctl, _perfil("medio", P4="forte"))  # noqa-acento: chave ASCII
    chegou = _controle(transporte)
    chegou._suppress_leds = com_no or transporte == "bt"
    ctl._handles[MACS[3]] = chegou
    if com_no:
        ctl._sysfs[MACS[3]] = _NoDeLed()
    ctl._reapply_desired(MACS[3], chegou)
    assert _o_aparelho_fica_em(chegou) == FORTE, (
        f"[{transporte}, {'com' if com_no else 'sem'} nó] o P4 que chegou depois "
        f"ficou em {_o_aparelho_fica_em(chegou)}, e o override dele é o Forte")
    assert [_o_aparelho_fica_em(h) for h in controles] == [MEDIO] * 3


@pytest.mark.parametrize("origem", ["manual", "auto"])
@pytest.mark.parametrize(("transporte", "com_no"), MATRIZ)
def test_a_troca_de_perfil_solta_o_brilho_do_perfil_anterior(
        transporte: str, com_no: bool, origem: str) -> None:
    """O perfil A dá Forte ao P2; o B não fala dele. Depois da troca, o P2 é Fraco.

    Achado da conferência de 25/09/2026: o «Todos» do `apply_output_defaults`
    mandava o RESOLVIDO de cada controle, e na ativação o manager o chama ANTES
    de publicar a camada do perfil novo — o merge ainda levava o override do A.
    No rádio e no cabo sem nó nada o repintava depois, e o P2 ficava no Forte
    sob um perfil que diz Fraco. Vale para a troca manual e para a automática.

    MORDIDA: volte o `apply_output_defaults` a mandar o
    `_merged_desired_for_key(key).player_led_brightness` — reprova no rádio (com
    e sem nó) e no cabo sem nó, nas duas origens.
    """
    from hefesto_dualsense4unix.profiles.manager import ProfileManager

    ctl, controles = _mesa(transporte, com_no=com_no)
    gerente = ProfileManager(controller=ctl)
    gerente.apply(_perfil("fraco", P2="forte"), origin=origem)
    assert [_o_aparelho_fica_em(h) for h in controles] == [FRACO, FORTE, FRACO, FRACO]
    gerente.apply(_perfil("fraco"), origin=origem)
    fica = [_o_aparelho_fica_em(h) for h in controles]
    assert fica == [FRACO] * 4, (
        f"[{transporte}, {'com' if com_no else 'sem'} nó, troca {origem}] os "
        f"quatro ficaram em {fica}: o P2 guardou o Forte do perfil anterior")



# ---------------------------------------------------------------------------
# 2b. Os caminhos que REPINTAM o número também levam o brilho
# ---------------------------------------------------------------------------
def _brilhos_novos(h: Any, desde: int) -> list[int]:
    """Os degraus autorizados pelo bit nos quadros que saíram depois de `desde`."""
    return [c[42] for c in map(_common, h.quadros[desde:])
            if c[rep.COMMON_VALID_FLAG2] & BIT]


@pytest.mark.parametrize(("transporte", "com_no"), MATRIZ)
def test_a_vigia_do_sequestro_devolve_o_brilho_so_de_quem_foi_sequestrado(
        transporte: str, com_no: bool) -> None:
    """A vigia do sequestro repinta o número do P3 — e o brilho dele volta junto.

    Achado da conferência de 25/09/2026: o relatório dizia que o brilho anda
    pela vigia (`reafirmar_barra_e_numero`), e nenhuma régua a cobria —
    arrancar o `_levar_o_brilho_das_luzes` dela passava verde. Quem sequestra o
    hidraw pode escrever o próprio degrau; a vigia devolve o dela, e só ao
    controle sequestrado.

    MORDIDA: tire o `_levar_o_brilho_das_luzes` da vigia (o cabo) ou o
    `brilho_das_luzes=brilho` do `_escrever_barra_e_numero_bt` (o rádio).
    """
    ctl, controles = _mesa(transporte, com_no=com_no)
    _aplicar(ctl, _perfil("medio", P3="forte"))  # noqa-acento: chave ASCII
    antes = [len(h.quadros) for h in controles]
    ctl.reafirmar_barra_e_numero([UNIQS[2]])
    assert _brilhos_novos(controles[2], antes[2]) == [FORTE], (
        f"[{transporte}, {'com' if com_no else 'sem'} nó] a vigia repintou o P3 "
        f"com os degraus {_brilhos_novos(controles[2], antes[2])}")
    for n in (0, 1, 3):
        assert len(controles[n].quadros) == antes[n], (
            f"a vigia do P3 escreveu no P{n + 1}")


@pytest.mark.parametrize("com_no", [True, False])
def test_o_gatilho_da_cor_pelo_radio_leva_o_brilho_de_cada_um(com_no: bool) -> None:
    """O gatilho do fim da rajada repinta os quatro do rádio num quadro só cada.

    MORDIDA: tire o `brilho_das_luzes=brilho` do `_escrever_barra_e_numero_bt`
    e os quatro saem sem o bit.
    """
    ctl, controles = _mesa("bt", com_no=com_no)
    _aplicar(ctl, _perfil("medio", P3="forte"))  # noqa-acento: chave ASCII
    antes = [len(h.quadros) for h in controles]
    ctl.reescrever_lightbar_por_hidraw()
    for n, h in enumerate(controles):
        assert len(h.quadros) - antes[n] == 1, (
            f"o gatilho escreveu {len(h.quadros) - antes[n]} quadros no P{n + 1}")
        assert _brilhos_novos(h, antes[n]) == [FORTE if n == 2 else MEDIO], (
            f"o gatilho levou ao P{n + 1} os degraus {_brilhos_novos(h, antes[n])}")


def test_o_reassert_leva_o_brilho_pelo_cabo_e_nao_gasta_quadro_no_radio() -> None:
    """O reassert da ativação: pelo cabo, o `0x02` do brilho; pelo rádio, nada.

    Pelo cabo a classe LED do kernel não carrega o degrau, e o reassert o manda
    num `0x02` ao lado. Pelo rádio o degrau já foi no `0x31` de cada escrita do
    número, e o reassert — que é só a classe LED — não gasta fatia.

    MORDIDA: tire o laço `do_cabo` do `reassert_resolved_outputs` e o cabo
    reprova.
    """
    ctl, cabo = _mesa("usb", com_no=True)
    _aplicar(ctl, _perfil("medio", P3="forte"))  # noqa-acento: chave ASCII
    antes = [len(h.quadros) for h in cabo]
    ctl.reassert_resolved_outputs()
    assert [_brilhos_novos(h, antes[n]) for n, h in enumerate(cabo)] == [
        [MEDIO], [MEDIO], [FORTE], [MEDIO]]

    ctl, radio = _mesa("bt", com_no=True)
    _aplicar(ctl, _perfil("medio", P3="forte"))  # noqa-acento: chave ASCII
    antes = [len(h.quadros) for h in radio]
    ctl.reassert_resolved_outputs()
    assert [len(h.quadros) for h in radio] == antes, (
        "o reassert gastou quadro no rádio — o brilho já foi com o número")

# ---------------------------------------------------------------------------
# 3. O IPC: com `uniq` só ele; sem, «Todos»
# ---------------------------------------------------------------------------
def _servidor(ctl: Any, tmp_path: pathlib.Path) -> Any:
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.manager import ProfileManager

    store = StateStore()
    return IpcServer(controller=ctl, store=store,
                     profile_manager=ProfileManager(controller=ctl, store=store),
                     socket_path=tmp_path / "brilho.sock")


@pytest.mark.asyncio
@pytest.mark.parametrize(("transporte", "com_no"), MATRIZ)
async def test_o_ipc_com_uniq_manda_so_no_controle_dele(
        transporte: str, com_no: bool, tmp_path: pathlib.Path) -> None:
    """`led.player_brightness_set` com `uniq`: o P3, e ninguém mais."""
    ctl, controles = _mesa(transporte, com_no=com_no)
    _aplicar(ctl, _perfil(None))
    antes = [len(h.quadros) for h in controles]
    resposta = await _servidor(ctl, tmp_path)._handle_led_player_brightness_set(
        {"brilho": "forte", "uniq": MACS[2]})
    assert resposta["aplicado_em"] == [MACS[2]] and resposta["guardado_em"] == []
    assert _o_aparelho_fica_em(controles[2]) == FORTE
    for n in (0, 1, 3):
        assert len(controles[n].quadros) == antes[n], f"o IPC do P3 escreveu no P{n + 1}"


@pytest.mark.asyncio
@pytest.mark.parametrize(("transporte", "com_no"), MATRIZ)
async def test_o_ipc_sem_uniq_e_o_todos_e_vence_o_override(
        transporte: str, com_no: bool, tmp_path: pathlib.Path) -> None:
    """«Todos» pelo IPC: os quatro, inclusive o que tinha override no perfil.

    E o padrão fica para quem chegar depois (o `_desired_default`).
    """
    ctl, controles = _mesa(transporte, com_no=com_no)
    _aplicar(ctl, _perfil("fraco", P2="forte"))
    resposta = await _servidor(ctl, tmp_path)._handle_led_player_brightness_set(
        {"brilho": "medio"})  # noqa-acento: chave ASCII
    assert sorted(resposta["aplicado_em"]) == sorted(UNIQS)
    assert [_o_aparelho_fica_em(h) for h in controles] == [MEDIO] * 4
    assert ctl._desired_default.player_led_brightness == MEDIO


@pytest.mark.asyncio
async def test_o_ipc_recusa_a_palavra_que_nao_existe(tmp_path: pathlib.Path) -> None:
    """Uma palavra fora das três é recusada DIZENDO quais são — nada sai."""
    ctl, controles = _mesa("usb", com_no=True, quantos=1)
    with pytest.raises(ValueError, match="fraco, medio, forte"):  # noqa-acento: chave ASCII
        await _servidor(ctl, tmp_path)._handle_led_player_brightness_set(
            {"brilho": "máximo", "uniq": MACS[0]})
    assert controles[0].quadros == []


# ---------------------------------------------------------------------------
# 4. O que o quadro NÃO pode levar
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_o_quadro_do_brilho_nao_reengata_a_barra(transporte: str) -> None:
    """O bit0 sai; o 0x02 do `flag2` e o 0x08 do `flag1` não saem nunca.

    `LIGHTBAR-BT-KEEPALIVE-01` (22/07) mediu que o SETUP da lightbar em regime
    trava a exibição; `LIGHTBAR-BT-CULPADO-01` (03/08) pegou o `RELEASE_LEDS`.
    O quadro do brilho não pede vibração, gatilho nem áudio.
    """
    ctl, controles = _mesa(transporte, com_no=True, quantos=1)
    _aplicar(ctl, _perfil("forte"))
    com_brilho = [c for c in map(_common, controles[0].quadros)
                  if c[rep.COMMON_VALID_FLAG2] & BIT]
    assert com_brilho, "nenhum quadro levou o brilho"
    for c in com_brilho:
        assert c[rep.COMMON_VALID_FLAG2] == BIT, (
            f"o `flag2` do quadro do brilho saiu {c[rep.COMMON_VALID_FLAG2]:#04x} — "
            f"só o bit0 pode sair")
        assert c[1] & rep.VALID_FLAG1_RELEASE_LEDS == 0
        assert c[0] == 0, "o quadro do brilho pediu vibração, gatilho ou áudio"


def test_pelo_radio_o_brilho_vai_no_mesmo_quadro_do_numero() -> None:
    """Cada report pelo rádio custa duas fatias: o brilho não ganha quadro próprio.

    No hotplug o número e o brilho saem JUNTOS, num `0x31` só.
    """
    ctl, controles = _mesa("bt", com_no=True, quantos=1)
    _aplicar(ctl, _perfil("forte"))
    h = controles[0]
    antes = len(h.quadros)
    ctl._reapply_desired(MACS[0], h)
    novos = [_common(q) for q in h.quadros[antes:]]
    assert len(novos) == 1, f"o hotplug pelo rádio escreveu {len(novos)} quadros"
    c = novos[0]
    assert c[1] & rep.VALID_FLAG1_PLAYER_INDICATOR_CONTROL_ENABLE
    assert c[rep.COMMON_VALID_FLAG2] & BIT and c[42] == FORTE


# ---------------------------------------------------------------------------
# 5. A tela: o clique grava no perfil e manda só naquele controle
# ---------------------------------------------------------------------------
class _PonteDeMentira:
    """A ponte com os mesmos nomes da de verdade, que só anota."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def player_led_brightness_set_detalhado(self, brilho: str, uniq: str | None = None
                                            ) -> dict[str, Any]:
        self.chamadas.append(("player_led_brightness_set_detalhado", (brilho,),
                              {"uniq": uniq}))
        return {"status": "ok", "brilho": brilho, "aplicado_em": [uniq],
                "guardado_em": []}


def test_o_clique_em_forte_no_p3_grava_so_o_p3_e_chama_so_o_p3() -> None:
    """A pílula «Forte» do P3: o disco dela recebe o Forte SÓ no override do P3.

    E a ponte é chamada uma vez, com a palavra e o MAC do P3 — é o que o
    daemon de mentira da prova de tela anota como `led.player_brightness_set`.
    """
    import json

    import pacotes
    from pacotes import a04_iluminacao as a04

    from hefesto_dualsense4unix.profiles.loader import save_profile

    arquivo = save_profile(_perfil(None), origem="regua")
    nome = "Régua do brilho das luzes"
    ctx = pacotes.Contexto(state={"active_profile": nome}, mesa=[])
    ponte = _PonteDeMentira()
    a04.brilho_luzes(ctx, {"uniq": MACS[2], "controle": "p3", "luzes": "forte"}, ponte)

    assert ponte.chamadas == [("player_led_brightness_set_detalhado", ("forte",),
                               {"uniq": MACS[2]})]
    disco = json.loads(pathlib.Path(arquivo).read_text(encoding="utf-8"))
    controles = disco.get("controllers") or {}
    assert controles.get(UNIQS[2], {}).get("leds") == {"player_led_brightness": "forte"}, (
        f"o override do P3 no disco é {controles.get(UNIQS[2])} — só o campo "
        f"clicado entra, para não densificar o resto")
    assert set(controles) == {UNIQS[2]}, f"o clique no P3 gravou em {sorted(controles)}"
    assert disco["leds"]["player_led_brightness"] == "fraco", (
        "o clique numa coluna mexeu no «Todos» do perfil")


def test_a_pilula_acesa_e_a_do_perfil_de_cada_controle() -> None:
    """A fileira de cada coluna acende a palavra do override dela, ou a do global."""
    from pacotes import a04_iluminacao as a04

    p = {"leds": {"player_led_brightness": "medio"},  # noqa-acento: chave ASCII
         "controllers": {UNIQS[2]: {"leds": {"player_led_brightness": "forte"}}}}
    assert a04.brilho_das_luzes_do_controle(p, MACS[2]) == "forte"
    assert a04.brilho_das_luzes_do_controle(p, MACS[0]) == "medio"  # noqa-acento: chave ASCII
    assert a04.brilho_das_luzes_do_controle({}, MACS[0]) == "fraco"
    fileira = a04.fileira_de_brilhos_das_luzes("forte")
    assert fileira.count('class="on"') == 1
    assert 'class="on" data-gesto="brilho-luzes" data-luzes="forte"' in fileira


def test_o_salvar_do_rodape_nao_apaga_o_brilho_das_luzes() -> None:
    """O «Salvar» do rodapé grava o que está valendo — e não apaga o brilho.

    Achado da conferência de 25/09/2026, a família do item 13 de 05/09 (*"o
    Salvar os DESTRUÍA"*): a pílula grava o brilho no override DAQUELE
    controle, e o Salvar remontava a seção `leds` do override com a cor viva
    (`with_controller_leds`), trocando-a inteira — o Médio do P3 voltava ao
    Fraco em silêncio. O global ia pelo mesmo caminho: o rascunho não tinha o
    campo, e o `to_profile` o regravava no padrão.

    MORDIDA: tire o `player_led_brightness` do que o `with_controller_leds`
    preserva e o override reprova; tire-o do `_leds_draft_to_config` e o
    global reprova.
    """
    from pacotes import rodape

    from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile

    save_profile(_perfil("forte", P3="medio"), origem="regua")  # noqa-acento: chave ASCII
    nome = "Régua do brilho das luzes"

    from types import SimpleNamespace

    ctx = SimpleNamespace(state={}, conectados=[
        {"uniq": UNIQS[2], "lightbar_rgb": [0, 0, 255], "lightbar_on": True,
         "lightbar_source": "sysfs"}])
    draft = rodape._draft_do_ativo(nome, ctx)
    gravado = draft.to_profile(nome, priority=load_profile(nome).priority)
    dele = gravado.controllers[UNIQS[2]].leds
    assert dele.lightbar == (0, 0, 255), "o Salvar deixou de gravar a cor viva"
    assert dele.player_led_brightness == "medio" and (  # noqa-acento: chave ASCII
        "player_led_brightness" in dele.model_fields_set), (
        f"o Salvar deixou o P3 em {dele.player_led_brightness!r} "
        f"(escrito: {sorted(dele.model_fields_set)}) — a pílula tinha gravado o Médio")
    assert gravado.leds.player_led_brightness == "forte", (
        f"o Salvar regravou o global em {gravado.leds.player_led_brightness!r}, e o "
        f"perfil dizia Forte")


def test_o_estilo_de_jogo_nao_apaga_o_brilho_das_luzes() -> None:
    """Aplicar um Estilo de Jogo na aba Perfis troca a cor, e não o brilho.

    O mesmo achado do «Salvar», no outro escritor que troca a seção `leds`
    inteira de um override: o estilo pinta cada unidade (`_com_o_estilo`), e o
    Forte que a pílula tinha gravado no P3 sumia. Quem guarda a regra é
    `schema.com_o_brilho_das_luzes_de`, e o P1 — sem opinião própria — continua
    sem opinião, herdando o global.

    MORDIDA: troque a chamada do dono em `_com_o_estilo` pelo `LedsConfig` cru e
    o P3 reprova.
    """
    from pacotes import a10_perfis as a10

    from hefesto_dualsense4unix.profiles.estilos_de_jogo import ESTILOS

    perfil = _perfil("medio", P3="forte")  # noqa-acento: chave ASCII
    mesa = [{"uniq": MACS[0], "jogador": 1}, {"uniq": MACS[2], "jogador": 3}]
    novo, pintados = a10._com_o_estilo(perfil, ESTILOS[0], mesa)
    assert pintados == 2
    p3 = novo.controllers[UNIQS[2]].leds
    assert p3.player_led_brightness == "forte" and (
        "player_led_brightness" in p3.model_fields_set), (
        f"o estilo deixou o P3 em {p3.player_led_brightness!r} — a pílula tinha "
        f"gravado o Forte")
    p1 = novo.controllers[UNIQS[0]].leds
    assert "player_led_brightness" not in p1.model_fields_set, (
        "o estilo inventou um brilho para o P1, que não tinha opinião própria")
