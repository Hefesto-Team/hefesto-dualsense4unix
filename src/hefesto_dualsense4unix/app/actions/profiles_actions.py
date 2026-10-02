"""Aba Perfis: lista + editor de matcher com persistência em disco.

Dois modos de editor:
- simples   (default): radios "Aplica a" + slider Prioridade humanamente legíveis.
- avancado  (toggle):  campos crus window_class / title_regex / process_name.

A preferência de modo persiste em ~/.config/hefesto-dualsense4unix/gui_preferences.json via
gui_prefs.load_gui_prefs / gui_prefs.set_pref.
"""
# ruff: noqa: E402
from __future__ import annotations

import contextlib
from typing import Any, NamedTuple

import gi
from pydantic import ValidationError

gi.require_version("Gtk", "3.0")
from gi.repository import GObject, Gtk

from hefesto_dualsense4unix.app.actions.carona_do_wrapper import (
    GESTO_APLICAR,
    GESTO_SALVAR,
    CaronaDoWrapperMixin,
)
from hefesto_dualsense4unix.app.actions.home_actions import (
    texto_do_custo_da_mascara,
    texto_do_radio_fragil,
)
from hefesto_dualsense4unix.app.actions.profile_writer import carimbo_que_o_save_leva
from hefesto_dualsense4unix.app.gui_prefs import load_gui_prefs, set_pref
from hefesto_dualsense4unix.app.ipc_bridge import (
    PROFILE_SWITCH_TIMEOUT_S,
    active_profile_name,
    call_async,
    run_in_thread,
)
from hefesto_dualsense4unix.app.widgets import SegmentedSelector
from hefesto_dualsense4unix.integrations.jogos_locais import (
    JogoLocal,
    casa_com_o_que_ela_digitou,
    catalogo_de_jogos,
    frase_do_campo_do_jogo,
    nomes_por_appid,
)
from hefesto_dualsense4unix.profiles import schema as _schema
from hefesto_dualsense4unix.profiles.loader import (
    delete_profile,
    load_all_profiles,
    perfil_em_disco,
    save_profile,
)
from hefesto_dualsense4unix.profiles.schema import (
    Match,
    MatchAny,
    MatchCriteria,
    MatchManual,
    Profile,
    ProfileModeConfig,
    normalizar_gamepad_flavor,
)
from hefesto_dualsense4unix.profiles.simple_match import (
    MENSAGENS_DE_GENTE,
    detect_simple_preset,
    from_simple_choice,
    normalize_appid,
    simple_extra,
)
from hefesto_dualsense4unix.profiles.slug import find_by_slug, mesmo_slug
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.markup import escapar_markup

logger = get_logger(__name__)

#
_RADIO_IDS = ("any", "steam", "browser", "terminal", "editor", "game",
              "steam_game", "janela")

_IDS_COM_CAMPO_LIVRE = ("game", "steam_game", "janela")

PRIORIDADE_MAXIMA = _schema.PRIORIDADE_MAXIMA

_FOLGA_ACIMA_DO_CATCH_ALL = 10

_CAMPO_LIVRE_DICAS: dict[str, tuple[str, str]] = {
    "game": (
        "ex.: eldenring",
        "Nome do programa Linux do jogo (o basename de /proc/PID/exe). "
        "Em jogo da Steam/Proton isso costuma ser o binário do wine — nesse "
        "caso use \"Jogo da Steam\".",
    ),
    "steam_game": (
        "nome do jogo, endereço da loja, ou o número (ex.: 1599660)",
        "Digite o nome do jogo e escolha na lista dos que estão nesta máquina, "
        "cole o endereço da página do jogo na loja da Steam "
        "(store.steampowered.com/app/…), ou escreva o número direto. Com o "
        "jogo aberto, o campo é preenchido sozinho.",
    ),
    "janela": (
        "ex.: GrimFandango",
        "A classe da janela do jogo — o que o detector de janela do Hefesto "
        "vê. Com o jogo em foco, o botão Detectar preenche sozinho. Use esta "
        "opção para jogo que não é da Steam.",
    ),
}

# o MESMO da interface nova (`perfis_web.AMBIENTE_DO_PRESET["janela"]`) de
_APLICA_A_ITEMS: list[tuple[str, str]] = [
    ("any", "Qualquer"),
    ("steam", "Steam"),
    ("browser", "Navegador"),
    ("terminal", "Terminal"),
    ("editor", "Editor"),
    ("game", "Jogo"),
    ("steam_game", "Jogo da Steam"),
    ("janela", "Jogo (pela janela)"),
]

_MODE_KIND_ITEMS: list[tuple[str, str]] = [
    ("none", "Não mexer no modo"),
    ("desktop", "Controlar o PC"),
    ("gamepad", "Jogar pelo Hefesto"),
    ("native", "Conexão Nativa (Sony)"),
]

_KIND_NATIVO = "native"


def frase_do_radio_fragil_no_modo(kind: object, state: Any) -> str | None:
    """O aviso de rádio frágil, **quando o modo escolhido aqui é o Nativo**."""
    if kind != _KIND_NATIVO:
        return None
    return texto_do_radio_fragil(state if isinstance(state, dict) else None)


_MODE_FLAVOR_ITEMS: list[tuple[str, str]] = [
    ("dualsense", "DualSense (botões PlayStation)"),
    ("xbox", "Xbox 360"),
    ("nintendo", "Nintendo Pro (botões da Nintendo)"),
]

# DualSense."* — e escolher entre dois botões sem saber o que cada um custa não

#: O que a tela diz sobre a máscara DualSense.
#:
TEXTO_MASCARA_DUALSENSE_VALIDADA: str = (
    "Nesta máscara o jogo recebe tudo: giroscópio, acelerômetro e touchpad. "
    "É a máscara validada em jogo real (Sackboy, Mad King e Pragmata, julho de "
    "2026), e a que vale numa instalação nova. Se um jogo não responder ao "
    "controle, troque para Xbox 360 e nos conte."
)

TEXTO_MASCARA_SEM_ESCOLHA: str = (
    "Sem marcar nenhuma delas, este perfil não mexe na máscara: ativar ele "
    "mantém a que estiver valendo. É assim que os perfis de gênero vêm."
)


def texto_do_preco_da_mascara(flavor: object) -> str:
    """A linha VISÍVEL embaixo dos botões de máscara, para o valor marcado."""
    if flavor == "dualsense":
        return TEXTO_MASCARA_DUALSENSE_VALIDADA
    return texto_do_custo_da_mascara(flavor) or TEXTO_MASCARA_SEM_ESCOLHA

LABEL_SO_MANUAL = "Só manual (nunca ativa sozinho)"

_MATCH_LABELS: dict[str, str] = {
    "any": "Sempre",
    "criteria": "Só neste programa",
    "manual": LABEL_SO_MANUAL,
}


def _match_label(match: object) -> str:
    """Rótulo da coluna "Quando usar" (função pura — testável sem GTK)."""
    tipo = getattr(match, "type", None)
    if tipo == "criteria" and not (
        getattr(match, "window_class", None)
        or getattr(match, "window_title_regex", None)
        or getattr(match, "process_name", None)
    ):
        return LABEL_SO_MANUAL
    if tipo is not None:
        return _MATCH_LABELS.get(str(tipo), str(tipo))
    return _MATCH_LABELS.get(str(match), str(match))


def rotulo_quando_usar(
    profile: Any, perfis: list[Any], incumbente: str | None = None
) -> str:
    """Texto da coluna "Quando usar" — função pura, testável sem GTK."""
    del perfis, incumbente
    return _match_label(getattr(profile, "match", None))


def explicacao_da_disputa(
    profile: Any, perfis: list[Any], incumbente: str | None = None
) -> str:
    """Tooltip da linha: vazio desde 01/10/2026 — não há disputa a explicar."""
    del profile, perfis, incumbente
    return ""


# O gesto de Ativar, esse, deixa fato em disco: `profile.switch` grava a

#: A cor do "ligado" desta casa — `@green` do `gui/theme.css:26`, a mesma que a
COR_DO_PERFIL_ATIVO = "#50fa7b"

_REALCE_DO_ATIVO: Any = None


def realce_do_perfil_ativo() -> Any:
    """A cor da linha dela como `Pango.AttrList` — e o motivo é MEDIDO."""
    global _REALCE_DO_ATIVO
    if _REALCE_DO_ATIVO is None:
        from gi.repository import Pango

        r, g, b = (int(COR_DO_PERFIL_ATIVO[i : i + 2], 16) * 257 for i in (1, 3, 5))
        lista = Pango.AttrList()
        lista.insert(Pango.attr_foreground_new(r, g, b))
        _REALCE_DO_ATIVO = lista
    return _REALCE_DO_ATIVO


def perfil_que_ela_ativou() -> str | None:
    """A escolha dela, lida do disco pelo dono (`utils.session.a_escolha_dela`).

    O Freestyle quando o botão está ligado; desligado, o último perfil que ela
    ativou; «sem escolha», `None`. Sobrevive ao daemon responder
    `active_profile: null` e a fechar e reabrir a janela. Best-effort:
    qualquer falha de I/O vira `None`, e a lista simplesmente não destaca
    ninguém — nunca uma exceção na thread GTK.

    NOTA DATADA — 01/10/2026: lia o `session.json` e o `active_profile.txt`,
    com o marcador vencendo na divergência; com a sessão no Freestyle de fora
    do jogo e o botão apagado, a perna do disco dizia «Freestyle».
    """
    from hefesto_dualsense4unix.utils.session import resolve_boot_profile

    with contextlib.suppress(Exception):
        return resolve_boot_profile()
    return None


ROTULO_NAO_SEI = "—"

ROTULO_NENHUM = "Nenhum"


class PerfilQueVale(NamedTuple):
    """Quem está valendo, de onde veio a resposta, e se houve resposta.

    ``fonte`` é o que separa os quatro casos, e existe para a tela poder
    escolher palavras diferentes para fatos diferentes:

    - ``"daemon"`` — o daemon respondeu com um nome. É a verdade mais fresca.
    - ``"disco"``  — o daemon respondeu ``null`` (ou não respondeu) e o
      marcador em disco tem um nome. **É o caso VIVO da máquina dela.**
    - ``"nenhum"`` — o daemon respondeu, ninguém tem nome: não há perfil ativo.
    - ``"nao_sei"`` — não houve resposta e não há marcador. A tela não sabe.
    """

    nome: str | None
    fonte: str

    @property
    def sabe(self) -> bool:
        """Alguém soube responder? ``False`` só no ``nao_sei``."""
        return self.fonte != "nao_sei"

    @property
    def rotulo(self) -> str:
        """O que a tela escreve quando precisa de UMA palavra."""
        if self.nome:
            return self.nome
        return ROTULO_NENHUM if self.fonte == "nenhum" else ROTULO_NAO_SEI


def perfil_que_esta_valendo(state: Any = None) -> PerfilQueVale:
    """O DONO da pergunta "qual perfil está valendo agora?"."""
    houve_resposta = isinstance(state, dict)
    if houve_resposta:
        do_daemon = state.get("active_profile")
        if isinstance(do_daemon, str) and do_daemon:
            return PerfilQueVale(do_daemon, "daemon")
    do_disco: str | None = None
    with contextlib.suppress(Exception):
        do_disco = perfil_que_ela_ativou()
    if do_disco:
        return PerfilQueVale(do_disco, "disco")
    return PerfilQueVale(None, "nenhum" if houve_resposta else "nao_sei")


#: na ordem que a casa exige de toda frase de diagnóstico (o quê, por quê, o
_AVISO_DA_REMOCAO_DO_ATIVO = (
    "Este é o perfil que está valendo agora.\n"
    "Remover o arquivo não desfaz o que já está no controle: a cor, os "
    "gatilhos e a vibração dele seguem aplicados até você ativar outro perfil.\n"
    "E o marcador em disco vai apontar para um perfil que não existe mais — "
    "ative outro perfil em seguida para acertar os dois."
)


def frase_da_remocao_do_perfil_ativo(nome: str, valendo: Any) -> str | None:
    """O aviso extra do diálogo de Remover. ``None`` é silêncio, e é a regra."""
    if not nome:
        return None
    do_dono = getattr(valendo, "nome", None)
    fonte = getattr(valendo, "fonte", "nao_sei")
    if not isinstance(do_dono, str) or not do_dono or fonte == "nao_sei":
        return None
    from hefesto_dualsense4unix.profiles.slug import slugify

    if slugify(do_dono) != slugify(nome):
        return None
    return _AVISO_DA_REMOCAO_DO_ATIVO


def ordem_de_exibicao(perfis: list[Any], ativo: str | None) -> list[Any]:
    """A ordem em que as linhas aparecem: o ativo primeiro, o resto como veio."""
    if not ativo:
        return list(perfis)
    primeiro = [p for p in perfis if str(getattr(p, "name", "")) == ativo]
    resto = [p for p in perfis if str(getattr(p, "name", "")) != ativo]
    return primeiro + resto


QUEDA_DE_PRIORIDADE_QUE_PEDE_AVISO = 10


def queda_de_prioridade_pede_aviso(antes: int, depois: int) -> bool:
    """Esta queda de prioridade precisa de confirmação? (função pura)."""
    return int(depois) < int(antes) and (
        int(antes) - int(depois)
    ) >= QUEDA_DE_PRIORIDADE_QUE_PEDE_AVISO


# `confirm_downgrade_match_to_any` cobre "o perfil passou a valer para TUDO".


def _nunca_entra_sozinho(match: object) -> bool:
    """O perfil com esta regra nunca casa com janela nenhuma?"""
    return _match_label(match) == LABEL_SO_MANUAL


def rebaixamento_para_so_manual(antes: object, depois: object) -> bool:
    """Este Salvar tira do perfil o que o fazia entrar sozinho? (função pura)."""
    return _nunca_entra_sozinho(depois) and not _nunca_entra_sozinho(antes)


# `profile.switch` responde a verdade desde a R-03 (`secoes`, `mode_aplicado`,

#: Nomes das seções que só o `profile.switch` relata. O mapa do rodapé
#: "gatilhos" e "luzes" — porque é a mesma seção; o que muda é só a chave.
_NOMES_DAS_SECOES_DA_ATIVACAO: dict[str, str] = {
    "mode": "modo",
    "suppression": "modo jogo",
    "rumble_policy": "vibração",
    "speaker": "alto-falante",
    "trigger": "gatilhos",
    "led": "luzes",
    "rumble_passthrough": "vibração do jogo",
    # 01/10/2026. Às 19h15 a janela escreveu «menos: button_actions,
    "button_actions": "o que cada botão faz",
    "remapeamento": "a troca de botões",
    "movimento": "a mira",
}

