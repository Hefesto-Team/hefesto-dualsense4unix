"""A luz do controle nunca sai preta, e a cor de um não depende do brilho de outro."""
from __future__ import annotations

import pathlib
import sys
from dataclasses import dataclass, replace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core import led_control as lc
from hefesto_dualsense4unix.core.controller import OutputSpec
from hefesto_dualsense4unix.core.led_control import (
    DA_PALETA,
    DO_GLOBAL,
    LEGADO,
    PecaDaMesa,
    cores_sem_colisao,
    player_slot_color,
)

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

RGB = tuple[int, int, int]

UNIQS = [f"aabbcc00000{n}" for n in (1, 2, 3, 4)]
MACS = [f"AA:BB:CC:00:00:0{n}" for n in (1, 2, 3, 4)]

BRILHOS = (0.01, 0.08, 0.5, 0.99, 1.0)


@dataclass(frozen=True)
class Escolha:
    """Uma peça da mesa como ela está no disco: a cor antes do brilho."""

    uniq: str
    numero: int
    cor: RGB | None
    procedencia: object
    brilho: float


VERMELHO: RGB = (255, 0, 0)
AMARELO: RGB = (255, 255, 0)
LARANJA: RGB = (255, 128, 0)
VERDE_AGUA: RGB = (0, 255, 128)
ROSA: RGB = (255, 0, 128)
BRANCO: RGB = (255, 255, 255)
AZUL: RGB = (0, 0, 255)
VERDE: RGB = (0, 255, 0)

MESA_DAS_0230 = (
    Escolha(UNIQS[0], 1, VERMELHO, LEGADO, 1.0),
    Escolha(UNIQS[1], 2, AMARELO, 1, 0.08),
    Escolha(UNIQS[2], 3, LARANJA, 3, 1.0),
    Escolha(UNIQS[3], 4, VERDE_AGUA, 4, 0.99),
)

MESA_DAS_0124 = (
    Escolha(UNIQS[0], 1, VERMELHO, LEGADO, 1.0),
    Escolha(UNIQS[1], 2, AMARELO, 1, 0.08),
    Escolha(UNIQS[2], 3, ROSA, LEGADO, 1.0),
    Escolha(UNIQS[3], 4, BRANCO, 4, 0.99),
)

MESA_SEM_PALETA = (
    Escolha(UNIQS[0], 1, AZUL, 1, 1.0),
    Escolha(UNIQS[1], 2, AZUL, 2, 0.5),
    Escolha(UNIQS[2], 3, None, DO_GLOBAL, 0.5),
    Escolha(UNIQS[3], 4, VERDE, 4, 1.0),
)
GLOBAL_AZUL: RGB = AZUL

MESA_DO_LEGADO_ESCURO = (
    Escolha(UNIQS[0], 1, None, DA_PALETA, 1.0),
    Escolha(UNIQS[1], 2, (0, 0, 209), LEGADO, 1.0),
    Escolha(UNIQS[2], 3, None, DA_PALETA, 0.5),
    Escolha(UNIQS[3], 4, LARANJA, 4, 1.0),
)

MESAS = {
    "0230": (MESA_DAS_0230, True),
    "0124": (MESA_DAS_0124, True),
    "sem-paleta": (MESA_SEM_PALETA, False),
    "legado-escuro": (MESA_DO_LEGADO_ESCURO, True),
}


def _na_escala(cor: RGB, brilho: float) -> RGB:
    """A conta do dono da escala, perguntada a ele."""
    return lc.LedSettings(lightbar=cor).apply_brightness(brilho).lightbar


def _pecas(escolhas: tuple[Escolha, ...], paleta: bool) -> list[PecaDaMesa]:
    """A mesa como o backend a monta: tudo no brilho de cada peça."""
    pecas = []
    for e in escolhas:
        do_numero = _na_escala(player_slot_color(e.numero), e.brilho) if paleta else None
        if e.cor is not None:
            pedida, procedencia = _na_escala(e.cor, e.brilho), e.procedencia
        elif paleta:
            pedida, procedencia = do_numero, DA_PALETA
        else:
            pedida, procedencia = _na_escala(GLOBAL_AZUL, e.brilho), DO_GLOBAL
        pecas.append(PecaDaMesa(uniq=e.uniq, pedida=pedida, do_numero=do_numero,
                                procedencia=procedencia, numero=e.numero,
                                brilho=e.brilho))
    return pecas


