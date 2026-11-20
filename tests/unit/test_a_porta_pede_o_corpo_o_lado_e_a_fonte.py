"""A porta pede o corpo, o lado e a fonte (A-PORTA-PEDE-O-CORPO-O-LADO-E-A-FONTE-01).

O ``corpo.ligar`` diz na resposta o desfecho de agora, e o toque da extensão honra a recusa do
corpo: o rádio sem fatia cai no motor, o jogo no endpoint cai no nível de cada motor do tocador
(que soma ao rumble do jogo, nunca por ``levar_o_rumble``), e a Força em 0 e os modos que calam
não caem. A mesa é a do gatilho por lado: ``AltoFalanteSubsystem`` e ``TatoVivo`` reais, só o
tocador é dublê.

MORDIDAS: ignorar o retorno de ``tocar_haptica`` em ``FonteDeFora._levar`` reprova a queda no
motor e nos lados; cair por ``levar_o_rumble`` reprova a queda do jogo no endpoint; tratar a
``forca_zero`` como queda reprova a Força 0; tirar o zero de ``_levar_nos_lados`` ao fim do toque
deixa o motor preso; tirar o ``desfecho_do_corpo`` da resposta reprova a porta; um par só por
tocador em ``AltoFalanteSubsystem.levar_os_lados`` deixa o toque apagar o padrão do gatilho.
"""
from __future__ import annotations

from array import array
from types import MappingProxyType, SimpleNamespace
from typing import Any, cast

import pytest

from hefesto_dualsense4unix.daemon import ganho_da_haptica
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from tests.unit import test_o_gatilho_toca_o_tipo_no_lado_dele as mesa_mod
from tests.unit.test_a_porta_liga_o_som_no_corpo import _pela_porta

P = mesa_mod.P
EXT = tv.PREFIXO_DA_EXTENSAO + "vibra"
GOLPE = {"golpes": [[0, 1000, 60, 1.0]], "repete": False}


class _Tocador(mesa_mod._Tocador):
    def __init__(self) -> None:
        super().__init__()
        self.corpo: list[tuple[str, int]] = []
        self.nivel = (0, 0)
        self.dono = ""
        self.vivo = False

    def levar(self, fraco: int, forte: int, **_kw: Any) -> None:
        self.nivel = (fraco, forte)

    def calar(self) -> None:
        self.nivel = (0, 0)

    def levar_o_corpo(
        self, amostras: array[float], lado: str, *, sink: str, dono: str, fonte: str = ""
    ) -> None:
        self.corpo.append((lado, len(amostras)))


class _Cena:
    def __init__(self, monkeypatch: pytest.MonkeyPatch, **mesa: Any) -> None:
        monkeypatch.setattr(mesa_mod, "_Tocador", _Tocador)
        self.mesa = mesa_mod._Mesa(monkeypatch, **mesa)
        self.tocadores = cast("dict[str, _Tocador]", self.mesa.tocadores)
        self.fonte = tv.ligar_a_fonte_de_fora(self.mesa.daemon, self.mesa.motor.de_fora)
        self.levar_o_rumble: list[tuple[str, int, int]] = []
        original = self.mesa.alto.levar_o_rumble

        def espiar(uniq: str, fraco: int, forte: int, **kw: Any) -> bool:
            self.levar_o_rumble.append((uniq, fraco, forte))
            return original(uniq, fraco, forte, **kw)

        monkeypatch.setattr(self.mesa.alto, "levar_o_rumble", espiar)
        self.fonte.registrar(EXT, "golpe", tv.padrao_de(GOLPE))

    def tocar(self, uniq: str, lado: str = tv.LADO_ESQUERDO, ate_s: float = 1.0) -> None:
        assert self.fonte.tocar(EXT, uniq, lado, "golpe", 1.0, None, 0.0, ate_s).vale

    def andar(self, de: float, ate: float) -> None:
        t = de
        while t <= ate + 1e-9:
            self.fonte.andar(t)
            t += tv.INTERVALO_S

    def motores(self, uniq: str) -> list[tuple[int, int]]:
        return [(forte, fraco) for u, fraco, forte in self.mesa.backend.rumble if u == uniq]

    def cede(self, uniq: str, cedendo: bool) -> None:
        alto = self.mesa.alto
        alto._vaga_da_ponte = MappingProxyType(
            {**alto._vaga_da_ponte, uniq: SimpleNamespace(cedendo=cedendo)})


def _radio(monkeypatch: pytest.MonkeyPatch, **mesa: Any) -> _Cena:
    cena = _Cena(monkeypatch, conexoes={P[0]: mesa_mod.RADIO_COM_PONTE}, **mesa)
    cena.cede(P[0], False)
    return cena


