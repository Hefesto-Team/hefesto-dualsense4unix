"""O estado do aparelho se vê igual em toda a janela da extensão.

O-ESTADO-DO-APARELHO-SE-VE-IGUAL-EM-TODA-A-JANELA-DA-EXTENSAO-01 (26/10/2026). Um dono só diz se o
aparelho está ativo (``como_esta``: o ``estado`` ligado e a chave não desligada), e a linha do
«Agora», o cartão, o cartão dos controles e o chip do «Ao vivo» o leem: desligado, os quatro se
apagam juntos. A chave de um controle desenha o glifo do ``icone`` (a luz, ``lampada``), o que a
separa da chave «Ligado». A aba dos controles nasce do manifesto, com a linha vazia sem aparelho,
e o «Ao vivo» sem aparelho ativo fica apagado, com a dica, e não manda nada à porta.

MORDIDAS (26/10/2026, executadas sobre a cura e devolvidas):

- o ``ligado`` ignorado na linha do «Agora» reprova os dois testes dos quatro lugares;
- a aba nascida do estado (``com_controles``) reprova a das abas iguais;
- o glifo arrancado reprova o da chave da luz e a leitura do WebKit;
- o guarda do ``mover`` arrancado reprova os dois casos do «Ao vivo» sem aparelho;
- o chip sem o ``.mj-alvo.fora`` no CSS e o tique sem a ``gestao`` na dica reprovam o WebKit;
- o guarda do «Gravar» arrancado reprova os dois casos do «Ao vivo» sem aparelho, e o apagado
  dele arrancado do CSS reprova o WebKit;
- o glifo da luz diferente da ``i-lampada`` do desenho do rádio reprova o do glifo da casa.
"""

from __future__ import annotations

import copy
import json
import pathlib
import re
from typing import Any

import pytest

