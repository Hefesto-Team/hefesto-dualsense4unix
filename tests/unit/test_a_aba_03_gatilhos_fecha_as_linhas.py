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
# [03] O REENVIO
# ---------------------------------------------------------------------------
def test_o_reenvio_manda_os_dois_gatilhos_da_coluna(a03, ctx):
    """Um clique, DOIS envios — L2 e R2 —, e cada um pela porta do seu modo.

    A DÍVIDA (linha `Aplicar o efeito no aparelho`): a GTK tem "Aplicar em L2" e
    "Aplicar em R2"; a interface nova não tinha nenhum, e o "Aplicar" do rodapé
    não substitui — ele manda o que está no DISCO.

    A R-19 ESTÁ NA MESMA LINHA, e é o que a mistura de modos prova: `Off` é
    `trigger.reset` (que LIMPA a trava manual da troca automática de perfil) e
    nunca `trigger.set` com `Off` (que a ARMA).

    MORDIDA: mandar só um lado reprova na contagem; mandar `Off` por
    `trigger_set_detalhado` reprova no NOME da função.
    """
    p = _Ponte()
    forma = {"modo-chave-e": "Rigid", "modo-chave-d": "Off"}
    _clicar(a03, "reenviar", ctx(), {"forma": forma}, p)

    assert [c[0] for c in p.chamadas] == [
        "trigger_set_detalhado", "trigger_reset_detalhado"], (
        f"o reenvio chamou {[c[0] for c in p.chamadas]} — esperava um envio por "
        f"gatilho, e o `Off` pela porta do reset (R-19)")
    assert p.chamadas[0][1][0] == "left" and p.chamadas[1][1][0] == "right"
    assert all(c[2].get("uniq") == UNIQ for c in p.chamadas), (
        "um dos dois envios foi sem `uniq` — sem ele o daemon vai em BROADCAST "
        "e zera o gatilho dos quatro (o defeito ABAS-06)")


def test_o_reenvio_manda_o_que_esta_na_tela_e_nao_o_que_esta_no_disco(a03, ctx):
    """É a diferença inteira em relação ao "Aplicar" do rodapé.

    O rodapé monta o rascunho com `DraftConfig.from_profile(load_profile(nome))`
    — o perfil do DISCO. Este botão recolhe a COLUNA (`data-hef-forma`), que é o
    único lugar onde a escolha viva existe: o DualSense não devolve o modo em
    que está.

    A régua põe no disco um modo e na tela OUTRO, e cobra o da tela.

    MORDIDA: trocar a leitura da `forma` por uma consulta ao perfil e o daemon
    passa a receber `Rigid` (o do disco) em vez de `Machine` (o da tela).
    """
    p = _Ponte()
    _clicar(a03, "reenviar", ctx("Rigid", "Rigid"),
            {"forma": {"modo-chave-e": "Machine"}}, p)

    assert len(p.chamadas) == 1, "só um lado tinha modo na tela"
    assert p.chamadas[0][1][1] == "Machine", (
        f"o reenvio mandou {p.chamadas[0][1][1]!r} — o modo do DISCO. A tela "
        f"dizia `Machine`, e é o que ela vê que tem de ir")


def test_o_reenvio_leva_os_ajustes_da_coluna(a03, ctx):
    """Os números vão junto, na ORDEM do spec — nunca na ordem da tela.

    Sem isto o reenvio mandaria os PADRÕES do modo, e ela veria o botão desfazer
    o ajuste que acabou de fazer. O leitor é o mesmo do "Guardar esse efeito"
    (`_ajustes_da_coluna`), e por isso não há uma segunda ordem a divergir.

    MORDIDA: mandar `_padroes(modo)` em vez de ler a coluna e o `200` some.
    """
    from pacotes.a03_gatilhos import _padroes

    p = _Ponte()
    _clicar(a03, "reenviar", ctx(),
            {"forma": {"modo-chave-e": "Rigid", "aj-val-e-1": "200"}}, p)

    esperado = list(_padroes("Rigid"))
    esperado[1] = 200
    assert p.chamadas[0][1][2] == esperado, (
        f"o reenvio mandou {p.chamadas[0][1][2]!r} e a coluna dizia "
        f"{esperado!r} — o botão desfaria na mão dela o ajuste que ela fez")


