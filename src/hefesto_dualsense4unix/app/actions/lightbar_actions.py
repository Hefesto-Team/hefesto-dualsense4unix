"""Aba Lightbar + Player LEDs."""
# ruff: noqa: E402
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.alvo_de_edicao import AlvoDeEdicao, alvo_de_edicao
from hefesto_dualsense4unix.app.textos_de_aplicacao import (
    alvo_fora_da_mesa,
    coop_manda_nas_luzes,
    frase_de_guardado,
    frase_do_desfecho,
)

_AVISO_HEFESTO_DESLIGADO = (
    "Não consegui aplicar a cor — o Hefesto pode estar desligado "
    "(ligue na aba Sistema)"
)

_TOAST_COR_ENVIADA = "Cor enviada ao controle ({pct}% de brilho)"

_ASSUNTO_COR = "Cor ({pct}% de brilho)"

#: por-MAC do "Aplicar no controle" logo ao lado (`led_set((0, 0, 0),
_TOAST_LIGHTBAR_APAGADA = "Lightbar apagada"
_ASSUNTO_APAGAR = "Apagar a lightbar"


#: escolha do usuário, e estão no §8 da sprint. Enquanto a resposta não vem, o
_AVISO_MESMO_DESENHO_NOS_QUATRO = (
    "O mesmo desenho foi para os {n} controles ligados."
)


def frase_do_envio(
    assunto: str,
    enviado: str,
    corpo: Any,
    host: Any,
    *,
    coop_aplica: bool = False,
) -> str:
    """A frase do gesto decidida pelo CORPO do daemon (BG-01, 26/08/2026).

    **Quem decide é ``textos_de_aplicacao.frase_do_desfecho``, e só ele.** Esta
    função não lê ``aplicado_em``, não conhece a ordem das razões e não tem
    opinião sobre ramo nenhum: ela chama o dono da decisão e, no ramo do
    APLICADO — e só nele —, devolve a frase que esta aba já tinha.

    **Por que a troca de palavra, e por que ela não é preferência.** O ramo do
    aplicado sai de lá como *"<assunto> aplicado"*, e "aplicada" é uma
    afirmação que esta aba MEDIU como falsa: LIGHTBAR-BT-RESET-01 (17-18/07,
    ainda em vigor em 09/08) — por Bluetooth, depois que o daemon adota o
    controle, o firmware ACEITA E IGNORA as escritas de cor; foram 330 mil
    escritas ignoradas com a barra apagada. O que o daemon sabe é que o byte
    saiu no fio, que é exatamente o que "enviada" diz e "aplicada" não. A
    decisão está registrada em ``_TOAST_COR_ENVIADA``, com a medição; trocar a
    palavra aqui seria desfazê-la em silêncio.

    **Se o ramo do aplicado mudar de forma lá, esta função para de reconhecê-lo**
    e a frase de lá aparece na tela com a palavra que esta aba recusa. É um
    acoplamento REAL, e por isso ele tem régua: ``test_a_regua_do_ramo_aplicado``
    em ``tests/unit/test_aplicar_verdade_ponte_lightbar.py`` reprova no dia em
    que as duas formas divergirem, em vez de a divergência sair na tela do usuário.

    ``coop_aplica`` viaja intacto: só quem escreve os 5 LEDs de jogador o passa
    ``True`` (``_COOP_LAYER_FIELDS = ("player_leds",)`` no backend), e a cor da
    lightbar nunca foi governada pelo co-op.

    ``nativo_aplica=False`` SEMPRE, e é a decisão de 23/09/2026
    (`D-2309-NO-NATIVO-A-LUZ-E-O-NUMERO-SAO-DO-HEFESTO`): no Modo Nativo o
    Hefesto escreve a barra e o número, e esta aba só fala dos dois.
    """
    frase = frase_do_desfecho(
        assunto, corpo, host, coop_aplica=coop_aplica, nativo_aplica=False
    )
    return enviado if frase.startswith(f"{assunto} aplicado") else frase


class LightbarActionsMixin(WidgetAccessMixin):
    """Controla a aba Lightbar + Player LEDs."""

    _current_rgb: tuple[int, int, int] = (255, 128, 0)
    _current_brightness: float = 1.0
    _pending_brightness: float = 1.0
    _refresh_guard: bool = False
    _brilho_pendente: bool = False
    _soltar_fiado: bool = False

    def _uniqs_conectados(self) -> list[str]:
        """MACs dos controles CONECTADOS, na ordem do índice (R-14).

        Fonte: ``_target_uniq_by_index``, o mapa que a aba Status recalcula do
        ``state_full`` a cada tick (só controles conectados entram). Controle
        sem MAC estável (handle por path) fica de fora — para ele não existe
        override por-controle, e a escrita dele continua sendo a global.

        Lista vazia = a GUI ainda não sabe quem está na mesa (nenhum tick do
        daemon, host parcial de teste). Os chamadores tratam isso como
        "escopo desconhecido" e caem no caminho global de sempre, nunca em
        broadcast disfarçado de por-controle.
        """
        mapa = getattr(self, "_target_uniq_by_index", None)
        if not isinstance(mapa, dict):
            return []
        vistos: set[str] = set()
        saida: list[str] = []
        for _idx, uniq in sorted(mapa.items(), key=lambda kv: kv[0]):
            if isinstance(uniq, str) and uniq and uniq not in vistos:
                vistos.add(uniq)
                saida.append(uniq)
        return saida

    def _edit_uniq(self) -> AlvoDeEdicao:
        """O alvo de edição (PERFIL-04), com o estado explícito ao lado do MAC."""
        return alvo_de_edicao(self)


    def _msg_do_desenho(
        self,
        *,
        ok: bool,
        motivo: str | None,
        corpo: dict[str, Any] | None,
        descricao: str,
        feito: str,
        fazer: str,
    ) -> str:
        """A frase do desenho das 5 luzes — UMA, para os três gestos."""
        if not ok:
            return motivo or (
                f"Não consegui {fazer} o desenho das luzes — o Hefesto pode "
                "estar desligado (ligue na aba Sistema)"
            )
        assunto = f"Desenho das luzes ({descricao})"
        enviado = f"Desenho das luzes {feito} — {descricao}"
        if coop_manda_nas_luzes(self):
            frase = frase_de_guardado(
                assunto,
                alvo_ausente=alvo_fora_da_mesa(self),
                coop=True,
            ) or enviado
        else:
            frase = frase_do_envio(assunto, enviado, corpo, self, coop_aplica=True)
        quantos = self._quantos_recebem_o_desenho()
        if quantos >= 2:
            frase = f"{frase} {_AVISO_MESMO_DESENHO_NOS_QUATRO.format(n=quantos)}"
        return frase

    def _quantos_recebem_o_desenho(self) -> int:
        """Quantos controles um clique de desenho atinge; 0 se for um só (L12)."""
        estado_alvo = self._edit_uniq()
        if estado_alvo.desconhecido or estado_alvo.uniq is not None:
            return 0
        return len(self._uniqs_conectados())

    @staticmethod
    def _descreve_player_leds(bits: list[bool] | tuple[bool, ...]) -> str:
        """Padrão dos LEDs de jogador em palavras (LB-03)."""
        acesos = [str(i) for i, ligado in enumerate(bits, start=1) if ligado]
        if not acesos:
            return "todos os LEDs apagados"
        if len(acesos) == 1:
            return f"LED aceso: {acesos[0]}"
        return "LEDs acesos: " + ", ".join(acesos[:-1]) + " e " + acesos[-1]


    def _toast_light(self, msg: str) -> None:
        self._status_toast("light", msg)
