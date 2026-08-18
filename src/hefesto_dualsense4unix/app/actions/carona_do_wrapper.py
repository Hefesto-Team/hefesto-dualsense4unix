"""A carona: salvar ou aplicar um perfil repõe o wrapper que a Steam comeu.

CARONA-DO-WRAPPER-01 — 16/08/2026, e o DESENHO É DELA.

O PEDIDO, textual
-----------------
*"nem precisa ter um botão na gui, mas ele se auto corrigir ao clicarmos em
aplicar ou salvar o perfil seja dentro ou fora da guia de perfis."*

Eu ia propor um botão. O desenho dela é melhor, e a razão é curta: **um botão
novo é mais uma coisa para lembrar de apertar**, e quem não souber que precisa
apertar continua quebrado. A correção passa a ser EFEITO COLATERAL do gesto que
já existe.

O DEFEITO QUE ISTO CURA (SENTINELA-WRAPPER-01, medido ao vivo em 16/08 02h30)
-----------------------------------------------------------------------------
A Steam guarda **uma** linha de `LaunchOptions` por jogo. Qualquer coisa
escrita nela — uma variável de vídeo, um mod, a própria pessoa — SUBSTITUI a
chamada do `hefesto-launch`, em silêncio. Sem o wrapper, o `launch_env` que o
daemon materializa nunca é lido, e vence a lista de IGNORE da própria Steam —
que contém ``0x054c/0x0df2``, o PID do NOSSO vpad. O jogo é instruído a ignorar
o controle que nós criamos para ele.

O sintoma, nas palavras dela: *"parou de ser reconhecido no jogo, mas o perfil
segue ativo no controle com tudo funcionando só não sendo reconhecido"*.
Funciona no cabo, quebra no rádio, e SÓ o jogo não enxerga.

A cura (`integrations/sentinela_do_wrapper`) foi entregue às 04h com 19 testes
— e ninguém a chamava. `grep sentinela_do_wrapper app/` devolvia ZERO. É o
defeito que o `CLAUDE.md` nomeia como o mais caro desta casa: *a cura escrita e
nunca ligada*. Este módulo é o fio que faltava.

O CENSO DOS GESTOS, e por que estes cinco
-----------------------------------------
Ela disse "aplicar ou salvar o perfil, **seja dentro ou fora da guia de
perfis**". Todo gesto do produto que aplica ou grava um PERFIL, e o que foi
feito de cada um. (Os "Aplicar" de rumble, lightbar e gatilhos não entram: são
o gesto de uma feature, não o de um perfil.)

===============================================  ========  ================
gesto                                            carona?   onde
===============================================  ========  ================
"Salvar este perfil" (aba Perfis)                SIM       profiles_actions
"Ativar" (aba Perfis)                            SIM       profiles_actions
"Salvar Perfil" (rodapé, fora da aba)            SIM       profile_writer
"Importar perfil" (rodapé)                       SIM       profile_writer
"Restaurar Padrão" (rodapé)                      SIM       profile_writer
"Aplicar" — o botão verde do rodapé              SIM       footer_actions
trocar de perfil pela BANDEJA                    SIM       app.py
trocar de perfil pela janela compacta            SIM       app.py
"Aplicar aos jogos da Steam" (aba Sistema)       não       (ver abaixo)
AUTOSWITCH — o daemon aplica sozinho             não       (ver abaixo)
===============================================  ========  ================

O card do controle NÃO aparece na tabela porque ele não tem gesto de perfil
nenhum: `grep -i 'switch\\|ativa' widgets/controller_card.py` não devolve nada
de perfil. O que o card aplica é som, mic e ponte BT.

A BANDEJA e a janela compacta saem do MESMO ``on_switch_profile`` do
``app.py``, e são o "fora da guia de perfis" que fica MAIS longe da guia: é o
caminho de quem nem abriu a janela. Entram por
``HefestoApp._trocar_perfil_de_fora``, sabendo que ali não há rodapé
garantido — a janela principal pode nem estar montada. Isso custa a FRASE,
nunca o REPARO, e reparar calado é melhor que não reparar.

Os dois de fora, cada um com o motivo:

- **"Aplicar aos jogos da Steam"** (`daemon_actions.on_steam_apply_launch`) já
  É a aplicação em massa, e tem uma máquina que a sentinela não tem: pedir
  consentimento para FECHAR a Steam por uns 20 segundos e reabrir. Trocá-lo por
  `reparar_ou_adiar` REMOVERIA essa capacidade — seria regressão, não carona.
  A única lacuna dele (não alimentar o `wrapper-visto.json`, a memória que
  separa "perdeu" de "nunca teve") fecha sozinha com a carona: o próximo
  salvar/aplicar roda `censo_do_wrapper(anotar=True)`, que anota todo mundo que
  está com o wrapper.
- **AUTOSWITCH** é o mais interessante e o mais perigoso, e por isso fica de
  fora: ele aplica perfil exatamente quando o JOGO ESTÁ SUBINDO. Nesse
  instante a Steam está viva e um jogo está aberto — as duas condições em que
  escrever no `localconfig.vdf` é jogar o reparo fora (a Steam regrava o
  arquivo ao sair; aconteceu em 16/08 e o reparo foi desfeito). Além disso ele
  roda no DAEMON (`daemon/subsystems/`, poll de 2 Hz enquanto o jogo está em
  foco), que não tem rodapé. Não é só inútil: a 2 Hz seria uma varredura do
  `localconfig.vdf` duas vezes por segundo durante a partida inteira, para
  cair sempre em ``adiado_jogo_aberto``. Garantidamente inútil, e caro.

O QUE A CARONA REPARA: a biblioteca INTEIRA, e só quando há o que reparar
-------------------------------------------------------------------------
O gesto dela é sobre UM perfil; o defeito é da biblioteca inteira. As três
opções estavam na mesa e a escolhida é a terceira:

(a) **reparar só o jogo daquele perfil** — recusada por três razões, e a
    primeira sozinha já basta: a maioria dos perfis **não tem appid nenhum**
    (regra de janela, `MatchAny`, "só manual"), então na maior parte dos
    gestos não haveria jogo a reparar. A segunda: consertar um jogo e deixar os
    outros cinquenta e nove quebrados, sem dizer nada, é pior que não
    consertar — ela sairia da janela achando que está tudo bem. A terceira: não
    existe hoje um reparo cirúrgico por appid, e inventar um segundo caminho de
    escrita no vdf quebraria a idempotência que segura os 60 jogos.
(b) **reparar a biblioteca inteira, sempre** — é o alvo certo, mas "sempre"
    faria uma varredura de disco e duas escritas a cada clique em Salvar, que é
    o gesto mais comum da janela.
(c) **reparar tudo, mas só quando houver o que reparar** — o escolhido, e é o
    que `reparar_ou_adiar` já faz por construção: ele começa pelo censo e
    devolve ``nada_a_fazer`` sem tocar em disco quando todo jogo elegível tem o
    wrapper. Em regime, portanto, o custo da carona é **uma leitura de arquivo
    e zero escritas**. Só o dia em que a Steam comer uma linha custa mais.

E reparar TAMBÉM os jogos que nunca tiveram o wrapper (motivo ``novo``, e não
só a ``regressao``) não é excesso: é a regra da casa escrita em duas linhas do
`CLAUDE.md` — *universal, nada por appid cravado, jogo instalado amanhã nasce
coberto*. É exatamente o que o passo sem flag do `install.sh` já faz.

A STEAM ABERTA, que é a restrição dura
--------------------------------------
Reparar com a Steam viva é jogar fora o reparo. `reparar_ou_adiar` já sabe
adiar (``adiado_steam_aberta`` / ``adiado_jogo_aberto``). A pergunta que sobra
é o que fazer com o adiamento, e a resposta tem de valer para o pedido dela:
**ela não pode precisar lembrar de nada.** Então são as duas coisas:

1. **avisa na hora**, uma vez (a frase da sentinela já nomeia o jogo e já diz
   o que vai acontecer: *"Vou repor assim que o jogo e a Steam fecharem"*);
2. **arma uma vigia** — um tique de :data:`INTERVALO_DA_VIGIA_S` segundos que
   refaz a passada até ela deixar de ser adiada. Quando ela fecha a Steam, o
   reparo simplesmente ACONTECE.

A vigia guarda a intenção **em memória, nunca em disco** — e isso é a decisão
da sentinela, não uma economia: *"estado guardado sobre um vdf que muda sozinho
envelheceria errado"*. Se a janela fechar antes, nada se perde: o censo é uma
leitura de arquivo, então o próximo gesto (ou o `install.sh`, ou o
`doctor.sh`) refaz a conta do zero.

A vigia é barata de propósito. O tique NÃO relê o vdf: ele só pergunta se a
Steam ainda está viva (:func:`passada` com ``completa=False``) e volta a
dormir. A leitura completa só acontece quando há chance real de escrever.

O QUE ELA VÊ
------------
Silêncio total é ruim — ela não saberia que foi consertada. Diálogo a cada
Salvar é pior — vira ruído no gesto mais comum da janela, e o pedido dela
começa justamente recusando mais um clique. O meio é **uma linha no rodapé, e
só quando há notícia**:

- nada faltando (o caso comum) → **silêncio absoluto**, nenhum widget tocado;
- reparado → uma linha dizendo em QUAIS jogos, pelo nome;
- adiado → a frase da sentinela, **uma vez por episódio**: enquanto o conjunto
  de jogos faltantes não mudar, salvar de novo não repete o aviso.

Nenhum diálogo, em nenhum caminho. A carona nunca interrompe o gesto dela.

THREAD, e por que não o executor compartilhado
----------------------------------------------
Tudo o que toca disco ou pergunta ao `/proc` corre numa thread própria, e a
frase que vai para a tela é MONTADA LÁ (o nome do jogo sai de um
`appmanifest`). O executor de `ipc_bridge` tem UM worker só e é o mesmo que
serve `profile.switch`; `steam_running()` forka dois `pgrep` com teto de 5 s
cada, e prender esse worker por até dez segundos atrasaria a ativação de perfil
dela. Uma thread dedicada custa menos que esse acoplamento.

O DESLIGADOR, e por que ele existe
----------------------------------
:data:`CARONA_ENV` desliga a carona. Ele NÃO é uma flag de produto — a regra da
casa é *toda cura entra no install, sem flag*, e em produção a carona está
sempre ligada. Ele existe pela mesma razão do `HEFESTO_BROKER_SOCKET` no
`conftest.py`: a suíte roda na máquina DELA, e um teste de GUI que chamasse
"Salvar" com a carona ligada varreria o `localconfig.vdf` REAL e poderia
escrever nele. O `conftest.py` desliga em todo teste; quem quer exercitar a
carona religa explicitamente, com fixtures.
"""
from __future__ import annotations

