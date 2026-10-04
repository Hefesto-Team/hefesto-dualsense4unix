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

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.carona_do_wrapper import (
    CaronaDoWrapperMixin,
)
from hefesto_dualsense4unix.profiles import schema as _schema
from hefesto_dualsense4unix.profiles.schema import (
    Match,
    Profile,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


PRIORIDADE_MAXIMA = _schema.PRIORIDADE_MAXIMA

_FOLGA_ACIMA_DO_CATCH_ALL = 10


# DualSense."* — e escolher entre dois botões sem saber o que cada um custa não


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


# `confirm_downgrade_match_to_any` cobre "o perfil passou a valer para TUDO".


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
    "mic:ganho": "ganho do microfone",
}

#: As seções POR CONTROLE do `profile.switch` (`<prefixo><uniq>`), com a palavra de tela
#: de cada uma. A ordem importa: `mic:ganho:` antes de `mic:`.
_PECAS_POR_CONTROLE: tuple[tuple[str, str], ...] = (
    ("mic:ganho:", "ganho do microfone de um controle"),
    ("mic:", "microfone de um controle"),
    ("speaker:", "alto-falante de um controle"),
    ("mascara:", "máscara de um controle"),
    ("sensores:", "sensores de um controle"),
    ("movimento:", "mira de um controle"),
)

#: O valor destas seções é o DADO que foi escrito (`mascara:<uniq>` → «xbox» ou «padrão»,
#: `sensores:<uniq>` → «giro=on accel=off»), e não um estado. Ler a palavra «aplicado» nelas
#: chamava de falta uma máscara que tinha entrado (03/10/2026, o Avatar Legends). A única
#: palavra de falta delas é a que o dono escreve quando recusa.
_PECAS_CUJO_VALOR_E_O_DADO: dict[str, frozenset[str]] = {
    "mascara:": frozenset({"recusado"}),
    "sensores:": frozenset(),
}

#: A peça de um controle que não está ligado agora não é falta: não há o que escrever, e o
#: produto reaplica quando ele conecta (`reapply_speaker_on_connect` e `reapply_mic_on_connect`).
_PECAS_QUE_ESPERAM_O_CONTROLE = ("speaker:", "mic:")
_SEM_CONTROLE = "ignorado_sem_controle"


def nome_da_secao_da_ativacao(chave: str) -> str:
    """A palavra de tela desta seção, ou a chave crua quando não há nome."""
    if chave in _NOMES_DAS_SECOES_DA_ATIVACAO:
        return _NOMES_DAS_SECOES_DA_ATIVACAO[chave]
    for prefixo, nome in _PECAS_POR_CONTROLE:
        if chave.startswith(prefixo):
            uniq = chave[len(prefixo) :]
            return f"{nome} ({uniq})" if uniq else nome
    return _NOMES_DAS_SECOES_DA_ATIVACAO.get(chave, chave)


def _e_falta(chave: str, estado: str) -> bool:
    """Esta seção, com este valor, é algo que NÃO entrou no controle?"""
    for prefixo, so_estas in _PECAS_CUJO_VALOR_E_O_DADO.items():
        if chave.startswith(prefixo):
            return estado in so_estas
    if estado in NAO_E_FALTA:
        return False
    if estado == _SEM_CONTROLE and chave.startswith(_PECAS_QUE_ESPERAM_O_CONTROLE):
        return False
    return estado != "aplicado"


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
    aplicadas = [
        str(s)
        for s, estado in secoes.items()
        if str(estado) == "aplicado"
        or (
            str(s).startswith(tuple(_PECAS_CUJO_VALOR_E_O_DADO))
            and not _e_falta(str(s), str(estado))
        )
    ]
    nao_entraram = {
        nome_da_secao_da_ativacao(str(s)): str(estado)
        for s, estado in secoes.items()
        if _e_falta(str(s), str(estado))
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


    # entra em `_build_profile_from_editor` nem no `Profile` do disco — o que


    SEM_NOME_NO_DISCO = "nome não encontrado"

    def _nome_do_appid(self, appid: str) -> str | None:
        """O nome do jogo pelo appid, do catálogo que a completação já leu."""
        mapa = getattr(self, "_nomes_dos_jogos", None)
        if not isinstance(mapa, dict):
            return None
        nome = mapa.get(appid)
        return nome if isinstance(nome, str) and nome.strip() else None


    # perfil na hora (profile.switch sem confirmação), atropelando edição em
    # andamento (selecionar texto/navegar vira 2 cliques rápidos por


    # LEITURA de 250 ms, e o `profile.switch` não cabe nele. Trocar só o texto,


    def _prioridade_acima_dos_catch_all(self) -> int:
        """Prioridade que vence TODO perfil "vale sempre" hoje em disco."""
        cache: list[Profile] = getattr(self, "_profiles_cache", None) or []
        tetos = [p.priority for p in cache if p.e_catch_all]
        base = max(tetos) if tetos else 0
        return max(0, min(PRIORIDADE_MAXIMA, base + _FOLGA_ACIMA_DO_CATCH_ALL))


    def _toast_profile(self, msg: str) -> None:
        self._status_toast("profiles", msg)


#     relê o perfil ATIVO — IPC `state_full` +   |  não lê disco nenhum
#    ativo lá é `rodape._draft_do_ativo`, que monta o `DraftConfig` do disco na
# pronto é `rodape._draft_do_ativo` — não o carregador da janela. O original