_PREFIXO_DO_ALTO_FALANTE_POR_CONTROLE = "speaker:"
_NOME_DO_ALTO_FALANTE_POR_CONTROLE = "alto-falante de um controle"


def nome_da_secao_da_ativacao(chave: str) -> str:
    """A palavra de tela desta seção, ou a chave crua quando não há nome."""
    if chave.startswith(_PREFIXO_DO_ALTO_FALANTE_POR_CONTROLE):
        uniq = chave[len(_PREFIXO_DO_ALTO_FALANTE_POR_CONTROLE) :]
        return f"{_NOME_DO_ALTO_FALANTE_POR_CONTROLE} ({uniq})"
    return _NOMES_DAS_SECOES_DA_ATIVACAO.get(chave, chave)


#: 01/10 a janela escreveu «menos: button_actions, remapeamento, movimento e
NAO_E_FALTA = frozenset({"de_fabrica", "do_computador", "desligado", "ignorado_sem_device"})


def relato_da_ativacao(result: Any) -> dict[str, Any] | None:
    """O relatório do ``profile.switch`` no vocabulário que o rodapé já fala.

    O daemon responde ``{"secoes": {seção: estado}}`` com o vocabulário do
    `lifecycle` (``"aplicado"``, ``"adiado_lock_manual"``, ``"ignorado_*"``,
    ``"falhou"``); o rodapé fala ``applied``/``failed`` (APLICAR-VERDADE-01/02).
    São a MESMA informação em dois formatos, então esta função TRADUZ e deixa a
    frase com quem já a tem.

    Devolve ``None`` quando não há relatório (daemon antigo, ou o ``True`` cru
    da ponte): sem informação não há do que desconfiar — a mesma regra do irmão.
    """
    if not isinstance(result, dict):
        return None
    secoes = result.get("secoes")
    if not isinstance(secoes, dict) or not secoes:
        return None
    aplicadas = [str(s) for s, estado in secoes.items() if str(estado) == "aplicado"]
    nao_entraram = {
        nome_da_secao_da_ativacao(str(s)): str(estado)
        for s, estado in secoes.items()
        if str(estado) != "aplicado" and str(estado) not in NAO_E_FALTA
    }
    return {"applied": aplicadas, "failed": nao_entraram}


def mensagem_de_ativacao(name: str, result: Any = None) -> str:
    """O que o rodapé diz depois de um ``profile.switch`` ACEITO.

    Tudo aplicado (ou daemon sem relatório) mantém a frase de sempre. Com seção
    de fora, o texto do que NÃO entrou é o do rodapé — reusado, não reescrito:
    dois donos da mesma frase derivam, e esta casa tem a regra escrita.
    """
    relato = relato_da_ativacao(result)
    if relato is None or not relato["failed"]:
        return f"Perfil ativado: {name}"
    from hefesto_dualsense4unix.app.actions.footer_actions import (
        _mensagem_de_aplicacao,
    )

    return f"Perfil ativado: {name} — {_mensagem_de_aplicacao(relato)}"


def mensagem_do_salvar(
    name: str,
    renomeado_de: str | None = None,
    reaplicou: bool = False,
    result: Any = None,
) -> str:
    """O que o rodapé diz depois do Salvar — e o que ele PARA de prometer.

    PERFIS-ABRE-O-QUE-GUARDA-01/P3b (25/08/2026). O Salvar lia o booleano de
    `profile_switch` — que a própria docstring dele declara ser "o daemon não
    confirmou", nunca "as seções entraram" — e escrevia **"Perfil salvo e
    reaplicado no controle"**. Com o jogo aberto, o gate R-04 recusa seções: o
    daemon respondia, o booleano era `True`, nenhuma seção chegava ao controle,
    e a janela comemorava. O botão vizinho — o **Ativar** — já sabia dizer a
    verdade desde a ATIVAR-NAO-MENTE-01, cem linhas acima, no mesmo arquivo.

    **Reuso, nunca frase nova.** A metade que nomeia o que ficou de fora é
    `_mensagem_de_aplicacao` do rodapé — a MESMA função, com as MESMAS
    palavras, que `mensagem_de_ativacao` usa. Dois donos da mesma frase
    derivam, e esta casa tem a regra escrita.

    Os três estados, e cada um diz só o que sabe:

    - **nada a reaplicar** (o perfil salvo não era o ativo) → "Perfil salvo",
      sem uma palavra sobre o controle;
    - **reaplicado sem relatório ou com tudo dentro** → a frase de sempre, que
      ela já aprovou;
    - **reaplicado com seção de fora** → "Perfil salvo: X — Aplicado, menos:
      …", no vocabulário do rodapé.

    Função PURA: os testes leem o texto sem subir GTK nem daemon.
    """
    cabeca = (
        f"Perfil renomeado: {renomeado_de} → {name}"
        if renomeado_de is not None
        else f"Perfil salvo: {name}"
    )
    if not reaplicou:
        return cabeca
    relato = relato_da_ativacao(result)
    if relato is None or not relato["failed"]:
        if renomeado_de is not None:
            return f"{cabeca} (reaplicado no controle)"
        return f"Perfil salvo e reaplicado no controle: {name}"
    from hefesto_dualsense4unix.app.actions.footer_actions import (
        _mensagem_de_aplicacao,
    )

    return f"{cabeca} — {_mensagem_de_aplicacao(relato)}"


#     app/draft_config.py:382:    # `manager.pontes_confirmadas()` …  <- comentário

_ROTULO_DA_PONTE: dict[str, str] = dict(_MODE_KIND_ITEMS)

_ROTULO_DA_MASCARA: dict[str, str] = dict(_MODE_FLAVOR_ITEMS)

_COMO_FOI_CONFIRMADA: dict[str, str] = {
    "gesto": "quando você aplicou o perfil",
    "silencio": "porque funcionou e ninguém precisou mexer",
    "escolha_dela": "porque você escolheu assim",
}


def _dia_do_carimbo(iso: object) -> str | None:
    """``2026-08-19T21:16:55-03:00`` -> ``19/08/2026``. Lixo -> ``None``."""
    from datetime import datetime

    if not isinstance(iso, str) or not iso:
        return None
    with contextlib.suppress(ValueError):
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y")
    return None


def frase_da_ponte_confirmada(pontes: Any, appid: object) -> str | None:
    """O carimbo deste jogo, em uma linha. ``None`` é SILÊNCIO, e é de propósito."""
    if not isinstance(pontes, dict):
        return None
    chave = normalize_appid(str(appid) if appid is not None else None)
    ponte = pontes.get(chave) if chave else None
    if not isinstance(ponte, dict):
        return None
    kind = str(ponte.get("kind") or "")
    por_onde = _ROTULO_DA_PONTE.get(kind)
    if por_onde is None:
        return None
    if kind == "gamepad":
        mascara = _ROTULO_DA_MASCARA.get(str(ponte.get("gamepad_flavor") or ""))
        if mascara:
            por_onde = f"{por_onde}, como {mascara}"
    if ponte.get("steam_input") is True:
        por_onde = f"{por_onde}, com o jogo marcado no Steam Input"
    partes = [f"Este jogo já sabe por onde entra: {por_onde}."]
    dia = _dia_do_carimbo(ponte.get("confirmada_em"))
    como = _COMO_FOI_CONFIRMADA.get(str(ponte.get("confirmada_por") or ""))
    if dia and como:
        partes.append(f"Confirmado em {dia}, {como}.")
    elif dia:
        partes.append(f"Confirmado em {dia}.")
    return " ".join(partes)


def texto_da_marca_do_steam_input(
    status: str, appid: object = None, controles: int | None = None
) -> str:
    """Toast da caixinha do Steam Input — pura, testável sem GTK."""
    if status == "appid_invalido":
        return "Esse não é um número de jogo da Steam — nada foi mudado."
    if status == "erro":
        return "Não consegui gravar a marca deste jogo — nada foi mudado."
    if status == "ja_estava":
        return f"O jogo {appid} já estava marcado."
    if status == "nao_estava":
        return f"O jogo {appid} não estava marcado."
    if status == "removido":
        return (
            f"Tirei a marca do jogo {appid}: ele volta a enxergar também o "
            "controle físico. Feche e abra o jogo para valer."
        )
    jogadores = (
        f" Os seus {controles} controles continuam sendo do Hefesto, um jogador "
        "cada — confira na tela do jogo."
        if controles is not None and controles >= 2
        else ""
    )
    return (
        f"Marquei o jogo {appid}: o controle físico fica escondido e ele passa a "
        "ver só o controle do Hefesto, sem o controle dobrado — a sua cor, os "
        f"seus gatilhos e a sua vibração continuam valendo.{jogadores} Feche e "
        "abra o jogo para valer."
    )


_BACKEND_NA_TELA = {
    "portal": "pelo portal do sistema (Wayland)",
    "wlrctl": "pelo wlrctl (Wayland)",
}


def texto_do_processo_que_nao_casa(state: dict[str, Any] | None) -> str | None:
    """O aviso de que o campo ``process_name`` NÃO casa neste ambiente.

    ``None`` = ele casa, ou não se sabe — e nos dois casos a linha não aparece.

    **O defeito**, medido no journal da máquina dela em 30 dias
    (PERFIL-MUDO-01, 10/08/2026): os cinco perfis de gênero dela (``FPS``,
    ``Ação``, ``Aventura``, ``Corrida``, ``Esportes``) trazem título **e**
    ``process_name``, e **nunca apareceram, nenhuma vez**. A causa não é o
    critério estar errado: é que em Wayland puro os dois backends devolvem
    ``exe_basename=""`` por construção, e `MatchCriteria` é um **E** entre os
    campos preenchidos — um campo que não casa derruba o perfil inteiro,
    inclusive a ``window_class`` que casaria sozinha.

    A aba "No jogo" já conta isso **depois** (``profiles.porque_nao_entrou``,
    quando o jogo já abriu sem o perfil). Falta contar **antes**, na tela em
    que alguém digita o campo — que é aqui.

    **QUEM DECIDE SE O BACKEND É CEGO NÃO É ESTA FUNÇÃO** — é
    ``integrations.window_detect.backend_ve_nome_do_processo``, que mora ao lado
    dos backends que produzem o fato. Dois critérios para a mesma pergunta
    divergem na primeira mudança, e esta casa já pagou por isso; aqui só se
    escolhe a frase.

    A ordem das perguntas, no molde de ``texto_do_alcance_da_intensidade``:

    1. **O dado veio?** ``state`` que não é dicionário, ou
       ``window_detect_backend`` ausente/desconhecido: silêncio. Afirmar "não
       casa" com o campo ausente seria inventar um defeito — e daemon mais
       velho que o código é rotina nesta casa;
    2. **O backend vê o processo?** Então nada a dizer;
    3. **É o ``null``?** Aí não é o ``process_name`` que está sozinho no
       problema: o detector não está lendo janela nenhuma, e **nenhum** dos
       três campos casa. Dizer só do ``process_name`` mandaria trocar de campo
       para cair no mesmo silêncio;
    4. **Sobrou** o Wayland puro: o campo não casa e os outros dois casam.

    A frase **não manda apagar nada** e não chama a configuração dela de
    errada, pelo mesmo motivo do `porque_nao_entrou`: quem escreveu o critério
    foi ela, *"a vontade da GUI prevalece"*. Ela diz o que o campo faz aqui e
    quais campos funcionam — a decisão continua sendo dela.
    """
    from hefesto_dualsense4unix.integrations.window_detect import (
        backend_ve_nome_do_processo,
    )

    if not isinstance(state, dict):
        return None
    backend = state.get("window_detect_backend")
    ve = backend_ve_nome_do_processo(backend if isinstance(backend, str) else None)
    if ve is not False:
        return None
    if backend == "null":
        return (
            "O Hefesto não está enxergando janela nenhuma nesta sessão: nenhum "
            "dos três campos casa, e nenhum perfil entra sozinho — inclusive "
            "por “process_name”. Ative este perfil pelo botão Ativar."
        )
    onde = _BACKEND_NA_TELA.get(str(backend), "por um backend de Wayland")
    return (
        f"O campo “process_name” não casa aqui: o Hefesto lê a janela {onde}, "
        "e esse caminho não entrega o nome do executável. Como os campos "
        "preenchidos são um E, preencher este faz o perfil não entrar nunca — "
        "nem com o “window_class” certo. “window_class” e “title_regex” casam "
        "normalmente nesta sessão."
    )


_RESP_RENOMEAR = 201
_RESP_COPIA = 202


def _motivo_do_cancelamento() -> str:
    """A frase da barra depois de um diálogo que devolveu "não"."""
    from hefesto_dualsense4unix.app import gui_dialogs

    if gui_dialogs.ultimo_socorro() is not None:
        return (
            "O aviso não conseguiu aparecer na tela — nada foi alterado. "
            "Tente salvar de novo."
        )
    return "Operação cancelada."


def dialogo_renomear_ou_copiar(
    parent: Any, antigo: str, novo: str
) -> str | None:
    """"Renomear" ou "Salvar como cópia" — devolve "renomear"/"copia"/None."""
    from hefesto_dualsense4unix.app import gui_dialogs

    dialog = Gtk.MessageDialog(
        parent=parent,
        modal=True,
        destroy_with_parent=True,
        message_type=Gtk.MessageType.QUESTION,
        buttons=Gtk.ButtonsType.NONE,
        text=f"Renomear '{antigo}' para '{novo}'?",
    )
    with contextlib.suppress(Exception):
        dialog.get_style_context().add_class("hefesto-dualsense4unix-window")
    dialog.format_secondary_text(
        f"'Renomear' apaga o perfil '{antigo}'. 'Salvar como cópia' mantém "
        f"os dois — e os dois vão disputar as mesmas janelas."
    )
    dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
    dialog.add_button("Salvar como cópia", _RESP_COPIA)
    dialog.add_button("Renomear", _RESP_RENOMEAR)
    dialog.set_default_response(_RESP_RENOMEAR)

    response = gui_dialogs.executar_dialogo(dialog, nome="renomear_ou_copiar")
    dialog.destroy()
    if response == _RESP_RENOMEAR:
        return "renomear"
    if response == _RESP_COPIA:
        return "copia"
    return None


