"""D-O-GESTO-DA-PONTE-E-UNIVERSAL-NAO-APRENDE-POR-JOGO (29/08/2026).

Decisão dela, com todas as letras: *"pera, pq isso tá sob a identidade de um
jogo específico? Isso deveria ser universal — não é produto, é gambiarra!"*

O DEFEITO, medido no journal dela, e a prova mais limpa é o MESMO JOGO com os
DOIS comportamentos em três horas:

    00:25:02  Mullet SEM carimbo  -> `ponte_escada_aberta motivo=perfil_manda`
    00:26:17  2º aperto -> `ponte_escada_parou_no_degrau_caro`
    03:23:13  `confirmada_por_silencio gestos=0` -> o carimbo NASCE SOZINHO
    03:27-03:29  quatro apertos, todos `escada=None`, todos `ok=True`

A MECÂNICA: o carimbo DESLIGA a escada (`ponte_escada.proximo_degrau`, a
primeira linha do corpo), e sem escada o gesto cai no `CICLO_DE_PONTES`, cujos
três degraus são TODOS alcançáveis com o jogo aberto. Com a escada ligada, o 2º
aperto pedia o degrau `native`, que exige REABRIR o jogo — e o aperto morria ali.

POR QUE ERA GAMBIARRA, na régua dela: **o usuário novo tinha o comportamento
PIOR.** Quem instala hoje não tem jogo carimbado nenhum; todo jogo dele travava
no segundo aperto. Medido nos perfis de dev dela em 29/08: os quatro jogos
nascem `mode=None, ponte=None`.

O ALVO: **o gesto se comporta igual com carimbo ou sem.** O que ela usa o gesto
para fazer é TESTAR a ponte sem fechar o jogo — *"o PS+R3 altera a bridge, e
isso permite que dentro do jogo eu possa testar a bridge sem fechar o jogo"*.
Um degrau que exige reabrir o jogo NÃO PERTENCE ao gesto; pertence ao
lançamento, e é lá que ele continua valendo.

Cada teste diz o que MORDE.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import hotkey as hk
from hefesto_dualsense4unix.integrations import ponte_escada as pe
from hefesto_dualsense4unix.integrations import ponte_tentativa as pt

APPID = 4242
EPOCH = 1

#: Os quatro jogos, como os perfis DELA os entregavam em 29/08/2026, lidos de
#: `~/.config/hefesto-dualsense4unix/profiles/`. Os três primeiros têm carimbo
#: (a escada não roda); o Sackboy não tem (a escada roda). Todos os quatro têm
#: `mode.gamepad_flavor = "dualsense"`, e é por isso que os quatro partem do
#: mesmo lugar — o que os separava era só o carimbo.
QUATRO_JOGOS = [
    ("pragmata", "dualsense", True),
    ("duskfade", "dualsense", True),
    ("mullet_mad_jack", "dualsense", True),
    ("sackboy", "dualsense", False),
]


class _FakeDevice:
    def __init__(self, flavor: str) -> None:
        self.flavor = flavor


class _FakeStore:
    def __init__(self) -> None:
        self.native_mode_active = False

    def bump(self, chave: str) -> None:
        pass


class _Daemon:
    """Daemon dublado. Não toca aparelho, não toca disco, não toca perfil."""

    def __init__(self, flavor: str) -> None:
        self.controller = SimpleNamespace()
        self.store = _FakeStore()
        self.display_authority = "game"
        self._gamepad_device: Any = _FakeDevice(flavor)
        self.pedidos: list[tuple[bool, str | None, str]] = []

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        return fn(*args)

    def set_gamepad_emulation(
        self, enabled: bool, flavor: str | None = None, *, origin: str = "manual"
    ) -> bool:
        self.pedidos.append((enabled, flavor, origin))
        self._gamepad_device = _FakeDevice(flavor or "dualsense") if enabled else None
        return True

    def set_mouse_emulation(self, enabled: bool, *, origin: str = "profile") -> bool:
        return enabled

    def set_keyboard_emulation(self, enabled: bool) -> bool:
        return enabled

    def set_emulation_suppressed(self, value: bool | None = None) -> bool:
        return bool(value)


@pytest.fixture(autouse=True)
def _sem_relogio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zera a lightbar: estes testes medem DECISÃO, não relógio de pulso."""
    monkeypatch.setattr(hk, "PULSO_SEG", 0.0)


