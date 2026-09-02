#!/usr/bin/env python3
"""O pacote da aba `03` Gatilhos — e ele nasceu ERRADO, corrigido em 01/09/2026.

O QUE ESTAVA ESCRITO AQUI, e era meu, e estava errado:

    "o modo escolhido      NÃO EXISTE no state    ← sem dono
     o efeito pronto       NÃO EXISTE no state    ← sem dono
     os ajustes do modo    NÃO EXISTEM no state   ← sem dono"

A parte factual continua verdadeira: o `state_full` do daemon **não** publica
`triggers`, e o DualSense não devolve o modo em que está — gatilho adaptativo é
comando de ida. O que estava errado era a CONCLUSÃO: dali eu tirei "não tem
dono" e pintei quatro travessões.

ELA PEGOU COM UMA PERGUNTA SÓ: *"vc tá corrigindo na origem esses problemas que
tá relatando né?"* Não estava. O dado tem dono, e são dois, os dois já no
produto que ela usa:

    profiles/schema.py       `triggers.left/right` → `mode` e `params`
    app/actions/trigger_specs.py   `PRESETS`: `name` (disco) → `label` (tela)
                                   e cada `param` com nome, faixa e padrão

MEDIDO NO DISCO DELA, perfil "Ação", em 01/09/2026::

    triggers.left  = {"mode": "Rigid",     "params": [0, 180]}
    triggers.right = {"mode": "Vibration", "params": [3, 8, 20]}

Cinco dos 33 perfis dela têm gatilho configurado. Mostrar `—` ali era apagar da
tela uma escolha que ela salvou.

O QUE AINDA NÃO TEM DONO, e agora a lista é honesta: nada desta aba. O que muda
é a NATUREZA do valor — ele é o que está **salvo no perfil**, não o que está
**aceso no plástico**, e essas são coisas diferentes. Como o aparelho não
devolve a segunda, a primeira é a melhor verdade disponível, e a tela diz de
qual está falando.
"""
from __future__ import annotations

import re
from typing import Any

from . import Contexto, perfil, registrar

#: Nada. E a lista vazia é uma AFIRMAÇÃO, não um esquecimento: cada valor desta
#: aba tem dono medido, e a régua de cobertura conta este zero junto com os
#: `pintados` — um pacote que pinta 0 e declara 0 é reprovado por
#: `test_o_despachante_serve_as_dez.py`, de propósito.
SEM_DONO: dict[str, str] = {}

#: O LADO NA TELA E O LADO NO DISCO. A tela usa `e`/`d` (o L2 e o R2 do
#: desenho); o perfil usa `left`/`right`. Dois vocabulários, uma tradução, num
#: lugar só — a regra da casa é que o que tem dono não se digita.
LADOS = {"e": "left", "d": "right"}

#: O TRAVESSÃO É DO PILOTO, e está aqui só para a régua poder cobrá-lo sem
#: repetir a string: `hefesto_vivo.escrever()` troca `''` por `—` antes de
#: escrever. Emitir `''` é dizer "esta casa não tem valor"; emitir `'—'` seria
#: esta aba inventando a marca de vazio de outra camada.
VAZIO = ""


# ---------------------------------------------------------------------------
# O QUE A PÁGINA TEM, LIDO DA PÁGINA — e é a cura do defeito D3.
#
# O DEFEITO, medido em 02/09/2026 com o perfil `meu_perfil` (`L2: mode='Off'
# params=[]`, `R2: idem`) e a foto da aba aberta: a tela mostrava, na coluna do
# P1, `Força 7 · Frequência 4 · Início do curso 25 · Fim do curso 230` — e, três
# linhas acima, `Modo: Desligado`. Os quatro números eram do MOCKUP.
#
# A CAUSA NÃO É "o pacote não pinta os ajustes": ele pinta, e a régua
# `test_o_perfil_chega_na_tela.py` prova que com `Rigid` no disco os valores
# dela chegam. A causa é que ele pintava **só as casas que o modo tem**. Com
# `Off` são ZERO casas, o laço não roda nenhuma volta, e as quatro barras que o
# desenho deixou na página nunca são endereçadas — ficam com o que o gerador
# escreveu. *Um endereço que ninguém escreve continua mostrando o desenho*, e é
# assim que um mockup passa por produto.
#
# A CURA É ENDEREÇAR A CASA VAZIA. Quantas casas existem não se digita: elas
# estão na página publicada, que é o que o `WebView` renderiza. Digitar `4` e
# `2` aqui criaria a segunda cópia de um número que o gerador já decide —
# e ela envelheceria calada no dia em que o desenho mudasse.
# ---------------------------------------------------------------------------
PAGINA = "03-gatilhos.html"

_CASA = re.compile(r'data-campo="aj-nome-(?P<lado>[ed])-(?P<i>\d+)"')
#: A barra de preenchimento e o alvo com que o piloto a pinta. `data-hef-alvo`
#: pode vir antes ou depois do `data-campo` no elemento — a régua olha os dois
#: sentidos porque o gerador é livre para escrever na ordem que quiser.
_BARRA = re.compile(
    r'<span[^>]*data-campo="aj-pct-[ed]-\d+"[^>]*>|<span[^>]*data-campo="aj-pct-[ed]-\d+"[^>]*/?>')

#: O LUGAR QUE O DESENHO JÁ DÁ POR VAZIO. `data-controle` e `data-conectado`
#: saem no MESMO elemento, nesta ordem, e o `[^>]*` atravessa a quebra de linha
#: que o gerador põe entre os dois atributos.
_LUGAR_VAZIO = re.compile(r'data-controle="(p\d+)"[^>]*data-conectado="nao"')

_LIDO: tuple[dict[str, int], bool] | None = None
_ENDERECOS: frozenset[str] | None = None
_VAZIOS: frozenset[str] | None = None


def _pagina_publicada() -> str:
    """O HTML que o produto renderiza AGORA, ou `''` se não der para ler.

    `publicado=True` É DELIBERADO, e é a exceção que o `onde.pagina` prevê: o
    padrão daquele módulo é a BANCADA, porque todo instrumento desta casa mede o
    desenho de hoje. Aqui não — quem pinta pinta no que está no `WebView`, e
    contar as casas da bancada faria o pacote endereçar barras que a página
    publicada ainda não tem.
    """
    from hefesto_dualsense4unix.interface import onde

    try:
        return onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")
    except OSError:
        return ""


