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


def _specs():
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


def _prontos():
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
            return chave
    return "custom"


def _do_lado(cfg: dict, specs) -> dict:
    """Um lado do gatilho, do perfil para a tela.

    `cfg` é o `{"mode": "Rigid", "params": [0, 180]}` do disco. Sai o rótulo em
    português, o nome de cada ajuste e o valor que ela salvou — que é o que as
    três linhas da aba mostram: Modo, Efeito pronto e Ajustes.
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
    if spec is None:
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
        fora["curva"] = [int(v[0]) if isinstance(v, list) and v else int(v or 0)
                         for v in valores]
        # A escala da curva é 0..8, a mesma dos `_RAMPA_PADRAO` do produto.
        fora["curva-pct"] = [round(max(0, min(100, x / 8 * 100))) for x in fora["curva"]]
        fora["pronto"] = _pronto_da_curva(nome, fora["curva"])
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
        fora["ajustes"].append({
            "nome": p.label,
            "valor": valor,
            # A PORCENTAGEM É DA FAIXA DAQUELE AJUSTE, não de 0..255. Um
            # `force` vai de 0 a 255 e uma `position` de 0 a 9; dividir os dois
            # pela mesma escala pintaria a barra da posição sempre no chão.
            "pct": round(max(0, min(100, (valor - p.min_value) / largura * 100))),
            "min": p.min_value, "max": p.max_value,
        })
    return fora


@registrar("03-gatilhos.html")
def pacote(ctx: Contexto) -> dict:
    """Endereço → valor, por controle da mesa.

    O gatilho é do PERFIL, e o perfil é um só para a mesa inteira — logo as
    colunas recebem o mesmo modo. Isso não é preguiça: o `ControllerOverrides`
    do schema permite gatilho por controle, e quando ele estiver preenchido esta
    função lê o override antes do perfil. Enquanto não estiver, repetir o valor
    é o que corresponde ao que o produto faz.
    """
    specs = _specs()
    p = perfil.ativo(ctx.state.get("active_profile"))
    trig = (p.get("triggers") or {}) if p else {}
    overrides = (p.get("controllers") or {}) if p else {}

    lados = {sig: _do_lado(trig.get(disco) or {}, specs) for sig, disco in LADOS.items()}

    colunas: dict[str, dict] = {}
    pintados = 0
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        entradas = c.get("inputs") or {}
        l2, r2 = entradas.get("l2_raw"), entradas.get("r2_raw")

        #: O OVERRIDE POR CONTROLE VENCE O PERFIL, e é o que o produto faz —
        #: `ControllerOverrides.triggers` existe no schema desde antes desta aba.
        meu = overrides.get(uniq) or {}
        seus = (meu.get("triggers") or {}) if isinstance(meu, dict) else {}
        deste = {sig: (_do_lado(seus[disco], specs) if seus.get(disco) else lados[sig])
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
        pintados += len(col)

    return {
        "colunas": colunas,
        "perfil": ctx.state.get("active_profile") or "",
        "sem_dono": {},
        "cobertura": {"pintados": pintados, "sem_dono": len(SEM_DONO)},
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


def _uniq(o: dict) -> str:
    """O `uniq` da coluna onde ela clicou. Vazio = recusa, nunca "todos".

    ESTA ABA TEM UMA COLUNA POR CONTROLE, e o alcance é a diferença entre um
    ajuste e um estrago: o `trigger.reset` sem `uniq` vai em BROADCAST e zera o
    gatilho dos quatro. Foi o defeito ABAS-06 (25/07), descrito no próprio
    `ipc_bridge.trigger_reset_detalhado`: *"com 'Controle 2' selecionado,
    'Desligar' zerava o gatilho dos QUATRO"*. Aqui ele não pode voltar.
    """
    return str(o.get("uniq") or "")


def _lado(o: dict) -> str:
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


def _escolhido(o: dict) -> str:
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


def _desfecho(resposta) -> tuple[bool, str]:
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
def modo(ctx: Contexto, o: dict, p) -> None:
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
    uniq, lado = _uniq(o), _lado(o)
    if not uniq:
        raise ValueError("modo: o clique não disse em qual controle")
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
        raise RuntimeError(motivo or f"o daemon não aplicou o modo {chave!r}")


@gesto("03-gatilhos.html", "pronto")
def pronto(ctx: Contexto, o: dict, p) -> None:
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
    uniq, lado = _uniq(o), _lado(o)
    if not uniq:
        raise ValueError("efeito pronto: o clique não disse em qual controle")
    chave = _escolhido(o)
    if chave in ("", "custom"):
        raise ValueError(
            "efeito pronto: não há curva a aplicar. '— Nenhum —' é a ausência de "
            "escolha, e os dois 'Meus efeitos' do desenho não existem em `src/` — "
            "não há onde guardar nem de onde ler um efeito com nome.")
    ok, motivo = _desfecho(
        p.trigger_set_detalhado(lado, MODO_DA_CURVA, _curva(chave), uniq=uniq))
    if not ok:
        raise RuntimeError(motivo or f"o daemon não aplicou a curva {chave!r}")


#: AS FUNÇÕES DA PONTE QUE ESTA ABA USA. A régua confere que existem — um nome
#: inventado aparece aqui, e não na mão de quem clica.
PONTE = {"trigger_set_detalhado", "trigger_reset_detalhado"}
#: Vazio: os dois métodos que esta aba usa (`trigger.set` e `trigger.reset`) têm
#: função no `ipc_bridge`, então nenhum passa pelo degrau cru `p.chamar`.
METODOS: set[str] = set()


#: O PISO E AS PROVAS MORAM AQUI, e não no teste — território exclusivo.
PAGINA = "03-gatilhos.html"
PISO_DA_ABA = 2
#: O `uniq` da prova é a faixa sintética da casa: há dois portões de anonimato
#: nesta árvore e eles não perdoam.
_UNIQ = "aa:bb:cc:00:00:01"
PROVAS = [
    # Um modo comum: os ajustes saem do produto, e é por isso que a prova os
    # BUSCA em vez de digitar `[5, 200]`. Digitados, eles ficariam errados
    # calados no dia em que ela mudasse um padrão — e a régua daria verde sobre
    # um gatilho aplicado com a força de ontem.
    {"pagina": PAGINA, "gesto": "modo", "clique": {"lado": "e", "modo": "Rigid"},
     "chama": [("trigger_set_detalhado", ["left", "Rigid", _padroes("Rigid")],
                {"uniq": _UNIQ})]},
    # "Desligado" é `trigger.reset` — a R-19. Se alguém trocar por um
    # `trigger.set` com `Off`, esta linha reprova: o nome da função muda.
    {"pagina": PAGINA, "gesto": "modo", "clique": {"lado": "d", "modo": "Off"},
     "chama": [("trigger_reset_detalhado", ["right"], {"uniq": _UNIQ})]},
    # A MESMA ESCOLHA PELA OUTRA CHAVE: `valor` é o que um `<select>` manda no
    # `change`. As duas portas do `_escolhido` têm de levar ao mesmo lugar.
    {"pagina": PAGINA, "gesto": "modo", "clique": {"lado": "e", "valor": "Vibration"},
     "chama": [("trigger_set_detalhado", ["left", "Vibration", _padroes("Vibration")],
                {"uniq": _UNIQ})]},
    # O efeito pronto: a curva sai de `profiles/trigger_presets.py`, e o modo é
    # o único em que dez posições existem.
    {"pagina": PAGINA, "gesto": "pronto", "clique": {"lado": "d", "v": "stop_hard"},
     "chama": [("trigger_set_detalhado",
                ["right", MODO_DA_CURVA, _curva("stop_hard")], {"uniq": _UNIQ})]},
]

#: OS GESTOS QUE O DAEMON ACEITA E NÃO PUBLICA. O `state_full` não traz
#: `triggers`: o DualSense não devolve o modo em que está — gatilho adaptativo é
#: comando de IDA, e o `docs/data/mapa-controles.csv` diz o mesmo pela outra
#: ponta. A prova destes é a porta `_detalhado`, que levanta quando o daemon
#: recusa; chegar a "aplicado" já é ele ter aceitado.
SEM_ECO = ("modo", "pronto", "ajuste")
