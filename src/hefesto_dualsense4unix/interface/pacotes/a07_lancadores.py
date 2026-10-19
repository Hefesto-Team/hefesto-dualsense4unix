#!/usr/bin/env python3
"""O pacote da aba `07` Lançadores — a aba que era desenho inteiro.

A DECISÃO DE PRODUTO QUE ABRIU ESTA ABA, e ela CADUCOU outra, de um dia antes:

    01/09/2026 — *"a única que não faremos, só deixamos o botão levando pra
    ela, é a de lançadores."*

    02/09/2026 — *"não daria para incluir G e F aqui? (…) temos um mapa
    funcional disso no gtk. a estrutura sim, validar de fato eu poderia
    somente juntos com ele."*   <!-- noqa-acento: citação literal -->

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
    integrations/prontuario_dos_jogos.jogos_instalados   os `appmanifest` do disco
    integrations/prontuario_dos_jogos.pontes_confirmadas quem já sabe por onde entrar
    integrations/prontuario_dos_jogos.classes_com_ponte  o mesmo, para os outros
    integrations/lista_de_exclusao                       a lista de exclusão
    integrations/jogos_locais.pastas_de_atalhos          onde moram os `.desktop`
    integrations/steam_launch_options.WRAPPER_LAUNCH     a linha à mostra
    app/actions/launch_wrapper_dialog.load_dismissed_appids  quem ela dispensou
    app/actions/launch_wrapper_dialog.extract_steam_appid    o jogo em foco
    daemon/launch_env.launch_session_appid               1º degrau da escada
    daemon/launch_env.read_last_run_marker               3º degrau da escada

O REPARO SAIU DESTA ABA — 21/09/2026, palavra de produto: *"a ideia é termos os
mesmos botões pra todos os lançadores. sempre."* O «Consertar», o «Ver o que
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
dizendo *"Feche a Steam e eu reponho"*, e até 03/09 **nada reperguntava** — a
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

import contextlib
import dataclasses
import logging
import pathlib
import re
import sys
import threading
import time
from collections.abc import Callable, Sequence
from typing import Any

from hefesto_dualsense4unix.integrations import kits_de_brinquedo, lista_de_exclusao
from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
from hefesto_dualsense4unix.interface import desenho_dos_lancadores as desenho

from . import Contexto, perfil, registrar

#: `RuntimeError`/`ValueError` (`hefesto_vivo`), não a um terminal.
_LOG = logging.getLogger(__name__)

TTL_S = 20.0

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
        """Invalida o cache: a próxima pintura relê o disco."""
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
    """O que o usuário declarou no `maquina.json`, no molde do procurador."""
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
    ) + _achados_por_conteudo() + _das_modificacoes()


def _das_modificacoes(lugares: Any = None) -> tuple[desenho.SemCenso, ...]:
    """Os lançadores que as modificações LIGADAS trazem, no molde do procurador.

    Entra a modificação ligada cujo manifesto, conferido de novo aqui, tem o
    tipo ``lancador``, o bloco ``lancador`` e a permissão ``lancador`` que a
    pessoa aceitou. Desligou, o cartão sai na volta seguinte da vigia. Nunca
    levanta: um registro ilegível ou um bloco torto deixa só aquela de fora.
    """
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo
    from hefesto_dualsense4unix.mods.instalador import (
        InstalacaoRecusadaError,
        Lugares,
        ler_registro,
    )
    from hefesto_dualsense4unix.mods.manifesto import ManifestoRecusadoError, ler_manifesto

    try:
        lg = lugares or Lugares.do_xdg()
        registro = ler_registro(lg.registro)
    except (InstalacaoRecusadaError, OSError):
        _LOG.debug("registro_das_modificacoes_ilegivel", exc_info=True)
        return ()
    fora: list[desenho.SemCenso] = []
    for mod_id, entrada in sorted(registro.items()):
        if not entrada.ligada or "lancador" not in entrada.permissoes_aceitas:
            continue
        pasta = lg.codigo / mod_id
        try:
            manifesto = ler_manifesto(pasta)
            if ("lancador" not in manifesto.tipos or manifesto.lancador is None
                    or "lancador" not in manifesto.permissoes or manifesto.id != mod_id):
                continue
            bloco = censo.lancador_da_modificacao(mod_id, manifesto.lancador, pasta)
        except (ManifestoRecusadoError, ValueError):
            _LOG.debug("lancador_da_modificacao_recusado", exc_info=True)
            continue
        fora.append(desenho.SemCenso(
            chave=bloco.chave, nome=bloco.rotulo, atalhos=bloco.atalhos,
            comandos=bloco.comandos, janelas=bloco.janelas,
            titulo_do_jogo=bloco.titulo_do_jogo, leitor=bloco.leitor,
            modificacao=mod_id))
    return tuple(fora)


#: A classe de janela que o emulador anuncia, por CHAVE DE CARTÃO achado pelo `.desktop`.
#:
#: O cartão que o produto acha sozinho só sabe o nome do arquivo (`org.vita3k.vita3k`), e a janela
#: do Vita3K se anuncia pelo nome do executável (`Vita3K` no AppImage, `vita3k` no AUR): sem esta
#: linha a «todos os jogos» do emulador não casa janela nenhuma e o perfil nunca entra. A chave é a
#: do cartão (o `stem` em minúsculas, o ponto trocado por hífen), nunca o `stem`; a comparação do
#: perfil ignora a caixa, então uma grafia cobre as duas. **Derivado do fonte, ainda NÃO MEDIDO na
#: janela viva** (o `app_id` do Wayland, degrau 3b da O-VITA3K-RECEBE-O-DUALSENSE-INTEIRO-01): a
#: bancada confirma ou troca a linha.
#:
#: O shadPS4 vale o mesmo para as duas chaves (O-SHADPS4-QUE-JA-MORA-AQUI-01). O do projeto dela
#: sobe com `SDL_APP_ID=net.shadps4.shadPS4` (`run.sh` do shadps4-cosmic); o AppImage oficial aberto
#: direto cai no `SDL_GetExeName`, `shadps4`, que também é o `StartupWMClass` do `.desktop` dele
#: (derivado do fonte, NÃO MEDIDO). A janela do launcher Qt (`shadPS4QtLauncher`) fica FORA de
#: propósito: viva e escondida durante outro jogo, ela puxaria o perfil errado (FOCO-ERRANTE-01).
_JANELAS_DO_EMULADOR_ACHADO: dict[str, tuple[str, ...]] = {
    "org-vita3k-vita3k": ("Vita3K",),
    "net-shadps4-shadps4": ("shadps4",),
    "io-github-vitoriamaria-shadps4-cosmic": ("net.shadps4.shadPS4", "shadps4"),
}


def _achados_por_conteudo() -> tuple[desenho.SemCenso, ...]:
    """Os lançadores que a máquina DECLARA ser, e que ninguém digitou."""
    from hefesto_dualsense4unix.integrations import jogos_locais as jl

    try:
        achados = jl.lancadores_por_conteudo()
    except Exception:  # pragma: no cover - o disco do usuário não derruba a aba
        return ()
    de_fabrica = {atalho for item in desenho.SEM_FONTE for atalho in item.atalhos}
    if desenho.A_STEAM is not None:
        de_fabrica |= set(desenho.A_STEAM.atalhos)
    return tuple(
        desenho.SemCenso(chave=stem.lower().replace(".", "-"), nome=nome,
                         atalhos=(stem,), comandos=(),
                         janelas=_JANELAS_DO_EMULADOR_ACHADO.get(
                             stem.lower().replace(".", "-"), ()))
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
    **mais** o que o usuário declarou.

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
    que dizer ONDE *"é o que deixa ela conferir a resposta sem acreditar em
    mim"* — e o código tinha
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


def _o_jogo_em_foco(state: dict[str, Any] | None) -> str:
    """O appid do jogo Steam em foco AGORA, ou `""`. **Não toca o disco.**"""
    from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as lwd

    if not isinstance(state, dict):
        return ""
    return lwd.extract_steam_appid(state.get("window_detect_last_class")) or ""


@dataclasses.dataclass
class _Escolha:
    """Qual cartão abriu a escolha do jogo, e para quê."""

    modo: str = ""
    lancador: str = ""
    jogos: tuple[desenho.JogoParaEscolher, ...] = ()
    janelas: dict[str, tuple[str, ...]] = dataclasses.field(default_factory=dict)
    #: O título que casa cada jogo, por chave: o jogo de um lançador de
    #: modificação, cuja janela é a do emulador para todos os jogos.
    titulos: dict[str, str] = dataclasses.field(default_factory=dict)
    #: A lista da janela «Criar perfis» (Criar / Tem perfil).
    miolo_novo: str = ""

    def limpar(self) -> None:
        self.modo = self.lancador = self.miolo_novo = ""
        self.jogos = ()
        self.janelas = {}
        self.titulos = {}


_ESCOLHA = _Escolha()

_COM_BIBLIOTECA = ("heroic", "lutris")
_SEM_JOGOS = ("flatpak",)


def _chave_do_emulador(lancador: str) -> str:
    return f"emulador:{lancador}"


def _titulo_que_casa(titulo: str) -> str:
    """``PPSA21567`` → a expressão que acha o ID no título, e nada colado nele."""
    return rf"(?<!\w){re.escape(titulo)}(?!\w)"


def _jogos_pelo_titulo(
    item: desenho.SemCenso, ja: set[str],
) -> tuple[list[desenho.JogoParaEscolher], dict[str, str]]:
    """Os jogos do leitor da modificação que têm o ID no título, e o título de cada um."""
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    jogos: list[desenho.JogoParaEscolher] = []
    titulos: dict[str, str] = {}
    biblioteca = censo.biblioteca_do_cartao(item.chave, leitor=item.leitor)
    for jogo in biblioteca.jogos:
        if jogo.titulo_do_jogo and jogo.chave not in ja and jogo.chave not in titulos:
            jogos.append(desenho.JogoParaEscolher(
                chave=jogo.chave, nome=jogo.nome, instalado=jogo.instalado))
            titulos[jogo.chave] = _titulo_que_casa(jogo.titulo_do_jogo)
    jogos.sort(key=lambda j: j.nome.casefold())
    return jogos, titulos


def _jogos_para_escolher(
    lancador: str, nome: str, state: dict[str, Any] | None,
) -> tuple[list[desenho.JogoParaEscolher], dict[str, tuple[str, ...]], bool]:
    """``(jogos, janelas por chave, é emulador)`` — a lista DAQUELE lançador.

    Só entra jogo com CHAVE DE JANELA: uma linha que nunca casa com janela
    nenhuma é pior que nenhuma (a regra da LANCADOR-AGNOSTICO-01). O jogo da
    escada (o aberto, ou o último) nasce marcado (D-2109-O-JOGO-SE-ESCOLHE-NA-
    LISTA). Nunca levanta: é chamado de dentro de um clique.

    O LANÇADOR DE MODIFICAÇÃO COM LEITOR lista os jogos que o leitor devolve com
    o ID do título: a janela é a do emulador para todos, e o perfil de UM jogo
    casa pelo título (os títulos ficam em ``_ESCOLHA.titulos``).
    """
    _ESCOLHA.titulos = {}
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
            if item is not None and item.leitor is not None:
                pelo_titulo, titulos = _jogos_pelo_titulo(item, ja)
                if pelo_titulo:
                    _ESCOLHA.titulos = titulos
                    return pelo_titulo, {}, False
            janelas = tuple(dict.fromkeys(
                (*(item.atalhos if item else ()), *(item.comandos if item else ()),
                 *(item.janelas if item else ()))))
            linha = desenho.JogoParaEscolher(
                chave=chave, nome=f"{nome} — todos os jogos", marcado=True)
            return ([] if chave in ja else [linha]), {chave: janelas}, True
    except Exception:
        logging.getLogger(__name__).debug("lista_da_escolha_falhou", exc_info=True)
    jogos = [j for j in jogos if j.chave not in ja]
    jogos.sort(key=lambda j: (not j.marcado, not j.instalado, j.nome.casefold()))
    return jogos, {}, False


def _abrir_a_escolha(modo: str, lancador: str, state: dict[str, Any] | None) -> None:
    """Monta a lista do lançador clicado na janela «Criar perfis». Nunca levanta."""
    lida = VIGIA.agora()
    nomes = {x.chave: x.nome for x in desenho.cartoes(lida)}
    nome = nomes.get(lancador, lancador)
    _ESCOLHA.limpar()
    _ESCOLHA.modo = modo
    jogos, janelas, _emulador = _jogos_para_escolher(lancador, nome, state)
    _ESCOLHA.lancador = lancador
    _ESCOLHA.jogos, _ESCOLHA.janelas = tuple(jogos), janelas
    _montar_a_escolha_nova(nome)


def _relatar(gesto_: str, frase: str) -> None:
    """O recibo de um gesto da exclusão, no diário — a tela mostra o cartão."""
    print(f"[relato] {PAGINA} · {gesto_}: {frase}", file=sys.stderr)


def _resposta(lida: desenho.Leitura | None,
              state: dict[str, Any] | None = None) -> dict[str, Any]:
    """A carga da aba, a mesma no tique e no gesto: a conta, a fila e as janelas abertas."""
    return _com_as_extensoes({"mesa": {}, "blocos": {}}, desenho.cartoes(lida))


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

    QUEM A USA: a lista da escolha do jogo (o aberto, ou o último, nasce
    marcado) e a aba Jogar. Com uma evidência só, a do jogo RODANDO enquanto ela
    clica na janela do Hefesto, a escada falharia justamente quando ela saiu do
    jogo para clicar.

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


@gesto("07-lancadores.html", desenho.CRIAR_PERFIL)
def abrir_o_criar_perfil(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Criar perfil para um jogo»: a mesma escolha, no modo do perfil."""
    _abrir_a_escolha(desenho.CRIAR_PERFIL, str(o.get("v") or ""), ctx.state)
    return _resposta(VIGIA.agora(), ctx.state)


