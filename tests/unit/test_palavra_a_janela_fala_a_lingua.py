"""PALAVRA-01 — a janela fala a língua de quem joga.

Três portões, um por queixa medida na sprint
``docs/process/sprints/2026-07-27-PALAVRA-01-a-janela-fala-a-lingua-de-quem-joga.md``:

1. **Capitalização.** Os textos de estado que ela lê no meio de uma frase
   ("ligado", "desligado (suprimido)", "daemon offline") começavam em
   minúscula. Frase que aparece na tela começa com maiúscula.
2. **Nome da aba.** A aba chamava-se "Navegação DSX". "DSX" é nome de um
   programa de outra casa: descreve de onde a ideia veio, não o que a aba
   faz. Nenhum rótulo visível pode voltar a exibir esse nome.
3. **Tooltip nos controles que mudam alguma coisa.** Botão, escala, seletor,
   entrada e switch explicam o que vão fazer antes de a pessoa clicar. O
   portão trava o número medido: a cobertura não pode cair.

O portão lê o CÓDIGO-FONTE (a árvore de sintaxe do Python e o XML do Glade),
não uma janela viva: assim ele roda na CI sem GTK e ainda assim morde quando
alguém reescreve o texto.
"""
from __future__ import annotations

import ast
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PACOTE = RAIZ / "src" / "hefesto_dualsense4unix"
GLADE = PACOTE / "gui" / "main.glade"
EMULACAO_PY = PACOTE / "app" / "actions" / "emulation_actions.py"
MOUSE_PY = PACOTE / "app" / "actions" / "mouse_actions.py"
GATILHOS_PY = PACOTE / "app" / "actions" / "trigger_specs.py"

#: Classes GTK que a pessoa aciona para MUDAR alguma coisa. Rótulo estático,
#: caixa, moldura e imagem ficam de fora de propósito: a sprint pediu tooltip
#: em quem decide, não nos 163 rótulos que só descrevem.
CLASSES_INTERATIVAS = frozenset({
    "GtkButton",
    "GtkCheckButton",
    "GtkColorButton",
    "GtkComboBox",
    "GtkComboBoxText",
    "GtkEntry",
    "GtkFileChooserButton",
    "GtkFontButton",
    "GtkLinkButton",
    "GtkMenuButton",
    "GtkRadioButton",
    "GtkScale",
    "GtkScaleButton",
    "GtkSearchEntry",
    "GtkSpinButton",
    "GtkSwitch",
    "GtkToggleButton",
    "GtkVolumeButton",
})

#: Medido na entrega: 82 controles interativos, 82 com tooltip. O piso é o
#: número medido — se alguém acrescentar controle sem tooltip, ou tirar um
#: tooltip que existe, a conta cai e o teste reprova.
CONTROLES_INTERATIVOS_ESPERADOS = 82
COBERTURA_MINIMA_DE_TOOLTIP = 82

_TAG_MARKUP = re.compile(r"<[^>]*>")
_PRIMEIRA_LETRA = re.compile(r"[^\W\d_]", re.UNICODE)


def _textos_de_tela(caminho: Path) -> list[str]:
    """Strings do módulo que carregam markup Pango — o que vai para o rótulo.

    A concatenação implícita já vem resolvida pelo parser; de f-string só
    entram os pedaços literais, que é onde mora a capitalização.
    """
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    achados: list[str] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Constant) and isinstance(no.value, str):
            achados.append(no.value)
        elif isinstance(no, ast.JoinedStr):
            achados.append(
                "".join(
                    parte.value
                    for parte in no.values
                    if isinstance(parte, ast.Constant) and isinstance(parte.value, str)
                )
            )
    return [t for t in achados if "<span" in t]


def _sem_markup(texto: str) -> str:
    return _TAG_MARKUP.sub("", texto).strip()


def _comeca_em_minuscula(texto: str) -> bool:
    m = _PRIMEIRA_LETRA.search(texto)
    return m is not None and m.group(0).islower()


