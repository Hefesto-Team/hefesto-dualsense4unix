"""FECHA-ILUMINACAO — a cor única, e a PROCEDÊNCIA que a fez parar de adivinhar.

`D-DUAS-PECAS-NUNCA-TEM-A-MESMA-COR` (`docs/data/decisoes-dela.csv:56`) é
**regra do produto, sempre**, e até 08/09/2026 não existia uma linha dela em
`src/`. A mesa dela provava: dois dos quatro DualSense guardavam no perfil as
cores dos slots **1 e 2**, e hoje eles são o **2 e o 4** — o número de outro dia
fossilizado no arquivo, com o rank 1 e o rank 2 acendendo o MESMO `#0000FF`.

**A PRIMEIRA VOLTA DESTA RÉGUA MENTIU, E ESTA NASCE DISSO.** Ela tinha um
`test_o_broadcast_dela_sobrevive` que punha **DOIS** controles e escolhia o
VERDE — que numa mesa de dois não é a cor do número de ninguém. *O nome do
teste prometia a mesa dela; o corpo mede o único arranjo em que o defeito não
aparece.* Na mesa de QUATRO, com os overrides dela, o mesmo broadcast saía
`[verde, vermelho, azul, rosa]`, com o P1 acendendo a cor do número do 3.

**ENTÃO TODA RÉGUA DESTE ARQUIVO EXERCITA QUATRO CONTROLES**, com os overrides
reais dela, e as três primeiras medem no PRODUTO: backend real
(`PyDualSenseController`), handler IPC real (`IpcServer._handle_led_set`) e
`reassert_resolved_outputs` real, com nós sysfs falsos para se poder LER o que
saiu no fio. É a mesma disciplina de `test_led_set_broadcast.py`, e é a única
que responde a pergunta *"que cor o plástico dela fica"*.
"""
from __future__ import annotations

import re
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.controller import ControllerState, OutputSpec
from hefesto_dualsense4unix.core.led_control import (
    DA_MAO,
    DA_PALETA,
    DO_BROADCAST,
    DO_GLOBAL,
    LEGADO,
    PecaDaMesa,
    cores_sem_colisao,
    player_slot_color,
)
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.manager import ProfileManager

RAIZ = Path(__file__).resolve().parents[2]
PAGINAS = RAIZ / "src/hefesto_dualsense4unix/interface/paginas"
BANCADA = RAIZ / "mockup"

#: A FORMA da mesa dela, medida em 08/09/2026 no `controllers.json` e no
#: `personalizado.json`: QUATRO controles, `auto_player_colors: true`, global
#: `[40,80,180]`, e override de cor em exatamente DOIS — os ranks 2 e 4,
#: guardando as cores dos slots **1 e 2**.
#:
#: OS ENDEREÇOS SÃO FORJADOS (`aa:bb:cc`), e não os dela mascarados: o que esta
#: régua mede é o PADRÃO — quem tem override e que cor ele guarda —, e a
#: identidade não entra na conta. Máscara não é anonimato em fixture
#: versionada; `test_anonimato_de_fixtures.py` reprova o MAC derivado de real
#: mesmo com os octetos 4 e 5 zerados, e está certo.
MACS = [f"AA:BB:CC:00:00:0{n}" for n in (1, 2, 3, 4)]
UNIQS = [f"aabbcc00000{n}" for n in (1, 2, 3, 4)]
RANK_DELA = {u: n for n, u in enumerate(UNIQS, start=1)}
OVERRIDE_DELA = {
    UNIQS[1]: player_slot_color(1),  # a cor do slot 1, no que hoje é o 2
    UNIQS[3]: player_slot_color(2),  # a cor do slot 2, no que hoje é o 4
}
GLOBAL_DELA = (40, 80, 180)
VERDE = (0, 255, 0)


# ---------------------------------------------------------------------------
# O PRODUTO REAL — backend, handler IPC e reassert de verdade
# ---------------------------------------------------------------------------
class _NoDeLed:
    """Nó sysfs falso: guarda o que SAIU no fio, que é o que ela vê no plástico."""

    def __init__(self) -> None:
        self.rgb: list[tuple[int, int, int]] = []

    def set_rgb(self, r: int, g: int, b: int, *, verify: bool = False) -> bool:
        self.rgb.append((r, g, b))
        return True

    def set_players(self, bits: Any) -> bool:
        return True

    def set_players_verified(self, bits: Any) -> bool:
        return True

    def invalidate_cache(self) -> None:
        return None


def _handle_falso() -> Any:
    """Handle pydualsense falso — `connected=True` é o que o `describe` lê.

    Sem ele o `describe_controllers` do backend REAL marca a entrada como
    desconectada, o fan-out por MAC nem é tentado, e a régua passaria pelo
    motivo errado (é a armadilha que `test_led_set_broadcast` já nomeia).
    """
    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

    return SimpleNamespace(
        connected=True, triggerL=DSTrigger(), triggerR=DSTrigger(),
        light=DSLight(), audio=DSAudio(),
        _raw_trigger_left=None, _raw_trigger_right=None,
    )


def _provider_da_identidade(ranks: dict[str, int], *, auto: bool = True) -> Any:
    """O provider automático com as DUAS companheiras do daemon.

    Mesmo contrato de `daemon/subsystems/identity.make_auto_output_provider`:
    a cor do slot, o `numero_do_slot` e o `uniqs_da_mesa`. Um dublê mais frouxo
    que o produto é como esta casa já envenenou duas medições — aqui as três
    respostas existem porque as três existem no daemon.
    """

    def provider(uniq: str) -> Any:
        slot = ranks.get(uniq)
        if slot is None or not auto:
            return None
        return bp._DesiredOutput(led=player_slot_color(slot))

    provider.numero_do_slot = ranks.get  # type: ignore[attr-defined]
    provider.uniqs_da_mesa = lambda: list(ranks)  # type: ignore[attr-defined]
    return provider


