"""O trilho de brilho da aba Iluminação passa a GRAVAR — decisão dela, 03/09/2026.

Perguntada se mexer no brilho grava o perfil na hora ou espera o "Salvar
Perfil", ela respondeu **"Grava na hora"**.

O QUE HAVIA ATÉ HOJE, e está fotografado no `docs/data/paridade-gtk-html.csv`:
o trilho JÁ ERA DESENHADO como slider — a regra `.cheio::after` punha um knob de
12px na ponta da barra roxa — e **não fazia nada**. Ela via `100%`, arrastava, e
o número não mudava. A linha do CSV o chamava de *"a maior falta desta aba"*,
com a contagem: `publicado = cor(16) apagar(2) auto(2) player(8)`; nenhum de
brilho em lugar nenhum.

POR QUE GRAVAR É A ÚNICA SAÍDA COERENTE, e está medido: esta interface NÃO TEM
RASCUNHO (decisão dela de 01/09 — *"clicar na cor já deveria aplicar a cor no
controle"*), e o número que a coluna imprime é lido do PERFIL EM DISCO por
`brilho_do_controle`. Sem gravar, o valor voltaria sozinho ao velho no tique
seguinte — mais um botão que aceita o toque e não age.

O QUE ESTES TESTES COBREM, cada um com a mordida escrita:

1. o gesto EXISTE, tem dono, e a página o oferece num `<input type="range">` —
   e o lugar VAZIO da mesa não oferece nenhum;
2. o arraste GRAVA no disco, no override DAQUELE controle, na escala do disco
   (0.0-1.0) e com a chave que o esquema exige (12 hex, sem `:`);
3. a gravação PRESERVA o que já estava no override — os overrides do disco dela
   hoje são `{"lightbar": [255, 0, 0]}` e nada mais;
4. o aparelho recebe a COR PEDIDA com o brilho NOVO, e a cor pedida sai do
   brilho VELHO (D8: o `lightbar_rgb` do daemon é pós-escala);
5. o `click` que o navegador manda DEPOIS do `change` não grava uma segunda vez;
6. as TRÊS recusas dizem por quê — e a quarta deixou de ser recusa em
   04/09/2026: quando não há cor a reacender o brilho VAI ao disco, e o gesto
   avisa pelo canal de SUCESSO da D-01, com a frase curta que ela escolheu;
7. o gesto está em `hefesto_vivo.PERIGOSOS` — uma régua não arrasta o brilho
   dela para provar que sabe clicar.

O LAR É DE MENTIRA. O `conftest` desvia `HOME` e os quatro `XDG_*`; estes testes
escrevem perfil de verdade, com `save_profile`, dentro dele — que é a única
forma de provar que o disco recebeu, em vez de provar que a função foi chamada.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"), str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: MAC da faixa sintética da casa — há dois portões de anonimato nesta árvore.
#: Ele vem COM `:` de propósito: é a forma em que a régua desta casa endereça um
#: controle, e o disco guarda a outra. Provar a ida e a volta entre as duas é
#: metade do que este arquivo mede.
UNIQ = "aa:bb:cc:00:00:01"
CHAVE = "aabbcc000001"
OUTRO = "aa:bb:cc:00:00:02"

MESA = [
    {"pref": "p1", "uniq": UNIQ, "jogador": 1, "cor": "white",
     "nome": "White", "via": "USB", "transporte": "usb"},
]

#: A COLUNA COMO O DAEMON A PUBLICA. `lightbar_rgb` é PÓS-escala de brilho por
#: contrato (D8) — aqui, o azul do P1 a 100%.
ACESO = {"uniq": UNIQ, "index": 0, "transport": "usb", "connected": True,
         "player": 1, "player_slot": 1, "is_primary": True,
         "lightbar_rgb": [0, 0, 255], "lightbar_on": True,
         "lightbar_source": "sysfs"}

PAGINA = "04-iluminacao.html"


@pytest.fixture
def a04():
    from pacotes import a04_iluminacao

    return a04_iluminacao


@pytest.fixture
def pac():
    import pacotes

    return pacotes


def _ctx(pac, *, perfil="regua", aceso=None, state=None):
    corpo = dict(ACESO)
    if aceso is not None:
        corpo.update(aceso)
    return pac.Contexto(state={"active_profile": perfil, **(state or {})},
                        mesa=list(MESA), conectados=[corpo], estados={})


class PonteDeMentira:
    """Um dublê da ponte que guarda o que foi chamado e devolve o corpo dado.

    O CORPO PADRÃO É O DO CAMINHO FELIZ do `led.set` — `aplicado_em` com o alvo
    dentro. Sem ele o gesto levantaria a frase do produto, e o teste mediria a
    recusa em vez da escrita.
    """

    def __init__(self, corpo=None):
        self.corpo = {"aplicado_em": [UNIQ], "guardado_em": []} if corpo is None else corpo
        self.chamadas: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, nome: str):
        def registrar(*args, **kwargs):
            self.chamadas.append((nome, args, kwargs))
            return True if nome == "chamar" else self.corpo

        return registrar


def _semear(nome: str, *, overrides: dict | None = None, brilho_global: float = 1.0):
    """Escreve um perfil no lar de mentira e devolve o caminho do arquivo.

    ELE PASSA PELO `save_profile` DO PRODUTO, e não por um `json.dump` à mão: o
    que este arquivo mede é um round-trip disco→gesto→disco, e semear por fora
    do dono deixaria a régua concordando com uma forma de arquivo que o produto
    não escreve.
    """
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        LedsConfig,
        MatchAny,
        Profile,
    )

    prof = Profile(
        name=nome,
        match=MatchAny(),
        leds=LedsConfig(lightbar=(40, 80, 180), lightbar_brightness=brilho_global),
        controllers={
            chave: ControllerOverrides(**{"leds": LedsConfig(**campos)} if campos else {})
            for chave, campos in (overrides or {}).items()
        },
    )
    return save_profile(prof, origem="regua")


def _do_disco(caminho: pathlib.Path) -> dict:
    return json.loads(pathlib.Path(caminho).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. o gesto existe, e a PÁGINA o oferece — no lugar certo
# ---------------------------------------------------------------------------
def test_o_trilho_tem_dono(pac, a04):
    """Um `data-gesto` sem função é um trilho que engole o arraste.

    A MORDIDA: apague o `@gesto("04-iluminacao.html", "brilho")` e esta linha
    reprova — que é exatamente o estado da aba até 03/09/2026, com a diferença
    de que lá nem o `data-gesto` existia.
    """
    assert pac.gesto_da_pagina(PAGINA, "brilho") is not None
    assert a04.PISO_DA_ABA >= 5, (
        f"o piso da aba é {a04.PISO_DA_ABA} e só sobe — com 4 a régua dos "
        f"botões daria verde sobre um trilho que voltou a não fazer nada")


def test_a_pagina_oferece_o_trilho_e_o_lugar_vazio_nao(a04):
    """O `<input type="range">` é o polegar de verdade — e ele não nasce sem dono.

    AS DUAS METADES, e a segunda é a que morde: a coluna VIVA tem o trilho com
    `data-gesto="brilho"`, e a coluna VAZIA não tem nenhum. Um ajuste vivo num
    lugar sem aparelho é um gesto que não teria em qual controle escrever — e
    este escreve no DISCO dela.

    A MORDIDA: emita o `<input>` também na `coluna_vazia` do `aba04.py` e a
    segunda asserção reprova (o próprio gerador já reprova antes, na régua 4 do
    `_conferir` — são duas réguas independentes sobre o mesmo defeito, que é
    regra desta casa).
    """
    from hefesto_dualsense4unix.interface import onde

    corpo = (onde.BANCADA / PAGINA).read_text(encoding="utf-8")
    vivas = corpo.count('data-gesto="brilho"')
    assert vivas >= 1, "a bancada não oferece o trilho de brilho a controle nenhum"
    assert corpo.count('type="range"') == vivas, (
        "há `type=\"range\"` sem `data-gesto=\"brilho\"` na página — um polegar "
        "que se arrasta e não chega a gesto nenhum")

    #: O RECORTE TEM DOIS LADOS, e os DOIS estavam errados na régua do gerador
    #: — medido em 03/09/2026 ao tentar mordê-la, e ela passou:
    #:
    #: * o fim de um bloco era `split('<div class="ctrl')`, e
    #:   `<div class="ctrl-rot">` começa com esse prefixo: o bloco terminava no
    #:   `</div>` da moldura, com 46.798 caracteres de SVG e NENHUMA das quatro
    #:   células que a régua existe para vigiar;
    #: * o fim do ÚLTIMO bloco era o fim do miolo, e por isso ele engolia o
    #:   RODAPÉ — os quatro botões do esqueleto das dez páginas.
    #:
    #: As duas metades são a mesma armadilha do `COMO-OLHAR-A-TELA.md`: casar
    #: uma FRONTEIRA por prefixo, em vez do campo que a significa.
    grade = corpo.split('<div class="luz-grade">', 1)[-1].split('<div class="rodape"', 1)[0]
    vazias = re.findall(r'<div class="ctrl vazia"(.*?)(?=<div class="ctrl[" ]|\Z)',
                        grade, re.S)
    assert vazias, "a página não tem lugar vazio — a régua não mediria nada"
    for bloco in vazias:
        assert "cel-brilho" in bloco and "cel-acoes" in bloco, (
            "o recorte da coluna vazia não alcança as células — a régua estaria "
            "dando verde sobre o desenho")
        assert "<button" not in bloco and "rodape" not in bloco, (
            "o recorte da coluna vazia passou do fim da grade e engoliu o rodapé")
        assert 'type="range"' not in bloco, (
            "um lugar VAZIO da mesa oferece o trilho de brilho — arrastá-lo não "
            "teria em qual controle gravar")
        assert "data-gesto" not in bloco, (
            "um lugar VAZIO oferece gesto — botão que engole o toque")


def test_o_trilho_e_pintado_pelo_produto(a04):
    """O polegar recebe o valor VIVO, e não fica no que o gerador cravou.

    `data-campo="brilho-pct"` + `data-hef-alvo="valor"` é o endereço que o
    `hefesto_vivo.escrever` conhece para escrever num `el.value`. Sem ele o
    trilho nasceria em 82% (o número do mockup) e ficaria lá para sempre,
    enquanto a barra roxa ao lado mostraria o valor de verdade — a coluna
    contradizendo a si mesma.

    A MORDIDA: tire o `data-hef-alvo="valor"` do `<input>` e esta linha reprova.
    """
    from hefesto_dualsense4unix.interface import onde

    corpo = (onde.BANCADA / PAGINA).read_text(encoding="utf-8")
    for trecho in corpo.split('data-gesto="brilho"')[1:]:
        campo = trecho.split(">", 1)[0]
        assert 'data-campo="brilho-pct"' in campo or 'data-campo="brilho-pct"' in \
            trecho.split("<input", 1)[0], campo
        assert 'data-hef-alvo="valor"' in campo, (
            f"o trilho não tem o alvo de pintura do valor: {campo!r}")


# ---------------------------------------------------------------------------
# 2. o arraste GRAVA — no disco, no controle, na escala do disco
# ---------------------------------------------------------------------------
def test_o_arraste_grava_no_override_daquele_controle(pac, a04):
    """A promessa do gesto: "Grava na hora". Esta é a régua que a mede.

    TRÊS COISAS NUMA LINHA SÓ, e cada uma foi um caminho para o defeito:

    * a ESCALA — o disco guarda `0.0-1.0` (`LedsConfig`) e a tela mostra `0-100`
      (`LedsDraft`). Gravar `40` num campo `le=1.0` levanta no pydantic; gravar
      `0.4` na tela mostraria 0%;
    * o ALVO — o override DAQUELE controle, não a seção global. Global faria o
      trilho do P2 mudar o brilho do P1;
    * a CHAVE — 12 hex sem `:`, que é o que `_validate_controllers_keys` exige.
      Com `aa:bb:cc:…` o esquema recusa o arquivo inteiro no próximo load.

    A MORDIDA: troque `_fracao_do_disco(pct)` por `pct` e a primeira asserção
    reprova com o ValidationError do esquema; grave em `prof.leds` e a segunda
    reprova; use `uniq` cru como chave e o `load_profile` seguinte levanta.
    """
    arquivo = _semear("regua")
    fn = pac.gesto_da_pagina(PAGINA, "brilho")
    fn(_ctx(pac), {"uniq": UNIQ, "valor": "40", "evento": "change"}, PonteDeMentira())

    disco = _do_disco(arquivo)
    assert list(disco["controllers"]) == [CHAVE], (
        f"a chave do override não é a que o esquema exige: {list(disco['controllers'])}")
    assert disco["controllers"][CHAVE]["leds"]["lightbar_brightness"] == pytest.approx(0.4)
    assert disco["leds"]["lightbar_brightness"] == pytest.approx(1.0), (
        "o brilho caiu na seção GLOBAL — o trilho de um controle mudou o de todos")


def test_o_que_o_disco_grava_e_o_que_a_coluna_le(pac, a04):
    """Ida e volta: o que o trilho escreve é o que `brilho_do_controle` lê.

    ESTE É O TESTE QUE A CASA PAGOU CARO POR NÃO TER. Até 03/09/2026 esta aba só
    LIA o override, e lia com a string CRUA (`dict.get(uniq)`); a escrita tem de
    canonizar, porque é o que o esquema exige. Ler numa forma e gravar noutra
    grava no `aabbcc000001` e imprime o global — para sempre, e sem uma linha de
    erro: ela arrasta, o número volta ao velho no tique seguinte, e o gesto
    parece não funcionar.

    A MORDIDA: tire o `chave_do_override` da LEITURA (volte ao
    `dict.get(uniq)`) e esta linha reprova com o brilho GLOBAL, 1.0.
    """
    arquivo = _semear("regua")
    fn = pac.gesto_da_pagina(PAGINA, "brilho")
    fn(_ctx(pac), {"uniq": UNIQ, "valor": "35", "evento": "change"}, PonteDeMentira())

    assert a04.brilho_do_controle(_do_disco(arquivo), UNIQ) == pytest.approx(0.35)
    assert a04.brilho_do_controle(_do_disco(arquivo), OUTRO) == pytest.approx(1.0), (
        "o brilho gravado num controle vazou para o vizinho")


def test_gravar_o_brilho_preserva_a_cor_propria_daquele_controle(pac):
    """Um override PARCIAL nunca apaga o que já estava lá (PERFIL-01).

    O CASO É O DA MESA DELA, medido em 03/09/2026: os overrides do
    `meu_perfil.json` são `{"lightbar": [255, 0, 0]}` e nada mais. Trocar a
    seção `leds` inteira por uma que só fala de brilho apagaria a cor que ela
    escolheu para aquele controle — e ela só descobriria no próximo replug.

    A MORDIDA: troque o `model_copy(update=…)` do ramo do override existente
    por uma `LedsConfig` só com o brilho, e a primeira asserção reprova.
    """
    arquivo = _semear("regua", overrides={CHAVE: {"lightbar": (255, 0, 0)}})
    fn = __import__("pacotes").gesto_da_pagina(PAGINA, "brilho")
    fn(_ctx(__import__("pacotes")),
       {"uniq": UNIQ, "valor": "20", "evento": "change"}, PonteDeMentira())

    leds = _do_disco(arquivo)["controllers"][CHAVE]["leds"]
    assert leds["lightbar"] == [255, 0, 0], "a cor própria do controle sumiu"
    assert leds["lightbar_brightness"] == pytest.approx(0.2)
    assert "player_leds" not in leds, (
        "a gravação DENSIFICOU o override — campo que ninguém pediu passa a "
        "vencer o global no merge por campo")


def test_arrastar_para_o_mesmo_lugar_nao_regrava(pac):
    """Voltar ao mesmo valor não troca a data do arquivo nem cria backup.

    A RAZÃO É DELA: cada `save_profile` copia o perfil para `.historico/`. Um
    arraste que sai de 40% e volta a 40% é UM gesto, não dois — e regravar por
    ele encheria o histórico dela de cópias idênticas.

    A MORDIDA: tire o `return None` do ramo "nada mudou" em
    `_com_o_brilho_gravado` e o `mtime` muda.
    """
    arquivo = pathlib.Path(_semear("regua", overrides={CHAVE: {"lightbar_brightness": 0.4}}))
    antes = arquivo.stat().st_mtime_ns
    fn = pac.gesto_da_pagina(PAGINA, "brilho")
    fn(_ctx(pac), {"uniq": UNIQ, "valor": "40", "evento": "change"}, PonteDeMentira())
    assert arquivo.stat().st_mtime_ns == antes, "regravou um perfil idêntico"


# ---------------------------------------------------------------------------
# 3. o APARELHO recebe a cor pedida com o brilho NOVO
# ---------------------------------------------------------------------------
def test_o_aparelho_recebe_a_cor_pedida_com_o_brilho_novo(pac):
    """Aplicar é a outra metade de "grava na hora" — e ela vai pelo caminho único.

    O `led.set` LEVA A COR e o `brightness`; não há um IPC de "só o brilho". É o
    mesmo que a janela GTK faz ao soltar o `GtkScale`
    (`_on_lightbar_brilho_solto` → `_aplicar_cor_no_controle`).

    A MORDIDA: passe `brilho=_DO_PERFIL` em vez do número, e o `brightness`
    chega como o do DISCO — que, com a ordem certa, é o novo; inverta a ordem
    dos dois tempos e ele chega VELHO. As duas formas reprovam aqui.
    """
    _semear("regua")
    p = PonteDeMentira()
    fn = pac.gesto_da_pagina(PAGINA, "brilho")
    fn(_ctx(pac), {"uniq": UNIQ, "valor": "50", "evento": "change"}, p)

    assert [c[0] for c in p.chamadas] == ["led_set_detalhado"], p.chamadas
    _nome, args, kwargs = p.chamadas[0]
    assert args[0] == (0, 0, 255), f"mandou {args[0]!r} — a cor mudou por um gesto de brilho"
    assert kwargs["brightness"] == pytest.approx(0.5)
    assert kwargs["uniq"] == UNIQ


def test_a_cor_pedida_sai_do_brilho_velho(pac):
    """D8: o `lightbar_rgb` do daemon é PÓS-escala. Inverter com o novo mente.

    O CASO, e ele é o que quebra: a barra está no azul do P1 a 50%, então o
    daemon publica `#00007F`. Ela arrasta para 100%. A cor PEDIDA continua sendo
    `#0000FF` — e para descobri-la é preciso desfazer a escala com o brilho
    VELHO (50%). Desfazendo com o NOVO (100%), `cor_escolhida` devolve o
    `#00007F` cru, e o gesto REPINTA a barra num azul escuro que ela nunca
    pediu — o brilho escurecendo duas vezes.

    A MORDIDA: leia o brilho depois de gravar (isto é, mova a leitura do `velho`
    para depois do `save_profile`) e esta linha reprova com `(0, 0, 127)`.
    """
    _semear("regua", overrides={CHAVE: {"lightbar_brightness": 0.5}})
    p = PonteDeMentira()
    fn = pac.gesto_da_pagina(PAGINA, "brilho")
    fn(_ctx(pac, aceso={"lightbar_rgb": [0, 0, 127]}),
       {"uniq": UNIQ, "valor": "100", "evento": "change"}, p)

    _nome, args, kwargs = p.chamadas[0]
    assert args[0] == (0, 0, 255), (
        f"mandou {args[0]!r} — a cor foi desescalada com o brilho errado")
    assert kwargs["brightness"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 4. o `click` que vem DEPOIS do `change` não é um segundo pedido
# ---------------------------------------------------------------------------
def test_o_clique_que_segue_o_change_nao_grava_de_novo(pac):
    """Um `<input type="range">` clicado na pista dispara `input`, `change` e `click`.

    O BOOTSTRAP escuta os DOIS últimos (`hefesto_vivo`, o ouvinte único), então
    sem o guarda cada clique na pista gravaria DUAS vezes no perfil dela e
    mandaria DUAS escritas ao rádio — que por Bluetooth disputa fila com os
    relatórios de input do próprio controle.

    A MORDIDA: tire o `_so_abriu_o_seletor` do gesto e esta linha reprova com
    duas chamadas.
    """
    _semear("regua")
    p = PonteDeMentira()
    fn = pac.gesto_da_pagina(PAGINA, "brilho")
    carga = {"uniq": UNIQ, "valor": "60", "tipo": "input"}
    fn(_ctx(pac), {**carga, "evento": "change"}, p)
    fn(_ctx(pac), {**carga, "evento": "click"}, p)
    assert len(p.chamadas) == 1, (
        f"o clique que segue o arraste virou um segundo pedido: {p.chamadas}")


# ---------------------------------------------------------------------------
# 5. as recusas DIZEM
# ---------------------------------------------------------------------------
def test_sem_controle_o_trilho_recusa_dizendo(pac):
    """`""` não vira "todos": um brilho sem dono mudaria a barra dos quatro."""
    fn = pac.gesto_da_pagina(PAGINA, "brilho")
    with pytest.raises(ValueError, match="qual controle"):
        fn(_ctx(pac), {"valor": "40", "evento": "change"}, PonteDeMentira())


@pytest.mark.parametrize("valor", ["", "abacaxi", "-1", "101"])
def test_valor_fora_da_faixa_recusa_dizendo(pac, valor):
    """A faixa tem dono — `LedsDraft.lightbar_brightness` é `int, ge=0, le=100`.

    A MORDIDA: digite `0 <= n <= 100` no lugar de perguntar ao esquema, e a
    régua passa a dar verde no dia em que o produto mudar a escala — que é o
    defeito que o BRIEFING desta leva nomeia seis vezes.
    """
    fn = pac.gesto_da_pagina(PAGINA, "brilho")
    with pytest.raises(ValueError, match="porcentagem"):
        fn(_ctx(pac), {"uniq": UNIQ, "valor": valor, "evento": "change"},
           PonteDeMentira())


def test_sem_perfil_ativo_recusa_dizendo_e_nao_escreve(pac):
    """O brilho é do PERFIL, não da máquina — e não há onde gravá-lo sem um."""
    p = PonteDeMentira()
    fn = pac.gesto_da_pagina(PAGINA, "brilho")
    with pytest.raises(RuntimeError, match="perfil ativo"):
        fn(_ctx(pac, perfil=""), {"uniq": UNIQ, "valor": "40", "evento": "change"}, p)
    assert not p.chamadas, "recusou e mesmo assim escreveu no aparelho"


def test_sem_cor_conhecida_o_brilho_aplica_e_a_ressalva_fica(pac):
    """Nos estados de ressalva do motor o brilho ACENDE — a cor cai para o slot.

    **ESTA RÉGUA FOI INVERTIDA EM 05/09/2026, e a razão é palavra dela.** Ela
    se chamava `test_sem_cor_conhecida_guarda_e_diz` e exigia o contrário: que o
    gesto guardasse o número no disco, NÃO escrevesse no aparelho, e devolvesse
    *"Guardei 30%. A barra não mudou agora: …"*. A decisão dela, na pergunta
    `04-Q4`, derrubou a premissa inteira:

        "O Hefesto não pode ter essa falha. Isso tem que APLICAR, não
         justificar a falha"

    Ela recusou as TRÊS opções que eu ofereci — todas eram redações da desculpa
    — e a resposta dela é a regra dela de 01/09: *"clicar na cor já deveria
    aplicar a cor no controle"*.

    O QUE A MEDIÇÃO ACHOU, e é o que torna a inversão barata: a resposta já
    estava escrita no mesmo arquivo. `_a_cor_de_agora` trata o MESMO "o motor
    não afirma a cor" e responde o contrário, com a razão por extenso — *"A
    QUEDA É A COR DO SLOT, e ela é a resposta CERTA e não um remendo"*. E a
    janela estável nunca teve o buraco: `lightbar_actions.py:830` escreve
    SEMPRE, com a cor do perfil.

    O QUE NÃO MUDOU: a ressalva continua saindo. Ela diz que o motor não afirma
    a cor, e isso continua sendo verdade — o que mudou é que a barra acendeu.
    Por isso o recado agora começa em *"Brilho em 30%"* e não em *"Guardei"*.

    A MORDIDA: faça o gesto voltar a recusar e este teste reprova por não
    acender; apague a ressalva e ele reprova por calar sobre o que o motor não
    sabe.
    """
    arquivo = _semear("regua")
    p = PonteDeMentira()
    fn = pac.gesto_da_pagina(PAGINA, "brilho")
    saiu = fn(_ctx(pac, state={"native_mode": True}),
              {"uniq": UNIQ, "valor": "30", "evento": "change"}, p)

    assert p.chamadas, (
        "o brilho não chegou ao aparelho. Se o gesto voltou a recusar quando o "
        "motor não afirma a cor, ele voltou a ser o botão que aceita o toque e "
        "não age — ver o cabeçalho desta régua."
    )
    assert isinstance(saiu, dict) and "Brilho em 30%" in saiu.get("recado", ""), (
        f"acendeu e não disse por que a cor é a do slot: {saiu!r}")
    assert _do_disco(arquivo)["controllers"][CHAVE]["leds"][
        "lightbar_brightness"] == pytest.approx(0.3), "acendeu e NÃO guardou"


def test_controle_fora_da_mesa_recusa_dizendo(pac):
    """Sem aparelho ligado não há barra em que aplicar — e não se grava às cegas.

    A FRASE MUDOU EM 06/09/2026 (A-PALAVRA-MESA-SAI-01), e o `match` foi junto:
    o recado dizia *"este controle não está na mesa agora"*, e a palavra saiu da
    tela por ordem dela. O nome deste teste fica: `mesa` é a palavra da casa.
    """
    _semear("regua")
    p = PonteDeMentira()
    fn = pac.gesto_da_pagina(PAGINA, "brilho")
    with pytest.raises(RuntimeError, match="não está ligado agora"):
        fn(_ctx(pac), {"uniq": OUTRO, "valor": "40", "evento": "change"}, p)
    assert not p.chamadas


# ---------------------------------------------------------------------------
# 6. uma régua não arrasta o brilho dela para provar que sabe clicar
# ---------------------------------------------------------------------------
def test_o_trilho_e_perigoso_para_a_prova_automatica():
    """Ele grava no perfil ATIVO, sem perguntar — como o `salvar` e o `guardar`.

    ELA ESCOLHEU A COMBINAÇÃO: o trilho LIGA *e* o gesto entra em `PERIGOSOS`.
    As duas metades são uma decisão só — a prova botão a botão roda aba por aba
    e arrastaria este trilho para o valor da tela, copiando por cima do brilho
    que ela escolheu, com backup novo em `.historico/`.

    A MORDIDA: tire a linha de `PERIGOSOS` e a prova automática passa a escrever
    no perfil dela a cada volta.
    """
    from hefesto_dualsense4unix.interface import hefesto_vivo

    assert (PAGINA, "brilho") in hefesto_vivo.PERIGOSOS
