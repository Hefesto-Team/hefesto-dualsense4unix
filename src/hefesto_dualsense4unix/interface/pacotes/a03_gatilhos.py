#!/usr/bin/env python3
"""O pacote da aba `03` Gatilhos — e ele nasceu ERRADO, corrigido em 01/09/2026.

O QUE ESTAVA ESCRITO AQUI, e estava errado:

    "o modo escolhido      NÃO EXISTE no state    ← sem dono
     o efeito pronto       NÃO EXISTE no state    ← sem dono
     os ajustes do modo    NÃO EXISTEM no state   ← sem dono"

A parte factual continua verdadeira: o `state_full` do daemon **não** publica
`triggers`, e o DualSense não devolve o modo em que está — gatilho adaptativo é
comando de ida. O que estava errado era a CONCLUSÃO: dali se tirou "não tem
dono" e pintei quatro travessões.

A PERGUNTA QUE DESFEZ O ERRO: o dado tem dono, e são dois, os dois já no
produto:

    profiles/schema.py       `triggers.left/right` → `mode` e `params`
    app/actions/trigger_specs.py   `PRESETS`: `name` (disco) → `label` (tela)
                                   e cada `param` com nome, faixa e padrão

MEDIDO NO DISCO DO USUÁRIO, perfil "Ação", em 01/09/2026::

    triggers.left  = {"mode": "Rigid",     "params": [0, 180]}
    triggers.right = {"mode": "Vibration", "params": [3, 8, 20]}

Cinco dos 33 perfis do usuário têm gatilho configurado. Mostrar `—` ali era apagar da
tela uma escolha que ela salvou.

O QUE AINDA NÃO TEM DONO, e agora a lista é honesta: nada desta aba. O que muda
é a NATUREZA do valor — ele é o que o **perfil manda ao controle**, não o que
está **aceso no plástico**, e essas são coisas diferentes. Como o aparelho não
devolve a segunda, a primeira é a melhor verdade disponível, e a tela diz de
qual está falando. No lado que o perfil não escreve, o que ele manda é o
nascimento do esquema (24/09/2026, ver `_o_que_o_controle_recebe`).
"""
from __future__ import annotations

import re
from typing import Any

from . import Contexto, jogador_de, perfil, registrar

SEM_DONO: dict[str, str] = {}

LADOS = {"e": "left", "d": "right"}

GESTO_DE_TODOS = "em-todos"

NOME_DO_LADO = {"left": "Gatilho esquerdo (L2)", "right": "Gatilho direito (R2)"}

VAZIO = ""


PAGINA = "03-gatilhos.html"

_CASA = re.compile(r'data-campo="aj-nome-(?P<lado>[ed])-(?P<i>\d+)"')

_LUGAR_VAZIO = re.compile(r'data-controle="(p\d+)"[^>]*data-conectado="nao"')

_QUALQUER_LUGAR = re.compile(r'data-controle="(p\d+)"')

_SELECT = re.compile(
    r'<select[^>]*class="(?P<classe>modo|pronto)"[^>]*>(?P<dentro>.*?)</select>', re.S)

_COMO_O_DOM_ESCREVE = re.compile(r"\s(disabled|hidden|readonly|required)(?=[\s>])")

_COMENTARIO_CSS = re.compile(r"/\*.*?\*/", re.S)

_LIDO: dict[str, int] | None = None
_ENDERECOS: frozenset[str] | None = None
_VAZIOS: frozenset[str] | None = None
_OFERECE: dict[str, frozenset[str]] | None = None
_OPCOES_DO_PRONTO: str | None = None
_CRESCE: dict[str, bool] | None = None


def _pagina_publicada() -> str:
    """O HTML que o produto renderiza AGORA, ou `''` se não der para ler."""
    from hefesto_dualsense4unix.interface import onde

    try:
        return onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")
    except OSError:
        return ""


def _casas_cravadas() -> dict[str, int]:
    """`{"e": N, "d": M}` — quantas barras de ajuste a página publicada CRAVA.

    NÃO É MAIS UMA INSTRUÇÃO, É UM DIAGNÓSTICO. Até 02/09/2026 este número
    mandava no pacote: ele escrevia exatamente `N` casas, enchendo de vazio as
    que o modo não usava. Era a cura do D3 pelo sintoma, e ela tinha um teto —
    `Machine` pede 6 barras, `MultiPositionVibration` pede 11, e a página crava
    4 e 2. *Os sete que sobram não cabiam, e a tela calava sobre eles.*

    Com a decisão de produto (a caixa acompanha o modo), quem manda é o MODO e a caixa
    inteira vem em `blocos:`. O que este número diz agora é UMA coisa: quantas
    barras o produto ainda tem de SOBRESCREVER porque a página publicada as
    trouxe do desenho velho. Ele vai a zero no dia em que ela publicar a bancada
    — e ali o bloco passa a pousar num lugar que já nasceu vazio.

    Ele continua LIDO e nunca digitado: `4` e `2` escritos aqui seriam a segunda
    cópia de um número que o gerador decide, e envelheceriam calados.
    """
    global _LIDO
    if _LIDO is None:
        casas = {"e": 0, "d": 0}
        for m in _CASA.finditer(_pagina_publicada()):
            lado, i = m.group("lado"), int(m.group("i"))
            casas[lado] = max(casas[lado], i + 1)
        _LIDO = casas
    return _LIDO


def sem_comentarios_de_css(doc: str) -> str:
    """O documento sem os `/* … */` — e sem espaço, para casar declaração."""
    return _COMENTARIO_CSS.sub(" ", doc).replace(" ", "").replace("\n", "")


def _a_caixa_cresce() -> dict[str, bool]:
    """`{"e": bool, "d": bool}` — a página publicada deixa a caixa crescer?

    É A PERGUNTA QUE MANTÉM A CURA VÁLIDA NOS DOIS MUNDOS, e ela nasceu de um
    estrago medido: a decisão de produto (a caixa acompanha o modo) tem DUAS metades,
    e elas moram em lados diferentes da fronteira da publicação. A metade que
    ENCHE a caixa é este pacote e vale hoje — um `blocos:` pousa na página
    publicada como pousa na bancada. A metade que a faz CRESCER é o desenho, e
    desenho só entra na tela do usuário quando ELA publica.

    A METADE SOZINHA É PIOR QUE NENHUMA. Medido em 02/09/2026 no Chrome, sobre
    o arquivo publicado, injetando o HTML que `html_dos_ajustes` emite e
    exatamente a operação do piloto (`alvo.innerHTML = html`), com os perfis do
    disco do usuário::

        aventura  L2 `Curva de força`  10 barras em caixa de  92px → vaza  58px
                  R2 `Curva de força`  10 barras em caixa de  46px → vaza 104px
        corrida   R2 `Vibração por posição` 11 barras em 46px → vaza 119px

    E o que vaza cai POR CIMA do `<select>` de Modo do R2 e do "Guardar esse
    efeito" (foto: `/tmp/gat-pub-aventura.png`).

    A RESPOSTA VEM DA PÁGINA, nunca de uma data ou de um interruptor: a trilha
    de ajustes cresce quando ela é `minmax(var(--r-aj-<lado>),auto)`. Enquanto
    a publicada trouxer a trilha FIXA, o pacote se limita ao que cabe lá; no dia
    em que ela publicar, a mesma leitura devolve `True` e a caixa passa a ter o
    tamanho do modo, sem ninguém lembrar de mexer aqui.

    POR LADO, e não uma resposta só: as duas trilhas são declaradas separadas
    (`--r-aj-e` e `--r-aj-d`), e um desenho que crescesse só a de cima é uma
    página que este pacote tem de saber ler.
    """
    global _CRESCE
    if _CRESCE is None:
        css = sem_comentarios_de_css(_pagina_publicada())
        _CRESCE = {lado: f"minmax(var(--r-aj-{lado}),auto)" in css
                   for lado in ("e", "d")}
    return _CRESCE


def _cabem_no_desenho(sigla: str) -> int | None:
    """Quantas barras a página publicada comporta naquele lado — ou `None`."""
    if _a_caixa_cresce().get(sigla):
        return None
    cabem = _casas_cravadas().get(sigla, 0)
    return cabem or None


def _o_que_o_select_oferece() -> dict[str, frozenset[str]]:
    """Os `value` que cada campo de escolha da página publicada aceita."""
    global _OFERECE
    if _OFERECE is None:
        fora: dict[str, set[str]] = {"modo": set(), "pronto": set()}
        for m in _SELECT.finditer(_pagina_publicada()):
            fora[m.group("classe")].update(
                re.findall(r'<option[^>]*value="([^"]*)"', m.group("dentro")))
        _OFERECE = {k: frozenset(v) for k, v in fora.items()}
    return _OFERECE


def _enderecos_da_pagina() -> frozenset[str]:
    """Todo `data-campo` que a página publicada tem. Vazio se ela não abrir."""
    global _ENDERECOS
    if _ENDERECOS is None:
        _ENDERECOS = frozenset(re.findall(r'data-campo="([^"]+)"', _pagina_publicada()))
    return _ENDERECOS