def _mesa_de_quatro(
    tmp_path: Path,
    *,
    overrides: dict[str, tuple[int, int, int]] | None = None,
    procedencias: dict[str, object] | None = None,
    auto: bool = True,
) -> tuple[IpcServer, bp.PyDualSenseController, dict[str, _NoDeLed]]:
    """Os quatro DualSense dela, no produto real, com o disco dela na camada certa.

    Os overrides entram pela porta do PERFIL (`reset_profile_overrides`), que é
    por onde eles chegam de verdade: é o `ProfileManager.apply` quem a chama, e
    é lá que a procedência do disco viaja junto.
    """
    ctl = bp.PyDualSenseController()
    ctl._handles = {m: _handle_falso() for m in MACS}
    nos = {m: _NoDeLed() for m in MACS}
    ctl._sysfs = dict(nos)
    ctl.set_auto_output_provider(_provider_da_identidade(RANK_DELA, auto=auto))
    # Sem jogo: a camada GAME fica FORA do merge. Quem a mede é o teste dela.
    ctl.set_game_authority_provider(lambda: "daemon")
    ctl.apply_output_defaults(OutputSpec(led=GLOBAL_DELA))
    if overrides is None:
        overrides = OVERRIDE_DELA
    if overrides:
        ctl.reset_profile_overrides(
            {u: OutputSpec(led=c) for u, c in overrides.items()},
            procedencias=procedencias,
        )
    store = StateStore()
    store.update_controller_state(ControllerState(
        battery_pct=100, l2_raw=0, r2_raw=0, connected=True, transport="usb"))
    server = IpcServer(
        controller=ctl, store=store,
        profile_manager=ProfileManager(controller=ctl, store=store),
        socket_path=tmp_path / "cor-unica.sock")
    return server, ctl, nos


def _no_fio(nos: dict[str, _NoDeLed]) -> list[tuple[int, int, int] | None]:
    """A última cor escrita em cada nó, na ordem do número."""
    return [nos[m].rgb[-1] if nos[m].rgb else None for m in MACS]


def _hexa(rgb: object) -> str:
    if not isinstance(rgb, tuple):
        return str(rgb)
    return "#" + "".join(f"{canal:02X}" for canal in rgb)


