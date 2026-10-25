#!/usr/bin/env python3
"""O-ESTILO-ESCOLHE-A-LUZ-O-TOQUE-E-A-IMERSAO-DO-GATILHO-01 — o estilo chega ao controle.

O CATALOGO da imersão (§2.4, §3 e §4) dá a cada estilo o acionamento de hoje, o toque e a reação
da luz. Estas réguas leem a fábrica (`profiles/estilos_de_jogo`), a ponte para o motor
(`tato_vivo.receita_do_estilo`) e os atuadores, sem dublê no caminho. Vale para P1 a P4 e para o
cabo e o rádio: o motor escreve pelo controle, e nenhum destes caminhos pergunta a conexão.

As mordidas: a Metralhadora do FPS de volta à Arma automática a 60 Hz; a duração do toque fora da
ponte; o Som no corpo como forma de um terceiro estilo; o pulso da luz com a Bateria longa ligada;
a batida só no controle que atirou.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from hefesto_dualsense4unix.app.actions import trigger_specs as specs
from hefesto_dualsense4unix.core.trigger_effects import build_from_name
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.profiles import estilos_de_jogo as ej
from hefesto_dualsense4unix.profiles import formas_de_haptica as fh

QUATRO = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04")

#: O acionamento do R2 de cada estilo (tabela S da página de 19/10/2026), já na chave da lista de
#: onze. O Arco saiu do catálogo e carrega como a Ação.
ACIONAMENTO = {
    "fps": "Machine", "corrida": "MultiPositionVibration", "acao": "Weapon",  # (noqa-acento) chave
    "arco": "Weapon", "aventura": "Bow", "esportes": "Resistance",
    "point_and_click": "Weapon", "terror": "Weapon", "luta": "Weapon", "maratona": "Off",
    "plataforma": "SlopeFeedback", "retro": "Off", "ritmo": "Weapon",
    "simulacao": "SlopeFeedback", "souls": "Weapon", "furtivo": "Weapon",
}


def _bytes_do_estilo(chave: str) -> str:
    estilo = ej.POR_CHAVE[chave]
    spec = specs.get_spec(estilo.gatilho or "")
    assert spec is not None, chave
    ajustes = dict(estilo.receita_invisivel.ajustes_do_gatilho) if estilo.receita_invisivel else {}
    valores = {p.name: int(v) for p, v in
               zip(spec.params, specs.preset_to_positional_params(spec, ajustes), strict=True)}
    efeito = build_from_name(spec.name, valores)
    return bytes([efeito.mode, *efeito.forces]).hex()[:16]


@pytest.mark.parametrize(("chave", "modo"), sorted(ACIONAMENTO.items()))
def test_o_estilo_guarda_o_acionamento_de_hoje(chave: str, modo: str) -> None:
    estilo = ej.POR_CHAVE[chave]
    assert estilo.gatilho == modo
    assert modo in {s.name for s in specs.PRESETS}, f"{chave}: {modo} saiu da lista de onze"


def test_nenhum_estilo_guarda_chave_que_saiu_da_lista() -> None:
    antigas = {s.name for s in specs.PRESETS_ANTIGOS}
    velhas = [e.chave for e in ej.ESTILOS if e.gatilho in antigas]
    assert not velhas, velhas


def test_o_fps_e_a_metralhadora_a_40_hz() -> None:
    """D-1910-O-ESTILO-ESCOLHE-O-GATILHO-DE-HOJE. MORDIDA: o FPS a 60 Hz reprova aqui."""
    fps = ej.POR_CHAVE["fps"]
    assert fps.gatilho == "Machine"
    assert fps.receita_invisivel is not None
    assert dict(fps.receita_invisivel.ajustes_do_gatilho) == {
        "start": 2, "end": 9, "strength": 4, "frequency": 40}
    assert _bytes_do_estilo("fps") == "26fc03c0b66d1b28"


@pytest.mark.parametrize("chave", ["corrida", "simulacao"])
def test_corrida_e_simulacao_nao_tocam_por_tiro_nem_pelo_lado_do_som(chave: str) -> None:
    receita = tv.receita_do_estilo(ej.POR_CHAVE[chave])
    assert receita.vibracao_por_tiro is False
    assert receita.lado_do_som is False


def test_o_ritmo_nao_segue_o_lado_do_som() -> None:
    receita = tv.receita_do_estilo(ej.POR_CHAVE["ritmo"])
    assert receita.lado_do_som is False
    assert receita.vibracao_por_tiro is True


def test_a_duracao_do_estilo_chega_ao_toque() -> None:
    """D-1910-A-DURACAO-DO-TOQUE-SEGUE-O-ESTILO. MORDIDA: sem a ponte, o Terror toca 40 ms."""
    assert tv.receita_do_estilo(ej.POR_CHAVE["terror"]).duracao_do_toque_ms == 60
    for estilo in ej.ESTILOS:
        if estilo.receita_invisivel is None or estilo.chave == "terror":
            continue
        assert tv.receita_do_estilo(estilo).duracao_do_toque_ms == 40, estilo.chave


@pytest.mark.parametrize(("duracao", "toque"), [(50, 25), (100, 25), (200, 40), (250, 50),
                                                (300, 60), (400, 60), (900, 60)])
def test_a_duracao_do_toque_e_40_vezes_d_sobre_200_de_25_a_60(duracao: int, toque: int) -> None:
    assert tv.duracao_do_toque_do_estilo(duracao) == toque


FORMA_DO_ESTILO = {
    "luta": fh.IMPACTO, "esportes": fh.IMPACTO, "ritmo": fh.ESTALO,
    "fps": fh.TOQUE, "acao": fh.IMPACTO, "arco": fh.IMPACTO,  # (noqa-acento) chave
    "aventura": fh.TOQUE, "plataforma": fh.ESTALO, "terror": fh.TOQUE,
    "souls": fh.ECO, "furtivo": fh.ESTALO,  # o Eco da Souls (bloco C, 20/10/2026)
    "corrida": fh.SOM_NO_CORPO, "simulacao": fh.GRAO,  # o motor no corpo; o chão em grãos
    "retro": fh.MOTOR_DE_EPOCA,  # o zumbido do motor de peso, só quando o jogo vibra
    # A resposta de 08/10 («Toque por tiro e lado do som, como nos outros») vence o «Sem efeito»
    # que a tabela do catálogo de 15/10 dá ao Point and click e à Maratona.
    "point_and_click": fh.TOQUE, "maratona": fh.TOQUE,
}


@pytest.mark.parametrize(("chave", "forma"), sorted(FORMA_DO_ESTILO.items()))
def test_o_estilo_escolhe_a_forma_do_toque(chave: str, forma: str | None) -> None:
    """D-1910-O-POINT-AND-CLICK-E-A-MARATONA-TOCAM-O-TOQUE: a forma de cada estilo."""
    assert fh.forma_que_vale(None, chave) == forma


def test_todo_estilo_de_fabrica_tem_a_forma_na_tabela() -> None:
    """Estilo novo sem linha aqui reprova: a forma dele não nasce por acaso.

    O Nativo é modo (quem manda é o jogo); Visual novel e Adulto ficam para as sprints delas.
    """
    fora = ({e.chave for e in ej.DE_FABRICA} - set(FORMA_DO_ESTILO)
            - {"nativo", "visual_novel", "adulto"})
    assert not fora, fora


def test_so_cinco_estilos_tem_forma_longa_de_estilo() -> None:
    """MORDIDA: a Guarda, o Aparo ou o Som no corpo num sexto estilo reprova aqui.

    D-1910-O-CONTINUO-VOLTA-A-CORRIDA-E-A-SIMULACAO (o motor e o chão passam pelo corpo) e o
    bloco C de 20/10/2026: o Eco da Souls, o Grão da Simulação e o Motor de época do Retrô.
    """
    longas = {e: f for e, f in fh.POR_ESTILO.items() if f in fh.FORMAS_LONGAS}
    assert longas == {"corrida": fh.SOM_NO_CORPO, "simulacao": fh.GRAO, "souls": fh.ECO,
                      "retro": fh.MOTOR_DE_EPOCA}
    assert set(fh.POR_ESTILO) <= set(ej.POR_CHAVE)


@pytest.mark.parametrize("chave", ["fps", "acao", "luta"])  # (noqa-acento) chave
def test_o_tiro_pulsa_a_luz_onde_o_estilo_reage(chave: str) -> None:
    receita = tv.receita_do_estilo(ej.POR_CHAVE[chave])
    luz = _luz()
    assert receita.reacao_ao_tiro == tv.REACAO_PULSA
    assert luz.responde_a(_evento(QUATRO[0], tv.TIPO_RUMBLE), receita)


def _luz(economia: frozenset[str] = frozenset()) -> tv.AtuadorDaLuz:
    return tv.AtuadorDaLuz(
        lambda uniq, cor: True,
        lambda uniq: (200, 40, 40),
        lambda uniq: True,
        na_economia=lambda uniq: uniq in economia,
    )


def _evento(uniq: str, tipo: str, instante: float = 10.0) -> tv.Evento:
    return tv.Evento(instante, uniq, tipo, tv.LADO_CENTRO, 0.8)


def test_o_ritmo_sobe_a_luz_na_batida_e_nao_no_tiro() -> None:
    receita = tv.receita_do_estilo(ej.POR_CHAVE["ritmo"])
    assert receita.reacao_ao_tiro == tv.REACAO_BATIDA
    assert receita.ligada
    luz = _luz()
    for uniq in QUATRO:
        assert luz.responde_a(_evento(uniq, tv.TIPO_BATIDA), receita), uniq
        assert not luz.responde_a(_evento(uniq, tv.TIPO_DEDO), receita)
        assert not luz.responde_a(_evento(uniq, tv.TIPO_RUMBLE), receita)
        assert not luz.responde_a(_evento(uniq, tv.TIPO_SOM), receita)


def test_a_batida_nao_passa_de_tres_por_segundo() -> None:
    receita = tv.receita_do_estilo(ej.POR_CHAVE["ritmo"])
    luz = _luz()
    subiram = 0
    for i in range(10):
        evento = _evento(QUATRO[0], tv.TIPO_BATIDA, 10.0 + i * 0.1)
        if luz.responde_a(evento, receita):
            luz.escrever(evento, receita, evento.instante)
            luz.devolver(QUATRO[0], evento.instante)
            subiram += 1
    assert subiram == tv.TETO_DA_LUZ_POR_S


def test_o_ritmo_sobe_o_ouvido_do_jogo() -> None:
    """Sem o ouvido, a batida nunca chega: o Ritmo não segue o lado do som nem toca o estalo."""
    assert tv.pede_o_ouvido(tv.receita_do_estilo(ej.POR_CHAVE["ritmo"]))
    assert not tv.pede_o_ouvido(tv.DESLIGADA)
    # o Som no corpo da Corrida também é o grave do jogo: pede o ouvido sem escolha nenhuma
    assert tv.pede_o_ouvido(tv.receita_do_estilo(ej.POR_CHAVE["corrida"]))


def test_a_batida_chega_aos_quatro_controles() -> None:
    """D-1910-O-RITMO-SOBE-A-LUZ-NA-BATIDA-NOS-QUATRO. MORDIDA: só no P1, os outros apagam."""
    anotados: list[tv.Evento] = []
    estalo = SimpleNamespace(instante=10.0, lado=tv.LADO_CENTRO, energia=0.7, recorte=None)
    ouvido = SimpleNamespace(comecar=lambda: None, tirar=lambda: [estalo])
    passo: Any = SimpleNamespace(
        motor=SimpleNamespace(ouvido=ouvido, anotar=anotados.append),
        dedo=SimpleNamespace(atirando=lambda uniq, instante: uniq == QUATRO[0]),
    )
    controles = [tv.Controle(uniq, None) for uniq in QUATRO]
    tv.Passo._ouvir_o_jogo(passo, tv.receita_do_estilo(ej.POR_CHAVE["ritmo"]), controles)
    batidas = sorted(e.uniq for e in anotados if e.tipo == tv.TIPO_BATIDA)
    assert batidas == sorted(QUATRO)

    anotados.clear()
    tv.Passo._ouvir_o_jogo(passo, tv.receita_do_estilo(ej.POR_CHAVE["fps"]), controles)
    assert not [e for e in anotados if e.tipo == tv.TIPO_BATIDA]


@pytest.mark.parametrize("tipo", [tv.TIPO_RUMBLE, tv.TIPO_BATIDA])
def test_a_bateria_longa_deixa_a_luz_fixa(tipo: str) -> None:
    """MORDIDA: com a Bateria longa, o pulso da luz do estilo reprova aqui (cada controle a sua)."""
    estilo = "fps" if tipo == tv.TIPO_RUMBLE else "ritmo"
    receita = tv.receita_do_estilo(ej.POR_CHAVE[estilo])
    luz = _luz(economia=frozenset({QUATRO[1]}))
    assert not luz.responde_a(_evento(QUATRO[1], tipo), receita)
    for uniq in (QUATRO[0], QUATRO[2], QUATRO[3]):
        assert luz.responde_a(_evento(uniq, tipo), receita), uniq


def test_a_bateria_longa_deixa_a_forma_do_estilo_curta() -> None:
    for chave in fh.POR_ESTILO:
        assert fh.forma_que_vale(None, chave, economia=True) not in fh.FORMAS_LONGAS


@pytest.mark.parametrize(("chave", "brilho"), [
    ("point_and_click", 0.4), ("terror", 0.7), ("maratona", 0.25), ("simulacao", 0.6)])
def test_o_brilho_do_estilo_e_o_do_catalogo(chave: str, brilho: float) -> None:
    assert ej.POR_CHAVE[chave].brilho == brilho


@pytest.mark.parametrize("chave", sorted(ACIONAMENTO))
def test_as_quatro_cores_seguem_distintas(chave: str) -> None:
    cores = ej.as_quatro(chave)
    assert len(set(cores)) == 4
