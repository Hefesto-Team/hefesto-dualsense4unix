"""A MARCA DA COR NÃO SOME — a borda e o X de cada controle vêm da cor DELE.

**A QUEIXA DELA, 24/09/2026:** *"quando eu abaixo o volume do lightbar,. o X
não permanece no seletor dos demais controles. isso é um erro que me
incomoda."*   # noqa-acento: citação literal dela

«Volume do lightbar» é o trilho «Brilho» da aba Iluminação; «o X» é a casa
`tomado` da fileira de tons, que marca a cor que OUTRO controle tem. A borda
(`on`) é a mesma marca vista da coluna do próprio controle.

**O QUE O PILOTO MEDIU, COM O CLIQUE** (a 04 publicada, P1 e P2 no USB, P3 e P4
no BT, o P2 laranja e o P3 ciano escolhidos, o P1 e o P4 na cor do número, o
perfil a 82%), e cada linha é uma régua abaixo::

    soltou o P2 em 50%   por ~meio segundo o X laranja some das outras três
                         fileiras, e a borda do P2 some: o disco já diz 50% e
                         o daemon ainda publica a luz de 82%
    P2 em 0%             a borda do P2 pula para o azul, o X laranja some de
                         vez e o P1 ganha um X no PRÓPRIO azul: a 0% os
                         catorze tons acendem preto, e a leitura devolvia o
                         primeiro da tabela
    subiu de 0%          o gesto reenviava o azul: o P4 voltou aceso na cor
                         do P1
    subiu de 0%          (medido depois da primeira cura) a coluna virava
                         preta por meio segundo: a luz velha é o preto, e o
                         `#000000` é tom da casa

**A REGRA, em todo tique:** a marca de cada controle vem da cor dele, e nenhum
gesto de outro controle a apaga — a borda na fileira dele, o X nas fileiras dos
outros três, e a caixa `#RRGGBB` dizendo a cor dele.

**O PRODUTO É O REAL DOS DOIS LADOS.** O daemon é o `IpcServer._handle_led_set`
sobre o `PyDualSenseController`, com `SysfsLedNode` escrevendo em arquivos do
`tmp_path`, o `ProfileManager.apply` do perfil do disco e a paleta de
`make_auto_output_provider` sobre o registro de identidade real; a luz publicada
sai do `_lightbar_for_uniq`. A tela é o `pacote` da 04 e os gestos `brilho` e
`cor`. O disco é o do `conftest` (HOME e XDG desviados).

**ARRASTAR NÃO CHEGA AQUI, e é de propósito:** o `input` do trilho só move o
rótulo pela página (`data-hef-vivo`); o gesto nasce no `change`, quando ela
solta. O que o arraste pode fazer à marca é o que a luz atrasada faz — medido
no piloto, 0 leituras fora do lugar durante os arrastes. Aqui, «soltar duas
vezes antes de a luz assentar» é o arraste que chega ao Python.
"""
from __future__ import annotations

import asyncio
import pathlib
import re
import sys
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"), str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from hefesto_dualsense4unix.core.led_control import player_slot_color

#: A faixa sintética da casa — octetos 4 e 5 zerados, nunca um endereço real.
MACS = [f"AA:BB:CC:00:00:0{n}" for n in (1, 2, 3, 4)]
UNIQS = [m.replace(":", "").lower() for m in MACS]
PREFS = ("p1", "p2", "p3", "p4")
VIAS = ("usb", "usb", "bt", "bt")
NOME = "regua-marca"
#: O global do perfil dela e o brilho dela: a 100% a luz acesa É o tom da
#: guia, e a inversão de escala nunca seria posta à prova.
GLOBAL = (40, 80, 180)
BRILHO_GLOBAL = 0.82
LARANJA = (255, 128, 0)
CIANO = (0, 255, 255)
#: A COR DE CADA UM: P2 e P3 escolheram pela guia; P1 e P4 nunca escolheram, e
#: a cor deles é a do número. O P1 é o azul de propósito — é a casa em que a
#: leitura velha caía a 0%, e a régua precisa do dono DAQUELE tom na mesa.
COR_DELE = {1: player_slot_color(1), 2: LARANJA, 3: CIANO, 4: player_slot_color(4)}
IDS = ["P1-USB", "P2-USB", "P3-BT", "P4-BT"]


