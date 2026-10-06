#!/usr/bin/env python3
"""A RÉGUA DA DECISÃO 5: as três palavras da "Função do teclado"."""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "06-navegacao.html"  # (noqa-acento) nome de arquivo

_SELECT = r'<select[^>]*data-campo="teclado-estado"[^>]*>(.*?)</select>'

OS_DOIS_MUNDOS = [
    pytest.param(True, id="a-pagina-publicada-de-hoje"),
    pytest.param(False, id="a-bancada-do-dia-da-publicacao"),
]


def _opcoes(publicado: bool) -> list[str]:
    """As `<option>` da "Função do teclado", LIDAS do HTML — nunca digitadas."""
    import onde

    doc = onde.pagina(PAGINA, publicado=publicado).read_text(encoding="utf-8")
    bloco = re.search(_SELECT, doc, re.S)
    assert bloco, f"não achei o `<select>` do teclado em {PAGINA} (publicado={publicado})"
    return re.findall(r"<option[^>]*>(.*?)</option>", bloco.group(1))


class _PonteQueAnota:
    """Aceita tudo e ANOTA. É o que separa "recusou" de "chamou e não disse".

    ELE RESPONDE PELO CORPO DESDE 03/09/2026, e a mudança é do contrato: o gesto
    passou de `chamar` (devolve `bool`, joga fora a resposta) para `resultado`
    (devolve o que o daemon disse), porque era o `bool` que fazia um
    `{"status": "failed"}` voltar como sucesso e a recusa não chegar à tela
    do usuário. O dublê devolve o `ok` do daemon de verdade — inclusive o bloco
    `keyboard_emulation`, que é o que o handler manda para a janela não precisar
    de uma segunda chamada (`daemon/ipc_handlers.py:3877`).

    O `chamar` FICA, e não é enfeite: ele prova que nenhum gesto desta aba
    voltou ao caminho que perde o motivo — se alguém reintroduzir um `p.chamar`,
    ele aparece em `self.chamadas` com o nome errado e o `assert` do método
    acusa.
    """

    def __init__(self, status: str = "ok", bloqueio: str | None = None) -> None:
        self.chamadas: list[tuple[str, dict]] = []
        self.status = status
        self.bloqueio = bloqueio

    def chamar(self, metodo: str, **params: object) -> bool:
        self.chamadas.append((metodo, dict(params)))
        return True

    def resultado(self, metodo: str, **params: object) -> dict:
        self.chamadas.append((metodo, dict(params)))
        bloco: dict[str, object] = {"enabled": bool(params.get("enabled"))}
        if self.bloqueio is not None:
            bloco["bloqueio"] = self.bloqueio
        return {"status": self.status,
                "enabled": bool(params.get("enabled")),
                "keyboard_emulation": bloco}


@pytest.fixture
def ctx():
    import pacotes

    return pacotes.Contexto(state={"active_profile": "regua"})


def test_as_tres_palavras_dela_estao_no_desenho():
    """O gerador e o pacote falam a MESMA lista, e ela é a dela."""
    import aba06
    from pacotes import a06_navegacao as mod

    assert aba06.OPCOES_TECLADO == [mod.TECLADO_SO_DENTRO, mod.TECLADO_SO_FORA,
                                    mod.TECLADO_DESATIVADO], (
        f"o desenho oferece {aba06.OPCOES_TECLADO} e o pacote fala outra "
        "língua — a lista pararia de ser pintada sem uma linha de erro.")
    assert aba06.TECLADO_PADRAO == mod.TECLADO_SO_FORA, (
        "a lista não nasce no padrão que ela escolheu")


def test_o_desenho_nasce_no_padrao_dela():
    """`Só fora do jogo` marcada, e é a única das três com dono hoje."""
    import onde
    from pacotes import a06_navegacao as mod

    doc = onde.pagina(PAGINA).read_text(encoding="utf-8")
    assert f"<option selected>{mod.TECLADO_SO_FORA}</option>" in doc
    for opcao in (mod.TECLADO_SO_DENTRO, mod.TECLADO_DESATIVADO):
        assert f"<option>{opcao}</option>" in doc, f"{opcao!r} sumiu do desenho"


@pytest.mark.parametrize("rotulo_e_bool", [("TECLADO_SO_FORA", True),
                                           ("TECLADO_DESATIVADO", False)])