import contextlib
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Desliga a carona quando o valor está em :data:`VALORES_DESLIGADOS`.
#: Ausente = LIGADA. Ver "O DESLIGADOR" na docstring do módulo: é isolamento
#: de suíte, não flag de produto.
CARONA_ENV = "HEFESTO_CARONA_WRAPPER"

#: O que conta como "desligado" numa variável de ambiente. A forma SEM acento
#: está aqui de propósito: ninguém digita til numa linha de `env`, e recusar
#: a forma crua deixaria a pessoa achando que desligou sem ter desligado.
VALORES_DESLIGADOS = frozenset(
    {"0", "off", "false", "no", "não", "nao"}  # (noqa-acento): valor de ambiente
)

#: De quanto em quanto tempo a vigia repergunta "a Steam já fechou?".
#: 45 s é o compromisso: curto o bastante para o reparo parecer imediato depois
#: de ela sair da Steam, longo o bastante para o tique custar menos que o
#: poller de 2 Hz que a janela já tem. O tique NÃO lê o vdf.
INTERVALO_DA_VIGIA_S = 45

#: Contexto da statusbar quando a janela não tem nenhum `_toast_*` montado.
CONTEXTO_DA_BARRA = "carona_wrapper"

#: Rótulos de gesto — só entram no log, para o journal dizer QUEM pegou carona.
GESTO_SALVAR = "salvar_perfil"
GESTO_APLICAR = "aplicar_perfil"
GESTO_VIGIA = "vigia_da_steam"