class TestAMesaDeQuatroNoProdutoReal:
    """As três medições que a segunda volta tinha de entregar."""

    @pytest.mark.asyncio
    async def test_o_broadcast_dela_pinta_os_quatro_de_verde(
        self, tmp_path: Path
    ) -> None:
        """(a) `led.set {rgb:[0,255,0]}` SEM `uniq` — o "pinta os quatro".

        Este é o teste que a primeira volta escreveu com DOIS controles e o
        verde, o único arranjo em que o defeito não aparece. Com QUATRO e os
        overrides dela, a primeira volta escrevia
        `[verde, vermelho, azul, rosa]`.

        **A MORDIDA:** faça `_e_fossil` (ou o ramo `DO_BROADCAST` de
        `cores_sem_colisao`) tratar o broadcast como escolha comum, e três dos
        quatro perdem o verde — com o P1 ficando com a cor do número do 3.
        """
        server, _ctl, nos = _mesa_de_quatro(tmp_path)

        await server._handle_led_set({"rgb": list(VERDE)})

        assert _no_fio(nos) == [VERDE] * 4, (
            f"o broadcast dela morreu na mesa de quatro: "
            f"{[_hexa(c) for c in _no_fio(nos)]}")

    @pytest.mark.asyncio
    async def test_o_broadcast_sobrevive_ao_proximo_reassert(
        self, tmp_path: Path
    ) -> None:
        """E ele tem de RESISTIR, não só ter sido a última escrita.

        A defesa de exibição (NUMA-03) e todo hotplug re-resolvem pelo mesmo
        merge. Se a cura vivesse só na escrita, o verde voltaria a virar paleta
        segundos depois — o defeito teria mudado de horário, não de existência.
        """
        server, ctl, nos = _mesa_de_quatro(tmp_path)
        await server._handle_led_set({"rgb": list(VERDE)})
        for no in nos.values():
            no.rgb.clear()

        ctl.reassert_resolved_outputs()

        assert _no_fio(nos) == [VERDE] * 4

    @pytest.mark.asyncio
    async def test_o_ipc_nao_diz_quatro_tendo_pintado_um(
        self, tmp_path: Path
    ) -> None:
        """`BROADCAST-QUE-NAO-MENTE-01`, ressuscitado e fechado de novo.

        A primeira volta respondia `aplicado_em` com os quatro MACs **tendo
        pintado um** de verde. A resposta e o fio têm de contar a MESMA
        história — é o que o nome daquela sprint promete.
        """
        server, _ctl, nos = _mesa_de_quatro(tmp_path)

        resposta = await server._handle_led_set({"rgb": list(VERDE)})

        verdes = [m for m in MACS if nos[m].rgb[-1] == VERDE]
        assert len(resposta["aplicado_em"]) == len(verdes), (
            f"o IPC disse {len(resposta['aplicado_em'])} e o fio mostra "
            f"{len(verdes)}")
        assert resposta["aplicado_em"] == UNIQS

    def test_sem_broadcast_as_quatro_cores_saem_distintas(
        self, tmp_path: Path
    ) -> None:
        """(b) O estado do disco dela, sem gesto nenhum: quatro cores, quatro.

        **A MORDIDA:** arranque `_com_cor_unica_locked` (devolva `r.saida`) e
        esta linha reprova com `3 de 4` — dois `#0000FF`, o rank 1 e o rank 2.
        É o número que ela mediu no daemon vivo em 08/09/2026.
        """
        _server, ctl, nos = _mesa_de_quatro(tmp_path)

        ctl.reassert_resolved_outputs()

        cores = _no_fio(nos)
        assert len(set(cores)) == 4, (
            f"duas peças ficaram da mesma cor: {[_hexa(c) for c in cores]}")
        assert cores == [ctl.resolved_led_for(u) for u in UNIQS], (
            "o fio e o leitor público discordam — a tela mostraria outra cor")

    def test_quem_pede_a_cor_do_proprio_numero_fica_com_ela(
        self, tmp_path: Path
    ) -> None:
        """(c) A regra sai na ordem CERTA, e a primeira volta a saía invertida.

        Lá o P1 ficava com o verde (a cor do número do 3) e o P3 com o azul (a
        do 1). Aqui cada um acende a cor do número dele: os dois sem override
        porque é a deles, e os dois com override porque o fóssil os devolve ao
        número de hoje.
        """
        _server, ctl, _nos = _mesa_de_quatro(tmp_path)

        assert [ctl.resolved_led_for(u) for u in UNIQS] == [
            player_slot_color(n) for n in (1, 2, 3, 4)
        ]

    @pytest.mark.asyncio
    async def test_o_gesto_por_controle_nao_pinta_o_vizinho(
        self, tmp_path: Path
    ) -> None:
        """Regressão do PERFIL-05 na mesa de quatro: com `uniq`, só um muda."""
        server, _ctl, nos = _mesa_de_quatro(tmp_path)
        roxo = (90, 20, 140)
        for no in nos.values():
            no.rgb.clear()

        resposta = await server._handle_led_set(
            {"rgb": list(roxo), "uniq": UNIQS[0]})

        assert resposta["aplicado_em"] == [UNIQS[0]]
        assert nos[MACS[0]].rgb[-1] == roxo
        # Os outros três CONTINUAM na cor do número deles. O reassert do
        # handler repinta a mesa inteira de propósito (é ele que faz o roxo
        # sobreviver ao merge), então "não pintou" se lê na COR, não na
        # contagem de escritas — contar escritas daria verde sobre a mesa
        # trocada, que é a família de defeito deste arquivo.
        assert _no_fio(nos)[1:] == [player_slot_color(n) for n in (2, 3, 4)], (
            "o gesto num controle mudou a cor dos outros três")

    def test_a_mesma_mesa_da_sempre_a_mesma_resposta(
        self, tmp_path: Path
    ) -> None:
        """Determinismo, e ele não é zelo: é o que impede a barra de piscar.

        Medido nesta casa em 05/09/2026 — devolver o endereço da fita fez a
        tela repintar 80 vezes em 80 tiques porque o valor tinha um segundo
        dono. Um passe que respondesse diferente na segunda volta faria a
        lightbar dela trocar de cor a cada batimento do reassert.
        """
        _server, ctl, _nos = _mesa_de_quatro(tmp_path)

        uma = [ctl.resolved_led_for(u) for u in UNIQS]
        outra = [ctl.resolved_led_for(u) for u in UNIQS]

        assert uma == outra

    def test_a_ordem_de_hotplug_nao_muda_a_resposta(
        self, tmp_path: Path
    ) -> None:
        """Quem religa primeiro não rouba a cor do vizinho.

        `_handles` é ordem de HOTPLUG. Se o passe lesse dela, a mesa inteira
        trocaria de cor a cada religada — o mesmo defeito que o
        `_assentar_mesa_locked` fechou no NÚMERO, de volta na COR.
        """
        _s1, ctl, _n1 = _mesa_de_quatro(tmp_path)
        esperado = [ctl.resolved_led_for(u) for u in UNIQS]

        _s2, de_tras, _n2 = _mesa_de_quatro(tmp_path)
        de_tras._handles = dict(reversed(list(de_tras._handles.items())))

        assert [de_tras.resolved_led_for(u) for u in UNIQS] == esperado