def test_um_lado_que_recusa_nao_cala_o_outro(a03, ctx):
    """Os dois gatilhos são independentes, e parar no primeiro deixa metade.

    E A FRASE TEM DE DIZER OS DOIS: um recibo que some a recusa de um lado com o
    sucesso do outro seria a tela afirmando o que não é — a nona aparição do
    mesmo defeito de forma nesta aba.

    MORDIDA: deixar o `RuntimeError` do primeiro lado subir e o R2 nunca é
    tentado; juntar tudo num "não deu" e o nome do lado some da frase.
    """
    p = _Ponte(recusa=("left",))
    with pytest.raises(RuntimeError) as erro:
        _clicar(a03, "reenviar", ctx(),
                {"forma": {"modo-chave-e": "Rigid", "modo-chave-d": "Bow"}}, p)

    assert len(p.chamadas) == 2, (
        f"o L2 recusou e o R2 recebeu {len(p.chamadas) - 1} envio(s) — parar no "
        f"primeiro deixa a coluna pela metade, sem dizer")
    frase = str(erro.value)
    assert a03.NOME_DO_LADO["left"] in frase and a03.NOME_DO_LADO["right"] in frase, (
        f"a frase não nomeia os dois gatilhos: {frase!r}. É a cura TRG-01 — a "
        f"barra dizia `LEFT -> Off`, trocando a fala dela por id interno")


def test_o_reenvio_recusa_dizendo_quando_nao_ha_o_que_mandar(a03, ctx):
    """Sem coluna e sem modo ele RECUSA DIZENDO, nunca manda às cegas.

    São dois casos e duas frases: o botão que chegou sem `data-hef-forma` (a
    página perdeu o endereço) e a coluna cujos dois campos estão no travessão (o
    lugar vazio). Tratá-los pela mesma frase foi um defeito medido nesta aba.

    MORDIDA: devolver `None` em vez de levantar e os dois cliques passam a
    "dar certo" sem um byte no fio.
    """
    p = _Ponte()
    with pytest.raises(RuntimeError):
        _clicar(a03, "reenviar", ctx(), {}, p)
    with pytest.raises(RuntimeError):
        _clicar(a03, "reenviar", ctx(),
                {"forma": {"modo-chave-e": a03.TRAVESSAO,
                           "modo-chave-d": a03.TRAVESSAO}}, p)
    assert p.chamadas == [], "recusou e chamou o daemon assim mesmo"


def test_o_reenvio_esta_nas_quatro_colunas_do_desenho():
    """O botão é um POR COLUNA, e recolhe a coluna.

    Um botão só no pé do quadro não diria de QUAL controle ele fala — a mesma
    ambiguidade que o recibo desta aba já pagou. E sem `data-hef-forma` o piloto
    não recolhe os campos: o gesto passaria a reenviar o disco, que é o que o
    rodapé já faz.

    MORDIDA: tirar o botão de uma coluna, ou o `data-hef-forma` dele, reprova
    aqui e no `_conferir` do gerador.
    """
    html = BANCADA.read_text(encoding="utf-8")
    colunas = html.count('<div class="ctrl"')
    assert colunas >= 2, "o desenho perdeu as colunas por controle"
    assert html.count('data-gesto="reenviar"') == colunas
    assert html.count('data-gesto="reenviar" data-hef-forma="@controle"') == colunas


def test_o_glifo_do_reenvio_nao_e_emoji():
    """`U+21BB` é do bloco Arrows, que o ADR-011 preserva como UI textual.

    O emoji de mesmo desenho (`U+1F504`) seria barrado por
    `scripts/validar-glifos.py`, e com razão — **e ele não aparece escrito
    aqui**: o portão lê os arquivos desta árvore, e um exemplo do proibido é o
    proibido. Foi assim que este arquivo reprovou o `glifos` na primeira leva de
    portões desta frente, com o exemplo dentro de um comentário.

    A régua olha o que o desenho PUBLICOU, e não a constante do gerador: é no
    arquivo que o portão morde.
    """
    from unicodedata import name

    html = BANCADA.read_text(encoding="utf-8")
    assert "↻" in html, "o glifo do reenvio sumiu do desenho"
    assert "ARROW" in name("↻")
    assert chr(0x1F504) not in html, (
        "o desenho ganhou o emoji U+1F504 — o portão de glifos o reprova")