def test_as_duas_com_dono_chamam_o_daemon(ctx, rotulo_e_bool):
    """Uma chamada, `keyboard.emulation.set`, e o bool que a opção quer dizer."""
    from pacotes import a06_navegacao as mod

    nome, esperado = rotulo_e_bool
    ponte = _PonteQueAnota()
    mod.teclado(ctx, {"valor": getattr(mod, nome)}, ponte)
    assert ponte.chamadas == [("keyboard.emulation.set", {"enabled": esperado})], (
        f"{nome}: o gesto chamou {ponte.chamadas}")


def test_a_terceira_recusa_dizendo_e_nao_chama_nada(ctx):
    """"Só dentro do jogo" não tem dono, e o botão DIZ isso."""
    from pacotes import a06_navegacao as mod

    ponte = _PonteQueAnota()
    with pytest.raises(RuntimeError) as caiu:
        mod.teclado(ctx, {"valor": mod.TECLADO_SO_DENTRO}, ponte)
    frase = str(caiu.value)
    assert mod.TECLADO_SO_DENTRO in frase, f"a recusa não diz qual opção: {frase!r}"
    assert mod.TECLADO_SO_FORA in frase, (
        "a recusa não diz o que o produto FAZ hoje, que é o outro lado — sem "
        f"isso ela é um 'não dá' sem saída: {frase!r}")
    assert not ponte.chamadas, f"recusou e ainda assim chamou {ponte.chamadas}"


def test_o_gesto_casa_pela_palavra_que_distingue(ctx):
    """Duas das três começam por "só" — casar pela primeira as confundiria."""
    from pacotes import a06_navegacao as mod

    ponte = _PonteQueAnota()
    mod.teclado(ctx, {"valor": "Só fora do jogo — o teclado vale no desktop"}, ponte)
    assert ponte.chamadas == [("keyboard.emulation.set", {"enabled": True})]

    with pytest.raises(RuntimeError):
        mod.teclado(ctx, {"valor": "Só dentro do jogo, e mais nada"},
                    _PonteQueAnota())

    for lixo in ("Modo turbo", "Só dentro do jogo e só fora do jogo"):
        with pytest.raises(ValueError, match="não reconheci"):
            mod.teclado(ctx, {"valor": lixo}, _PonteQueAnota())


@pytest.mark.parametrize("publicado", OS_DOIS_MUNDOS)
def test_toda_opcao_que_a_tela_oferece_tem_resposta(ctx, publicado):
    """A DIREÇÃO DO ATO: nenhuma opção da lista pode virar clique morto."""
    from pacotes import a06_navegacao as mod

    mudos = []
    for rotulo in _opcoes(publicado):
        ponte = _PonteQueAnota()
        try:
            mod.teclado(ctx, {"valor": rotulo}, ponte)
        except ValueError:
            mudos.append(rotulo)
        except RuntimeError:
            continue
        else:
            assert ponte.chamadas, f"{rotulo!r}: aceitou o clique e não chamou nada"
    assert not mudos, (
        f"a lista {'publicada' if publicado else 'da bancada'} oferece "
        f"{mudos} e o gesto levanta clique-inválido nelas. A frase de um "
        "`ValueError` NÃO chega ao cartão dela — `hefesto_vivo._recusou_dizendo` "
        "leva só a do `RuntimeError`, porque clique-inválido fala com quem "
        "programa. Então ela clica e nada acontece, sem uma palavra do porquê.")


@pytest.mark.parametrize("publicado", OS_DOIS_MUNDOS)
def test_a_pintura_diz_a_palavra_que_aquela_pagina_sabe_receber(publicado, monkeypatch):
    """A pintura acompanha a página CARREGADA, e não uma constante cravada."""
    import pacotes
    from pacotes import a06_navegacao as mod

    ofertas = frozenset(_opcoes(publicado))
    monkeypatch.setattr(mod, "_o_que_a_pagina_oferece", lambda: ofertas)
    dito = {}
    for ligado in (True, False):
        estado = {"active_profile": None,
                  "keyboard_emulation": {"enabled": ligado}}
        mesa = mod.pacote(pacotes.Contexto(state=estado))["mesa"]
        valor = mesa["teclado-estado"]
        assert valor in ofertas, (
            f"teclado {'ligado' if ligado else 'desligado'}: o pacote emite "
            f"{valor!r} e a lista desta página é {sorted(ofertas)} — a escrita "
            "seria descartada em silêncio e a tela ficaria na opção do desenho.")
        dito[ligado] = valor
    assert dito[True] != dito[False], (
        f"os dois estados dizem a mesma palavra ({dito[True]!r}) — a linha "
        "pararia de distinguir teclado ligado de desligado.")

    mudo = mod.pacote(pacotes.Contexto(state={"active_profile": None}))["mesa"]
    assert "teclado-estado" not in mudo, (
        "sem `keyboard_emulation` no estado, a tela afirmaria um estado que o "
        "daemon não disse")