def _casas_e_barras() -> tuple[dict[str, int], bool]:
    """`({"e": N, "d": M}, a barra aceita largura?)` — lido da página publicada.

    `N` é quantas casas de ajuste o desenho reservou naquele lado, contando a
    coluna que tem mais: endereçar uma casa que uma coluna não tem é um
    `querySelector` que não acha nada — inofensivo —, enquanto DEIXAR de
    endereçar uma que existe é o defeito D3 de volta.

    O SEGUNDO VALOR ERA UM DEFEITO DECLARADO, **e ele FECHOU**. `escrever()` do
    piloto só põe LARGURA em quem declara `data-hef-alvo="largura"`; sem isso o
    alvo é `texto`, e a pintura escreve o número DENTRO da barra em vez de
    encompridá-la. O gerador ganhou o atributo, ela publicou (`70b58116`), e a
    medição de 02/09/2026 na página publicada é a de agora:

        11 barras `aj-pct-*`, 11 com `data-hef-alvo="largura"`  → devolve True
        16 `<select>`, 16 com `data-hef-alvo="valor"`

    FATO SUBSTITUÍDO: esta docstring dizia *"nenhuma das 11 barras declara
    `largura`"*, e era verdade no dia em que foi escrita — antes da publicação.
    Guardá-la ao lado do número certo obrigaria a próxima pessoa a escolher
    entre duas afirmações.

    O `False` continua possível e continua querendo dizer a mesma coisa —
    gerador esperando a publicação dela, não pacote incompleto —, e é por isso
    que esta função LÊ em vez de digitar `True`.
    """
    global _LIDO
    if _LIDO is None:
        texto = _pagina_publicada()
        casas = {"e": 0, "d": 0}
        for m in _CASA.finditer(texto):
            lado, i = m.group("lado"), int(m.group("i"))
            casas[lado] = max(casas[lado], i + 1)
        barras = _BARRA.findall(texto)
        largura = bool(barras) and all('data-hef-alvo="largura"' in b for b in barras)
        _LIDO = (casas, largura)
    return _LIDO


def _enderecos_da_pagina() -> frozenset[str]:
    """Todo `data-campo` que a página publicada tem. Vazio se ela não abrir.

    É com ele que a `cobertura` para de contar pintura no vazio. Um conjunto
    VAZIO faz a contagem cair a zero, e a régua do despachante reprova um
    pacote que pinta 0 — o que é o desfecho certo se a página sumir do wheel.
    """
    global _ENDERECOS
    if _ENDERECOS is None:
        _ENDERECOS = frozenset(re.findall(r'data-campo="([^"]+)"', _pagina_publicada()))
    return _ENDERECOS


def _lugares_que_o_desenho_da_por_vazios() -> frozenset[str]:
    """Os `pref` que a página publicada já marca `data-conectado="nao"`.

    POR QUE O PACOTE PRECISA SABER DISSO, e é o defeito D4, medido em
    02/09/2026: os quatro `<select>` das colunas P3 e P4 são **endereço morto**.
    O piloto preenche todo lugar que a mesa não tem com `dict.fromkeys(chaves,
    "—")` (`hefesto_vivo.py:1006-1016`), e `escrever()` **recusa** escrever um
    valor que o `<select>` não oferece (`hefesto_vivo.py:145-151`) — a recusa é
    CERTA, porque escrever qualquer outra coisa deixaria o campo em branco
    somando +1 por tique para sempre. O desfecho é que o travessão nunca pousa e
    a coluna vazia continua mostrando o que o gerador escreveu.

    Enquanto o valor cravado é `Off`/`custom`, isso passa por inofensivo. **Ele
    não é**: o dia em que um controle sai do P3 com `Rígido` aplicado, o
    `Rígido` FICA na tela — a coluna de um lugar sem aparelho afirmando um
    efeito. É a nona aparição do defeito que esta casa nomeia, *a tela afirmando
    o que não é*, e a única cura é o pacote escrever ali um valor que o
    `<select>` aceite.

    POR QUE SÓ OS LUGARES QUE O DESENHO JÁ DÁ POR VAZIOS, e não todo lugar
    vazio: quem emite uma coluna SAI da conta `TODOS_OS_LUGARES - vivos` do
    piloto, e com ela perde o `data-conectado="nao"` que o piloto escreveria —
    que é o que segura o `pointer-events:none` do lugar vazio. Nas colunas que a
    página já dá por vazias isso não custa nada (a marca está no arquivo); numa
    que a página dá por conectada — o P2 com um controle só na mesa — custaria a
    trava. O acoplamento é do piloto (ele deduz "vazio" de "quem não emitiu", em
    vez de perguntar à mesa) e a cura é lá; aqui fica a metade que não regride.
    """
    global _VAZIOS
    if _VAZIOS is None:
        _VAZIOS = frozenset(_LUGAR_VAZIO.findall(_pagina_publicada()))
    return _VAZIOS


def _specs() -> Any:
    """A tabela de presets do produto, ou `None` se o `src/` não abrir.

    `None` NÃO vira travessão silencioso: sem a tabela, o pacote não sabe
    traduzir `Rigid` para `Rígido` nem nomear os ajustes, e devolver rótulos
    crus seria pior que devolver nada. Quem chama trata.
    """
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions import trigger_specs

        return trigger_specs
    except Exception:
        return None


def _prontos() -> Any:
    """As curvas prontas do produto (`profiles/trigger_presets.py`), ou `None`.

    São as MESMAS cinco que o desenho oferece em "Efeito pronto" — a tela não as
    inventou: `FEEDBACK_POSITION_LABELS` traz "Rampa crescente", "Rampa
    decrescente", "Plateau central", "Stop hard" e "Stop macio", letra por letra,
    e cada uma resolve para dez intensidades de 0 a 8.
    """
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.profiles import trigger_presets

        return trigger_presets
    except Exception:
        return None


#: O MODO QUE UMA CURVA PRONTA É. Uma curva de dez posições só existe como
#: `MultiPositionFeedback` — é o único modo cujos ajustes são `pos_0..pos_9`
#: (`app/actions/trigger_specs.py`), e é o que a GUI estável exige para sequer
#: MOSTRAR a linha de preset (`triggers_actions._update_preset_row_visibility`,
#: que a esconde nos outros 17 modos).
MODO_DA_CURVA = "MultiPositionFeedback"


