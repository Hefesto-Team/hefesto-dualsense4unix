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


def alvo_fora_da_mesa(host: Any) -> str | None:
    """Nome do alvo de edição quando ele NÃO está na mesa; ``None`` se está.

    Lê o estado de UM dono só — o mapa de conectados que a aba Status
    recalcula do ``state_full`` a cada tique (``_target_uniq_by_index``, só
    controles conectados) e o alvo escolhido (``_edit_target_uniq``, mantido
    quando o controle some — R-16). ``getattr`` defensivo porque os mixins só
    convivem de fato na instância composta.

    **Devolve ``None`` só quando a janela NÃO TEM o mapa** — o atributo não
    existe (host parcial de teste, mixin instanciada sozinha). Chamar de
    "guardado" o que talvez tenha sido aplicado seria trocar uma mentira por
    outra.

    **Mapa VAZIO não é "não sei": é "não tem DualSense na mesa"** (conserto
    1.5). A guarda anterior tratava os dois como a mesma coisa e devolvia
    ``None``, e com isso os toasts voltavam a afirmar sucesso no exato caso em
    que o daemon responde ``guardado_em=[uniq]``. A justificativa escrita —
    "nenhum tique do daemon ainda" — não existe no produto, e está medida:

    * ``_edit_target_uniq`` só é escrito em dois lugares
      (``status_actions.py``): ``= None`` no construtor da aba e
      ``_sync_edit_target``, que roda DEPOIS de ``_update_target_maps`` na
      mesma passada de ``_refresh_controller_target_combo``. Alvo preenchido
      sem mapa preenchido nunca é "antes do primeiro tique";
    * e o estado é alcançável de verdade: com ZERO DualSense e um externo na
      mesa (8BitDo, Pro Controller), ``editavel = contagem.adotados >= 1`` é
      falso, ``_sync_edit_target`` NÃO é chamado — o alvo fica de pé, como a
      R-16 quer — e o mapa vem vazio de ``_update_target_maps([])``. É o ramo
      que o próprio código comenta com *"Só externos conectados: nenhum radio
      (não há alvo de edição)"*.
    """
    uniq = getattr(host, "_edit_target_uniq", None)
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


__all__ = [
    "ALVO_SEM_NOME",
    "GUARDADO",
    "alvo_fora_da_mesa",
    "com_artigo",
    "coop_manda_nas_luzes",
    "frase_de_guardado",
    "guardado_ate_o_alvo_voltar",
    "guardado_ate_o_coop_sair",
    "guardado_ate_o_nativo_sair",
    "modo_nativo_manda_no_output",
    "nome_curto_do_alvo",
]
