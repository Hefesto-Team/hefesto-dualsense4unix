"""A aba 10 fecha as linhas da ONDA2 — e cada régua daqui nasceu de uma medição.

**O QUE ESTE ARQUIVO GUARDA**, na ordem em que a sprint as pediu:

* **T-04 · a coluna "Ajuste próprio" acende o que o disco não guarda.** A
  medição de 04/09/2026 leu, do DOM vivo com dois controles na mesa, uma coluna
  que não batia com o arquivo do perfil. Régua nenhuma desta casa
  media a **DISTRIBUIÇÃO**  (noqa-acento: verbo medir, imperfeito)
  — o passo em que uma lista plana de N por 5 valores encontra
  as N por 5 células na ordem do documento. As duas réguas que existiam
  (`test_a_coluna_do_ajuste_proprio_acende_pela_classe`) param no que o pacote
  EMITE; o defeito, se houvesse, moraria depois disso. Aqui a distribuição é
  refeita como o `BOOTSTRAP` a faz, sobre o HTML de verdade, e o resultado é
  comparado **célula a célula com o disco**.

* **[01] o cadeado e o ponto de alerta** — as duas marcas que o PO decidiu, com
  o invariante que as torna seguras: *a marca acende exatamente quando a frase
  existe*.

* **[02] o fim da frase que mandava a um lugar que não existe aqui** — e a
  guarda que impede a remenda de apodrecer.

* **[03] a frase da Prioridade que ela aprovou**, agora no desenho, amarrada ao
  produto por leitura.

* **[04] o campo do jogo se corrige** depois que ela sai dele.

* **[05] a tira do desfecho ganhou a segunda linha**, que é onde mora a metade
  que avisa.

**O DUBLÊ DE DISCO É OBRIGATÓRIO**, e a razão está medida no próprio pacote: a
`tests/conftest.py` põe ``HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1`` em todo
teste, e ``load_all_profiles()`` devolve **zero** perfis nesta suíte. Sem
dublê, ``pacote_da_aba`` devolveria ``guarda=[]``, a tabela nunca seria medida,
e este arquivo ficaria verde por vacuidade — que é o pior estado de uma régua.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import perfis_web
from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis

PAGINA = "10-perfis.html"  # (noqa-acento) nome de arquivo

#: A MESA DA RÉGUA — DOIS controles, com os endereços MASCARADOS (octetos 4 e 5
#: zerados, faixa sintética da casa). Dois porque o defeito de T-04 é de
#: DESLOCAMENTO: com um só, uma lista deslocada continuaria caindo na primeira
#: linha e a régua ficaria verde sobre o defeito.
MESA = [
    {"pref": "p1", "uniq": "aabbcc000001", "jogador": 1, "cor": "cosmic-red",
     "nome": "Cosmic Red", "via": "USB", "transporte": "usb", "alvo": True,
     "mascara": "DualSense"},
    {"pref": "p2", "uniq": "aabbcc000002", "jogador": 2, "cor": "starlight-blue",
     "nome": "Starlight Blue", "via": "BT", "transporte": "bt", "alvo": False,
     "mascara": "DualSense"},
]

#: O MENOR CORPO QUE CADA SEÇÃO ACEITA. O contrato de ``ControllerOverrides`` é
#: *"campo `None` = sem opinião"*, e ``_secoes_do_controle`` pergunta exatamente
#: ``is not None`` — o conteúdo não importa. O ``speaker`` exige ``volume``
#: (SOM-02: ``muted`` sem ``volume`` mandaria volume ZERO e tomaria a posse do
#: alto-falante).
MENOR_CORPO: dict[str, dict[str, Any]] = {
    "leds": {}, "triggers": {}, "rumble": {}, "speaker": {"volume": 40},
    "mic": {},
}


# ---------------------------------------------------------------------------
# O ferramental
# ---------------------------------------------------------------------------
def _pagina(publicado: bool) -> str:
    return onde.pagina(PAGINA, publicado=publicado).read_text(encoding="utf-8")


def _celulas_da_guarda(html: str) -> list[tuple[int, str]]:
    """``(índice da linha, nome da seção)`` de cada célula, NA ORDEM DO DOCUMENTO.

    É a mesma ordem que o ``BOOTSTRAP`` percorre: ele faz
    ``document.querySelectorAll('[data-hef="guarda.secao"]')`` e distribui a
    lista com ``alvos.forEach((el, i) => i < v.length ? v[i] : '')``. Aqui o
    `<tbody>` é recortado primeiro para que a contagem de LINHA seja a de
    verdade — se um dia nascer uma célula `guarda.secao` fora da tabela, a
    distribuição inteira desloca, e é justamente essa hipótese que esta função
    torna mensurável.
    """
    corpo = re.search(r'<tbody data-hef="guarda\.linhas">(.*?)</tbody>', html,
                      re.S)
    assert corpo is not None, (
        "o `<tbody data-hef=\"guarda.linhas\">` sumiu da página — sem ele não "
        "há tabela por controle, e esta régua não teria o que medir")
    fora: list[tuple[int, str]] = []
    for linha, bruto in enumerate(re.split(r"<tr\b", corpo.group(1))[1:]):
        for celula in re.findall(
                r'<span[^>]*data-hef="guarda\.secao"[^>]*>', bruto):
            secao = re.search(r'data-hef-secao="([^"]+)"', celula)
            assert secao is not None, (
                f"uma célula de `guarda.secao` na linha {linha} não diz QUAL "
                f"seção ela é (`data-hef-secao`) — sem isso a coluna só pode "
                f"ser lida pela posição, e é a posição que estava sob suspeita")
            fora.append((linha, secao.group(1)))
    return fora


def _todas_as_celulas(html: str) -> int:
    return len(re.findall(r'<span[^>]*data-hef="guarda\.secao"[^>]*>', html))


def _perfil(guardado: dict[str, list[str]]) -> Any:
    """Um perfil de disco: ``{uniq: [seções que ele guarda só daquele controle]}``."""
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        MatchAny,
        Profile,
    )

    return Profile(
        name="régua", match=MatchAny(),
        controllers={
            uniq: ControllerOverrides(**{s: MENOR_CORPO[s] for s in secoes})
            for uniq, secoes in guardado.items()
        },
    )


@pytest.fixture(autouse=True)
def _limpo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Estado de módulo zerado: um teste não herda a escolha do anterior.

    **O `load_all_profiles` ENTRA AQUI, e não é zelo — é a cicatriz de 04/09.**
    O `_emitido` abaixo troca a função por atribuição crua (`loader.x = lambda`)
    e a atribuição crua **não se desfaz**: rodando este arquivo junto com os
    vizinhos, o dublê vazava e derrubava QUATRO testes de outras réguas —
    ``test_as_tres_cargas_de_perfil_disparam_a_semeadura`` entre eles, que só
    pergunta se a carga dispara a semeadura e recebia a minha lambda.

    Registrar o nome aqui com `monkeypatch` faz o pytest guardar o valor
    ORIGINAL antes de qualquer teste tocá-lo, e devolvê-lo no teardown — a
    atribuição crua lá dentro passa a ser desfeita de graça. É o mesmo arranjo
    que a régua vizinha (`test_a_coluna_do_ajuste_proprio_acende_pela_classe`)
    já usava, e foi por copiar só a METADE dele que este arquivo sujou os
    vizinhos.
    """
    from hefesto_dualsense4unix.profiles import loader

    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_PINTADO_PARA", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ULTIMO_TIQUE", 0.0, raising=False)
    monkeypatch.setattr(a10_perfis, "_DESFECHO", None, raising=False)
    monkeypatch.setattr(loader, "load_all_profiles", loader.load_all_profiles)