def test_o_radio_que_passa_a_ceder_no_meio_do_toque_cai_no_motor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-1911-O-TOQUE-DA-EXTENSAO-HONRA-A-RECUSA-DO-CORPO: o rádio sem fatia cai no motor."""
    cena = _radio(monkeypatch)
    cena.tocar(P[0])
    cena.andar(0.0, 0.2)
    assert cena.tocadores[P[0]].corpo, "com fatia o toque vai pelo corpo"
    assert not any(cena.motores(P[0]))
    cena.cede(P[0], True)
    cena.andar(0.3, 0.6)
    assert (P[0], 0, 255) in cena.levar_o_rumble, "o rádio sem fatia deixou o toque mudo"


def test_o_jogo_no_endpoint_cai_nos_lados_e_nunca_apaga_o_rumble_do_jogo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-1911-O-TOQUE-DA-EXTENSAO-HONRA-A-RECUSA-DO-CORPO: o jogo no endpoint cai nos lados."""
    cena = _Cena(monkeypatch, conexoes={P[0]: mesa_mod.CABO})
    tocador = cena.tocadores[P[0]]
    cena.tocar(P[0], tv.LADO_DIREITO)
    cena.andar(0.0, 0.1)
    corpo_antes = len(tocador.corpo)
    assert corpo_antes and not tocador.lados
    cena.mesa.alto._aparelhos_com_jogo = frozenset({cena.mesa.alto._aparelho_de[P[0]]})
    cena.andar(0.2, 0.5)
    assert len(tocador.corpo) == corpo_antes, "o corpo seguiu tocando por cima do jogo"
    assert (0, 255) in tocador.lados, "o toque da extensão sumiu com o jogo no endpoint"
    assert cena.levar_o_rumble == [], "caiu por levar_o_rumble e apagou o rumble do jogo"
    assert not any(cena.motores(P[0]))
    cena.mesa.alto._aparelhos_com_jogo = frozenset()
    cena.andar(0.6, 0.7)
    assert tocador.lados[-1] == (0, 0), "o jogo saiu do endpoint e o nível dos lados ficou"
    assert len(tocador.corpo) > corpo_antes, "o toque não voltou ao corpo"


def test_ao_fim_do_toque_o_nivel_dos_lados_volta_a_zero_e_o_outro_lado_segue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-1911-O-TOQUE-DA-EXTENSAO-HONRA-A-RECUSA-DO-CORPO: o fim do toque solta os lados."""
    cena = _Cena(monkeypatch, conexoes={P[0]: mesa_mod.CABO})
    tocador = cena.tocadores[P[0]]
    cena.mesa.alto._aparelhos_com_jogo = frozenset({cena.mesa.alto._aparelho_de[P[0]]})
    cena.tocar(P[0], tv.LADO_ESQUERDO, ate_s=0.3)
    cena.tocar(P[0], tv.LADO_DIREITO, ate_s=1.0)
    cena.andar(0.0, 0.2)
    assert tocador.lados[-1] == (255, 255)
    cena.andar(0.3, 0.5)
    assert tocador.lados[-1] == (0, 255), "o lado que acabou segurou o outro, ou ficou preso"
    cena.andar(0.6, 1.2)
    assert tocador.lados[-1] == (0, 0), "o motor ficou preso depois do último toque"


def test_o_toque_nos_lados_soma_ao_padrao_do_gatilho_e_nao_o_apaga(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-1911-O-TOQUE-DA-EXTENSAO-HONRA-A-RECUSA-DO-CORPO: nos lados, cada fonte no seu par."""
    cena = _Cena(monkeypatch, conexoes={P[0]: mesa_mod.CABO})
    tocador = cena.tocadores[P[0]]
    cena.mesa.alto._aparelhos_com_jogo = frozenset({cena.mesa.alto._aparelho_de[P[0]]})
    gatilho = tv.saida_dos_padroes(cena.mesa.daemon)
    cena.tocar(P[0], tv.LADO_DIREITO, ate_s=0.3)
    gatilho(P[0], 0, 120)
    cena.andar(0.0, 0.2)
    assert tocador.lados[-1] == (120, 255), "o toque apagou o padrão do gatilho, ou o contrário"
    cena.andar(0.3, 0.5)
    assert tocador.lados[-1] == (120, 0), "o fim do toque calou o padrão do gatilho"
    gatilho(P[0], 0, 0)
    assert tocador.lados[-1] == (0, 0)


