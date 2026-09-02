#!/usr/bin/env python3
"""O pacote da aba `07` Lançadores — a aba que era desenho inteiro.

A DECISÃO DELA QUE ABRIU ESTA ABA, e ela CADUCOU outra, de um dia antes:

    01/09/2026 — *"a única que não faremos, só deixamos o botão levando pra
    ela, é a de lançadores."*

    02/09/2026 — *"não daria para incluir G e F aqui? (…) temos um mapa
    funcional disso no gtk. a estrutura sim, validar de fato eu poderia
    somente juntos com ele."*   <!-- noqa-acento: citação literal dela -->

A `F` é esta aba (`docs/process/sprints/2026-09-02-ROTA-F-a-aba-lancadores.md`).
A segunda decisão vale, e ela traz a razão: **o GTK tem o mapa funcional** —
`sentinela_do_wrapper`, `prontuario_dos_jogos`, `carona_do_wrapper` e
`launch_wrapper_dialog` já sabiam responder o que esta tela pergunta. A primeira
fica registrada com data nas duas réguas que a codificavam
(`test_o_despachante_serve_as_dez.py`, `test_o_casamento_das_dez.py`): não se
apaga decisão medida, e a nota é o que impede a próxima pessoa de reabrir.

O QUE ESTA ABA AFIRMAVA, E O QUE O PRODUTO RESPONDE
---------------------------------------------------
Medido em 02/09/2026 na máquina dela, com `censo_do_wrapper(anotar=False)` e
`prontuario_dos_jogos.levantar_censo` — leitura pura, nada escrito:

    o HTML afirmava                  o produto responde
    ------------------------------   -------------------------------------------
    Steam · 412 jogos                23 jogos INSTALADOS; 63 appids com o
                                     wrapper na linha do `localconfig.vdf`
    ◆ 3 jogos já sabem por onde      0 pontes confirmadas
    5 encontrados · 1 impedimento    1 lançador medível, 0 impedidos
    Heroic · 28 jogos · NÃO CHEGAM   o produto não tem UMA função que olhe o
                                     Heroic — as menções são COMENTÁRIO

Quatro afirmações, quatro contradições. **A cura não é apagar o desenho** — é
dar-lhe fonte, e dizer `NÃO SEI` onde não há fonte. Um selo `CHEGAM` sobre um
lançador que ninguém olhou é a `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` na cor verde.

NADA SE REESCREVE — o que este arquivo NÃO faz
----------------------------------------------
Nenhuma linha daqui decide se um jogo tem o wrapper, nem repõe o wrapper, nem
nomeia um impedimento. Quem faz é o motor, e cada função tem endereço:

    integrations/sentinela_do_wrapper.censo_do_wrapper   quem tem e quem não tem
    integrations/sentinela_do_wrapper.reparar_ou_adiar   o reparo, com os portões
    integrations/sentinela_do_wrapper.frase_do_aviso     a frase que vai à TELA
    integrations/steam_launch_options.rotulo_do_jogo     o nome, do `appmanifest`
    integrations/steam_launch_options.marcar_jogo_sem_wrapper    o "tirar daqui"
    integrations/steam_launch_options.desmarcar_jogo_sem_wrapper o "voltar a usar"
    integrations/steam_launch_options.steam_game_running_appid   o jogo em foco
    integrations/prontuario_dos_jogos.levantar_censo     os cinco impedimentos
    integrations/prontuario_dos_jogos.jogos_instalados   os `appmanifest` do disco

`carona_do_wrapper.passada()` responderia parte disto — mas ela ESCREVE no
`localconfig.vdf` quando há o que repor, e uma PINTURA que escreve em disco a
cada tique é a coisa mais perigosa que esta aba poderia fazer. A pintura usa o
CENSO (read-only, seguro com a Steam aberta — e é por isso que ele é uma camada
separada do reparo); só o gesto "Consertar" chama o caminho que escreve.

O DESENHO dos cartões mora em `interface/desenho_dos_lancadores.py`, e é o MESMO
que o gerador `aba07.py` usa. Um dono, dois dados — é o que impede o número
digitado de voltar: não há onde digitá-lo.

O CUSTO, E POR QUE O DISCO NÃO ENTRA NO TIQUE
----------------------------------------------
Medido em 02/09/2026, na máquina dela:

    censo_do_wrapper()          26 ms (85 ms na primeira)
    jogos_instalados()          12 ms
    levantar_censo()        13.440 ms   <- treze segundos e meio

O tique do piloto é de 500 ms. Ler 40 ms de disco a cada tique seria 8% do
orçamento gasto relendo um arquivo que muda uma vez por semana; o prontuário
sequer cabe. Por isso a leitura vive na :class:`_Vigia`: a pintura NUNCA
bloqueia, uma thread refaz a conta quando ela passa de :data:`TTL_S`, e o
prontuário só sai do lugar quando ela clica em "Ver o que impede".
"""
from __future__ import annotations

