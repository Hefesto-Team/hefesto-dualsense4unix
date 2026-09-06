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
    # **O TAMANHO PASSOU A SER O DA TABELA, E NÃO O DA MESA — 05/09/2026.** A
    # hipótese que esta régua matou continua morta, e com número: um bloco a
    # MAIS que a tabela empurraria os valores para a linha seguinte. O que
    # mudou é o alvo da conta. O pacote emite as QUATRO linhas por decisão dela
    # (*"os svgs não deveriam aparecer prós demais controles desconectados"*):
    # o `forEach` do bootstrap escreve `''` no que sobra, e `''` APAGA uma
    # classe sem nunca ACENDÊ-LA — o lugar vazio não tinha como ligar o `fora`
    # que esconde os glifos. A régua fica MAIS estrita: o número não depende
    # mais de quantos controles estão na mesa, então uma mesa que encolha não
    # pode mais encolher a lista sem reprovar.
    largura = len(a10_perfis.SECOES_DA_COLUNA)
    esperado = a10_perfis.LUGARES_DA_TABELA * largura
    for quantos in (1, 2):
        fora = _emitido(_perfil({MESA[0]["uniq"]: ["leds"]}), mesa=MESA[:quantos])
        assert len(fora["guarda.secao"]) == esperado, (
            f"com {quantos} controle(s) na mesa a lista tem "
            f"{len(fora['guarda.secao'])} valores, e a tabela tem "
            f"{a10_perfis.LUGARES_DA_TABELA} linhas de {largura} — {esperado}")
        # E OS BLOCOS QUE SOBRAM SÃO VAZIOS, não repetição do vizinho.
        for linha in range(quantos, a10_perfis.LUGARES_DA_TABELA):
            bloco = fora["guarda.secao"][linha * largura:(linha + 1) * largura]
            assert bloco == [""] * largura, (
                f"a linha {linha + 1} não tem controle e veio com {bloco!r}")


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

    **O ARGUMENTO DESTA DOCSTRING CADUCOU EM 06/09/2026 — ONDA5-10-01, decisão
    10-Q2 dela.** Ele dizia que a frase *"precisa de um fim que esta tela
    alcança"*, e o fim que ela alcançava era mandar usar
    ``hefesto-dualsense4unix profile`` na linha de comando. A palavra dela sobre
    isso foi ***"Isso é erro do produto."*** — **o fim agora é o FATO**, e para
    aí. A régua não mudou uma linha: ela sempre comparou contra a CONSTANTE, e
    é por isso que continua verde com um fim novo. Quem cobra que o fim não
    volte a mandar ninguém para fora é
    ``test_a_tela_nao_manda_ela_para_fora_do_produto``.

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


def test_o_matcher_nao_nomeia_botao_de_tela_nenhuma() -> None:
    """A REMENDA ACABOU — 05/09/2026, e esta régua guarda o que ficou no lugar.

    ELA COBRAVA UM SUFIXO. Até aqui, `exigencia_invisivel` devolvia a frase com
    o fim *"Ligue o Modo avançado para ver e mudar."* — o nome de um interruptor
    do `main.glade` — e esta aba TROCAVA esse sufixo pelo caminho que ela
    alcança. A régua guardava a troca: *"no dia em que o produto mudar o fim,
    ela reprova AQUI"*.

    O CONSERTO DE VERDADE ERA OUTRO, e estava escrito no próprio bloco que a
    remenda documentava: um matcher de `profiles/` não pode nomear um botão de
    uma tela. O FATO saiu para `exigencia_invisivel` e o CAMINHO para cada
    tela — `simple_match.CAMINHO_DA_JANELA_GTK` na janela estável, o
    `FIM_DA_EXIGENCIA_AQUI` aqui.

    O QUE ESTA RÉGUA COBRA AGORA é o que a remenda existia para impedir, sem a
    remenda: que a frase do produto não volte a mandar ninguém a um botão.

    A MORDIDA: devolva `CAMINHO_DA_JANELA_GTK` ao fim de `exigencia_invisivel`
    e este teste reprova nomeando a peça de tela que voltou ao matcher.
    """
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria
    from hefesto_dualsense4unix.profiles.simple_match import (
        CAMINHO_DA_JANELA_GTK,
        exigencia_invisivel,
    )

    match = MatchCriteria(window_class=["steam_app_3357650"],
                          process_name=["PRAGMATA.exe"])
    do_produto = exigencia_invisivel(match)
    assert do_produto, "o produto parou de contar a exigência escondida"
    assert CAMINHO_DA_JANELA_GTK not in do_produto, (
        f"o caminho da janela GTK voltou para dentro do matcher:\n"
        f"    {do_produto!r}\n"
        f"Um matcher de `profiles/` não sabe que botões cada tela desenhou, e "
        f"esta interface não tem 'Modo avançado' nenhum.")
    assert "Modo avançado" not in do_produto, (
        "o matcher voltou a nomear uma peça da janela GTK")

    # E O FIM DESTA TELA CONTINUA SENDO SOMADO — 06/09/2026, ONDA5-10-01.
    #
    # AQUI ESTAVA ESCRITO *"sem isto o aviso vira beco sem saída: ela lê que
    # falta um campo e não lê onde mexer"*, e essa é exatamente a frase que a
    # decisão 10-Q2 substituiu: o "onde mexer" era a linha de comando, e a
    # palavra dela foi *"Isso é erro do produto"*. O aviso PARA no fato de
    # propósito — o beco sem saída é o produto, não a frase, e o conserto de um
    # beco é abrir a saída (foi o que o Passo 3 fez com o "Detectar"), nunca
    # pintar uma placa apontando para fora.
    #
    # O que esta asserção guarda continua valendo e é outra coisa: que a aba
    # some o fim DELA ao fato do produto, em vez de reescrever o fato.
    daqui = a10_perfis._exigencia_para_esta_tela(match)
    assert daqui.startswith(do_produto), (
        f"esta aba deixou de partir do fato do produto: {daqui!r}")
    assert daqui.endswith(a10_perfis.FIM_DA_EXIGENCIA_AQUI), (
        f"esta aba deixou de somar o caminho dela: {daqui!r}")


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