#: Status extra desta camada: a vigia perguntou pela Steam e nem abriu o vdf.
#: Nome próprio (em vez de reusar ``adiado_steam_aberta``) porque as duas
#: coisas são diferentes: uma viu o censo, a outra não olhou.
ADIADO_SEM_OLHAR = "adiado_sem_olhar"


@dataclass(frozen=True)
class ResultadoDaCarona:
    """O que a passada apurou — já pronto para a tela, montado no worker.

    ``frase`` vazia significa **não diga nada**. É o caso comum, e é de
    propósito: a carona só fala quando tem notícia.
    """

    status: str
    frase: str
    #: AppIDs que continuam sem o wrapper. É a identidade do "episódio": só um
    #: conjunto DIFERENTE volta a falar na tela.
    faltantes: frozenset[str]
    #: True quando ficou trabalho pendente — é o que arma (e mantém) a vigia.
    adiado: bool


def ligada() -> bool:
    """A carona está ligada neste processo? Produção: sempre. Suíte: nunca."""
    bruto = os.environ.get(CARONA_ENV, "").strip().lower()
    return bruto not in VALORES_DESLIGADOS


def despachar(
    trabalho: Callable[[], ResultadoDaCarona],
    ao_terminar: Callable[[ResultadoDaCarona], bool],
) -> None:
    """Roda ``trabalho()`` fora da thread do GTK e devolve na thread do GTK.

    Ponto único de troca de thread da carona — os testes o substituem por uma
    versão síncrona, do mesmo jeito que a suíte já faz com
    ``ipc_bridge.run_in_thread``. Uma thread própria (e não o executor de um
    worker do `ipc_bridge`): ver "THREAD" na docstring do módulo.
    """

    def _corpo() -> None:
        try:
            resultado = trabalho()
        except Exception as exc:  # nunca deixa a thread morrer calada
            logger.warning("carona_do_wrapper_passada_falhou", erro=str(exc))
            return
        _de_volta_para_o_gtk(ao_terminar, resultado)

    threading.Thread(
        target=_corpo, name="hefesto-carona-wrapper", daemon=True
    ).start()


