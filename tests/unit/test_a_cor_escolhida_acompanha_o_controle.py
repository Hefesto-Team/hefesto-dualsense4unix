"""A cor escolhida acompanha o controle — `D-2909-A-COR-ESCOLHIDA-ACOMPANHA-O-CONTROLE`.

Ela respondeu em 29/09/2026 (~21h40) que a cor de um controle não muda quando a mesa
se renumera: *«Acompanha o controle»*. A regra de 08/09 dizia o contrário (a cor presa
ao número, fóssil quando o número mudava) e foi a que apagou o laranja e o verde-água
às 02:51 de 29/09, quando o vermelho caiu e a mesa se renumerou.

Três réguas na REGRA (`PecaDaMesa` → `fosseis`/`cores_sem_colisao`) e uma no PRODUTO
(`PyDualSenseController`), com a cena das 02:51 reencenada: nenhuma mede a própria saída.

**As mordidas** (cada uma arranca a cura da sua régua e vê reprovar):

1. `_e_fossil` com a linha `peca.numero is None or peca.procedencia != peca.numero`
   de volta → as réguas 1 e a do produto reprovam;
2. `_e_fossil` tratando o legado como escolha (`return False` antes da prova pela
   forma) → a régua 2 reprova;
3. `_repetida` sem consultar `escolhas_que_ficam` para a cor da paleta → a régua 3
   reprova (a automática vence a escolha);
4. `_repetida` com o `if peca.do_plastico is None: return False` de volta → a automática
   do número sem o plástico vence a escolha que voltou noutro número, e a régua 3 reprova;
   a vizinhança ligada também sem o plástico reprova a régua do tom vizinho.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.controller import OutputSpec
from hefesto_dualsense4unix.core.led_control import (
    DA_PALETA,
    LEGADO,
    PecaDaMesa,
    cores_sem_colisao,
    fosseis,
    player_slot_color,
)

UNIQS = [f"aabbcc00000{n}" for n in (1, 2, 3, 4)]
MACS = [f"AA:BB:CC:00:00:0{n}" for n in (1, 2, 3, 4)]
LARANJA = (255, 140, 0)
VERDE_AGUA = (0, 200, 170)
GLOBAL_DELA = (40, 80, 180)


def _automatica(uniq: str, numero: int) -> PecaDaMesa:
    """Um controle sem escolha: acende o tom do número dele."""
    cor = player_slot_color(numero)
    return PecaDaMesa(uniq=uniq, pedida=cor, do_numero=cor,
                      procedencia=DA_PALETA, numero=numero)


def _escolhida(uniq: str, cor: tuple[int, int, int], para: int, numero: int
               ) -> PecaDaMesa:
    """Um controle com cor escolhida à mão para o número `para`, hoje no `numero`."""
    return PecaDaMesa(uniq=uniq, pedida=cor, do_numero=player_slot_color(numero),
                      procedencia=para, numero=numero)


class TestAEscolhaAtravessaARenumeracao:
    """Régua 1 — a escolha de um controle fica nele, em qualquer número."""

    def test_a_escolha_do_p3_que_virou_p2_nao_e_fossil(self) -> None:
        """Escolhida com procedência 3; o P2 saiu e o P3 virou P2."""
        mesa = [
            _automatica(UNIQS[0], 1),
            _escolhida(UNIQS[2], LARANJA, para=3, numero=2),
            _escolhida(UNIQS[3], VERDE_AGUA, para=4, numero=3),
        ]

        assert fosseis(mesa) == frozenset(), "a cor escolhida saiu do controle"
        saida = cores_sem_colisao(mesa)
        assert saida[UNIQS[2]] == LARANJA
        assert saida[UNIQS[3]] == VERDE_AGUA

    def test_o_numero_que_sumiu_tambem_nao_faz_fossil(self) -> None:
        """Controle fora da mesa (sem número): a escolha ainda é dele."""
        peca = PecaDaMesa(uniq=UNIQS[2], pedida=LARANJA, do_numero=None,
                          procedencia=3, numero=None)

        assert fosseis([peca]) == frozenset()
        assert cores_sem_colisao([peca]) == {UNIQS[2]: LARANJA}

    def test_a_cena_das_0251_no_produto(self) -> None:
        """O vermelho cai, a mesa se renumera, e o laranja e o verde-água ficam."""
        ranks = {u: n for n, u in enumerate(UNIQS, start=1)}
        ctl = _backend(ranks)
        ctl.reset_profile_overrides(
            {UNIQS[2]: OutputSpec(led=LARANJA), UNIQS[3]: OutputSpec(led=VERDE_AGUA)},
            procedencias={UNIQS[2]: 3, UNIQS[3]: 4},
        )
        antes = [ctl.resolved_led_for(u) for u in UNIQS]
        assert antes[2:] == [LARANJA, VERDE_AGUA]

        del ranks[UNIQS[1]]
        ranks[UNIQS[2]], ranks[UNIQS[3]] = 2, 3
        depois = {u: ctl.resolved_led_for(u) for u in (UNIQS[0], UNIQS[2], UNIQS[3])}

        assert depois[UNIQS[2]] == LARANJA, "o laranja saiu do controle em que foi escolhido"
        assert depois[UNIQS[3]] == VERDE_AGUA, "o verde-água saiu do controle"
        assert len(set(depois.values())) == 3, f"luz repetida na mesa: {depois}"


class TestOLegadoSegueAFormaDoDisco:
    """Régua 2 — perfil escrito antes de 08/09 (sem carimbo) prova fóssil pela forma."""

    def test_legado_no_tom_automatico_de_outro_e_fossil(self) -> None:
        mesa = [
            _automatica(UNIQS[0], 1),
            PecaDaMesa(uniq=UNIQS[1], pedida=player_slot_color(1),
                       do_numero=player_slot_color(2), procedencia=LEGADO, numero=2),
        ]

        assert fosseis(mesa) == frozenset({UNIQS[1]})

    def test_legado_numa_cor_propria_nao_e_fossil(self) -> None:
        mesa = [
            _automatica(UNIQS[0], 1),
            PecaDaMesa(uniq=UNIQS[1], pedida=LARANJA,
                       do_numero=player_slot_color(2), procedencia=LEGADO, numero=2),
        ]

        assert fosseis(mesa) == frozenset()


class TestNuncaDuasIguais:
    """Régua 3 — a escolha fica e quem cede é a automática do outro."""

    def test_a_escolha_no_tom_do_plastico_de_outro_o_manda_ao_tom_livre(self) -> None:
        azul = player_slot_color(1)
        p1 = PecaDaMesa(uniq=UNIQS[0], pedida=azul, do_numero=azul,
                        procedencia=DA_PALETA, numero=1, do_plastico=azul)
        p2 = PecaDaMesa(uniq=UNIQS[1], pedida=azul,
                        do_numero=player_slot_color(2), procedencia=2, numero=2)

        saida = cores_sem_colisao([p1, p2])

        assert saida[UNIQS[1]] == azul, "a automática do P1 venceu a escolha do P2"
        assert saida[UNIQS[0]] != azul, "duas luzes iguais na mesa"

    def test_a_escolha_de_outro_numero_tambem_vence_a_automatica(self) -> None:
        """A mesma cena com a escolha carimbada para um número que já não é o dela."""
        azul = player_slot_color(1)
        p1 = PecaDaMesa(uniq=UNIQS[0], pedida=azul, do_numero=azul,
                        procedencia=DA_PALETA, numero=1, do_plastico=azul)
        p2 = PecaDaMesa(uniq=UNIQS[1], pedida=azul,
                        do_numero=player_slot_color(2), procedencia=4, numero=2)

        saida = cores_sem_colisao([p1, p2])

        assert saida[UNIQS[1]] == azul
        assert saida[UNIQS[0]] != azul

    def test_sem_a_cor_do_plastico_a_automatica_do_numero_tambem_cede(self) -> None:
        """O azul escolhido quando ele era o P1; ele sai, outro vira P1, e ele volta P2.

        Sem a cor do plástico (controle que não a informa), a automática é a do número:
        o novo P1 acende o azul do número 1, e é ela quem cede, não a escolha.
        """
        azul = player_slot_color(1)
        p1 = _automatica(UNIQS[0], 1)
        p2 = _escolhida(UNIQS[1], azul, para=1, numero=2)

        saida = cores_sem_colisao([p1, p2])

        assert saida[UNIQS[1]] == azul, "a automática do número venceu a escolha do controle"
        assert saida[UNIQS[0]] != azul, "duas luzes iguais na mesa"

    def test_sem_o_plastico_a_automatica_nao_cede_a_vizinha(self) -> None:
        """Sem o plástico, a automática cede só ao MESMO tom, e não a um tom vizinho."""
        quase_azul = (20, 40, 255)
        p1 = _automatica(UNIQS[0], 1)
        p2 = _escolhida(UNIQS[1], quase_azul, para=2, numero=2)

        saida = cores_sem_colisao([p1, p2])

        assert saida == {UNIQS[0]: player_slot_color(1), UNIQS[1]: quase_azul}


class _NoDeLed:
    def set_rgb(self, r: int, g: int, b: int, *, verify: bool = False) -> bool:
        return True

    def set_players(self, bits: Any) -> bool:
        return True

    def set_players_verified(self, bits: Any) -> bool:
        return True

    def invalidate_cache(self) -> None:
        return None


def _handle_falso() -> Any:
    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

    return SimpleNamespace(
        connected=True, triggerL=DSTrigger(), triggerR=DSTrigger(),
        light=DSLight(), audio=DSAudio(),
        _raw_trigger_left=None, _raw_trigger_right=None,
    )


def _backend(ranks: dict[str, int]) -> bp.PyDualSenseController:
    """O backend real com o provider automático lendo `ranks` AO VIVO (a mesa gira)."""
    ctl = bp.PyDualSenseController()
    ctl._handles = {m: _handle_falso() for m in MACS}
    ctl._sysfs = {m: _NoDeLed() for m in MACS}

    def provider(uniq: str) -> Any:
        slot = ranks.get(uniq)
        return None if slot is None else bp._DesiredOutput(led=player_slot_color(slot))

    provider.numero_do_slot = ranks.get  # type: ignore[attr-defined]
    provider.uniqs_da_mesa = lambda: list(ranks)  # type: ignore[attr-defined]
    ctl.set_auto_output_provider(provider)
    ctl.set_game_authority_provider(lambda: "daemon")
    ctl.apply_output_defaults(OutputSpec(led=GLOBAL_DELA))
    return ctl