# ---------------------------------------------------------------------------
# ONDA5-10-01 · o Hefesto não manda ninguém para o terminal (decisão 10-Q2)
# ---------------------------------------------------------------------------
#: AS FORMAS QUE `from_simple_choice` SABE ESCREVER e que NÃO são chave de
#: ``SIMPLE_MATCH_PRESETS``: elas moram em ``if``s do corpo da função, e por
#: isso nenhuma varredura de dicionário as alcança. Quem escrever a sétima vem
#: aqui — e apagar um nome desta tupla é um ato que se vê no diff, ao contrário
#: de esquecer um rótulo.
FORMAS_FORA_DO_DICIONARIO = ("game", "steam_game", "janela")


def test_a_classe_de_uma_janela_fecha_o_round_trip() -> None:
    """Escreve "janela", relê, e tem de voltar "janela" — com a classe junto.

    É o Passo 1 da ONDA5-10-01, e o round-trip é a prova inteira: uma forma que
    o produto ESCREVE e não RECONHECE abre o perfil travado, com o seletor
    rebaixado e sem ninguém ter mexido em nada. É o defeito R-12.

    A SEGUNDA METADE PROTEGE A ORDEM: um ``steam_app_<id>`` **também** é um
    ``window_class`` de um elemento. Se a detecção da forma nova correr antes de
    ``_detect_steam_appid``, todo perfil de jogo da Steam passa a abrir como
    "Jogo (pela janela)" — e a caixinha do Steam Input, que só nasce com "Jogo
    da Steam" escolhido, some da tela dela.

    MORDIDA: apague o ramo do ``"janela"`` em ``detect_simple_preset`` e a
    primeira asserção reprova com ``None`` — que é o perfil travado de volta.
    Mova o ramo para ANTES do ``_detect_steam_appid`` e reprova a segunda.
    """
    from hefesto_dualsense4unix.profiles.simple_match import (
        MSG_JANELA_SEM_CLASSE,
        detect_simple_preset,
        from_simple_choice,
        simple_extra,
    )

    escrito = from_simple_choice("janela", "GrimFandango")
    assert list(escrito.window_class) == ["GrimFandango"], (
        f"a escrita não guardou a classe como ela veio: {escrito!r}")
    assert detect_simple_preset(escrito) == "janela", (
        f"a leitura não reconhece o que a escrita gravou: "
        f"{detect_simple_preset(escrito)!r} — o perfil abriria travado")
    assert simple_extra(escrito) == "GrimFandango", (
        f"o campo livre volta {simple_extra(escrito)!r} em vez da classe — a "
        f"tela abriria VAZIA sobre um perfil que tem regra no disco")

    da_steam = from_simple_choice("steam_game", "1599660")
    assert detect_simple_preset(da_steam) == "steam_game", (
        "um `steam_app_<id>` deixou de sair como jogo da Steam — a forma nova "
        "roubou o round-trip que o R-12 existe para proteger")
    assert simple_extra(da_steam) == "1599660"

    # E A RECUSA FALANTE, irmã do `MSG_JOGO_SEM_NOME`: campo obrigatório em
    # branco não degrada em silêncio para uma regra que nunca casa.
    with pytest.raises(ValueError, match="Diga a janela do jogo"):
        from_simple_choice("janela", "   ")
    from hefesto_dualsense4unix.profiles.simple_match import MENSAGENS_DE_GENTE
    assert MSG_JANELA_SEM_CLASSE in MENSAGENS_DE_GENTE, (
        "a frase nova não está declarada como frase de gente — a janela a "
        "trocaria pelo genérico “Revise os campos do perfil”")


