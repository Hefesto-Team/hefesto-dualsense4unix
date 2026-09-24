"""O-MODO-FREESTYLE-01 — o cadeado vira «Modo Freestyle».

A palavra dela, 23/09/2026, com a foto da aba Jogar dizendo «Perfil ativo
Personalizado» no topo:

    *"Personalizado sai e o botão Trava o perfil Ativo na aba jogar. Vira Modo
    Freestyle o botão. E a fonte dele aumenta e a altura do botão aumenta também
    na hoje. O trava perfil ativo já faz isso."*  (noqa-acento: citação dela)

Este arquivo guarda a metade da TELA e a matriz do botão: ele diz «Modo
Freestyle», maior que hoje, no desenho — e a página publicada continua com a
palavra de ontem até o `--publicar 01`.

NOTA DATADA — 24/09/2026, O-MODO-FREESTYLE-02. Aqui morava também o MOTOR da
01, que tirava o «Personalizado» do disco (`aposentar_o_personalizado`) e
esperava a sessão dela (`O_PERSONALIZADO_ESPERA_A_SESSAO_DELA`), com a medição
que o segurava: sem ele, do boot ao primeiro jogo nenhum perfil vale e as abas
recusam o ajuste. A decisão por delegação dela
(`D-2409-O-PERFIL-DE-FORA-DO-JOGO-VIRA-FREESTYLE`) trocou a saída pela
renomeação: o perfil de fora do jogo fica e se chama «Freestyle». O motor e a
espera saíram; as réguas deles passaram a medir o Freestyle, e moram em
`tests/unit/test_o_perfil_freestyle.py`.
"""
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
JOGO = "steam_app_2111190"  # Mullet Mad Jack — o jogo sem perfil de 24/07

# =============================================================================
# 1. A MATRIZ — o Modo Freestyle é um só, para os quatro, nos dois transportes
# =============================================================================

class _Ponte:
    """Responde ao `autoswitch_lock_set` como `ipc_bridge` responde: o estado
    que ficou valendo. Nada mais frouxo que o real — um `True` para tudo
    mentiria sobre um pedido de soltar."""

    def __init__(self) -> None:
        self.chamadas: list[dict[str, Any]] = []

    def autoswitch_lock_set(self, locked: bool | None = None) -> bool | None:
        self.chamadas.append({"locked": locked})
        return locked


def _mesa_de_quatro() -> list[dict[str, Any]]:
    """P1 e P3 no cabo, P2 e P4 no rádio — a mesa inteira, não só o P1."""
    return [{"uniq": f"aa:bb:cc:00:00:0{n}", "player": n, "connected": True,
             "transport": "usb" if n % 2 else "bluetooth"} for n in (1, 2, 3, 4)]


@pytest.mark.parametrize("caminho", ["dualsense", "xbox", "steam_input"])
@pytest.mark.parametrize("travado", [False, True], ids=["liga", "desliga"])
def test_o_freestyle_e_um_so_para_a_mesa_inteira(caminho: str, travado: bool) -> None:
    """Um clique, UMA chamada, com o valor absoluto — em qualquer caminho.

    O Modo Freestyle trava a TROCA DE PERFIL, que é da máquina inteira: o gesto
    não lê o controle escolhido na fita, nem o transporte, nem o caminho. Se um
    dia ele virar por controle, esta régua reprova e a decisão volta a ela.
    """
    from hefesto_dualsense4unix.interface.pacotes import Contexto
    from hefesto_dualsense4unix.interface.pacotes import a01_jogar as aba

    mesa = _mesa_de_quatro()
    estado = {"controllers": mesa, "autoswitch_locked": travado,
              "gamepad_emulation": {"caminho": caminho}}
    ponte = _Ponte()

    aba.cadeado(Contexto(state=estado, mesa=mesa, conectados=mesa),
                {"evento": "click"}, ponte)

    assert ponte.chamadas == [{"locked": not travado}]


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_com_o_freestyle_ligado_a_janela_de_jogo_nao_troca_o_perfil(
    transporte: str,
) -> None:
    """A prova da sprint, no motor: liga o modo e abre uma janela de jogo.

    Nos dois transportes, com o controle de mentira no cabo e no rádio: a trava
    é da máquina, e o transporte não pode decidir o resultado.

    O jogo aqui não tem perfil próprio — e é o caso em que a trava segura. O
    jogo COM perfil próprio entra por cima (LOCK-CEDE-01, decisão dela de
    24/07), e isso não mudou: `test_autoswitch_lock` guarda aquela metade.
    """
    loader.save_profile(Profile(name="Navegação",
                                match=MatchCriteria(window_class=["steam"]),
                                priority=50))
    store = StateStore()
    store.set_active_profile("Mullet Mad Jack")
    store.set_autoswitch_locked(True)
    controle = FakeController(transport=transporte)
    controle.connect()
    sw = AutoSwitcher(manager=ProfileManager(controller=controle, store=store),
                      window_reader=lambda: {}, store=store)

    for janela in ({"wm_class": JOGO, "wm_name": "Mullet Mad Jack"},
                   {"wm_class": "steam", "wm_name": "Steam"}):
        for t in (0.0, 0.6, 30.0, 60.0):
            sw._tick(janela, t)

    assert store.active_profile == "Mullet Mad Jack"


# =============================================================================
# 2. A TELA — o desenho diz «Modo Freestyle», e a publicada muda no `--publicar 01`
# =============================================================================

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

    # O QUE O PRODUTO ESCONDE, perguntado ao dono: a legenda do desenho (`.nota`)
    # mora fora da janela e faria o DOCUMENTO rolar numa página que o produto
    # nunca mostra assim.
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
    """O pedido dela, em pixels: maior que hoje, e ainda um botão de canto.

    MORDE: devolva o `height:17px`/`font-size:10.5px` ao `.cadeado` do
    `aba01.py`, regere o desenho, e esta régua reprova.

    Desde o `--publicar 01` de 24/09/2026 as duas são a mesma página, e a
    régua confere que o desenho CHEGOU inteiro ao produto.
    """
    desenho, hoje = as_duas_paginas["desenho"], as_duas_paginas["publicada"]
    assert (desenho["fonte"], desenho["altura"]) == (hoje["fonte"], hoje["altura"]), (
        f"a publicada diz {hoje['rotulo']!r} e não tem a letra e a altura do "
        f"desenho: {hoje} contra {desenho}")
    # Menor que um botão de escolha: da altura dos chips de modo ele voltaria
    # a ler como um quinto modo (o motivo de ter subido ao canto em 08/09).
    assert desenho["altura"] < desenho["escolha"], desenho
    assert desenho["linhas"] == 1, desenho
    assert desenho["no_topo"] and desenho["a_direita"] < 20, desenho


def test_a_aba_continua_sem_rolar(as_duas_paginas: dict[str, dict[str, Any]]) -> None:
    """A conta de altura, paga: a linha do título cresceu e a aba não rola."""
    assert not as_duas_paginas["desenho"]["rola"], as_duas_paginas["desenho"]
