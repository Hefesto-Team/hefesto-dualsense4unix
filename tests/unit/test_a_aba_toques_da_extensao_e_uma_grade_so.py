"""A aba «Toques» da extensão é uma grade só.

A-ABA-TOQUES-DA-EXTENSAO-E-UMA-GRADE-SO-01 (31/10/2026). Com o manifesto da Lovense 2.10.0, os
botões do ``por_botao`` e as entradas com glifo saíam em duas ``.tq-lista``: o «Inclinar», primeiro
no dado, caía na segunda grade. A onda da entrada só desenhava Nenhum, Direto e Suave, e a forma
gravada no «Ao vivo» não entrava na escolha de uma entrada. Agora a grade é uma só, na ordem do
manifesto, a onda sai das formas declaradas e a escolha dos efeitos aceita, lista e desenha a
forma gravada.

MORDIDAS (31/10/2026, executadas sobre a cura e devolvidas):

- o ``groupby`` das entradas com glifo de volta em ``_linhas_das_opcoes`` reprova
  ``test_uma_grade_so_com_o_inclinar_logo_depois_do_clique_do_touchpad``,
  ``test_a_grade_segue_a_ordem_do_manifesto_em_toda_extensao`` e a leitura do WebKit;
- o caminho pelas ``formas`` arrancado de ``_onda_da_entrada`` reprova
  ``test_o_duplo_numa_entrada_tem_a_onda_do_duplo`` e ``test_a_forma_gravada_vale_numa_entrada``;
- a ``escolha`` sem as ``formas_extras`` em ``opcoes.validar``, o ``escolhas_de`` sem as gravadas
  e o ``por_botao_dos_efeitos`` sem comparar as formas com as escolhas reprovam, cada um,
  ``test_a_forma_gravada_vale_numa_entrada``;
- o ``por_botao_dos_efeitos`` que exige as ``escolhas`` iguais às ``formas``, e não contidas
  reprova ``test_a_entrada_com_parte_dos_efeitos_dos_botoes_desenha_e_aceita_a_gravada``: o
  ``por_botao`` com uma forma a mais que as entradas tirava das entradas a onda e a forma gravada;
- o ``esquecer_a_forma_do_livre`` sem devolver ao padrão a entrada que usava a forma reprova
  ``test_a_forma_gravada_vale_numa_entrada``: o ``opcoes.json`` guardava a forma esquecida.
"""

from __future__ import annotations

import json
import re
from typing import Any

from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    ctx,
    lar,
)
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (  # noqa: F401
    VIVO,
    _Ponte,
    janela,
)
from tests.unit.test_a_linha_sem_aparelho_fica_a_direita_do_parear import (  # noqa: F401
    no_webkit,
    pagina_fresca,
)
from tests.unit.test_a_lista_da_janela_configurar_nao_pula_ao_clicar_um_efeito import (
    ENDERECO,
    MOD,
    VISTAS,
    pecas_da_lovense,
)

EFEITOS = ["Nenhum", "Curto", "Toque", "Duplo", "Triplo", "Longo", "Onda", "Subida", "Pulso",
           "Direto", "Suave"]
FORMAS = {"Nenhum": [], "Curto": [[0.6, 0.12]], "Toque": [[1.0, 0.2]],
          "Duplo": [[1.0, 0.12], [0.0, 0.1], [1.0, 0.12]],
          "Triplo": [[1.0, 0.1], [0.0, 0.08], [1.0, 0.1], [0.0, 0.08], [1.0, 0.1]],
          "Longo": [[1.0, 0.7]],
          "Onda": [[0.3, 0.12], [0.6, 0.12], [1.0, 0.16], [0.6, 0.12], [0.3, 0.12]],
          "Subida": [[0.25, 0.12], [0.5, 0.12], [0.75, 0.12], [1.0, 0.2]],
          "Pulso": [[1.0, 0.07], [0.0, 0.06], [0.7, 0.07], [0.0, 0.06], [0.4, 0.07]],
          "Direto": [[1.0, 1.0]], "Suave": [[1.0, 1.0]]}
