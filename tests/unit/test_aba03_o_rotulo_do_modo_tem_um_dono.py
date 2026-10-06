"""A aba Gatilhos parou de digitar o que já tem dono — 03/09/2026."""

from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

PAGINA = "03-gatilhos.html"

UNIQ = "aa:bb:cc:00:00:01"
FALSO = {"uniq": UNIQ, "player": 1, "transport": "usb", "is_primary": True,
         "inputs": {"l2_raw": 0, "r2_raw": 0}}
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "USB", "cor": "starlight-blue", "mascara": "DualSense"}]

_OPCAO = re.compile(r'<option value="(?P<valor>[^"]*)"[^>]*>(?P<texto>[^<]*)</option>')
_SELECT = re.compile(
    r'<select[^>]*class="(?P<classe>modo|pronto)"[^>]*>(?P<dentro>.*?)</select>',
    re.S)


_PERFIL_DA_CENA: dict = {}


@pytest.fixture(autouse=True)
def _o_perfil_de_mentira_nao_vaza():
    """O dublê de `perfil.ativo` VOLTA — sem isto ele envenenava a suíte."""
    from pacotes import perfil

    original = perfil.ativo
    perfil.ativo = lambda _nome: dict(_PERFIL_DA_CENA)  # type: ignore[assignment]
    yield
    perfil.ativo = original
    _PERFIL_DA_CENA.clear()


@pytest.fixture
def a03():
    import pacotes  # noqa: F401  (registra os dez)
    from pacotes import a03_gatilhos

    a03_gatilhos.esquecer_o_rascunho()
    yield a03_gatilhos
    a03_gatilhos.esquecer_o_rascunho()


@pytest.fixture
def presets():
    from hefesto_dualsense4unix.app.actions.trigger_specs import PRESETS

    return PRESETS


def _o_da_tela(preset) -> str:
    """O rótulo que a tela dá ao modo: o do produto, salvo o «Desligado» (`Off`)."""
    from pacotes.a03_gatilhos import ROTULO_DO_JOGO_DECIDE

    return ROTULO_DO_JOGO_DECIDE if preset.name == "Off" else preset.label


def _bancada() -> str:
    from hefesto_dualsense4unix.interface import onde

    return onde.pagina(PAGINA).read_text(encoding="utf-8")


def _selects(doc: str, classe: str) -> list[str]:
    return [m.group("dentro") for m in _SELECT.finditer(doc)
            if m.group("classe") == classe]


def test_o_rotulo_de_cada_modo_no_pacote_e_o_do_produto(a03, presets):
    """O que o produto pinta nos oito campos traz o `label` do `PRESETS`.

    Esta é a metade que chega à tela do usuário hoje, sem esperar publicação: o pacote
    monta a lista a cada tique, então a página publicada pode continuar com a
    cópia velha que a palavra na tela já é a certa.

    A MORDIDA: em `html_das_opcoes_de_modo`, devolva `_opcoes_cravadas_do_modo()`
    sem passar pelo `rotular` — isto é, deixe a página mandar no rótulo. Medido:
    **2 testes reprovam** (este e o do DOM abaixo), nomeando `Bow` e `Weapon`.
    """
    opcoes = dict(_OPCAO.findall(a03.html_das_opcoes_de_modo()))
    erradas = [(p.name, opcoes[p.name], _o_da_tela(p)) for p in presets
               if p.name in opcoes and opcoes[p.name] != _o_da_tela(p)]
    assert not erradas, (
        "o pacote pinta um rótulo que não é o do produto:\n  "
        + "\n  ".join(f"{n}: tela={t!r} produto={e!r}" for n, t, e in erradas))


def test_todo_modo_do_produto_tem_opcao_no_pacote(a03, presets):
    """Nenhum dos 19 pode faltar — um modo sem opção é um modo inalcançável."""
    tem = {v for v, _ in _OPCAO.findall(a03.html_das_opcoes_de_modo())}
    faltam = sorted({p.name for p in presets} - tem)
    assert not faltam, f"modos do produto sem opção no campo: {faltam}"


def test_o_rotulo_de_cada_modo_na_bancada_e_o_do_produto(presets):
    """E o DESENHO também parou de digitar — senão sobrariam duas verdades."""
    do_produto = {p.name: _o_da_tela(p) for p in presets}
    erradas: list[str] = []
    for i, dentro in enumerate(_selects(_bancada(), "modo")):
        for valor, texto in _OPCAO.findall(dentro):
            if valor in do_produto and texto != do_produto[valor]:
                erradas.append(
                    f"select #{i} · {valor}: desenho={texto!r} "
                    f"produto={do_produto[valor]!r}")
    assert not erradas, (
        "o desenho digita um rótulo que o produto já nomeia:\n  "
        + "\n  ".join(erradas))