def _de_volta_para_o_gtk(
    fn: Callable[[ResultadoDaCarona], bool], resultado: ResultadoDaCarona
) -> None:
    """``GLib.idle_add`` quando há GTK; chamada direta quando não há."""
    try:
        from gi.repository import GLib
    except Exception:  # pragma: no cover - sem GTK (dublê de teste)
        fn(resultado)
        return
    GLib.idle_add(fn, resultado)


def passada(*, completa: bool = True) -> ResultadoDaCarona:
    """Uma passada da carona. **Só em thread worker** — lê disco e o `/proc`.

    ``completa=False`` é o tique da vigia: pergunta só pelo estado da Steam e
    desiste barato quando ela ainda está viva, sem abrir o `localconfig.vdf`.
    Com a Steam fechada as duas formas fazem a mesma coisa.

    Nunca levanta pelo caminho normal; erro de leitura vira ``erro`` no censo,
    que a sentinela já sabe reportar sem concluir nada.
    """
    from hefesto_dualsense4unix.integrations import (
        sentinela_do_wrapper as sw,
    )
    from hefesto_dualsense4unix.integrations import (
        steam_launch_options as slo,
    )

    # A pergunta vai ao `steam_launch_options`, que é onde as duas funções
    # NASCEM — a sentinela apenas as reexporta. Mesma função, e o gate fica na
    # ordem canônica: JOGO antes de Steam (fechar a Steam com um jogo aberto
    # mataria o jogo).
    if not completa and (slo.steam_game_running() or slo.steam_running()):
        # Nada a dizer: quem armou a vigia já falou uma vez.
        return ResultadoDaCarona(ADIADO_SEM_OLHAR, "", frozenset(), True)

    status, censo, resultado = sw.reparar_ou_adiar()
    faltantes = frozenset(jogo.appid for jogo in censo.reparaveis)

    if status == sw.REPARO_FEITO:
        appids = [item["appid"] for item in (resultado or {}).get("applied", [])]
        if not appids:
            return ResultadoDaCarona(status, "", frozenset(), False)
        plural = "jogos" if len(appids) > 1 else "jogo"
        frase = (
            f"Reposta a Opção de Inicialização do Hefesto em {len(appids)} "
            f"{plural} da Steam: {slo.lista_de_jogos(appids)}. Sem ela, no "
            "Bluetooth o jogo tende a não enxergar controle nenhum. As opções "
            "que você já tinha na linha foram preservadas."
        )
        return ResultadoDaCarona(status, frase, frozenset(), False)

    if status in (sw.REPARO_ADIADO_JOGO, sw.REPARO_ADIADO_STEAM):
        # A frase da sentinela já nomeia o jogo E já diz o que vai acontecer
        # ("vou repor assim que…") — que é exatamente o contrato da vigia.
        return ResultadoDaCarona(status, sw.frase_do_aviso(censo), faltantes, True)

    if status == sw.REPARO_ERRO:
        motivos = ", ".join(
            sorted({item.get("reason", "") for item in (resultado or {}).get("errors", [])})
        )
        frase = (
            "Não consegui repor as Opções de Inicialização do Hefesto na "
            "Steam" + (f" ({motivos})" if motivos else "") + ". Nada foi "
            "perdido — há backup ao lado de cada arquivo tocado."
        )
        return ResultadoDaCarona(status, frase, faltantes, True)

    return ResultadoDaCarona(sw.REPARO_NADA, "", frozenset(), False)


