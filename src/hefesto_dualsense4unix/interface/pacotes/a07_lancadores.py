#!/usr/bin/env python3
"""O pacote da aba `07` Lançadores — a aba que era desenho inteiro.

A DECISÃO DE PRODUTO QUE ABRIU ESTA ABA, e ela CADUCOU outra, de um dia antes:

    01/09/2026

    02/09/2026

A `F` é esta aba (o registro «ROTA-F-a-aba-lancadores» de 02/09/2026).
A segunda decisão vale, e ela traz a razão: **o GTK tem o mapa funcional** —
`sentinela_do_wrapper`, `prontuario_dos_jogos`, `carona_do_wrapper` e
`launch_wrapper_dialog` já sabiam responder o que esta tela pergunta. A primeira
fica registrada com data nas duas réguas que a codificavam
(`test_o_despachante_serve_as_dez.py`, `test_o_casamento_das_dez.py`): não se
apaga decisão medida, e a nota é o que impede a próxima pessoa de reabrir.

O QUE ESTA ABA AFIRMAVA, E O QUE O PRODUTO RESPONDE
---------------------------------------------------
Medido em 02/09/2026 na máquina do usuário, com `censo_do_wrapper(anotar=False)` e
`prontuario_dos_jogos.levantar_censo` — leitura pura, nada escrito:

    o HTML afirmava                  o produto responde
    ------------------------------   -------------------------------------------
    Steam · 412 jogos                23 jogos INSTALADOS; 63 appids com o
                                     wrapper na linha do `localconfig.vdf`
    ◆ 3 jogos já sabem por onde      0 pontes confirmadas
    5 encontrados · 1 impedimento    2 lançadores achados, 0 impedidos
    Heroic · 28 jogos · NÃO CHEGAM   não achei o Heroic nesta máquina

Quatro afirmações, quatro contradições. **A cura não é apagar o desenho** — é
dar-lhe fonte, e dizer `NÃO SEI` onde não há fonte. Um selo `CHEGAM` sobre um
lançador que ninguém olhou é a `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` na cor verde.

E O NÚMERO ANDOU NO MESMO DIA, o que é o argumento inteiro desta aba: às 19h20
de 02/09, `censo_do_wrapper(anotar=False)` respondia **62** appids com o wrapper
e **um reparável — o PRAGMATA, com motivo `regressao`** (*"tinha o atalho e
perdeu"*). Às 15h a mesma leitura dava 63 e zero reparáveis. A Steam comeu a
linha de novo entre as duas medições, e **nada a repôs**: a carona
(`carona_do_wrapper.pegar_carona_no_gesto`) nunca migrou para a interface nova
— `grep -rn carona_do_wrapper src/hefesto_dualsense4unix/interface/` devolve só
comentário. Enquanto ela não abrir esta aba e clicar em Consertar, o jogo fica
sem o atalho. Está relatado como trabalho de fora desta aba.

O QUE MUDOU EM 02/09, À TARDE, e é a diferença entre duas perguntas
-------------------------------------------------------------------
Os cinco cartões sem censo diziam `NÃO SEI` por CONSTANTE: o pacote escrevia
sempre a mesma palavra, e a tela não podia diferir *"o produto mediu e não
sabe"* de *"ninguém pintou"*. **São duas perguntas, e o produto responde uma
delas de graça:**

    "sei ler a biblioteca deste lançador?"   não, em nenhum dos cinco
    "este lançador está instalado aqui?"     SIM, e é um `stat` por candidato

`_onde_estao_os_lancadores` responde a segunda pelas pastas de `.desktop` que
`jogos_locais.pastas_de_atalhos()` já resolve (a spec XDG, não dois caminhos
cravados). Medido nesta máquina em 02/09/2026, com 4 pastas de atalhos:

    heroic · lutris · retroarch · emuladores    NÃO ACHEI
    flatpak                                     achado em `/usr/bin/flatpak`
    steam                     achada em `/usr/local/share/applications/steam.desktop`

O selo `off` (`NÃO ACHEI`) existia em `SELOS` desde que o desenho nasceu e
**nenhum caminho o produzia**. Ele era a palavra que faltava para a tela dizer
o que o produto mediu.

E A SEXTA ENTROU NA BUSCA À NOITE, porque a segunda pergunta não era só dos
cinco. O cartão da Steam era o único cuja presença ninguém mediu — ele tinha
CENSO, e ter censo do interior responde outra coisa. Medido com o `HOME` numa
casa de mentira, `PATH` sem binário e `pastas_de_atalhos` numa pasta vazia:

    ANTES   steam · selo 'ok' (CHEGAM) · presente True · topo "1 encontrado"
            "Os controles chegam. O atalho de inicialização está no lugar em
             0 jogos da sua biblioteca."
    DEPOIS  steam · selo 'off' (NÃO ACHEI) · presente False · topo "0 encontrados"

Uma máquina sem Steam recebia o selo VERDE, na mesma tela em que os outros
cinco diziam `NÃO ACHEI`. **Na máquina do usuário nada muda** — a Steam está lá, e a
busca a acha pelo `.desktop`.

NADA SE REESCREVE — o que este arquivo NÃO faz
----------------------------------------------
Nenhuma linha daqui decide se um jogo tem o wrapper, nem repõe o wrapper, nem
nomeia um impedimento. Quem faz é o motor, e cada função tem endereço:

    integrations/sentinela_do_wrapper.censo_do_wrapper   quem tem e quem não tem
    integrations/steam_launch_options.rotulo_do_jogo     o nome, do `appmanifest`
    integrations/steam_launch_options.marcar_jogo_sem_wrapper    o "tirar daqui"
    integrations/steam_launch_options.desmarcar_jogo_sem_wrapper o "voltar a usar"
    integrations/prontuario_dos_jogos.jogos_instalados   os `appmanifest` do disco
    integrations/prontuario_dos_jogos.pontes_confirmadas quem já sabe por onde entrar
    integrations/prontuario_dos_jogos.classes_com_ponte  o mesmo, para os outros
    integrations/lista_de_exclusao                       a lista de exclusão
    integrations/jogos_locais.pastas_de_atalhos          onde moram os `.desktop`
    integrations/steam_launch_options.WRAPPER_LAUNCH     a linha à mostra
    app/actions/launch_wrapper_dialog.load_dismissed_appids  quem ela dispensou
    app/actions/launch_wrapper_dialog.remove_dismissed_appid o "voltar a perguntar"
    app/actions/launch_wrapper_dialog.extract_steam_appid    o jogo em foco
    app/actions/home_actions.wrapper_banner_text         o aviso do jogo aberto
    daemon/launch_env.launch_session_appid               1º degrau da escada
    daemon/launch_env.read_last_run_marker               3º degrau da escada

O REPARO SAIU DESTA ABA — 21/09/2026,  O «Consertar», o «Ver o que
impede», o «Posso fechar a Steam», o «Não perguntar», o «Copiar a linha» e os
dois do Steam Input saíram, e com eles a vigia de dentro da aba
(`_VigiaDaSteam`) e os portões do censo. Quem repõe o atalho é o vigia de fora
(`hefesto-steam-input-guard`, a cada 30 min e a cada escrita da Steam), que
na mesma noite repôs o do PRAGMATA sem clique nenhum. Os parágrafos abaixo
contam como a aba chegou até ali, e ficam como registro.

O QUE ENTROU EM 03/09/2026, e é PONTE e não código novo: a interface nova
jogava fora `gamepad_emulation.wrapper_used` — a chave que o daemon publica a
cada tique e que a GTK vira banner em DUAS abas, sem clique nenhum. `grep -rn
wrapper_used src/hefesto_dualsense4unix/interface/` só achava o dublê de
perfis. Junto vieram as duas metades que faltavam do mesmo assunto: o botão que
DISPENSA o aviso (a lista existia e só a GTK a escrevia) e o caminho para
`with_steam_closed`, sem o qual o `Consertar` recusa sempre na bancada.

`carona_do_wrapper.passada()` responderia parte disto — mas ela ESCREVE no
`localconfig.vdf` quando há o que repor, e uma PINTURA que escreve em disco a
cada tique é a coisa mais perigosa que esta aba poderia fazer. A pintura usa o
CENSO (read-only, seguro com a Steam aberta — e é por isso que ele é uma camada
separada do reparo); quem chama o caminho que escreve é o gesto "Consertar" e,
desde 03/09/2026, a :class:`_VigiaDaSteam` que esse gesto arma quando é adiado
— nunca a pintura, e nunca sem um clique do usuário antes.

E ELA FOI A ÚLTIMA METADE QUE FALTAVA: com a Steam aberta o `Consertar` recusa
dizendo , e até 03/09 **nada reperguntava** — a
tela prometia e ela é que tinha de lembrar. A janela velha cumpre essa frase
desde 16/08 com um tique de `INTERVALO_DA_VIGIA_S`; a página cumpre agora com o
mesmo tique, a mesma frase e o mesmo desligador.

O DESENHO dos cartões mora em `interface/desenho_dos_lancadores.py`, e é o MESMO
que o gerador `aba07.py` usa. Um dono, dois dados — é o que impede o número
digitado de voltar: não há onde digitá-lo.

O CUSTO, E POR QUE O DISCO NÃO ENTRA NO TIQUE
----------------------------------------------
Medido em 02/09/2026, na máquina do usuário:

    censo_do_wrapper()          26 ms (85 ms na primeira)
    jogos_instalados()          12 ms
    levantar_censo()        13.440 ms   <- treze segundos e meio

O tique do piloto é de 100 ms. Ler 40 ms de disco a cada tique seria 40% do
orçamento gasto relendo um arquivo que muda uma vez por semana; o prontuário
sequer cabe. (A 500 ms, que era o tique até 04/09/2026, isso já custava 8% — a
cura vale MAIS agora, não menos.) Por isso a leitura vive na :class:`_Vigia`: a pintura NUNCA
bloqueia, uma thread refaz a conta quando ela passa de :data:`TTL_S`, e o
prontuário só sai do lugar quando ela clica em "Ver o que impede".
"""
from __future__ import annotations