BOTOES = ["cross", "circle", "square", "triangle", "l1", "r1", "l3", "r3", "dpad_up", "dpad_down",
          "dpad_left", "dpad_right", "options", "create", "touchpad_left_press",
          "touchpad_middle_press", "touchpad_right_press"]
PADRAO_DOS_BOTOES = {"cross": "Toque", "circle": "Duplo", "square": "Pulso", "triangle": "Onda",
                     "l1": "Curto", "r1": "Curto", "l3": "Triplo", "r3": "Triplo",
                     "dpad_up": "Curto", "dpad_down": "Curto", "dpad_left": "Curto",
                     "dpad_right": "Curto", "options": "Nenhum", "create": "Nenhum",
                     "touchpad_left_press": "Toque", "touchpad_middle_press": "Duplo",
                     "touchpad_right_press": "Toque"}
ENTRADAS = [("entrada_inclinar", "Inclinar"), ("entrada_l2", "Gatilho esquerdo (L2)"),
            ("entrada_r2", "Gatilho direito (R2)"),
            ("entrada_analogico_esquerdo", "Analógico esquerdo"),
            ("entrada_analogico_direito", "Analógico direito"), ("entrada_touchpad", "Touchpad"),
            ("entrada_sacudir", "Sacudir")]
OPCOES_2_10_0 = [
    {"id": "ligada", "rotulo": "Ligada", "tipo": "ligado",
     "padrao": True},  # (noqa-acento)
    {"id": "toques", "rotulo": "Toques", "tipo": "ligado", "grupo": "Toques",
     "padrao": True},  # (noqa-acento)
    {"id": "toques_dos_botoes", "rotulo": "Botões", "tipo": "por_botao", "formas": FORMAS,
     "botoes": BOTOES, "grupo": "Toques",
     "padrao": PADRAO_DOS_BOTOES},  # (noqa-acento)
    *({"id": i, "rotulo": r, "tipo": "escolha", "escolhas": EFEITOS, "grupo": "Toques",
       "padrao": "Nenhum"} for i, r in ENTRADAS),  # (noqa-acento)
    {"id": "forca_dos_toques", "rotulo": "Força", "tipo": "deslizante", "passo": 1,
     "minimo": 0, "maximo": 100,  # (noqa-acento)
     "padrao": 60, "grupo": "Toques", "degraus": 20},  # (noqa-acento)
    {"id": "servidor_do_brinquedo", "rotulo": "Brinquedos por", "tipo": "escolha",
     "escolhas": ["Adaptador USB", "Bluetooth do computador", "Intiface Central"],
     "padrao": "Adaptador USB", "grupo": "Ligação"},  # (noqa-acento)
    {"id": "ao_vivo", "rotulo": "Ao vivo", "tipo": "livre", "modos": True},
]
GRAVADA = "Meu 1"
PASSOS_GRAVADOS = [[0.3, 0.1], [0.9, 0.2], [0.5, 0.1]]


def _instalar(janela: Any, opcoes: list[dict[str, Any]] = OPCOES_2_10_0  # noqa: F811
              ) -> tuple[Any, _Ponte, str]:
    a07, instalar, abrir = janela
    pecas = {**pecas_da_lovense(), "chave": "ligada",
             "opcoes": opcoes}  # (noqa-acento)
    instalar(mod_id=MOD, **pecas)
    a07._MEXIDA.limpar()
    ponte = _Ponte(VIVO)
    return a07, ponte, str(abrir(ponte, mod_id=MOD)["blocos"]["#mod-janela"])


def _tela_dos_toques(html: str) -> str:
    nomes = re.findall(r'<label for="mj-aba-\d+">([^<]*)', html)
    corpos = re.split(r'<div class="mj-tela" id="mod-tela-\d+">', html)[1:]
    return dict(zip(nomes, corpos, strict=True))["Toques"]


def _escolher(a07: Any, ctx: Any, ponte: _Ponte, opcao: str, valor: str) -> str:  # noqa: F811
    o = {"v": f"{MOD}:{opcao}", "evento": "change", "valor": valor}
    resposta = dict(a07.guardar_opcao_da_modificacao(ctx, o, ponte) or {})
    return exp.janela_pintada(resposta["blocos"])


