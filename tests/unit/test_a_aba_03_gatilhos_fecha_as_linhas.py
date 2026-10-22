"""A aba Gatilhos e as quatro decisões de 04/09/2026 — a régua de cada uma."""

from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

PAGINA = "03-gatilhos.html"
BANCADA = RAIZ / "mockup" / PAGINA


def _publicada() -> str:
    """O HTML que o PRODUTO renderiza — o mesmo que o piloto abre."""
    from hefesto_dualsense4unix.interface import onde

    return onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")

UNIQ = "aa:bb:cc:00:00:01"
FALSO = {"uniq": UNIQ, "player": 1, "transport": "usb", "is_primary": True,
         "inputs": {"l2_raw": 0, "r2_raw": 0}}
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "USB", "cor": "starlight-blue", "mascara": "DualSense"}]

#: contrato de `ipc_bridge.trigger_set_detalhado`.
APLICOU = {"status": "ok", "aplicado_em": [UNIQ], "guardado_em": []}


@pytest.fixture
def a03():
    """O pacote, com o rascunho LIMPO nas duas pontas."""
    import pacotes  # noqa: F401  (registra os dez)
    from pacotes import a03_gatilhos

    a03_gatilhos.esquecer_o_rascunho()
    yield a03_gatilhos
    a03_gatilhos.esquecer_o_rascunho()


class _Ponte:
    """A ponte que ACEITA e diz onde aplicou. Guarda o que foi chamado."""

    def __init__(self, corpo: dict | None = None,
                 recusa: tuple[str, ...] = ()) -> None:
        self.chamadas: list[tuple[str, tuple, dict]] = []
        self.avulsas: list[str] = []
        self.corpo = APLICOU if corpo is None else corpo
        self.recusa = recusa

    def _responder(self, nome, *a, **k):
        self.chamadas.append((nome, a, k))
        if a and a[0] in self.recusa:
            return (False, "end (3) deve ser > start (5)", None)
        return (True, str(self.corpo.get("motivo") or ""), self.corpo)

    def trigger_set_detalhado(self, *a, **k):
        return self._responder("trigger_set_detalhado", *a, **k)

    def trigger_reset_detalhado(self, *a, **k):
        return self._responder("trigger_reset_detalhado", *a, **k)

    def chamar(self, metodo: str, **_):
        """O último passo da GRAVAÇÃO no perfil — `launch_env.refresh`.

        O DUBLÊ ERA MAIS FROUXO QUE O DAEMON e isso importa aqui: desde a
        decisão D2 (05/09) o gatilho que chega ao aparelho vai também ao perfil
        ativo, e `_gravar_so_o_gatilho` termina pedindo ao daemon que releia o
        ambiente de lançamento. Sem este método, a gravação levantaria
        `AttributeError` dentro de `_guardar_no_perfil`, o ramo do `except`
        devolveria a frase do disco, e a régua do SUCESSO PLENO mediria uma
        falha que ela mesma fabricou. Três dos vermelhos de 05/09 foram dublê
        mais frouxo que o real.
        """
        # Somar o `launch_env.refresh` ali faria a régua da R-19 reprovar por
        self.avulsas.append(metodo)
        return True


@pytest.fixture
def ctx(monkeypatch):
    """A mesa de um controle, com o perfil injetado pela porta de cima."""
    from pacotes import Contexto, perfil

    def _fabricar(esquerdo: str = "Rigid", direito: str = "Bow"):
        monkeypatch.setattr(perfil, "ativo", lambda _n: {
            "triggers": {"left": {"mode": esquerdo, "params": []},
                         "right": {"mode": direito, "params": []}},
            "controllers": {},
        })
        return Contexto(state={"active_profile": "régua"}, mesa=MESA,
                        conectados=[FALSO], estados={})

    return _fabricar


