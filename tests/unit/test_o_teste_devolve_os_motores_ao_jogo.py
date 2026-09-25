"""O "Testar" da Vibração nunca deixa o jogo mudo — A-TELA-QUE-TRAVA-02.

ORDEM DELA, 15/09/2026, com o controle na mão:

    *"o testar e parar é sobre o teste naquele momento isso nao  (noqa-acento: dela)
     interfere in game. testar eu ligo o status de vibração pra ver se eu
     concordo como isso vai funcionar. mas clicar em parar é só pra impactar no teste naquele
     momento e não mutar a vibração in game. em game se eu quiser desligar a
     vibração do motor esquerdo zero o slicer, no direito o mesmo e de forma
     geral eu zero no perfil max min e personalizado."*
     (noqa-acento: citação literal dela)

O QUE ESTAVA QUEBRADO, e foi medido antes de ser curado: o "Testar" tira os
motores do jogo (`rumble.passthrough(False)`) e `parar_o_teste()` tinha DOIS
chamadores — o botão "Parar" e o controle que sai da mesa. **Nenhum deles é
fechar a janela.** Trocar de aba, fechar a janela ou a janela morrer deixava
`rumble_passthrough=False` para sempre: o jogo ficava sem vibração até ela
reabrir a aba Vibração e clicar em "Parar", e nada na tela dizia por quê —
porque a tela já não estava lá.

    $ grep "parar_o_teste|em_teste|rumble_passthrough" hefesto_vivo.py
    (nada)

ELA ESCOLHEU ENTRE QUATRO CAMINHOS e pegou **as duas metades mais a rede**:

1. **a LARGADA** — o piloto devolve ao trocar de página e ao fim da janela;
2. **o CORAÇÃO** — enquanto a janela vive, a aba rebate a cada 1 s, e por isso
   um teste deixado ligado com a janela aberta NÃO solta sozinho (o pedido dela
   de 07/09: *"o botão Testar tem que ficar em estado de ligado"*);
3. **o TETO** — o daemon solta o rumble fixado que ninguém rebate em 3 s. É a
   rede para a janela que MORRE sem conseguir largar, e cobre TODOS os
   chamadores: o `hef test rumble` da CLI tinha o mesmo buraco.

O QUE ESTA RÉGUA NÃO COBRE, e está dito para ninguém a ler como mais do que é:
o teto de verdade mora no daemon (`subsystems/rumble.reassert_rumble`) e é
medido pela régua dele. Aqui se mede o lado da JANELA — as duas metades — e o
contrato entre elas.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05

UNIQ = "aa:bb:cc:00:00:05"


class PonteQueAnota:
    """A ponte de mentira: guarda o que foi pedido, na ordem."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...]]] = []

    def rumble_stop(self, *a: Any) -> tuple[bool, dict[str, Any]]:
        self.chamadas.append(("rumble_stop", a))
        return True, {"status": "ok"}

    def rumble_passthrough(self, *a: Any) -> tuple[bool, dict[str, Any]]:
        self.chamadas.append(("rumble_passthrough", a))
        return True, {"status": "ok"}

    def rumble_set_checked(self, *a: Any) -> tuple[bool, dict[str, Any]]:
        self.chamadas.append(("rumble_set_checked", a))
        return True, {"status": "ok"}

    @property
    def nomes(self) -> list[str]:
        return [n for n, _ in self.chamadas]


@pytest.fixture(autouse=True)
def _mesa_limpa():
    """Nenhum teste herda o `_EM_TESTE` do anterior — eles rodam no MESMO processo."""
    a05.parar_o_teste()
    a05._BATEU_EM[0] = 0.0
    yield
    a05.parar_o_teste()
    a05._BATEU_EM[0] = 0.0


def _ctx(com_o_controle: bool = True) -> pacotes.Contexto:
    item = {"uniq": UNIQ, "pref": "p1", "jogador": 1, "nome": "Prova", "cor": "",
            "transporte": "usb", "via": "cabo", "alvo": True, "mascara": "dualsense"}
    controle = {"uniq": UNIQ, "connected": True, "player": 1, "transport": "usb"}
    return pacotes.Contexto(
        state={"controllers": [controle], "rumble_motor_pct_padrao": 100},
        mesa=[item] if com_o_controle else [],
        conectados=[controle], estados={}, externos=[])


