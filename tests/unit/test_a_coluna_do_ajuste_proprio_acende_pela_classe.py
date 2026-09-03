"""A coluna "Ajuste próprio" da aba Perfis acende por CLASSE — e só quando pode.

**O QUE ESTAVA ERRADO, e são dezesseis células da tabela ``Controle / Ajuste
próprio / ID da peça``.** Cada linha tem quatro ``<span class="gr">``, um por
seção que o perfil sabe guardar por controle (luz · gatilhos · vibração ·
alto-falante). Aceso é ``.gr.on``; apagado é ``.gr``. Nenhum dos cinco alvos do
pintor até 02/09/2026 (texto · largura · fundo · valor · html) alcançava uma
CLASSE, então o endereço vivia em ``a10_perfis.NAO_PINTAVEIS`` e **a coluna
mostrava o desenho para todo perfil**: a régua do mockup acusava 16 dos 17
campos que faltavam nesta aba.

**AS TRÊS COISAS QUE ESTE ARQUIVO GUARDA:**

1. **O DESENHO DECLARA O ALVO.** ``aba10.linha_do_controle`` escreve
   ``data-hef-alvo="classe"`` nos dezesseis ``<span>``, e a bancada sai com ele.

2. **O PACOTE MANDA O ESTADO, não o nome da seção.** A emissão era
   ``[s for g in guarda for s in (g.get("secoes") or [])]`` — iterar um ``dict``
   devolve as CHAVES. Com dois controles na mesa ela dava
   ``["leds","triggers","rumble","speaker"] * 2`` para QUALQUER perfil, e como
   ``ligado("leds")`` é verdadeiro isso teria acendido as quatro seções nos
   quatro controles. O defeito viveu escondido atrás de ``NAO_PINTAVEIS``: uma
   emissão que ninguém pinta é uma emissão que ninguém confere.

3. **A CURA VALE NOS DOIS MUNDOS.** ``--publicar-enderecos 10`` RECUSOU — a
   ferramenta é por PÁGINA e esta já carregava uma mudança de desenho pendente
   (a opção ``—`` do Estilo de Jogo, decisão dela). Então o pacote **pergunta à
   página publicada** se ela traz o atributo, e cala enquanto não trouxer:
   escrever texto num ``<span>`` com um ``<svg>`` dentro apaga o glifo, dezesseis
   vezes, duas vezes por segundo.

**E POR QUE A CLASSE BASTA — medido, não suposto:** ``monta.glifo(p,
ativo=True)`` e ``monta.glifo(p, ativo=False)`` devolvem bytes IDÊNTICOS para as
sete peças destas quatro seções. Os arquivos ``X.svg`` e ``X_active.svg`` só
diferem no traço (``#f8f8f2`` contra ``#bd93f9``) e ``glifo`` troca os dois por
``currentColor``. Logo a diferença visível inteira entre aceso e apagado é o
``color`` que ``.gr.on`` dá ao ``<span>`` — trocar a classe é a cura COMPLETA.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import perfis_web
from hefesto_dualsense4unix.interface import onde, regua_do_mockup
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis

#: A MESA DA RÉGUA — dois controles, com os endereços MASCARADOS (octetos 4 e 5
#: zerados). Nenhum endereço real de rádio entra em arquivo versionado.
MESA = [
    {"pref": "p1", "uniq": "aabbcc000001", "jogador": 1, "cor": "cosmic-red",
     "nome": "Cosmic Red", "via": "BT", "transporte": "bt", "alvo": True,
     "mascara": "DualSense"},
    {"pref": "p2", "uniq": "aabbcc000002", "jogador": 2, "cor": "starlight-blue",
     "nome": "Starlight Blue", "via": "USB", "transporte": "usb", "alvo": False,
     "mascara": "DualSense"},
]


def _gerador() -> Any:
    """O ``aba10.py`` importado como o gerador se importa — só no TESTE.

    Ele insere a própria pasta no ``sys.path`` e lê o ``monta``, que abre seis
    arquivos do repositório no import. É barato aqui e é justamente o que o
    produto não pode fazer — por isso o pacote copia a forma em vez de importar.
    """
    pytest.importorskip(
        "hefesto_dualsense4unix.interface.monta",
        reason="o gerador lê o repositório no import; num pacote instalado não há",
    )
    pasta = Path(onde.__file__).parent
    if str(pasta) not in sys.path:
        sys.path.insert(0, str(pasta))
    import aba10  # type: ignore[import-not-found]

    return aba10


def _perfil(**overrides: Any) -> Any:
    """Um perfil de disco com ajuste próprio SÓ do primeiro controle.

    O DISCO NÃO SERVE: a ``tests/conftest.py`` põe
    ``HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1`` em todo teste, e
    ``load_all_profiles()`` devolve **zero** perfis nesta suíte. Sem dublê,
    ``pacote_da_aba`` devolveria ``guarda=[]`` e a tabela nunca seria medida —
    verde por vacuidade.
    """
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        MatchAny,
        Profile,
    )

    return Profile(
        name="régua", match=MatchAny(),
        controllers={MESA[0]["uniq"]: ControllerOverrides(**overrides)},
    )


@pytest.fixture(autouse=True)
def _lar(monkeypatch: pytest.MonkeyPatch) -> None:
    """O perfil da régua no lugar da pasta dela, e a resposta da página LIMPA.

    ``_SECAO_POR_CLASSE`` é estado de módulo (a página publicada é lida uma vez
    por processo). Sem zerá-lo, um teste herdaria a resposta do anterior — que é
    pior que não ter prova nenhuma.
    """
    from hefesto_dualsense4unix.profiles import loader

    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_SECAO_POR_CLASSE", None, raising=False)
    monkeypatch.setattr(loader, "load_all_profiles",
                        lambda *a, **k: [_perfil(rumble={"policy": "economia"})])


def _emitidos(**overrides: Any) -> dict[str, Any]:
    """O que ``a10_perfis.pacote()`` manda pintar, com a mesa de dois."""
    from hefesto_dualsense4unix.profiles import loader

    if overrides:
        alvo = _perfil(**overrides)
        loader.load_all_profiles = lambda *a, **k: [alvo]  # type: ignore[assignment]
    ctx = Contexto(state={"active_profile": "régua"}, mesa=list(MESA),
                   conectados=list(MESA), estados={})
    return a10_perfis.pacote(ctx)


# ---------------------------------------------------------------------------
# 1. O DESENHO DECLARA O ALVO
# ---------------------------------------------------------------------------
def test_a_bancada_declara_o_alvo_classe_nas_dezesseis_celulas() -> None:
    """Sem ``data-hef-alvo="classe"`` o pintor cai no ramo padrão e apaga o SVG.

    MORDIDA: tire o ``data-hef-alvo="classe"`` de
    ``aba10.linha_do_controle`` e este teste reprova dizendo quantas células
    ficaram sem alvo.
    """
    html = onde.pagina("10-perfis.html").read_text(encoding="utf-8")
    celulas = re.findall(r'<span[^>]*data-hef="guarda\.secao"[^>]*>', html)
    assert len(celulas) == 16, (
        f"a tabela da guarda tem {len(celulas)} células endereçadas, e o "
        "desenho dela são quatro linhas de quatro seções")
    sem_alvo = [c for c in celulas if 'data-hef-alvo="classe"' not in c]
    assert not sem_alvo, (
        f"{len(sem_alvo)} de 16 células de `guarda.secao` não declaram "
        "`data-hef-alvo=\"classe\"` — o pintor escreveria TEXTO nelas e o "
        "`el.textContent` apagaria o glifo SVG de dentro")


def test_o_glifo_aceso_e_o_apagado_sao_o_mesmo_desenho() -> None:
    """A classe é a cura COMPLETA, e é isto que o prova.

    Se um dia o par ``X_active.svg`` passar a ter FORMA diferente (e não só cor),
    trocar a classe deixaria de bastar: a célula acenderia com o desenho errado
    dentro. Esta régua reprova nesse dia, antes de a tela mentir.

    MORDIDA: mude um ``<rect>`` de ``assets/glyphs/lightbar_active.svg`` e ela
    reprova nomeando a peça.
    """
    aba10 = _gerador()
    from hefesto_dualsense4unix.interface import monta

    diferentes = [
        peca
        for _campo, pecas, _dica in aba10.SECOES
        for peca in pecas
        if monta.glifo(peca, ativo=True, tam=15) != monta.glifo(peca, ativo=False,
                                                               tam=15)
    ]
    assert not diferentes, (
        f"o glifo aceso e o apagado divergem em {diferentes} — a classe deixou "
        "de ser a diferença inteira, e pintar só ela mostraria a forma errada")


# ---------------------------------------------------------------------------
# 2. A ORDEM É O CONTRATO
# ---------------------------------------------------------------------------
def test_o_produtor_e_o_desenho_dizem_as_quatro_secoes_na_mesma_ordem() -> None:
    """O piloto distribui a lista pelos elementos na ordem do DOM.

    ``perfis_web.SECOES_POR_CONTROLE`` decide a ordem dos VALORES e
    ``aba10.SECOES`` a das CÉLULAS. Se as duas discordarem, a tela acende a luz
    onde a vibração está guardada — e nada acusa, porque o número de valores
    continua batendo.

    MORDIDA: troque duas linhas de ``aba10.SECOES`` (ou de
    ``SECOES_POR_CONTROLE``) e este teste reprova mostrando as duas sequências.
    """
    aba10 = _gerador()
    do_desenho = tuple(campo for campo, _pecas, _dica in aba10.SECOES)
    assert do_desenho == perfis_web.SECOES_POR_CONTROLE, (
        "o desenho e o produto discordam na ordem das seções:\n"
        f"  desenho (aba10.SECOES)         {do_desenho}\n"
        f"  produto (SECOES_POR_CONTROLE)  {perfis_web.SECOES_POR_CONTROLE}")


# ---------------------------------------------------------------------------
# 3. O PACOTE MANDA O ESTADO, e não o nome da seção
# ---------------------------------------------------------------------------
def test_a_emissao_e_o_estado_de_cada_secao_e_nao_o_nome_dela(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O defeito que ``NAO_PINTAVEIS`` escondia — e ele acenderia tudo.

    Com o perfil guardando SÓ a vibração do primeiro controle, a coluna tem de
    dizer: apagado, apagado, ACESO, apagado · e quatro apagados no segundo.

    MORDIDA: volte a ``[s for g in guarda for s in (g.get("secoes") or [])]`` e
    este teste reprova com ``['leds', 'triggers', …]`` no lugar dos oito
    booleanos.
    """
    monkeypatch.setattr(a10_perfis, "_SECAO_POR_CLASSE", True, raising=False)
    fora = _emitidos(rumble={"policy": "economia"})
    assert fora["guarda.secao"] == [False, False, True, False,
                                    False, False, False, False], (
        f"a coluna não conta o que o perfil guarda: {fora['guarda.secao']!r}")

    # E O QUE A TELA FARIA COM ISSO — a mesma lista que o `ligado()` do JS lê.
    acesos = [regua_do_mockup._ligado(str(v)) for v in fora["guarda.secao"]]
    assert acesos == [False, False, True, False, False, False, False, False], (
        "o que o pacote emite não é lido como aceso/apagado pelo alvo `classe`")


