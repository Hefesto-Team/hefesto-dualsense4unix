"""O-ASSENTO-GUARDADO-NAO-ANDA-04 — os 60 arranjos raros também fecham o buraco no jogo.

**Decidido por delegação e mantido por ela em 24/09/2026, 19h.** A varredura
da O-ASSENTO-03 (``_as_mesas_do_produto``, todas as mesas de até quatro lugares)
deixou 60 arranjos em que a guarda de quem já está no boneco certo deixava o
jogo como estava: com dois controles fora e prazos diferentes, o buraco que
VENCEU fica à frente de um lugar AINDA GUARDADO, e o sufixo só fecharia o
buraco pondo no lugar guardado quem já estava certo.

**A CONTAGEM, refeita pela função pura antes da cura:** os 60 são as mesas em
que o plano da O-ASSENTO-03 difere do mesmo sufixo sem a guarda. São DEZ
formas, cada uma com os três secundários em seis ordens (:data:`AS_DEZ_FORMAS`),
todas com quatro vpads sentados, nenhum nascendo e o jogo aberto. As famílias,
pelo lugar do vpad do P1 (fixo com o jogo na autoridade, a R-04):

- o P1 no boneco dele, na frente do buraco (``1F@1 2@3 3@4 5@5``);
- o P1 certo no meio da faixa, que passa por cima dele (``1@2 2@4 3F@3 5@5``
  e ``1@3 2F@2 3@4 5@5``);
- o P1 certo atrás do lugar guardado (``1@2 2@3 4@4 5F@5`` e
  ``1@2 2@3 4F@4 5@5``);
- o P1 fora do boneco dele, esperando o jogo (as outras cinco).

Em todas, um ou dois secundários estão atrás do buraco que venceu, e um
secundário certo está atrás do lugar guardado. **Chegar a elas exige seis
controles de uma vez** (quatro vpads sentados, um que venceu e um guardado):
com P1 a P4 e quaisquer dois fora, nenhuma das 60 acontece
(:class:`TestAMatrizDeQuatro`).

**A CURA mora no dono** (``coop._a_faixa``): quando o sufixo deixa alguém fora
do boneco, numa mesa já em ordem e com o jogo aberto, tenta-se recriar só uma
FAIXA de cartas. Ela só vale se ninguém dela está certo ou é fixo, se todo
mundo dela renasce no boneco da própria carta e se bate o sufixo em (fora do
boneco, recriações). Nos 60, todo secundário acaba no boneco da carta; só o P1
fora do boneco continua fora, esperando o jogo.

**E A MESMA FAMÍLIA fora dos 60:** a varredura muda 652 mesas, e 592 não são
dos 60 — o buraco à frente do lugar guardado com três sentados, que sufixo
nenhum fechava (322, com menos gente fora do boneco), e os empates em que o
sufixo recriava quem espera o lugar guardado para jogá-lo DENTRO dele (270,
a mesma conta com menos recriações). O caso que já fechava não muda: a faixa
só roda com alguém fora do boneco.

AS MORDIDAS (24/09/2026, cada uma devolvida com o md5 conferido):

- ``_a_faixa`` desligada (o ``planejar_a_ordem`` de antes) reprova 25: as dez
  famílias, os dois casos puros de quem espera, a varredura e as doze da
  bancada de queda (seis e cinco controles). A matriz de quatro passa, e é o
  que ela afirma;
- a faixa aceitando quem não cai no boneco da carta reprova a varredura (24
  mesas em que o renascido cairia no boneco do P1 fixo) e a mesa de cinco;
- a faixa sem a exigência da mesa em ordem reprova a varredura (mesa fora de
  ordem é do sufixo, STEAM-NO-FISICO-01);
- o fixo entrando na faixa reprova três famílias, a varredura, a mesa de cinco
  e três casos da matriz de quatro: o vpad do P1 renasceria com o jogo aberto
  (a R-04);
- a faixa pesando só a conta de fora, sem as recriações, reprova oito: é quem
  espera o lugar guardado renascendo à toa;
- sem a guarda da O-ASSENTO-03 (o ``break``), a faixa acha o mesmo plano nas
  34.790 mesas de até quatro; quem ainda a mede é
  :meth:`TestOs60.test_a_guarda_da_03_continua_valendo_numa_mesa_de_cinco`.

Saíram da faixa a exclusão de quem já está certo e o pulo da faixa vazia:
arrancadas as duas, nenhuma das 6,4 milhões de mesas de até cinco sentados
muda de plano (medido). A exigência do boneco já deixa de fora quem está
certo, e a faixa vazia é o plano de nenhuma recriação, que o sufixo já pesou.
O desempate a favor do sufixo também não se mede: nessas mesas, nenhuma faixa
diferente empata com ele.

Nenhum endereço real: faixa forjada ``aa:bb:cc`` com os octetos 4 e 5 zerados.
"""
from __future__ import annotations