def test_toda_forma_que_o_produto_escreve_tem_rotulo_nas_duas_telas() -> None:
    """Nenhuma forma nasce órfã de rótulo — e a que não tem, se DECLARA.

    ELA REPROVAVA ANTES DO PASSO 2, e de propósito: ``browser``, ``terminal`` e
    ``editor`` existem no produto e não no desenho dela. Eles não passaram a ter
    rótulo — passaram a estar DECLARADOS em ``perfis_web.FORA_DO_DESENHO``, que
    é a diferença entre dívida e esquecimento.

    A SEGUNDA ASSERÇÃO é a do campo livre: toda forma cujo ``simple_extra``
    devolve alguma coisa tem de estar em ``_IDS_COM_CAMPO_LIVRE``. Sem isso o
    ``_populate_editor`` escreve ``""`` no campo e a tela abre VAZIA sobre um
    perfil que tem regra no disco — o defeito que o R-12 já cobrou do
    ``steam_game``.

    MORDIDA: tire ``("janela", …)`` de ``_APLICA_A_ITEMS`` e a primeira reprova
    nomeando a forma órfã. Tire só ``"janela"`` de ``_IDS_COM_CAMPO_LIVRE`` e
    reprova a segunda.
    """
    from hefesto_dualsense4unix.app.actions import profiles_actions as pa
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria
    from hefesto_dualsense4unix.profiles.simple_match import (
        SIMPLE_MATCH_PRESETS,
        simple_extra,
    )

    formas = tuple(SIMPLE_MATCH_PRESETS) + FORMAS_FORA_DO_DICIONARIO
    na_gtk = dict(pa._APLICA_A_ITEMS)
    orfas = [f for f in formas
             if f not in na_gtk
             or (f not in perfis_web.AMBIENTE_DO_PRESET
                 and f not in perfis_web.FORA_DO_DESENHO)]
    assert not orfas, (
        f"as formas {orfas} o produto sabe ESCREVER e alguma tela não sabe "
        f"MOSTRAR, sem declaração nenhuma. Um perfil gravado assim abre com o "
        f"seletor travado — e ninguém fica sabendo por quê. Dê rótulo em "
        f"`AMBIENTE_DO_PRESET` e em `_APLICA_A_ITEMS`, ou declare a ausência "
        f"em `FORA_DO_DESENHO`, com a razão.")
    assert not (set(perfis_web.AMBIENTE_DO_PRESET)
                & set(perfis_web.FORA_DO_DESENHO)), (
        "uma forma está nas duas tabelas — com rótulo E declarada ausente")

    # O CAMPO LIVRE, forma a forma: a régua PERGUNTA ao `simple_extra` em vez
    # de digitar a lista das que têm campo.
    exemplos = {
        "game": MatchCriteria(process_name=["eldenring"]),
        "steam_game": MatchCriteria(window_class=["steam_app_1599660"]),
        "janela": MatchCriteria(window_class=["GrimFandango"]),
    }
    for chave, match in exemplos.items():
        if simple_extra(match):
            assert chave in pa._IDS_COM_CAMPO_LIVRE, (
                f"a forma {chave!r} guarda um valor que `simple_extra` devolve "
                f"({simple_extra(match)!r}) e o editor não abre o campo livre "
                f"para ela — a tela mostraria vazio sobre a regra do disco")
        assert chave in pa._RADIO_IDS, (
            f"a forma {chave!r} não está em `_RADIO_IDS`: `_select_radio` cai "
            f"em “any” e o perfil abre dizendo “Qualquer”, que é o "
            f"rebaixamento que o R-12 existe para impedir")


