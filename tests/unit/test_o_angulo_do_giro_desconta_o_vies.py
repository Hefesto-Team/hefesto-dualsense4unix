"""O ÂNGULO DO GIRO DESCONTA O VIÉS, EM TODO CAMINHO.

A sprint: A-CALIBRAR-GRAVA-O-ZERO-DESCONTA-EM-TODO-CAMINHO-E-CABE-A-940-PX-01.

O defeito medido em 08/10/2026: a velocidade (o analógico) e a inclinação já descontavam o
zero que o «Começar» da Calibrar guarda, mas o ÂNGULO do Modo mouse (a integral do giro cru
no leitor) passava sem desconto. O portão da velocidade já descontada esconde o defeito com
o controle PARADO, e ele aparece EM MOVIMENTO: cada tique que passa o portão leva
`viés x dt` junto, e virar para um lado e voltar deixa o cursor deslocado.

A cura é uma só, no roteador (`angulo_do_tique`, que já guarda o instante da drenagem
anterior): o primário, o Modo mouse e o co-op passam por `aplicar_o_movimento`, que é o
único chamador do ângulo.

AS RÉGUAS NÃO USAM O CONTROLE PARADO: ele dá zero pixel hoje (o portão da velocidade) e
passaria com a cura arrancada. Usam a ida e a volta.

MORDIDA (08/10/2026, devolvida): com o `angulo_do_tique` sem o desconto, a ida e a volta
sobram `2 x 1,5° x pixels_por_grau` e as réguas da soma reprovam.

Endereços: faixa SINTÉTICA da casa (``aa:bb:cc``).
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from hefesto_dualsense4unix.core import roteador_de_movimento as rot
from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.profiles.schema import ProfileMovimentoConfig

_P1, _P2 = "aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"
_GRAVIDADE = (0.0, 0.0, 1.0)
_TIQUE_S = 1.0 / 60.0
_GIRO_REAL = 30.0
_VIES = (0.0, 1.5, 0.0)


class _Mouse:
    """O mouse virtual: soma os pixels que o Hefesto mandaria ao cursor."""

    def __init__(self) -> None:
        self.x = 0.0
        self.y = 0.0

    def emit_gyro_move(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy


class _Hub:
    """O leitor: cada controle gira à velocidade `real + viés`, e o ângulo é a integral CRUA.

    É o que o `evdev_reader` faz: `consume_angulo` devolve o giro cru acumulado desde a
    última drenagem, sem saber do zero.
    """

    def __init__(self, vies: dict[str, tuple[float, float, float]]) -> None:
        self.vies = vies
        self.real: dict[str, float] = dict.fromkeys(vies, 0.0)
        self.acumulado: dict[str, list[float]] = {u: [0.0, 0.0, 0.0] for u in vies}

    def _cru(self, u: str) -> tuple[float, float, float]:
        v = self.vies[u]
        return (v[0], v[1] + self.real[u], v[2])

    def passar(self, segundos: float) -> None:
        for u in self.vies:
            for i, g in enumerate(self._cru(u)):
                self.acumulado[u][i] += g * segundos

    def aceleracao_do_movimento(self, _u: str) -> tuple[float, float, float]:
        return _GRAVIDADE

    def velocidade_do_movimento(self, u: str) -> tuple[float, float, float] | None:
        return self._cru(u) if u in self.vies else None

    def angulo_do_movimento(self, u: str) -> tuple[float, float, float] | None:
        if u not in self.vies:
            return None
        a = self.acumulado[u]
        self.acumulado[u] = [0.0, 0.0, 0.0]
        return (a[0], a[1], a[2])


class _Bancada:
    """Um relógio, um hub, o armazém do daemon e um mouse por controle."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, vies: dict[str, tuple[float, float, float]],
                 zeros: dict[str, tuple[float, float, float]],
                 na_navegacao: bool = False) -> None:
        self.agora = 1000.0
        monkeypatch.setattr(gp, "time", SimpleNamespace(monotonic=lambda: self.agora))
        monkeypatch.setattr(REGISTRO, "estado", lambda _u: SimpleNamespace(
            giroscopio=True, acelerometro=True))
        self.store = SimpleNamespace()
        # O perfil grava o cursor como `analogico_direito` (o destino «mouse» só existe no
        # arranjo montado): o primário recebe o arranjo já em «mouse», e a Navegação e o Modo
        # mouse o recebem do perfil e o levam ao cursor por `na_navegacao`.
        base = rot.montar(ProfileMovimentoConfig.model_validate(
            {"destino": rot.DESTINO_ANALOGICO_DIREITO}))
        self.na_navegacao = na_navegacao
        self.arranjo = base if na_navegacao else rot.para_o_cursor(base)
        rot.definir_ativo(self.store, self.arranjo)
        for u, z in zeros.items():
            rot.definir_o_zero(self.store, u, rot.ZeroDoControle(giro=z, gravidade=_GRAVIDADE))
        self.hub = _Hub(vies)
        self.mouses = {u: _Mouse() for u in vies}

    def tique(self, uniq: str) -> None:
        self.agora += _TIQUE_S
        self.hub.passar(_TIQUE_S)
        daemon = SimpleNamespace(_garantir_sensor_hub=lambda: self.hub, store=self.store,
                                 _mouse_device=self.mouses[uniq])
        gp.aplicar_o_movimento(daemon, self.arranjo, uniq=uniq, lx=128, ly=128, rx=128,
                               ry=128, botoes=frozenset(), na_navegacao=self.na_navegacao)

    def ida_e_volta(self, uniq: str) -> tuple[float, float]:
        """Um tique de aquecimento (o primeiro ângulo é descartado), um giro `+v` por 1 s e
        o `-v` por 1 s. Devolve os pixels da ida e a soma da ida e da volta."""
        self.tique(uniq)
        self.hub.real[uniq] = _GIRO_REAL
        for _ in range(60):
            self.tique(uniq)
        na_ida = self.mouses[uniq].x
        self.hub.real[uniq] = -_GIRO_REAL
        for _ in range(60):
            self.tique(uniq)
        return na_ida, self.mouses[uniq].x


