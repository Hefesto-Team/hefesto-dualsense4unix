"""A aba Gatilhos e as quatro decisões de 04/09/2026 — a régua de cada uma.

As quatro estão em `docs/process/2026-09-04-O-PO-DECIDE-as-54-e-os-sete-conflitos.md`
§2 `03-gatilhos`, e nascem da sprint `ONDA2-03-GATILHOS-01`:

1. **[01] a descrição do modo escolhido** — a dica do campo deixa de ser fixa e
   passa a ser a explicação do modo ESCOLHIDO, reescrita a cada tique, com o
   texto DESTA tela (a concreta: fala de freio de carro e de espingarda).
2. **[02] a curva pronta que troca o modo** — fica como está, e a dica avisa
   ANTES do clique.
3. **[03] o reenvio** — um botão na faixa que já existe, mandando os DOIS
   gatilhos daquela coluna.
4. **[04] a tela avisa quando o efeito chega** — no cartão, pela peça da D-01.
   **Conflito C-3:** a lista da aba propunha *o campo que pisca*; ela escolheu o
   cartão, e um segundo canal quebraria a peça que fecha CINCO abas de uma vez.

**A REGRA QUE ATRAVESSA ESTE ARQUIVO:** a régua LÊ, não digita. Onde uma frase
de tela é medida, o que se compara é o dado do PRODUTO dentro dela — o rótulo
que `app/actions/trigger_specs.PRESETS` publica — e nunca a frase inteira
copiada para cá. Esta casa pagou onze vezes em 26/08 por réguas que digitavam o
que deviam ler: elas reprovavam a MELHORA em vez do defeito.
"""

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
    """O HTML que o PRODUTO renderiza — o mesmo que o piloto abre.

    O CAMINHO TEM DONO E NÃO SE DIGITA: `interface/onde.py` é o único módulo que
    sabe onde moram a bancada e o publicado, e montar a pasta à mão aqui seria a
    segunda cópia — a que envelhece calada no dia em que a pasta mudar de nome.
    Já aconteceu nesta casa: três réguas deram verde sobre nada porque *as
    pastas mudaram de nome e as réguas não foram junto*.
    """
    from hefesto_dualsense4unix.interface import onde

    return onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")

#: O MAC é da faixa sintética da casa (`aa:bb:cc`): há DOIS portões de anonimato
#: nesta árvore, e o segundo pega por FORMA, sem consultar OUI nenhum.
UNIQ = "aa:bb:cc:00:00:01"
FALSO = {"uniq": UNIQ, "player": 1, "transport": "usb", "is_primary": True,
         "inputs": {"l2_raw": 0, "r2_raw": 0}}
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "USB", "cor": "starlight-blue", "mascara": "DualSense"}]

#: O QUE O DAEMON RESPONDE QUANDO O BYTE SAIU — a forma medida em 23/08 e o
#: contrato de `ipc_bridge.trigger_set_detalhado`.
APLICOU = {"status": "ok", "aplicado_em": [UNIQ], "guardado_em": []}


# ---------------------------------------------------------------------------
# a bancada
# ---------------------------------------------------------------------------
@pytest.fixture
def a03():
    """O pacote, com o rascunho LIMPO nas duas pontas.

    Ele é estado de MÓDULO: sem esta limpeza um teste herdaria o que o anterior
    aplicou, e a régua passaria a medir a ordem em que os testes rodam.
    """
    import pacotes  # noqa: F401  (registra os dez)
    from pacotes import a03_gatilhos

    a03_gatilhos.esquecer_o_rascunho()
    yield a03_gatilhos
    a03_gatilhos.esquecer_o_rascunho()


class _Ponte:
    """A ponte que ACEITA e diz onde aplicou. Guarda o que foi chamado.

    `recusa` é a lista de LADOS que devem falhar — é o que permite provar que um
    gatilho recusado não cala o outro, que é o caso do reenvio.
    """

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
        # LISTA SEPARADA, E NÃO A `chamadas`: as réguas do reenvio comparam
        # `[c[0] for c in p.chamadas]` com a lista EXATA dos envios ao gatilho.
        # Somar o `launch_env.refresh` ali faria a régua da R-19 reprovar por
        # um método que não é envio nenhum.
        self.avulsas.append(metodo)
        return True