def test_as_curvas_de_feedback_estao_no_campo_em_qualquer_modo(a03, presets):
    """A firmeza constante não pode exigir que ela troque o modo antes.

    O campo "Efeito pronto" fica visível nos 19 modos (decisão de produto), e nos 17
    que não são por posição ele mostra as curvas de FEEDBACK — que é o que a
    página crava. Oferecer cinco das seis ali é um buraco arbitrário: o gesto
    `pronto` sabe aplicar a sexta em qualquer modo, porque tira o modo da TABELA
    em que a curva mora.

    O MODO DE VIBRAÇÃO FICA DE FORA deste laço de propósito — lá o campo mostra
    a OUTRA tabela, e há régua própria para ele
    (`test_as_cinco_curvas_de_vibracao_existem_no_modo_delas`).

    A MORDIDA: faça `_tabela_que_o_campo_mostra` devolver `_tabela_da_curva(modo)`
    cru. Medido: **1 teste reprova**, nomeando `linear_medio` em 18 modos.
    """
    tp = a03._prontos()
    devem = {c for c in tp.FEEDBACK_POSITION_LABELS if c != "custom"}
    buracos: list[str] = []
    for p in presets:
        if p.name == a03.MODO_DA_VIBRACAO:
            continue
        tem = {v for v, _ in _OPCAO.findall(a03.html_das_opcoes_de_pronto(p.name))}
        if devem - tem:
            buracos.append(f"{p.label}: faltam {sorted(devem - tem)}")
    assert not buracos, (
        "curvas do produto fora do alcance de quem clica:\n  " + "\n  ".join(buracos))


def test_a_bancada_oferece_as_seis_curvas_de_feedback(a03):
    """E o desenho também: `PRONTOS` deixou de ser digitada."""
    tp = a03._prontos()
    devem = {c for c in tp.FEEDBACK_POSITION_LABELS if c != "custom"}
    faltam: list[str] = []
    for i, dentro in enumerate(_selects(_bancada(), "pronto")):
        tem = {v for v, _ in _OPCAO.findall(dentro)}
        if devem - tem:
            faltam.append(f"select #{i}: faltam {sorted(devem - tem)}")
    assert not faltam, (
        "o desenho esqueceu curva que o produto tem:\n  " + "\n  ".join(faltam))


def test_o_rotulo_de_cada_curva_na_bancada_e_o_do_produto(a03):
    """O nome da curva também tem dono, e é o mesmo dicionário."""
    tp = a03._prontos()
    do_produto = {c: r for c, r in tp.FEEDBACK_POSITION_LABELS.items()
                  if c != "custom"}
    erradas: list[str] = []
    for i, dentro in enumerate(_selects(_bancada(), "pronto")):
        for valor, texto in _OPCAO.findall(dentro):
            if valor in do_produto and texto != do_produto[valor]:
                erradas.append(f"select #{i} · {valor}: desenho={texto!r} "
                               f"produto={do_produto[valor]!r}")
    assert not erradas, ("o desenho renomeia uma curva do produto:\n  "
                         + "\n  ".join(erradas))


def test_a_lista_de_modo_e_emitida_para_os_oito_campos(a03):
    """Um dono, oito lugares: `blocos` leva a lista a cada `select.modo`."""
    from pacotes import Contexto

    _PERFIL_DA_CENA.clear()
    _PERFIL_DA_CENA.update({
        "triggers": {"left": {"mode": "Off", "params": []},
                     "right": {"mode": "Off", "params": []}},
        "controllers": {},
    })
    ctx = Contexto(state={"active_profile": "régua"}, mesa=MESA,
                   conectados=[FALSO], estados={})
    blocos = a03.pacote(ctx)["blocos"]
    esperados = {f'[data-controle="p{n}"] select.modo[data-lado="{s}"]'
                 for n in (1, 2, 3, 4) for s in ("e", "d")}
    faltam = sorted(esperados - set(blocos))
    assert not faltam, f"campos de modo que o produto não pinta: {faltam}"
    for sel in esperados:
        assert 'value="Bow"' in blocos[sel], (
            f"{sel} recebeu um bloco que não é a lista de modos")


def test_a_lista_de_modo_sai_como_o_dom_a_escreve(a03):
    """Nem `selected`, nem `disabled` cru — senão o piloto repinta para sempre."""
    html = a03.html_das_opcoes_de_modo()
    assert " selected" not in html, (
        "o bloco emitido carrega a escolha do desenho para a mesa dela")
    assert re.search(r"\sdisabled(?=[\s>])", html) is None, (
        "o `disabled` saiu cru: o navegador devolve `disabled=\"\"` e o piloto "
        "reescreveria os oito campos a cada tique, para sempre")
    assert 'disabled=""' in html, (
        "o travessão da decisão 13 dela perdeu o `disabled` — o lugar vazio "
        "passaria a ser escolhível com o rato")