import functools
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import PRIMARIO_RESERVA_SEC
from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems.coop import (
    _CHAVE_DO_P1,
    _a_mesa_depois,
    _em_ordem,
    _fora_do_boneco,
    planejar_a_ordem,
)
from hefesto_dualsense4unix.daemon.subsystems.identity import prazo_do_lugar_guardado
from tests.unit import test_o_jogo_espera_a_carta_do_lugar_guardado as bancada_mod
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

#: As dez formas dos 60, em «carta@boneco» na ordem da carta (``F`` é o vpad do
#: P1, fixo com o jogo na autoridade), com o boneco do buraco que venceu e a
#: carta ainda guardada.
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


# -- os oráculos: o plano de antes desta sprint, com e sem a guarda -----------


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


def _fora(mesa: Mapping[int, str], cartas: Mapping[str, int], nascer: Sequence[str],
          recriar: Sequence[str], compacta: bool) -> int:
    return _fora_do_boneco(_a_mesa_depois(mesa, recriar, nascer, cartas, compacta=compacta),
                           cartas)


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
        for mesa, cartas, _nascer, _fixos, _compacta, _da_03, _sem, (recriar, _i) in casos:
            lugar_de = {c: lugar for lugar, c in mesa.items()}
            fora_do_boneco = {c for c in mesa.values() if lugar_de[c] != cartas[c] - 1}
            assert set(recriar) == fora_do_boneco - FIXO, (mesa, cartas, recriar)
            depois = _a_mesa_depois(mesa, recriar, (), cartas, compacta=False)
            assert all(
                lugar == cartas[c] - 1 for lugar, c in depois.items() if c not in FIXO
            ), f"um secundário ficou fora do boneco: {depois}"
            assert not set(recriar) & FIXO

    def test_quem_espera_o_lugar_guardado_nao_se_mexe(self) -> None:
        """O ``d`` certo atrás do 4 guardado fica; o ``b`` e o ``c`` fecham o buraco."""
        mesa = {0: "p1", 2: "b", 3: "c", 4: "d"}
        cartas = {"p1": 1, "b": 2, "c": 3, "d": 5}
        assert _o_plano_da_03(mesa, cartas, fixos=FIXO) == ([], True)
        assert planejar_a_ordem(mesa, cartas, fixos=FIXO) == (["b", "c"], True)

    def test_quem_espera_fora_do_boneco_tambem_fica(self) -> None:
        """Cinco controles: o P2 venceu, o P4 ainda está guardado (a carta 3).

        O sufixo recriava o ``novo`` (carta 4, no boneco 5) junto com o P3, e o
        jogo o punha no boneco 3 — o lugar guardado do P4, ainda errado. A
        faixa recria só o P3; o ``novo`` espera o P4 voltar ou vencer.
        """
        mesa = {0: "p1", 2: "p3", 4: "novo"}
        cartas = {"p1": 1, "p3": 2, "novo": 4}
        assert _o_plano_da_03(mesa, cartas, fixos=FIXO) == (["p3", "novo"], True)
        assert planejar_a_ordem(mesa, cartas, fixos=FIXO) == (["p3"], True)

    def test_dentro_do_prazo_ninguem_renasce(self) -> None:
        mesa = {0: "p1", 2: "p3", 3: "p4"}
        assert planejar_a_ordem(mesa, {"p1": 1, "p3": 3, "p4": 4}, fixos=FIXO) == ([], True)

    def test_a_guarda_da_03_continua_valendo_numa_mesa_de_cinco(self) -> None:
        """Sem a guarda, o ``e`` (certo no boneco 6) iria para o lugar guardado do 5.

        A faixa não conserta esta mesa: o ``b`` renasceria no boneco 2, e o 1
        é do P1 fixo. Fica como está, e é a guarda que segura o ``e``.
        """
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