@pytest.fixture
def ctx(monkeypatch):
    """A mesa de um controle, com o perfil injetado pela porta de cima.

    `monkeypatch` E NÃO ATRIBUIÇÃO CRUA: `pacotes.perfil` é um módulo, e uma
    troca sem desfazer vazaria para todo teste que rodasse depois neste mesmo
    processo — a suíte roda em oito lotes, e um lote é um processo só.
    """
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

    return str(get_spec(chave).label)


def _clicar(a03, gesto_: str, ctx_, o: dict, p):
    from pacotes import gesto_da_pagina

    acao = gesto_da_pagina(PAGINA, gesto_)
    assert acao is not None, f"o gesto {gesto_!r} não tem dono nesta página"
    return acao(ctx_, {"controle": "p1", "uniq": UNIQ, **o}, p)


# ---------------------------------------------------------------------------
# [01] A DESCRIÇÃO DO MODO ESCOLHIDO
# ---------------------------------------------------------------------------
def test_a_dica_do_modo_e_a_do_modo_que_esta_escolhido(a03, ctx):
    """A dica sai do modo DAQUELE lado, e os dois lados não dizem a mesma coisa.

    O DEFEITO: a página não tinha elemento de descrição. Depois de escolher, a
    coluna deixava de dizer o que aquele modo faz — o `<select>` fechado mostra
    só o rótulo, e o `title` da opção escolhida **não é** o `title` do
    `<select>`. Na GTK a explicação do modo em uso está SEMPRE na tela
    (`GtkLabel` em itálico debaixo da grade, `main.glade:874`).

    MORDIDA: cravar a dica (devolver a mesma frase para os dois lados, ou a
    frase fixa de antes) reprova nas duas asserções — a de igualdade com a
    descrição do modo EMITIDO e a de que L2 e R2 divergem quando os modos
    divergem.
    """
    col = a03.pacote(ctx("Rigid", "Vibration"))["colunas"][UNIQ]

    for sigla in ("e", "d"):
        chave = col[f"modo-chave-{sigla}"]
        assert col[f"dica-modo-{sigla}"] == a03.descricao_do_modo(chave), (
            f"a dica do lado {sigla!r} não é a do modo {chave!r} que a MESMA "
            f"carga pinta no campo — a tela explicaria um modo e mostraria "
            f"outro")
        assert col[f"dica-modo-{sigla}"].strip(), (
            f"a dica do lado {sigla!r} saiu vazia — o `escrever()` do piloto "
            f"troca vazio por travessão, e o `title` viraria um `—` solto")

    assert col["dica-modo-e"] != col["dica-modo-d"], (
        "os dois gatilhos estão em modos diferentes e a dica é a mesma — é a "
        "frase FIXA de antes, com outro endereço")


def test_a_dica_do_modo_muda_quando_o_modo_muda(a03, ctx):
    """*"reescrita a cada tique"* — e é o tique que prova, não a função pura.

    UMA DICA QUE SÓ ESTÁ CERTA NO PRIMEIRO TIQUE é o defeito de forma que esta
    casa já nomeou: a tela afirmando o estado de ontem. A régua roda o pacote
    DUAS VEZES, com o perfil trocado entre as duas.

    MORDIDA: guardar a dica num cache de módulo, ou lê-la da CENA em vez do
    dado, e as duas cargas passam a devolver a mesma frase.
    """
    antes = a03.pacote(ctx("Rigid", "Rigid"))["colunas"][UNIQ]["dica-modo-e"]
    depois = a03.pacote(ctx("Machine", "Rigid"))["colunas"][UNIQ]["dica-modo-e"]

    assert antes != depois, (
        "o perfil trocou de `Rigid` para `Machine` e a dica do L2 não mudou — "
        "ela está congelada em algum lugar entre o perfil e a tela")
    assert depois == a03.descricao_do_modo("Machine")


