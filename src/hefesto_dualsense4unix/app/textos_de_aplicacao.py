"""O vocabulário de "GUARDADO" — a D-9 mora aqui, e só aqui.

**A decisão (D-9, 14/08/2026):** aplicar num controle DESCONECTADO é
*guardado*, não *aplicado*. O mecanismo sempre esteve certo — o override fica
registrado e o hotplug o aplica quando o controle volta
(`core/backend_pydualsense.apply_output_for`, que agora devolve
``"registrado"``); era a **palavra** que mentia.

**Por que um módulo só para as frases do guardado.** A regra de execução da própria
D-9: *"as três entregas põem esse vocabulário NUM LUGAR SÓ, para que trocá-lo
seja uma linha, e não uma caçada por strings"*. Espalhar "guardado" por cinco
arquivos seria repetir, com a palavra certa, o defeito que ela veio consertar —
a janela dizendo coisas diferentes sobre o mesmo estado.

**As TRÊS razões de um ajuste ficar guardado** (eram duas quando este módulo
nasceu; o Modo Nativo entrou no conserto 1.3 e o cabeçalho ficou para trás), e
elas são diferentes na tela porque são diferentes no mundo:

1. **o alvo saiu da mesa** — o controle escolhido no cabeçalho não está
   conectado. O alvo é MANTIDO de propósito quando o controle some (R-16), e
   com quatro controles isso deixa de ser caso raro;
2. **o co-op está ligado** — quem manda nas 5 luzes é ele, por construção
   (a camada do co-op vence a escolha manual no merge do backend). A aba
   Lightbar já dizia isso três centímetros abaixo do toast que dizia o
   contrário: era a tela se contradizendo sozinha;
3. **o Modo Nativo está ligado** — o JOGO é o dono do `hidraw`, e o backend
   muta TODA escrita de output (`_output_mute`). Esta é a terceira linha da
   tabela de mentiras da MESA-CHEIA-09, e a única que sobreviveu à primeira
   leva: o backend devolvia "escreveu" mutado, e o toast dizia "aplicado" com
   zero byte no fio. Ao desmutar, o desejado é re-escrito — então é
   *guardado*, exatamente como o do controle que saiu da mesa.

**As razões se ACUMULAM, e a frase tem de acumular junto** (conserto 1.5).
Duas delas valendo ao mesmo tempo é o estado NORMAL da mesa dela: o co-op fica
ligado e a R-16 mantém o alvo justamente quando o controle cai. Enquanto cada
gesto escolhia UMA razão e voltava, a tela prometia uma liberação que não
libera — *"Vale quando o co-op sair"* com o controle fora da mesa é falso, e
*"vai valer quando o Controle 2 voltar"* com o co-op ligado é falso do mesmo
jeito. Por isso a decisão de ordem mora em :func:`frase_de_guardado`, que
recebe as três condições e monta UMA frase com todas as pendências.

**Função pura, sem GTK.** Quem monta a frase não toca em widget, e é por isso
que todas se provam sem janela nenhuma.
"""
from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.app.alvo_de_edicao import MOTIVO_SEM_ESTADO, alvo_de_edicao
from hefesto_dualsense4unix.app.ipc_bridge import destinos_da_aplicacao

#: A palavra. Trocá-la é trocar esta linha.
GUARDADO = "guardado"

#: Como o produto chama um controle sem nome próprio. Cai aqui quando a janela
#: perdeu o rótulo do alvo (ele saiu da mesa antes do primeiro tique).
#:
#: Já traz o determinante DENTRO dele ("esse"), e é por isso que
#: :func:`com_artigo` existe: a frase do guardado dizia "quando o esse controle
#: voltar" — pt-BR quebrado saindo do módulo cujo motivo de existir é a palavra
#: certa (conserto 1.5).
ALVO_SEM_NOME = "esse controle"