import threading
import time
from typing import Any

from hefesto_dualsense4unix.interface import desenho_dos_lancadores as desenho

from . import Contexto, registrar

#: De quanto em quanto tempo a vigia repergunta ao disco. 20 s é o compromisso:
#: a linha de inicialização só muda quando a Steam a regrava (ao sair) ou quando
#: ela clica em Consertar — e o gesto invalida o cache na hora, então o TTL não
#: precisa ser curto para a tela parecer viva.
TTL_S = 20.0

SEM_DONO: dict[str, str] = {
    "abrir-lancador": "abrir a Steam (ou qualquer lançador) é `xdg-open`, não "
                      "IPC — o daemon não tem método para isso, e um botão que "
                      "responde calado é pior que um que recusa",
    "criar-perfil": "criar perfil é da aba Perfis (`a10_perfis`); dois caminhos "
                    "para o mesmo disco é como duas telas passam a discordar",
    "heroic": "o produto não tem UMA função que olhe o Heroic, o Lutris, o "
              "RetroArch, o Dolphin ou o mGBA — as cinco menções em `src/` são "
              "comentário, e por isso os cartões deles dizem NÃO SEI",
}


# ---------------------------------------------------------------------------
# A VIGIA — o disco fica FORA do tique
# ---------------------------------------------------------------------------
class _Vigia:
    """Guarda a última leitura do disco e a refaz FORA da thread da janela.

    O CONTRATO É "NUNCA BLOQUEIE": :meth:`agora` devolve o que tem — ``None`` na
    primeira volta — e dispara a releitura quando o dado passou do TTL. Quem
    precisa do valor de verdade (um gesto, uma régua) chama :meth:`ler`, que
    bloqueia; os gestos já rodam em thread (`hefesto_vivo._gesto`).

    UMA LEITURA POR VEZ: duas varreduras concorrentes do mesmo
    `localconfig.vdf` não corrompem nada (o censo é read-only), mas dobrariam o
    I/O sem dar resposta mais nova — é o mesmo cuidado do
    `carona_do_wrapper._carona_em_curso`, pelo mesmo motivo.
    """

    def __init__(self) -> None:
        self._dado: desenho.Leitura | None = None
        self._quando = 0.0
        self._em_curso = False
        self._trava = threading.Lock()

    def agora(self) -> desenho.Leitura | None:
        """O que se sabe AGORA. Nunca bloqueia, nunca levanta."""
        if self._precisa():
            self._disparar()
        return self._dado

    def _precisa(self) -> bool:
        return not self._em_curso and (
            self._dado is None or (time.monotonic() - self._quando) > TTL_S
        )

    def _disparar(self) -> None:
        with self._trava:
            if self._em_curso:
                return
            self._em_curso = True
        threading.Thread(
            target=self._corpo, name="hefesto-lancadores", daemon=True
        ).start()

    def _corpo(self) -> None:
        try:
            self.ler()
        except Exception:
            # Uma leitura que levanta não pode deixar a vigia travada em
            # `_em_curso` para sempre — a aba pararia de se atualizar em
            # silêncio, que é o defeito desta casa com nome.
            pass
        finally:
            self._em_curso = False

    def esquecer(self) -> None:
        """Invalida o cache. É o que o "Procurar de novo" faz de verdade."""
        self._quando = 0.0

    def ler(self) -> desenho.Leitura:
        """BLOQUEIA — lê o disco. Só de thread worker, nunca do tique."""
        dado = _ler_do_disco()
        self._dado = dado
        self._quando = time.monotonic()
        return dado


