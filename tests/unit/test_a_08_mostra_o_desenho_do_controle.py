"""A-08-MOSTRA-O-DESENHO-DO-CONTROLE-E-O-HUB-PERGUNTA-A-ENTRADA-01, item 1: o desenho no quadrado.

Ela, 08/10/2026: *«temos os svgs deles no repo já (…) colocamos eles nos quadrados de cada controle.»*
A linha do controle de fora ganha o desenho do modelo (o do repositório, ou o Xbox, que é desenho
nosso) e o nome do modelo vai para a dica do quadrado, não para o corpo da linha.

O que se mede, com cabo e com rádio e com quatro externos na mesma lista:

* cada marca que tem desenho (Nintendo, Xbox, 8BitDo) leva UM quadrado `<svg><use>` apontando para
  um símbolo que EXISTE no sprite da página, e o nome do modelo mora só no `title` do quadrado;
* a marca sem desenho não ganha quadrado (a tela não afirma um modelo que ninguém desenhou);
* o Xbox é desenho nosso: o arquivo existe, é só traçado e não referencia nada de fora.

Item 2, o «Acrescentar hub» com dono (a face B-hub): o botão abre a pergunta curta (em qual entrada,
nome opcional, Acrescentar/Cancelar) e o ato real é da `LogicaDoMapa`, que grava pelo mesmo caminho
dos outros gestos do mapa (`machine_declare`, o gabinete inteiro).
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from pacotes import Contexto
from pacotes import a08_conexoes as conexoes

from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

# Faixas forjadas (`aa:bb:cc`), nunca endereço real mascarado.
PRO = {"name": "Pro Controller", "vid": "057e", "pid": "2009", "driver": "hid-nintendo"}
XBOX = {"name": "Xbox 360 Controller", "vid": "045e", "pid": "028e", "driver": "xpad"}
SN30 = {"name": "8BitDo SN30 Pro", "vid": "2dc8", "pid": "6003", "driver": "hid-generic"}
HORI = {"name": "Controle da HORI", "vid": "0f0d", "pid": "0092", "driver": "hid-generic"}

MODELO = {"057e:2009": "Pro Controller (modo Switch)", "045e:028e": "Xbox 360"}
SIMBOLO = {"057e:2009": "ext-nintendo", "045e:028e": "ext-xbox", "2dc8:6003": "ext-8bitdo"}


@pytest.fixture(autouse=True)
def _sem_o_maquina_json_dela(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.interface import mesa_viva

    monkeypatch.setattr(mesa_viva, "_declaracao_do_disco",
                        lambda: MaquinaConfig.model_validate({}))


def _externo(base: dict[str, Any], bus: str, ordem: int) -> dict[str, Any]:
    return {**base, "bus": bus, "uniq": f"aa:bb:cc:00:00:{ordem:02x}",
            "player_slot": ordem + 2}


def _linhas(*externos: dict[str, Any]) -> list[str]:
    ctx = Contexto(state={"connected": True}, mesa=[], conectados=[], externos=list(externos))
    html = conexoes._html_dos_externos(ctx)
    return re.findall(r'<div class="ext-linha".*?</div>', html, re.S)


def _a_pagina() -> str:
    return (RAIZ / "mockup" / "08-conexoes.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("bus", ["usb", "bluetooth"])
@pytest.mark.parametrize("base", [PRO, XBOX, SN30], ids=["pro", "xbox", "sn30"])
def test_cada_modelo_tem_o_seu_desenho_no_quadrado_no_cabo_e_no_radio(
        base: dict[str, Any], bus: str) -> None:
    (linha,) = _linhas(_externo(base, bus, 1))
    quadrados = re.findall(r'<span class="ext-desenho"[^>]*>(.*?)</span>', linha, re.S)
    assert len(quadrados) == 1, linha
    simbolo = SIMBOLO[f"{base['vid']}:{base['pid']}"]
    assert f'<svg aria-hidden="true"><use href="#{simbolo}"/></svg>' in quadrados[0]
    # o quadrado é o PRIMEIRO filho da linha: o desenho abre a linha, o nome vem depois
    assert re.match(r'<div class="ext-linha"[^>]*><span class="ext-desenho"', linha), linha


def test_o_simbolo_de_cada_quadrado_existe_no_sprite_da_pagina() -> None:
    pagina = _a_pagina()
    assert pagina.count('<svg class="ext-sprite"') == 1
    for marca, simbolo in conexoes.SIMBOLO_DO_EXTERNO.items():
        achados = re.findall(rf'<symbol id="{simbolo}" viewBox="[^"]+">(.+?)</symbol>', pagina, re.S)
        assert len(achados) == 1, f"{marca}: o símbolo {simbolo} não está no sprite da página"
        assert "<path" in achados[0] or "<circle" in achados[0], marca
        assert "currentColor" in achados[0], f"{marca}: o desenho não segue a cor do texto"
    assert set(conexoes.SIMBOLO_DO_EXTERNO.values()) == set(SIMBOLO.values())


@pytest.mark.parametrize("vp", ["057e:2009", "045e:028e"])
def test_o_nome_do_modelo_mora_na_dica_do_quadrado_e_nao_no_corpo_da_linha(vp: str) -> None:
    base = PRO if vp == "057e:2009" else XBOX
    (linha,) = _linhas(_externo(base, "usb", 1))
    assert f'title="{MODELO[vp]}"' in linha and f'aria-label="{MODELO[vp]}"' in linha
    sem_atributos = re.sub(r"<[^>]+>", "|", linha)
    assert MODELO[vp] not in sem_atributos, "o modelo voltou a ser texto da linha"


def test_marca_sem_desenho_nao_ganha_quadrado_e_quatro_externos_cabem_em_quatro_linhas() -> None:
    linhas = _linhas(_externo(PRO, "bluetooth", 1), _externo(XBOX, "usb", 2),
                     _externo(SN30, "bluetooth", 3), _externo(HORI, "usb", 4))
    assert len(linhas) == 4
    com = ["ext-desenho" in x for x in linhas]
    assert com == [True, True, True, False], com


def test_o_xbox_e_desenho_nosso_sem_nada_de_fora() -> None:
    arquivo = RAIZ / "assets" / "control-svg" / "xbox.svg"
    texto = arquivo.read_text(encoding="utf-8")
    assert texto.lstrip().startswith("<svg") and "viewBox=" in texto
    for fora in ("<image", "http://", "https://", "<metadata", "xlink:href", "<script"):
        if fora == "http://":
            assert texto.count("http://") == texto.count("http://www.w3.org/2000/svg"), texto
        else:
            assert fora not in texto, f"o desenho nosso referencia `{fora}`"


# ---------------------------------------------------------------- item 2: o hub pergunta a entrada

GABINETE = {
    "faces": [{"nome": "Traseira", "portas": ["1", "2"], "perto": False, "alto": False},
              {"nome": "Frontal", "portas": ["3"], "perto": True, "alto": False}],
    "portas": {"1": {"caminho": None}, "2": {"caminho": None}, "3": {"caminho": None}},
}


class _Ponte:
    """Guarda o que foi pedido ao daemon. Responde a qualquer nome, de propósito."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, nome: str):
        def registrar(*args: Any, **kwargs: Any):
            self.chamadas.append((nome, args, kwargs))
            return True
        return registrar