def com_artigo(alvo: str) -> str:
    """``"Controle 2"`` -> ``"o Controle 2"``; ``ALVO_SEM_NOME`` sai intacto.

    O rótulo do seletor é um nome ("Controle 2", "8BitDo") e pede artigo; o
    nome de fallback é um sintagma que já traz o seu determinante. Colar "o"
    nos dois compunha *"quando o esse controle voltar"*.
    """
    return alvo if alvo == ALVO_SEM_NOME else f"o {alvo}"


def nome_curto_do_alvo(label: str | None) -> str:
    """``"Controle 2 (BT)"`` -> ``"Controle 2"``; vazio -> ``ALVO_SEM_NOME``.

    O rótulo do seletor carrega o transporte entre parênteses. Na frase do
    guardado o transporte é ruído — ela precisa saber QUEM, não por onde;
    e o transporte de um controle que está fora da mesa é justamente o dado
    que pode ter mudado quando ele voltar.
    """
    if not isinstance(label, str) or not label.strip():
        return ALVO_SEM_NOME
    return label.split("(")[0].strip() or ALVO_SEM_NOME


class AlvoDesconhecidoNaMesaError(RuntimeError):
    """`alvo_fora_da_mesa` foi chamada com a janela sem saber o alvo.

    Z2-3 (24/08/2026). Não deveria disparar em produção: os chamadores de
    hoje (Lightbar, Gatilhos) já recusam o gesto ANTES de chegar aqui — a
    escrita para no choke point (`_aplicar_cor_no_controle`,
    `_apply_trigger`...) assim que `alvo_de_edicao(host).desconhecido` é
    verdade (Z2-1/Z2-2). Esta exceção existe para o QUINTO chamador futuro
    que esquecer esse cheque: ele quebra alto em vez de compor "guardado"
    ou "aplicado" sobre um gesto que não devia ter acontecido — a mentira
    que `app/alvo_de_edicao.py` documenta como o pior caso medido do P3
    ("Cor enviada ao controle", no singular, com zero controles ligados).
    """


def alvo_fora_da_mesa(host: Any) -> str | None:
    """Nome do alvo de edição quando ele NÃO está na mesa; ``None`` se está.

    Lê o estado de UM dono só — `app/alvo_de_edicao.py` — e o mapa de
    conectados que a aba Status recalcula do ``state_full`` a cada tique
    (``_target_uniq_by_index``, só controles conectados).

    **Levanta `AlvoDesconhecidoNaMesaError` quando a janela não sabe o alvo.**
    Chamar de "guardado" (ou de "aplicado") o que talvez nem devesse ter
    escrito seria trocar uma mentira por outra — e ``None`` some em
    silêncio dentro de um ``or`` (`frase_de_guardado(...) or
    _TOAST_COR_ENVIADA...`), que é exatamente como a mentira do P3 chegava
    à tela. Zero chamadores de produção precisam capturar esta exceção
    hoje: todos já checam ``alvo_de_edicao(host).desconhecido`` antes.

    **Devolve ``None``** quando ela ESCOLHEU "Todos" (não há alvo a
    guardar) ou quando o alvo escolhido está conectado agora.

    **Mapa VAZIO não é "não sei": é "não tem DualSense na mesa"** (conserto
    1.5). Com ZERO DualSense e um externo na mesa (8BitDo, Pro Controller),
    ``editavel = contagem.adotados >= 1`` é falso, ``_sync_edit_target`` não
    é chamado — o alvo fica de pé, como a R-16 quer — e o mapa vem vazio de
    ``_update_target_maps([])``: é o ramo que o próprio código comenta com
    *"Só externos conectados: nenhum radio (não há alvo de edição)"*.
    """
    estado = alvo_de_edicao(host)
    if estado.desconhecido:
        raise AlvoDesconhecidoNaMesaError(estado.motivo or MOTIVO_SEM_ESTADO)
    uniq = estado.uniq
    if not isinstance(uniq, str) or not uniq:
        return None  # "Todos": a escrita é global, não há alvo a guardar
    mapa = getattr(host, "_target_uniq_by_index", None)
    if not isinstance(mapa, dict):
        return None
    conectados = {v for v in mapa.values() if isinstance(v, str) and v}
    if uniq in conectados:
        return None
    return nome_curto_do_alvo(getattr(host, "_edit_target_label", None))