#: A vigia é do MÓDULO, e não do `Contexto`: o pacote é recriado a cada tique, e
#: um cache dentro dele releria o disco duas vezes por segundo — que é
#: exatamente o que esta classe existe para impedir.
VIGIA = _Vigia()


def _porque(motivo: str) -> str:
    """O motivo do censo em português de tela. As CHAVES saem do motor.

    Digitar `"regressao"` aqui seria a segunda cópia de um fato que já tem dono
    em `sentinela_do_wrapper` — e a cópia envelheceria calada no dia em que o
    nome mudasse lá.
    """
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw

    return {
        sw.MOTIVO_REGRESSAO: "tinha o atalho e perdeu",
        sw.MOTIVO_NOVO: "nunca recebeu o atalho",
        sw.MOTIVO_ESTENDIDO: "linha editada à mão — não vou tocar",
    }.get(motivo, motivo)


def _ler_do_disco() -> desenho.Leitura:
    """Uma passada de leitura. **Nunca escreve** — nem no vdf, nem no registro.

    `anotar=False` NÃO É ZELO: o `censo_do_wrapper` com `anotar=True` grava o
    `wrapper-visto.json`, que é a memória que separa *"perdeu o wrapper"* de
    *"nunca teve"*. Uma PINTURA que anotasse transformaria todo jogo novo em
    "já visto" antes de ela ver o aviso uma única vez — e a regressão do
    Pragmata, que essa memória existe para nomear, ficaria muda para sempre.
    """
    from hefesto_dualsense4unix.integrations import prontuario_dos_jogos as pdj
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    try:
        censo = sw.censo_do_wrapper(anotar=False)
    except Exception as erro:  # o disco dela não pode derrubar a aba
        return desenho.Leitura(erros=(str(erro),))

    try:
        instalados = len(pdj.jogos_instalados())
    except Exception:
        instalados = 0

    def trio(jogos: list[Any]) -> tuple[tuple[str, str, str], ...]:
        return tuple((j.appid, j.rotulo, _porque(j.motivo)) for j in jogos)

    return desenho.Leitura(
        com_wrapper=tuple(censo.com_wrapper),
        reparaveis=trio(censo.reparaveis),
        intocaveis=trio(censo.intocaveis),
        recusados=tuple((a, slo.rotulo_do_jogo(a)) for a in censo.recusados),
        instalados=instalados,
        frase=sw.frase_do_aviso(censo),
        erros=tuple(censo.erros),
    )


def _valores(lida: desenho.Leitura | None) -> dict[str, str]:
    """Os endereços da aba inteira, montados pelo desenho."""
    return desenho.Quadro(lancadores=desenho.cartoes(lida)).valores()