@pytest.fixture
def disco_que_guarda(monkeypatch):
    """O disco em que o perfil ABRE e a gravação passa — o SUCESSO PLENO.

    ELE É INDISPENSÁVEL PARA MEDIR A `03-Q4`, e a razão é uma medição: as
    réguas desta aba rodam com `active_profile="régua"`, um nome que NÃO está
    em disco. Sem esta fixture, todo clique cai no ramo do perfil que não abre
    e o `recado` volta cheio — a régua do sucesso pleno estaria medindo a
    `AS-DUAS-ABAS-FALAM-01`, e daria VERDE com a cura da `03-Q4` arrancada.

    O `Profile` é o do PRODUTO, e não um dublê: é ele que `_com_os_gatilhos`
    densifica, e um dicionário solto aceitaria uma escrita que o esquema real
    recusaria.
    """
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import Profile

    gravados: list[object] = []
    monkeypatch.setattr(loader, "load_profile",
                        lambda nome: Profile(name=nome, match={"type": "any"}),
                        raising=False)
    monkeypatch.setattr(loader, "save_profile",
                        lambda prof, **_: gravados.append(prof), raising=False)
    return gravados


@pytest.fixture
def disco_que_nao_abre(monkeypatch):
    """O disco em que `load_profile` LEVANTA — a segunda metade da frase.

    É o par da de cima, e as duas juntas é que separam *"não há notícia"* de
    *"há notícia"*. Sem esta, o Passo 1 poderia calar a
    `AS-DUAS-ABAS-FALAM-01` inteira e nenhuma régua desta aba veria: a que
    mede a D-17 vive noutro arquivo e interroga o gesto, não o `_aplicar`.
    """
    from hefesto_dualsense4unix.profiles import loader

    def _sem_perfil(nome: str):
        raise FileNotFoundError(f"perfil não encontrado: {nome}")

    monkeypatch.setattr(loader, "load_profile", _sem_perfil, raising=False)


def _rotulo(chave: str) -> str:
    """O rótulo de tela daquele modo, LIDO do produto."""
    from hefesto_dualsense4unix.app.actions.trigger_specs import get_spec
    from pacotes.a03_gatilhos import ROTULO_DO_JOGO_DECIDE

    if chave == "Off":  # o «Desligado» do produto é, na tela, «Sem efeito»
        return ROTULO_DO_JOGO_DECIDE
    return str(get_spec(chave).label)


def _clicar(a03, gesto_: str, ctx_, o: dict, p):
    from pacotes import gesto_da_pagina

    acao = gesto_da_pagina(PAGINA, gesto_)
    assert acao is not None, f"o gesto {gesto_!r} não tem dono nesta página"
    return acao(ctx_, {"controle": "p1", "uniq": UNIQ, **o}, p)


def test_a_dica_do_efeito_e_a_do_efeito_que_esta_escolhido(a03, ctx):
    """A dica sai do efeito DAQUELE lado, e os dois lados não dizem a mesma coisa."""
    col = a03.pacote(ctx("Rigid", "Vibration"))["colunas"][UNIQ]

    for sigla in ("e", "d"):
        escolhido = col[f"imersao-{sigla}"]
        assert col[f"dica-imersao-{sigla}"] == a03.dica_da_imersao(escolhido), (
            f"a dica do lado {sigla!r} não é a do efeito {escolhido!r} que a MESMA "
            f"carga pinta no campo — a tela explicaria um efeito e mostraria outro")
        assert col[f"dica-imersao-{sigla}"].strip(), (
            f"a dica do lado {sigla!r} saiu vazia — o `escrever()` do piloto "
            f"troca vazio por travessão, e o `title` viraria um `—` solto")

    assert col["dica-imersao-e"] != col["dica-imersao-d"], (
        "os dois gatilhos estão em acionamentos diferentes e a dica é a mesma — é a "
        "frase FIXA de antes, com outro endereço")


def test_a_dica_do_efeito_muda_quando_o_acionamento_muda(a03, ctx):
    """*"reescrita a cada tique"* — e é o tique que prova, não a função pura."""
    antes = a03.pacote(ctx("Rigid", "Rigid"))["colunas"][UNIQ]
    depois = a03.pacote(ctx("Machine", "Rigid"))["colunas"][UNIQ]

    assert antes["dica-imersao-e"] != depois["dica-imersao-e"], (
        "o perfil trocou de `Rigid` para `Machine` e a dica do L2 não mudou — "
        "ela está congelada em algum lugar entre o perfil e a tela")
    assert depois["dica-imersao-e"] == a03.dica_da_imersao(depois["imersao-e"])