@pytest.fixture(autouse=True)
def _appid_fixo(monkeypatch: pytest.MonkeyPatch) -> None:
    """O gesto sozinho não sabe em que jogo está; quem sabe é o wrapper."""
    monkeypatch.setattr(hk, "_appid_do_jogo_do_wrapper", lambda: APPID)


def _abrir_como_no_lancamento(daemon: _Daemon, flavor: str, *, carimbo: bool) -> None:
    """Põe o daemon no estado em que `arm_launch_profile` o deixaria.

    Jogo COM carimbo: nenhuma tentativa (`proximo_degrau` recusa rodar). Jogo
    SEM carimbo e com `mode`: a tentativa abre PARADA no degrau do perfil — é
    a linha `ponte_escada_aberta motivo=perfil_manda` do journal dela.
    """
    if carimbo:
        return
    pt.comecar(
        daemon,
        appid=APPID,
        epoch=EPOCH,
        ponte_do_perfil=pe.Ponte(pe.KIND_GAMEPAD, flavor),
        confirmada=None,
        jogo_vivo=True,
        agora=0.0,
    )


async def _apertar(daemon: _Daemon, vezes: int) -> list[str]:
    """Aperta `PS + R3` e devolve a ponte de pé depois de cada aperto."""
    cb = hk.build_next_bridge_callback(daemon)  # type: ignore[arg-type]
    saida = []
    for _ in range(vezes):
        await cb()
        saida.append(hk.ponte_atual(daemon))
    return saida


# ---------------------------------------------------------------------------
# 1. A CONVERGÊNCIA — o teste que dá nome ao arquivo
# ---------------------------------------------------------------------------
class TestOGestoSeComportaIgual:
    @pytest.mark.asyncio
    async def test_as_quatro_sequencias_convergem(self) -> None:
        """Os quatro jogos dela, quatro apertos cada, a MESMA sequência.

        MEDIDO antes da cura, com este mesmo código: os três carimbados faziam
        `xbox -> mouse_teclado -> dualsense -> xbox` (4 trocas em 4 apertos), e
        o Sackboy fazia `xbox -> xbox -> mouse_teclado -> dualsense` — **3
        trocas em 4 apertos**, porque o 2º aperto pedia o degrau `native` e
        morria ali. Dali para a frente ele ficava um aperto atrasado, para
        sempre.

        MORDE a caminhada de `avancar_por_gesto`. Troque o `pulados.append` +
        `continue` por um `break` na primeira volta não alcançável (que é o
        comportamento de antes) e o Sackboy volta a divergir na posição 2.
        """
        sequencias: dict[str, list[str]] = {}
        for nome, flavor, carimbo in QUATRO_JOGOS:
            d = _Daemon(flavor)
            _abrir_como_no_lancamento(d, flavor, carimbo=carimbo)
            sequencias[nome] = await _apertar(d, 4)

        esperado = ["xbox", "mouse_teclado", "dualsense", "xbox"]
        assert sequencias["sackboy"] == esperado, (
            "o jogo SEM carimbo divergiu — é o defeito que ela chamou de "
            f"gambiarra. Sequências: {sequencias}"
        )
        assert len(set(map(tuple, sequencias.values()))) == 1, (
            "o gesto se comportou diferente conforme o jogo tivesse carimbo: "
            f"{sequencias}"
        )

    @pytest.mark.asyncio
    async def test_nenhum_aperto_e_comido(self) -> None:
        """Toda apertada troca a ponte. Quatro apertos, quatro trocas.

        É a régua direta do que ela usa o gesto para fazer: testar a ponte sem
        fechar o jogo. Um aperto que não troca nada é um teste que ela não
        consegue fazer.

        MORDE qualquer `return` antecipado em `_ciclar_ponte` antes do
        `_aplicar_ponte` — inclusive o ramo `PASSO_PAROU` que existia até hoje.
        """
        for nome, flavor, carimbo in QUATRO_JOGOS:
            d = _Daemon(flavor)
            _abrir_como_no_lancamento(d, flavor, carimbo=carimbo)
            await _apertar(d, 4)
            assert len(d.pedidos) == 4, (
                f"{nome}: {len(d.pedidos)} trocas em 4 apertos — "
                f"{4 - len(d.pedidos)} aperto(s) comido(s)"
            )