def _emitido(prof: Any, mesa: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    from hefesto_dualsense4unix.profiles import loader

    loader.load_all_profiles = lambda *a, **k: [prof]  # type: ignore[assignment]
    da_mesa = list(MESA if mesa is None else mesa)
    ctx = Contexto(state={"active_profile": prof.name}, mesa=da_mesa,
                   conectados=da_mesa, estados={})
    return a10_perfis.pacote(ctx)


def _distribuir(valores: list[Any], celulas: list[tuple[int, str]]) -> list[bool]:
    """O ``forEach`` do BOOTSTRAP, em Python — e o ``ligado()`` junto.

    ``escrever(el, '')`` troca o vazio por travessão e ``ligado('—')`` é falso;
    por isso a célula que sobra da lista APAGA, em vez de guardar o que o
    mockup cravou.
    """
    from hefesto_dualsense4unix.interface import regua_do_mockup

    return [
        regua_do_mockup._ligado(str(valores[i])) if i < len(valores) else False
        for i in range(len(celulas))
    ]


# ---------------------------------------------------------------------------
# T-04 · a coluna "Ajuste próprio" e o disco, célula a célula
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("publicado", [False, True], ids=["bancada", "publicada"])
def test_cada_celula_da_guarda_diz_o_que_o_disco_guarda(publicado: bool) -> None:
    """A régua que faltava a T-04: a DISTRIBUIÇÃO, e não só a emissão.

    O QUE ELA REFAZ: o pacote emite uma lista PLANA (uma linha da tabela é um
    bloco de ``len(SECOES_DA_COLUNA)`` valores) e o piloto a distribui pela
    ordem do documento. Entre os dois passos não havia régua nenhuma — e é
    exatamente ali que um deslocamento moraria: a lista continua com o número
    certo de valores, a coluna continua acendendo, e cada linha mostra o que é
    da vizinha.

    O PERFIL É ASSIMÉTRICO DE PROPÓSITO: se os dois controles guardassem as
    mesmas seções, um deslocamento de uma LINHA inteira passaria despercebido.

    MORDIDA: troque `for g in guarda for secao in SECOES_DA_COLUNA` por
    `for secao in SECOES_DA_COLUNA for g in guarda` em `a10_perfis.pacote` — a
    lista continua com dez valores e este teste reprova nomeando a célula.
    """
    guardado = {MESA[0]["uniq"]: ["leds", "rumble"], MESA[1]["uniq"]: ["triggers"]}
    fora = _emitido(_perfil(guardado))
    celulas = _celulas_da_guarda(_pagina(publicado))
    acesos = _distribuir(fora["guarda.secao"], celulas)

    # O QUE O DISCO DIZ, POR LINHA — e a ordem das linhas é a da MESA, que é a
    # que `perfis_web._linhas_da_guarda` percorre.
    do_disco = [set(guardado.get(str(c["uniq"]), [])) for c in MESA]
    errados = []
    for (linha, secao), aceso in zip(celulas, acesos, strict=True):
        quer = secao in do_disco[linha] if linha < len(do_disco) else False
        if aceso != quer:
            dono = MESA[linha]["pref"] if linha < len(MESA) else f"linha {linha}"
            errados.append(f"{dono}/{secao}: tela={'acesa' if aceso else 'apagada'}"
                           f" disco={'guarda' if quer else 'não guarda'}")
    assert not errados, (
        "a coluna “Ajuste próprio” diz o que o disco não guarda:\n  "
        + "\n  ".join(errados))


@pytest.mark.parametrize("publicado", [False, True], ids=["bancada", "publicada"])
def test_a_linha_sem_controle_na_mesa_apaga_a_coluna_inteira(publicado: bool) -> None:
    """As linhas que sobram do desenho não guardam o que o MOCKUP cravou.

    O desenho tem quatro linhas e a mesa dela tem uma ou duas. As que sobram
    recebem `''` pelo `forEach` e têm de APAGAR — se não apagassem, a tela
    mostraria o ajuste próprio do controle de exemplo sobre um lugar vazio, que
    é a metade mais fácil de acreditar do defeito medido em 04/09.

    MORDIDA: faça o `forEach` do BOOTSTRAP parar em `i < v.length` sem escrever
    nas que sobram (ou devolva `'sim'` no lugar do `''`) e esta régua reprova.
    """
    fora = _emitido(_perfil({MESA[0]["uniq"]: ["leds", "triggers", "rumble",
                                              "speaker", "mic"]}),
                    mesa=[MESA[0]])
    celulas = _celulas_da_guarda(_pagina(publicado))
    acesos = _distribuir(fora["guarda.secao"], celulas)
    sobrando = [f"{linha}/{secao}"
                for (linha, secao), aceso in zip(celulas, acesos, strict=True)
                if linha >= 1 and aceso]
    assert not sobrando, (
        f"{len(sobrando)} célula(s) de linha sem controle continuaram acesas "
        f"({sobrando[:5]}) — a tela guardou o desenho no lugar de um controle "
        f"que não está na mesa")


@pytest.mark.parametrize("publicado", [False, True], ids=["bancada", "publicada"])
def test_a_tabela_da_guarda_nao_tem_celula_fora_das_linhas(publicado: bool) -> None:
    """Uma célula `guarda.secao` fora do `<tbody>` desloca a coluna INTEIRA.

    Era a segunda das três hipóteses que a medição de 04/09 deixou em aberto, e
    ela é verificável sem daemon nenhum: o `querySelectorAll` do piloto varre o
    DOCUMENTO, e o `<tbody>` é só onde as linhas moram. Uma célula solta na
    legenda, num exemplo ou num quadro novo entra na contagem antes das da
    tabela e empurra todas as outras.

    MORDIDA: acrescente um `<span data-hef="guarda.secao">` fora da tabela no
    `aba10.MIOLO` e esta régua reprova com a diferença.
    """
    html = _pagina(publicado)
    na_tabela = len(_celulas_da_guarda(html))
    no_documento = _todas_as_celulas(html)
    assert na_tabela == no_documento, (
        f"{no_documento - na_tabela} célula(s) de `guarda.secao` moram FORA do "
        f"`<tbody data-hef=\"guarda.linhas\">` — a distribuição por ordem do "
        f"documento passa a casar cada linha com os valores da vizinha")


def test_a_lista_emitida_tem_um_bloco_por_controle_da_mesa() -> None:
    """O tamanho é o contrato: ``len(mesa) vezes len(SECOES_DA_COLUNA)``.

    Era a terceira hipótese de 04/09 (*"ou `guarda` traz mais linhas do que a
    mesa"*). Ela morre aqui, e com número: `_linhas_da_guarda` itera a MESA, e
    um bloco a mais empurraria os valores para a linha seguinte.
    """
    for quantos in (1, 2):
        fora = _emitido(_perfil({MESA[0]["uniq"]: ["leds"]}), mesa=MESA[:quantos])
        esperado = quantos * len(a10_perfis.SECOES_DA_COLUNA)
        assert len(fora["guarda.secao"]) == esperado, (
            f"com {quantos} controle(s) na mesa a lista tem "
            f"{len(fora['guarda.secao'])} valores, e a tabela espera blocos de "
            f"{len(a10_perfis.SECOES_DA_COLUNA)} — {esperado}")


# ---------------------------------------------------------------------------
# [01] o cadeado e o ponto de alerta
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("classe", "estado", "frase"),
    [("trava", "editor.ambiente.travado", "editor.ambiente.recado"),
     ("exige", "editor.jogo.exige", "editor.jogo.exigencia")])