def test_o_lugar_vazio_nao_explica_modo_nenhum(a03, ctx):
    """Num lugar sem aparelho a dica diz o que o CHIP daquela coluna já diz."""
    fora = a03.pacote(ctx())["colunas"]
    vazias = [pref for pref in fora if pref != UNIQ]
    assert vazias, "o pacote deixou de escrever os lugares vazios"

    for pref in vazias:
        for sigla in ("e", "d"):
            assert fora[pref][f"dica-imersao-{sigla}"] == a03.SEM_APARELHO_AQUI


# Elas exercitavam `a03_gatilhos.reenviar`, que foi apagado no dia em que a

def test_o_reenvio_saiu_do_desenho():
    """O `↻` SAIU da bancada — 06/09/2026, decisão de produto.

    **ESTA RÉGUA INVERTEU**, e a versão antiga (`…esta_nas_quatro_colunas…`)
    cobrava o botão em cada coluna, pela decisão [03] do PO de 04/09. Ela leu a
    `03-Q3` — *"a coluna GANHA um botão para mandar o efeito de novo?"* — e
    marcou *"Nada novo"* **dezenove horas depois de o botão nascer**, respondendo
    sobre um mundo em que ele não existia. Perguntada de novo em 06/09, com o
    botão na tela e a foto ao lado, escolheu **"sai"**.

    POR QUE A RÉGUA CONTINUA EXISTINDO em vez de simplesmente sumir: a remoção é
    de um `<button>` dentro da f-string da coluna, e um `git revert` desatento ou
    uma sprint velha o devolvem sem barulho — o portão do desenho veria a
    bancada só "andando" de novo, e ela reencontraria na tela um botão que
    mandou tirar.

    MORDIDA: devolva o `<button class="btn reenviar" …>` ao `aba03.py`, rode o
    gerador, e esta régua reprova junto com a 5-bis do `_conferir`.
    """
    html = BANCADA.read_text(encoding="utf-8")
    assert html.count('class="g2-cab"') >= 2, (
        "o desenho perdeu as colunas por controle — sem elas esta régua daria "
        "verde sobre uma página vazia")
    assert 'data-gesto="reenviar"' not in html, (
        "o botão de reenvio voltou ao desenho; ela mandou tirá-lo em 06/09/2026")


def test_o_reenvio_sai_do_pacote_quando_sair_do_produto(a03):
    """O botão e o dono dele saem JUNTOS, e esta régua é a corda entre os dois.

    **O ATO ACONTECEU — 08/09/2026, e esta régua é quem o cobrou.** O usuário mandou
    tirar o `↻` em 06/09 (*"sai"*), vendo-o na tela; o desenho saiu no mesmo dia
    e o gesto ficou de propósito, porque o produto renderiza a PUBLICADA e o
    botão continuava lá. A publicação veio em `f1393b41` e a segunda metade do
    ato ficou pendurada — esta régua acendeu no dia em que venceu, e portão
    nenhum dos 49 roda este arquivo, então o vermelho atravessou a integração
    calado. Hoje os dois lados estão fora: página sem botão, pacote sem gesto.

    **ELA CONTINUA MORDENDO NOS DOIS SENTIDOS**, e é por isso que fica depois de
    cobrada:

    * devolva o `<button>` ao desenho e publique → reprova, porque haveria um
      botão sem dono, e um clique sem dono não recusa, não avisa e não muda a
      tela: o piloto só imprime `[gesto sem dono]` no stderr de quem lançou a
      janela. É a `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` em miniatura;
    * devolva o `@gesto(…, "reenviar")` sem o botão → reprova, porque sobra
      código que ninguém alcança.

    Um `git revert` desatento ou uma sprint velha fazem qualquer um dos dois sem
    barulho. A lápide em `a03_gatilhos.py` diz o que o botão pagava e o que
    continua aberto: a GTK tem *"Aplicar em L2"*/*"Aplicar em R2"* e esta aba
    não tem equivalente, porque o DualSense não devolve o modo em que está.
    """
    from pacotes import gesto_da_pagina

    publicado = _publicada()
    no_produto = 'data-gesto="reenviar"' in publicado
    tem_dono = gesto_da_pagina(PAGINA, "reenviar") is not None

    assert no_produto == tem_dono, (
        "o botão de reenvio e o dono dele saíram de sincronia: a página "
        f"publicada {'TEM' if no_produto else 'NÃO tem'} o botão e o pacote "
        f"{'TEM' if tem_dono else 'NÃO tem'} o gesto. Com botão e sem dono, o "
        "clique dela morre calado; com dono e sem botão, sobrou código que "
        "ninguém alcança — e o `PISO_DA_ABA` continua cobrando 5 gestos. "
        "Ver a docstring desta régua para o que apagar.")