def _criar_o_perfil_de(ctx: Contexto, p: Any, jogo: desenho.JogoParaEscolher) -> str:
    """Cria o perfil do jogo pela aba Perfis e devolve a frase de produto."""
    from . import a10_perfis

    titulo = _ESCOLHA.titulos.get(jogo.chave, "")
    if titulo:
        # O JOGO DE UM EMULADOR QUE ABRE TODOS NA MESMA JANELA casa pelo ID
        # no título, e só por ele: a classe e o processo do KytyPS5 ainda não
        # foram medidos, e uma condição a mais que não casa calaria o perfil.
        from hefesto_dualsense4unix.profiles.schema import MatchCriteria

        regra = MatchCriteria(window_title_regex=titulo)
        try:
            return a10_perfis._nascer(ctx, p, regra, jogo.nome.strip() or "Novo perfil")
        except ValueError:
            return a10_perfis._nascer(ctx, p, regra, "Novo perfil")
    janelas = _ESCOLHA.janelas.get(jogo.chave, ())
    classes = janelas if janelas else (jogo.chave,)
    return a10_perfis.criar_para_o_jogo(
        ctx, p, classes=classes, nome_do_jogo=jogo.nome.split(" — ")[0])


_PARA_QUEM = ""

_MAXIMO_DA_AGULHA = 240