from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    ctx,
    lar,
)
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (  # noqa: F401
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

LUZ = {"id": "acesa", "tipo": "chave", "valor": True, "rotulo": "Acesa", "icone": "lampada"}


def _aparelho(n: int, ligado: bool = True) -> dict[str, Any]:
    return {"id": f"g{n}", "nome": f"Aparelho {n}", "estado": "ligado", "ligado": ligado,
            "bateria": 60, "forca": 0.4, "controles": [copy.deepcopy(LUZ)]}


def _estado(*aparelhos: dict[str, Any], serie: int = 1) -> dict[str, Any]:
    return {"ligado": True, "nivel": 3, "aparelhos": list(aparelhos), "serie": serie}


def _abrir(janela: Any, ctx: Any, lar: Any,  # noqa: F811
           estado: dict[str, Any]) -> tuple[Any, _Ponte, str]:
    """A janela da forma da Lovense aberta com a extensão rodando (na porta)."""
    a07, instalar, abrir = janela
    instalar(mod_id=MOD, **pecas_da_lovense())
    if a07.ligar_modificacao(ctx, {"v": MOD}, None).get("armou"):
        a07.ligar_modificacao(ctx, {"v": MOD}, None)
    lar.estado.parent.mkdir(parents=True, exist_ok=True)
    lar.estado.write_text(json.dumps({"mods": {MOD: {"estado": "rodando", "motivo": ""}}}),
                          encoding="utf-8")
    a07.REGISTRO.esquecer()
    a07.VIGIA.esquecer()
    a07._MEXIDA.limpar()
    ponte = _Ponte(estado)
    return a07, ponte, str(abrir(ponte, mod_id=MOD)["blocos"]["#mod-janela"])


def _tique(a07: Any, ponte: _Ponte, estado: dict[str, Any]) -> dict[str, str]:
    ponte.estado = estado
    a07._AGORA.ler(MOD, ponte)
    carga = a07._com_as_extensoes({"mesa": {}, "blocos": {}}, [])
    blocos = {k: str(v) for k, v in carga["blocos"].items()
              if k.startswith("#mod-") and k != "#mod-janela"}
    blocos["mesa"] = json.dumps(carga["mesa"])
    return blocos


def _apagados(html: str) -> dict[str, bool]:
    """O aparelho 2 em cada lugar da janela: ``True`` se apagado."""
    linha = re.search(r'<div class="ap( fora)?">(?:(?!<div class="ap).)*?>Aparelho 2<', html, re.S)
    cartao = re.search(r'<div class="mj-ap( fora)?" data-alvo="g2">', html)
    controles = re.search(r'<div class="mj-ap mj-cc( fora)?" data-alvo="g2">', html)
    chip = re.search(r'<span class="chip mj-alvo( on| fora)[^"]*"[^>]*:g2"', html)
    assert linha and cartao and controles and chip, "o aparelho 2 faltou num dos quatro lugares"
    return {"agora": bool(linha.group(1)), "cartao": bool(cartao.group(1)),
            "controles": bool(controles.group(1)), "chip": chip.group(1) == " fora"}


def test_desligar_apaga_os_quatro_lugares_juntos_e_religar_acende(
        janela: Any, ctx: Any, lar: Any) -> None:  # noqa: F811
    a07, ponte, html = _abrir(janela, ctx, lar, _estado(_aparelho(1), _aparelho(2)))
    assert set(_apagados(html).values()) == {False}, _apagados(html)
    desligado = _tique(a07, ponte, _estado(_aparelho(1), _aparelho(2, False), serie=2))
    assert set(_apagados("".join(desligado.values())).values()) == {True}
    caido = _tique(a07, ponte, _estado(_aparelho(1), {**_aparelho(2), "estado": "falhou"},
                                       serie=3))
    assert set(_apagados("".join(caido.values())).values()) == {True}, "o estado caído não apaga"
    religado = _tique(a07, ponte, _estado(_aparelho(1), _aparelho(2), serie=4))
    assert set(_apagados("".join(religado.values())).values()) == {False}


def test_a_chave_da_luz_tem_o_glifo_e_a_chave_ligado_nao(
        janela: Any, ctx: Any, lar: Any) -> None:  # noqa: F811
    _a07, _ponte, html = _abrir(janela, ctx, lar, _estado(_aparelho(1), _aparelho(2)))
    luz = re.findall(r'<span class="mj-cc-chave"><svg class="mj-cc-gl"[^>]*>(.*?)</svg>'
                     r'<span class="mj-chave[^"]*" role="switch"[^>]*data-v="intiface:acesa:g\d"',
                     html)
    assert len(luz) == 2 and all("M9 18h6" in g for g in luz), "a chave da luz sem o glifo"
    cartao = re.search(r'<div class="mj-ap" data-alvo="g1">.*?</div></div>', html, re.S)
    assert cartao and "mj-cc-gl" not in cartao.group(0), "a chave «Ligado» ganhou o glifo"
    sem_icone = {k: v for k, v in LUZ.items() if k != "icone"}
    so_rotulo = _estado({**_aparelho(1), "controles": [sem_icone]})
    _a07, _ponte, escrito = _abrir(janela, ctx, lar, so_rotulo)
    assert '<span class="mj-cc-chave"><span class="mj-cc-marca">Acesa</span>' in escrito


def test_a_porta_guarda_o_icone_do_conjunto_e_recusa_o_de_fora() -> None:
    from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
    from hefesto_dualsense4unix.mods.porta import (
        ICONES_DO_CONTROLE,
        RecusaError,
        estado_dos_acessorios,
    )

    assert set(ICONES_DO_CONTROLE) == set(exp.GLIFO_DO_CONTROLE), "glifo sem ícone ou o contrário"
    certo = estado_dos_acessorios(MOD, _estado(_aparelho(1)))
    assert certo["aparelhos"][0]["controles"][0]["icone"] == "lampada"
    torto = _aparelho(1)
    torto["controles"][0]["icone"] = "sol"
    with pytest.raises(RecusaError, match="o ícone de um controle é um de lampada"):
        estado_dos_acessorios(MOD, _estado(torto))


def test_o_glifo_da_luz_e_a_lampada_do_desenho_do_radio() -> None:
    from hefesto_dualsense4unix.interface import desenho_da_experimental as exp

    desenho = (pathlib.Path(__file__).resolve().parents[2] / "mockup" / "mapa-do-radio.html")
    casa = re.search(r'<symbol id="i-lampada"[^>]*>(.*?)</symbol>',
                     desenho.read_text(encoding="utf-8"), re.S)
    assert casa, "o desenho do rádio perdeu a i-lampada"
    assert exp.GLIFO_DO_CONTROLE["lampada"] == casa.group(1).strip()


def _abas(html: str) -> list[str]:
    return re.findall(r'<label for="mj-aba-\d+">([^<]*)', html)


def test_as_abas_sao_as_mesmas_com_zero_um_e_dois_aparelhos(
        janela: Any, ctx: Any, lar: Any) -> None:  # noqa: F811
    abas = [_abas(_abrir(janela, ctx, lar, _estado(*(_aparelho(n) for n in range(1, k + 1))))[2])
            for k in range(3)]
    assert abas[0] == abas[1] == abas[2] and "Luz" in abas[0], abas
    a07, ponte, vazia = _abrir(janela, ctx, lar, _estado())
    assert 'id="mod-controles"><div class="mj-cc-vazio">' in vazia
    chegou = _tique(a07, ponte, _estado(_aparelho(1), serie=2))
    assert 'data-alvo="g1"' in chegou["#mod-controles"]
    assert a07._MEXIDA.html_mod == vazia, "o tique refez a janela"


@pytest.mark.parametrize("estado", [_estado(), _estado(_aparelho(1, False))],
                         ids=["sem-aparelho", "todos-desligados"])
def test_sem_aparelho_ativo_o_ao_vivo_nao_chega_a_porta(
        janela: Any, ctx: Any, lar: Any, estado: dict[str, Any]) -> None:  # noqa: F811
    from hefesto_dualsense4unix.interface import desenho_da_experimental as exp

    a07, ponte, html = _abrir(janela, ctx, lar, estado)
    assert f'class="mj-trilho fora" data-dica="{exp.DICA_DA_BARRA_SEM_ALVO}"' in html
    o = {"v": f"{MOD}:ao_vivo", "valor": "60", "vivo": "1", "carimbo": "1", "evento": "input"}
    assert a07.mover_o_livre_da_modificacao(ctx, o, ponte) == {}
    with pytest.raises(RuntimeError, match="Nenhum aparelho ligado"):
        a07.soltar_o_livre_da_modificacao(ctx, {**o, "evento": "change"}, ponte)
    with pytest.raises(RuntimeError, match="Nada foi gravado"):
        a07.gravar_o_livre_da_modificacao(ctx, {"v": f"{MOD}:ao_vivo"}, ponte)
    assert not a07._VIVA.ao_vivo(MOD).gravando, "o «Gravar» começou sem aparelho"
    assert not [m for m, _ in ponte.chamadas if m == "mods.livre"], ponte.chamadas
    chegou = _tique(a07, ponte, _estado(_aparelho(1), serie=2))
    assert json.loads(chegou["mesa"])[exp.CAMPO_DA_BARRA_FORA] == "", "o aparelho não acendeu"
    a07.mover_o_livre_da_modificacao(ctx, {**o, "vivo": "2", "carimbo": "2"}, ponte)
    assert [p["valor"] for m, p in ponte.chamadas if m == "mods.livre"] == [0.6]


_ABRIR = """(function(endereco, h){
  location.hash = endereco;
  window.__hef.pintar({blocos: {'#mod-janela': h}});
  const j = document.getElementById('mod-janela');
  const rot = [...j.querySelectorAll('.mj-abas > label')].find(l => l.textContent === 'Brinquedos');
  if (!rot) return 'sem a aba';
  rot.click();
  return 'ok';
})(%s, %s)"""
_PINTAR = """(function(b, mesa){
  window.__hef.pintar({blocos: b, mesa: mesa});
  return 'ok';
})(%s, %s)"""
_LER = """(function(){
  const j = document.getElementById('mod-janela');
  const o = e => e ? parseFloat(getComputedStyle(e).opacity) : null;
  const linha = [...j.querySelectorAll('#mod-agora .ap')]
    .find(a => (a.querySelector('.ap-nome') || {}).textContent === 'Aparelho 2');
  const trilho = j.querySelector('.mj-trilho');
  return JSON.stringify({agora: o(linha),
    cartao: o(j.querySelector('.mj-ap:not(.mj-cc)[data-alvo="g2"]')),
    controles: o(j.querySelector('.mj-cc[data-alvo="g2"]')),
    chip: o(j.querySelector('.mj-alvo[data-v$=":g2"]')),
    gravar: o(j.querySelector('.mj-gravar')),
    trilho: trilho.classList.contains('fora'), dica: trilho.getAttribute('data-dica') || ''});
})()"""
_LUZ = """(function(){
  const j = document.getElementById('mod-janela');
  [...j.querySelectorAll('.mj-abas > label')].find(l => l.textContent === 'Luz').click();
  const r = e => e.getBoundingClientRect();
  const cab = j.querySelector('.mj-cc[data-alvo="g1"] .mj-ap-cab');
  const gl = cab.querySelector('.mj-cc-gl'), chave = cab.querySelector('.mj-chave');
  const ligado = j.querySelector('.mj-ap:not(.mj-cc)[data-alvo="g1"] .mj-ap-cab');
  return JSON.stringify({glifo: gl ? [r(gl).width, r(gl).height] : null,
    antes: gl ? r(gl).right <= r(chave).left : false,
    dentro: gl ? r(gl).right <= r(cab).right && r(chave).right <= r(cab).right + 0.5 : false,
    ligado_sem: !ligado.querySelector('.mj-cc-gl')});
})()"""


def test_no_webkit_os_quatro_se_apagam_juntos_e_a_luz_tem_o_glifo(
        janela: Any, ctx: Any, lar: Any, pagina_fresca: pathlib.Path) -> None:  # noqa: F811
    from hefesto_dualsense4unix.interface import hefesto_vivo

    a07, ponte, html = _abrir(janela, ctx, lar, _estado(_aparelho(1), _aparelho(2)))
    passos: list[list[Any]] = [["js", hefesto_vivo.BOOTSTRAP],
                               ["js", _ABRIR % (json.dumps(ENDERECO), json.dumps(html))],
                               ["espera", 0.3], ["js", _LER]]
    for serie, estado in ((2, _estado(_aparelho(1), _aparelho(2, False))),
                          (3, _estado(_aparelho(1), _aparelho(2))),
                          (4, _estado(_aparelho(1, False), _aparelho(2, False)))):
        blocos = _tique(a07, ponte, {**estado, "serie": serie})
        mesa = json.loads(blocos.pop("mesa"))
        passos += [["js", _PINTAR % (json.dumps(blocos), json.dumps(mesa))], ["espera", 0.3],
                   ["js", _LER]]
    passos.append(["js", _LUZ])
    lidos = no_webkit(pagina_fresca, {f"{w}x{h}": (w, h, passos) for w, h in VISTAS})
    print(json.dumps(lidos, ensure_ascii=False))
    for caso, (_, abriu, ligado, *pintados) in lidos.items():
        assert len(pintados) == 7, (caso, pintados)
        desligado, religado, nenhum, luz = pintados[1], pintados[3], pintados[5], pintados[6]
        assert abriu == "ok", (caso, abriu)
        ligado, desligado, religado, nenhum = map(json.loads, (ligado, desligado, religado, nenhum))
        lugares = ("agora", "cartao", "controles", "chip")
        assert all(ligado[k] == 1.0 for k in lugares), (caso, ligado)
        assert all(desligado[k] == 0.5 for k in lugares), (caso, "não se apagam juntos", desligado)
        assert religado == ligado, (caso, religado)
        assert not ligado["trilho"] and not desligado["trilho"], (caso, desligado)
        assert nenhum["trilho"], (caso, nenhum)
        assert ligado["gravar"] == 1.0 and nenhum["gravar"] == 0.5, (caso, "o Gravar aceso", nenhum)
        assert nenhum["dica"].startswith("Nenhum aparelho ligado"), (caso, nenhum)
        luz = json.loads(luz)
        assert luz["glifo"] == [16, 16] and luz["antes"] and luz["dentro"], (caso, luz)
        assert luz["ligado_sem"], caso
