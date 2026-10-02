"""O-ASSENTO-GUARDADO-NAO-ANDA-04 — os 60 arranjos raros também fecham o buraco no jogo."""
from __future__ import annotations

import functools
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import PRIMARIO_RESERVA_SEC
from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems.coop import (
    _a_mesa_depois,
    _em_ordem,
    _fora_do_boneco,
    planejar_a_ordem,
)
from hefesto_dualsense4unix.daemon.subsystems.identity import prazo_do_lugar_guardado
from tests.unit.test_coop_bancada_de_queda_do_primario import _LeitorDeSecundario
from tests.unit.test_o_buraco_de_quem_saiu_se_fecha_no_jogo import _as_mesas_do_produto
from tests.unit.test_o_jogo_espera_a_carta_do_lugar_guardado import (  # noqa: F401
    NOVO,
    P1,
    P2,
    P3,
    P4,
    TIQUE,
    TRANSPORTES,
    UNIQS,
    MesaDoJogo,
    Relogio,
    config_isolado,
    montar,
)

FIXO = frozenset({"p1"})

AS_DEZ_FORMAS = {
    "1F@1 2@3 3@4 5@5": (2, 4),
    "1@2 2@4 3F@3 5@5": (1, 4),
    "1@3 2F@2 3@4 5@5": (1, 4),
    "1@2 2@3 4@4 5F@5": (1, 3),
    "1@2 2@3 4F@4 5@5": (1, 3),
    "1@2 2@3 3F@4 5@5": (1, 4),
    "1@2 2@3 3F@5 4@4": (1, 5),
    "1@2 2@4 4F@3 5@5": (1, 3),
    "1@3 3@4 4F@2 5@5": (1, 2),
    "2@3 3@4 4F@1 5@5": (2, 1),
}


def _o_plano_da_03(
    mesa: Mapping[int, str],
    cartas: Mapping[str, int],
    nascer: Sequence[str] = (),
    *,
    fixos: frozenset[str] = frozenset(),
    compacta: bool = False,
    guarda: bool = True,
) -> tuple[list[str], bool]:
    """O ``planejar_a_ordem`` da O-ASSENTO-03: o sufixo, e a guarda de quem está certo."""
    sentados = [c for _lugar, c in sorted(mesa.items())]
    lugar_de = {c: lugar for lugar, c in mesa.items()}
    limites = sorted({*(cartas[c] for c in sentados), *(cartas[c] for c in nascer)})
    melhor: tuple[int, list[str], bool] | None = None
    for t in [max(limites, default=0) + 1, *reversed(limites)]:
        recriar = [c for c in sentados if cartas[c] >= t and c not in fixos]
        if guarda and melhor is not None and any(
            lugar_de[c] == cartas[c] - 1 for c in recriar if c not in melhor[1]
        ):
            break
        depois = _a_mesa_depois(mesa, recriar, nascer, cartas, compacta=compacta)
        if not _em_ordem([cartas[c] for c in depois.values() if c not in fixos]):
            continue
        fora = _fora_do_boneco(depois, cartas)
        if melhor is None or fora < melhor[0]:
            melhor = (fora, recriar, _em_ordem([cartas[c] for c in depois.values()]))
    return ([], False) if melhor is None else (melhor[1], melhor[2])


def _forma(mesa: Mapping[int, str], cartas: Mapping[str, int], fixos: frozenset[str]) -> str:
    """A mesa sem os nomes: «carta@boneco» na ordem da carta, ``F`` no fixo."""
    return " ".join(
        f"{cartas[c]}{'F' if c in fixos else ''}@{lugar + 1}"
        for lugar, c in sorted(mesa.items(), key=lambda item: cartas[item[1]])
    )


def _fora(
    mesa: Mapping[int, str],
    cartas: Mapping[str, int],
    nascer: Sequence[str],
    recriar: Sequence[str],
    compacta: bool,
) -> int:
    depois = _a_mesa_depois(mesa, recriar, nascer, cartas, compacta=compacta)
    return _fora_do_boneco(depois, cartas)