def _hexa(rgb: Any) -> str:
    return "#" + "".join(f"{int(c):02X}" for c in tuple(rgb)[:3])


@pytest.fixture
def a04():
    from pacotes import a04_iluminacao

    return a04_iluminacao


@pytest.fixture
def pac():
    import pacotes

    return pacotes


# ---------------------------------------------------------------------------
# A mesa de quatro, no produto real
# ---------------------------------------------------------------------------
def _handle_falso() -> Any:
    """Handle pydualsense falso — `connected=True` é o que o `describe` lê."""
    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

    return SimpleNamespace(
        connected=True, triggerL=DSTrigger(), triggerR=DSTrigger(),
        light=DSLight(), audio=DSAudio(),
        _raw_trigger_left=None, _raw_trigger_right=None)


def _no(raiz: pathlib.Path, n: int) -> Any:
    """Um `SysfsLedNode` REAL, sobre arquivos: o que o daemon lê de volta é o que ele escreveu."""
    from hefesto_dualsense4unix.core.sysfs_leds import SysfsLedNode

    base = raiz / "sys" / f"ds{n}"
    ind = base / "rgb:indicator"
    ind.mkdir(parents=True, exist_ok=True)
    (ind / "multi_intensity").write_text("0 0 0\n")
    (ind / "brightness").write_text("0\n")
    jogadores = []
    for j in range(1, 6):
        d = base / f"white:player-{j}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "brightness").write_text("0\n")
        jogadores.append(str(d))
    return SysfsLedNode(str(ind), jogadores)


class PonteDoDaemon:
    """A ponte da aba com o `led.set` entregue ao handler REAL do daemon.

    O payload sai do `_payload_led_set` da ponte do produto (o dono da forma),
    e o corpo que volta é o do `_handle_led_set`. Qualquer outra chamada é
    recusada: um dublê que aceita tudo mede menos que o produto.
    """

    def __init__(self, mesa: Mesa) -> None:
        self.mesa = mesa
        self.enviados: list[dict[str, Any]] = []

    def led_set_detalhado(self, rgb: Any, brightness: float | None = None,
                          uniq: str | None = None) -> dict[str, Any]:
        from hefesto_dualsense4unix.app.ipc_bridge import _payload_led_set

        payload = _payload_led_set(tuple(rgb), brightness, uniq)
        self.enviados.append(payload)
        return self.mesa.rodar(self.mesa.server._handle_led_set(payload))

    def __getattr__(self, nome: str) -> Any:
        raise AttributeError(f"a régua não previu a aba chamar a ponte em {nome!r}")