def test_a_marca_e_a_frase_moram_na_bancada(classe: str, estado: str,
                                            frase: str) -> None:
    """As duas metades de cada marca existem no desenho, e a dica nasce VAZIA.

    MORDIDA: tire a chamada de `marca_com_dica` do `aba10.MIOLO`, regere, e esta
    régua reprova nomeando a marca que sumiu.
    """
    html = _pagina(publicado=False)
    marca = re.search(rf'<span class="{classe}"[^>]*>', html)
    assert marca is not None, f"a marca `{classe}` não está na bancada"
    assert f'data-hef="{estado}"' in marca.group(0)
    assert 'data-hef-alvo="classe"' in marca.group(0)
    assert (f'<span class="dica" data-hef="{frase}" data-hef-alvo="html">'
            f'</span>') in html, (
        f"a dica de `{classe}` não é um `{frase}` vazio — ou o endereço sumiu, "
        f"ou o desenho passou a cravar uma frase que é dado do perfil dela")


def test_a_marca_acende_exatamente_quando_a_frase_existe() -> None:
    """O invariante que torna os DOIS endereços seguros — nos dois sentidos.

    São dois campos para um fato, e o `monta.botao_cinza` já escreveu por que
    isso é perigoso: *"com dois campos seria possível pintar um botão cinza sem
    razão, ou uma razão sem botão cinza"*. Aqui os dois saem da mesma linha do
    mesmo cálculo — e é ESTA régua que impede que deixem de sair.

    OS TRÊS ESTADOS SÃO REAIS, e cada um é um perfil que ela tem no disco:
    o que casa por título de janela (travado, sem exigência), o Pragmata
    (destravado, COM exigência escondida) e o perfil simples (nenhum dos dois).

    MORDIDA: emita `fora["editor.jogo.exige"] = "sim"` fixo em `pacote()` e
    este teste reprova no perfil simples.
    """
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile

    casos = {
        "por título": Profile(name="por título",
                              match=MatchCriteria(window_title_regex="^Elden")),
        "Pragmata": Profile(name="Pragmata", match=MatchCriteria(
            window_class=["steam_app_3357650"], process_name=["PRAGMATA.exe"])),
        "simples": Profile(name="simples", match=MatchCriteria(
            window_class=["steam_app_1245620"])),
    }
    for nome, prof in casos.items():
        fora = _emitido(prof)
        for marca, frase in (("editor.ambiente.travado", "editor.ambiente.recado"),
                             ("editor.jogo.exige", "editor.jogo.exigencia")):
            acesa = bool(fora[marca]) and str(fora[marca]).lower() not in (
                "false", "", "0")
            tem_frase = bool(str(fora[frase] or "").strip())
            assert acesa == tem_frase, (
                f"no perfil “{nome}” a marca `{marca}` está "
                f"{'acesa' if acesa else 'apagada'} e a frase `{frase}` "
                f"{'existe' if tem_frase else 'está vazia'} — uma marca sem "
                f"explicação, ou uma explicação que ninguém alcança")