# --------------------------------------------------------------------------
# 1. A LARGADA — o que a aba segurava volta ao jogo
# --------------------------------------------------------------------------
def test_a_aba_registrou_a_largada_no_despachante() -> None:
    """Sem o registro, o piloto larga o vazio e a cura não existe."""
    assert pacotes.LARGADAS, (
        "nenhuma aba registrou uma largada — o `pacotes.largar_o_que_as_abas_"
        "seguram` do piloto virou um laço sobre lista vazia")
    assert a05._largar_o_teste in pacotes.LARGADAS


def test_largar_devolve_os_motores_ao_jogo_na_ordem_do_parar() -> None:
    """`rumble.stop` e DEPOIS `passthrough(True)` — parar sozinho deixa mudo.

    A ordem não é estilo: `rumble_stop` fixa `(0, 0)` e o laço do daemon
    re-afirma o silêncio. Sem o `passthrough(True)` em seguida, o jogo fica
    mudo — é a SPRINT-GAME-RUMBLE-01, e é exatamente o defeito que esta cura
    existe para fechar.
    """
    p = PonteQueAnota()
    a05._EM_TESTE[0] = UNIQ
    a05._largar_o_teste(p)
    assert p.nomes == ["rumble_stop", "rumble_passthrough"], (
        f"a largada chamou {p.nomes}")
    assert p.chamadas[1][1] == (True,), (
        f"o passthrough foi devolvido com {p.chamadas[1][1]!r} — tem de ser "
        f"`True`, que é o que devolve a mão ao jogo")
    assert a05.em_teste() == "", "a marca do teste sobreviveu à largada"


def test_largar_sem_teste_ligado_nao_fala_com_o_daemon() -> None:
    """Trocar de aba com o teste desligado não pode mexer na vibração do jogo.

    O piloto larga a CADA travessia de página. Se a largada falasse sempre, um
    passeio pelas dez abas mandaria dez `rumble.stop` ao daemon dela — e o
    `stop` fixa `(0, 0)`, que é o jogo mudo por um gesto que ninguém fez.
    """
    p = PonteQueAnota()
    a05._largar_o_teste(p)
    assert p.nomes == [], (
        f"a largada falou com o daemon sem teste ligado: {p.nomes}")


def test_a_marca_cai_mesmo_com_a_ponte_morta() -> None:
    """A janela indo embora é justamente quando a ponte morre.

    Se a marca só caísse depois de os dois passos darem certo, uma ponte morta
    deixaria `_EM_TESTE` ligado — e o próximo arraste de barra ressuscitaria o
    tremor de um teste que já acabou.
    """
    class PonteMorta:
        def rumble_stop(self, *a: Any) -> None:
            raise OSError("a ponte morreu")

        def rumble_passthrough(self, *a: Any) -> None:
            raise OSError("a ponte morreu")

    a05._EM_TESTE[0] = UNIQ
    a05._largar_o_teste(PonteMorta())
    assert a05.em_teste() == "", (
        "a ponte morta deixou a marca do teste ligada")


def test_o_despachante_nunca_levanta_por_causa_de_uma_largada() -> None:
    """Uma aba que levanta na largada não pode derrubar a saída da janela."""
    def larga_mal(_p: Any) -> None:
        raise RuntimeError("eu quebro")

    pacotes.LARGADAS.append(larga_mal)
    try:
        pacotes.largar_o_que_as_abas_seguram(PonteQueAnota())
    finally:
        pacotes.LARGADAS.remove(larga_mal)


# --------------------------------------------------------------------------
# 2. O CORAÇÃO — enquanto a janela vive, o teste fica de pé
# --------------------------------------------------------------------------
def test_a_aba_registrou_o_coracao() -> None:
    assert a05._bater_o_coracao_do_teste in pacotes.CORACOES


def test_sem_teste_ligado_o_coracao_nao_bate() -> None:
    """Dez batimentos por segundo sobre nada seriam dez IPCs por segundo."""
    p = PonteQueAnota()
    for _ in range(5):
        a05._bater_o_coracao_do_teste(_ctx(), p)
    assert p.nomes == [], f"o coração bateu sem teste ligado: {p.nomes}"


def test_o_coracao_bate_uma_vez_por_segundo_e_nao_por_tique() -> None:
    """O espaçamento é da ABA, e é o que separa a cura de uma enxurrada.

    MORDIDA: apague o `if agora - _BATEU_EM[0] < SEGUNDOS_ENTRE_BATIMENTOS` e
    este teste reprova — dez tiques viram dez viagens de IPC.
    """
    p = PonteQueAnota()
    a05._EM_TESTE[0] = UNIQ
    for _ in range(10):          # dez tiques, ~1 s de janela
        a05._bater_o_coracao_do_teste(_ctx(), p)
    assert p.nomes == ["rumble_set_checked"], (
        f"dez tiques deram {len(p.nomes)} batimentos: {p.nomes}. O espaçamento "
        f"de {a05.SEGUNDOS_ENTRE_BATIMENTOS}s morreu")