class TestAProcedenciaEOQueElaLe:
    """O campo de 08/09/2026 — o resolvedor LÊ, e parou de adivinhar."""

    def test_a_cor_escolhida_para_outro_numero_e_fossil(
        self, tmp_path: Path
    ) -> None:
        """A decisão dela, palavra por palavra: *"quando o número daquele
        aparelho muda, a cor gravada é FÓSSIL e sai sozinha"*.

        Aqui o roxo NÃO é a cor do número de ninguém — a primeira volta o
        manteria, porque só sabia provar fóssil pela forma. Com a procedência
        gravada dizendo "escolhido para o número 1" num aparelho que hoje é o
        2, ele sai.

        **A MORDIDA:** faça `_e_fossil` ignorar a procedência inteira e o roxo
        fica — a cor de um dia que passou continua acesa.
        """
        roxo = (90, 20, 140)
        _s, ctl, _n = _mesa_de_quatro(
            tmp_path,
            overrides={UNIQS[1]: roxo},
            procedencias={UNIQS[1]: 1},
        )

        assert ctl.resolved_led_for(UNIQS[1]) == player_slot_color(2), (
            "o fóssil declarado ficou aceso")

    def test_a_cor_escolhida_para_o_numero_de_hoje_fica(
        self, tmp_path: Path
    ) -> None:
        """E uma escolha VIVA sobrevive, mesmo sendo um tom qualquer.

        É a outra metade da mesma linha, e sem ela a cura seria "apagar tudo":
        um perfil com procedência certa não pode perder a cor dela.
        """
        roxo = (90, 20, 140)
        _s, ctl, _n = _mesa_de_quatro(
            tmp_path,
            overrides={UNIQS[1]: roxo},
            procedencias={UNIQS[1]: 2},
        )

        assert ctl.resolved_led_for(UNIQS[1]) == roxo

    def test_o_legado_do_disco_ainda_prova_fossil_pela_forma(
        self, tmp_path: Path
    ) -> None:
        """Perfil ESCRITO ANTES do campo: sem carimbo, a regra volta à forma.

        É o disco dela hoje, e é a razão de `LEGADO` existir em vez de "sem
        procedência = fóssil": um roxo escolhido de verdade num perfil antigo
        sobrevive à migração; a cor do número de OUTRO da mesa não.
        """
        roxo = (90, 20, 140)
        _s, ctl, _n = _mesa_de_quatro(
            tmp_path, overrides={UNIQS[1]: roxo, UNIQS[3]: player_slot_color(1)})

        assert ctl.resolved_led_for(UNIQS[1]) == roxo, "o legado honesto sumiu"
        assert ctl.resolved_led_for(UNIQS[3]) == player_slot_color(4), (
            "o legado fóssil ficou aceso")

    def test_o_carimbo_do_broadcast_vence_a_forma_da_cor(self) -> None:
        """O caso que derrubou a primeira volta, medido na REGRA.

        Os quatro pedem o VERDE, que é a cor do número do 3 — a forma diz
        "fóssil" para três deles. O carimbo diz "Todos", e o carimbo manda.
        """
        mesa = [
            PecaDaMesa(uniq=u, pedida=VERDE, do_numero=player_slot_color(n),
                       procedencia=DO_BROADCAST, numero=n)
            for n, u in enumerate(UNIQS, start=1)
        ]

        assert cores_sem_colisao(mesa) == dict.fromkeys(UNIQS, VERDE)

    def test_o_perfil_leva_a_procedencia_do_disco_ao_backend(self) -> None:
        """`LedsConfig.lightbar_para_o_numero` → `_controllers_to_procedencias`.

        Sem esta ponte, o campo existiria no arquivo e o resolvedor nunca o
        leria — que é a família de defeito que esta casa chama de "campo que
        grava e ninguém lê".
        """
        from hefesto_dualsense4unix.profiles.manager import (
            _controllers_to_procedencias,
        )
        from hefesto_dualsense4unix.profiles.schema import (
            ControllerOverrides,
            LedsConfig,
        )

        controles = {
            UNIQS[0]: ControllerOverrides(leds=LedsConfig(
                lightbar=(1, 2, 3), lightbar_para_o_numero=3)),
            UNIQS[1]: ControllerOverrides(leds=LedsConfig(lightbar=(4, 5, 6))),
            # só brilho: não materializa cor, então não tem procedência
            UNIQS[2]: ControllerOverrides(leds=LedsConfig(
                lightbar_brightness=0.5)),
        }

        assert _controllers_to_procedencias(controles) == {
            UNIQS[0]: 3,
            UNIQS[1]: LEGADO,
        }

    def test_o_interruptor_congela_a_cor_com_o_numero_de_hoje(self) -> None:
        """Desligar o automático GRAVA a cor de cada um — e agora com o número.

        Ele congelava "azul" e perdia "azul porque ele era o 1", que é
        exatamente como os fósseis nasciam.

        **FATO SUBSTITUÍDO — 09/09/2026.** Estas linhas diziam que este era *"o
        único caminho da aba que escreve cor no disco"*, e era verdade — era
        também o defeito: a cor que ela ESCOLHIA não ia a lugar nenhum, e
        voltava ao azul no primeiro replug. Agora `_escrever_a_cor` grava toda
        escolha dela pelo mesmo `_com_a_cor_gravada`; ver
        `test_a_cor_escolhida_vai_ao_disco_e_o_trilho_nao_reescala.py`.

        **A MORDIDA:** tire o `numero` de `_com_a_cor_gravada` e o campo volta
        a nascer `None` — todo perfil novo já nasceria `LEGADO`.
        """
        from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04
        from hefesto_dualsense4unix.profiles.schema import (
            LedsConfig,
            MatchManual,
            Profile,
        )

        prof = Profile(name="regua", match=MatchManual())
        novo = a04._com_a_cor_gravada(prof, UNIQS[0], player_slot_color(2), 2)

        leds = novo.controllers[a04.chave_do_override(UNIQS[0])].leds
        assert isinstance(leds, LedsConfig)
        assert leds.lightbar == player_slot_color(2)
        assert leds.lightbar_para_o_numero == 2


