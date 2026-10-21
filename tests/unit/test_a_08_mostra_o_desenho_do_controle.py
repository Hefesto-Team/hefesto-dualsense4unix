"""A-08-MOSTRA-O-DESENHO-DO-CONTROLE-E-O-HUB-PERGUNTA-A-ENTRADA-01, item 1: o desenho no quadrado.

Ela, 08/10/2026: *«temos os svgs deles no repo já (…) colocamos eles nos quadrados de cada
controle.»*
A linha do controle de fora ganha o desenho do modelo (desenho nosso: a arte que a casa já trazia
não tem origem nem licença registradas) e o nome do modelo vai para a dica do quadrado, não para o
corpo da linha.

O que se mede, com cabo e com rádio e com quatro externos na mesma lista:

* cada forma que tem desenho (Pro Controller, Xbox, 8BitDo) leva UM quadrado `<svg><use>` apontando
  para um símbolo que EXISTE no sprite da página, e o nome do modelo mora só no `title` do quadrado;
* o que não tem desenho próprio (o Joy-Con, a HORI) leva o contorno genérico: o Joy-Con é Nintendo,
  mas não tem a forma do Pro Controller, e a tela não afirma um modelo que ninguém desenhou;
* os quatro desenhos são nossos: só traçado, sem nada de fora, e são eles que a página leva.

Item 2, o «Acrescentar hub» com dono (a face B-hub): o botão abre a pergunta curta (em qual entrada,
nome opcional, Acrescentar/Cancelar) e o ato real é da `LogicaDoMapa`, que grava pelo mesmo caminho
dos outros gestos do mapa (`machine_declare`, o gabinete inteiro).

Item 3, a maiúscula e o texto que vira dica (o laço da régua da primeira letra, com as telas abertas
por âncora, é o `test_todo_texto_que_abre_uma_linha_comeca_com_maiuscula.py`); item 4, o mouse sem
faixa pede o aparelho no Bluetooth.
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"


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
JOYCON = {"name": "Joy-Con (L)", "vid": "057e", "pid": "2006", "driver": "hid-nintendo"}

MODELO = {"057e:2009": "Pro Controller (modo Switch)", "045e:028e": "Xbox 360"}
SIMBOLO = {"057e:2009": "ext-pro", "045e:028e": "ext-xbox", "2dc8:6003": "ext-8bitdo"}
NOSSOS = ("pro-controller.svg", "xbox.svg", "8bitdo.svg", "generico.svg")


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
    todos = {*conexoes.SIMBOLO_DO_EXTERNO.values(), conexoes.SIMBOLO_DO_PRO,
             conexoes.SIMBOLO_GENERICO}
    for simbolo in todos:
        achados = re.findall(
            rf'<symbol id="{simbolo}" viewBox="[^"]+">(.+?)</symbol>', pagina, re.S)
        assert len(achados) == 1, f"o símbolo {simbolo} não está no sprite da página"
        assert "<path" in achados[0] or "<circle" in achados[0], simbolo
        assert "currentColor" in achados[0], f"{simbolo}: o desenho não segue a cor do texto"
    assert todos == {*SIMBOLO.values(), "ext-generico"}


@pytest.mark.parametrize("vp", ["057e:2009", "045e:028e"])
def test_o_nome_do_modelo_mora_na_dica_do_quadrado_e_nao_no_corpo_da_linha(vp: str) -> None:
    base = PRO if vp == "057e:2009" else XBOX
    (linha,) = _linhas(_externo(base, "usb", 1))
    assert f'title="{MODELO[vp]}"' in linha and f'aria-label="{MODELO[vp]}"' in linha
    sem_atributos = re.sub(r"<[^>]+>", "|", linha)
    assert MODELO[vp] not in sem_atributos, "o modelo voltou a ser texto da linha"


def test_o_que_nao_tem_desenho_proprio_leva_o_generico_e_quatro_externos_cabem_em_quatro_linhas(
        ) -> None:
    linhas = _linhas(_externo(PRO, "bluetooth", 1), _externo(XBOX, "usb", 2),
                     _externo(SN30, "bluetooth", 3), _externo(HORI, "usb", 4))
    assert len(linhas) == 4
    simbolos = [re.findall(r'<use href="#([^"]+)"/>', x) for x in linhas]
    assert simbolos == [["ext-pro"], ["ext-xbox"], ["ext-8bitdo"], ["ext-generico"]], simbolos


@pytest.mark.parametrize("bus", ["usb", "bluetooth"])
def test_o_joy_con_nao_ganha_o_desenho_do_pro_controller(bus: str) -> None:
    (linha,) = _linhas(_externo(JOYCON, bus, 1))
    assert '<use href="#ext-generico"/>' in linha, linha
    assert 'title="Joy-Con (E)"' in linha, linha


@pytest.mark.parametrize("nome", NOSSOS)
def test_os_desenhos_sao_nossos_sem_nada_de_fora_e_sao_eles_que_a_pagina_leva(nome: str) -> None:
    texto = (RAIZ / "assets" / "control-svg" / nome).read_text(encoding="utf-8")
    assert texto.lstrip().startswith("<svg") and "viewBox=" in texto
    for fora in ("<image", "http://", "https://", "<metadata", "xlink:href", "<script"):
        if fora == "http://":
            assert texto.count("http://") == texto.count("http://www.w3.org/2000/svg"), texto
        else:
            assert fora not in texto, f"o desenho nosso cita `{fora}`"
    # o corpo do desenho (o primeiro traçado) é o que o sprite da página leva
    (corpo,) = re.findall(r'<path d="([^"]+)"/>', texto)[:1]
    assert f'<path d="{corpo}"/>' in _a_pagina(), f"{nome}: a página não leva este desenho"


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
    assert "Ligado na entrada <b>2</b>" in html


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
    corpo = re.search(r'<div class="hub-pergunta" id="hub-pergunta">(.*?)</div>\s*'
                      r'<div class="mm-grade',
                      pagina, re.S)
    assert corpo, "a pergunta do hub saiu do mockup"
    texto = corpo.group(1)
    assert 'data-linha="hub-entrada"' in texto and 'data-linha="hub-nome"' in texto
    assert 'maxlength="24"' in texto and "Nome do hub (opcional)" in texto
    assert 'data-gesto="novo-hub-gravar" data-hef-forma="hub-pergunta"' in texto
    assert 'data-gesto="novo-hub-cancelar"' in texto


# ───────────────────── item 3: a maiúscula e o texto que vira dica ─────────────────────


def test_o_quadrado_do_mapa_abre_cada_frase_com_maiuscula() -> None:
    """O motor devolve «ocupada», «vale evitar»: quem desenha sobe só a primeira letra."""
    from hefesto_dualsense4unix.interface.conexoes import html_do_mapa

    html = html_do_mapa(
        [{"nome": "Traseira", "portas": ["1", "2"]}],
        quem_esta={"1": ("Mouse", "3-1")}, extensoes={"2": "2a"},
        veredito_de=lambda n, e: ("evite", "vale evitar", "colada no Mouse, na entrada 1"),
        rotulos={"vazia": "vazia", "por_extensao": "por extensão",
                 "nova_entrada": "Acrescentar entrada"},
        dicas={"esticada": "Foi você.", "enumera": "Enumera {c}.", "nova_entrada": "",
               "novo_hub": ""},
        nomes={}, pergunta=None)
    assert ">Vale evitar<" in html and ">Vazia<" in html and ">Por extensão<" in html
    assert "Colada no Mouse, na entrada 1" in html
    assert "Ligado na entrada <b>2</b>" in html
    for minuscula in (">vale evitar<", ">vazia<", ">por extensão<", ">ligado na entrada"):
        assert minuscula not in html


def test_o_mapa_sem_face_diz_uma_frase_curta_e_a_explicacao_vai_na_dica() -> None:
    from hefesto_dualsense4unix.interface.conexoes import html_do_mapa
    from hefesto_dualsense4unix.interface.logica_do_mapa import DICA_SEM_FACE, ROTULO_SEM_FACE

    html = html_do_mapa([], quem_esta={}, extensoes={}, veredito_de=lambda n, e: ("", "", ""),
                        rotulos={"vazia": "", "por_extensao": "", "nova_entrada": ""},
                        dicas={"esticada": "", "enumera": "", "nova_entrada": "", "novo_hub": ""})
    assert ROTULO_SEM_FACE in html and DICA_SEM_FACE not in html.split("title=")[0]
    assert f'title="{DICA_SEM_FACE}"' in html
    assert ROTULO_SEM_FACE.count(".") == 1, "a frase do corpo voltou a explicar"


def test_o_contador_da_cerimonia_abre_com_maiuscula_no_desenho_e_no_pacote() -> None:
    from hefesto_dualsense4unix.interface import aba08

    assert aba08._pacote08.contador_da_cerimonia(3, 7) == "Entrada 3 de 7"
    pagina = _a_pagina()
    assert re.search(r'class="ce-cont"[^>]*>Entrada \d+ de \d+', pagina)
    assert not re.search(r'class="ce-cont"[^>]*>entrada ', pagina)


def test_o_texto_explicativo_das_telas_de_mapear_mora_no_titulo_da_janela() -> None:
    """Ordem de produto (ESCOLHAS, 08/10): o explicativo de «Mapear entradas» e de
    «Entrada a Entrada» sai do corpo e vai para o hover do título (o «?» saiu, 13/10)."""
    pagina = _a_pagina()
    assert 'class="ce-relogios"' not in pagina, "o texto dos dois relógios voltou ao corpo da tela"
    depois_do_fim = pagina.split('id="mapear-entrada-a-entrada-fim"')[1]
    corpo_fim = depois_do_fim.split('id="mapear-entrada-a-entrada-em-pe"')[0]
    assert re.search(r'<span class="ce-quem"[^>]*></span>', corpo_fim), "o convite voltou ao corpo"
    assert 'data-dica="Falta marcar as entradas vazias"' in corpo_fim, "a dica saiu do título"
    portas = pagina.split('id="mapear-portas"')[1].split("</script>")[0]
    assert 'data-dica="Use o mesmo DualSense em todas as entradas"' in portas
    assert "Nomeie a entrada" not in portas, "a explicação longa da porta voltou à tela"
    assert ('data-campo="mapear-diz">Conecte um DualSense em cada entrada USB do seu '
            'dispositivo.</span>') in portas


# ───────────────────── item 4: o mouse sem faixa pede o aparelho no Bluetooth ─────────────────────


def test_o_mouse_que_nao_achou_a_faixa_pede_um_aparelho_no_bluetooth(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import copy

    from hefesto_dualsense4unix.integrations import receptor_sem_fio
    from hefesto_dualsense4unix.interface import aba08

    base = aba08.CENA_DO_RADIO
    cena = copy.deepcopy(base)
    lug = cena["lugares"][1]["id"]
    cena["vizinhos"] = [*cena.get("vizinhos", []), {
        "id": "aaaa:bbbb", "tipo": "mouse", "nome": "Mouse", "sugestao": "", "sugestao_tipo": "",
        "no": "", "lido": "", "produto": "", "receptor": True, "banda": None, "saude": None}]
    cena["canais_medidos"] = {**cena.get("canais_medidos", {}), lug: False}
    monkeypatch.setattr(conexoes, "_passo_da_linha", lambda _c: receptor_sem_fio.PASSO_NADA)
    html = conexoes.html_dos_canais(cena)
    assert "<span>Precisa de um aparelho no Bluetooth · Tentar de novo</span>" in html
    assert "Faixa não encontrada" not in html
    assert conexoes.TENTAR_DE_NOVO == "Precisa de um aparelho no Bluetooth · Tentar de novo"
    assert "Bluetooth" in conexoes.FAIXA_NAO_ACHADA
    assert "não só o controle" in conexoes.FAIXA_NAO_ACHADA


def test_o_via_da_linha_do_externo_cede_com_reticencias_e_leva_a_frase_inteira_na_dica() -> None:
    """O quadrado do modelo tomou 42 px da linha, e a 1272 px as listas vazavam: quem cede é o
    «via», que vira reticências e guarda a frase inteira no `title`."""
    from hefesto_dualsense4unix.app.actions.home_actions import _format_external_subtitle

    entrada = {"nome": "8BitDo Pro 2", "mac": "aa:bb:cc:00:00:41", "tipo": "bluetooth",
               "bus": "bluetooth", "vendor": "2dc8", "product": "6003"}
    ctx = Contexto(state={"connected": True}, mesa=[], conectados=[], externos=[entrada])
    html = conexoes._html_dos_externos(ctx)
    frase = _format_external_subtitle(entrada)
    assert f'<span class="ext-via" title="{frase}">{frase}</span>' in html
    css = (INTERFACE / "aba08.py").read_text(encoding="utf-8")
    assert re.search(r"\.gc \.ext-via\{[^}]*min-width:0;[^}]*text-overflow:ellipsis", css)