class ProfilesActionsMixin(CaronaDoWrapperMixin):
    """Controla a aba Perfis."""

    _profiles_store: Gtk.ListStore
    _mode_advanced: bool = False
    # load_all_profiles() síncrono na thread GTK a cada clique/tecla. Populado
    # on_profile_selection_changed e _build_profile_from_editor.
    _profiles_cache: list[Profile]
    _suppress_advanced_toggle: bool = False
    # usado como base em _build_profile_from_editor para copiar triggers/LEDs/etc.
    _duplicate_source: Profile | None = None
    _aplica_a: Any
    _mode_kind_selector: Any = None
    _mode_flavor_selector: Any = None
    _mode_flavor_price_label: Any = None
    _mode_gamepad_opts: Any = None
    _regra_do_disco: Match | None = None
    _assinatura_da_regra_ao_abrir: tuple[object, ...] | None = None
    _prioridade_do_disco: int | None = None
    _prioridade_ao_abrir: int | None = None
    _regra_tocada: bool = False
    _prioridade_tocada: bool = False
    _modo_tocado: bool = False
    _selecao_programatica: bool = False
    _alvo_do_salvar: str | None = None
    _active_profile_hint: str | None = None

    def install_profiles_tab(self) -> None:
        """Inicializa a aba Perfis: lista, colunas, handlers e estado inicial do toggle."""
        tree: Gtk.TreeView = self._get("profiles_tree")
        from gi.repository import Pango

        store = Gtk.ListStore(
            GObject.TYPE_STRING,
            GObject.TYPE_INT,
            GObject.TYPE_STRING,
            GObject.TYPE_INT,
            GObject.TYPE_STRING,
            Pango.AttrList,
        )
        tree.set_model(store)
        self._profiles_store = store

        for idx, title in ((0, "Nome"), (1, "Prioridade"), (2, "Quando usar")):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(
                title, renderer, text=idx, weight=3, attributes=5
            )
            if idx == 2:
                with contextlib.suppress(Exception):
                    from gi.repository import Pango

                    renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
                    column.set_resizable(True)
                    column.set_max_width(320)
            tree.append_column(column)
        with contextlib.suppress(Exception):
            tree.set_tooltip_column(4)

        tree.get_selection().connect(
            "changed", self.on_profile_selection_changed
        )

        sel = SegmentedSelector(wrap=True)
        sel.set_items(_APLICA_A_ITEMS)
        sel.set_tooltip_text("Contexto em que este perfil será aplicado")
        slot = self._get("profile_aplica_a_slot")
        if slot is not None:
            slot.pack_start(sel, True, True, 0)
            sel.show_all()
        self._aplica_a = sel
        sel.connect("changed", self._on_aplica_a_changed)
        sel.set_active_id("any")

        # `_signal_handlers()`, e um handler declarado no glade que não esteja
        self._suppress_steam_input_toggle = False
        check = self._get("profile_steam_input_check")
        if check is not None:
            with contextlib.suppress(Exception):
                check.connect("toggled", self.on_profile_steam_input_toggled)
        campo_do_jogo = self._get("profile_simple_custom_name")
        if campo_do_jogo is not None:
            with contextlib.suppress(Exception):
                campo_do_jogo.connect("changed", self._on_campo_do_jogo_mudou)
        self._instalar_lista_de_jogos_do_pc()

        escala_prio = self._get("profile_priority_scale")
        if escala_prio is not None:
            with contextlib.suppress(Exception):
                escala_prio.connect("value-changed", self._on_prioridade_tocada)

        self._install_mode_section()

        prefs = load_gui_prefs()
        self._mode_advanced = bool(prefs.get("advanced_editor", False))
        switch: Gtk.Switch = self._get("profile_advanced_switch")
        self._suppress_advanced_toggle = True
        try:
            switch.set_active(self._mode_advanced)
        finally:
            self._suppress_advanced_toggle = False
        self._apply_editor_mode()
        if self._mode_advanced:
            self._atualizar_aviso_do_processo()

        self._profiles_cache = []
        self._active_profile_hint = perfil_que_ela_ativou()
        self._reload_profiles_store(on_done=self._sync_selection_with_active_profile)

    def _install_mode_section(self) -> None:
        """Monta a seção "Modo" do editor (FEAT-PROFILE-MODE-GUI-01)."""
        slot = self._get("profile_mode_slot")
        if slot is None:
            # do perfil sobrevive por herança em _build_profile_from_editor.
            self._mode_kind_selector = None
            return

        kind_sel = SegmentedSelector(wrap=True)
        kind_sel.set_items(_MODE_KIND_ITEMS)
        kind_sel.set_tooltip_text(
            "O que ativar este perfil liga: controlar o PC, jogar pelo "
            "Hefesto ou a conexão nativa (Sony)"
        )
        slot.pack_start(kind_sel, False, False, 0)
        self._mode_kind_selector = kind_sel

        # aqui no editor em 2026-07-13). A linha própria dá a largura toda.
        opts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        mask_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        flavor_label = Gtk.Label(label="O jogo vê o controle como:")
        mask_row.pack_start(flavor_label, False, False, 0)
        flavor_sel = SegmentedSelector(wrap=True)
        flavor_sel.set_items(_MODE_FLAVOR_ITEMS)
        flavor_sel.set_tooltip_text(
            "Quais desenhos de botão o jogo mostra na tela"
        )
        flavor_sel.set_tooltips(
            {
                sabor: texto_do_custo_da_mascara(sabor)
                for sabor, _rotulo in _MODE_FLAVOR_ITEMS
                if texto_do_custo_da_mascara(sabor)
            }
        )
        self._mode_flavor_selector = flavor_sel
        mask_row.pack_start(flavor_sel, True, True, 0)
        opts.pack_start(mask_row, False, False, 0)

        preco = Gtk.Label(label=texto_do_preco_da_mascara(None))
        preco.set_xalign(0.0)
        preco.set_line_wrap(True)
        preco.set_max_width_chars(64)
        preco.get_style_context().add_class("dim-label")
        self._mode_flavor_price_label = preco
        opts.pack_start(preco, False, False, 0)

        self._mode_gamepad_opts = opts
        slot.pack_start(opts, False, False, 0)

        hint = Gtk.Label(
            label=(
                "\"Não mexer no modo\" = ativar este perfil deixa o sistema "
                "exatamente como está."
            )
        )
        hint.set_xalign(0.0)
        hint.set_line_wrap(True)
        hint.get_style_context().add_class("dim-label")
        slot.pack_start(hint, False, False, 0)

        #
        aviso_radio = Gtk.Label()
        aviso_radio.set_xalign(0.0)
        aviso_radio.set_line_wrap(True)
        aviso_radio.set_max_width_chars(64)
        aviso_radio.set_visible(False)
        aviso_radio.set_no_show_all(True)
        self._aviso_do_radio_fragil = aviso_radio
        slot.pack_start(aviso_radio, False, False, 0)
        slot.show_all()

        kind_sel.connect("changed", self._on_mode_kind_changed)
        flavor_sel.connect("changed", self._on_mode_flavor_changed)

        kind_sel.set_active_id("none")
        flavor_sel.limpar_ativo()
        self._atualizar_preco_da_mascara(None)
        self._sync_mode_options_visibility("none")
        self._modo_tocado = False

    def _sync_mode_options_visibility(self, kind: str) -> None:
        """Mostra/habilita a máscara apenas com kind == "gamepad"."""
        self._sincronizar_aviso_do_radio(kind)
        opts = self._mode_gamepad_opts
        if opts is None:
            return
        is_gamepad = kind == "gamepad"
        opts.set_visible(is_gamepad)
        opts.set_no_show_all(not is_gamepad)
        opts.set_sensitive(is_gamepad)

    def _sincronizar_aviso_do_radio(self, kind: str) -> None:
        """Escreve (ou apaga) o aviso de rádio frágil da seção "Modo"."""
        rotulo = getattr(self, "_aviso_do_radio_fragil", None)
        if rotulo is None:
            return
        frase = frase_do_radio_fragil_no_modo(
            kind, getattr(self, "_estado_do_radio", None)
        )
        try:
            if frase is None:
                rotulo.set_text("")
                with contextlib.suppress(Exception):
                    rotulo.set_no_show_all(True)
                rotulo.set_visible(False)
                return
            rotulo.set_markup(
                f'<span foreground="#ffb86c">{escapar_markup(frase)}</span>'
            )
            with contextlib.suppress(Exception):
                rotulo.set_tooltip_text(frase)
            with contextlib.suppress(Exception):
                rotulo.set_no_show_all(False)
            rotulo.set_visible(True)
        except Exception as exc:
            logger.debug("aviso_do_radio_falhou", err=str(exc))

    def _buscar_o_estado_do_radio(self) -> None:
        """Pede o `state_full` ao daemon — por GESTO, e só quando faz falta.

        `native_bt_fragil` mora no `daemon.state_full`
        (`daemon/ipc_handlers.py`), e esta aba não tem tique próprio: ela não
        fala com o daemon em lugar nenhum. Uma busca ao escolher o Modo Nativo
        é atual o bastante — o que decide o aviso é quantos controles estão no
        rádio AGORA, e a resposta chega antes de ela terminar de ler a linha.

        Daemon offline deixa o cache como está e a linha não aparece.
        """
        call_async(
            method="daemon.state_full",
            params={},
            on_success=self._ao_chegar_o_estado_do_radio,
            on_failure=lambda _exc: False,
        )

    def _ao_chegar_o_estado_do_radio(self, result: Any = None) -> bool:
        """Callback GTK: guarda o estado e repinta o aviso do modo escolhido."""
        if isinstance(result, dict):
            self._estado_do_radio = result
            with contextlib.suppress(Exception):
                selector = getattr(self, "_mode_kind_selector", None)
                if selector is not None:
                    self._sincronizar_aviso_do_radio(
                        selector.get_active_id() or "none"
                    )
        return False

    def _on_mode_kind_changed(self, selector: Any) -> None:
        """Handler do kind: sincroniza a visibilidade das opções do modo."""
        kind = selector.get_active_id() or "none"
        if kind == _KIND_NATIVO:
            self._buscar_o_estado_do_radio()
        self._modo_tocado = True
        self._sync_mode_options_visibility(kind)

    def _atualizar_preco_da_mascara(self, flavor: object) -> None:
        """Põe na etiqueta o preço da máscara ``flavor`` (no-op sem o widget)."""
        rotulo = getattr(self, "_mode_flavor_price_label", None)
        if rotulo is not None:
            rotulo.set_text(texto_do_preco_da_mascara(flavor))

    def _on_mode_flavor_changed(self, selector: Any = None) -> None:
        """Handler da máscara: marca o gesto e atualiza a etiqueta de preço."""
        self._modo_tocado = True
        alvo = selector if selector is not None else self._mode_flavor_selector
        atual = alvo.get_active_id() if alvo is not None else None
        self._atualizar_preco_da_mascara(atual)

    def _set_mode_editor(self, mode: ProfileModeConfig | None) -> None:
        """Preenche a seção "Modo" a partir de ``profile.mode`` (None → "none")."""
        kind_sel = self._mode_kind_selector
        if kind_sel is None:
            return
        kind = mode.kind if mode is not None else "none"
        flavor = mode.gamepad_flavor if mode is not None else None
        kind_sel.set_active_id(kind)
        if self._mode_flavor_selector is not None:
            if flavor is None:
                self._mode_flavor_selector.limpar_ativo()
            else:
                self._mode_flavor_selector.set_active_id(flavor)
        self._atualizar_preco_da_mascara(flavor)
        self._sync_mode_options_visibility(kind)
        self._modo_tocado = False

    def _mode_section_from_editor(self) -> dict[str, Any] | None:
        """Monta o dict da seção ``mode`` a partir dos widgets do editor."""
        kind_sel = self._mode_kind_selector
        kind = (kind_sel.get_active_id() if kind_sel is not None else None) or "none"
        if kind == "none":
            return None
        flavor: str | None = None
        if kind == "gamepad":
            flavor_sel = self._mode_flavor_selector
            flavor = flavor_sel.get_active_id() if flavor_sel is not None else None
        return {"kind": kind, "gamepad_flavor": flavor}

    def _sync_selection_with_active_profile(self) -> None:
        """Consulta o daemon e seleciona a linha do perfil ativo (FEAT-GUI-LOAD-LAST-PROFILE-01)."""
        call_async(
            method="daemon.status",
            params=None,
            on_success=self._on_daemon_status_for_sync,
            on_failure=self._on_daemon_status_sync_failed,
            timeout_s=0.5,
        )

    def _on_daemon_status_for_sync(self, result: Any) -> bool:
        """Callback GTK: recebe daemon.status e seleciona perfil ativo se casar."""
        try:
            if not isinstance(result, dict):
                return False
            active = result.get("active_profile")
            if not isinstance(active, str) or not active:
                return False
            self._mark_active_profile_row(active)
            self._select_profile_by_name(active)
        except Exception as exc:
            logger.warning("profile_sync_callback_falhou", err=str(exc))
        return False

    def _on_daemon_status_sync_failed(self, exc: Exception) -> bool:
        """Callback GTK: falha silenciosa — mantém fallback (primeiro da lista)."""
        logger.debug("profile_sync_daemon_offline", err=str(exc))
        return False

    def _select_profile_by_name(self, name: str) -> bool:
        """Seleciona a linha do store cujo nome bate com ``name``."""
        if not self._selecao_pode_se_mover_sozinha(name):
            logger.info(
                "perfis_selecao_automatica_recusada",
                pedido=name,
                editando=getattr(self, "_alvo_do_salvar", None),
            )
            return False
        store = self._profiles_store
        tree: Gtk.TreeView = self._get("profiles_tree")
        tree_iter = store.get_iter_first()
        while tree_iter is not None:
            if str(store.get_value(tree_iter, 0)) == name:
                self._mover_selecao_sem_gesto(tree_iter)
                path = store.get_path(tree_iter)
                tree.scroll_to_cell(path, None, False, 0.0, 0.0)
                return True
            tree_iter = store.iter_next(tree_iter)
        return False

    def _selecao_pode_se_mover_sozinha(self, destino: str) -> bool:
        """A seleção pode pular para ``destino`` sem que ela tenha pedido?"""
        alvo = getattr(self, "_alvo_do_salvar", None)
        if alvo and (destino == alvo or mesmo_slug(destino, alvo)):
            return True
        return not self._ha_trabalho_no_editor()

    def _mover_selecao_sem_gesto(self, linha: Any) -> None:
        """Seleciona ``linha`` marcando que quem mexeu foi o CÓDIGO."""
        tree: Gtk.TreeView = self._get("profiles_tree")
        anterior = self._selecao_programatica
        self._selecao_programatica = True
        try:
            tree.get_selection().select_iter(linha)
        finally:
            self._selecao_programatica = anterior

    def _ha_trabalho_no_editor(self) -> bool:
        """Há trabalho NÃO SALVO que uma repintura do editor destruiria?

        NUNCA-TROCA-O-ALVO-01 (06/08/2026). A queixa dela: *"clico em salvar e
        ele salva com um nome aleatório ou de outro perfil"*. Medido: o campo
        Nome trocava sozinho porque `_populate_editor` reescreve o editor
        inteiro e é disparado pelo sinal `changed` da SELEÇÃO — que a própria
        janela emite em três caminhos sem ela encostar na lista (o sync com o
        perfil ativo ao voltar para a aba, o "Recarregar lista" e o
        `install_profiles_tab`). O Salvar seguinte gravava no perfil que a
        janela pôs no campo, e o trabalho dela evaporava.

        Respondem "sim" aqui, nesta ordem de custo:

        - ``_new_profile`` / ``_duplicate_source``: o editor descreve um perfil
          que ainda NÃO existe em disco. Repintar é apagar o que ela digitou.
        - as marcas de gesto do SALVAR-NAO-REBAIXA-01/02 e da
          PERFIL-SALVA-TUDO-01 (regra, prioridade, modo): elas existem porque
          "ela mexeu nisto" já era uma pergunta que a aba precisava responder.
        - o campo Nome divergindo do perfil aberto: ela está renomeando.
        - ``_tem_edicao_pendente`` (R-08): as OUTRAS abas têm alteração por
          salvar. É o caminho 1 da queixa — ela mexe na cor, o jogo abre, o
          autoswitch troca o perfil ativo e a volta para a aba Perfis reescreve
          o campo Nome. O Salvar da aba Perfis emite o rascunho inteiro
          (`_edita_o_perfil_do_rascunho`), então a cor dela é trabalho que este
          botão grava — e trocar o alvo por baixo dele é perdê-la.

        Por que a resposta é esta e não uma flag de supressão sozinha: suprimir
        só o `changed` deixaria a barra azul numa linha e o editor em outra, e o
        `on_profile_save` lê AS DUAS (a linha responde "quem estou editando?" e
        o campo responde "com que nome vou gravar?"). Divergentes, elas viram um
        RENAME aos olhos do R-10 — a janela perguntaria "renomear 'sackboy' para
        'vitoria'?" por causa de um sinal que ninguém emitiu. Por isso a cura é
        em três peças que se sustentam: a lista não se move sozinha, o editor
        não é repintado por seleção que não é dela, e o Salvar mira o alvo
        MEMORIZADO (`_alvo_do_salvar`) em vez do widget.
        """
        if getattr(self, "_new_profile", False):
            return True
        if getattr(self, "_duplicate_source", None) is not None:
            return True
        if (
            getattr(self, "_regra_tocada", False)
            or getattr(self, "_prioridade_tocada", False)
            or getattr(self, "_modo_tocado", False)
        ):
            return True
        alvo = getattr(self, "_alvo_do_salvar", None)
        if alvo:
            try:
                digitado = (self._get("profile_name_entry").get_text() or "").strip()
            except Exception:
                digitado = ""
            if digitado and not mesmo_slug(digitado, alvo):
                return True
        checar = getattr(self, "_tem_edicao_pendente", None)
        if callable(checar):
            try:
                if bool(checar()):
                    return True
            except Exception as exc:
                logger.warning("perfis_edicao_pendente_indeterminada", err=str(exc))
                return True
        return False

    def _alvo_do_salvar_do_editor(self) -> str | None:
        """Qual perfil do disco o "Salvar este perfil" vai gravar por cima."""
        alvo = getattr(self, "_alvo_do_salvar", None)
        if alvo:
            return str(alvo)
        try:
            return self._selected_profile_name()
        except Exception:
            return None


    def on_profile_advanced_toggle(
        self,
        switch: Gtk.Switch,
        state: bool,
    ) -> bool:
        """Alterna entre modo simples e avançado; persiste preferência.

        O-AVANCADO-QUE-MOSTRAVA-VAZIO-01 (10/08/2026, duas fotos dela às 04:34,
        a mesma tela com um segundo de diferença): com o switch DESLIGADO,
        "Jogo da Steam · 3357650"; com o switch LIGADO, os três campos crus em
        branco, só com os textos-fantasma do glade. O arquivo dela, no mesmo
        instante, dizia ``window_class: ["steam_app_3357650"]``.

        A mecânica: ``_populate_editor`` só escreve nos campos crus no ramo do
        match COMPLEXO — no ramo do preset simples ele mexe no seletor e no
        campo livre e deixa os crus como estiverem. Este handler, que é a outra
        porta para a página avançada, só trocava a página da stack. Ligar o
        avançado depois do perfil aberto nunca teve de onde tirar a regra.

        Por que isso é grave, e não só feio: os três campos vazios são o que o
        ``_build_profile_from_editor`` LÊ com o avançado ligado. Medido nesta
        cura, no editor sem ela: trocar o número do jogo na página simples,
        ligar o avançado e Salvar gravava ``MatchManual`` — o perfil do jogo
        dela virava "só ativa na mão", sem uma palavra na tela. E a frase do
        ``exigencia_invisivel`` manda "Ligue o Modo avançado para ver e mudar",
        ou seja, a janela mandava olhar exatamente onde ela mentia.
        """
        # BUG-ADVANCED-TOGGLE-CLOBBER-01: ignora chamadas programáticas (set_active
        if self._suppress_advanced_toggle:
            return False
        self._mode_advanced = state
        if state:
            self._mostrar_a_regra_nos_campos_crus()
            self._atualizar_aviso_do_processo()
        self._apply_editor_mode()
        set_pref("advanced_editor", state)
        return False

    def _atualizar_aviso_do_processo(self) -> None:
        """Mostra/esconde o aviso de que ``process_name`` não casa (PROCESSO-CEGO-01).

        Best-effort e assíncrono, no mesmo molde do `_prefill_steam_appid`:
        daemon desligado é **silêncio**, não alarme. A decisão da frase é da
        função pura `texto_do_processo_que_nao_casa`; aqui só a costura.

        Escondido quando ela devolve ``None`` — e isso cobre dois casos que a
        tela não pode confundir: "o campo casa" e "não sei se casa". Nos dois,
        uma linha de alerta seria pior que nenhuma.
        """
        aviso = self._get("profile_process_name_aviso")
        if aviso is None:
            return

        def _on_state(result: Any) -> bool:
            try:
                texto = texto_do_processo_que_nao_casa(
                    result if isinstance(result, dict) else None
                )
                alvo = self._get("profile_process_name_aviso")
                if alvo is None:
                    return False
                if texto is None:
                    alvo.set_visible(False)
                else:
                    # as aspas são as tipográficas “ ”, que o Pango passa
                    alvo.set_markup(f'<span foreground="#ffb86c">{texto}</span>')
                    alvo.set_visible(True)
            except Exception as exc:
                logger.debug("aviso_do_processo_falhou", err=str(exc))
            return False

        call_async(
            method="daemon.state_full",
            params=None,
            on_success=_on_state,
            on_failure=lambda _exc: False,
            timeout_s=0.5,
        )

    def _on_aplica_a_changed(self, combo: Any) -> None:
        """Mostra o campo livre nas escolhas que exigem alvo ("game"/"steam_game")."""
        active_id = combo.get_active_id() or "any"
        self._regra_tocada = True
        entry = self._get("profile_simple_custom_name")
        dica = _CAMPO_LIVRE_DICAS.get(active_id)
        if entry is not None and dica is not None:
            placeholder, tooltip = dica
            with contextlib.suppress(Exception):
                entry.set_placeholder_text(placeholder)
            with contextlib.suppress(Exception):
                entry.set_tooltip_text(tooltip)
        box: Gtk.Box = self._get("profile_game_entry_box")
        if box is None:
            return
        if active_id in _IDS_COM_CAMPO_LIVRE:
            box.set_no_show_all(False)
            box.show_all()
        else:
            box.hide()
        if active_id in _IDS_COM_CAMPO_LIVRE and getattr(self, "_new_profile", False):
            self._prefill_modo_de_jogo()
        if active_id == "steam_game":
            self._prefill_steam_appid()
        self._mostrar_caixa_do_steam_input(active_id == "steam_game")
        self._atualizar_frase_do_jogo()

    # entra em `_build_profile_from_editor` nem no `Profile` do disco — o que

    def _mostrar_caixa_do_steam_input(self, mostrar: bool) -> None:
        """Revela (ou esconde) a caixinha, e sincroniza o estado dela."""
        box = self._get("profile_steam_input_box")
        if box is None:
            return
        if mostrar:
            self._sincronizar_caixa_do_steam_input()
            self._sincronizar_outros_marcados()
            self._sincronizar_exigencia_invisivel()
            self._buscar_as_pontes_confirmadas()
            with contextlib.suppress(Exception):
                box.set_no_show_all(False)
            box.show_all()
        else:
            with contextlib.suppress(Exception):
                box.set_no_show_all(True)
            box.hide()

    def _sincronizar_exigencia_invisivel(self) -> None:
        """Diz o que o perfil exige e esta página NÃO mostra."""
        rotulo = self._get("profile_exigencia_invisivel")
        if rotulo is None:
            return
        # de `profiles/` fazia a frase mandar a pessoa a um botão que a
        from hefesto_dualsense4unix.profiles.simple_match import (
            CAMINHO_DA_JANELA_GTK,
            exigencia_invisivel,
        )

        regra = self._regra_do_disco
        fato = exigencia_invisivel(regra) if regra is not None else ""
        texto = f"{fato} {CAMINHO_DA_JANELA_GTK}" if fato else ""
        if texto:

            rotulo.set_markup(
                f'<span foreground="#f1fa8c">{escapar_markup(texto)}</span>'
            )
            with contextlib.suppress(Exception):
                rotulo.set_no_show_all(False)
        else:
            rotulo.set_text("")
            with contextlib.suppress(Exception):
                rotulo.set_no_show_all(True)
        rotulo.set_visible(bool(texto))

    @staticmethod
    def _appids_do_steam_input() -> set[str]:
        """AppIDs marcados hoje, lidos do arquivo dela. Erro = conjunto vazio."""
        try:
            from hefesto_dualsense4unix.integrations.steam_launch_options import (
                parse_steam_input_allowlist,
                steam_input_allowlist_path,
            )

            caminho = steam_input_allowlist_path()
            return set(parse_steam_input_allowlist(caminho.read_text(encoding="utf-8")))
        except Exception:
            return set()

    def _sincronizar_caixa_do_steam_input(self) -> None:
        """Põe a caixinha no estado do DISCO, sem disparar o handler."""
        check = self._get("profile_steam_input_check")
        if check is None:
            return
        appid = self._appid_do_editor()
        marcado = appid is not None and appid in self._appids_do_steam_input()
        self._suppress_steam_input_toggle = True
        try:
            with contextlib.suppress(Exception):
                check.set_active(marcado)
            with contextlib.suppress(Exception):
                check.set_sensitive(appid is not None)
        finally:
            self._suppress_steam_input_toggle = False

    SEM_NOME_NO_DISCO = "nome não encontrado"

    def _nome_do_appid(self, appid: str) -> str | None:
        """O nome do jogo pelo appid, do catálogo que a completação já leu."""
        mapa = getattr(self, "_nomes_dos_jogos", None)
        if not isinstance(mapa, dict):
            return None
        nome = mapa.get(appid)
        return nome if isinstance(nome, str) and nome.strip() else None

    def _sincronizar_outros_marcados(self) -> None:
        """Desenha os OUTROS jogos marcados, um por linha, com o botão de tirar."""
        caixa = self._get("profile_steam_input_outros")
        if caixa is None:
            return
        for filho in list(caixa.get_children()):
            caixa.remove(filho)
            filho.destroy()

        deste = self._appid_do_editor()
        outros = sorted(self._appids_do_steam_input() - {deste or ""})
        if not outros:
            with contextlib.suppress(Exception):
                caixa.set_no_show_all(True)
            caixa.hide()
            return

        from gi.repository import Gtk

        titulo = Gtk.Label()
        titulo.set_xalign(0.0)
        titulo.set_markup(
            f"<i>Outros jogos marcados: {len(outros)}</i>"
        )
        with contextlib.suppress(Exception):
            titulo.get_style_context().add_class("dim-label")
        caixa.pack_start(titulo, False, False, 0)

        grade = Gtk.Grid()
        grade.set_column_spacing(12)
        grade.set_row_spacing(2)
        grade.set_halign(Gtk.Align.START)
        for linha, appid in enumerate(outros):
            for coluna, widget in enumerate(self._celulas_de_outro_marcado(appid)):
                grade.attach(widget, coluna, linha, 1, 1)
        caixa.pack_start(grade, False, False, 0)

        with contextlib.suppress(Exception):
            caixa.set_no_show_all(False)
        caixa.show_all()

    def _celulas_de_outro_marcado(self, appid: str) -> list[Any]:
        """As três células de uma linha: o nome, o número e o botão que tira."""
        from gi.repository import Gtk

        nome = self._nome_do_appid(appid)
        rotulo = Gtk.Label()
        rotulo.set_xalign(0.0)
        if nome is None:
            rotulo.set_markup(f"<i>{self.SEM_NOME_NO_DISCO}</i>")
            with contextlib.suppress(Exception):
                rotulo.get_style_context().add_class("dim-label")
        else:
            rotulo.set_text(nome)

        numero = Gtk.Label(label=appid)
        numero.set_xalign(0.0)
        with contextlib.suppress(Exception):
            numero.get_style_context().add_class("mono")

        tirar = Gtk.Button(label="Tirar")
        tirar.set_tooltip_text(
            "Tira este jogo da lista. Ele volta a enxergar os controles "
            "físicos na próxima vez que você o abrir."
        )
        tirar.connect("clicked", self._ao_tirar_outro_marcado, appid)
        return [rotulo, numero, tirar]

    def _ao_tirar_outro_marcado(self, _botao: Any, appid: str) -> None:
        """Desmarca um jogo que NÃO é o deste editor."""
        self._gravar_marca_do_steam_input(appid, marcar=False)

    def _appid_do_editor(self) -> str | None:
        """O appid digitado no campo do jogo, ou None se não houver um válido."""
        if self._selected_simple_choice() != "steam_game":
            return None
        entry = self._get("profile_simple_custom_name")
        if entry is None:
            return None
        try:
            texto = (entry.get_text() or "").strip()
        except Exception:
            return None
        return texto if texto.isdigit() else None

    def _on_campo_do_jogo_mudou(self, _entry: object = None) -> None:
        """Digitar outro appid muda de qual jogo a caixinha está falando."""
        if self._selected_simple_choice() != "steam_game":
            self._atualizar_frase_do_jogo()
            return
        if self._colar_virou_numero():
            return
        self._sincronizar_caixa_do_steam_input()
        self._sincronizar_outros_marcados()
        self._atualizar_frase_do_jogo()


    def _instalar_lista_de_jogos_do_pc(self) -> None:
        """Liga a completação do campo do jogo, com o catálogo lido em thread."""
        self._jogos_do_pc: list[JogoLocal] = []
        self._nomes_dos_jogos: dict[str, str] = {}
        self._jogos_store = None
        entry = self._get("profile_simple_custom_name")
        if entry is None:
            return
        try:
            store = Gtk.ListStore(GObject.TYPE_STRING, GObject.TYPE_STRING)
            completion = Gtk.EntryCompletion()
            completion.set_model(store)
            # `steam_app_Sea of Stars` que nunca casa com janela nenhuma.
            completion.set_text_column(0)
            completion.set_minimum_key_length(1)
            completion.set_popup_completion(True)
            completion.set_inline_completion(False)
            completion.set_match_func(self._jogo_casa_com_o_texto, None)
            completion.connect("match-selected", self._on_jogo_escolhido_na_lista)
            entry.set_completion(completion)
        except Exception as exc:
            logger.debug("lista_de_jogos_sem_completacao", err=str(exc))
            return
        self._jogos_store = store
        run_in_thread(
            catalogo_de_jogos,
            on_success=self._guardar_jogos_do_pc,
            on_failure=lambda exc: bool(
                logger.debug("catalogo_de_jogos_falhou", err=str(exc))
            ),
        )

    def _guardar_jogos_do_pc(self, jogos: Any) -> bool:
        """Recebe o catálogo lido na thread e enche a lista suspensa."""
        try:
            self._jogos_do_pc = list(jogos or [])
            self._nomes_dos_jogos = nomes_por_appid(self._jogos_do_pc)
            alvo = getattr(self, "_jogos_store", None)
            if alvo is not None:
                alvo.clear()
                for jogo in self._jogos_do_pc:
                    alvo.append([jogo.rotulo, jogo.appid])
            logger.info("jogos_do_pc_lidos", quantos=len(self._jogos_do_pc))
            self._atualizar_frase_do_jogo()
        except Exception as exc:
            logger.debug("lista_de_jogos_nao_montou", err=str(exc))
        return False

    def _jogo_casa_com_o_texto(
        self, _completion: Any, chave: str, iterador: Any, _dados: Any = None
    ) -> bool:
        """A linha entra na lista suspensa para o que ela digitou até agora?

        O GTK entrega a `chave` já achatada; a comparação de verdade — sem
        acento, por pedaço do nome e por começo do número — é da função pura
        `jogos_locais.casa_com_o_que_ela_digitou`, que o teste exercita sem GTK.
        """
        try:
            store = getattr(self, "_jogos_store", None)
            if store is None:
                return False
            appid = store.get_value(iterador, 1)
            for jogo in getattr(self, "_jogos_do_pc", []):
                if jogo.appid == appid:
                    return casa_com_o_que_ela_digitou(jogo, chave)
        except Exception:
            return False
        return False

    def _on_jogo_escolhido_na_lista(
        self, _completion: Any, model: Any, iterador: Any
    ) -> bool:
        """Ela escolheu um jogo: o campo fica com o APPID, não com o rótulo."""
        with contextlib.suppress(Exception):
            appid = model.get_value(iterador, 1)
            entry = self._get("profile_simple_custom_name")
            if entry is not None and appid:
                entry.set_text(str(appid))
                with contextlib.suppress(Exception):
                    entry.set_position(-1)
        return True

    def _colar_virou_numero(self) -> bool:
        """Endereço colado no campo vira o appid. ``True`` = o campo foi reescrito."""
        if getattr(self, "_reescrevendo_o_campo_do_jogo", False):
            return False
        entry = self._get("profile_simple_custom_name")
        if entry is None:
            return False
        try:
            bruto = (entry.get_text() or "").strip()
        except Exception:
            return False
        appid = normalize_appid(bruto)
        if appid is None or appid == bruto:
            return False
        self._reescrevendo_o_campo_do_jogo = True
        try:
            entry.set_text(appid)
            with contextlib.suppress(Exception):
                entry.set_position(-1)
        except Exception:
            return False
        finally:
            self._reescrevendo_o_campo_do_jogo = False
        # O `set_text` já reentrou aqui com o campo normalizado e fez o resto.
        return True

    def _atualizar_frase_do_jogo(self) -> None:
        """Escreve (ou apaga) o rótulo que fica ao lado do campo do jogo."""
        rotulo = self._get("profile_jogo_reconhecido")
        if rotulo is None:
            return
        try:
            if self._selected_simple_choice() != "steam_game":
                rotulo.set_text("")
                rotulo.set_visible(False)
                return
            entry = self._get("profile_simple_custom_name")
            texto = (entry.get_text() or "") if entry is not None else ""
            nomes = getattr(self, "_nomes_dos_jogos", {})
            decisao = frase_do_campo_do_jogo(texto, nomes)
            do_carimbo = frase_da_ponte_confirmada(
                getattr(self, "_pontes_confirmadas", None), texto
            )
            if decisao is None and do_carimbo is None:
                rotulo.set_text("")
                rotulo.set_visible(False)
                return
            linhas: list[str] = []
            if decisao is not None:
                frase, e_alerta = decisao
                cor = "#ffb86c" if e_alerta else "#8be9fd"
                linhas.append(
                    f'<span foreground="{cor}">{escapar_markup(frase)}</span>'
                )
            if do_carimbo is not None:
                linhas.append(f"<i>{escapar_markup(do_carimbo)}</i>")
            rotulo.set_markup("\n".join(linhas))
            with contextlib.suppress(Exception):
                rotulo.set_tooltip_text(
                    "\n".join(
                        p
                        for p in (
                            decisao[0] if decisao is not None else None,
                            do_carimbo,
                        )
                        if p
                    )
                )
            rotulo.set_visible(True)
        except Exception as exc:
            logger.debug("frase_do_jogo_falhou", err=str(exc))

    def _buscar_as_pontes_confirmadas(self) -> None:
        """Pede ao daemon o carimbo de cada jogo — por GESTO, nunca por tique.

        **Por que `daemon.status` e não o `state_full` que a janela já lê a cada
        tique:** o `state_full` TAMBÉM publica `pontes_confirmadas` desde a
        BG-02 (`daemon/ipc_handlers.py:1814`, dentro de
        `_handle_daemon_state_full`), mas **atrás de um cache de 5 s**
        (`_PONTES_CONFIRMADAS_TTL_SEC`, `:189`) — porque a leitura crua abre
        CADA perfil do disco sob `FileLock` e o tique roda a 10-20 Hz. Quem
        precisa da resposta exata no instante seguinte ao gesto é esta caixa: o
        carimbo muda justamente quando um perfil é salvo ou confirmado, e o
        `daemon.status` não passa pelo cache. A escolha está escrita dos dois
        lados — ver o comentário do TTL, que nomeia esta aba.

        Best-effort inteiro: daemon offline deixa o cache como está e a linha
        simplesmente não aparece — que é o silêncio já contratado no §P2.
        """
        call_async(
            method="daemon.status",
            params={},
            on_success=self._ao_chegar_o_carimbo_das_pontes,
            on_failure=lambda _exc: False,
        )

    def _ao_chegar_o_carimbo_das_pontes(self, result: Any = None) -> bool:
        """Callback GTK: guarda o carimbo e repinta a linha do jogo."""
        if isinstance(result, dict):
            pontes = result.get("pontes_confirmadas")
            self._pontes_confirmadas = pontes if isinstance(pontes, dict) else {}
            with contextlib.suppress(Exception):
                self._atualizar_frase_do_jogo()
        return False

    def on_profile_steam_input_toggled(self, check: Any = None) -> None:
        """Marca/desmarca ESTE jogo na allowlist do Steam Input."""
        if getattr(self, "_suppress_steam_input_toggle", False):
            return
        if check is None:
            check = self._get("profile_steam_input_check")
        try:
            marcar = bool(check.get_active())
        except Exception:
            return
        appid = self._appid_do_editor()
        if appid is None:
            self._toast_profile(
                "Escreva o número do jogo da Steam antes de marcar."
            )
            self._sincronizar_caixa_do_steam_input()
            return
        # RELANCAR-01 (08/08/2026): marcar/desmarcar cria uma BORDA em
        if self._perguntar_antes_de_relancar(
            mudanca="steam_input_do_jogo",
            valor="marcado" if marcar else "desmarcado",
            aplicar=lambda: self._gravar_marca_do_steam_input(appid, marcar),
        ):
            return
        self._gravar_marca_do_steam_input(appid, marcar)

    def _gravar_marca_do_steam_input(self, appid: str, marcar: bool) -> None:
        """Escreve a marca no disco e avisa o daemon. Separado de propósito."""
        try:
            from hefesto_dualsense4unix.integrations import (
                steam_launch_options as slo,
            )

            if marcar:
                status = slo.add_appid_to_steam_input_allowlist(
                    appid, nota="marcado no editor de perfil"
                )
            else:
                status = slo.remove_appid_from_steam_input_allowlist(appid)
        except Exception as exc:
            logger.warning("steam_input_do_perfil_falhou", err=str(exc))
            status = "erro"
        self._toast_profile(
            texto_da_marca_do_steam_input(status, appid, self._controles_na_mesa())
        )
        if status in ("adicionado", "removido"):
            self._avisar_o_daemon_da_allowlist()
        self._sincronizar_caixa_do_steam_input()
        self._sincronizar_outros_marcados()

    def _controles_na_mesa(self) -> int | None:
        """Quantos controles CONECTADOS o daemon reporta, ou None se não der."""
        contagem = getattr(self, "_controles_conectados", None)
        return contagem if isinstance(contagem, int) else None

    def _avisar_o_daemon_da_allowlist(self) -> None:
        """Faz a marca VALER agora, sem reiniciar nada."""
        recarregar = getattr(self, "_recarregar_apos_allowlist", None)
        if callable(recarregar):
            with contextlib.suppress(Exception):
                recarregar()
            return
        with contextlib.suppress(Exception):
            call_async(
                method="launch_env.refresh",
                params={},
                on_success=lambda _r: False,
                on_failure=lambda _e: False,
            )

    def _prefill_modo_de_jogo(self) -> None:
        """Perfil NOVO de jogo nasce com o modo jogo pré-selecionado (MODO-01/B1)."""
        if not getattr(self, "_new_profile", False):
            return
        kind_sel = getattr(self, "_mode_kind_selector", None)
        if kind_sel is None:
            return
        with contextlib.suppress(Exception):
            if (kind_sel.get_active_id() or "none") != "none":
                return
        bruto: object = None
        flavor_sel = getattr(self, "_mode_flavor_selector", None)
        if flavor_sel is not None:
            with contextlib.suppress(Exception):
                bruto = flavor_sel.get_active_id()
        self._set_mode_editor(
            ProfileModeConfig(
                kind="gamepad", gamepad_flavor=normalizar_gamepad_flavor(bruto)
            )
        )

        from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
            mascaras_validas,
        )

        def _on_state(result: Any) -> bool:
            try:
                if not isinstance(result, dict):
                    return False
                gamepad = result.get("gamepad_emulation")
                flavor = (gamepad or {}).get("flavor") if isinstance(gamepad, dict) else None
                if flavor not in mascaras_validas():
                    return False
                seletor = getattr(self, "_mode_flavor_selector", None)
                kind_atual = getattr(self, "_mode_kind_selector", None)
                if seletor is None or kind_atual is None:
                    return False
                if (kind_atual.get_active_id() or "none") != "gamepad":
                    return False
                seletor.set_active_id(flavor)
            except Exception as exc:
                logger.debug("prefill_modo_jogo_falhou", err=str(exc))
            return False

        call_async(
            method="daemon.state_full",
            params=None,
            on_success=_on_state,
            on_failure=lambda _exc: False,
            timeout_s=0.5,
        )

    def _prefill_steam_appid(self) -> None:
        """Preenche o appid a partir do jogo em foco (R-12 item 1)."""
        entry = self._get("profile_simple_custom_name")
        if entry is None:
            return
        try:
            if (entry.get_text() or "").strip():
                return
        except Exception:
            return

        def _on_state(result: Any) -> bool:
            try:
                if not isinstance(result, dict):
                    return False
                from hefesto_dualsense4unix.app.actions.launch_wrapper_dialog import (
                    extract_steam_appid,
                )

                appid = extract_steam_appid(result.get("window_detect_last_class"))
                if not appid:
                    return False
                alvo = self._get("profile_simple_custom_name")
                if alvo is None or (alvo.get_text() or "").strip():
                    return False
                if self._selected_simple_choice() != "steam_game":
                    return False
                alvo.set_text(appid)
                self._toast_profile(f"Jogo em foco detectado: appid {appid}")
            except Exception as exc:
                logger.debug("prefill_appid_falhou", err=str(exc))
            return False

        call_async(
            method="daemon.state_full",
            params=None,
            on_success=_on_state,
            on_failure=lambda _exc: False,
            timeout_s=0.5,
        )


    def on_profile_selection_changed(self, selection: Gtk.TreeSelection) -> None:
        name = self._selected_profile_name(selection)
        if name is None:
            return
        profile = self._find_cached_profile(name)
        if profile is None:
            return
        if self._selecao_programatica and self._ha_trabalho_no_editor():
            logger.info(
                "perfis_editor_preservado_em_selecao_automatica",
                linha=name,
                editando=getattr(self, "_alvo_do_salvar", None),
            )
            return
        self._populate_editor(profile)

    # perfil na hora (profile.switch sem confirmação), atropelando edição em
    # andamento (selecionar texto/navegar vira 2 cliques rápidos por

    def on_profile_new(self, _btn: Gtk.Button | None) -> None:
        self._duplicate_source = None
        self._new_profile = True
        self._alvo_do_salvar = None
        self._get("profile_name_entry").set_text("Novo perfil")
        self._get("profile_priority_scale").set_value(0)
        self._select_radio("any")
        self._get("profile_window_class_entry").set_text("")
        self._get("profile_title_regex_entry").set_text("")
        self._get("profile_process_name_entry").set_text("")
        self._get("profile_simple_custom_name").set_text("")
        self._set_mode_editor(None)
        self._mode_advanced = False
        stack: Gtk.Stack = self._get("profile_editor_stack")
        if stack is not None:
            stack.set_visible_child_name("simples")
        switch: Gtk.Switch = self._get("profile_advanced_switch")
        if switch is not None:
            self._suppress_advanced_toggle = True
            try:
                switch.set_active(False)
            finally:
                self._suppress_advanced_toggle = False
        # reabilitadas em `_build_profile_from_editor` acreditavam nas marcas.
        self._esquecer_a_fotografia_do_editor()
        self._toast_profile("Novo perfil: edite e clique Salvar")
        self._nascer_com_o_jogo_em_foco()

    def _nascer_com_o_jogo_em_foco(self) -> None:
        """Pergunta ao daemon qual janela está em foco e nasce com a regra dela."""
        def _on_state(result: Any) -> bool:
            self._aplicar_nascimento_com_jogo(result)
            return False

        call_async(
            method="daemon.state_full",
            params=None,
            on_success=_on_state,
            on_failure=lambda _exc: False,
            timeout_s=0.5,
        )

    def _aplicar_nascimento_com_jogo(self, result: Any) -> bool:
        """Aplica ao editor o nascimento com a regra do jogo em foco.

        Separado do IPC para ser exercitável sem daemon. Devolve True quando
        de fato mexeu no editor.

        PERFIL-NASCE-CERTO-01 (entrega 1). Medido em 26/07, com ela jogando: o
        perfil que ela criou para o Pragmata nasceu `match:any` e prioridade 0,
        e por isso NUNCA valia no jogo — a regra R-21 nega autoridade a
        catch-all em janela de jogo, e o catch-all dela (prioridade 100) vencia
        em todo o resto. Ela não errou a configuração: a janela não tinha saída.

        Guardas deliberadamente estreitas — este caminho só age sobre um
        editor ainda intocado:

        - só em perfil NOVO (`_new_profile`);
        - só se o "Aplica a" ainda estiver em "Qualquer" (o default do nascer);
        - só com o campo do alvo VAZIO. Se ela já escolheu ou digitou algo, a
          resposta do daemon chegou tarde e não tem direito de atropelar.

        Sem jogo em foco, nada acontece e o perfil continua nascendo catch-all
        — que é o certo para um perfil de desktop.
        """
        try:
            if not isinstance(result, dict):
                return False
            if not getattr(self, "_new_profile", False):
                return False
            from hefesto_dualsense4unix.app.actions.launch_wrapper_dialog import (
                extract_steam_appid,
            )

            appid = extract_steam_appid(result.get("window_detect_last_class"))
            if not appid:
                return False
            if self._selected_simple_choice() != "any":
                return False
            entry = self._get("profile_simple_custom_name")
            if entry is not None and (entry.get_text() or "").strip():
                return False
            self._select_radio("steam_game")
            if entry is not None:
                entry.set_text(appid)
            prioridade = self._prioridade_acima_dos_catch_all()
            escala = self._get("profile_priority_scale")
            if escala is not None:
                escala.set_value(prioridade)
            self._toast_profile(
                f"Perfil novo para o jogo em foco (número {appid}), prioridade "
                f"{prioridade} — acima dos perfis que valem sempre."
            )
            return True
        except Exception as exc:
            logger.debug("nascer_com_o_jogo_em_foco_falhou", err=str(exc))
            return False

    def on_profile_duplicate(self, _btn: Gtk.Button | None) -> None:
        name = self._selected_profile_name()
        if name is None:
            self._toast_profile("Selecione um perfil para duplicar")
            return
        # _build_profile_from_editor copie triggers/lightbar/LEDs/etc — antes a
        self._duplicate_source = self._find_cached_profile(name)
        self._new_profile = False
        # NUNCA-TROCA-O-ALVO-01: a cópia vai para um arquivo NOVO — o Salvar
        self._alvo_do_salvar = None
        current = self._get("profile_name_entry").get_text()
        self._get("profile_name_entry").set_text(f"{current} (cópia)")
        self._toast_profile("Editor preenchido com cópia completa; ajuste o nome e Salvar")

    def on_profile_remove(self, _btn: Gtk.Button | None) -> None:
        name = self._selected_profile_name()
        if name is None:
            self._toast_profile("Selecione um perfil para remover")
            return
        from hefesto_dualsense4unix.app import gui_dialogs

        window = self._get("main_window")
        aviso = frase_da_remocao_do_perfil_ativo(name, perfil_que_esta_valendo())
        if not gui_dialogs.confirm_delete_profile(
            parent=window, name=name, aviso=aviso
        ):
            self._toast_profile("Remoção cancelada.")
            return
        try:
            delete_profile(name)
        except (FileNotFoundError, OSError) as exc:
            self._toast_profile(f"Falha ao remover: {exc}")
            return
        # alvo cair no fallback (a linha selecionada), que depois da recarga é
        # OUTRO perfil — e um Salvar em seguida viraria um RENAME dele, com o
        # diálogo do R-10 se oferecendo para apagá-lo. Mantido apontado para o
        # ele estiver limpo, que é o caso normal.
        self._reload_profiles_store()
        self._toast_profile(f"Perfil removido: {name}")
        self._notify_launch_env_refresh()

    def on_profile_activate(self, _btn: Gtk.Button | None) -> None:
        name = self._selected_profile_name()
        if name is None:
            self._toast_profile("Selecione um perfil para ativar")
            return
        # T4: profile.switch é I/O do daemon (asyncio.run no _safe_call síncrono
        # (250 ms) e o handler `profile.switch` levou ~1,2 s MEDIDOS no journal
        call_async(
            method="profile.switch",
            params={"name": name},
            on_success=lambda result: self._on_profile_switch_success(name, result),
            on_failure=self._on_profile_switch_failure,
            timeout_s=PROFILE_SWITCH_TIMEOUT_S,
        )
        # nada a ver com o daemon ter respondido ou não, e com o daemon parado
        self.pegar_carona_no_gesto(GESTO_APLICAR)

    def _on_profile_switch_success(self, name: str, result: Any = None) -> bool:
        """Callback GTK do switch de perfil: toast + re-sincroniza a seleção."""
        self._toast_profile(mensagem_de_ativacao(name, result))
        self._mark_active_profile_row(name)
        self._sync_selection_with_active_profile()
        self._refazer_as_abas_apos_ativar(name)
        return False

    def _refazer_as_abas_apos_ativar(self, name: str) -> None:
        """As abas passam a mostrar o perfil ATIVADO, na hora.

        ATIVAR-NAO-MENTE-01 (leva 2, 05/08). Queixa literal dela: *"o perfil
        que eu ativei não aplica imediatamente as features das abas"*. E era
        verdade — `on_profile_activate` não refazia aba nenhuma. As abas só
        acompanhavam pelo tique de 2 Hz, e esse caminho
        (`_reconciliar_draft_com_perfil_ativo`) tem um portão que DESISTE
        quando há edição pendente: com uma cor mexida e não salva, a ativação
        explícita dela não mudava a tela nunca.

        Recarregar em silêncio seria trocar um jeito de perder trabalho por
        outro (é o que a R-08 já tinha decidido para o tique). Ignorar em
        silêncio deixa as abas mentindo. Então a decisão é DELA, por diálogo —
        e o default do diálogo é MANTER o que ela não salvou.
        """
        pendente = False
        checar = getattr(self, "_tem_edicao_pendente", None)
        if callable(checar):
            with contextlib.suppress(Exception):
                pendente = bool(checar())
        if pendente:
            from hefesto_dualsense4unix.app import gui_dialogs

            editando = getattr(self, "_active_profile_name", "") or None
            if not gui_dialogs.confirm_discard_pending_edits(
                parent=self._get("main_window"), ativado=name, editando=editando
            ):
                self._toast_profile(
                    f"Perfil ativado: {name}. As abas seguem mostrando as suas "
                    f"alterações não salvas de '{editando or '—'}'."
                )
                return
        self._recarregar_as_abas_do_perfil_ativo()

    def _recarregar_as_abas_do_perfil_ativo(self) -> None:
        """Repinta as abas com o rascunho em memória. NÃO relê o disco hoje."""
        recarregar = getattr(self, "_bootstrap_draft_async", None)
        if callable(recarregar):
            try:
                recarregar()
                return
            except Exception as exc:
                logger.warning("ativar_recarregar_rascunho_falhou", err=str(exc))
        from hefesto_dualsense4unix.app.actions.footer_actions import (
            _refresh_all_tabs,
        )

        try:
            _refresh_all_tabs(self)
        except Exception as exc:
            logger.warning("ativar_refazer_abas_falhou", err=str(exc))

    def _on_profile_switch_failure(self, exc: Exception) -> bool:
        """Callback GTK de falha do switch (daemon offline / erro de transporte)."""
        logger.debug("profile_switch_falhou", err=str(exc))
        # ("Não consegui aplicar o perfil — o Hefesto pode estar desligado.").
        self._toast_profile("Não consegui trocar de perfil — o Hefesto pode estar desligado.")
        return False

    def on_profile_reload(self, _btn: Gtk.Button | None) -> None:
        self._reload_profiles_store()
        self._toast_profile("Lista recarregada")

    def on_profile_save(self, _btn: Gtk.Button | None) -> None:
        try:
            profile = self._build_profile_from_editor()
        except (ValueError, ValidationError) as exc:
            self._toast_profile(self._humanize_profile_error(exc))
            return
        # NUNCA-TROCA-O-ALVO-01: quem responde "que perfil eu estou editando?" é
        # selecionada agora — a lista se move sozinha (sync com o perfil ativo,
        selected = self._alvo_do_salvar_do_editor()
        cache: list[Profile] = getattr(self, "_profiles_cache", [])
        selecionado = find_by_slug(selected, cache) if selected else None
        e_novo = bool(getattr(self, "_new_profile", False))
        duplicando = self._duplicate_source is not None

        # prioridade disputando as mesmas janelas, e o "removido" voltando a
        renomeando_de: str | None = None
        if (
            not e_novo
            and not duplicando
            and selecionado is not None
            and not mesmo_slug(selecionado.name, profile.name)
        ):
            escolha = self._prompt_rename_or_copy(selecionado.name, profile.name)
            if escolha is None:
                self._toast_profile(_motivo_do_cancelamento())
                return
            if escolha == "renomear":
                renomeando_de = selecionado.name

        alvo = find_by_slug(profile.name, cache)
        editando_em_lugar = (
            not e_novo
            and not duplicando
            and alvo is not None
            and selecionado is not None
            and mesmo_slug(alvo.name, selecionado.name)
        )
        if alvo is not None and not editando_em_lugar:
            from hefesto_dualsense4unix.app import gui_dialogs

            window = self._get("main_window")
            if not gui_dialogs.prompt_overwrite_existing(parent=window, name=alvo.name):
                self._toast_profile(_motivo_do_cancelamento())
                return
        original = selecionado if renomeando_de is not None else alvo
        if (
            isinstance(profile.match, MatchAny)
            and original is not None
            and not isinstance(original.match, MatchAny)
        ):
            from hefesto_dualsense4unix.app import gui_dialogs

            window = self._get("main_window")
            # que a lista chama de "Só manual".
            if not gui_dialogs.confirm_downgrade_match_to_any(
                parent=window,
                name=original.name,
                regra_atual=_match_label(original.match),
            ):
                self._toast_profile(_motivo_do_cancelamento())
                return
        # regra: bastava trocar o número do jogo na página simples e ligar o
        # (`_mostrar_a_regra_nos_campos_crus`). Isto é o cinto para o gesto que
        if original is not None and rebaixamento_para_so_manual(
            original.match, profile.match
        ):
            from hefesto_dualsense4unix.app import gui_dialogs

            window = self._get("main_window")
            if not gui_dialogs.confirm_downgrade_match_to_manual(
                parent=window,
                name=original.name,
                regra_atual=_match_label(original.match),
            ):
                self._toast_profile(_motivo_do_cancelamento())
                return
        if original is not None and queda_de_prioridade_pede_aviso(
            original.priority, profile.priority
        ):
            from hefesto_dualsense4unix.app import gui_dialogs

            window = self._get("main_window")
            if not gui_dialogs.confirm_downgrade_priority(
                parent=window,
                name=original.name,
                de=int(original.priority),
                para=int(profile.priority),
            ):
                self._toast_profile(_motivo_do_cancelamento())
                return
        # o `profile.switch` de migração precisa da foto anterior.
        try:
            ativo_antes = active_profile_name()
        except Exception:
            ativo_antes = None
        try:
            save_profile(profile)
        except OSError as exc:
            self._toast_profile(f"Falha ao salvar: {exc}")
            return
        if renomeando_de is not None:
            try:
                delete_profile(renomeando_de)
            except (FileNotFoundError, OSError, ValueError) as exc:
                logger.warning(
                    "profile_rename_delete_falhou", antigo=renomeando_de, err=str(exc)
                )
                self._toast_profile(
                    f"Salvo como {profile.name}, mas o antigo "
                    f"'{renomeando_de}' não pôde ser removido: {exc}"
                )
        self._duplicate_source = None
        self._new_profile = False
        self._alvo_do_salvar = profile.name
        self._regra_tocada = False
        self._prioridade_tocada = False
        self._modo_tocado = False
        self._reconciliar_rascunho_com_perfil_salvo(profile, renomeando_de)
        self._reload_profiles_store(select_name=profile.name)
        # ATIVO agora reaplica na hora via `profile.switch` (relê o disco).
        precisa_reaplicar = ativo_antes is not None and (
            ativo_antes == profile.name or ativo_antes == renomeando_de
        )
        self._reaplicar_e_dizer(profile.name, renomeando_de, precisa_reaplicar)
        self._notify_launch_env_refresh()
        # Pragmata em 16/08. As duas linhas andam juntas por isso.
        self.pegar_carona_no_gesto(GESTO_SALVAR)

    # LEITURA de 250 ms, e o `profile.switch` não cabe nele. Trocar só o texto,

    def _reaplicar_e_dizer(
        self, nome: str, renomeando_de: str | None, reaplicar: bool
    ) -> None:
        """Reaplica no controle (se for o caso) e diz o que de fato aconteceu."""
        if not reaplicar:
            self._toast_profile(mensagem_do_salvar(nome, renomeando_de))
            return
        call_async(
            method="profile.switch",
            params={"name": nome},
            on_success=lambda result: self._ao_reaplicar_o_salvo(
                nome, renomeando_de, result
            ),
            on_failure=lambda exc: self._ao_nao_reaplicar_o_salvo(
                nome, renomeando_de, exc
            ),
            timeout_s=PROFILE_SWITCH_TIMEOUT_S,
        )

    def _ao_reaplicar_o_salvo(
        self, nome: str, renomeando_de: str | None, result: Any = None
    ) -> bool:
        """Callback GTK: o daemon aceitou — o toast lê o relatório `secoes`."""
        self._toast_profile(
            mensagem_do_salvar(nome, renomeando_de, reaplicou=True, result=result)
        )
        return False

    def _ao_nao_reaplicar_o_salvo(
        self, nome: str, renomeando_de: str | None, exc: Exception
    ) -> bool:
        """Callback GTK: o daemon não confirmou. O disco mudou; o controle não."""
        logger.debug("salvar_reaplicar_falhou", perfil=nome, err=str(exc))
        self._toast_profile(mensagem_do_salvar(nome, renomeando_de))
        return False


    def _prompt_rename_or_copy(self, antigo: str, novo: str) -> str | None:
        """Ponte para o diálogo de rename (R-10) — ponto único de override."""
        return dialogo_renomear_ou_copiar(
            self._get("main_window"), antigo, novo
        )

    def _notify_launch_env_refresh(self) -> None:
        """Avisa o daemon que o conjunto de perfis mudou (`launch_env.refresh`).

        save/delete de perfil rodam no processo da GUI, direto no disco — o
        daemon não vê (achado MED da revisão adversarial da Fase 2).
        Best-effort: daemon offline é normal (rematerializa no boot).
        """
        call_async(
            method="launch_env.refresh",
            params={},
            on_success=lambda _result: False,
            on_failure=lambda _exc: False,
        )

    def _apply_editor_mode(self) -> None:
        """Aplica a página correta da stack conforme _mode_advanced."""
        stack: Gtk.Stack = self._get("profile_editor_stack")
        page = "avancado" if self._mode_advanced else "simples"
        stack.set_visible_child_name(page)


    def _regra_real_do_perfil_aberto(self) -> Match | None:
        """A regra que o perfil aberto TEM agora — a mesma conta do Salvar.

        Não é "o que está no disco" nem "o que a página simples mostra": é o
        que este editor gravaria se ela clicasse Salvar neste segundo. Por isso
        a conta é a MESMA de `_build_profile_from_editor`, linha por linha —
        duas contas para a mesma pergunta divergiriam no primeiro caso de
        borda, e aí a página avançada voltaria a mentir, só que de um jeito
        mais convincente.

        Os dois ramos, na ordem em que o Salvar os avalia:

        - ela ainda NÃO mexeu na regra → vale o que o disco diz, inteiro. É o
          ramo que preserva o campo que a página simples não mostra
          (ESCONDER-EM-VEZ-DE-SAIR-01) e o que impede a ida ao avançado de
          apagar um match complexo que o seletor "Aplica a" não sabe exprimir;
        - ela MEXEU → vale a leitura da página simples, que é a página que
          estava na frente até agora (este helper só é chamado ao LIGAR o
          avançado).

        ``None`` quer dizer "não há regra conhecida a mostrar" — perfil novo
        sem escolha utilizável, dublê de teste, glade degradado. O chamador não
        escreve nada nesse caso: em branco por falta de resposta é melhor que
        em branco por invenção.
        """
        nome = ""
        with contextlib.suppress(Exception):
            nome = (self._get("profile_name_entry").get_text() or "").strip()
        regra_do_disco = self._regra_do_disco_ao_salvar(nome)
        # O espelho de `_build_profile_from_editor`: sem fotografia de abertura
        mexida = (
            self._regra_foi_mexida()
            if self._regra_do_disco is not None
            else self._regra_tocada
        )
        if regra_do_disco is not None and not mexida:
            return regra_do_disco
        custom: str | None = None
        with contextlib.suppress(Exception):
            custom = (
                self._get("profile_simple_custom_name").get_text() or ""
            ).strip() or None
        try:
            return from_simple_choice(
                choice=self._selected_simple_choice(),
                custom_name=custom,
                regra_do_disco=regra_do_disco,
            )
        except ValueError:
            return regra_do_disco

    def _mostrar_a_regra_nos_campos_crus(self) -> None:
        """Escreve nos três campos crus a regra real do perfil aberto."""
        regra = self._regra_real_do_perfil_aberto()
        if regra is None:
            return
        mexida_antes = self._regra_foi_mexida()
        campos = (
            (
                "profile_window_class_entry",
                ",".join(getattr(regra, "window_class", None) or []),
            ),
            (
                "profile_title_regex_entry",
                getattr(regra, "window_title_regex", None) or "",
            ),
            (
                "profile_process_name_entry",
                ",".join(getattr(regra, "process_name", None) or []),
            ),
        )
        for widget_id, texto in campos:
            widget = self._get(widget_id)
            if widget is None:
                continue
            with contextlib.suppress(Exception):
                widget.set_text(texto)
        if not mexida_antes:
            self._assinatura_da_regra_ao_abrir = self._assinatura_da_regra_no_editor()

    def _selected_simple_choice(self) -> str:
        """Retorna o id ativo do seletor "Aplica a:"."""
        combo = getattr(self, "_aplica_a", None)
        if combo is None:
            return "any"
        active_id = combo.get_active_id()
        if active_id in _RADIO_IDS:
            return str(active_id)
        return "any"

    def _select_radio(self, choice: str) -> None:
        """Seleciona o id correspondente no seletor "Aplica a:"."""
        combo = getattr(self, "_aplica_a", None)
        if combo is None:
            return
        target_id = choice if choice in _RADIO_IDS else "any"
        combo.set_active_id(target_id)

    def _selected_profile_name(
        self,
        selection: Gtk.TreeSelection | None = None,
    ) -> str | None:
        sel = selection or self._get("profiles_tree").get_selection()
        model, tree_iter = sel.get_selected()
        if tree_iter is None:
            return None
        return str(model.get_value(tree_iter, 0))

    def _reload_profiles_store(
        self,
        select_name: str | None = None,
        on_done: Any | None = None,
    ) -> None:
        """Recarrega a lista de perfis SEM bloquear a thread GTK.

        PERF-GUI-PROFILE-LOAD-NONBLOCKING-01: load_all_profiles() (glob + FileLock
        + parse Pydantic) roda em thread worker; o store e o cache em memória
        (`_profiles_cache`) são atualizados no callback, na thread GTK. `on_done`
        (opcional) roda após popular o store (ex.: sincronizar a seleção com o
        perfil ativo no boot).
        """
        def _load() -> list[Profile]:
            return list(load_all_profiles())

        def _on_loaded(profiles: Any) -> bool:
            self._profiles_cache = list(profiles)
            self._populate_profiles_store(profiles, select_name)
            if on_done is not None:
                on_done()
            return False

        run_in_thread(_load, _on_loaded)

    def _populate_profiles_store(
        self, profiles: list[Profile], select_name: str | None
    ) -> None:
        """Popula o ListStore a partir da lista de perfis (thread GTK)."""
        store = self._profiles_store
        atual: str | None = None
        if select_name is None:
            with contextlib.suppress(Exception):
                atual = self._selected_profile_name()
        anterior = self._selecao_programatica
        self._selecao_programatica = True
        try:
            store.clear()
            select_iter = None
            first_iter = None
            active = getattr(self, "_active_profile_hint", None)
            for profile in ordem_de_exibicao(profiles, active):
                e_o_ativo = profile.name == active
                weight = 700 if e_o_ativo else 400
                row_iter = store.append(
                    [
                        profile.name,
                        profile.priority,
                        rotulo_quando_usar(profile, profiles, active),
                        weight,
                        explicacao_da_disputa(profile, profiles, active),
                        realce_do_perfil_ativo() if e_o_ativo else None,
                    ]
                )
                if first_iter is None:
                    first_iter = row_iter
                desejado = select_name if select_name is not None else atual
                if desejado is not None and profile.name == desejado:
                    select_iter = row_iter
            target = select_iter if select_iter is not None else first_iter
            if target is not None:
                self._mover_selecao_sem_gesto(target)
        finally:
            self._selecao_programatica = anterior

    def _mark_active_profile_row(self, active: str | None) -> None:
        """Realça a linha do perfil ATIVO no ListStore, in-place: cor, negrito e topo.

        EMPATE-01/E2: o perfil ativo é também o INCUMBENTE, que é o terceiro
        termo do desempate entre os "Sempre" — trocar de perfil pode trocar o
        vencedor anunciado. Por isso as colunas da disputa (2 e 4) são
        recalculadas aqui junto com o negrito, e não só na recarga do disco.

        PERFIL-ATUAL-01: e a linha ativa também ganha a COR e o PRIMEIRO LUGAR
        aqui, sem passar pelo disco — ativar um perfil é gesto dela, e reler
        `load_all_profiles()` para mover uma linha faria a lista piscar em cima
        do editor aberto.
        """
        self._active_profile_hint = active
        store = getattr(self, "_profiles_store", None)
        if store is None:
            return
        cache: list[Profile] = list(getattr(self, "_profiles_cache", []) or [])
        por_nome = {p.name: p for p in cache}
        row = store.get_iter_first()
        while row is not None:
            name = store.get_value(row, 0)
            e_o_ativo = name == active
            store.set_value(row, 3, 700 if e_o_ativo else 400)
            store.set_value(row, 5, realce_do_perfil_ativo() if e_o_ativo else None)
            perfil = por_nome.get(name)
            if perfil is not None:
                with contextlib.suppress(Exception):
                    store.set_value(
                        row, 2, rotulo_quando_usar(perfil, cache, active)
                    )
                    store.set_value(
                        row, 4, explicacao_da_disputa(perfil, cache, active)
                    )
            row = store.iter_next(row)
        self._levar_o_ativo_para_o_topo(store, active)

    def _levar_o_ativo_para_o_topo(self, store: Any, active: str | None) -> None:
        """Move a linha do perfil dela para a primeira posição (PERFIL-ATUAL-01)."""
        cache: list[Profile] = list(getattr(self, "_profiles_cache", []) or [])
        if not cache:
            return
        nomes: list[str] = []
        row = store.get_iter_first()
        while row is not None:
            nomes.append(str(store.get_value(row, 0)))
            row = store.iter_next(row)
        if len(set(nomes)) != len(nomes):
            return
        desejada = [
            str(getattr(p, "name", "")) for p in ordem_de_exibicao(cache, active)
        ]
        if sorted(desejada) != sorted(nomes):
            return
        posicao = {nome: idx for idx, nome in enumerate(nomes)}
        nova_ordem = [posicao[nome] for nome in desejada]
        if nova_ordem == list(range(len(nova_ordem))):
            return
        with contextlib.suppress(Exception):
            store.reorder(nova_ordem)

    def _find_cached_profile(self, name: str) -> Profile | None:
        """Retorna o perfil do cache em memória pelo nome, ou None."""
        cache: list[Profile] = getattr(self, "_profiles_cache", [])
        for profile in cache:
            if profile.name == name:
                return profile
        return None

    def _populate_editor(self, profile: Profile) -> None:
        """Preenche o editor com os dados do perfil.

        Detecta automaticamente se o match bate com um preset simples:
        - bate → modo simples, seleciona radio correspondente.
        - não bate → força modo avançado para não perder informação.

        NUNCA-TROCA-O-ALVO-01: esta é a linha em que a janela decide o que ela
        está editando, e ela SÓ é chamada por gesto dela (clique na lista) ou
        com o editor limpo — quem faz esse portão é
        `on_profile_selection_changed`, e a razão inteira está em
        `_ha_trabalho_no_editor`. Aqui só se registra a decisão:
        `_alvo_do_salvar` passa a ser este perfil, e é ele — não a linha
        selecionada — que o `on_profile_save` vai gravar por cima.
        """
        self._duplicate_source = None
        self._new_profile = False
        self._alvo_do_salvar = profile.name
        self._get("profile_name_entry").set_text(profile.name)
        prio = max(0, min(PRIORIDADE_MAXIMA, profile.priority))
        self._get("profile_priority_scale").set_value(prio)
        self._set_mode_editor(profile.mode)

        match = profile.match
        preset_key = detect_simple_preset(match)

        if preset_key is not None:
            self._select_radio(preset_key)
            if preset_key in _IDS_COM_CAMPO_LIVRE:
                self._get("profile_simple_custom_name").set_text(simple_extra(match))
            else:
                self._get("profile_simple_custom_name").set_text("")
            stack: Gtk.Stack = self._get("profile_editor_stack")
            stack.set_visible_child_name("simples")
            switch: Gtk.Switch = self._get("profile_advanced_switch")
            self._suppress_advanced_toggle = True
            try:
                switch.set_active(False)
            finally:
                self._suppress_advanced_toggle = False
            self._mode_advanced = False
        else:
            self._select_radio("any")
            self._get("profile_simple_custom_name").set_text("")
            if isinstance(match, MatchCriteria):
                self._get("profile_window_class_entry").set_text(
                    ",".join(match.window_class)
                )
                self._get("profile_title_regex_entry").set_text(
                    match.window_title_regex or ""
                )
                self._get("profile_process_name_entry").set_text(
                    ",".join(match.process_name)
                )
            else:
                self._get("profile_window_class_entry").set_text("")
                self._get("profile_title_regex_entry").set_text("")
                self._get("profile_process_name_entry").set_text("")
            stack = self._get("profile_editor_stack")
            stack.set_visible_child_name("avancado")
            switch = self._get("profile_advanced_switch")
            self._suppress_advanced_toggle = True
            try:
                switch.set_active(True)
            finally:
                self._suppress_advanced_toggle = False
            self._mode_advanced = True

        # que o disco realmente diz. `_build_profile_from_editor` compara as
        self._regra_do_disco = profile.match
        self._assinatura_da_regra_ao_abrir = self._assinatura_da_regra_no_editor()
        self._prioridade_do_disco = profile.priority
        self._prioridade_ao_abrir = prio
        self._regra_tocada = False
        self._prioridade_tocada = False

    def _assinatura_da_regra_no_editor(self) -> tuple[object, ...]:
        """Fotografia dos widgets que definem a REGRA de janela do perfil."""
        def texto(widget_id: str) -> str:
            widget = self._get(widget_id)
            try:
                return (widget.get_text() or "").strip()
            except Exception:
                return ""

        return (
            self._selected_simple_choice(),
            texto("profile_simple_custom_name"),
            texto("profile_window_class_entry"),
            texto("profile_title_regex_entry"),
            texto("profile_process_name_entry"),
        )

    def _on_prioridade_tocada(self, _escala: object = None) -> None:
        """A escala de prioridade se mexeu — marca o gesto (SALVAR-NAO-REBAIXA-01)."""
        self._prioridade_tocada = True

    def _regra_foi_mexida(self) -> bool:
        """Ela mudou a regra de janela desde que este perfil abriu no editor?"""
        ao_abrir = self._assinatura_da_regra_ao_abrir
        if ao_abrir is None:
            return True
        if self._regra_tocada:
            return True
        return self._assinatura_da_regra_no_editor() != ao_abrir

    def _prioridade_foi_mexida(self) -> bool:
        """Ela moveu a escala de prioridade desde que o perfil abriu no editor?"""
        if self._prioridade_tocada:
            return True
        ao_abrir = self._prioridade_ao_abrir
        if ao_abrir is None:
            return True
        try:
            return int(self._get("profile_priority_scale").get_value()) != int(ao_abrir)
        except Exception:
            return True

    def _perfil_que_o_salvar_sobrescreve(self, name: str) -> Profile | None:
        """O perfil JÁ EM DISCO que este Salvar vai gravar por cima, ou ``None``.

        SALVAR-NAO-REBAIXA-02: quem responde "quem vou sobrescrever?" é o SLUG,
        nunca o nome de exibição — a lição do R-10, e a mesma pergunta que
        `on_profile_save` já faz com `find_by_slug` para decidir o diálogo de
        sobrescrita. Lê o cache em memória, nunca o disco: este caminho roda na
        thread do GTK (PERF-GUI-PROFILE-LOAD-NONBLOCKING-01).
        """
        cache: list[Profile] = getattr(self, "_profiles_cache", None) or []
        try:
            return find_by_slug(name, cache)
        except Exception:
            return None

    def _regra_do_disco_ao_salvar(self, name: str) -> Match | None:
        """A regra que este Salvar sobrescreve — para NÃO apagar o que a tela não mostra.

        ESCONDER-EM-VEZ-DE-SAIR-01 (10/08/2026). A página simples do "Jogo da
        Steam" tem um campo só, o número; um perfil pode ter no disco também um
        ``process_name`` do mesmo jogo. ``from_simple_choice`` precisa dele para
        preservar o campo invisível — ver `profiles/simple_match.py`.

        Duas fontes, na mesma ordem que as guardas SALVAR-NAO-REBAIXA já usam:
        a fotografia tirada quando o perfil ABRIU (o caso normal) e, quando não
        há fotografia (perfil "novo" salvando por cima de um arquivo que
        existe — o buraco que a SALVAR-NAO-REBAIXA-02 mediu), o próprio disco
        pelo slug.

        Vale SÓ para o editor simples, e é de propósito: no avançado o
        ``process_name`` está na tela, e apagá-lo ali é um gesto dela. Devolver
        esta regra para lá desfaria a exclusão que ela acabou de fazer.
        """
        regra = self._regra_do_disco
        if regra is not None:
            return regra
        alvo = self._perfil_que_o_salvar_sobrescreve(name)
        return alvo.match if alvo is not None else None

    def _esquecer_a_fotografia_do_editor(self) -> None:
        """Zera as fotografias — o editor deixou de mostrar um perfil do disco.

        Chamado por "Novo perfil": ali não há valor de disco a preservar, e o
        que está nos widgets É a intenção dela. O que EXISTE em disco continua
        protegido na hora de salvar, por ``_perfil_que_o_salvar_sobrescreve``
        (SALVAR-NAO-REBAIXA-02) — esquecer aqui não pode virar rebaixar lá.
        """
        self._regra_do_disco = None
        self._assinatura_da_regra_ao_abrir = None
        self._prioridade_do_disco = None
        self._prioridade_ao_abrir = None
        self._regra_tocada = False
        self._prioridade_tocada = False

    def _prioridade_acima_dos_catch_all(self) -> int:
        """Prioridade que vence TODO perfil "vale sempre" hoje em disco."""
        cache: list[Profile] = getattr(self, "_profiles_cache", None) or []
        tetos = [p.priority for p in cache if p.e_catch_all]
        base = max(tetos) if tetos else 0
        return max(0, min(PRIORIDADE_MAXIMA, base + _FOLGA_ACIMA_DO_CATCH_ALL))

    def _edita_o_perfil_do_rascunho(self, name: str) -> bool:
        """O "Salvar" em curso está gravando o perfil que o RASCUNHO representa?

        ABAS-03 (25/07). A mesclagem com o rascunho só acontecia quando o nome
        digitado batia com o do perfil ativo — o que exclui justamente o
        RENAME, onde o nome já mudou. Nesse caminho a base vinha do disco e, em
        seguida, `on_profile_save` apagava o perfil antigo: toda a edição de
        cor, gatilho, vibração e teclado feita na sessão evaporava, sem aviso e
        sem chance de desfazer (o arquivo de origem já não existia).

        Quem responde "qual perfil o rascunho é" é `_active_profile_name`, não
        o campo Nome. Então a resposta é sim quando:

        - o nome digitado ocupa o MESMO ARQUIVO do perfil ativo — comparação
          por SLUG, a lição do R-10: "Navegacao" e "Navegação" são o mesmo
          `navegacao.json`, e comparar nome de exibição deixava a edição do
          próprio perfil ativo cair no ramo do disco; ou
        - o PERFIL ABERTO NO EDITOR é o perfil ativo e este save não é "Novo
          perfil" nem duplicação — ou seja, é o rename dele.

        NUNCA-TROCA-O-ALVO-01: "o perfil aberto no editor" era lido da linha
        selecionada, e a lista se move sozinha — o rename do perfil ativo caía
        no ramo do disco assim que o autoswitch pulava a seleção para outra
        linha, que é o mesmo estrago que esta guarda existe para impedir.

        As duas exclusões são as mesmas do R-09: "Novo perfil" parte de
        defaults (não pode clonar overrides por-MAC de quem estava
        selecionado) e a duplicação parte da fonte guardada.
        """
        ativo = getattr(self, "_active_profile_name", "") or ""
        if not ativo:
            return False
        if name == ativo or mesmo_slug(name, ativo):
            return True
        if getattr(self, "_new_profile", False):
            return False
        if getattr(self, "_duplicate_source", None) is not None:
            return False
        try:
            no_editor = self._alvo_do_salvar_do_editor() or ""
        except Exception:
            return False
        return bool(no_editor) and mesmo_slug(no_editor, ativo)

    def _reconciliar_rascunho_com_perfil_salvo(
        self, profile: Profile, renomeando_de: str | None
    ) -> None:
        """Reaponta o rascunho para o perfil ACABADO DE GRAVAR (ABAS-01).

        A aba Perfis é a única superfície que edita e persiste perfil, e ela
        nunca escrevia de volta em `self.draft` — não havia uma única
        atribuição a ele no arquivo. As seções que só ela edita (`mode`,
        `match`, `priority`, `suppress_desktop_emulation`) iam direto para o
        disco, enquanto o rascunho seguia com a fotografia tirada no boot da
        janela. Aí o "Salvar Perfil" do rodapé, que reemite essa fotografia,
        desfazia o trabalho:

            aba Perfis → Modo = "Jogar pelo Hefesto" → Salvar *(grava certo)*
            → aba Lightbar → muda a cor → rodapé "Salvar Perfil" →
            a seção `mode` SOME do arquivo.

        É o mesmo estrago do MODO-01 visto de outro ângulo: ela faz tudo certo
        e o modo do perfil evapora. Vale igual para regra de janela,
        prioridade e supressão.

        Só reaponta quando o perfil gravado É o do rascunho (mesmo arquivo que
        o ativo, ou o rename dele) — salvar OUTRO perfil pela aba Perfis não
        pode mexer no que as demais abas estão editando. No rename, o nome do
        perfil ativo migra junto: sem isso a reconciliação do tick de 2 Hz
        veria o `profile.switch` de migração como "trocaram de perfil por fora"
        e recarregaria o rascunho por baixo dela.

        A linha de base do "há edição pendente" (R-08) também acompanha: o que
        estava em memória acabou de virar disco, então a sessão volta a ficar
        limpa e a reconciliação com o perfil ativo continua funcionando pelo
        resto dela.
        """
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        ativo = getattr(self, "_active_profile_name", "") or ""
        if not ativo:
            return
        e_do_rascunho = mesmo_slug(profile.name, ativo) or (
            renomeando_de is not None and mesmo_slug(renomeando_de, ativo)
        )
        if not e_do_rascunho:
            return
        self.draft = draft.with_profile_identity(profile)
        self._active_profile_name = profile.name
        self._draft_baseline = self.draft

    def _build_profile_from_editor(self) -> Profile:
        """Constrói Profile a partir do editor (modo simples ou avançado)."""
        name = self._get("profile_name_entry").get_text().strip()
        priority = int(self._get("profile_priority_scale").get_value())

        match: Match
        if self._mode_advanced:
            wc = self._split_csv(
                self._get("profile_window_class_entry").get_text()
            )
            regex = self._get("profile_title_regex_entry").get_text().strip() or None
            pn = self._split_csv(
                self._get("profile_process_name_entry").get_text()
            )
            if not wc and not regex and not pn:
                match = MatchManual()
            else:
                match = MatchCriteria(
                    window_class=wc,
                    window_title_regex=regex,
                    process_name=pn,
                )
        else:
            choice = self._selected_simple_choice()
            custom = self._get("profile_simple_custom_name").get_text().strip() or None
            match = from_simple_choice(
                choice=choice,
                custom_name=custom,
                regra_do_disco=self._regra_do_disco_ao_salvar(name),
            )

        existing = self._find_cached_profile(name)
        selected_source = None
        try:
            selected_source = self._find_cached_profile(
                self._selected_profile_name() or ""
            )
        except Exception:
            selected_source = None
        # fazia o arquivo nascer clonando overrides por-MAC e
        if getattr(self, "_new_profile", False):
            source = existing or self._duplicate_source
        else:
            source = existing or self._duplicate_source or selected_source

        # — e é pior que perder o arquivo: `on_profile_save` chama
        draft = getattr(self, "draft", None)
        ativo = getattr(self, "_active_profile_name", "") or ""
        base: dict[str, Any]
        base_veio_do_rascunho = False
        if draft is not None and ativo and self._edita_o_perfil_do_rascunho(name):
            try:
                do_draft = draft.to_profile(ativo)
            except Exception as exc:
                logger.warning("profile_build_draft_falhou", erro=str(exc))
                do_draft = None
            if do_draft is not None:
                base = do_draft.model_dump(mode="python")
                base["controllers"] = do_draft.controllers
                source = do_draft
                base_veio_do_rascunho = True
            else:
                base = source.model_dump(mode="python") if source else {}
        else:
            base = source.model_dump(mode="python") if source else {}
        if source is not None:
            base["controllers"] = source.controllers

        # carimbo viaja junto, `pontes_confirmadas()` publica uma ponte que
        # mais comum que existe (salvar por cima de si mesmo), e ali o carimbo
        # (`profile_writer.carimbo_que_o_save_leva`, o dono único): DISCO, depois
        # (PERF-GUI-PROFILE-LOAD-NONBLOCKING-01) — e `on_profile_save` já grava
        # entregar o objeto validado que `carimbo_que_o_save_leva` promete.
        estreia = bool(getattr(self, "_new_profile", False)) or (
            getattr(self, "_duplicate_source", None) is not None
        )
        base["ponte"] = carimbo_que_o_save_leva(
            perfil_em_disco(name),
            None if estreia or source is None else source.ponte,
        )

        pending_brightness: float = getattr(self, "_pending_brightness", 1.0)
        leds_base: dict[str, Any] = dict(base.get("leds") or {})
        leds_base.setdefault("lightbar_brightness", pending_brightness)
        base["leds"] = leds_base

        # FEAT-PROFILE-MODE-GUI-01: a seção `mode` vem dos widgets do editor.
        if self._mode_kind_selector is not None:
            modo_do_rascunho_vence = (
                base_veio_do_rascunho
                and bool(getattr(draft, "mode_dirty", False))
                and not self._modo_tocado
            )
            if not modo_do_rascunho_vence:
                base["mode"] = self._mode_section_from_editor()

        prioridade_do_disco = self._prioridade_do_disco
        regra_do_disco = self._regra_do_disco
        prioridade_mexida = self._prioridade_foi_mexida()
        regra_mexida = self._regra_foi_mexida()
        if prioridade_do_disco is None or regra_do_disco is None:
            alvo_no_disco = self._perfil_que_o_salvar_sobrescreve(name)
            if alvo_no_disco is not None:
                if prioridade_do_disco is None:
                    prioridade_do_disco = alvo_no_disco.priority
                    prioridade_mexida = self._prioridade_tocada
                if regra_do_disco is None:
                    regra_do_disco = alvo_no_disco.match
                    regra_mexida = self._regra_tocada
        prioridade_final = priority
        if prioridade_do_disco is not None and not prioridade_mexida:
            prioridade_final = int(prioridade_do_disco)
        regra_final = match
        if regra_do_disco is not None and not regra_mexida:
            regra_final = regra_do_disco

        base.update(
            {
                "name": name,
                "priority": prioridade_final,
                "match": regra_final.model_dump(mode="python"),
            }
        )
        return Profile.model_validate(base)

    @staticmethod
    def _split_csv(raw: str) -> list[str]:
        return [item.strip() for item in raw.split(",") if item.strip()]

    @staticmethod
    def _humanize_profile_error(exc: Exception) -> str:
        """Traduz erros de validação do perfil para frase de gente (COR-D)."""
        text = str(exc)
        if text in MENSAGENS_DE_GENTE:
            return text
        if "name não pode ser vazio" in text:
            return "Dê um nome ao perfil."
        if "caractere inválido" in text:
            return "O nome não pode ter barra ( / ) nem dois pontos ( .. )."
        if "não produz slug válido" in text:
            return "Use letras ou números no nome do perfil."
        return "Não foi possível salvar. Revise os campos do perfil."

    def _toast_profile(self, msg: str) -> None:
        self._status_toast("profiles", msg)

    def _tem_edicao_pendente(self) -> bool:
        """As OUTRAS abas têm alteração por salvar? (R-08)

        Delega para :func:`profile_writer.tem_edicao_pendente`, que é onde a
        pergunta ficou quando a janela GTK saiu — a docstring de lá tem a
        medição de por que ela ficou sem dono.

        Aqui ela existe como MÉTODO porque é assim que os dois consumidores a
        procuram (``_ha_trabalho_no_editor`` e ``_refazer_as_abas_apos_ativar``,
        ambos por ``getattr(self, …)``), e porque um dublê de teste precisa
        poder trocá-la por uma que estoura para provar que a guarda fecha no
        escuro.

        **POR QUE NO FIM DO ARQUIVO, E COM IMPORT LOCAL** — 08/09/2026, e é
        cura de um defeito que eu mesmo criei e medi. A primeira versão punha o
        import no topo e o método no meio da classe: **16 linhas a mais**, e
        tudo abaixo andou junto. OITO citações `profiles_actions.py:NNNN` em
        `interface/aba10.py` e `interface/pacotes/a10_perfis.py` passaram a
        apontar para outra coisa, e o portão `citacoes-no-codigo` as pegou.
        Reapontá-las parecia o conserto — e não era: **uma delas vive dentro do
        `CSS` que `aba10.py` EMBUTE na página**, então mexer nela obriga a
        regerar `mockup/10-perfis.html` e a publicar, que é gesto DELA e não
        meu. O teste `test_os_dez_geradores_rodam` foi quem disse isso, e só
        apareceu na regressão dos doze lotes — portão nenhum o alcança.

        Entrando depois de `_toast_profile`, que é o último método do arquivo,
        nada se move: as oito citações continuam válidas e a bancada dela fica
        byte a byte onde estava.
        """
        from hefesto_dualsense4unix.app.actions.profile_writer import (
            tem_edicao_pendente,
        )

        return tem_edicao_pendente(self)


#     relê o perfil ATIVO — IPC `state_full` +   |  não lê disco nenhum
#    ativo lá é `rodape._draft_do_ativo`, que monta o `DraftConfig` do disco na
# pronto é `rodape._draft_do_ativo` — não o carregador da janela. O original
