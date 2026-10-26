"""A aba Gatilhos parou de digitar o que já tem dono — 03/09/2026."""

from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

PAGINA = "03-gatilhos.html"

UNIQ = "aa:bb:cc:00:00:01"
FALSO = {"uniq": UNIQ, "player": 1, "transport": "usb", "is_primary": True,
         "inputs": {"l2_raw": 0, "r2_raw": 0}}
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "USB", "cor": "starlight-blue", "mascara": "DualSense"}]

_OPCAO = re.compile(r'<option value="(?P<valor>[^"]*)"[^>]*>(?P<texto>[^<]*)</option>')
_SELECT = re.compile(
    r'<select[^>]*class="(?P<classe>modo|pronto|g2-acion|g2-imersao)"[^>]*>(?P<dentro>.*?)</select>',
    re.S)


_PERFIL_DA_CENA: dict = {}


@pytest.fixture(autouse=True)
def _o_perfil_de_mentira_nao_vaza():
    """O dublê de `perfil.ativo` VOLTA — sem isto ele envenenava a suíte."""
    from pacotes import perfil

    original = perfil.ativo
    perfil.ativo = lambda _nome: dict(_PERFIL_DA_CENA)  # type: ignore[assignment]
    yield
    perfil.ativo = original
    _PERFIL_DA_CENA.clear()


@pytest.fixture
def a03():
    import pacotes  # noqa: F401
    from pacotes import a03_gatilhos

    a03_gatilhos.esquecer_o_rascunho()
    yield a03_gatilhos
    a03_gatilhos.esquecer_o_rascunho()


@pytest.fixture
def presets():
    from hefesto_dualsense4unix.app.actions.trigger_specs import PRESETS

    return PRESETS


def _o_da_tela(preset) -> str:
    """O rótulo que a tela dá ao modo: o do produto, salvo o «Desligado» (`Off`)."""
    from pacotes.a03_gatilhos import ROTULO_DO_JOGO_DECIDE

    return ROTULO_DO_JOGO_DECIDE if preset.name == "Off" else preset.label


def _bancada() -> str:
    from hefesto_dualsense4unix.interface import onde

    return onde.pagina(PAGINA).read_text(encoding="utf-8")


def _selects(doc: str, classe: str) -> list[str]:
    return [m.group("dentro") for m in _SELECT.finditer(doc) if m.group("classe") == classe]


def _oferecidos(a03, presets):
    """Os modos que o perfil antigo pode trazer: o «Montar do zero» (`Custom`) não é um."""
    return [p for p in presets if p.name != "Custom"]


def _opcao_do_perfil(a03, nome: str) -> str:
    """A lista do efeito do gatilho para um perfil que só tem o acionamento `nome`."""
    return a03.html_das_opcoes_de_imersao("", "", f"{a03.PREFIXO_DO_ACIONAMENTO}{nome}")


def test_o_rotulo_de_cada_modo_no_pacote_e_o_do_produto(a03, presets):
    """22/10/2026: a lista de acionamento saiu; o rótulo do produto mora na opção «Do perfil».

    Um perfil antigo só com acionamento abre com ele escolhido, e o texto da opção é o rótulo
    do produto (`_rotulo_do_modo`), nunca o que o desenho digitou.

    A MORDIDA: em `html_das_opcoes_de_imersao`, escreva a chave crua (`modo_`) no lugar de
    `_rotulo_do_modo(modo_)`. Medido: este teste nomeia `Bow` e `Weapon`.
    """
    erradas = []
    for p in _oferecidos(a03, presets):
        opcoes = dict(_OPCAO.findall(_opcao_do_perfil(a03, p.name)))
        valor = f"{a03.PREFIXO_DO_ACIONAMENTO}{p.name}"
        if opcoes.get(valor) != _o_da_tela(p):
            erradas.append((p.name, opcoes.get(valor), _o_da_tela(p)))
    assert not erradas, (
        "o pacote pinta um rótulo que não é o do produto:\n  "
        + "\n  ".join(f"{n}: tela={t!r} produto={e!r}" for n, t, e in erradas))


def test_todo_modo_do_produto_tem_opcao_no_pacote(a03, presets):
    """Nenhum acionamento do perfil antigo fica sem opção: sem ela o campo abriria vazio."""
    sem = [p.name for p in _oferecidos(a03, presets)
           if f'value="{a03.PREFIXO_DO_ACIONAMENTO}{p.name}"' not in _opcao_do_perfil(a03, p.name)]
    assert not sem, f"acionamentos do produto sem opção no campo: {sem}"