@functools.cache
def _a_varredura() -> tuple[tuple[Any, ...], ...]:
    """Cada mesa da varredura com as três respostas: a da 03, a sem guarda e a de hoje."""
    linhas = []
    for mesa, cartas, nascer, fixos, compacta in _as_mesas_do_produto():
        linhas.append((
            mesa,
            cartas,
            tuple(nascer),
            fixos,
            compacta,
            _o_plano_da_03(mesa, cartas, nascer, fixos=fixos, compacta=compacta),
            _o_plano_da_03(mesa, cartas, nascer, fixos=fixos, compacta=compacta, guarda=False),
            planejar_a_ordem(mesa, cartas, nascer, fixos=fixos, compacta=compacta),
        ))
    return tuple(linhas)


def _os_60() -> list[tuple[Any, ...]]:
    return [linha for linha in _a_varredura() if linha[5][0] != linha[6][0]]


class TestOs60:
    """A contagem da conferência, refeita, e cada família fechando."""

    def test_a_contagem_dos_60(self) -> None:
        os_60 = _os_60()
        assert len(os_60) == 60
        formas: Counter[str] = Counter()
        for mesa, cartas, nascer, fixos, compacta, da_03, _sem_guarda, _hoje in os_60:
            assert (len(mesa), nascer, fixos, compacta) == (4, (), FIXO, False)
            assert da_03[0] == [], "a guarda deixava o jogo como estava"
            buraco = next(lugar for lugar in range(5) if lugar not in mesa) + 1
            guardada = next(n for n in range(1, 6) if n not in cartas.values())
            forma = _forma(mesa, cartas, fixos)
            assert AS_DEZ_FORMAS.get(forma) == (buraco, guardada), forma
            formas[forma] += 1
        assert formas == dict.fromkeys(AS_DEZ_FORMAS, 6)

    @pytest.mark.parametrize("forma", list(AS_DEZ_FORMAS))
    def test_cada_familia_fecha_o_buraco(self, forma: str) -> None:
        """Atrás do buraco, renasce no boneco da carta; quem espera o guardado fica."""
        casos = [linha for linha in _os_60() if _forma(linha[0], linha[1], FIXO) == forma]
        assert len(casos) == 6
        for mesa, cartas, _nascer, _fixos, _compacta, _da_03, _sem, (recriar, inteira) in casos:
            lugar_de = {c: lugar for lugar, c in mesa.items()}
            fora_do_boneco = {c for c in mesa.values() if lugar_de[c] != cartas[c] - 1}
            assert set(recriar) == fora_do_boneco - FIXO, (mesa, cartas, recriar)
            depois = _a_mesa_depois(mesa, recriar, (), cartas, compacta=False)
            assert all(
                lugar == cartas[c] - 1 for lugar, c in depois.items() if c not in FIXO
            ), f"um secundário ficou fora do boneco: {depois}"
            assert not set(recriar) & FIXO
            numeros = [cartas[c] for _lugar, c in sorted(depois.items())]
            assert inteira == (numeros == sorted(numeros)), (mesa, cartas, inteira)

    def test_quem_espera_o_lugar_guardado_nao_se_mexe(self) -> None:
        """O ``d`` certo atrás do 4 guardado fica; o ``b`` e o ``c`` fecham o buraco."""
        mesa = {0: "p1", 2: "b", 3: "c", 4: "d"}
        cartas = {"p1": 1, "b": 2, "c": 3, "d": 5}
        assert _o_plano_da_03(mesa, cartas, fixos=FIXO) == ([], True)
        assert planejar_a_ordem(mesa, cartas, fixos=FIXO) == (["b", "c"], True)

    def test_quem_espera_fora_do_boneco_tambem_fica(self) -> None:
        """Cinco controles: o P2 venceu, o P4 ainda está guardado (a carta 3)."""
        mesa = {0: "p1", 2: "p3", 4: "novo"}
        cartas = {"p1": 1, "p3": 2, "novo": 4}
        assert _o_plano_da_03(mesa, cartas, fixos=FIXO) == (["p3", "novo"], True)
        assert planejar_a_ordem(mesa, cartas, fixos=FIXO) == (["p3"], True)

    def test_dentro_do_prazo_ninguem_renasce(self) -> None:
        mesa = {0: "p1", 2: "p3", 3: "p4"}
        assert planejar_a_ordem(mesa, {"p1": 1, "p3": 3, "p4": 4}, fixos=FIXO) == ([], True)

    def test_a_guarda_da_03_continua_valendo_numa_mesa_de_cinco(self) -> None:
        """Sem a guarda, o ``e`` (certo no boneco 6) iria para o lugar guardado do 5."""
        mesa = {0: "p1", 2: "b", 3: "c", 4: "d", 5: "e"}
        cartas = {"p1": 2, "b": 1, "c": 3, "d": 4, "e": 6}
        sem_guarda = _o_plano_da_03(mesa, cartas, fixos=FIXO, guarda=False)
        assert "e" in sem_guarda[0]
        assert planejar_a_ordem(mesa, cartas, fixos=FIXO) == ([], False)