def test_o_detectar_cumpre_o_que_o_title_promete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O botão promete "qualquer lugar" no ``title``, e agora entrega.

    A RÉGUA LÊ A PROMESSA, não a digita: ela recorta o ``title`` do
    ``data-hef-gesto="detectar"`` da página e confere que ele continua dizendo
    *"qualquer lugar"*. Se alguém apagar a promessa, esta metade cai — e aí a
    régua diz que a promessa sumiu, em vez de cobrar uma frase que ninguém faz
    mais.

    O DUBLÊ USA UMA CLASSE QUE NÃO É DA STEAM, e isso é o teste inteiro: um
    ``steam_app_123`` mediria o ramo velho e daria verde sobre o Passo 3
    completo. ``GrimFandango`` é a classe de um perfil de fábrica de verdade
    (``assets/profiles_default/point_and_click.json``).

    MORDIDA: devolva o ``raise`` ao ramo do ``appid is None`` em ``detectar`` e
    esta régua reprova — o gesto levanta em vez de gravar.
    """
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
    from hefesto_dualsense4unix.profiles.simple_match import detect_simple_preset

    html = _pagina(publicado=False)
    botao = re.search(r'<button[^>]*data-hef-gesto="detectar"[^>]*>', html)
    assert botao is not None, "o botão Detectar sumiu do desenho"
    titulo = re.search(r'title="([^"]*)"', botao.group(0))
    assert titulo is not None, "o Detectar perdeu a dica que explica o que ele faz"
    assert "qualquer lugar" in titulo.group(1), (
        f"o `title` deixou de prometer jogo de qualquer lugar: "
        f"{titulo.group(1)!r} — se a promessa saiu, revise a decisão 10-Q2 "
        f"antes de mexer nesta régua")

    prof = Profile(name="Grim", match=MatchAny())
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: [prof])
    monkeypatch.setattr(loader, "load_profile", lambda *a, **k: prof)
    monkeypatch.setattr(loader, "save_profile", lambda *a, **k: None)
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "Grim", raising=False)

    class _PonteMuda:
        def profile_switch(self, nome: str) -> bool:
            return True

        def chamar(self, metodo: str, *a: Any, **kw: Any) -> bool:
            return True

    ctx = Contexto(state={"active_profile": None,
                          "window_detect_last_class": "GrimFandango"},
                   mesa=list(MESA), conectados=list(MESA), estados={})
    fora = a10_perfis.detectar(ctx, {}, _PonteMuda())

    assert list(prof.match.window_class) == ["GrimFandango"], (
        f"o Detectar não gravou a classe que o detector viu: {prof.match!r}")
    assert detect_simple_preset(prof.match) == "janela", (
        "a regra que o botão gravou não volta como forma que a tela mostra")
    assert isinstance(fora, dict) and fora.get("mesa"), (
        "o Detectar gravou a regra e não devolveu notícia nenhuma")
    assert fora["mesa"].get("editor.jogo") == "GrimFandango", (
        f"o campo “Nome do Jogo” não recebeu a classe que passou a valer: "
        f"{fora['mesa'].get('editor.jogo')!r} — ele continuaria mostrando o "
        f"que havia antes do clique, sobre uma regra que já é outra")


def test_a_tela_nao_manda_ela_para_fora_do_produto() -> None:
    """Nenhum texto desta aba manda a pessoa para o terminal. Decisão 10-Q2.

    ***"Isso é erro do produto."*** — ela, 05/09/2026, sobre a frase que
    terminava mandando usar ``hefesto-dualsense4unix profile`` na linha de
    comando. E o glossário da casa
    (``docs/A-LINGUA-DESTA-CASA-…``) proíbe em texto de tela *"linha de
    comando"* e qualquer frase que mande a pessoa procurar um botão ou uma
    janela que não existe.

    A VARREDURA É POR CONSTANTE, e não por arquivo: são os textos de tela desta
    aba que têm dono declarado. O corpo do ``detectar`` entra pelas STRINGS
    LITERAIS dele, que é onde a terceira boca vivia — a recusa mora num
    ``raise``, não numa constante.

    **E ELA LÊ AS STRINGS, NUNCA O FONTE CRU — a armadilha é de 05/09/2026 e
    esta régua caiu nela na primeira execução.** Um ``inspect.getsource`` pega
    a DOCSTRING junto, e a docstring do ``detectar`` CITA a recusa antiga para
    explicar por que ela saiu: o comentário que avisa vira a primeira ocorrência
    do arquivo, e a régua reprova a explicação em vez do defeito. Prosa não
    chega à tela dela; ``ast`` separa uma coisa da outra.

    MORDIDA: devolva o fim antigo a ``FIM_DA_EXIGENCIA_AQUI`` (ou a
    ``AMBIENTE_QUE_A_TELA_NAO_MOSTRA``, ou o ``raise`` velho do ``detectar``) e
    esta régua reprova nomeando a constante e o trecho proibido.
    """
    import ast
    import inspect
    import textwrap

    proibidos = ("linha de comando", "hefesto-dualsense4unix profile",
                 "Modo avançado")
    textos: dict[str, str] = {
        "perfis_web.AMBIENTE_QUE_A_TELA_NAO_MOSTRA":
            perfis_web.AMBIENTE_QUE_A_TELA_NAO_MOSTRA,
        "a10_perfis.FIM_DA_EXIGENCIA_AQUI": a10_perfis.FIM_DA_EXIGENCIA_AQUI,
        "perfis_web.LISTA_VAZIA": perfis_web.LISTA_VAZIA,
        "perfis_web.GUARDA_SEM_MESA": perfis_web.GUARDA_SEM_MESA,
        "perfis_web.GUARDA_SEM_DAEMON": perfis_web.GUARDA_SEM_DAEMON,
        "perfis_web.ESTILO_APLICA_E_SAI": perfis_web.ESTILO_APLICA_E_SAI,
    }
    textos.update({f"perfis_web.GESTOS_SEM_MOTOR[{k!r}]": v
                   for k, v in perfis_web.GESTOS_SEM_MOTOR.items()})
    # A RECUSA DO `detectar` é texto de tela e mora num `raise`. A régua junta
    # as STRINGS do gesto — a docstring de fora, porque ela cita a recusa velha
    # para explicar por que ela saiu (ver a nota da armadilha, acima).
    fn = ast.parse(textwrap.dedent(inspect.getsource(a10_perfis.detectar))).body[0]
    assert isinstance(fn, ast.FunctionDef)
    # O PRIMEIRO `Expr` É A DOCSTRING, e a exclusão é por POSIÇÃO e não por
    # texto: `ast.get_docstring` devolve o valor LIMPO (dedentado), que nunca é
    # igual ao literal cru — comparar os dois deixava a docstring passar.
    sem_doc = fn.body[1:] if (fn.body and isinstance(fn.body[0], ast.Expr)
                              and isinstance(getattr(fn.body[0], "value", None),
                                             ast.Constant)) else fn.body
    textos["a10_perfis.detectar (as frases)"] = " ".join(
        n.value for corpo in sem_doc for n in ast.walk(corpo)
        if isinstance(n, ast.Constant) and isinstance(n.value, str))

    achados = [f"{onde_}: “{p}”" for onde_, t in textos.items()
               for p in proibidos if p in t]
    assert not achados, (
        "esta tela voltou a mandar a pessoa para fora do produto:\n  "
        + "\n  ".join(achados)
        + "\nO Hefesto não explica a própria falha — ele a conserta. Se a "
          "regra não cabe na tela, a frase diz o que a regra É e para.")

    # E O FATO CONTINUA SENDO DITO: podar o fim não pode ter emudecido a frase.
    assert "não sabe mostrar" in perfis_web.AMBIENTE_QUE_A_TELA_NAO_MOSTRA
    assert "não mostra esses campos" in a10_perfis.FIM_DA_EXIGENCIA_AQUI
    # O CAMINHO DA JANELA GTK NÃO SE TOCA: lá o "Modo avançado" existe.
    from hefesto_dualsense4unix.profiles.simple_match import CAMINHO_DA_JANELA_GTK

    assert "Modo avançado" in CAMINHO_DA_JANELA_GTK, (
        "a poda alcançou o caminho da janela GTK, onde a frase é VERDADE — "
        "seria trocar um defeito por outro")


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


# ---------------------------------------------------------------------------
# ONDA5-10-02 · o rótulo ao lado do campo (10-Q4) e a metade curta (10-Q5)
# ---------------------------------------------------------------------------
def test_o_rotulo_do_jogo_separa_a_rotina_do_erro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Três entradas, três respostas — e a terceira ACENDE, as duas primeiras não.

    O BOOLEANO É O PONTO INTEIRO desta régua. Até 06/09 `_jogo_reconhecido`
    devolvia só a PRIMEIRA metade do par, e o ``é_alerta`` que
    ``frase_do_campo_do_jogo`` devolve morria ali — o mesmo bit que separa *"não
    instalado aqui (o número vale)"*, que é o jogo que ela ainda vai comprar, de
    *"não reconheci este endereço"*, que é erro de digitação. Sem ele o rótulo
    sairia da mesma cor nos dois casos.

    ELA LÊ AS CONSTANTES DE `jogos_locais` em vez de digitar as frases: foi
    digitando o que devia LER que esta casa perdeu onze réguas em 26/08.

    MORDIDA: faça `_jogo_reconhecido` devolver só a frase (ou fixe o segundo
    membro do par em `False`) e esta régua reprova no endereço malformado.
    """
    from hefesto_dualsense4unix.integrations import jogos_locais

    monkeypatch.setattr(a10_perfis, "_nomes_dos_jogos",
                        lambda: {"1245620": "Elden Ring"})

    instalado = a10_perfis._jogo_reconhecido("1245620")
    assert instalado == ("Elden Ring", False), (
        f"o appid instalado devia devolver o NOME sem alerta: {instalado!r}")

    ausente = a10_perfis._jogo_reconhecido("999999")
    assert ausente == (jogos_locais.MSG_FORA_DA_MAQUINA, False), (
        f"o jogo que ela ainda vai comprar é ROTINA, não alerta: {ausente!r}")

    # `parece_endereco` é quem decide o que "parece endereço" — a régua não
    # inventa a forma, usa a que o dono reconhece.
    malformado = "store.steampowered.com/app/"
    assert jogos_locais.parece_endereco(malformado), (
        "a semente desta régua deixou de parecer endereço para o dono — "
        "troque a semente, não a asserção")
    erro = a10_perfis._jogo_reconhecido(malformado)
    assert erro == (jogos_locais.MSG_NAO_RECONHECI, True), (
        f"o endereço malformado tem de acender o alerta: {erro!r}")

    vazio = a10_perfis._jogo_reconhecido("")
    assert vazio == ("", False), (
        f"campo vazio é silêncio, e alerta em campo em branco é ruído: {vazio!r}")