def _linha(html: str, opcao: str) -> str:
    achado = re.search(rf'<div class="tql" id="mod-op-{opcao}".*?</select></div>', html, re.S)
    assert achado is not None, f"a linha de {opcao} não está na janela"
    return achado.group(0)


def _onda(linha: str) -> str:
    achado = re.search(r'<svg class="onda".*?</svg>', linha, re.S)
    assert achado is not None, linha[:200]
    return achado.group(0)


def test_uma_grade_so_com_o_inclinar_logo_depois_do_clique_do_touchpad(
        janela: Any) -> None:  # noqa: F811
    _a07, _ponte, html = _instalar(janela)
    tela = _tela_dos_toques(html)
    assert tela.count('class="tq-lista"') == 1, "os botões e as entradas em mais de uma grade"
    grade = tela.split('class="tq-lista"', 1)[1]
    ordem = re.findall(r'<div class="tql" id="mod-op-([^"]+)"', grade)
    esperada = [f"toques_dos_botoes-{b}" for b in BOTOES] + [i for i, _r in ENTRADAS]
    assert ordem == esperada, ordem
    assert ordem[ordem.index("toques_dos_botoes-touchpad_right_press") + 1] == "entrada_inclinar"


def test_a_grade_segue_a_ordem_do_manifesto_em_toda_extensao() -> None:
    entradas = [exp.OpcaoDaJanela("outra", i, r, "escolha", "Nenhum", ("Nenhum",), "Toques")
                for i, r in ENTRADAS[:2]]
    botoes = exp.OpcaoDaJanela("outra", "b", "Botões", "por_botao", {}, (), "Toques",
                               formas=(("Nenhum", ()),), botoes=("cross", "circle"))
    html = exp._linhas_das_opcoes([entradas[0], botoes, entradas[1]])
    assert html.count('class="tq-lista"') == 1
    assert re.findall(r'<div class="tql" id="mod-op-([^"]+)"', html) == [
        "entrada_inclinar", "b-cross", "b-circle", "entrada_l2"]
    assert html.count('id="mod-op-b"') == 1


def test_o_duplo_numa_entrada_tem_a_onda_do_duplo(janela: Any, ctx: Any) -> None:  # noqa: F811
    a07, ponte, _html = _instalar(janela)
    duplo = exp._onda_da_forma([tuple(p) for p in FORMAS["Duplo"]])
    assert duplo.count("<rect") == 2
    for opcao, _rotulo in ENTRADAS:
        linha = _linha(_escolher(a07, ctx, ponte, opcao, "Duplo"), opcao)
        assert _onda(linha) == duplo, opcao
        assert "<option selected>Duplo</option>" in linha


def test_a_forma_gravada_vale_numa_entrada(janela: Any, ctx: Any, lar: Any) -> None:  # noqa: F811
    from hefesto_dualsense4unix.mods import opcoes
    from hefesto_dualsense4unix.mods.instalador import manifesto_instalado

    a07, ponte, _html = _instalar(janela)
    manifesto = manifesto_instalado(MOD, lugares=lar)
    assert manifesto is not None
    opcoes.guardar(manifesto, "ao_vivo", {GRAVADA: PASSOS_GRAVADOS}, lar)
    html = _escolher(a07, ctx, ponte, "entrada_inclinar", GRAVADA)
    assert opcoes.ler(manifesto, lar)["entrada_inclinar"] == GRAVADA
    linha = _linha(html, "entrada_inclinar")
    assert f"<option selected>{GRAVADA}</option>" in linha
    assert _onda(linha) == exp._onda_da_forma([tuple(p) for p in PASSOS_GRAVADOS])
    for opcao, _rotulo in ENTRADAS[1:]:
        assert f"<option>{GRAVADA}</option>" in _linha(html, opcao), opcao
    assert GRAVADA not in re.search(r'data-v="intiface:servidor_do_brinquedo".*?</select>',
                                    html, re.S).group(0)
    try:
        opcoes.guardar(manifesto, "servidor_do_brinquedo", GRAVADA, lar)
    except Exception as recusa:
        assert "não é uma das escolhas" in str(recusa)
    else:
        raise AssertionError("a escolha que não é de efeitos aceitou a forma gravada")
    a07.esquecer_a_forma_do_livre(
        ctx, {"v": f"{MOD}:ao_vivo:{GRAVADA}", "evento": "click"}, ponte)
    assert opcoes.ler(manifesto, lar)["entrada_inclinar"] == "Nenhum"
    gravado = json.loads(opcoes.caminho(MOD, lar).read_text(encoding="utf-8"))
    assert gravado["entrada_inclinar"] == "Nenhum", "a forma esquecida ficou no arquivo"