# ---------------------------------------------------------------------------
# [04] A TELA AVISA QUANDO O EFEITO CHEGA — a D-01, e o conflito C-3
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("gesto_", "clique"),
    [("modo", {"lado": "e", "valor": "Rigid"}),
     ("pronto", {"lado": "d", "v": "stop_hard"}),
     ("reenviar", {"forma": {"modo-chave-e": "Rigid"}})])
def test_o_gesto_devolve_o_recado_que_o_piloto_leva_ao_cartao(
        a03, ctx, gesto_, clique):
    """O caminho de volta do sucesso, e ele é UM: a chave `recado`.

    **O DEFEITO:** até 04/09 a interface nova só falava quando RECUSAVA. Um
    gesto que dava certo imprimia `[gesto] … → aplicado` no terminal de quem
    lançou a janela, e quem clica não lê terminal. Cinco linhas do CSV paravam
    neste mesmo buraco, em cinco abas.

    A decisão dela: *"No próprio cartão, como a recusa."* — e o conflito C-3
    recusou o campo que pisca, que era o que a lista desta aba propunha.

    A RÉGUA LÊ O CONTRATO DO PILOTO, não uma cópia dele: o nome da chave sai de
    `hefesto_vivo._deu_certo_dizendo`, que é quem a consome.

    MORDIDA: voltar a devolver `None` e o `assert` da chave reprova nos três
    gestos de uma vez.
    """
    fora = _clicar(a03, gesto_, ctx(), clique, _Ponte())

    assert isinstance(fora, dict) and fora.get("recado"), (
        f"o gesto {gesto_!r} devolveu {fora!r} — sem a chave `recado` o piloto "
        f"deposita a frase genérica e o cartão não diz O QUE chegou")
    assert a03.NOME_DO_LADO["left"] in fora["recado"] or (
        a03.NOME_DO_LADO["right"] in fora["recado"]), (
        f"o recibo não nomeia o gatilho: {fora['recado']!r}")


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

    MORDIDA: chamar `frase_do_desfecho` sem a guarda e o recibo passa a dizer
    "nenhum controle recebeu" — verde sobre defeito vivo, a quinta vez.
    """
    from hefesto_dualsense4unix.app.textos_de_aplicacao import NADA_ACONTECEU

    class _PonteAntiga(_Ponte):
        """A ponte de antes do `_detalhado`: devolve `bool`, sem corpo nenhum.

        Ela é a OUTRA metade do caso — `_desfecho` traduz um `bool` em
        `(ok, "", None)`, e um `None` também não fala de destino.
        """

        def _responder(self, nome, *a, **k):
            self.chamadas.append((nome, a, k))
            return True

    for p in (_Ponte(corpo={}), _PonteAntiga()):
        fora = _clicar(a03, "modo", ctx(), {"lado": "e", "valor": "Rigid"}, p)
        assert NADA_ACONTECEU not in fora["recado"], (
            f"o recibo de SUCESSO diz {fora['recado']!r} sobre um corpo que não "
            f"fala de destino nenhum")


def test_o_recibo_conta_quando_o_daemon_diz_dois_destinos(a03, ctx):
    """Quando o daemon SABE onde aplicou, quem escreve a frase é ele.

    A frase é do dono do assunto (`app/textos_de_aplicacao.frase_do_desfecho`,
    a mesma da barra da GTK), e é ela que sabe dizer "aplicado em 2 controles"
    em vez de um "aplicado" que não conta.

    MORDIDA: montar a frase à mão no pacote e o número some.
    """
    outro = "aa:bb:cc:00:00:02"
    p = _Ponte(corpo={"status": "ok", "aplicado_em": [UNIQ, outro],
                      "guardado_em": []})
    fora = _clicar(a03, "modo", ctx(), {"lado": "e", "valor": "Rigid"}, p)
    assert "2" in fora["recado"], (
        f"o daemon disse DOIS destinos e o recibo diz {fora['recado']!r}")


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