@pytest.mark.parametrize("publicado", [False, True], ids=["bancada", "publicada"])
def test_o_rotulo_do_jogo_tem_onde_pousar(publicado: bool) -> None:
    """Os dois sentidos: endereço emitido sem lugar, e lugar sem quem escreva.

    É o espelho de `test_a_marca_acende_exatamente_quando_a_frase_existe`, um
    degrau acima: lá o par é marca/frase, aqui é PRODUTO/DESENHO. Um rótulo
    emitido para um endereço que a página não tem cai no vazio sem notícia
    (foi o defeito do `ativo`, em 02/09); um `<span>` no desenho que ninguém
    escreve é desenho congelado se passando por produto.

    A PÁGINA PUBLICADA AINDA NÃO TEM O RÓTULO, e é por isso que os dois nomes
    estão em `ESPERANDO_A_PUBLICACAO` — publicar é ato dela. Esta régua cobra
    exatamente essa declaração: enquanto o endereço não estiver na publicada,
    ele tem de estar na lista; quando ela publicar, a lista tem de esvaziar.

    MORDIDA: tire `{rotulo_do_jogo()}` do `aba10.MIOLO` e regere — o ramo da
    bancada reprova. Tire as duas entradas de `ESPERANDO_A_PUBLICACAO` e o ramo
    da publicada reprova.
    """
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile

    html = _pagina(publicado)
    fora = _emitido(Profile(name="Elden Ring", match=MatchCriteria(
        window_class=["steam_app_1245620"])))

    for endereco in ("editor.jogo.rotulo", "editor.jogo.alerta"):
        assert endereco in fora, (
            f"o produto parou de emitir `{endereco}` — o `<span>` do desenho "
            f"fica com o que o mockup cravou, para sempre")
        tem_lugar = f'data-hef="{endereco}"' in html
        declarado = endereco in a10_perfis.ESPERANDO_A_PUBLICACAO
        assert tem_lugar or declarado, (
            f"`{endereco}` sai do pacote e a página "
            f"{'publicada' if publicado else 'da bancada'} não tem onde pô-lo — "
            f"e ele não está declarado em `ESPERANDO_A_PUBLICACAO`")
        if publicado and tem_lugar:
            assert not declarado, (
                f"`{endereco}` já chegou à página publicada e continua na lista "
                f"de espera — a declaração envelheceu, e uma lista que descreve "
                f"o passado é a régua se desligando sozinha. Tire no mesmo commit")

    if not publicado:
        # A BANCADA TEM DE TER OS TRÊS `<span>`: o que acende, o que pinta e o
        # que escreve. Sem o primeiro, `escrever()` troca o vazio por `'—'` e a
        # tela ganha um travessão solto ao lado do campo em todo perfil que não
        # é da Steam.
        assert html.count('data-hef="editor.jogo.rotulo"') == 2, (
            "o rótulo do jogo perdeu um dos dois endereços na bancada — sem o "
            "`classe` ele acende sempre, sem o `<span>` ele nunca escreve")
        assert ('<span class="rot" data-hef="editor.jogo.rotulo"'
                ' data-hef-alvo="classe">') in html, (
            "o `<span>` de fora do rótulo perdeu o alvo `classe`")
        assert ('data-hef="editor.jogo.alerta" data-hef-alvo="classe"'
                ' data-hef-classe="alerta"') in html, (
            "o rótulo perdeu a tinta do alerta — «não reconheci este endereço» "
            "sairia com a cara de «não instalado aqui»")
        assert '<span data-hef="editor.jogo.rotulo"></span>' in html, (
            "o rótulo não nasce VAZIO no desenho — um exemplo aqui é a tela "
            "afirmando um jogo que o perfil dela não tem")


