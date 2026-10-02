"""O-MODO-FREESTYLE-01 — o cadeado vira «Modo Freestyle»."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile
from hefesto_dualsense4unix.testing import FakeController

RAIZ = Path(__file__).resolve().parents[2]
JOGO = "steam_app_2111190"


class _Ponte:
    """Responde ao `freestyle_set` como `ipc_bridge` responde: o estado"""

    def __init__(self) -> None:
        self.chamadas: list[dict[str, Any]] = []

    def freestyle_set(self, ligado: bool | None = None) -> bool | None:
        self.chamadas.append({"ligado": ligado})
        return ligado


def _mesa_de_quatro() -> list[dict[str, Any]]:
    """P1 e P3 no cabo, P2 e P4 no rádio — a mesa inteira, não só o P1."""
    return [{"uniq": f"aa:bb:cc:00:00:0{n}", "player": n, "connected": True,
             "transport": "usb" if n % 2 else "bluetooth"} for n in (1, 2, 3, 4)]


@pytest.mark.parametrize("caminho", ["dualsense", "xbox", "steam_input"])
@pytest.mark.parametrize("travado", [False, True], ids=["liga", "desliga"])
def test_o_freestyle_e_um_so_para_a_mesa_inteira(caminho: str, travado: bool) -> None:
    """Um clique, UMA chamada, com o valor absoluto — em qualquer caminho."""
    from hefesto_dualsense4unix.interface.pacotes import Contexto
    from hefesto_dualsense4unix.interface.pacotes import a01_jogar as aba

    mesa = _mesa_de_quatro()
    estado = {"controllers": mesa, "freestyle_ligado": travado,
              "gamepad_emulation": {"caminho": caminho}}
    ponte = _Ponte()

    aba.cadeado(Contexto(state=estado, mesa=mesa, conectados=mesa),
                {"evento": "click"}, ponte)

    assert ponte.chamadas == [{"ligado": not travado}]


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_com_o_freestyle_ligado_a_janela_de_jogo_nao_troca_o_perfil(
    transporte: str,
) -> None:
    """A prova da sprint, no motor: liga o modo e abre uma janela de jogo."""
    loader.save_profile(Profile(name="Navegação",
                                match=MatchCriteria(window_class=["steam"]),
                                priority=50))
    loader.save_profile(Profile(name="Mullet Mad Jack",
                                match=MatchCriteria(window_class=[JOGO]),
                                priority=90))
    loader.save_profile(Profile(name=loader.NOME_DO_PADRAO,
                                match=MatchCriteria(), priority=0))
    store = StateStore()
    store.set_active_profile(loader.NOME_DO_PADRAO)
    store.set_freestyle_ligado(True)
    controle = FakeController(transport=transporte)
    controle.connect()
    sw = AutoSwitcher(manager=ProfileManager(controller=controle, store=store),
                      window_reader=lambda: {}, store=store)

    for janela in ({"wm_class": JOGO, "wm_name": "Mullet Mad Jack"},
                   {"wm_class": "steam", "wm_name": "Steam"}):
        for t in (0.0, 0.6, 30.0, 60.0):
            sw._tick(janela, t)

    assert store.active_profile == loader.NOME_DO_PADRAO


def _rotulo_do_botao(html: str) -> str:
    import re

    achado = re.search(r'<button class="cadeado"[^>]*><span class="p"></span>([^<]+)</button>',
                       html)
    assert achado, "a página não tem o botão do canto do bloco Modo"
    return achado.group(1).strip()


def test_o_desenho_diz_modo_freestyle() -> None:
    from hefesto_dualsense4unix.interface import onde
    from hefesto_dualsense4unix.interface.pacotes.a01_jogar import CADEADO_ROTULO

    assert CADEADO_ROTULO == "Modo Freestyle"
    assert _rotulo_do_botao(onde.pagina("01-jogar.html").read_text()) == CADEADO_ROTULO


_MEDE = """() => {
  const cad = document.querySelector('.cadeado');
  const cs = getComputedStyle(cad), b = cad.getBoundingClientRect();
  const texto = [...cad.childNodes].find(n => n.nodeType === 3 && n.textContent.trim());
  const r = document.createRange(); r.selectNodeContents(texto);
  const jan = document.querySelector('.janela');
  return {fonte: parseFloat(cs.fontSize), altura: b.height,
          rotulo: texto ? texto.textContent.trim() : '',
          escolha: parseFloat(getComputedStyle(document.documentElement)
                              .getPropertyValue('--h-escolha')),
          linhas: r.getClientRects().length,
          no_topo: cad.closest('.quadro-topo') !== null,
          a_direita: Math.round(cad.closest('.quadro').getBoundingClientRect().right - b.right),
          rola: jan.scrollHeight > jan.clientHeight + 1
                || document.documentElement.scrollHeight > innerHeight + 1};
}"""


@pytest.fixture(scope="module")
def as_duas_paginas() -> dict[str, dict[str, Any]]:
    """O desenho e a publicada, no Chrome, na vista mais apertada (1212x809)."""
    chrome = Path("/usr/bin/google-chrome")
    if not chrome.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    from playwright.sync_api import sync_playwright

    from hefesto_dualsense4unix.interface import onde
    from hefesto_dualsense4unix.interface.folha_da_casa import seletores_escondidos

    esconde = "".join(f"{s}{{display:none}}" for s in seletores_escondidos())
    saida: dict[str, dict[str, Any]] = {}
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(chrome), args=["--no-sandbox"])
        try:
            for nome, publicado in (("desenho", False), ("publicada", True)):
                pg = nav.new_page(viewport={"width": 1212, "height": 809})
                pg.goto(onde.pagina("01-jogar.html", publicado=publicado).as_uri())
                pg.wait_for_load_state("networkidle")
                pg.add_style_tag(content=esconde)
                pg.wait_for_timeout(200)
                saida[nome] = dict(pg.evaluate(_MEDE))
                pg.close()
        finally:
            nav.close()
    return saida


def test_o_botao_do_desenho_tem_letra_e_altura_maiores(
    as_duas_paginas: dict[str, dict[str, Any]],
) -> None:
    """O pedido dela, em pixels: maior que hoje, e ainda um botão de canto."""
    desenho, hoje = as_duas_paginas["desenho"], as_duas_paginas["publicada"]
    assert (desenho["fonte"], desenho["altura"]) == (hoje["fonte"], hoje["altura"]), (
        f"a publicada diz {hoje['rotulo']!r} e não tem a letra e a altura do "
        f"desenho: {hoje} contra {desenho}")
    assert desenho["altura"] < desenho["escolha"], desenho
    assert desenho["linhas"] == 1, desenho
    assert desenho["no_topo"] and desenho["a_direita"] < 20, desenho


def test_a_aba_continua_sem_rolar(as_duas_paginas: dict[str, dict[str, Any]]) -> None:
    """A conta de altura, paga: a linha do título cresceu e a aba não rola."""
    assert not as_duas_paginas["desenho"]["rola"], as_duas_paginas["desenho"]