# -- a bancada de queda, com a classe real -----------------------------------

#: O sexto controle: os 60 pedem seis de uma vez (a bancada de queda tem cinco).
SEXTO = "aabbcc000006"

#: Seis controles no cabo, no rádio, e alternados.
TRANSPORTES_DE_SEIS = {
    "usb": ("usb",) * 6,
    "bt": ("bt",) * 6,
    "mista": ("usb", "bt") * 3,
}


class _LeitorQueDemora(_LeitorDeSecundario):
    """O leitor de um jogador cujo grab ainda não confirmou.

    É o «aguardando grab» do produto (BUG-COOP-GRAB-PENDING-VPAD-01): a thread
    do leitor ainda não abriu o nó, e o jogador está na mesa sem vpad.
    """

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


#: Quanto o lugar guardado dura (os dois prazos têm o mesmo dono).
PRAZO = max(PRIMARIO_RESERVA_SEC, prazo_do_lugar_guardado())
#: Quanto depois do primeiro o segundo sai: o prazo do primeiro vence antes.
DEPOIS = 10.0


@pytest.fixture
def mesa_de_seis(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bancada de queda com um sexto controle (a mesa de cinco lê ``CHAVE_DE``)."""
    monkeypatch.setitem(bancada_mod.CHAVE_DE, SEXTO, "AA:BB:CC:00:00:06")
    # O jogador que chega pronto não espera o vpad do que demora no grab: é o
    # piso de acessibilidade do produto, sem os 4 s de relógio de verdade.
    monkeypatch.setattr(coop_mod, "ESPERA_PELA_ORDEM_S", 0.0)


@pytest.mark.usefixtures("config_isolado", "mesa_de_seis")
class TestUmDosSessentaComSeisControles:
    """A forma ``1F@1 2@3 3@4 5@5``, com a classe real e seis controles.

    O ``g`` (o quinto a chegar) demora no grab e o ``z`` nasce antes dele, no
    boneco 5. O P2 sai; dez segundos depois o ``g`` sai sem nunca ter tido
    vpad. Quando o prazo do P2 vence, o do ``g`` ainda corre: a tela fecha a
    fila (o P3 é 2, o P4 é 3, o ``z`` é 5) e o boneco 4 é do ``g``.
    """

    @staticmethod
    def _ate_o_p2_vencer(
        monkeypatch: pytest.MonkeyPatch, bancada: MesaDoJogo, g: str
    ) -> tuple[int, Planos, Any]:
        bancada.mesa.levantar(P2)
        for _ in range(_ticks(DEPOIS)):
            bancada.tique()
        bancada.mesa.levantar(g)
        bancada.tique()
        antes = len(bancada.vpads)
        vpad_do_z = bancada.vpad_de(SEXTO)
        planos = Planos(monkeypatch)
        for _ in range(_ticks(PRAZO - DEPOIS) + 1):
            bancada.tique()
        assert bancada.reg.guardados(), "o prazo do g venceu junto — a mesa não é a dos 60"
        return antes, planos, vpad_do_z

    @pytest.mark.parametrize("volta", [True, False], ids=["o-g-volta", "o-g-vence"])
    @pytest.mark.parametrize("transporte", list(TRANSPORTES_DE_SEIS))
    def test_o_buraco_fecha_e_o_z_nao_se_mexe(
        self, monkeypatch: pytest.MonkeyPatch, transporte: str, volta: bool
    ) -> None:
        g = NOVO
        quem = (P1, P2, P3, P4, g, SEXTO)
        bancada = _montar(
            monkeypatch, quem, TRANSPORTES_DE_SEIS[transporte], demorados=frozenset({g})
        )
        assert bancada.vpad_de(g) is None, "o g devia estar esperando o grab"
        assert bancada.o_jogo_ve() == {1: P1, 2: P2, 3: P3, 4: P4, 5: SEXTO}
        vias = dict(zip(quem, TRANSPORTES_DE_SEIS[transporte], strict=True))

        antes, planos, vpad_do_z = self._ate_o_p2_vencer(monkeypatch, bancada, g)

        # O co-op perguntou uma das 60, e a faixa respondeu.
        mudados = planos.os_que_a_faixa_mudou()
        assert len(mudados) == 1, mudados
        mesa, cartas, nascer, fixos, compacta, resposta = mudados[0]
        assert (nascer, fixos, compacta) == ((), frozenset({_CHAVE_DO_P1}), False)
        assert _forma(mesa, cartas, fixos) == "1F@1 2@3 3@4 5@5"
        assert resposta == ([P3, P4], True)
        assert bancada.a_tela() == {P1: 1, P3: 2, P4: 3, SEXTO: 5}
        bancada.o_jogo_segue_a_tela()
        assert 4 not in bancada.o_jogo_ve(), "o boneco 4 é do g, que ainda pode voltar"
        for uniq in (P3, P4):
            assert len(_nascidos(bancada, antes, uniq)) == 1, f"{uniq} renasce uma vez"
        assert bancada.vpad_de(SEXTO) is vpad_do_z, "o z estava certo e renasceu"

        # E depois: o g volta ao boneco dele, ou vence e o z desce uma vez.
        if volta:
            monkeypatch.setattr(_LeitorQueDemora, "demorados", frozenset())
            bancada.mesa.sentar(g, transporte=vias[g])
            bancada.tique()
            bancada.tique()
            assert bancada.a_tela() == {P1: 1, P3: 2, P4: 3, g: 4, SEXTO: 5}
            assert bancada.vpad_de(SEXTO) is vpad_do_z
        else:
            for _ in range(_ticks(DEPOIS) + 1):
                bancada.tique()
            assert bancada.a_tela() == {P1: 1, P3: 2, P4: 3, SEXTO: 4}
            assert len(_nascidos(bancada, antes, SEXTO)) == 1
        bancada.o_jogo_segue_a_tela()
        for uniq in (P3, P4):
            assert len(_nascidos(bancada, antes, uniq)) == 1, f"{uniq} renasceu de novo"


@pytest.mark.usefixtures("config_isolado")
class TestQuemEsperaOLugarGuardado:
    """Cinco controles, e quem espera o lugar guardado não renasce à toa.

    O P2 sai; dez segundos depois, o P4. Quando o prazo do P2 vence, o P3 desce
    ao boneco 2 e o ``novo`` (carta 4, no boneco 5) ESPERA: recriado agora, o
    jogo o poria no boneco 3, que é do P4. Ele renasce uma vez só, quando o P4
    volta (e aí vai ao boneco 4) ou quando o prazo do P4 vence (boneco 3).
    """

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
    """P1 a P4, quaisquer dois fora com prazos diferentes, USB, BT e a mesa mista.

    O primeiro sai, o segundo sai dez segundos depois, o prazo do primeiro
    vence; o segundo volta dentro do prazo dele, ou o prazo vence também. Com
    quatro controles a faixa nunca muda o plano: cada pergunta que o co-op faz
    tem a resposta da O-ASSENTO-03. O jogo termina seguindo a tela, e quem
    ficou na mesa o tempo todo só renasce quando o número dele muda, e sempre
    no boneco do número novo (o ~1 s sem controle nunca é à toa).

    A exceção é a R-04, e ela não é desta sprint: o P1 sai, o P2 sai, o prazo
    do P1 vence com o P2 fora, e o posto passa ao P3. O P2 volta com a carta 1
    e dirige o boneco que o jogo lhe deu até o jogo devolver a autoridade
    (:class:`TestAVoltaTardiaDoP1`, na régua da O-ASSENTO-03).
    """

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
                # Sem vpad é quem cedeu o controle ao posto do P1: não renasceu.
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