_OS_QUE_APLICAM = [
    ("modo", {"lado": "e", "valor": "Rigid"}),
    ("imersao", {"lado": "e", "valor": "rajada-que-sobe-sozinha"}),
]


@pytest.mark.parametrize(("gesto_", "clique"), _OS_QUE_APLICAM)
def test_o_sucesso_pleno_nao_manda_recado(
        a03, ctx, disco_que_guarda, gesto_, clique):
    """Deu tudo certo? A tela PISCA, e nenhuma palavra nova entra nela.

    **ESTA RÉGUA INVERTEU EM 06/09/2026**, e a inversão é decisão de produto. Ela
    cobrava a chave `recado` em todo sucesso — a D-01 do PO, *"no próprio
    cartão, como a recusa"*. Em 05/09 ela respondeu a `03-Q4` vendo as quatro
    formas lado a lado e escolheu **"O campo pisca em verde"**, recusando
    explicitamente a tarja verde no cartão, descrita na opção com a frase viva
    desta aba. A palavra de produto: *"nenhuma palavra nova entra na tela"*.

    **O DEFEITO QUE A VERSÃO ANTIGA GUARDAVA CONTINUA GUARDADO** — *o gesto dá
    certo e a tela não diz nada* —, e quem o guarda agora é a piscada, medida
    na `ONDA5-03-01` (`test_o_numero_da_piscada_e_o_mesmo_nos_dois_lados`).
    Trocou-se o canal, não a promessa.

    **ELA COBRE OS DOIS DE UMA VEZ DE PROPÓSITO.** A cura mora no `_aplicar`,
    que é o único lugar em que o corpo do daemon existe; escrita dentro de um
    gesto, ela passaria em metade desta régua. É o defeito de forma que esta
    casa pagou duas vezes em 05/09 — *quando a cura conhece a causa, ela cobre
    TODOS os chamadores*.

    O `disco_que_guarda` É A METADE QUE FAZ ESTA RÉGUA MEDIR ALGUMA COISA: sem
    ele o perfil `"régua"` não abre, o `recado` volta cheio pela
    `AS-DUAS-ABAS-FALAM-01`, e a régua daria verde com a cura arrancada.

    MORDIDA: devolva o recibo sempre em `_aplicar` — os DOIS reprovam juntos.
    Se reprovar um só, a cura entrou no gesto e não no `_aplicar`.
    """
    p = _Ponte()
    fora = _clicar(a03, gesto_, ctx(), clique, p)

    assert p.chamadas, (
        f"o gesto {gesto_!r} não chegou ao aparelho — sem envio esta régua "
        f"mediria o silêncio de um clique que não fez nada")
    assert not (fora or {}).get("recado"), (
        f"o gesto {gesto_!r} devolveu recado {(fora or {}).get('recado')!r} "
        f"num sucesso PLENO. Ela escolheu a piscada em 05/09 (`03-Q4`) e "
        f"recusou a palavra no cartão: *'nenhuma palavra nova entra na tela'*")


