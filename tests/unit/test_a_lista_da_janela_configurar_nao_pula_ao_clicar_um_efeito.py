"""A lista da janela «Configurar» não pula ao clicar um efeito.

A-LISTA-DA-JANELA-CONFIGURAR-NAO-PULA-AO-CLICAR-UM-EFEITO-01 (26/10/2026).
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
from typing import Any

import pytest

from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    ctx,
    lar,
)
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (  # noqa: F401
    VIVO,
    _Ponte,
    janela,
)

MOD = "intiface"
BOTOES = ["cross", "circle", "square", "triangle", "l1", "r1", "l3", "r3", "dpad_up",
          "dpad_down", "dpad_left", "dpad_right", "options", "create", "touchpad_left_press",
          "touchpad_middle_press", "touchpad_right_press"]
FORMAS = {"Nenhum": [], "Curto": [[0.6, 0.12]], "Toque": [[1.0, 0.2]],
          "Duplo": [[1.0, 0.12], [0.0, 0.1], [1.0, 0.12]]}
ENTRADAS = [("entrada_l2", "Gatilho esquerdo (L2)"), ("entrada_r2", "Gatilho direito (R2)"),
            ("entrada_analogico_esquerdo", "Analógico esquerdo"),
            ("entrada_analogico_direito", "Analógico direito"), ("entrada_touchpad", "Touchpad"),
            ("entrada_sacudir", "Sacudir"), ("entrada_inclinar", "Inclinar")]


def _deslizante(id_: str, rotulo: str, grupo: str) -> dict[str, Any]:
    return {"id": id_, "rotulo": rotulo, "tipo": "deslizante",
            "minimo": 0, "maximo": 100,  # (noqa-acento)
            "passo": 5, "padrao": 50, "grupo": grupo}  # (noqa-acento)


def _chave(id_: str, rotulo: str, grupo: str) -> dict[str, Any]:
    return {"id": id_, "rotulo": rotulo, "tipo": "ligado",
            "padrao": True, "grupo": grupo}  # (noqa-acento)


def pecas_da_lovense() -> dict[str, Any]:
    """A forma do manifesto da Lovense: três grupos de opções, as ações, os aparelhos e o livre."""
    escolha = {"tipo": "escolha", "escolhas": ["Nenhum", "Direto", "Suave"],
               "padrao": "Nenhum", "grupo": "Toques"}  # (noqa-acento)
    por_botao = {"id": "toques_dos_botoes", "rotulo": "Botões", "tipo": "por_botao",
                 "formas": FORMAS, "botoes": BOTOES, "grupo": "Toques",
                 "padrao": {b: "Toque" for b in BOTOES}}  # (noqa-acento)
    lista = [
        _chave("toques", "Toques", "Toques"),
        por_botao,
        *({"id": i, "rotulo": r, **escolha} for i, r in ENTRADAS),
        _deslizante("forca_dos_toques", "Força (%)", "Toques"),
        _deslizante("cena_do_jogo", "Cena do jogo (%)", "Força"),
        _deslizante("teto", "Teto (%)", "Força"),
        _chave("vibrar_os_controles", "Vibrar os controles", "Força"),
        _chave("usar_o_intiface", "Brinquedo", "Ligação"),
        _chave("usar_o_telefone", "Telefone", "Ligação"),
        _chave("porta_20010", "Game Mode · 20010", "Ligação"),
        _chave("servidor_buttplug", "DualSense como brinquedo", "Ligação"),
        {"id": "ao_vivo", "rotulo": "Ao vivo", "tipo": "livre", "modos": True},
    ]
    parear = {"id": "parear", "rotulo": "Parear", "grupo": "Brinquedos", "icone": "procurar"}
    nos_aparelhos = [{"id": "ligar", "rotulo": "Ligado", "icone": "ligar"},
                     {"id": "testar", "rotulo": "Testar", "icone": "testar"}]
    return {"opcoes": lista, "parar_tudo": True,  # (noqa-acento)
            "agora": ["conexoes", "aparelhos"],  # (noqa-acento)
            "acoes": [parear],  # (noqa-acento)
            "aparelhos_acoes": {"grupo": "Brinquedos",
                                "acoes": nos_aparelhos},  # (noqa-acento)
            "aparelhos_controles": {"grupo": "Luz"}}


CLIQUES = {
    "efeito": ("guardar_opcao_da_modificacao", "toques_dos_botoes:circle", "Duplo", "Toques",
               "j.querySelector('[data-v=\"intiface:toques_dos_botoes:circle\"]').value"),
    "entrada": ("guardar_opcao_da_modificacao", "entrada_r2", "Suave", "Toques",
                "j.querySelector('[data-v=\"intiface:entrada_r2\"]').value"),
    "forca": ("guardar_opcao_da_modificacao", "forca_dos_toques", "65", "Toques",
              "j.querySelector('[data-v=\"intiface:forca_dos_toques\"]').value"),
    "chave": ("guardar_opcao_da_modificacao", "servidor_buttplug", None, "Ligação",
              "j.querySelector('[data-v=\"intiface:servidor_buttplug\"]').textContent"),
    "modo": ("modo_do_livre_da_modificacao", "ao_vivo:repetir", None, "Toques",
             "j.querySelector('.mj-modos .on').dataset.modo"),
}
MOSTRA = {"efeito": "Duplo", "entrada": "Suave", "forca": "65", "chave": "Desligado",
          "modo": "repetir"}
VISTAS = ((1918, 840), (1212, 809))
RAIZ = pathlib.Path(__file__).resolve().parents[2]

@pytest.fixture(scope="session")
def pagina_fresca(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    """O desenho da 07 gerado agora, do CSS e do Python desta árvore, numa pasta de prova: a
    régua mede o que o gerador faz hoje, e a ``mockup/`` (que a costura regera) não entra."""
    pasta = tmp_path_factory.mktemp("bancada-07")
    for vizinha in (RAIZ / "mockup").glob("*.html"):
        shutil.copy2(vizinha, pasta / vizinha.name)
    ambiente = dict(os.environ, HEFESTO_BANCADA=str(pasta), PYTHONDONTWRITEBYTECODE="1",
                    PYTHONPATH=os.pathsep.join(filter(None, [str(RAIZ / "src"),
                                                             os.environ.get("PYTHONPATH", "")])))
    gerou = subprocess.run([sys.executable, "-m", "hefesto_dualsense4unix.interface.aba07"],
                           cwd=RAIZ, env=ambiente, capture_output=True, text=True, timeout=300)
    assert gerou.returncode == 0, gerou.stdout[-300:] + gerou.stderr[-300:]
    return pasta / "07-lancadores.html"


_ABRIR = """(function(endereco, h, aba){
  location.hash = endereco;
  window.__hef.pintar({blocos: {'#mod-janela': h}});
  const j = document.getElementById('mod-janela');
  const rot = [...j.querySelectorAll('.mj-abas > label')].find(l => l.textContent === aba);
  if (!rot) return 'sem a aba ' + aba;
  rot.click();
  const lista = rot.nextElementSibling;
  lista.scrollTop = lista.scrollHeight;
  return 'ok';
})(%s, %s, %s)"""
ENDERECO = "#modificacao"  # (noqa-acento)
ENDERECO = "#modificacao"  # (noqa-acento)
_PINTAR = "(function(b){ window.__hef.pintar({blocos: b}); return 'ok'; })(%s)"
_LER = """(function(){
  const j = document.getElementById('mod-janela');
  const marcada = j.querySelector('.mj-abas > input:checked');
  const lista = marcada.nextElementSibling.nextElementSibling;
  return JSON.stringify({topo: lista.scrollTop, altura: lista.scrollHeight,
    vista: lista.clientHeight, janela: j.getBoundingClientRect().height,
    aba: marcada ? marcada.nextElementSibling.textContent : null,
    mesma: lista === window.__lista, mostra: String(%s).trim()});
})()"""
_GUARDAR = "(function(){ window.__lista = document.querySelector(" \
           "'#mod-janela .mj-abas > input:checked + label + .mj-tela'); return 'ok'; })()"


Medida = tuple[str, str, dict[str, str], dict[str, str]]


def _da_janela(blocos: dict[str, Any]) -> dict[str, str]:
    return {k: str(v) for k, v in blocos.items() if k.startswith("#mod-")}


@pytest.fixture
def cliques(janela: Any, ctx: Any) -> dict[str, Medida]:  # noqa: F811
    """A janela montada e, para cada clique, os blocos da janela que o gesto e o tique mandam."""
    a07, instalar, abrir = janela
    instalar(mod_id=MOD, **pecas_da_lovense())
    ponte = _Ponte(VIVO)
    montada = str(abrir(ponte, mod_id=MOD)["blocos"]["#mod-janela"])
    saida = {}
    for nome, (gesto, v, valor, aba, _ler) in CLIQUES.items():
        o = {"v": f"{MOD}:{v}", "evento": "click" if valor is None else "change", "valor": valor}
        resposta = dict(getattr(a07, gesto)(ctx, o, ponte) or {})
        a07.REGISTRO.esquecer()
        tique = dict(a07.pacote(ctx))
        saida[nome] = (montada, aba, _da_janela(resposta.get("blocos", {})),
                       _da_janela(tique["blocos"]))
    return saida


def _medir(cliques: dict[str, Medida], pagina: pathlib.Path) -> dict[str, list[Any]]:
    from hefesto_dualsense4unix.interface import hefesto_vivo
    from tests.unit.test_a_linha_sem_aparelho_fica_a_direita_do_parear import no_webkit

    casos = {}
    for nome, (montada, aba, resposta, tique) in cliques.items():
        ler = _LER % CLIQUES[nome][4]
        for w, h in VISTAS:
            casos[f"{nome}@{w}x{h}"] = (w, h, [
                ["js", hefesto_vivo.BOOTSTRAP],
                ["js", _ABRIR % (json.dumps(ENDERECO), json.dumps(montada), json.dumps(aba))],
                ["espera", 0.3],
                ["js", _GUARDAR], ["js", ler],
                ["js", _PINTAR % json.dumps(resposta)], ["espera", 0.3], ["js", ler],
                ["js", _PINTAR % json.dumps(tique)], ["espera", 0.3], ["js", ler]])
    return no_webkit(pagina, casos)


def test_o_clique_na_lista_nao_mexe_na_rolagem_nem_na_aba(
        cliques: dict[str, Medida], pagina_fresca: pathlib.Path) -> None:
    """A aba que rola vai ao fim antes do clique, e a que cabe (a regra sem rolagem) segue cabendo.

    Nos dois casos, o gesto e o tique não mexem na rolagem, na aba nem na janela.
    """
    medidas = _medir(cliques, pagina_fresca)
    falhas = []
    for caso, lidos in medidas.items():
        _, abriu, _, antes, _, depois, _, tique = lidos
        assert abriu == "ok", (caso, abriu)
        antes, depois, tique = json.loads(antes), json.loads(depois), json.loads(tique)
        if antes["altura"] > antes["vista"]:
            assert antes["topo"] > 0, f"{caso}: a lista não rolou antes do clique: {antes}"
        mostra = MOSTRA[caso.partition("@")[0]]
        for quando, lido in (("no gesto", depois), ("no tique", tique)):
            for chave in ("topo", "altura", "aba", "janela"):
                if lido[chave] != antes[chave]:
                    falhas.append(f"{caso} {quando}: {chave} {antes[chave]} -> {lido[chave]}")
            if lido["mostra"] != mostra:
                falhas.append(f"{caso} {quando}: a tela mostra {lido['mostra']!r}, não {mostra!r}")
    print(json.dumps(medidas, ensure_ascii=False))
    assert not falhas, "\n".join(falhas)


def test_a_tela_segue_a_janela_do_servidor_a_cada_clique_mesmo_o_que_volta(
        janela: Any, ctx: Any) -> None:  # noqa: F811
    """A chave virada e desvirada, o efeito trocado e devolvido: a tela é a janela do servidor."""
    from hefesto_dualsense4unix.interface import desenho_da_experimental as exp

    a07, instalar, abrir = janela
    instalar(mod_id=MOD, **pecas_da_lovense())
    ponte = _Ponte(VIVO)
    aberta = abrir(ponte, mod_id=MOD)["blocos"]["#mod-janela"]
    passos = [("servidor_buttplug", None), ("servidor_buttplug", None),
              ("toques_dos_botoes:circle", "Duplo"), ("toques_dos_botoes:circle", "Toque"),
              ("entrada_l2", "Direto")]
    for v, valor in passos:
        o = {"v": f"{MOD}:{v}", "evento": "click" if valor is None else "change", "valor": valor}
        blocos = a07.guardar_opcao_da_modificacao(ctx, o, ponte)["blocos"]
        tela = exp.janela_pintada(blocos)
        assert exp._sem_o_que_a_pessoa_muda(tela) == exp._sem_o_que_a_pessoa_muda(
            a07._MEXIDA.html_mod), f"depois de {v}={valor}, a tela não é a janela do servidor"
        assert blocos["#mod-janela"] == aberta, f"{v}={valor} repintou a janela inteira"