def _lugares_que_o_desenho_da_por_vazios() -> frozenset[str]:
    """Os `pref` que a página publicada já marca `data-conectado="nao"`.

    POR QUE O PACOTE PRECISA SABER DISSO, e é o defeito D4, medido em
    02/09/2026: os quatro `<select>` das colunas P3 e P4 são **endereço morto**.
    O piloto preenche todo lugar que a mesa não tem com `dict.fromkeys(chaves,
    "—")` (`pacotes/__init__.py:175`), e `escrever()` **recusa** escrever um
    valor que o `<select>` não oferece (`hefesto_vivo.py:170-174`) — a recusa é
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


def _todos_os_lugares_da_pagina() -> frozenset[str]:
    """Os `pref` de TODAS as colunas da página publicada, cheias ou vazias."""
    return frozenset(_QUALQUER_LUGAR.findall(_pagina_publicada()))


#: O QUE O DESENHO OFERECE PARA DIZER "NÃO HÁ NADA AQUI" — decisão 13 dela,
TRAVESSAO = "—"


def _sem_nada(campo: str, cravado: str) -> str:
    """O que este campo mostra num lugar SEM APARELHO, hoje."""
    return VAZIO if TRAVESSAO in _o_que_o_select_oferece().get(campo, ()) else cravado


def _escapar(texto: str) -> str:
    """O mínimo para um texto de dado caber num atributo e num nó de texto."""
    return (texto.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _specs() -> Any:
    """A tabela de presets do produto, ou `None` se o `src/` não abrir."""
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions import trigger_specs

        return trigger_specs
    except Exception:
        return None


def _prontos() -> Any:
    """As curvas prontas do produto (`profiles/trigger_presets.py`), ou `None`."""
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.profiles import trigger_presets

        return trigger_presets
    except Exception:
        return None


#: O outro é o `MODO_DA_VIBRACAO`, logo abaixo — a GUI estável repovoa o mesmo
MODO_DA_CURVA = "MultiPositionFeedback"

#: gesto mandava sempre `MultiPositionFeedback`.
MODO_DA_VIBRACAO = "MultiPositionVibration"

MODOS_COM_CURVA = (MODO_DA_CURVA, MODO_DA_VIBRACAO)


DICA_DO_MODO = {
 "Off": "O jogo manda no gatilho; sem jogo, ele fica solto, como num controle comum.",
 "Rigid": "Trava dura do começo ao fim do curso. Serve para freio de carro e para arma travada.",
 "SimpleRigid": "Trava dura, com um só ponto de ajuste em vez de dez.",
 "Pulse": "Um solavanco num ponto do curso e depois solta — o coice de um tiro único.",
 "PulseA": "Pulso com a subida mais suave: a força cresce antes do estalo.",
 "PulseB": "Pulso com a descida mais suave: o estalo vem e a força cai devagar.",
 "Resistance": "Peso constante do começo ao fim, sem trava — remada, alavanca, arco sendo puxado.",
 "Bow": "Fica cada vez mais pesado até o fim do curso, e então solta de uma vez.",
 "Galloping": "Batidas ritmadas enquanto o gatilho está apertado — cavalo correndo, motor pegando.",
 "SemiAutoGun": "Uma trava, um estalo, e o gatilho volta. Um tiro por aperto.",
 "AutoGun": "Vibra continuamente enquanto está apertado — rajada.",
 "Machine": "Batidas rápidas e fortes enquanto apertado.",
 "Feedback": "Solto até certo ponto do curso, e daí em diante duro. O ponto é ajustável.",
 "Weapon": "Trava, solta no estalo e fica leve até o fim — espingarda.",
 "Vibration": "Treme o gatilho na frequência escolhida, sem opor força.",
 "SlopeFeedback": "A força sobe em linha reta do início ao fim do curso.",
 "MultiPositionFeedback": "Você desenha a força em dez posições do curso, uma por uma.",
 "MultiPositionVibration": "Treme só na faixa do curso que você marcar.",
 "Custom": "As dez posições em branco, para desenhar a curva do jeito que a sua mão pedir.",
}

SEM_APARELHO_AQUI = "Nenhum controle neste lugar."

PREFIXO_DA_DICA_DO_MODO = "dica-modo-"
PREFIXO_DA_DICA_DO_PRONTO = "dica-pronto-"


def descricao_do_modo(chave: str) -> str:
    """A explicação do modo, na frase desta tela — vazio nunca.

    A QUEDA É A DESCRIÇÃO DO PRODUTO, e não o silêncio: um modo que o produto
    ganhe e que esta tela ainda não tenha frase para continua tendo o
    `spec.description`, que é a frase da GTK. Entre a frase concreta, a genérica
    e nenhuma, a ordem é essa — e o gerador reprova alto no dia em que a
    primeira faltar, para que a segunda não vire o padrão calado.
    """
    daqui = DICA_DO_MODO.get(chave)
    if daqui:
        return daqui
    specs = _specs()
    spec = specs.get_spec(chave) if specs else None
    return str(getattr(spec, "description", "") or "")


#: O QUE A TELA CHAMA O «DESLIGADO» DO GATILHO — 03/10/2026, ela: *«o certo
#: seria os controles obedecerem quando o jogo manda e na
#: ausencia disso o perfil ganha»*  (noqa-acento: citação literal).
#: A chave segue sendo `Off` (o perfil não muda de forma, e o
#: `trigger.reset` do gesto é o mesmo): o que muda é o NOME, que diz o que o
#: gesto faz. O dono do rótulo do produto (`trigger_specs`, «Desligado») não
#: muda: a CLI e o daemon seguem falando dele.
ROTULO_DO_JOGO_DECIDE = "O jogo decide"


def _rotulo_do_modo(chave: str) -> str:
    """O rótulo de tela de um modo (`Rigid` → `Rígido`), ou a chave crua."""
    if chave == "Off":
        return ROTULO_DO_JOGO_DECIDE
    specs = _specs()
    spec = specs.get_spec(chave) if specs else None
    return str(getattr(spec, "label", "") or chave)


def destinos_do_campo_de_pronto(modo_chave: str) -> list[str]:
    """Os modos a que as curvas OFERECIDAS neste campo levam, naquele modo.

    ELE É DERIVADO, NUNCA DIGITADO — e essa é a razão de ele existir em vez de
    duas frases escritas à mão. Quem decide o que o campo oferece é
    :func:`_tabela_que_o_campo_mostra`; quem decide para que modo cada curva
    leva é :func:`_curva`, pela TABELA em que ela mora. Perguntar aos dois é o
    único jeito de a dica não prometer um caminho que a lista não abre.
    """
    presets, _ = _tabela_que_o_campo_mostra(modo_chave)
    fora: list[str] = []
    for chave in presets:
        try:
            destino = _curva(chave)[1]
        except (ValueError, RuntimeError):
            continue
        if destino not in fora:
            fora.append(destino)
    return fora


def dica_do_pronto(modo_chave: str) -> str:
    """O aviso do campo "Efeito pronto" — ANTES do clique, com o modo de AGORA.

    DECISÃO [02] do PO, 04/09/2026: *"Fica como está, e a dica avisa ANTES do
    clique. O desenho é do usuário, o atalho de um clique é real, e a única dívida
    medida é a tela não avisar que o modo vai mudar."*

    **CONFIRMADA PELO USUÁRIO EM 05/09/2026, pergunta `03-Q2`**: perguntada se uma
    curva pronta pode trocar o modo sozinha, marcou *"Aplica na hora, com
    aviso"* — que é este comportamento, com esta frase. **É esta linha que vale
    daqui em diante**, e a de cima fica pela mesma razão da `03-Q1`.

    **NÃO REESCREVA A FRASE À MÃO.** Ela é DERIVADA: quem diz para onde cada
    família de curva leva é :func:`destinos_do_campo_de_pronto`, lendo a tabela
    em que a curva mora. A primeira versão prometia dois destinos onde a lista
    abre um, e foi a mordida que a derrubou. Uma frase digitada volta a mentir
    no dia em que a tabela mudar.

    A DIVERGÊNCIA COM A GTK É REAL E CONHECIDA (linha `Quando o campo "Efeito
    pronto" aparece, e o que escolhê-lo faz`): lá a linha só existe nos DOIS
    modos por posição e escolher um preset preenche os sliders **sem mexer no
    modo**; aqui o campo aparece nos 19 e o clique já aplica — logo, fora dos
    dois modos por posição, escolher uma curva TROCA o modo. Quem decidiu manter
    foi o PO; o que faltava era a tela dizer isso antes.

    **A PRIMEIRA VERSÃO DESTA FRASE PROMETIA DEMAIS, e quem a derrubou foi a
    mordida.** Ela dizia *"as curvas de força vão para «Curva de força» e as de
    vibração para «Vibração por posição»"* nos dezessete modos comuns — e é
    FALSO: com o gatilho em `Rigid`, o campo oferece SÓ as seis curvas de
    feedback (`_tabela_que_o_campo_mostra`, medido no DOM em 03/09), então
    `Vibração por posição` não é alcançável dali. A tela estaria descrevendo um
    caminho que a lista não abre — que é o alarme sem medição que esta casa bane.

    **A CURA É PERGUNTAR À LISTA**, e não escolher melhor as palavras: o destino
    sai de :func:`destinos_do_campo_de_pronto`, que lê o que o campo oferece
    naquele modo e resolve cada curva pela tabela em que ela mora. Se um dia o
    campo passar a oferecer as onze, a dica nomeia as duas sozinha.
    """
    agora = _rotulo_do_modo(modo_chave)
    fim = "Um efeito seu volta ao modo com que foi guardado."
    destinos = destinos_do_campo_de_pronto(modo_chave)
    if not destinos:
        return f"Este gatilho está em «{agora}». {fim}"
    para = " ou ".join(f"«{_rotulo_do_modo(d)}»" for d in destinos)
    if destinos == [modo_chave]:
        return (f"Este gatilho está em «{agora}», e o campo mostra as curvas "
                f"deste modo: escolher uma aplica as dez posições dela na hora, "
                f"sem trocar o modo. {fim}")
    return (f"Está em «{agora}». Escolher uma curva troca o modo para "
            f"{para}, na hora. {fim}")


def _tabela_da_curva(modo: str) -> tuple[dict[str, list[int]], dict[str, str]]:
    """`(presets, rótulos)` do modo por posição, ou dois vazios nos outros 17.

    ESTA É A REGRA DA GUI ESTÁVEL, palavra por palavra
    (`triggers_actions._populate_preset_combo`): `MultiPositionFeedback` lê
    `FEEDBACK_POSITION_*`, `MultiPositionVibration` lê `VIBRATION_POSITION_*`,
    e nenhum outro modo tem curva. Escrever a escolha em dois lugares — na
    lista que a tela mostra e no gesto que aplica — era como a tela passaria a
    oferecer uma curva que o gesto não sabe resolver.
    """
    tp = _prontos()
    if tp is None:
        return {}, {}
    if modo == MODO_DA_VIBRACAO:
        return dict(tp.VIBRATION_POSITION_PRESETS), dict(tp.VIBRATION_POSITION_LABELS)
    if modo == MODO_DA_CURVA:
        return dict(tp.FEEDBACK_POSITION_PRESETS), dict(tp.FEEDBACK_POSITION_LABELS)
    return {}, {}


def _pronto_da_curva(nome: str, curva: list[int]) -> str:
    """Qual efeito pronto é aquela curva salva, ou `custom` se não for nenhum."""
    presets, _ = _tabela_da_curva(nome)
    if not presets or len(curva) != 10:
        return "custom"
    for chave, valores in presets.items():
        if list(valores) == list(curva):
            return str(chave)
    return "custom"


# * TROCA DE PERFIL — o daemon REAPLICA o perfil no `profile.switch`, então o
_PERFIL_DO_RASCUNHO: str = ""
_RASCUNHO: dict[tuple[str, str], dict[str, Any]] = {}


def _chave_do_rascunho(uniq: str, disco: str) -> tuple[str, str]:
    """O endereço de uma metade do rascunho: `uniq` NORMALIZADO e o lado.

    O `uniq` do clique vem da mesa (`d4:2f:…`) e o do perfil vem do disco
    (`d42f…`). Normalizar aqui é o que impede o mesmo controle de ter duas
    entradas — a mesma razão que `_com_os_gatilhos` já escreve.
    """
    return (uniq.replace(":", "").lower(), disco)


def esquecer_o_rascunho() -> None:
    """Joga fora o que esta sessão lembrava de ter aplicado."""
    _RASCUNHO.clear()


def _o_rascunho_e_deste_perfil(perfil: str) -> None:
    """Poda o rascunho quando o perfil ativo mudou. Ver a nota da seção."""
    global _PERFIL_DO_RASCUNHO
    if perfil != _PERFIL_DO_RASCUNHO:
        _PERFIL_DO_RASCUNHO = perfil
        esquecer_o_rascunho()


def _o_rascunho_e_de_quem_esta_na_mesa(uniqs: set[str]) -> None:
    """Poda o rascunho dos controles que saíram. Ver a nota da seção."""
    for chave in [k for k in _RASCUNHO if k[0] not in uniqs]:
        _RASCUNHO.pop(chave, None)


def _lembrar_o_aplicado(perfil: str, uniq: str, disco: str,
                        cfg: dict[str, Any]) -> None:
    """Grava no rascunho o que acabou de ir para o aparelho."""
    _o_rascunho_e_deste_perfil(perfil)
    _RASCUNHO[_chave_do_rascunho(uniq, disco)] = {
        "mode": str(cfg.get("mode") or "Off"),
        "params": [int(v) for v in (cfg.get("params") or [])],
    }


def _do_rascunho(uniq: str, disco: str) -> dict[str, Any] | None:
    """O que esta sessão aplicou naquele gatilho, ou `None` se não aplicou nada."""
    return _RASCUNHO.get(_chave_do_rascunho(uniq, disco))


def _chave_no_perfil(uniq: str) -> str:
    """O `uniq` na grafia do mapa `controllers` — doze hexa, ou `""`."""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    return norm_mac(str(uniq or "").strip()) or ""


def _o_lado_que_o_perfil_cala(disco: str) -> dict[str, Any]:
    """O gatilho com que o esquema preenche o lado que o perfil não escreve."""
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.profiles.schema import TriggersConfig

        lado = getattr(TriggersConfig(), disco)
        return {"mode": str(lado.mode), "params": list(lado.params)}
    except Exception:
        return {}


def _o_que_o_controle_recebe(p: dict[str, Any] | None, uniq: str,
                             disco: str) -> dict[str, Any]:
    """O gatilho que aquele controle RECEBE daquele lado — `{"mode", "params"}`."""
    seu = _do_rascunho(uniq, disco)
    if seu:
        return seu
    if not p:
        return {}
    alvo = _chave_no_perfil(uniq)
    controles = p.get("controllers")
    for chave, dele in (controles.items() if isinstance(controles, dict) else ()):
        if not alvo or _chave_no_perfil(str(chave)) != alvo or not isinstance(dele, dict):
            continue
        seus = dele.get("triggers")
        escrito = seus.get(disco) if isinstance(seus, dict) else None
        if isinstance(escrito, dict) and escrito:
            return escrito
    globais = p.get("triggers")
    escrito = globais.get(disco) if isinstance(globais, dict) else None
    if isinstance(escrito, dict) and escrito:
        return escrito
    return _o_lado_que_o_perfil_cala(disco)


# `app/gui_prefs.py`, a mesma caixa de preferências da interface que já existe,
# vazar no `$HOME` de quem roda) e tem três funções públicas de módulo —
# `load_gui_prefs`, `save_gui_prefs`, `set_pref`. **É reuso, e a LEI 0 desta

#: A CHAVE NA CAIXA DE PREFERÊNCIAS. Ela não está nos `_DEFAULTS` do
#: `gui_prefs` de propósito: ausente quer dizer "ela ainda não salvou nenhum",
#: que é diferente de "salvou e apagou todos" — e `load_gui_prefs` devolve o
CHAVE_DOS_MEUS = "gatilhos_meus_efeitos"

PREFIXO_DO_MEU = "meu:"

SEPARADOR_DOS_MEUS = "Meus efeitos"


def meus_efeitos() -> dict[str, Any]:
    """Os efeitos que ELA salvou, do disco. `{}` quando não há nenhum.

    NUNCA LEVANTA: `load_gui_prefs` já engole `JSONDecodeError` e `OSError` com
    aviso no log e devolve os padrões. Um arquivo corrompido não pode derrubar a
    pintura da aba inteira — a tela ficaria congelada sem dizer por quê.
    """
    try:
        from hefesto_dualsense4unix.app.gui_prefs import load_gui_prefs

        guardado = load_gui_prefs().get(CHAVE_DOS_MEUS)
    except Exception:
        return {}
    if not isinstance(guardado, dict):
        return {}
    return {str(nome): valor for nome, valor in guardado.items()
            if isinstance(valor, dict) and nome.strip()}


def _guardar_meus_efeitos(todos: dict[str, Any]) -> None:
    """Escreve a biblioteca de volta, PRESERVANDO o resto das preferências.

    O `load` antes do `save` não é cerimônia: `save_gui_prefs` grava o
    dicionário INTEIRO, e escrever só a nossa chave apagaria o
    `advanced_editor` e o `ambiente_corrigido` dela.
    """
    from hefesto_dualsense4unix.app.gui_prefs import load_gui_prefs, save_gui_prefs

    prefs = load_gui_prefs()
    prefs[CHAVE_DOS_MEUS] = todos
    save_gui_prefs(prefs)


def _meia_do_efeito(efeito: Any, disco: str) -> dict[str, Any] | None:
    """A metade `left`/`right` de um efeito salvo, ou `None` se ele não a tem."""
    if not isinstance(efeito, dict):
        return None
    meia = efeito.get(disco)
    if not isinstance(meia, dict) or not meia.get("mode"):
        return None
    return meia


def _meu_efeito_que_casa(disco: str, cfg: dict[str, Any]) -> str:
    """O nome do efeito salvo que É esta configuração, ou `""`."""
    modo_agora = str((cfg or {}).get("mode") or "Off")
    params_agora = list((cfg or {}).get("params") or [])
    for nome, efeito in meus_efeitos().items():
        meia = _meia_do_efeito(efeito, disco)
        if meia is None:
            continue
        if str(meia.get("mode")) == modo_agora and list(meia.get("params") or []) == params_agora:
            return nome
    return ""


def _do_lado(cfg: dict[str, Any], specs: Any) -> dict[str, Any]:
    """Um lado do gatilho, do perfil para a tela."""
    nome = str((cfg or {}).get("mode") or "Off")
    valores = list((cfg or {}).get("params") or [])
    spec = specs.get_spec(nome) if specs else None

    fora: dict[str, object] = {
        "modo": spec.label if spec else nome,
        "modo-chave": nome,
        "pronto": "custom",
        "ajustes": [],
    }
    ajustes: list[dict[str, Any]] = []
    fora["ajustes"] = ajustes

    if spec is None:
        return fora

    #: ajuste — mas `MultiPositionFeedback` e `MultiPositionVibration` gravam
    por_indice: dict[int, int] = {}
    if any(isinstance(v, list) for v in valores):
        curva_da_tela: list[int] = [
            int(v[0]) if isinstance(v, list) and v else int(v or 0)
            for v in valores]
        fora["curva"] = curva_da_tela
        fora["curva-pct"] = [round(max(0, min(100, x / 8 * 100)))
                             for x in curva_da_tela]
        fora["pronto"] = _pronto_da_curva(nome, curva_da_tela)
        # `aventura` tem `MultiPositionFeedback` nos dois gatilhos e o `corrida`
        posicoes = [i for i, q in enumerate(spec.params) if q.name.startswith("pos_")]
        alvos = posicoes if len(posicoes) == len(curva_da_tela) else list(
            range(len(curva_da_tela)))
        por_indice = dict(zip(alvos, curva_da_tela, strict=False))
    elif nome in MODOS_COM_CURVA:
        # controle na mesa e li o DOM — modo `MultiPositionFeedback`, dez barras
        # o MODO que voltava para o disco, aqui é o NOME DA CURVA que some. E
        posicoes = [i for i, q in enumerate(spec.params) if q.name.startswith("pos_")]
        deitada = [int(valores[i] or 0) for i in posicoes if i < len(valores)]
        if posicoes and len(deitada) == len(posicoes):
            fora["curva"] = deitada
            fora["curva-pct"] = [round(max(0, min(100, x / 8 * 100)))
                                 for x in deitada]
            fora["pronto"] = _pronto_da_curva(nome, deitada)

    #: posições do `MultiPositionFeedback` — logo, nos outros 18 modos não há

    for i, p in enumerate(spec.params):
        if por_indice:
            valor = por_indice.get(i, p.default)
        else:
            valor = valores[i] if i < len(valores) else p.default
        largura = max(1, p.max_value - p.min_value)
        ajustes.append({
            "nome": p.label,
            "valor": valor,
            "pct": round(max(0, min(100, (valor - p.min_value) / largura * 100))),
            "min": p.min_value, "max": p.max_value,
        })
    return fora


SEM_AJUSTE = "Sem ajustes."


#: `minmax(var(--r-aj-<lado>),auto)` na página e devolve `None`, então nada é


def html_dos_ajustes(sigla: str, ajustes: list[dict[str, Any]],
                     cabem: int | None = None, editavel: bool = False) -> str:
    """A caixa de ajustes daquele lado, em HTML — a lista do MODO.

    Uma linha por parâmetro do modo, com o rótulo, a barra na porcentagem da
    FAIXA daquele parâmetro e o número. Zero parâmetros devolvem a frase, que é
    o que as colunas vazias do desenho já diziam.

    `editavel` É QUEM PODE ARRASTAR — 03/09/2026, e ele tem DOIS donos de razão,
    não um:

    * o PRODUTO passa `True` só nas colunas que têm aparelho. Um ajuste é de um
      gatilho; arrastar num lugar vazio só pode terminar em recusa, e o botão
      que convida para uma recusa é pior que o botão que não existe — é a mesma
      regra que o `pointer-events:none` do CSS já aplica aos `<select>`;
    * o DESENHO fica no padrão `False`, e isto está esperando a palavra de produto.
      A alavanca é invisível — o desenho não muda um pixel —, mas o que o usuário
      aprovou em 27/08 foi uma barra de LEITURA, e transformar leitura em
      controle é decisão de produto. O gerador escreve a bancada e a bancada é
      o que ela olha; enquanto ela não disser, o desenho segue mostrando o que
      o usuário aprovou e o produto segue tendo a paridade com a GTK que a Lei 0
      manda ter.

    `cabem` É O TETO DA PÁGINA QUE O PRODUTO RENDERIZA HOJE, e `None` quer dizer
    "não há teto". Ele é a metade que faltava da decisão de produto: a caixa acompanha
    o modo, mas a trilha que a deixa CRESCER está na bancada e a bancada só
    chega à tela quando ela publica. Sem o teto, uma caixa de 92px recebe onze
    barras e as sete que sobram caem por cima do `<select>` de Modo do R2 e do
    "Guardar esse efeito" — medido no Chrome sobre o arquivo PUBLICADO, com dois
    perfis do disco do usuário (`aventura` vaza 58px à esquerda e 104 à direita;
    `corrida` vaza 119). Ver `_a_caixa_cresce`.

    COM TETO, A ÚLTIMA CASA VIRA O AVISO. Ela perde uma barra e ganha o número
    do que não está vendo — que é a única coisa que a caixa cheia não lhe diz.
    Calar seria repetir o defeito que esta aba existe para matar: hoje, na
    página publicada, um `Curva de força` mostra QUATRO barras em branco sobre
    dez intensidades gravadas, e nada na tela conta que há dez.

    E O QUE NÃO COUBE CONTINUA NO DOM, invisível — `style="display:none"`, que
    ganha da classe `.barra` por ser inline. Não é enfeite: o "Guardar esse
    efeito" lê os `aj-val-*` DA TELA (o daemon não devolve o modo do gatilho), e
    `_ajustes_da_coluna` cai no PADRÃO do modo para o índice que não achar.
    Emitir só as barras visíveis faria o botão gravar os padrões por cima das
    sete posições que ela salvou — destruir dado dela em silêncio, no clique de
    um botão que diz "guardar".

    A MARCAÇÃO É A MESMA QUE O GERADOR ESCREVIA — `data-campo` inclusive, e o
    `data-hef-alvo="largura"` da barra. Ela não é enfeite:

    * o `data-campo` é o que o "Guardar esse efeito" lê. O piloto recolhe a
      coluna por `[data-linha],[data-campo]`, e sem endereço nenhum ali o
      Guardar leria zero ajustes e gravaria os PADRÕES do modo por cima do que
      ela salvou;
    * o `data-hef-alvo="largura"` é como a régua do mockup sabe LER a barra: sem
      ele, o valor cravado de `aj-pct-*` passa a ser o texto (vazio) em vez da
      largura, e a régua deixa de enxergar a barra.

    E NADA PINTA AQUI DENTRO: o pacote não emite `aj-*` em `colunas`, então o
    `escrever()` do piloto nunca visita estes elementos — logo nenhum
    `data-hef-visto` é carimbado, o `innerHTML` não diverge do emitido, e o
    bloco é trocado UMA vez em vez de quatro por segundo. Medido: 17 tiques,
    1 pintura.
    """
    if not ajustes:
        return f'            <div class="ajustes-vazio">{SEM_AJUSTE}</div>'

    a_vista = len(ajustes) if cabem is None else min(len(ajustes), cabem)
    linhas = [_html_de_uma_barra(sigla, i, a, escondida=i >= a_vista,
                                 editavel=editavel)
              for i, a in enumerate(ajustes)]
    return "\n".join(linhas)


_ALAVANCA = ("position:absolute;left:0;top:-9px;width:100%;height:23px;"
             "margin:0;padding:0;opacity:0;cursor:ew-resize;"
             "-webkit-appearance:none;background:transparent")


def _html_de_uma_barra(sigla: str, i: int, a: dict[str, Any],
                       escondida: bool = False, editavel: bool = False) -> str:
    """Uma linha da caixa de ajustes. `escondida` guarda o valor sem mostrá-lo.

    `editavel` PÕE A ALAVANCA — 03/09/2026, e é a maior dívida desta aba.
    Medido: 17 dos 19 modos têm ajuste, somando 73 parâmetros (Rigid 2,
    Machine 6, MultiPositionFeedback 10, MultiPositionVibration 11). Na GTK
    cada um é um `Gtk.Scale` que ela arrasta, com faixa e padrão vindos do
    `trigger_specs`; no HTML **nenhum** era tocável, e escolher um modo
    aplicava os PADRÕES dele e acabava.

    O DESENHO NÃO MUDA UM PIXEL: a alavanca é um `<input type="range">`
    transparente POR CIMA do trilho que o usuário aprovou. Quem desenha continua
    sendo o `.cheio` que o pacote pinta; o `<input>` só recebe o arrasto. Uma
    barra visível nova seria desenho, e desenho é do usuário.

    A FAIXA É A DO PARÂMETRO, e sai do produto: `spec.params[i].min_value` e
    `.max_value`, os mesmos números que o `Gtk.Scale` usa. Digitar `0..255`
    aqui poria a posição do curso (0..9) numa régua trinta vezes maior.

    ELE PEDE A FORMA E NÃO ENTRA NELA. `data-hef-forma="@controle"` é o que faz
    o arrasto chegar ao Python com a coluna inteira — o modo e os outros
    ajustes —, porque o daemon lê a lista posicional INTEIRA e um número solto
    trocaria os vizinhos pelos padrões. Mas a alavanca não tem `data-linha` nem
    `data-campo`, e a varredura do piloto recolhe só esses dois: quem carrega o
    valor daquela casa continua sendo o `.num`. Dois endereços para o mesmo
    número seriam duas verdades no mesmo clique.

    E ELE NÃO FAZ O BLOCO PISCAR: o `value` viaja no ATRIBUTO, e arrastar muda
    a *propriedade*. O `innerHTML` continua igual ao emitido enquanto ela
    arrasta, então o piloto não troca a caixa debaixo da mão do usuário.
    """
    oculta = ' style="display:none"' if escondida else ""
    alavanca = ""
    if editavel and not escondida:
        alavanca = (
            f'<input type="range" min="{int(a.get("min", 0))}" '
            f'max="{int(a.get("max", 255))}" step="1" '
            f'value="{int(a["valor"])}" data-gesto="ajuste" '
            f'data-lado="{sigla}" data-i="{i}" data-hef-forma="@controle" '
            f'aria-label="{_escapar(str(a["nome"]))}" '
            f'style="{_ALAVANCA}">')
    return (
        f'            <div class="barra" data-ajuste="{sigla}-{i}"{oculta}>\n'
        f'              <span class="nome" data-campo="aj-nome-{sigla}-{i}">'
        f'{_escapar(str(a["nome"]))}</span>\n'
        f'              <span class="trilho"><span class="cheio" '
        f'data-campo="aj-pct-{sigla}-{i}" data-hef-alvo="largura" '
        f'style="width:{a["pct"]}%"></span>{alavanca}</span>\n'
        f'              <span class="num" data-campo="aj-val-{sigla}-{i}">'
        f'{_escapar(str(a["valor"]))}</span>\n'
        f'            </div>')


#: é o rótulo, e é só ele que `html_das_opcoes_de_modo` troca. Tudo o mais da
_OPCAO = re.compile(
    r'(?P<cabeca><option value="(?P<valor>[^"]*)"[^>]*>)(?P<texto>[^<]*)</option>')

_OPCOES_DO_MODO: str | None = None


def _opcoes_cravadas_do_modo() -> str:
    """As opções do campo "Modo" que a página publicada traz, como o DOM as escreve."""
    global _OPCOES_DO_MODO
    if _OPCOES_DO_MODO is None:
        dentro = ""
        for m in _SELECT.finditer(_pagina_publicada()):
            if m.group("classe") == "modo":
                dentro = m.group("dentro")
                break
        _OPCOES_DO_MODO = _COMO_O_DOM_ESCREVE.sub(
            r' \1=""', dentro.replace(" selected", "")).rstrip()
    return _OPCOES_DO_MODO


def html_das_opcoes_de_modo() -> str:
    """As opções do campo "Modo", com o RÓTULO perguntado ao dono."""
    specs = _specs()
    if specs is None:
        return _opcoes_cravadas_do_modo()
    do_produto = {p.name: _rotulo_do_modo(p.name) for p in specs.PRESETS}

    def rotular(m: re.Match[str]) -> str:
        if m.group("valor") == TRAVESSAO and "hidden" not in m.group("cabeca"):
            # O `—` é do lugar vazio, não da lista que ela abre — também numa
            # página publicada antes de o desenho o esconder.
            return m.group(0).replace(">", ' hidden="">', 1)
        rot = do_produto.get(m.group("valor"))
        return m.group(0) if rot is None else f'{m.group("cabeca")}{_escapar(rot)}</option>'

    return _OPCAO.sub(rotular, _opcoes_cravadas_do_modo())


def _opcoes_cravadas_do_pronto() -> str:
    """As opções de "Efeito pronto" que O DESENHO oferece, lidas da página."""
    global _OPCOES_DO_PRONTO
    if _OPCOES_DO_PRONTO is None:
        dentro = ""
        for m in _SELECT.finditer(_pagina_publicada()):
            if m.group("classe") == "pronto":
                dentro = m.group("dentro")
                break
        antes = dentro.split("<option disabled>", 1)[0].replace(" selected", "")
        _OPCOES_DO_PRONTO = _COMO_O_DOM_ESCREVE.sub(r' \1=""', antes).rstrip()
    return _OPCOES_DO_PRONTO


def _valores_cravados_do_pronto() -> frozenset[str]:
    """Os `value` que o DESENHO já oferece no campo "Efeito pronto"."""
    return frozenset(re.findall(r'<option value="([^"]*)"',
                                _opcoes_cravadas_do_pronto()))


def _tabela_que_o_campo_mostra(modo: str) -> tuple[dict[str, list[int]], dict[str, str]]:
    """A tabela que o campo "Efeito pronto" OFERECE naquele modo.

    NÃO É `_tabela_da_curva`, e a diferença é uma decisão de produto. A GUI estável
    ESCONDE a linha de preset fora dos dois modos por posição
    (`_update_preset_row_visibility`); o desenho dela a mostra nos DEZENOVE. Nos
    outros 17 a página crava as curvas de FEEDBACK — logo é a tabela de feedback
    que o campo mostra ali, e o gesto `pronto` já sabe aplicá-las: ele tira o
    modo da TABELA em que a curva mora (ver `_curva`), não do modo de agora.

    O BURACO QUE ISTO TAPA, medido no DOM VIVO em 03/09/2026 com o gatilho em
    `Desligado` e um controle na mesa: os oito campos ofereciam CINCO curvas de
    feedback e não a sexta — `linear_medio`, a firmeza constante. As cinco vêm
    cravadas da página; a sexta só era acrescentada quando `_tabela_da_curva`
    devolvia a tabela de feedback, isto é, **só com o gatilho já em "Curva de
    força"**. Oferecer cinco das seis irmãs é um buraco arbitrário: para
    alcançar a sexta ela teria de trocar o modo antes, e nada na tela dizia.

    `_tabela_da_curva` CONTINUA COMO ESTÁ, e tem de continuar: quem a chama para
    RECONHECER uma curva salva (`_pronto_da_curva`) precisa da tabela do modo
    gravado, e cair no feedback ali nomearia uma curva de vibração com o nome de
    outra tabela.
    """
    presets, rotulos = _tabela_da_curva(modo)
    if rotulos:
        return presets, rotulos
    return _tabela_da_curva(MODO_DA_CURVA)


def _curvas_que_a_pagina_esqueceu(modo: str) -> list[str]:
    """As curvas que o PRODUTO tem naquele modo e a página não oferece.

    A DÍVIDA QUE ISTO PAGA, medida em 03/09/2026 lendo os dois lados:

    * `linear_medio` ("Linear médio", `[4]` dez vezes, a firmeza constante) existe em
      `FEEDBACK_POSITION_PRESETS` desde antes desta aba, a GUI estável a
      oferece, e a lista `PRONTOS` do gerador — digitada à mão — a esqueceu;
    * as CINCO de `VIBRATION_POSITION_PRESETS` (pulso crescente, machine gun,
      galope, senoide, vibração final) nunca chegaram à tela nova: o campo só
      carregava as de feedback.

    Seis curvas do produto fora do alcance de quem clica, e nenhuma régua
    acusava — o gerador reprova um rótulo que o produto NÃO tem, e nunca um que
    o produto tem e a tela esqueceu.

    O RÓTULO É O DO PRODUTO, letra por letra (`FEEDBACK_POSITION_LABELS` /
    `VIBRATION_POSITION_LABELS`). Não invento texto de tela: estas palavras já
    são as que a aba Gatilhos da GUI estável mostra a ela.

    `custom` FICA DE FORA porque a página já o tem, com o nome que O usuário aprovou
    ("— Nenhum —", contra o "Personalizar" do motor). Acrescentá-lo daria duas
    opções para a mesma chave, com dois nomes.

    A TABELA É A QUE O CAMPO MOSTRA, e não a do modo — 03/09/2026. Ver
    `_tabela_que_o_campo_mostra`: com o gatilho em `Desligado` esta função
    devolvia lista vazia, e a sexta curva de feedback ficava fora dos oito
    campos até alguém trocar o modo primeiro.
    """
    _, rotulos = _tabela_que_o_campo_mostra(modo)
    if not rotulos:
        return []
    ja_tem = _valores_cravados_do_pronto()
    return [chave for chave in rotulos
            if chave != "custom" and chave not in ja_tem]


def html_das_opcoes_de_pronto(modo: str = MODO_DA_CURVA) -> str:
    """As opções do campo "Efeito pronto": o desenho + o produto + os efeitos DO USUÁRIO."""
    _, rotulos = _tabela_que_o_campo_mostra(modo)
    linhas = [_opcoes_cravadas_do_pronto()]
    if modo == MODO_DA_VIBRACAO:
        cravadas = _opcoes_cravadas_do_pronto().split("\n")
        de_feedback, _ = _tabela_da_curva(MODO_DA_CURVA)
        linhas = [uma for uma in cravadas
                  if not any(f'value="{c}"' in uma for c in de_feedback)]
    for chave in _curvas_que_a_pagina_esqueceu(modo):
        linhas.append(f'                <option value="{chave}">'
                      f'{_escapar(str(rotulos[chave]))}</option>')
    meus = meus_efeitos()
    if meus:
        linhas.append(f'                <option disabled>'
                      f'{SEPARADOR_DOS_MEUS}</option>')
        for nome in sorted(meus):
            linhas.append(
                f'                <option value="{PREFIXO_DO_MEU}{_escapar(nome)}">'
                f'{_escapar(nome)}</option>')
    return "\n".join(linhas)


# emite o chip sem `--plastico`. Esta aba continua não dependendo disso: ela lê

CLASSE_DO_CHIP = "cabeca"

#: * logo o `--plastico` ficava num elemento cujo alvo era `texto`, e
CAMPO_DO_CHIP = "chip-do-controle"

#: O ALVO É `plastico`, e ele é o único que escreve `--plastico`: os outros
#: `.chip.plastico{border-color:var(--plastico, var(--border-forte))}` e a queda
CAMPO_DO_PLASTICO = "plastico"

ALVO_DO_PLASTICO = "plastico"

PONTO = ' <span class="pt">•</span> '


def cor_de_borda(tinta: str) -> str:
    """A tinta da zona quando ela É cor, e `""` quando o mapa não tem hex.

    O QUE O MAPA DO USUÁRIO RESPONDE, e são TRÊS formas — `gerar_cores_do_dualsense.
    _tinta` é quem as escreve, a partir de `docs/data/cores-do-dualsense.csv`:

        `#rrggbb`                 o hexadecimal daquela zona
        `url(#casca-<modelo>)`    a casca partida em duas, num gradiente
        `url(#hachura-sem-hex)`   a AUSÊNCIA DECLARADA — *"o acabamento não cabe
                                  num hexadecimal (iridescente, metálico,
                                  camuflado, arte)"*

    Só a primeira é uma cor. E a terceira não é caso raro: **OITO dos vinte e
    oito modelos** respondem hachura na `casca-solida`, que é justamente a zona
    do chip — Grey Camouflage, Chroma Teal, Chroma Indigo, Chroma Pearl, Ghost
    of Yōtei, Marathon, Genshin Impact e 007 First Light.

    MEDIDO NO WEBKIT DESTA MÁQUINA, 03/09/2026, com a regra que o `topo.html`
    declara (`.chip.plastico{border-color:var(--plastico, var(--border-forte))}`)::

        --plastico:#ae335a                → rgb(174, 51, 90)   a cor do plástico
        --plastico ausente                → rgb(98, 114, 164)  a QUEDA declarada
        --plastico:url(#hachura-sem-hex)  → rgb(139, 233, 253) a cor do TEXTO

    A terceira linha é o defeito, e ele é do CSS e não do desenho: uma `var()`
    que resolve para algo que a propriedade não aceita fica **inválida no tempo
    de valor computado**, e nesse caso o navegador NÃO usa a queda escrita ao
    lado — ele volta ao valor herdado, que numa `border-color` é o
    `currentColor`. O chip vestia a cor da LETRA e a dica ao lado dizia, com
    todas as letras, que aquela era a cor do plástico daquele aparelho.

    A REGRA É A DO USUÁRIO: *sem cor lida, sem cor na tela.* Sem `--plastico` a queda
    do `topo.html` vale, a borda fica neutra, e a dica diz por quê.

    O TESTE DO `#` NÃO É NOVO: é o mesmo que `gerar_cores_do_dualsense.legivel`
    já usa, pela mesma razão — *"gradiente, hachura: não são cor"*. Não há
    tabela de cor aqui; quem sabe a cor continua sendo o CSV dela.
    """
    tinta = (tinta or "").strip()
    return tinta if tinta.startswith("#") else ""


def miolo_do_chip(jogador: int, nome: str, via: str,
                  conectado: bool = True) -> str:
    """O texto do chip: `P1 • White • USB`, e cada pedaço só entra se existir."""
    if not conectado:
        return f"P{jogador}{PONTO}Desconectado"
    pedacos = [f"P{jogador}"]
    if nome:
        pedacos.append(nome)
    if via:
        pedacos.append(via)
    return PONTO.join(pedacos)


def a_pagina_recebe_a_cor_por_endereco() -> bool:
    """A página PUBLICADA já tem onde receber a cor por endereço?

    ELA EXISTE PARA NÃO APAGAR A BORDA NA TELA DO USUÁRIO. O desenho de hoje pôs o
    `--plastico` no embrulho, com `data-campo="plastico"`; a página que o
    `WebView` renderiza AGORA não o tem — ela só recebe o chip inteiro pelo alvo
    `html`. Um pacote que escrevesse só no endereço novo deixaria as duas
    colunas dela com a borda neutra até o `--publicar 03`, que é ato dela.

    Medido em 03/09/2026, com a página publicada e um Nova Pink na mesa: a
    borda saía `rgb(68, 71, 90)` — a queda do tema — em vez de
    `rgb(227, 91, 140)`.

    ELA SE APOSENTA SOZINHA. No dia em que a bancada virar produto, o endereço
    passa a existir e este ramo deixa de correr. É a mesma forma de
    `_lugares_que_o_desenho_da_por_vazios` e `_casas_cravadas`: o pacote
    pergunta à PÁGINA o que ela sabe receber, em vez de presumir.
    """
    return CAMPO_DO_PLASTICO in _enderecos_da_pagina()


def chip_do_controle(jogador: int, nome: str, via: str, plastico: str,
                     conectado: bool = True, cor_no_chip: bool = False) -> str:
    """O `<span>` do cabeçalho da coluna, com endereço e sem cor inventada.

    `plastico` é o HEX JÁ RESOLVIDO, e não o *slug*, de propósito: o gerador
    resolve por `monta.cor_da_zona`, que **levanta** num colorway que o desenho
    não tem (é portão, e está certo em levantar); o pacote resolve por
    `_cor_do_plastico`, que devolve `""` — derrubar a pintura da aba por causa
    de um modelo novo seria trocar uma borda que falta por uma tela congelada.
    A política de resolução é de quem chama; a MARCAÇÃO é daqui, e é ela que não
    pode divergir.

    A COR NÃO SAI DAQUI NO DESENHO — 03/09/2026, e é a mudança desta frente. O
    `--plastico` subiu para o EMBRULHO (:func:`_cabeca_do_controle`), que tem
    endereço e alvo próprios; este `<span>` é o miolo que o alvo `html` refaz.
    O parâmetro `plastico` fica porque é ele que decide A DICA, e a dica tem de
    saber separar as duas ausências. Quem julga o que é hex é
    :func:`cor_de_borda`, que recusa o que o mapa dela responde quando não há
    hex. A borda não some: `topo.html` declara
    `.chip.plastico{border-color:var(--plastico, var(--border-forte))}`, com a
    queda já escrita.

    `cor_no_chip` É A PONTE ATÉ O `--publicar 03`, e só o PACOTE a levanta —
    ver :func:`a_pagina_recebe_a_cor_por_endereco`. A página que ela vê hoje não
    tem o endereço da cor; enquanto não tiver, o produto continua mandando a cor
    dentro do chip, como sempre mandou. O DESENHO nunca a levanta: ali a cor tem
    de estar no embrulho, ou a régua a acusa — e com razão, porque num arquivo
    estático ninguém a reescreve.

    **E A DICA ACOMPANHA A COR — 03/09/2026.** Ela dizia *"a borda é a cor do
    plástico"* nos TRÊS casos, e nos dois últimos era mentira: sem hex a borda é
    a neutra do tema, não o plástico de ninguém. São duas ausências diferentes, e
    a tela tem de saber dizer qual é qual — porque uma se conserta lendo o
    aparelho e a outra não se conserta:

        o mapa RESPONDEU e não é cor  o acabamento não cabe num hexadecimal
                                      (:func:`cor_de_borda`, oito dos 28 modelos)
        ninguém leu a cor             pelo rádio ela pode não chegar nunca, hoje

    É a metade que faltava da regra de produto: *sem cor lida, sem cor na tela* — e,
    quando não há, dizer POR QUE não há.

    **A SEGUNDA AUSÊNCIA PAROU DE SE EXPLICAR — FRASES-E-DICAS-02, 13/09/2026.**
    A dica de quem ninguém leu confessava que a cor ainda não tinha sido lida:
    confissão sobre um estado nosso numa dica flutuante, e a ordem de 13/09
    a tira da tela. Ela diz só o nome — e, sem nome, o `<span>` não tem dica.
    A do acabamento fica: ela diz o que o modelo É, não o que nós não fizemos.
    """
    cor = cor_de_borda(plastico)
    classe = "chip plastico" if conectado else "chip vazio"
    if not conectado:
        dica = SEM_APARELHO_AQUI
    elif cor:
        dica = (f"{nome} — a borda é a cor do plástico" if nome
                else "A borda é a cor do plástico deste controle.")
    elif plastico:
        dica = (f"{nome} — o acabamento deste modelo não cabe num hexadecimal, "
                f"e a borda fica neutra" if nome else
                "O acabamento deste modelo não cabe num hexadecimal, e a borda "
                "fica neutra.")
    else:
        dica = nome
    estilo = f' style="--plastico:{cor}"' if cor_no_chip and cor else ""
    titulo = f' title="{dica}"' if dica else ""
    return (f'<span class="{classe}"{estilo}{titulo}>'
            f"{miolo_do_chip(jogador, nome, via, conectado)}</span>")


def _cabeca_do_controle(jogador: int, nome: str, via: str, plastico: str,
                        conectado: bool = True) -> str:
    """O cabeçalho INTEIRO da coluna: o embrulho que veste a cor e o miolo.

    ELE É PRIVADO, e o nome diz um fato: **só o gerador monta este elemento**. O
    produto escreve nos dois endereços que ele deixa; nunca refaz a `.cabeca`.
    Público, ele seria uma promessa ao produto sem chamador em produção — e o
    `portao_a_casa_sabe_e_o_produto_nao_faz` acusa isso, com razão: os dez
    `interface/abaNN.py` são BANCADA e saem da conta pela poda dele.

    MORA AQUI E NÃO NO GERADOR porque a MARCAÇÃO tem um dono só. Se o desenho a
    escrevesse por conta própria, a estrutura que ele emite e a que
    :func:`seletor_do_chip` procura divergiriam no primeiro dia em que alguém
    mexesse numa só — e o produto passaria a escrever no lugar errado, calado.

    DOIS ELEMENTOS, DOIS ENDEREÇOS, e a divisão é o ponto:

        .cabeca   `data-campo="plastico"`  alvo `plastico`  → a COR do aparelho
          span    `data-campo="chip-do-controle"` alvo `html` → o CHIP inteiro

    Só o gerador emite esta função — o produto escreve nos dois endereços que
    ela deixa. Aninhá-los é o que permite as duas escritas conviverem: o selo do
    embrulho fica FORA do `innerHTML` que o miolo compara, e o selo do miolo fica
    no elemento que o escreve. Com a cor dentro do miolo (como era até hoje) uma
    das duas tinha de ser sacrificada, e a sacrificada era a cor.

    O EMBRULHO TEM ENDEREÇO NAS QUATRO COLUNAS, inclusive nas vazias, e isso é
    deliberado: a página é estática e o piloto não cria endereço. Sem ele, o dia
    em que um controle entra no P3 a coluna mostra o nome do plástico e uma borda
    neutra — a cor não teria por onde chegar. Onde não há leitura o produto
    escreve o vazio, que APAGA a variável.
    """
    cor = cor_de_borda(plastico) if conectado else ""
    estilo = f' style="--plastico:{cor}"' if cor else ""
    return (f'<div class="{CLASSE_DO_CHIP}" data-campo="{CAMPO_DO_PLASTICO}"'
            f' data-hef-alvo="{ALVO_DO_PLASTICO}"{estilo}>'
            f'<span data-campo="{CAMPO_DO_CHIP}" data-hef-alvo="html">'
            f"{chip_do_controle(jogador, nome, via, plastico, conectado)}"
            f"</span></div>")


def _cor_do_plastico(slug: str) -> str:
    """A TINTA da casca daquele modelo, como o mapa dela a escreve — ou `""`."""
    if not slug:
        return ""
    try:
        import monta

        # dela não têm hexa amostrado e devolvem `url(#hachura-sem-hex)`, que
        return str(monta.cor_de_css(slug))
    except (Exception, SystemExit):
        return ""


def _casa_na_mesa(ctx: Contexto, uniq: str) -> dict[str, Any]:
    """A entrada da MESA daquele controle — a mesma que a FITA DO TOPO desenha."""
    for m in ctx.mesa:
        if str(m.get("uniq") or "") == uniq:
            return m
    return {}


def seletor_do_chip(pref: str) -> str:
    """O endereço de bloco do cabeçalho daquela coluna."""
    return f'[data-controle="{pref}"] [data-campo="{CAMPO_DO_CHIP}"]'


def _numero_da_posicao(pref: str) -> int:
    """`p3` → 3. O número do lugar VAZIO, que é posição e não identidade."""
    digitos = "".join(ch for ch in pref if ch.isdigit())
    return int(digitos) if digitos else 0


def _identidade_viva(ctx: Contexto, c: dict[str, Any]) -> tuple[int, str, str, str]:
    """`(jogador, nome, via, plástico)` de um controle que está na mesa AGORA."""
    from . import VIA_DO_TRANSPORTE, identidade_de

    casa = _casa_na_mesa(ctx, str(c.get("uniq") or ""))
    via = str(casa.get("via")
              or VIA_DO_TRANSPORTE.get(str(c.get("transport") or "").lower(), ""))
    # `identidade_de` É O DONO DO NOME NA TELA, e ele já sabe que `"Não sei"`
    # o transporte já tem lugar próprio, então a queda vira ausência.
    nome = identidade_de(c, ctx.mesa)
    if nome in ("—", via):
        nome = ""
    jogador = casa.get("jogador")
    if not isinstance(jogador, int) or isinstance(jogador, bool):
        jogador = _numero_da_posicao(str(casa.get("pref") or ""))
    return jogador, nome, via, _cor_do_plastico(str(casa.get("cor") or ""))


def _cabecalho_vivo(ctx: Contexto, c: dict[str, Any]) -> tuple[str, str]:
    """`(chip, cor)` de um controle que está na mesa AGORA — de UMA leitura.

    Os dois valores vão para endereços diferentes (o miolo pelo alvo `html`, a
    cor pelo alvo `plastico`) e por isso saem juntos daqui: lidos em duas
    chamadas, `_identidade_viva` podia responder duas mesas no mesmo tique — e a
    coluna vestiria a borda de um controle com o nome de outro, que é a família
    de defeito desta frente.

    A COR VAI PENEIRADA por :func:`cor_de_borda`, e não crua: em oito dos 28
    modelos o mapa dela responde a hachura do SEM-HEX, que não é cor. Escrevê-la
    em `--plastico` deixa a `var()` inválida no tempo de valor computado, e a
    borda vira o `currentColor` — o chip vestindo a cor da LETRA com a dica ao
    lado dizendo que aquela é a cor do plástico. Vazio APAGA a variável, e a
    queda do `topo.html` assume.
    """
    identidade = _identidade_viva(ctx, c)
    chip = chip_do_controle(
        *identidade, cor_no_chip=not a_pagina_recebe_a_cor_por_endereco())
    return chip, cor_de_borda(identidade[3])


def _chip_do_lugar_vazio(pref: str) -> str:
    """O chip de um lugar sem aparelho: a posição e o estado, e mais nada."""
    return chip_do_controle(_numero_da_posicao(pref), "", "", "", conectado=False)


@registrar("03-gatilhos.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    """Endereço → valor, por controle da mesa. E a caixa de ajustes, em bloco."""
    specs = _specs()
    p = perfil.ativo(ctx.state.get("active_profile"))
    tem_endereco = _enderecos_da_pagina()

    _o_rascunho_e_deste_perfil(perfil.nome_do_ativo(ctx.state))
    _o_rascunho_e_de_quem_esta_na_mesa(
        {_chave_do_rascunho(str(c.get("uniq") or ""), "")[0] for c in ctx.conectados})

    pref_de = {str(m.get("uniq") or ""): str(m.get("pref") or "") for m in ctx.mesa}

    colunas: dict[str, dict[str, Any]] = {}
    blocos: dict[str, str] = {}
    pintados = 0
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        entradas = c.get("inputs") or {}
        l2, r2 = entradas.get("l2_raw"), entradas.get("r2_raw")

        cfgs = {sig: _o_que_o_controle_recebe(p, uniq, disco)
                for sig, disco in LADOS.items()}
        deste = {sig: _do_lado(cfgs[sig], specs) for sig in LADOS}

        chip, plastico = _cabecalho_vivo(ctx, c)
        col: dict[str, object] = {
            CAMPO_DO_CHIP: chip,
            CAMPO_DO_PLASTICO: plastico,
            "l2-raw": l2, "r2-raw": r2,
            "l2-pct": round((l2 or 0) / 255 * 100),
            "r2-pct": round((r2 or 0) / 255 * 100),
        }
        for sig, d in deste.items():
            col[f"modo-{sig}"] = d["modo"]
            col[f"modo-chave-{sig}"] = d["modo-chave"]
            col[f"{PREFIXO_DA_DICA_DO_MODO}{sig}"] = descricao_do_modo(
                str(d["modo-chave"]))
            col[f"{PREFIXO_DA_DICA_DO_PRONTO}{sig}"] = dica_do_pronto(
                str(d["modo-chave"]))
            meu_nome = _meu_efeito_que_casa(LADOS[sig], cfgs[sig])
            col[f"pronto-{sig}"] = (f"{PREFIXO_DO_MEU}{meu_nome}" if meu_nome
                                    else d["pronto"])
            if d.get("curva"):
                col[f"curva-{sig}"] = d["curva"]
                col[f"curva-pct-{sig}"] = d["curva-pct"]
        colunas[uniq] = col
        pintados += sum(1 for k in col if k in tem_endereco)
        blocos.update(_blocos_da_coluna(pref_de.get(uniq) or uniq, deste,
                                        editavel=True))

    ocupados = {str(m.get("pref") or "") for m in ctx.mesa}
    sem_ninguem = _do_lado({}, specs)
    for pref in sorted(_lugares_que_o_desenho_da_por_vazios() - ocupados):
        vazia = {f"modo-chave-{sig}": _sem_nada("modo", str(sem_ninguem["modo-chave"]))
                 for sig in LADOS}
        vazia.update({f"pronto-{sig}": _sem_nada("pronto", str(sem_ninguem["pronto"]))
                      for sig in LADOS})
        vazia.update({f"{pref_}{sig}": SEM_APARELHO_AQUI
                      for pref_ in (PREFIXO_DA_DICA_DO_MODO,
                                    PREFIXO_DA_DICA_DO_PRONTO)
                      for sig in LADOS})
        # colunas` do piloto, e com ela some o `data-conectado="nao"` que segura
        vazia[CAMPO_DO_CHIP] = _chip_do_lugar_vazio(pref)
        # `--plastico` do embrulho (`escrever` chama `removeProperty`), que é o
        vazia[CAMPO_DO_PLASTICO] = ""
        colunas[pref] = vazia
        pintados += sum(1 for k in vazia if k in tem_endereco)

    # depende o `data-conectado="nao"` do piloto. Com um controle só na mesa,
    for pref in sorted(_todos_os_lugares_da_pagina() - ocupados):
        blocos.update(_blocos_da_coluna(
            pref, dict.fromkeys(LADOS, sem_ninguem)))
        # emitir uma coluna custaria o `data-conectado="nao"` que segura o
        if CAMPO_DO_CHIP not in (colunas.get(pref) or {}):
            blocos[seletor_do_chip(pref)] = _chip_do_lugar_vazio(pref)

    return {
        "colunas": colunas,
        "blocos": blocos,
        # `perfil` saiu em 13/09/2026: o chip é das dez, dono `pacotes.topo()`.
        "sem_dono": {},
        "cobertura": {"pintados": pintados, "sem_dono": len(SEM_DONO),
                      "sem_endereco": sum(1 for col in colunas.values()
                                          for k in col if k not in tem_endereco),
                      "blocos": len(blocos),
                      # `_casas_cravadas`.
                      "casas_cravadas": sum(_casas_cravadas().values()),
                      "caixa_cresce": sum(_a_caixa_cresce().values())},
    }


def _blocos_da_coluna(pref: str, deste: dict[str, dict[str, Any]],
                      editavel: bool = False) -> dict[str, str]:
    """Os quatro blocos de uma coluna: as duas caixas de ajuste e as duas listas.

    O SELETOR É CSS, e ele tem de achar UM elemento só: o piloto usa
    `document.querySelector` (o primeiro que casar). `[data-controle="p1"]
    .ajustes.e` é único na página; `.ajustes.e` sozinho acharia o do P1 e
    escreveria a caixa do P3 nele.

    A LISTA DO "EFEITO PRONTO" É DO LADO, e não da coluna — 03/09/2026. Ela era
    uma só para os oito campos; agora ela depende do MODO daquele gatilho,
    porque as curvas de vibração só existem em `MultiPositionVibration` (ver
    `html_das_opcoes_de_pronto`). A biblioteca do usuário continua igual nos oito: o
    que muda é a metade que vem do motor.

    E A LISTA DE "MODO" ENTROU — 03/09/2026, e ela é IGUAL nos oito: os 19
    rótulos não dependem de coluna nem de lado. Ela vem em bloco pela mesma
    razão que a de cima: o rótulo tem dono no produto, e enquanto a página
    publicada carregar a cópia digitada, é o bloco que põe a palavra de produto na
    tela sem esperar publicação. Ver `html_das_opcoes_de_modo`.

    O BLOCO NÃO DESFAZ A ESCOLHA, e a ordem é o que garante: o piloto pinta os
    BLOCOS antes dos CAMPOS (`hefesto_vivo`, passo 0 contra passo 2), então o
    `modo-chave-<lado>` reescolhe a opção depois de a lista ser trocada. É o
    mesmo caminho que o `select.pronto` já percorre desde 02/09.
    """
    fora: dict[str, str] = {}
    if not pref:
        return fora
    for sig, d in deste.items():
        fora[f'[data-controle="{pref}"] select.modo[data-lado="{sig}"]'] = (
            html_das_opcoes_de_modo())
        fora[f'[data-controle="{pref}"] .ajustes.{sig}'] = html_dos_ajustes(
            sig, list(d.get("ajustes") or []), _cabem_no_desenho(sig),
            editavel=editavel)
        fora[f'[data-controle="{pref}"] select.pronto[data-lado="{sig}"]'] = (
            html_das_opcoes_de_pronto(str(d.get("modo-chave") or MODO_DA_CURVA)))
    return fora


from . import gesto  # noqa: E402


def _uniq(o: dict[str, Any]) -> str:
    """O `uniq` da coluna onde o usuário clicou. Vazio = recusa, nunca "todos".

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
            f"não há controle no lugar {lugar.upper()}. Ligue um aqui e ele "
            f"pega o efeito.")
    raise ValueError(f"{gesto_}: o clique não disse em qual controle")