def _sem_acento(texto: str) -> str:
    """`Ryujinx à Solta` → `ryujinx a solta`. Só para fabricar a CHAVE."""
    import unicodedata

    cru = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in cru if not unicodedata.combining(c)).lower()


def chave_do_rotulo(rotulo: str) -> str:
    """A chave de um lançador novo, a partir do nome que o usuário deu.

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

    **DECISÃO, 09/09/2026, a opção (C):** *"Ou no Máximo Localizar o
    lançador. aí eu mesmo abro a tela e procuro o .desktop."* — o campo de
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


def _ok_e_motivo(resposta: Any) -> tuple[bool, str | None]:
    """`(ok, motivo)`, seja tupla ou `bool` o que a ponte devolveu."""
    if isinstance(resposta, tuple) and len(resposta) == 2:
        return bool(resposta[0]), resposta[1]
    return bool(resposta), None


# -- As extensões (modificações) e as janelas da aba Experimental ----------------------------------
#
# O desenho é o de `desenho_da_experimental`, o mesmo do gerador. O pacote só entrega os dados:
# o registro das modificações (`mods.instalador`), o que a janela de cada uma pede (`mods.opcoes`) e
# os impedimentos da Steam (`integrations.impedimentos_da_steam`). A pintura não abre arquivo a cada
# tique além da releitura do registro, que dura `TTL_DO_REGISTRO_S`; o resto é montado no clique.

TTL_DO_REGISTRO_S = 1.0
CAMPO_DA_CONTA = "mod-conta"
JANELA_DA_EXTENSAO = "#modificacao"  # (noqa-acento): contrato ASCII
JANELA_DO_LANCADOR = "#lanc-conf"
_COR_DA_EXTENSAO = {"kyty": "cyan", "lovense": "pink"}
NOME_DO_ARQUIVO_DO_MANIFESTO = "hefesto-mod.json"
TITULO_DO_SELETOR_DA_EXTENSAO = "Escolha o hefesto-mod.json da pasta da extensão"


@dataclasses.dataclass(frozen=True)
class _Instalada:
    """Uma linha do registro com o manifesto relido e o estado vivo."""

    entrada: Any
    manifesto: Any
    estado: str = ""


class _Registro:
    """As extensões instaladas, relidas no máximo a cada ``TTL_DO_REGISTRO_S`` e a cada gesto."""

    def __init__(self) -> None:
        self._em = float("-inf")
        self._valor: tuple[_Instalada, ...] = ()
        self._trava = threading.Lock()

    def esquecer(self) -> None:
        with self._trava:
            self._em = float("-inf")

    def ler(self) -> tuple[_Instalada, ...]:
        with self._trava:
            agora = time.monotonic()
            if agora - self._em >= TTL_DO_REGISTRO_S:
                self._valor, self._em = _ler_as_instaladas(), agora
            return self._valor


REGISTRO = _Registro()


@dataclasses.dataclass
class _Mexida:
    """O que a pessoa abriu: o ⋮ de uma extensão e as janelas, com o miolo já montado no clique."""

    menu: str = ""
    permissoes: str = ""
    remover: str = ""
    conf: str = ""
    imp: str = ""
    mod: str = ""
    impedimentos: tuple[Any, ...] = ()
    #: As permissões (e o aviso, por último) que a pessoa viu antes do «sim» de ligar.
    vistas: dict[str, tuple[str, ...]] = dataclasses.field(default_factory=dict)
    #: O aviso do manifesto que o primeiro «Instalar» mostrou, por endereço.
    avisos: dict[str, str] = dataclasses.field(default_factory=dict)
    html_conf: str = ""
    html_imp: str = ""
    html_mod: str = ""
    #: Os pedaços da coluna «Agora» que o manifesto da janela aberta declara.
    agora: tuple[str, ...] = ()
    #: O rascunho da janela da extensão: as opções mudadas, já validadas, à espera do Guardar.
    rascunho: dict[str, Any] = dataclasses.field(default_factory=dict)
    #: O atalho que a pessoa escolheu na janela «Configurar», à espera do Guardar.
    onde_escolhido: str = ""
    #: A extensão que trouxe o lançador da janela «Configurar» aberta; vazio no que é de fábrica.
    conf_da_modificacao: str = ""

    def limpar(self) -> None:
        self.menu = self.permissoes = self.remover = self.conf = self.imp = self.mod = ""
        self.impedimentos = ()
        self.vistas = {}
        self.avisos = {}
        self.html_conf = self.html_imp = self.html_mod = ""
        self.agora = ()
        self.rascunho = {}
        self.onde_escolhido = self.conf_da_modificacao = ""


_MEXIDA = _Mexida()

#: De quanto em quanto a coluna «Agora» pergunta ao serviço, no máximo.
TTL_DO_AGORA_S = 0.5
METODO_DO_AGORA = "mods.agora"
METODO_DO_PARAR = "mods.parar_tudo"


class _Agora:
    """O último ``acessorios.estado`` da extensão de janela aberta, relido FORA do tique.

    A pintura nunca bloqueia: :meth:`agora` devolve o que tem e, passado o ``TTL_DO_AGORA_S``,
    dispara a pergunta numa thread, pela ponte que o gesto da engrenagem trouxe. Sem serviço,
    o valor é ``None`` e a coluna fica vazia.
    """

    def __init__(self) -> None:
        self._mod = ""
        self._ponte: Any = None
        self._estado: dict[str, Any] | None = None
        self._quando = float("-inf")
        self._em_curso = False
        self._trava = threading.Lock()

    def abrir(self, mod: str, ponte: Any) -> None:
        with self._trava:
            if mod != self._mod:
                self._estado = None
            self._mod, self._ponte, self._quando = mod, ponte, float("-inf")

    def esquecer(self) -> None:
        with self._trava:
            self._quando = float("-inf")

    def agora(self) -> dict[str, Any] | None:
        """O que se sabe AGORA. Nunca bloqueia, nunca levanta."""
        with self._trava:
            precisa = (bool(self._mod) and self._ponte is not None and not self._em_curso
                       and time.monotonic() - self._quando >= TTL_DO_AGORA_S)
            if precisa:
                self._em_curso = True
            mod, ponte, estado = self._mod, self._ponte, self._estado
        if precisa:
            threading.Thread(target=self._corpo, args=(mod, ponte), name="hefesto-agora",
                             daemon=True).start()
        return estado

    def _corpo(self, mod: str, ponte: Any) -> None:
        try:
            self.ler(mod, ponte)
        finally:
            with self._trava:
                self._em_curso = False

    def ler(self, mod: str, ponte: Any) -> dict[str, Any] | None:
        """BLOQUEIA: pergunta ao serviço. Só de thread de gesto, nunca do tique."""
        try:
            resposta = ponte.resultado(METODO_DO_AGORA, mod=mod)
        except Exception:
            _LOG.debug("agora_da_extensao_sem_resposta", exc_info=True)
            resposta = None
        estado = resposta if isinstance(resposta, dict) and resposta.get("mod") == mod else None
        with self._trava:
            if mod == self._mod:
                self._estado, self._quando = estado, time.monotonic()
        return estado


_AGORA = _Agora()


def _lugares() -> Any:
    from hefesto_dualsense4unix.mods.instalador import Lugares

    return Lugares.do_xdg()


def _ler_as_instaladas() -> tuple[_Instalada, ...]:
    """O registro, o estado vivo e o manifesto de cada uma. Nunca levanta."""
    from hefesto_dualsense4unix.mods.instalador import (
        InstalacaoRecusadaError,
        ler_estado,
        ler_registro,
    )
    from hefesto_dualsense4unix.mods.manifesto import ManifestoRecusadoError, ler_manifesto

    try:
        lg = _lugares()
        registro = ler_registro(lg.registro)
        vivo = ler_estado(lg.estado)
    except (InstalacaoRecusadaError, OSError):
        _LOG.debug("registro_das_extensoes_ilegivel", exc_info=True)
        return ()
    saida: list[_Instalada] = []
    for mod_id, entrada in sorted(registro.items()):
        try:
            manifesto = ler_manifesto(lg.codigo / mod_id, exigir_api=False)
        except (ManifestoRecusadoError, OSError):
            manifesto = None
        saida.append(_Instalada(entrada, manifesto, str(vivo.get(mod_id, {}).get("estado") or "")))
    return tuple(saida)


@contextlib.contextmanager
def _dizendo_a_recusa() -> Any:
    """A recusa da infra de modificações vira a frase que a tela mostra."""
    from hefesto_dualsense4unix.mods.instalador import InstalacaoRecusadaError

    try:
        yield
    except InstalacaoRecusadaError as exc:
        raise RuntimeError(exc.frase) from exc


def _extensao_de(item: _Instalada) -> Any:
    """A linha do quadro «Extensões» de uma modificação instalada."""
    from hefesto_dualsense4unix.mods.instalador import aviso_por_ver
    from hefesto_dualsense4unix.mods.manifesto import o_que_a_permissao_deixa

    e = item.entrada
    menu = ""
    if _MEXIDA.menu == e.id:
        pedidas = item.manifesto.permissoes if item.manifesto is not None else e.permissoes_aceitas
        aviso = aviso_por_ver(e, item.manifesto) if item.manifesto is not None else ""
        menu = exp.menu_html(
            e.id, [x for x in (aviso,) if x] + [o_que_a_permissao_deixa(x) for x in pedidas]
            if _MEXIDA.permissoes == e.id else None, remover=_MEXIDA.remover == e.id)
    dica = item.manifesto.descricao if item.manifesto is not None else ""
    versao = e.versao
    esperando = getattr(e, "versao_esperando", "")
    if esperando:
        # A atualização sozinha baixou e não instalou: a linha diz o que espera o «Atualizar».
        versao = f"{e.versao} · a {esperando} espera o «Atualizar»"
        dica = " ".join(x for x in (getattr(e, "motivo_da_espera", ""), dica) if x)
    return exp.Extensao(
        chave=e.id, nome=e.nome, dica=dica,
        para="", janela=JANELA_DA_EXTENSAO, cor=_COR_DA_EXTENSAO.get(e.id, "purple"),
        versao=versao, selo=exp.SELO_DA_ORIGEM.get(e.origem, "Oficial"),
        ligada=e.ligada, menu=menu)


def _jogos_da_fila(lanc: desenho.Lancador) -> str:
    """A contagem da fila: «48 jogos», sem o «instalados» do cartão velho.

    A linha da fila só tem lugar para a contagem: a frase do cartão velho («Abra o Heroic uma
    vez…») passava por baixo dos três botões, e fica fora.
    """
    if not lanc.presente:
        return ""
    conta = lanc.jogos.replace("jogos instalados", "jogos").replace("jogo instalado", "jogo")
    return conta if _CONTAGEM_DA_FILA.fullmatch(conta) else ""


_CONTAGEM_DA_FILA = re.compile(r"\d+ jogos?")


def _fila_de(lancadores: list[desenho.Lancador]) -> list[Any]:
    return [exp.Fila(chave=x.chave, nome=x.nome, jogos=_jogos_da_fila(x), achado=x.presente,
                     configurar=JANELA_DO_LANCADOR) for x in lancadores]


def _com_as_extensoes(carga: dict[str, Any], lancadores: list[desenho.Lancador]) -> dict[str, Any]:
    """Acrescenta à carga da aba o quadro das extensões, a fila e as janelas abertas."""
    instaladas = REGISTRO.ler()
    carga["mesa"][CAMPO_DA_CONTA] = exp.conta_das_extensoes(len(instaladas))
    blocos = carga["blocos"]
    blocos[".ext-lista"] = exp.extensoes_html([_extensao_de(i) for i in instaladas])
    blocos[".lanc-fila"] = exp.fila_com_novo_html(_fila_de(lancadores))
    janelas = (("#lanc-janela", _MEXIDA.html_conf), ("#imp-janela", _MEXIDA.html_imp),
               ("#mod-janela", _MEXIDA.html_mod), ("#lanc-escolha", _ESCOLHA.miolo_novo))
    for seletor, miolo in janelas:
        if miolo:
            blocos[seletor] = miolo
    if _MEXIDA.html_mod and _MEXIDA.agora:
        blocos["#mod-agora"] = exp.agora_html(_MEXIDA.agora, _AGORA.agora())
    return carga


def _id_do_clique(o: dict[str, Any], gesto_: str) -> str:
    mod_id = str(o.get("v") or "").strip()
    if not mod_id:
        _LOG.warning("%s: clique sem `data-v`", gesto_)
        raise ValueError("O clique não disse de qual extensão se trata. Nada foi alterado.")
    return mod_id


def _a_instalada(mod_id: str) -> _Instalada:
    REGISTRO.esquecer()
    item = next((i for i in REGISTRO.ler() if i.entrada.id == mod_id), None)
    if item is None:
        raise RuntimeError(f"«{mod_id}» não está instalada.")
    return item


def _valor_na_tela(valor: Any) -> Any:
    return int(valor) if isinstance(valor, float) and valor == int(valor) else valor


def _jogos_com_perfil() -> tuple[tuple[str, str], ...]:
    """Os jogos que o Hefesto conhece: (``steam_app_<N>``, nome do perfil), na ordem dos nomes.

    É o perfil que declara o jogo (``match.window_class``); sem perfil, o jogo não está aqui.
    """
    from hefesto_dualsense4unix.profiles.loader import load_all_profiles
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria
    from hefesto_dualsense4unix.profiles.steam_app import steam_appid_from_wm_class

    try:
        perfis = list(load_all_profiles())
    except Exception:
        _LOG.debug("perfis_ilegiveis_para_a_lista_de_jogos", exc_info=True)
        return ()
    achados: dict[str, str] = {}
    for perfil_ in perfis:
        if not isinstance(perfil_.match, MatchCriteria):
            continue
        for classe in perfil_.match.window_class:
            appid = steam_appid_from_wm_class(classe)
            if appid is not None:
                achados.setdefault(f"steam_app_{appid}", perfil_.name)
    return tuple(sorted(achados.items(), key=lambda par: (par[1].casefold(), par[0])))


def _kits_dos_jogos(
    chaves: Sequence[str],
) -> tuple[tuple[str, kits_de_brinquedo.KitDoJogo], ...]:
    """O kit que a pasta de cada jogo traz, lido do disco; sem pasta ou sem kit, fica de fora."""
    from hefesto_dualsense4unix.integrations.prontuario_dos_jogos import (
        jogos_instalados,
    )

    pedidos = {c.removeprefix("steam_app_") for c in chaves}
    try:
        instalados = jogos_instalados()
    except Exception:
        _LOG.debug("jogos_instalados_ilegiveis_para_o_kit", exc_info=True)
        return ()
    achados = []
    for appid, _nome, raiz in instalados:
        if appid not in pedidos or raiz is None:
            continue
        kit = kits_de_brinquedo.kit_do_jogo(raiz, appid)
        if kit is not None:
            achados.append((f"steam_app_{appid}", kit))
    return tuple(achados)


def _montar_a_janela_da_extensao(mod_id: str) -> None:
    """O miolo da janela de opções: o valor guardado de cada opção, com o rascunho por cima."""
    from hefesto_dualsense4unix.mods import opcoes

    item = _a_instalada(mod_id)
    manifesto = item.manifesto
    if manifesto is None:
        raise RuntimeError("O manifesto desta extensão não pôde ser lido. Nada foi alterado.")
    valores = {**opcoes.ler(manifesto, _lugares()),
               **(_MEXIDA.rascunho if _MEXIDA.mod == mod_id else {})}
    jogos = _jogos_com_perfil() if any(x.tipo == "jogos" for x in manifesto.opcoes) else ()
    kit_de = _kits_dos_jogos([chave for chave, _nome in jogos]) if jogos else ()
    linhas = [exp.OpcaoDaJanela(
        mod=mod_id, id=x.id, rotulo=x.rotulo, tipo=x.tipo, valor=_valor_na_tela(valores[x.id]),
        escolhas=tuple(x.escolhas), grupo=x.grupo or "", minimo=x.minimo or 0,
        maximo=x.maximo or 0, passo=x.passo or 1,
        jogos=jogos if x.tipo == "jogos" else (),
        kit_de=kit_de if x.tipo == "jogos" else ()) for x in manifesto.opcoes]
    _MEXIDA.mod = mod_id
    _MEXIDA.agora = tuple(manifesto.agora)
    _MEXIDA.html_mod = exp.modificacao_miolo_html(
        manifesto.nome, linhas, mod=mod_id, agora=_MEXIDA.agora,
        estado=_AGORA.agora() if _MEXIDA.agora else None, parar_tudo=manifesto.parar_tudo)


def _a_pintura_agora(ctx: Contexto) -> dict[str, Any]:
    return _resposta(VIGIA.agora(), ctx.state)


@gesto("07-lancadores.html", "ligar-modificacao", grava="_ligar_ou_desligar_a_modificacao")
def ligar_modificacao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """A chave da extensão. Permissão nova pede um segundo clique, depois de mostrada."""
    recado = _ligar_ou_desligar_a_modificacao(_id_do_clique(o, "ligar-modificacao"))
    if recado is None:
        return {**_a_pintura_agora(ctx), "armou": True}
    return {**_a_pintura_agora(ctx), "recado": recado}


def _ligar_ou_desligar_a_modificacao(mod_id: str) -> str | None:
    """Liga ou desliga pela infra. Permissão nova pede o «sim»: o primeiro clique só a mostra.

    A lista aparece no ⋮ aberto da linha (o recado não chega à tela), e o ``None`` é o
    clique que só armou.
    """
    from hefesto_dualsense4unix.mods.instalador import (
        aviso_por_ver,
        desligar,
        ler_registro,
        ligar,
        manifesto_instalado,
    )
    from hefesto_dualsense4unix.mods.manifesto import permissoes_novas

    lg = _lugares()
    with _dizendo_a_recusa():
        entrada = ler_registro(lg.registro).get(mod_id)
        if entrada is None:
            raise RuntimeError(f"«{mod_id}» não está instalada.")
        if entrada.ligada:
            desligar(mod_id, lugares=lg)
            REGISTRO.esquecer()
            return f"{entrada.nome} desligada."
        manifesto = manifesto_instalado(mod_id, lugares=lg)
        pedidas = tuple(sorted(manifesto.permissoes))
        aviso = aviso_por_ver(entrada, manifesto)
        if (permissoes_novas(entrada.permissoes_aceitas, list(pedidas)) or aviso) and (
                _MEXIDA.vistas.get(mod_id) != (*pedidas, aviso)):
            _MEXIDA.vistas[mod_id] = (*pedidas, aviso)
            _MEXIDA.menu = _MEXIDA.permissoes = mod_id
            _MEXIDA.remover = ""
            return None
        ligar(mod_id, permissoes_vistas=pedidas, aviso_visto=aviso, lugares=lg)
        _MEXIDA.vistas.pop(mod_id, None)
        if _MEXIDA.menu == mod_id:
            _MEXIDA.menu = _MEXIDA.permissoes = ""
    REGISTRO.esquecer()
    return f"{entrada.nome} ligada."


@gesto("07-lancadores.html", "configurar-modificacao")
def configurar_modificacao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """A engrenagem da extensão: a janela com as opções que o manifesto dela declara.

    A coluna «Agora» nasce com o estado lido aqui (o gesto roda em thread) e segue pela ponte.
    """
    _MEXIDA.menu = _MEXIDA.permissoes = ""
    mod_id = _id_do_clique(o, "configurar-modificacao")
    _MEXIDA.rascunho = {}
    _MEXIDA.mod = mod_id
    _AGORA.abrir(mod_id, p)
    _AGORA.ler(mod_id, p)
    _montar_a_janela_da_extensao(mod_id)
    return _a_pintura_agora(ctx)


@gesto("07-lancadores.html", exp.GESTO_DO_PARAR)
def parar_tudo_da_modificacao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O «Parar tudo» da janela: o serviço publica o gesto ``para`` só para esta extensão."""
    mod_id = _id_do_clique(o, exp.GESTO_DO_PARAR)
    ok, motivo = p.chamar_detalhado(METODO_DO_PARAR, mod=mod_id)
    if not ok:
        raise RuntimeError(motivo or "O serviço não respondeu. Nada foi parado.")
    _AGORA.esquecer()
    return {**_a_pintura_agora(ctx), "recado": "Parar tudo enviado."}