def _pronto_da_curva(nome: str, curva: list[int]) -> str:
    """Qual efeito pronto é aquela curva salva, ou `custom` se não for nenhum.

    O DISCO NÃO GUARDA QUAL PRESET FOI ESCOLHIDO — guarda as dez intensidades.
    Então a chave se RECONHECE, comparando com a tabela do produto; ela não se
    adivinha e não se digita. Sem isto a tela mostraria "— Nenhum —" para uma
    curva que é exatamente a "Stop hard" que ela escolheu.

    `custom` é o token do próprio produto para "nenhuma pronta"
    (`FEEDBACK_POSITION_LABELS["custom"]`), e é o `value` que a opção
    "— Nenhum —" carrega no desenho — a tela e o disco falam a mesma palavra.
    """
    tp = _prontos()
    if tp is None or nome != MODO_DA_CURVA or len(curva) != 10:
        return "custom"
    for chave, valores in tp.FEEDBACK_POSITION_PRESETS.items():
        if list(valores) == list(curva):
            return str(chave)
    return "custom"


def _do_lado(cfg: dict[str, Any], specs: Any, casas: int = 0) -> dict[str, Any]:
    """Um lado do gatilho, do perfil para a tela.

    `cfg` é o `{"mode": "Rigid", "params": [0, 180]}` do disco. Sai o rótulo em
    português, o nome de cada ajuste e o valor que ela salvou — que é o que as
    três linhas da aba mostram: Modo, Efeito pronto e Ajustes.

    `casas` é quantas barras o DESENHO reservou naquele lado, e serve a uma
    coisa só: as que o modo não usa saem VAZIAS em vez de não saírem. Um modo
    de zero ajustes com quatro barras na tela é o defeito D3 — a tela dizia
    `Desligado` no campo de cima e `Força 7` três linhas abaixo.
    """
    nome = str((cfg or {}).get("mode") or "Off")
    valores = list((cfg or {}).get("params") or [])
    spec = specs.get_spec(nome) if specs else None

    fora: dict[str, object] = {
        "modo": spec.label if spec else nome,
        # O `name` cru viaja junto: é o contrato de disco, e é por ele que a
        # tela sabe qual botão acender sem depender do texto traduzido.
        "modo-chave": nome,
        # O `pronto` É A CHAVE, e não o rótulo — 01/09/2026. Ele é pintado no
        # `<select class="pronto">` por `data-hef-alvo="valor"`, e `select.value`
        # casa com o `value` da opção, que carrega a chave do produto
        # (`rampa_crescente`, `stop_hard`…). Um rótulo aqui não casaria com opção
        # nenhuma e o campo nasceria em branco.
        "pronto": "custom",
        "ajustes": [],
    }
    # O NOME PRÓPRIO PELA MESMA RAZÃO DA CURVA ACIMA: reler
    # `fora["ajustes"]` devolve `object`, que não tem `.append`. A lista tem
    # um nome e um tipo, e o dicionário guarda ELA — as duas apontam para o
    # mesmo objeto, então o que se acrescenta aqui sai lá.
    ajustes: list[dict[str, Any]] = []
    fora["ajustes"] = ajustes

    def encher() -> None:
        """As casas que o modo não usa saem VAZIAS — nunca não saem.

        `pct` fica `0` e não vazio: a barra é largura, e largura vazia vira
        `width:—%`, que o navegador ignora — a barra ficaria com a do mockup. O
        zero é a única largura que quer dizer "não há valor aqui".
        """
        while len(ajustes) < casas:
            ajustes.append({"nome": VAZIO, "valor": VAZIO, "pct": 0,
                            "min": 0, "max": 0, "vazia": True})

    if spec is None:
        encher()
        return fora

    #: A CURVA, e ela é a segunda forma que o disco guarda. Medido nos 33
    #: perfis dela em 01/09/2026: `Rigid` grava `[0, 180]` — um escalar por
    #: ajuste — mas `MultiPositionFeedback` e `MultiPositionVibration` gravam
    #: `[[1], [2], ..., [8]]`, dez posições do curso, cada uma numa lista de um.
    #:
    #: São DOIS controles de tela diferentes: o primeiro é um punhado de
    #: sliders com nome, o segundo é o desenho de dez barrinhas que a aba chama
    #: de "Curva de força" e "Vibração por posição". Tratar os dois pela mesma
    #: conta foi o que quebrou este pacote na primeira execução — `[1] - 0`
    #: não é uma subtração que exista.
    if any(isinstance(v, list) for v in valores):
        # O NOME PRÓPRIO, e não `fora["curva"]` relido três vezes: o `fora` é
        # um `dict[str, Any]`, e cada releitura devolvia `object` — o que o
        # `mypy` recusava iterar, indexar e passar adiante. A lista tem um
        # nome e um tipo, e as três linhas seguintes falam com ela.
        curva_da_tela: list[int] = [
            int(v[0]) if isinstance(v, list) and v else int(v or 0)
            for v in valores]
        fora["curva"] = curva_da_tela
        # A escala da curva é 0..8, a mesma dos `_RAMPA_PADRAO` do produto.
        fora["curva-pct"] = [round(max(0, min(100, x / 8 * 100)))
                             for x in curva_da_tela]
        fora["pronto"] = _pronto_da_curva(nome, curva_da_tela)
        # A CURVA NÃO OCUPA AS BARRAS DE AJUSTE — ela tem desenho próprio
        # (`curva-<lado>`), e a página publicada ainda não o tem. As barras que
        # o desenho reservou continuam existindo, então continuam tendo de sair
        # vazias: sem isto, escolher "Curva de força" deixaria os quatro
        # números do mockup na tela ao lado de uma curva de dez posições.
        encher()
        return fora

    #: O EFEITO PRONTO NÃO É O MODO — corrigido em 01/09/2026. Estava escrito
    #: aqui que *"até existir um segundo eixo, o pronto É o modo"*, e o campo
    #: recebia `spec.label`. O segundo eixo EXISTE, e existia antes desta aba:
    #: `profiles/trigger_presets.py` guarda as cinco curvas que o desenho
    #: oferece, com os mesmos cinco nomes. O que elas preenchem são as dez
    #: posições do `MultiPositionFeedback` — logo, nos outros 18 modos não há
    #: pronto nenhum, e o honesto é `custom` ("— Nenhum —"), que já é o padrão
    #: lá em cima. Repetir o nome do modo aqui era dizer duas vezes a mesma
    #: escolha em duas linhas que a tela apresenta como diferentes.

    for i, p in enumerate(spec.params):
        valor = valores[i] if i < len(valores) else p.default
        largura = max(1, p.max_value - p.min_value)
        ajustes.append({
            "nome": p.label,
            "valor": valor,
            # A PORCENTAGEM É DA FAIXA DAQUELE AJUSTE, não de 0..255. Um
            # `force` vai de 0 a 255 e uma `position` de 0 a 9; dividir os dois
            # pela mesma escala pintaria a barra da posição sempre no chão.
            "pct": round(max(0, min(100, (valor - p.min_value) / largura * 100))),
            "min": p.min_value, "max": p.max_value,
        })
    # E AS QUE SOBRAM DA TELA SAEM VAZIAS. É esta linha que mata o D3: o
    # `Off` tem spec (não cai no ramo de cima) e tem ZERO parâmetros, então o
    # laço acima não roda nenhuma volta — sem ela, as quatro barras do desenho
    # ficam com `Força 7 · Frequência 4 · Início do curso 25 · Fim do curso 230`
    # debaixo de um campo que diz `Desligado`.
    encher()
    return fora