def _variacoes(escolhas: tuple[Escolha, ...]):
    """Cada OUTRA peça em cada brilho da régua — e quem varia é dito."""
    for i, outra in enumerate(escolhas):
        for brilho in BRILHOS:
            if brilho == outra.brilho:
                continue
            nova = list(escolhas)
            nova[i] = replace(outra, brilho=brilho)
            yield i, brilho, tuple(nova)


@pytest.mark.parametrize("nome", sorted(MESAS))
def test_o_tom_de_uma_peca_nao_depende_do_brilho_de_outra(nome: str) -> None:
    """A saída de cada peça é a mesma com o trilho de qualquer OUTRA em qualquer ponto."""
    escolhas, paleta = MESAS[nome]
    base = cores_sem_colisao(_pecas(escolhas, paleta))
    trocas = []
    for i, brilho, variada in _variacoes(escolhas):
        saida = cores_sem_colisao(_pecas(variada, paleta))
        for j, peca in enumerate(escolhas):
            if j != i and saida.get(peca.uniq) != base.get(peca.uniq):
                trocas.append(
                    f"P{escolhas[i].numero} a {brilho:.0%} trocou a luz do "
                    f"P{peca.numero}: {base.get(peca.uniq)} -> {saida.get(peca.uniq)}")
    assert trocas == []


def test_a_repetida_e_o_global_cedem_pelo_tom() -> None:
    """A escolha repetida a 50% e o global a 50% ao lado do P1 azul cheio saem do azul."""
    saida = cores_sem_colisao(_pecas(MESA_SEM_PALETA, False))
    for uniq in (UNIQS[1], UNIQS[2]):
        assert not lc._mesmo_tom(saida[uniq], saida[UNIQS[0]]), saida


def _provider(ranks: dict[str, int]) -> Any:
    """O provider com as duas companheiras do daemon (o número e a mesa)."""

    def provider(uniq: str) -> Any:
        slot = ranks.get(uniq)
        if slot is None:
            return None
        return bp._DesiredOutput(led=player_slot_color(slot))

    provider.numero_do_slot = ranks.get  # type: ignore[attr-defined]
    provider.uniqs_da_mesa = lambda: list(ranks)  # type: ignore[attr-defined]
    return provider


def _fosseis_do_daemon(escolhas: tuple[Escolha, ...]) -> frozenset[str]:
    """O backend REAL, com o perfil na camada dele, pergunta ao dono."""
    ctl = bp.PyDualSenseController()
    ctl._handles = dict.fromkeys(MACS)
    ctl.set_auto_output_provider(_provider({e.uniq: e.numero for e in escolhas}))
    ctl.set_game_authority_provider(lambda: "daemon")
    ctl.set_led_scales({e.uniq: e.brilho for e in escolhas},
                       brilho_do_perfil=1.0, cor_do_perfil=None)
    ctl.reset_profile_overrides(
        {e.uniq: OutputSpec(led=_na_escala(e.cor, e.brilho))
         for e in escolhas if e.cor is not None},
        procedencias={e.uniq: e.procedencia for e in escolhas
                      if isinstance(e.procedencia, int)},
    )
    with ctl._io_lock:
        return lc.fosseis(ctl._mesa_de_cores_locked(incluir_coop=True))


