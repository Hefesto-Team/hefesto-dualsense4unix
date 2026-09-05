#!/usr/bin/env python3
"""A coluna "Ajuste próprio" mostra TUDO o que o perfil guarda — na célula certa.

QUEIXA DELA, 05/09/2026: *"a aba 10 tá com o mesmo problema de antes. nada
mudou."*

**A HIPÓTESE QUE ESTAVA NA MESA CAIU, e está medida.** A triagem anterior dizia
que a coluna mostrava dado *deslocado uma casa* — a linha do segundo controle
exibindo o que é do primeiro. Medido em 05/09 com o disco dela
(``meu_perfil.json``, dois controles com ``leds``/``triggers``/``rumble``), a
distribuição pousa certa: a leitura é POR NOME (``SECOES_DA_COLUNA``) e não pela
ordem do dicionário, e o bloco por linha bate com o número de células.

**O DEFEITO ERA OUTRO, E MAIOR: a coluna ESCONDIA uma seção inteira.**
``ControllerOverrides`` ganhou ``sensores`` em 04/09 (``8f9589ba``,
SENSOR-DE-VERDADE-01) e ``aba10.SECOES`` ficou nos cinco. O perfil passou a
guardar giroscópio e acelerômetro por peça e a tabela que existe para responder
*"o que este controle tem de próprio"* não tinha célula para dizê-lo — a dica da
linha, que sai do ESQUEMA, já contava *"3 de 6 ajustes"* enquanto o cabeçalho ao
lado dizia *"os cinco ajustes"*. Um controle cujo único ajuste próprio fosse o
sensor entrava na conta do cabeçalho (*"1 de 2 controles com ajuste próprio"*)
com a fileira inteira apagada.

POR QUE ESTA RÉGUA, tendo três irmãs no assunto
------------------------------------------------
As três comparam LISTAS em Python — nomes contra nomes, valor contra posição no
que o pacote EMITE. Nenhuma abre a página. Esta é a única que fecha o circuito:
ela põe o valor na página PUBLICADA, com o ``BOOTSTRAP`` do piloto de verdade
injetado, e pergunta ao Chrome QUAL célula acendeu — a linha e o nome da seção,
lidos do DOM. É a régua que mediria um deslocamento se ele existisse, e é a que
reprova no dia em que o esquema ganhar um sétimo campo sem coluna.

O QUE ELA NÃO ALCANÇA: o WebKitGTK, que é o motor do produto. Aqui se mede o
CONTRATO (quem acende o quê); a prova no motor de verdade é o ``--prova-clique``
do piloto, com o daemon vivo.

MORDIDA (as duas provadas em 05/09):
  1. tire ``"sensores"`` de ``a10_perfis.SECOES_DA_COLUNA`` — cai
     ``test_toda_secao_do_esquema_tem_celula_na_pagina`` e o caso do sensor;
  2. troque a emissão de ``pacote()`` por ``for secao in (g.get("secoes") or {})``
     (iterar o dicionário, que é o defeito de 02/09) — cai o caso da célula
     única, dizendo quantas acenderam.
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.app.actions import perfis_web
from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis

CHROME = pathlib.Path("/usr/bin/google-chrome")

#: A MESA DA RÉGUA — dois controles, endereços MASCARADOS (octetos 4 e 5
#: zerados). Nenhum endereço real de rádio entra em arquivo versionado.
MESA = [
    {"pref": "p1", "uniq": "aabbcc000001", "jogador": 1, "cor": "cosmic-red",
     "nome": "Cosmic Red", "via": "BT", "transporte": "bt", "alvo": True,
     "mascara": "DualSense"},
    {"pref": "p2", "uniq": "aabbcc000002", "jogador": 2, "cor": "starlight-blue",
     "nome": "Starlight Blue", "via": "USB", "transporte": "usb", "alvo": False,
     "mascara": "DualSense"},
]

#: O MENOR CORPO QUE CADA SEÇÃO ACEITA — ``None`` é "sem opinião", e
#: ``_secoes_do_controle`` pergunta ``is not None`` sobre a SEÇÃO, não sobre o
#: campo de dentro. Só o ``speaker`` exige conteúdo (SOM-02: ``muted`` sem
#: ``volume`` mandaria volume ZERO e tomaria a posse do alto-falante).
MENOR_CORPO: dict[str, dict[str, Any]] = {
    "leds": {}, "triggers": {}, "rumble": {}, "speaker": {"volume": 40},
    "mic": {}, "sensores": {},
}

#: O QUE O PILOTO FAZ COM UMA LISTA, e é a linha que se mede aqui:
#: ``alvos.forEach(function(el, i){ escrever(el, i < v.length ? v[i] : ''); })``.
#: Ela é chamada pelo ``BOOTSTRAP`` de verdade — o texto abaixo só ENTREGA a
#: carga e LÊ o DOM depois.
LER_AS_CELULAS = """
() => {
  const linhas = [];
  for (const tr of document.querySelectorAll(
         'tbody[data-hef="guarda.linhas"] tr')) {
    linhas.push([...tr.querySelectorAll('[data-hef="guarda.secao"]')].map(
      el => [el.dataset.hefSecao, el.classList.contains('on')]));
  }
  return linhas;
}
"""


def _bootstrap() -> str:
    """O ``BOOTSTRAP`` do piloto, lido do FONTE — sem importar ``gi``.

    Importar o piloto traria o GTK junto, e uma régua que exige GTK deixa de
    rodar no CI. Ler do fonte é o que garante que se mede o bootstrap DE
    VERDADE, e não uma cópia que envelhece sozinha.
    """
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py").read_text(
        encoding="utf-8")
    m = re.search(r'BOOTSTRAP = r"""(.*?)"""', fonte, re.S)
    assert m, "não achei o BOOTSTRAP no piloto — a régua ficaria verde sobre nada"
    return m.group(1)


def _perfil(uniq: str, **overrides: Any) -> Any:
    """Um perfil de disco com ajuste próprio de UM controle só.

    O DISCO NÃO SERVE: a ``tests/conftest.py`` põe
    ``HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1`` em todo teste e
    ``load_all_profiles()`` devolve **zero** perfis nesta suíte — sem dublê,
    ``pacote_da_aba`` devolveria ``guarda=[]`` e a tabela nunca seria medida.
    """
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        MatchAny,
        Profile,
    )

    return Profile(name="régua", match=MatchAny(),
                   controllers={uniq: ControllerOverrides(**overrides)})


def _emitidos(
    monkeypatch: pytest.MonkeyPatch, uniq: str, **overrides: Any,
) -> dict[str, Any]:
    """O que ``a10_perfis.pacote()`` manda pintar, com a mesa de dois.

    O DUBLÊ ENTRA PELO ``monkeypatch``, e não por atribuição crua — **medido em
    05/09/2026, neste arquivo**. A primeira versão fazia
    ``loader.load_all_profiles = lambda …`` direto, e o dublê SOBREVIVIA ao fim
    do teste: rodando esta régua no mesmo processo que
    ``test_ativar_nao_diz_aplicado_sobre_o_perfil_que_ja_vale.py``, aquele
    arquivo caía com *"reativar o perfil que já vale passou pela guarda"* — dois
    testes vermelhos num arquivo que não tinha defeito nenhum, e verdes quando
    rodados sozinhos. É a mesma assinatura do dublê do co-op que envenenava
    outro arquivo por ORDEM DE TESTE (04/09), e a cura é a mesma: quem troca
    algo global devolve no teardown.
    """
    from hefesto_dualsense4unix.profiles import loader

    alvo = _perfil(uniq, **overrides)
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: [alvo])
    ctx = Contexto(state={"active_profile": "régua"}, mesa=list(MESA),
                   conectados=list(MESA), estados={})
    return a10_perfis.pacote(ctx)


@pytest.fixture(autouse=True)
def _lar(monkeypatch: pytest.MonkeyPatch) -> None:
    """Estado de módulo zerado — sem isto um caso herda a resposta do anterior."""
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_SECAO_POR_CLASSE", True, raising=False)


# ---------------------------------------------------------------------------
# 1. A PÁGINA TEM CÉLULA PARA TUDO O QUE O ESQUEMA GUARDA
#    (a leitura é da PÁGINA publicada, não de uma lista Python)
# ---------------------------------------------------------------------------
def test_toda_secao_do_esquema_tem_celula_na_pagina() -> None:
    """Um campo de ``ControllerOverrides`` sem célula é ajuste que a tela ESCONDE.

    Ela guardaria o giroscópio daquele controle no disco e a tabela que existe
    para mostrar o que a peça tem de próprio ficaria muda — foi o que aconteceu
    entre 04/09 e 05/09, e é a queixa dela.

    A CONTA SAI DA PÁGINA E DO ESQUEMA, e nenhum dos dois é digitado aqui.
    """
    html = onde.pagina("10-perfis.html", publicado=True).read_text(encoding="utf-8")
    na_pagina = {m for m in re.findall(r'data-hef-secao="([^"]+)"', html)}
    faltando = [s for s in perfis_web.SECOES_POR_CONTROLE if s not in na_pagina]
    assert not faltando, (
        f"o perfil guarda {faltando} por controle e a página publicada não tem "
        f"célula para essas seções — ajuste guardado no disco que a tela esconde. "
        f"Acrescente a seção a `aba10.SECOES` e a `a10_perfis.SECOES_DA_COLUNA`, "
        f"regere e publique a aba 10.")


def test_a_pagina_nao_inventa_secao_que_o_esquema_nao_guarda() -> None:
    """O sentido contrário: célula sem campo acende sobre nada.

    Ele é legítimo por um tempo — ver ``a10_perfis.ESPERANDO_O_ESQUEMA``, que
    declara a coluna aprovada antes de o campo existir. O que não é legítimo é
    uma coluna assim SEM declaração.
    """
    html = onde.pagina("10-perfis.html", publicado=True).read_text(encoding="utf-8")
    na_pagina = {m for m in re.findall(r'data-hef-secao="([^"]+)"', html)}
    sobrando = sorted(
        na_pagina - set(perfis_web.SECOES_POR_CONTROLE)
        - set(a10_perfis.ESPERANDO_O_ESQUEMA))
    assert not sobrando, (
        f"a página tem célula para {sobrando} e o esquema não guarda esses "
        f"campos — a coluna acenderia sobre nada. Declare em "
        f"`a10_perfis.ESPERANDO_O_ESQUEMA` ou tire a célula do desenho.")


# ---------------------------------------------------------------------------
# 2. O CIRCUITO FECHADO — o valor sai do perfil e acende A CÉLULA CERTA
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not CHROME.exists(),
                    reason="sem o Chrome do sistema — a régua não tem motor")
@pytest.mark.parametrize("linha", [0, 1])
@pytest.mark.parametrize("secao", list(perfis_web.SECOES_POR_CONTROLE))
def test_uma_secao_guardada_acende_uma_celula_so_e_na_linha_dela(
    monkeypatch: pytest.MonkeyPatch, linha: int, secao: str,
) -> None:
    """Um ajuste, um controle: acende UMA célula, na linha e na coluna dele.

    É a régua que mediria o *"deslocado uma casa"* — a linha do segundo controle
    mostrando o do primeiro. Ela varre as duas linhas e as seis seções: 12 casos,
    e cada um afirma o endereço EXATO do que acendeu.

    O CAMINHO É O DO PRODUTO, inteiro: ``pacote()`` monta a lista achatada, o
    ``BOOTSTRAP`` de verdade a distribui pelos ``[data-hef="guarda.secao"]`` na
    ordem do documento, e o alvo ``classe`` decide quem fica ``.on``. Nada aqui
    reimplementa a pintura.
    """
    from playwright.sync_api import sync_playwright

    assert secao in MENOR_CORPO, (
        f"o esquema ganhou `{secao}` e esta régua não sabe montar o corpo mínimo "
        f"dessa seção — acrescente-a a `MENOR_CORPO`, senão a coluna nova "
        f"atravessa este arquivo sem ser medida")
    fora = _emitidos(monkeypatch, str(MESA[linha]["uniq"]),
                     **{secao: MENOR_CORPO[secao]})
    carga = {"mesa": {"guarda.secao": fora["guarda.secao"]}}

    pagina = onde.pagina("10-perfis.html", publicado=True)
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(
            executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = navegador.new_page(viewport={"width": 1180, "height": 900})
            pg.goto(pagina.as_uri())
            # A PONTE DE MENTIRA É O `webkit.messageHandlers`, como nas outras
            # réguas de tela: o Chrome não tem `window.webkit`, e o bootstrap o
            # toca ao instalar o ouvinte.
            pg.evaluate(
                "window.webkit = {messageHandlers: {hefesto: "
                "{postMessage: function(){}}}};")
            pg.evaluate(_bootstrap())
            pg.evaluate("(p) => window.__hef.pintar(p)", carga)
            linhas = pg.evaluate(LER_AS_CELULAS)
        finally:
            navegador.close()

    acesas = [(i, nome) for i, celulas in enumerate(linhas)
              for nome, on in celulas if on]
    assert acesas == [(linha, secao)], (
        f"com só `{secao}` guardado do controle da linha {linha}, a tela acendeu "
        f"{acesas} — o esperado é exatamente [({linha}, {secao!r})]. "
        f"Duas acesas na mesma linha, ou uma acesa na linha errada, é a coluna "
        f"casando célula com vizinha.")


# ---------------------------------------------------------------------------
# 3. A DICA DO CABEÇALHO NÃO PODE CONTAR DIFERENTE DA LINHA
# ---------------------------------------------------------------------------
def test_o_cabecalho_e_a_dica_da_linha_contam_o_mesmo_numero() -> None:
    """Dois números para o mesmo fato, na mesma tela, é a divergência que ela viu.

    A dica da LINHA sai do esquema (``perfis_web._linhas_da_guarda``: *"3 de 6
    ajustes só deste controle"*); a dica do CABEÇALHO sai do desenho
    (``aba10.QUANTAS_SECOES``). Entre 04/09 e 05/09 a primeira dizia SEIS e a
    segunda dizia CINCO, a poucos pixels uma da outra.

    MORDIDA: tire uma seção de ``aba10.SECOES``, regere e publique — o cabeçalho
    passa a dizer "cinco" e esta régua reprova mostrando os dois números.
    """
    html = onde.pagina("10-perfis.html", publicado=True).read_text(encoding="utf-8")
    extenso = {1: "um", 2: "dois", 3: "três", 4: "quatro", 5: "cinco", 6: "seis"}
    quantas = len(perfis_web.SECOES_POR_CONTROLE)
    esperado = extenso.get(quantas, str(quantas))
    assert f"São os {esperado} ajustes" in html, (
        f"o esquema guarda {quantas} seções por controle e a dica do cabeçalho "
        f"não diz `{esperado}` — a linha ao lado já conta o número do esquema "
        f"(`{quantas} de {quantas} ajustes só deste controle`), e as duas frases "
        f"ficam na mesma tela discordando.")


# ---------------------------------------------------------------------------
# 4. O LUGAR SEM CONTROLE NÃO DESENHA CONTROLE — 05/09/2026, palavra dela
# ---------------------------------------------------------------------------
def test_a_linha_sem_controle_nao_mostra_glifo_nenhum(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """*"os svgs não deveriam aparecer prós demais controles desconectados"*.

    A QUEIXA É DELA, E O QUE ELA VIU ESTAVA MEDIDO DESDE 03/09 no próprio
    pacote: com a mesa em dois controles, *"a fileira de OITO glifos de 'Ajuste
    próprio' sai IDÊNTICA à das duas linhas de cima"*. O lugar vazio mostrava um
    controle desenhado — apagado, mas desenhado — ao lado de um nome que já
    dizia que ali não há ninguém.

    ESTA RÉGUA MEDE A TELA, e não o CSS. Uma que procurasse a regra
    `.tab.miuda tr.fora .gr{visibility:hidden}` no arquivo estaria DIGITANDO o
    que devia LER — o defeito que esta casa nomeou onze vezes numa leva só —, e
    ficaria verde com a regra presente e sem efeito (um seletor que não casa, um
    `!important` do vizinho, a classe que o produto não acende).

    O CAMINHO É O DO PRODUTO INTEIRO: `pacote()` monta as listas com UM controle
    na mesa, o `BOOTSTRAP` de verdade as distribui, o alvo `classe` acende o
    `fora` na `<tr>` — e a pergunta é feita ao navegador:
    `getComputedStyle(glifo).visibility`.

    A MORDIDA: apague a regra do `aba10.py`, regere e publique. As três linhas
    sem controle voltam a `visible` e esta régua reprova nomeando a linha.
    """
    from playwright.sync_api import sync_playwright

    fora = _emitidos(monkeypatch, str(MESA[0]["uniq"]), leds={})
    carga = {"mesa": {chave: fora[chave] for chave in
                      ("guarda.secao", "guarda.vazio", "guarda.nome")}}

    pagina = onde.pagina("10-perfis.html", publicado=True)
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(
            executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = navegador.new_page(viewport={"width": 1180, "height": 900})
            pg.goto(pagina.as_uri())
            pg.evaluate(
                "window.webkit = {messageHandlers: {hefesto: "
                "{postMessage: function(){}}}};")
            pg.evaluate(_bootstrap())
            pg.evaluate("(p) => window.__hef.pintar(p)", carga)
            visto = pg.evaluate("""() => {
              const ls = [...document.querySelectorAll('.tab.miuda tbody tr')];
              return ls.map(tr => ({
                nome: (tr.querySelector('[data-hef="guarda.nome"]')||{}).textContent,
                fora: tr.classList.contains('fora'),
                glifos: [...tr.querySelectorAll('.gr')].map(
                    g => getComputedStyle(g).visibility),
              }));
            }""")
        finally:
            navegador.close()

    assert len(visto) == a10_perfis.LUGARES_DA_TABELA, (
        f"a tabela tem {len(visto)} linhas e a régua espera "
        f"{a10_perfis.LUGARES_DA_TABELA} — a medição perdeu o objeto")

    # A MESA DESTA RÉGUA TEM DOIS: as duas primeiras linhas têm controle.
    for n, linha in enumerate(visto[:len(MESA)], start=1):
        assert not linha["fora"], (
            f"a linha {n} TEM controle e foi marcada como vazia")
        assert set(linha["glifos"]) == {"visible"}, (
            f"a linha {n} tem controle e os glifos dela sumiram: "
            f"{linha['glifos']}")

    for n, linha in enumerate(visto[len(MESA):], start=len(MESA) + 1):
        assert linha["fora"], (
            f"a linha {n} não tem controle e o produto não a marcou — sem a "
            f"marca o CSS não tem em que se pendurar. Nome na tela: "
            f"{linha['nome']!r}")
        assert linha["glifos"], (
            f"a linha {n} não tem glifo nenhum no desenho — a régua mediria o "
            "vazio e ficaria verde por ausência de dado")
        assert set(linha["glifos"]) == {"hidden"}, (
            f"a linha {n} não tem controle e ainda desenha os glifos: "
            f"{linha['glifos']}. É a tela mostrando um aparelho que não está "
            f"aqui — a queixa dela de 05/09.")