def coop_manda_nas_luzes(host: Any) -> bool:
    """O co-op está ligado — e, com ele ligado, as 5 luzes são dele.

    Mesmo dado que o rótulo de leitura de volta da aba já usa
    (``_coop_ligado``, mantido pela Status a partir do ``state_full``): um
    dono só para as duas frases, que era exatamente o que faltava quando o
    toast e o rótulo se contradiziam.
    """
    return bool(getattr(host, "_coop_ligado", False))


def modo_nativo_manda_no_output(host: Any) -> bool:
    """O Modo Nativo está ligado — e, com ele, o dono do controle é o jogo.

    Mesmo dado do banner e dos cards (``native_mode`` do ``state_full``,
    publicado pela aba Status em ``_modo_nativo_ligado``): um dono só para a
    frase, pelo mesmo motivo que o co-op tem um. ``getattr`` defensivo porque
    os mixins só convivem de fato na instância composta — e o padrão ``False``
    é o seguro: sem saber, a tela não inventa uma pendência.
    """
    return bool(getattr(host, "_modo_nativo_ligado", False))


#: Cada pendência em DUAS metades: por que não vale AGORA, e o que precisa
#: acontecer para valer. Separá-las é o que deixa somar duas sem inventar uma
#: frase nova para cada combinação — e é por isso que as frases de UMA
#: pendência, logo abaixo, se montam destas mesmas peças em vez de repetirem o
#: texto (repetir era como as duas metades divergiriam).
_MOTIVO_COOP = "com o co-op ligado, quem manda nas 5 luzes é ele"
_LIBERA_COOP = "o co-op sair"
_MOTIVO_NATIVO = "em Modo Nativo quem manda no controle é o jogo"
_LIBERA_NATIVO = "o Modo Nativo sair"


def guardado_ate_o_nativo_sair(assunto: str) -> str:
    """*"<assunto> — guardado; em Modo Nativo quem manda no controle é o jogo."*

    Mesma estrutura das outras duas de propósito: o estado é o mesmo
    (guardado), o que muda é o evento que o libera.
    """
    return f"{assunto} — {GUARDADO}; {_MOTIVO_NATIVO}. Vale quando {_LIBERA_NATIVO}."


def guardado_ate_o_alvo_voltar(assunto: str, alvo: str) -> str:
    """*"<assunto> — guardado, vai valer quando o Controle N voltar."*

    A frase é a da D-9, com o assunto na frente para ela saber O QUE ficou
    guardado quando três toasts se sucedem.
    """
    return f"{assunto} — {GUARDADO}, vai valer quando {com_artigo(alvo)} voltar."


def guardado_ate_o_coop_sair(assunto: str) -> str:
    """*"<assunto> — guardado; com o co-op ligado, quem manda nas 5 luzes é ele."*

    Mesma estrutura da frase de cima de propósito: o estado é o mesmo
    (guardado), o que muda é o que precisa acontecer para valer.
    """
    return f"{assunto} — {GUARDADO}; {_MOTIVO_COOP}. Vale quando {_LIBERA_COOP}."


def _e(partes: list[str]) -> str:
    """``["a", "b", "c"]`` -> ``"a, b e c"`` (a mesma vírgula do resto da tela)."""
    if len(partes) == 1:
        return partes[0]
    return ", ".join(partes[:-1]) + " e " + partes[-1]