def _fosseis_da_tela(escolhas: tuple[Escolha, ...]) -> frozenset[str]:
    """A aba Iluminação, pelo perfil cru e pela mesa do `state_full`."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")
    for caminho in (str(RAIZ / "src"), str(INTERFACE)):
        if caminho not in sys.path:
            sys.path.insert(0, caminho)
    from pacotes import Contexto
    from pacotes import a04_iluminacao as a04

    conectados = [{"uniq": e.uniq, "player_slot": e.numero, "connected": True}
                  for e in escolhas]
    controllers: dict[str, Any] = {}
    for e in escolhas:
        if e.cor is None:
            continue
        leds: dict[str, Any] = {"lightbar": list(e.cor),
                                "lightbar_brightness": e.brilho}
        if isinstance(e.procedencia, int):
            leds["lightbar_para_o_numero"] = e.procedencia
        controllers[a04.chave_do_override(e.uniq)] = {"leds": leds}
    cru = {"leds": {"auto_player_colors": True, "lightbar_brightness": 1.0},
           "controllers": controllers}
    ctx = Contexto(state={}, mesa=[], conectados=conectados, estados={})
    return frozenset(
        c["uniq"] for c in conectados
        if any(e.uniq == c["uniq"] and e.cor is not None for e in escolhas)
        and a04._a_cor_guardada_que_vale(ctx, cru, c) is None
    )


@pytest.mark.parametrize("nome", ["0230", "0124", "legado-escuro"])
def test_a_tela_e_o_daemon_dizem_o_mesmo_fossil(nome: str) -> None:
    """Peça a peça, em todo brilho da régua 4, a tela e o daemon concordam."""
    escolhas, _paleta = MESAS[nome]
    divergencias = []
    for _i, brilho, variada in [(None, None, escolhas), *_variacoes(escolhas)]:
        tela, daemon = _fosseis_da_tela(variada), _fosseis_do_daemon(variada)
        if tela != daemon:
            divergencias.append(f"{brilho}: tela={sorted(tela)} daemon={sorted(daemon)}")
    assert divergencias == []


def test_o_legado_da_cor_de_outro_numero_e_fossil_em_todo_brilho() -> None:
    """O rosa legado do Starlight Blue é o tom do número 4: fóssil, a 99% e a 100%."""
    for brilho in (0.99, 1.0):
        variada = tuple(replace(e, brilho=brilho) if e.numero == 4 else e
                        for e in MESA_DAS_0124)
        assert UNIQS[2] in _fosseis_do_daemon(variada)


BRANCO_ID = "aabbcc0000b1"
BRANCO_ID_2 = "aabbcc0000b2"
SEM_PLASTICO = "aabbcc0000c1"


@pytest.fixture
def registro(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """O registro de identidade REAL, num disco de mentira, com o leitor de dublê."""
    from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod
    from hefesto_dualsense4unix.integrations import cor_do_plastico as cp
    from hefesto_dualsense4unix.utils import xdg_paths

    def config_de_mentira(ensure: bool = False) -> pathlib.Path:
        if ensure:
            tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path

    monkeypatch.setattr(xdg_paths, "config_dir", config_de_mentira)
    monkeypatch.setattr(id_mod, "_read_boot_id", lambda: "boot-da-luz")
    perguntas: list[str] = []

    def leitor(uniq: str) -> Any:
        perguntas.append(uniq)
        if uniq in (BRANCO_ID, BRANCO_ID_2):
            return cp.IdentidadeDeFabrica(serial="DUBLE00##########",
                                          cor=cp.cor_do_nome("White"))
        return cp.IdentidadeDeFabrica(serial="DUBLE01##########", cor=None)

    monkeypatch.setattr(cp, "ler_identidade_pelo_cabo", leitor)
    reg = id_mod.ControllerIdentityRegistry()
    reg.perguntas = perguntas  # type: ignore[attr-defined]
    return reg


def _esperar_o_plastico(reg: Any, *uniqs: str) -> None:
    """A pergunta sai numa thread: espera a resposta chegar ao cache."""
    import time

    fim = time.monotonic() + 5.0
    while time.monotonic() < fim:
        if all(reg.identidade_de_fabrica(u) is not None for u in uniqs):
            return
        time.sleep(0.01)
    raise AssertionError(f"o plástico de {uniqs} não chegou ao registro")


def _mesa_do_registro(reg: Any, uniqs: list[str]) -> Any:
    from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod

    provider = id_mod.make_auto_output_provider(reg)
    reg.sync_connected(uniqs)
    reg.liberar_as_lampadas()
    return provider


def test_o_white_lido_acende_branco_e_sem_plastico_acende_o_numero(registro: Any) -> None:
    """O provider acende o plástico lido; sem ele, a cor do número de hoje."""
    provider = _mesa_do_registro(registro, [BRANCO_ID, SEM_PLASTICO])
    _esperar_o_plastico(registro, BRANCO_ID, SEM_PLASTICO)
    assert provider(BRANCO_ID).led == BRANCO
    numero = provider.numero_do_slot(SEM_PLASTICO)
    assert provider(SEM_PLASTICO).led == player_slot_color(numero)


def test_dois_white_o_segundo_cai_no_numero(registro: Any) -> None:
    """Dois plásticos iguais: o primeiro fica com o branco, o segundo vai ao número dele."""
    provider = _mesa_do_registro(registro, [BRANCO_ID, BRANCO_ID_2])
    _esperar_o_plastico(registro, BRANCO_ID, BRANCO_ID_2)
    ctl = bp.PyDualSenseController()
    ctl._handles = {"AA:BB:CC:00:00:B1": None, "AA:BB:CC:00:00:B2": None}
    ctl.set_auto_output_provider(provider)
    ctl.set_game_authority_provider(lambda: "daemon")
    with ctl._io_lock:
        saida = cores_sem_colisao(ctl._mesa_de_cores_locked(incluir_coop=True))
    primeiro, segundo = sorted((BRANCO_ID, BRANCO_ID_2), key=provider.numero_do_slot)
    assert saida[primeiro] == BRANCO
    assert saida[segundo] == player_slot_color(provider.numero_do_slot(segundo))


def test_o_degrau_4_da_tela_diz_o_mesmo_que_o_provider(registro: Any) -> None:
    """A tela pergunta ao mesmo dono: para as mesmas entradas, a mesma cor."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")
    for caminho in (str(RAIZ / "src"), str(INTERFACE)):
        if caminho not in sys.path:
            sys.path.insert(0, caminho)
    from pacotes import Contexto
    from pacotes import a04_iluminacao as a04

    provider = _mesa_do_registro(registro, [BRANCO_ID, SEM_PLASTICO])
    _esperar_o_plastico(registro, BRANCO_ID, SEM_PLASTICO)
    conectados = []
    for uniq in (BRANCO_ID, SEM_PLASTICO):
        achado = registro.identidade_de_fabrica(uniq)
        conectados.append({
            "uniq": uniq, "player_slot": provider.numero_do_slot(uniq),
            "connected": True,
            "modelo": None if achado.cor is None else achado.cor.nome,
        })
    ctx = Contexto(state={}, mesa=[], conectados=conectados, estados={})
    for c in conectados:
        assert a04._a_cor_de_agora(ctx, None, c) == provider(c["uniq"]).led, c


