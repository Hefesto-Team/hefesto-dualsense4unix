#!/usr/bin/env python3
"""A RÉGUA DA ABA 06: o que o pacote manda tem onde cair, e o que cai é inteiro."""
from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

UNIQ = "aa:bb:cc:00:00:01"
FALSO = {"uniq": UNIQ, "player": 1, "connected": True, "transport": "bt",
         "battery_pct": 95, "is_primary": True, "inputs": {}, "audio": {},
         "speaker": {}}
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "BT", "cor": "starlight-blue", "mascara": "DualSense"}]

#: O estado do daemon como a aba o consome. Sem `keyboard_emulation` o pacote
ESTADO = {
    "active_profile": "regua",
    "mouse_emulation": {"enabled": False, "speed": 6, "scroll_speed": 1,
                        "bloqueio": "desligada", "despachando": False},
    "keyboard_emulation": {"enabled": True, "osk_disponivel": True},
    "controllers": [FALSO],
}

PAGINA = "06-navegacao.html"  # (noqa-acento) nome de arquivo
CAMPO = re.compile(r'data-(?:campo|papel|hef)="([^"]+)"')


def _perfil_de_mentira(monkeypatch, tmp_path, **campos):
    """Grava um perfil no disco e aponta a `pacotes.perfil` para ele."""
    from pacotes import perfil

    corpo = {"name": "Régua", "version": 1, "priority": 50,
             "match": {"type": "criteria"}}
    corpo.update(campos)
    (tmp_path / "regua.json").write_text(json.dumps(corpo), encoding="utf-8")
    monkeypatch.setattr(perfil, "pasta", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def aba(monkeypatch, tmp_path):
    """O pacote da 06 rodado contra o estado acima, com um perfil no disco."""
    import pacotes
    from pacotes import a06_navegacao

    _perfil_de_mentira(monkeypatch, tmp_path)
    ctx = pacotes.Contexto(state=ESTADO, mesa=MESA, conectados=[FALSO], estados={})
    bruto = a06_navegacao.pacote(ctx)
    pronto = pacotes.normalizar(bruto, {UNIQ: "p1"})
    for chave, valor in pacotes.topo(ctx).items():
        pronto["mesa"].setdefault(chave, valor)
    return ctx, a06_navegacao, pronto


def _enderecos(publicado: bool) -> set[str]:
    import onde

    return set(CAMPO.findall(
        onde.pagina(PAGINA, publicado=publicado).read_text(encoding="utf-8")))


def test_toda_chave_emitida_tem_endereco_ou_esta_declarada(aba):
    """Órfão calado é o defeito; órfão DECLARADO é inventário."""
    _, mod, pronto = aba
    emitidas = {k for k, v in pronto["mesa"].items() if not isinstance(v, (dict, list))}
    for campos in pronto["colunas"].values():
        emitidas |= {k for k, v in campos.items() if not isinstance(v, (dict, list))}
    emitidas |= {k for k, v in pronto["mesa"].items() if isinstance(v, (dict, list))}
    # O CABEÇALHO É DAS DEZ ABAS (`pacotes.topo`) e não é desta: cobrar dele
    import pacotes

    ctx, _, _ = aba
    do_topo = set(pacotes.topo(ctx))
    orfaos = emitidas - _enderecos(publicado=False) - do_topo - set(mod.SEM_ENDERECO)
    assert not orfaos, (
        f"o pacote da 06 manda {sorted(orfaos)} e o desenho de hoje "
        f"(`mockup/{PAGINA}`) não tem onde pôr.\n"
        "Ou o gerador marca o campo, ou a chave entra em `SEM_ENDERECO` com a "
        "razão medida. Emitir para o vazio não aparece na tela nem no portão — "
        "foi assim que `via` mandou metade de uma linha por uma leva inteira.")


def test_o_sem_endereco_nao_guarda_quem_ja_tem_casa(aba):
    """Declaração que envelheceu é a régua desligada sem ninguém decidir isso."""
    _, mod, _ = aba
    tem_casa = set(mod.SEM_ENDERECO) & _enderecos(publicado=False)
    assert not tem_casa, (
        f"{sorted(tem_casa)} está em `SEM_ENDERECO` e o desenho JÁ tem endereço "
        "para essas chaves — tire-as da lista e deixe a pintura acontecer.")


def test_as_vinte_e_uma_linhas_saem_do_perfil(monkeypatch, tmp_path):
    """O que o perfil guarda vence o de fábrica, linha a linha.

    A mordida: faça `_linhas_dos_botoes` ignorar `button_actions` — este teste
    reprova, porque a tela voltaria a mostrar o de fábrica com o perfil dizendo
    outra coisa. Era exatamente o estado de 02/09, e era o que fazia o "Guardar"
    apagar.
    """
    import pacotes
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes  # noqa: F401
    from pacotes import a06_navegacao

    _perfil_de_mentira(monkeypatch, tmp_path, button_actions={"cross": "KEY_ESC"})
    ctx = pacotes.Contexto(state=ESTADO, mesa=MESA, conectados=[FALSO], estados={})
    mesa = a06_navegacao.pacote(ctx)["mesa"]
    assert mesa["acao-cross"] == "Esc", (
        "a linha do X saiu do de fábrica, e o perfil manda `KEY_ESC` — a tela "
        "estaria mostrando o desenho no lugar da escolha dela.")
    assert mesa["acao-square"] == "Esc"
    # `core/keyboard_mappings.DEFAULT_BUTTON_BINDINGS["l3"]` é o `__TOGGLE_OSK__`.
    assert mesa["acao-l3"] == "Teclado na tela"


def test_todo_valor_emitido_existe_como_opcao_daquela_lista(aba):
    """`escrever()` com `data-hef-alvo="valor"` SE CALA quando o texto não casa."""
    import onde

    doc = onde.pagina(PAGINA, publicado=False).read_text(encoding="utf-8")
    _, _, pronto = aba
    for chave, valor in sorted(pronto["mesa"].items()):
        if not str(chave).startswith("acao-"):
            continue
        bloco = re.search(
            rf'<select[^>]*data-campo="{re.escape(str(chave))}"[^>]*>(.*?)</select>',
            doc, re.S)
        assert bloco, f"{chave}: o desenho não tem `<select>` com esse endereço"
        opcoes = set(re.findall(r"<option[^>]*>(.*?)</option>", bloco.group(1)))
        assert str(valor) in opcoes, (
            f"{chave}: o pacote manda {valor!r} e a lista do desenho não tem "
            f"essa opção — a pintura se calaria e o campo ficaria parado para "
            f"sempre.")


class _PerfilDeMentira:
    """O mínimo de um `Profile` que o "Guardar" toca, no idioma do pydantic."""

    def __init__(self, nome, button_actions=None, key_bindings=None):
        self.name = nome
        self.button_actions = button_actions
        self.key_bindings = key_bindings

    def model_copy(self, *, update):
        novo = _PerfilDeMentira(self.name, self.button_actions, self.key_bindings)
        for k, v in update.items():
            setattr(novo, k, v)
        return novo


@pytest.fixture
def disco(monkeypatch):
    """Um disco de mentira: guarda o que o gesto mandou gravar."""
    from hefesto_dualsense4unix.profiles import loader

    from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc

    gravados: list[_PerfilDeMentira] = []
    estado: dict[str, _PerfilDeMentira] = {}
    monkeypatch.setattr(loader, "load_profile", lambda n: estado[n], raising=False)
    monkeypatch.setattr(loader, "save_profile",
                        lambda prof, **_: gravados.append(prof), raising=False)

    def _pelo_gesto(_cartao, nome, muda, **_k):
        novo = muda(estado[nome])
        if novo is not None:
            estado[nome] = novo
            loader.save_profile(novo)
        return opc.JOGO, novo

    monkeypatch.setattr(opc, "gravar_pelo_gesto", _pelo_gesto)
    return estado, gravados


def _forma_de_fabrica(**trocas):
    """As 21 linhas como a tela publicada as mostra HOJE: o de fábrica inteiro."""
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    forma = {b: acoes.rotulo(a) for b, a in acoes.padrao().items()}
    forma.update(trocas)
    return forma


def test_o_nome_do_botao_e_o_do_motor_e_nao_uma_segunda_tabela():
    """Os nomes já existem no produto; escrevê-los de novo é o defeito."""
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes
    from hefesto_dualsense4unix.app.actions import input_actions
    from pacotes import a06_navegacao

    for botao in acoes.BOTOES:
        assert a06_navegacao._nome_do_botao(botao) == \
            input_actions.humanize_button(botao), (
            f"{botao}: o pacote respondeu um nome que o motor não deu — é a "
            "segunda tabela nascendo.")


def test_o_produto_nunca_esta_a_frente_do_desenho():
    """Endereço no publicado que a bancada não tem = alguém editou o produto."""
    a_mais = _enderecos(publicado=True) - _enderecos(publicado=False)
    assert not a_mais, (
        f"{sorted(a_mais)} existe na página publicada e não no desenho de hoje.")


class _PonteMuda:
    """Uma ponte que aceita tudo e não fala com daemon nenhum.

    A gravação do perfil é de disco (`profiles/loader`); o que a ponte faria é
    o `profile.switch` da reaplicação, e ele não é o que estes testes medem.
    """

    def __getattr__(self, _nome):
        return lambda *a, **k: True