@pytest.fixture
def logica(monkeypatch: pytest.MonkeyPatch):
    from hefesto_dualsense4unix.interface.logica_do_mapa import LogicaDoMapa
    from hefesto_dualsense4unix.utils.maquina import MapaDaMesa

    nova = LogicaDoMapa(MapaDaMesa.model_validate(GABINETE))
    monkeypatch.setattr(conexoes, "_LOGICA", nova, raising=False)
    return nova


def _gesto(nome: str):
    import pacotes

    fn = pacotes.gesto_da_pagina("08-conexoes.html", nome)
    assert fn is not None, f"08-conexoes.html:{nome} ficou sem dono"
    return fn


def _ctx() -> Contexto:
    return Contexto(state={"active_profile": "regua"}, mesa=[], conectados=[], estados={})


def _o_mapa_vivo() -> str:
    return conexoes._html_do_mapa()


def test_o_hub_acrescentado_nasce_filha_da_entrada_escolhida_com_o_nome(logica) -> None:
    assert logica.acrescentar_hub("2", "Hub da mesa") == "2a"
    assert logica.portas["2a"] == {"caminho": None, "filha_de": "2", "nome": "Hub da mesa"}
    # sem nome é hub sem nome; o nome que é só o número da entrada não vale
    assert logica.acrescentar_hub("3", "") == "3a" and "nome" not in logica.portas["3a"]
    assert logica.acrescentar_hub("1", "Entrada 1") == "1a" and "nome" not in logica.portas["1a"]