# ---------------------------------------------------------------------------
# 2. O DEGRAU CARO NÃO SOME EM SILÊNCIO
# ---------------------------------------------------------------------------
class TestOPuloSeAnuncia:
    @pytest.mark.asyncio
    async def test_a_lightbar_pisca_a_cor_do_degrau_pulado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ela tem de saber que o Nativo ficou para o lançamento.

        Pular em silêncio seria trocar um defeito por outro: hoje o aperto
        piscava e voltava (e ela não sabia por quê); amanhã trocaria e ela não
        saberia que um degrau ficou de fora.

        As cores não são novas — são as que ela mesma nomeou em 19/08: *"modo
        steam input azul clarinho, modo xbox verde claro, modo sony nativo
        branco"*. Até esta data `MODO_NATIVO` e `MODO_STEAM_INPUT` estavam em
        `CORES_DO_MODO` sem NINGUÉM que as pintasse.

        MORDE o laço `for degrau_pulado in passo.pulados` de `_ciclar_ponte`.
        """
        pintadas: list[tuple[int, int, int]] = []

        async def _espiao(daemon: Any, cores: list[Any]) -> None:
            pintadas.extend(cor for cor, _ in cores)

        monkeypatch.setattr(hk, "_sinalizar_lightbar", _espiao)

        d = _Daemon("dualsense")
        _abrir_como_no_lancamento(d, "dualsense", carimbo=False)
        await _apertar(d, 2)  # o 2º é o que encontra o degrau caro

        assert hk.CORES_DO_MODO[hk.MODO_NATIVO] in pintadas, (
            "o degrau `native` foi pulado sem ela ficar sabendo"
        )
        assert hk.CORES_DO_MODO[hk.MODO_STEAM_INPUT] in pintadas, (
            "o degrau `steam_input` foi pulado sem ela ficar sabendo"
        )

    @pytest.mark.asyncio
    async def test_o_journal_diz_qual_degrau_e_quanto_ele_custa(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`ponte_escada_pulou_o_degrau_caro`, com o preço de cada um.

        O journal é onde ela lê DEPOIS o que a lightbar disse na hora — foi
        assim que este defeito inteiro foi diagnosticado. Intercepta o
        `logger.warning` do módulo em vez do `caplog`: o structlog desta casa
        não passa pelo `logging` da stdlib, e um `caplog` vazio daria um teste
        que "passa" sem medir nada.

        MORDE o `logger.warning` da caminhada.
        """
        avisos: list[tuple[str, dict[str, Any]]] = []
        monkeypatch.setattr(
            pt.logger,
            "warning",
            lambda evento, **kw: avisos.append((evento, kw)),
        )

        d = _Daemon("dualsense")
        _abrir_como_no_lancamento(d, "dualsense", carimbo=False)
        await _apertar(d, 2)  # o 2º é o que encontra o degrau caro

        pulados = [kw for evento, kw in avisos if evento == "ponte_escada_pulou_o_degrau_caro"]
        assert [kw["pulado"] for kw in pulados] == [
            "native/-",
            "gamepad/dualsense+steam_input",
        ], f"o journal não anunciou os dois degraus pulados: {avisos}"
        # `preco` é o nome do kwarg no journal, não prosa.  # noqa: acentuacao
        assert [kw["preco"] for kw in pulados] == [  # noqa: acentuacao
            pe.SUBIR_REABRINDO_O_JOGO,
            pe.SUBIR_FECHANDO_A_STEAM,
        ], "não disse quanto cada degrau custa"


