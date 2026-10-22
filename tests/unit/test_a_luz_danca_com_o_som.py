"""A luz dança com o som (A-LUZ-DANCA-COM-O-SOM-01, 22/10/2026).

O efeito «Ao som», no grupo «Que reage» da lista da aba Iluminação: o brilho da barra segue a
energia do som da saída padrão (sobe depressa, desce devagar), os graves deixam a cor escolhida e os
agudos a puxam para o branco. A leitura é só do monitor da saída, nunca de uma fonte de microfone,
existe só enquanto algum controle toca o efeito, e batida rápida não vira estrobo (três subidas por
segundo).

MORDIDAS (22/10/2026): trocar ``FONTE_DO_MONITOR`` por ``@DEFAULT_SOURCE@`` reprova a fonte; tirar
fazer o ``e_o_monitor`` aceitar tudo reprova a recusa do microfone; tirar o
``_conferir_o_som`` do ``tique`` reprova o abre-e-fecha; trocar o ``BrilhoDoAcende`` do ``AoSom``
por ``_escalar(cor, nivel)`` reprova o teto de três subidas; tirar o ``fluxo.parar()`` do
``fechar`` reprova o fecho; tirar a divisão pelo pico do ``Medidor`` reprova a independência do
volume.
"""
from __future__ import annotations

import array
import asyncio
import math
import pathlib
import re
import subprocess
import sys
import time
from itertools import pairwise
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import luz_animada as luz
from hefesto_dualsense4unix.integrations import energia_do_som as som
from hefesto_dualsense4unix.profiles import efeitos_de_luz as fx
from hefesto_dualsense4unix.profiles.schema import (
    BASES_DO_SOM_DA_LUZ,
    TODAS_AS_BASES_DA_LUZ,
    EfeitoDaLuz,
    ler_o_efeito_da_luz,
)

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

MOCKUP = RAIZ / "mockup" / "04-iluminacao.html"
RGB = tuple[int, int, int]
LARANJA: RGB = (255, 128, 0)
#: Faixa forjada (`aa:bb:cc`), nunca endereço de aparelho de verdade.
JOGADORES = [f"aa:bb:cc:00:00:0{n}" for n in range(1, 5)]
PASSO_S = 1 / 60
MICROFONE = "alsa_input.usb-forjado-00.mono-fallback"


def _luz(canal: int) -> float:
    return max(canal) / 255 if isinstance(canal, tuple) else canal / 255


def _subidas(brilhos: list[float], piso: float = 0.25) -> list[float]:
    """Os instantes em que o brilho cruza o meio do passeio para cima (histerese de 10%)."""
    meio = (piso + 1.0) / 2
    folga = 0.1 * (1.0 - piso)
    embaixo, fora = False, []
    for i, b in enumerate(brilhos):
        if b <= meio - folga:
            embaixo = True
        elif embaixo and b >= meio + folga:
            embaixo = False
            fora.append(i * PASSO_S)
    return fora


def _mais_em_um_segundo(tempos: list[float]) -> int:
    mais = 0
    for i, inicio in enumerate(tempos):
        mais = max(mais, sum(1 for t in tempos[i:] if t - inicio < 1.0 - 1e-6))
    return mais


def _tocar(estado: fx.AoSom, nivel_por_passo: list[float], agudos: float = 0.0) -> list[RGB]:
    return [estado.andar(fx.Entrada(som=(n, agudos)), i * PASSO_S)
            for i, n in enumerate(nivel_por_passo)]


# ---------------------------------------------------------------- a base existe no perfil


def test_ao_som_esta_fora_das_oito_que_se_criam_e_o_perfil_a_le() -> None:
    assert BASES_DO_SOM_DA_LUZ == ("ao-som",)
    assert "ao-som" in TODAS_AS_BASES_DA_LUZ
    assert ler_o_efeito_da_luz("ao-som;FF8000;5") == EfeitoDaLuz("ao-som", ((255, 128, 0),), 5)
    assert ler_o_efeito_da_luz("ao-som;;5") is None, "os graves levam a cor escolhida"
    assert fx.cor_no_instante(EfeitoDaLuz("ao-som", (LARANJA,), 5), 3.0) == LARANJA


# ---------------------------------------------------------------- o efeito


