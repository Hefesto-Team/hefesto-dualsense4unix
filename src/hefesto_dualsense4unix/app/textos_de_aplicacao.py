"""O vocabulário de "GUARDADO" — a D-9 mora aqui, e só aqui."""
from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.app.alvo_de_edicao import MOTIVO_SEM_ESTADO, alvo_de_edicao
from hefesto_dualsense4unix.app.ipc_bridge import destinos_da_aplicacao

GUARDADO = "guardado"

ALVO_SEM_NOME = "esse controle"


def com_artigo(alvo: str) -> str:
    """``"Controle 2"`` -> ``"o Controle 2"``; ``ALVO_SEM_NOME`` sai intacto."""
    return alvo if alvo == ALVO_SEM_NOME else f"o {alvo}"


def nome_curto_do_alvo(label: str | None) -> str:
    """``"Controle 2 (BT)"`` -> ``"Controle 2"``; vazio -> ``ALVO_SEM_NOME``."""
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

    **Devolve ``None``** quando o usuário ESCOLHEU "Todos" (não há alvo a
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
        return None
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


_MOTIVO_COOP = "com o co-op ligado, quem manda nas 5 luzes é ele"
_LIBERA_COOP = "o co-op sair"
_MOTIVO_NATIVO = "em Modo Nativo quem manda no controle é o jogo"
_LIBERA_NATIVO = "o Modo Nativo sair"


def guardado_ate_o_nativo_sair(assunto: str) -> str:
    """*"<assunto> — guardado; em Modo Nativo quem manda no controle é o jogo."*"""
    return f"{assunto} — {GUARDADO}; {_MOTIVO_NATIVO}. Vale quando {_LIBERA_NATIVO}."


def guardado_ate_o_alvo_voltar(assunto: str, alvo: str) -> str:
    """*"<assunto> — guardado, vai valer quando o Controle N voltar."*"""
    return f"{assunto} — {GUARDADO}, vai valer quando {com_artigo(alvo)} voltar."


def guardado_ate_o_coop_sair(assunto: str) -> str:
    """*"<assunto> — guardado; com o co-op ligado, quem manda nas 5 luzes é ele."*"""
    return f"{assunto} — {GUARDADO}; {_MOTIVO_COOP}. Vale quando {_LIBERA_COOP}."


def _e(partes: list[str]) -> str:
    """``["a", "b", "c"]`` -> ``"a, b e c"`` (a mesma vírgula do resto da tela)."""
    if len(partes) == 1:
        return partes[0]
    return ", ".join(partes[:-1]) + " e " + partes[-1]


def _ponto_e_virgula(partes: list[str]) -> str:
    """Junta os MOTIVOS. Ponto e vírgula, não " e ": o motivo do co-op já tem"""
    return "; ".join(partes)


def frase_de_guardado(
    assunto: str,
    *,
    alvo_ausente: str | None,
    coop: bool = False,
    nativo: bool = False,
) -> str | None:
    """A frase do guardado com TODAS as pendências; ``None`` se não há nenhuma."""
    motivos: list[str] = []
    liberacoes: list[str] = []
    if coop:
        motivos.append(_MOTIVO_COOP)
        liberacoes.append(_LIBERA_COOP)
    if nativo:
        motivos.append(_MOTIVO_NATIVO)
        liberacoes.append(_LIBERA_NATIVO)
    if alvo_ausente:
        motivos.append(f"{com_artigo(alvo_ausente)} não está ligado")
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


#: Modo Nativo ligado COM controle na mesa (:1183), `get_output_target_index`
NADA_ACONTECEU = "nenhum controle recebeu"
NADA_ACONTECEU_MESA_VAZIA = "nenhum controle recebeu — não há controle ligado"
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
    nativo_aplica: bool = True,
) -> str:
    """A frase de um gesto de aplicação, com o CORPO do daemon como autoridade."""
    nativo = nativo_aplica and modo_nativo_manda_no_output(host)
    if isinstance(corpo, dict):
        motivo = corpo.get("motivo")
        if isinstance(motivo, str) and motivo:
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
                    nativo=nativo,
                )
                or f"{assunto} — {GUARDADO}"
            )
        if nativo:
            return f"{assunto} — {NADA_ACONTECEU_NATIVO}"
        if mesa_vazia(host):
            return f"{assunto} — {NADA_ACONTECEU_MESA_VAZIA}"
        return f"{assunto} — {NADA_ACONTECEU}"
    if nativo:
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