import dataclasses
import logging
import re
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

from hefesto_dualsense4unix.integrations import lista_de_exclusao
from hefesto_dualsense4unix.interface import desenho_dos_lancadores as desenho

from . import Contexto, perfil, registrar

#: `RuntimeError`/`ValueError` (`hefesto_vivo`), não a um terminal.
_LOG = logging.getLogger(__name__)

TTL_S = 20.0

#: dono dele, `pacotes/confirmacao.SEGUNDOS_PARA_CONFIRMAR`.

#: O `heroic` SAIU DAQUI EM 09/09/2026 — LANCADORES-ZERO-01, e o motivo escrito
SEM_DONO: dict[str, str] = {
    "criar-perfil": "criar perfil é da aba Perfis (`a10_perfis`); dois caminhos "
                    "para o mesmo disco é como duas telas passam a discordar",
}


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


VIGIA = _Vigia()


def _porque(motivo: str) -> str:
    """O motivo do censo em português de tela. As CHAVES saem do motor."""
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw

    return {
        sw.MOTIVO_REGRESSAO: "tinha o atalho e perdeu",
        sw.MOTIVO_NOVO: "nunca recebeu o atalho",
        sw.MOTIVO_ESTENDIDO: "linha editada à mão — não vou tocar",
    }.get(motivo, motivo)


def _declarados() -> tuple[desenho.SemCenso, ...]:
    """O que ELA declarou no `maquina.json`, no molde do procurador."""
    # veria, porque o motor estava todo lá.
    perfil._com_o_src()
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina

    try:
        declaracao = carregar_maquina()
    except Exception:  # pragma: no cover - o disco do usuário não derruba a aba
        return ()
    return tuple(
        desenho.SemCenso(chave=chave, nome=item.rotulo,
                         atalhos=tuple(item.atalhos),
                         comandos=tuple(item.comandos),
                         declarado=True)
        for chave, item in sorted(declaracao.lancadores.items())
    ) + _achados_por_conteudo()


def _achados_por_conteudo() -> tuple[desenho.SemCenso, ...]:
    """Os lançadores que a máquina DECLARA ser, e que ninguém digitou."""
    from hefesto_dualsense4unix.integrations import jogos_locais as jl

    try:
        achados = jl.lancadores_por_conteudo()
    except Exception:  # pragma: no cover - o disco do usuário não derruba a aba
        return ()
    de_fabrica = {atalho for item in desenho.SEM_FONTE for atalho in item.atalhos}
    de_fabrica |= {atalho for atalho in desenho.A_STEAM.atalhos}
    return tuple(
        desenho.SemCenso(chave=stem.lower().replace(".", "-"), nome=nome,
                         atalhos=(stem,), comandos=())
        for stem, nome in sorted(achados.items())
        if stem not in de_fabrica
    )


def _onde_estao_os_lancadores(
    declarados: tuple[desenho.SemCenso, ...] | None = None,
) -> tuple[tuple[str, str], ...]:
    """PROCURA os lançadores desta máquina. Não lê dentro de nenhum.

    `declarados=None` LÊ O DISCO; uma tupla dispensa a leitura. O parâmetro
    existe para que uma passada da vigia abra o `maquina.json` UMA vez em vez de
    duas (a busca e a `Leitura` precisam da mesma lista), e para que uma régua
    monte a declaração à mão sem tocar no disco.

    A PERGUNTA É ESTREITA DE PROPÓSITO, e é a única que o produto sabe
    responder hoje sem inventar: *"este lançador está instalado aqui?"* — não
    *"quais jogos ele tem"*, nem *"os controles chegam neles"*. Responder a
    estreita com honestidade vale mais que calar as três.

    A STEAM ENTROU EM 02/09, e ela era a AUSÊNCIA que custava: a busca percorria
    `SEM_FONTE`, que é a lista de *"não sei ler a biblioteca dele"* — e a Steam
    não está nela porque o produto LÊ a biblioteca do usuário. Só que ter censo do
    interior não responde se o lançador está aqui, e o cartão da Steam nascia
    com `presente=True` cravado. Numa casa de mentira sem Steam nenhuma o topo
    dizia **"1 encontrado"** e o cartão acendia o selo verde `CHEGAM`. Agora a
    lista percorrida é :func:`desenho.procurados`, que devolve os de fábrica
    **mais** o que ela declarou.

    UM PROCURADOR SÓ, E É ESTE — 08/09/2026. O lançador que ela acrescenta pelo
    botão de registro não ganha busca própria: ele entra na MESMA lista,
    com os MESMOS três campos, e é achado pelas MESMAS duas buscas. Um segundo
    caminho seria a assimetria que produz duas respostas para a mesma pergunta —
    e a segunda envelhece calada, porque só a máquina do usuário a exercita.

    AS PASTAS SÃO AS DO MOTOR, e não uma lista local:
    `jogos_locais.pastas_de_atalhos()` já resolve `XDG_DATA_HOME` e
    `XDG_DATA_DIRS` pela spec, e já pagou o preço de não fazê-lo — em 23/08 o
    produto olhava DOIS diretórios cravados e perdia os 54 atalhos de
    `~/.local/share/flatpak/exports/share/applications`, que é onde um Heroic
    ou um Lutris instalados por Flatpak apareceriam. Repetir a lista aqui seria
    repetir aquele defeito num segundo lugar.

    O CUSTO É UM `stat` POR CANDIDATO, e nenhum `glob`: são seis lançadores,
    dezesseis `stem` no total e quatro pastas nesta máquina — 64 verificações de
    existência, contra as centenas de arquivos que um `glob("*.desktop")`
    abriria. Ainda assim ela roda pela :class:`_Vigia`, fora do tique: disco é
    disco, e o orçamento do tique é de 100 ms para a janela inteira.

    NUNCA LEVANTA. Um `PATH` estranho ou uma pasta sem permissão devolve
    "não achei" para aquele lançador, que é o pior caso honesto — e degradar
    calado AQUI é requisito, o mesmo que `pastas_de_atalhos` já declara.

    O `onde` É O CAMINHO INTEIRO, e isso é o que a frase prometia. A docstring
    do `DIZ_ACHEI` (a frase saiu da tela em 11/09 e o nome em 21/09/2026) dizia
    que dizer ONDE ** — e o código tinha
    o caminho na mão e o jogava fora: `shutil.which` já devolve
    `/usr/bin/flatpak` e a linha o trocava por `PATH/flatpak`, uma notação que
    ela não pode `ls`. O mesmo no laço das pastas: ele sabe em QUAL das quatro
    pastas o arquivo estava e guardava só o `stem`. Numa máquina com o Heroic
    nativo **e** o Heroic por Flatpak, o cartão não dizia qual dos dois achou.
    """
    import shutil

    from hefesto_dualsense4unix.integrations import jogos_locais as jl

    try:
        pastas = jl.pastas_de_atalhos()
    except Exception:
        pastas = []

    fora: list[tuple[str, str]] = []
    lista = _declarados() if declarados is None else declarados
    for item in desenho.procurados(lista):
        onde = ""
        for pasta in pastas:
            for stem in item.atalhos:
                try:
                    caminho = pasta / f"{stem}.desktop"
                    if caminho.is_file():
                        onde = str(caminho)
                        break
                except OSError:  # pragma: no cover - pasta sumiu no meio
                    continue
            if onde:
                break
        if not onde:
            for comando in item.comandos:
                try:
                    achado = shutil.which(comando)
                except Exception:  # pragma: no cover - PATH torto
                    continue
                if achado:
                    onde = achado
                    break
        fora.append((item.chave, onde))
    return tuple(fora)


def _dispensados() -> tuple[tuple[str, str], ...]:
    """Os jogos que O usuário mandou não perguntar mais — e que tela nenhuma mostrava."""
    from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as lwd
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    try:
        appids = sorted(lwd.load_dismissed_appids())
    except Exception:
        return ()
    return tuple((a, slo.rotulo_do_jogo(a)) for a in appids)