@pytest.mark.parametrize(("gesto_", "clique"), _OS_QUE_APLICAM)
def test_a_falha_de_disco_continua_falando(
        a03, ctx, disco_que_nao_abre, gesto_, clique):
    """Meio ato deu certo: aí SIM a tela fala, e diz as DUAS metades.

    É a `AS-DUAS-ABAS-FALAM-01` (decisão **D-17** dela), e esta régua existe
    porque o Passo 1 da `03-Q4` poderia calá-la inteira sem que nada nesta aba
    reclamasse: a régua que mede a D-17 vive noutro arquivo e interroga o
    GESTO, não o `_aplicar`.

    A REGRA QUE AS DUAS RÉGUAS ESCREVEM JUNTAS, e ela é da `ONDA5-03-01`:
    *quando o gesto só repete o que ela acabou de fazer, a tela pisca; quando
    ele tem NOTÍCIA, a tela fala.*

    MORDIDA: faça `_aplicar` devolver `""` sempre — os dois reprovam.
    """
    fora = _clicar(a03, gesto_, ctx(), clique, _Ponte())

    recado = (fora or {}).get("recado") or ""
    assert recado, (
        f"o gesto {gesto_!r} calou sobre um perfil que não abriu. O aparelho "
        f"recebeu e o disco não guardou — ela descobriria a perda no dia "
        f"seguinte, longe do clique")
    assert a03._E_TAMBEM in recado, (
        f"a frase não tem as duas metades: {recado!r}")


@pytest.mark.parametrize(("gesto_", "clique"), _OS_QUE_APLICAM)
def test_o_recibo_ainda_nomeia_o_gatilho_quando_prefixa_a_noticia(
        a03, ctx, disco_que_nao_abre, gesto_, clique):
    """A frase abre pelo que ELA FEZ, e o recibo é quem nomeia o gatilho.

    É o que `test_o_gesto_devolve_o_recado_que_o_piloto_leva_ao_cartao` cobrava
    antes da inversão, e que não podia se perder com ela: sem o recibo na
    frente, a segunda metade abriria por *"o efeito FOI para o aparelho…"* e a
    tela não diria de QUAL dos dois gatilhos ela está falando.

    MORDIDA: inverta a ordem do `_E_TAMBEM.join` em `_aplicar`, ou tire o
    `_recibo` da soma, e os dois reprovam.
    """
    recado = (_clicar(a03, gesto_, ctx(), clique, _Ponte()) or {}).get("recado") or ""

    assert recado.startswith(a03.NOME_DO_LADO["left"]) or (
        recado.startswith(a03.NOME_DO_LADO["right"])), (
        f"a frase não abre pelo gatilho: {recado!r}. A segunda metade vem "
        f"DEPOIS do recibo — a frase tem de abrir pelo que ela fez")


def test_o_piloto_le_a_chave_recado_e_a_tira_da_pintura():
    """O contrato dos dois lados: o pacote ESCREVE `recado`, o piloto o LÊ."""
    fonte = (INTERFACE / "hefesto_vivo.py").read_text(encoding="utf-8")
    assert 'resposta.get("recado")' in fonte, (
        "o piloto deixou de ler a chave `recado` que os gestos desta aba "
        "devolvem")
    recusadas = next((linha for linha in fonte.splitlines()
                      if linha.startswith("CHAVES_QUE_O_VIVO_RECUSA = (")), "")
    assert '"recado"' in recusadas, (
        "o piloto deixou de TIRAR o `recado` da carga antes da pintura — ele "
        "não é endereço de página nenhuma")