def test_o_seletor_travado_tem_onde_pousar_o_travessao(gerador: Any) -> None:
    """A outra metade do cadeado: o CAMPO também para de afirmar.

    MEDIDO NO DOM VIVO em 04/09/2026, com o cadeado já aceso ao lado:

        trava.acesa      true      ← "esta tela não sabe mostrar a regra"
        editor.ambiente  "Jogo"    ← o desenho, afirmando uma regra que não é

    `perfis_web` devolve `ambiente: None` para o perfil de regra fina; o
    `escrever()` do piloto troca isso por `—`, e num `<select>` ele só escreve
    se alguma opção CASAR. Nenhuma casava, então ele devolvia 0 e o campo ficava
    com o valor que o MOCKUP cravou. As duas metades da mesma linha diziam
    coisas diferentes.

    MORDIDA: tire o `travessao=True` da chamada de `opts` no `aba10.MIOLO`,
    regere, e esta régua reprova.
    """
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile

    fora = _emitido(Profile(name="por título",
                            match=MatchCriteria(window_title_regex="^Elden")))
    assert not fora["editor.ambiente"], (
        "o produto passou a nomear um ambiente para o perfil de regra fina — "
        "releia `perfis_web._ambiente_do_perfil` antes de mudar esta régua")

    seletor = re.search(
        r'<select data-hef="editor\.ambiente".*?</select>',
        _pagina(publicado=False), re.S)
    assert seletor is not None, "o seletor 'Funciona em' sumiu do desenho"
    alvo = f'<option value="{gerador.TRAVESSAO}" disabled>'
    assert alvo in seletor.group(0), (
        f"o 'Funciona em' não oferece o `{gerador.TRAVESSAO}` que o "
        f"`escrever()` manda quando não há regra a mostrar — o campo fica com "
        f"a opção que o desenho cravou")
    assert 'value=""' not in seletor.group(0), (
        "a opção do travessão voltou a `value=\"\"` — `el.value = '—'` deixa de "
        "casar, o campo renderiza em branco e o contador de pinturas soma +1 "
        "por tique, para sempre")