def test_um_som_em_pulsos_da_brilho_que_sobe_e_desce_e_nunca_preto() -> None:
    estado = fx.AoSom(LARANJA, 5)
    pulsos = ([1.0] * 30 + [0.0] * 60) * 3  # meio segundo ligado, um e meio desligado
    quadros = _tocar(estado, pulsos)
    brilho = [max(q) / 255 for q in quadros]
    assert max(brilho) > 0.95, "o pulso leva a barra à cor cheia"
    assert min(brilho) < 0.4, "e entre pulsos ela volta para perto do piso"
    assert min(brilho) >= fx.PISO_DO_ACENDE - 0.01, "mas nunca preta"
    assert all(q != (0, 0, 0) for q in quadros)
    assert len(_subidas(brilho)) == 3, "uma subida por pulso"


def test_o_brilho_sobe_depressa_e_desce_devagar() -> None:
    estado = fx.AoSom(LARANJA, 3)
    subindo = [max(q) / 255 for q in _tocar(estado, [1.0] * 40)]
    sobe = next(i for i, b in enumerate(subindo) if b >= 0.9) * PASSO_S
    descendo = [max(q) / 255 for q in [estado.andar(fx.Entrada(som=(0.0, 0.0)), (40 + i) * PASSO_S)
                                       for i in range(120)]]
    desce = next(i for i, b in enumerate(descendo) if b <= 0.4) * PASSO_S
    assert sobe < 0.3, sobe
    assert desce > 2 * sobe, (sobe, desce)


def test_a_cauda_encurta_com_o_ritmo() -> None:
    assert fx.descida_do_som_s(1) > fx.descida_do_som_s(5) > fx.descida_do_som_s(10)


def test_os_graves_deixam_a_cor_escolhida_e_os_agudos_a_puxam_para_o_branco() -> None:
    graves = fx.AoSom(LARANJA, 5)
    agudos = fx.AoSom(LARANJA, 5)
    cheio = [1.0] * 180
    cor_g = _tocar(graves, cheio, agudos=0.0)[-1]
    cor_a = _tocar(agudos, cheio, agudos=1.0)[-1]
    assert cor_g == LARANJA
    assert cor_a[2] > 120 and cor_a[1] > cor_g[1], "os agudos esbranquiçam"
    assert cor_a != (255, 255, 255), "mas a barra não vira só branca"