# ---------------------------------------------------------------------------
# 3. O QUE NÃO SE PODE PERDER — a escada continua valendo no LANÇAMENTO
# ---------------------------------------------------------------------------
class TestONativoNaoSePerdeEleMudaDeLugar:
    def test_a_escada_do_lancamento_nao_foi_tocada(self) -> None:
        """A cura mexe no GESTO e em nada mais. A prova, degrau a degrau.

        O risco declarado no enunciado desta cura era matar a feature que
        descobre a ponte sozinha. Ela não é tocada: `ESCADA`, `como_subir` e
        `comecar` ficaram como estavam, e é isso que este teste trava.

        MORDE uma cura que tivesse tirado o `native` da `ESCADA` (a lista
        encolheria) ou que tivesse resolvido o problema em `como_subir` (o
        preço com o jogo fora deixaria de ser `SUBIR_AGORA`).
        """
        assert [d.ponte.chave for d in pe.ESCADA] == [
            "gamepad/dualsense",
            "gamepad/xbox",
            "native/-",
            "gamepad/dualsense+steam_input",
        ], "a ESCADA mudou — a cura era para ser só no gesto"
        # Com o jogo FORA, os três primeiros degraus são de graça. É a regra
        # que separa o lançamento do gesto, e ela continua inteira.
        assert pe.como_subir(pe.ESCADA[2], jogo_vivo=False) == pe.SUBIR_AGORA
        assert pe.como_subir(pe.ESCADA[2], jogo_vivo=True) == (
            pe.SUBIR_REABRINDO_O_JOGO
        )
        assert pt.comecar(
            _Daemon("dualsense"),
            appid=APPID,
            epoch=EPOCH,
            ponte_do_perfil=None,  # o usuário novo: perfil sem `mode`
            confirmada=None,
            jogo_vivo=False,
            agora=0.0,
        ).armar == pe.ESCADA[0], "o lançamento parou de armar o primeiro degrau"

    def test_achado_o_nativo_nao_e_armado_por_caminho_nenhum(self) -> None:
        """MEDIDO em 30/08/2026, e NÃO consertado: o registro do buraco.

        É o mesmo achado que `2b6bc5f9` deixou escrito sem fechar — *"a escada
        nunca ARMA o Nativo nem o Steam Input... fechá-lo mexe no ramo 'o
        perfil manda', que é decisão dela"* — e esta régua o fixa em número.

        O ramo `perfil manda` de `comecar` arma `None` **por decisão**, e
        depois do primeiro alinhamento TODO perfil tem `mode`. Os quatro jogos
        dela têm. Logo o degrau `native` não é alcançado nem ao vivo (o gesto
        agora o pula) nem no lançamento (ninguém o arma).

        **Isto não é consequência da cura do gesto** — é anterior a ela, e é
        por isso que pular ao vivo não perde degrau nenhum: não havia o que
        perder.

        ESTE TESTE TEM DE FALHAR NO DIA EM QUE ALGUÉM CONSERTAR o ramo `perfil
        manda`. Quando falhar, a correção é apagar este teste e atualizar o §
        *O DEGRAU CARO NÃO PERTENCE AO GESTO* de `ponte_tentativa`, que hoje
        cita esta medição.
        """
        armados = []
        for ponte in (
            pe.Ponte(pe.KIND_GAMEPAD, pe.MASCARA_DUALSENSE),
            pe.Ponte(pe.KIND_GAMEPAD, pe.MASCARA_XBOX),
            pe.Ponte(pe.KIND_NATIVE),
        ):
            comeco = pt.comecar(
                _Daemon("dualsense"),
                appid=APPID,
                epoch=EPOCH,
                ponte_do_perfil=ponte,
                confirmada=None,
                jogo_vivo=False,
                agora=0.0,
            )
            armados.append((comeco.motivo, comeco.armar))

        assert all(motivo == pt.COMECO_PERFIL_MANDA for motivo, _ in armados)
        assert all(armar is None for _, armar in armados), (
            "o ramo `perfil manda` passou a armar — o buraco foi fechado. "
            "Apague este teste e atualize o cabeçalho de `ponte_tentativa`."
        )

    @pytest.mark.asyncio
    async def test_a_ponte_de_pe_e_guardada_para_o_lancamento_seguinte(self) -> None:
        """É ISTO que torna o pulo seguro, e é a metade de `2b6bc5f9` que fica.

        O pulo só não perde o degrau caro porque a ponte de pé no momento do
        pulo é GUARDADA (`a_registrar`) e o tique a grava no `mode` do perfil
        SEM carimbar. Sem essa gravação, o próximo lançamento recomeçaria do
        `mode` de antes e o Nativo nunca seria alcançado por caminho nenhum.

        MORDE o `_anotar_o_gesto(..., a_registrar=bool(pulados))` da caminhada.
        """
        d = _Daemon("dualsense")
        _abrir_como_no_lancamento(d, "dualsense", carimbo=False)
        await _apertar(d, 2)

        guardado = pt.gesto_em_curso(d)
        assert guardado is not None, "a ponte de pé evaporou com a tentativa"
        assert guardado.a_registrar is True, "não vai chegar ao perfil"
        assert guardado.ponte == pe.Ponte(pe.KIND_GAMEPAD, pe.MASCARA_XBOX), (
            f"guardou a ponte errada: {guardado.ponte.chave}"
        )


