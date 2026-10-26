"""OS-MEUS-TOQUES-VIBRAM-O-CONTROLE-A-CADA-ENTRADA-01: o controle vibra a cada entrada de quem joga.

Relógio injetado e controle de mentira que guarda o que os motores receberam. O
``apply_game_rumble``, o barramento e o backend do caso do jogo que vibra são os do produto.

AS MORDIDAS (executadas na implementação, uma a uma, com o md5 conferido na volta):

* a mistura «maior» que devolve só os toques → ``test_o_maior_nunca_deixa_o_jogo_mais_fraco``;
* tirar a guarda da háptica por áudio → ``test_a_haptica_por_audio_cala_os_toques``;
* tirar o teto de 12 toques → ``test_cinquenta_apertos_em_um_segundo_viram_doze_toques``;
* o analógico «movimento» sem o cala em 0,3 s → ``test_o_movimento_cala_em_0_3_s_parado``;
* o «so_meus_toques» que mantém o jogo → ``test_so_meus_toques_tira_o_jogo``;
* o lado do botão invertido → ``test_cada_botao_toca_no_motor_do_seu_lado``;
* a guarda do Modo Nativo → ``test_no_modo_nativo_nada_se_escreve``;
* o gatilho com efeito do jogo que toca → ``test_o_gatilho_com_efeito_do_jogo_cala_o_toque``.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.daemon.subsystems.meus_toques import (
    Ajuste,
    Entrada,
    Ligacoes,
    MeusToques,
    ajuste_do_perfil,
    entradas_do_daemon,
)
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from tests.unit.test_a_forca_da_vibracao_de_cada_controle_sai_de_um_funil_so import (
    UNIQS,
    _Mesa,
)

P1, P2, P3, P4 = UNIQS
Par = tuple[int, int]
BASE = 76


@dataclass
class Mesa:
    """O controle de mentira: o que os motores receberam e o que as guardas respondem."""

    agora: float = 1000.0
    motores: list[tuple[float, str, int, int]] = field(default_factory=list)
    eventos: list[tuple[str, Par, Par, Par, Par]] = field(default_factory=list)
    pode: bool = True
    nativo: bool = False
    haptica: bool = False
    gatilho: bool = False
    forca: tuple[float, float] = (1.0, 1.0)

    def ligacoes(self) -> Ligacoes:
        return Ligacoes(
            motores=lambda uniq, fraco, forte: self.motores.append(
                (self.agora, uniq, fraco, forte)),
            pode_falar=lambda uniq: self.pode,
            haptica_do_jogo=lambda uniq: self.haptica,
            gatilho_do_jogo=lambda uniq: self.gatilho,
            dizer=lambda uniq, pedido, efetivo, jogo, toques: self.eventos.append(
                (uniq, pedido, efetivo, jogo, toques)),
            forca=lambda uniq: self.forca,
            pode_calar=lambda uniq: not self.nativo,
        )

    def de(self, uniq: str) -> list[tuple[float, int, int]]:
        return [(t, f, s) for t, u, f, s in self.motores if u == uniq]


def _meus(mesa: Mesa, **ajuste: Any) -> MeusToques:
    ajuste.setdefault("modo", "jogo_e_meus_toques")
    ajuste.setdefault("analogicos", "posicao")
    meus = MeusToques(mesa.ligacoes())
    meus.ajustar(Ajuste(**ajuste))
    return meus


def _andar(
    meus: MeusToques,
    mesa: Mesa,
    entrada: Callable[[float], list[Entrada] | Entrada],
    ate: float,
    passo: float = 0.005,
) -> None:
    """Anda o relógio da mesa até ``ate`` (instante absoluto), um tique por ``passo``."""
    while mesa.agora < ate:
        mesa.agora = round(mesa.agora + passo, 6)
        visto = entrada(mesa.agora)
        meus.tique(visto if isinstance(visto, list) else [visto], mesa.agora)


def _parado(uniq: str = P1, **campos: Any) -> Callable[[float], Entrada]:
    return lambda t: Entrada(uniq, **campos)


def test_sem_o_bloco_o_controle_vibra_so_pelo_jogo() -> None:
    mesa = Mesa()
    meus = MeusToques(mesa.ligacoes())
    assert meus.precisa_andar() is False
    _andar(meus, mesa, _parado(lx=255, rx=255, l2=255), mesa.agora + 1.0)
    assert mesa.motores == [], "inclinar o analógico não escreve nos motores"
    assert meus.misturar_o_jogo(P1, (200, 200)) is None, "o pedido do jogo segue como veio"


def test_o_modo_so_o_jogo_com_o_bloco_escrito_tambem_nao_escreve() -> None:
    mesa = Mesa()
    meus = _meus(mesa, modo="so_o_jogo")
    _andar(meus, mesa, _parado(lx=255), mesa.agora + 0.5)
    assert mesa.motores == []


def test_o_maior_nunca_deixa_o_jogo_mais_fraco() -> None:
    mesa = Mesa()
    meus = _meus(mesa, mistura="maior")
    _andar(meus, mesa, _parado(lx=255, rx=255), mesa.agora + 0.1)
    assert mesa.de(P1)[-1][1:] == (BASE, BASE), "sozinho, o toque chega"
    mistura = meus.misturar_o_jogo(P1, (200, 200))
    assert mistura is not None and mistura.motores == (200, 200), "jogo a 200 e toques a 76: 200"
    assert mistura.toques == (BASE, BASE)
    _andar(meus, mesa, _parado(lx=255, rx=255), mesa.agora + 0.1)
    assert mesa.de(P1)[-1][1:] == (BASE, BASE) or mesa.de(P1)[-1][1:] == (200, 200)


def test_somar_limita_ao_teto_do_controle() -> None:
    mesa = Mesa()
    meus = _meus(mesa, mistura="somar", forca=100)
    _andar(meus, mesa, _parado(lx=255, rx=255), mesa.agora + 0.1)
    mistura = meus.misturar_o_jogo(P1, (200, 200))
    assert mistura is not None and mistura.motores == (255, 255), "200 + 255 limita a 255"
    mistura = meus.misturar_o_jogo(P1, (100, 0))
    assert mistura is not None and mistura.motores == (255, 255)


def test_somar_com_toque_pequeno_soma_de_verdade() -> None:
    mesa = Mesa()
    meus = _meus(mesa, mistura="somar")
    _andar(meus, mesa, _parado(lx=255), mesa.agora + 0.1)
    mistura = meus.misturar_o_jogo(P1, (100, 50))
    assert mistura is not None and mistura.motores == (100, 50 + BASE)


def test_o_jogo_que_para_deixa_os_toques_sozinhos_no_motor() -> None:
    mesa = Mesa()
    meus = _meus(mesa)
    _andar(meus, mesa, _parado(rx=255), mesa.agora + 0.1)
    meus.misturar_o_jogo(P1, (200, 200))
    mistura = meus.misturar_o_jogo(P1, (0, 0))
    assert mistura is not None and mistura.motores == (BASE, 0), "o zero do jogo não zera o toque"


def test_so_meus_toques_tira_o_jogo() -> None:
    mesa = Mesa()
    meus = _meus(mesa, modo="so_meus_toques")
    mistura = meus.misturar_o_jogo(P1, (200, 200))
    assert mistura is not None and mistura.motores == (0, 0), "sem toque, o jogo não chega"
    _andar(meus, mesa, _parado(lx=255), mesa.agora + 0.1)
    mistura = meus.misturar_o_jogo(P1, (200, 200))
    assert mistura is not None and mistura.motores == (0, BASE)


def test_o_movimento_cala_em_0_3_s_parado() -> None:
    mesa = Mesa()
    meus = _meus(mesa, analogicos="movimento")
    _andar(meus, mesa, _parado(lx=128), mesa.agora + 0.05)
    comeco = mesa.agora
    _andar(meus, mesa, _parado(lx=255), comeco + 0.28)
    assert mesa.de(P1)[-1][1:] == (0, BASE), "se mexeu, vibra no esquerdo (o forte)"
    _andar(meus, mesa, _parado(lx=255), comeco + 0.4)
    ultimo = mesa.de(P1)[-1]
    assert ultimo[1:] == (0, 0), "parado inclinado, silencia"
    assert 0.29 <= ultimo[0] - comeco <= 0.35, f"calou em {ultimo[0] - comeco:.3f} s"


def test_a_posicao_segue_vibrando_enquanto_inclinado() -> None:
    mesa = Mesa()
    meus = _meus(mesa, analogicos="posicao")
    _andar(meus, mesa, _parado(rx=255), mesa.agora + 1.5)
    assert mesa.de(P1)[-1][1:] == (BASE, 0), "o direito é o fraco"
    assert mesa.de(P1)[-1][1:] != (0, 0)


def test_o_analogico_desligado_nao_vibra() -> None:
    mesa = Mesa()
    meus = _meus(mesa, analogicos="desligado")
    _andar(meus, mesa, _parado(lx=255, rx=255), mesa.agora + 0.3)
    assert mesa.motores == []


def test_a_intensidade_acompanha_a_inclinacao() -> None:
    mesa = Mesa()
    meus = _meus(mesa, forca=100)
    _andar(meus, mesa, _parado(rx=200), mesa.agora + 0.1)
    meio = mesa.de(P1)[-1][1]
    _andar(meus, mesa, _parado(rx=255), mesa.agora + 0.1)
    cheio = mesa.de(P1)[-1][1]
    assert 0 < meio < cheio == 255


def test_a_zona_morta_do_analogico_nao_vibra() -> None:
    mesa = Mesa()
    meus = _meus(mesa)
    _andar(meus, mesa, _parado(lx=140, ly=120), mesa.agora + 0.2)
    assert mesa.motores == []


def test_soltar_o_analogico_zera_o_motor() -> None:
    mesa = Mesa()
    meus = _meus(mesa)
    _andar(meus, mesa, _parado(lx=255), mesa.agora + 0.1)
    _andar(meus, mesa, _parado(lx=128), mesa.agora + 0.1)
    assert mesa.de(P1)[-1][1:] == (0, 0)


def test_cada_botao_toca_no_motor_do_seu_lado() -> None:
    mesa = Mesa()
    meus = _meus(mesa, analogicos="desligado", gatilhos=False, chacoalhar=False)
    casos = {
        "cross": (BASE, 0), "circle": (BASE, 0), "square": (BASE, 0), "triangle": (BASE, 0),
        "r1": (BASE, 0), "dpad_up": (0, BASE), "dpad_left": (0, BASE), "l1": (0, BASE),
    }
    for botao, esperado in casos.items():
        antes = len(mesa.motores)
        _andar(meus, mesa, _parado(botoes=frozenset({botao})), mesa.agora + 0.02)
        assert mesa.motores[antes][2:] == esperado, f"{botao}: {mesa.motores[antes]}"
        _andar(meus, mesa, _parado(), mesa.agora + 1.1)


def test_options_e_share_nao_tocam() -> None:
    mesa = Mesa()
    meus = _meus(mesa, analogicos="desligado", gatilhos=False, chacoalhar=False)
    for botao in ("options", "create", "ps", "mic_btn", "touchpad"):
        _andar(meus, mesa, _parado(botoes=frozenset({botao})), mesa.agora + 0.1)
        _andar(meus, mesa, _parado(), mesa.agora + 0.1)
    assert mesa.motores == []


def test_o_toque_do_botao_dura_40_ms_e_depois_zera() -> None:
    mesa = Mesa()
    meus = _meus(mesa, analogicos="desligado", gatilhos=False, chacoalhar=False)
    _andar(meus, mesa, _parado(), mesa.agora + 0.01)
    inicio = mesa.agora
    _andar(meus, mesa, _parado(botoes=frozenset({"cross"})), inicio + 0.3)
    escritas = mesa.de(P1)
    assert escritas[0][1:] == (BASE, 0) and escritas[-1][1:] == (0, 0)
    assert 0.035 <= escritas[-1][0] - escritas[0][0] <= 0.06


def test_cinquenta_apertos_em_um_segundo_viram_doze_toques() -> None:
    mesa = Mesa()
    meus = _meus(mesa, analogicos="desligado", gatilhos=False, chacoalhar=False)
    estado = {"n": 0}

    def alternando(t: float) -> Entrada:
        estado["n"] += 1
        return Entrada(P1, botoes=frozenset({"cross"}) if estado["n"] % 2 else frozenset())

    _andar(meus, mesa, alternando, mesa.agora + 1.0, passo=0.01)
    assert meus.toques_dados == 12, f"{meus.toques_dados} toques em 1 s"


def test_o_teto_total_e_de_40_por_segundo() -> None:
    mesa = Mesa()
    meus = _meus(mesa, analogicos="desligado", gatilhos=False, chacoalhar=False)
    quatro = (P1, P2, P3, P4)
    estado = {"n": 0}

    def todos(t: float) -> list[Entrada]:
        estado["n"] += 1
        botoes = frozenset({"cross"}) if estado["n"] % 2 else frozenset()
        return [Entrada(u, botoes=botoes) for u in quatro]

    _andar(meus, mesa, todos, mesa.agora + 1.0, passo=0.01)
    assert 36 <= meus.toques_dados <= 40, f"{meus.toques_dados} toques de quatro controles"


def test_o_par_continuo_nao_gasta_o_teto_dos_botoes() -> None:
    mesa = Mesa()
    meus = _meus(mesa, gatilhos=False, chacoalhar=False)
    estado = {"n": 0}

    def tudo(t: float) -> Entrada:
        estado["n"] += 1
        return Entrada(
            P1, botoes=frozenset({"cross"}) if estado["n"] % 2 else frozenset(),
            lx=255 if estado["n"] % 8 < 4 else 128)

    _andar(meus, mesa, tudo, mesa.agora + 1.0, passo=0.01)
    assert meus.toques_dados == 12
    esquerdo = [e for e in mesa.de(P1) if e[2] == BASE]
    assert esquerdo, "o analógico seguiu vibrando com o teto dos botões gasto"


def test_botoes_desligados_nao_tocam() -> None:
    mesa = Mesa()
    meus = _meus(mesa, botoes=False, analogicos="desligado", gatilhos=False, chacoalhar=False)
    _andar(meus, mesa, _parado(botoes=frozenset({"cross"})), mesa.agora + 0.3)
    assert mesa.motores == []


def test_o_zero_passa_mesmo_dentro_dos_33_ms_da_escrita_anterior() -> None:
    mesa = Mesa()
    meus = _meus(mesa)
    meus.tique([Entrada(P1, lx=255)], mesa.agora)
    meus.tique([Entrada(P1, lx=128)], mesa.agora + 0.005)
    assert mesa.motores[-1][2:] == (0, 0), "soltar não espera a vez: o motor não fica ligado"


def test_o_gatilho_vibra_pelo_fundo_do_curso_no_motor_do_lado() -> None:
    mesa = Mesa()
    meus = _meus(mesa, analogicos="desligado", chacoalhar=False)
    _andar(meus, mesa, _parado(l2=255), mesa.agora + 0.1)
    assert mesa.de(P1)[-1][1:] == (0, BASE), "L2 no esquerdo"
    _andar(meus, mesa, _parado(r2=255), mesa.agora + 0.1)
    assert mesa.de(P1)[-1][1:] == (BASE, 0), "R2 no direito"


def test_o_gatilho_com_efeito_do_jogo_cala_o_toque() -> None:
    mesa = Mesa(gatilho=True)
    meus = _meus(mesa, analogicos="desligado", chacoalhar=False)
    _andar(meus, mesa, _parado(l2=255, r2=255), mesa.agora + 0.3)
    assert mesa.motores == []


def test_o_chacoalhar_passa_do_limiar_e_vibra_os_dois() -> None:
    mesa = Mesa()
    meus = _meus(mesa, analogicos="desligado", gatilhos=False)
    _andar(meus, mesa, _parado(giro=100.0), mesa.agora + 0.1)
    assert mesa.motores == [], "um giro leve não é chacoalhar"
    _andar(meus, mesa, _parado(giro=700.0), mesa.agora + 0.1)
    assert mesa.de(P1)[-1][1:] == (BASE, BASE)


def test_a_forca_do_perfil_limita_o_toque() -> None:
    mesa = Mesa()
    meus = _meus(mesa, forca=10)
    _andar(meus, mesa, _parado(lx=255), mesa.agora + 0.1)
    assert mesa.de(P1)[-1][1:] == (0, 26)
    meus.ajustar(Ajuste(modo="jogo_e_meus_toques", analogicos="posicao", forca=0))
    _andar(meus, mesa, _parado(lx=255), mesa.agora + 0.1)
    assert mesa.de(P1)[-1][1:] == (0, 0), "força zero é sem toque"


def test_a_forca_de_quem_recebe_vale_para_o_toque() -> None:
    mesa = Mesa(forca=(0.5, 0.5))
    meus = _meus(mesa, forca=100)
    _andar(meus, mesa, _parado(lx=255, rx=255), mesa.agora + 0.1)
    assert mesa.de(P1)[-1][1:] == (128, 128), "a política de intensidade vale como no jogo"


def test_a_haptica_por_audio_cala_os_toques() -> None:
    mesa = Mesa(haptica=True)
    meus = _meus(mesa)
    _andar(meus, mesa, _parado(lx=255, rx=255, botoes=frozenset({"cross"})), mesa.agora + 0.3)
    assert mesa.motores == [], "o rumble dos motores calaria a háptica do jogo"
    assert meus.misturar_o_jogo(P1, (0, 0), pelo_audio=True) is None


def test_a_haptica_que_volta_a_calar_devolve_os_toques() -> None:
    mesa = Mesa(haptica=True)
    meus = _meus(mesa)
    _andar(meus, mesa, _parado(lx=255), mesa.agora + 0.2)
    mesa.haptica = False
    _andar(meus, mesa, _parado(lx=255), mesa.agora + 0.1)
    assert mesa.de(P1)[-1][1:] == (0, BASE)


def test_no_modo_nativo_nada_se_escreve() -> None:
    mesa = Mesa(pode=False)
    meus = _meus(mesa)
    _andar(meus, mesa, _parado(lx=255, botoes=frozenset({"cross"})), mesa.agora + 0.3)
    assert mesa.motores == []
    assert meus.misturar_o_jogo(P1, (200, 200)) is None


def test_o_jogo_que_sai_do_foco_com_o_toque_no_ar_devolve_o_zero_e_o_nativo_nao() -> None:
    """Prova da D-1610-OS-MEUS-TOQUES-DEVOLVEM-O-ZERO-QUANDO-O-JOGO-SAI."""
    mesa = Mesa()
    meus = _meus(mesa)
    _andar(meus, mesa, _parado(lx=255), mesa.agora + 0.1)
    assert mesa.de(P1)[-1][1:] == (0, BASE)
    mesa.pode = False
    _andar(meus, mesa, _parado(lx=255), mesa.agora + 0.1)
    assert mesa.de(P1)[-1][1:] == (0, 0), "sem jogo, o motor não fica no nível do toque"
    assert len(mesa.de(P1)) == 2, "o zero sai uma vez só"
    mesa.pode, mesa.nativo = True, False
    _andar(meus, mesa, _parado(lx=255), mesa.agora + 0.1)
    mesa.pode, mesa.nativo = False, True
    escritos = len(mesa.motores)
    _andar(meus, mesa, _parado(lx=255), mesa.agora + 0.1)
    assert len(mesa.motores) == escritos, "no Modo Nativo o Hefesto não escreve, nem o zero"


def test_o_toque_do_jogador_2_nao_vibra_o_jogador_1() -> None:
    mesa = Mesa()
    meus = _meus(mesa)
    _andar(meus, mesa, lambda t: [Entrada(P1), Entrada(P2, rx=255)], mesa.agora + 0.2)
    assert mesa.de(P1) == []
    assert mesa.de(P2)[-1][1:] == (BASE, 0)


def test_cada_jogador_tem_o_seu_jogo_e_os_seus_toques() -> None:
    mesa = Mesa()
    meus = _meus(mesa, mistura="somar")
    _andar(meus, mesa, lambda t: [Entrada(P1, lx=255), Entrada(P3, rx=255)], mesa.agora + 0.1)
    um = meus.misturar_o_jogo(P1, (10, 10))
    tres = meus.misturar_o_jogo(P3, (20, 20))
    assert um is not None and tres is not None
    assert um.motores == (10, 10 + BASE) and tres.motores == (20 + BASE, 20)


def test_trocar_o_modo_para_so_o_jogo_devolve_o_motor() -> None:
    mesa = Mesa()
    meus = _meus(mesa)
    _andar(meus, mesa, _parado(lx=255), mesa.agora + 0.1)
    assert mesa.de(P1)[-1][1:] == (0, BASE)
    meus.ajustar(Ajuste())
    assert meus.precisa_andar() is True, "falta desfazer o que ficou nos motores"
    _andar(meus, mesa, _parado(lx=255), mesa.agora + 0.05)
    assert mesa.de(P1)[-1][1:] == (0, 0)
    assert meus.precisa_andar() is False


def test_parar_o_servico_zera_o_que_os_toques_seguravam() -> None:
    mesa = Mesa()
    meus = _meus(mesa)
    _andar(meus, mesa, _parado(lx=255), mesa.agora + 0.1)
    meus.soltar_tudo(mesa.agora)
    assert mesa.de(P1)[-1][1:] == (0, 0)


def test_o_par_continuo_escreve_no_maximo_30_vezes_por_segundo() -> None:
    mesa = Mesa()
    meus = _meus(mesa, forca=100)
    estado = {"n": 0}

    def varrendo(t: float) -> Entrada:
        estado["n"] += 1
        return Entrada(P1, rx=140 + estado["n"] % 100)

    _andar(meus, mesa, varrendo, mesa.agora + 1.0, passo=0.002)
    assert len(mesa.de(P1)) <= 31, f"{len(mesa.de(P1))} escritas em 1 s"


def test_o_evento_dos_toques_leva_o_par_e_nenhum_nome_de_botao() -> None:
    mesa = Mesa()
    meus = _meus(mesa)
    _andar(meus, mesa, _parado(lx=255, botoes=frozenset({"cross"})), mesa.agora + 0.05)
    assert mesa.eventos, "o toque chegou aos acessórios"
    assert any(e[4] == (BASE, BASE) for e in mesa.eventos), "o botão e o analógico, juntos"
    uniq, _, efetivo, jogo, toques = mesa.eventos[-1]
    assert uniq == P1 and toques == (BASE, 0) and jogo == (0, 0), "o toque do botão já passou"
    assert "cross" not in repr(mesa.eventos)
    assert efetivo[0] <= 255 and efetivo[1] <= 255


def test_o_jogo_vibracao_do_pedido_do_jogo_leva_jogo_e_toques(tmp_path: Path) -> None:
    mesa = _Mesa(tmp_path)
    bus = EventBus()
    mesa.daemon.bus = bus
    fila = bus.subscribe(EventTopic.JOGO_VIBRACAO)
    controle = Mesa()
    meus = MeusToques(Ligacoes(
        motores=lambda uniq, fraco, forte: mesa.backend.set_rumble_for(uniq, fraco, forte),
        pode_falar=lambda uniq: True,
        haptica_do_jogo=lambda uniq: False,
        gatilho_do_jogo=lambda uniq: False,
        dizer=controle.ligacoes().dizer,
    ))
    meus.ajustar(Ajuste(modo="jogo_e_meus_toques", analogicos="posicao"))
    mesa.daemon._meus_toques = meus
    meus.tique([Entrada(P1, lx=255)], 1000.0)
    mesa.limpar()

    par = gp.apply_game_rumble(mesa.daemon, 200, 120, target_uniq=P1)

    assert par == (200, 120), "o jogo a 200 e 120, os toques a 76: o maior de cada motor"
    assert mesa.handles[0].par() == (200, 120)
    evento = fila.get_nowait()
    assert evento["jogo"] == [120, 200] and evento["toques"] == [BASE, 0]
    assert evento["efetivo"] == [200, 120] and evento["pedido"] == [200, 120]
    assert set(evento) == {"uniq", "jogador", "pedido", "efetivo", "jogo", "toques", "t"}


def test_o_jogo_a_200_com_somar_chega_a_255(tmp_path: Path) -> None:
    mesa = _Mesa(tmp_path)
    meus = MeusToques(Ligacoes(
        motores=lambda uniq, fraco, forte: mesa.backend.set_rumble_for(uniq, fraco, forte),
        pode_falar=lambda uniq: True,
        haptica_do_jogo=lambda uniq: False,
        gatilho_do_jogo=lambda uniq: False,
        dizer=lambda *a: None,
    ))
    meus.ajustar(Ajuste(modo="jogo_e_meus_toques", mistura="somar", forca=100,
                        analogicos="posicao"))
    mesa.daemon._meus_toques = meus
    meus.tique([Entrada(P1, lx=255, rx=255)], 1000.0)

    par = gp.apply_game_rumble(mesa.daemon, 200, 200, target_uniq=P1)

    assert par == (255, 255)
    assert mesa.handles[0].par() == (255, 255)


def test_sem_os_meus_toques_o_pedido_do_jogo_chega_como_sempre(tmp_path: Path) -> None:
    mesa = _Mesa(tmp_path)
    bus = EventBus()
    mesa.daemon.bus = bus
    fila = bus.subscribe(EventTopic.JOGO_VIBRACAO)

    par = gp.apply_game_rumble(mesa.daemon, 200, 120, target_uniq=P1)

    assert par == (200, 120) and mesa.handles[0].par() == (200, 120)
    evento = fila.get_nowait()
    assert evento["toques"] == [0, 0] and evento["jogo"] == [120, 200]


def test_o_passo_anda_os_meus_toques_sem_receita(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = Mesa()
    meus = _meus(mesa)
    motor = tv.TatoVivo()
    motor.meus_toques = meus
    monkeypatch.setattr(tv, "meus_toques_ativos", lambda daemon: meus.ajuste)
    daemon = SimpleNamespace(
        controller=SimpleNamespace(primary_uniq=P1),
        _last_state=SimpleNamespace(
            buttons_pressed=frozenset(), raw_lx=255, raw_ly=128, raw_rx=128, raw_ry=128,
            l2_raw=0, r2_raw=0),
        _motion_reader=None,
    )
    passo = tv.Passo(daemon, motor)

    passo(mesa.agora)

    assert mesa.de(P1)[-1][1:] == (0, BASE)
    assert motor.ligado is False, "a receita seguiu desligada"


def test_as_entradas_do_daemon_trazem_o_primario_e_os_do_coop() -> None:
    foto = SimpleNamespace(
        buttons_pressed=frozenset({"l1"}), lx=10, ly=20, rx=30, ry=40, l2_raw=50, r2_raw=60)
    daemon = SimpleNamespace(
        controller=SimpleNamespace(primary_uniq=P1),
        _last_state=SimpleNamespace(
            buttons_pressed=frozenset({"cross"}), raw_lx=1, raw_ly=2, raw_rx=3, raw_ry=4,
            l2_raw=5, r2_raw=6),
        _motion_reader=SimpleNamespace(snapshot=lambda: SimpleNamespace(x=3.0, y=4.0, z=0.0)),
        _coop_manager=SimpleNamespace(_players={P2: SimpleNamespace(
            reader=SimpleNamespace(snapshot=lambda: foto), motion_reader=None)}),
    )
    um, dois = entradas_do_daemon(daemon)
    assert (um.uniq, um.botoes, um.lx, um.l2, um.giro) == (P1, frozenset({"cross"}), 1, 5, 5.0)
    assert (dois.uniq, dois.botoes, dois.ly, dois.r2) == (P2, frozenset({"l1"}), 20, 60)


def _perfil(**bloco: Any) -> Profile:
    return Profile(name="Jogo", match=MatchAny(), meus_toques=bloco or None)


def test_perfil_antigo_carrega_em_so_o_jogo_e_nao_ganha_o_bloco_ao_salvar() -> None:
    perfil = _perfil()
    assert perfil.meus_toques is None
    assert "meus_toques" not in perfil.model_dump(mode="json")
    assert ajuste_do_perfil(perfil) == Ajuste(), "sem bloco, só o jogo"
    assert Ajuste().liga is False


def test_o_bloco_do_perfil_vira_o_ajuste() -> None:
    perfil = _perfil(modo="jogo_e_meus_toques", mistura="somar", forca=55, analogicos="posicao",
                     botoes=False)
    ajuste = ajuste_do_perfil(perfil)
    assert (ajuste.modo, ajuste.mistura, ajuste.forca, ajuste.analogicos, ajuste.botoes) == (
        "jogo_e_meus_toques", "somar", 55, "posicao", False)
    assert ajuste.liga is True and ajuste.gatilhos is True and ajuste.chacoalhar is True


def test_o_bloco_de_fabrica_e_so_o_jogo_com_a_forca_de_30() -> None:
    perfil = _perfil(modo="so_meus_toques")
    ajuste = ajuste_do_perfil(perfil)
    assert (ajuste.mistura, ajuste.forca, ajuste.analogicos) == ("maior", 30, "movimento")
    assert _perfil().meus_toques is None


def test_o_schema_recusa_o_que_nao_e_do_bloco() -> None:
    for ruim in ({"modo": "sempre"}, {"mistura": "dobrar"}, {"forca": 101}, {"forca": -1},
                 {"analogicos": "cheio"}, {"botao_cruz": True}):
        with pytest.raises(ValidationError):
            _perfil(**ruim)


def test_o_bloco_ilegivel_cai_na_fabrica_em_vez_de_derrubar_o_laco() -> None:
    ruim = SimpleNamespace(meus_toques={"modo": "x", "forca": "muito"})
    assert ajuste_do_perfil(ruim) == Ajuste()
    bloco = {"meus_toques": {"modo": "so_meus_toques", "forca": 500}}
    assert ajuste_do_perfil(bloco).forca == 100
