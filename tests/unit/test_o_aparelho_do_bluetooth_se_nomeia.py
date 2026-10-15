"""O aparelho do Bluetooth sem tipo se nomeia pela pessoa.

O-APARELHO-DO-BLUETOOTH-SEM-TIPO-SE-NOMEIA-PELA-PESSOA-01 (13/10/2026). O que a régua prova:

* a linha do aparelho que nem o ``Icon``, nem a ``Class``, nem a ``Appearance`` nomeiam leva o
  «?» que abre a grade «O que é este aparelho?», e a linha com tipo (dado ou escolhido) não leva;
* a grade tem as nove palavras do desenho, e cada uma grava um valor que o ``maquina.json`` aceita;
* o gesto ``aparelho-tipo`` guarda a escolha pelo ENDEREÇO do aparelho que a tela tem agora, e ela
  vence a adivinhação a cada leitura, no aparelho conectado e no desligado, e SOBREVIVE à releitura
  do disco;
* a escolha «Outro» também vale: o aparelho deixa de perguntar e não vira «Acessório» pelo enlace.

MORDIDAS: tirar a leitura da escolha (``_tipo_que_ela_disse``) reprova a sobrevivência e a vitória
sobre a adivinhação; tirar o ``tipo_dela`` do teste do enlace devolve o «Acessório» ao «Outro» dela;
tirar o «?» do ``_linha_sem_tipo`` reprova a linha; tirar o ``data-alvo`` do «?» reprova a bancada.
"""

from __future__ import annotations

import pathlib
import re
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08
from hefesto_dualsense4unix.utils import maquina

RAIZ = pathlib.Path(__file__).resolve().parents[2]
BANCADA = RAIZ / "mockup" / "08-conexoes.html"
PUBLICADA = RAIZ / "src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html"
ARQUIVOS = [pytest.param(BANCADA, id="bancada"), pytest.param(PUBLICADA, id="publicada")]

ENDERECO = "AA:BB:CC:00:00:E2"
ADAPTADOR = "/org/bluez/hci0"
LUGAR = "AA:BB:CC:00:00:F0"
PALAVRAS = ["Controle", "Fone", "Caixa de som", "Teclado", "Mouse", "Celular", "Relógio",
            "Acessório", "Outro"]


class _Ponte:
    """A ponte do produto, com o ``machine_declare`` gravando no ``maquina.json`` do teste."""

    def __init__(self) -> None:
        self.chamadas: list[dict[str, Any]] = []

    def machine_declare(self, declaracao: dict[str, Any]) -> tuple[bool, str | None]:
        self.chamadas.append(declaracao)
        maquina.gravar_maquina_com_descartes(declaracao)
        return True, None


def _bluez(*, conectado: bool = True, icone: str = "", classe: int | None = None,
           aparencia: int | None = None) -> Any:
    return SimpleNamespace(
        adaptador=ADAPTADOR, endereco=ENDERECO, pareado=True, conectado=conectado, nome="",
        classe=classe, icone=icone, aparencia=aparencia, modalias="")