@pytest.mark.parametrize("quando", ["forca_zero", "nativo"])
def test_forca_zero_e_modo_nativo_nao_caem_em_nenhum_caminho(
    monkeypatch: pytest.MonkeyPatch, quando: str,
) -> None:
    """D-1911-O-TOQUE-DA-EXTENSAO-HONRA-A-RECUSA-DO-CORPO: a Força 0 e o Nativo não caem."""
    nativo = quando == "nativo"
    cena = _Cena(monkeypatch, conexoes={P[0]: mesa_mod.CABO},
                 chip=mesa_mod.NATIVO if nativo else mesa_mod.SONY,
                 forca=0 if quando == "forca_zero" else 80)
    tocador = cena.tocadores[P[0]]
    cena.mesa.alto._aparelhos_com_jogo = frozenset()
    if nativo:
        assert not cena.fonte.tocar(EXT, P[0], tv.LADO_ESQUERDO, "golpe", 1.0, None, 0.0, 1.0).vale
    else:
        cena.tocar(P[0])
    cena.andar(0.0, 0.5)
    assert not tocador.corpo and not tocador.lados
    assert not any(cena.motores(P[0])) and cena.levar_o_rumble == []


def _quatro(monkeypatch: pytest.MonkeyPatch) -> _Cena:
    """Quatro controles, cabo e rádio misturados, cada um num motivo."""
    cena = _Cena(monkeypatch, conexoes={
        P[0]: mesa_mod.CABO, P[1]: mesa_mod.CABO, P[2]: mesa_mod.RADIO_COM_PONTE,
        P[3]: mesa_mod.CABO}, familias={P[3]: mesa_mod.PRO})
    monkeypatch.setattr(
        ganho_da_haptica.GANHO, "pct", lambda uniq: 0 if uniq == P[1] else 80)
    cena.cede(P[2], False)
    return cena


def test_a_resposta_do_corpo_ligar_diz_o_desfecho_de_cada_controle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-1911-A-PORTA-DIZ-O-DESFECHO-DO-CORPO: cada controle responde o seu desfecho."""
    cena = _quatro(monkeypatch)
    cena.cede(P[2], True)

    async def roteiro(pedir: Any) -> list[dict[str, Any]]:
        return [(await pedir("corpo.ligar", {"uniq": u, "som_no_corpo": 0.5, "ate_ms": 500}))
                ["result"] for u in P]

    respostas = _pela_porta(cena.fonte, roteiro, ["escrever:corpo"])
    assert respostas == [
        {"status": "ok", "corpo": "tocando"},
        {"status": "ok", "corpo": "cedeu", "motivo": "forca_zero"},
        {"status": "ok", "corpo": "cedeu", "motivo": "radio_cede"},
        {"status": "ok", "corpo": "cedeu", "motivo": "sem_endpoint"},
    ]


def test_o_jogo_no_endpoint_e_o_controle_sem_aparelho_chegam_na_resposta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-1911-A-PORTA-DIZ-O-DESFECHO-DO-CORPO: o motivo chega na resposta."""
    cena = _quatro(monkeypatch)
    alto = cena.mesa.alto
    alto._aparelhos_com_jogo = frozenset({alto._aparelho_de[P[0]]})
    alto._aparelho_de = MappingProxyType(
        {u: m for u, m in alto._aparelho_de.items() if u != P[2]})

    async def roteiro(pedir: Any) -> list[dict[str, Any]]:
        return [(await pedir("corpo.ligar", {"uniq": u, "som_no_corpo": 0.5, "ate_ms": 500}))
                ["result"] for u in (P[0], P[2])] + [
            await pedir("corpo.ligar", {"uniq": P[0], "gatilhos": {"tipo": "tranco", "forca": 0.5},
                                        "ate_ms": 500})]

    jogo, sem_aparelho, so_gatilhos = _pela_porta(cena.fonte, roteiro, ["escrever:corpo"])
    assert jogo == {"status": "ok", "corpo": "cedeu", "motivo": "jogo_no_endpoint"}
    assert sem_aparelho == {"status": "ok", "corpo": "cedeu", "motivo": "sem_aparelho"}
    assert so_gatilhos["result"] == {"status": "ok"}, "sem Som no corpo pedido não há desfecho"


def test_os_quatro_juntos_cada_um_cai_pelo_seu_caminho(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-1911-O-TOQUE-DA-EXTENSAO-HONRA-A-RECUSA-DO-CORPO: quatro controles, quatro motivos."""
    cena = _quatro(monkeypatch)
    for uniq in P:
        cena.tocar(uniq)
    cena.andar(0.0, 0.2)
    cena.cede(P[2], True)
    cena.andar(0.3, 0.5)
    t = cena.tocadores
    assert t[P[0]].corpo and not any(cena.motores(P[0]))
    assert not t[P[1]].corpo and not any(cena.motores(P[1])), "a Força 0 caiu no motor"
    assert (P[2], 0, 255) in cena.levar_o_rumble
    assert not any(cena.motores(P[3])), "o Pro não tem corpo e não leva a queda"