class TestOsBuracosDaPrimeiraVolta:
    """Os cinco que o conferente mediu, cada um com a sua linha."""

    def test_a_cor_global_entra_na_mesa(self, tmp_path: Path) -> None:
        """O `if not r.cor_por_controle: continue` deixava o global de FORA.

        Medido pelo conferente: um controle numerado em azul automático ao
        lado de um que cai no azul GLOBAL ficava com dois `#0000FF`. Quem cede
        é o do global — ele não tem identidade a defender.

        **A MORDIDA:** devolva o `continue` e os dois voltam a `#0000FF`.
        """
        # o `d4` some da mesa do provider (fica sem número e sem automática) e
        # o global do perfil é EXATAMENTE o azul do número 1.
        ranks = {u: n for n, u in enumerate(UNIQS[:3], start=1)}
        inst = _backend_cru(ranks, {}, global_=player_slot_color(1))
        inst._handles = dict.fromkeys(MACS)

        cores = [inst.resolved_led_for(u) for u in UNIQS]

        assert cores[0] == player_slot_color(1)
        assert cores[3] != cores[0], (
            f"o do global ficou igual ao numerado: {[_hexa(c) for c in cores]}")

    def test_dois_overrides_iguais_com_o_automatico_desligado(
        self, tmp_path: Path
    ) -> None:
        """`auto_player_colors: false` — sem paleta, a regra ainda vale.

        Sem camada automática ninguém tem `do_numero`, então a prova por forma
        não alcança nada: os dois overrides idênticos ficavam os dois
        `#0000FF`. Quem separa agora é a ordem do número — o primeiro fica, o
        segundo se acomoda no primeiro tom livre.
        """
        _s, ctl, _n = _mesa_de_quatro(
            tmp_path,
            overrides={UNIQS[0]: player_slot_color(1),
                       UNIQS[1]: player_slot_color(1)},
            auto=False,
        )

        cores = [ctl.resolved_led_for(u) for u in UNIQS[:2]]
        assert cores[0] == player_slot_color(1)
        assert cores[1] != cores[0], f"os dois ficaram {_hexa(cores[0])}"

    def test_o_todos_global_do_perfil_nao_e_colisao(self) -> None:
        """D4: pintar os quatro com a cor GLOBAL é um ato dela, não um defeito.

        É o limite da linha de cima, e sem ele "a cor global entra na mesa"
        viraria "a cor global some da mesa": quatro controles sem opinião
        própria acendem a cor do perfil, e nenhum deles cede a nenhum outro.
        """
        mesa = [
            PecaDaMesa(uniq=u, pedida=GLOBAL_DELA, do_numero=None,
                       procedencia=DO_GLOBAL, numero=n)
            for n, u in enumerate(UNIQS, start=1)
        ]

        assert cores_sem_colisao(mesa) == dict.fromkeys(UNIQS, GLOBAL_DELA)

    def test_dois_controles_acima_do_oito_nao_ficam_os_dois_brancos(
        self,
    ) -> None:
        """`player_slot_color(slot)` devolve BRANCO para todo slot ≥ 9.

        O irmão `player_led_pattern` tem `_PLAYER_LED_OVERFLOW` documentado
        como *"só colide consigo mesmo"*; a cor não tinha essa garantia, e a
        docstring dela não a reivindicava.
        """
        branco = player_slot_color(9)
        mesa = [
            PecaDaMesa(uniq="u9", pedida=branco, do_numero=branco,
                       procedencia=DA_PALETA, numero=9),
            PecaDaMesa(uniq="u10", pedida=branco, do_numero=branco,
                       procedencia=DA_PALETA, numero=10),
        ]

        saida = cores_sem_colisao(mesa)

        assert saida["u9"] != saida["u10"], "os dois ficaram brancos"

    def test_o_merge_responde_sem_o_mapa_de_handles(self) -> None:
        """O CRASH que a primeira volta não declarou, e é a régua dele.

        `AttributeError: 'PyDualSenseController' object has no attribute
        '_handles'` dentro do `_mesa_de_cores_locked`: a regra de cor única é
        a ÚNICA parte do merge que olha para fora da chave que resolve, e ela
        transformou um merge que respondia numa exceção. Quem sabe quem está
        na mesa é a IDENTIDADE, e é de lá que a lista vem agora.

        **A MORDIDA:** volte a ler `self._handles` como fonte única da mesa e
        esta linha levanta de novo — foi assim que
        `test_troca_de_player_01_a_escolha_sobrepoe.py` ficou vermelho.
        """
        inst = object.__new__(bp.PyDualSenseController)
        inst._key_to_uniq = lambda k: k
        inst._desired_default = bp._DesiredOutput()
        inst._assentar_mesa_locked = lambda: None
        inst._auto_output_provider = _provider_da_identidade(RANK_DELA)
        inst._desired_coop_by_uniq = {}
        inst._scaled_led = lambda uniq, resolvido: resolvido
        inst._game_output_by_uniq = {}
        inst._game_wins = lambda: False
        inst._desired_by_uniq = {UNIQS[1]: bp._DesiredOutput(led=(128, 0, 255))}

        assert inst._merged_desired_for_key(UNIQS[1]).led == (128, 0, 255)
        assert inst._merged_desired_for_key(UNIQS[0]).led == player_slot_color(1)

    def test_a_barra_apagada_nao_e_colisao(self) -> None:
        """Preto é AUSÊNCIA de cor, não identidade.

        Deslocar uma barra apagada acenderia um controle que ela mandou
        apagar — e duas apagadas não são duas peças confundíveis: "as duas
        estão desligadas" é uma resposta.
        """
        mesa = [
            PecaDaMesa(uniq=u, pedida=(0, 0, 0),
                       do_numero=player_slot_color(n),
                       procedencia=DA_MAO, numero=n)
            for n, u in enumerate(UNIQS, start=1)
        ]

        assert cores_sem_colisao(mesa) == dict.fromkeys(UNIQS, (0, 0, 0))

    def test_o_jogo_pinta_por_cima_da_regra(self, tmp_path: Path) -> None:
        """A camada GAME fica ACIMA do passe, como já fica acima do brilho.

        Deslocar a cor que o jogo pediu seria mentir sobre o que ele pediu —
        é a mesma razão do R-20 item 2.
        """
        _s, ctl, _n = _mesa_de_quatro(tmp_path)
        ctl.set_game_authority_provider(lambda: "game")
        assert ctl.set_game_output_for(MACS[1], led=player_slot_color(1)) is True

        assert ctl.resolved_led_for(UNIQS[1]) == player_slot_color(1)


