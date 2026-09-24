#!/usr/bin/env python3
"""O CINZA DA MIRA E DO «NATIVO» DO MICROFONE AVISA O LEITOR DE TELA.

**A-MIRA-NA-NAVEGACAO-01, 24/09/2026**, item 3 da sprint: o chip «Mira
Virtual» fica cinza no Modo Nativo (`D-2409-NO-NATIVO-A-MIRA-FICA-CINZA`) e o
«Nativo» do microfone fica cinza no BT (decisão dela de 20/09). Os dois
ficavam cinza SÓ para quem enxerga: o endereço do cinza morava no GRUPO, e o
botão não tinha `aria-disabled`.

A FORMA É A DA PEÇA DAS DEZ (`monta.botao_cinza`): o botão leva o campo do
cinza com `data-hef-atributo="aria-disabled"`, e o piloto deriva o atributo da
classe no mesmo elemento (`test_o_alvo_classe_tambem_veste_o_aria`). Como um
elemento aceita UM alvo, o aceso que o botão carregava (`mira-ligada`,
`mic-modo-aceso`) desceu para um invólucro de `display:contents` — e é esse o
risco que esta régua vigia: **a geometria medida não pode mudar**.

A régua abre a BANCADA de verdade (`mockup/02-controles.html`) num WebKit
offscreen, instala o BOOTSTRAP lido do fonte do piloto e pinta os três
estados com os valores que o pacote pinta (`MIRA_NO_NATIVO`,
`_selo_do_sensor`).

AS MORDIDAS, uma por teste:

* tire o `data-hef-atributo="aria-disabled"` do botão da Mira no gerador e
  `test_no_nativo_os_dois_avisam_o_leitor` reprova;
* tire `.sensores-peca .chip-da-mira{display:contents}` da folha e
  `test_a_geometria_nao_mudou` reprova (o chip sai da grade de três);
* tire `.sensores-peca .chip-da-mira.off>.sw` da folha e
  `test_a_mira_apagada_tem_a_cara_do_sensor_apagado` reprova.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PILOTO = RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"
BANCADA = RAIZ / "mockup/02-controles.html"

from pacotes.a02_controles import MIRA_NO_NATIVO

#: A razão do «Nativo» fora de alcance: qualquer texto não vazio acende o
#: cinza (o alvo `classe` sem `data-hef-quando` é booleano). O texto de
#: verdade é do pacote (`nativo_fora_de_alcance`) e não é o que se mede aqui.
RAZAO_DE_ENSAIO = "No BT o microfone não entra sozinho."


def _constante(nome: str) -> str:
    """O BOOTSTRAP lido do FONTE do piloto, e não importado."""
    fonte = PILOTO.read_text(encoding="utf-8")
    achou = re.search(rf'^{nome} = r"""(.*?)"""$', fonte, re.S | re.M)
    assert achou, f"o piloto perdeu o {nome} — não há o que testar"
    return achou.group(1)


ROTEIRO = """
(function(){
  const r = document.getElementById('c-p1');
  if (r) { r.checked = true; }
  const card = document.querySelector('[data-controle="p1"]');
  const q = s => card.querySelector(s);
  const mira = q('button[data-gesto="mira"]');
  const giro = q('button[data-sensor="giroscopio"]');
  const accel = q('button[data-sensor="acelerometro"]');
  const nativo = q('button[data-mic-modo="nativo"]');
  const virtual = q('button[data-mic-modo="virtual"]');
  const caixa = el => { const b = el.getBoundingClientRect();
    return [b.x, b.y, b.width, b.height].map(v => Math.round(v * 10) / 10); };
  const cara = el => { const s = getComputedStyle(el);
    return {cor: s.color, fundo: s.backgroundColor, borda: s.borderTopColor,
            peso: s.fontWeight, cursor: s.cursor}; };
  const foto = () => ({
    aria_mira: mira.getAttribute('aria-disabled'),
    aria_mic: nativo.getAttribute('aria-disabled'),
    aria_virtual: virtual.getAttribute('aria-disabled'),
    caixa_mira: caixa(mira), caixa_giro: caixa(giro), caixa_accel: caixa(accel),
    caixa_nativo: caixa(nativo), caixa_virtual: caixa(virtual),
    cara_mira: cara(mira), cara_accel: cara(accel),
    cara_nativo: cara(nativo), cara_virtual: cara(virtual),
  });
  const fora = {};
  fora.virgem = foto();
  // O MODO NATIVO, no cabo e no rádio: a Mira fica cinza nos quatro, e o
  // «Nativo» do microfone fica cinza onde ele não alcança.
  window.__hef.pintar({colunas: {p1: {
    'mira-fora': 'MIRA_NO_NATIVO_AQUI', 'mira-ligada': 'DESLIGADO',
    'accel-ligado': 'DESLIGADO', 'giro-ligado': 'LIGADO',
    'mic-nativo-fora': 'RAZAO_AQUI', 'mic-modo-aceso': 'virtual'}}});
  fora.cinza = foto();
  // FORA DO NATIVO, com a Mira acesa e o «Nativo» do microfone escolhido.
  window.__hef.pintar({colunas: {p1: {
    'mira-fora': '', 'mira-ligada': 'LIGADO',
    'accel-ligado': 'LIGADO', 'giro-ligado': 'LIGADO',
    'mic-nativo-fora': '', 'mic-modo-aceso': 'nativo'}}});
  fora.livre = foto();
  // E a Mira APAGADA fora do Nativo, ao lado de um sensor apagado.
  window.__hef.pintar({colunas: {p1: {
    'mira-ligada': 'DESLIGADO', 'accel-ligado': 'DESLIGADO',
    'mic-modo-aceso': 'virtual'}}});
  fora.apagada = foto();
  return JSON.stringify(fora);
})()
"""


@pytest.fixture(scope="module")
def medido() -> dict:
    """Abre a bancada num WebKit offscreen, instala o BOOTSTRAP e pinta."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    roteiro = (ROTEIRO.replace("MIRA_NO_NATIVO_AQUI", MIRA_NO_NATIVO)
               .replace("RAZAO_AQUI", RAZAO_DE_ENSAIO))
    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    view = WebKit2.WebView()
    view.set_size_request(1280, 900)
    janela.add(view)
    janela.show_all()

    def guardou(v, res):
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:  # a exceção É a resposta desta ponte
            saiu.append(f"ERRO {e}")
        Gtk.main_quit()

    def instalou(v, res):
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(f"ERRO no bootstrap: {e}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(roteiro, -1, None, None, None, guardou)

    def carregou(v, evento):
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(_constante("BOOTSTRAP"), -1, None, None,
                                  None, instalou)

    view.connect("load-changed", carregou)
    view.load_uri(BANCADA.as_uri())
    guarda = GLib.timeout_add(20000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        # Um `timeout_add` pendente depois da fixture dispara DENTRO do laço do
        # PRÓXIMO teste de GUI do mesmo processo.
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu, "o WebKit não respondeu em 20 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    return json.loads(saiu[0])


def test_no_nativo_os_dois_avisam_o_leitor(medido: dict) -> None:
    """Cinza na tela é `aria-disabled="true"` no botão — os dois."""
    cinza = medido["cinza"]
    assert cinza["aria_mira"] == "true", (
        f"a Mira ficou cinza no Nativo e o leitor de tela não soube: "
        f"aria-disabled={cinza['aria_mira']!r}")
    assert cinza["aria_mic"] == "true", (
        f"o «Nativo» do microfone ficou cinza e o leitor de tela não soube: "
        f"aria-disabled={cinza['aria_mic']!r}")
    assert cinza["cara_mira"]["cursor"] == "not-allowed", cinza["cara_mira"]
    assert cinza["cara_nativo"]["cursor"] == "not-allowed", cinza["cara_nativo"]


def test_fora_do_nativo_os_dois_dizem_false(medido: dict) -> None:
    """`aria-disabled` ausente e `"false"` não são a mesma coisa para o ARIA."""
    livre = medido["livre"]
    assert livre["aria_mira"] == "false", livre["aria_mira"]
    assert livre["aria_mic"] == "false", livre["aria_mic"]
    assert livre["aria_virtual"] is None, (
        "o «Virtual» nunca fica cinza e não tem por que carregar o atributo")


def test_a_geometria_nao_mudou(medido: dict) -> None:
    """O invólucro não tem caixa: os três chips e os dois do microfone continuam
    dividindo a linha em partes iguais, na MESMA caixa nos quatro estados."""
    for estado in ("virgem", "cinza", "livre", "apagada"):
        foto = medido[estado]
        mira, giro, accel = foto["caixa_mira"], foto["caixa_giro"], foto["caixa_accel"]
        assert mira[2] > 0 and mira[3] > 0, f"{estado}: o chip da Mira sumiu {mira}"
        assert mira[1] == giro[1] == accel[1], (
            f"{estado}: o chip da Mira saiu da linha dos sensores: {mira} contra {giro}")
        assert mira[2] == accel[2] and mira[3] == accel[3], (
            f"{estado}: o chip da Mira mudou de tamanho — {mira} contra {accel}; o "
            f"invólucro virou caixa e saiu da grade de três")
        nat, vir = foto["caixa_nativo"], foto["caixa_virtual"]
        assert nat[1] == vir[1] and nat[2] == vir[2] and nat[3] == vir[3], (
            f"{estado}: o «Nativo» do microfone mudou de tamanho — {nat} contra {vir}")
    virgem = medido["virgem"]
    for estado in ("cinza", "livre", "apagada"):
        assert medido[estado]["caixa_mira"] == virgem["caixa_mira"], estado
    # O PAR DO MICROFONE ENCOLHE 9 PX NA PRIMEIRA PINTURA, e não é deste
    # invólucro: medido em 24/09/2026 com este mesmo roteiro na página
    # PUBLICADA, que ainda tem o botão sem invólucro — 144,1 px parado, 135,1
    # px pintado, os mesmos números daqui. Por isso o par se compara entre os
    # estados PINTADOS, e a igualdade com o «Virtual» acima é a outra régua.
    pintado = medido["cinza"]["caixa_nativo"]
    for estado in ("livre", "apagada"):
        assert medido[estado]["caixa_nativo"] == pintado, estado


def test_a_mira_apagada_tem_a_cara_do_sensor_apagado(medido: dict) -> None:
    """O `off` mora no invólucro, e a folha o leva ao botão: a Mira apagada é o
    MESMO cinza do Acelerômetro apagado, e a acesa é a mesma cara do aceso."""
    apagada = medido["apagada"]
    assert apagada["cara_mira"] == apagada["cara_accel"], (
        f"a Mira apagada não tem a cara do sensor apagado: "
        f"{apagada['cara_mira']} contra {apagada['cara_accel']}")
    livre = medido["livre"]
    assert livre["cara_mira"] == livre["cara_accel"], (
        f"a Mira acesa não tem a cara do sensor aceso: "
        f"{livre['cara_mira']} contra {livre['cara_accel']}")
    assert livre["cara_mira"] != apagada["cara_mira"], "aceso e apagado iguais"


def test_o_nativo_escolhido_tem_a_cara_do_virtual_escolhido(medido: dict) -> None:
    """O `on` do «Nativo» mora no invólucro: escolhido, ele tem a cara que o
    «Virtual» tem quando é ele o escolhido."""
    livre, apagada = medido["livre"], medido["apagada"]
    assert livre["cara_nativo"] == apagada["cara_virtual"], (
        f"o «Nativo» escolhido não tem a cara do escolhido: "
        f"{livre['cara_nativo']} contra {apagada['cara_virtual']}")
    assert livre["cara_nativo"] != apagada["cara_nativo"], (
        "o «Nativo» escolhido e o não escolhido estão iguais")