def _lado(o: dict[str, Any]) -> str:
    """`e`/`d` da tela → `left`/`right` do daemon, pela tradução que já existe."""
    sigla = str(o.get("lado") or "").strip()
    if sigla not in LADOS:
        raise ValueError(
            f"o clique não disse qual gatilho (veio {sigla!r}; espero 'e' ou 'd'). "
            f"É o `data-lado` do campo de escolha.")
    return LADOS[sigla]


def _escolhido(o: dict[str, Any]) -> str:
    """O que o usuário escolheu no campo, sem inventar nada quando não veio."""
    return str(o.get("modo") or o.get("v") or o.get("valor") or "").strip()


def _desfecho(resposta: Any) -> tuple[bool, str, dict[str, Any] | None]:
    """`(ok, motivo, corpo)` de uma resposta da ponte, que tem TRÊS formas.

    `trigger_set` devolve `bool`, `trigger_set_checked` devolve `(ok, motivo)` e
    `trigger_set_detalhado` devolve `(ok, motivo, corpo)`. Normalizar aqui é o
    que permite o gesto RECUSAR DIZENDO sem depender de qual das três a ponte
    entregou — e um `ok, motivo = ...` rígido rebentaria com um `TypeError` na
    primeira troca de porta, que é erro sobre erro.

    O CORPO DEIXOU DE SER JOGADO FORA — 03/09/2026, e era a terceira mentira
    desta aba. Esta função reduzia a resposta a `(ok, motivo)`, e com isso três
    desfechos diferentes chegavam à tela como o mesmo silêncio de sucesso:

    * `{status: ok, aplicado_em: [], guardado_em: []}` — **nada aconteceu**, e é
      a rota que a bancada mediu em 23/08 com a aba dizendo "aplicado";
    * `guardado_em` com alguém — a intenção ficou guardada e o gatilho dela
      **não mudou**;
    * `status: ok` COM `motivo` — a recusa que vem dentro de uma resposta
      bem-sucedida (`ipc_bridge._recusa_no_corpo`), que `trigger_set_detalhado`
      entrega com `ok=True`.

    `None` quer dizer *"não há corpo a ler"* — a ponte antiga, ou o dublê da
    régua. Nesse caso quem decide continua sendo o `ok`, exatamente como antes.
    """
    if isinstance(resposta, tuple):
        motivo = resposta[1] if len(resposta) > 1 else ""
        corpo = resposta[2] if len(resposta) > 2 else None
        return (bool(resposta[0]), str(motivo or ""),
                corpo if isinstance(corpo, dict) else None)
    return bool(resposta), "", None


