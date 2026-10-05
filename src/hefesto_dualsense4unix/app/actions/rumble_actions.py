"""Aba Rumble: intensidade global (Economia/Balanceado/Máximo/Auto) + Testar motores.

FEAT-RUMBLE-POLICY-01: aba reestruturada em 2 cards:
  1. "Intensidade da vibração" — 4 GtkToggleButton agrupados + slider + label Auto.
  2. "Testar motores" — sliders de vibração leve/forte + botões Testar/Aplicar/Parar.

LEIGO-06: "política", "rumble", "weak"/"strong" e "throttle" saíram da TELA —
continuam sendo os nomes do IPC e do schema (`rumble.policy`, `policy="max"`),
que este módulo traduz na fronteira.

Política define multiplicador global aplicado pelo daemon sobre todo rumble,
inclusive passthrough de jogo (XInput virtual). Slider de intensidade ajusta
"custom" em 0-200% (mapeamento valor/100 nos dois sentidos).

HARM-19: o teto tem UM dono — ``profiles.schema.RUMBLE_CUSTOM_MULT_MAX``. Eram
três (2.0 no schema, 1.0 no handler ``rumble.policy_custom``, 200% no slider), e
de 101% em diante a usuária levava um erro de validação que esta aba nem
mostrava. Mexeu no teto? Mexa no schema — este slider é ``mult * 100``.

FEAT-RUMBLE-POLICY-PROFILE-01: cada escolha de política da usuária também é
gravada em ``self.draft.rumble`` — o "Salvar Perfil" do rodapé persiste no
perfil exatamente o que a aba mostra (aplicada de volta na ativação).
"""
# ruff: noqa: E402
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app.alvo_de_edicao import (
    AlvoDeEdicao,
    EstadoDoAlvo,
)
from hefesto_dualsense4unix.daemon.subsystems.rumble import (
    RUMBLE_POLICY_MULT,
    sem_dono_do_rumble,
)

_POLICY_MULT: dict[str, float] = {
    **RUMBLE_POLICY_MULT,
    "auto": 1.0,
}


_POLICY_LABEL: dict[str, str] = {
    "economia": "Economia",
    "balanceado": "Padrão",
    "max": "Máximo",
    "auto": "Auto",
}

ROTULOS_DO_ORCAMENTO: dict[str, str] = dict(_POLICY_LABEL)


_ALCANCE_O_QUE_ACONTECE = "A intensidade não está chegando a jogo nenhum: "

_ALCANCE_O_QUE_SOBRA = " Aqui embaixo ela ainda vale."

#: A única causa que sobra do aviso: com a emulação ligada e nenhum gamepad
#: virtual, o jogo ainda enxerga o físico. O sujeito é o sistema, não o Hefesto
#: (a régua é `scripts/check_a_tela_nao_confessa.py`). A Navegação saiu daqui em
#: `D-2909-A-NAVEGACAO-NAO-E-AVISO-NA-VIBRACAO`: lá nenhum jogo recebe gamepad
#: por decisão dela (`D-1409`), e a intensidade guardada vale quando ele chega.
_CAUSA_O_GAMEPAD_VIRTUAL_NAO_SUBIU = (
    "o Status já está em “Ligado”, e o sistema não deixou o Hefesto criar o "
    "gamepad virtual."
)


def _emulacao_ligada(state: dict[str, Any]) -> bool | None:
    """``gamepad_emulation.enabled`` do ``state_full``, ou ``None`` se não veio.

    É o mesmo campo que ``mode_of_state`` lê: a tela não ganha um segundo leitor
    da pergunta «a emulação está ligada?». Daemon velho, sem o bloco: «não sei».
    """
    bloco = state.get("gamepad_emulation")
    if not isinstance(bloco, dict) or "enabled" not in bloco:
        return None
    return bool(bloco["enabled"])