# ---------------------------------------------------------------------------
# 4. A RÉGUA VIVE NO TEMPO — a lição que `2b6bc5f9` pagou para aprender
# ---------------------------------------------------------------------------
class TestARéguaViveNoTempo:
    @pytest.mark.asyncio
    async def test_o_pulo_alinha_o_modo_e_nao_carimba_nem_depois_dos_181s(
        self,
    ) -> None:
        """O tique roda até t+181 s, e o carimbo NÃO pode nascer.

        A regressão que `2b6bc5f9` pegou: a régua rodava o tique UMA VEZ e
        afirmava que o degrau caro não carimba. A vida não para — 181 segundos
        depois o produto carimbava sozinho o degrau que ela acabou de recusar,
        e no lançamento seguinte a escada via `produto_ja_sabe`: **o caminho
        para o Modo Nativo morria**. Os 67 testes daquela leva passavam com o
        defeito de pé.

        Esta régua vive até os 181 s, e o pulo tem de sobreviver a ela.

        MORDE o `esquecer_o_gesto()` do ramo `a_registrar` em `_tique_do_gesto`
        (troque-o por `gesto.a_registrar = False` e veja o carimbo nascer aos
        181 s), e morde qualquer cura que carimbasse no pulo.
        """
        d = _Daemon("dualsense")
        _abrir_como_no_lancamento(d, "dualsense", carimbo=False)
        await _apertar(d, 2)

        alinhados: list[pe.Ponte] = []
        carimbados: list[pe.Ponte] = []
        # 1 Hz, de t=0 a t=181 s — o silêncio confirma aos 180.
        for segundo in range(182):
            t = float(segundo)
            resultado = pt.tique(d, jogo_vivo=True, agora=t)
            if resultado.alinhar is not None:
                alinhados.append(resultado.alinhar)
            if resultado.carimbar is not None:
                carimbados.append(resultado.carimbar)

        assert alinhados == [pe.Ponte(pe.KIND_GAMEPAD, pe.MASCARA_XBOX)], (
            f"o `mode` tinha de ser alinhado UMA vez, com `xbox`: {alinhados}"
        )
        assert carimbados == [], (
            "o produto carimbou sozinho um degrau que ninguém confirmou — "
            f"e com isso matou o caminho para o Modo Nativo: {carimbados}"
        )