def test_cada_secao_guardada_acende_a_sua_celula_e_so_a_dela(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uma seção de cada vez, e a célula que acende é sempre a mesma posição.

    É a régua que pega uma ordem trocada NO PRODUTO (o dicionário de
    ``_secoes_do_controle``), que a régua de ordem acima não alcança: lá se
    comparam duas listas de nomes, aqui se compara o VALOR com a POSIÇÃO.
    """
    monkeypatch.setattr(a10_perfis, "_SECAO_POR_CLASSE", True, raising=False)
    # O MENOR CORPO QUE CADA SEÇÃO ACEITA. O contrato de `ControllerOverrides`
    # é *"campo `None` = sem opinião"*, e `_secoes_do_controle` pergunta
    # exatamente `is not None` — o conteúdo não importa aqui. Três das quatro
    # aceitam `{}`; o `speaker` exige `volume`, e a razão está no próprio
    # schema (SOM-02: `muted` sem `volume` mandaria volume ZERO e tomaria a
    # posse do alto-falante).
    minimo: dict[str, dict[str, Any]] = {
        "leds": {}, "triggers": {}, "rumble": {}, "speaker": {"volume": 40},
    }
    for posicao, secao in enumerate(perfis_web.SECOES_POR_CONTROLE):
        fora = _emitidos(**{secao: minimo[secao]})
        esperado = [i == posicao for i in range(4)] + [False] * 4
        assert fora["guarda.secao"] == esperado, (
            f"com só `{secao}` guardado, a coluna acendeu "
            f"{fora['guarda.secao']!r} em vez de {esperado!r}")


# ---------------------------------------------------------------------------
# 4. A CURA VALE NOS DOIS MUNDOS
# ---------------------------------------------------------------------------
def _pagina_de_mentira(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                       com_alvo: bool) -> None:
    """Põe no lugar da página publicada uma com — ou sem — o alvo declarado."""
    alvo = ' data-hef-alvo="classe"' if com_alvo else ""
    arquivo = tmp_path / "10-perfis.html"
    arquivo.write_text(
        f'<span class="gr on" data-hef="guarda.secao"{alvo}'
        f' data-hef-secao="leds"><svg></svg></span>', encoding="utf-8")
    verdadeiro = onde.pagina
    monkeypatch.setattr(
        onde, "pagina",  # (noqa-acento) nome de função
        lambda nome, publicado=False: (
            arquivo if (publicado and nome == a10_perfis.PAGINA)
            else verdadeiro(nome, publicado)))
    monkeypatch.setattr(a10_perfis, "_SECAO_POR_CLASSE", None, raising=False)


def test_sem_o_alvo_na_pagina_publicada_o_pacote_cala(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enquanto ela não publicar, escrever ali apagaria dezesseis glifos.

    MORDIDA: tire o ``if _a_pagina_acende_a_secao_por_classe():`` de
    ``a10_perfis.pacote`` e este teste reprova — o pacote passa a emitir para
    uma página que só sabe receber TEXTO.
    """
    _pagina_de_mentira(tmp_path, monkeypatch, com_alvo=False)
    assert a10_perfis._a_pagina_acende_a_secao_por_classe() is False
    assert "guarda.secao" not in _emitidos(), (
        "o pacote emitiu `guarda.secao` para uma página publicada SEM "
        "`data-hef-alvo=\"classe\"` — o pintor escreveria texto nos dezesseis "
        "`<span>` e o `el.textContent` apagaria o glifo SVG de cada um")


def test_com_o_alvo_na_pagina_publicada_o_pacote_escreve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O outro lado, e sem ele a guarda acima seria silêncio para sempre.

    No tique seguinte ao ``--publicar 10`` dela as dezesseis células passam a
    receber o estado — sem ninguém tocar em código.
    """
    _pagina_de_mentira(tmp_path, monkeypatch, com_alvo=True)
    assert a10_perfis._a_pagina_acende_a_secao_por_classe() is True
    fora = _emitidos(rumble={"policy": "economia"})
    assert fora["guarda.secao"] == [False, False, True, False,
                                    False, False, False, False]


def test_a_pergunta_e_feita_a_pagina_publicada_e_nao_a_bancada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O piloto abre SEMPRE o publicado; medir a bancada é verde sobre o futuro.

    É a armadilha nomeada em ``onde.pagina``: *"apontá-lo para o publicado o
    faria dar verde sobre a página congelada"* — aqui o erro é o inverso e é o
    que derrubou três frentes em 02/09, medir a BANCADA e o produto renderizar
    outra coisa.

    MORDIDA: troque ``publicado=True`` por ``publicado=False`` em
    ``_a_pagina_acende_a_secao_por_classe`` e este teste reprova.
    """
    _pagina_de_mentira(tmp_path, monkeypatch, com_alvo=False)
    # A BANCADA DE VERDADE JÁ TEM O ALVO — é isto que separa as duas perguntas.
    bancada = onde.pagina("10-perfis.html", publicado=False).read_text(
        encoding="utf-8")
    assert 'data-hef-alvo="classe"' in bancada, (
        "a bancada perdeu o alvo; sem ele esta régua não separa nada")
    assert a10_perfis._a_pagina_acende_a_secao_por_classe() is False, (
        "o pacote respondeu pela BANCADA — no dia em que o desenho anda à "
        "frente do produto, é a tela dela que paga")


def test_pagina_ilegivel_responde_que_nao(monkeypatch: pytest.MonkeyPatch) -> None:
    """O erro seguro é não escrever: uma página que não abre não sabe receber."""

    def _explode(nome: str, publicado: bool = False) -> Path:
        raise OSError("a página sumiu")

    monkeypatch.setattr(onde, "pagina", _explode)  # (noqa-acento) nome de função
    monkeypatch.setattr(a10_perfis, "_SECAO_POR_CLASSE", None, raising=False)
    assert a10_perfis._a_pagina_acende_a_secao_por_classe() is False


def test_o_endereco_saiu_de_nao_pintaveis_e_nao_voltou_calado() -> None:
    """``guarda.secao`` não é mais um nome cravado — quem decide é a MEDIÇÃO.

    Se alguém o devolver a ``NAO_PINTAVEIS``, o ``pop`` do fim de ``pacote()``
    apagaria a emissão mesmo depois de ela publicar, e as dezesseis células
    voltariam a mostrar o desenho — calado, porque nada mais acusa.
    """
    assert "guarda.secao" not in a10_perfis.NAO_PINTAVEIS, (
        "`guarda.secao` voltou a `NAO_PINTAVEIS`; quem decide hoje é "
        "`_a_pagina_acende_a_secao_por_classe()`, que se cura sozinha no dia "
        "do `--publicar 10`")