def texto_do_alcance_da_intensidade(state: dict[str, Any]) -> str | None:
    """O aviso de que a intensidade escolhida NÃO chega à vibração dos jogos.

    ``None`` = ela chega, ou não se sabe, ou não há o que ajustar — e nos três
    casos a linha não aparece.

    **Quem decide o quadrante não é esta função**, é
    ``daemon.subsystems.rumble.sem_dono_do_rumble``, o mesmo predicado do
    ``rumble_sem_dono`` do journal: dois critérios para o mesmo buraco divergem
    na primeira mudança. O ``state_full`` manda a CONTAGEM de gamepads virtuais;
    como o predicado só olha a verdade da sequência, a tradução é feita aqui.

    A ordem das perguntas:

    1. **O dado veio?** ``rumble_ff`` ausente, ``vpads`` que não é inteiro, ou
       ``gamepad_emulation`` ausente (daemon mais velho): silêncio. Afirmar
       «não alcança» com o campo ausente seria inventar um defeito;
    2. **Emulação ligada e nenhum gamepad virtual?** É a falha do sistema
       (VPAD-09): o jogo ainda vê o físico e a intensidade não passa. É a única
       frase de defeito. **Na Navegação não há aviso** (emulação desligada,
       ``D-2909-A-NAVEGACAO-NAO-E-AVISO-NA-VIBRACAO``): nenhum jogo recebe
       gamepad ali, por decisão dela (``D-1409``), e a intensidade fica
       guardada e vale no primeiro pedido de um jogo com gamepad;
    3. **Conexão Nativa (Sony) sem gamepad virtual?** A intensidade também não
       alcança, mas é o modo funcionando como deve: a frase não manda consertar
       nada;
    4. **Sobrou.** Há gamepad virtual e a intensidade alcança: nada a dizer.

    A frase do defeito termina dizendo o que a intensidade AINDA faz: vale para
    a vibração fixada em «Testar agora», pelo ``reassert_rumble``. Sem essa
    metade, o aviso viraria «esta parte da tela não serve para nada», que é
    falso. Ela cabe em UMA sublinha da ``.vib-estado`` (961 px de 1119 em
    17/09): uma segunda sublinha faz o quadro rolar e CORTA o fim do aviso, que
    foi o defeito de 02/09 que a fez mandar encurtar.
    """
    ff = state.get("rumble_ff")
    if not isinstance(ff, dict):
        return None
    vpads = ff.get("vpads")
    if not isinstance(vpads, int) or isinstance(vpads, bool):
        return None
    native = bool(state.get("native_mode"))
    emulacao = _emulacao_ligada(state)
    backends = ("vpad",) * max(0, vpads)
    if emulacao is not None and sem_dono_do_rumble(
        native=native, backends=backends, emulacao=emulacao
    ):
        return (
            _ALCANCE_O_QUE_ACONTECE
            + _CAUSA_O_GAMEPAD_VIRTUAL_NAO_SUBIU
            + _ALCANCE_O_QUE_SOBRA
        )
    if vpads == 0 and native:
        return (
            "Conexão Nativa (Sony): o jogo fala direto com o controle, e a "
            "intensidade acima não passa por ele. Enquanto o modo estiver "
            "ligado, fixar vibração aqui embaixo também não chega ao motor — "
            "quem manda nele é o jogo."
        )
    return None


def texto_do_teto_do_orcamento(
    pedido: float | None, orcamento: str | None
) -> str | None:
    """A linha *"150% · limitado a 30% pelo orçamento"*, ou ``None``.

    CONFIG-05 (22/08/2026), e ela é a metade visível da invariante **teto, não
    troca**: o orçamento CALCULA, a aba de origem só EXIBE. Nada aqui reescreve
    a escolha dela — os quatro botões seguem afundando onde ela os pôs, o
    deslizador segue mostrando o número que ela escolheu, e voltar o orçamento
    para Balanceado devolve tudo sem um clique a mais. Espelhar estado entre
    abas é a classe de defeito que a `ABAS-01` curou, e esta linha é o formato
    que não a repete.

    ``None`` = **a linha não aparece**, e são quatro os silêncios, na ordem em
    que a função pergunta. A disciplina é a do
    :func:`texto_do_alcance_da_intensidade` acima, palavra por palavra: *"não
    sei" e "não chega" mandam caçar em lugares opostos*.

    1. **Ninguém declarou orçamento** (``orcamento is None``). Afirmar um teto
       aqui seria inventar um limite que o daemon não impõe.
    2. **O orçamento não impõe teto** — ``balanceado``, ``max``, e também o
       ``auto``, cujo teto é MÓVEL: ele muda a cada tique com a bateria, e a
       casa já decidiu não prometer número móvel na tela
       (`profiles/manager.py:1818-1820`). Um "limitado a 70%" que vira 30% no
       minuto seguinte ensina a desconfiar da tela inteira.
    3. **Não se sabe o que a aba está pedindo** (``pedido is None``): política
       fora dos degraus conhecidos, deslizador ainda não lido.
    4. **O teto não morde** (``pedido <= teto``): o número que a aba mostra é
       exatamente o que chega ao controle, e dizer "limitado" seria falso.

    O percentual do teto sai de :func:`core.rumble.teto_do_orcamento`, que o
    deriva de ``RUMBLE_POLICY_MULT``. Esta aba não recalcula degrau nenhum: a
    única cópia autorizada em ``app/`` é o ``_POLICY_MULT`` do topo deste
    arquivo, e há teste que vigia isso por grep.
    """
    from hefesto_dualsense4unix.core.rumble import teto_do_orcamento

    if pedido is None:
        return None
    teto = teto_do_orcamento(orcamento)
    if teto is None or pedido <= teto:
        return None
    return (
        f"{round(pedido * 100)}% · limitado a {round(teto * 100)}% pelo orçamento"
    )


TEXTO_ONDE_GRAVA_E_ONDE_MANDA = (
    "Com um controle escolhido: a intensidade acima vale agora para todos os "
    "controles ligados — só o que você salvar no perfil fica deste controle."
)


def texto_de_onde_grava_e_onde_manda(alvo: AlvoDeEdicao) -> str | None:
    """O aviso de alcance do GESTO; ``None`` = não há divergência a confessar."""
    if alvo.estado is EstadoDoAlvo.CONTROLE:
        return TEXTO_ONDE_GRAVA_E_ONDE_MANDA
    return None


def _inteiro(valor: Any) -> int | None:
    """O inteiro do payload, ou ``None`` quando o campo não veio (daemon velho)."""
    if isinstance(valor, int) and not isinstance(valor, bool):
        return valor
    return None


