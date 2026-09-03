#!/usr/bin/env python3
"""O pacote da aba `05` Vibração.

CORRIGIDO EM 01/09/2026. O que estava aqui:

    "motor-esq: o valor por motor — o daemon publica a política da mesa, não o
     motor"

Está errado, e o próprio daemon desmente: `rumble_ff.per_vpad[]` traz
`last_weak` e `last_strong` — **os dois motores, por gamepad virtual** — além de
`ff_maior_pedido: [weak, strong]`, `rumble_no_fisico` e a contagem de plays.
Medido no daemon dela, com o DualSense no cabo.

O DualSense tem DOIS motores e eles não são "esquerdo e direito" por acaso: o
`strong` é o motor pesado e o `weak` o leve — a nomenclatura vem do protocolo de
force-feedback do evdev, e é a que o produto usa de ponta a ponta. A tela fala
"esquerdo/direito" porque é onde eles ficam no plástico.

O QUE DE FATO NÃO TEM DONO: nada. O que a aba mostra é o pedido que o JOGO fez
(o que chegou ao gamepad virtual), e não a corrente que passou no motor — isso o
aparelho não devolve. É uma ressalva sobre o SIGNIFICADO do número, não sobre a
existência dele, e a tela a carrega no `title`.
"""
from __future__ import annotations

import time
from typing import Any

# O IMPORT É DE MÓDULO, e não de dentro da função — 01/09/2026. O
# `portao_a_casa_sabe_e_o_produto_nao_faz` segue o fecho de IMPORT a partir do
# piloto que o lançador abre, e um `from … import` escondido dentro de uma
# função não entra nesse fecho: a camada do produto continuava aparecendo como
# "promessa sem caminho" mesmo depois de eu a ligar.
#
# O `sys.path` já tem o `src/` quando esta linha roda: `pacotes/__init__.py` o
# insere no import do pacote.
from hefesto_dualsense4unix.app.telas import vibracao as _tela

from . import Contexto, registrar

#: O QUE ESTA ABA MOSTRA E ESTE PACOTE NÃO PINTA — com o motivo e o DONO da
#: cura. Estava `{}` até 02/09/2026, e o vazio dizia "nada falta", que é a forma
#: mais barata de mentir numa aba onde quatro coisas faltavam.
#:
#: **DOIS DOS QUATRO MUDARAM DE DONO no mesmo dia**, quando o alvo `classe`
#: nasceu no pintor: `degrau-aceso` e `mult-teto` deixaram de esperar por outro
#: arquivo e passaram a esperar por ESTE mais o gerador da aba — e, no fim, pela
#: publicação dela. Ver a nota logo abaixo.
SEM_DONO: dict[str, str] = {
    # FATO SUBSTITUÍDO — 02/09/2026. As duas linhas abaixo diziam "o pintor não
    # sabe mexer em classe" e "mesma cura, mesmo dono: o pintor". **O PINTOR JÁ
    # SABE**: `hefesto_vivo.py:217` tem o ramo `if(alvo === 'classe')`, e o
    # comentário que o abre (`:187-191`) nomeia estes dois casos pelo nome —
    # "qual dos quatro degraus da Vibração está aceso" e "o rótulo `Máx` do
    # teto". O dono mudou de lado, e mantê-los como estavam faria a próxima
    # pessoa esperar por uma cura que já chegou.
    "degrau-aceso": "O ENDEREÇO NASCEU E A EMISSÃO TAMBÉM — 02/09/2026. Os "
    "quatro botões levam `data-campo=\"degrau\" data-hef-alvo=\"classe\" "
    "data-hef-quando=<degrau>` (`aba05._coluna`) e este pacote emite `degrau` "
    "por coluna. O QUE FALTA É SÓ A PUBLICAÇÃO DELA: na página que o produto "
    "renderiza HOJE o endereço não existe, então o `achar()` do piloto devolve "
    "lista vazia e nada é pintado — a tela dela não piora e não melhora até o "
    "`--publicar 05`. Enquanto isso o desenho continua cravando 'Máximo' na "
    "coluna do P1 com `rumble_policy = 'balanceado'` no daemon, que é a tela "
    "afirmando o contrário do disco. E o degrau da COLUNA não é sempre o da "
    "mesa: `profiles/schema.ControllerRumbleOverride` guarda `policy` e "
    "`custom_mult` por peça desde POR-UNIDADE-01 (10/08/2026), e "
    "`core/backend_pydualsense._escalar_rumble` os aplica — quando essa fonte "
    "chegar, ela muda dentro do `pacote_da_coluna` e a emissão daqui não muda.",
    "mult-teto": "O rótulo `Máx` ao lado do multiplicador aparece SÓ quando a "
    "coluna está no teto, e hoje é cravado: a foto de 02/09 mostra `70%` com "
    "`Máx` ao lado, afirmando que 70% é o teto. Pintá-lo por TEXTO poria `—` "
    "onde o desenho não põe nada (`hefesto_vivo.py:112` troca vazio por "
    "travessão); o alvo certo é o `classe` SEM `data-hef-quando`, que é "
    "booleano — o próprio comentário do pintor cita este rótulo. Mesma "
    "pendência do `degrau-aceso`: endereço no HTML e emissão aqui.",
    "lado:ligado": "Os oito interruptores de punho são DESENHO, e o produto "
    "concorda por escrito: `app/telas/vibracao.SEM_FONTE['lado:ligado']` — não "
    "há campo em `profiles/schema.py`, nem método de IPC, nem chave no "
    "`state_full`. Fecha: MIGRA-VIBRACAO-06.",
    "barra:motor": "Arrastar a barra de um motor mandaria `rumble.set`, e o "
    "dono está escrito (`app/telas/vibracao.DONOS_DOS_GESTOS['barra:motor']`). "
    "O que falta é o NÚMERO: a linha é um `<div>`, o ouvinte manda "
    "`valor: alvo.value ?? ''` (`hefesto_vivo.py:299`) e um `<div>` não tem "
    "`value`. Sem um `<input type=range>` no desenho, o clique chega sem "
    "quantidade nenhuma — e é decisão dela trocar a barra por um controle "
    "arrastável.",
}