class TestAVarredura:
    """A função pura contra todas as mesas de até quatro lugares."""

    def test_nenhum_caso_que_ja_fechava_muda(self) -> None:
        fechavam = 0
        for mesa, cartas, nascer, fixos, compacta, da_03, _sem, hoje in _a_varredura():
            if _fora(mesa, cartas, nascer, da_03[0], compacta):
                continue
            fechavam += 1
            assert hoje == da_03, (mesa, cartas, nascer, fixos, compacta)
        assert fechavam == 2488, fechavam

    def test_quem_muda_so_melhora(self) -> None:
        """Toda mesa que muda: jogo aberto, mesa em ordem, e a faixa melhor que o sufixo."""
        mudaram: Counter[str] = Counter()
        os_60 = {id(linha) for linha in _os_60()}
        for linha in _a_varredura():
            mesa, cartas, nascer, fixos, compacta, da_03, _sem, hoje = linha
            if hoje == da_03:
                continue
            caso = (mesa, cartas, nascer, fixos, compacta)
            assert not compacta, caso
            parada = _a_mesa_depois(mesa, [], nascer, cartas, compacta=False)
            assert _em_ordem([cartas[c] for c in parada.values() if c not in fixos]), caso
            antes = (_fora(mesa, cartas, nascer, da_03[0], False), len(da_03[0]))
            agora = (_fora(mesa, cartas, nascer, hoje[0], False), len(hoje[0]))
            assert agora < antes, caso
            lugar_de = {c: lugar for lugar, c in mesa.items()}
            assert not any(lugar_de[c] == cartas[c] - 1 for c in hoje[0]), caso
            assert not set(hoje[0]) & fixos, caso
            depois = _a_mesa_depois(mesa, hoje[0], nascer, cartas, compacta=False)
            assert all(lugar == cartas[c] - 1 for lugar, c in depois.items() if c in hoje[0]), (
                "quem renasce pela faixa cai no boneco da própria carta",
                caso,
            )
            assert _em_ordem([cartas[c] for c in depois.values() if c not in fixos]), (
                "a faixa quebrou a ordem do jogo",
                caso,
            )
            if id(linha) in os_60:
                mudaram["os 60"] += 1
            elif agora[0] < antes[0]:
                mudaram["menos gente fora do boneco"] += 1
            else:
                mudaram["a mesma conta, menos recriações"] += 1
        assert mudaram == {
            "os 60": 60,
            "menos gente fora do boneco": 322,
            "a mesma conta, menos recriações": 270,
        }


SEXTO = "aabbcc000006"

TRANSPORTES_DE_SEIS = {
    "usb": ("usb",) * 6,
    "bt": ("bt",) * 6,
    "mista": ("usb", "bt") * 3,
}


class _LeitorQueDemora(_LeitorDeSecundario):
    """O leitor de um jogador cujo grab ainda não confirmou."""

    demorados: frozenset[str] = frozenset()

    def set_grab(self, grab: bool) -> bool:
        if grab and self.target_uniq in type(self).demorados:
            self.grab_state = "pending"
            return True
        return super().set_grab(grab)