def test_a_exigencia_do_pragmata_chega_a_esta_tela() -> None:
    """O caso medido com ela jogando, e ele não tinha endereço nenhum até hoje.

    MORDIDA: faça `_exigencia_para_esta_tela` devolver `""` sempre e esta régua
    reprova.
    """
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile

    prof = Profile(name="Pragmata", match=MatchCriteria(
        window_class=["steam_app_3357650"], process_name=["PRAGMATA.exe"]))
    fora = _emitido(prof)
    frase = str(fora["editor.jogo.exigencia"])
    assert "PRAGMATA.exe" in frase, (
        f"a exigência escondida não nomeia o que o perfil exige: {frase!r}")


# ---------------------------------------------------------------------------
# [02] o fim da frase, reescrito para ESTA tela
# ---------------------------------------------------------------------------
def test_o_modo_avancado_nao_chega_a_esta_tela() -> None:
    """Ele não existe nesta interface, e a frase não pode mandar ninguém a ele.

    A frase do produto está CERTA na janela GTK (`main.glade:2275` tem o
    interruptor com esse nome). Aqui ela seria a tela mandando a um lugar que
    não existe — decisão [02] do PO: *"Isso é fato errado e se substitui."*

    MORDIDA: devolva `exigencia_invisivel(match)` cru em
    `_exigencia_para_esta_tela` e esta régua reprova citando a frase.
    """
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile

    prof = Profile(name="Pragmata", match=MatchCriteria(
        window_class=["steam_app_3357650"], process_name=["PRAGMATA.exe"]))
    frase = str(_emitido(prof)["editor.jogo.exigencia"])
    assert "Modo avançado" not in frase, (
        f"a tela manda ela ligar um “Modo avançado” que esta interface não "
        f"tem: {frase!r}")
    assert frase.endswith(a10_perfis.FIM_DA_EXIGENCIA_AQUI), (
        f"a frase não termina no caminho que ESTA tela alcança: {frase!r}")