def _na_lingua_da_tela(motivo: str, modo: str) -> str:
    """A recusa do daemon na língua dos rótulos desta aba. Sem dono novo.

    O TRADUTOR JÁ EXISTIA E NINGUÉM O CHAMAVA. `triggers_actions.
    humanizar_erro_gatilho` (`app/actions/triggers_actions.py`) é a HARM-19,
    escrita e testada para a aba Gatilhos da GUI estável: o daemon fala a língua
    do `core/trigger_effects` — *"end (3) deve ser > start (5)"* — e ela devolve
    *"Fim (3) precisa ser maior que Início (5)"*, com os MESMOS rótulos que o
    `<select>` desta tela mostra, porque tira os dois do mesmo `spec.params`.
    Conferido em 02/09/2026: zero pacotes da interface nova a chamavam, e a
    recusa chegava CRUA à tela do usuário.

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
            "modo: não consegui ler os ajustes deste modo, e aplicá-lo assim "
            "deixaria o gatilho solto. Nada foi mandado.")
    spec = specs.get_spec(nome)
    if spec is None:
        raise ValueError(
            f"modo: {nome!r} não é um dos 19 modos do produto "
            f"(`app/actions/trigger_specs.PRESETS`).")
    return list(specs.preset_to_positional_params(spec, {}))


def _curva(chave: str) -> tuple[list[int], str]:
    """`(as dez intensidades, o modo em que elas existem)` daquele efeito pronto.

    O MODO SAI DA TABELA EM QUE A CURVA MORA, e não de uma constante: as duas
    tabelas do produto não compartilham chave nenhuma
    (`rampa_crescente`… contra `pulso_crescente`…), então saber DE ONDE a curva veio
    é saber em que modo ela existe. Antes desta linha o gesto mandava sempre
    `MultiPositionFeedback`, e as cinco curvas de vibração não tinham como ser
    aplicadas nem que a lista as oferecesse.
    """
    tp = _prontos()
    if tp is None:
        raise RuntimeError(
            "efeito pronto: não consegui ler as curvas. Nada foi mandado.")
    for modo_, resolver in ((MODO_DA_CURVA, tp.resolve_feedback_preset),
                            (MODO_DA_VIBRACAO, tp.resolve_vibration_preset)):
        valores = resolver(chave)
        if valores:
            return list(valores), modo_
    raise ValueError(
        f"efeito pronto: {chave!r} não é uma curva do produto "
        f"(`profiles/trigger_presets.FEEDBACK_POSITION_PRESETS` nem "
        f"`VIBRATION_POSITION_PRESETS`).")


def _params_da_curva(modo_: str, curva: list[int]) -> list[int]:
    """As dez posições postas nos parâmetros `pos_*` do modo, o resto no padrão."""
    specs = _specs()
    fora = _padroes(modo_)
    if specs is None:
        return fora
    spec = specs.get_spec(modo_)
    posicoes = [i for i, q in enumerate(spec.params) if q.name.startswith("pos_")]
    for i, valor in zip(posicoes, curva, strict=False):
        fora[i] = int(valor)
    return fora


#: `reenviar`, que somava com ele os desfechos dos DOIS gatilhos da coluna, e
#: saiu com o botão. Fica o primeiro, a D-17: o `_aplicar` soma o recibo do
#: guardou*. A constante fica onde subiu, acima do chamador: quem lê `_aplicar`
_E_TAMBEM = " · "


def _aplicar(p: Any, lado: str, modo_: str, params: list[int],
             uniq: str, ctx: Contexto | None = None,
             guardar: bool = True, *,
             lembrar_em: list[str] | None = None) -> tuple[bool, str, str]:
    """Manda o efeito ao daemon pela porta CERTA, e a certa depende do modo.

    "DESLIGADO" É `trigger.reset`, E NÃO `trigger.set` COM `Off` — a R-19. O
    `_handle_trigger_set` do daemon termina em `mark_manual_trigger_active`:
    mandar `Off` por ali ARMA a trava que pausa a troca automática de perfil,
    e o `trigger.reset` faz o oposto. Está escrito com todas as letras em
    `triggers_actions._reset_trigger`: *"o botão que a usuária usa para 'voltar
    ao normal' era mais um jeito de PAUSAR a troca automática de perfil, sem
    nada na tela dizendo isso"*.

    A FUNÇÃO EXISTE PORQUE HÁ TRÊS CHAMADORES — o `modo`, o `pronto` quando
    aplica um efeito dela, e a régua. Escrito três vezes, o `if chave == "Off"`
    some num deles no dia em que alguém mexer, e a trava volta calada.

    E ELA É O CHOKE POINT DO RASCUNHO — 03/09/2026. Toda escrita no gatilho
    passa por aqui, então é aqui que a tela aprende o que foi aplicado. É o
    lugar da GTK: `_persist_params_to_draft` é chamado ANTES de todo envio
    (`triggers_actions.py`), pela mesma razão — quatro chamadores gravando
    o draft por conta própria seria o quarto que esquece.

    O RASCUNHO SÓ RECEBE O QUE O DAEMON ACEITOU. Guardar antes faria a tela
    afirmar um efeito que o aparelho recusou — trocaria a mentira de hoje (a
    escolha some) por uma pior (a escolha fica, e é falsa).

    E ELE DEVOLVE O RECIBO — 04/09/2026, a D-01. A terceira casa é a frase de
    SUCESSO daquele envio, e ela sai daqui porque é aqui que o CORPO do daemon
    existe: montá-la nos quatro chamadores seria o quarto que esquece, que é o
    mesmo argumento pelo qual o rascunho já mora nesta função.

    **A TERCEIRA CASA DEIXOU DE SER O RECIBO E PASSOU A SER A NOTÍCIA —
    06/09/2026, a `03-Q4` dela.** Perguntada com as quatro formas lado a lado,
    o usuário escolheu *"O campo pisca em verde"*, e a opção que descrevia o que esta
    função fazia até aqui — a tarja verde no cartão com a frase do recibo — foi
    a que ela recusou, com estas palavras: *"nenhuma palavra nova entra na
    tela"*. A regra que isso escreve, e ela vale para a aba inteira:

        *quando o gesto só repete o que ela acabou de fazer, a tela pisca;
        quando ele tem NOTÍCIA, a tela fala.*

    Então a terceira casa passa a responder **"o que ela precisa saber e não
    está vendo"**, e são dois casos só:

    * aparelho recebeu **e** perfil guardou → `""`. A piscada do campo
      (`hefesto_vivo.MS_DA_PISCADA`) é a resposta inteira, e o cartão fica
      calado. Um `""` cai no MESMO ramo de um `{}` porque
      `_deu_certo_dizendo` testa `bruto.strip()` antes de aceitar a frase —
      conferido no fonte do piloto, não suposto.
    * aparelho recebeu **e** o disco não guardou → as duas metades, somadas
      pelo :data:`_E_TAMBEM`, com o recibo NA FRENTE. É a `AS-DUAS-ABAS-FALAM-01`
      inteira, e ela não se desfaz aqui: é justamente por ela existir que o
      corte é entre *sucesso pleno* e *meio ato*, e não entre *sucesso* e
      *recusa*.

    **A ESCOLHA MORA NESTA FUNÇÃO, e não nos gestos**, pela razão de sempre:
    escrita nos quatro, o quarto é o que esquece — e o defeito seria mudo,
    porque um gesto que manda recibo a mais não quebra nada, só devolve à tela
    a palavra que o usuário mandou tirar. É o defeito de forma que esta casa pagou
    duas vezes em 05/09.

    **`_recibo` NÃO se apagou**, e continua dono da frase: o que mudou é QUANDO
    ele é chamado — só quando há uma segunda metade para prefixar.

    ``recibo_sempre`` SAIU EM 08/09/2026, COM O `reenviar`. Ele era a exceção e
    tinha um dono só: o reenvio decidia pelo **par** e não pelo lado, então
    pedia o recibo sempre e escolhia depois. Com o botão fora da tela por
    decisão de produto, o sinalizador ficou sem chamador — e um parâmetro que ninguém
    passa é um ramo que ninguém mede. Se a faixa de reenvio voltar, ele volta
    com ela; a razão está guardada na lápide. **Sem aquela porta, a frase da
    recusa perderia o nome do gatilho que
    FUNCIONOU** — medido: a régua `test_um_lado_que_recusa_nao_cala_o_outro`
    reprovou com a frase *"Gatilho esquerdo (L2): Rigid — end (3)… · "*, com o
    separador pendurado e o R2 sumido. É a cura TRG-01 de novo, pelo avesso.

    **E O RECIBO PASSOU A DIZER AS DUAS METADES — 06/09/2026, a decisão D-17**
    (a sprint `AS-DUAS-ABAS-FALAM-01`). Quando o
    efeito FOI para o aparelho e o DISCO não recebeu, a terceira casa sai como
    *«… aplicado · o efeito FOI para o aparelho, mas não consegui ABRIR o
    perfil …»*, somada pelo :data:`_E_TAMBEM`. Ela continua sendo a frase de
    SUCESSO — o canal é o `{"recado": …}` do verde de 6 s, e não o `RuntimeError`
    do laranja de 30 s, porque um gesto que fez o que prometeu no aparelho **não
    é recusa**. É a mesma escolha que `a06_navegacao._guardar_no_perfil` já
    tinha feito, com a razão escrita lá.

    E ELE PASSOU A GRAVAR NO PERFIL — 05/09/2026, a **decisão D2**
    (o registro «AS-TRES-DECISOES-DO-PERFIL-medidas-e-decididas» de 05/09/2026):
    *"persistência no clique em toda parte, com o rodapé como rede de
    segurança"*. O usuário pediu, com estas palavras: *"ao pular e sair configurando
    de aba em aba o perfil vai se lembrando de cada config de cada aba pra cada
    controle … e salvar se lembra disso quando eu for jogar o jogo e no dia
    seguinte"*.

    **O QUE FALTAVA, MEDIDO:** `controllers[uniq].triggers` não persistia por
    clique nenhum. O `_RASCUNHO` guardava o gatilho aplicado NESTA SESSÃO e o
    rodapé não o alcançava — `pacotes/rodape.py` não importa este módulo. Clicar
    `Rígido` no L2 e depois "Salvar Perfil" gravava o gatilho DE ONTEM, porque o
    rodapé monta o rascunho a partir do PERFIL NO DISCO. É o mesmo defeito que
    o reenvio nomeava pela outra ponta, antes de o botão sair da tela.

    **O RASCUNHO CONTINUA, e não é redundância:** ele é a memória entre o clique
    e o tique seguinte (500 ms), e é ele que impede a coluna de voltar ao valor
    velho enquanto o disco não chega. O disco é a memória do dia seguinte.

    **A GUARDA É A MESMA DO RASCUNHO** — `ok and _chegou_ao_aparelho(corpo)`.
    Gravar no perfil um efeito que o aparelho recusou seria a tela prometendo
    amanhã o que não fez hoje.

    ``guardar=False`` é para quem manda ao aparelho sem opinar pelo controle —
    hoje só o :func:`em_todos`, que escreve na seção GLOBAL e não pode criar um
    override por MAC. O sinalizador existe para que esse contrato continue
    verdadeiro sem que o ESCRITOR se multiplique: a gravação segue morando só
    aqui.

    ``lembrar_em`` É PARA QUEM MANDA EM BROADCAST — :func:`em_todos`, e é o
    único chamador. Com `uniq=""` o pedido vai para os controles todos (é o que
    a GTK faz com o alvo em "Todos": `triggers_actions._apply_trigger` passa
    `uniq=None`), e aí o `uniq` do envio não é endereço de ninguém — guardar o
    rascunho sob `""` criaria uma entrada que a poda de mesa
    (`_o_rascunho_e_de_quem_esta_na_mesa`) apaga no tique seguinte, e as quatro
    colunas voltariam ao valor do disco enquanto ele não chega. Passando os
    `uniq` de quem está na mesa, cada coluna lembra o que acabou de receber.
    **O padrão continua sendo `[uniq]`**, para que o choke point não se
    multiplique: quem grava o rascunho continua sendo só esta função.
    """
    if modo_ == "Off":
        ok, motivo, corpo = _desfecho(p.trigger_reset_detalhado(lado, uniq=uniq))
        params = []
    else:
        ok, motivo, corpo = _desfecho(
            p.trigger_set_detalhado(lado, modo_, params, uniq=uniq))
    nao_guardou = ""
    if ok and _chegou_ao_aparelho(corpo):
        for quem in (lembrar_em if lembrar_em is not None else [uniq]):
            _lembrar_o_aplicado(
                perfil.nome_do_ativo(ctx.state if ctx else None),
                quem, lado, {"mode": modo_, "params": params})
        if guardar:
            nao_guardou = _guardar_no_perfil(ctx, p, uniq, lado,
                                             {"mode": modo_, "params": params})
    ok, motivo = _conferir_o_desfecho(lado, modo_, ok, motivo, corpo, ctx, uniq)
    recibo = ""
    if nao_guardou:
        recibo = _recibo(lado, modo_, corpo, ctx, uniq)
    if nao_guardou:
        recibo = _E_TAMBEM.join((recibo, nao_guardou))
    return ok, motivo, recibo


def _guardar_no_perfil(ctx: Contexto | None, p: Any, uniq: str, disco: str,
                       cfg: dict[str, Any]) -> str:
    """Grava no perfil ATIVO o gatilho que acabou de chegar ao aparelho.

    :return: `""` quando gravou — e também quando não havia o que gravar, ou
        quando não há perfil ativo. A frase do que NÃO deu quando havia perfil
        NOMEADO e o arquivo não abriu. É a mesma assinatura de
        `a06_navegacao._guardar_no_perfil`, e usar a mesma não é gosto: são os
        dois únicos escritores de perfil por clique que não podem levantar.

    **SÓ O LADO QUE ELA TOCOU.** :func:`_com_os_gatilhos` recebe um dicionário
    de um item só, e o esquema faz o resto: `model_fields_set` decide o que é
    opinião do controle e o que herda a seção global do perfil
    (`profiles/manager._controllers_to_specs` lê os dois lados separados). Se
    este caminho escrevesse os DOIS, clicar `Rígido` no L2 gravaria um `Off`
    explícito no R2 e silenciaria o gatilho direito que o perfil dava a todo
    mundo — um efeito dela apagado por um clique no outro lado.

    **NÃO ABRIU O PERFIL, NÃO GRAVA — E NÃO LEVANTA.** São dois casos: não há
    `active_profile` (o `guardar` já explica esse na frase dele), ou o nome que
    o daemon publica não existe para ESTE leitor. O segundo não é hipótese: as
    réguas desta aba rodam com `active_profile` de mentira, e na máquina do usuário o
    daemon pode nomear um perfil que a pasta lida aqui não tem (apagado,
    renomeado, outra pasta). Nos dois, o gatilho FOI para o aparelho e o
    `_RASCUNHO` o segura na tela — levantar diria "não deu" sobre um efeito que
    ela está sentindo na mão. **Esta metade vale, e é ela que escolhe o CANAL:**
    o do `{"recado": …}` verde, nunca o do `RuntimeError` laranja.

    **NÃO ABRIU O PERFIL, NÃO FALA — CADUCOU EM 05/09/2026, decisão D-17**
    (*"as duas abas falam"*, dela). Até aqui esta função sumia neste ramo, e o
    argumento acima era usado para as duas coisas — mas ele é verdadeiro sobre
    o CANAL e falso sobre o SILÊNCIO. **A frase não diz "não deu": diz as duas
    metades** — *o aparelho recebeu · o perfil não guardou* —, e é o ramo irmão
    logo abaixo que já a escrevia. E o caso que justificava o silêncio é
    justamente o caso em que ela precisa saber: perfil apagado, renomeado ou
    noutra pasta quer dizer que **cada gatilho ajustado a partir dali morre na
    próxima troca de perfil**, com o produto SABENDO e não dizendo.

    **MAS A GRAVAÇÃO QUE FALHA FALA.** Perfil aberto e escrita recusada é a
    promessa de amanhã que não se cumpre — o defeito exato que a decisão D2 veio
    matar. A frase diz as duas metades: o aparelho recebeu, o perfil não
    guardou. Sem isso, ela descobriria a perda no dia seguinte, longe do clique.

    **E ELA AINDA FALA PELO CANAL DA RECUSA — declarado, não esquecido.** Os
    dois ramos desta função dizem as duas metades desde a D-17, mas por canais
    diferentes: o de ABRIR devolve frase (verde de 6 s) e o de GRAVAR levanta
    `RuntimeError` (laranja de 30 s). Alinhá-los é outra sprint, e ela precisa
    das réguas do outro ramo relidas uma a uma — a mesma divergência que a
    §5 da D-17 mede entre a aba 02 e a aba 06 e deixa declarada.

    O CAMINHO DE DISCO É O DO `guardar` — :func:`_gravar_so_o_gatilho`, e não
    `perfil.gravar_e_reaplicar`. A razão está medida lá: reaplicar o perfil
    inteiro acende de volta a barra de luz que ela desligou noutra aba.
    """
    nome = perfil.nome_do_ativo(getattr(ctx, "state", None)).strip()
    if not nome:
        return ""
    try:
        prof = perfil._com_o_src().load_profile(nome)
    except Exception:
        return (f"o efeito foi para o aparelho, mas não entrou no perfil "
                f"{nome}. Ele vale até você trocar de perfil.")
    try:
        novo = _com_os_gatilhos(prof, uniq, {disco: cfg})
        if novo is not None:
            _gravar_so_o_gatilho(novo, p)
    except Exception as erro:
        raise RuntimeError(
            f"o efeito foi para o aparelho, mas não entrou no perfil "
            f"{nome}. Ele vale até você trocar de perfil.") from erro
    return ""


_CAMPOS_DE_DESTINO = ("aplicado_em", "guardado_em")


def _fala_de_destino(corpo: dict[str, Any] | None) -> bool:
    """O corpo diz alguma coisa sobre ONDE a escrita foi parar?"""
    return isinstance(corpo, dict) and any(c in corpo for c in _CAMPOS_DE_DESTINO)


def _chegou_ao_aparelho(corpo: dict[str, Any] | None) -> bool:
    """O byte SAIU no fio para alguém — a pergunta que decide o rascunho."""
    if not _fala_de_destino(corpo):
        return True
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.ipc_bridge import destinos_da_aplicacao
    except Exception:
        return True
    aplicado, _ = destinos_da_aplicacao(corpo)
    return bool(aplicado)


def _como_a_janela_pergunta(ctx: Contexto | None, uniq: str) -> Any:
    """O `host` que `frase_do_desfecho` interroga, com o que ESTA aba sabe.

    A GTK lê três coisas do objeto da janela para explicar um "guardado": o
    alvo de edição, o mapa de conectados e o Modo Nativo. Esta aba SABE as três,
    e melhor do que a GTK — ela não tem alvo de edição, tem uma COLUNA POR
    CONTROLE, e a coluna clicada é o alvo sem ambiguidade nenhuma.

    POR QUE UM DUBLÊ E NÃO UMA SEGUNDA FRASE: `app/textos_de_aplicacao.py` é o
    dono único do vocabulário de aplicado/guardado/nada-aconteceu, e a D-9 diz
    com todas as letras por que ele é um só — *"para que trocá-lo seja uma
    linha, e não uma caçada por strings"*. Escrever aqui "guardado, vai valer
    quando…" seria a sexta cópia.

    OS TRÊS ATRIBUTOS SÃO OS DO CONTRATO, e não inventados:
    `_alvo_de_edicao` (o canônico de `app/alvo_de_edicao.py`),
    `_target_uniq_by_index` (o mapa que a aba Status recalcula do `state_full`)
    e `_modo_nativo_ligado` (o `native_mode` do mesmo `state_full`).
    """
    from hefesto_dualsense4unix.app.alvo_de_edicao import AlvoDeEdicao, EstadoDoAlvo

    conectados = list((ctx.conectados if ctx else []) or [])
    rotulo = ""
    for c in conectados:
        if str(c.get("uniq") or "") == uniq:
            # `player_slot` preenchido. Lendo cru, o secundário do co-op vinha
            rotulo = f"Controle {jogador_de(c) or '?'}"
            break

    class _Janela:
        def __init__(self) -> None:
            self._alvo_de_edicao = AlvoDeEdicao(EstadoDoAlvo.CONTROLE, uniq=uniq,
                                                label=rotulo or None)
            self._target_uniq_by_index = {i: str(c.get("uniq") or "")
                                          for i, c in enumerate(conectados)}
            self._modo_nativo_ligado = bool(
                (ctx.state if ctx else {}).get("native_mode"))

    return _Janela()


def _assunto(lado: str, modo_: str) -> str:
    """`"Gatilho esquerdo (L2): Rigid"` — o assunto de toda frase desta aba."""
    return f"{NOME_DO_LADO.get(lado, lado)}: {modo_}"


def _recibo(lado: str, modo_: str, corpo: dict[str, Any] | None,
            ctx: Contexto | None, uniq: str) -> str:
    """A frase de SUCESSO que vai ao CARTÃO daquele controle — a D-01 em ato.

    **O DEFEITO QUE ELA FECHA**, e ele é a queixa de origem desta casa: quando
    dava certo, a tela não dizia nada. O piloto imprimia `[gesto] … → aplicado`
    no terminal de quem lançou a janela, e quem clica não lê terminal. A decisão, 04/09/2026: *"No
    próprio cartão, como a recusa."*

    **NÃO HÁ CANAL NOVO AQUI, e é o ponto inteiro do conflito C-3.** A lista
    desta aba propunha *o campo que pisca*; o cartão é a mesma peça das outras
    quatro abas. Esta função só ESCREVE a frase — quem a leva ao cartão é o
    `hefesto_vivo._deu_certo_dizendo`, lendo o `recado` que o gesto devolve.

    **QUEM ESCOLHEU O CARTÃO FOI O PO, E A ESCOLHA CADUCOU — 06/09/2026.** Este
    parágrafo dizia *"o usuário escolheu o cartão"*, e a atribuição estava errada nas
    duas metades. Quem recusou o campo que pisca foi o PO, em 04/09, lendo a
    D-01 (*"no próprio cartão, como a recusa"*) como se ela fechasse a FORMA —
    o conflito C-3 de `2026-09-04-O-PO-DECIDE-as-54-e-os-sete-conflitos.md` é
    dele. Em 05/09 ELA respondeu a `03-Q4` vendo as quatro formas lado a lado e
    escolheu **o campo que pisca**, com *"nenhuma palavra nova entra na tela"*.
    A palavra de produto vence a leitura que o PO fez da palavra de produto.

    **O QUE ISSO FAZ COM ESTA FUNÇÃO: ela sai do caminho do sucesso pleno, e
    não do produto.** O `_aplicar` só a chama quando há uma segunda metade a
    prefixar (a `AS-DUAS-ABAS-FALAM-01`), e aí a frase abre pelo que ela fez.
    As três frases que contam esta história — esta, a do `_aplicar` e a do
    `hefesto_vivo._deu_certo_dizendo` — têm de dizer o mesmo, ou a próxima
    pessoa acredita na que ler primeiro.

    A FRASE É DO DONO DO ASSUNTO: `app/textos_de_aplicacao.frase_do_desfecho`,
    a mesma que a barra da GTK usa, com o CORPO do daemon como autoridade — é
    ela que sabe dizer *"aplicado em 2 controles"* em vez de um "aplicado" que
    não conta.

    **O CORPO QUE NÃO FALA DE DESTINO NÃO PASSA POR ELA**, e essa guarda é a
    lição de 04/09: o dublê da régua devolve `{}`, e `frase_do_desfecho` leria
    as duas listas vazias como *"nenhum controle recebeu"* — um recibo de
    SUCESSO afirmando que nada aconteceu. É a mesma armadilha que
    `_fala_de_destino` já documenta do outro lado, e a resposta é a mesma
    pergunta.
    """
    assunto = _assunto(lado, modo_)
    if not _fala_de_destino(corpo):
        return f"{assunto} aplicado"
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.textos_de_aplicacao import frase_do_desfecho

        return frase_do_desfecho(assunto, corpo, _como_a_janela_pergunta(ctx, uniq))
    except Exception:
        return f"{assunto} aplicado"


def _conferir_o_desfecho(lado: str, modo_: str, ok: bool, motivo: str,
                         corpo: dict[str, Any] | None,
                         ctx: Contexto | None, uniq: str) -> tuple[bool, str]:
    """Levanta quando o gatilho dela NÃO mudou, com a frase do dono do assunto.

    A DÍVIDA QUE ISTO PAGA, e ela é a feature 19 da medição de 03/09: *"dizer
    na tela o desfecho — aplicado, guardado para depois, nada aconteceu"*. A
    GTK escreve na barra de status a cada Aplicar, lendo o CORPO do daemon
    (`_toast_trigger` → `frase_do_desfecho`, ELO-MUDO-01/T3). O HTML jogava o
    corpo fora, e três desfechos diferentes viravam o mesmo nada.

    O CANAL É O `RuntimeError`, e é o único que esta tela tem: o piloto leva a
    frase de um `RuntimeError` ao CARTÃO daquele controle
    (`hefesto_vivo._recusou_dizendo`) e não tem por onde levar a de um sucesso.
    Então a regra é a honesta: **cala quando o byte saiu, fala quando não
    saiu.** O "aplicado" na tela — a outra metade da feature 19 — precisa de um
    lugar na página, e lugar na página é do usuário.

    SÃO DOIS OS CASOS QUE FALAM, e o segundo é o mais fino:

    * nada saiu no fio (as duas listas vazias, ou só `guardado_em`);
    * o corpo traz `motivo` COM `status: ok` — sucesso PARCIAL
      (`ipc_bridge._recusa_no_corpo`). O `ok` continua `True` e o byte pode até
      ter saído, mas o daemon disse alguma coisa e essa coisa é do usuário.

    A RECUSA SECA (`ok=False`) NÃO PASSA POR AQUI: quem a trata é o chamador,
    que sabe nomear o que tentou aplicar ("o seu efeito 'Recuo do MK'", "a curva
    'stop_hard'"). Repetir a decisão aqui daria duas frases para a mesma recusa.

    SEM CORPO NÃO HÁ O QUE CONFERIR: a ponte antiga e o dublê da régua não
    devolvem corpo, e nesse caso o `ok` decide, palavra por palavra como antes.

    O ASSUNTO É A FRASE DA GTK, e não uma escrita aqui: `_toast_trigger` monta
    `"Gatilho esquerdo (L2): <modo>"` — a cura TRG-01, que existe porque a barra
    dizia `"LEFT -> Off"`, trocando a fala do usuário por id interno mais o lado em
    inglês. A tela nova não vai reintroduzir o defeito com outro atalho.
    """
    assunto = _assunto(lado, modo_)
    if not ok or corpo is None:
        return ok, motivo
    calado = ((not _fala_de_destino(corpo) or _chegou_ao_aparelho(corpo))
              and not str(corpo.get("motivo") or ""))
    if calado:
        return ok, motivo
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.textos_de_aplicacao import frase_do_desfecho

        frase = frase_do_desfecho(assunto, corpo, _como_a_janela_pergunta(ctx, uniq))
    except Exception:
        frase = f"{assunto} — o Hefesto respondeu, e nenhum controle recebeu."
    raise RuntimeError(frase)


@gesto("03-gatilhos.html", "modo", grava="_gravar_so_o_gatilho")
def modo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Escolher um modo APLICA o efeito naquele gatilho, naquele controle.

    É O QUE O PRÓPRIO DESENHO PROMETE, na dica do quadro: *"Escolher um modo já
    manda o efeito para aquele controle, e quem está com ele na mão sente na
    hora"* — e *"soltar já manda"*. É também a decisão de 01/09 para a
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
    if chave == TRAVESSAO:
        raise ValueError(
            "modo: `—` é como esta tela diz que não há controle neste lugar, e "
            "não um efeito a aplicar. Escolha `O jogo decide` para soltar o gatilho.")
    ok, motivo, recibo = _aplicar(p, lado, chave, _padroes(chave), uniq, ctx)
    if not ok:
        raise RuntimeError(_na_lingua_da_tela(motivo, chave)
                           or f"o Hefesto não aplicou o modo «{_rotulo_do_modo(chave)}»")
    return {"recado": recibo}


@gesto("03-gatilhos.html", "pronto", grava="_gravar_so_o_gatilho")
def pronto(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Escolher um efeito pronto põe aquela CURVA no gatilho, na hora.

    O EFEITO PRONTO TEM DONO, e o dono é `profiles/trigger_presets.py`. São
    ONZE curvas em DUAS tabelas: seis em `FEEDBACK_POSITION_PRESETS` (as cinco
    do desenho mais `linear_medio`) e cinco em `VIBRATION_POSITION_PRESETS`.
    Cada uma resolve para dez intensidades de 0 a 8.

    FATO SUBSTITUÍDO — 03/09/2026. Esta docstring dizia, e a nota do
    `MODO_DA_CURVA` repetia: *"Uma curva de dez posições SÓ existe como
    `MultiPositionFeedback`"*. **É falso**, e o produto o desmente em duas
    linhas: `MultiPositionVibration` tem `frequency, pos_0..pos_9` no
    `trigger_specs`, e o `_MODES_COM_PRESET` da GUI estável lista os DOIS. Foi
    essa afirmação que manteve as cinco curvas de vibração fora do alcance
    desta tela — o gesto mandava sempre o modo de força. Agora o modo sai da
    TABELA em que a curva mora (ver `_curva`).

    E ELE TROCA O MODO NOS OUTROS 17 — está dito aqui porque é a única coisa
    deste gesto que não é dedução direta do produto. Na GUI estável a linha de
    preset nem aparece fora dos dois modos por posição
    (`_update_preset_row_visibility`). No desenho ela aparece sempre, para os
    19 — então escolher "Stop hard" com o modo em "Metralhadora" só pode querer
    dizer *"põe este gatilho na curva Stop hard"*. **Isto é escolha de produto
    e é do usuário**; está no relato para ela decidir. O que não faço é a alternativa
    calada: aplicar dez intensidades num modo que não tem posições, que o
    `build_from_name` recusaria e a tela não explicaria.

    "— Nenhum —" NÃO APLICA NADA, e recusa dizendo. O `value` dele é `custom`,
    que é o token do próprio produto para "os valores são os que estão aí" —
    não há curva a mandar, e mandar o modo "de volta ao normal" seria confundir
    este campo com o "Desligado" do campo de cima.

    E OS "MEUS EFEITOS" PASSARAM A EXISTIR — decisão 17 dela, 02/09/2026. Uma
    opção `meu:<nome>` é um efeito que ELA salvou (ver `meus_efeitos`), e o que
    se aplica é a metade DESTE gatilho do par que ela guardou. Até hoje esta
    função recusava dizendo *"não há onde guardar nem de onde ler um efeito com
    nome"*; agora há, e a frase saiu junto com o defeito.
    """
    uniq, lado = _exigir_controle(o, "efeito pronto"), _lado(o)
    chave = _escolhido(o)
    if chave.startswith(PREFIXO_DO_MEU):
        nome = chave[len(PREFIXO_DO_MEU):]
        meia = _meia_do_efeito(meus_efeitos().get(nome), lado)
        if meia is None:
            raise RuntimeError(
                f"«{nome}» não tem nada para este gatilho: quando ele foi "
                f"guardado, só o outro lado estava ajustado.")
        modo_salvo = str(meia.get("mode") or "Off")
        params = [int(v) for v in (meia.get("params") or [])]
        ok, motivo, recibo = _aplicar(p, lado, modo_salvo, params, uniq, ctx)
        if not ok:
            raise RuntimeError(_na_lingua_da_tela(motivo, modo_salvo)
                               or f"o Hefesto não aplicou o efeito «{nome}»")
        return {"recado": recibo}
    if chave in ("", "custom", TRAVESSAO):
        raise ValueError(
            "efeito pronto: não há curva a aplicar. '— Nenhum —' é a ausência "
            "de escolha, e `—` é como esta tela diz que o lugar está vazio. "
            "Para guardar um efeito seu, dê um nome a ele e use "
            "'Guardar esse efeito'.")
    # aplicadas: mandá-las como `MultiPositionFeedback` poria uma curva de
    curva, modo_da_curva = _curva(chave)
    ok, motivo, recibo = _aplicar(p, lado, modo_da_curva,
                                  _params_da_curva(modo_da_curva, curva), uniq, ctx)
    if not ok:
        raise RuntimeError(_na_lingua_da_tela(motivo, modo_da_curva)
                           or f"o Hefesto não aplicou a curva "
                             f"«{_tabela_da_curva(modo_da_curva)[1].get(chave, chave)}»")
    return {"recado": recibo}


@gesto("03-gatilhos.html", "ajuste", grava="_gravar_so_o_gatilho")
def ajuste(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Arrastar uma barra muda AQUELE parâmetro e reaplica o efeito na hora.

    A MAIOR DÍVIDA DESTA ABA, e o nome dela já estava reservado: o `SEM_ECO`
    listava um gesto `ajuste` que não existia. São **73 parâmetros em 17 dos 19
    modos** que a GTK deixa mexer e o HTML só mostrava — Rigid 2, Machine 6,
    MultiPositionFeedback 10, MultiPositionVibration 11. Sem eles, escolher um
    modo aplicava os PADRÕES dele e não havia como sair de lá; e "Montar do
    zero" (`Custom`), cujos oito padrões são ZERO, era um modo que não faz nada
    — um item de menu que responde "aplicado" com o gatilho intacto.

    NADA DE LÓGICA NOVA. A ordem dos parâmetros é a do produto
    (`preset_to_positional_params`, ver `_padroes`), quem lê a coluna é o
    `_ajustes_da_coluna` que o "Guardar esse efeito" já usava, e quem manda ao
    daemon é o `_aplicar`. Este gesto só troca UM número no meio da lista.

    O MODO VEM DA COLUNA, e não do servidor: é a mesma `forma` que o Guardar
    recolhe (`data-hef-forma`), e ela traz o `modo-chave-<lado>` que está na
    tela. Perguntar ao perfil daria o modo do DISCO, e o rascunho existe
    justamente porque os dois podem divergir.

    O `click` NÃO REPETE O `change`, e a guarda é a IGUALDADE, não o nome do
    evento. Uma alavanca dispara os dois no mesmo gesto — `change` ao soltar,
    `click` logo depois, com o mesmo valor —, e sem guarda cada arrasto viraria
    dois pedidos idênticos ao daemon. É o que o debounce de 300 ms da GTK
    (`_schedule_live_preview`) resolve do outro lado; aqui não há arrasto
    contínuo a conter, só a repetição do próprio evento.

    POR QUE PELA IGUALDADE E NÃO POR `evento == "click"`, e a diferença foi
    medida: o clique sintético desta casa (`--prova-clique`, `CLIQUE_COM_ALVO`)
    chama `el.click()` — se o gesto recusasse todo `click`, a régua da tela
    nunca alcançaria a alavanca e daria verde sobre um controle que ela nunca
    tocou. É o defeito do `--prova-gesto` que dava verde sobre dois botões
    mortos, com o sinal trocado. Comparar com o RASCUNHO cala a repetição sem
    calar a prova: o primeiro pedido passa, o segundo é o mesmo pedido.
    """
    uniq, lado = _exigir_controle(o, "ajuste"), _lado(o)
    sigla = str(o.get("lado") or "").strip()
    forma = o.get("forma")
    if not isinstance(forma, dict) or not forma:
        raise RuntimeError(
            "não consegui ler os ajustes desta coluna, e mandar um só trocaria "
            "os outros. Nada foi mandado.")
    modo_ = str(forma.get(f"modo-chave-{sigla}") or "").strip()
    if not modo_ or modo_ == TRAVESSAO:
        raise RuntimeError(
            "este gatilho ainda não tem modo. Escolha um modo primeiro.")
    params = _ajustes_da_coluna(forma, sigla, modo_)
    try:
        i = int(str(o.get("i") or "").strip())
    except ValueError:
        raise ValueError(
            "ajuste: o clique não disse QUAL barra. É o `data-i` da alavanca, "
            "e ele é o índice do parâmetro na ordem do spec.") from None
    if not 0 <= i < len(params):
        raise ValueError(
            f"ajuste: a barra {i} não existe no modo {modo_!r}, que tem "
            f"{len(params)} ajuste(s). O índice é posicional — se a caixa e o "
            f"modo saíram de sincronia, aplicar aqui escreveria no parâmetro "
            f"errado.")
    try:
        params[i] = int(float(str(o.get("valor") or "").strip()))
    except ValueError:
        raise ValueError(
            f"ajuste: a barra devolveu {o.get('valor')!r}, que não é número. "
            f"Zero é uma medida; o que a tela não soube dizer não vira zero.") from None
    ja = _do_rascunho(uniq, lado)
    if ja and ja.get("mode") == modo_ and list(ja.get("params") or []) == params:
        return None
    ok, motivo, recibo = _aplicar(p, lado, modo_, params, uniq, ctx)
    if not ok:
        raise RuntimeError(_na_lingua_da_tela(motivo, modo_)
                           or f"o Hefesto não aplicou o ajuste no modo «{_rotulo_do_modo(modo_)}»")
    return {"recado": recibo}


#: A LÁPIDE DO `reenviar` — 08/09/2026, e o roteiro desta remoção foi escrito
#: do aparelho — o DualSense não devolve o modo em que está, `state_full` não
#: reenviar. Se ela pedir de novo, o lugar é uma faixa própria, não a `guardar`.

    """O par L2+R2 que está NA COLUNA, pronto para o disco. Levanta se não houver.

    ELE ERA O MIOLO DO `guardar` E VIROU FUNÇÃO em 06/09/2026, quando o
    :func:`em_todos` passou a precisar exatamente do mesmo par. Escrito duas
    vezes, o segundo é o que esquece o `TRAVESSAO` — e `—` não é *"desligue este
    gatilho"*, é *"não há controle neste lugar"*. Gravar um `Off` por causa dele
    silenciaria, no perfil, um gatilho que o perfil dava a todo mundo.

    O LADO SEM MODO FICA DE FORA, e é o que faz a fusão por campo funcionar: o
    esquema lê `model_fields_set` lado a lado, e um lado ausente do pedido
    continua *"sem opinião"*. Ver :func:`_com_os_gatilhos`.
    """
    dos_lados: dict[str, dict[str, Any]] = {}
    for lado, sigla in (("left", "e"), ("right", "d")):
        modo_ = str(forma.get(f"modo-chave-{sigla}") or "").strip()
        if not modo_ or modo_ == TRAVESSAO:
            continue
        dos_lados[lado] = {"mode": modo_,
                           "params": _ajustes_da_coluna(forma, sigla, modo_)}
    if not dos_lados:
        raise RuntimeError(
            "não consegui ler o modo desta coluna. Nada foi guardado.")
    return dos_lados


def _o_par_da_coluna(forma: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """O par L2+R2 que está NA COLUNA, pronto para o disco. Levanta se não houver.

    ELE ERA O MIOLO DO `guardar` E VIROU FUNÇÃO em 06/09/2026, quando o
    :func:`em_todos` passou a precisar exatamente do mesmo par. Escrito duas
    vezes, o segundo é o que esquece o `TRAVESSAO` — e `—` não é *"desligue este
    gatilho"*, é *"não há controle neste lugar"*. Gravar um `Off` por causa dele
    silenciaria, no perfil, um gatilho que o perfil dava a todo mundo.

    O LADO SEM MODO FICA DE FORA, e é o que faz a fusão por campo funcionar: o
    esquema lê `model_fields_set` lado a lado, e um lado ausente do pedido
    continua *"sem opinião"*. Ver :func:`_com_os_gatilhos`.
    """
    dos_lados: dict[str, dict[str, Any]] = {}
    for lado, sigla in (("left", "e"), ("right", "d")):
        modo_ = str(forma.get(f"modo-chave-{sigla}") or "").strip()
        if not modo_ or modo_ == TRAVESSAO:
            continue
        dos_lados[lado] = {"mode": modo_,
                           "params": _ajustes_da_coluna(forma, sigla, modo_)}
    if not dos_lados:
        raise RuntimeError(
            "não consegui ler o modo desta coluna. Nada foi guardado.")
    return dos_lados


_RECADO_DE_TODOS = (
    "Este efeito passou a valer para todos os controles. Ele saiu do ajuste "
    "próprio de cada um e foi para o perfil — um controle que você ligar "
    "depois já nasce com ele.")


@gesto("03-gatilhos.html", GESTO_DE_TODOS, grava="_gravar_so_o_gatilho")
def em_todos(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Em todos": o par desta coluna vai para a seção GLOBAL do perfil.

    **A LINHA 110 DO CSV DA PARIDADE**, e o defeito que ela nomeia não é de
    conforto: *"o perfil salvo pelo HTML fica com dois overrides por MAC em vez
    de uma seção global, o que muda o que acontece quando ela liga um TERCEIRO
    controle: ele herda a global (que o HTML nunca escreveu), não o efeito que
    ela configurou"*. Até aqui **toda** escrita desta aba era por MAC — o `modo`,
    o `pronto`, o `ajuste` e o `guardar` chamam `_com_os_gatilhos`, que escreve
    em `controllers[uniq].triggers`. Não havia caminho nenhum, nesta tela, para
    a seção global; e é ela que um aparelho novo herda.

    **O GÊMEO NA GTK É `triggers_actions._persist_params_to_draft`**, no ramo em
    que `alvo_de_edicao(self).uniq is None` — o alvo em `TODOS`. Ele faz DUAS
    coisas, e as duas estão aqui:

    1. grava o lado editado na seção global do rascunho;
    2. `draft.with_override_fields_cleared("triggers", {side})` — LIMPA aquele
       lado dos overrides por controle de todo mundo. Sem o passo 2 a global
       seria escrita e continuaria perdendo: o override por MAC vence o global
       no merge por campo do backend (`profiles/manager._controllers_to_specs`
       lê `model_fields_set`), e os controles que já tinham opinião ficariam com
       a de ontem. Quem faz os dois aqui é :func:`_com_os_gatilhos_de_todos`.

    **O ENVIO VAI EM BROADCAST, e isto é o oposto do ABAS-06.** O `_uniq` desta
    aba avisa, com razão, que *"o `trigger.reset` sem `uniq` vai em BROADCAST e
    zera o gatilho dos quatro"* — foi um defeito quando o alvo era UM controle e
    o pedido saía sem endereço. Aqui o alvo É toda a mesa, por um botão cujo
    texto diz isso, e mandar quatro pedidos endereçados em vez de um seria
    reescrever o que a ponte já resolve: a GTK, no alvo `TODOS`, passa
    `uniq=None` pela mesma porta (`_apply_trigger`). O corpo do daemon volta com
    `aplicado_em` cheio, e é dele que sai a frase que conta em quantos entrou.

    **ESCREVER GLOBAL AQUI NÃO É O `None` QUE O `alvo_de_edicao` PROÍBE.** Aquele
    módulo existe porque `None` carregava duas coisas — *"o usuário clicou em Todos"* e
    *"eu não sei quem é o alvo"* —, e a segunda virava escrita global silenciosa.
    Este gesto é a PRIMEIRA: `EstadoDoAlvo.TODOS`, escolha deliberada, com um
    clique do usuário por trás. O que ele nunca faz é o segundo caso — sem coluna não
    há `forma`, e sem `forma` ele recusa dizendo.

    **A FONTE É A TELA, e não o disco** — pela razão do aparelho: o DualSense
    não devolve o modo em que está, e o que ela acabou de escolher só existe na
    coluna. O piloto recolhe a coluna pelo `data-hef-forma="@controle"`,
    e por isso este gesto reusa o :func:`_o_par_da_coluna` do "Guardar esse
    efeito" em vez de escrever uma segunda leitura.

    **DEIXOU DE SER PROVISÓRIO — 08/09/2026.** Esta docstring dizia que o botão
    estava na bancada e **não** na publicada, esperando o ato dela; a publicação
    de `f1393b41` o levou, e as quatro colunas da página que o produto renderiza
    o têm. O gesto que estava à espera passou a ser clicável, e o texto que
    dizia o contrário atravessou dois dias — o mesmo `--publicar` cuja outra
    metade deixou o `reenviar` sem botão. Ver a lápide dele neste arquivo.
    """
    uniq = _exigir_controle(o, "em todos")
    forma = o.get("forma")
    if not isinstance(forma, dict) or not forma:
        raise RuntimeError(
            "não consegui ler o efeito desta coluna. Nada foi mandado.")
    dos_lados = _o_par_da_coluna(forma)

    na_mesa = [str(c.get("uniq") or "") for c in (ctx.conectados or [])]
    na_mesa = [u for u in na_mesa if u] or [uniq]

    for disco, cfg in dos_lados.items():
        ok, motivo, _ = _aplicar(p, disco, str(cfg["mode"]), list(cfg["params"]),
                                 "", ctx, guardar=False, lembrar_em=na_mesa)
        if not ok:
            raise RuntimeError(
                f"{_assunto(disco, str(cfg['mode']))} — "
                f"{_na_lingua_da_tela(motivo, str(cfg['mode'])) or 'o daemon não aplicou'}")

    nome = perfil.nome_do_ativo(getattr(ctx, "state", None)).strip()
    if not nome:
        raise RuntimeError(
            "o efeito foi para os controles ligados, mas sem perfil ativo ele "
            "não vale para os próximos. Escolha um perfil na aba Perfis.")
    loader = perfil._com_o_src()
    try:
        prof = loader.load_profile(nome)
    except Exception as erro:
        raise RuntimeError(
            f"o efeito foi para os controles ligados, mas não entrou no perfil "
            f"{nome}. Um controle que você ligar depois não vai pegá-lo.") from erro
    novo = _com_os_gatilhos_de_todos(prof, dos_lados)
    if novo is not None:
        _gravar_so_o_gatilho(novo, p)
    return {"recado": _RECADO_DE_TODOS}


def _com_os_gatilhos_de_todos(prof: Any, dos_lados: dict[str, Any]) -> Any:
    """O perfil com o gatilho na seção GLOBAL — e o lado editado FORA de todo override.

    AS DUAS METADES SÃO UMA SÓ, e separá-las seria escrever a global e continuar
    perdendo: `profiles/manager._controllers_to_specs` monta o `OutputSpec` de
    cada controle a partir do `model_fields_set` do override dele, e um `left`
    escrito ali VENCE o `profile.triggers.left`. Um "em todos" que só escrevesse
    a global mudaria a tela e não mudaria o aparelho de quem já tinha opinião.

    É A REGRA DO BACKEND, e ela tem dono escrito: `draft_config`
    `with_override_fields_cleared` — *"uma edição em 'Todos' vale para todo
    mundo, então o campo editado sai dos overrides por-controle"*. Aquela função
    é do `DraftConfig` (o rascunho da janela GTK) e esta escreve no `Profile`
    direto, que é o caminho de disco desta aba; o que NÃO se reescreve é a regra
    de quando um override some — `_override_vazio` é importado de lá.

    **SEÇÃO QUE ESVAZIA VIRA `None`; ENTRADA SEM SEÇÃO SOME DO MAPA.** Um
    `ControllerOverrides` sem nada, deixado no lugar, faz o JSON salvo carregar
    uma chave de endereço apontando para `{}` — e a próxima leitura conclui que
    aquele aparelho tem opinião. É a mesma disciplina, com a mesma razão, do
    lado do rascunho.

    :return: `None` quando nada mudou. Regravar um perfil idêntico troca a data
        do arquivo e faz o daemon reaplicá-lo — e um `profile.switch` no meio de
        uma partida não é de graça. É o mesmo contrato de :func:`_com_os_gatilhos`.
    """
    from hefesto_dualsense4unix.app.draft_config import _override_vazio
    from hefesto_dualsense4unix.profiles.schema import TriggerConfig, TriggersConfig

    lados_pedidos = set(dos_lados)
    globais = prof.triggers.model_copy(
        update={lado: TriggerConfig(**cfg) for lado, cfg in dos_lados.items()})
    atuais: dict[str, Any] = {}
    limpou = False
    for chave, dele in (prof.controllers or {}).items():
        antes = dele.triggers
        if antes is None or not (antes.model_fields_set & lados_pedidos):
            atuais[chave] = dele
            continue
        # mesma pegadinha que `_com_os_gatilhos` documenta pelo outro lado. Um
        limpou = True
        restantes = antes.model_fields_set - lados_pedidos
        nova = (TriggersConfig(**{n: getattr(antes, n) for n in restantes})
                if restantes else None)
        depois = dele.model_copy(update={"triggers": nova})
        if _override_vazio(depois):
            continue
        atuais[chave] = depois
    if not limpou and globais == prof.triggers:
        return None
    return prof.model_copy(update={"triggers": globais,
                                   "controllers": atuais or None})


@gesto("03-gatilhos.html", "guardar", grava="_gravar_so_o_gatilho")
def guardar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Guardar esse efeito": a coluna vai para o PERFIL — e, com nome, para ELA.

    POR QUE ELE PRECISA EXISTIR, e é a diferença entre esta aba e as outras: os
    dois gestos vizinhos (`modo` e `pronto`) APLICAM na hora — é a decisão
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

    E O NOME É O QUE FALTAVA — decisão de produto de 02/09/2026: o efeito salvo aparece com o
    nome que o usuário deu. O campo ao lado do botão é opcional; preenchido, o par L2+R2
    entra em "Meus efeitos" com aquele nome e passa a aparecer nas quatro
    colunas. Vazio, este botão continua exatamente o que era.

    A LEGENDA DO DESENHO JÁ DIZIA ISSO, e é de onde veio a forma do dado:
    *"Guarda o par L2+R2 em Meus efeitos"*. A frase morreu num redesenho de
    30/08; o comentário do CSS que a explica sobreviveu em `aba03.py`.
    """
    uniq = _exigir_controle(o, "guardar")
    forma = o.get("forma")
    if not isinstance(forma, dict) or not forma:
        raise RuntimeError(
            "não consegui ler o efeito desta coluna. Nada foi guardado.")

    dos_lados = _o_par_da_coluna(forma)

    apelido = str(forma.get("nome-do-efeito") or "").strip()
    if len(apelido) > 60:
        raise ValueError(
            "o nome do efeito passou de 60 letras. O campo de escolha em que "
            "ele aparece tem 220px de coluna — um nome que não cabe some "
            "cortado, e um efeito que ela não consegue ler é um efeito perdido.")
    if apelido:
        _salvar_o_meu(apelido, dos_lados)

    nome = perfil.nome_do_ativo(ctx.state).strip()
    if not nome:
        if apelido:
            return {"blocos": _blocos_do_pronto(ctx)}
        raise RuntimeError(
            "sem perfil ativo não há onde guardar. Escolha um perfil na aba "
            "Perfis, ou dê um nome ao efeito para guardá-lo em Meus efeitos.")

    loader = perfil._com_o_src()
    prof = loader.load_profile(nome)
    novo = _com_os_gatilhos(prof, uniq, dos_lados)
    if novo is not None:
        _gravar_so_o_gatilho(novo, p)
    return {"blocos": _blocos_do_pronto(ctx)} if apelido else None


def _gravar_so_o_gatilho(novo: Any, p: Any) -> None:
    """Grava o perfil no disco — e NÃO reaplica o perfil inteiro no aparelho.

    ELE NÃO PODE SER O `perfil.gravar_e_reaplicar`, e o motivo foi MEDIDO em
    03/09/2026, clicando este botão no produto instalado com um DualSense no
    cabo. `gravar_e_reaplicar` termina em `p.profile_switch(...)`, que manda o
    daemon aplicar o perfil INTEIRO — barra de luz, LEDs de jogador, tudo. A
    prova, com um gesto só (`--prova-clique guardar`) e a barra apagada antes:

        antes   lightbar_on: false · lightbar_rgb: [0, 0, 0]
        depois  lightbar_on: true  · lightbar_rgb: [0, 0, 255]

    Ou seja: ela desliga a barra na aba Iluminação, vai aos Gatilhos, clica
    "Guardar esse efeito" — e a barra ACENDE de novo, sem nada na tela dizendo
    que isso ia acontecer. É *a tela afirmando o que não é*, na forma mais cara:
    um botão de escopo estreito ("esse efeito") desfazendo escolha viva dela em
    OUTRA aba.

    E A REAPLICAÇÃO NÃO ERA NECESSÁRIA PARA NADA. Esta aba aplica NA HORA — é a
    decisão de 01/09, *"clicar já aplica"*: quando ela chega a este botão,
    `modo` e `pronto` já mandaram o efeito ao aparelho por `_aplicar`. O
    `profile_switch` reaplicava por cima um gatilho que já estava lá, e levava
    junto nove seções que ninguém pediu.

    O `launch_env.refresh` FICA, e é a metade que tem de sobreviver: sem ele o
    perfil novo só chega ao jogo no próximo start do daemon. Ele relê o que os
    jogos vão receber e não escreve no aparelho.
    """
    loader = perfil._com_o_src()
    loader.save_profile(novo, origem="interface-nova")
    p.chamar("launch_env.refresh")


def _salvar_o_meu(apelido: str, dos_lados: dict[str, dict[str, Any]]) -> None:
    """Guarda o par L2+R2 na biblioteca do usuário, com o nome que ela deixou."""
    guardado: dict[str, Any] = {}
    for disco, cfg in dos_lados.items():
        _padroes(str(cfg["mode"]))
        guardado[disco] = {"mode": str(cfg["mode"]),
                           "params": [int(v) for v in cfg["params"]]}
    todos = meus_efeitos()
    todos[apelido] = guardado
    _guardar_meus_efeitos(todos)


def _blocos_do_pronto(ctx: Contexto) -> dict[str, str]:
    """As listas de "Efeito pronto" das quatro colunas, com a biblioteca de agora."""
    fora: dict[str, str] = {}
    for m in ctx.mesa:
        pref = str(m.get("pref") or "")
        if not pref:
            continue
        uniq = str(m.get("uniq") or "")
        for sig, disco in LADOS.items():
            fora[f'[data-controle="{pref}"] select.pronto[data-lado="{sig}"]'] = (
                html_das_opcoes_de_pronto(_modo_de_agora(ctx, uniq, disco)))
    return fora


def _modo_de_agora(ctx: Contexto, uniq: str, disco: str) -> str:
    """O modo em que aquele gatilho está, pela MESMA função que a tela pinta."""
    p = perfil.ativo(ctx.state.get("active_profile")) or {}
    return str(_o_que_o_controle_recebe(p, uniq, disco).get("mode") or "Off")


def _ajustes_da_coluna(forma: dict[str, Any], sigla: str, modo: str) -> list[int]:
    """Os ajustes daquele lado, na ORDEM do spec — nunca na ordem da tela."""
    padrao = _padroes(modo)
    fora = list(padrao)
    for i in range(len(padrao)):
        cru = str(forma.get(f"aj-val-{sigla}-{i}") or "").strip()
        if not cru:
            continue
        try:
            fora[i] = int(float(cru))
        except ValueError:
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

    LADO NÃO TOCADO NÃO VIRA OPINIÃO — 05/09/2026, e é o que faz a persistência
    no clique caber aqui. Antes desta linha, um `dos_lados` com uma metade só
    densificava a outra: sem override anterior ela virava um `Off` EXPLÍCITO, e
    `profiles/manager._controllers_to_specs` lê exatamente `model_fields_set`
    para decidir o que herda a seção global do perfil. Ou seja: clicar `Rígido`
    no L2 gravava um `Off` no R2 e silenciava, só naquele controle, o gatilho
    direito que o perfil dava a todos.

    Agora o lado ausente do pedido só entra se o override JÁ o tinha escrito —
    a metade que ela nunca tocou continua herdando o global, que é o contrato do
    esquema (*"`None` = sem opinião"*). O mesmo vale para o `guardar` quando a
    coluna traz `—` num dos lados: `—` é *"não há controle neste lugar"*, não
    uma escolha de desligar.
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
    ja_escritos = antes.model_fields_set if antes is not None else set()
    lados: dict[str, Any] = {}
    for lado in ("left", "right"):
        if lado in dos_lados:
            lados[lado] = TriggerConfig(**dos_lados[lado])
        elif lado in ja_escritos:
            lados[lado] = getattr(antes, lado)
    novos = TriggersConfig(**lados)
    if (antes is not None and antes == novos
            and antes.model_fields_set == novos.model_fields_set):
        return None
    atuais[chave] = dele.model_copy(update={"triggers": novos})
    return prof.model_copy(update={"controllers": atuais})


PONTE = {"trigger_set_detalhado", "trigger_reset_detalhado"}
#: Vazio: os dois métodos que esta aba usa (`trigger.set` e `trigger.reset`) têm
METODOS: set[str] = set()


#: 4 → 5 EM 04/09/2026: nasceu o `reenviar`, a decisão [03] do PO — o botão que
#: sem ninguém escolher isso. Ver a lápide do `reenviar` acima.
PISO_DA_ABA = 5
_UNIQ = "aa:bb:cc:00:00:01"
_GUARDOU: tuple[str, list[str], dict[str, Any]] = (
    "chamar", ["launch_env.refresh"], {})

_STOP_HARD, _MODO_STOP_HARD = _curva("stop_hard")
_GALOPE, _MODO_GALOPE = _curva("galope")


def _forma_de_prova(sigla: str, modo_: str) -> dict[str, str]:
    """A coluna que o piloto recolheria, montada pelo endereço que a pintura usa."""
    return {f"modo-chave-{sigla}": modo_}
PROVAS = [
    # calados no dia em que ela mudasse um padrão — e a régua daria verde sobre
    {"pagina": PAGINA, "gesto": "modo", "clique": {"lado": "e",  # (noqa-acento) id
     "modo": "Rigid"},
     "chama": [("trigger_set_detalhado", ["left", "Rigid", _padroes("Rigid")],
                {"uniq": _UNIQ}), _GUARDOU]},
    # "Desligado" é `trigger.reset` — a R-19. Se alguém trocar por um
    {"pagina": PAGINA, "gesto": "modo", "clique": {"lado": "d", "modo": "Off"},  # (noqa-acento) id
     "chama": [("trigger_reset_detalhado", ["right"], {"uniq": _UNIQ}), _GUARDOU]},
    {"pagina": PAGINA,  # (noqa-acento) chave do contrato
     "gesto": "modo", "clique": {"lado": "e", "valor": "Vibration"},
     "chama": [("trigger_set_detalhado", ["left", "Vibration", _padroes("Vibration")],
                {"uniq": _UNIQ}), _GUARDOU]},
    {"pagina": PAGINA,  # (noqa-acento) chave do contrato
     "gesto": "pronto", "clique": {"lado": "d", "v": "stop_hard"},
     "chama": [("trigger_set_detalhado",
                ["right", _MODO_STOP_HARD,
                 _params_da_curva(_MODO_STOP_HARD, _STOP_HARD)],
                {"uniq": _UNIQ}), _GUARDOU]},
    {"pagina": PAGINA,  # (noqa-acento) chave do contrato
     "gesto": "pronto", "clique": {"lado": "e", "v": "galope"},
     "chama": [("trigger_set_detalhado",
                ["left", _MODO_GALOPE, _params_da_curva(_MODO_GALOPE, _GALOPE)],
                {"uniq": _UNIQ}), _GUARDOU]},
    # número mexido, os outros viram padrão calados e esta linha reprova.
    {"pagina": PAGINA,  # (noqa-acento) chave do contrato
     "gesto": "ajuste", "clique": {"lado": "e", "i": "1", "valor": "200",
                                   "forma": _forma_de_prova("e", "Rigid")},
     "chama": [("trigger_set_detalhado",
                ["left", "Rigid", [_padroes("Rigid")[0], 200]], {"uniq": _UNIQ}), _GUARDOU]},
    # `_com_os_gatilhos_de_todos` devolve `None` quando nada muda, de propósito:
    {"pagina": PAGINA,  # (noqa-acento) chave do contrato
     "gesto": GESTO_DE_TODOS,
     "clique": {"forma": _forma_de_prova("e", "Pulse")},
     "chama": [("trigger_set_detalhado", ["left", "Pulse", _padroes("Pulse")],
                {"uniq": ""}), _GUARDOU]},
]

#: OS GESTOS QUE O DAEMON ACEITA E NÃO PUBLICA. O `state_full` não traz
#: `triggers`: o DualSense não devolve o modo em que está — gatilho adaptativo é
SEM_ECO = ("modo", "pronto", "ajuste")