@gesto("07-lancadores.html", "guardar-opcao-da-modificacao")
def guardar_opcao_da_modificacao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Uma opção da janela vai ao rascunho, validada; quem grava é o Guardar.

    A caixa e o número agem no ``change``; a chave de ligado, no clique.
    """
    from hefesto_dualsense4unix.mods import opcoes

    mod_id, _, resto = _id_do_clique(o, "guardar-opcao-da-modificacao").partition(":")
    opcao_id, _, jogo = resto.partition(":")
    item = _a_instalada(mod_id)
    declaradas = item.manifesto.opcoes if item.manifesto else ()
    opcao = next((x for x in declaradas if x.id == opcao_id), None)
    if opcao is None:
        raise RuntimeError("Esta extensão não tem essa opção. Nada foi guardado.")
    evento = str(o.get("evento") or "")
    if opcao.tipo == "ligado":
        if evento == "change":
            return None
        valor: Any = not bool(_valor_na_janela(item, opcao))
    elif opcao.tipo == "jogos":
        if evento == "click":
            return None
        valor = _jogos_com_a_caixa(_valor_na_janela(item, opcao), jogo)
    else:
        if evento == "click":
            return None
        valor = o.get("valor")
    with _dizendo_a_recusa():
        certo = opcoes.validar(opcao, valor)
    if _MEXIDA.mod != mod_id:
        _MEXIDA.mod, _MEXIDA.rascunho = mod_id, {}
    _MEXIDA.rascunho[opcao_id] = certo
    _montar_a_janela_da_extensao(mod_id)
    return _a_pintura_agora(ctx)


@gesto("07-lancadores.html", exp.GESTO_DO_GUARDAR, grava="_guardar_a_opcao_da_modificacao")
def guardar_modificacao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O Guardar da janela da extensão: grava o rascunho inteiro em ``opcoes.json``."""
    mod_id = _id_do_clique(o, exp.GESTO_DO_GUARDAR)
    recado = _guardar_a_opcao_da_modificacao(mod_id)
    _montar_a_janela_da_extensao(mod_id)
    carga = _a_pintura_agora(ctx)
    return {**carga, "recado": recado} if recado else carga