def test_o_teto_do_daemon_cabe_em_tres_batimentos() -> None:
    """O contrato entre os dois números, e é o que faz o teste não piscar.

    Se o teto do daemon encolher para perto do espaçamento, UM batimento
    perdido — um tique pulado por pintura no ar, um IPC lento — solta os motores
    no meio do teste dela.
    """
    from hefesto_dualsense4unix.daemon.subsystems import rumble as _rumble

    cabem = _rumble.TETO_DO_RUMBLE_FIXADO_S / a05.SEGUNDOS_ENTRE_BATIMENTOS
    assert cabem >= 3, (
        f"o teto do daemon ({_rumble.TETO_DO_RUMBLE_FIXADO_S}s) cabe só "
        f"{cabem:.1f} batimentos de {a05.SEGUNDOS_ENTRE_BATIMENTOS}s. Com menos "
        f"de três, um batimento perdido solta o teste na mão dela")


def test_o_controle_que_sai_da_mesa_desliga_o_teste() -> None:
    """Rebater com o dono ausente mandaria o par para o alvo de output DE AGORA."""
    p = PonteQueAnota()
    a05._EM_TESTE[0] = UNIQ
    a05._bater_o_coracao_do_teste(_ctx(com_o_controle=False), p)
    assert p.nomes == [], f"bateu com o controle fora da mesa: {p.nomes}"
    assert a05.em_teste() == "", "o teste continuou ligado com o dono ausente"


def test_o_despachante_nunca_levanta_por_causa_de_um_coracao() -> None:
    """Um tique que levanta para de pintar a aba INTEIRA.

    Trocar um jogo sem vibração por uma tela congelada seria o pior dos dois
    negócios — e é a A-TELA-QUE-TRAVA-01 de volta pela outra porta.
    """
    def bate_mal(_ctx: Any, _p: Any) -> None:
        raise RuntimeError("eu quebro")

    pacotes.CORACOES.append(bate_mal)
    try:
        pacotes.bater_os_coracoes(_ctx(), PonteQueAnota())
    finally:
        pacotes.CORACOES.remove(bate_mal)


# --------------------------------------------------------------------------
# 3. O PILOTO — ele bate e larga, sem saber que o assunto é vibração
# --------------------------------------------------------------------------
def test_o_piloto_larga_ao_trocar_de_pagina_e_ao_sair() -> None:
    import inspect

    from hefesto_dualsense4unix.interface import hefesto_vivo as hv

    assert "largar_o_que_as_abas_seguram" in inspect.getsource(hv.Piloto._ir), (
        "o piloto não larga mais ao TROCAR de página — sair da aba Vibração com "
        "o Testar ligado volta a deixar o jogo mudo")
    assert "largar_o_que_as_abas_seguram" in inspect.getsource(hv.Piloto._relatar), (
        "o piloto não larga mais no fim da janela — fechar a janela com o "
        "Testar ligado volta a deixar o jogo mudo")
    assert "bater_os_coracoes" in inspect.getsource(hv.Piloto._tique), (
        "o piloto parou de bater o coração — o teto de ociosidade do daemon "
        "passaria a soltar o teste dela em 3 s, com a janela aberta")


def test_o_piloto_nao_sabe_que_o_assunto_e_vibracao() -> None:
    """A régua contra o desvio por nome de página no dono das dez abas.

    O piloto é o dono das DEZ e não conhece o assunto de nenhuma. Uma segunda
    aba que segure um aparelho amanhã registra em `pacotes` e ganha as duas
    metades de graça — e quem escreve a aba não precisa lembrar de mexer aqui,
    que é a forma de defeito que o `GESTOS_QUE_MEXEM` já nomeia.
    """
    import inspect

    from hefesto_dualsense4unix.interface import hefesto_vivo as hv

    for metodo in (hv.Piloto._ir, hv.Piloto._relatar, hv.Piloto._tique):
        corpo = inspect.getsource(metodo)
        linhas = [ln for ln in corpo.splitlines()
                  if ("a05_vibracao" in ln or "em_teste" in ln
                      or "parar_o_teste" in ln or "rumble" in ln.lower())
                  and not ln.lstrip().startswith("#")]
        assert not linhas, (
            f"`{metodo.__name__}` passou a conhecer o assunto de UMA aba:\n  "
            + "\n  ".join(ln.strip() for ln in linhas))