def test_o_lugar_vazio_nao_explica_modo_nenhum(a03, ctx):
    """Num lugar sem aparelho a dica diz o que o CHIP daquela coluna já diz.

    São a mesma frase e uma constante só (`SEM_APARELHO_AQUI`): duas cópias
    divergiriam no primeiro dia em que alguém mexesse numa, e a coluna vazia
    passaria a dizer duas coisas diferentes sobre o mesmo nada. Deixar ali a
    explicação do `Desligado` seria a tela explicando o efeito de um aparelho
    que não está aqui.

    MORDIDA: emitir a descrição do modo (ou `""`) para o lugar vazio reprova —
    a primeira por conteúdo, a segunda porque o piloto pinta vazio como `—`.
    """
    fora = a03.pacote(ctx())["colunas"]
    vazias = [pref for pref in fora if pref != UNIQ]
    assert vazias, "o pacote deixou de escrever os lugares vazios"

    for pref in vazias:
        for sigla in ("e", "d"):
            assert fora[pref][f"dica-modo-{sigla}"] == a03.SEM_APARELHO_AQUI
            assert fora[pref][f"dica-pronto-{sigla}"] == a03.SEM_APARELHO_AQUI


# ---------------------------------------------------------------------------
# [02] A CURVA PRONTA QUE TROCA O MODO — o aviso ANTES do clique
# ---------------------------------------------------------------------------
def _destinos_da_lista(a03, modo: str) -> set[str]:
    """Para que modos as curvas que o campo OFERECE naquele modo levam.

    A RÉGUA NÃO PERGUNTA AO PACOTE O QUE O PACOTE RESPONDE: ela monta a lista
    do jeito que a TELA a monta (`html_das_opcoes_de_pronto`, o mesmo HTML que
    o piloto troca a cada tique), lê os `value` das opções e resolve cada um
    pela tabela do produto. É o caminho de quem clica, e não uma segunda cópia
    da conta que está sendo medida.
    """
    html = a03.html_das_opcoes_de_pronto(modo)
    fora: set[str] = set()
    for chave in re.findall(r'<option value="([^"]*)"', html):
        if (not chave or chave in ("custom", a03.TRAVESSAO)
                or chave.startswith(a03.PREFIXO_DO_MEU)):
            continue
        try:
            fora.add(a03._curva(chave)[1])
        except ValueError:
            continue
    return fora


@pytest.mark.parametrize("modo", ["Rigid", "Off", "Machine",
                                  "MultiPositionFeedback",
                                  "MultiPositionVibration"])
def test_a_dica_do_pronto_nomeia_exatamente_os_destinos_que_a_lista_abre(a03, modo):
    """A dica nomeia os modos que um clique PODE produzir — nem mais, nem menos.

    **ESTA RÉGUA JÁ DERRUBOU A PRIMEIRA VERSÃO DA CURA, e é por isso que ela
    está escrita assim.** A frase dizia, nos dezessete modos comuns, que *"as
    curvas de força vão para «Curva de força» e as de vibração para «Vibração
    por posição»"* — e é FALSO: com o gatilho em `Rigid` o campo oferece só as
    seis curvas de FEEDBACK, então `Vibração por posição` não é alcançável dali.
    A tela descreveria um caminho que a lista não abre. **Nenhum alarme sem
    medição.**

    A régua monta a lista como a tela a monta e resolve cada curva pela tabela
    em que ela mora. Nada aqui é digitado: os rótulos saem do `PRESETS`.

    MORDIDA (as duas, e as duas reprovam):
    * anunciar um destino a mais (a frase de antes) → o `<=` da igualdade cai;
    * calar o destino, ou trocar o ramo dos modos por posição pelo dos outros
      dezessete, → o `>=` cai, ou a última asserção cai.
    """
    dica = a03.dica_do_pronto(modo)
    abre = _destinos_da_lista(a03, modo)

    assert _rotulo(modo) in dica, (
        f"a dica não diz que o gatilho está em {modo!r} — sem o estado de agora "
        f"ela não é um aviso, é um manual")

    nomeados = {d for d in a03.MODOS_COM_CURVA if _rotulo(d) in dica}
    if abre == {modo}:
        # O gatilho JÁ está no modo da lista: nenhum clique troca coisa
        # nenhuma, e o único nome que aparece é o dele mesmo.
        assert nomeados == {modo}, (
            f"{modo!r} não troca de modo por esta lista, e a dica nomeia "
            f"{sorted(nomeados)} — avisar de uma troca que não acontece ensina "
            f"a ignorar o aviso")
    else:
        assert nomeados == abre, (
            f"a lista deste campo leva a {sorted(abre)} e a dica nomeia "
            f"{sorted(nomeados)}")


