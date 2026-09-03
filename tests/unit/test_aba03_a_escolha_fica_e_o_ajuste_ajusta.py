"""A aba Gatilhos com a paridade que faltava — 03/09/2026.

QUATRO DÍVIDAS MEDIDAS CONTRA A GTK, e as quatro nesta régua:

1. **A escolha não ficava na tela.** Clicar `Rígido` aplicava no aparelho — ela
   sente na mão — e, em no máximo meio segundo, o tique repintava o campo com o
   modo do PERFIL NO DISCO. Aplicar não grava, e a pintura não conhecia o que
   foi aplicado. Isso não é tela vazia: é **tela que mente**, e contaminava o
   "Guardar esse efeito", que lê a coluna.
   *Na GTK:* `_persist_params_to_draft` grava antes de todo envio e
   `_refresh_triggers_from_draft` repinta do RASCUNHO.

2. **Nenhum ajuste era ajustável.** 17 dos 19 modos têm ajuste, somando **73
   parâmetros**; a caixa do HTML era `<span>` de leitura, sem `data-gesto` e sem
   `<input>`. Escolher um modo aplicava os padrões dele e acabou — e "Montar do
   zero" (`Custom`), cujos oito padrões são ZERO, era um item de menu que
   responde "aplicado" com o gatilho intacto.
   *Na GTK:* um `Gtk.Scale` por parâmetro, com faixa e padrão do `trigger_specs`.

3. **Seis curvas do produto fora do alcance.** `linear_medio` (a sexta de
   feedback) e as CINCO de `VIBRATION_POSITION_PRESETS` existiam no motor, a GTK
   as oferecia, e a tela nova não tinha como aplicar nenhuma.
   *Na GTK:* `_populate_preset_combo` troca a tabela conforme o modo.

4. **A tela calava sobre o desfecho.** `_desfecho` jogava o corpo do daemon
   fora, e três coisas diferentes viravam o mesmo silêncio de sucesso: nada
   aconteceu, ficou guardado, e a recusa que vem DENTRO de uma resposta
   bem-sucedida.
   *Na GTK:* `_toast_trigger` → `frase_do_desfecho`, lendo o corpo (ELO-MUDO-01/T3).

A MORDIDA DE CADA UMA está no docstring do teste que a mede, e as quatro foram
arrancadas de verdade antes deste arquivo entrar.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

PAGINA = "03-gatilhos.html"

#: O MAC é da faixa sintética da casa (`aa:bb:cc`): há dois portões de anonimato
#: nesta árvore e eles não perdoam.
UNIQ = "aa:bb:cc:00:00:01"
FALSO = {"uniq": UNIQ, "player": 1, "transport": "usb", "is_primary": True,
         "inputs": {"l2_raw": 0, "r2_raw": 0}}
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "USB", "cor": "starlight-blue", "mascara": "DualSense"}]

#: O QUE O DAEMON RESPONDE QUANDO O BYTE SAIU. É a forma medida em 23/08 e o
#: contrato de `ipc_bridge.trigger_set_detalhado`.
APLICOU = {"status": "ok", "aplicado_em": [UNIQ], "guardado_em": []}


@pytest.fixture
def a03():
    """O pacote, com o rascunho LIMPO — ele é estado de módulo.

    Sem esta limpeza um teste herdaria o que o anterior aplicou, e a régua
    passaria a medir a ordem em que os testes rodam.
    """
    import pacotes  # noqa: F401  (registra os dez)
    from pacotes import a03_gatilhos

    a03_gatilhos.esquecer_o_rascunho()
    yield a03_gatilhos
    a03_gatilhos.esquecer_o_rascunho()


class _Ponte:
    """A ponte que ACEITA e diz onde aplicou. Guarda o que foi chamado."""

    def __init__(self, corpo: dict | None = None) -> None:
        self.chamadas: list[tuple[str, tuple, dict]] = []
        self.corpo = APLICOU if corpo is None else corpo

    def _responder(self, nome, *a, **k):
        self.chamadas.append((nome, a, k))
        return (True, str(self.corpo.get("motivo") or ""), self.corpo)

    def trigger_set_detalhado(self, *a, **k):
        return self._responder("trigger_set_detalhado", *a, **k)

    def trigger_reset_detalhado(self, *a, **k):
        return self._responder("trigger_reset_detalhado", *a, **k)


def _ctx(perfil_ativo: str = "régua", modo_no_disco: str = "Off"):
    """O contexto da mesa de um controle, com o perfil injetado pela porta de cima.

    O PERFIL NÃO VAI PARA O DISCO, e é a mesma escolha do
    `test_a_aba_gatilhos_nao_deixa_o_mockup_na_tela`: o que se mede aqui é a
    ordem entre rascunho e perfil, não o leitor de perfis — que tem régua
    própria.
    """
    from pacotes import Contexto, perfil

    perfil.ativo = lambda _nome: {  # type: ignore[assignment]
        "triggers": {"left": {"mode": modo_no_disco, "params": []},
                     "right": {"mode": modo_no_disco, "params": []}},
        "controllers": {},
    }
    return Contexto(state={"active_profile": perfil_ativo}, mesa=MESA,
                    conectados=[FALSO], estados={})


def _clicar(gesto_: str, o: dict, p) -> None:
    from pacotes import gesto_da_pagina

    acao = gesto_da_pagina(PAGINA, gesto_)
    assert acao is not None, f"o gesto {gesto_!r} não tem dono nesta página"
    acao(_clicar.ctx, {"uniq": UNIQ, **o}, p)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# 1. A ESCOLHA FICA NA TELA
# ---------------------------------------------------------------------------
def test_o_modo_aplicado_continua_no_campo_no_tique_seguinte(a03):
    """Clicar `Rígido` e ver o campo voltar para o disco é a queixa dela.

    A MORDIDA: apague a linha `_do_rascunho(uniq, disco) or` do `cfgs` em
    `pacote()` — ou chame `esquecer_o_rascunho()` entre o gesto e a leitura — e
    o campo volta a dizer `Off` sobre um gatilho que está em `Rigid`.
    """
    ctx = _ctx(modo_no_disco="Off")
    antes = a03.pacote(ctx)["colunas"][UNIQ]["modo-chave-e"]
    assert antes == "Off", "o cenário partiu do lugar errado"

    _clicar.ctx = ctx  # type: ignore[attr-defined]
    _clicar("modo", {"lado": "e", "valor": "Rigid"}, _Ponte())

    depois = a03.pacote(ctx)["colunas"][UNIQ]["modo-chave-e"]
    assert depois == "Rigid", (
        f"o campo voltou para {depois!r} meio segundo depois do clique. É a "
        f"queixa dela — a escolha não fica —, e ela contamina o 'Guardar esse "
        f"efeito', que lê o que está na TELA.")


def test_os_ajustes_aplicados_tambem_ficam(a03):
    """Não é só o modo: a caixa tem de mostrar os números que foram ao aparelho.

    Sem isto o modo ficaria certo e as barras mostrariam os ajustes do DISCO —
    a tela meio verdadeira, que é pior que a falsa inteira porque parece
    conferida.
    """
    ctx = _ctx(modo_no_disco="Off")
    _clicar.ctx = ctx  # type: ignore[attr-defined]
    _clicar("ajuste", {"lado": "e", "i": "1", "valor": "240",
                       "forma": {"modo-chave-e": "Rigid", "aj-val-e-0": "0",
                                 "aj-val-e-1": "180"}}, _Ponte())
    caixa = a03.pacote(ctx)["blocos"]['[data-controle="p1"] .ajustes.e']
    assert 'data-campo="aj-val-e-1">240<' in caixa, (
        f"a barra arrastada não voltou com o valor aplicado:\n{caixa}")


def test_trocar_de_perfil_esquece_o_que_foi_aplicado(a03):
    """O daemon REAPLICA o perfil no `profile.switch` — o rascunho tem de morrer.

    Guardá-lo por perfil e ressuscitá-lo na volta faria a tela afirmar um efeito
    que o daemon já desfez. A GTK paga o mesmo preço: o draft é remontado.

    A MORDIDA: tire a poda `_o_rascunho_e_deste_perfil` do `pacote()` e o modo
    aplicado no perfil anterior reaparece no perfil novo.
    """
    ctx = _ctx(perfil_ativo="ação", modo_no_disco="Off")
    _clicar.ctx = ctx  # type: ignore[attr-defined]
    _clicar("modo", {"lado": "e", "valor": "Rigid"}, _Ponte())
    assert a03.pacote(ctx)["colunas"][UNIQ]["modo-chave-e"] == "Rigid"

    outro = _ctx(perfil_ativo="corrida", modo_no_disco="Off")
    assert a03.pacote(outro)["colunas"][UNIQ]["modo-chave-e"] == "Off", (
        "o rascunho do perfil anterior sobreviveu à troca — a tela afirmaria "
        "um efeito que o `profile.switch` já desfez")


def test_o_controle_que_sai_da_mesa_leva_o_rascunho(a03):
    """No replug o daemon aplica o perfil de novo. Ver a nota da seção do rascunho."""
    from pacotes import Contexto

    ctx = _ctx(modo_no_disco="Off")
    _clicar.ctx = ctx  # type: ignore[attr-defined]
    _clicar("modo", {"lado": "e", "valor": "Rigid"}, _Ponte())

    # A MESA ESVAZIA — e o pacote é chamado, que é quando a poda roda.
    a03.pacote(Contexto(state={"active_profile": "régua"}, mesa=MESA,
                        conectados=[], estados={}))
    assert a03.pacote(ctx)["colunas"][UNIQ]["modo-chave-e"] == "Off", (
        "o rascunho de um controle que saiu da mesa sobreviveu — no replug o "
        "daemon reaplica o perfil, e a tela diria o efeito de antes de ele sair")


def test_o_rascunho_so_recebe_o_que_o_daemon_aceitou(a03):
    """Guardar antes da resposta trocaria uma mentira por outra, pior.

    Hoje a escolha SOME; sem esta guarda ela FICARIA — e seria falsa.
    """
    ctx = _ctx(modo_no_disco="Off")
    _clicar.ctx = ctx  # type: ignore[attr-defined]
    guardado = {"status": "ok", "aplicado_em": [], "guardado_em": [UNIQ]}
    with pytest.raises(RuntimeError):
        _clicar("modo", {"lado": "e", "valor": "Rigid"}, _Ponte(guardado))
    assert a03.pacote(ctx)["colunas"][UNIQ]["modo-chave-e"] == "Off", (
        "o rascunho ficou com um efeito que o daemon GUARDOU sem mandar ao fio")


# ---------------------------------------------------------------------------
# 2. OS 73 AJUSTES VIRARAM AJUSTÁVEIS
# ---------------------------------------------------------------------------
def test_a_barra_do_produto_tem_alavanca_e_a_do_desenho_nao(a03):
    """A alavanca é invisível e é do PRODUTO; o desenho é dela.

    A MORDIDA: troque o `editavel=True` do `_blocos_da_coluna` por `False` e a
    caixa volta a ser somente-leitura, com os 73 parâmetros fora do alcance.
    """
    ctx = _ctx(modo_no_disco="Off")
    _clicar.ctx = ctx  # type: ignore[attr-defined]
    _clicar("modo", {"lado": "e", "valor": "Machine"}, _Ponte())
    caixa = a03.pacote(ctx)["blocos"]['[data-controle="p1"] .ajustes.e']
    quantas = caixa.count('type="range"')
    assert quantas == 6, (
        f"o modo `Machine` tem seis parâmetros e a caixa trouxe "
        f"{quantas} alavanca(s):\n{caixa}")
    assert 'data-gesto="ajuste"' in caixa and 'data-hef-forma="@controle"' in caixa, (
        "a alavanca não pede a coluna — o gesto não saberia em que modo o "
        "gatilho está, e o daemon lê a lista de ajustes INTEIRA")
    assert "opacity:0" in caixa, (
        "a alavanca ficou VISÍVEL — o desenho é dela, e ela aprovou uma barra")

    do_desenho = a03.html_dos_ajustes(
        "e", [{"nome": "Força", "valor": 200, "pct": 78, "min": 0, "max": 255}])
    assert "type=\"range\"" not in do_desenho, (
        "o gerador passou a desenhar a alavanca na bancada. Publicar controle "
        "novo no desenho é ato dela — o padrão de `editavel` é `False`")


def test_a_faixa_da_alavanca_sai_do_produto(a03):
    """`0..9` para uma posição do curso, `0..255` para uma força. Nunca digitado.

    Uma faixa cravada poria a posição do curso numa régua trinta vezes maior, e
    arrastar até o fim mandaria 255 num campo que aceita 9.
    """
    ctx = _ctx(modo_no_disco="Off")
    _clicar.ctx = ctx  # type: ignore[attr-defined]
    _clicar("modo", {"lado": "e", "valor": "Machine"}, _Ponte())
    caixa = a03.pacote(ctx)["blocos"]['[data-controle="p1"] .ajustes.e']
    spec = a03._specs().get_spec("Machine")
    for q in spec.params:
        assert f'min="{q.min_value}" max="{q.max_value}"' in caixa, (
            f"a alavanca de {q.label!r} não tem a faixa do produto "
            f"({q.min_value}..{q.max_value}):\n{caixa}")


def test_o_lugar_sem_aparelho_nao_ganha_alavanca(a03):
    """Arrastar onde não há controle só pode terminar em recusa.

    É a mesma regra que o `pointer-events:none` do CSS já aplica aos `<select>`
    das colunas vazias.
    """
    ctx = _ctx(modo_no_disco="Rigid")
    caixa = a03.pacote(ctx)["blocos"]['[data-controle="p3"] .ajustes.e']
    assert 'type="range"' not in caixa, (
        f"a coluna vazia ganhou alavanca:\n{caixa}")


def test_o_ajuste_manda_a_lista_inteira_com_um_numero_trocado(a03):
    """O daemon lê a lista posicional INTEIRA — mandar só o número mexido apaga
    o que ela não tocou.

    A MORDIDA: troque `params[i] = ...` por `params = [valor]` no gesto e esta
    régua reprova, dizendo qual lista chegou.
    """
    ctx = _ctx(modo_no_disco="Off")
    _clicar.ctx = ctx  # type: ignore[attr-defined]
    p = _Ponte()
    _clicar("ajuste", {"lado": "e", "i": "1", "valor": "240",
                       "forma": {"modo-chave-e": "Rigid", "aj-val-e-0": "3",
                                 "aj-val-e-1": "180"}}, p)
    assert p.chamadas == [("trigger_set_detalhado", ("left", "Rigid", [3, 240]),
                           {"uniq": UNIQ})], (
        f"o ajuste não chegou ao daemon com a coluna inteira: {p.chamadas}")


def test_o_click_nao_repete_o_change_da_alavanca(a03):
    """Uma alavanca dispara `change` E `click` no mesmo gesto, com o mesmo valor.

    Sem guarda, cada arrasto vira DOIS pedidos idênticos ao daemon. É o que o
    debounce de 300 ms da GTK resolve do outro lado.

    A GUARDA É A IGUALDADE, e não o nome do evento — as DUAS metades estão
    medidas aqui: o segundo pedido idêntico é calado, e um pedido DIFERENTE
    passa mesmo vindo de um `click`. Recusar todo `click` calaria também o
    clique sintético da régua desta casa (`--prova-clique` faz `el.click()`),
    e a tela ganharia verde sobre uma alavanca nunca tocada.
    """
    ctx = _ctx(modo_no_disco="Off")
    _clicar.ctx = ctx  # type: ignore[attr-defined]
    forma = {"modo-chave-e": "Rigid", "aj-val-e-0": "0", "aj-val-e-1": "180"}
    p = _Ponte()
    _clicar("ajuste", {"lado": "e", "i": "1", "valor": "240",
                       "evento": "change", "forma": forma}, p)
    _clicar("ajuste", {"lado": "e", "i": "1", "valor": "240",
                       "evento": "click", "forma": forma}, p)
    assert len(p.chamadas) == 1, (
        f"o `click` que segue o `change` virou um segundo pedido: {p.chamadas}")

    _clicar("ajuste", {"lado": "e", "i": "1", "valor": "241",
                       "evento": "click", "forma": forma}, p)
    assert len(p.chamadas) == 2, (
        "um `click` com valor NOVO foi calado — a régua da tela clica por "
        "`el.click()`, e assim ela nunca alcançaria a alavanca")


def test_montar_do_zero_deixa_de_ser_um_item_de_menu_que_nao_faz_nada(a03):
    """`Custom` = byte de modo + 7 forças, e os oito padrões são ZERO.

    Sem alavanca, escolher "Montar do zero" mandava `[0]*8` — modo 0 com sete
    forças zeradas — e a tela dizia "aplicado" com o gatilho intacto. É a
    `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` num item de menu.
    """
    ctx = _ctx(modo_no_disco="Off")
    _clicar.ctx = ctx  # type: ignore[attr-defined]
    _clicar("modo", {"lado": "d", "valor": "Custom"}, _Ponte())
    caixa = a03.pacote(ctx)["blocos"]['[data-controle="p1"] .ajustes.d']
    assert a03._padroes("Custom") == [0] * 8, (
        "os padrões do `Custom` deixaram de ser oito zeros — a razão desta "
        "régua mudou, e o texto dela precisa mudar junto")
    assert caixa.count('type="range"') == 8, (
        f"os oito ajustes do `Custom` não são alcançáveis:\n{caixa}")


# ---------------------------------------------------------------------------
# 3. AS SEIS CURVAS QUE A TELA NÃO ALCANÇAVA
# ---------------------------------------------------------------------------
def test_a_sexta_curva_de_feedback_entrou(a03):
    """`linear_medio` existe no produto desde antes desta aba, e a lista digitada
    à mão no gerador a esqueceu.

    O gerador reprova um rótulo que o produto NÃO tem, e nunca um que o produto
    tem e a tela esqueceu — esta régua é a que faltava, do outro lado.
    """
    tp = a03._prontos()
    opcoes = a03.html_das_opcoes_de_pronto()
    for chave, rotulo in tp.FEEDBACK_POSITION_LABELS.items():
        if chave == "custom":
            continue
        assert f'value="{chave}"' in opcoes, (
            f"a curva {rotulo!r} do produto não está no campo:\n{opcoes}")


def test_as_cinco_curvas_de_vibracao_existem_no_modo_delas(a03):
    """Com o gatilho em `MultiPositionVibration` o campo mostra as CINCO.

    É a regra da GTK (`_populate_preset_combo`), e sem ela as curvas de vibração
    do produto não tinham como chegar ao aparelho por esta tela.

    A MORDIDA: faça `html_das_opcoes_de_pronto` ignorar o argumento e as cinco
    somem — e o gesto passa a receber uma chave que a lista não oferece.
    """
    tp = a03._prontos()
    opcoes = a03.html_das_opcoes_de_pronto(a03.MODO_DA_VIBRACAO)
    for chave, rotulo in tp.VIBRATION_POSITION_LABELS.items():
        if chave == "custom":
            continue
        assert f'value="{chave}"' in opcoes, (
            f"a curva de vibração {rotulo!r} não está no campo:\n{opcoes}")
    for chave in tp.FEEDBACK_POSITION_PRESETS:
        assert f'value="{chave}"' not in opcoes, (
            f"a curva de FORÇA {chave!r} ficou oferecida num gatilho que está "
            f"em vibração — escolhê-la aplicaria uma curva que este modo não "
            f"sabe ler:\n{opcoes}")
    assert 'value="custom"' in opcoes, (
        "o '— Nenhum —' que ela aprovou saiu junto com as curvas de força")


def test_a_curva_de_vibracao_vai_no_modo_dela_e_nas_posicoes(a03):
    """Dez posições nos `pos_*`, a frequência no padrão do modo.

    Alinhar por índice poria a posição 0 debaixo do rótulo "Frequência" — um
    número certo com o nome errado, e o efeito errado no fio. É a mesma cura que
    `_on_preset_changed` da GTK escreve pulando o slider de frequência.
    """
    ctx = _ctx(modo_no_disco="Off")
    _clicar.ctx = ctx  # type: ignore[attr-defined]
    p = _Ponte()
    _clicar("pronto", {"lado": "e", "v": "galope"}, p)

    tp = a03._prontos()
    curva = list(tp.VIBRATION_POSITION_PRESETS["galope"])
    spec = a03._specs().get_spec(a03.MODO_DA_VIBRACAO)
    esperado = a03._padroes(a03.MODO_DA_VIBRACAO)
    for i, q in enumerate(spec.params):
        if q.name.startswith("pos_"):
            esperado[i] = curva[int(q.name[4:])]
    assert p.chamadas == [("trigger_set_detalhado",
                           ("left", a03.MODO_DA_VIBRACAO, esperado),
                           {"uniq": UNIQ})], (
        f"a curva de vibração não chegou como vibração: {p.chamadas}")


# ---------------------------------------------------------------------------
# 4. O DESFECHO CHEGA À TELA
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("corpo", "pedaco"),
    [
        ({"status": "ok", "aplicado_em": [], "guardado_em": []},
         "nenhum controle recebeu"),
        ({"status": "ok", "aplicado_em": [], "guardado_em": [UNIQ]},
         "guardado"),
        ({"status": "ok", "motivo": "o jogo segura o hidraw",
          "aplicado_em": [UNIQ], "guardado_em": []},
         "o jogo segura o hidraw"),
    ],
    ids=["nada-aconteceu", "guardado", "recusa-dentro-do-sucesso"],
)
def test_o_que_nao_chegou_ao_gatilho_e_dito(a03, corpo, pedaco):
    """Os três desfechos que passavam por sucesso silencioso.

    O CANAL É O `RuntimeError`: é o único que o piloto leva ao cartão daquele
    controle (`hefesto_vivo._recusou_dizendo`). E a frase é do dono do assunto —
    `app/textos_de_aplicacao.frase_do_desfecho`, a mesma que a barra de status
    da GTK usa —, nunca uma escrita aqui.

    A MORDIDA: faça `_desfecho` devolver `(ok, motivo)` de novo, jogando o corpo
    fora, e os três voltam a ser silêncio.
    """
    ctx = _ctx(modo_no_disco="Off")
    _clicar.ctx = ctx  # type: ignore[attr-defined]
    with pytest.raises(RuntimeError) as erro:
        _clicar("modo", {"lado": "e", "valor": "Rigid"}, _Ponte(corpo))
    assert pedaco in str(erro.value), (
        f"a frase não diz o que aconteceu: {erro.value!r}")
    assert a03.NOME_DO_LADO["left"] in str(erro.value), (
        f"a frase não nomeia o gatilho com a palavra da GTK — a barra de "
        f"status dela diz {a03.NOME_DO_LADO['left']!r}, e a cura TRG-01 existe "
        f"porque um dia ela dizia `LEFT`: {erro.value!r}")


def test_o_que_chegou_ao_gatilho_nao_vira_recusa(a03):
    """A mordida gêmea: a cura não pode avançar longe demais.

    Um `aplicado_em` com alguém dentro é sucesso, e sucesso não levanta — senão
    todo clique certo viraria um recado vermelho no cartão dela.
    """
    ctx = _ctx(modo_no_disco="Off")
    _clicar.ctx = ctx  # type: ignore[attr-defined]
    _clicar("modo", {"lado": "e", "valor": "Rigid"}, _Ponte())


def test_a_ponte_sem_corpo_continua_calada(a03):
    """A ponte antiga e o dublê da régua não dizem ONDE a escrita parou.

    Concluir "nenhum controle recebeu" de um corpo que não fala de destino seria
    inventar o diagnóstico — e foi assim que uma régua desta casa já reprovou a
    cura em vez do defeito.
    """
    class _Muda:
        def trigger_set_detalhado(self, *a, **k):
            return (True, "", {})

        def trigger_reset_detalhado(self, *a, **k):
            return (True, "", {})

    ctx = _ctx(modo_no_disco="Off")
    _clicar.ctx = ctx  # type: ignore[attr-defined]
    _clicar("modo", {"lado": "e", "valor": "Rigid"}, _Muda())
