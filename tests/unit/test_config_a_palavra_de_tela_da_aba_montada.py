"""O portão de redação da aba Configurações — sobre a aba MONTADA, não o XML.

`scripts/validar-palavra-de-tela.py` é o portão de redação desta casa, e ele
varre um arquivo só: o `main.glade` (`:60`, e o docstring declara o alcance
estreito de propósito). Isso bastou enquanto todo texto de tela morava no XML.

A aba Configurações não mora no XML. Ela é montada em código, um módulo por
seção, e a decisão é anterior a este arquivo: o Glade reserva só o container.
Consequência medida em 22/08/2026, com o andaime pronto e as seções ainda
vazias: **cem por cento do texto desta aba nasceria fora do alcance do portão
de redação** — cinco seções, mais de cem rótulos, nenhum conferido.

Portão que não alcança o texto novo é portão que envelhece sozinho. Este
arquivo é o alcance que faltava: monta a aba de verdade, anda a árvore de
widgets e aplica as MESMAS regras do validador — as do módulo, importadas dele,
nunca copiadas. Copiar as regras criaria duas listas de jargão que divergem na
primeira edição, que é o defeito que a casa já pagou.

O QUE ELE COBRA

1. **Maiúscula inicial** em todo rótulo, opção e título — inclusive dentro de
   botão segmentado, que era onde a inconsistência morava.
2. **Jargão banido** — a lista viva de `validar-palavra-de-tela.py`, que
   recusa "daemon", "uinput" e companhia.
3. **Acentuação** — texto de tela em português do Brasil, escrito certo.

A MORDIDA (verificada em 22/08/2026): pus `TITULO = "orçamento"` em
`secao_orcamento.py` e o primeiro teste reprovou pela minúscula; troquei a dica
da mesa por uma frase com "daemon" e o segundo reprovou pelo jargão.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi`, como no portão
# irmão. "Pulei porque não tenho GTK" é reprovação no job `gtk-real`.
exigir_gi_real("palavra de tela da aba configurações")

import importlib.util
import sys
import unicodedata
from pathlib import Path
from typing import Any

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import ABA_CONFIG, ConfigActionsMixin
from hefesto_dualsense4unix.app.constants import MAIN_GLADE

RAIZ = Path(__file__).resolve().parents[2]


def _validador() -> Any:
    """O `validar-palavra-de-tela.py` importado como módulo.

    Ele mora em `scripts/` e tem hífen no nome, então não é importável pelo
    caminho normal. A alternativa — copiar `JARGAO_BANIDO` para cá — criaria
    duas listas de jargão para divergirem na primeira edição.
    """
    caminho = RAIZ / "scripts" / "validar-palavra-de-tela.py"
    spec = importlib.util.spec_from_file_location("_validador_de_tela", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["_validador_de_tela"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _aba_montada() -> Any:
    """Carrega o Glade, roda o mixin e devolve a caixa da aba."""

    class _Host(ConfigActionsMixin):
        def __init__(self, builder: Gtk.Builder) -> None:
            self.builder = builder

    builder = Gtk.Builder()
    builder.add_from_file(str(MAIN_GLADE))
    _Host(builder).install_config_tab()
    return builder.get_object(ABA_CONFIG)


def _textos_da_arvore(raiz: Any) -> list[tuple[str, str]]:
    """Todo texto visível da árvore, como `(origem, texto)`.

    Origem é o nome do tipo do widget mais o papel do texto (rótulo, dica),
    para a mensagem de falha dizer ONDE consertar sem obrigar a caçar.
    """
    achados: list[tuple[str, str]] = []
    pilha = [raiz]
    while pilha:
        widget = pilha.pop()
        nome = type(widget).__name__
        if isinstance(widget, Gtk.Label):
            texto = widget.get_text()
            if texto:
                achados.append((f"{nome} (rótulo)", texto))
        obter_rotulo = getattr(widget, "get_label", None)
        if obter_rotulo is not None and not isinstance(widget, Gtk.Label):
            texto = obter_rotulo()
            if texto:
                achados.append((f"{nome} (rótulo)", texto))
        dica = widget.get_tooltip_text()
        if dica:
            achados.append((f"{nome} (dica)", dica))
        if isinstance(widget, Gtk.Frame):
            rotulo = widget.get_label_widget()
            if rotulo is not None:
                pilha.append(rotulo)
        obter_filhos = getattr(widget, "get_children", None)
        if obter_filhos is not None:
            pilha.extend(obter_filhos())
    return achados


def test_todo_rotulo_da_aba_comeca_em_maiuscula() -> None:
    """Rótulo, opção e título começam com maiúscula.

    A regra vale para dentro do segmentado, que é onde a inconsistência estava
    quando o desenho foi revisado: `teclado sem fio` ao lado de `Não sei`.
    """
    fora_da_regra = []
    for origem, texto in _textos_da_arvore(_aba_montada()):
        primeira = texto.strip()[:1]
        if not primeira or not primeira.isalpha():
            continue
        if primeira.islower():
            fora_da_regra.append(f"{origem}: {texto!r}")

    assert not fora_da_regra, (
        "texto de tela começando em minúscula na aba Configurações:\n  "
        + "\n  ".join(fora_da_regra)
    )


def test_nenhum_texto_da_aba_carrega_jargao_banido() -> None:
    """A lista de jargão é a do validador — importada, não copiada."""
    banido: dict[str, str] = _validador().JARGAO_BANIDO
    achados = []
    for origem, texto in _textos_da_arvore(_aba_montada()):
        for termo, troca in banido.items():
            if termo.lower() in texto.lower():
                achados.append(f"{origem}: {texto!r} contém {termo!r} — use {troca!r}")

    assert not achados, "jargão na aba Configurações:\n  " + "\n  ".join(achados)


def test_o_texto_da_aba_esta_acentuado() -> None:
    """Português do Brasil escrito certo, na tela como no fonte.

    A checagem é a que cabe num portão de widget: uma palavra que aparece na
    aba SEM acento, quando a mesma palavra aparece COM acento em outro ponto da
    mesma aba, é erro de digitação e não escolha. Comparar contra um dicionário
    inteiro seria o trabalho do `validar-acentuacao.py`, que já roda no fonte.
    """
    palavras_com_acento: dict[str, str] = {}
    todas: list[tuple[str, str, str]] = []
    for origem, texto in _textos_da_arvore(_aba_montada()):
        for palavra in texto.replace("\n", " ").split():
            limpa = palavra.strip(".,;:!?()[]{}\"'—·").lower()
            if not limpa.isalpha() or len(limpa) < 3:
                continue
            sem_acento = "".join(
                caractere
                for caractere in unicodedata.normalize("NFD", limpa)
                if unicodedata.category(caractere) != "Mn"
            )
            if sem_acento != limpa:
                palavras_com_acento[sem_acento] = limpa
            todas.append((origem, limpa, sem_acento))

    achados = [
        f"{origem}: {palavra!r} — a mesma aba escreve "
        f"{palavras_com_acento[palavra]!r}"
        for origem, palavra, sem_acento in todas
        if palavra == sem_acento and palavra in palavras_com_acento
    ]

    assert not achados, (
        "a mesma palavra aparece com e sem acento na aba Configurações:\n  "
        + "\n  ".join(sorted(set(achados)))
    )
