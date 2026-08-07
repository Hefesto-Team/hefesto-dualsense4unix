"""LUGAR-À-MESA-01 — dois aparelhos NUNCA exibem o mesmo número de jogador.

O teste que a medição dela de **06/08/2026, 22h40** exigiu, e que não existia:

> *"a `E0` ganha um critério a mais: não basta parar de afirmar o que não se
> entrega — é preciso garantir que **dois aparelhos nunca acendam o mesmo
> número**, inclusive quando um deles é o nosso próprio vpad. Um teste que
> conte LEDs acesos por número fecha isso, e não existe hoje."*

## O que conta como "exibir um número"

Duas superfícies, e a pessoa lê as duas como a mesma coisa:

- **a lâmpada**, no plástico — a barra branca do DualSense
  (`core/sysfs_leds.py`), a barra verde do Nintendo e a lightbar RGB do 8BitDo
  em modo DS4 (`core/external_leds.py`);
- **o nome do vpad**, que é o que o JOGO lê — `DualSense Wireless Controller
  (Hefesto P1)` (`integrations/uhid_gamepad.py`). O vpad não tem lâmpada, mas
  anuncia um número de jogador em texto, para o jogo e para a lista do sistema.

Por isso este arquivo escreve as lâmpadas de verdade, num `/sys/class/leds`
FALSO, com os escritores de produção, e depois **lê de volta e conta quantos
aparelhos ficaram em cada número** — é a última polegada, e é onde a numeração
única já morreu antes (R-25: o slot 7 acendia o mesmo padrão do 4).

## A única partilha PERMITIDA, e ela é declarada

O vpad de um jogador e o controle físico que ele espelha são **o mesmo
jogador** — o vpad existe para ser o aparelho daquela pessoa dentro do jogo
(VPAD-03). Esses dois não só PODEM exibir o mesmo número: eles TÊM de exibir,
senão a luz no plástico contradiz o nome que o jogo mostra, que é o par que ela
usa para saber quem é quem.

Logo o invariante tem duas metades, e as duas estão aqui:

1. **entre jogadores diferentes, o número é único** (nenhum par repete);
2. **dentro do mesmo jogador, o número é o MESMO** (a lâmpada casa com o nome).

## As duas contabilidades que podem discordar

- o número da **lâmpada** sai da fila única de identidade —
  `CoopManager._numero_exibido` (`daemon/subsystems/coop.py`) para o DualSense
  e `ExternalIdentityRegistry.slot_for`
  (`daemon/subsystems/external_identity.py`) para o externo, ambos "colocação
  entre os PRESENTES";
- o número do **jogo** sai de `CoopManager.player_indexes()`
  (`daemon/subsystems/coop.py`): 1 no primário eleito pelo backend, 2..N nos
  secundários. É ele que vira o `player` do vpad e o nome `Hefesto P{n}`.

São funções diferentes do mesmo MAC, e **nada obriga as duas a concordarem** —
é essa a fresta que os casos com `xfail` abaixo abrem.

Nenhum endereço real: todos os aparelhos usam a faixa forjada `aa:bb:cc:…`
(ver o comentário das constantes).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from hefesto_dualsense4unix.core import external_leds, sysfs_leds
from hefesto_dualsense4unix.core.led_control import player_led_pattern, player_slot_color
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
    ExternalIdentityRegistry,
    ExternalLedSync,
)
from hefesto_dualsense4unix.daemon.subsystems.identity import ControllerIdentityRegistry
from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense

# --- os aparelhos da mesa dela, mascarados ---------------------------------

#: Todos na faixa `aa:bb:cc:...`, que é o placeholder canônico de fixture
#: desta casa. As OUIs públicas dos fabricantes (Nintendo, 8BitDo) NÃO entram
#: aqui de propósito: `tests/unit/test_anonimato_de_fixtures.py` trava os MACs
#: de teste por ALLOWLIST de faixas forjadas, e afrouxá-la para caber uma OUI
#: real seria abrir a porta pela qual um endereço de verdade entra depois.
#: Nada neste arquivo depende da OUI — quem numera olha a fila, não o
#: fabricante.
#:
#: Os dois DualSense (o de `rank=1` estava DESLIGADO na medição das 22h40).
DS_DESLIGADO = "aa:bb:cc:00:00:01"
DS_LIGADO = "aa:bb:cc:00:00:02"
#: Pro Controller Nintendo genuíno — barra VERDE de player (padrão Switch).
PRO = "aa:bb:cc:00:00:11"
#: 8BitDo em modo PS4 — lightbar RGB, sem barra de player nenhuma.
BITDO = "aa:bb:cc:00:00:12"


# --- o /sys/class/leds falso, e os escritores/leitores REAIS ---------------


@dataclass
class Lampada:
    """Uma barra de LEDs no sysfs falso — sabe se acender e se ler.

    ``especie`` decide QUAL escritor de produção governa a lâmpada, e as três
    são diferentes de verdade (é o achado da sprint: "LED de jogador 3 no
    8BitDo" é impreciso — o que acende lá é a COR do jogador 3):

    - ``dualsense`` — 5 LEDs brancos + o nó ``:rgb:indicator`` que
      `sysfs_leds.discover()` usa para achar o dono pelo MAC;
    - ``nintendo`` — 4 LEDs verdes + o azul ``player-5`` (o bit "+5" do R-25);
    - ``ds4`` — lightbar RGB (``:red``/``:green``/``:blue``/``:global``).
    """

    nome: str
    especie: str
    identidade: str
    prefixo: str
    _raiz: Path = field(repr=False, default=Path())

    # -- construção do sysfs falso ----------------------------------------

    def criar(self, raiz: Path) -> None:
        self._raiz = raiz
        leds = raiz / "leds"
        if self.especie == "dualsense":
            # `discover()` resolve o dono por realpath do :rgb:indicator ->
            # .../<HID>/leds/<prefixo>:rgb:indicator, e lê o MAC do `uevent`
            # do <HID>. O sysfs falso tem de ter essa forma exata.
            hid = raiz / "devices" / self.prefixo
            (hid / "leds" / f"{self.prefixo}:rgb:indicator").mkdir(parents=True)
            (hid / "uevent").write_text(
                f"HID_UNIQ={self.identidade}\n", encoding="utf-8"
            )
            os.symlink(
                hid / "leds" / f"{self.prefixo}:rgb:indicator",
                leds / f"{self.prefixo}:rgb:indicator",
            )
            for i in range(1, 6):
                (leds / f"{self.prefixo}:white:player-{i}").mkdir()
        elif self.especie == "nintendo":
            for i in range(1, 5):
                alvo = leds / f"{self.prefixo}:green:player-{i}" / "brightness"
                alvo.parent.mkdir()
                alvo.write_text("0", encoding="ascii")
            azul = leds / f"{self.prefixo}:blue:player-5" / "brightness"
            azul.parent.mkdir()
            azul.write_text("0", encoding="ascii")
        elif self.especie == "ds4":
            for cor in ("red", "green", "blue", "global"):
                alvo = leds / f"{self.prefixo}:{cor}" / "brightness"
                alvo.parent.mkdir()
                alvo.write_text("0", encoding="ascii")
        else:  # pragma: no cover - erro de escrita do teste
            raise AssertionError(f"espécie de lâmpada desconhecida: {self.especie}")

    # -- escrita: os escritores de PRODUÇÃO -------------------------------

    def acender(self, numero: int) -> None:
        raiz = str(self._raiz / "leds")
        if self.especie == "dualsense":
            nodes = sysfs_leds.discover()
            node = nodes[sysfs_leds.norm_mac(self.identidade) or ""]
            assert node.set_players(player_led_pattern(numero))
        elif self.especie == "nintendo":
            assert external_leds.write_player_number(self.prefixo, numero, raiz)
        else:
            assert external_leds.write_lightbar_slot(self.prefixo, numero, raiz)

    # -- leitura: o número que a lâmpada EXIBE ----------------------------

    def numero_aceso(self) -> int | None:
        """Decodifica o número lendo os nós — ``None`` = padrão de ninguém."""
        raiz = str(self._raiz / "leds")
        if self.especie == "dualsense":
            nodes = sysfs_leds.discover()
            bits = nodes[sysfs_leds.norm_mac(self.identidade) or ""].get_players()
            if bits is None:
                return None
            for n in range(1, 9):
                if tuple(bits) == player_led_pattern(n):
                    return n
            return None
        if self.especie == "nintendo":
            lido = external_leds.read_player_pattern(self.prefixo, raiz)
            return lido if isinstance(lido, int) and lido >= 1 else None
        cor = tuple(
            int((self._raiz / "leds" / f"{self.prefixo}:{c}" / "brightness").read_text())
            for c in ("red", "green", "blue")
        )
        for n in range(1, 9):
            if cor == player_slot_color(n):
                return n
        return None


@dataclass
class Aparelho:
    """Um aparelho da mesa: o que ele é, de quem é, e como ele exibe número.

    ``jogador`` é a IDENTIDADE DO JOGADOR, não o número: o vpad de alguém e o
    controle físico que ele espelha compartilham a mesma string, e é isso que
    autoriza os dois a exibirem o mesmo número (e obriga, ver o módulo). Um
    externo é jogador de ninguém — cada um recebe uma string própria, então
    ele nunca pode dividir número com quem quer que seja.
    """

    nome: str
    jogador: str
    lampada: Lampada | None = None
    vpad: UhidDualSense | None = None


@pytest.fixture
def raiz_leds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Um `/sys/class/leds` só deste teste, para os DOIS módulos de escrita."""
    (tmp_path / "leds").mkdir()
    monkeypatch.setattr(sysfs_leds, "LEDS_ROOT", str(tmp_path / "leds"))
    monkeypatch.setattr(external_leds, "LEDS_ROOT", str(tmp_path / "leds"))
    return tmp_path


# --- a fiação REAL das duas contabilidades ---------------------------------


class _ControllerFalso:
    """Só o que o co-op lê do backend: quem é o primário (`primary_uniq`)."""

    def __init__(self, primary: str) -> None:
        self.primary_uniq = primary


class _DaemonFalso:
    """Dublê de APARELHO, não de lógica: os registros abaixo são os reais."""

    def __init__(self, registro: ControllerIdentityRegistry, primary: str) -> None:
        self.identity_registry = registro
        self.controller = _ControllerFalso(primary)


@dataclass
class Mesa:
    """A mesa inteira: registros reais + as lâmpadas + os vpads."""

    ds: ControllerIdentityRegistry
    ext: ExternalIdentityRegistry
    sync: ExternalLedSync
    coop: CoopManager
    aparelhos: list[Aparelho] = field(default_factory=list)

    def numeros_exibidos(self) -> dict[str, int | None]:
        """Nome do aparelho -> número que ele EXIBE (lâmpada ou nome do vpad)."""
        out: dict[str, int | None] = {}
        for ap in self.aparelhos:
            if ap.vpad is not None:
                out[ap.nome] = ap.vpad.player
            elif ap.lampada is not None:
                out[ap.nome] = ap.lampada.numero_aceso()
        return out


def montar_mesa(
    *,
    fila: list[tuple[str, str]],
    presentes: list[str],
    primario: str,
    secundarios: dict[str, int] | None = None,
    reserva_dos_externos: bool = True,
) -> Mesa:
    """Monta a mesa com os registros de produção, na ordem de chegada dada.

    ``fila`` é ``[(identidade, espécie)]`` na ordem em que os aparelhos
    apareceram pela PRIMEIRA vez — é assim que a fila real nasce, e é o que
    define o `rank` de cada um. ``presentes`` é quem está ligado AGORA.

    ``reserva_dos_externos`` liga o provider que o `lifecycle` fia no daemon
    real (`set_external_reserve_provider`): sem ele, um DualSense novo pode
    receber um lugar que um externo já detém. Fica parametrizável porque o
    `FakeController` roda sem ele — e um teste que só medisse o caminho fiado
    não veria a mesa de quem usa o outro.
    """
    ds = ControllerIdentityRegistry()
    ext = ExternalIdentityRegistry()
    daemon = _DaemonFalso(ds, primario)
    sync = ExternalLedSync.__new__(ExternalLedSync)
    sync._daemon = daemon
    sync._registry = ext
    # A ponte de PRESENÇA entre os dois registros, feita pelo código real.
    sync._wire_presence_providers()
    if reserva_dos_externos:
        ds.set_external_reserve_provider(lambda: set(ext.snapshot().values()))
    coop = CoopManager.__new__(CoopManager)
    coop._daemon = daemon
    coop._players = {}
    for identidade, especie in fila:
        if especie == "dualsense":
            ds.slot_for(identidade)
        else:
            ext.slot_for(identidade, reserve=sync._ds_reserve())
    ds.sync_connected([i for i, e in fila if e == "dualsense" and i in presentes])
    ext.sync_connected([i for i, e in fila if e != "dualsense" and i in presentes])
    mesa = Mesa(ds=ds, ext=ext, sync=sync, coop=coop)
    mesa.secundarios = dict(secundarios or {})  # type: ignore[attr-defined]
    return mesa


def numero_da_lampada(mesa: Mesa, identidade: str, especie: str) -> int:
    """O número que o daemon MANDA acender neste aparelho, código real."""
    if especie == "dualsense":
        usados: set[int] = set()
        # `_numero_exibido` é a função que o co-op usa para escolher o padrão
        # da barra — o `fallback` só vale sem registro, e aqui há registro.
        return mesa.coop._numero_exibido(identidade, 1, usados)
    return mesa.ext.slot_for(identidade, reserve=mesa.sync._ds_reserve()) or 0


def conferir_sem_repetir(mesa: Mesa) -> None:
    """O invariante inteiro, nas duas metades (ver o topo do módulo).

    A metade 1 varre APARELHO por aparelho, e não um representante por
    jogador: com um grupo internamente incoerente (o caso da luz que discorda
    do nome), escolher um representante esconderia a colisão do outro membro —
    foi assim que a primeira versão desta função deixou o cenário do Pro no
    lugar 1 passar quando a metade 2 estava arrancada.
    """
    numeros = mesa.numeros_exibidos()
    # metade 1: cada número tem UM dono. Repetir só é permitido entre
    # aparelhos do MESMO jogador (o vpad e o físico que ele espelha).
    donos: dict[int | None, set[str]] = {}
    for ap in mesa.aparelhos:
        donos.setdefault(numeros[ap.nome], set()).add(ap.jogador)
    for numero, jogadores in sorted(donos.items(), key=lambda par: par[0] or 0):
        assert len(jogadores) == 1, (
            f"dois jogadores exibem o número {numero}: {sorted(jogadores)} "
            f"(mesa inteira: {numeros})"
        )
    # metade 2: dentro do mesmo jogador, o número é o MESMO.
    por_jogador: dict[str, dict[str, int | None]] = {}
    for ap in mesa.aparelhos:
        por_jogador.setdefault(ap.jogador, {})[ap.nome] = numeros[ap.nome]
    for jogador, aparelhos in por_jogador.items():
        assert len(set(aparelhos.values())) == 1, (
            f"o jogador {jogador} exibe números diferentes em aparelhos seus: "
            f"{aparelhos} — a lâmpada no plástico contradiz o nome que o jogo lê"
        )


# --- os cenários -----------------------------------------------------------


def _mesa_de_06_08(raiz: Path, *, com_vpad: bool) -> Mesa:
    """A mesa medida em 06/08/2026, 22h40 — a fila do `controllers.json` dela.

    `rank` 1 e 2 são os dois DualSense (o 1 estava DESLIGADO), 3 é o Pro
    Controller e 4 é o 8BitDo em modo PS4. Presentes: um DualSense e os dois
    externos.
    """
    mesa = montar_mesa(
        fila=[
            (DS_DESLIGADO, "dualsense"),
            (DS_LIGADO, "dualsense"),
            (PRO, "externo"),
            (BITDO, "externo"),
        ],
        presentes=[DS_LIGADO, PRO, BITDO],
        primario=DS_LIGADO,
    )
    lampadas = [
        ("DualSense físico", DS_LIGADO, "dualsense", "0005:054C:0CE6.0006"),
        ("Pro Controller", PRO, "nintendo", "0005:057E:2009.0007"),
        ("8BitDo (modo PS4)", BITDO, "ds4", "input42"),
    ]
    for nome, identidade, especie, prefixo in lampadas:
        lamp = Lampada(
            nome=nome, especie=especie, identidade=identidade, prefixo=prefixo
        )
        lamp.criar(raiz)
        especie_fila = "dualsense" if especie == "dualsense" else "externo"
        lamp.acender(numero_da_lampada(mesa, identidade, especie_fila))
        mesa.aparelhos.append(
            Aparelho(
                nome=nome,
                # o físico do P1 e o vpad do P1 são o MESMO jogador; cada
                # externo é jogador de ninguém, logo é um grupo só dele.
                jogador="jogador-1" if especie == "dualsense" else f"ninguem:{nome}",
                lampada=lamp,
            )
        )
    if com_vpad:
        mesa.aparelhos.append(
            Aparelho(
                nome="vpad Hefesto P1",
                jogador="jogador-1",
                vpad=UhidDualSense(player=1),
            )
        )
    return mesa


class TestAMesaMedidaEm0608:
    """O cenário exato das 22h40 — e ele tem de continuar sem repetir."""

    def test_os_numeros_batem_com_o_journal_dela(self, raiz_leds: Path) -> None:
        """Ancoragem: se estes três números mudarem, o resto não vale nada.

        A medição entregue: `external_led_written slot=2` no Pro e `slot=3` no
        8BitDo, e o DualSense presente acendendo o LED do meio da barra branca
        — que é o padrão canônico do número **1** (`player_led_pattern(1)` ==
        `(False, False, True, False, False)`, e o nó do meio chama-se
        `:white:player-3` no sysfs; o nome do NÓ não é o número do JOGADOR).
        """
        mesa = _mesa_de_06_08(raiz_leds, com_vpad=False)
        assert mesa.numeros_exibidos() == {
            "DualSense físico": 1,
            "Pro Controller": 2,
            "8BitDo (modo PS4)": 3,
        }

    def test_sem_o_vpad_ninguem_repete(self, raiz_leds: Path) -> None:
        conferir_sem_repetir(_mesa_de_06_08(raiz_leds, com_vpad=False))

    def test_com_o_vpad_na_conta_ninguem_repete(self, raiz_leds: Path) -> None:
        """O vpad P1 e o DualSense que ele espelha são o MESMO jogador.

        Os dois exibem 1 — e é assim que tem de ser. O que este teste prova é
        que o vpad ENTRA na conta sem colidir com o Pro (2) nem com o 8BitDo
        (3), que é a metade da medição das 22h40 que se sustenta.
        """
        conferir_sem_repetir(_mesa_de_06_08(raiz_leds, com_vpad=True))

    def test_a_lampada_do_p1_casa_com_o_nome_do_vpad(self, raiz_leds: Path) -> None:
        """O par que ela usa para saber quem é quem: a luz e o nome."""
        mesa = _mesa_de_06_08(raiz_leds, com_vpad=True)
        numeros = mesa.numeros_exibidos()
        assert numeros["vpad Hefesto P1"] == numeros["DualSense físico"]
        assert "Hefesto P1" in UhidDualSense(player=1).name


class TestOVpadEntraNaConta:
    """O vpad anuncia número em TEXTO, e o texto tem de ser o mesmo da luz."""

    @pytest.mark.parametrize("jogador", [1, 2, 3, 4])
    def test_o_nome_do_vpad_anuncia_o_proprio_numero(self, jogador: int) -> None:
        """`player` e o nome não podem divergir DENTRO do mesmo objeto."""
        vpad = UhidDualSense(player=jogador)
        assert f"Hefesto P{jogador}" in vpad.name
        assert vpad.mac == f"02:fe:00:00:00:{jogador:02x}"


#: A razão do `xfail` das duas classes abaixo, escrita uma vez só porque é a
#: MESMA fresta vista de dois ângulos: o número da LÂMPADA sai da fila de
#: identidade (ordem de primeira aparição, persistida em `controllers.json`) e
#: o número do JOGO sai de `player_indexes()` (primário eleito pelo backend +
#: `player_index` do co-op). Ninguém casa os dois espaços, e o vpad — que só
#: existe no segundo — carrega o número no NOME.
#:
#: Não se cura aqui por ordem expressa: a cura pode tocar a adoção dos
#: externos, que ela ADIOU até a máscara por controle existir (decisão dela de
#: 07/08/2026, resposta 3 — `docs/process/2026-08-07-DECISOES-DELA-as-onze-
#: respostas-do-painel.md`). O teste fica VERMELHO e declarado.
RAZAO_XFAIL = (
    "LUGAR-À-MESA-01: a fila da lâmpada e o índice do jogo são espaços de "
    "numeração independentes, e o vpad só vive no segundo. Cura NÃO "
    "autorizada aqui (decisão dela de 07/08: os externos só ganham lugar "
    "próprio depois da máscara por controle)."
)


@pytest.mark.xfail(strict=True, reason=RAZAO_XFAIL)
class TestExternoNaFrenteNaFila:
    """O Pro chega ao PC antes de qualquer DualSense — e fica com o lugar 1.

    Rota medida uma vez e registrada no próprio código
    (`ExternalLedSync._ds_reserve`, R-24: *"o Pro Nintendo USB abocanhava o
    slot 1 e os dois DualSense nasciam 2 e 3 — medido no `controllers.json`
    dela"*). A cura daquela vez foi de ORDEM (o `sync_connected` do lado
    DualSense passou a atribuir antes do tick dos externos), e ela não alcança
    quem liga o PC com só o Pro plugado: o externo recebe o lugar 1 sem
    ninguém para disputá-lo, e o lugar na fila é PERMANENTE por promessa (D2).

    O que sai disso, com o código de hoje:

    - o Pro acende **1** no plástico;
    - o DualSense acende **2**;
    - o jogo chama o DualSense de **P1**, e o vpad dele se apresenta
      `DualSense Wireless Controller (Hefesto P1)`.

    Dois aparelhos anunciando o jogador 1, e nenhum dos dois é do outro.

    **GRAU: SUSPEITA COM MECANISMO, forte** — o mecanismo está em código e a
    fila ancestral foi MEDIDA; a mesa exata não foi reproduzida na máquina
    dela.
    """

    def test_o_vpad_e_o_pro_disputam_o_numero_1(self, raiz_leds: Path) -> None:
        mesa = montar_mesa(
            fila=[(PRO, "externo"), (DS_LIGADO, "dualsense")],
            presentes=[PRO, DS_LIGADO],
            primario=DS_LIGADO,
        )
        for nome, identidade, especie, prefixo in (
            ("Pro Controller", PRO, "nintendo", "0005:057E:2009.0007"),
            ("DualSense físico", DS_LIGADO, "dualsense", "0005:054C:0CE6.0006"),
        ):
            lamp = Lampada(
                nome=nome, especie=especie, identidade=identidade, prefixo=prefixo
            )
            lamp.criar(raiz_leds)
            especie_fila = "dualsense" if especie == "dualsense" else "externo"
            lamp.acender(numero_da_lampada(mesa, identidade, especie_fila))
            mesa.aparelhos.append(
                Aparelho(
                    nome=nome,
                    jogador="jogador-1" if especie == "dualsense" else "ninguem:pro",
                    lampada=lamp,
                )
            )
        mesa.aparelhos.append(
            Aparelho(
                nome="jogo (vpad Hefesto P1)",
                jogador="jogador-1",
                vpad=UhidDualSense(player=1),
            )
        )
        # O retrato do que o código de HOJE produz — fica escrito para que a
        # cura, quando vier, mostre exatamente o que mudou.
        assert mesa.numeros_exibidos() == {
            "Pro Controller": 1,
            "DualSense físico": 2,
            "jogo (vpad Hefesto P1)": 1,
        }
        conferir_sem_repetir(mesa)


@pytest.mark.xfail(strict=True, reason=RAZAO_XFAIL)
class TestPrimarioQueNaoEOPrimeiroDaFila:
    """Dois DualSense, e o backend elege como primário o SEGUNDO da fila.

    `PyDualSenseController` escolhe o primário com
    ``self._primary_key = next(iter(self._handles), None)``
    (`core/backend_pydualsense.py`) — a ordem de ENUMERAÇÃO do hidapi. A fila
    de identidade é a ordem de PRIMEIRA APARIÇÃO, persistida entre boots
    (`daemon/subsystems/identity.py`). São duas ordens diferentes, e um replug
    basta para separá-las.

    Quando separam, os números não se repetem por acaso — eles TROCAM de dono:
    quem o jogo chama de P1 acende 2 no plástico, e quem o jogo chama de P2
    acende 1. É a queixa "nunca sei qual é qual" na forma mais cruel, porque
    as duas superfícies estão certas cada uma no seu espaço.

    **GRAU: SUSPEITA COM MECANISMO** — o mecanismo é código lido; a divergência
    não foi observada ao vivo nesta mesa.
    """

    def test_a_luz_e_o_nome_trocam_de_dono(self, raiz_leds: Path) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.coop import _SecondaryPlayer

        mesa = montar_mesa(
            fila=[(DS_DESLIGADO, "dualsense"), (DS_LIGADO, "dualsense")],
            presentes=[DS_DESLIGADO, DS_LIGADO],
            primario=DS_LIGADO,  # o backend elegeu o SEGUNDO da fila
        )
        vpad_p2 = UhidDualSense(player=2)
        mesa.coop._players = {
            DS_DESLIGADO: _SecondaryPlayer(
                identity=DS_DESLIGADO,
                evdev_path="/dev/input/event0",
                reader=None,  # type: ignore[arg-type]
                player_index=2,
                vpad=vpad_p2,
            )
        }
        indices = mesa.coop.player_indexes()
        assert indices == {DS_LIGADO: 1, DS_DESLIGADO: 2}
        for nome, identidade, prefixo, jogador in (
            ("DualSense A", DS_DESLIGADO, "0005:054C:0CE6.0005", "jogador-2"),
            ("DualSense B", DS_LIGADO, "0005:054C:0CE6.0006", "jogador-1"),
        ):
            lamp = Lampada(
                nome=nome,
                especie="dualsense",
                identidade=identidade,
                prefixo=prefixo,
            )
            lamp.criar(raiz_leds)
            lamp.acender(numero_da_lampada(mesa, identidade, "dualsense"))
            mesa.aparelhos.append(Aparelho(nome=nome, jogador=jogador, lampada=lamp))
        mesa.aparelhos.append(
            Aparelho(
                nome="jogo (vpad Hefesto P1)",
                jogador="jogador-1",
                vpad=UhidDualSense(player=1),
            )
        )
        mesa.aparelhos.append(
            Aparelho(nome="jogo (vpad Hefesto P2)", jogador="jogador-2", vpad=vpad_p2)
        )
        # O retrato do código de hoje: a luz e o nome TROCADOS entre os dois.
        assert mesa.numeros_exibidos() == {
            "DualSense A": 1,
            "DualSense B": 2,
            "jogo (vpad Hefesto P1)": 1,
            "jogo (vpad Hefesto P2)": 2,
        }
        conferir_sem_repetir(mesa)


class TestOTesteMorde:
    """Prova que o invariante reprova quando a numeração de fato colide.

    Sem isto o arquivo inteiro seria decoração: um teste que só passa não
    mostra nada. Aqui a colisão é FORÇADA na lâmpada e na conta, e o
    invariante tem de gritar nas duas metades.
    """

    def test_dois_fisicos_no_mesmo_numero_reprovam(self, raiz_leds: Path) -> None:
        mesa = _mesa_de_06_08(raiz_leds, com_vpad=True)
        # O Pro passa a acender o mesmo número do DualSense presente.
        pro = next(a for a in mesa.aparelhos if a.nome == "Pro Controller")
        assert pro.lampada is not None
        pro.lampada.acender(1)
        with pytest.raises(AssertionError, match="dois jogadores exibem o número 1"):
            conferir_sem_repetir(mesa)

    def test_vpad_no_numero_de_outro_jogador_reprova(self, raiz_leds: Path) -> None:
        mesa = _mesa_de_06_08(raiz_leds, com_vpad=True)
        # O vpad do P1 nasce anunciando 3 — o número do 8BitDo na mesa.
        vpad = next(a for a in mesa.aparelhos if a.vpad is not None)
        vpad.vpad = UhidDualSense(player=3)
        with pytest.raises(AssertionError, match="dois jogadores exibem o número 3"):
            conferir_sem_repetir(mesa)

    def test_lampada_que_discorda_do_nome_reprova(self, raiz_leds: Path) -> None:
        mesa = _mesa_de_06_08(raiz_leds, com_vpad=True)
        fisico = next(a for a in mesa.aparelhos if a.nome == "DualSense físico")
        assert fisico.lampada is not None
        fisico.lampada.acender(4)
        with pytest.raises(AssertionError, match="números diferentes"):
            conferir_sem_repetir(mesa)
