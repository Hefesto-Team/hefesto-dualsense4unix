"""O portão de redação da aba Configurações — sobre a aba MONTADA, não o XML."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

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

from tests.unit.aba_config_sem_a_janela import (
    FOLGA_DO_AMBIENTE,
    FRASES_DO_ESPELHO,
    PISO_DA_COLHEITA,
    PISO_POR_SECAO,
    SECOES_NO_GLADE,
    HospedeiroDaAbaConfig,
    aba_config_montada,
    textos_da_arvore,
)

RAIZ = Path(__file__).resolve().parents[2]


def _validador() -> Any:
    """O `validar-palavra-de-tela.py` importado como módulo."""
    caminho = RAIZ / "scripts" / "validar-palavra-de-tela.py"
    spec = importlib.util.spec_from_file_location("_validador_de_tela", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["_validador_de_tela"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _aba_montada() -> Any:
    """Monta a aba em CÓDIGO e devolve a caixa — o berço saiu do glade.

    06/09/2026 (`GTK-3`): esta função abria o `gui/main.glade` só para pegar a
    caixa vazia `tab_config_box`; as cinco seções sempre nasceram em código. Com
    o XML apagado, o berço é `tests/unit/aba_config_sem_a_janela.py`, e ele
    entrega os DOIS widgets que as seções pedem — a caixa e o
    `daemon_autostart_switch`. A colheita foi conferida contra o glade
    restaurado do git — os dois lados deram o mesmo número —, e
    `test_o_berco_nao_e_mais_frouxo_que_o_glade` reprova se ela encolher.

    O NÚMERO SAIU DAQUI EM 08/09/2026, e o de lá também caducou. Era "199 textos
    dos dois lados"; virou 189 solto e 186 sob a suíte, pelo censo do gabinete.
    Desde 13/09/2026 o berço monta sobre uma bancada FIXA e são 190 em todo
    ambiente medido — ver `aba_config_sem_a_janela.FOLGA_DO_AMBIENTE`.

    A RAZÃO QUE ESTAVA ESCRITA AQUI TAMBÉM CAIU: dizia que a colheita cresce
    com os controles ligados, porque "Os controles" monta um card por controle.
    Medido em 08/09/2026 com QUATRO DualSense adotados, a seção montou os
    mesmos 8 textos do estado vazio — este berço não tem `_controles_leitor` e
    o pedido que sobrava era assíncrono. Desde 13/09 ele nem sai.
    """
    return aba_config_montada()


def _textos_da_arvore(raiz: Any) -> list[tuple[str, str]]:
    """Todo texto visível da árvore, como `(origem, texto)`."""
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


def test_o_berco_nao_e_mais_frouxo_que_o_glade() -> None:
    """O berço em código entrega a MESMA aba que o `main.glade` entregava."""
    caixa = _aba_montada()
    assert len(caixa.get_children()) == SECOES_NO_GLADE, (
        f"a aba montou {len(caixa.get_children())} seções e o glade dava "
        f"{SECOES_NO_GLADE} — o berço perdeu uma seção"
    )
    colhidos = textos_da_arvore(caixa)
    for frase in FRASES_DO_ESPELHO:
        assert frase in colhidos, (
            f"a linha do espelho sumiu da aba: {frase!r} não foi colhida. É o "
            "sintoma exato de `BercoDaAbaConfig` não entregar o widget que a "
            "seção pede — a linha some sem levantar, e as três réguas desta "
            "aba passam a medir menos sem nada acusar."
        )

    for moldura in caixa.get_children():
        rotulo = getattr(moldura, "get_label", lambda: None)() or "?"
        quantos = len(textos_da_arvore(moldura))
        assert quantos >= PISO_POR_SECAO, (
            f"a seção {rotulo!r} montou com {quantos} textos — ela subiu oca, "
            "e o total das outras quatro esconderia a causa"
        )

    assert len(colhidos) >= PISO_DA_COLHEITA, (
        f"o berço colheu {len(colhidos)} textos, abaixo do piso de "
        f"{PISO_DA_COLHEITA}: uma seção perdeu conteúdo sem esvaziar. Dê ao "
        "`BercoDaAbaConfig` o widget que ela pede, ou confira se a bancada do "
        "berço continua sendo a que o piso mediu."
    )


def test_a_folga_do_piso_tem_tamanho_medido() -> None:
    """A folga entre a colheita e o piso é a do AMBIENTE, e nada além."""
    colhidos = len(textos_da_arvore(_aba_montada()))
    folga = colhidos - PISO_DA_COLHEITA

    assert folga >= 0, (
        f"a aba colheu {colhidos} textos e o piso é {PISO_DA_COLHEITA}: "
        f"faltam {-folga}. Ou sumiu texto da tela, ou o piso subiu sem a "
        "colheita subir junto."
    )
    assert folga <= FOLGA_DO_AMBIENTE, (
        f"a aba colheu {colhidos} textos contra um piso de {PISO_DA_COLHEITA}: "
        f"{folga} de folga, e o ambiente explica {FOLGA_DO_AMBIENTE} desde que o "
        "berço fixa a bancada. Folga sem fonte é piso comprado — uma seção pode "
        "perder metade do conteúdo e atravessar. Se a aba ganhou texto, suba o "
        "`PISO_DA_COLHEITA` junto e diga na nota dele o que entrou."
    )


def test_a_colheita_nao_le_o_sys_nem_pergunta_ao_daemon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A régua mede a ABA, e não a máquina de quem roda — BERCO-SEM-A-BANCADA-01."""
    from hefesto_dualsense4unix.app import ipc_bridge
    from hefesto_dualsense4unix.app.actions.config import secao_controles, secao_mesa

    chamadas: list[str] = []

    def _que_levanta(nome: str) -> Any:
        def _duble(*_args: Any, **_kwargs: Any) -> Any:
            chamadas.append(nome)
            raise AssertionError(f"a colheita chamou {nome}")

        return _duble

    for nome in ("ler_a_mesa", "ler_o_barramento", "listar_entradas", "ler_do_disco"):
        monkeypatch.setattr(secao_mesa, nome, _que_levanta(nome))
    monkeypatch.setattr(secao_controles, "call_async", _que_levanta("call_async"))
    monkeypatch.setattr(ipc_bridge, "call_async", _que_levanta("call_async"))

    colhidos = textos_da_arvore(_aba_montada())

    assert not chamadas, (
        f"a colheita da aba passou por {chamadas}: ela está lendo a máquina de "
        "quem roda a suíte, e o piso volta a medir a bancada. Injete o leitor "
        "que falta em `HospedeiroDaAbaConfig`, no molde dos que já estão lá."
    )
    assert len(colhidos) >= PISO_DA_COLHEITA, (
        f"com os leitores vivos proibidos a aba colheu {len(colhidos)} textos, "
        f"abaixo do piso de {PISO_DA_COLHEITA}. Se as duas réguas de piso acima "
        "também reprovaram, a aba perdeu texto; se só esta, a bancada do berço "
        "passa por uma leitura que ela não devia fazer."
    )