def _tom(nome: str) -> RGB:
    from hefesto_dualsense4unix.integrations.cor_do_plastico import tom_da_luz_do_nome

    tom = tom_da_luz_do_nome(nome)
    assert tom is not None, nome
    return tom


ROXO_DA_PALETA: RGB = player_slot_color(8)


def _automatica(uniq: str, numero: int, plastico: str | None,
                brilho: float = 1.0) -> PecaDaMesa:
    """A peça sem escolha: acende o plástico (ou o número), como o backend a monta."""
    do_numero = _na_escala(player_slot_color(numero), brilho)
    do_plastico = None if plastico is None else _na_escala(_tom(plastico), brilho)
    pedida = do_plastico if do_plastico is not None else do_numero
    return PecaDaMesa(uniq=uniq, pedida=pedida, do_numero=do_numero,
                      procedencia=DA_PALETA, numero=numero, brilho=brilho,
                      do_plastico=do_plastico)


def _escolhida(uniq: str, numero: int, cor: RGB, plastico: str | None,
               brilho: float = 1.0) -> PecaDaMesa:
    """A peça com a cor escolhida para o número de hoje (não é fóssil)."""
    base = _automatica(uniq, numero, plastico, brilho)
    return replace(base, pedida=_na_escala(cor, brilho), procedencia=numero)


@pytest.mark.parametrize("via", ["usb", "bt"])
@pytest.mark.parametrize("k", [1, 2, 3, 4], ids=["P1", "P2", "P3", "P4"])
@pytest.mark.parametrize(("plastico", "escolha"), [
    ("Galactic Purple", ROXO_DA_PALETA),
    ("Cosmic Red", ROSA),
    ("White", (252, 252, 252)),
], ids=["roxo-ao-lado-do-galactic", "rosa-ao-lado-do-cosmic", "branco-ao-lado-do-white"])
def test_a_escolha_ao_lado_de_um_plastico_vizinho_fica(plastico: str, escolha: RGB,
                                                        k: int, via: str) -> None:
    """A cor que ela escolheu fica, e o plástico vizinho de outro controle cede ao número."""
    del via
    numeros = [1, 2, 3, 4]
    quem_escolhe = numeros[(k % 4)]
    mesa = []
    for n in numeros:
        uniq = UNIQS[n - 1]
        if n == k:
            mesa.append(_automatica(uniq, n, plastico))
        elif n == quem_escolhe:
            mesa.append(_escolhida(uniq, n, escolha, "Starlight Blue"))
        else:
            mesa.append(_automatica(uniq, n, None))
    saida = cores_sem_colisao(mesa)
    assert saida[UNIQS[quem_escolhe - 1]] == escolha, saida
    assert not lc._mesmo_tom(saida[UNIQS[k - 1]], escolha), saida
    luzes = list(saida.values())
    for i, a in enumerate(luzes):
        for b in luzes[i + 1:]:
            assert not lc._mesmo_tom(a, b), saida