@registrar("03-gatilhos.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    """Endereço → valor, por controle da mesa.

    O gatilho é do PERFIL, e o perfil é um só para a mesa inteira — logo as
    colunas recebem o mesmo modo. Isso não é preguiça: o `ControllerOverrides`
    do schema permite gatilho por controle, e quando ele estiver preenchido esta
    função lê o override antes do perfil. Enquanto não estiver, repetir o valor
    é o que corresponde ao que o produto faz.

    A COBERTURA CONTA O QUE A PÁGINA RECEBE, e não o que este dicionário tem —
    mudado em 02/09/2026. Medido com a mesa dela (dois controles, `meu_perfil`,
    gatilho `Off` nos dois lados): o pacote devolvia **20 chaves por tique** e o
    piloto escrevia **8 valores**. As doze restantes são endereços que a página
    publicada não tem — `l2-raw`, `l2-pct`, `r2-raw`, `r2-pct` e o rótulo
    `modo-e`/`modo-d` (o campo de escolha casa pelo `value`, que é a CHAVE; o
    rótulo continua saindo porque `test_o_perfil_chega_na_tela.py:133` o cobra,
    mas nenhum elemento o lê). Contar as doze era esta aba dando-se nota por
    escrever no vazio — a mesma forma do "77%" que a medição de 02/09 derrubou.
    """
    specs = _specs()
    p = perfil.ativo(ctx.state.get("active_profile"))
    trig = (p.get("triggers") or {}) if p else {}
    overrides = (p.get("controllers") or {}) if p else {}
    casas, barra_por_largura = _casas_e_barras()
    tem_endereco = _enderecos_da_pagina()

    lados = {sig: _do_lado(trig.get(disco) or {}, specs, casas.get(sig, 0))
             for sig, disco in LADOS.items()}

    colunas: dict[str, dict[str, Any]] = {}
    pintados = 0
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        entradas = c.get("inputs") or {}
        l2, r2 = entradas.get("l2_raw"), entradas.get("r2_raw")

        #: O OVERRIDE POR CONTROLE VENCE O PERFIL, e é o que o produto faz —
        #: `ControllerOverrides.triggers` existe no schema desde antes desta aba.
        meu = overrides.get(uniq) or {}
        seus = (meu.get("triggers") or {}) if isinstance(meu, dict) else {}
        deste = {sig: (_do_lado(seus[disco], specs, casas.get(sig, 0))
                       if seus.get(disco) else lados[sig])
                 for sig, disco in LADOS.items()}

        col: dict[str, object] = {
            "l2-raw": l2, "r2-raw": r2,
            "l2-pct": round((l2 or 0) / 255 * 100),
            "r2-pct": round((r2 or 0) / 255 * 100),
        }
        for sig, d in deste.items():
            col[f"modo-{sig}"] = d["modo"]
            col[f"modo-chave-{sig}"] = d["modo-chave"]
            col[f"pronto-{sig}"] = d["pronto"]
            for i, aj in enumerate(d["ajustes"]):
                col[f"aj-nome-{sig}-{i}"] = aj["nome"]
                col[f"aj-val-{sig}-{i}"] = aj["valor"]
                col[f"aj-pct-{sig}-{i}"] = aj["pct"]
            # A CURVA VAI JUNTO, e ela precisa entrar na CONTAGEM: sem estas
            # duas linhas o perfil "Aventura" — que é curva nos dois lados —
            # pintava 10 valores enquanto o "Ação" pintava 25, e a cobertura
            # diria que a aba está meio ligada quando ela está inteira.
            if d.get("curva"):
                col[f"curva-{sig}"] = d["curva"]
                col[f"curva-pct-{sig}"] = d["curva-pct"]
        colunas[uniq] = col
        pintados += sum(1 for k in col if k in tem_endereco)

    # O LUGAR VAZIO TAMBÉM É ESCRITO — a cura do D4, ver
    # `_lugares_que_o_desenho_da_por_vazios`. A chave é o `pref` cru: o
    # `pacotes.normalizar` traduz `uniq → pref` quando conhece a tradução e
    # deixa passar o que já é `pref` (`pacotes/__init__.py:423`).
    #
    # O VALOR NÃO SE DIGITA: um lugar sem aparelho é um lugar sem configuração
    # de gatilho, e `_do_lado({}, …)` é exatamente isso — a mesma função que
    # traduz o perfil, com o perfil vazio. Sai `modo-chave='Off'` (o
    # "Desligado" que o `<select>` oferece) e `pronto='custom'` (o "— Nenhum —"),
    # que são os dois únicos valores desta coluna que querem dizer *não há
    # efeito aqui*.
    #
    # SÓ OS DOIS CAMPOS POR LADO, e não as barras de ajuste: medido na página
    # publicada de 02/09/2026, a coluna vazia não tem `aj-*` nenhum — ela traz
    # "Este modo não tem o que ajustar." no lugar. Emitir `aj-val-e-0` ali seria
    # o pacote dando-se nota por escrever no vazio, que é o que a `cobertura`
    # desta aba passou a recusar.
    ocupados = {str(m.get("pref") or "") for m in ctx.mesa}
    sem_ninguem = _do_lado({}, specs, 0)
    for pref in sorted(_lugares_que_o_desenho_da_por_vazios() - ocupados):
        vazia = {f"modo-chave-{sig}": sem_ninguem["modo-chave"] for sig in LADOS}
        vazia.update({f"pronto-{sig}": sem_ninguem["pronto"] for sig in LADOS})
        colunas[pref] = vazia
        pintados += sum(1 for k in vazia if k in tem_endereco)

    return {
        "colunas": colunas,
        "perfil": ctx.state.get("active_profile") or "",
        "sem_dono": {},
        "cobertura": {"pintados": pintados, "sem_dono": len(SEM_DONO),
                      # O QUE SAI E NÃO TEM ONDE POUSAR, dito em voz alta. Não é
                      # erro — `modo-e` tem régua que o cobra — mas contá-lo como
                      # pintura era a aba dando-se nota por escrever no vazio.
                      "sem_endereco": sum(1 for col in colunas.values()
                                          for k in col if k not in tem_endereco),
                      # A barra de preenchimento chega ao produto? Ver
                      # `_casas_e_barras`. `False` aqui é trabalho de gerador
                      # esperando a publicação dela, não pacote incompleto.
                      "barra_por_largura": barra_por_largura},
    }


# ---------------------------------------------------------------------------
# OS GESTOS — o clique dela chegando ao gatilho. Ver o exemplo comentado em
# `a04_iluminacao.py`; o que é PRÓPRIO desta aba está escrito aqui.
#
# NADA SE REESCREVE: o `p` é a `pacotes/ponte.py`, que expõe o
# `app/ipc_bridge.py` — a mesma camada que a aba Gatilhos da GUI estável usa
# (`app/actions/triggers_actions.py:622` e `:701`). O payload, o timeout e a
# tradução da recusa já estão lá.
# ---------------------------------------------------------------------------
from . import gesto  # noqa: E402


def _uniq(o: dict[str, Any]) -> str:
    """O `uniq` da coluna onde ela clicou. Vazio = recusa, nunca "todos".

    ESTA ABA TEM UMA COLUNA POR CONTROLE, e o alcance é a diferença entre um
    ajuste e um estrago: o `trigger.reset` sem `uniq` vai em BROADCAST e zera o
    gatilho dos quatro. Foi o defeito ABAS-06 (25/07), descrito no próprio
    `ipc_bridge.trigger_reset_detalhado`: *"com 'Controle 2' selecionado,
    'Desligar' zerava o gatilho dos QUATRO"*. Aqui ele não pode voltar.
    """
    return str(o.get("uniq") or "")


def _exigir_controle(o: dict[str, Any], gesto_: str) -> str:
    """O `uniq` da coluna, ou uma recusa que DIZ QUAL é o caso. Nunca inventa.

    SÃO DOIS CASOS, e tratá-los pela mesma frase foi um defeito medido em
    02/09/2026. O `hefesto_vivo._gesto` resolve `uniq` percorrendo a mesa por
    `pref`; um clique numa coluna VAZIA não acha nada e chega aqui igualzinho a
    um clique que não trouxe controle nenhum. A frase única — *"o clique não
    disse em qual controle"* — culpa o instrumento quando quem está errado é a
    tela: a página publicada deixa os quatro `<select>` e o "Guardar esse
    efeito" das colunas P3 e P4 CLICÁVEIS, com `data-conectado="nao"` ao lado.

    Fotografado no mesmo dia: as colunas P3 e P4 dizem `Desconectado` no
    cabeçalho e mostram `Desligado` · `— Nenhum —` em campos que abrem. A cura
    de forma é o `disabled` no gerador (`aba03.py`), e publicá-la é ato dela;
    a cura de FUNDO é esta — o gesto recusa, e a frase vai para a tela.
    """
    uniq = _uniq(o)
    if uniq:
        return uniq
    lugar = str(o.get("controle") or "").strip()
    if lugar:
        raise RuntimeError(
            f"{gesto_}: não há controle no lugar {lugar.upper()} — esta coluna "
            f"está vazia. Um gatilho é de um aparelho; sem aparelho não há onde "
            f"aplicar. Ligue um controle neste lugar e ele pega o efeito.")
    raise ValueError(f"{gesto_}: o clique não disse em qual controle")


def _lado(o: dict[str, Any]) -> str:
    """`e`/`d` da tela → `left`/`right` do daemon, pela tradução que já existe.

    O `LADOS` lá em cima é o dono dessa tradução e serve a pintura desde que
    esta aba nasceu — o gesto usa o mesmo, e não uma segunda cópia.
    """
    sigla = str(o.get("lado") or "").strip()
    if sigla not in LADOS:
        raise ValueError(
            f"o clique não disse qual gatilho (veio {sigla!r}; espero 'e' ou 'd'). "
            f"É o `data-lado` do campo de escolha.")
    return LADOS[sigla]


def _escolhido(o: dict[str, Any]) -> str:
    """O que ela escolheu no campo, sem inventar nada quando não veio.

    DUAS CHAVES, E AS DUAS SÃO REAIS. `modo`/`v` é o `data-modo`/`data-v` que o
    ouvinte de clique do piloto manda hoje (`hefesto_vivo.py:203-207`). `valor` é
    o que um `<select>` mandava no piloto ANTERIOR desta casa —
    `sistema_viva.py:336`: `b.addEventListener('change', ()=>manda({gesto:nome,
    valor:b.value}))`. O piloto único não trouxe esse ramo, e é por isso que os
    campos de escolha desta aba ainda não entregam a escolha (está no relato).
    Aceitar as duas é o que faz o gesto funcionar no dia em que ele voltar, sem
    ninguém ter de lembrar de mexer aqui.
    """
    return str(o.get("modo") or o.get("v") or o.get("valor") or "").strip()


def _desfecho(resposta: Any) -> tuple[bool, str]:
    """`(ok, motivo)` de uma resposta da ponte, que tem TRÊS formas.

    `trigger_set` devolve `bool`, `trigger_set_checked` devolve `(ok, motivo)` e
    `trigger_set_detalhado` devolve `(ok, motivo, corpo)`. Normalizar aqui é o
    que permite o gesto RECUSAR DIZENDO sem depender de qual das três a ponte
    entregou — e um `ok, motivo = ...` rígido rebentaria com um `TypeError` na
    primeira troca de porta, que é erro sobre erro.
    """
    if isinstance(resposta, tuple):
        motivo = resposta[1] if len(resposta) > 1 else ""
        return bool(resposta[0]), str(motivo or "")
    return bool(resposta), ""


def _na_lingua_da_tela(motivo: str, modo: str) -> str:
    """A recusa do daemon na língua dos rótulos desta aba. Sem dono novo.

    O TRADUTOR JÁ EXISTIA E NINGUÉM O CHAMAVA. `triggers_actions.
    humanizar_erro_gatilho` (`app/actions/triggers_actions.py:53`) é a HARM-19,
    escrita e testada para a aba Gatilhos da GUI estável: o daemon fala a língua
    do `core/trigger_effects` — *"end (3) deve ser > start (5)"* — e ela devolve
    *"Fim (3) precisa ser maior que Início (5)"*, com os MESMOS rótulos que o
    `<select>` desta tela mostra, porque tira os dois do mesmo `spec.params`.
    Conferido em 02/09/2026: zero pacotes da interface nova a chamavam, e a
    recusa chegava CRUA à tela dela.

    O `_rotulo_do_param` (`:45`) FICA PRIVADO, e é decisão escrita: quem precisa
    dele é esta função, que já o usa por dentro. Torná-lo público criaria uma
    segunda porta para a mesma tradução — e a próxima pessoa teria de escolher
    entre duas, que é o defeito que a regra do dono único existe para matar.

    O MOTIVO CRU VOLTA INTEIRO quando não há tradução, e é deliberado: o
    `humanizar_erro_gatilho` devolve `None` para todo formato que não conhece
    (*"aí o chamador mostra o texto cru do daemon, que ainda diz mais que
    'daemon offline?'"*, palavras do próprio docstring dele). Calar aqui seria
    trocar uma frase feia por nenhuma.

    E ELE NÃO PODE DERRUBAR O GESTO. O módulo do tradutor importa `Gtk` no topo;
    numa árvore sem PyGObject o import levanta, e um `except` que virasse erro
    faria a interface recusar um clique VÁLIDO por causa da tradução da recusa.
    """
    if not motivo:
        return motivo
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions.triggers_actions import (
            humanizar_erro_gatilho,
        )
    except Exception:
        return motivo
    specs = _specs()
    spec = specs.get_spec(modo) if specs else None
    return humanizar_erro_gatilho(motivo, spec) or motivo


def _padroes(nome: str) -> list[int]:
    """Os ajustes PADRÃO daquele modo, na ordem em que o daemon os lê.

    NÃO SE DIGITA NENHUM NÚMERO. `preset_to_positional_params(spec, {})` devolve
    `[p.default for p in spec.params]`, que é a mesma lista que a GUI estável
    monta nos sliders ao trocar de modo (`triggers_actions._rebuild_params` →
    `_apply_trigger`), e a mesma ordem que `_persist_params_to_draft` grava —
    *"usa SEMPRE a lista posicional plana na ordem do spec"*.

    E ELA JÁ É O FORMATO DO FIO PARA OS TRÊS MODOS "ESPECIAIS", conferido contra
    `triggers_actions._send_trigger_named`: `MultiPositionFeedback` tem
    `pos_0..pos_9` (= `strengths`), `MultiPositionVibration` tem
    `frequency, pos_0..pos_9` (= `[freq, *strengths]`) e `Custom` tem
    `mode, force_0..force_6` (= `[mode, *forces]`). Os três casos que aquela
    função trata à mão saem prontos daqui — não há caso especial a reescrever.
    """
    specs = _specs()
    if specs is None:
        raise RuntimeError(
            "modo: não consegui abrir `app/actions/trigger_specs.py`, e sem ele "
            "não sei quais ajustes este modo tem. Mandar `params` vazio faria o "
            "daemon aplicar um efeito sem zona ativa — o gatilho ficaria solto e "
            "a tela diria que aplicou.")
    spec = specs.get_spec(nome)
    if spec is None:
        raise ValueError(
            f"modo: {nome!r} não é um dos 19 modos do produto "
            f"(`app/actions/trigger_specs.PRESETS`).")
    return list(specs.preset_to_positional_params(spec, {}))


def _curva(chave: str) -> list[int]:
    """As dez intensidades daquele efeito pronto, lidas do produto."""
    tp = _prontos()
    if tp is None:
        raise RuntimeError(
            "efeito pronto: não consegui abrir `profiles/trigger_presets.py`.")
    valores = tp.resolve_feedback_preset(chave)
    if not valores:
        raise ValueError(
            f"efeito pronto: {chave!r} não é uma curva do produto "
            f"(`profiles/trigger_presets.FEEDBACK_POSITION_PRESETS`).")
    return list(valores)


@gesto("03-gatilhos.html", "modo")
def modo(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Escolher um modo APLICA o efeito naquele gatilho, naquele controle.

    É O QUE O PRÓPRIO DESENHO PROMETE, na dica do quadro: *"Escolher um modo já
    manda o efeito para aquele controle, e quem está com ele na mão sente na
    hora"* — e *"soltar já manda"*. É também a decisão dela de 01/09 para a
    interface inteira: o gesto age na hora, e não junta rascunho.

    E É O QUE A GUI ESTÁVEL FAZ. `triggers_actions._on_mode_changed` remonta os
    ajustes nos padrões do modo (`_rebuild_params`) e agenda o live-preview de
    300 ms, que chama `_apply_trigger` com esses mesmos padrões. Aqui não há
    debounce a fazer: o clique é um, não um arrastar de slider.

    "DESLIGADO" É `trigger.reset`, E NÃO `trigger.set` COM `Off` — e esta é a
    parte que não se adivinha pelo nome. O `_handle_trigger_set` do daemon
    termina em `mark_manual_trigger_active("trigger")`: mandar `Off` por ali
    ARMA a trava que pausa a troca automática de perfil. O `_handle_trigger_reset`
    faz o oposto, `clear_manual_trigger_active("trigger")`. É a R-19, escrita com
    todas as letras em `triggers_actions._reset_trigger`: *"o botão que a usuária
    usa para 'voltar ao normal' era mais um jeito de PAUSAR a troca automática de
    perfil, sem nada na tela dizendo isso"*.

    A PORTA É A `_detalhado`, e não a `_checked`, pela mesma razão que a GUI
    estável migrou (ELO-MUDO-01/T3): só ela junta as DUAS formas de o daemon
    dizer não — o erro JSON-RPC de parâmetro inválido e a recusa que vem DENTRO
    de uma resposta bem-sucedida (`_recusa_no_corpo`). Com a `_checked`, a
    segunda chegaria como sucesso.
    """
    uniq, lado = _exigir_controle(o, "modo"), _lado(o)
    chave = _escolhido(o)
    if not chave:
        raise ValueError(
            "modo: o clique não trouxe qual modo foi escolhido. O `<select>` "
            "carrega a chave no `value` de cada opção; quem tem de mandá-la é a "
            "ponte do piloto, no `change` — ver `_escolhido`.")
    if chave == "Off":
        ok, motivo = _desfecho(p.trigger_reset_detalhado(lado, uniq=uniq))
    else:
        ok, motivo = _desfecho(
            p.trigger_set_detalhado(lado, chave, _padroes(chave), uniq=uniq))
    if not ok:
        raise RuntimeError(_na_lingua_da_tela(motivo, chave)
                           or f"o daemon não aplicou o modo {chave!r}")


@gesto("03-gatilhos.html", "pronto")
def pronto(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Escolher um efeito pronto põe aquela CURVA no gatilho, na hora.

    O EFEITO PRONTO TEM DONO, e o dono é `profiles/trigger_presets.py`: os cinco
    nomes que o desenho oferece são cinco dos seis `FEEDBACK_POSITION_LABELS`, e
    cada um resolve para dez intensidades de 0 a 8.

    E ELE TROCA O MODO — está dito aqui porque é a única coisa deste gesto que
    não é dedução direta do produto. Uma curva de dez posições SÓ existe como
    `MultiPositionFeedback`; na GUI estável a linha de preset nem aparece nos
    outros 17 modos (`_update_preset_row_visibility`). No desenho ela aparece
    sempre, para os 19 — então escolher "Stop hard" com o modo em "Metralhadora"
    só pode querer dizer *"põe este gatilho na curva Stop hard"*. **Isto é
    escolha de produto e é dela**; está no relato para ela decidir. O que não
    faço é a alternativa calada: aplicar dez intensidades num modo que não tem
    posições, que o `build_from_name` recusaria e a tela não explicaria.

    "— Nenhum —" NÃO APLICA NADA, e recusa dizendo. O `value` dele é `custom`,
    que é o token do próprio produto para "os valores são os que estão aí" —
    não há curva a mandar, e mandar o modo "de volta ao normal" seria confundir
    este campo com o "Desligado" do campo de cima.
    """
    uniq, lado = _exigir_controle(o, "efeito pronto"), _lado(o)
    chave = _escolhido(o)
    if chave in ("", "custom"):
        raise ValueError(
            "efeito pronto: não há curva a aplicar. '— Nenhum —' é a ausência de "
            "escolha, e os dois 'Meus efeitos' do desenho não existem em `src/` — "
            "não há onde guardar nem de onde ler um efeito com nome.")
    ok, motivo = _desfecho(
        p.trigger_set_detalhado(lado, MODO_DA_CURVA, _curva(chave), uniq=uniq))
    if not ok:
        # O SPEC DA TRADUÇÃO É O DA CURVA, e não o do preset: quem recusa é o
        # `MultiPositionFeedback`, e é dele que saem os rótulos `Posição 0..9`
        # que a recusa vai nomear.
        raise RuntimeError(_na_lingua_da_tela(motivo, MODO_DA_CURVA)
                           or f"o daemon não aplicou a curva {chave!r}")


@gesto("03-gatilhos.html", "guardar")
def guardar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Guardar esse efeito": o que está na coluna vai para o PERFIL, neste controle.

    POR QUE ELE PRECISA EXISTIR, e é a diferença entre esta aba e as outras: os
    dois gestos vizinhos (`modo` e `pronto`) APLICAM na hora — é a decisão dela
    de 01/09, *"clicar já aplica"*. Mas aplicar não guarda: o efeito vale até a
    próxima troca de perfil, e o disco continua com o que estava lá. Este botão
    é o ponto de gravação, e é a única coisa nesta tela que sobrevive a um
    `profile.switch`.

    DE ONDE VEM O QUE ELE GRAVA — e a resposta não é o daemon. O DualSense **não
    devolve** o modo em que está: gatilho é comando de ida, e o `state_full` não
    o publica (é por isso que `modo` e `pronto` estão no `SEM_ECO` desta aba).
    Logo o único lugar onde a escolha viva existe é a TELA, e é dela que a
    `forma` vem — o piloto recolhe a coluna inteira quando o botão traz
    `data-hef-forma="@controle"`.

    O ALVO É O OVERRIDE DO CONTROLE, e não a seção global: `ControllerOverrides`
    tem `triggers` desde a PERFIL-02, e a aba mostra uma coluna POR CONTROLE.
    Gravar no global faria o "Guardar" do P2 mudar o gatilho do P1 — a mesma
    contradição que mantém o `mic-escopo` da aba Conexões recusando.

    A FUSÃO É POR CAMPO, e o esquema a escreve: *"`None` = sem opinião — o
    controle herda a seção GLOBAL do perfil (merge POR CAMPO na aplicação,
    PERFIL-01: override parcial nunca apaga a cor global no replug)"*. Por isso
    este gesto só toca `triggers` do controle clicado e devolve o resto intacto.
    """
    uniq = _exigir_controle(o, "guardar")
    forma = o.get("forma")
    if not isinstance(forma, dict) or not forma:
        raise RuntimeError(
            "não consegui ler a coluna deste controle. O botão precisa do "
            "`data-hef-forma` para o piloto recolher os campos — sem ele não há "
            "o que guardar, porque o daemon não devolve o modo do gatilho.")

    nome = str((ctx.state or {}).get("active_profile") or "").strip()
    if not nome:
        raise RuntimeError(
            "não há perfil ativo agora, e o efeito do gatilho é do perfil — não "
            "da máquina. Escolha um perfil na aba Perfis e tente de novo.")

    dos_lados = {}
    for lado, sigla in (("left", "e"), ("right", "d")):
        modo = str(forma.get(f"modo-chave-{sigla}") or "").strip()
        if not modo:
            continue
        dos_lados[lado] = {"mode": modo, "params": _ajustes_da_coluna(forma, sigla, modo)}
    if not dos_lados:
        raise RuntimeError(
            "a coluna não trouxe modo nenhum. Os dois `<select>` de modo são "
            "`modo-chave-e` e `modo-chave-d` — se eles mudaram de endereço, o "
            "Guardar deixou de achar o que guardar.")

    loader = perfil._com_o_src()
    prof = loader.load_profile(nome)
    novo = _com_os_gatilhos(prof, uniq, dos_lados)
    if novo is None:
        return
    perfil.gravar_e_reaplicar(novo, ctx, p)


def _ajustes_da_coluna(forma: dict[str, Any], sigla: str, modo: str) -> list[int]:
    """Os ajustes daquele lado, na ORDEM do spec — nunca na ordem da tela.

    A ordem é a que o daemon lê, e ela tem dono: `preset_to_positional_params`
    (ver `_padroes`). A tela desenha uma barra por parâmetro, na mesma ordem,
    endereçadas `aj-val-<lado>-<i>` — então o índice da barra É o índice do
    parâmetro. Ler por índice, e não por NOME, é o que faz isto sobreviver a uma
    tradução de rótulo.

    O QUE NÃO VEIO NA TELA CAI NO PADRÃO DO MODO. Um modo de quatro parâmetros
    desenhado numa coluna que só mostra dois não pode gravar dois — o daemon lê
    a lista posicional inteira, e uma curta muda o que ela não escolheu.
    """
    padrao = _padroes(modo)
    fora = list(padrao)
    for i in range(len(padrao)):
        cru = str(forma.get(f"aj-val-{sigla}-{i}") or "").strip()
        if not cru:
            continue
        try:
            fora[i] = int(float(cru))
        except ValueError:
            # UM VALOR QUE NÃO É NÚMERO NÃO VIRA ZERO. Zero é uma medida; o que
            # a tela não soube dizer tem de cair no padrão do modo, que é o que
            # o daemon aplicaria de qualquer jeito.
            continue
    return fora


def _com_os_gatilhos(prof: Any, uniq: str, dos_lados: dict[str, Any]) -> Any:
    """O perfil com o gatilho DESTE controle trocado, ou `None` se nada mudou.

    `None` evita o barulho: regravar um perfil idêntico troca a data do arquivo
    e faz o daemon reaplicar — e um `profile.switch` no meio de uma partida não
    é de graça.

    A CHAVE DO OVERRIDE É O `uniq` NORMALIZADO, e é o que o esquema espera
    (`_validate_controllers_keys`). Escrever `d4:2f:…` onde o disco guarda
    `d42f…` criaria um segundo dono para o mesmo controle.
    """
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        TriggerConfig,
        TriggersConfig,
    )

    chave = uniq.replace(":", "").lower()
    atuais = dict(prof.controllers or {})
    dele = atuais.get(chave) or ControllerOverrides()
    antes = dele.triggers
    novos = TriggersConfig(
        left=TriggerConfig(**dos_lados["left"]) if "left" in dos_lados
        else (antes.left if antes else TriggerConfig(mode="Off")),
        right=TriggerConfig(**dos_lados["right"]) if "right" in dos_lados
        else (antes.right if antes else TriggerConfig(mode="Off")),
    )
    if antes is not None and antes == novos:
        return None
    atuais[chave] = dele.model_copy(update={"triggers": novos})
    return prof.model_copy(update={"controllers": atuais})


#: AS FUNÇÕES DA PONTE QUE ESTA ABA USA. A régua confere que existem — um nome
#: inventado aparece aqui, e não na mão de quem clica.
PONTE = {"trigger_set_detalhado", "trigger_reset_detalhado"}
#: Vazio: os dois métodos que esta aba usa (`trigger.set` e `trigger.reset`) têm
#: função no `ipc_bridge`, então nenhum passa pelo degrau cru `p.chamar`.
METODOS: set[str] = set()


#: O PISO E AS PROVAS MORAM AQUI, e não no teste — território exclusivo.
#: O `PAGINA` é declarado lá em cima, junto de quem lê a página publicada.
PISO_DA_ABA = 3
#: O `uniq` da prova é a faixa sintética da casa: há dois portões de anonimato
#: nesta árvore e eles não perdoam.
_UNIQ = "aa:bb:cc:00:00:01"
PROVAS = [
    # Um modo comum: os ajustes saem do produto, e é por isso que a prova os
    # BUSCA em vez de digitar `[5, 200]`. Digitados, eles ficariam errados
    # calados no dia em que ela mudasse um padrão — e a régua daria verde sobre
    # um gatilho aplicado com a força de ontem.
    {"pagina": PAGINA, "gesto": "modo", "clique": {"lado": "e",  # (noqa-acento) id
     "modo": "Rigid"},
     "chama": [("trigger_set_detalhado", ["left", "Rigid", _padroes("Rigid")],
                {"uniq": _UNIQ})]},
    # "Desligado" é `trigger.reset` — a R-19. Se alguém trocar por um
    # `trigger.set` com `Off`, esta linha reprova: o nome da função muda.
    {"pagina": PAGINA, "gesto": "modo", "clique": {"lado": "d", "modo": "Off"},  # (noqa-acento) id
     "chama": [("trigger_reset_detalhado", ["right"], {"uniq": _UNIQ})]},
    # A MESMA ESCOLHA PELA OUTRA CHAVE: `valor` é o que um `<select>` manda no
    # `change`. As duas portas do `_escolhido` têm de levar ao mesmo lugar.
    {"pagina": PAGINA,  # (noqa-acento) chave do contrato
     "gesto": "modo", "clique": {"lado": "e", "valor": "Vibration"},
     "chama": [("trigger_set_detalhado", ["left", "Vibration", _padroes("Vibration")],
                {"uniq": _UNIQ})]},
    # O efeito pronto: a curva sai de `profiles/trigger_presets.py`, e o modo é
    # o único em que dez posições existem.
    {"pagina": PAGINA,  # (noqa-acento) chave do contrato
     "gesto": "pronto", "clique": {"lado": "d", "v": "stop_hard"},
     "chama": [("trigger_set_detalhado",
                ["right", MODO_DA_CURVA, _curva("stop_hard")], {"uniq": _UNIQ})]},
]

#: OS GESTOS QUE O DAEMON ACEITA E NÃO PUBLICA. O `state_full` não traz
#: `triggers`: o DualSense não devolve o modo em que está — gatilho adaptativo é
#: comando de IDA, e o `docs/data/mapa-controles.csv` diz o mesmo pela outra
#: ponta. A prova destes é a porta `_detalhado`, que levanta quando o daemon
#: recusa; chegar a "aplicado" já é ele ter aceitado.
SEM_ECO = ("modo", "pronto", "ajuste")