def test_o_desenho_nao_tem_mais_a_lista_de_acionamento():
    """A bancada não digita rótulo de modo: o campo que os carregava saiu do desenho."""
    doc = _bancada()
    assert not _selects(doc, "modo") and not _selects(doc, "g2-acion")
    assert "g2-acion" not in doc.split("</style>", 1)[-1]
    assert len(_selects(doc, "g2-imersao")) == 8
    assert "Do perfil" not in doc, "o grupo «Do perfil» é do pacote, só quando o gatilho está assim"


def test_a_lista_do_efeito_e_emitida_para_os_oito_campos(a03):
    """Um dono, oito lugares: `blocos` leva a lista a cada `select.g2-imersao`."""
    from pacotes import Contexto

    _PERFIL_DA_CENA.clear()
    _PERFIL_DA_CENA.update({
        "triggers": {"left": {"mode": "Bow", "params": [1, 2, 3, 4]},
                     "right": {"mode": "Off", "params": []}},
        "controllers": {},
    })
    ctx = Contexto(state={"active_profile": "régua"}, mesa=MESA,
                   conectados=[FALSO], estados={})
    blocos = a03.pacote(ctx)["blocos"]
    esperados = {f'[data-controle="p{n}"] select.g2-imersao[data-lado="{s}"]'
                 for n in (1, 2, 3, 4) for s in ("e", "d")}
    faltam = sorted(esperados - set(blocos))
    assert not faltam, f"campos de efeito que o produto não pinta: {faltam}"
    esquerdo = blocos['[data-controle="p1"] select.g2-imersao[data-lado="e"]']
    assert f'value="{a03.PREFIXO_DO_ACIONAMENTO}Bow"' in esquerdo, (
        "o perfil antigo só com acionamento tem de abrir com a opção certa")
    direito = blocos['[data-controle="p1"] select.g2-imersao[data-lado="d"]']
    assert a03.PREFIXO_DO_ACIONAMENTO not in direito, "o `Off` é «Sem efeito», não um acionamento"


def test_a_lista_do_efeito_sai_como_o_dom_a_escreve(a03):
    """Nem `selected`, nem `disabled` cru — senão o piloto repinta para sempre."""
    html = a03.html_das_opcoes_de_imersao()
    assert " selected" not in html, (
        "o bloco emitido carrega a escolha do desenho para a mesa dela")
    assert re.search(r"\sdisabled(?=[\s>])", html) is None, (
        "o `disabled` saiu cru: o navegador devolve `disabled=\"\"` e o piloto "
        "reescreveria os oito campos a cada tique, para sempre")
    assert 'disabled=""' in html, (
        "o travessão da decisão 13 dela perdeu o `disabled` — o lugar vazio "
        "passaria a ser escolhível com o rato")


def test_o_title_de_cada_modo_continua_sendo_o_desta_tela(a03, presets):
    """A frase aprovada do modo vive no `title` da opção «Do perfil», e não é a do motor.

    A MORDIDA: faça a opção «Do perfil» sem `title`. Medido: este teste reprova nomeando os
    modos que perderam a dica.
    """
    prefixo = a03.PREFIXO_DO_ACIONAMENTO
    sem_dica = [p.name for p in _oferecidos(a03, presets)
                if not re.search(rf'value="{prefixo}{p.name}"[^>]*\stitle="[^"]+"',
                                 _opcao_do_perfil(a03, p.name))]
    assert not sem_dica, f"modos que perderam a dica desta tela: {sem_dica}"


def test_nenhum_teste_deste_arquivo_troca_simbolo_de_modulo() -> None:
    """Nada aqui reatribui `perfil.ativo` — quem o troca é a fixture, que desfaz."""
    fonte = pathlib.Path(__file__).read_text(encoding="utf-8")
    linhas = [
        f"{n}: {ln.strip()}"
        for n, ln in enumerate(fonte.splitlines(), start=1)
        if re.search(r"^\s*perfil\.ativo\s*=", ln)
        and "original" not in ln
    ]
    assert len(linhas) <= 1, (
        "há atribuição crua a `perfil.ativo` fora da fixture que a desfaz:\n"
        + "\n".join(linhas)
        + "\n\nFoi assim que este arquivo envenenou a suíte até 05/09/2026.")