def _esqueleto(a03, modo: str) -> str:
    """A dica com TODOS os rótulos de modo apagados — o que sobra é a promessa.

    É o instrumento que separa *"a frase mudou porque o modo mudou"* de *"a
    frase mudou porque o que ela promete mudou"*. Sem ele a régua compara nomes
    e dá verde sobre uma dica que anuncia troca onde não há nenhuma — medido na
    mordida desta frente, e é por isso que este teste existe.
    """
    from hefesto_dualsense4unix.app.actions.trigger_specs import PRESETS

    fora = a03.dica_do_pronto(modo)
    for rotulo in sorted((p.label for p in PRESETS), key=len, reverse=True):
        fora = fora.replace(rotulo, "MODO")
    return fora


def test_onde_a_curva_nao_troca_o_modo_a_dica_nao_anuncia_troca(a03):
    """Duas promessas diferentes para dois casos diferentes — e não uma só.

    Com o gatilho já em `MultiPositionFeedback`, a lista só oferece curvas
    daquele modo: **nenhum clique troca coisa nenhuma**, e a dica tem de dizer
    isso. Fora dali, todo clique troca, e a dica tem de dizer aquilo. Um aviso
    de troca que não acontece ensina a ignorar o aviso — que é o custo real de
    um alarme sem medição.

    A RÉGUA APAGA OS RÓTULOS antes de comparar: sem isso ela mede o NOME do modo
    (que muda sempre, por construção) em vez da promessa. Foi exatamente assim
    que a primeira versão desta linha deu verde sobre a cura arrancada.

    MORDIDA: fazer os 19 caírem no mesmo ramo e os dois esqueletos ficam
    idênticos.
    """
    assert _esqueleto(a03, "MultiPositionFeedback") != _esqueleto(a03, "Rigid"), (
        "a dica promete a mesma coisa nos dois casos, e eles são opostos: num "
        "o clique troca o modo, no outro não troca nada")


def test_a_dica_do_pronto_acompanha_o_modo_no_tique(a03, ctx):
    """E ela chega à tela pelo tique, com o modo daquele lado — não uma por aba.

    MORDIDA: emitir uma dica só para a coluna (em vez de uma por LADO) e os dois
    lados passam a dizer o mesmo com modos diferentes.
    """
    col = a03.pacote(ctx("Rigid", "MultiPositionFeedback"))["colunas"][UNIQ]
    assert col["dica-pronto-e"] == a03.dica_do_pronto(col["modo-chave-e"])
    assert col["dica-pronto-d"] == a03.dica_do_pronto(col["modo-chave-d"])
    assert col["dica-pronto-e"] != col["dica-pronto-d"]


# ---------------------------------------------------------------------------
# [03] O REENVIO — as cinco réguas do GESTO saíram em 08/09/2026, com ele.
#
# Elas exercitavam `a03_gatilhos.reenviar`, que foi apagado no dia em que a
# publicação de `44c2327e` tirou o `↻` da página que o produto renderiza. Ver a
# lápide em `a03_gatilhos.py`, que diz o que o botão pagava e continua aberto.
#
# AS DUAS QUE FICAM são as que guardam a DECISÃO DELA, e nenhuma das duas toca
# o gesto: uma cobra que o botão não volte ao desenho, a outra que o botão e o
# dono nunca voltem em separado.
# ---------------------------------------------------------------------------

def test_o_reenvio_saiu_do_desenho():
    """O `↻` SAIU da bancada — 06/09/2026, decisão dela.

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
    assert html.count('<div class="ctrl"') >= 2, (
        "o desenho perdeu as colunas por controle — sem elas esta régua daria "
        "verde sobre uma página vazia")
    assert 'data-gesto="reenviar"' not in html, (
        "o botão de reenvio voltou ao desenho; ela mandou tirá-lo em 06/09/2026")


def test_o_reenvio_sai_do_pacote_quando_sair_do_produto(a03):
    """O botão e o dono dele saem JUNTOS, e esta régua é a corda entre os dois.

    **O ATO ACONTECEU — 08/09/2026, e esta régua é quem o cobrou.** Ela mandou
    tirar o `↻` em 06/09 (*"sai"*), vendo-o na tela; o desenho saiu no mesmo dia
    e o gesto ficou de propósito, porque o produto renderiza a PUBLICADA e o
    botão continuava lá. A publicação veio em `44c2327e` e a segunda metade do
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