def test_na_mesa_das_0230_cada_plastico_acende_a_luz_da_prova() -> None:
    """A prova da sprint na função pura: a mesa das 02:30 com os plásticos lidos."""
    mesa = [
        replace(_automatica(UNIQS[0], 1, "Cosmic Red"), pedida=VERMELHO,
                procedencia=LEGADO),
        replace(_automatica(UNIQS[1], 2, "White", 0.08),
                pedida=_na_escala(AMARELO, 0.08), procedencia=1),
        _escolhida(UNIQS[2], 3, LARANJA, "Starlight Blue"),
        _escolhida(UNIQS[3], 4, VERDE_AGUA, "Galactic Purple", 0.99),
    ]
    saida = cores_sem_colisao(mesa)
    assert saida == {
        UNIQS[0]: VERMELHO,
        UNIQS[1]: _na_escala(BRANCO, 0.08),
        UNIQS[2]: LARANJA,
        UNIQS[3]: _na_escala(VERDE_AGUA, 0.99),
    }, saida


def test_o_tique_de_presenca_pergunta_o_plastico_sem_state_full(registro: Any) -> None:
    """O `sync_connected` agenda a pergunta de quem chega, e o provider vê o plástico."""
    provider = _mesa_do_registro(registro, [BRANCO_ID])
    _esperar_o_plastico(registro, BRANCO_ID)
    assert registro.perguntas == [BRANCO_ID]
    assert provider.tom_do_plastico(BRANCO_ID) == BRANCO
    registro.sync_connected([BRANCO_ID])
    assert registro.perguntas == [BRANCO_ID]


@pytest.mark.parametrize(("uniq", "reafirma"), [(BRANCO_ID, True), (SEM_PLASTICO, False)],
                         ids=["plastico-com-tom", "sem-plastico"])
def test_a_luz_converge_quando_o_plastico_chega(registro: Any, uniq: str,
                                               reafirma: bool) -> None:
    """O plástico com tom chega e o backend reafirma a luz na hora, sem esperar o `connect()`."""
    import threading

    chegou = threading.Event()
    ctl = bp.PyDualSenseController()
    ctl.reassert_resolved_outputs = lambda **_k: chegou.set()  # type: ignore[method-assign]
    provider = _mesa_do_registro(registro, [])
    ctl.set_auto_output_provider(provider)
    registro.sync_connected([uniq])
    _esperar_o_plastico(registro, uniq)
    assert chegou.wait(2.0 if reafirma else 0.3) is reafirma


def test_sem_a_fiacao_do_daemon_nenhuma_pergunta_sai(registro: Any) -> None:
    """O registro sem o provider do daemon (teste, CLI) não fala com aparelho nenhum."""
    registro.sync_connected([BRANCO_ID])
    assert registro.perguntas == []
    assert registro.identidade_de_fabrica(BRANCO_ID) is None


LIDA_COMO_PRETO = 20
BRILHO_DAS_0230 = 0.08


def _tons_da_regua() -> list[RGB]:
    """Os tons da paleta e os do plástico do mapa (a resposta (b))."""
    from hefesto_dualsense4unix.integrations import cor_do_plastico as cp

    tons = [player_slot_color(n) for n in range(1, 9)]
    for cor in cp.TABELA.values():
        tom = cp.tom_da_luz(cor)
        if tom is not None and tom not in tons:
            tons.append(tom)
    return tons


def _piso_do_dono() -> int:
    """O canal maior mais fraco que o trilho acende, lido do dono."""
    return int(255 * lc.PISO_DO_BRILHO)