def test_a_cor_dos_agudos_nao_pisca_a_cada_pancada() -> None:
    """Prato a cada 125 ms: a cor muda devagar, o salto por quadro fica pequeno."""
    estado = fx.AoSom(LARANJA, 5)
    entradas = [(1.0, 1.0 if (i // 7) % 2 else 0.0) for i in range(240)]
    quadros = [estado.andar(fx.Entrada(som=e), i * PASSO_S) for i, e in enumerate(entradas)]
    saltos = [abs(a[2] - b[2]) for a, b in pairwise(quadros)]
    assert max(saltos) < 25, max(saltos)


@pytest.mark.parametrize(("ligados", "desligados"), [(3, 9), (2, 4), (4, 4)])
def test_batida_rapida_nao_passa_de_tres_subidas_por_segundo(ligados: int, desligados: int) -> None:
    """5, 10 e 7,5 batidas por segundo, no ritmo mais curto (a cauda de 0,2 s)."""
    estado = fx.AoSom(LARANJA, 10)
    batida = ([1.0] * ligados + [0.0] * desligados) * 40
    brilho = [max(q) / 255 for q in _tocar(estado, batida)]
    sobe = _subidas(brilho)
    assert sobe, "ainda acompanha a batida (não congela)"
    assert _mais_em_um_segundo(sobe) <= 3, sobe


def test_o_teto_de_tres_subidas_vale_mesmo_se_a_suavizacao_do_nivel_ficar_instantanea(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A cauda lenta já segura a batida; o teto do ``BrilhoDoAcende`` segura o resto, e é ele que
    esta prova mede: sem suavizar, 7,5 batidas por segundo passam de três só sem o teto."""
    monkeypatch.setattr(fx, "SUBIDA_DO_SOM_S", 0.001)
    monkeypatch.setattr(fx, "descida_do_som_s", lambda _ritmo: 0.001)
    batida = ([1.0] * 4 + [0.0] * 4) * 40
    com_teto = fx.AoSom(LARANJA, 10)
    brilho = [max(q) / 255 for q in _tocar(com_teto, batida)]
    assert _mais_em_um_segundo(_subidas(brilho)) <= 3
    assert max(brilho) - min(brilho) > 0.1, "e ainda acompanha"
    solto = fx.AoSom(LARANJA, 10)
    monkeypatch.setattr(solto, "_brilho", SimpleNamespace(
        andar=lambda curso, _agora: fx.brilho_do_acende(curso)))
    sem_teto = [max(q) / 255 for q in _tocar(solto, batida)]
    assert _mais_em_um_segundo(_subidas(sem_teto)) > 3, "a régua enxerga a batida sem o teto"


def test_sem_leitura_a_luz_desce_ao_piso_e_nao_apaga() -> None:
    estado = fx.AoSom(LARANJA, 5)
    _tocar(estado, [1.0] * 30)
    sem = [estado.andar(fx.Entrada(), (30 + i) * PASSO_S) for i in range(240)]
    assert max(sem[-1]) / 255 == pytest.approx(fx.PISO_DO_ACENDE, abs=0.02)
    assert all(q != (0, 0, 0) for q in sem)


def test_cada_controle_tem_o_estado_dele() -> None:
    a, b = fx.AoSom(LARANJA, 5), fx.AoSom((0, 128, 255), 5)
    _tocar(a, [1.0] * 40)
    quieto = _tocar(b, [0.0] * 40)[-1]
    assert max(quieto) / 255 < 0.3, "o som que fez o A subir não acende o B parado"


# ---------------------------------------------------------------- o que o som vira em números


def _pcm(frequencia: float, amplitude: float, segundos: float, fase: float = 0.0) -> bytes:
    n = int(som.TAXA_HZ * segundos)
    return array.array("f", (
        amplitude * math.sin(2 * math.pi * frequencia * (i / som.TAXA_HZ) + fase)
        for i in range(n))).tobytes()


def test_silencio_da_nivel_zero() -> None:
    analise = som.Medidor()
    assert analise.alimentar(bytes(4 * som.TAXA_HZ // 5)) == (0.0, 0.0)


def test_um_grave_e_um_agudo_se_separam_pelos_agudos() -> None:
    grave = som.Medidor().alimentar(_pcm(120.0, 0.5, 0.5))
    agudo = som.Medidor().alimentar(_pcm(3500.0, 0.5, 0.5))
    medio = som.Medidor().alimentar(_pcm(700.0, 0.5, 0.5))
    assert grave is not None and agudo is not None and medio is not None
    assert grave[1] < 0.1, grave
    assert agudo[1] > 0.5, agudo
    assert medio[1] < agudo[1]


def test_o_volume_da_maquina_nao_muda_o_nivel() -> None:
    alto, baixo = som.Medidor(), som.Medidor()
    n_alto = alto.alimentar(_pcm(300.0, 0.8, 1.0))
    n_baixo = baixo.alimentar(_pcm(300.0, 0.08, 1.0))
    assert n_alto is not None and n_baixo is not None
    assert n_alto[0] == pytest.approx(n_baixo[0], abs=0.1), (n_alto, n_baixo)
    assert n_baixo[0] > 0.8


def test_um_pulso_forte_depois_de_um_fraco_sobe_o_nivel() -> None:
    analise = som.Medidor()
    analise.alimentar(_pcm(300.0, 0.6, 1.0))
    fraco = analise.alimentar(_pcm(300.0, 0.1, 0.2))
    forte = analise.alimentar(_pcm(300.0, 0.6, 0.2))
    assert fraco is not None and forte is not None
    assert forte[0] > fraco[0] + 0.5, (fraco, forte)


def test_bytes_em_pedacos_dao_a_mesma_medida_do_bloco_inteiro() -> None:
    dados = _pcm(300.0, 0.5, 0.4)
    inteiro = som.Medidor().alimentar(dados)
    picado = som.Medidor()
    ultimo = None
    for i in range(0, len(dados), 77):
        ultimo = picado.alimentar(dados[i:i + 77]) or ultimo
    assert inteiro is not None and ultimo is not None
    assert ultimo[0] == pytest.approx(inteiro[0], abs=1e-6)


# ---------------------------------------------------------------- só o monitor, nunca o microfone


def test_o_argv_le_o_monitor_da_saida_padrao() -> None:
    argv = som.argv_da_energia()
    assert argv[0] == "parec"
    assert f"--device={som.FONTE_DO_MONITOR}" in argv
    assert som.FONTE_DO_MONITOR == "@DEFAULT_MONITOR@"
    assert not any("DEFAULT_SOURCE" in a or MICROFONE in a for a in argv)


@pytest.mark.parametrize("fonte", [MICROFONE, "@DEFAULT_SOURCE@", "bluez_input.AA_BB_CC_00_00_01",
                                   "", "alsa_output.pci-0000.analog-stereo"])
def test_uma_fonte_que_nao_e_monitor_e_recusada(
        fonte: str, monkeypatch: pytest.MonkeyPatch) -> None:
    assert not som.e_o_monitor(fonte)
    with pytest.raises(ValueError, match="monitor"):
        som.argv_da_energia(fonte)

    def _nao_abre(*_a: Any, **_k: Any) -> None:
        raise AssertionError("abriu um processo para uma fonte que não é monitor")

    monkeypatch.setattr(subprocess, "Popen", _nao_abre)
    assert som.abrir_fluxo(fonte) is None


def test_o_monitor_de_uma_saida_nomeada_vale() -> None:
    assert som.e_o_monitor("alsa_output.pci-0000.analog-stereo.monitor")
    assert som.e_o_monitor("@DEFAULT_MONITOR@")


class _FluxoDeMentira:
    """Entrega os blocos combinados e depois bloqueia até ser parado, como o ``parec``."""

    def __init__(self, blocos: list[bytes]) -> None:
        import threading

        self.blocos = list(blocos)
        self.parou = threading.Event()
        self.entregue = threading.Event()

    def ler(self, _n: int) -> bytes:
        if self.blocos:
            return self.blocos.pop(0)
        self.entregue.set()
        self.parou.wait(5.0)
        return b""

    def parar(self) -> None:
        self.parou.set()


def _esperar(condicao: Any, segundos: float = 3.0) -> bool:
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(0.005)
    return False


def test_a_leitura_abre_so_o_monitor_entrega_a_medida_e_fecha_o_fluxo() -> None:
    abertas: list[str] = []
    fluxo = _FluxoDeMentira([_pcm(300.0, 0.5, 0.5)])

    def abrir(fonte: str) -> _FluxoDeMentira:
        abertas.append(fonte)
        return fluxo

    leitura = som.EnergiaDoSom(abrir=abrir)
    assert leitura.nivel() is None and not leitura.aberto
    leitura.abrir()
    leitura.abrir()  # idempotente
    assert _esperar(lambda: leitura.nivel() is not None)
    assert abertas == [som.FONTE_DO_MONITOR], "uma abertura, só do monitor"
    medida = leitura.nivel()
    assert medida is not None and medida[0] > 0.5
    leitura.fechar()
    leitura.fechar()  # idempotente
    assert fluxo.parou.is_set(), "fechar termina o parec"
    assert leitura.nivel() is None and not leitura.aberto


def test_mudo_ha_mais_de_um_segundo_e_nao_sei_nunca_silencio() -> None:
    relogio = [100.0]
    fluxo = _FluxoDeMentira([_pcm(300.0, 0.5, 0.5)])
    leitura = som.EnergiaDoSom(abrir=lambda _f: fluxo, agora=lambda: relogio[0])
    leitura.abrir()
    assert _esperar(lambda: leitura.nivel() is not None)
    relogio[0] += som.MUDEZ_S + 0.1
    assert leitura.nivel() is None
    leitura.fechar()


def test_sem_o_servidor_de_som_tenta_de_novo_sem_levantar() -> None:
    tentativas: list[str] = []

    def abrir(fonte: str) -> None:
        tentativas.append(fonte)

    leitura = som.EnergiaDoSom(abrir=abrir, espera_apos_falha_s=0.01)
    leitura.abrir()
    assert _esperar(lambda: len(tentativas) >= 3)
    leitura.fechar()
    assert set(tentativas) == {som.FONTE_DO_MONITOR}
    assert leitura.nivel() is None


# ---------------------------------------------------------------- o laço: abre e fecha com o efeito


class _SomDeMentira:
    def __init__(self) -> None:
        self.abriu = 0
        self.fechou = 0
        self.valor: tuple[float, float] | None = (1.0, 0.0)

    def abrir(self) -> None:
        self.abriu += 1

    def fechar(self) -> None:
        self.fechou += 1

    def nivel(self) -> tuple[float, float] | None:
        return self.valor


def _plano(texto: str, uniqs: list[str] | None = None) -> dict[str, luz.PlanoDoControle]:
    efeito = ler_o_efeito_da_luz(texto)
    assert efeito is not None
    return {u: luz.PlanoDoControle(efeito, 1.0, i, i) for i, u in enumerate(uniqs or JOGADORES[:1])}


def _laco(fonte: _SomDeMentira) -> tuple[luz.LuzAnimada, dict[str, list[RGB]]]:
    saiu: dict[str, list[RGB]] = {}
    laco = luz.LuzAnimada(lambda u, c: saiu.setdefault(u, []).append(c), lambda u: None,
                          som=fonte)
    return laco, saiu


def test_o_laco_abre_o_som_quando_um_controle_entra_e_fecha_quando_o_ultimo_sai() -> None:
    fonte = _SomDeMentira()
    laco, _ = _laco(fonte)
    laco.tique(100.0, _plano("respirar;FF8000;5"))
    assert (fonte.abriu, fonte.fechou) == (0, 0), "outro efeito não abre o som"
    for i in range(5):
        laco.tique(101.0 + i / 30, _plano("ao-som;FF8000;5", JOGADORES[:2]))
    assert (fonte.abriu, fonte.fechou) == (1, 0), "dois controles no efeito, uma abertura"
    laco.tique(102.0, _plano("ao-som;FF8000;5", JOGADORES[1:2]))
    assert (fonte.abriu, fonte.fechou) == (1, 0), "enquanto um ainda toca, segue aberto"
    laco.tique(103.0, _plano("respirar;FF8000;5"))
    assert (fonte.abriu, fonte.fechou) == (1, 1), "o último saiu: fecha"
    laco.tique(104.0, _plano("respirar;FF8000;5"))
    assert (fonte.abriu, fonte.fechou) == (1, 1)


def test_parar_tudo_e_controle_calado_fecham_o_som() -> None:
    fonte = _SomDeMentira()
    laco, _ = _laco(fonte)
    laco.tique(100.0, _plano("ao-som;FF8000;5"), calados=frozenset(JOGADORES[:1]))
    assert fonte.abriu == 0, "quem está calado não toca, então o som não abre"
    laco.tique(101.0, _plano("ao-som;FF8000;5"))
    assert fonte.abriu == 1
    laco.parar_tudo()
    assert fonte.fechou == 1


def test_o_laco_pinta_pelo_som_e_a_falha_do_som_nao_derruba() -> None:
    fonte = _SomDeMentira()
    laco, saiu = _laco(fonte)
    plano = _plano("ao-som;FF8000;5")
    for i in range(30):
        laco.tique(100.0 + i / 30, plano)
    alto = max(saiu[JOGADORES[0]][-1]) / 255
    fonte.valor = None
    for i in range(30, 150):
        laco.tique(100.0 + i / 30, plano)
    baixo = max(saiu[JOGADORES[0]][-1]) / 255
    assert alto > 0.9 and baixo < 0.35

    class _Quebrada(_SomDeMentira):
        def abrir(self) -> None:
            raise RuntimeError("sem servidor de som")

    quebrado, _ = _laco(_Quebrada())
    assert quebrado.tique(100.0, plano) == 1, "a luz sai mesmo sem som"


def test_dois_controles_pintam_cada_um_na_sua_cor_com_o_mesmo_som() -> None:
    fonte = _SomDeMentira()
    laco, saiu = _laco(fonte)
    efeitos = {JOGADORES[0]: luz.PlanoDoControle(EfeitoDaLuz("ao-som", (LARANJA,), 5), 1.0),
               JOGADORES[1]: luz.PlanoDoControle(EfeitoDaLuz("ao-som", ((0, 128, 255),), 5), 1.0)}
    for i in range(30):
        laco.tique(100.0 + i / 30, efeitos)
    assert saiu[JOGADORES[0]][-1] == LARANJA and saiu[JOGADORES[1]][-1] == (0, 128, 255)


def test_o_daemon_sobe_o_laco_com_a_leitura_de_producao() -> None:
    async def subir() -> Any:
        daemon = SimpleNamespace(_tasks=[], _is_stopping=lambda: True, controller=None)
        luz.start_luz_animada(daemon)
        await asyncio.gather(*daemon._tasks, return_exceptions=True)
        return daemon._luz_animada

    laco = asyncio.run(subir())
    assert isinstance(laco._som, som.EnergiaDoSom)
    assert not laco._som.aberto, "sem controle no efeito, o som nem abre"


# ---------------------------------------------------------------- a tela


def _doc() -> str:
    bruto = MOCKUP.read_text(encoding="utf-8")
    sem_comentario = re.sub(r"<!--.*?-->", "", bruto, flags=re.S)
    return re.sub(r"<(style|script)\b[^>]*>.*?</\1>", "", sem_comentario, flags=re.S)


def _ctx(n: int = 1) -> Any:
    import pacotes
    from hefesto_dualsense4unix.core.led_control import player_slot_color

    uniq = JOGADORES[n - 1]
    return pacotes.Contexto(
        state={"active_profile": ""},
        mesa=[{"pref": f"p{n}", "jogador": n, "uniq": uniq, "nome": "Régua", "via": "USB",
               "cor": "starlight-blue"}],
        conectados=[{"uniq": uniq, "connected": True, "transport": "usb", "index": n - 1,
                     "player": n, "lightbar_rgb": list(player_slot_color(n))}],
        estados={})


def _gesto(nome: str) -> Any:
    import pacotes

    gesto = pacotes.gesto_da_pagina("04-iluminacao.html", nome)
    assert gesto is not None, nome
    return gesto


def test_o_ao_som_esta_no_grupo_que_reage_das_quatro_listas_e_nada_novo_na_tela() -> None:
    doc = _doc()
    listas = re.findall(r'<select class="g4-efeito".*?</select>', doc, flags=re.S)
    assert len(listas) == 4
    for lista in listas:
        grupo = lista.split('<optgroup label="Que reage">', 1)[1].split("</optgroup>", 1)[0]
        opcoes = re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)</option>', grupo)
        assert ("base:ao-som", "Ao som") in opcoes
    assert doc.count('class="g4-efeito"') == 4, "uma lista por controle, nada a mais na tela"


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_escolher_ao_som_grava_o_texto_com_a_cor_do_controle_e_a_lista_o_reconhece(n: int) -> None:
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_computador
    from pacotes import a04_iluminacao as a04

    uniq = JOGADORES[n - 1]
    cor = a04.pacote(_ctx(n))["colunas"][uniq]["hex"].lstrip("#").upper()
    _gesto("efeito-da-luz")(_ctx(n), {"uniq": uniq, "valor": "base:ao-som"}, None)
    guardado = o_computador().controles[uniq.replace(":", "")].leds.efeito
    assert guardado == f"ao-som;{cor};5", guardado
    coluna = a04.pacote(_ctx(n))["colunas"][uniq]
    assert coluna[a04.CAMPO_DO_EFEITO] == "base:ao-som"
    assert coluna[a04.CAMPO_DA_DICA_DO_EFEITO] == a04.DICA_DA_BASE["ao-som"]
    assert a04.ROTULO_DA_BASE["ao-som"] == "Ao som"


def test_trocar_a_cor_leva_o_ao_som_junto() -> None:
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_computador
    from pacotes import a04_iluminacao as a04

    class _Ponte:
        def led_set_detalhado(self, *_a: Any, **_k: Any) -> dict[str, Any]:
            return {"aplicado_em": [JOGADORES[0]], "guardado_em": []}

    _gesto("efeito-da-luz")(_ctx(), {"uniq": JOGADORES[0], "valor": "base:ao-som"}, None)
    a04.cor(_ctx(), {"uniq": JOGADORES[0], "hex": "FF8000"}, _Ponte())
    assert o_computador().controles["aabbcc000001"].leds.efeito == "ao-som;FF8000;5"


def test_o_criar_efeitos_novos_recusa_o_ao_som() -> None:
    import pacotes

    ctx = pacotes.Contexto(state={"active_profile": ""}, mesa=[], conectados=[], estados={})
    with pytest.raises(RuntimeError, match="Escolha como a luz se move"):
        pacotes.gesto_da_pagina("04-iluminacao.html", "criar-efeito")(
            ctx, {"forma": {"base": "ao-som", "cores": "#ff0000", "ritmo": "5", "nome": "X"}},
            None)