def test_a_entrada_com_parte_dos_efeitos_dos_botoes_desenha_e_aceita_a_gravada(
        janela: Any, ctx: Any, lar: Any) -> None:  # noqa: F811
    from hefesto_dualsense4unix.mods import opcoes
    from hefesto_dualsense4unix.mods.instalador import manifesto_instalado

    mais = [{**o, "formas": {**FORMAS, "Rajada": [[1.0, 0.05], [0.0, 0.05]]}}
            if o["tipo"] == "por_botao" else o for o in OPCOES_2_10_0]
    a07, ponte, _html = _instalar(janela, mais)
    manifesto = manifesto_instalado(MOD, lugares=lar)
    assert manifesto is not None
    linha = _linha(_escolher(a07, ctx, ponte, "entrada_l2", "Duplo"), "entrada_l2")
    assert _onda(linha) == exp._onda_da_forma([tuple(p) for p in FORMAS["Duplo"]])
    assert "<option>Rajada</option>" not in linha
    opcoes.guardar(manifesto, "ao_vivo", {GRAVADA: PASSOS_GRAVADOS}, lar)
    html = _escolher(a07, ctx, ponte, "entrada_sacudir", GRAVADA)
    assert opcoes.ler(manifesto, lar)["entrada_sacudir"] == GRAVADA
    assert _onda(_linha(html, "entrada_sacudir")) == exp._onda_da_forma(
        [tuple(p) for p in PASSOS_GRAVADOS])


_ABRIR = """(function(endereco, h){
  location.hash = endereco;
  window.__hef.pintar({blocos: {'#mod-janela': h}});
  const j = document.getElementById('mod-janela');
  const rot = [...j.querySelectorAll('.mj-abas > label')].find(l => l.textContent === 'Toques');
  if (!rot) return 'sem a aba';
  rot.click();
  return 'ok';
})(%s, %s)"""
_LER = """(function(){
  const j = document.getElementById('mod-janela');
  const r = id => { const e = document.getElementById(id); if (!e) return null;
    const x = e.getBoundingClientRect(); return {x: x.left, y: x.top, d: x.right, b: x.bottom}; };
  const listas = [...j.querySelectorAll('.mj-tela .tq-lista')].filter(l => l.offsetParent);
  return JSON.stringify({listas: listas.length,
    clique: r('mod-op-toques_dos_botoes-touchpad_right_press'),
    inclinar: r('mod-op-entrada_inclinar')});
})()"""


def test_no_webkit_o_inclinar_fica_a_direita_do_clique_do_touchpad(
        janela: Any, pagina_fresca: Any) -> None:  # noqa: F811
    from hefesto_dualsense4unix.interface import hefesto_vivo

    _a07, _ponte, html = _instalar(janela)
    passos = [["js", hefesto_vivo.BOOTSTRAP], ["js", _ABRIR % (json.dumps(ENDERECO),
                                                                json.dumps(html))],
              ["espera", 0.3], ["js", _LER]]
    lidos = no_webkit(pagina_fresca, {f"{w}x{h}": (w, h, passos) for w, h in VISTAS})
    for caso, r in lidos.items():
        assert r[1] == "ok", (caso, r[1])
        lido = json.loads(r[2])
        clique, inclinar = lido["clique"], lido["inclinar"]
        assert lido["listas"] == 1, (caso, lido)
        assert abs(clique["y"] - inclinar["y"]) < 1, (caso, lido)
        assert 0 <= inclinar["x"] - clique["d"] < 40, (caso, lido)