def _ponto_e_virgula(partes: list[str]) -> str:
    """Junta os MOTIVOS. Ponto e vírgula, não " e ": o motivo do co-op já tem
    uma vírgula dentro dele, e somar com " e " produzia *"…é ele e o Controle 2
    não está na mesa"*, que se lê como uma frase só."""
    return "; ".join(partes)


def frase_de_guardado(
    assunto: str,
    *,
    alvo_ausente: str | None,
    coop: bool = False,
    nativo: bool = False,
) -> str | None:
    """A frase do guardado com TODAS as pendências; ``None`` se não há nenhuma.

    Ponto único de decisão do vocabulário — inclusive da ORDEM, que era o
    defeito (conserto 1.5). Cada gesto perguntava as três condições e voltava
    na primeira que batesse; com duas valendo ao mesmo tempo — o estado normal
    da mesa dela, co-op ligado e o alvo mantido pela R-16 depois que o
    controle cai — a tela prometia uma liberação que não libera nada.

    Ordem das pendências: os donos de AGORA (co-op, Modo Nativo) antes da
    ausência do alvo, a mesma de antes, porque eles valem mesmo com o controle
    na mesa. Com UMA pendência a frase é palavra por palavra a que já saía.

    ``coop`` só é verdade para quem escreve os 5 LEDs de jogador: a camada do
    co-op tem vocabulário de um campo só (``_COOP_LAYER_FIELDS =
    ("player_leds",)`` no backend), então ela não tem opinião sobre a cor da
    lightbar.
    """
    motivos: list[str] = []
    liberacoes: list[str] = []
    if coop:
        motivos.append(_MOTIVO_COOP)
        liberacoes.append(_LIBERA_COOP)
    if nativo:
        motivos.append(_MOTIVO_NATIVO)
        liberacoes.append(_LIBERA_NATIVO)
    if alvo_ausente:
        motivos.append(f"{com_artigo(alvo_ausente)} não está na mesa")
        liberacoes.append(f"{com_artigo(alvo_ausente)} voltar")
    if not liberacoes:
        return None
    if len(liberacoes) == 1:
        if coop:
            return guardado_ate_o_coop_sair(assunto)
        if nativo:
            return guardado_ate_o_nativo_sair(assunto)
        assert alvo_ausente is not None
        return guardado_ate_o_alvo_voltar(assunto, alvo_ausente)
    return (
        f"{assunto} — {GUARDADO}: {_ponto_e_virgula(motivos)}. "
        f"Vale quando {_e(liberacoes)}."
    )


#: T5/T7 (ONDA0-Z1, 24/08/2026). A frase de "o daemon respondeu e não houve
#: nem aplicado nem guardado" — a rota clássica de mesa vazia com o alvo em
#: "Todos", medida na bancada viva em 23/08 (`{"status":"ok","aplicado_em":
#: [],"guardado_em":[]}` com a aba dizendo "aplicado").
#:
#: PROVISÓRIO — decisão dela (D3, 23/08): texto novo de tela. Enquanto não
#: passar pelo olho dela, esta é a redação de trabalho — funcional e honesta,
#: não a redação final.
#:
#: CORREÇÃO DE FATO — 25/08/2026, achada pela conferência da frente C1.
#: Esta constante era UMA só e afirmava a causa: *"não há controle na mesa"*.
#: **`_destinos_do_broadcast` (daemon/ipc_handlers.py:1130-1205) devolve duas
#: listas vazias em CINCO situações, e só UMA é mesa vazia** — as outras são
#: Modo Nativo ligado COM controle na mesa (:1183), `get_output_target_index`
#: ausente (:1190), exceção ao ler o índice (:1195) e alvo sem uniq estável
#: (:1203). Nas quatro últimas a barra afirmava um fato falso, e no Modo
#: Nativo era REGRESSÃO: o código anterior a `41541a7` acertava, dizendo
#: *"guardado; em Modo Nativo quem manda no controle é o jogo"*.
#:
#: São três agora porque a janela distingue três estados e não mais:
#: ela SABE o Modo Nativo (`_modo_nativo_ligado`), SABE se a mesa está vazia
#: (`_target_uniq_by_index`), e NÃO TEM COMO SABER os outros três casos.
#: A terceira frase existe para esse não-saber — "olhei e não sei por quê" é
#: uma resposta, e disfarçá-la de diagnóstico é o defeito de forma que esta
#: função inteira existe para matar.
NADA_ACONTECEU = "nenhum controle recebeu"
NADA_ACONTECEU_MESA_VAZIA = "nenhum controle recebeu — não há controle na mesa"
NADA_ACONTECEU_NATIVO = f"nenhum controle recebeu — {_MOTIVO_NATIVO}"