def test_a_tira_diz_a_metade_curta(monkeypatch: pytest.MonkeyPatch) -> None:
    """A carona longa não cabe nas duas linhas; a curta cabe — e a 07 não muda.

    **O TETO É MEDIDO, e não digitado aqui**: `aba10.CABEM_NA_TIRA` é o número
    que saiu da bissecção no Chrome sobre a `.desfecho` acesa (413 caracteres a
    1140px, 11px, `line-height:15px`, `-webkit-line-clamp:2`).

    **E A PREMISSA DA SPRINT CAIU AO SER MEDIDA.** A ONDA5-10-02 dizia que DUAS
    frases do produto passavam do teto *por serem longas* — 212 e ~290
    caracteres. Elas não passam: o que estoura é o NÚMERO DE JOGOS, porque
    `steam_launch_options.lista_de_jogos` não tem teto. Com a frase de ativação
    grudada, a forma longa cabe até DOIS jogos e a curta até CINCO. A escolha
    dela continua certa e continua tendo trabalho; o que mudou foi a razão.

    O DUBLÊ É OBRIGATÓRIO, e sem ele esta régua daria verde sobre a cura
    inteira: `carona.ligada()` lê `HEFESTO_CARONA_WRAPPER`, a `conftest.py` o
    põe em `0`, e `_com_a_carona` devolveria a frase de entrada sem tocar em
    nada.

    MORDIDA: faça `_com_a_carona` voltar a somar `resultado.frase` e esta régua
    reprova pelo tamanho.
    """
    from hefesto_dualsense4unix.app.actions import carona_do_wrapper as carona
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw

    jogos = [f"Jogo Número {n} (appid {1000000 + n})" for n in range(3)]
    longa = (
        "3 jogos perderam as Opções de Inicialização do Hefesto na Steam: "
        f"{', '.join(jogos[:-1])} e {jogos[-1]}. {sw.AVISO_DA_REGRESSAO}"
        "Vou repor assim que o jogo e a Steam fecharem — não mexo agora porque "
        "fechar a Steam com um jogo aberto mata o jogo.")
    curta = longa.replace(sw.AVISO_DA_REGRESSAO, "")

    monkeypatch.setattr(carona, "ligada", lambda: True)
    monkeypatch.setattr(
        carona, "passada",
        lambda **k: carona.ResultadoDaCarona(
            sw.REPARO_ADIADO_JOGO, longa, frozenset(), True, curta))

    ativacao = "Perfil ativado: Elden Ring"
    na_tira = a10_perfis._com_a_carona(ativacao)

    teto = _teto_da_tira()
    assert len(f"{ativacao} · {longa}") > teto, (
        "a semente desta régua deixou de estourar o teto — ela mede a cura "
        "contra um caso que já cabia, e daria verde sobre nada")
    assert len(na_tira) <= teto, (
        f"a tira recebeu {len(na_tira)} caracteres e cabem {teto}: o fim da "
        f"frase — que é o que diz «vou repor assim que…» — sai com reticências")
    assert sw.AVISO_DA_REGRESSAO.strip() not in na_tira, (
        "o aviso continua no texto da tira; a decisão 10-Q5 dela é que ele SAIA "
        "daqui")

    # E O CARTÃO DA ABA 07 CONTINUA RECEBENDO A FRASE INTEIRA. Sem esta metade,
    # a cura vaza para a outra aba — e lá o aviso tem onde caber: um cartão tem
    # CORPO, e é o mesmo lugar onde a recusa aparece.
    resultado = carona.passada()
    assert resultado.frase == longa, (
        "o dono passou a devolver a frase curta em `frase` — a janela GTK e o "
        "corpo do cartão da Steam perderiam o aviso junto com a tira")
    assert sw.AVISO_DA_REGRESSAO.strip() in resultado.frase