# ---------------------------------------------------------------------------
# [04] A TELA AVISA QUANDO O EFEITO CHEGA — a D-01, e o conflito C-3
# ---------------------------------------------------------------------------
#: OS QUATRO GESTOS QUE CHEGAM AO APARELHO. O `guardar` fica de fora porque ele
#: nunca devolveu `recado` — ver `test_o_guardar_nao_ganhou_recibo`.
_OS_QUE_APLICAM = [
    ("modo", {"lado": "e", "valor": "Rigid"}),
    ("pronto", {"lado": "d", "v": "stop_hard"}),
    ("ajuste", {"lado": "e", "i": "1", "valor": "200",
                "forma": {"modo-chave-e": "Rigid"}}),
]


@pytest.mark.parametrize(("gesto_", "clique"), _OS_QUE_APLICAM)
def test_o_sucesso_pleno_nao_manda_recado(
        a03, ctx, disco_que_guarda, gesto_, clique):
    """Deu tudo certo? A tela PISCA, e nenhuma palavra nova entra nela.

    **ESTA RÉGUA INVERTEU EM 06/09/2026**, e a inversão é decisão dela. Ela
    cobrava a chave `recado` em todo sucesso — a D-01 do PO, *"no próprio
    cartão, como a recusa"*. Em 05/09 ela respondeu a `03-Q4` vendo as quatro
    formas lado a lado e escolheu **"O campo pisca em verde"**, recusando
    explicitamente a tarja verde no cartão, descrita na opção com a frase viva
    desta aba. A palavra dela: *"nenhuma palavra nova entra na tela"*.

    **O DEFEITO QUE A VERSÃO ANTIGA GUARDAVA CONTINUA GUARDADO** — *o gesto dá
    certo e a tela não diz nada* —, e quem o guarda agora é a piscada, medida
    na `ONDA5-03-01` (`test_o_numero_da_piscada_e_o_mesmo_nos_dois_lados`).
    Trocou-se o canal, não a promessa.

    **ELA COBRE OS QUATRO DE UMA VEZ DE PROPÓSITO.** A cura mora no `_aplicar`,
    que é o único lugar em que o corpo do daemon existe; escrita dentro de um
    gesto, ela passaria em um quarto desta régua. É o defeito de forma que esta
    casa pagou duas vezes em 05/09 — *quando a cura conhece a causa, ela cobre
    TODOS os chamadores*.

    O `disco_que_guarda` É A METADE QUE FAZ ESTA RÉGUA MEDIR ALGUMA COISA: sem
    ele o perfil `"régua"` não abre, o `recado` volta cheio pela
    `AS-DUAS-ABAS-FALAM-01`, e a régua daria verde com a cura arrancada.

    MORDIDA: devolva o recibo sempre em `_aplicar` — os QUATRO reprovam juntos.
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

    O `reenviar` FICA DE FORA, e não é esquecimento: ele passa `guardar=False`
    e não escreve byte nenhum no disco dela — logo não tem segunda metade a
    dizer. Quem guarda esse contrato é
    `test_o_gatilho_aplicado_vai_para_o_perfil.py::test_o_reenviar_nao_ganhou_frase_de_disco`.

    MORDIDA: faça `_aplicar` devolver `""` sempre — os três reprovam.
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
    `_recibo` da soma, e os três reprovam.
    """
    recado = (_clicar(a03, gesto_, ctx(), clique, _Ponte()) or {}).get("recado") or ""

    assert recado.startswith(a03.NOME_DO_LADO["left"]) or (
        recado.startswith(a03.NOME_DO_LADO["right"])), (
        f"a frase não abre pelo gatilho: {recado!r}. A segunda metade vem "
        f"DEPOIS do recibo — a frase tem de abrir pelo que ela fez")


def test_o_guardar_nao_ganhou_recibo(a03, ctx, disco_que_guarda):
    """O "Guardar esse efeito" nunca devolveu `recado`, e continua sem.

    ELE JÁ ESTAVA CERTO ANTES DA `03-Q4`, e é a razão de esta régua ser curta:
    com a piscada da `ONDA5-03-01`, um `None` passou a dizer "deu certo" sem
    palavra nenhuma — exatamente o que ela pediu, sem uma linha nova. O risco
    que ela guarda é o de alguém "uniformizar" os cinco gestos acrescentando
    recibo a este, que é a forma pela qual a palavra voltaria à tela pela porta
    dos fundos.

    MORDIDA: devolva `{"recado": …}` no `guardar` e esta régua reprova.
    """
    fora = _clicar(a03, "guardar", ctx(),
                   {"forma": {"modo-chave-e": "Rigid", "modo-chave-d": "Bow"}},
                   _Ponte())

    assert not (fora or {}).get("recado"), (
        f"o `guardar` ganhou um recibo: {(fora or {}).get('recado')!r}")