def _onde_falta_o_ambiente(
    onde_estao: tuple[tuple[str, str], ...], declarados: tuple[desenho.SemCenso, ...],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Os cartões ACHADOS em que o ambiente do Hefesto falta — AS-SOLUCOES-NOS-LANCADORES-01."""
    from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe

    onde = dict(onde_estao)
    try:
        exclusao = lista_de_exclusao.o_que_a_carona_pula()
    except Exception:
        exclusao = cpe.NaExclusao()
    fora: list[tuple[str, tuple[str, ...]]] = []
    for item in desenho.procurados(declarados):
        if item.chave == desenho.STEAM or not onde.get(item.chave):
            continue
        try:
            faltam = cpe.onde_falta_o_ambiente(item.chave, item.atalhos, exclusao=exclusao)
        except Exception:
            continue
        if faltam:
            fora.append((item.chave, faltam))
    return tuple(fora)


def _ler_do_disco() -> desenho.Leitura:
    """Uma passada de leitura. **Nunca escreve** — nem no vdf, nem no registro.

    `anotar=False` NÃO É ZELO: o `censo_do_wrapper` com `anotar=True` grava o
    `wrapper-visto.json`, que é a memória que separa *"perdeu o wrapper"* de
    *"nunca teve"*. Uma PINTURA que anotasse transformaria todo jogo novo em
    "já visto" antes de ela ver o aviso uma única vez — e a regressão do
    Pragmata, que essa memória existe para nomear, ficaria muda para sempre.

    A PRESENÇA DOS LANÇADORES FICA FORA DO `try` DO CENSO, e de propósito: a
    Steam quebrada não pode apagar a resposta sobre o Heroic. Eram duas
    perguntas independentes tratadas como uma só, e é assim que uma tela inteira
    cai por causa de um arquivo.

    E DESDE QUE A STEAM ENTROU NA BUSCA, essa ordem passou a valer para ela
    também: o ramo de erro devolve `onde_estao=onde_estao`, então o cartão da
    Steam sabe dizer "não achei" mesmo com o vdf ilegível — e sabe **não** dizer
    isso quando o erro prova que o arquivo existe (ver
    :meth:`desenho.Leitura.viu_a_biblioteca`).
    """
    from hefesto_dualsense4unix.integrations import prontuario_dos_jogos as pdj
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    declarados = _declarados()
    onde_estao = _onde_estao_os_lancadores(declarados)
    try:
        com_ponte = frozenset(pdj.classes_com_ponte())
    except Exception:
        com_ponte = frozenset()
    do_disco = desenho.medir_no_disco(onde_estao, declarados, com_ponte=com_ponte)
    do_disco = dataclasses.replace(
        do_disco, sem_ambiente=_onde_falta_o_ambiente(onde_estao, declarados))

    try:
        censo = sw.censo_do_wrapper(anotar=False)
    except Exception as erro:
        return desenho.Leitura(erros=(str(erro),), onde_estao=onde_estao,
                               declarados=declarados, do_disco=do_disco)

    try:
        instalados = len(pdj.jogos_instalados())
    except Exception:
        instalados = 0

    try:
        pontes = len(pdj.pontes_confirmadas())
    except Exception:
        pontes = 0

    def trio(jogos: list[Any]) -> tuple[tuple[str, str, str], ...]:
        return tuple((j.appid, j.rotulo, _porque(j.motivo)) for j in jogos)

    return desenho.Leitura(
        com_wrapper=tuple(censo.com_wrapper),
        reparaveis=trio(censo.reparaveis),
        intocaveis=trio(censo.intocaveis),
        recusados=tuple((a, slo.rotulo_do_jogo(a)) for a in censo.recusados),
        dispensados=_dispensados(),
        instalados=instalados,
        pontes=pontes,
        onde_estao=onde_estao,
        declarados=declarados,
        # e a MESMA que o `apply_wrapper_to_all_games` grava no vdf. Digitá-la
        linha=slo.WRAPPER_LAUNCH,
        erros=tuple(censo.erros),
        do_disco=do_disco,
    )


def _valores(lida: desenho.Leitura | None) -> dict[str, str]:
    """Os endereços da aba inteira, montados pelo desenho."""
    return desenho.Quadro(lancadores=desenho.cartoes(lida)).valores()


# `gamepad_emulation.wrapper_used` a cada tique — *"há jogo aberto AGORA e ele
# sem clique nenhum (`home_actions.wrapper_banner_text`, consumido pela Início
def _o_jogo_em_foco(state: dict[str, Any] | None) -> str:
    """O appid do jogo Steam em foco AGORA, ou `""`. **Não toca o disco.**"""
    from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as lwd

    if not isinstance(state, dict):
        return ""
    return lwd.extract_steam_appid(state.get("window_detect_last_class")) or ""


def aviso_do_jogo_aberto(
    state: dict[str, Any] | None, lida: desenho.Leitura | None
) -> tuple[str, str]:
    """`(html do aviso, appid)` — ou `("", "")` quando não há o que avisar.

    A DECISÃO É DA GTK, INTEIRA: `home_actions.wrapper_banner_text` só acende
    no ``False`` LITERAL de `wrapper_used` (``None``/ausente = sem jogo aberto,
    ou daemon antigo sem o campo → **nunca** alarme falso por payload
    incompleto). Reescrever esse teste aqui seria a segunda cópia de uma regra
    que já tem dono — e a cópia envelheceria calada no dia em que o daemon
    ganhasse um quarto valor.

    **O TEXTO DEIXOU DE SER O DA JANELA VELHA — TELA-CALADA-02, 13/09/2026.**
    O cartão escreve :data:`JOGO_ABERTO_SEM_O_ATALHO`, um rótulo de estado; a
    frase longa (`home_actions.WRAPPER_MISSING_TEXT`) continua do dono e não é
    redigitada aqui. Os dois parágrafos de baixo contam como ela era, e ficam
    porque a decisão `07-Q2` que eles registram continua valendo para quem
    ainda a mostra.

    **A FRASE MUDOU EM 06/09/2026 (ONDA5-07-03), e a palavra é de produto.** Ela
    terminava em *"Copie as opções na aba Sistema."*, e a aba Sistema da
    interface nova tem doze botões e nenhum copia coisa alguma. A decisão
    `07-Q2` dela, em 05/09, recusou as TRÊS opções oferecidas — só o fato,
    apontar o Consertar, duas frases — e respondeu com uma quarta: *"O produto
    aplica ela"*. A frase passou a dizer o fato **mais** a promessa que o
    produto cumpre, sem nomear lugar nenhum:
    *"O jogo está rodando sem o atalho de inicialização — controles podem
    duplicar. Reponho o atalho no próximo Aplicar ou Salvar Perfil, com a Steam
    fechada."*

    O DONO CONTINUA SENDO UM SÓ (`app/actions/home_actions.WRAPPER_MISSING_TEXT`)
    e esta aba continua sem redigitar uma palavra. A condição *"com a Steam
    fechada"* está na frase porque a carona não tem relógio próprio: quem repõe
    é `carona_do_wrapper.passada`, de carona nos gestos de perfil.

    AS DUAS RECUSAS CALAM — PO, 04/09/2026, `07[03]`. Até hoje só a dispensa
    (*"Não perguntar para este jogo"*) calava; o *"Não usar neste jogo"* — o
    `jogos_sem_wrapper.txt`, a lista que o produto INTEIRO respeita no reparo —
    não calava tela nenhuma. Ela tirava o jogo de propósito e a tela reclamava
    dele toda vez que ele abrisse. **Um aviso que sobrevive à resposta de produto
    ensina que o botão não obedece.**

    E AS DUAS SÃO A MESMA FRASE DE PRODUTO, dita de dois jeitos. O desfazer de cada uma já está na
    lista do cartão — *"Voltar a
    usar"* e *"Voltar a perguntar"* —, e é o que impede o silêncio por engano
    de ser um caminho só de ida.

    AS DUAS LISTAS SAEM DA `Leitura` QUE A VIGIA JÁ LEU (`lida.dispensados` e
    `lida.recusados`), nunca do disco: reler dois arquivos a cada tique seria
    disco na thread da janela, que é o que a :class:`_Vigia` existe para
    impedir — e é o custo que a própria decisão nomeia (*"a leitura das duas
    listas vem de vigia em segundo plano"*).

    SEM O APPID O AVISO CONTINUA, e é decisão: `wrapper_used is False` é o
    daemon afirmando que HÁ jogo aberto sem o wrapper. Calar porque a
    `window_detect_last_class` ainda não casou trocaria um aviso verdadeiro por
    silêncio — o que some é só o botão de dispensar, que sem appid não teria
    sobre o que agir.

    E AS QUATRO CONDIÇÕES SÃO AS DO DONO — 06/09/2026, `STEAM-INPUT-01`. Até
    aqui esta função aplicava DUAS das quatro do lembrete da janela velha (o
    `wrapper_used is False`, que já traz a janela em foco e o jogo sem o
    atalho, e a dispensa) e **não aplicava a da EMULAÇÃO**. O buraco é medível:
    no Modo Nativo não há gamepad virtual, logo não há o que duplicar — e a aba
    avisava assim mesmo, com um alarme que não podia acontecer. A janela velha
    nunca teve esse defeito, porque a decisão de produto é uma função PURA
    (`launch_wrapper_dialog.wrapper_dialog_decision`) e ela pergunta pelo modo.

    ELA É IMPORTADA, E NÃO REDIGITADA. O que esta aba faz é ENTREGAR a evidência
    que já tem no lugar da que a janela velha vai buscar: o `vdf_cache` do dono
    responde *"falta o atalho neste jogo?"*, e aqui quem já respondeu isso foi o
    DAEMON (`wrapper_used is False`), com evidência mais forte — o marker diz se
    o wrapper de fato RODOU, e não só se a linha está escrita. Os dois campos que
    não existem numa página (o popup e o diálogo do GTK) vão `False`, que é o
    que eles são.

    O `shown_this_session` VAI VAZIO DE PROPÓSITO, e é a única condição que não
    se importa: o anti-spam da janela velha existe porque lá o lembrete é um
    DIÁLOGO que rouba o foco, e mostrá-lo duas vezes por sessão seria castigo.
    Aqui ele é uma linha dentro do cartão, que nasce e morre com o jogo aberto —
    aplicá-lo faria o aviso sumir no segundo tique e voltar nunca, com o jogo
    ainda rodando sem o atalho.

    SEM O APPID A DECISÃO NÃO É CONSULTADA, e isso mantém a decisão de cima
    (o aviso continua): o dono responde `SKIP` sem appid, e trocar um aviso
    verdadeiro do daemon por silêncio seria o contrário do que esta função faz.
    """
    from hefesto_dualsense4unix.app.actions import home_actions as ha
    from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as lwd

    texto = ha.wrapper_banner_text(state)
    if not texto:
        return "", ""
    appid = _o_jogo_em_foco(state)
    if appid:
        acao, _ = lwd.wrapper_dialog_decision(
            state,
            # `wrapper_banner_text` acima só devolve texto no `False` LITERAL de
            vdf_cache={appid: True},
            dismissed=calados(lida) if lida is not None else set(),
            shown_this_session=set(),
            popup_open=False,
            dialog_open=False,
        )
        if acao != lwd.DECISION_PROMPT:
            return "", ""
    return f"<b>{_texto(JOGO_ABERTO_SEM_O_ATALHO)}</b><br>", appid


#: `home_actions.wrapper_banner_text` (e a dispensa, e o modo). Muda só o que se
JOGO_ABERTO_SEM_O_ATALHO = "Jogo aberto sem o atalho"


def calados(lida: desenho.Leitura | None) -> set[str]:
    """Os appids sobre os quais ela JÁ RESPONDEU — as duas recusas juntas."""
    if lida is None:
        return set()
    return ({a for a, _ in lida.dispensados} | {a for a, _ in lida.recusados})


#: `tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py`: `hefesto-launch` só
#: CARONA (`perfil.com_a_carona`, que o Salvar e o Aplicar já chamam), e quem a


def com_o_que_o_daemon_diz(
    lancadores: list[desenho.Lancador],
    state: dict[str, Any] | None,
    lida: desenho.Leitura | None,
) -> list[desenho.Lancador]:
    """O cartão da Steam com o AVISO VIVO do jogo aberto — e só ele.

    O RÓTULO DO JOGO ABERTO SEM O ATALHO é a única coisa que o produto vivo
    acrescenta ao cartão: a decisão de acender é de
    `home_actions.wrapper_banner_text`, e o texto é
    :data:`JOGO_ABERTO_SEM_O_ATALHO` (ver :func:`aviso_do_jogo_aberto`).

    OS BOTÕES SAÍRAM DAQUI — 21/09/2026,  Esta função pendurava no
    cartão da Steam o «Não perguntar para este jogo», o «Posso fechar a Steam
    por uns 20 segundos?», o «Desligar o Steam Input» e o «Deixar tudo
    pronto» — botões que só ela tinha, e que faziam à mão o que o produto já faz
    sozinho: o vigia repõe o atalho e o guarda desliga o Steam Input
    (`hefesto-steam-input-guard`, a cada 30 min e a cada escrita da Steam). O
    jogo que ela não quer com o Hefesto vai para a lista de exclusão, que é o
    «não mexa neste jogo» inteiro.

    POR QUE AQUI E NÃO NO DESENHO: `dataclasses.replace` sobre o cartão que o
    desenho montou mantém UM dono para a forma do cartão.
    """
    if not lancadores:
        return lancadores
    steam = lancadores[0]
    cabeca, _appid = aviso_do_jogo_aberto(state, lida)
    if cabeca == "":
        return lancadores
    fora = list(lancadores)
    fora[0] = dataclasses.replace(steam, diz=cabeca + steam.diz)
    return fora


def _texto(x: object) -> str:
    """Escapa para posição de TEXTO, com a aspa CRUA — como o desenho faz."""
    return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# `mesa_viva.texto_da_contagem` é quem escreve o cabeçalho, e a régua daquela


@dataclasses.dataclass
class _Escolha:
    """Qual cartão abriu a escolha do jogo, e para quê."""

    modo: str = ""
    lancador: str = ""
    miolo: str = ""
    jogos: tuple[desenho.JogoParaEscolher, ...] = ()
    janelas: dict[str, tuple[str, ...]] = dataclasses.field(default_factory=dict)

    def limpar(self) -> None:
        self.modo = self.lancador = self.miolo = ""
        self.jogos = ()
        self.janelas = {}


_ESCOLHA = _Escolha()

_JANELAS_MEDIDAS: dict[str, tuple[str, ...]] = {
    "retroarch": ("com.libretro.RetroArch",),
}

_COM_BIBLIOTECA = ("heroic", "lutris")
_SEM_JOGOS = ("flatpak",)


def _chave_do_emulador(lancador: str) -> str:
    return f"emulador:{lancador}"


def _jogos_para_escolher(
    lancador: str, nome: str, state: dict[str, Any] | None,
) -> tuple[list[desenho.JogoParaEscolher], dict[str, tuple[str, ...]], bool]:
    """``(jogos, janelas por chave, é emulador)`` — a lista DAQUELE lançador.

    Só entra jogo com CHAVE DE JANELA: uma linha que nunca casa com janela
    nenhuma é pior que nenhuma (a regra da LANCADOR-AGNOSTICO-01). O jogo da
    escada (o aberto, ou o último) nasce marcado (D-2109-O-JOGO-SE-ESCOLHE-NA-
    LISTA). Nunca levanta: é chamado de dentro de um clique.
    """
    appid, _quando = a_escada_do_jogo(state)
    marcado = f"steam_app_{appid}" if appid is not None else ""
    ja = {e.chave for e in lista_de_exclusao.ler()}
    jogos: list[desenho.JogoParaEscolher] = []
    try:
        if lancador == desenho.STEAM:
            from hefesto_dualsense4unix.integrations import proton_pin
            from hefesto_dualsense4unix.integrations import steam_launch_options as slo

            for numero in proton_pin.list_installed_appids():
                chave = f"steam_app_{numero}"
                jogos.append(desenho.JogoParaEscolher(
                    chave=chave, nome=slo.nome_do_appid(numero) or f"appid {numero}",
                    marcado=chave == marcado))
        elif lancador in _COM_BIBLIOTECA:
            from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

            for jogo in censo.biblioteca_do_cartao(lancador).jogos:
                chave = jogo.classe_de_janela
                if chave and not jogo.e_acessorio:
                    jogos.append(desenho.JogoParaEscolher(
                        chave=chave, nome=jogo.nome, instalado=bool(jogo.instalado),
                        marcado=chave == marcado))
        elif lancador not in _SEM_JOGOS:
            chave = _chave_do_emulador(lancador)
            item = next((x for x in desenho.procurados(_declarados())
                         if x.chave == lancador), None)
            janelas = tuple(dict.fromkeys(
                (*(item.atalhos if item else ()), *(item.comandos if item else ()),
                 *_JANELAS_MEDIDAS.get(lancador, ()))))
            linha = desenho.JogoParaEscolher(
                chave=chave, nome=f"{nome} — todos os jogos", marcado=True)
            return ([] if chave in ja else [linha]), {chave: janelas}, True
    except Exception:
        logging.getLogger(__name__).debug("lista_da_escolha_falhou", exc_info=True)
    jogos = [j for j in jogos if j.chave not in ja]
    jogos.sort(key=lambda j: (not j.marcado, not j.instalado, j.nome.casefold()))
    return jogos, {}, False


def _abrir_a_escolha(modo: str, lancador: str, state: dict[str, Any] | None) -> None:
    """Monta a lista do cartão clicado e o miolo da pop-up. Nunca levanta."""
    lida = VIGIA.agora()
    nomes = {x.chave: x.nome for x in desenho.cartoes(lida)}
    nome = nomes.get(lancador, lancador)
    jogos, janelas, emulador = _jogos_para_escolher(lancador, nome, state)
    _ESCOLHA.modo, _ESCOLHA.lancador = modo, lancador
    _ESCOLHA.jogos, _ESCOLHA.janelas = tuple(jogos), janelas
    _ESCOLHA.miolo = desenho.miolo_da_escolha_html(
        modo, nome, jogos, emulador=emulador)


def _o_escolhido(o: dict[str, Any]) -> desenho.JogoParaEscolher:
    """O jogo que ela marcou na pop-up — ou a recusa, dita."""
    forma = o.get("forma") or {}
    chave = str(forma.get(desenho.ESCOLHA) or "").strip()
    jogo = next((j for j in _ESCOLHA.jogos if j.chave == chave), None)
    if jogo is None:
        raise RuntimeError("Escolha um jogo da lista antes de confirmar.")
    return jogo


def com_a_exclusao(
    lancadores: list[desenho.Lancador], lida: desenho.Leitura | None,
) -> list[desenho.Lancador]:
    """O rodapé da exclusão nos cartões LOCALIZADOS, e a lista da Steam sem eles.

    O PÉ DO CARTÃO diz os jogos DAQUELE lançador que estão na lista, cada um com
    o seu «Tirar da lista». Só onde há o botão de excluir (um cartão que não
    achou o lançador não tem o que excluir), e SÓ COM JOGO NA LISTA: a frase do
    vazio saiu em 21/09/2026

    A LISTA DA STEAM PERDE OS EXCLUÍDOS. A exclusão escreve no
    `jogos_sem_wrapper.txt`, e a lista do cartão mostra esse arquivo como
    «você tirou», com um «Voltar a usar» que desfaria SÓ o atalho — metade da
    exclusão, que é tudo-ou-nada. O jogo excluído aparece num lugar só: aqui.
    """
    try:
        entradas = lista_de_exclusao.ler()
    except Exception:
        entradas = []
    por_cartao: dict[str, list[tuple[str, str]]] = {}
    for e in entradas:
        por_cartao.setdefault(e.lancador, []).append((e.chave, e.nome))
    appids_fora = {
        a for a in (lista_de_exclusao.appid_da_chave(e.chave) for e in entradas
                    if "atalho" in e.escritas) if a}
    saida: list[desenho.Lancador] = []
    for lanc in lancadores:
        steam = lanc.chave == desenho.STEAM and lida is not None
        if (not any(a.gesto == desenho.EXCLUIR for a in lanc.acoes)
                or not (por_cartao.get(lanc.chave) or (steam and appids_fora))):
            saida.append(lanc)
            continue
        fora = rodape = desenho.rodape_da_exclusao_html(por_cartao.get(lanc.chave, []))
        if steam and lida is not None:
            filtrada = dataclasses.replace(
                lida, recusados=tuple(r for r in lida.recusados if r[0] not in appids_fora))
            lista = desenho.lista_de_jogos(filtrada)
            if (desenho.LISTA_VAZIA not in lista and lista.strip()) or not rodape:
                fora = lista + rodape
        saida.append(dataclasses.replace(lanc, fora=fora, tem_lista=True))
    return saida


def _relatar(gesto_: str, frase: str) -> None:
    """O recibo de um gesto da exclusão, no diário — a tela mostra o cartão."""
    print(f"[relato] {PAGINA} · {gesto_}: {frase}", file=sys.stderr)


def _pintura(lancadores: list[desenho.Lancador]) -> dict[str, Any]:
    """A carga da aba: os endereços **e a grade inteira**, com as molduras."""
    quem = {x.chave: x.nome for x in lancadores}
    valores = desenho.Quadro(lancadores=lancadores).valores()
    valores[desenho.NOVO_PARA_QUEM] = (
        desenho.NOVO_PARA_O_CARTAO.format(nome=quem[_PARA_QUEM])
        if _PARA_QUEM in quem else desenho.NOVO_SEM_ALVO)
    blocos = {desenho.SELETOR_DA_GRADE: desenho.cartoes_html(lancadores)}
    if _ESCOLHA.miolo:
        blocos[f"#{desenho.MIOLO_DA_ESCOLHA}"] = _ESCOLHA.miolo
    return {"mesa": valores, "blocos": blocos}


def _resposta(lida: desenho.Leitura | None,
              state: dict[str, Any] | None = None) -> dict[str, Any]:
    """O que um gesto devolve para a tela — a mesma carga da pintura."""
    return _pintura(com_a_exclusao(
        com_o_que_o_daemon_diz(desenho.cartoes(lida), state, lida), lida))


@registrar("07-lancadores.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    """A aba inteira, e ela NÃO depende de controle nenhum."""
    carga = _resposta(VIGIA.agora(), ctx.state)
    valores = carga["mesa"]
    # ajuda; a de 03/09 deu-lhe endereço e alimentou-o da mesa VIVA. Agora a
    fora: dict[str, Any] = dict(valores)
    fora["blocos"] = dict(carga["blocos"])
    fora["sem_dono"] = {k: {"sem_dono": True, "oque": v} for k, v in SEM_DONO.items()}
    fora["cobertura"] = {"pintados": len(valores), "sem_dono": len(SEM_DONO)}
    return fora


# `jogos_sem_wrapper.txt`, dois arquivos em disco. O inventário do daemon
from . import gesto  # noqa: E402


@gesto("07-lancadores.html", "procurar")
def procurar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Procurar de novo": esquece o cache e relê o disco AGORA."""
    VIGIA.esquecer()
    return _resposta(VIGIA.ler(), ctx.state)


# `tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py`.
# Steam a casa já honrou isso (`perfil.com_a_carona`, chamada pelo «Aplicar» e


def _com_outra_frase(diz: str,
                     state: dict[str, Any] | None = None) -> dict[str, Any]:
    """A aba de novo, com o corpo do cartão da Steam trocado."""
    lida = VIGIA.agora()
    cartoes = com_o_que_o_daemon_diz(desenho.cartoes(lida), state, lida)
    cartoes[0] = dataclasses.replace(cartoes[0], diz=diz)
    return _pintura(cartoes)


FECHADO = "fechado"
ABERTO = "aberto"


def a_escada_do_jogo(state: dict[str, Any] | None) -> tuple[int | None, str]:
    """`(appid, "aberto"|"fechado")` — as TRÊS evidências da GTK, nesta ordem.

    ELA É A DA JANELA VELHA, e a ordem vem de lá: `daemon_actions`
    (`_appid_do_jogo_ativo`) já respondia esta pergunta com as três, da mais
    forte para a mais tolerante, e a interface nova usava UMA.

    1. `launch_env.launch_session_appid()` — jogo lançado PELO wrapper e ainda
       vivo (marker no disco + pid vivo). Autoritativa e imune a alt-tab, que é
       exatamente o que acontece aqui: para clicar nesta aba ela SAI do jogo;
    2. `window_detect_last_class` do estado do daemon, traduzida pelo
       `extract_steam_appid` do lembrete. Cobre o jogo aberto SEM o wrapper —
       o que a primeira, por construção, não alcança;
    3. o marker `last_run` cru — o ÚLTIMO jogo lançado pelo wrapper, **mesmo já
       fechado**. É o caso que a GTK documenta com todas as letras: *"o jogo
       não funcionou, ela fechou, e só então veio reclamar"*.

    O QUE ISTO CURA, medido em 03/09/2026: o `detectar` usava só
    `steam_game_running_appid()`, que exige o jogo RODANDO enquanto ela clica na
    janela do Hefesto — justamente o momento em que ela saiu do jogo. Não era
    que ele não detectasse: ele detectava pior, e falhava no caso comum.

    A ESCADA É DAQUI E O ESTADO VEM DE FORA: a GTK faz uma chamada de IPC no
    degrau 2 (`daemon_state_full()`); aqui o `state` já chegou pelo `Contexto`,
    então o degrau sai de graça. Um IPC dentro de um gesto de tela seria uma
    segunda ida ao daemon para saber o que a janela acabou de receber.

    NUNCA LEVANTA — os três degraus leem disco, e disco falha. Um degrau que
    explode não pode comer os outros dois: cada um vai no seu `try`, como a GTK
    faz com o `contextlib.suppress`.
    """
    from hefesto_dualsense4unix.daemon.launch_env import (
        launch_session_appid,
        read_last_run_marker,
    )

    try:
        vivo = launch_session_appid()
        if vivo is not None:
            return vivo, ABERTO
    except Exception:  # pragma: no cover - marker ilegível
        pass
    foco = _o_jogo_em_foco(state)
    if foco:
        try:
            return int(foco), ABERTO
        except ValueError:  # pragma: no cover - `extract_steam_appid` já filtra
            pass
    try:
        marker = read_last_run_marker()
        if marker is not None:
            return marker[0], FECHADO
    except Exception:  # pragma: no cover - marker ilegível
        pass
    return None, FECHADO


@gesto("07-lancadores.html", "detectar")
def detectar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Detectar o jogo que está aberto": diz QUAL é, ou recusa dizendo."""
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    appid, quando = a_escada_do_jogo(ctx.state)
    if appid is None:
        raise RuntimeError(
            "Nenhum jogo aberto agora. Abra o jogo, volte aqui e clique de "
            "novo.")
    lida = VIGIA.agora()
    if lida is None:
        lida = VIGIA.ler()
    tem = str(appid) in lida.com_wrapper
    nome = f"<b>{desenho._e(slo.rotulo_do_jogo(appid))}</b>"
    abertura = (f"{nome} está aberto agora e " if quando == ABERTO else
                f"{nome} foi o último jogo que passou pelo atalho do Hefesto, e "
                "já fechou. Ele ")
    return _com_outra_frase(
        abertura
        + ("<b>abre pelo atalho do Hefesto</b>." if tem else
           "<b>não abre pelo atalho do Hefesto</b>"
           + _quem_repoe_o_atalho(lida, appid)), ctx.state)


REPOE_QUANDO_A_STEAM_FECHAR = " — o atalho volta quando a Steam fechar."


def _quem_repoe_o_atalho(lida: desenho.Leitura | None, appid: int) -> str:
    """O fim da frase do jogo sem o atalho — a promessa só quando há quem a cumpra.

    A PROMESSA É SÓ PARA O REPARÁVEL (`Leitura.reparaveis`, da mesma passada do
    censo que a sentinela usa): o jogo que ELA tirou (`recusados`, o
    `jogos_sem_wrapper.txt`) ou o intocável fica sem o atalho de propósito, e
    prometer que ele volta seria a tela afirmando o que ninguém vai fazer.
    Sem leitura ainda (`None`), também não se promete — o ponto final basta.
    """
    if lida is not None and str(appid) in {a for a, _r, _p in lida.reparaveis}:
        return REPOE_QUANDO_A_STEAM_FECHAR
    return "."


def _appid_do_clique(o: dict[str, Any], nome: str) -> str:
    """O appid que o botão da linha mandou. Vazio é RECUSA, nunca palpite."""
    appid = str(o.get("v") or "").strip()
    if not appid:
        _LOG.warning(
            "%s: clique sem `data-v`. Cada linha da lista manda o appid ali — "
            "se ele sumiu do desenho, o botão agiria sobre um jogo escolhido "
            "por acaso.", nome)
        raise ValueError(
            "O clique não disse de qual jogo se trata. Nada foi alterado.")
    return appid


@gesto("07-lancadores.html", "tirar-daqui", grava="marcar_jogo_sem_wrapper")
def tirar_daqui(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Não usar neste jogo": põe o appid no `jogos_sem_wrapper.txt`.

    É A RECUSA DO USUÁRIO, e o produto inteiro a respeita: `censo_do_wrapper` pula
    quem está nessa lista, e `apply_wrapper_to_all_games` a recebe em
    `excluir=`. Sem este botão, a única forma de tirar um jogo era editar o
    arquivo à mão — a lista existia sem NENHUMA tela que a escrevesse.
    """
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    slo.marcar_jogo_sem_wrapper(_appid_do_clique(o, "tirar-daqui"))
    VIGIA.esquecer()
    return _resposta(VIGIA.ler(), ctx.state)


@gesto("07-lancadores.html", "voltar-a-usar", grava="desmarcar_jogo_sem_wrapper")
def voltar_a_usar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Voltar a usar": tira o appid do `jogos_sem_wrapper.txt`.

    O par do de cima, e ele precisa existir pelo mesmo motivo que o "Automático"
    da Iluminação precisa existir: um gesto que só vai numa direção deixa a
    pessoa presa no estado em que clicou.
    """
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    slo.desmarcar_jogo_sem_wrapper(_appid_do_clique(o, "voltar-a-usar"))
    VIGIA.esquecer()
    return _resposta(VIGIA.ler(), ctx.state)


@gesto("07-lancadores.html", "voltar-a-perguntar", grava="remove_dismissed_appid")
def voltar_a_perguntar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Voltar a perguntar": tira o appid do `launch_dialog_dismissed.json`.

    O DESFAZER QUE NÃO EXISTIA, e a falta era de MOTOR e não de tela: até hoje
    `launch_wrapper_dialog` só tinha `add_dismissed_appid`. Clicar em *"Não
    perguntar para este jogo"* no lembrete da GTK produzia um silêncio
    permanente, e desfazê-lo pedia editar um JSON à mão. Decisão,
    02/09/2026 — nasce o par, e o botão é este.

    A RECUSA VAI PARA A TELA, e é por isso que `remove_dismissed_appid` devolve
    `bool` em vez de engolir como o `add`: se o arquivo não deu para reescrever,
    a linha continuaria na lista e o segundo clique pareceria o primeiro — o
    botão que aceita o clique e não faz nada.
    """
    from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as lwd

    appid = _appid_do_clique(o, "voltar-a-perguntar")
    if not lwd.remove_dismissed_appid(appid):
        raise RuntimeError(
            "Não consegui voltar a perguntar por este jogo — o lembrete "
            "continua desligado.")
    VIGIA.esquecer()
    return _resposta(VIGIA.ler(), ctx.state)


@gesto("07-lancadores.html", desenho.ABRIR,
       grava="abre a janela da Steam por cima do que ela está fazendo")
def abrir_lancador(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Abrir o lançador": abre a Steam. Nos outros cinco, RECUSA dizendo.

    DECISÃO 17 DO USUÁRIO, 03/09/2026: o botão LIGA, e o gesto entra em
    `hefesto_vivo.PERIGOSOS` — as duas metades, e a segunda não é opcional. Sem
    ela a `--prova-gesto` clicaria este botão e abriria a Steam na tela do usuário,
    que é o oposto de toda janela desta casa nascer `--oculta`.

    O FATO QUE CAIU, e ele estava escrito no próprio arquivo:
    `SEM_DONO["abrir-lancador"]` dizia *"o daemon não tem método para isso"*.
    É verdade e é a **pergunta errada**. Medido em 03/09/2026:
    o inventário do daemon (hoje `tests/unit/inventario_do_daemon.metodos()`)
    tinha **40 métodos**, e o único cujo nome sequer
    sugere abrir algo é `launch_env.refresh` — que regrava o arquivo de
    ambiente de inicialização e não abre janela nenhuma. O IPC de fato não sabe
    abrir a Steam; **o produto sabe**, desde 23/08 e por outro caminho:
    `steam_launch_options.reopen_steam`, função PÚBLICA, com os
    dois caminhos já provados (o binário `steam` e o `xdg-open steam://open/main`
    de quem a instalou por Flatpak ou Snap). Ela tinha **zero chamadores vindos
    de `interface/`** — é a `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` na forma mais
    literal: a casa sabe, e o botão da tela não chamava.

    OS CINCO QUE FICARAM DE FORA, e por quê. `reopen_steam` é da Steam e não
    tem irmã: **não existe no produto uma função que abra o Heroic, o Lutris, o
    RetroArch, o Dolphin ou o mGBA** — e o Flatpak nem aplicativo é (a
    `SemCenso` dele o diz: *"ele não publica atalho próprio, só o comando"*;
    rodar `/usr/bin/flatpak` sem argumento imprime ajuda num terminal que
    ninguém vê). O produto sabe ONDE eles estão (`_onde_estao_os_lancadores`
    devolve o caminho inteiro) e **não sabe abri-los**: lançar um `.desktop`
    exige ler o `Exec=` com os códigos de campo, ou um `Gio.DesktopAppInfo`,
    e isso é capacidade NOVA — não é ligar o que já existe. Está em
    `espera_a_palavra_dela`.

    RECUSAR É MELHOR QUE CALAR, e é a razão de o gesto valer nos SEIS. Até hoje
    o botão dos cinco não tinha `data-gesto`: o ouvinte do piloto não o
    reconhecia, o clique não chegava ao Python, e **nada acontecia** — nem na
    tela, nem no terminal. É o *"botão que responde calado"* que o próprio
    `SEM_DONO` chamava de pior que a recusa. Agora o clique chega, e a frase
    diz o que o produto sabe e o que não sabe.
    """
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    qual = str(o.get("v") or "").strip()
    if not qual:
        _LOG.warning(
            "abrir-lancador: clique sem `data-v`. Cada botão manda a chave do "
            "cartão ali — sem ela o gesto abriria um lançador escolhido por "
            "acaso.")
        raise ValueError(
            "O clique não disse de qual lançador se trata. Nada foi alterado.")
    if qual != desenho.STEAM:
        nomes = {x.chave: x.nome for x in desenho.SEM_FONTE}
        raise RuntimeError(
            f"Abra o {nomes.get(qual, qual)} como você já abre — o perfil "
            "entra do mesmo jeito, pelo nome do processo e pela janela.")
    if not slo.reopen_steam():
        raise RuntimeError(
            "Não achei como abrir a Steam nesta máquina. Abra-a pelo seu "
            "menu — nada foi alterado.")
    return None


@gesto("07-lancadores.html", desenho.EXCLUIR)
def abrir_a_exclusao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Adicionar à lista de exclusão»: abre a escolha do jogo DAQUELE lançador."""
    _abrir_a_escolha(desenho.EXCLUIR, str(o.get("v") or ""), ctx.state)
    return _resposta(VIGIA.agora(), ctx.state)


@gesto("07-lancadores.html", desenho.CRIAR_PERFIL)
def abrir_o_criar_perfil(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Criar perfil para um jogo»: a mesma escolha, no modo do perfil."""
    _abrir_a_escolha(desenho.CRIAR_PERFIL, str(o.get("v") or ""), ctx.state)
    return _resposta(VIGIA.agora(), ctx.state)


@gesto("07-lancadores.html", desenho.CONFIRMAR_EXCLUSAO, grava="adicionar")
def confirmar_a_exclusao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """Põe o jogo marcado na lista e tira dele, agora, o que o Hefesto pôs no disco."""
    jogo = _o_escolhido(o)
    status = lista_de_exclusao.adicionar(
        jogo.chave, lancador=_ESCOLHA.lancador, nome=jogo.nome,
        janelas=_ESCOLHA.janelas.get(jogo.chave, ()))
    if status in ("erro", "chave_invalida"):
        raise RuntimeError(
            "Não consegui gravar a lista de exclusão — o arquivo está ilegível "
            "ou a pasta de configuração não aceita escrita.")
    disco = lista_de_exclusao.tirar_do_disco(jogo.chave)
    _relatar(desenho.CONFIRMAR_EXCLUSAO,
             f"{jogo.nome}: {status}; no disco: {disco}")
    _ESCOLHA.limpar()
    VIGIA.esquecer()
    return _resposta(VIGIA.ler(), ctx.state)


@gesto("07-lancadores.html", desenho.TIRAR_DA_EXCLUSAO, grava="tirar")
def tirar_da_exclusao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Tirar da lista»: o jogo volta ao Hefesto."""
    chave = str(o.get("v") or "").strip()
    status = lista_de_exclusao.tirar(chave)
    if status == "erro":
        raise RuntimeError("Não consegui tirar o jogo da lista de exclusão.")
    _relatar(desenho.TIRAR_DA_EXCLUSAO, f"{chave}: {status}")
    VIGIA.esquecer()
    return _resposta(VIGIA.ler(), ctx.state)


@gesto("07-lancadores.html", desenho.CONFIRMAR_PERFIL, grava="criar_para_o_jogo")
def confirmar_o_perfil(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """Cria o perfil do jogo marcado PELA ABA PERFIS, e a tela vai para lá."""
    from . import a10_perfis

    jogo = _o_escolhido(o)
    janelas = _ESCOLHA.janelas.get(jogo.chave, ())
    classes = janelas if janelas else (jogo.chave,)
    frase = a10_perfis.criar_para_o_jogo(
        ctx, p, classes=classes, nome_do_jogo=jogo.nome.split(" — ")[0])
    _relatar(desenho.CONFIRMAR_PERFIL, frase)
    _ESCOLHA.limpar()
    return _resposta(VIGIA.agora(), ctx.state)


_PARA_QUEM = ""

_MAXIMO_DA_AGULHA = 240


def _sem_acento(texto: str) -> str:
    """`Ryujinx à Solta` → `ryujinx a solta`. Só para fabricar a CHAVE."""
    import unicodedata

    cru = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in cru if not unicodedata.combining(c)).lower()


def chave_do_rotulo(rotulo: str) -> str:
    """A chave de um lançador novo, a partir do nome que ELA deu.

    ELA VIRA ATRIBUTO DE HTML (`data-lancador`, e o prefixo de todo `data-campo`
    do cartão), então a forma é a que `maquina._CHAVE_DE_LANCADOR` cobra:
    minúscula, sem acento, sem espaço. Fabricá-la aqui é o que poupa ELA de
    digitar um identificador — o que a tela pede é o NOME.

    DEVOLVE `""` QUANDO NÃO SOBRA NADA (um rótulo só de pontuação), e quem chama
    recusa dizendo. Fabricar uma chave de um nome que não tem letra nem número
    daria um cartão endereçado por acaso.
    """
    limpo = re.sub(r"[^a-z0-9]+", "-", _sem_acento(rotulo)).strip("-")
    return limpo[:32].strip("-")


def onde_isso_esta(alvo: str) -> tuple[str, str, str]:
    """O que o usuário digitou, resolvido no disco: `(campo, agulha, onde)`."""
    import shutil

    from hefesto_dualsense4unix.integrations import jogos_locais as jl

    stem = alvo[:-len(".desktop")] if alvo.endswith(".desktop") else alvo
    nu = stem.rsplit("/", 1)[-1]
    if nu:
        try:
            pastas = jl.pastas_de_atalhos()
        except Exception:  # pragma: no cover - pastas ilegíveis
            pastas = []
        for pasta in pastas:
            try:
                caminho = pasta / f"{nu}.desktop"
                if caminho.is_file():
                    return "atalhos", nu, str(caminho)
            except OSError:  # pragma: no cover - pasta sumiu no meio
                continue

    try:
        achado = shutil.which(alvo)
    except Exception:  # pragma: no cover - PATH torto
        achado = None
    if achado:
        return "comandos", alvo, achado
    return "", "", ""


def _botoes_do_cartao_agora(chave: str) -> tuple[str, ...]:
    """Os rótulos que o cartão de `chave` mostra NESTE instante."""
    try:
        lida = VIGIA.agora()
        for cartao in desenho.cartoes(lida):
            if cartao.chave == chave:
                return tuple(a.rotulo for a in cartao.acoes)
    except Exception:
        return ()
    return ()


def _recusa_de_quem_ja_tem_cartao(chave: str, nome: str,
                                  tem: tuple[str, ...] | None = None) -> str:
    """A recusa do botão global para um lançador que já tem cartão de fábrica."""
    if tem is None:
        tem = _botoes_do_cartao_agora(chave)
    abertura = f"{nome} já tem cartão nesta aba"

    for aponta in (desenho.ADICIONAR_ROTULO, desenho.APONTAR_ROTULO):
        if aponta in tem:
            return (f"{abertura}. Use o «{aponta}» do cartão dele — assim o "
                    f"que você disser entra na busca daquele cartão, em vez "
                    f"de criar um segundo.")

    tirar = desenho.acao_de_tirar(chave).rotulo
    if tirar in tem:
        return (f"{abertura}, e ele já está apontado. Use o «{tirar}» do "
                f"cartão dele primeiro — depois ele volta a perguntar onde "
                f"está.")

    return (f"{abertura} — o que você digitar aqui criaria um segundo com o "
            f"mesmo nome.")


def _o_que_ela_digitou(o: dict[str, Any]) -> tuple[str, str]:
    """`(rótulo, alvo)` da tela de registro, já aparados."""
    forma = o.get("forma") or {}
    if not isinstance(forma, dict):
        forma = {}
    return (str(forma.get(desenho.NOVO_ROTULO) or "").strip(),
            str(forma.get(desenho.NOVO_ALVO) or "").strip())


@gesto("07-lancadores.html", desenho.ADICIONAR, grava="machine_declare")
def adicionar_lancador(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Localizar este Lançador» — ela diz ONDE ele está, e o cartão acende.

    ELE NÃO INSTALA NADA, e o cartão já explicava por quê antes de este gesto
    existir: *"Instalado de outro jeito (um AppImage solto, por exemplo) ele não
    aparece aqui"*. O que faltava não era o programa — era o produto saber onde
    procurá-lo. Ver :data:`desenho.ADICIONAR_ROTULO`.

    **AS DUAS METADES.** Sem `forma`, o clique é o do botão de um cartão: ele só
    aponta a tela para aquele cartão e devolve a aba repintada, com a linha de
    cima dizendo de quem se trata. Com `forma`, é o «Adicionar» da tela — e é
    aqui que se grava.

    **NÃO GRAVA O QUE NÃO ESTÁ NO DISCO**, e esta é a regra que mais importa:
    :func:`onde_isso_esta` procura antes, com as MESMAS duas buscas do
    procurador. Se não acha, o gesto recusa dizendo o que procurou. Um declarado
    que a busca nunca acha é um cartão «NÃO LOCALIZADO» permanente — a tela
    mentindo sobre uma coisa que ela mesma declarou.

    **A CHAVE REPETIDA ENSINA, NÃO DUPLICA** (ver :func:`desenho.procurados`).
    Pelo botão de um cartão isso é o ato inteiro. Pelo botão GLOBAL não é: ali
    ela quis um lançador NOVO, e um nome que por acaso caia sobre um cartão de
    fábrica faria o rótulo dela ser descartado em silêncio. Esse caso recusa
    dizendo qual cartão já responde por aquele nome.

    O `machine.declare` E NÃO UMA ESCRITA DAQUI: o `maquina.json` tem UM
    escritor (`_handle_machine_declare`), e o lock dele é de PROCESSO. Uma
    segunda escrita viva noutro processo perde a declaração de quem gravou
    primeiro, sem uma linha de erro.
    """
    global _PARA_QUEM

    rotulo, alvo = _o_que_ela_digitou(o)
    if not o.get("forma"):
        _PARA_QUEM = str(o.get("v") or "").strip()
        return _resposta(VIGIA.agora(), ctx.state)

    if not alvo:
        raise ValueError(
            "Diga onde ele está — os exemplos estão no campo. Ou clique em "
            f"«{desenho.PROCURAR_O_ARQUIVO_ROTULO}» e aponte com o mouse.")
    if len(alvo) > _MAXIMO_DA_AGULHA:
        raise ValueError(
            f"São {len(alvo)} caracteres, e o teto é {_MAXIMO_DA_AGULHA}. Diga "
            "só o comando ou o nome do atalho.")
    # chama `VIGIA.esquecer()`, e num `{**_resposta(VIGIA.ler(), …), "recado":
    recado = _guardar_onde_ele_esta(p, rotulo, alvo, _achar_o_que_ela_digitou)
    return {**_resposta(VIGIA.ler(), ctx.state), "recado": recado}


def _achar_o_que_ela_digitou(alvo: str) -> tuple[str, str, str]:
    """`onde_isso_esta`, e a RECUSA na língua de quem DIGITOU."""
    achado = onde_isso_esta(alvo)
    if not achado[0]:
        raise RuntimeError(
            f"Não achei {alvo!r} nesta máquina. Procurei o comando no `PATH` e "
            f"o atalho `{alvo.rsplit('/', 1)[-1]}.desktop` nas pastas de "
            f"aplicativos. Confira e tente de novo; nada foi guardado.")
    return achado


def _guardar_onde_ele_esta(p: Any, rotulo: str, alvo: str,
                           achar: Callable[[str], tuple[str, str, str]]) -> str:
    """Grava a agulha no `maquina.json` e devolve o RECIBO. Dono único da escrita."""
    global _PARA_QUEM

    para_quem = _PARA_QUEM
    de_fabrica = {x.chave: x.nome for x in desenho.EMBUTIDOS}

    chave = para_quem or chave_do_rotulo(rotulo)
    if not chave:
        raise ValueError(
            "Diga como ele se chama — é o nome que aparece no topo do cartão.")
    if not para_quem and chave in de_fabrica:
        raise RuntimeError(_recusa_de_quem_ja_tem_cartao(chave, de_fabrica[chave]))

    campo, agulha, onde = achar(alvo)

    de_hoje = {x.chave: x.nome for x in desenho.procurados(_declarados())}
    ok, motivo = _ok_e_motivo(p.machine_declare({"lancadores": {
        chave: {"rotulo": de_hoje.get(chave) or rotulo or chave,
                campo: [agulha]}}}))
    if not ok:
        raise RuntimeError(
            motivo or "Não consegui guardar isso agora. Nada foi alterado.")

    _PARA_QUEM = ""
    VIGIA.esquecer()
    nome = de_fabrica.get(chave) if para_quem else rotulo
    recado = f"Guardei: {nome or chave} está em {onde}."

    if para_quem and rotulo and nome and rotulo.strip().casefold() != nome.casefold():
        recado += (f" O nome «{rotulo.strip()}» não entrou: este cartão já se "
                   f"chama {nome}, e o botão dele só acrescenta onde procurar.")

    return recado


def _pasta_de_partida() -> str:
    """A primeira pasta de atalhos que existe, ou `""`. NUNCA levanta."""
    from hefesto_dualsense4unix.integrations import jogos_locais as jl

    try:
        for pasta in jl.pastas_de_atalhos():
            if pasta.is_dir():
                return str(pasta)
    except Exception:  # pragma: no cover - pastas ilegíveis
        return ""
    return ""


TITULO_DO_SELETOR = "Escolha o atalho do lançador (.desktop)"


def _achar_o_que_ela_apontou(alvo: str) -> tuple[str, str, str]:
    """`onde_isso_esta`, e a RECUSA na língua de quem APONTOU um arquivo.

    **A RECUSA É OUTRA, e a diferença é medida.** Quem digitou errou o comando
    ou o nome do atalho, e a frase manda conferir os dois. Quem apontou com o
    mouse acertou o arquivo — o que ele pode ter errado é a PASTA: o produto só
    reencontra um `.desktop` que esteja numa das quatro pastas de aplicativos
    (`jogos_locais.pastas_de_atalhos`), e mandar a frase do teclado aqui seria
    dizer *"confira o caminho"* sobre um caminho que o usuário apontou com o dedo.

    **E A RECUSA ESTÁ CERTA, não é aspereza:** um atalho fora das quatro pastas
    é um lançador que a busca nunca acharia — o cartão diria «NÃO LOCALIZADO»
    para sempre sobre uma coisa que ela mesma acabou de apontar. É a mesma regra
    de `onde_isso_esta`: *não se grava o que não está no disco onde o produto
    procura*.
    """
    achado = onde_isso_esta(alvo)
    if not achado[0]:
        pastas = ", ".join(str(x) for x in _pastas_de_atalhos_para_a_frase())
        raise RuntimeError(
            f"Este arquivo está fora das pastas em que eu procuro, e eu não o "
            f"reencontraria: {alvo}. Escolha um atalho de "
            f"{pastas or 'uma pasta de aplicativos'}. Nada foi guardado.")
    return achado


def _pastas_de_atalhos_para_a_frase() -> tuple[str, ...]:
    """As pastas que a recusa NOMEIA — lidas do dono, nunca digitadas."""
    from hefesto_dualsense4unix.integrations import jogos_locais as jl

    try:
        return tuple(str(x) for x in jl.pastas_de_atalhos())
    except Exception:  # pragma: no cover - pastas ilegíveis
        return ()


@gesto("07-lancadores.html", desenho.PROCURAR_O_ARQUIVO, grava="machine_declare")
def procurar_o_arquivo(ctx: Contexto, o: dict[str, Any], p: Any
                       ) -> dict[str, Any] | None:
    """«Escolher o arquivo…» — ela aponta o `.desktop` com o mouse.

    **DECISÃO, 09/09/2026, a opção (C):**  — o campo de
    texto FICA (é o único caminho para um AppImage solto, que não tem
    `.desktop`) e ganha ao lado o botão que abre o seletor do sistema.

    **NÃO É CAPACIDADE NOVA.** `ponte.escolher_arquivo` é um ponto de extensão
    que o piloto preenche ao subir, com precedente vivo no «Importar» do
    rodapé. O pacote continua PURO — quem importa GTK é o piloto —, e é por
    isso que a régua o prova com um dublê.

    **CANCELAR NÃO É ERRO NEM NOTÍCIA**, e o `None` explícito diz isso: ela
    fechou o diálogo, nada mudou, e a tela não fala. Um `RuntimeError` aqui
    acenderia a tarja laranja de 30 s por um clique que ela mesma desfez.

    **COM A JANELA OCULTA NÃO HÁ DIÁLOGO**, e é de propósito: uma
    `Gtk.OffscreenWindow` não tem onde pôr um modal, e abrir um sem pai o
    jogaria NA TELA DO USUÁRIO. O piloto devolve `None` e imprime no `stderr`, e este
    gesto o lê como "cancelou" — que é a leitura certa: nada foi escolhido.
    Logo a prova botão a botão (`--prova-gesto`) **não pode** exercitá-lo, e é
    por isso que ele declara `grava=` e entra em `pacotes.perigosos()` **pela
    derivação** — como o `importar` do rodapé já entra.

    **A GRAVAÇÃO É A MESMA DO «Adicionar»** (:func:`_guardar_onde_ele_esta`), e
    tem de ser: dois caminhos escrevendo o `maquina.json` cada um do seu jeito
    é como um deles esquece a colisão com cartão de fábrica. O que muda é só a
    frase de "não achei" — ver :func:`_achar_o_que_ela_apontou`.
    """
    caminho = p.escolher_arquivo(TITULO_DO_SELETOR, padrao="*.desktop",
                                 sugestao=_pasta_de_partida())
    if not caminho:
        return None
    rotulo, _digitado = _o_que_ela_digitou(o)
    recado = _guardar_onde_ele_esta(p, rotulo, str(caminho),
                                    _achar_o_que_ela_apontou)
    return {**_resposta(VIGIA.ler(), ctx.state), "recado": recado}


@gesto("07-lancadores.html", desenho.REMOVER, grava="machine_declare")
def esquecer_lancador(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Tirar daqui» — desfaz o que ela declarou sobre um lançador.

    *O QUE SE ACRESCENTA SE TIRA.* Sem isto a lista dela vira lixo permanente:
    um cartão acrescentado por engano ficaria na tela para sempre, e a única
    saída seria editar o `maquina.json` à mão — que é exatamente a forma de
    defeito que o `jogos_sem_wrapper.txt` tinha antes desta aba existir.

    NUM CARTÃO DE FÁBRICA ELE NÃO APAGA O CARTÃO: apaga o ENSINO. O cartão volta
    a ser procurado só pelos caminhos de fábrica, que é o estado anterior ao
    clique do usuário — e é por isso que o botão é o mesmo nos dois casos, e não dois.

    O DESFAZER É O `None`, e a língua é a que o `maquina.json` já fala — ver
    `MaquinaConfig._o_none_e_o_esquecimento`, que carrega a razão inteira:
    `machine.declare` não tem verbo de remoção, e mandar a lista MENOS uma chave
    não tira chave nenhuma.
    """
    qual = str(o.get("v") or "").strip()
    if not qual:
        _LOG.warning(
            "esquecer-lancador: clique sem `data-v`. Cada botão manda a chave "
            "do cartão ali — sem ela eu apagaria a declaração de um lançador "
            "escolhido por acaso.")
        raise ValueError(
            "O clique não disse de qual lançador se trata. Nada foi tirado.")
    declarados = {x.chave: x.nome for x in _declarados()}
    if qual not in declarados:
        raise RuntimeError(
            "Não há nada a tirar: este cartão é de fábrica e você não apontou "
            "nada nele.")

    ok, motivo = _ok_e_motivo(p.machine_declare({"lancadores": {qual: None}}))
    if not ok:
        raise RuntimeError(
            motivo or "Não consegui guardar isso agora. Nada foi alterado.")
    VIGIA.esquecer()
    return {**_resposta(VIGIA.ler(), ctx.state),
            "recado": f"Tirei {declarados[qual]} daqui."}


def _ok_e_motivo(resposta: Any) -> tuple[bool, str | None]:
    """`(ok, motivo)`, seja tupla ou `bool` o que a ponte devolveu."""
    if isinstance(resposta, tuple) and len(resposta) == 2:
        return bool(resposta[0]), resposta[1]
    return bool(resposta), None


METODO_DA_RECARGA = "launch_env.refresh"

#: o wrapper vive em dois arquivos em disco, e o `state_full` não tem UMA chave
# `machine_declare` ENTROU EM 08/09/2026 com o lançador declarado por ELA: é a
PONTE: set[str] = {"chamar", "machine_declare", "escolher_arquivo"}
METODOS: set[str] = {"machine.declare"}


PAGINA = "07-lancadores.html"
#: caminho para `with_steam_closed`, que a interface nova não tinha); e de
PISO_DA_ABA = 14

PROVAS: list[dict[str, Any]] = []

#: TODOS, e não por preguiça: o `state_full` do daemon não tem UMA chave sobre
SEM_ECO = ("procurar", "detectar",
           "tirar-daqui", "voltar-a-usar", "voltar-a-perguntar",
           "abrir-lancador",
           # `maquina.json`, e o `state_full` não tem UMA chave sobre a
           desenho.ADICIONAR, desenho.REMOVER,
           # — e o `state_full` não tem UMA chave sobre lançador. Quando ela
           desenho.PROCURAR_O_ARQUIVO)

# bloco «O «Consertar» DOS OUTROS LANÇADORES SAIU», logo abaixo de `calados`.
