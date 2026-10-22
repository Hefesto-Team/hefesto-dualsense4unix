"""O-GATILHO-SO-TEM-O-EFEITO-01 — o gatilho só tem o efeito (22/10/2026).

O pedido de 21/10: *«o botão avançado em gatilhos não faz sentido e como o gatilho faz não faz
sentido também»*, e na pergunta do chat, «Sai tudo». <!-- noqa-acento: citação literal -->
A aba Gatilhos não tem a chave «Avançado», nem a linha «Como o gatilho faz», nem o tipo
Acionamento no «Criar efeitos novos». O acionamento vem dentro de cada efeito da lista «Efeito do
gatilho»; o gesto `modo` do daemon e o perfil gravado ficam, e nada some do disco.

MORDIDAS (cada uma reprova a régua que a guarda):

* devolver `<label class="g2-avtog">` ao desenho (ou o `hef-gatilhos-avancado`, a linha
  `g2-acion`, o rádio `tipo-criar`) -> `test_o_desenho_nao_traz_de_volta_o_que_saiu` e a prova
  de que cada resto é visto por `_o_que_voltou`;
* tirar a opção «Do perfil» (`acionamento:<modo>`) do `html_das_opcoes_de_imersao` -> o perfil
  antigo só com acionamento abre sem a opção e
  `test_perfil_so_com_acionamento_abre_com_a_opcao_certa` reprova;
* trocar o prefixo `meu-acionamento:` do que ela guardou ->
  `test_o_acionamento_guardado_continua_na_lista`;
* devolver o `tipo` ao `criar-efeito` (guardar na biblioteca dos gatilhos) ->
  `test_criar_sempre_cria_um_efeito_da_lista_unica`.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

MOCKUP = RAIZ / "mockup" / "03-gatilhos.html"
PUBLICADA = INTERFACE / "paginas" / "03-gatilhos.html"  # (noqa-acento: nome da pasta)

UNIQ = "aa:bb:cc:00:00:01"
FALSO = {"uniq": UNIQ, "player": 1, "transport": "usb", "is_primary": True,
         "inputs": {"l2_raw": 0, "r2_raw": 0}}
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua", "via": "USB",
         "cor": "starlight-blue", "mascara": "DualSense"}]

#: O que a cura tirou: cada resto com o texto que o denuncia numa página.
RESTOS = {
    "a chave Avançado": "g2-avtog",
    "o roteiro da chave na sessão": "hef-gatilhos-avancado",
    "a classe das linhas escondidas": 'class="g2-cel g2-av',
    "a linha Como o gatilho faz": "Como o gatilho faz",
    "a caixa de acionamento": 'class="g2-acion"',
    "o endereço da caixa de acionamento": 'data-campo="modo-chave-',
    "o gesto modo na página": 'data-gesto="modo"',
    "o rádio do tipo de efeito a criar": 'name="tipo-criar"',
}


def _sem_estilo(doc: str) -> str:
    return re.sub(r"<(style|script)\b[^>]*>.*?</\1>", "", doc, flags=re.S)


def _o_que_voltou(doc: str) -> list[str]:
    """O que a página ainda traz do que saiu (vazio quando a cura está inteira)."""
    return [nome for nome, traco in RESTOS.items() if traco in doc]


def test_o_desenho_nao_traz_de_volta_o_que_saiu() -> None:
    doc = MOCKUP.read_text(encoding="utf-8")
    assert _o_que_voltou(doc) == []
    assert "Avançado" not in _sem_estilo(doc)
    assert doc.count('data-gesto="imersao"') == 8, "a lista do efeito é a única de cada gatilho"


@pytest.mark.parametrize("nome", sorted(RESTOS))
def test_cada_resto_que_voltar_e_visto(nome: str) -> None:
    """MORDIDA: devolver qualquer um dos restos ao desenho faz a régua acusá-lo pelo nome."""
    doc = MOCKUP.read_text(encoding="utf-8")
    mordido = doc.replace("</body>", f"<!--{RESTOS[nome]}--></body>", 1)
    assert mordido != doc
    assert nome in _o_que_voltou(mordido)


def test_a_publicada_nao_traz_de_volta_o_que_saiu() -> None:
    """A página que o produto renderiza: igual ao desenho depois do `--publicar 03`."""
    publicada = PUBLICADA.read_text(encoding="utf-8")
    desenho = MOCKUP.read_text(encoding="utf-8")
    if publicada != desenho:
        pytest.skip("a 03 publicada ainda é a de antes: o `--publicar 03` é da costura")
    assert _o_que_voltou(publicada) == []


def _caches_do_arquivo(a03, monkeypatch, arquivo: pathlib.Path) -> None:
    """O pacote lê a página PUBLICADA (endereços, opções, lugares): aponta-o para `arquivo`."""
    monkeypatch.setattr(a03, "_pagina_publicada", lambda: arquivo.read_text(encoding="utf-8"))
    for cache in ("_ENDERECOS", "_VAZIOS", "_OFERECE"):
        monkeypatch.setattr(a03, cache, None)


@pytest.fixture
def a03():
    import pacotes  # noqa: F401  (registra os dez)
    from pacotes import a03_gatilhos

    a03_gatilhos.esquecer_o_rascunho()
    yield a03_gatilhos
    a03_gatilhos.esquecer_o_rascunho()


def _coluna(a03, monkeypatch, modo_esq: str, params_esq: list[int]) -> dict:
    from pacotes import Contexto, perfil

    monkeypatch.setattr(perfil, "ativo", lambda _nome: {
        "triggers": {"left": {"mode": modo_esq, "params": params_esq},
                     "right": {"mode": "Off", "params": []}},
        "controllers": {}})
    ctx = Contexto(state={"active_profile": "régua"}, mesa=MESA, conectados=[FALSO], estados={})
    return next(iter(a03.pacote(ctx)["colunas"].values()))


@pytest.mark.parametrize("arquivo", [MOCKUP, PUBLICADA], ids=["desenho", "publicada"])
@pytest.mark.parametrize(("modo", "params"), [("Bow", [3, 7, 4, 5]), ("Galloping", [2, 8, 3, 4, 6]),
                                              ("Vibration", [4, 90, 9])])
def test_perfil_so_com_acionamento_abre_com_a_opcao_certa(a03, monkeypatch, arquivo, modo, params):
    """Nunca «Sem efeito» se o gatilho resiste; vale com a página de antes e com a nova."""
    _caches_do_arquivo(a03, monkeypatch, arquivo)
    col = _coluna(a03, monkeypatch, modo, params)
    escolhida = col["imersao-e"]
    assert escolhida != a03.SEM_IMERSAO, "o gatilho resiste: a lista não pode dizer «Sem efeito»"
    assert escolhida, "a lista abriria sem escolha"
    if escolhida.startswith(a03.PREFIXO_DO_ACIONAMENTO):
        assert escolhida == f"{a03.PREFIXO_DO_ACIONAMENTO}{modo}"
        bloco = a03.html_das_opcoes_de_imersao("", "left", escolhida)
        assert f'<option value="{escolhida}"' in bloco, "a opção escolhida tem de existir"
        assert a03.GRUPO_DO_PERFIL in bloco


def test_o_solto_segue_sendo_sem_efeito(a03, monkeypatch):
    _caches_do_arquivo(a03, monkeypatch, MOCKUP)
    assert _coluna(a03, monkeypatch, "Off", [])["imersao-e"] == a03.SEM_IMERSAO


def test_o_acionamento_guardado_continua_na_lista(a03, monkeypatch):
    """O acionamento que ela guardou mora em «Seus efeitos», do lado dele, e o perfil o acha."""
    from pacotes import meus_efeitos as me

    me.guardar_meus_efeitos(
        {"Freio da régua": {"left": {"mode": "Rigid", "params": [3, 200]}}}, "gatilhos")
    valor = f"{a03.PREFIXO_DO_SEU_ACIONAMENTO}Freio da régua"
    assert valor in a03.html_das_opcoes_de_imersao("", "left")
    assert valor not in a03.html_das_opcoes_de_imersao("", "right")
    _caches_do_arquivo(a03, monkeypatch, MOCKUP)
    assert _coluna(a03, monkeypatch, "Rigid", [3, 200])["imersao-e"] == valor


def test_criar_sempre_cria_um_efeito_da_lista_unica(a03):
    """Sem tipo a escolher: a forma que ainda traga `tipo: acionamento` cria o efeito da lista."""
    from pacotes import meus_efeitos as me

    forma = {"tipo": "acionamento", "partir": "Rigid", "nome": "Recuo da régua",
             "inicio": "3", "fim": "9", "forca": "5", "freq": "40"}
    a03.criar_efeito_dos_gatilhos(None, {"forma": forma}, None)
    assert me.meus_efeitos("gatilhos") == {}, "nada novo entra na biblioteca dos acionamentos"
    assert "Recuo da régua" in me.meus_efeitos("imersao")
    for lado in ("left", "right"):
        assert f"{me.PREFIXO_DO_MEU}Recuo da régua" in a03.html_das_opcoes_de_imersao("", lado)