class TestARecusaComAMesaCheia:
    """Oito tons em uso: recusa, não gira."""

    def test_com_os_oito_tomados_a_cor_pedida_fica_como_esta(self) -> None:
        """Girar com a mesa cheia trocaria a cor de todo mundo a cada tique."""
        mesa = [
            PecaDaMesa(uniq=f"u{n}", pedida=player_slot_color(n),
                       do_numero=player_slot_color(n),
                       procedencia=DA_PALETA, numero=n)
            for n in range(1, 9)
        ]
        # o nono pede a cor do primeiro, e não sobra tom livre
        mesa.append(PecaDaMesa(uniq="u9", pedida=player_slot_color(1),
                               do_numero=None, procedencia=LEGADO, numero=9))

        saida = cores_sem_colisao(mesa)

        assert saida["u9"] == player_slot_color(1), (
            "com as oito tomadas a regra tem de RECUSAR, não girar")
        assert saida["u1"] == player_slot_color(1), "girou e tirou a cor do dono"


def _backend_cru(
    ranks: dict[str, int],
    overrides: dict[str, tuple[int, int, int]],
    *,
    global_: tuple[int, int, int] = GLOBAL_DELA,
) -> bp.PyDualSenseController:
    """Backend montado à mão — para os estados que o produto não sabe POR.

    Usado só onde a mesa precisa divergir do provider (um controle com handle
    aberto e FORA da mesa da identidade), que é um estado real e transitório
    do rádio dela e que a porta pública não sabe construir.
    """
    inst = bp.PyDualSenseController.__new__(bp.PyDualSenseController)
    inst._io_lock = threading.RLock()
    inst._handles = dict.fromkeys(ranks)
    inst._desired_default = bp._DesiredOutput(led=global_)
    inst._desired_by_uniq = {
        u: bp._DesiredOutput(led=c) for u, c in overrides.items()
    }
    inst._desired_coop_by_uniq = {}
    inst._game_output_by_uniq = {}
    inst._led_scale_by_uniq = {}
    inst._mesa_apresentada = frozenset()
    inst._game_authority_provider = None
    inst._procedencia_da_cor = {}
    inst._auto_output_provider = _provider_da_identidade(ranks)
    return inst


class _CtxDeMentira:
    """A mesa DE QUATRO dela, do lado da tela.

    Ela existia com DOIS, e a razão de crescer é a mesma do arquivo inteiro:
    numa mesa de dois metade dos tons da paleta está livre, e uma guarda que
    desloca sempre acha para onde. Com quatro, a conta aperta.
    """

    def __init__(self) -> None:
        self.state: dict[str, Any] = {"active_profile": ""}
        self.conectados: list[dict[str, Any]] = [
            {"uniq": u, "lightbar_rgb": list(player_slot_color(n)),
             "player_slot": n}
            for n, u in enumerate(UNIQS, start=1)
        ]
        self.mesa: list[dict[str, Any]] = [
            {"uniq": u, "jogador": n, "nome": "DualSense"}
            for n, u in enumerate(UNIQS, start=1)
        ]


class _PonteQueAceita:
    """Ponte falsa que responde o corpo do caminho FELIZ do `led.set`."""

    def __init__(self) -> None:
        self.cores: list[tuple[Any, dict[str, Any]]] = []

    def led_set_detalhado(self, rgb: Any, **kwargs: Any) -> dict[str, Any]:
        self.cores.append((tuple(rgb), dict(kwargs)))
        return {"status": "ok",
                "aplicado_em": [kwargs.get("uniq")], "guardado_em": []}

    def __getattr__(self, nome: str) -> Any:
        return lambda *a, **k: True