def test_a_remenda_do_fim_da_frase_nao_apodrece() -> None:
    """No dia em que o produto mudar o fim, a régua reprova AQUI.

    É o que separa uma remenda declarada de uma remenda podre: a troca é por
    sufixo exato, e um sufixo que deixa de casar faria a frase da GTK voltar
    inteira à tela, calada.

    MORDIDA: mude uma letra de `FIM_DA_EXIGENCIA_NA_GTK` e esta régua reprova.
    """
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria
    from hefesto_dualsense4unix.profiles.simple_match import exigencia_invisivel

    match = MatchCriteria(window_class=["steam_app_3357650"],
                          process_name=["PRAGMATA.exe"])
    do_produto = exigencia_invisivel(match)
    assert do_produto, "o produto parou de contar a exigência escondida"
    assert do_produto.endswith(a10_perfis.FIM_DA_EXIGENCIA_NA_GTK), (
        f"o fim da frase do produto mudou e a remenda desta aba não o alcança "
        f"mais:\n    produto  {do_produto!r}\n"
        f"    esperava {a10_perfis.FIM_DA_EXIGENCIA_NA_GTK!r}")


def test_nenhuma_pagina_desta_interface_oferece_o_modo_avancado() -> None:
    """A medição que sustenta a decisão [02], refeita a cada execução.

    Se um dia esta interface GANHAR um "Modo avançado", a substituição do fim da
    frase deixa de fazer sentido — e é melhor descobrir por uma régua vermelha
    do que por uma tela que manda ela a um lugar que agora existe e não é
    citado.
    """
    achados = [p.name for p in onde.paginas(publicado=True)
               if "Modo avançado" in p.read_text(encoding="utf-8")
               and p.name.startswith(("0", "1"))]
    assert not achados, (
        f"as páginas {achados} passaram a ter um “Modo avançado” — releia a "
        f"decisão [02] do PO antes de manter a substituição do fim da frase")


# ---------------------------------------------------------------------------
# [03] a frase da Prioridade
# ---------------------------------------------------------------------------
def test_a_frase_da_prioridade_do_desenho_e_a_que_ela_aprovou(
    gerador: Any,
) -> None:
    """O desenho recita a frase DELA, e a régua a lê do PRODUTO.

    Decisão nº11 dela (02/09) e decisão [03] do PO (04/09): a frase entra no
    desenho, e vão as duas — a dela primeiro. O literal mora num lugar só
    (`aba10.FRASE_DA_PRIORIDADE_DELA`) e esta régua o amarra ao
    `prioridade_dica` que `perfis_web` devolve: divergirem é a tela recitando
    uma versão que o produto já abandonou.

    MORDIDA: mude uma palavra de `FRASE_DA_PRIORIDADE_DELA` e ela reprova
    mostrando as duas.
    """
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    do_produto = perfis_web._pacote_do_editor(
        Profile(name="régua", match=MatchAny()))["prioridade_dica"]
    assert do_produto == gerador.FRASE_DA_PRIORIDADE_DELA, (
        "o desenho e o produto discordam sobre a frase da Prioridade:\n"
        f"    desenho {gerador.FRASE_DA_PRIORIDADE_DELA!r}\n"
        f"    produto {do_produto!r}")

    html = _pagina(publicado=False)
    dica = re.search(r'data-hef="editor\.prioridade\.dica" title="([^"]*)"', html)
    assert dica is not None, "a dica da Prioridade perdeu o `title` do desenho"
    assert dica.group(1) == gerador.DICA_DA_PRIORIDADE
    assert dica.group(1).startswith(do_produto), (
        "a frase DELA deixou de vir primeiro — a explicação do Universal "
        "responde a pergunta que a dela deixa aberta, e não a substitui")