def test_a_cor_do_plastico_nao_e_perguntada_ao_aparelho(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Com controle na aba, a cor do plástico vem do berço, e não do `/sys`."""
    from hefesto_dualsense4unix.app.actions.config import secao_controles

    chamadas: list[str] = []
    perguntas: list[str] = []

    def _ler_pelo_cabo_que_levanta(uniq: str) -> Any:
        chamadas.append("ler_pelo_cabo")
        raise AssertionError(f"a aba perguntou a cor de {uniq} ao aparelho")

    def _na_hora(fn: Any, ao_chegar: Any, ao_falhar: Any = None) -> None:
        try:
            resultado = fn()
        except Exception as exc:
            if ao_falhar is not None:
                ao_falhar(exc)
            return
        ao_chegar(resultado)

    original = secao_controles._pergunta_de_cor

    def _pergunta_contada(uniq: str, ler: Any) -> Any:
        perguntas.append(uniq)
        return original(uniq, ler)

    monkeypatch.setattr(secao_controles, "ler_pelo_cabo", _ler_pelo_cabo_que_levanta)
    monkeypatch.setattr(secao_controles, "run_in_thread", _na_hora)
    monkeypatch.setattr(secao_controles, "_pergunta_de_cor", _pergunta_contada)

    class _ComControles(HospedeiroDaAbaConfig):
        def __init__(self) -> None:
            super().__init__()
            self._controles_leitor = lambda: {
                "controllers": [
                    {
                        "uniq": "aa:bb:cc:00:00:01",
                        "connected": True,
                        "transport": "usb",
                        "player_slot": 1,
                    },
                    {
                        "uniq": "aa:bb:cc:00:00:02",
                        "connected": True,
                        "transport": "bt",
                        "player_slot": 2,
                    },
                ]
            }

    _ComControles().install_config_tab()

    assert len(perguntas) == 2, (
        f"a seção perguntou a cor de {len(perguntas)} controles, e são dois: a "
        "régua não percorreu o caminho que ela vigia"
    )
    assert not chamadas, (
        f"a aba montada no berço perguntou a cor ao aparelho: {chamadas}. É "
        "leitura de `/sys/class/hidraw` da máquina de quem roda — o berço tem de "
        "trazer o `_cor_do_plastico_leitor`."
    )


def test_todo_rotulo_da_aba_comeca_em_maiuscula() -> None:
    """Rótulo, opção e título começam com maiúscula."""
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


#: pagou em 13/08 com o `portao_a_casa_sabe_e_o_produto_nao_faz`. A isenção é
PARES_LEGITIMOS: frozenset[tuple[str, str]] = frozenset(
    {
        ("tem", "têm"),
        ("vem", "vêm"),
        ("contem", "contêm"),
        ("mantem", "mantêm"),
    }
)


def test_o_texto_da_aba_esta_acentuado() -> None:
    """Português do Brasil escrito certo, na tela como no fonte."""
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
        if palavra == sem_acento
        and palavra in palavras_com_acento
        and (palavra, palavras_com_acento[palavra]) not in PARES_LEGITIMOS
    ]

    assert not achados, (
        "a mesma palavra aparece com e sem acento na aba Configurações:\n  "
        + "\n  ".join(sorted(set(achados)))
    )