def _teto_da_tira() -> int:
    """`aba10.CABEM_NA_TIRA`, importado como o gerador se importa."""
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

    return int(aba10.CABEM_NA_TIRA)


def test_a_frase_curta_e_a_longa_sem_o_aviso_e_nao_um_corte(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quem encurta é o DONO da frase, e a curta é a longa MENOS o aviso.

    Cortar no primeiro ponto seria um segundo dono do texto: a tira passaria a
    depender da pontuação de uma frase que outra pessoa escreve, e mudar a
    redação lá quebraria a tira aqui sem ninguém ver.

    E `""` CONTINUA QUERENDO DIZER "não tenho versão curta", nunca "não diga
    nada": o jogo NOVO e a lista de IGNORE estendida à mão já cabem, e para eles
    quem fala é a `frase`.

    MORDIDA: faça `frase_do_aviso_curta` devolver `frase_do_aviso(censo)` e a
    primeira asserção reprova; faça-a devolver `""` na regressão e a segunda.
    """
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw

    def _censo(motivo: str) -> Any:
        return sw.Censo(
            com_wrapper=[], recusados=[], sandbox=[], erros=[],
            steam_aberta=True, jogo_aberto=True,
            faltantes=[sw.JogoSemWrapper(
                appid="1245620", rotulo="Elden Ring (appid 1245620)",
                opcoes="", motivo=motivo, vdf="/x")])

    regressao = _censo(sw.MOTIVO_REGRESSAO)
    longa = sw.frase_do_aviso(regressao)
    curta = sw.frase_do_aviso_curta(regressao)
    assert curta and curta != longa, (
        "a regressão não ganhou forma curta — é a frase que estoura a tira")
    assert curta == longa.replace(sw.AVISO_DA_REGRESSAO, ""), (
        f"a curta não é a longa MENOS o aviso: alguém a redigitou, e as duas "
        f"vão envelhecer separadas.\n  longa: {longa!r}\n  curta: {curta!r}")
    assert "Vou repor assim que" in curta, (
        "a curta perdeu o que vai ACONTECER — é o contrato da vigia, e é o fim "
        "da frase que a reticência comia")

    assert sw.frase_do_aviso_curta(_censo(sw.MOTIVO_NOVO)) == "", (
        "o jogo novo ganhou forma curta — a frase dele já cabe, e uma segunda "
        "forma sem necessidade é mais um texto a envelhecer")


def test_o_campo_do_jogo_nao_grava_por_tecla(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O guarda-costas da QUARTA PORTA: só `change` grava — `input` não.

    O "ao vivo" da decisão 10-Q4 pede que o piloto ouça `input`, o único evento
    que um campo de texto dispara a cada TECLA. As três portas de hoje
    (`change`, `click`, `blur`) despacham pelo `data-hef-gesto`, que aqui é
    `editor.jogo` — e ele GRAVA NO DISCO. Ligar `input` ao mesmo atributo faria
    o perfil ser regravado a cada tecla.

    ATÉ 06/09 A GUARDA ERA UMA LISTA DE PROIBIDOS COM UM NOME (`!= "click"`), e
    uma lista de proibidos não sabe do que ainda não nasceu: `input` não é
    `click`, logo passava. Virou lista de permitidos, e o vazio continua
    valendo — um dicionário de régua, montado à mão, não tem de saber o nome do
    evento do navegador.

    MORDIDA: devolva `_so_mudou` a `!= "click"` e esta régua reprova com o
    `input` gravando.
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

    for evento in ("input", "keyup", "paste", "click"):
        gravados.clear()
        a10_perfis.editor_jogo(ctx, {"valor": "1599660", "evento": evento}, None)
        assert not gravados, (
            f"um evento `{evento}` gravou o perfil no disco — com o `input` "
            f"ligado, isso é uma gravação por TECLA que ela digita")

    # E O CAMINHO QUE GRAVA CONTINUA GRAVANDO, senão a guarda virou uma parede.
    for aberto in ({"valor": "1599660", "evento": "change"},
                   {"valor": "1599660"}):
        gravados.clear()
        a10_perfis.editor_jogo(ctx, dict(aberto), None)
        assert gravados, (
            f"o gesto parou de gravar com {aberto!r} — a lista de permitidos "
            f"virou uma parede, e o campo ficou intocável")