def _rotulos_de_aba() -> list[str]:
    raiz = ET.parse(GLADE).getroot()
    rotulos: list[str] = []
    for filho in raiz.iter("child"):
        if filho.get("type") != "tab":
            continue
        for obj in filho.iter("object"):
            for prop in obj.findall("property"):
                if prop.get("name") == "label" and prop.text:
                    rotulos.append(prop.text)
    return rotulos


def _textos_visiveis_do_glade() -> list[str]:
    raiz = ET.parse(GLADE).getroot()
    visiveis: list[str] = []
    for obj in raiz.iter("object"):
        for prop in obj.findall("property"):
            nome = prop.get("name") or ""
            visivel = nome in {"label", "tooltip-text", "tooltip_text", "placeholder-text"}
            if visivel and prop.text:
                visiveis.append(prop.text)
    return visiveis


def _interativos_e_com_tooltip() -> tuple[int, list[str]]:
    raiz = ET.parse(GLADE).getroot()
    total = 0
    sem_tooltip: list[str] = []
    for obj in raiz.iter("object"):
        if obj.get("class") not in CLASSES_INTERATIVAS:
            continue
        total += 1
        nomes = {p.get("name") for p in obj.findall("property")}
        if not ({"tooltip-text", "tooltip_text"} & nomes):
            sem_tooltip.append(obj.get("id") or f"<sem id: {obj.get('class')}>")
    return total, sem_tooltip


# --- Grupo 1: capitalização dos textos de estado ---------------------------


@pytest.mark.parametrize("arquivo", [EMULACAO_PY, MOUSE_PY], ids=["emulacao", "mouse"])
def test_texto_de_estado_nao_comeca_em_minuscula(arquivo: Path) -> None:
    """Ela lê "ligado"/"desligado"/"daemon offline" no meio de uma frase.

    Morde ao arrancar a cura: devolver ``'<span ...>ligado</span>'`` a
    ``emulation_actions`` faz este teste apontar o texto exato.
    """
    culpados = [
        _sem_markup(t) for t in _textos_de_tela(arquivo) if _comeca_em_minuscula(_sem_markup(t))
    ]
    assert culpados == [], (
        f"{arquivo.name}: texto de tela começando em minúscula: {culpados}"
    )


def test_os_estados_de_hoje_estao_escritos_como_frase() -> None:
    """Trava, um a um, os textos que a sprint listou por nome."""
    emulacao = [_sem_markup(t) for t in _textos_de_tela(EMULACAO_PY)]
    mouse = [_sem_markup(t) for t in _textos_de_tela(MOUSE_PY)]

    assert "Ligado" in emulacao
    assert "Desligado" in emulacao
    assert "Desligado (suprimido)" in emulacao
    assert "O Hefesto está em pausa" in emulacao
    assert "O Hefesto está desligado" in emulacao
    assert any(t.startswith("Desligado — emulação normal") for t in emulacao)
    assert any(t.startswith("Jogar direto (Sony)") for t in emulacao)
    assert any(t.startswith("Ligado —") for t in emulacao)

    assert "Pronto para usar como mouse" in mouse
    assert any(t.startswith("O mouse virtual está sem permissão") for t in mouse)
    assert any(t.startswith("O mouse virtual ainda não está pronto") for t in mouse)
    assert any(t.startswith("Falta um componente do mouse virtual") for t in mouse)


# --- Grupo 2: a aba deixa de se chamar "Navegação DSX" ---------------------


def test_nenhuma_aba_carrega_nome_de_produto_de_terceiro() -> None:
    """"DSX" não diz o que a aba faz — e é nome de programa de outra casa."""
    rotulos = _rotulos_de_aba()
    assert rotulos, "nenhuma aba encontrada no Glade: a varredura está cega"
    com_dsx = [r for r in rotulos if "DSX" in r.upper()]
    assert com_dsx == [], f"aba com nome de produto de terceiro: {com_dsx}"