def _guardar_a_opcao_da_modificacao(mod_id: str) -> str:
    """Grava cada opção do rascunho, validada de novo contra o manifesto, e esvazia o rascunho."""
    from hefesto_dualsense4unix.mods import opcoes

    item = _a_instalada(mod_id)
    rascunho = _MEXIDA.rascunho if _MEXIDA.mod == mod_id else {}
    if not rascunho:
        return ""
    with _dizendo_a_recusa():
        for opcao_id, valor in rascunho.items():
            opcoes.guardar(item.manifesto, opcao_id, valor, _lugares())
    _MEXIDA.rascunho = {}
    return "Guardado."


def _jogos_com_a_caixa(marcados: list[str], jogo: str) -> list[str]:
    """A lista com a caixa virada: o jogo sai se estava nela, entra no fim se não estava."""
    if not jogo:
        raise RuntimeError("Qual jogo? O clique não disse. Nada foi guardado.")
    if jogo in marcados:
        return [x for x in marcados if x != jogo]
    if jogo not in {chave for chave, _nome in _jogos_com_perfil()}:
        raise RuntimeError("Esse jogo não tem perfil. Nada foi guardado.")
    return [*marcados, jogo]


def _valor_na_janela(item: _Instalada, opcao: Any) -> Any:
    """O que a janela mostra agora: o rascunho, ou o guardado."""
    from hefesto_dualsense4unix.mods import opcoes

    if _MEXIDA.mod == item.entrada.id and opcao.id in _MEXIDA.rascunho:
        return _MEXIDA.rascunho[opcao.id]
    return opcoes.ler(item.manifesto, _lugares())[opcao.id]