def test_o_produto_continua_sem_tentar_pintar_a_dica_da_prioridade() -> None:
    """A frase mora no desenho; emiti-la apagaria o trilho e o número.

    O `<span>` que carrega a dica tem DOIS filhos-elemento (o trilho com o
    slider dentro, e o número ao lado), e o pintor termina em `textContent` —
    escrever ali os apaga. É por isso que `editor.prioridade.dica` está em
    `NAO_PINTAVEIS`, e é por isso que a decisão [03] pôs a frase no desenho.

    MORDIDA: tire `editor.prioridade.dica` de `NAO_PINTAVEIS` e esta régua
    reprova.
    """
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    fora = _emitido(Profile(name="régua", match=MatchAny()))
    assert "editor.prioridade.dica" not in fora, (
        "o produto voltou a mandar a dica da Prioridade — ela apagaria o "
        "trilho e o número que moram dentro do mesmo `<span>`")


# ---------------------------------------------------------------------------
# [04] o campo do jogo se corrige
# ---------------------------------------------------------------------------
def test_o_endereco_colado_vira_o_numero_na_frente_dela(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any,
) -> None:
    """Colar o endereço da loja grava o número — e o CAMPO passa a mostrá-lo.

    Decisão [04] do PO: *"Só a tira, e o campo se corrige."* A regra sempre
    guardou o número; o que ficava errado era a tela, mostrando o endereço
    colado sobre uma regra que já guardava outra coisa — e assim ficava até ela
    trocar de perfil, porque `editor.jogo` não se repinta no tique.

    MORDIDA: tire o `**{"editor.jogo": …}` do `return` de `editor_jogo` e esta
    régua reprova dizendo que a resposta não corrige o campo.
    """
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    prof = Profile(name="régua", match=MatchAny())
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: [prof])
    monkeypatch.setattr(loader, "load_profile", lambda *a, **k: prof)
    gravados: list[Any] = []
    monkeypatch.setattr(a10_perfis, "_gravar",
                        lambda p_, ctx, p, **k: gravados.append(p_))
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "régua", raising=False)

    ctx = Contexto(state={"active_profile": "régua"}, mesa=list(MESA),
                   conectados=list(MESA), estados={})
    colado = "https://store.steampowered.com/app/1599660/Sackboy/"
    resposta = a10_perfis.editor_jogo(ctx, {"valor": colado, "evento": "change"},
                                      None)
    assert resposta is not None, "o gesto não respondeu"
    assert resposta["mesa"]["editor.jogo"] == "1599660", (
        f"o campo continua mostrando o endereço colado: "
        f"{resposta['mesa']['editor.jogo']!r}")
    assert gravados, "o gesto não gravou o perfil"