def _na_tela(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(a08, "_CENA_NA_TELA", {"aparelhos": [{"id": ENDERECO, "tipo": "outro"}]})


def _conectado() -> dict[str, Any]:
    ctx = a08.Contexto(state={"controllers": []}, mesa=[], conectados=[], estados={})
    (ap,) = a08._aparelhos_da_cena(ctx, ctx.state, {}, [], (_bluez(),), {ADAPTADOR: LUGAR},
                                   [LUGAR])
    return ap


def _escolher(monkeypatch: pytest.MonkeyPatch, valor: str) -> _Ponte:
    _na_tela(monkeypatch)
    ponte = _Ponte()
    a08.aparelho_tipo(None, {"alvo": ENDERECO, "valor": valor}, ponte)
    return ponte


# --- a linha --------------------------------------------------------------------------------

def test_o_aparelho_sem_tipo_leva_o_ponto_de_interrogacao_que_abre_a_grade() -> None:
    ap = {"id": ENDERECO, "tipo": "outro", "lugar": LUGAR, "nome": "", "rotulo": "",
          "esperando": False, "fixo": False}
    linha = a08.html_da_linha(ap, {"aparelhos": [ap], "lugares": [{"id": LUGAR}]})
    assert re.search(r'<a class="tipo-qual" href="#tipo-do-aparelho" data-alvo="[^"]+"[^>]*>\?</a>',
                     linha), linha
    assert "Sem tipo" in linha and "#rd-ajuda" not in linha
    assert 'placeholder="Aparelho sem nome"' in linha


@pytest.mark.parametrize("tipo", ["fone", "teclado", "acessorio", "gamepad"])
def test_o_aparelho_com_tipo_nao_pergunta(tipo: str) -> None:
    ap = {"id": ENDERECO, "tipo": tipo, "lugar": LUGAR, "nome": "X", "rotulo": "X",
          "esperando": False, "fixo": False}
    linha = a08.html_da_linha(ap, {"aparelhos": [ap], "lugares": [{"id": LUGAR}]})
    assert "tipo-qual" not in linha and "Sem tipo" not in linha


def test_o_outro_que_ela_escolheu_nao_pergunta_de_novo() -> None:
    ap = {"id": ENDERECO, "tipo": "outro", "tipo_dela": True, "lugar": LUGAR, "nome": "X",
          "rotulo": "X", "esperando": False, "fixo": False}
    linha = a08.html_da_linha(ap, {"aparelhos": [ap], "lugares": [{"id": LUGAR}]})
    assert "tipo-qual" not in linha and "Sem tipo" not in linha


# --- a grade --------------------------------------------------------------------------------

def test_a_grade_tem_as_nove_palavras_e_cada_uma_grava_um_valor_que_o_schema_aceita() -> None:
    html = a08.html_da_grade_de_tipos()
    assert re.findall(r"<span>([^<]+)</span></button>", html) == PALAVRAS
    valores = re.findall(r'data-gesto="aparelho-tipo" data-alvo="" value="([^"]+)"', html)
    assert len(valores) == 9
    for valor in valores:
        declarado = maquina.MaquinaConfig.model_validate(
            {"aparelhos": {"aabbcc0000e2": {"tipo": valor}}})
        assert declarado.aparelhos["aabbcc0000e2"].tipo == valor
    assert 'class="tn-x" href="#" data-dica="Fechar"' in html


# --- a escolha: pelo endereço, vence a adivinhação, sobrevive à releitura --------------------

def test_sem_escolha_o_aparelho_fica_outro_e_pergunta() -> None:
    ap = _conectado()
    assert ap["tipo"] == "outro" and ap["tipo_dela"] is False


def test_a_escolha_se_guarda_pelo_endereco_e_vence_a_adivinhacao(
        monkeypatch: pytest.MonkeyPatch) -> None:
    ponte = _escolher(monkeypatch, "fone")
    assert ponte.chamadas == [{"aparelhos": {"aabbcc0000e2": {"tipo": "fone"}}}]
    ap = _conectado()
    assert (ap["tipo"], ap["tipo_dela"]) == ("fone", True)
    # vence até o que o BlueZ diz: o ``Icon`` de teclado não desfaz a palavra de produto.
    ctx = a08.Contexto(state={"controllers": []}, mesa=[], conectados=[], estados={})
    (com_icone,) = a08._aparelhos_da_cena(
        ctx, ctx.state, {}, [], (_bluez(icone="input-keyboard"),), {ADAPTADOR: LUGAR}, [LUGAR])
    assert com_icone["tipo"] == "fone"


def test_a_escolha_sobrevive_a_releitura_do_disco(monkeypatch: pytest.MonkeyPatch) -> None:
    _escolher(monkeypatch, "caixa")
    a08._reler_a_declaracao()
    assert a08._tipo_que_ela_disse(ENDERECO) == "caixa"
    assert a08._tipo_que_ela_disse(ENDERECO.lower().replace(":", "")) == "caixa"
    assert _conectado()["tipo"] == "caixa"
    do_disco = maquina.carregar_maquina().aparelhos
    assert do_disco["aabbcc0000e2"].tipo == "caixa"


def test_o_desligado_guarda_a_escolha(monkeypatch: pytest.MonkeyPatch) -> None:
    _escolher(monkeypatch, "relogio")
    (ap,) = a08._os_desligados((_bluez(conectado=False),), {ADAPTADOR: LUGAR}, [])
    assert ap["tipo"] == "relogio" and ap["rotulo"] == "Relógio"


def test_controle_vira_o_aparelho_de_glifo_de_controle_e_nao_o_controle_do_hefesto(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _escolher(monkeypatch, "controle")
    ap = _conectado()
    assert ap["tipo"] == "gamepad"
    assert a08.glifo_do_tipo("gamepad") == "ds" and a08.PALAVRA_DO_TIPO["gamepad"] == "controle"


def test_o_outro_dela_nao_vira_acessorio_pelo_enlace(monkeypatch: pytest.MonkeyPatch) -> None:
    _escolher(monkeypatch, "outro")
    ap = _conectado()
    enlaces = {LUGAR: {a08._so_hex(ENDERECO): {"le": True}}}
    a08._com_a_categoria_do_enlace([ap], enlaces)
    assert (ap["tipo"], ap["tipo_dela"]) == ("outro", True)
    sem_escolha = {"id": ENDERECO, "tipo": "outro", "tipo_dela": False, "lugar": LUGAR}
    a08._com_a_categoria_do_enlace([sem_escolha], enlaces)
    assert sem_escolha["tipo"] == a08.TIPO_ACESSORIO


def test_o_gesto_recusa_o_que_nao_e_da_grade_e_o_que_nao_esta_na_tela(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _na_tela(monkeypatch)
    ponte = _Ponte()
    with pytest.raises(ValueError, match="não é uma das respostas da grade"):
        a08.aparelho_tipo(None, {"alvo": ENDERECO, "valor": "geladeira"}, ponte)
    with pytest.raises(ValueError, match="não disse um aparelho"):
        a08.aparelho_tipo(None, {"alvo": "AABBCC0000AA", "valor": "fone"}, ponte)
    assert ponte.chamadas == []
    assert a08.aparelho_tipo(None, {"alvo": ENDERECO, "valor": ""}, ponte) == {"armou": True}
    assert ponte.chamadas == []


def test_com_o_hefesto_desligado_a_escolha_desce_ao_disco(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _na_tela(monkeypatch)

    class _Sem:
        def machine_declare(self, _declaracao: dict[str, Any]) -> tuple[bool, None]:
            return False, None

    a08.aparelho_tipo(None, {"alvo": ENDERECO, "valor": "mouse"}, _Sem())
    assert maquina.carregar_maquina().aparelhos["aabbcc0000e2"].tipo == "mouse"


# --- o desenho -------------------------------------------------------------------------------

@pytest.mark.parametrize("arquivo", ARQUIVOS)
def test_o_desenho_tem_a_grade_e_a_linha_que_a_abre(arquivo: pathlib.Path) -> None:
    doc = arquivo.read_text(encoding="utf-8")
    assert doc.count('id="tipo-do-aparelho"') == 1
    assert re.findall(r'class="tipo-op"[^>]*value="([^"]+)"', doc) == [
        "controle", "fone", "caixa", "teclado", "mouse", "celular", "relogio", "acessorio",
        "outro"]
    qual = re.findall(r'<a class="tipo-qual" href="#tipo-do-aparelho" data-alvo="([^"]+)"', doc)
    assert qual and all(qual), "o «?» da linha tem de levar o endereço do aparelho"
    assert 'symbol id="rd-ajuda"' in doc, "o «Outro» da grade usa o símbolo do «?»"