@gesto("07-lancadores.html", "mais-da-modificacao", grava="_mexer_na_modificacao")
def mais_da_modificacao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O ⋮ da extensão: abre o menu; o ``data-v`` é ``id:<ação>``, um dos três botões dele."""
    mod_id, _, acao = _id_do_clique(o, "mais-da-modificacao").partition(":")
    if not acao:
        _MEXIDA.menu = "" if _MEXIDA.menu == mod_id else mod_id
        _MEXIDA.permissoes = _MEXIDA.remover = ""
        _repintar_a_conf_da(mod_id)
        return _a_pintura_agora(ctx)
    _MEXIDA.menu = mod_id
    if acao == "permissoes":  # (noqa-acento): contrato ASCII
        _a_instalada(mod_id)
        _MEXIDA.permissoes, _MEXIDA.remover = mod_id, ""
        _repintar_a_conf_da(mod_id)
        return _a_pintura_agora(ctx)
    recado = _mexer_na_modificacao(mod_id, acao)
    _repintar_a_conf_da(mod_id)
    if recado is None:
        return {**_a_pintura_agora(ctx), "armou": True}
    return {**_a_pintura_agora(ctx), "recado": recado}


def _repintar_a_conf_da(mod_id: str) -> None:
    """A janela «Configurar» aberta acompanha o ⋮: o da extensão dela, ou o do próprio lançador.

    O lançador que vem com o Hefesto manda a chave dele no ⋮ (o menu é o apagado). Removida a
    extensão, o lançador sai junto: a confirmação da janela já a fechou (``href="#"``).
    """
    if not _MEXIDA.conf:
        return
    if _MEXIDA.conf_da_modificacao != mod_id and (
            _MEXIDA.conf_da_modificacao or _MEXIDA.conf != mod_id):
        return
    VIGIA.esquecer()
    try:
        _montar_a_conf(_MEXIDA.conf)
    except RuntimeError:
        _MEXIDA.conf = _MEXIDA.html_conf = _MEXIDA.conf_da_modificacao = ""


def _mexer_na_modificacao(mod_id: str, acao: str) -> str | None:
    """Atualiza ou remove. Remover apaga o código e os dados dela: pede o segundo clique.

    O primeiro clique em Remover troca o botão por «Confirmar remoção» e devolve ``None``.
    """
    from hefesto_dualsense4unix.mods.instalador import atualizar, remover

    item = _a_instalada(mod_id)
    nome = item.entrada.nome
    lg = _lugares()
    with _dizendo_a_recusa():
        if acao == "atualizar":
            feito = atualizar(mod_id, lugares=lg)
            REGISTRO.esquecer()
            extra = (" Ela pede permissão nova: ligue-a de novo para aceitar."
                     if feito.permissoes_novas else "")
            return f"{nome} atualizada para a versão {feito.entrada.versao}.{extra}"
        if acao != "remover":
            raise RuntimeError("Essa ação do menu não existe. Nada foi alterado.")
        if _MEXIDA.remover != mod_id:
            _MEXIDA.remover = mod_id
            return None
        restos = remover(mod_id, lugares=lg)
    _MEXIDA.menu = _MEXIDA.permissoes = _MEXIDA.remover = ""
    if _MEXIDA.mod == mod_id:
        _MEXIDA.mod = _MEXIDA.html_mod = ""
        _MEXIDA.rascunho = {}
    REGISTRO.esquecer()
    if restos:
        raise RuntimeError(f"Não consegui remover {nome} por inteiro: {'; '.join(restos)}.")
    return f"{nome} removida."


def _instalar_a_modificacao(origem: str) -> str:
    """Instala de um endereço git ou de uma pasta local. Não liga: ligar é a chave.

    O manifesto com ``aviso``: o primeiro gesto só o mostra, e o segundo instala.
    """
    from hefesto_dualsense4unix.mods.instalador import AvisoParaVerError, instalar

    try:
        with _dizendo_a_recusa():
            feito = instalar(origem, aviso_visto=_MEXIDA.avisos.get(origem, ""))
    except RuntimeError as exc:
        if not isinstance(exc.__cause__, AvisoParaVerError):
            raise
        _MEXIDA.avisos[origem] = exc.__cause__.aviso
        return f"{exc} Instale de novo para confirmar."
    _MEXIDA.avisos.pop(origem, None)
    REGISTRO.esquecer()
    return f"{feito.entrada.nome} instalada. Ligue-a na chave quando quiser."


@gesto("07-lancadores.html", "instalar-modificacao", grava="_instalar_a_modificacao")
def instalar_modificacao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Instalar»: o endereço digitado na linha do rodapé do quadro."""
    forma = o.get("forma") or {}
    origem = str(forma.get("mod-endereco") or "").strip()
    if not origem:
        raise RuntimeError("Digite o endereço da extensão, ou escolha a pasta dela.")
    recado = _instalar_a_modificacao(origem)
    return {**_a_pintura_agora(ctx), "recado": recado}


@gesto("07-lancadores.html", "escolher-arquivo-da-modificacao", grava="_instalar_a_modificacao")
def escolher_arquivo_da_modificacao(ctx: Contexto, o: dict[str, Any], p: Any
                                    ) -> dict[str, Any] | None:
    """«Escolher a pasta…»: ela aponta o ``hefesto-mod.json`` e a pasta dele é instalada.

    Cancelar não é erro: o seletor devolve vazio e a tela não fala.
    """
    caminho = p.escolher_arquivo(TITULO_DO_SELETOR_DA_EXTENSAO, padrao=NOME_DO_ARQUIVO_DO_MANIFESTO)
    if not caminho:
        return None
    alvo = pathlib.Path(str(caminho))
    if alvo.name != NOME_DO_ARQUIVO_DO_MANIFESTO:
        raise RuntimeError(
            f"Escolha o arquivo {NOME_DO_ARQUIVO_DO_MANIFESTO} da pasta da extensão.")
    recado = _instalar_a_modificacao(str(alvo.parent))
    return {**_a_pintura_agora(ctx), "recado": recado}