def test_o_recibo_nao_afirma_o_que_o_daemon_nao_disse(a03, ctx):
    """A armadilha do dublê: corpo `{}` não é "nenhum controle recebeu".

    `frase_do_desfecho` lê as duas listas de destino, e um corpo VAZIO as devolve
    vazias — o que ela traduz por *"nenhum controle recebeu"*. Num RECIBO DE
    SUCESSO isso é a tela afirmando o contrário do que aconteceu. A ponte antiga
    e o dublê da régua não dizem onde a escrita parou; a pergunta anterior
    (`_fala_de_destino`) é o que separa *"o daemon não falou disso"* de *"o
    daemon disse que ninguém recebeu"*.

    **ELA PERGUNTA AO `_recibo`, E NÃO AO GESTO — 06/09/2026.** Até aqui lia
    `fora["recado"]` de um clique de sucesso pleno, e desde a `03-Q4` esse
    recado é VAZIO: a régua passaria a medir a ausência da frase em vez da
    honestidade dela, e daria verde com a guarda `_fala_de_destino` arrancada.
    A armadilha que ela mede é do `_recibo`, e é a ele que ela pergunta.

    MORDIDA: chamar `frase_do_desfecho` sem a guarda e o recibo passa a dizer
    "nenhum controle recebeu" — verde sobre defeito vivo, a quinta vez.
    """
    from hefesto_dualsense4unix.app.textos_de_aplicacao import NADA_ACONTECEU

    for corpo in ({}, None):
        recibo = a03._recibo("left", "Rigid", corpo, ctx(), UNIQ)
        assert recibo, "o recibo ficou vazio — ele é a frase, e some se calar"
        assert NADA_ACONTECEU not in recibo, (
            f"o recibo de SUCESSO diz {recibo!r} sobre um corpo que não fala "
            f"de destino nenhum")


def test_o_recibo_conta_quando_o_daemon_diz_dois_destinos(a03, ctx):
    """Quando o daemon SABE onde aplicou, quem escreve a frase é ele.

    A frase é do dono do assunto (`app/textos_de_aplicacao.frase_do_desfecho`,
    a mesma da barra da GTK), e é ela que sabe dizer "aplicado em 2 controles"
    em vez de um "aplicado" que não conta.

    **REPONTADA EM 06/09/2026, pela mesma razão da régua acima:** o clique de
    sucesso pleno não devolve mais frase, e o dono do "aplicado em 2 controles"
    é o `_recibo` — que continua sendo chamado sempre que há uma segunda metade
    a prefixar.

    MORDIDA: montar a frase à mão no pacote e o número some.
    """
    outro = "aa:bb:cc:00:00:02"
    corpo = {"status": "ok", "aplicado_em": [UNIQ, outro], "guardado_em": []}
    recibo = a03._recibo("left", "Rigid", corpo, ctx(), UNIQ)
    assert "2" in recibo, (
        f"o daemon disse DOIS destinos e o recibo diz {recibo!r}")


def test_o_embrulho_de_cada_campo_e_pintavel_e_o_select_nao_tem_title():
    """As duas metades da mesma cura, e uma sem a outra é pior que nenhuma."""
    html = BANCADA.read_text(encoding="utf-8")
    colunas = len(set(re.findall(r'data-controle="(p\d+)"', html)))
    assert colunas >= 4, "a bancada perdeu os lugares: o laço abaixo passaria vazio"

    for prefixo in ("dica-imersao-",):
        for lado in ("e", "d"):
            achados = re.findall(
                rf'data-campo="{prefixo}{lado}"\s+data-hef-alvo="atributo"'
                rf' data-hef-atributo="(?:title|data-dica)"', html)
            assert len(achados) == colunas, (
                f"{len(achados)} embrulhos pintáveis de `{prefixo}{lado}` para "
                f"{colunas} colunas — a que ficar de fora guarda a dica da CENA")

    for atributos in re.findall(r"<select\b([^>]*)>", html):
        assert 'title="' not in atributos, (
            f"um `<select>` voltou a ter `title` próprio ({atributos.strip()!r}) "
            f"— ele sombreia a dica que o produto reescreve a cada tique")


def test_o_title_do_alvo_atributo_e_escrevivel_pelo_piloto():
    """`title` é a exceção NOMEADA da guarda de atributos do piloto."""
    fonte = (INTERFACE / "hefesto_vivo.py").read_text(encoding="utf-8")
    assert "ATRIBUTO_A_MAIS = ['title']" in fonte, (
        "a guarda do piloto deixou de permitir `title` — as dicas desta aba "
        "seriam recusadas CALADAS, que é o defeito medido em 03/09")
