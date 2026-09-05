"""A coluna "Ajuste próprio" da aba Perfis acende por CLASSE, e com o dado DELA.

**O QUE ESTAVA ERRADO, e é a tabela ``Controle / Ajuste próprio / ID da
peça``.** Cada linha tem um ``<span class="gr">`` por seção que o perfil sabe
guardar daquele controle (luz · gatilhos · vibração · alto-falante · microfone).
Aceso é ``.gr.on``; apagado é ``.gr``. Nenhum dos cinco alvos do pintor até
02/09/2026 (texto · largura · fundo · valor · html) alcançava uma CLASSE, então
o endereço vivia em ``a10_perfis.NAO_PINTAVEIS`` e **a coluna mostrava o desenho
para todo perfil**: a régua do mockup acusava 16 dos 17 campos daquela aba.

**AS DUAS COISAS QUE ESTE ARQUIVO GUARDA:**

1. **O DESENHO DECLARA O ALVO.** ``aba10.linha_do_controle`` escreve
   ``data-hef-alvo="classe"`` em toda célula, e a bancada sai com ele.

2. **O PACOTE MANDA O ESTADO, não o nome da seção.** A emissão era
   ``[s for g in guarda for s in (g.get("secoes") or [])]`` — iterar um ``dict``
   devolve as CHAVES. Com dois controles na mesa ela dava
   ``["leds","triggers","rumble","speaker"] * 2`` para QUALQUER perfil, e como
   ``ligado("leds")`` é verdadeiro isso teria acendido tudo para todo mundo. O
   defeito viveu escondido atrás de ``NAO_PINTAVEIS``: uma emissão que ninguém
   pinta é uma emissão que ninguém confere.

**E POR QUE A CLASSE BASTA — medido, não suposto:** ``monta.glifo(p,
ativo=True)`` e ``monta.glifo(p, ativo=False)`` devolvem bytes IDÊNTICOS para as
peças destas seções. Os arquivos ``X.svg`` e ``X_active.svg`` só diferem no
traço (``#f8f8f2`` contra ``#bd93f9``) e ``glifo`` troca os dois por
``currentColor``. Logo a diferença visível inteira entre aceso e apagado é o
``color`` que ``.gr.on`` dá ao ``<span>`` — trocar a classe é a cura COMPLETA.

O DIA EM QUE ESTE ARQUIVO INTEIRO MORREU — 03/09/2026
------------------------------------------------------
Ele nasceu em ``c3712efb`` (02/09, 23h38) e ``7e64c2e3`` (03/09, 02h56) mudou
por baixo dele TRÊS contratos sem tocá-lo. **Nove dos dez testes pararam de
rodar** — não de reprovar: ``ValueError``, ``AttributeError`` e um ``20 == 16``:

- ``aba10.SECOES`` virou um PAR (era ``campo, pecas, dica``); a decisão nº4 dela
  tirou as oito dicas das células;
- ``_a_pagina_acende_a_secao_por_classe`` foi REMOVIDA, com razão — ver a nota
  datada na seção 4;
- a página passou de 16 para 20 células, e três asserções cravavam o 16 e o 4.

**E foi sob esta régua morta que a coluna do microfone ficou apagada à força por
um dia**: ``ControllerOverrides`` ganhou o campo ``mic`` às 02h50 e o produto
continuou emitindo quatro chaves, porque ``SECOES_POR_CONTROLE`` era digitada.
As três asserções cravadas foram trocadas por leituras do gerador — a régua que
digita o que devia LER é a forma de instrumento falso que esta casa já pagou
onze vezes, e aqui ela cobrou duas: reprovava a melhora e morria com ela.
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
def test_a_bancada_declara_o_alvo_classe_em_toda_celula() -> None:
    """Sem ``data-hef-alvo="classe"`` o pintor cai no ramo padrão e apaga o SVG.

    O NÚMERO É LIDO, E NÃO DIGITADO — 03/09/2026. Esta régua se chamava
    ``…_nas_dezesseis_celulas`` e cravava ``== 16``. No dia em que a decisão
    nº20 dela pôs a quinta coluna, ela passou a reprovar a MELHORA: *"a tabela
    tem 20 células, e o desenho dela são quatro linhas de quatro seções"* — a
    régua digitando o que devia LER, que é a forma de instrumento falso que esta
    casa já pagou onze vezes. O número sai agora do gerador.

    MORDIDA: tire o ``data-hef-alvo="classe"`` de ``aba10.linha_do_controle`` e
    este teste reprova dizendo quantas células ficaram sem alvo.
    """
    aba10 = _gerador()
    esperado = len(aba10.MESA) * len(aba10.SECOES)
    html = onde.pagina("10-perfis.html").read_text(encoding="utf-8")
    celulas = re.findall(r'<span[^>]*data-hef="guarda\.secao"[^>]*>', html)
    assert len(celulas) == esperado, (
        f"a tabela da guarda tem {len(celulas)} células endereçadas, e o "
        f"desenho são {len(aba10.MESA)} linhas de {len(aba10.SECOES)} seções "
        f"({esperado})")
    sem_alvo = [c for c in celulas if 'data-hef-alvo="classe"' not in c]
    assert not sem_alvo, (
        f"{len(sem_alvo)} de {esperado} células de `guarda.secao` não declaram "
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

    # A FORMA DE `SECOES` É LIDA, E NÃO SUPOSTA — 03/09/2026. Estas três linhas
    # desempacotavam `(campo, pecas, dica)`; a decisão nº4 dela tirou as oito
    # dicas das células e a tupla virou um PAR. O `ValueError` que isso produzia
    # não é reprovação, é a régua morta — quatro testes deste arquivo caíram
    # assim, e a coluna ficou sem guarda no dia em que mais precisava dela.
    diferentes = [
        peca
        for _campo, pecas in aba10.SECOES
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
def test_o_produtor_e_o_desenho_dizem_as_secoes_na_mesma_ordem() -> None:
    """O piloto distribui a lista pelos elementos na ordem do DOM.

    ``perfis_web.SECOES_POR_CONTROLE`` decide a ordem dos VALORES e
    ``aba10.SECOES`` a das CÉLULAS. Se as duas discordarem, a tela acende a luz
    onde a vibração está guardada — e nada acusa, porque o número de valores
    continua batendo.

    MORDIDA: troque duas linhas de ``aba10.SECOES`` (ou de
    ``SECOES_POR_CONTROLE``) e este teste reprova mostrando as duas sequências.
    """
    aba10 = _gerador()
    do_desenho = tuple(campo for campo, _pecas in aba10.SECOES)
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
    dizer: apagado, apagado, ACESO, apagado, apagado · e cinco apagados no
    segundo.

    O ESPERADO É CALCULADO, e não digitado — 03/09/2026. Este ``assert`` trazia
    oito booleanos cravados; a emissão passou a mandar ``"sim"``/``""`` (o alvo
    ``classe`` lê string) e a coluna ganhou a quinta seção, e a régua morreu
    duas vezes na mesma linha.

    MORDIDA: volte a ``[s for g in guarda for s in (g.get("secoes") or [])]`` e
    este teste reprova com ``['leds', 'triggers', …]`` no lugar dos estados.
    """
    monkeypatch.setattr(a10_perfis, "_SECAO_POR_CLASSE", True, raising=False)
    fora = _emitidos(rumble={"policy": "economia"})
    quantas = len(a10_perfis.SECOES_DA_COLUNA)
    onde_acende = a10_perfis.SECOES_DA_COLUNA.index("rumble")
    esperado = ["sim" if i == onde_acende else "" for i in range(quantas)]
    # AS LINHAS QUE SOBRAM DA TABELA SÃO VAZIAS — a `_emitidos` põe DOIS
    # controles na mesa e a tabela tem quatro lugares (05/09/2026: o pacote
    # emite os quatro para o lugar vazio poder acender a marca que esconde os
    # glifos do mockup).
    esperado += [""] * quantas * (a10_perfis.LUGARES_DA_TABELA - 1)
    assert fora["guarda.secao"] == esperado, (
        f"a coluna não conta o que o perfil guarda: {fora['guarda.secao']!r} "
        f"em vez de {esperado!r}")

    # E O QUE A TELA FARIA COM ISSO — a mesma lista que o `ligado()` do JS lê.
    acesos = [regua_do_mockup._ligado(str(v)) for v in fora["guarda.secao"]]
    assert acesos == [v == "sim" for v in esperado], (
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
    menor_corpo: dict[str, dict[str, Any]] = {
        "leds": {}, "triggers": {}, "rumble": {}, "speaker": {"volume": 40},
        # O `mic` é o QUINTO ajuste desde a decisão nº20 dela (03/09/2026). Ele
        # aceita `{}` como os três primeiros — `ControllerMicOverride.muted`
        # nasce `None`, e `_secoes_do_controle` pergunta `is not None` sobre a
        # SEÇÃO, não sobre o campo de dentro.
        "mic": {},
        # O `sensores` é o SEXTO desde 04/09/2026 (SENSOR-DE-VERDADE-01), e ele
        # atravessou este arquivo por um dia exatamente como o aviso acima
        # previa: o campo entrou no esquema em `8f9589ba` e a coluna só nasceu
        # em 05/09, com esta régua VERMELHA no `dev` no meio. `{}` basta —
        # `ControllerSensoresOverride.giroscopio`/`.acelerometro` nascem `None`.
        "sensores": {},
    }
    faltando = set(perfis_web.SECOES_POR_CONTROLE) - set(menor_corpo)
    assert not faltando, (
        f"o esquema ganhou {sorted(faltando)} e esta régua não sabe montar o "
        f"corpo mínimo dessa seção — acrescente-o a `menor_corpo`, senão a coluna "
        f"nova atravessa este arquivo sem ser medida (foi o que aconteceu com "
        f"o `mic` em 03/09/2026)")
    quantas = len(perfis_web.SECOES_POR_CONTROLE)
    for posicao, secao in enumerate(perfis_web.SECOES_POR_CONTROLE):
        fora = _emitidos(**{secao: menor_corpo[secao]})
        esperado = ["sim" if i == posicao else "" for i in range(quantas)]
        # As três linhas que sobram da tabela vêm vazias — ver a nota no teste
        # acima, 05/09/2026.
        esperado += [""] * quantas * (a10_perfis.LUGARES_DA_TABELA - 1)
        assert fora["guarda.secao"] == esperado, (
            f"com só `{secao}` guardado, a coluna acendeu "
            f"{fora['guarda.secao']!r} em vez de {esperado!r}")


# ---------------------------------------------------------------------------
# 4. A CURA VALIA NOS DOIS MUNDOS — E OS DOIS MUNDOS VIRARAM UM (03/09/2026)
#
# Aqui viviam QUATRO testes sobre `a10_perfis._a_pagina_acende_a_secao_por_classe`:
# o pacote perguntava à página PUBLICADA se ela trazia `data-hef-alvo="classe"` e
# calava enquanto não trouxesse, porque escrever texto num `<span>` com `<svg>`
# dentro apaga o glifo.
#
# ESSA GUARDA NÃO EXISTE MAIS, e a remoção foi certa: `7e64c2e3` mediu que o
# `--publicar-enderecos` nunca copiava página nenhuma (o ramo `shutil.copy2` era
# INALCANÇÁVEL — o `elif` de cima comparava por `soma()`, o sha256 que APAGA os
# atributos de endereço, então duas páginas que diferem só num `data-hef-alvo`
# caíam em "já igual"). Corrigido isso, o alvo chegou à página publicada e a
# espera acabou.
#
# O QUE ELES GUARDAVAM CONTINUA GUARDADO, e por isso não foram substituídos:
# `test_a_pagina_publicada_sabe_receber_a_pintura`, em
# `test_a_coluna_de_ajuste_proprio_da_aba10_e_dado.py`, exige o alvo em TODA
# célula da página publicada. Uma publicação futura que o perdesse reprova lá.
#
# POR QUE ISTO ESTÁ ESCRITO EM VEZ DE APAGADO: os quatro ficaram QUEBRADOS no
# `dev` por um dia inteiro (`AttributeError`, e mais cinco irmãos deste arquivo),
# e uma régua quebrada não reprova nada — foi sob ela que a coluna do microfone
# passou apagada à força. Quem apagar em silêncio a próxima régua caduca deixa a
# mesma armadilha.
# ---------------------------------------------------------------------------
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
