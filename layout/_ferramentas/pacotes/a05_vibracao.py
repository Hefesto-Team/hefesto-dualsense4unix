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

from . import Contexto, registrar

SEM_DONO: dict[str, str] = {}


def _do_vpad(ff: dict, player) -> dict:
    """O bloco `per_vpad` daquele jogador, ou `{}`.

    Casa por `player`, não por posição na lista: a ordem do `per_vpad` é a de
    criação dos gamepads virtuais, e ela não acompanha a ordem da mesa quando um
    controle cai e volta.
    """
    for v in (ff or {}).get("per_vpad") or []:
        if v.get("player") == player:
            return v
    return {}


@registrar("05-vibracao.html")
def pacote(ctx: Contexto) -> dict:
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
    """
    import mesa_viva

    from hefesto_dualsense4unix.app.telas import vibracao as _tela

    bruto = _tela.pacote_da_mesa(ctx.state, ctx.mesa, ctx.conectados,
                                 contagem=mesa_viva.texto_da_contagem(ctx.mesa))
    colunas: dict[str, dict] = {}
    for uniq, col in (bruto.get("colunas") or {}).items():
        pct = col.get("pct") or {}
        plano = {
            "identidade": _sem_marcacao(col.get("identidade", "")),
            "forca": col.get("forca", "—"),
            "forca-pct": str(pct.get("w", "")).rstrip("%"),
        }
        for lado, m in (col.get("motores") or {}).items():
            plano[f"motor-{lado}"] = m.get("n", "—")
            plano[f"motor-{lado}-pct"] = str(m.get("w", "")).rstrip("%")
        colunas[uniq] = plano
    return {
        "colunas": colunas,
        "mesa": {"forca": ctx.state.get("rumble_policy") or "—",
                 "passthrough": bool(ctx.state.get("rumble_passthrough"))},
        "sem_dono": {},
        "cobertura": {"pintados": sum(len(v) for v in colunas.values()) + 2,
                      "sem_dono": 0},
    }


def _sem_marcacao(texto: str) -> str:
    """Tira o HTML do produto: a tela nova escreve `textContent`, não `innerHTML`.

    A camada do produto monta `P1 <span class="pt">•</span> Não sei` porque a
    janela dela injeta como HTML. Escrever isso num `textContent` mostraria as
    tags. O separador vira o `·` que o resto desta interface usa.
    """
    import re as _re

    return _re.sub(r"<[^>]+>", "·", texto).replace("··", "·").strip()




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


def _uniq(o: dict) -> str:
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


def _resposta(r) -> tuple[bool, str | None]:
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


def _mirar(ctx: Contexto, o: dict, p) -> str:
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
def forca(ctx: Contexto, o: dict, p) -> None:
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
def testar(ctx: Contexto, o: dict, p) -> None:
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
def parar(ctx: Contexto, o: dict, p) -> None:
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
    {"pagina": PAGINA, "gesto": "forca", "clique": {"forca": "max"},  # (noqa-acento)
     "chama": [("rumble_policy_set_checked", ["max"], {"timeout": 1.0})]},
    # QUATRO chamadas, e a ordem é o gesto inteiro: mirar, vibrar, calar,
    # devolver. Invertidas, o passthrough soltaria antes de o silêncio ir.
    {"pagina": PAGINA, "gesto": "testar", "clique": {},  # (noqa-acento)
     "chama": [("chamar", ["controller.target.set"], {"index": 0}),
               ("rumble_set_checked", [160, 220], {}),
               ("rumble_stop", [], {}),
               ("rumble_passthrough", [True], {})]},
    {"pagina": PAGINA, "gesto": "parar", "clique": {},  # (noqa-acento)
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