def test_a_curva_aplicada_e_nomeada_de_volta_no_campo(a03):
    """Escolher `Linear médio` e o campo voltar a "— Nenhum —" é a tela mentindo.

    ACHADO CLICANDO, 03/09/2026, no controle da mesa: apliquei `linear_medio` no
    L2 e li o DOM — o modo virou `MultiPositionFeedback` e a caixa de ajustes
    mostrou dez barras em 4, que é a curva certa **no aparelho**; e o campo de
    baixo dizia `— Nenhum —`. Valia para as ONZE curvas do produto.

    A CAUSA, e ela explica por que ninguém tinha visto: o disco guarda a curva
    como dez listas de um (`[[0], [1], …]`) e o RASCUNHO guarda o que foi ao
    daemon, que é a lista posicional PLANA. O reconhecimento só olhava a
    primeira forma — então a tela sabia nomear a curva que veio do disco e não a
    que ela acabou de escolher.

    O CUSTO IA ALÉM DA PALAVRA: o "Guardar esse efeito" lê a coluna, e uma
    coluna que diz "sem curva" logo depois de ela escolher uma é a mesma família
    de defeito que o rascunho veio curar.

    A MORDIDA: apague o ramo `elif nome in MODOS_COM_CURVA` de `_do_lado`.
    Medido: **1 teste reprova**, nomeando as onze curvas.
    """
    tp = a03._prontos()
    specs = a03._specs()
    mudas: list[str] = []
    for tabela in (tp.FEEDBACK_POSITION_PRESETS, tp.VIBRATION_POSITION_PRESETS):
        for chave in tabela:
            curva, modo_ = a03._curva(chave)
            plana = a03._params_da_curva(modo_, curva)
            visto = a03._do_lado({"mode": modo_, "params": plana}, specs)
            if visto["pronto"] != chave:
                mudas.append(f"{chave} ({modo_}): a tela diz {visto['pronto']!r}")
    assert not mudas, (
        "curvas que o produto aplicou e a tela não sabe nomear de volta:\n  "
        + "\n  ".join(mudas))


def test_a_curva_vinda_do_disco_continua_nomeada(a03):
    """A cura não pode quebrar a forma ANTIGA — o disco guarda dez listas de um."""
    tp = a03._prontos()
    specs = a03._specs()
    mudas: list[str] = []
    for chave, valores in tp.FEEDBACK_POSITION_PRESETS.items():
        aninhada = [[v] for v in valores]
        visto = a03._do_lado({"mode": a03.MODO_DA_CURVA, "params": aninhada}, specs)
        if visto["pronto"] != chave:
            mudas.append(f"{chave}: a tela diz {visto['pronto']!r}")
    assert not mudas, ("curvas gravadas no disco que a tela não nomeia:\n  "
                       + "\n  ".join(mudas))


def test_o_title_de_cada_modo_continua_sendo_o_desta_tela(a03, presets):
    """A cura do rótulo não pode levar junto a frase que o usuário aprovou.

    A dica desta tela é mais concreta que a do motor ("Trava dura do começo ao
    fim do curso. Serve para freio de carro e para arma travada." contra
    "Barreira rígida numa posição fixa."), e trocá-la para fechar a dívida do
    rótulo seria pagar uma dívida abrindo outra.

    A MORDIDA: faça `html_das_opcoes_de_modo` remontar a opção inteira em vez de
    trocar só o nó de texto. Medido: **1 teste reprova**, dizendo que os 19
    `title` sumiram.
    """
    html = a03.html_das_opcoes_de_modo()
    sem_dica = [p.name for p in presets
                if not re.search(rf'value="{p.name}"[^>]*\stitle="[^"]+"', html)]
    assert not sem_dica, f"modos que perderam a dica desta tela: {sem_dica}"


def test_nenhum_teste_deste_arquivo_troca_simbolo_de_modulo() -> None:
    """Nada aqui reatribui `perfil.ativo` — quem o troca é a fixture, que desfaz."""
    fonte = pathlib.Path(__file__).read_text(encoding="utf-8")
    linhas = [
        f"{n}: {ln.strip()}"
        for n, ln in enumerate(fonte.splitlines(), start=1)
        if re.search(r"^\s*perfil\.ativo\s*=", ln)
        and "original" not in ln
    ]
    assert len(linhas) <= 1, (
        "há atribuição crua a `perfil.ativo` fora da fixture que a desfaz:\n"
        + "\n".join(linhas)
        + "\n\nFoi assim que este arquivo envenenou a suíte até 05/09/2026.")