# -- Os impedimentos da Steam --------------------------------------------------------------------


def _sondar_a_steam() -> tuple[Any, ...]:
    from hefesto_dualsense4unix.integrations import impedimentos_da_steam

    return impedimentos_da_steam.sondar()


def _montar_os_impedimentos(chave: str) -> None:
    linhas = [exp.LinhaDeImpedimento(i.chave, i.jogo, i.frase, i.botao)
              for i in _MEXIDA.impedimentos]
    nome = next((x.nome for x in desenho.cartoes(VIGIA.agora()) if x.chave == chave), chave)
    _MEXIDA.imp = chave
    _MEXIDA.html_imp = exp.impedimentos_miolo_html(nome, linhas)


@gesto("07-lancadores.html", "ver-impedimentos")
def ver_impedimentos(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Ver e resolver»: sonda a Steam de novo e abre a lista, uma linha por jogo."""
    chave = _id_do_clique(o, "ver-impedimentos")
    if chave != desenho.STEAM:
        raise RuntimeError("Só a Steam tem esta leitura. Nada foi alterado.")
    _MEXIDA.impedimentos = _sondar_a_steam()
    _montar_os_impedimentos(chave)
    _montar_a_conf(chave, ctx.state)
    return _a_pintura_agora(ctx)


def _curar_o_impedimento(chaves: tuple[str, ...] | None) -> str:
    """Cura os impedimentos nomeados (todos, se ``None``) pelas primitivas da Steam."""
    from hefesto_dualsense4unix.integrations import impedimentos_da_steam as imp

    atuais = _sondar_a_steam()
    alvo = [i for i in atuais if chaves is None or i.chave in chaves]
    try:
        frase = imp.curar(alvo)
    except imp.ImpedimentoNaoCuradoError as exc:
        _MEXIDA.impedimentos = _sondar_a_steam() if alvo else atuais
        raise RuntimeError(exc.frase) from exc
    finally:
        VIGIA.esquecer()
    _MEXIDA.impedimentos = _sondar_a_steam()
    return frase


@gesto("07-lancadores.html", "resolver-impedimento", grava="_curar_o_impedimento")
def resolver_impedimento(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O botão de UM jogo: ``tipo:appid``. Com a Steam aberta a cura recusa dizendo."""
    chave = _id_do_clique(o, "resolver-impedimento")
    frase = _curar_o_impedimento((chave,))
    _montar_os_impedimentos(desenho.STEAM)
    _montar_a_conf(desenho.STEAM, ctx.state)
    return {**_a_pintura_agora(ctx), "recado": frase}


@gesto("07-lancadores.html", "resolver-todos-os-impedimentos", grava="_curar_o_impedimento")
def resolver_todos_os_impedimentos(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O botão do rodapé: cura todos os jogos da lista de uma vez."""
    frase = _curar_o_impedimento(None)
    _montar_os_impedimentos(desenho.STEAM)
    _montar_a_conf(desenho.STEAM, ctx.state)
    return {**_a_pintura_agora(ctx), "recado": frase}


# -- Os três botões de todo lançador ---------------------------------------------------------------


def _montar_a_conf(chave: str, state: dict[str, Any] | None = None) -> None:
    """O miolo da janela «Configurar», com o que o produto sabe do lançador e o rascunho dela."""
    from hefesto_dualsense4unix.integrations.censo_dos_lancadores import LANCADORES_COM_JOGOS
    from hefesto_dualsense4unix.mods.manifesto import o_que_a_permissao_deixa

    lida = VIGIA.agora()
    cartao = next((x for x in desenho.cartoes(lida) if x.chave == chave), None)
    if cartao is None:
        raise RuntimeError("Não conheço esse lançador. Nada foi alterado.")
    mod_id = next((x.modificacao for x in _declarados() if x.chave == chave and x.modificacao), "")
    onde = dict(lida.onde_estao).get(chave, "") if lida is not None else ""
    impedimentos = len(_MEXIDA.impedimentos) if chave == desenho.STEAM else None
    menu = ""
    if mod_id and _MEXIDA.menu == mod_id:
        item = _a_instalada(mod_id)
        pedidas = item.manifesto.permissoes if item.manifesto is not None else (
            item.entrada.permissoes_aceitas)
        menu = exp.menu_html(
            mod_id, [o_que_a_permissao_deixa(x) for x in pedidas]
            if _MEXIDA.permissoes == mod_id else None, remover=_MEXIDA.remover == mod_id,
            fecha=True)
    elif not mod_id and _MEXIDA.menu == chave:
        menu = "aberto"
    _MEXIDA.conf, _MEXIDA.conf_da_modificacao = chave, mod_id
    _MEXIDA.html_conf = exp.lanc_conf_miolo_html(exp.Conf(
        chave=chave, nome=cartao.nome, entrou="Como extensão" if mod_id else "Do sistema",
        onde=_abreviado(_MEXIDA.onde_escolhido or onde), jogos=_jogos_da_fila(cartao),
        impedimentos=impedimentos, pastas=_pastas_dos_jogos(chave),
        perfil_por_jogo=_perfil_por_jogo(chave) if chave in LANCADORES_COM_JOGOS else None,
        modificacao=mod_id, menu=menu))


def _abreviado(caminho: str) -> str:
    """O caminho com a pasta da casa trocada por ``~``, como o desenho mostra."""
    casa = str(pathlib.Path.home())
    if caminho == casa or caminho.startswith(casa + "/"):
        return "~" + caminho[len(casa):]
    return caminho


def _pastas_dos_jogos(chave: str) -> tuple[str, ...]:
    """As bibliotecas da Steam (a raiz e as do ``libraryfolders.vdf``); os outros não têm."""
    if chave != desenho.STEAM:
        return ()
    from hefesto_dualsense4unix.integrations.steam_launch_options import pastas_steamapps

    try:
        return tuple(dict.fromkeys(_abreviado(str(x.parent)) for x in pastas_steamapps()))
    except Exception:  # pragma: no cover - o disco do usuário não derruba a janela
        return ()


def _perfil_por_jogo(chave: str) -> bool:
    """A chave «Cada jogo ganha o seu perfil» deste lançador, no ``maquina.json``; nasce ligada."""
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina

    try:
        return carregar_maquina().perfil_por_jogo.get(chave, True)
    except Exception:  # pragma: no cover - o disco do usuário não derruba a janela
        return True


@gesto("07-lancadores.html", "configurar-lancador")
def configurar_lancador(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Configurar»: a janela igual para todos. A Steam sonda os impedimentos ao abrir."""
    chave = _id_do_clique(o, "configurar-lancador")
    _MEXIDA.conf = chave
    _MEXIDA.onde_escolhido = ""
    _MEXIDA.menu = _MEXIDA.permissoes = _MEXIDA.remover = ""
    _MEXIDA.imp = _MEXIDA.html_imp = ""
    _MEXIDA.impedimentos = _sondar_a_steam() if chave == desenho.STEAM else ()
    _montar_a_conf(chave, ctx.state)
    return _a_pintura_agora(ctx)


@gesto("07-lancadores.html", exp.GESTO_DE_ESCOLHER)
def escolher_o_lancador(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """«Escolher o arquivo…» da janela «Configurar»: o atalho apontado vai ao rascunho dela.

    A busca é a mesma do «Adicionar um lançador» (um atalho fora das pastas de aplicativos
    recusa); quem grava é o Guardar. Cancelar o seletor não é erro: a tela não fala.
    """
    chave = _id_do_clique(o, exp.GESTO_DE_ESCOLHER)
    if chave != _MEXIDA.conf:
        raise RuntimeError("Abra o «Configurar» deste lançador de novo. Nada foi alterado.")
    caminho = p.escolher_arquivo(TITULO_DO_SELETOR, padrao="*.desktop",
                                 sugestao=_pasta_de_partida())
    if not caminho:
        return None
    _achar_o_que_ela_apontou(str(caminho))
    _MEXIDA.onde_escolhido = str(caminho)
    _montar_a_conf(chave, ctx.state)
    return _a_pintura_agora(ctx)


@gesto("07-lancadores.html", exp.GESTO_DO_GUARDAR_LANCADOR, grava="machine_declare")
def guardar_lancador(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O Guardar da janela «Configurar»: o atalho escolhido e a chave do perfil por jogo.

    As duas escritas vão pelo ``machine.declare``; o atalho, pelo mesmo dono do «Adicionar».
    """
    global _PARA_QUEM

    chave = _id_do_clique(o, exp.GESTO_DO_GUARDAR_LANCADOR)
    if chave != _MEXIDA.conf:
        raise RuntimeError("Abra o «Configurar» deste lançador de novo. Nada foi guardado.")
    bruta = o.get("forma")
    forma: dict[str, Any] = bruta if isinstance(bruta, dict) else {}
    recados: list[str] = []
    if _MEXIDA.onde_escolhido:
        _PARA_QUEM = chave
        try:
            recados.append(_guardar_onde_ele_esta(p, "", _MEXIDA.onde_escolhido,
                                                  _achar_o_que_ela_apontou))
        finally:
            _PARA_QUEM = ""
        _MEXIDA.onde_escolhido = ""
    dito = str(forma.get(exp.CAMPO_DO_PERFIL) or "").strip()
    if dito:
        ligado = dito == "Ligado"
        if ligado != _perfil_por_jogo(chave):
            ok, motivo = _ok_e_motivo(p.machine_declare({"perfil_por_jogo": {chave: ligado}}))
            if not ok:
                raise RuntimeError(motivo or "Não consegui guardar isso agora. Nada foi alterado.")
            recados = recados or ["Guardado."]
    VIGIA.esquecer()
    _montar_a_conf(chave, ctx.state)
    carga = _resposta(VIGIA.ler(), ctx.state)
    return {**carga, "recado": " ".join(recados)} if recados else carga


@gesto("07-lancadores.html", "identificar-lancador")
def identificar_lancador(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Identificar»: procura de novo no disco e diz o que achou, ou como ensinar onde ele está.

    Achou: a fila repintada mostra a linha achada, e a frase vai ao diário. Não achou: sobe como
    recusa e o botão pisca a recusa; pelo recado, ele piscaria «deu certo» sem ter achado nada.
    """
    chave = _id_do_clique(o, "identificar-lancador")
    VIGIA.esquecer()
    lida = VIGIA.ler()
    cartao = next((x for x in desenho.cartoes(lida) if x.chave == chave), None)
    if cartao is None:
        raise RuntimeError("Não conheço esse lançador. Nada foi alterado.")
    if not cartao.presente:
        raise RuntimeError(
            f"Não achei {cartao.nome} nesta máquina. Instale-o, ou aponte o atalho dele "
            "em «Adicionar um lançador».")
    onde = dict(lida.onde_estao).get(chave, "") if lida is not None else ""
    frase = f"Achei {cartao.nome}" + (f" em {onde}." if onde else ".")
    return {**_resposta(lida, ctx.state), "recado": frase}


# -- A janela «Criar perfis» ---------------------------------------------------------------------


def _perfis_que_casam() -> tuple[set[str], set[str]]:
    """As classes de janela e os títulos que algum perfil já casa."""
    from hefesto_dualsense4unix.profiles.loader import load_all_profiles
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria

    classes: set[str] = set()
    titulos: set[str] = set()
    try:
        perfis = list(load_all_profiles())
    except Exception:
        _LOG.debug("perfis_ilegiveis_para_a_lista", exc_info=True)
        return classes, titulos
    for perfil_ in perfis:
        regra = perfil_.match
        if isinstance(regra, MatchCriteria):
            classes.update(c.casefold() for c in regra.window_class)
            if regra.window_title_regex:
                titulos.add(regra.window_title_regex)
    return classes, titulos


def _montar_a_escolha_nova(nome: str) -> None:
    """A lista da janela «Criar perfis»: cada jogo, com «Criar» ou «Tem perfil»."""
    classes, titulos = _perfis_que_casam()
    linhas = []
    for jogo in _ESCOLHA.jogos:
        titulo = _ESCOLHA.titulos.get(jogo.chave, "")
        janelas = _ESCOLHA.janelas.get(jogo.chave, ()) or (jogo.chave,)
        tem = titulo in titulos if titulo else any(j.casefold() in classes for j in janelas)
        linhas.append(exp.JogoDaLista(jogo.chave, jogo.nome, tem))
    _ESCOLHA.miolo_novo = exp.escolha_miolo_html(nome, linhas)


@gesto("07-lancadores.html", "criar-perfil-do-jogo", grava="criar_para_o_jogo")
def criar_perfil_do_jogo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O «Criar» de um jogo da lista: o perfil nasce na aba Perfis e a janela continua aberta."""
    chave = str(o.get("v") or "").strip()
    jogo = next((j for j in _ESCOLHA.jogos if j.chave == chave), None)
    if jogo is None:
        raise RuntimeError("Esse jogo não está mais na lista. Nada foi criado.")
    frase = _criar_o_perfil_de(ctx, p, jogo)
    _relatar("criar-perfil-do-jogo", frase)
    _montar_a_escolha_nova(_nome_da_escolha())
    return {**_resposta(VIGIA.agora(), ctx.state), "recado": frase}


def _nome_da_escolha() -> str:
    return next((x.nome for x in desenho.cartoes(VIGIA.agora()) if x.chave == _ESCOLHA.lancador),
                _ESCOLHA.lancador)


METODO_DA_RECARGA = "launch_env.refresh"

#: o wrapper vive em dois arquivos em disco, e o `state_full` não tem UMA chave
# `machine_declare` ENTROU EM 08/09/2026 com o lançador declarado pelo usuário: é a
PONTE: set[str] = {"chamar", "chamar_detalhado", "resultado", "machine_declare", "escolher_arquivo"}
METODOS: set[str] = {"machine.declare", METODO_DO_AGORA, METODO_DO_PARAR}


PAGINA = "07-lancadores.html"
#: caminho para `with_steam_closed`, que a interface nova não tinha); e de
PISO_DA_ABA = 14

PROVAS: list[dict[str, Any]] = []

#: TODOS, e não por preguiça: o `state_full` do daemon não tem UMA chave sobre
SEM_ECO = (# `maquina.json`: o `state_full` não tem UMA chave sobre lançador.
           desenho.ADICIONAR, desenho.PROCURAR_O_ARQUIVO,
           # Os gestos das extensões, da janela de cada lançador e dos impedimentos: o estado
           # que o daemon devolve não tem chave sobre o registro das modificações nem sobre a Steam.
           "ligar-modificacao", "configurar-modificacao", "guardar-opcao-da-modificacao",
           "mais-da-modificacao", "instalar-modificacao", "escolher-arquivo-da-modificacao",
           exp.GESTO_DO_PARAR, exp.GESTO_DO_GUARDAR, exp.GESTO_DE_ESCOLHER,
           exp.GESTO_DO_GUARDAR_LANCADOR,
           "ver-impedimentos", "resolver-impedimento", "resolver-todos-os-impedimentos",
           "identificar-lancador", "configurar-lancador", "criar-perfil-do-jogo")