class Planos:
    """Cada pergunta que o co-op faz ao ``planejar_a_ordem``, com a resposta."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.feitos: list[tuple[Any, ...]] = []
        real: Callable[..., tuple[list[str], bool]] = coop_mod.planejar_a_ordem

        def gravar(
            mesa: Mapping[int, str],
            cartas: Mapping[str, int],
            nascer: Sequence[str] = (),
            *,
            fixos: frozenset[str] = frozenset(),
            compacta: bool = False,
        ) -> tuple[list[str], bool]:
            resposta = real(mesa, cartas, nascer, fixos=fixos, compacta=compacta)
            self.feitos.append(
                (dict(mesa), dict(cartas), tuple(nascer), fixos, compacta, resposta)
            )
            return resposta

        monkeypatch.setattr(coop_mod, "planejar_a_ordem", gravar)

    def os_que_a_faixa_mudou(self) -> list[tuple[Any, ...]]:
        return [
            feito
            for feito in self.feitos
            if feito[5]
            != _o_plano_da_03(feito[0], feito[1], feito[2], fixos=feito[3], compacta=feito[4])
        ]


def _montar(
    monkeypatch: pytest.MonkeyPatch,
    quem: Sequence[str],
    vias: Sequence[str],
    *,
    demorados: frozenset[str] = frozenset(),
) -> MesaDoJogo:
    """A mesa de ``quem``, nesta ordem de chegada, com o jogo aberto."""
    relogio = Relogio()
    bancada = MesaDoJogo(monkeypatch, relogio=relogio, tempo=relogio)
    monkeypatch.setattr(_LeitorQueDemora, "demorados", demorados)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.EvdevReader", _LeitorQueDemora
    )
    for uniq, via in zip(quem, vias, strict=True):
        bancada.mesa.sentar(uniq, transporte=via)
    for _ in range(3):
        bancada.tique()
    assert bancada.dono_do_vpad_do_p1() == quem[0]
    return bancada


def _ticks(segundos: float) -> int:
    return int(segundos / TIQUE)


def _nascidos(bancada: MesaDoJogo, desde: int, uniq: str) -> list[Any]:
    return [v for v in bancada.vpads[desde:] if getattr(v, "identidade", None) == uniq]


PRAZO = max(PRIMARIO_RESERVA_SEC, prazo_do_lugar_guardado())
DEPOIS = 10.0


@pytest.mark.usefixtures("config_isolado")
class TestQuemEsperaOLugarGuardado:
    """Cinco controles, e quem espera o lugar guardado não renasce à toa."""

    @pytest.mark.parametrize("volta", [True, False], ids=["o-p4-volta", "o-p4-vence"])
    @pytest.mark.parametrize("transporte", list(TRANSPORTES_DE_SEIS))
    def test_o_novo_renasce_uma_vez_so(
        self, monkeypatch: pytest.MonkeyPatch, transporte: str, volta: bool
    ) -> None:
        quem = (P1, P2, P3, P4, NOVO)
        vias = TRANSPORTES_DE_SEIS[transporte][:5]
        bancada = _montar(monkeypatch, quem, vias)
        assert bancada.o_jogo_ve() == {n + 1: u for n, u in enumerate(quem)}
        vpad_do_novo = bancada.vpad_de(NOVO)

        bancada.mesa.levantar(P2)
        for _ in range(_ticks(DEPOIS)):
            bancada.tique()
        bancada.mesa.levantar(P4)
        bancada.tique()
        antes = len(bancada.vpads)
        for _ in range(_ticks(PRAZO - DEPOIS) + 1):
            bancada.tique()
        assert bancada.reg.guardados(), "o prazo do P4 venceu junto"

        assert bancada.a_tela() == {P1: 1, P3: 2, NOVO: 4}
        jogo = bancada.o_jogo_ve()
        assert jogo[2] == P3 and len(_nascidos(bancada, antes, P3)) == 1
        assert 3 not in jogo, "o boneco 3 é do P4, que ainda pode voltar"
        assert bancada.vpad_de(NOVO) is vpad_do_novo, (
            "o novo renasceu para cair no lugar guardado do P4"
        )

        if volta:
            bancada.mesa.sentar(P4, transporte=vias[3])
            bancada.tique()
            bancada.tique()
            assert bancada.a_tela() == {P1: 1, P3: 2, P4: 3, NOVO: 4}
        else:
            for _ in range(_ticks(DEPOIS) + 1):
                bancada.tique()
            assert bancada.a_tela() == {P1: 1, P3: 2, NOVO: 3}
        bancada.o_jogo_segue_a_tela()
        assert len(_nascidos(bancada, antes, NOVO)) == 1, "o novo renasce uma vez só"
        assert len(_nascidos(bancada, antes, P3)) == 1


DOIS_FORA = [
    pytest.param(primeiro, segundo, transporte, volta, id=(
        f"sai-p{primeiro + 1}-depois-p{segundo + 1}-{transporte}-"
        f"{'volta' if volta else 'vence'}"
    ))
    for primeiro in range(4)
    for segundo in range(4)
    if segundo != primeiro
    for transporte in TRANSPORTES
    for volta in (True, False)
]


@pytest.mark.usefixtures("config_isolado")
class TestAMatrizDeQuatro:
    """P1 a P4, quaisquer dois fora com prazos diferentes, USB, BT e a mesa mista."""

    @pytest.mark.parametrize(("primeiro", "segundo", "transporte", "volta"), DOIS_FORA)
    def test_a_faixa_nao_muda_nada_na_mesa_de_quatro(
        self,
        monkeypatch: pytest.MonkeyPatch,
        primeiro: int,
        segundo: int,
        transporte: str,
        volta: bool,
    ) -> None:
        bancada = montar(monkeypatch, 4, transporte)
        planos = Planos(monkeypatch)
        via = bancada.mesa.transporte_de(UNIQS[segundo])
        sempre = [u for n, u in enumerate(UNIQS[:4]) if n not in (primeiro, segundo)]

        def tique() -> None:
            vpads = {u: bancada.vpad_de(u) for u in sempre}
            jogo, tela = bancada.o_jogo_ve(), bancada.a_tela()
            certos = {u for u in sempre if jogo.get(tela.get(u)) == u}
            bancada.tique()
            jogo, numeros = bancada.o_jogo_ve(), bancada.a_tela()
            for uniq in sempre:
                novo = bancada.vpad_de(uniq)
                if novo is not None and vpads[uniq] is not None and novo is not vpads[uniq]:
                    assert uniq not in certos or numeros[uniq] != tela[uniq], (
                        f"{uniq} estava no boneco do número dele e renasceu"
                    )
                    assert jogo.get(numeros[uniq]) == uniq, (
                        f"{uniq} renasceu fora do boneco do número: {jogo}, {numeros}"
                    )

        bancada.mesa.levantar(UNIQS[primeiro])
        for _ in range(_ticks(DEPOIS)):
            tique()
        bancada.mesa.levantar(UNIQS[segundo])
        for _ in range(_ticks(PRAZO - DEPOIS) + 1):
            tique()
        if volta:
            bancada.mesa.sentar(UNIQS[segundo], transporte=via)
            tique()
            tique()
        else:
            for _ in range(_ticks(DEPOIS) + 1):
                tique()

        assert planos.feitos, "o co-op não perguntou nada ao planejador"
        assert planos.os_que_a_faixa_mudou() == []
        ficaram = [u for n, u in enumerate(UNIQS[:4]) if n != primeiro and (volta or n != segundo)]
        assert set(bancada.a_tela()) == set(ficaram)
        if (primeiro, segundo, volta) == (0, 1, True):
            assert bancada.inst.primary_uniq == P3, "a R-04: o posto ficou com o P3"
            assert bancada.coop._p1_espera_o_jogo is True
            jogo = bancada.o_jogo_ve()
            assert P2 in jogo.values() and jogo[bancada.a_tela()[P4]] == P4, jogo
        else:
            bancada.o_jogo_segue_a_tela()