class TestOGestoDaAba:
    """A metade que só a TELA cumpre — a frase que diz de quem é a cor."""

    def test_escolher_o_tom_do_vizinho_recusa_e_diz_de_quem_e(self) -> None:
        """A cor com dono RECUSA — decisão dela, 09/09/2026.

        **FATO SUBSTITUÍDO.** Este teste chamava-se
        `test_escolher_o_tom_do_vizinho_desloca_e_diz_de_quem_e` e mediu o
        deslocamento — *"o segundo desloca para o tom vizinho"* —, que existiu
        de 08/09 a 09/09. Ela decidiu o contrário
        (`D-0909-A-COR-DE-OUTRO-CONTROLE-SE-RECUSA-COM-X`), e o deslocamento
        era uma terceira coisa: ela clicava num tom e o aparelho acendia
        OUTRO, escolhido pelo produto.

        **A MORDIDA:** faça `_sem_repetir_a_cor_do_vizinho` devolver
        `(rgb, None)` quando há dono e nada recusa — a cor sai repetida e ela
        não sabe de quem era o tom.
        """
        from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

        with pytest.raises(RuntimeError) as erro:
            a04._sem_repetir_a_cor_do_vizinho(
                _CtxDeMentira(), UNIQS[0], player_slot_color(2))

        frase = str(erro.value)
        assert "P2" in frase, f"a tela não disse de quem é: {frase}"
        assert "Nada foi mudado" in frase, (
            f"a recusa não diz que o aparelho ficou como estava: {frase}")

    def test_a_guia_desenha_o_x_exatamente_no_que_o_gesto_recusa(self) -> None:
        """As duas metades da regra leem a MESMA mesa — COR-X-01.

        Uma tela que oferece o que o gesto recusa é pior do que uma que não
        oferece nada: ela clica, o produto diz não, e a culpa parece dela.

        **A MORDIDA:** faça `fileira_de_tons` ignorar `tomadas` e o X some,
        enquanto o gesto continua recusando.
        """
        from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

        tomado = _hexa(player_slot_color(2))
        html = a04.fileira_de_tons(
            _hexa(player_slot_color(1)),
            {tomado: {"nome": "P2 (DualSense)", "plastico": "#1c1c1c"}})

        casas = [linha for linha in html.splitlines() if "data-hex" in linha]
        assert len(casas) == len(a04.tons_da_guia())
        do_vizinho = [c for c in casas if f'data-hex="{tomado}"' in c]
        assert len(do_vizinho) == 1
        assert "tomado" in do_vizinho[0], "a casa do vizinho não ganhou o X"
        assert "--dono:#1c1c1c" in do_vizinho[0], (
            "o X não saiu na cor do plástico de quem tem o tom")
        assert "P2 (DualSense)" in do_vizinho[0], "o X não diz de quem é"
        # a MINHA cor ganha o anel, e nunca o X
        minha = [c for c in casas if f'data-hex="{_hexa(player_slot_color(1))}"' in c]
        assert "tom on" in minha[0] and "tomado" not in minha[0]

    def test_um_lugar_sem_controle_nao_ganha_anel_nem_x(self) -> None:
        """Não há escolha a marcar e não há dono a proteger — COR-X-01 §3.4.

        **A MORDIDA:** tire o `if ligado` da conta do `on` e o lugar vazio
        passa a afirmar uma cor que ninguém escolheu.
        """
        from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

        html = a04.fileira_de_tons(
            _hexa(player_slot_color(1)),
            {_hexa(player_slot_color(2)): {"nome": "P2", "plastico": "#1c1c1c"}},
            ligado=False)

        assert "tom on" not in html
        assert "tomado" not in html

    def test_o_reenviar_passa_pela_mesma_porta_que_o_cor(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A SEGUNDA porta de escolha de cor não tinha a regra da primeira.

        A caixa `#RRGGBB` alcança o tom EXATO de outra coluna — é literalmente
        o texto que a outra coluna imprime —, então era a porta mais barata
        para pôr duas peças da mesma cor. E a docstring do `_escrever_a_cor`
        já prometia uma porta só.

        **A MORDIDA:** tire o `escolha=True` do `reenviar` e a cor pedida sai
        no fio como veio, igual à do vizinho.
        """
        from hefesto_dualsense4unix.interface import pacotes
        from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

        monkeypatch.setattr(a04.perfil, "ativo", lambda _nome: {})
        ponte = _PonteQueAceita()
        vizinho = _hexa(player_slot_color(2))

        # PELO DESPACHANTE, e não pela função: é o caminho do CLIQUE. Um teste
        # que chama `a04.reenviar` direto passaria com o `data-gesto` da página
        # apontando para lugar nenhum, que é o defeito que esta casa nomeia
        # como "botão que aceita o toque e não age".
        atende = pacotes.gesto_da_pagina("04-iluminacao.html", "reenviar")
        assert atende is not None, "ninguém atende o `reenviar` da página 04"
        with pytest.raises(RuntimeError) as erro:
            atende(_CtxDeMentira(), {"uniq": UNIQS[0], "texto": vizinho}, ponte)

        assert "P2" in str(erro.value)
        assert not ponte.cores, (
            "o reenviar escreveu no aparelho apesar da recusa — "
            "«Nada foi mudado» tem de ser verdade")

    def test_o_tom_livre_passa_calado(self) -> None:
        """Sem colisão não há frase — recado sobre nada é ruído."""
        from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

        alvo, recado = a04._sem_repetir_a_cor_do_vizinho(
            _CtxDeMentira(), UNIQS[0], (90, 20, 140))

        assert alvo == (90, 20, 140)
        assert recado is None

    def test_apagar_nao_passa_pela_guarda(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """"Desligar" manda PRETO, e preto não colide com nada.

        Se o preto passasse pela guarda, apagar o segundo controle acenderia
        uma cor nova nele — o oposto do que o botão promete.
        """
        from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

        monkeypatch.setattr(a04.perfil, "ativo", lambda _nome: {})
        ponte = _PonteQueAceita()

        a04.apagar(_CtxDeMentira(), {"uniq": UNIQS[0]}, ponte)

        assert ponte.cores[-1][0] == (0, 0, 0)


#: O NOME DO BOTÃO QUE MORREU, **NAS DUAS GRAFIAS**. Ele saiu da aba no
#: `2c228352` — o gesto foi junto, e a página só conhece `apagar`,
#: `auto-cores`, `brilho`, `cor`, `player` e `reenviar`.
#:
#: A PRIMEIRA VERSÃO SÓ CASAVA A ACENTUADA (`"autom"+"ático"`), e o bloco que
#: vazou na tela escrevia a forma SEM acento — a régua deu verde por cima do
#: defeito que ela existia para pegar. Uma régua que mede uma grafia de uma
#: palavra que a casa escreve nas duas é meia régua.
_BOTAO_MORTO = re.compile("autom" + "[áa]tico", re.I)


def _comentarios_aninhados(html: str) -> list[int]:
    """As linhas em que um `<!--` abre DENTRO de um comentário já aberto.

    **COMENTÁRIO HTML NÃO ANINHA**, e é a quinta forma da armadilha da prosa
    nesta casa: o `-->` de dentro FECHA o de fora, e todo o resto do bloco
    vira CORPO VISÍVEL. Em 08/09/2026 um `<!-- noqa-acento -->` escrito dentro
    da nota de um widget pôs na tela dela a prosa de projeto e um hash de
    commit — o defeito que a própria nota dizia estar curando.

    A régua olha a FORMA, e é por isso que ela é uma régua e não uma lista:
    nenhuma palavra proibida a alcança, porque o texto que vaza é diferente a
    cada vez.
    """
    achados: list[int] = []
    i = 0
    while True:
        abre = html.find("<!--", i)
        if abre < 0:
            return achados
        fecha = html.find("-->", abre + 4)
        if fecha < 0:
            return achados
        dentro = html.find("<!--", abre + 4)
        if 0 <= dentro < fecha:
            achados.append(html.count("\n", 0, dentro) + 1)
        i = fecha + 3


class TestAProsaQueVaiPararNaTela:
    """*"Ainda temos 3 cantos falando sobre o automatico"* — palavra dela."""  # noqa-acento: citação literal dela

    @pytest.mark.parametrize("pasta", [PAGINAS, BANCADA])
    def test_a_pagina_04_nao_fala_do_botao_que_saiu(self, pasta: Path) -> None:
        """NAS DUAS LEITURAS, e a diferença entre elas é o ponto.

        `texto_visivel_no_produto` desconta o que a
        `interface/folha_da_casa.FOLHA_DA_CASA` esconde (`.nota`); a bancada é
        o que ela abre NO NAVEGADOR, sem folha nenhuma. Uma régua só do
        produto daria VERDE sobre as duas ocorrências da legenda — que é a
        assinatura de instrumento falso que esta casa persegue.

        **A MORDIDA:** devolva à dica do interruptor a frase que explicava o
        botão por coluna, ou à legenda o item que narrava a saída dele, e a
        linha correspondente reprova. **E a mordida de 08/09:** devolva o
        comentário HTML aninhado ao gerador, regere, e esta linha pega o
        vazamento — porque agora ela casa também a forma sem acento.
        """
        from hefesto_dualsense4unix.interface.frases_que_ela_baniu import (
            texto_visivel,
            texto_visivel_no_produto,
        )

        ler = texto_visivel if pasta is BANCADA else texto_visivel_no_produto
        texto = ler((pasta / "04-iluminacao.html").read_text(encoding="utf-8"))

        achados = _BOTAO_MORTO.findall(texto)

        assert achados == [], (
            f"{pasta.name}/04-iluminacao.html ainda fala do botão que saiu, "
            f"{len(achados)} vez(es)")

    @pytest.mark.parametrize("pasta", [PAGINAS, BANCADA])
    def test_nenhuma_pagina_tem_comentario_html_aninhado(
        self, pasta: Path
    ) -> None:
        """A régua ESTRUTURAL da armadilha da prosa, e ela é nova.

        As dez abas de uma vez: o defeito não é da 04, é da FORMA — qualquer
        gerador pode escrever a nota de dentro sem saber que fecha a de fora.
        Uma régua por página seria a nona vez que esta casa cura um lugar e
        deixa dezoito.

        **A MORDIDA:** ponha um `<!-- noqa -->` dentro de qualquer `<!-- … -->`
        de qualquer gerador, regere, e a linha daquela página reprova com o
        número dela.
        """
        vazamentos = {
            html.name: _comentarios_aninhados(html.read_text(encoding="utf-8"))
            for html in sorted(pasta.glob("*.html"))
        }
        sujas = {nome: linhas for nome, linhas in vazamentos.items() if linhas}

        assert sujas == {}, (
            f"comentário HTML aninhado em {pasta.name} — o `-->` de dentro "
            f"fecha o de fora e o resto vira corpo visível: {sujas}")

    def test_a_legenda_nao_narra_commit_nem_cita_decisao_dela(self) -> None:
        """A tela não é changelog — regra dela, 07/09/2026.

        *"O app tem que funcionar e não mostrar na tela que o app não presta.
        (...) o layout não informa os nossos defeitos."*
        """
        from hefesto_dualsense4unix.interface.frases_que_ela_baniu import (
            texto_visivel,
        )

        texto = texto_visivel(
            (BANCADA / "04-iluminacao.html").read_text(encoding="utf-8"))

        for frase in ("O que mudou hoje", "Ainda aberto", "tongle",
                      "pedido seu", "decisão sua", "2c228352"):
            assert frase not in texto, f"a tela ainda narra: {frase!r}"


class TestORecadoQueMentia:
    """A frase do interruptor, e o comentário que a gerou."""

    def test_a_frase_nao_promete_o_que_o_produto_nao_faz(self) -> None:
        """*"Cada controle volta a acender a cor do número dele"* era FALSA.

        A camada automática está ABAIXO do override por-uniq no
        `_merged_desired_for_key`, então uma cor gravada continua vencendo —
        e dois dos quatro controles dela tinham uma. A frase de hoje diz as
        duas metades: quem não tem cor própria acende a do número, e duas
        nunca ficam iguais (que é a promessa que o passe agora cumpre).
        """
        from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao

        frase = a04_iluminacao._RECADO_DO_AUTOMATICO_VOLTOU

        assert "sem cor própria" in frase, (
            "a frase voltou a prometer a cor do número para TODO controle")
        assert "duas nunca ficam iguais" in frase