class CaronaDoWrapperMixin(WidgetAccessMixin):
    """Dá a qualquer mixin da janela o gesto que repõe o wrapper de carona.

    Base de ``ProfileWriterMixin`` (e portanto do rodapé inteiro) e de
    ``ProfilesActionsMixin`` (a aba Perfis). Quem grava ou aplica perfil chama
    :meth:`pegar_carona_no_gesto` e mais nada.

    **Este caminho nunca pode derrubar o gesto dela.** Salvar um perfil tem de
    salvar o perfil mesmo que a Steam esteja num estado que ninguém previu —
    por isso cada degrau daqui engole as próprias exceções e as manda para o
    journal, em vez de deixá-las subir para o handler do botão.
    """

    #: Uma passada por vez: duas escritas concorrentes no mesmo vdf seriam a
    #: única forma de esta cura estragar a biblioteca dela.
    _carona_em_curso: bool = False
    #: `source id` da vigia do GLib; ``None`` = desarmada.
    _carona_vigia_id: int | None = None
    #: Episódio já anunciado — o que impede o aviso de repetir a cada Salvar.
    _carona_ja_avisado: frozenset[str] = frozenset()

    # ------------------------------------------------------------------
    # A carona
    # ------------------------------------------------------------------

    def pegar_carona_no_gesto(self, gesto: str = GESTO_SALVAR) -> None:
        """Chamada pelos gestos de SALVAR e APLICAR perfil. Nunca levanta."""
        self._carona_passar(gesto=gesto, completa=True)

    def _carona_passar(self, *, gesto: str, completa: bool) -> None:
        if not ligada():
            return
        if getattr(self, "_carona_em_curso", False):
            logger.debug("carona_do_wrapper_ja_em_curso", gesto=gesto)
            return
        self._carona_em_curso = True
        try:
            despachar(
                lambda: passada(completa=completa), self._carona_ao_terminar
            )
        except Exception as exc:  # não existe gesto que valha uma exceção aqui
            self._carona_em_curso = False
            logger.warning("carona_do_wrapper_despacho_falhou", erro=str(exc))

    def _carona_ao_terminar(self, resultado: ResultadoDaCarona) -> bool:
        """Callback na thread do GTK. Retorna ``False`` (contrato do idle_add)."""
        self._carona_em_curso = False
        try:
            self._carona_reagir(resultado)
        except Exception as exc:
            logger.warning("carona_do_wrapper_reacao_falhou", erro=str(exc))
        return False

    def _carona_reagir(self, resultado: ResultadoDaCarona) -> None:
        """Decide a vigia e a linha do rodapé. Thread do GTK."""
        if resultado.adiado:
            self._carona_armar_vigia()
        else:
            # Nada pendente: o episódio ACABOU, e a memória do aviso vai junto.
            # Zerar aqui (e não lá embaixo, junto do toast) é o que impede um
            # episódio NOVO com os mesmos jogos de nascer calado — o caso é
            # real: ela conserta a linha na mão, o próximo Salvar diz
            # "nada a fazer" (frase vazia, o `return` de baixo), e a Steam come
            # o wrapper de novo na semana seguinte. Com a memória velha ainda
            # de pé, esse segundo episódio seria silencioso.
            self._carona_desarmar_vigia()
            self._carona_ja_avisado = frozenset()
        if not resultado.frase:
            return
        if resultado.adiado and resultado.faltantes == self._carona_ja_avisado:
            return  # mesmo episódio: repetir a cada Salvar viraria ruído
        if resultado.adiado:
            self._carona_ja_avisado = resultado.faltantes
        logger.info(
            "carona_do_wrapper", status=resultado.status, frase=resultado.frase
        )
        self._carona_toast(resultado.frase)

    # ------------------------------------------------------------------
    # A vigia — "ela não precisa lembrar de nada"
    # ------------------------------------------------------------------

    def _carona_armar_vigia(self) -> None:
        """Passa a reperguntar "a Steam já fechou?" até o reparo caber."""
        if getattr(self, "_carona_vigia_id", None) is not None:
            return
        try:
            from gi.repository import GLib
        except Exception:  # pragma: no cover - dublê sem GTK
            return
        with contextlib.suppress(Exception):
            self._carona_vigia_id = GLib.timeout_add_seconds(
                INTERVALO_DA_VIGIA_S, self._carona_tique_da_vigia
            )

    def _carona_tique_da_vigia(self) -> bool:
        """Tique barato: só olha a Steam. Quem desarma é o ``_carona_reagir``."""
        self._carona_passar(gesto=GESTO_VIGIA, completa=False)
        return True

    def _carona_desarmar_vigia(self) -> None:
        vigia: Any = getattr(self, "_carona_vigia_id", None)
        if vigia is None:
            return
        self._carona_vigia_id = None
        with contextlib.suppress(Exception):
            from gi.repository import GLib

            GLib.source_remove(vigia)

    # ------------------------------------------------------------------

    def _carona_toast(self, msg: str) -> None:
        """A linha no rodapé, pelo caminho que o mixin dono já usa.

        Mesma escada do ``_toast_de_gravacao`` do funil: o helper do rodapé
        quando existe (é o que os dublês de teste substituem), o da aba Perfis
        depois, e a statusbar crua como último degrau.
        """
        for nome in ("_footer_toast", "_toast_profile"):
            toast = getattr(self, nome, None)
            if callable(toast):
                toast(msg)
                return
        self._status_toast(CONTEXTO_DA_BARRA, msg)


__all__ = [
    "ADIADO_SEM_OLHAR",
    "CARONA_ENV",
    "CONTEXTO_DA_BARRA",
    "GESTO_APLICAR",
    "GESTO_SALVAR",
    "GESTO_VIGIA",
    "INTERVALO_DA_VIGIA_S",
    "VALORES_DESLIGADOS",
    "CaronaDoWrapperMixin",
    "ResultadoDaCarona",
    "despachar",
    "ligada",
    "passada",
]