class Mesa:
    """Os quatro DualSense, o perfil no disco e a aba 04 — um tique de cada vez."""

    def __init__(self, raiz: pathlib.Path, pac: Any, a04: Any, *,
                 alvo: str = "todos") -> None:
        from hefesto_dualsense4unix.core import backend_pydualsense as bp
        from hefesto_dualsense4unix.core.controller import ControllerState
        from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
        from hefesto_dualsense4unix.daemon.state_store import StateStore
        from hefesto_dualsense4unix.daemon.subsystems.identity import (
            get_identity_registry,
            make_auto_output_provider,
        )
        from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
        from hefesto_dualsense4unix.profiles.manager import ProfileManager
        from hefesto_dualsense4unix.profiles.schema import LedsConfig, MatchAny, Profile

        self.pac, self.a04 = pac, a04
        self.loop = asyncio.new_event_loop()
        save_profile(Profile(
            name=NOME, match=MatchAny(),
            leds=LedsConfig(lightbar=GLOBAL, lightbar_brightness=BRILHO_GLOBAL,
                            auto_player_colors=True)), origem="regua")
        registro = get_identity_registry()
        registro.sync_connected(UNIQS)
        registro.liberar_as_lampadas()
        # SEM VARRER O /dev/input DELA: o construtor do backend procura o
        # DualSense abrindo cada `event*` da máquina, e a luz não passa por ali.
        # É o `_null_evdev` de `test_backend_no_device_resilient.py`, com um
        # caminho que não existe no lugar do `None` que dispara a varredura.
        from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

        leitor = EvdevReader(device_path=raiz / "sem-evdev")
        leitor._device_path = None
        self.ctl = bp.PyDualSenseController(evdev_reader=leitor)
        self.ctl._handles = {m: _handle_falso() for m in MACS}
        self.ctl._sysfs = {m: _no(raiz, n) for n, m in enumerate(MACS, start=1)}
        self.ctl.set_auto_output_provider(make_auto_output_provider(registro))
        # Sem jogo: a camada GAME fica fora do merge.
        self.ctl.set_game_authority_provider(lambda: "daemon")
        store = StateStore()
        store.update_controller_state(ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb"))
        self.pm = ProfileManager(controller=self.ctl, store=store)
        self._perfil = lambda: load_profile(NOME)
        self.pm.apply(self._perfil(), origin="system")
        self.server = IpcServer(controller=self.ctl, store=store,
                                profile_manager=self.pm,
                                socket_path=raiz / "nao-abre.sock")
        self.ponte = PonteDoDaemon(self)
        # «TODOS» OU UM CONTROLE SÓ, no seletor de cima, pelo handler real. A
        # 04 não escolhe pela fita (`monta.ABAS_QUE_ESCOLHEM`), mas o daemon
        # guarda o alvo — e os gestos desta aba levam o `uniq` da coluna.
        self.alvo = alvo
        self.rodar(self.server._handle_controller_target_set(
            {"index": None} if alvo == "todos" else {"uniq": UNIQS[1]}))
        # ELA ESCOLHE O LARANJA NO P2 E O CIANO NO P3, pelo gesto da aba.
        self.clicar_no_tom(2, LARANJA)
        self.clicar_no_tom(3, CIANO)

    def rodar(self, corotina: Any) -> Any:
        return self.loop.run_until_complete(corotina)

    def fechar(self) -> None:
        self.loop.close()

    def reaplicar_o_perfil(self) -> None:
        """O perfil do disco aplicado de novo — replug, troca de perfil, boot."""
        self.pm.apply(self._perfil(), origin="system")

    def publicado(self) -> list[dict[str, Any]]:
        """Os controles como o `state_full` os publica AGORA, com a luz assentada.

        A luz sai do `_lightbar_for_uniq` REAL. O cache de 1 s dele é zerado
        aqui: o tique ATRASADO é o que o teste guarda de um `publicado()`
        anterior, e não o que o relógio decide.
        """
        from hefesto_dualsense4unix.daemon import ipc_handlers as ih

        self.server._lightbar_read_cache = {}
        nos: dict[str, Any] = {}
        escritos: dict[str, Any] = {}
        for chave, no in self.ctl._sysfs.items():
            u = ih._norm_uniq(chave)
            if u is not None and no is not None:
                nos[u] = no
        for chave, cru in (getattr(self.ctl, "_sysfs_written", None) or {}).items():
            u = ih._norm_uniq(chave)
            rgb = ih._rgb_or_none(cru)
            if u is not None and rgb is not None:
                escritos[u] = rgb
        saida = []
        for i, (u, via) in enumerate(zip(UNIQS, VIAS, strict=True)):
            rgb, aceso, fonte = self.server._lightbar_for_uniq(u, nos, escritos)
            saida.append({
                "uniq": u, "index": i, "player": i + 1, "player_slot": i + 1,
                "connected": True, "is_primary": i == 0, "transport": via,
                "lightbar_rgb": list(rgb) if rgb is not None else None,
                "lightbar_on": aceso, "lightbar_source": fonte,
                "lightbar_disputada": False,
            })
        return saida

    def ctx(self, conectados: list[dict[str, Any]] | None = None) -> Any:
        conectados = self.publicado() if conectados is None else conectados
        mesa = [{"pref": p, "uniq": u, "jogador": n, "cor": "white",
                 "nome": "DualSense", "via": v.upper(), "transporte": v}
                for n, (p, u, v) in enumerate(zip(PREFS, UNIQS, VIAS, strict=True), 1)]
        return self.pac.Contexto(
            state={"active_profile": NOME, "controllers": conectados,
                   "output_target_index": None if self.alvo == "todos" else 1},
            mesa=mesa, conectados=conectados, estados={})

    def gravar_o_brilho(self, n: int, fracao: float) -> None:
        """O brilho do P<n> gravado no perfil por FORA do trilho — a outra porta do disco."""
        from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile

        prof = load_profile(NOME)
        chave = self.a04.chave_do_override(UNIQS[n - 1])
        dele = prof.controllers[chave]
        leds = dele.leds.model_copy(update={"lightbar_brightness": fracao})
        save_profile(prof.model_copy(update={"controllers": {
            **prof.controllers, chave: dele.model_copy(update={"leds": leds})}}),
            origem="regua")

    def clicar_no_tom(self, n: int, rgb: tuple[int, int, int]) -> None:
        self.a04.cor(self.ctx(), {"uniq": UNIQS[n - 1], "hex": _hexa(rgb)[1:],
                                  "tipo": "button", "evento": "click"}, self.ponte)

    def soltar(self, n: int, pct: int,
               tique: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        """Ela solta o trilho do P<n> em `pct` — o `change`, que é o gesto.

        Devolve o tique que a tela tinha na mão no instante do gesto: é a luz
        que o daemon ainda publica enquanto o disco já diz o brilho novo.
        """
        antes = self.publicado() if tique is None else tique
        self.a04.brilho(self.ctx(antes), {"uniq": UNIQS[n - 1], "valor": str(pct),
                                          "tipo": "input", "evento": "change"},
                        self.ponte)
        return antes

    def fora_do_lugar(self, conectados: list[dict[str, Any]] | None = None) -> list[str]:
        """Cada marca que saiu do lugar neste tique — vazio é a regra dela cumprida."""
        pacote = self.a04.pacote(self.ctx(conectados))
        guia = [_hexa(t) for t in self.a04.tons_da_guia()]
        erros = []
        for n, u in enumerate(UNIQS, start=1):
            coluna = pacote["colunas"][u]
            casas = re.findall(r'<button class="([^"]*)"', coluna["tons"])
            assert len(casas) == len(guia), "a fileira não tem as casas da guia"
            borda = [guia[i] for i, c in enumerate(casas) if "on" in c.split()]
            xis = sorted(guia[i] for i, c in enumerate(casas) if "tomado" in c.split())
            dele = _hexa(COR_DELE[n])
            dos_outros = sorted(_hexa(COR_DELE[k]) for k in COR_DELE if k != n)
            if borda != [dele]:
                erros.append(f"P{n}: a borda está em {borda}, e a cor dele é {dele}")
            if xis != dos_outros:
                erros.append(f"P{n}: o X está em {xis}, e as dos outros são {dos_outros}")
            if coluna["hex"] != dele:
                erros.append(f"P{n}: a caixa diz {coluna['hex']}, e a cor dele é {dele}")
        return erros


@pytest.fixture
def mesa_de(tmp_path, pac, a04):
    feitas: list[Mesa] = []

    def montar(alvo: str = "todos") -> Mesa:
        m = Mesa(tmp_path / f"mesa-{len(feitas)}", pac, a04, alvo=alvo)
        feitas.append(m)
        return m

    yield montar
    for m in feitas:
        m.fechar()


# ---------------------------------------------------------------------------
# 1. A mesa assentada — o ponto de partida de toda régua abaixo
# ---------------------------------------------------------------------------
def test_a_mesa_nasce_com_as_quatro_marcas_no_lugar(mesa_de):
    """Sem gesto de brilho nenhum, as quatro fileiras já cumprem a regra.

    Se esta reprova, as de baixo mediriam outra mesa: é a precondição que o
    piloto passou a conferir no disco depois de medir uma mesa sem as cores
    (o `cor` estourou os 250 ms da ponte com a máquina carregada). Ela não tem
    mordida própria — a mesa assentada a 82% já casava um tom só antes da cura.
    """
    mesa = mesa_de()
    assert mesa.fora_do_lugar() == []


# ---------------------------------------------------------------------------
# 2. Soltar o trilho — os quatro, USB e BT, «Todos» e um controle só
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("alvo", ["todos", "um"])
@pytest.mark.parametrize("n", [1, 2, 3, 4], ids=IDS)
def test_soltar_o_brilho_nao_tira_marca_de_ninguem(mesa_de, n, alvo):
    """Cada soltar do trilho, no tique ATRASADO e no assentado.

    O tique atrasado é o do defeito: o gesto grava o brilho novo no disco e só
    DEPOIS manda o `led.set`, e o `state_full` guarda a leitura do nó por 1 s —
    por meio segundo a tela invertia a luz velha com o brilho novo, nenhum tom
    casava, e a marca daquele controle sumia das quatro fileiras.

    **A MORDIDA:** devolva a `_a_cor_de_agora` a leitura só pela luz
    (`cor_escolhida(cor_do_swatch(c), brilho)`, com a cor do número como
    queda) e o tique atrasado reprova nos quatro.
    """
    mesa = mesa_de(alvo)
    for pct in (50, 30, 100, 64):
        atrasado = mesa.soltar(n, pct)
        assert mesa.fora_do_lugar(atrasado) == [], (
            f"P{n} solto em {pct}%, a luz ainda a de antes")
        assert mesa.fora_do_lugar() == [], f"P{n} solto em {pct}%, luz assentada"


@pytest.mark.parametrize("n", [1, 2, 3, 4], ids=IDS)
def test_soltar_duas_vezes_antes_de_a_luz_assentar(mesa_de, n):
    """O arraste que chega ao Python: dois `change` com a luz de antes dos dois.

    A luz publicada fica DOIS brilhos atrás do disco. Uma cura que só
    desfizesse o último passo (o brilho de antes do gesto) erraria aqui.

    **AS MORDIDAS:** a do soltar, ou a borda voltando a ler a luz
    (`pedida = cor_escolhida(crua, b)` no `pacote`, no lugar de `cor_dele`).
    """
    mesa = mesa_de()
    antes_dos_dois = mesa.soltar(n, 60)
    mesa.soltar(n, 35, tique=antes_dos_dois)
    assert mesa.fora_do_lugar(antes_dos_dois) == []
    assert mesa.fora_do_lugar() == []


# ---------------------------------------------------------------------------
# 3. O zero e a volta dele
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("n", [1, 2, 3, 4], ids=IDS)
def test_a_zero_a_marca_fica_onde_estava(mesa_de, n):
    """A 0% os catorze tons acendem preto, e a luz não diz mais tom nenhum.

    Brilho não é cor: o controle apagado pelo trilho continua sendo o laranja,
    o ciano, o do número. A leitura velha devolvia o PRIMEIRO tom que casava,
    o `#0000FF` — a borda pulava para o azul e o P1 ganhava um X na própria cor.

    **A MORDIDA:** arranque as DUAS guardas de `_o_tom_que_acende` — o
    `if alvo == (0, 0, 0)` e o `len(casados) == 1` — e esta reprova do P2 ao
    P4 com a borda no azul (o P1 passa por coincidência: o azul é a cor dele).
    Uma só não basta, porque cada uma cobre o 0% sozinha.
    """
    mesa = mesa_de()
    atrasado = mesa.soltar(n, 0)
    assert mesa.fora_do_lugar(atrasado) == []
    assert mesa.fora_do_lugar() == []


@pytest.mark.parametrize("n", [1, 2, 3, 4], ids=IDS)
def test_subir_do_zero_acende_a_cor_dele(mesa_de, n):
    """Do 0% para 70%: o `led.set` leva a cor DELE, e a coluna não fica preta.

    Duas medidas do piloto numa régua só. A luz de antes do gesto é o preto:
    a leitura velha devolvia o azul (o primeiro tom) e o gesto o reenviava — o
    P4 voltava aceso na cor do P1. E, com a primeira cura, a coluna virava
    PRETA no tique atrasado: o `#000000` é tom da casa e, a 70%, é o único que
    acende preto.

    **AS MORDIDAS:** tire o `if alvo == (0, 0, 0): return None` de
    `_o_tom_que_acende` e o tique atrasado reprova com a borda fora da guia e
    a caixa em `#000000`; troque o `_a_cor_de_agora` do `alvo` do gesto
    `brilho` pela luz invertida e o P1 e o P4 saem do 0% com o preto.
    """
    mesa = mesa_de()
    mesa.soltar(n, 0)
    atrasado = mesa.soltar(n, 70)
    enviado = mesa.ponte.enviados[-1]
    assert tuple(enviado["rgb"]) == COR_DELE[n], (
        f"P{n} saiu do 0% com {_hexa(enviado['rgb'])}, e a cor dele é "
        f"{_hexa(COR_DELE[n])}")
    assert enviado["brightness"] == pytest.approx(0.70)
    assert mesa.fora_do_lugar(atrasado) == []
    assert mesa.fora_do_lugar() == []


def test_abaixo_de_um_por_cento_a_luz_nao_escolhe_o_primeiro_tom(mesa_de):
    """De 0,4% a 0,7%, o vermelho, o rosa e o laranja acendem o mesmo `(1, 0, 0)`.

    O trilho não chega lá (anda de 1 em 1%), mas o disco chega. Com o P2 a
    0,5%, a luz dele casa com três tons, e a leitura que devolvia o primeiro
    da tabela diria que o P2 é VERMELHO — a cor do número 2 —, com o X laranja
    fora das outras três fileiras.

    **A MORDIDA:** faça `_o_tom_que_acende` devolver `casados[0]` sempre que
    houver casamento, e esta reprova com a borda do P2 no vermelho.
    """
    mesa = mesa_de()
    mesa.gravar_o_brilho(2, 0.005)
    mesa.ponte.led_set_detalhado(LARANJA, brightness=0.005, uniq=UNIQS[1])
    luz = {c["uniq"]: c["lightbar_rgb"] for c in mesa.publicado()}
    assert luz[UNIQS[1]] == [1, 0, 0], (
        f"a régua precisa da luz que casa com três tons, e o P2 acende {luz[UNIQS[1]]}")
    assert mesa.fora_do_lugar() == []


def test_a_zero_o_vizinho_nao_toma_a_cor_de_quem_apagou(mesa_de):
    """O X a 0% não é enfeite: o gesto `cor` do P3 recusa o laranja do P2.

    Sem a marca, o laranja pareceria livre e o P3 o tomaria — e o P2, ao subir
    o trilho, voltaria laranja também: duas peças da mesma cor, que é a regra
    dela que o X existe para cumprir (`D-DUAS-PECAS-NUNCA-TEM-A-MESMA-COR`).

    **A MORDIDA:** a do teste do zero — sem as duas guardas, o P2 a 0% "é"
    azul, e o laranja passa.
    """
    mesa = mesa_de()
    mesa.soltar(2, 0)
    with pytest.raises(RuntimeError) as recusa:
        mesa.clicar_no_tom(3, LARANJA)
    assert "P2" in str(recusa.value), f"a recusa não diz de quem é: {recusa.value}"


# ---------------------------------------------------------------------------
# 4. O perfil reaplicado — a luz que o daemon refaz a partir do disco
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("n", [1, 2, 3, 4], ids=IDS)
def test_o_perfil_reaplicado_nao_tira_a_marca(mesa_de, n):
    """Replug, troca de perfil, boot: o daemon refaz a luz pelo disco.

    O brilho por controle que o trilho gravou volta pela porta do perfil, e a
    luz que sai dali não precisa bater com a conta da aba (o override que só
    traz brilho é aplicado como FATOR por cima da cor já escalada). A marca não
    pode depender de a conta bater.

    **AS MORDIDAS:** as mesmas de soltar duas vezes.
    """
    mesa = mesa_de()
    mesa.soltar(n, 30)
    mesa.reaplicar_o_perfil()
    assert mesa.fora_do_lugar() == []
    mesa.soltar(n, 0)
    mesa.reaplicar_o_perfil()
    assert mesa.fora_do_lugar() == []