def test_o_pacote_olha_mesmo_a_pagina_que_o_piloto_carrega():
    """SEM DUBLÊ NENHUM: o leitor real, contra o arquivo real."""
    from pacotes import a06_navegacao as mod

    mod._OFERTAS = None
    visto = mod._o_que_a_pagina_oferece()
    assert visto == frozenset(_opcoes(True)), (
        f"o pacote enxerga {sorted(visto)} e a página que o piloto carrega "
        f"oferece {_opcoes(True)}. Um leitor cego devolve a palavra dela em "
        "qualquer página, e volta o campo que afirma o contrário.")


def test_a_pintura_sem_duble_casa_com_a_pagina_do_produto():
    """A pintura de verdade, na página de verdade, nos dois estados do daemon."""
    import pacotes
    from pacotes import a06_navegacao as mod

    mod._OFERTAS = None
    ofertas = frozenset(_opcoes(True))
    for ligado in (True, False):
        estado = {"active_profile": None, "keyboard_emulation": {"enabled": ligado}}
        valor = mod.pacote(pacotes.Contexto(state=estado))["mesa"]["teclado-estado"]
        assert valor in ofertas, (
            f"teclado {'ligado' if ligado else 'desligado'}: o pacote emitiria "
            f"{valor!r} na página do produto, que oferece {sorted(ofertas)}.")


@pytest.mark.parametrize("publicado", OS_DOIS_MUNDOS)
def test_a_palavra_que_a_tela_diz_e_a_que_o_clique_devolve(ctx, publicado, monkeypatch):
    """A IDA E VOLTA: o que a linha AFIRMA e o que o clique nela FAZ são o mesmo."""
    from pacotes import a06_navegacao as mod

    import pacotes

    monkeypatch.setattr(mod, "_o_que_a_pagina_oferece",
                        lambda: frozenset(_opcoes(publicado)))
    for ligado in (True, False):
        estado = {"active_profile": None, "keyboard_emulation": {"enabled": ligado}}
        palavra = mod.pacote(pacotes.Contexto(state=estado))["mesa"]["teclado-estado"]
        ponte = _PonteQueAnota()
        mod.teclado(ctx, {"valor": palavra}, ponte)
        assert ponte.chamadas == [("keyboard.emulation.set", {"enabled": ligado})], (
            f"com o teclado {'ligado' if ligado else 'desligado'} a tela diz "
            f"{palavra!r}, e clicar nessa mesma palavra manda "
            f"{ponte.chamadas} — a linha afirma um estado e o clique nela faz "
            "outro.")


def test_a_travessia_acabou_e_nao_deixou_lapide():
    """A régua que existia para ficar vermelha CUMPRIU — e virou esta."""
    from pacotes import a06_navegacao as mod

    assert not hasattr(mod, "SINONIMOS_ATE_A_PUBLICACAO"), (
        "`SINONIMOS_ATE_A_PUBLICACAO` voltou. Ele só se justifica enquanto a "
        "bancada e o publicado divergirem nos rótulos — e neste caso ele vem "
        "com a régua que o apaga no dia da publicação, como a anterior tinha.")
    for mundo, publicado in (("publicada", True), ("bancada", False)):
        texto = " ".join(_opcoes(publicado)).lower()
        for palavra in mod._ESCOLHA:
            assert palavra in texto, (
                f"o gesto entende {palavra!r} e a página {mundo} não a oferece "
                f"({_opcoes(publicado)}) — ou é tradução sem prazo, ou é a "
                "bancada tendo andado sem ninguém perguntar o que a tela dela "
                "mostra hoje.")