@registrar("07-lancadores.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    """A aba inteira, e ela NÃO depende de controle nenhum.

    O gerador já tinha medido isto e escrito no próprio arquivo: nenhuma função
    de `prontuario_dos_jogos` recebe controle, MAC, device ou transporte — os
    cinco impedimentos e as duas curas são fatos do JOGO EM DISCO. É por isso
    que a fita desta aba nasce esmaecida (`fita_viva=False`) e por isso este
    pacote não devolve `colunas`: não há nada a dizer por controle.
    """
    valores = _valores(VIGIA.agora())
    fora: dict[str, Any] = dict(valores)
    fora["sem_dono"] = {k: {"sem_dono": True, "oque": v} for k, v in SEM_DONO.items()}
    fora["cobertura"] = {"pintados": len(valores), "sem_dono": len(SEM_DONO)}
    return fora


# ---------------------------------------------------------------------------
# OS GESTOS — ver o exemplo comentado em `a04_iluminacao.py`
#
# NENHUM DELES FALA COM O DAEMON, e isto os separa de todos os outros gestos
# desta casa: o wrapper vive no `localconfig.vdf` da Steam e na lista
# `jogos_sem_wrapper.txt`, dois arquivos em disco. `pacotes.daemon.metodos()`
# não traz UM método que os toque — por isso `PONTE` e `METODOS` ficam vazios, e
# a prova destes botões é a régua da aba, que cobra o efeito NO ARQUIVO.
# ---------------------------------------------------------------------------
from . import gesto  # noqa: E402


@gesto("07-lancadores.html", "procurar")
def procurar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Procurar de novo": esquece o cache e relê o disco AGORA.

    Ele devolve a aba repintada — e é o caminho de volta do piloto que torna
    isso possível. Sem o retorno, o botão dependeria do próximo tique com o TTL
    já vencido, e quem clicasse veria a tela igual por até 20 segundos: o botão
    que responde calado.
    """
    VIGIA.esquecer()
    return {"mesa": _valores(VIGIA.ler())}


@gesto("07-lancadores.html", "consertar")
def consertar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Consertar": repõe o atalho de inicialização onde ele falta.

    `reparar_ou_adiar` É O DONO, e os portões dele não são negociáveis: **jogo
    aberto antes de tudo** (fechar a Steam ali mataria o jogo e o progresso não
    salvo), depois Steam aberta (ela regrava o vdf ao sair e engoliria a
    edição), e só então a escrita. Reimplementar a ordem aqui seria uma segunda
    porta para o mesmo arquivo — e a primeira já sabe preservar o `VKD3D_CONFIG`
    que cura o crash do Pragmata, porque o `migrate_value` PREPENDE.

    A RECUSA VAI PARA A TELA. `RuntimeError` é o contrato desta casa para "o
    produto recusou", e a frase é a da sentinela, que já nomeia o jogo e já diz
    o que vai acontecer — *"Vou repor assim que o jogo e a Steam fecharem"*.
    """
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw

    status, censo, _ = sw.reparar_ou_adiar()
    VIGIA.esquecer()
    if status in (sw.REPARO_ADIADO_JOGO, sw.REPARO_ADIADO_STEAM, sw.REPARO_ERRO):
        raise RuntimeError(sw.frase_do_aviso(censo) or
                           "não consegui repor o atalho de inicialização")
    return {"mesa": _valores(VIGIA.ler())}


@gesto("07-lancadores.html", "ver-o-que-impede")
def ver_o_que_impede(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Ver o que impede": os cinco impedimentos nomeados, do prontuário.

    `levantar_censo` e `curar_o_que_e_automatico` estavam em
    `integrations/prontuario_dos_jogos.py` **sem um chamador em `src/`** — o
    gerador da aba já tinha medido e escrito isso na própria legenda ("o que
    estava no código e nunca teve tela"). Este é o chamador.

    ELE LEVA TREZE SEGUNDOS E MEIO, medido em 02/09/2026 — examina o executável
    de cada jogo instalado. É a razão de ser um GESTO e não pintura: o gesto
    roda em thread (`hefesto_vivo._gesto`), a pintura roda no laço do GTK e
    congelaria a janela.
    """
    from hefesto_dualsense4unix.integrations import prontuario_dos_jogos as pdj

    censo = pdj.levantar_censo()
    return {"mesa": _com_outra_frase(desenho._e(censo.frase()))}


def _com_outra_frase(diz: str) -> dict[str, str]:
    """A aba de novo, com o corpo do cartão da Steam trocado.

    OS DOIS GESTOS QUE RESPONDEM COM TEXTO passam por aqui, e não montam o
    cartão cada um do seu jeito: dois lugares escrevendo o mesmo cartão é como
    um deles esquece um endereço e a tela fica com metade do valor velho.
    """
    lida = VIGIA.agora()
    cartoes = desenho.cartoes(lida)
    steam = cartoes[0]
    cartoes[0] = desenho.Lancador(
        chave=steam.chave, nome=steam.nome, selo=steam.selo, jogos=steam.jogos,
        diz=diz, acoes=steam.acoes, carimbo=steam.carimbo, fora=steam.fora,
        tem_lista=steam.tem_lista)
    return desenho.Quadro(lancadores=cartoes).valores()


@gesto("07-lancadores.html", "detectar")
def detectar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Detectar o jogo que está aberto": diz QUAL é, ou recusa dizendo.

    `steam_game_running_appid` lê a `/proc` procurando a linha
    `SteamLaunch AppId=` — a mesma fonte que o `launch_wrapper_dialog` usa para
    decidir se mostra o lembrete, e a única do produto que responde "que jogo
    está rodando agora".

    O QUE ELE NÃO FAZ: criar o perfil. Isso é da aba Perfis (`a10_perfis`), e
    ter dois caminhos para o mesmo disco é como duas telas passam a discordar.
    """
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    appid = slo.steam_game_running_appid()
    if appid is None:
        raise RuntimeError(
            "Não achei jogo nenhum aberto agora. Abra o jogo de onde for, "
            "volte aqui e clique de novo.")
    lida = VIGIA.agora()
    tem = lida is not None and str(appid) in lida.com_wrapper
    return {"mesa": _com_outra_frase(
        f"<b>{desenho._e(slo.rotulo_do_jogo(appid))}</b> está aberto agora e "
        + ("<b>abre pelo atalho do Hefesto</b>." if tem else
           "<b>não abre pelo atalho do Hefesto</b> — clique em Consertar com o "
           "jogo e a Steam fechados."))}


def _appid_do_clique(o: dict[str, Any], nome: str) -> str:
    """O appid que o botão da linha mandou. Vazio é RECUSA, nunca palpite."""
    appid = str(o.get("v") or "").strip()
    if not appid:
        raise ValueError(
            f"{nome}: o clique não disse qual jogo. Cada linha da lista manda "
            f"`data-v` com o appid — se ele sumiu do desenho, o botão agiria "
            f"sobre um jogo escolhido por acaso.")
    return appid


@gesto("07-lancadores.html", "tirar-daqui")
def tirar_daqui(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Não usar neste jogo": põe o appid no `jogos_sem_wrapper.txt`.

    É A RECUSA DELA, e o produto inteiro a respeita: `censo_do_wrapper` pula
    quem está nessa lista, e `apply_wrapper_to_all_games` a recebe em
    `excluir=`. Sem este botão, a única forma de tirar um jogo era editar o
    arquivo à mão — a lista existia sem NENHUMA tela que a escrevesse.
    """
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    slo.marcar_jogo_sem_wrapper(_appid_do_clique(o, "tirar-daqui"))
    VIGIA.esquecer()
    return {"mesa": _valores(VIGIA.ler())}


@gesto("07-lancadores.html", "voltar-a-usar")
def voltar_a_usar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Voltar a usar": tira o appid do `jogos_sem_wrapper.txt`.

    O par do de cima, e ele precisa existir pelo mesmo motivo que o "Automático"
    da Iluminação precisa existir: um gesto que só vai numa direção deixa a
    pessoa presa no estado em que clicou.
    """
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    slo.desmarcar_jogo_sem_wrapper(_appid_do_clique(o, "voltar-a-usar"))
    VIGIA.esquecer()
    return {"mesa": _valores(VIGIA.ler())}


#: VAZIOS, E É A MEDIÇÃO QUE OS DEIXA VAZIOS: nenhum gesto desta aba fala com o
#: daemon. O wrapper vive em dois arquivos em disco, e `pacotes.daemon.metodos()`
#: não traz um método sequer que os toque.
PONTE: set[str] = set()
METODOS: set[str] = set()


PAGINA = "07-lancadores.html"
PISO_DA_ABA = 6

#: SEM `PROVAS`, e a razão é o contrato da régua dos botões: ela injeta uma
#: `PonteDeMentira` e cobra QUAL função da ponte o gesto chamou. Um gesto que
#: não usa a ponte chamaria zero e a régua reprovaria por estar CERTO — o
#: defeito que esta casa nomeou onze vezes em 26/08 (*a régua reprovando a
#: melhora em vez do defeito*). Quem prova estes seis é
#: `tests/unit/test_a_aba_lancadores_diz_a_verdade.py`, com o `HOME` desviado e
#: o efeito cobrado NO ARQUIVO — que é a prova mais forte, não a mais fraca.
PROVAS: list[dict[str, Any]] = []

#: TODOS OS SEIS, e não por preguiça: o `state_full` do daemon não tem UMA
#: chave sobre a Steam, sobre o `localconfig.vdf` ou sobre a lista de
#: recusados. O efeito destes botões é o DISCO e a TELA — e os dois têm régua.
SEM_ECO = ("procurar", "consertar", "ver-o-que-impede", "detectar",
           "tirar-daqui", "voltar-a-usar")