def test_a_aba_do_mouse_diz_o_que_faz() -> None:
    assert "Navegação" in _rotulos_de_aba()


def test_nenhum_texto_visivel_da_janela_diz_dsx() -> None:
    """O nome não pode reaparecer em rótulo, tooltip ou dica de campo."""
    culpados = [t for t in _textos_visiveis_do_glade() if "DSX" in t.upper()]
    assert culpados == [], f"texto visível ainda diz DSX: {culpados}"


# --- Grupo 3: cobertura de tooltip nos controles interativos ---------------


def test_todo_controle_que_muda_alguma_coisa_explica_o_que_faz() -> None:
    """Botão, escala, seletor, entrada e switch: nenhum fica mudo.

    Morde ao arrancar a cura: apagar um ``tooltip-text`` do Glade faz este
    teste nomear o ``id`` que ficou sem explicação.
    """
    total, sem_tooltip = _interativos_e_com_tooltip()
    assert sem_tooltip == [], f"controle interativo sem tooltip: {sem_tooltip}"
    assert total - len(sem_tooltip) >= COBERTURA_MINIMA_DE_TOOLTIP, (
        f"a cobertura caiu: {total - len(sem_tooltip)} de {total} "
        f"(piso medido: {COBERTURA_MINIMA_DE_TOOLTIP})"
    )


def test_a_conta_de_controles_interativos_nao_encolheu_sem_aviso() -> None:
    """Se o universo medido mudar, o piso acima precisa ser remedido a mão."""
    total, _ = _interativos_e_com_tooltip()
    assert total >= CONTROLES_INTERATIVOS_ESPERADOS, (
        f"o Glade tem {total} controles interativos; a medição da entrega viu "
        f"{CONTROLES_INTERATIVOS_ESPERADOS}. Remedir antes de baixar o piso."
    )


# --- Grupo 4: jargão dos gatilhos ------------------------------------------


def _rotulos_de_gatilho() -> list[str]:
    from hefesto_dualsense4unix.app.actions.trigger_specs import PRESETS

    rotulos = [spec.label for spec in PRESETS]
    for spec in PRESETS:
        rotulos.extend(p.label for p in spec.params)
    return rotulos


def test_gatilhos_nao_mostram_jargao_em_ingles() -> None:
    """"start+1..8" e "raw HID" estavam dentro de uma janela em português."""
    banidos = ("start+1", "raw HID", "Mode HID", "Force ", "Pos ")
    culpados = [r for r in _rotulos_de_gatilho() if any(b in r for b in banidos)]
    assert culpados == [], f"rótulo de gatilho ainda em jargão: {culpados}"


# Aqui morava `test_o_termo_tecnico_fica_so_onde_ajuda_a_achar_o_modo_em_guia`,
# que EXIGIA "Rígido (Rigid)", "Arco (Bow)" e os irmãos no rótulo, para ela
# reconhecer o modo que um guia em inglês cita. A decisão dela em 31/07 trocou
# o lado — os parênteses saem, pela regra R2 do `docs/process/CLEAN-ROOM.md` —
# e a regra inversa passou a morar em `test_gatilho_palavra_rotulos.py`, que
# tem a exceção nomeada `PENDENCIA_DE_PALAVRA` para os dois rótulos cuja
# palavra ainda é decisão dela ("Arco" e "Arma" sozinhos são ambíguos).
# Repetir a cobrança aqui, sem a exceção, brigaria com aquele portão.


def test_o_arquivo_de_gatilhos_nao_guarda_mais_o_texto_antigo() -> None:
    """Portão de fonte: o texto banido não pode voltar nem em outro preset."""
    fonte = GATILHOS_PY.read_text(encoding="utf-8")
    for proibido in ("start+1..8", "raw HID"):
        assert proibido not in fonte, f"voltou ao trigger_specs.py: {proibido}"