def test_o_piloto_le_a_chave_recado_e_a_tira_da_pintura():
    """O contrato dos dois lados: o pacote ESCREVE `recado`, o piloto o LÊ.

    Esta régua existe porque as duas metades vivem em arquivos diferentes e uma
    troca de nome numa delas some em silêncio — o `escrever()` procuraria um
    `data-campo="recado"` que não existe, e o recibo nunca chegaria ao cartão.

    MORDIDA: renomear a chave num dos dois lados reprova aqui.
    """
    fonte = (INTERFACE / "hefesto_vivo.py").read_text(encoding="utf-8")
    assert 'resposta.get("recado")' in fonte, (
        "o piloto deixou de ler a chave `recado` que os gestos desta aba "
        "devolvem")
    assert '"recado" in resposta' in fonte, (
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

    # `None` é a ponte ANTIGA (`_desfecho` traduz um `bool` em `(ok, "", None)`)
    # e `{}` é o dublê da régua: nenhum dos dois fala de destino.
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


# ---------------------------------------------------------------------------
# O DESENHO — o que a página tem de oferecer para as quatro caberem nela
# ---------------------------------------------------------------------------
def test_o_embrulho_de_cada_campo_e_pintavel_e_o_select_nao_tem_title():
    """As duas metades da mesma cura, e uma sem a outra é pior que nenhuma.

    O navegador mostra o `title` do ancestral mais próximo quando o elemento sob
    o rato não tem o seu. Um `title` no `<select>` VENCE o do embrulho — e o
    embrulho é o único que pode ser pintado, porque o campo de escolha já gasta
    o seu `data-hef-alvo` com `valor` (sem ele a primeira pintura faria
    `select.textContent = "Rígido"` e apagaria as 19 opções).

    Devolver o `title` ao `<select>` não deixaria a tela vazia: deixaria a
    explicação CONGELADA na frase da cena — a tela afirmando o modo de ontem.

    MORDIDA: pôr um `title` de volta no `<select>`, ou tirar o `data-hef-alvo`
    de um embrulho, reprova aqui e no `_conferir` do gerador.
    """
    html = BANCADA.read_text(encoding="utf-8")
    colunas = html.count('<div class="ctrl"')

    for prefixo in ("dica-modo-", "dica-pronto-"):
        for lado in ("e", "d"):
            achados = re.findall(
                rf'data-campo="{prefixo}{lado}"\s+data-hef-alvo="atributo"'
                rf' data-hef-atributo="title"', html)
            assert len(achados) == colunas, (
                f"{len(achados)} embrulhos pintáveis de `{prefixo}{lado}` para "
                f"{colunas} colunas — a que ficar de fora guarda a dica da CENA")

    for atributos in re.findall(r"<select\b([^>]*)>", html):
        assert 'title="' not in atributos, (
            f"um `<select>` voltou a ter `title` próprio ({atributos.strip()!r}) "
            f"— ele sombreia a dica que o produto reescreve a cada tique")


def test_o_title_do_alvo_atributo_e_escrevivel_pelo_piloto():
    """`title` é a exceção NOMEADA da guarda de atributos do piloto.

    Ela é curta de propósito (`data-*`/`aria-*`, menos os cinco de endereço e
    todo `data-hef`), e o `title` entrou por nome em 03/09. Se alguém a fechar,
    os embrulhos desta aba passam a pedir um atributo que nunca pinta — e o
    único barulho viria de um portão, nunca da tela.
    """
    fonte = (INTERFACE / "hefesto_vivo.py").read_text(encoding="utf-8")
    assert "ATRIBUTO_A_MAIS = ['title']" in fonte, (
        "a guarda do piloto deixou de permitir `title` — as dicas desta aba "
        "seriam recusadas CALADAS, que é o defeito medido em 03/09")