@pytest.mark.parametrize("navegacao", [False, True], ids=["primário", "modo-mouse"])
def test_ida_e_volta_com_o_zero_guardado_devolve_o_cursor_ao_lugar(
        monkeypatch: pytest.MonkeyPatch, navegacao: bool) -> None:
    """O defeito: a soma sobrava `2 x 1,5° x pixels_por_grau` para o lado do viés."""
    b = _Bancada(monkeypatch, {_P1: _VIES}, {_P1: _VIES}, navegacao)
    ida, soma = b.ida_e_volta(_P1)
    assert abs(ida) > 100.0, f"a ida quase não andou ({ida}): a régua mede outra coisa"
    assert abs(soma) < 0.02 * abs(ida), (
        f"o cursor voltou deslocado {soma:.1f} px de {ida:.1f} px: o ângulo não desconta o zero")


@pytest.mark.parametrize("navegacao", [False, True], ids=["primário", "modo-mouse"])
def test_sem_zero_guardado_os_pixels_sao_os_de_hoje(
        monkeypatch: pytest.MonkeyPatch, navegacao: bool) -> None:
    """A cura só age em quem calibrou: sem zero o viés continua entrando, como antes."""
    b = _Bancada(monkeypatch, {_P1: _VIES}, {}, navegacao)
    ida, soma = b.ida_e_volta(_P1)
    esperado = rot.pixels((0.0, _VIES[1] * 2.0, 0.0), b.arranjo)[0]
    assert soma == pytest.approx(esperado, rel=0.05), (soma, esperado)
    assert abs(soma) > 0.02 * abs(ida), "sem zero o viés devia continuar na soma"