def _do_vpad(ff: dict[str, Any], player: Any) -> dict[str, Any]:
    """O bloco `per_vpad` daquele jogador, ou `{}`.

    Casa por `player`, não por posição na lista: a ordem do `per_vpad` é a de
    criação dos gamepads virtuais, e ela não acompanha a ordem da mesa quando um
    controle cai e volta.
    """
    for v in (ff or {}).get("per_vpad") or []:
        if v.get("player") == player:
            do_vpad: dict[str, Any] = v
            return do_vpad
    return {}


@registrar("05-vibracao.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    """DELEGA para `app/telas/vibracao.pacote_da_mesa` — a camada do PRODUTO.

    ELA JÁ EXISTIA E NUNCA TINHA SIDO LIGADA, e é o `casa-sabe` que a denunciou:
    `app/telas/vibracao.py` tem oito funções públicas — `pacote_da_mesa`,
    `pacote_da_coluna`, `estado_da_coluna`, `degraus_da_forca`,
    `motores_do_controle`, `teto_da_barra`, `gesto_do_clique` — e **nenhuma
    tinha chamador em produção**. O portão as listava como promessa sem caminho
    desde 31/08/2026.

    Ela é MAIS COMPLETA que o que este pacote tinha: devolve a largura da barra
    já em `%` (`pct.w`), o número formatado, o `sabe` que distingue "zero" de
    "não sei", a cor do plástico e o `treme` por motor. Reescrever isso era a
    duplicação que a pergunta dela de 01/09 pegou — *"não estamos refazendo do
    zero né?"*

    O QUE SOBRA AQUI é o ACHATAMENTO: o produto devolve `{"pct": {"w": "46.7%"}}`
    e a tela endereça `data-campo="forca-pct"`. Traduzir a forma é da interface;
    calcular o valor é do produto.

    O NOME `forca` NÃO SAI MAIS DAQUI — 02/09/2026, e a razão está fotografada.
    O pintor procura um valor por `[data-campo=X],[data-papel=X],[data-hef=X]`
    (`hefesto_vivo.py:183`), e nesta página `forca` é **as duas coisas**: o
    `data-campo` do número do multiplicador E o `data-papel` dos quatro degraus
    mais o da linha inteira do "Personalizado". Emitir a chave `forca` escrevia
    `"balanceado"` em DEZ elementos por tique:

    * os quatro botões perdiam o rótulo — "Economia", "Balanceado", "Máximo" e
      "Auto" viraram os quatro a mesma palavra, e ela deixa de poder escolher;
    * a linha do "Personalizado" é um `<div>` com filhos, e `textContent`
      **apaga os filhos**: o trilho, o número e o "Máx" sumiam da tela — junto
      com os endereços `forca-pct` e `mult`, que a pintura seguinte já não
      achava.

    Medido em 02/09/2026 na foto `/tmp/antes-05.png`, com o daemon dela vivo.
    O NÚMERO passou a se endereçar por `mult` (`aba05._barra`, `campo_num`);
    o trilho continua `forca-pct`, que nunca esteve em colisão. A régua
    `test_a_vibracao_nao_escreve_no_botao.py` reprova qualquer nome que volte a
    ser valor e clique ao mesmo tempo.
    """
    import mesa_viva


    bruto = _tela.pacote_da_mesa(ctx.state, ctx.mesa, ctx.conectados,
                                 contagem=mesa_viva.texto_da_contagem(ctx.mesa))
    colunas: dict[str, dict[str, Any]] = {}
    for uniq, col in (bruto.get("colunas") or {}).items():
        pct = col.get("pct") or {}
        plano = {
            "identidade": _sem_marcacao(col.get("identidade", "")),
            # O NÚMERO DO MULTIPLICADOR, e não o nome do degrau: o desenho
            # escreve `150%` nesta caixa, ao lado do trilho e do "Máx". Quem diz
            # QUAL degrau está aceso é a classe `on` do botão — e ela não tem
            # dono (ver :data:`SEM_DONO`).
            "mult": pct.get("n", "—"),
            "forca-pct": str(pct.get("w", "")).rstrip("%"),
            # QUAL DOS QUATRO DEGRAUS ESTÁ ACESO — 02/09/2026. O valor é a
            # CHAVE do produto (`economia`/`balanceado`/`max`/`auto`), e é ela
            # que o `data-hef-quando` de cada botão carrega; o alvo `classe` do
            # `escrever()` acende quem casar e apaga as irmãs. O rótulo NUNCA
            # sai daqui: escrever texto nestes botões apagaria a escolha dela,
            # que é o defeito de 02/09 pela manhã.
            #
            # A POLÍTICA É DA MESA, e emiti-la por coluna não é contradição: o
            # `pacote_da_coluna` já a monta assim (`app/telas/vibracao.py:270`)
            # porque o desenho tem quatro colunas e a resposta é uma só. Quando
            # `ControllerRumbleOverride.policy` chegar à tela, a fonte muda ali
            # dentro e esta linha não se mexe.
            "degrau": col.get("forca", ""),
        }
        for lado, m in (col.get("motores") or {}).items():
            plano[f"motor-{lado}"] = m.get("n", "—")
            plano[f"motor-{lado}-pct"] = str(m.get("w", "")).rstrip("%")
        colunas[uniq] = plano
    # A LINHA DO ESTADO — 02/09/2026, e ela é a única coisa que esta aba diz
    # sobre a MESA. Vai por `blocos` e não por campo: o NÚMERO de linhas muda com
    # o estado (um aviso que não se aplica não aparece), e o pintor troca vazio
    # por travessão — um `—` numa linha de alerta afirmaria "não sei" onde a
    # resposta é "não há nada a avisar" (`hefesto_vivo.py:118`).
    #
    # O SELETOR É `#vib-estado`, e ele só existe na BANCADA até ela publicar. Na
    # página publicada o `document.querySelector` devolve `null` e o laço do
    # bootstrap não faz nada — nem erro, nem pintura contada. É o preço de a
    # publicação ser ato dela, e está declarado em `mockup/DIVERGENCIAS.md`.
    estado = _tela.html_do_estado(_tela.textos_do_estado(ctx.state))
    return {
        "colunas": colunas,
        # A MESA NÃO EMITE CAMPO NENHUM, e é o que a página comporta.
        # `rumble_policy` não tem `data-campo` — o degrau aceso é uma CLASSE, não
        # um texto — e `rumble_passthrough` também não. Emiti-los custava dez
        # elementos destruídos por tique e não pintava um valor sequer.
        "mesa": {},
        "blocos": {"#vib-estado": estado},
        "sem_dono": dict(SEM_DONO),
        "cobertura": {"pintados": sum(len(v) for v in colunas.values()),
                      "sem_dono": len(SEM_DONO)},
    }


def _sem_marcacao(texto: str) -> str:
    """Tira o HTML do produto: a tela nova escreve `textContent`, não `innerHTML`.

    A camada do produto monta `P1 <span class="pt">•</span> Não sei` porque a
    janela dela injeta como HTML. Escrever isso num `textContent` mostraria as
    tags.

    CORRIGIDO EM 02/09/2026. O que estava aqui trocava CADA TAG por um `·` e
    dizia, no próprio docstring, que *"o separador vira o `·`"* — mas a tag de
    abertura e a de fechamento são DUAS, com o `•` no meio, e o que saía era
    `P1 ·•· Não sei ·•· BT`. Medido contra o daemon dela:

        antes:  'P1 ·•· Não sei ·•· BT'
        depois: 'P1 · Não sei · BT'

    O `·` é o separador que os outros pacotes usam (`a01_jogar.py:50`); o `•` é
    o do desenho, e ele vive dentro da tag que sai. Some com a marcação, e o
    ponto que ela vê é um só.
    """
    import re as _re

    sem_tags = _re.sub(r"<[^>]+>", "", texto)
    return _re.sub(r"\s*•\s*", " · ", sem_tags).strip()




# ---------------------------------------------------------------------------
# OS GESTOS — o clique dela chegando aos DOIS motores
# ---------------------------------------------------------------------------
# O QUE ESTA ABA TEM DE DIFERENTE DAS OUTRAS NOVE, e muda todo gesto daqui:
# **os métodos de vibração não recebem `uniq`.** Medido no censo do daemon em
# 01/09/2026 (`pacotes/daemon.parametros`):
#
#     rumble.set          ('weak', 'strong')      ← nenhum endereço
#     rumble.stop         ()                      ← nenhum endereço
#     rumble.policy_set   ('policy',)             ← nenhum endereço
#     rumble.passthrough  ('enabled',)            ← nenhum endereço
#
# Quem escolhe o controle é o ALVO DE OUTPUT do daemon, e o handler o congela
# junto do par: `daemon/ipc_handlers.py:4294` grava `rumble_active_uniq =
# uniq_do_alvo_de_output(self.controller)`. Sem alvo escolhido o padrão é
# BROADCAST (`ipc_handlers.py:4133`) — os quatro tremeriam, e a coluna, que é o
# endereço desta aba, estaria mentindo. Por isso `_mirar()` vem antes.
#
# A política é a exceção, e não é descuido meu: ela é DA MESA e o produto sabe
# disso — `app/actions/rumble_actions.py:911` escreve *"não há IPC de política
# por unidade, e inventar um seria mecanismo novo"*.
from . import gesto  # noqa: E402

#: O PAR DO TESTE quando ninguém pediu vibração ainda. É o mesmo da janela
#: estável (`app/actions/rumble_actions.py:1012`, `weak = 160` / `strong =
#: 220`), e ele **não tem dono em lugar nenhum** — lá é literal dentro do
#: método, e aqui é literal dentro do módulo. São duas cópias, e a segunda
#: nasce declarada para que a próxima pessoa as ache com um `grep`.
PAR_DE_TESTE = (160, 220)

#: MEIO SEGUNDO, e a decisão dela de 30/08 preservou o comportamento e mudou só
#: o rótulo: *"ali vai ser só Testar; se o user quiser parar vai clicar em
#: Parar"* — e o gerador registra na mesma linha que *"o meio segundo continua
#: sendo o que o gesto manda ao daemon; o que sai é a PROMESSA na tela"*
#: (`aba05.py:582`). A dica publicada diz o mesmo: *"faz aquele controle tremer
#: meio segundo"*.
SEGUNDOS_DO_TESTE = 0.5


def _uniq(o: dict[str, Any]) -> str:
    """O `uniq` do controle onde ela clicou. Vazio = clique solto, e recusa.

    `""` NÃO vira "todos": sem alvo o `rumble.set` faz BROADCAST, e um "Testar"
    sem dono sacudiria a mesa inteira. O desenho promete o contrário — *"Testar
    faz aquele controle tremer meio segundo"*.
    """
    return str(o.get("uniq") or "")


def _indice(ctx: Contexto, uniq: str) -> int:
    """A POSIÇÃO daquele controle na lista do daemon — o que o alvo espera.

    `controller.target.set` recebe `index` (0 = primário), **não** `uniq`:
    `daemon/ipc_handlers.py:4137`. O número sai do próprio bloco `controllers`
    (`core/backend_pydualsense.py:5107`, `"index": idx`), que é a posição em
    `list(self._handles)` — o MESMO que cada linha do seletor da janela estável
    carrega (`app/actions/status_actions.py:1585`).

    O RECURSO À POSIÇÃO NA MESA existe porque nem toda entrada publica `index`
    (backend falso, daemon legado); o próprio handler cai nesse recurso em
    `_numero_de_exibicao` (`ipc_handlers.py:526`). E se o controle não estiver
    na mesa, levanta: mirar um lugar vazio deixaria o alvo ANTERIOR de pé, e o
    tremor sairia na coluna errada, calado.
    """
    i = ctx.por_uniq(uniq).get("index")
    if isinstance(i, int) and not isinstance(i, bool):
        return i
    for pos, c in enumerate(ctx.conectados):
        if str(c.get("uniq") or "") == uniq:
            return pos
    raise ValueError(f"o controle {uniq} não está na mesa agora")


def _resposta(r: Any) -> tuple[bool, str | None]:
    """`(ok, motivo)` seja qual for a forma que a função da ponte devolveu.

    O `ipc_bridge` tem DUAS formas de retorno, e esta aba usa as duas: as
    `*_checked` devolvem o par `(ok, motivo)` — o motivo é a recusa do daemon
    já traduzida em frase de tela — e as outras devolvem só `bool`. Sem este
    normalizador, trocar uma função pela irmã (`rumble_stop` por
    `rumble_stop_checked`) rebentaria no primeiro clique com um `TypeError` de
    desempacotamento, que é o erro mais barato de cometer e o mais caro de ler.
    """
    if isinstance(r, tuple):
        ok = bool(r[0]) if r else False
        motivo = r[1] if len(r) > 1 else None
        return ok, (str(motivo) if motivo else None)
    return bool(r), None


def _mirar(ctx: Contexto, o: dict[str, Any], p: Any) -> str:
    """Aponta o alvo de output para a coluna clicada, e devolve o `uniq`.

    ISTO NÃO É ENFEITE: é a única forma de o botão da coluna falar com AQUELE
    controle, porque `rumble.set` e `rumble.stop` não têm parâmetro de endereço
    (ver o bloco no topo desta seção). O `rumble.stop` mira no mesmo lugar —
    `ipc_handlers.py:4367` lê `uniq_do_alvo_de_output` antes de zerar.

    É o MESMO par de passos da janela estável, só que sem seletor: lá o chip
    manda `controller.target.set` (`app/actions/status_actions.py:2452`) e a
    aba Rumble manda o `rumble.set` depois. Aqui os dois viram um gesto só,
    porque nesta aba o endereço é a coluna — a fita nasce esmaecida de
    propósito (decisão dela, 28/08).

    `controller.target.set` não tem função no `ipc_bridge` (procurei: o módulo
    não cita `target` uma vez), então é o degrau 3 da ponte — e passa pelo
    mesmo `_safe_call`, com o mesmo timeout.
    """
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("o clique não disse em qual controle — e sem alvo a mesa inteira treme")
    p.chamar("controller.target.set", index=_indice(ctx, uniq))
    return uniq


@gesto("05-vibracao.html", "forca")
def forca(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Um dos quatro degraus: quanto da vibração pedida chega ao aparelho.

    `rumble_policy_set_checked` é a ÚNICA porta do `rumble.policy_set` desde
    26/08 (`app/ipc_bridge.py:666`) — as outras duas caíram por descartarem o
    motivo da recusa. É a mesma função que a janela estável chama em
    `app/actions/rumble_actions.py:797`, com a MESMA folga de leitura: o
    `STATE_IPC_TIMEOUT_S` não se digita aqui, sai de quem é dono dele.

    O DEGRAU VEM DO `data-forca`, nunca do rótulo: o HTML carrega a CHAVE do
    produto (`economia`/`balanceado`/`max`/`auto`), e o gerador reprova a si
    mesmo se os degraus divergirem do `RUMBLE_POLICY_MULT` (`aba05.py:98`).

    A BARRA "Personalizado" TAMBÉM É `data-papel="forca"` — e é a leitura do
    multiplicador, não um botão. Um clique nela chega aqui sem degrau, e a
    recusa é o que separa as duas coisas: `rumble.policy_custom` pede um número
    (`mult`), e um clique numa barra sem cursor não carrega número nenhum.

    O QUE ESTE BOTÃO NÃO FAZ, e o produto já sabia: **a política é da MESA, não
    da coluna.** `app/actions/rumble_actions.py:911` escreve *"não há IPC de
    política por unidade, e inventar um seria mecanismo novo"*. O desenho
    endereça por coluna e o daemon responde pela mesa inteira — clicar
    "Economia" na coluna do P2 muda os quatro. O que vale por peça chega pelo
    perfil (`set_rumble_scales`), não por este clique.
    """
    from hefesto_dualsense4unix.app.actions.mode_transition import STATE_IPC_TIMEOUT_S

    degrau = str(o.get("forca") or "")
    if not degrau:
        raise ValueError(
            "força: este clique não trouxe degrau — a barra 'Personalizado' não é "
            "botão, e o multiplicador dela precisa de um número que o clique não tem")
    ok, motivo = _resposta(p.rumble_policy_set_checked(degrau, timeout=STATE_IPC_TIMEOUT_S))
    if not ok:
        raise RuntimeError(motivo or "o Hefesto não está rodando — ligue na aba Sistema")


@gesto("05-vibracao.html", "testar")
def testar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Testar": AQUELE controle treme meio segundo e a mão volta para o jogo.

    QUATRO CHAMADAS, e a ordem é a da janela estável mais o alvo que esta aba
    precisa:

    1. `controller.target.set` — sem ele o par iria para os quatro (`_mirar`);
    2. `rumble_set_checked` — a mesma função do `on_rumble_test_500ms`
       (`app/actions/rumble_actions.py:1019`). A CHECADA, e não a crua: a
       recusa do Modo Nativo vem no CORPO da resposta, não como erro JSON-RPC
       (`app/ipc_bridge.py:597`), e foi por não a ler que a aba anunciou
       "vibração travada" com o motor parado — NATIVO-RUMBLE-01;
    3. `rumble_stop` e 4. `rumble_passthrough(True)` — os dois passos exatos do
       `_rumble_test_stop` (`rumble_actions.py:1214-1215`). Parar sozinho fixa
       `(0, 0)` e o laço do daemon re-afirma o silêncio: o jogo ficaria mudo
       depois de um teste, que é a queixa "testei os motores e o jogo não vibra
       mais" (SPRINT-GAME-RUMBLE-01). O passthrough é a segunda metade.

    OS VALORES SÃO OS DAS BARRAS DAQUELA COLUNA, que é o que a tela promete:
    *"Testar faz aquele controle tremer meio segundo com os valores das barras
    daquela coluna"*. As barras saem de `_do_vpad` — `last_strong` é o motor da
    ESQUERDA e `last_weak` o da direita, e a inversão é a armadilha deste
    assunto (`core/backend_pydualsense.py:3791`: `setLeftMotor(eff_strong)`).
    Com as duas em zero — ninguém pediu vibração ainda — vale o
    :data:`PAR_DE_TESTE`, exatamente como a janela estável faz.

    O MEIO SEGUNDO BLOQUEIA, e pode: o piloto roda todo gesto em thread
    própria, de propósito (`hefesto_vivo.py:388`, medido com o `daemon.reload`
    de 9,5 s). A janela estável usa `GLib.timeout_add` porque lá o gesto roda
    no laço do GTK.
    """
    uniq = _mirar(ctx, o, p)
    v = _do_vpad(ctx.state.get("rumble_ff") or {}, ctx.por_uniq(uniq).get("player"))
    strong = int(v.get("last_strong") or 0)
    weak = int(v.get("last_weak") or 0)
    if not weak and not strong:
        weak, strong = PAR_DE_TESTE
    ok, motivo = _resposta(p.rumble_set_checked(weak, strong))
    if not ok:
        raise RuntimeError(motivo or "o Hefesto não está rodando — ligue na aba Sistema")
    time.sleep(SEGUNDOS_DO_TESTE)
    p.rumble_stop()
    p.rumble_passthrough(True)


@gesto("05-vibracao.html", "parar")
def parar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Parar": corta a vibração daquele controle AGORA e devolve a mão ao jogo.

    SÃO DUAS COISAS, e nesta aba elas são um botão só — a dica publicada diz
    isso com todas as letras: *"Parar corta a vibração dele agora e devolve a
    mão ao jogo"*. Na janela estável são DOIS botões: o "Parar"
    (`rumble_stop_checked`, que FIXA `(0, 0)` e manda o laço re-afirmar o
    silêncio) e o "Devolver ao jogo" (`rumble_passthrough(True)`,
    `rumble_actions.py:1111`).

    O SEGUNDO PASSO NÃO É ENFEITE: esta aba não tem o botão de devolver, e sem
    ele o "Parar" deixaria o controle num estado MORTO — mudo para o jogo, sem
    caminho de volta na tela. É a regra da casa: *nada fica num estado morto*.

    A CHECADA, e não a crua: dentro do Modo Nativo o `rumble.stop` não trava
    silêncio, ele SOLTA o par e diz que não alcança o motor que o jogo toca
    pelo hidraw (`ipc_handlers.py:4380`). Anunciar "parada" ali seria prometer
    o que não aconteceu — NATIVO-RUMBLE-01, segunda metade. O motivo sobe como
    erro porque é o único canal que esta aba tem hoje; um recado de tela para
    ele ainda não existe, e está no relato.
    """
    _mirar(ctx, o, p)
    ok, motivo = _resposta(p.rumble_stop_checked())
    if not ok:
        raise RuntimeError("o Hefesto não está rodando — ligue na aba Sistema")
    p.rumble_passthrough(True)
    if motivo:
        raise RuntimeError(motivo)


#: AS FUNÇÕES DA PONTE QUE ESTA ABA USA. A régua confere que existem — um nome
#: inventado aparece aqui, e não na mão de quem clica.
PONTE = {"chamar", "rumble_policy_set_checked", "rumble_set_checked",
         "rumble_stop", "rumble_stop_checked", "rumble_passthrough"}
#: O ÚNICO MÉTODO CRU, e ele é o que dá endereço aos outros quatro.
METODOS = {"controller.target.set"}


#: O QUE ESTA ABA DECLARA À RÉGUA — o piso e as provas moram AQUI, não no teste.
PAGINA = "05-vibracao.html"
PISO_DA_ABA = 3
PROVAS = [
    # A política NÃO leva alvo: é da mesa, e mirar antes só mentiria melhor.
    {"pagina": PAGINA, "gesto": "forca", "clique": {"forca": "max"},  # (noqa-acento) id
     "chama": [("rumble_policy_set_checked", ["max"], {"timeout": 1.0})]},
    # QUATRO chamadas, e a ordem é o gesto inteiro: mirar, vibrar, calar,
    # devolver. Invertidas, o passthrough soltaria antes de o silêncio ir.
    {"pagina": PAGINA, "gesto": "testar", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["controller.target.set"], {"index": 0}),
               ("rumble_set_checked", [160, 220], {}),
               ("rumble_stop", [], {}),
               ("rumble_passthrough", [True], {})]},
    {"pagina": PAGINA, "gesto": "parar", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["controller.target.set"], {"index": 0}),
               ("rumble_stop_checked", [], {}),
               ("rumble_passthrough", [True], {})]},
]

#: OS DOIS QUE O DAEMON ACEITA E NÃO PUBLICA, e a razão é do assunto: "Testar"
#: e "Parar" produzem um efeito FÍSICO — o plástico treme na mão dela — e o
#: tremor não deixa rastro no `state_full`. O `rumble_ff` conta os pedidos do
#: JOGO ao gamepad virtual; um teste mandado pela tela não passa por ali.
#:
#: A prova destes dois é a mão dela, e é honesto dizer isso em vez de fingir que
#: uma régua os alcança.
SEM_ECO = ("testar", "parar")
