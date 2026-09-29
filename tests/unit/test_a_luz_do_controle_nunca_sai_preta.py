"""A luz do controle nunca sai preta, e a cor de um não depende do brilho de outro.

A-LUZ-DO-CONTROLE-NUNCA-SAI-PRETA-01, o achado 10 da bancada de 29/09 (02h30):
*«a lightbar do controle tá preto (preto tinha sido banido) e pra piorar a cor
do lightbar do branco é azul»*. A luz do White saía `(0, 0, 20)`: a cor
guardada era fóssil, a do número dele estava com o Cosmic Red, o resolvedor a
deslocava ao primeiro tom livre (o azul), e tudo no brilho de 8% dele.

As réguas, e nenhuma mede a própria saída:

4. o tom de uma peça não depende do brilho de outra: o resolvedor comparado
   consigo mesmo, com o brilho de cada OUTRA peça variando;
5. a tela e o daemon dizem o mesmo fóssil: a aba Iluminação e a mesa que o
   backend real monta, peça a peça, em todos os brilhos da régua 4.

COMO MORDER:

* régua 4 — volte qualquer uma das três perguntas de `led_control` para o
  byte (`peca.pedida in numeros` no legado de `_e_fossil`, `in tomadas` na
  repetida, `not in tomadas` no global): a mesa dela reprova;
* régua 5 — a tela volta a montar a peça com as cores cheias e a comparar
  pelo byte (`peca.pedida in numeros`).
"""
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

#: Uniqs FORJADOS (faixa `aa:bb:cc`), nunca a máscara de um endereço real.
UNIQS = [f"aabbcc00000{n}" for n in (1, 2, 3, 4)]
MACS = [f"AA:BB:CC:00:00:0{n}" for n in (1, 2, 3, 4)]

#: Os brilhos da régua 4: o de 8% é o do White das 02:30, e o de 99% e 100%
#: são a borda em que o byte trocava a resposta.
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

#: A mesa das 02:30 (`demo/05-estado.txt` e o `freestyle.json` lido): o Cosmic
#: Red com o vermelho legado, o White com o amarelo escolhido para o 1 a 8%, o
#: Starlight Blue com o laranja do 3 e o Galactic Purple com o verde-água do 4
#: a 99%.
MESA_DAS_0230 = (
    Escolha(UNIQS[0], 1, VERMELHO, LEGADO, 1.0),
    Escolha(UNIQS[1], 2, AMARELO, 1, 0.08),
    Escolha(UNIQS[2], 3, LARANJA, 3, 1.0),
    Escolha(UNIQS[3], 4, VERDE_AGUA, 4, 0.99),
)

#: A mesa das 01:24: o Starlight Blue com o rosa legado (a cor do número 4) e
#: o Galactic Purple a 99%. O rosa dele ficava aceso por 1% de brilho do outro.
MESA_DAS_0124 = (
    Escolha(UNIQS[0], 1, VERMELHO, LEGADO, 1.0),
    Escolha(UNIQS[1], 2, AMARELO, 1, 0.08),
    Escolha(UNIQS[2], 3, ROSA, LEGADO, 1.0),
    Escolha(UNIQS[3], 4, BRANCO, 4, 0.99),
)

#: A paleta desligada: uma escolha repetida (o azul do P1 no P2, a 50%) e um
#: controle no azul GLOBAL a 50% ao lado do P1 azul.
MESA_SEM_PALETA = (
    Escolha(UNIQS[0], 1, AZUL, 1, 1.0),
    Escolha(UNIQS[1], 2, AZUL, 2, 0.5),
    Escolha(UNIQS[2], 3, None, DO_GLOBAL, 0.5),
    Escolha(UNIQS[3], 4, VERDE, 4, 1.0),
)
GLOBAL_AZUL: RGB = AZUL

#: Um legado ESCURECIDO: o azul do P1 a 82%, `(0, 0, 209)`, gravado como cor
#: por um «Salvar» que leu o aparelho. Pelo byte cheio ele não é a cor de
#: número de ninguém; pelo tom, é o azul do 1, e é fóssil no P2.
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


# ===========================================================================
# 4. O tom de uma peça não depende do brilho de outra
# ===========================================================================
@pytest.mark.parametrize("nome", sorted(MESAS))
def test_o_tom_de_uma_peca_nao_depende_do_brilho_de_outra(nome: str) -> None:
    """A saída de cada peça é a mesma com o trilho de qualquer OUTRA em qualquer ponto.

    Antes da cura, com o byte: o Cosmic Red virava azul com o White a 100%, o
    Starlight Blue virava verde com o Galactic Purple a 100%, e a repetida e o
    global só se deslocavam no brilho igual ao do dono da cor.
    """
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
    """A escolha repetida a 50% e o global a 50% ao lado do P1 azul cheio saem do azul.

    O byte deixava os dois no azul, porque `(0, 0, 127)` não é `(0, 0, 255)`.
    """
    saida = cores_sem_colisao(_pecas(MESA_SEM_PALETA, False))
    for uniq in (UNIQS[1], UNIQS[2]):
        assert not lc._mesmo_tom(saida[uniq], saida[UNIQS[0]]), saida


# ===========================================================================
# 5. A tela e o daemon dizem o mesmo fóssil
# ===========================================================================
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


# ===========================================================================
# 6. A cor automática tem um dono, e ele sabe o plástico
#    (D-2909-A-COR-AUTOMATICA-VEM-DO-PLASTICO, a resposta (b))
# ===========================================================================
BRANCO_ID = "aabbcc0000b1"
BRANCO_ID_2 = "aabbcc0000b2"
SEM_PLASTICO = "aabbcc0000c1"


@pytest.fixture
def registro(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """O registro de identidade REAL, num disco de mentira, com o leitor de dublê.

    O leitor de dublê responde como o de verdade (`IdentidadeDeFabrica`), e
    quem o chama é o registro, pelo mesmo fio que o daemon arma
    (`make_auto_output_provider`). Nenhum byte vai a aparelho nenhum.
    """
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


# ===========================================================================
# 7. O daemon sabe o plástico sem a janela
# ===========================================================================
def test_o_tique_de_presenca_pergunta_o_plastico_sem_state_full(registro: Any) -> None:
    """O `sync_connected` agenda a pergunta de quem chega, e o provider vê o plástico."""
    provider = _mesa_do_registro(registro, [BRANCO_ID])
    _esperar_o_plastico(registro, BRANCO_ID)
    assert registro.perguntas == [BRANCO_ID]
    assert provider.tom_do_plastico(BRANCO_ID) == BRANCO
    # A resposta definitiva não se pergunta de novo.
    registro.sync_connected([BRANCO_ID])
    assert registro.perguntas == [BRANCO_ID]


def test_sem_a_fiacao_do_daemon_nenhuma_pergunta_sai(registro: Any) -> None:
    """O registro sem o provider do daemon (teste, CLI) não fala com aparelho nenhum."""
    registro.sync_connected([BRANCO_ID])
    assert registro.perguntas == []
    assert registro.identidade_de_fabrica(BRANCO_ID) is None