@pytest.mark.parametrize("navegacao", [False, True], ids=["primário", "modo-mouse"])
def test_cada_controle_desconta_o_proprio_vies(
        monkeypatch: pytest.MonkeyPatch, navegacao: bool) -> None:
    """O zero é por controle (P1 a P4, cabo e rádio): o do P2 não conserta o P1."""
    vies_p2 = (0.0, -2.5, 0.0)
    b = _Bancada(monkeypatch, {_P1: _VIES, _P2: vies_p2}, {_P2: vies_p2}, navegacao)
    _, soma_p1 = b.ida_e_volta(_P1)
    ida_p2, soma_p2 = b.ida_e_volta(_P2)
    assert abs(soma_p2) < 0.02 * abs(ida_p2), soma_p2
    assert abs(soma_p1) > 0.1 * abs(ida_p2), (
        "o P1 não tem zero guardado e andou como o P2 calibrado")


def test_o_desconto_vale_nos_tres_eixos_do_giro() -> None:
    """O roteador desconta `viés x dt` de x, y e z, com o dt da drenagem anterior."""
    dono = SimpleNamespace()
    zero = (0.6, -2.4, 1.1)
    rot.definir_o_zero(dono, _P1, rot.ZeroDoControle(giro=zero, gravidade=_GRAVIDADE))
    assert rot.angulo_do_tique(dono, _P1, (9.0, 9.0, 9.0), 10.0) is None
    descontado = rot.angulo_do_tique(dono, _P1, (9.0, 9.0, 9.0), 10.25)
    assert descontado == pytest.approx(
        (9.0 - 0.6 * 0.25, 9.0 + 2.4 * 0.25, 9.0 - 1.1 * 0.25))


def test_sem_zero_o_angulo_e_o_mesmo_objeto_e_o_acumulado_segue_descartado() -> None:
    dono = SimpleNamespace()
    angulo = (1.0, 2.0, 3.0)
    assert rot.angulo_do_tique(dono, _P1, angulo, 5.0) is None
    assert rot.angulo_do_tique(dono, _P1, angulo, 5.1) is angulo
    assert rot.angulo_do_tique(dono, _P1, angulo, 9.0) is None, "o silêncio longo é acumulado"


def test_o_ultimo_instante_da_drenagem_avanca_mesmo_sem_zero() -> None:
    """Calibrar no meio do jogo não pode herdar um `dt` velho: o instante anda sempre."""
    dono = SimpleNamespace()
    rot.angulo_do_tique(dono, _P1, (0.0, 0.0, 0.0), 1.0)
    rot.angulo_do_tique(dono, _P1, (0.0, 0.0, 0.0), 1.2)
    rot.definir_o_zero(dono, _P1, rot.ZeroDoControle(giro=(0.0, 1.0, 0.0), gravidade=_GRAVIDADE))
    saida = rot.angulo_do_tique(dono, _P1, (0.0, 5.0, 0.0), 1.3)
    assert saida == pytest.approx((0.0, 5.0 - 0.1, 0.0))


def test_so_o_aplicar_o_movimento_drena_o_angulo() -> None:
    """Os três chamadores (primário, Modo mouse e co-op) passam pelo mesmo funil.

    Quem lesse `angulo_do_movimento` por fora do funil teria o ângulo cru: esta régua
    reprova o segundo chamador antes de ele existir.
    """
    daemon = Path(gp.__file__).resolve().parents[1]
    achados = sorted(
        str(arq.relative_to(daemon))
        for arq in daemon.rglob("*.py")
        if re.search(r"\.angulo_do_movimento\(", arq.read_text(encoding="utf-8"))
        and arq.name != "gamepad.py"
    )
    assert achados == [], f"chamam o ângulo cru fora do funil: {achados}"
    fonte = Path(gp.__file__).read_text(encoding="utf-8")
    assert fonte.count(".angulo_do_movimento(") == 1
    for quem in ("mouse.py", "coop.py"):
        texto = (daemon / "subsystems" / quem).read_text(encoding="utf-8")
        assert "aplicar_o_movimento(" in texto, f"{quem} não passa pelo funil do movimento"