@pytest.mark.parametrize("tom", _tons_da_regua(), ids=lambda t: "#{:02X}{:02X}{:02X}".format(*t))
def test_todo_passo_do_trilho_acende_uma_cor_que_se_ve(tom: RGB) -> None:
    """De 1% a 100%, o canal maior nunca fica abaixo do piso, e a luz sobe a cada passo."""
    anterior: RGB | None = None
    for pct in range(1, 101):
        luz = _na_escala(tom, pct / 100)
        assert max(luz) >= _piso_do_dono(), (pct, luz)
        if anterior is not None:
            assert all(a <= b for a, b in zip(anterior, luz, strict=True)), (pct, anterior, luz)
            assert luz != anterior, f"o passo de {pct - 1}% a {pct}% não muda a luz {luz}"
        anterior = luz
    assert _na_escala(tom, 0.0) == (0, 0, 0), "o 0% (o «Desligar») apaga"


@pytest.mark.parametrize("tom", _tons_da_regua(), ids=lambda t: "#{:02X}{:02X}{:02X}".format(*t))
def test_a_oito_por_cento_a_luz_nao_e_mais_a_que_ela_leu_como_preto(tom: RGB) -> None:
    """A âncora: a 8%, em todo tom, o canal maior passa do `20` das 02:30."""
    assert max(_na_escala(tom, BRILHO_DAS_0230)) > LIDA_COMO_PRETO


def test_o_provider_acende_no_piso(registro: Any) -> None:
    """A cor automática do daemon, no brilho de 8% do perfil, se vê."""
    registro.configure(brightness=BRILHO_DAS_0230)
    provider = _mesa_do_registro(registro, [SEM_PLASTICO])
    _esperar_o_plastico(registro, SEM_PLASTICO)
    assert max(provider(SEM_PLASTICO).led) > LIDA_COMO_PRETO


@pytest.mark.parametrize("brilho_do_perfil", [1.0, None], ids=["com-o-perfil", "fator-sem-base"])
def test_o_trilho_por_controle_acende_no_piso(brilho_do_perfil: float | None) -> None:
    """O merge do backend com o trilho de um controle a 8% e o perfil a 100%."""
    escolhas = MESA_DO_LEGADO_ESCURO
    ctl = bp.PyDualSenseController()
    ctl._handles = dict.fromkeys(MACS)
    ctl.set_auto_output_provider(_provider({e.uniq: e.numero for e in escolhas}))
    ctl.set_game_authority_provider(lambda: "daemon")
    ctl.set_led_scales({UNIQS[0]: BRILHO_DAS_0230}, brilho_do_perfil=brilho_do_perfil,
                       cor_do_perfil=None)
    with ctl._io_lock:
        luz = ctl._merged_desired_for_key(MACS[0]).led
    assert luz == _na_escala(player_slot_color(1), BRILHO_DAS_0230)
    assert max(luz) > LIDA_COMO_PRETO


def test_o_perfil_aplicado_acende_no_piso(tmp_path: pathlib.Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    """O `ProfileManager.apply` de um perfil a 8% manda ao aparelho uma luz que se vê."""
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.profiles.schema import LedsConfig, MatchCriteria, Profile
    from hefesto_dualsense4unix.testing import FakeController

    perfil = Profile(name="piso", match=MatchCriteria(window_class=["piso_class"]),
                     priority=10,
                     leds=LedsConfig(lightbar=AMARELO, lightbar_brightness=BRILHO_DAS_0230))
    fc = FakeController()
    fc.connect()
    ProfileManager(controller=fc).apply(perfil)
    assert fc.last_led is not None
    assert tuple(fc.last_led.color) == _na_escala(AMARELO, BRILHO_DAS_0230)
    assert max(fc.last_led.color) > LIDA_COMO_PRETO


@pytest.mark.asyncio
async def test_o_led_set_da_aba_acende_no_piso(tmp_path: pathlib.Path) -> None:
    """O gesto de brilho da aba Iluminação (`led.set` com `brightness`) passa pelo dono."""
    from tests.unit.test_fecha_iluminacao_01_duas_pecas_nunca_tem_a_mesma_cor import (
        MACS as MACS_DA_MESA,
    )
    from tests.unit.test_fecha_iluminacao_01_duas_pecas_nunca_tem_a_mesma_cor import (
        _mesa_de_quatro,
    )

    server, _ctl, nos = _mesa_de_quatro(tmp_path, overrides={})
    await server._handle_led_set({"rgb": list(AMARELO), "brightness": BRILHO_DAS_0230,
                                  "uniq": MACS_DA_MESA[1]})
    assert nos[MACS_DA_MESA[1]].rgb[-1] == _na_escala(AMARELO, BRILHO_DAS_0230)
    assert max(nos[MACS_DA_MESA[1]].rgb[-1]) > LIDA_COMO_PRETO