def test_o_campo_nunca_volta_vazio_da_correcao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Corrigir não pode APAGAR o que ela digitou.

    `simple_extra` devolve `""` para uma regra que não guarda extra nenhum, e o
    `escrever()` do piloto troca vazio por travessão: sem o piso, o campo
    diria "não sei" sobre um valor que ela acabou de escrever e que está no
    disco.

    MORDIDA: tire o `or texto` do `return` de `editor_jogo` e esta régua
    reprova.
    """
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    prof = Profile(name="régua", match=MatchAny())
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: [prof])
    monkeypatch.setattr(loader, "load_profile", lambda *a, **k: prof)
    monkeypatch.setattr(a10_perfis, "_gravar", lambda *a, **k: None)
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "régua", raising=False)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.profiles.simple_match.simple_extra",
        lambda *a, **k: "")

    ctx = Contexto(state={"active_profile": "régua"}, mesa=list(MESA),
                   conectados=list(MESA), estados={})
    resposta = a10_perfis.editor_jogo(
        ctx, {"valor": "Cyberpunk2077.exe", "evento": "change"}, None)
    assert resposta is not None
    assert resposta["mesa"]["editor.jogo"] == "Cyberpunk2077.exe", (
        "a correção apagou o que ela digitou")


# ---------------------------------------------------------------------------
# [05] a tira do desfecho, em duas linhas
# ---------------------------------------------------------------------------
def test_a_tira_do_desfecho_tem_duas_linhas_reservadas() -> None:
    """A metade que AVISA mora no fim da frase, e é a que a linha única comia.

    **A RÉGUA SE INVERTEU EM 05/09/2026, e a última asserção era o defeito.**
    Ela exigia ``height:30px`` e ``visibility:hidden`` na MESMA regra, dizendo
    *"a tira deixou de RESERVAR o espaço"* — e o espaço reservado em repouso são
    **37px de banda morta debaixo do título "Perfis"**, que ela viu e chamou de
    *"espaço vertical bizarro desnecessário"*. As duas linhas continuam
    cobradas; o que mudou de regra é ONDE elas valem: a altura mora na ``.on``,
    e a de repouso tem de colapsar. A medição em pixels está em
    ``test_a_aba10_nao_reserva_banda_morta_no_titulo.py``.

    MORDIDA: devolva `height:30px;margin-top:7px` à regra `.desfecho{…}` do
    `aba10.CSS`, regere, e esta régua reprova.
    """
    html = _pagina(publicado=False)
    regra = re.search(r"\.desfecho\{[^}]*\}", html)
    assert regra is not None, "a regra da tira do desfecho sumiu do CSS"
    corpo = regra.group(0)
    acesa = re.search(r"\.desfecho\.on\{[^}]*\}", html)
    assert acesa is not None, "a regra `.desfecho.on` sumiu do CSS"
    assert "height:30px" in acesa.group(0), (
        f"a tira acesa voltou a uma linha: {acesa.group(0)}")
    assert "-webkit-line-clamp:2" in corpo, (
        f"sem o `line-clamp` a frase longa vaza para fora da caixa: {corpo}")
    assert "white-space:nowrap" not in corpo, (
        f"o `nowrap` voltou, e com ele a frase continua numa linha só: {corpo}")
    assert "visibility:hidden" in corpo, (
        f"a tira vazia deixou de se esconder — ela apareceria como uma faixa em "
        f"branco em toda tela sem recado: {corpo}")
    assert "height:0" in corpo and "margin-top:0" in corpo, (
        f"a tira VAZIA voltou a reservar espaço: {corpo}")


def test_a_altura_reservada_e_a_conta_das_linhas_que_a_tira_mostra() -> None:
    """``height`` = ``line-height`` vezes ``line-clamp`` — na regra que ABRE a tira.

    É a metade que some sem sintoma: `-webkit-line-clamp:2` com `height:15px`
    reticencia na segunda linha e depois a ESCONDE com o `overflow` — a tela
    volta a cortar o aviso, e o CSS jura que não. Um `height:45px` faria o
    contrário: 15px de espaço morto sobre a lista de perfis a cada recado.

    NÃO SE DIGITA O 30: os três números são lidos das regras e a conta é feita.
    O ``height`` mudou de casa em 05/09 (ver a régua acima); os outros dois
    continuam na regra de repouso, que é onde a caixa se define.
    """
    html = _pagina(publicado=False)
    repouso = re.search(r"\.desfecho\{[^}]*\}", html)
    acesa = re.search(r"\.desfecho\.on\{[^}]*\}", html)
    assert repouso is not None and acesa is not None
    numero = {chave: int(re.search(rf"{chave}:(\d+)", repouso.group(0)).group(1))  # type: ignore[union-attr]
              for chave in ("line-height", "-webkit-line-clamp")}
    numero["height"] = int(
        re.search(r"height:(\d+)px", acesa.group(0)).group(1))  # type: ignore[union-attr]
    assert numero["height"] == numero["line-height"] * numero["-webkit-line-clamp"], (
        f"a tira acesa reserva {numero['height']}px para "
        f"{numero['-webkit-line-clamp']} linha(s) de {numero['line-height']}px "
        f"— ou ela corta o aviso, ou sobra espaço morto sobre a lista")


@pytest.fixture()
def gerador() -> Any:
    """O ``aba10.py`` importado como o gerador se importa — só no TESTE.

    Ele insere a própria pasta no ``sys.path`` e lê o ``monta``, que abre seis
    arquivos do repositório no import. É barato aqui e é justamente o que o
    produto não pode fazer — por isso o pacote copia a forma em vez de importar.
    """
    import sys
    from pathlib import Path

    pytest.importorskip(
        "hefesto_dualsense4unix.interface.monta",
        reason="o gerador lê o repositório no import; num pacote instalado não há",
    )
    pasta = Path(onde.__file__).parent
    if str(pasta) not in sys.path:
        sys.path.insert(0, str(pasta))
    import aba10  # type: ignore[import-not-found]

    return aba10