def mesa_vazia(host: Any) -> bool:
    """A mesa não tem DualSense conectado AGORA — e a janela sabe disso.

    Mesmo mapa que :func:`alvo_fora_da_mesa` já lê (`_target_uniq_by_index`,
    que a aba Status recalcula do ``state_full`` a cada tique, só com
    controles conectados).

    **O padrão é ``False``, e é o seguro**: sem o mapa, a janela não sabe se
    a mesa está vazia — e afirmar que está seria inventar o diagnóstico que
    a `NADA_ACONTECEU_MESA_VAZIA` só pode dar quando é verdade. Mesmo
    critério do ``getattr`` defensivo de :func:`modo_nativo_manda_no_output`.
    """
    mapa = getattr(host, "_target_uniq_by_index", None)
    if not isinstance(mapa, dict):
        return False
    return not any(isinstance(v, str) and v for v in mapa.values())


def frase_do_desfecho(
    assunto: str,
    corpo: object,
    host: object,
    *,
    coop_aplica: bool = False,
) -> str:
    """A frase de um gesto de aplicação, com o CORPO do daemon como autoridade.

    ELO-MUDO-01/P1 (ONDA0-Z1, 24/08/2026, T1). Até esta função, cada aba
    decidia "aplicado" x "guardado" pela HEURÍSTICA do estado da janela — as
    três funções logo abaixo — que cobre só duas das três razões que o daemon
    já conhecia, e caía exatamente na rota que a bancada mediu em 23/08: mesa
    vazia, alvo em "Todos", corpo dizendo zero destino, tela dizendo
    "aplicado". **A inversão é o coração da tarefa**: antes a janela deduzia e
    o daemon era ignorado; agora o daemon manda e a janela só preenche o
    silêncio quando ele não respondeu.

    A ORDEM DE DECISÃO, e ela é a entrega:

    1. o daemon RECUSOU e explicou (``corpo["motivo"]``, mesmo campo que
       :func:`~hefesto_dualsense4unix.app.ipc_bridge._recusa_no_corpo` lê do
       outro lado da ponte) — a frase é o motivo DELE, nunca uma dedução
       nossa;
    2. :func:`~hefesto_dualsense4unix.app.ipc_bridge.destinos_da_aplicacao`:
       ``aplicado_em`` com alguém dentro é **aplicado** — a frase de sempre,
       sem número quando é um destino só (a mordida gêmea que prova que a
       cura não avançou longe demais); só ``guardado_em`` com alguém é
       **guardado**, e as TRÊS razões da janela (``host``) entram como o
       PORQUÊ, não mais como a decisão;
    3. as duas listas vazias com corpo presente: nada aconteceu, e a frase
       diz isso — é o caso medido em 23/08, e o motivo de esta função existir;
    4. corpo ausente (``None``, ``_corpo_do_daemon`` não teve o que ler): só
       aí a heurística de hoje decide, porque não há resposta do daemon a
       ler. As três funções de leitura de ``host`` não somem — mudam de
       AUTORIDADE (ramo 4) para EXPLICAÇÃO (ramo 2).

    ``coop_aplica``: o co-op só tem opinião sobre os 5 LEDs de jogador
    (``_COOP_LAYER_FIELDS = ("player_leds",)`` no backend) — nunca sobre a cor
    da lightbar ou o gatilho. Quem chama por um assunto que NÃO é o desenho
    dos 5 LEDs deixa o padrão ``False``; só o chamador de ``player_leds`` passa
    ``True``. Ignorar isso atribuiria ao co-op uma recusa que é do Modo Nativo
    ou do alvo fora da mesa, num assunto que o co-op nunca governou — o mesmo
    defeito de frase errada, só que com a palavra certa por engano.
    """
    if isinstance(corpo, dict):
        motivo = corpo.get("motivo")
        if isinstance(motivo, str) and motivo:
            # NATIVO-RUMBLE-01 já mediu (`ipc_bridge._recusa_no_corpo`): um
            # `motivo` presente não é sinônimo de recusa — `status: "ok"` com
            # `motivo` é sucesso PARCIAL (ex.: `rumble.stop` que solta o par
            # mas não cala o motor que o jogo ainda segura pelo hidraw).
            # Achado pelo advogado da premissa em 24/08/2026: sem esta
            # distinção, um futuro consumidor de Rumble rotularia sucesso
            # parcial como recusa — a mesma classe de mentira que esta
            # função existe para matar, na direção oposta.
            if corpo.get("status") == "ok":
                return f"{assunto} — {motivo}"
            return f"{assunto} — recusado: {motivo}"
        aplicado_em, guardado_em = destinos_da_aplicacao(corpo)
        if aplicado_em:
            if len(aplicado_em) <= 1:
                return f"{assunto} aplicado"
            return f"{assunto} aplicado em {len(aplicado_em)} controles"
        if guardado_em:
            return (
                frase_de_guardado(
                    assunto,
                    alvo_ausente=alvo_fora_da_mesa(host),
                    coop=coop_aplica and coop_manda_nas_luzes(host),
                    nativo=modo_nativo_manda_no_output(host),
                )
                or f"{assunto} — {GUARDADO}"
            )
        # Duas listas vazias: NADA foi escrito e NADA foi guardado. A frase
        # diz o PORQUÊ apenas quando a janela o conhece — a mesma ordem do
        # ramo 4, e pela mesma razão. O daemon colapsa cinco caminhos neste
        # par vazio; a janela enxerga dois deles e cala sobre os outros três.
        if modo_nativo_manda_no_output(host):
            return f"{assunto} — {NADA_ACONTECEU_NATIVO}"
        if mesa_vazia(host):
            return f"{assunto} — {NADA_ACONTECEU_MESA_VAZIA}"
        return f"{assunto} — {NADA_ACONTECEU}"
    # Corpo ausente: a heurística de hoje é o que sobra, porque não há
    # resposta do daemon a ler. Mesma ordem de sempre — o dono de AGORA
    # (Modo Nativo, depois co-op quando aplica) antes da ausência do alvo.
    if modo_nativo_manda_no_output(host):
        return guardado_ate_o_nativo_sair(assunto)
    if coop_aplica and coop_manda_nas_luzes(host):
        return guardado_ate_o_coop_sair(assunto)
    fora = alvo_fora_da_mesa(host)
    if fora:
        return guardado_ate_o_alvo_voltar(assunto, fora)
    return f"{assunto} aplicado"


__all__ = [
    "ALVO_SEM_NOME",
    "GUARDADO",
    "NADA_ACONTECEU",
    "NADA_ACONTECEU_MESA_VAZIA",
    "NADA_ACONTECEU_NATIVO",
    "alvo_fora_da_mesa",
    "com_artigo",
    "coop_manda_nas_luzes",
    "frase_de_guardado",
    "frase_do_desfecho",
    "guardado_ate_o_alvo_voltar",
    "guardado_ate_o_coop_sair",
    "guardado_ate_o_nativo_sair",
    "mesa_vazia",
    "modo_nativo_manda_no_output",
    "nome_curto_do_alvo",
]