def test_nome_acima_do_limite_recusa_e_nao_acrescenta_nada(logica) -> None:
    from hefesto_dualsense4unix.utils.rotulo_da_entrada import MAXIMO_DO_NOME_DA_ENTRADA

    logica.perguntar_o_hub()
    assert logica.acrescentar_hub("2", "x" * (MAXIMO_DO_NOME_DA_ENTRADA + 1)) == ""
    assert "2a" not in logica.portas and logica.perguntando_o_hub is True


def test_hub_so_nas_entradas_de_numero_sem_neta(logica) -> None:
    assert logica.entradas_para_o_hub() == ["1", "2", "3"]
    assert logica.acrescentar_hub("2a") == "" and logica.acrescentar_hub("9") == ""


def test_o_gesto_abre_a_pergunta_sem_falar_com_o_daemon(logica) -> None:
    p = _Ponte()
    _gesto("novo-hub")(_ctx(), {}, p)
    assert logica.perguntando_o_hub is True and p.chamadas == []
    html = _o_mapa_vivo()
    assert 'aria-expanded="true"' in html and 'id="hub-pergunta"' in html
    assert re.findall(r'<option value="(\d+)">', html) == ["1", "2", "3"]


def test_o_cancelar_fecha_a_pergunta_e_nao_grava(logica) -> None:
    p = _Ponte()
    _gesto("novo-hub")(_ctx(), {}, p)
    _gesto("novo-hub-cancelar")(_ctx(), {}, p)
    assert logica.perguntando_o_hub is False and p.chamadas == []
    assert "hub-pergunta" not in _o_mapa_vivo() and not logica.filhas_de("2")


def test_o_acrescentar_grava_o_gabinete_inteiro_com_o_hub_dentro(logica) -> None:
    p = _Ponte()
    _gesto("novo-hub")(_ctx(), {}, p)
    _gesto("novo-hub-gravar")(
        _ctx(), {"forma": {"hub-entrada": "2", "hub-nome": "Hub da mesa"}}, p)
    assert [c[0] for c in p.chamadas] == ["machine_declare"]
    mapa = p.chamadas[0][1][0]["mapa"]
    assert mapa["faces"] and mapa["portas"]["2a"] == {
        "caminho": None, "filha_de": "2", "nome": "Hub da mesa"}
    assert logica.perguntando_o_hub is False
    html = _o_mapa_vivo()
    assert "hub-pergunta" not in html and "Hub da mesa" in html
    assert "ligado na entrada <b>2</b>" in html


def test_o_acrescentar_recusa_dizendo_e_nao_grava(logica) -> None:
    from hefesto_dualsense4unix.utils.rotulo_da_entrada import MAXIMO_DO_NOME_DA_ENTRADA

    p = _Ponte()
    _gesto("novo-hub")(_ctx(), {}, p)
    for forma in ({}, {"hub-entrada": "2", "hub-nome": "x" * (MAXIMO_DO_NOME_DA_ENTRADA + 1)},
                  {"hub-entrada": "9", "hub-nome": ""}):
        with pytest.raises((ValueError, RuntimeError)) as caiu:
            _gesto("novo-hub-gravar")(_ctx(), {"forma": forma}, p)
        assert len(str(caiu.value).strip()) >= 20, forma
    assert p.chamadas == [] and logica.perguntando_o_hub is True


def test_sem_entrada_no_desenho_a_pergunta_recusa_dizendo(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.interface.logica_do_mapa import LogicaDoMapa
    from hefesto_dualsense4unix.utils.maquina import MapaDaMesa

    monkeypatch.setattr(conexoes, "_LOGICA", LogicaDoMapa(MapaDaMesa()), raising=False)
    with pytest.raises(RuntimeError, match="entrada"):
        _gesto("novo-hub")(_ctx(), {}, _Ponte())


def test_o_desenho_da_pergunta_tem_os_quatro_elementos_e_o_limite_do_nome() -> None:
    pagina = _a_pagina()
    corpo = re.search(r'<div class="hub-pergunta" id="hub-pergunta">(.*?)</div>\s*<div class="mm-grade',
                      pagina, re.S)
    assert corpo, "a pergunta do hub saiu do mockup"
    texto = corpo.group(1)
    assert 'data-linha="hub-entrada"' in texto and 'data-linha="hub-nome"' in texto
    assert 'maxlength="24"' in texto and "Nome do hub (opcional)" in texto
    assert 'data-gesto="novo-hub-gravar" data-hef-forma="hub-pergunta"' in texto
    assert 'data-gesto="novo-hub-cancelar"' in texto
