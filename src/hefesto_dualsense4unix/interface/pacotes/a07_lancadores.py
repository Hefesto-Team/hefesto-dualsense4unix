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

    heroic                                      NÃO ACHEI
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

from hefesto_dualsense4unix.integrations import lista_de_exclusao
from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
from hefesto_dualsense4unix.interface import desenho_dos_lancadores as desenho

from . import Contexto, fios, perfil, registrar

_LOG = logging.getLogger(__name__)

TTL_S = 20.0

SEM_DONO: dict[str, str] = {}


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
        fios.soltar(
            "hefesto-lancadores", self._corpo
        )

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
    perfil._com_o_src()
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina

    try:
        declaracao = carregar_maquina()
    except Exception:  # pragma: no cover
        return ()
    return tuple(
        desenho.SemCenso(chave=chave, nome=item.rotulo,
                         atalhos=tuple(item.atalhos),
                         comandos=tuple(item.comandos),
                         declarado=True)
        for chave, item in sorted(declaracao.lancadores.items())
    ) + _achados_por_conteudo() + _das_modificacoes()


def _das_modificacoes(lugares: Any = None) -> tuple[desenho.SemCenso, ...]:
    """Os lançadores que as extensões LIGADAS trazem, no molde do procurador.

    Quem lê o registro e confere o manifesto é o censo
    (:func:`censo_dos_lancadores.lancadores_das_extensoes`), o mesmo que o serviço consulta para
    a chave de janela e o Proton em uso: uma lista só. Desligou, o cartão sai na volta seguinte da
    vigia. Nunca levanta.
    """
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    return tuple(
        desenho.SemCenso(
            chave=ext.bloco.chave, nome=ext.bloco.rotulo, atalhos=ext.bloco.atalhos,
            comandos=ext.bloco.comandos, janelas=ext.bloco.janelas,
            titulo_do_jogo=ext.bloco.titulo_do_jogo, leitor=ext.bloco.leitor,
            modificacao=ext.bloco.chave, pela_porta=ext.pela_porta)
        for ext in censo.lancadores_das_extensoes(lugares))


def _achados_por_conteudo() -> tuple[desenho.SemCenso, ...]:
    """Os lançadores que a máquina DECLARA ser, e que ninguém digitou."""
    from hefesto_dualsense4unix.integrations import jogos_locais as jl

    try:
        achados = jl.lancadores_por_conteudo()
    except Exception:  # pragma: no cover
        return ()
    de_fabrica = {atalho for item in desenho.SEM_FONTE for atalho in item.atalhos}
    if desenho.A_STEAM is not None:
        de_fabrica |= set(desenho.A_STEAM.atalhos)
    tem_linha = {a.casefold() for a in de_fabrica | _atalhos_que_tem_linha_propria()}
    return tuple(
        desenho.SemCenso(chave=stem.lower().replace(".", "-"), nome=nome,
                         atalhos=(stem,), comandos=())
        for stem, nome in sorted(achados.items())
        if stem.casefold() not in tem_linha
    )


def _atalhos_que_tem_linha_propria() -> set[str]:
    """Os atalhos que já têm linha na fila: o da extensão ligada e o do que virou extensão.

    Medido na bancada de 19/10/2026: com o Lutris no Flatpak da máquina, o achado por conteúdo
    punha uma linha «Lutris» genérica ao lado da linha da migração (e, com a extensão ligada, ao
    lado da linha dela). O lançador que virou extensão fala por uma linha só.
    """
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    fora = {str(x["flatpak"]) for x in censo._os_que_viraram_extensao()
            if isinstance(x.get("flatpak"), str)}
    for ext in censo.lancadores_das_extensoes():
        fora |= set(ext.bloco.atalhos)
    return fora


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
                except OSError:  # pragma: no cover
                    continue
            if onde:
                break
        if not onde:
            for comando in item.comandos:
                try:
                    achado = shutil.which(comando)
                except Exception:  # pragma: no cover
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
    da_porta = _jogos_pela_porta(declarados)
    onde_estao = _com_os_da_porta(onde_estao, declarados, da_porta)
    do_disco = desenho.medir_no_disco(onde_estao, declarados, com_ponte=com_ponte,
                                      da_porta=da_porta)
    do_disco = dataclasses.replace(
        do_disco, sem_ambiente=_onde_falta_o_ambiente(onde_estao, declarados))

    viraram = _os_que_viraram_extensao()
    try:
        censo = sw.censo_do_wrapper(anotar=False)
    except Exception as erro:
        return desenho.Leitura(erros=(str(erro),), onde_estao=onde_estao,
                               declarados=declarados, do_disco=do_disco,
                               viraram_extensao=viraram)

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
        linha=slo.WRAPPER_LAUNCH,
        erros=tuple(censo.erros),
        do_disco=do_disco,
        viraram_extensao=viraram,
    )


PRAZO_DOS_JOGOS_DA_PORTA_S = 1.5


def _jogos_pela_porta(declarados: Sequence[desenho.SemCenso]) -> dict[str, object]:
    """``{chave do cartão: jogos}`` das extensões de lançador que entregam pela porta.

    BLOQUEIA (um RPC por extensão): só da vigia. A pergunta é o ``mods.jogos`` ao serviço, que
    guarda o que a extensão entregou pelo ``lancador.jogos``; o serviço fora do ar, a extensão sem
    conexão ou a resposta torta deixam a chave de fora, e o cartão fica sem contagem, que é a
    resposta honesta de «não sei». Nunca levanta.
    """
    from hefesto_dualsense4unix.app import ipc_bridge

    fora: dict[str, object] = {}
    for item in declarados:
        if not item.pela_porta or item.leitor is not None or not item.modificacao:
            continue
        try:
            corpo = ipc_bridge._corpo_do_daemon(
                "mods.jogos", {"mod": item.modificacao}, timeout=PRAZO_DOS_JOGOS_DA_PORTA_S)
        except Exception:
            _LOG.debug("jogos_da_porta_sem_resposta", exc_info=True)
            continue
        jogos = corpo.get("jogos") if isinstance(corpo, dict) else None
        if isinstance(jogos, list):
            fora[item.chave] = jogos
    return fora


def _com_os_da_porta(onde_estao: tuple[tuple[str, str], ...],
                     declarados: Sequence[desenho.SemCenso],
                     da_porta: dict[str, object]) -> tuple[tuple[str, str], ...]:
    """O cartão de extensão que entregou jogos pela porta conta como achado.

    A extensão é o lançador: o programa dela pode não ter atalho nem comando nesta máquina (um
    lançador que mora na rede, um script), e a lista que ela entregou é a prova de que ele está
    aqui. O ``onde`` diz de onde veio, em palavra de tela.
    """
    nomes = {x.chave: x.nome for x in declarados if x.pela_porta}
    return tuple((chave, onde or (f"pela extensão {nomes[chave]}"
                                  if chave in da_porta and chave in nomes else ""))
                 for chave, onde in onde_estao)


def _os_que_viraram_extensao() -> tuple[tuple[str, str, str], ...]:
    """``(chave, nome, endereço)`` de quem virou extensão, tem pasta aqui e não está instalado.

    É a linha da migração: quem usava o Lutris (ou o RetroArch, o Dolphin, o mGBA) lê na fila que
    o lançador virou extensão e o endereço. Nada se instala sozinho. Nunca levanta.
    """
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    try:
        achados = censo.lancadores_que_viraram_extensao()
        instaladas = {e.entrada.id for e in REGISTRO.ler()}
    except Exception:
        _LOG.debug("os_que_viraram_extensao_falhou", exc_info=True)
        return ()
    return tuple((x.chave, x.nome, x.endereco) for x in achados if x.chave not in instaladas)


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
    titulos: dict[str, str] = dataclasses.field(default_factory=dict)
    miolo_novo: str = ""

    def limpar(self) -> None:
        self.modo = self.lancador = self.miolo_novo = ""
        self.jogos = ()
        self.janelas = {}
        self.titulos = {}


_ESCOLHA = _Escolha()

_COM_BIBLIOTECA = ("heroic",)
_SEM_JOGOS = ("flatpak",)


def _chave_do_emulador(lancador: str) -> str:
    return f"emulador:{lancador}"


def _titulo_que_casa(titulo: str) -> str:
    """``PPSA21567`` → a expressão que acha o ID no título, e nada colado nele."""
    return rf"(?<!\w){re.escape(titulo)}(?!\w)"


def _biblioteca_da_extensao(item: desenho.SemCenso) -> Any:
    """A biblioteca do lançador da extensão: a do leitor dela ou a que ela entregou pela porta."""
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    if item.leitor is None and item.pela_porta:
        return censo.biblioteca_da_porta(item.nome, _jogos_pela_porta((item,)).get(item.chave))
    return censo.biblioteca_do_cartao(item.chave, leitor=item.leitor)


def _jogos_da_extensao(
    item: desenho.SemCenso, ja: set[str], marcado: str,
) -> tuple[list[desenho.JogoParaEscolher], dict[str, str]]:
    """Os jogos da extensão que casam uma janela, e o título de cada um que casa pelo título.

    O jogo com a janela própria (o ``janela`` que a extensão entrega, como o ``steam_app_N`` do
    jogo do Lutris que vai pelo Proton) entra pela chave da janela, como o do Heroic; o que só tem
    o ID no título entra pela chave dele, e o perfil casa pelo título (``_ESCOLHA.titulos``).
    """
    jogos: list[desenho.JogoParaEscolher] = []
    titulos: dict[str, str] = {}
    vistos: set[str] = set()
    for jogo in _biblioteca_da_extensao(item).jogos:
        if jogo.janela:
            chave = jogo.janela
        elif jogo.titulo_do_jogo:
            chave = jogo.chave
        else:
            continue
        if chave in ja or chave in vistos:
            continue
        vistos.add(chave)
        jogos.append(desenho.JogoParaEscolher(
            chave=chave, nome=jogo.nome, instalado=jogo.instalado, marcado=chave == marcado))
        if not jogo.janela:
            titulos[chave] = _titulo_que_casa(jogo.titulo_do_jogo)
    jogos.sort(key=lambda j: (not j.marcado, not j.instalado, j.nome.casefold()))
    return jogos, titulos


def _jogos_para_escolher(
    lancador: str, nome: str, state: dict[str, Any] | None,
) -> tuple[list[desenho.JogoParaEscolher], dict[str, tuple[str, ...]], bool]:
    """``(jogos, janelas por chave, é emulador)`` — a lista DAQUELE lançador.

    Só entra jogo com chave de janela (a regra da LANCADOR-AGNOSTICO-01); o jogo da escada nasce
    marcado (D-2109-O-JOGO-SE-ESCOLHE-NA-LISTA). O lançador de extensão lista os jogos do leitor
    ou da porta com a janela própria ou o ID do título (os títulos ficam em ``_ESCOLHA.titulos``);
    sem nenhum, sobra a linha «todos os jogos». Nunca levanta: é chamado de dentro de um clique.
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
            if item is not None and (item.leitor is not None or item.pela_porta):
                da_extensao, titulos = _jogos_da_extensao(item, ja, marcado)
                if da_extensao:
                    _ESCOLHA.titulos = titulos
                    return da_extensao, {}, False
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
    return _com_as_extensoes({"mesa": {}, "blocos": {}}, desenho.cartoes(lida),
                             lida.viraram_extensao if lida is not None else ())


@registrar("07-lancadores.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    """A aba inteira, e ela NÃO depende de controle nenhum."""
    carga = _resposta(VIGIA.agora(), ctx.state)
    valores = carga["mesa"]
    fora: dict[str, Any] = dict(valores)
    fora["blocos"] = dict(carga["blocos"])
    fora["sem_dono"] = {k: {"sem_dono": True, "oque": v} for k, v in SEM_DONO.items()}
    fora["cobertura"] = {"pintados": len(valores), "sem_dono": len(SEM_DONO)}
    return fora


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
    except Exception:  # pragma: no cover
        pass
    foco = _o_jogo_em_foco(state)
    if foco:
        try:
            return int(foco), ABERTO
        except ValueError:  # pragma: no cover
            pass
    try:
        marker = read_last_run_marker()
        if marker is not None:
            return marker[0], FECHADO
    except Exception:  # pragma: no cover
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
    """`Meu Emulador à Solta` → `meu emulador a solta`. Só para fabricar a CHAVE."""
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
        except Exception:  # pragma: no cover
            pastas = []
        for pasta in pastas:
            try:
                caminho = pasta / f"{nu}.desktop"
                if caminho.is_file():
                    return "atalhos", nu, str(caminho)
            except OSError:  # pragma: no cover
                continue

    try:
        achado = shutil.which(alvo)
    except Exception:  # pragma: no cover
        achado = None
    if achado:
        return "comandos", alvo, achado
    return "", "", ""


def _botoes_do_cartao_agora(chave: str) -> tuple[str, ...]:
    """Os botões que o cartão de `chave` tem ACESOS na 07 publicada NESTE instante.

    A fileira é a da página (`exp.BOTOES`, acesa por `exp.botao_ativo`): o achado acende «Criar
    perfis» e «Configurar», o não achado acende só o «Identificar». Não é a de `desenho.cartoes`,
    que descreve a fileira velha e já não é o que a tela mostra.
    """
    try:
        lida = VIGIA.agora()
        for cartao in desenho.cartoes(lida):
            if cartao.chave == chave:
                return tuple(rotulo for gesto, rotulo, _ in exp.BOTOES
                             if exp.botao_ativo(gesto, cartao.presente))
    except Exception:
        return ()
    return ()


def _recusa_de_quem_ja_tem_cartao(chave: str, nome: str,
                                  tem: tuple[str, ...] | None = None) -> str:
    """A recusa do botão global para um lançador que já tem cartão de fábrica.

    Cita só o botão que o cartão tem aceso: o «Configurar», que abre a janela do «Onde ele está».
    Sem ele aceso (o lançador não foi achado, ou a leitura falhou), a frase diz o fato e para.
    """
    if tem is None:
        tem = _botoes_do_cartao_agora(chave)
    abertura = f"{nome} já tem cartão nesta aba"

    if desenho.CONFIGURAR_ROTULO in tem:
        return (f"{abertura}. Use o «{desenho.CONFIGURAR_ROTULO}» do cartão dele, em «Onde ele "
                f"está» — assim o que você disser entra na busca daquele cartão, em vez de criar "
                f"um segundo.")

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
    except Exception:  # pragma: no cover
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
    except Exception:  # pragma: no cover
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


TTL_DO_REGISTRO_S = 1.0
CAMPO_DA_CONTA = "mod-conta"
JANELA_DA_EXTENSAO = "#modificacao"  # (noqa-acento)
JANELA_DO_LANCADOR = "#lanc-conf"
NOME_DO_ARQUIVO_DO_MANIFESTO = "hefesto-mod.json"
TITULO_DO_SELETOR_DA_EXTENSAO = "Escolha o hefesto-mod.json da pasta da extensão"


@dataclasses.dataclass(frozen=True)
class _Instalada:
    """Uma linha do registro com o manifesto relido e o estado vivo."""

    entrada: Any
    manifesto: Any
    estado: str = ""
    nota_do_css: str = ""
    porque: str = ""


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
    menu_na_conf: bool = False
    permissoes: str = ""
    remover: str = ""
    conf: str = ""
    imp: str = ""
    mod: str = ""
    impedimentos: tuple[Any, ...] = ()
    vistas: dict[str, tuple[str, ...]] = dataclasses.field(default_factory=dict)
    html_conf: str = ""
    html_imp: str = ""
    html_mod: str = ""
    agora: tuple[str, ...] = ()
    rascunho: dict[str, Any] = dataclasses.field(default_factory=dict)
    onde_escolhido: str = ""
    conf_da_modificacao: str = ""
    nota_do_css: str = ""
    aba: str = ""
    armada: tuple[str, ...] = ()
    descartar: tuple[str, ...] = ()
    desligada: bool = False
    pintura: exp.PinturaDaJanela = dataclasses.field(default_factory=exp.PinturaDaJanela)

    def limpar(self) -> None:
        self.menu = self.permissoes = self.remover = self.conf = self.imp = self.mod = ""
        self.menu_na_conf = False
        self.impedimentos = ()
        self.vistas = {}
        self.html_conf = self.html_imp = self.html_mod = ""
        self.agora = ()
        self.rascunho = {}
        self.onde_escolhido = self.conf_da_modificacao = self.nota_do_css = self.aba = ""
        self.armada = self.descartar = ()
        self.desligada = False
        self.pintura.esquecer()


_MEXIDA = _Mexida()

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
            fios.soltar("hefesto-agora", self._corpo,
                        mod, ponte)
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
    from hefesto_dualsense4unix.mods import tema
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
        nota = tema.css_da_extensao(manifesto, lg).recusa_curta if manifesto is not None else ""
        dela = vivo.get(mod_id) or {}
        saida.append(_Instalada(entrada, manifesto, str(dela.get("estado") or ""), nota,
                                _porque_do_supervisor(dela)))
    return tuple(saida)


TETO_DA_ULTIMA_LINHA = 160


def _porque_do_supervisor(dela: dict[str, Any]) -> str:
    """O motivo e a última linha do diário que o supervisor gravou: a dica da chave que não roda."""
    motivo = str(dela.get("motivo") or "").strip()
    linha = " ".join(str(dela.get("ultima_linha") or "").split())
    if len(linha) > TETO_DA_ULTIMA_LINHA:
        linha = linha[: TETO_DA_ULTIMA_LINHA - 1] + "…"
    return " ".join(x for x in (motivo, f"«{linha}»" if linha else "") if x)


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
    if _MEXIDA.menu == e.id and not _MEXIDA.menu_na_conf:
        pedidas = item.manifesto.permissoes if item.manifesto is not None else e.permissoes_aceitas
        aviso = aviso_por_ver(e, item.manifesto) if item.manifesto is not None else ""
        menu = exp.menu_html(
            e.id, [x for x in (aviso,) if x] + [o_que_a_permissao_deixa(x) for x in pedidas]
            if _MEXIDA.permissoes == e.id else None, remover=_MEXIDA.remover == e.id)
    dica = item.manifesto.descricao if item.manifesto is not None else ""
    versao = e.versao
    esperando = getattr(e, "versao_esperando", "")
    if esperando:
        versao = f"{e.versao} · a {esperando} espera o «Atualizar»"
        dica = " ".join(x for x in (getattr(e, "motivo_da_espera", ""), dica) if x)
    return exp.Extensao(
        chave=e.id, nome=e.nome, dica=dica, janela=JANELA_DA_EXTENSAO,
        versao=versao, selo=exp.SELO_DA_ORIGEM.get(e.origem, "Oficial"),
        ligada=e.ligada, menu=menu, processo=exp.processo_de(e.ligada, item.estado),
        porque=item.porque, pede=_o_que_pede(item))


def _o_que_pede(item: _Instalada) -> str:
    """O aviso e as permissões da extensão cuja chave já armou o «sim»: a dica da chave.

    Vazio quando a chave não está armada (o próximo clique não liga), ou quando a extensão já
    está ligada. O primeiro clique na chave não abre nada no cartão: as três ações moram no ⋮.
    """
    from hefesto_dualsense4unix.mods.instalador import aviso_por_ver
    from hefesto_dualsense4unix.mods.manifesto import o_que_a_permissao_deixa, permissoes_novas

    e, m = item.entrada, item.manifesto
    if e.ligada or m is None:
        return ""
    pedidas = tuple(sorted(m.permissoes))
    aviso = aviso_por_ver(e, m)
    if not (permissoes_novas(e.permissoes_aceitas, list(pedidas)) or aviso) or (
            _MEXIDA.vistas.get(e.id) != (*pedidas, aviso)):
        return ""
    return " ".join([x for x in (aviso,) if x] + [o_que_a_permissao_deixa(x) for x in pedidas])


def _jogos_da_fila(lanc: desenho.Lancador) -> str:
    """A contagem da fila: «48 jogos», sem o «instalados» do cartão velho.

    A linha da fila só tem lugar para a contagem: a frase do cartão velho («Abra o Heroic uma
    vez…») passava por baixo dos três botões, e fica fora. A biblioteca lida (o Heroic, a
    extensão de lançador) conta os instalados: «12 jogos na biblioteca · 2 instalados» vira
    «2 jogos», o mesmo número que a Steam conta.
    """
    if not lanc.presente:
        return ""
    lida = _BIBLIOTECA_DA_FILA.fullmatch(lanc.jogos)
    conta = f"{lida[1]} {'jogo' if lida[1] == '1' else 'jogos'}" if lida else (
        lanc.jogos.replace("jogos instalados", "jogos").replace("jogo instalado", "jogo"))
    return conta if _CONTAGEM_DA_FILA.fullmatch(conta) else ""


_CONTAGEM_DA_FILA = re.compile(r"\d+ jogos?")
_BIBLIOTECA_DA_FILA = re.compile(r"\d+ jogos? na biblioteca · (\d+) instalados?")


def _fila_de(lancadores: list[desenho.Lancador],
             viraram: Sequence[tuple[str, str, str]] = ()) -> list[Any]:
    """A fila: um por cartão e, no fim, a linha da migração de cada um que virou extensão."""
    cartoes = {x.chave for x in lancadores}
    return [exp.Fila(chave=x.chave, nome=x.nome, jogos=_jogos_da_fila(x), achado=x.presente,
                     configurar=JANELA_DO_LANCADOR) for x in lancadores] + [
        exp.Fila(chave=chave, nome=nome, jogos="", achado=False,
                 configurar=JANELA_DO_LANCADOR, virou=endereco)
        for chave, nome, endereco in viraram if chave not in cartoes]


def _com_as_extensoes(carga: dict[str, Any], lancadores: list[desenho.Lancador],
                      viraram: Sequence[tuple[str, str, str]] = ()) -> dict[str, Any]:
    """Acrescenta à carga da aba o quadro das extensões, a fila e as janelas abertas."""
    instaladas = REGISTRO.ler()
    carga["mesa"][CAMPO_DA_CONTA] = exp.conta_das_extensoes(len(instaladas))
    carga["mesa"][exp.CAMPO_DA_BARRA_FORA] = ""
    blocos = carga["blocos"]
    blocos[".ext-lista"] = exp.extensoes_html([_extensao_de(i) for i in instaladas])
    blocos[".lanc-fila"] = exp.fila_com_novo_html(_fila_de(lancadores, viraram))
    _seguir_o_meu_css(instaladas)
    janelas = (("#lanc-janela", _MEXIDA.html_conf), ("#imp-janela", _MEXIDA.html_imp),
               ("#lanc-escolha", _ESCOLHA.miolo_novo))
    for seletor, miolo in janelas:
        if miolo:
            blocos[seletor] = miolo
    if _MEXIDA.html_mod and _MEXIDA.agora:
        dela = next((i for i in instaladas if i.entrada.id == _MEXIDA.mod), None)
        blocos["#mod-agora"] = exp.agora_html(
            _MEXIDA.agora, _AGORA.agora(),
            processo=exp.processo_de(dela.entrada.ligada, dela.estado) if dela else "",
            porque=dela.porque if dela else "")
    carga = _com_os_aparelhos(carga)
    carga["blocos"] = {**_MEXIDA.pintura.blocos(_MEXIDA.html_mod), **carga["blocos"]}
    return carga


def _id_do_clique(o: dict[str, Any], gesto_: str) -> str:
    mod_id = str(o.get("v") or "").strip()
    if not mod_id:
        _LOG.warning("%s: clique sem `data-v`", gesto_)
        raise ValueError("O clique não disse de qual extensão se trata. Nada foi alterado.")
    return mod_id


def _a_instalada_ou_nada(mod_id: str) -> _Instalada | None:
    REGISTRO.esquecer()
    return next((i for i in REGISTRO.ler() if i.entrada.id == mod_id), None)


def _a_instalada(mod_id: str) -> _Instalada:
    item = _a_instalada_ou_nada(mod_id)
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


def _seguir_o_meu_css(instaladas: Sequence[_Instalada]) -> None:
    """A janela da extensão aberta segue o ``meu.css`` salvo, como a página segue a folha: a frase
    da recusa entra e sai sem reabrir a janela. Usa só o que o registro já leu."""
    if not (_MEXIDA.html_mod and _MEXIDA.mod):
        return
    item = next((i for i in instaladas if i.entrada.id == _MEXIDA.mod), None)
    if item is not None and item.manifesto is not None and item.nota_do_css != _MEXIDA.nota_do_css:
        _montar_a_janela_da_extensao(_MEXIDA.mod, item)


def _montar_a_janela_da_extensao(mod_id: str, item: _Instalada | None = None) -> None:
    """O miolo da janela de opções: o valor guardado de cada opção, com o rascunho por cima."""
    from hefesto_dualsense4unix.mods import opcoes

    item = item or _a_instalada(mod_id)
    manifesto = item.manifesto
    if manifesto is None:
        raise RuntimeError("O manifesto desta extensão não pôde ser lido. Nada foi alterado.")
    guardados = opcoes.ler(manifesto, _lugares())
    valores = {**guardados, **(_MEXIDA.rascunho if _MEXIDA.mod == mod_id else {})}
    jogos = _jogos_com_perfil() if any(x.tipo == "jogos" for x in manifesto.opcoes) else ()
    nota = _MEXIDA.nota_do_css = item.nota_do_css
    aparecem = opcoes.aparecem(manifesto, valores)
    linhas = [exp.OpcaoDaJanela(
        mod=mod_id, id=x.id, rotulo=x.rotulo, tipo=x.tipo, valor=_valor_na_tela(valores[x.id]),
        escolhas=tuple(x.escolhas), grupo=x.grupo or "", minimo=x.minimo or 0,
        maximo=x.maximo or 0, passo=x.passo or 1,
        jogos=jogos if x.tipo == "jogos" else (),
        nota=nota if x.tipo == "css" else "",
        formas=_formas_da_opcao(manifesto, x, valores),
        botoes=x.botoes_da_janela if x.tipo == "por_botao" else (),
        modo=_o_modo_de(manifesto, valores) if x.tipo == "livre" else "",
        dica=x.dica or "", unidade=x.unidade or "", zero=x.zero or "")
        for x in manifesto.opcoes if x.id in aparecem and x.id != manifesto.chave]
    chave = bool(guardados[manifesto.chave]) if manifesto.chave else None
    _MEXIDA.desligada = chave is False
    _MEXIDA.mod = mod_id
    _VIVA.com_o_modo(mod_id, _o_modo_de(manifesto, valores) or None)
    _MEXIDA.agora = tuple(manifesto.agora)
    estado = _estado_da_janela(manifesto)
    _MEXIDA.html_mod = exp.modificacao_miolo_html(
        manifesto.nome, linhas, mod=mod_id, agora=_MEXIDA.agora,
        estado=estado, parar_tudo=manifesto.parar_tudo, chave=chave,
        aba=_MEXIDA.aba, processo=exp.processo_de(item.entrada.ligada, item.estado),
        porque=item.porque, rascunho=_o_rascunho_da_janela(mod_id, guardados),
        **_pecas_da_janela(manifesto, mod_id))


def _o_rascunho_da_janela(mod_id: str, guardados: dict[str, Any]) -> exp.Rascunho:
    """Pendente quando um valor do rascunho difere do guardado; o Descartar armado vale só para
    o rascunho de quando foi armado (mudar uma opção depois o desarma)."""
    rascunho = _MEXIDA.rascunho if _MEXIDA.mod == mod_id else {}
    pendente = any(k not in guardados or guardados[k] != v for k, v in rascunho.items())
    return exp.Rascunho(pendente, pendente and _MEXIDA.descartar == _o_armar_do_descartar(mod_id))


def _o_armar_do_descartar(mod_id: str) -> tuple[str, ...]:
    import json

    return (mod_id, json.dumps(_MEXIDA.rascunho, sort_keys=True, default=str))


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
    """Liga ou desliga pela infra. Permissão nova pede o «sim»: o primeiro clique só arma.

    A chave armada diz «Aceitar e ligar», com o aviso e as permissões na dica (``_o_que_pede``;
    o recado não chega à tela), e o ``None`` é o clique que só armou.
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
    _MEXIDA.armada = ()
    _MEXIDA.menu = _MEXIDA.permissoes = ""
    mod_id = _id_do_clique(o, "configurar-modificacao")
    anterior = _VIVA.mod
    recusa = _desfazer_o_modo(anterior, p) if anterior else None
    _MEXIDA.rascunho = (_o_modo_que_vale(mod_id) if recusa is not None and anterior == mod_id
                        else {})
    _MEXIDA.mod, _MEXIDA.aba, _MEXIDA.descartar = mod_id, "", ()
    _MEXIDA.pintura.esquecer()
    _AGORA.abrir(mod_id, p)
    _AGORA.ler(mod_id, p)
    _montar_a_janela_da_extensao(mod_id)
    carga = _a_pintura_agora(ctx)
    return {**carga, "recado": recusa} if recusa else carga


@gesto("07-lancadores.html", exp.GESTO_DO_PARAR)
def parar_tudo_da_modificacao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O «Parar tudo» da janela: o serviço publica o gesto ``para`` só para esta extensão."""
    _MEXIDA.armada = ()
    mod_id = _id_do_clique(o, exp.GESTO_DO_PARAR)
    ok, motivo, corpo = p.chamar_com_o_corpo(METODO_DO_PARAR, mod=mod_id)
    if not ok:
        raise RuntimeError(motivo or "O serviço não respondeu. Nada foi parado.")
    if not (isinstance(corpo, dict) and corpo.get("parado") is True):
        raise RuntimeError(f"{_a_instalada(mod_id).entrada.nome} não está rodando: nada a parar.")
    _AGORA.esquecer()
    return {**_a_pintura_agora(ctx), "recado": "Parar tudo enviado."}


def _guardar_a_chave_da_modificacao(mod_id: str, ligada: bool) -> None:
    """A opção da chave gravada na hora, fora do rascunho (as outras mudanças dele ficam)."""
    from hefesto_dualsense4unix.mods import opcoes

    item = _a_instalada(mod_id)
    if item.manifesto is None or not item.manifesto.chave:
        raise RuntimeError("Esta extensão não tem a chave Ligado/Desligado. Nada foi guardado.")
    with _dizendo_a_recusa():
        opcoes.guardar(item.manifesto, item.manifesto.chave, ligada, _lugares())


@gesto("07-lancadores.html", exp.GESTO_DA_CHAVE_DA_EXTENSAO,
       grava="_guardar_a_chave_da_modificacao")
def chave_da_modificacao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """A chave Ligado/Desligado do topo da janela: grava na hora o contrário do guardado.

    Desligar pede ao serviço o gesto ``para`` (``mods.parar_tudo``), que grava a chave de novo e
    põe os aparelhos a zero; com a extensão fora da porta, a chave fica desligada assim mesmo.
    Ligar só grava: a extensão relê as opções a cada volta.
    """
    _MEXIDA.armada = ()
    from hefesto_dualsense4unix.mods import opcoes

    mod_id = _id_do_clique(o, exp.GESTO_DA_CHAVE_DA_EXTENSAO)
    item = _a_instalada(mod_id)
    manifesto = item.manifesto
    if manifesto is None or not manifesto.chave:
        raise RuntimeError("Esta extensão não tem a chave Ligado/Desligado. Nada foi guardado.")
    ligada = not bool(opcoes.ler(manifesto, _lugares())[manifesto.chave])
    _guardar_a_chave_da_modificacao(mod_id, ligada)
    recado = "Ligada." if ligada else "Desligada: os aparelhos estão a zero."
    if not ligada:
        ok, _motivo, corpo = p.chamar_com_o_corpo(METODO_DO_PARAR, mod=mod_id)
        if not ok or not (isinstance(corpo, dict) and corpo.get("parado") is True):
            recado = "Desligada."
    _AGORA.esquecer()
    _montar_a_janela_da_extensao(mod_id)
    return {**_a_pintura_agora(ctx), "recado": recado}


@gesto("07-lancadores.html", "guardar-opcao-da-modificacao",
       grava="_guardar_a_opcao_da_modificacao")
def guardar_opcao_da_modificacao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Uma opção da janela, validada, grava na hora no ``opcoes.json``: a janela nunca mostra uma
    escolha que não vale (medido em 28/10/2026: o rascunho esperava um Guardar que não se via, e o
    Sacudir e o Inclinar em «Direto» na janela seguiam «Nenhum» no disco).

    A caixa e o número agem no ``change``; a chave de ligado, no clique.
    """
    _MEXIDA.armada = ()
    from hefesto_dualsense4unix.mods import opcoes

    mod_id, _, resto = _id_do_clique(o, "guardar-opcao-da-modificacao").partition(":")
    opcao_id, _, jogo = resto.partition(":")
    item = _a_instalada(mod_id)
    declaradas = item.manifesto.opcoes if item.manifesto else ()
    opcao = next((x for x in declaradas if x.id == opcao_id), None)
    if opcao is None:
        raise RuntimeError("Esta extensão não tem essa opção. Nada foi guardado.")
    evento = str(o.get("evento") or "")
    if opcao.tipo in ("ligado", "css"):
        if evento == "change":
            return None
        valor: Any = not bool(_valor_na_janela(item, opcao))
    elif opcao.tipo == "jogos":
        if evento == "click":
            return None
        valor = _jogos_com_a_caixa(_valor_na_janela(item, opcao), jogo)
    elif opcao.tipo == "por_botao":
        if evento == "click":
            return None
        if jogo not in opcao.botoes_da_janela:
            raise RuntimeError("Qual botão? O clique não disse. Nada foi guardado.")
        valor = {**_valor_na_janela(item, opcao), jogo: o.get("valor")}
    else:
        if evento == "click":
            return None
        valor = o.get("valor")
    with _dizendo_a_recusa():
        certo = opcoes.validar(opcao, valor, formas_extras=_formas_da_janela(item))
    if _MEXIDA.mod != mod_id:
        _MEXIDA.mod, _MEXIDA.rascunho = mod_id, {}
    _MEXIDA.rascunho[opcao_id] = certo
    _MEXIDA.aba = opcao.grupo or ""
    _guardar_a_opcao_da_modificacao(mod_id)
    _montar_a_janela_da_extensao(mod_id)
    return _a_pintura_agora(ctx)


def _abrir_no_editor(alvo: pathlib.Path) -> None:
    """Pede o arquivo ao editor padrão do sistema (``xdg-open``), sem esperar por ele."""
    import subprocess

    try:
        subprocess.Popen(["xdg-open", str(alvo)], start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except OSError as erro:
        raise RuntimeError(f"Não consegui abrir o editor. O arquivo está em {alvo}.") from erro


def _criar_o_css_da_modificacao(mod_id: str) -> pathlib.Path:
    """O ``meu.css`` da extensão, criado com o exemplo comentado se ainda não existe."""
    from hefesto_dualsense4unix.mods import meu_css

    return meu_css.garantir(mod_id, _lugares())


@gesto("07-lancadores.html", exp.GESTO_DO_CSS, grava="_criar_o_css_da_modificacao")
def editar_o_css_da_modificacao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Editar o meu CSS»: o ``meu.css`` da extensão nasce com o exemplo, se ainda não existe, e
    abre no editor do sistema. Salvar o aplica na janela, sem reabrir (o vigia é o do tema)."""
    _MEXIDA.armada = ()
    mod_id, _, opcao_id = _id_do_clique(o, exp.GESTO_DO_CSS).partition(":")
    item = _a_instalada(mod_id)
    opcao = item.manifesto.opcao_do_css if item.manifesto else None
    if opcao is None or opcao.id != opcao_id:
        raise RuntimeError("Esta extensão não aceita o CSS de quem usa. Nada foi aberto.")
    _abrir_no_editor(_criar_o_css_da_modificacao(mod_id))
    return _a_pintura_agora(ctx)


@gesto("07-lancadores.html", exp.GESTO_DO_GUARDAR, grava="_guardar_a_opcao_da_modificacao")
def guardar_modificacao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O Guardar da janela da extensão: grava o rascunho inteiro em ``opcoes.json``."""
    _MEXIDA.armada = ()
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
        for opcao_id, valor in _livre_primeiro(item.manifesto, rascunho):
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
    na_conf = o.get("onde") == exp.ONDE_DA_CONF
    if not acao:
        mesmo = _MEXIDA.menu == mod_id and _MEXIDA.menu_na_conf == na_conf
        _MEXIDA.menu = "" if mesmo else mod_id
        _MEXIDA.menu_na_conf = na_conf
        _MEXIDA.permissoes = _MEXIDA.remover = ""
        _repintar_a_conf_da(mod_id)
        return _a_pintura_agora(ctx)
    _MEXIDA.menu, _MEXIDA.menu_na_conf = mod_id, na_conf
    if acao == "permissoes":  # (noqa-acento)
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
    from hefesto_dualsense4unix.mods.instalador import atualizar, aviso_por_ver, remover

    item = _a_instalada(mod_id)
    nome = item.entrada.nome
    lg = _lugares()
    with _dizendo_a_recusa():
        if acao == "atualizar":
            nomes = _nomes_das_instaladas(lg)
            feito = atualizar(mod_id, lugares=lg)
            REGISTRO.esquecer()
            aviso = aviso_por_ver(feito.entrada, feito.manifesto)
            if feito.permissoes_novas or aviso:
                _MEXIDA.vistas[mod_id] = (*sorted(feito.manifesto.permissoes), aviso)
                _MEXIDA.menu = _MEXIDA.permissoes = mod_id
                _MEXIDA.remover = ""
            extra = (" Ela pede permissão nova: ligue-a de novo para aceitar."
                     if feito.permissoes_novas else "")
            return (f"{nome} atualizada para a versão {feito.entrada.versao}."
                    f"{_saiu(feito.substituidas, nomes)}{extra}")
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

    O ``aviso`` do manifesto fica por ver: o recado do gesto não chega à tela, e o ⋮ do
    primeiro «sim» da chave o mostra antes de a extensão fazer qualquer coisa.
    """
    from hefesto_dualsense4unix.mods.instalador import instalar

    lg = _lugares()
    nomes = _nomes_das_instaladas(lg)
    with _dizendo_a_recusa():
        feito = instalar(origem, lugares=lg)
    REGISTRO.esquecer()
    return (f"{feito.entrada.nome} instalada.{_saiu(feito.substituidas, nomes)} "
            "Ligue-a na chave quando quiser.")


def _nomes_das_instaladas(lg: Any) -> dict[str, str]:
    """O nome de cada extensão instalada, lido ANTES de instalar: a que o ``substitui`` manda
    embora sai do registro, e o recado a conhece pelo nome (sem ele, pelo id). Nunca levanta."""
    from hefesto_dualsense4unix.mods.instalador import InstalacaoRecusadaError, ler_registro

    try:
        return {mod_id: e.nome for mod_id, e in ler_registro(lg.registro).items()}
    except (InstalacaoRecusadaError, OSError):
        return {}


def _saiu(ids: Sequence[str], nomes: dict[str, str]) -> str:
    """« Saiu a X.» (ou « Saíram a X e a Y.»), com o espaço da frase de antes; vazio sem nenhuma."""
    if not ids:
        return ""
    citadas = [f"a {nomes.get(mod_id, mod_id)}" for mod_id in ids]
    lista = citadas[0] if len(citadas) == 1 else f"{', '.join(citadas[:-1])} e {citadas[-1]}"
    return f" {'Saiu' if len(ids) == 1 else 'Saíram'} {lista}."


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


def _montar_a_conf(chave: str, state: dict[str, Any] | None = None) -> None:
    """O miolo da janela «Configurar», com o que o produto sabe do lançador e o rascunho dela."""
    from hefesto_dualsense4unix.integrations.censo_dos_lancadores import lancadores_com_jogos
    from hefesto_dualsense4unix.mods.manifesto import o_que_a_permissao_deixa

    lida = VIGIA.agora()
    cartao = next((x for x in desenho.cartoes(lida) if x.chave == chave), None)
    if cartao is None:
        raise RuntimeError("Não conheço esse lançador. Nada foi alterado.")
    mod_id = next((x.modificacao for x in _declarados() if x.chave == chave and x.modificacao), "")
    onde = dict(lida.onde_estao).get(chave, "") if lida is not None else ""
    impedimentos = len(_MEXIDA.impedimentos) if chave == desenho.STEAM else None
    menu = ""
    if mod_id and _MEXIDA.menu == mod_id and _MEXIDA.menu_na_conf:
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
        perfil_por_jogo=_perfil_por_jogo(chave) if chave in lancadores_com_jogos() else None,
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
    except Exception:  # pragma: no cover
        return ()


def _perfil_por_jogo(chave: str) -> bool:
    """A chave «Cada jogo ganha o seu perfil» deste lançador, no ``maquina.json``; nasce ligada."""
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina

    try:
        return carregar_maquina().perfil_por_jogo.get(chave, True)
    except Exception:  # pragma: no cover
        return True


@gesto("07-lancadores.html", "configurar-lancador")
def configurar_lancador(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Configurar»: a janela igual para todos. A Steam sonda os impedimentos ao abrir."""
    chave = _id_do_clique(o, "configurar-lancador")
    _MEXIDA.conf = chave
    _MEXIDA.onde_escolhido = ""
    _MEXIDA.menu = _MEXIDA.permissoes = _MEXIDA.remover = ""
    _MEXIDA.menu_na_conf = False
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

PONTE: set[str] = {"chamar", "chamar_detalhado", "resultado", "machine_declare", "escolher_arquivo"}
METODOS: set[str] = {"machine.declare", METODO_DO_AGORA, METODO_DO_PARAR}


PAGINA = "07-lancadores.html"
PISO_DA_ABA = 14

PROVAS: list[dict[str, Any]] = []

SEM_ECO: tuple[str, ...] = (
           desenho.ADICIONAR, desenho.PROCURAR_O_ARQUIVO,
           "ligar-modificacao", "configurar-modificacao", "guardar-opcao-da-modificacao",
           "mais-da-modificacao", "instalar-modificacao", "escolher-arquivo-da-modificacao",
           exp.GESTO_DO_PARAR, exp.GESTO_DA_CHAVE_DA_EXTENSAO,
           exp.GESTO_DO_GUARDAR, exp.GESTO_DE_ESCOLHER,
           exp.GESTO_DO_GUARDAR_LANCADOR,
           "ver-impedimentos", "resolver-impedimento", "resolver-todos-os-impedimentos",
           "identificar-lancador", "configurar-lancador", "criar-perfil-do-jogo")



METODO_DA_ACAO = "mods.acao"
METODO_DO_LIVRE = "mods.livre"
TETO_DO_EM_CURSO_S = 5.0
SEGUNDOS_DA_GRAVACAO = 160.0
LACO_MINIMO_S = 0.1


class _Viva:
    """O que as peças que agem seguram entre um gesto e outro, de UMA extensão: as ações à espera
    do estado novo e o controle livre (o valor, o rastro, a gravação e, com ``modos``, o modo e o
    trecho que o «Repetir» toca em laço).

    O arrastar chega por gestos vivos, cada um na sua thread: a série do vivo e o carimbo do
    evento descartam o que chega fora de ordem, e a chamada ao serviço sai dentro da trava, na
    ordem em que foi aceita.
    """

    def __init__(self) -> None:
        self._trava = threading.Lock()
        self._zerar("")

    def _zerar(self, mod: str) -> None:
        self.mod = mod
        self.em_curso: dict[tuple[str, str], tuple[int, float]] = {}
        self.valor = 0.0
        self.ultimo_vivo = (float("-inf"), 0)
        self.solto_em = float("-inf")
        self.rastro: list[tuple[float, float]] = []
        self.gravando = False
        self.gravadas: list[tuple[float, float]] = []
        self.modo: str | None = None
        self.trecho: list[tuple[float, float]] = []
        self.ultimo: list[tuple[float, float]] = []
        self.laco: tuple[float, float] | None = None
        self.laco_ate = 0.0

    def _da(self, mod: str) -> None:
        if mod != self.mod:
            self._zerar(mod)

    def com_o_modo(self, mod: str, modo: str | None) -> None:
        """O modo que a janela de ``mod`` mostra, a cada vez que ela se monta."""
        with self._trava:
            self._da(mod)
            self.modo = modo

    def _anotar(self, t: float, valor: float) -> None:
        self.valor = valor
        self.rastro = [(a, v) for a, v in self.rastro if t - a <= 2 * exp.RASTRO_S]
        self.rastro.append((t, valor))
        if self.gravando:
            self.gravadas.append((t, valor))

    def _assentar(self, agora: float) -> None:
        """O laço do «Repetir» entra no rastro (e na gravação) até ``agora``: cada volta toca o
        trecho do último soltar com os tempos dele."""
        if self.laco is None:
            return
        inicio, periodo = self.laco
        t0 = self.ultimo[0][0]
        desde = max(self.laco_ate, agora - 2 * exp.RASTRO_S)
        volta = max(0, int((desde - inicio) // periodo))
        while (base := inicio + volta * periodo) <= agora:
            for t, v in self.ultimo[:-1]:
                if desde < base + (t - t0) <= agora:
                    self._anotar(base + (t - t0), v)
            volta += 1
        self.laco_ate = agora

    def _soltar_no_modo(self, agora: float, modo: str | None) -> None:
        """O que a barra faz ao soltar: «Soltar» volta a 0, «Segurar» fica e «Repetir» toca o
        trecho em laço (o curto demais fica)."""
        self.laco = None
        if modo == "soltar" and self.valor:
            self._anotar(agora, 0.0)
        elif modo == "repetir" and len(self.ultimo) >= 2 and (
                self.ultimo[-1][0] - self.ultimo[0][0] >= LACO_MINIMO_S):
            self.laco = (agora, self.ultimo[-1][0] - self.ultimo[0][0])
            self.laco_ate = agora - 1e-6
            self._assentar(agora)

    def marcar(self, mod: str, acao: str, alvo: str, serie: int) -> None:
        with self._trava:
            self._da(mod)
            self.em_curso[(acao, alvo)] = (serie, time.monotonic())

    def esperando(self, mod: str, estado: dict[str, Any] | None) -> frozenset[tuple[str, str]]:
        """As ações à espera: saem quando a extensão devolve um estado novo, ou no teto."""
        serie = estado.get("serie") if isinstance(estado, dict) else None
        with self._trava:
            if mod != self.mod:
                return frozenset()
            agora = time.monotonic()
            self.em_curso = {
                k: (s, t) for k, (s, t) in self.em_curso.items()
                if agora - t < TETO_DO_EM_CURSO_S and not (isinstance(serie, int) and serie > s)}
            return frozenset(self.em_curso)

    def enviar(self, mod: str, opcao_id: str, valor: float, *, vivo: int, carimbo: float,
               soltou: bool, ponte: Any) -> tuple[bool, str | None, Any] | None:
        """O arrastar (ou o soltar) do livre ao serviço; ``None`` quando chegou fora de ordem.

        A ordem é a do carimbo do evento, e a série do vivo só desempata: a série recomeça em cada
        página que a janela carrega (medido em 28/10/2026: depois de trocar de aba, a faixa «Ao
        vivo» caía inteira como fora de ordem, até a série nova passar a antiga)."""
        with self._trava:
            self._da(mod)
            if soltou:
                self.solto_em = max(self.solto_em, carimbo)
            elif (carimbo, vivo) <= self.ultimo_vivo or carimbo <= self.solto_em:
                return None
            else:
                self.ultimo_vivo = (carimbo, vivo)
            agora = time.monotonic()
            self._assentar(agora)
            if not soltou and self.laco is not None:
                self.laco, self.trecho = None, []
            self._anotar(agora, valor)
            self.trecho.append((agora, valor))
            if soltou:
                self.ultimo, self.trecho = self.trecho, []
                self._soltar_no_modo(agora, self.modo)
            com_o_modo = {"modo": self.modo} if self.modo else {}
            return ponte.chamar_com_o_corpo(  # type: ignore[no-any-return]
                METODO_DO_LIVRE, mod=mod, id=opcao_id, valor=valor, soltou=soltou, **com_o_modo)

    def mudar_o_modo(self, mod: str, opcao_id: str, modo: str,
                     ponte: Any) -> tuple[bool, str | None, Any] | None:
        """O modo novo vale na hora, como um soltar nele: a barra faz o que ele faz e, depois de um
        arrastar, a extensão recebe o soltar com o valor de agora e o modo novo. ``None`` quando
        o modo não mudou ou nada foi arrastado nesta janela. O soltar que não chega à extensão
        (recusado, ou ela fora da porta) devolve a barra e o modo ao que eram."""
        with self._trava:
            self._da(mod)
            if modo == self.modo:
                return None
            antes = (self.modo, self.valor, list(self.rastro), list(self.gravadas), self.laco,
                     self.laco_ate)
            self.modo = modo
            if not self.rastro:
                return None
            agora = time.monotonic()
            self._assentar(agora)
            valor = self.valor
            self._soltar_no_modo(agora, modo)
            resposta: tuple[bool, str | None, Any] = ponte.chamar_com_o_corpo(
                METODO_DO_LIVRE, mod=mod, id=opcao_id, valor=valor, soltou=True, modo=modo)
            if _a_recusa_do_soltar(resposta) is not None:
                (self.modo, self.valor, self.rastro, self.gravadas, self.laco,
                 self.laco_ate) = antes
            return resposta

    def sem_a_extensao(self, mod: str, modo: str) -> None:
        """A extensão fora da porta não segura modo nenhum (ao voltar, ela lê o guardado): a barra
        faz o ``modo`` sem mandar nada."""
        with self._trava:
            self._da(mod)
            if modo == self.modo:
                return
            self.modo = modo
            if self.rastro:
                agora = time.monotonic()
                self._assentar(agora)
                self._soltar_no_modo(agora, modo)

    def modo_de(self, mod: str) -> str | None:
        """O modo que vale agora na barra (e na extensão) de ``mod``, ou ``None``."""
        with self._trava:
            return self.modo if mod == self.mod else None

    def ao_vivo(self, mod: str) -> exp.LivreAoVivo:
        with self._trava:
            if mod != self.mod:
                return exp.LivreAoVivo()
            agora = time.monotonic()
            self._assentar(agora)
            return exp.LivreAoVivo(self.valor, self.gravando, tuple(self.rastro), agora)

    def gravar(self, mod: str) -> list[tuple[float, float]] | None:
        """Começa a gravar (devolve ``None``) ou para, e devolve o que se arrastou."""
        with self._trava:
            self._da(mod)
            agora = time.monotonic()
            self._assentar(agora)
            if not self.gravando:
                self.gravando, self.gravadas = True, [(agora, self.valor)]
                return None
            self.gravando = False
            amostras, self.gravadas = [*self.gravadas, (agora, self.valor)], []
            return amostras


_VIVA = _Viva()


def passos_da_gravacao(amostras: Sequence[tuple[float, float]]) -> list[list[float]]:
    """O arrastar gravado como forma: ``[[força, segundos], ...]``, no máximo 16 passos de 10 s.

    ``amostras`` é ``(instante, valor)``, a última o instante do «Parar»: cada valor vale até o
    seguinte. O tempo se divide em 16 fatias iguais (até 160 s), cada fatia leva a média da força
    pesada pelo tempo, e as vizinhas iguais se juntam enquanto cabem em 10 s. Sem arrastar
    nenhum (um valor só), a lista é vazia.
    """
    from hefesto_dualsense4unix.mods.manifesto import PASSOS_DA_FORMA, SEGUNDOS_DO_PASSO

    if len(amostras) < 3:
        return []
    inicio = amostras[0][0]
    fim = min(amostras[-1][0], inicio + SEGUNDOS_DA_GRAVACAO)
    if fim - inicio <= 0:
        return []
    fatia = (fim - inicio) / PASSOS_DA_FORMA
    trechos = [(t, amostras[n + 1][0], v) for n, (t, v) in enumerate(amostras[:-1])]
    passos: list[list[float]] = []
    for n in range(PASSOS_DA_FORMA):
        a, b = inicio + n * fatia, inicio + (n + 1) * fatia
        soma = sum(v * (min(b, t1) - max(a, t0)) for t0, t1, v in trechos if t1 > a and t0 < b)
        forca = round(max(0.0, min(1.0, soma / fatia)), 2)
        if passos and passos[-1][0] == forca and passos[-1][1] + fatia <= SEGUNDOS_DO_PASSO:
            passos[-1][1] += fatia
        else:
            passos.append([forca, fatia])
    return [[f, max(0.01, round(s, 2))] for f, s in passos]


def _nome_da_forma_nova(formas: dict[str, Any]) -> str:
    n = 1
    while f"Meu {n}" in formas:
        n += 1
    return f"Meu {n}"


def _formas_do_livre_na_janela(item: _Instalada) -> dict[str, Any]:
    """As formas gravadas que a janela mostra agora: o rascunho, ou o guardado."""
    from hefesto_dualsense4unix.mods import opcoes

    livre = item.manifesto.opcao_livre if item.manifesto else None
    if livre is None:
        return {}
    return dict(opcoes.formas_do_livre(item.manifesto, {livre.id: _valor_na_janela(item, livre)}))


def _formas_da_janela(item: _Instalada) -> tuple[str, ...]:
    """Os nomes das formas gravadas no livre (o rascunho por cima): os botões as aceitam."""
    return tuple(_formas_do_livre_na_janela(item))


def _formas_da_opcao(manifesto: Any, opcao: Any, valores: dict[str, Any]) -> tuple[Any, ...]:
    """As formas que a linha da opção mostra: as declaradas e, num ``por_botao``, as gravadas no
    ``livre`` da mesma extensão (nunca as de outra)."""
    from hefesto_dualsense4unix.mods import opcoes

    formas = dict(opcao.formas)
    if opcao.tipo == "por_botao":
        formas.update(opcoes.formas_do_livre(manifesto, valores))
    return tuple((f, tuple((a, b) for a, b in passos)) for f, passos in formas.items())


def _livre_primeiro(manifesto: Any, rascunho: dict[str, Any]) -> list[tuple[str, Any]]:
    """O rascunho com o ``livre`` na frente: o ``por_botao`` que usa uma forma gravada agora só
    passa depois que ela está no disco."""
    livre = manifesto.opcao_livre if manifesto else None
    return sorted(rascunho.items(), key=lambda par: livre is None or par[0] != livre.id)


def _o_modo_de(manifesto: Any, valores: dict[str, Any]) -> str:
    """O modo do ``livre`` com ``modos`` que a janela mostra (o rascunho por cima do guardado), ou
    vazio sem ``modos``."""
    from hefesto_dualsense4unix.mods import opcoes

    chave = opcoes.chave_do_modo(manifesto)
    return str(valores.get(chave) or "") if chave else ""


def _estado_da_janela(manifesto: Any) -> dict[str, Any] | None:
    """O ``acessorios.estado`` que a janela desenha: com a coluna «Agora», com aparelhos ou com
    os controles deles."""
    return (_AGORA.agora() if _MEXIDA.agora or manifesto.aparelhos_acoes
            or manifesto.aparelhos_controles else None)


def _aba_dos_controles(manifesto: Any) -> str:
    """A aba dos controles dos aparelhos (``aparelhos_controles.grupo``), ou vazio sem ela."""
    return str(manifesto.aparelhos_controles.grupo) if manifesto.aparelhos_controles else ""


def _acao_da_janela(a: Any) -> exp.AcaoDaJanela:
    return exp.AcaoDaJanela(a.id, a.rotulo, a.grupo or "", a.icone or "")


def _aparelhos_da_janela(manifesto: Any) -> exp.AparelhosDaJanela | None:
    geridos = manifesto.aparelhos_acoes
    if geridos is None:
        return None
    return exp.AparelhosDaJanela(tuple(_acao_da_janela(a) for a in geridos.acoes),
                                 geridos.grupo or "")


def _pecas_da_janela(manifesto: Any, mod_id: str) -> dict[str, Any]:
    """O que a janela desenha das peças que agem: as ações, os aparelhos, o «Em curso» e o livre."""
    return {"acoes": tuple(_acao_da_janela(a) for a in manifesto.acoes),  # (noqa-acento)
            "aparelhos": _aparelhos_da_janela(manifesto),
            "em_curso": _VIVA.esperando(mod_id, _AGORA.agora()),
            "livre": _VIVA.ao_vivo(mod_id), "controles": _aba_dos_controles(manifesto),
            "armada": _armada_de(mod_id)}


def _armada_de(mod_id: str) -> tuple[str, ...]:
    """A ação desta extensão que espera o segundo clique, como (ação, alvo), ou vazio."""
    return _MEXIDA.armada[1:] if _MEXIDA.armada[:1] == (mod_id,) else ()


def _pede_o_segundo_clique(mod_id: str, acao: str, alvo: str) -> bool:
    """A ação com o glifo que desfaz (``exp.ICONE_QUE_CONFIRMA``): a do aparelho, com ``alvo``, ou
    a da janela, sem ele."""
    item = _a_instalada_ou_nada(mod_id)
    manifesto = item.manifesto if item else None
    if manifesto is None:
        return False
    geridos = manifesto.aparelhos_acoes
    lista = (geridos.acoes if geridos else ()) if alvo else manifesto.acoes
    return any(a.id == acao and a.icone == exp.ICONE_QUE_CONFIRMA for a in lista)


def _com_os_aparelhos(carga: dict[str, Any]) -> dict[str, Any]:
    """A cada tique, os blocos vivos da janela aberta: os aparelhos, as ações em curso, o rastro
    do livre e quem o recebe. A barra que se arrasta nunca está num bloco repintado."""
    if not (_MEXIDA.html_mod and _MEXIDA.mod):
        return carga
    item = next((i for i in REGISTRO.ler() if i.entrada.id == _MEXIDA.mod), None)
    manifesto = item.manifesto if item else None
    if item is None or manifesto is None:
        return carga
    mod_id, estado, blocos = _MEXIDA.mod, _AGORA.agora(), carga["blocos"]
    aparelhos = _aparelhos_da_janela(manifesto)
    em_curso = _VIVA.esperando(mod_id, estado)
    armada = _armada_de(mod_id)
    aba_cc = _aba_dos_controles(manifesto)
    gestao = (exp.Gestao(mod_id, aparelhos, estado, em_curso, armada, _MEXIDA.desligada,
                         bool(aba_cc) and aba_cc == aparelhos.grupo)
              if aparelhos else None)
    if gestao and gestao.aparelhos.grupo:
        blocos["#mod-aparelhos"] = exp.aparelhos_geridos_html(gestao)
    elif gestao and _MEXIDA.agora:
        blocos["#mod-agora"] = exp.agora_html(
            _MEXIDA.agora, estado, processo=exp.processo_de(item.entrada.ligada, item.estado),
            porque=item.porque, gestao=gestao)
    if aba_cc and not (gestao and gestao.controles):
        blocos["#mod-controles"] = exp.controles_dos_aparelhos_html(mod_id, estado, em_curso)
    acoes = tuple(_acao_da_janela(a) for a in manifesto.acoes)
    if acoes or (aparelhos and aparelhos.grupo) or aba_cc:
        grupos = [exp.OpcaoDaJanela(mod_id, o.id, o.rotulo, o.tipo, "", grupo=o.grupo or "")
                  for o in manifesto.opcoes if o.tipo != "livre" and o.id != manifesto.chave]
        for n, delas in exp.acoes_por_aba(grupos, acoes, aparelhos, aba_cc).items():
            blocos[f"#mod-acoes-{n}"] = exp.barra_de_acoes_html(
                mod_id, delas, em_curso, _armada_de(mod_id), _MEXIDA.desligada)
    if manifesto.opcao_livre is not None:
        blocos["#mod-livre-rastro"] = exp.rastro_html(_VIVA.ao_vivo(mod_id))
        blocos["#mod-livre-alvos"] = exp.alvos_do_livre_html(gestao)
        carga.setdefault("mesa", {})[exp.CAMPO_DA_BARRA_FORA] = exp.dica_da_barra_fora(
            manifesto.nome, exp.processo_de(item.entrada.ligada, item.estado), gestao)
    return carga


def _partes_do_clique(o: dict[str, Any], gesto_: str, quantas: int) -> list[str]:
    partes = _id_do_clique(o, gesto_).split(":", quantas - 1)
    return partes + [""] * (quantas - len(partes))


@gesto("07-lancadores.html", exp.GESTO_DA_ACAO)
def acao_da_modificacao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """Um botão de ação da janela, ou a chave e os botões de um aparelho gerido: o serviço leva o
    clique só a esta extensão (``data-v`` é ``mod:ação[:alvo]``). O botão diz «Em curso» até a
    extensão devolver o estado novo. A ação que desfaz pede o segundo clique: o primeiro só a arma
    («Confirmar») e não manda nada; qualquer outro gesto da janela a desarma."""
    mod_id, acao, alvo = _partes_do_clique(o, exp.GESTO_DA_ACAO, 3)
    if not acao:
        raise RuntimeError("O clique não disse qual ação. Nada foi enviado.")
    armar = (mod_id, acao, alvo)
    if _MEXIDA.armada != armar and _pede_o_segundo_clique(mod_id, acao, alvo):
        _MEXIDA.armada = armar
        return _a_pintura_agora(ctx)
    _MEXIDA.armada = ()
    params: dict[str, Any] = {"mod": mod_id, "acao": acao}  # (noqa-acento)
    if alvo:
        params["alvo"] = alvo
    if alvo and acao == exp.ACAO_DE_LIGAR:
        params["valor"] = str(o.get("ligado") or "") == "1"
    antes = _AGORA.ler(mod_id, p) if _MEXIDA.mod == mod_id else None
    if alvo and o.get("quer") is not None:
        params["valor"] = _valor_do_controle(antes, alvo, acao, str(o.get("quer")))
    ok, motivo, corpo = p.chamar_com_o_corpo(METODO_DA_ACAO, **params)
    if not ok:
        raise RuntimeError(motivo or "O serviço não respondeu. Nada foi enviado.")
    if not (isinstance(corpo, dict) and corpo.get("enviada") is True):
        raise RuntimeError(_nao_esta_rodando(mod_id))
    serie = antes.get("serie") if isinstance(antes, dict) else None
    _VIVA.marcar(mod_id, acao, alvo, serie if isinstance(serie, int) else 0)
    _AGORA.esquecer()
    return _a_pintura_agora(ctx)


def _valor_do_controle(estado: dict[str, Any] | None, alvo: str, controle_id: str,
                       quer: str) -> bool | str:
    """O valor que o clique num controle do aparelho pede, no tipo do controle do estado de agora:
    a chave, verdadeiro ou falso (``quer`` é ``1`` ou ``0``); a paleta e a escolha, o ``id``."""
    aparelho = next((a for a in exp.com_controles(estado) if a.get("id") == alvo), None)
    controle = next((c for c in (aparelho or {}).get("controles") or []
                     if c.get("id") == controle_id), None)
    if controle is None:
        raise RuntimeError("Este controle não está mais no aparelho. Nada foi enviado.")
    return quer == "1" if controle.get("tipo") == "chave" else quer


def _nao_esta_rodando(mod_id: str) -> str:
    return f"{_a_instalada(mod_id).entrada.nome} não está rodando: nada foi enviado."


def _a_recusa_do_soltar(resposta: tuple[bool, str | None, Any] | None) -> str | None:
    """Por que o soltar não chegou à extensão (a frase do serviço, ou vazio quando ela está fora
    da porta); ``None`` quando chegou, ou quando nada foi mandado."""
    if resposta is None:
        return None
    ok, motivo, corpo = resposta
    if not ok:
        return motivo or "O serviço não respondeu. Nada foi enviado."
    return None if isinstance(corpo, dict) and corpo.get("enviado") is True else ""


def _o_modo_na_extensao(mod_id: str, opcao_id: str, modo: str, p: Any) -> str | None:
    """O ``modo`` do livre na barra e na extensão. Fora da porta, ela volta lendo o guardado: a
    barra segue o modo sem acusar recusa. Devolve a frase da recusa de verdade, ou ``None``."""
    porque = _a_recusa_do_soltar(_VIVA.mudar_o_modo(mod_id, opcao_id, modo, p))
    if porque == "":
        _VIVA.sem_a_extensao(mod_id, modo)
        return None
    return porque


def _desfazer_o_modo(mod_id: str, p: Any) -> str | None:
    """O Cancelar (e o reabrir) devolve à extensão o modo guardado do ``livre``, pelo mesmo
    caminho que aplica: o soltar com ele, só quando o modo vivo difere. Devolve a frase da recusa,
    ou ``None`` quando nada havia a desfazer, a extensão recebeu ou ela está fora da porta."""
    from hefesto_dualsense4unix.mods import opcoes

    item = _a_instalada_ou_nada(mod_id)
    manifesto = item.manifesto if item else None
    livre = manifesto.opcao_livre if manifesto else None
    chave = opcoes.chave_do_modo(manifesto) if manifesto else None
    if manifesto is None or livre is None or chave is None:
        return None
    guardado = str(opcoes.ler(manifesto, _lugares())[chave])
    return _o_modo_na_extensao(mod_id, livre.id, guardado, p)


def _o_modo_que_vale(mod_id: str) -> dict[str, Any]:
    """O rascunho que diz o modo que ainda vale na extensão, depois de um desfazer recusado."""
    from hefesto_dualsense4unix.mods import opcoes

    chave = opcoes.chave_do_modo(_a_instalada(mod_id).manifesto)
    vivo = _VIVA.modo_de(mod_id)
    return {chave: vivo} if chave and vivo else {}


@gesto("07-lancadores.html", exp.GESTO_DA_ABA)
def aba_da_modificacao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """A aba trocada na janela da extensão: ela fica a aberta ao redesenhar, e a ação armada
    desarma. Age no ``change`` do rádio; o clique que o precede não pinta nada."""
    mod_id, aba = _partes_do_clique(o, exp.GESTO_DA_ABA, 2)
    if str(o.get("evento") or "") != "change" or _MEXIDA.mod != mod_id:
        return None
    _MEXIDA.aba = aba
    if not _MEXIDA.armada:
        return None
    _MEXIDA.armada = ()
    return _a_pintura_agora(ctx)


@gesto("07-lancadores.html", exp.GESTO_DO_CANCELAR)
def cancelar_modificacao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O Cancelar e o X da janela da extensão (o Esc clica o X). Com rascunho por gravar, o primeiro
    gesto só arma o «Descartar» e a janela fica; o segundo (ou o primeiro, sem rascunho) devolve ao
    guardado o modo do ``livre`` que já valeu e o rascunho sai. Recusado o desfazer, nada muda (o
    rascunho diz o modo que ainda vale) e a recusa aparece; o reabrir tenta de novo."""
    _MEXIDA.armada = ()
    mod_id = _id_do_clique(o, exp.GESTO_DO_CANCELAR)
    if _MEXIDA.mod == mod_id and _MEXIDA.descartar != _o_armar_do_descartar(mod_id):
        item = _a_instalada(mod_id)
        if item.manifesto and _o_rascunho_da_janela(mod_id, _guardados_de(item)).pendente:
            _MEXIDA.descartar = _o_armar_do_descartar(mod_id)
            _montar_a_janela_da_extensao(mod_id, item)
            return {**_a_pintura_agora(ctx), "armou": True}
    _MEXIDA.descartar = ()
    recusa = _desfazer_o_modo(mod_id, p)
    if recusa is not None:
        raise RuntimeError(recusa)
    if _MEXIDA.mod == mod_id:
        _MEXIDA.rascunho = {}
        _montar_a_janela_da_extensao(mod_id)
    return _a_pintura_agora(ctx)


def _guardados_de(item: _Instalada) -> dict[str, Any]:
    from hefesto_dualsense4unix.mods import opcoes

    return opcoes.ler(item.manifesto, _lugares())


def _do_trilho(o: dict[str, Any], gesto_: str) -> tuple[str, str, float]:
    mod_id, opcao_id = _partes_do_clique(o, gesto_, 2)
    try:
        valor = float(str(o.get("valor") or "0")) / 100
    except ValueError as erro:
        raise RuntimeError("A barra não disse a força. Nada foi enviado.") from erro
    return mod_id, opcao_id, max(0.0, min(1.0, valor))


def _numero(texto: Any) -> float:
    try:
        return float(str(texto or "0"))
    except ValueError:
        return 0.0


def _sem_alvo(mod_id: str) -> bool:
    """A extensão que gere aparelhos e não tem nenhum ativo agora: a barra não tem para onde ir,
    pela mesma regra que a apaga (``exp.sem_alvo``)."""
    item = _a_instalada_ou_nada(mod_id)
    aparelhos = _aparelhos_da_janela(item.manifesto) if item and item.manifesto else None
    if not aparelhos:
        return False
    return exp.sem_alvo(exp.Gestao(mod_id, aparelhos, _AGORA.agora(), frozenset()))


@gesto("07-lancadores.html", exp.GESTO_DO_LIVRE)
def mover_o_livre_da_modificacao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O arrastar do controle livre, um gesto VIVO (a cada ``input``): manda e não grava nada.

    O serviço segura em 20 por segundo; o que chega fora de ordem cai aqui. Não pinta: o rastro
    é do tique, e a barra é a que o dedo está arrastando.
    """
    _MEXIDA.armada = ()
    mod_id, opcao_id, valor = _do_trilho(o, exp.GESTO_DO_LIVRE)
    if _sem_alvo(mod_id):
        return {}
    _VIVA.enviar(mod_id, opcao_id, valor, vivo=int(_numero(o.get("vivo"))),
                 carimbo=_numero(o.get("carimbo")), soltou=False, ponte=p)
    return {}


@gesto("07-lancadores.html", exp.GESTO_DE_SOLTAR)
def soltar_o_livre_da_modificacao(ctx: Contexto, o: dict[str, Any],
                                  p: Any) -> dict[str, Any] | None:
    """O soltar da barra (o ``change``): sai sempre, com o valor final, fora do compasso."""
    _MEXIDA.armada = ()
    if str(o.get("evento") or "") != "change":
        return None
    mod_id, opcao_id, valor = _do_trilho(o, exp.GESTO_DE_SOLTAR)
    if _sem_alvo(mod_id):
        raise RuntimeError(f"{exp.DICA_DA_BARRA_SEM_ALVO} Nada foi enviado.")
    resposta = _VIVA.enviar(mod_id, opcao_id, valor, vivo=0, carimbo=_numero(o.get("carimbo")),
                            soltou=True, ponte=p)
    ok, motivo, corpo = resposta or (True, None, {"enviado": True})
    if not ok:
        raise RuntimeError(motivo or "O serviço não respondeu. Nada foi enviado.")
    if not (isinstance(corpo, dict) and corpo.get("enviado") is True):
        raise RuntimeError(_nao_esta_rodando(mod_id))
    return _a_pintura_agora(ctx)


def _o_livre_de(item: _Instalada, opcao_id: str) -> Any:
    livre = item.manifesto.opcao_livre if item.manifesto else None
    if livre is None or livre.id != opcao_id:
        raise RuntimeError("Esta extensão não tem esse controle livre. Nada foi guardado.")
    return livre


def _ao_rascunho(mod_id: str, opcao: Any, valor: Any, item: _Instalada) -> None:
    """Uma opção validada vai ao rascunho da janela, como no ``guardar-opcao-da-modificacao``."""
    from hefesto_dualsense4unix.mods import opcoes

    with _dizendo_a_recusa():
        certo = opcoes.validar(opcao, valor, formas_extras=_formas_da_janela(item))
    if _MEXIDA.mod != mod_id:
        _MEXIDA.mod, _MEXIDA.rascunho = mod_id, {}
    _MEXIDA.rascunho[opcao.id] = certo


@gesto("07-lancadores.html", exp.GESTO_DE_GRAVAR, grava="_guardar_a_opcao_da_modificacao")
def gravar_o_livre_da_modificacao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Gravar» começa; o segundo clique, com ele aceso, faz do que se arrastou uma forma nova
    («Meu N»), gravada na hora, que entra na escolha dos botões desta extensão."""
    _MEXIDA.armada = ()
    from hefesto_dualsense4unix.mods.manifesto import FORMAS_POR_OPCAO

    mod_id, opcao_id = _partes_do_clique(o, exp.GESTO_DE_GRAVAR, 2)
    item = _a_instalada(mod_id)
    livre = _o_livre_de(item, opcao_id)
    formas = _formas_do_livre_na_janela(item)
    gravando = _VIVA.ao_vivo(mod_id).gravando
    if not gravando and _sem_alvo(mod_id):
        raise RuntimeError(f"{exp.DICA_DA_BARRA_SEM_ALVO} Nada foi gravado.")
    if len(formas) >= FORMAS_POR_OPCAO and not gravando:
        raise RuntimeError(
            f"Já há {FORMAS_POR_OPCAO} formas gravadas: esqueça uma antes de gravar.")
    amostras = _VIVA.gravar(mod_id)
    recado = ""
    if amostras is not None:
        passos = passos_da_gravacao(amostras)
        if not passos:
            recado = "Nada foi arrastado enquanto gravava: nenhuma forma nova."
        else:
            nome = _nome_da_forma_nova(formas)
            _ao_rascunho(mod_id, livre, {**formas, nome: passos}, item)
            _guardar_a_opcao_da_modificacao(mod_id)
            recado = f"«{nome}» gravada: já está na escolha dos botões."
    _montar_a_janela_da_extensao(mod_id)
    carga = _a_pintura_agora(ctx)
    return {**carga, "recado": recado} if recado else carga


@gesto("07-lancadores.html", exp.GESTO_DE_ESQUECER_A_FORMA,
       grava="_guardar_a_opcao_da_modificacao")
def esquecer_a_forma_do_livre(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O «x» de uma forma gravada: sai na hora do ``opcoes.json``, e o botão que a usava volta
    ao padrão."""
    _MEXIDA.armada = ()
    from hefesto_dualsense4unix.mods import opcoes

    mod_id, opcao_id, nome = _partes_do_clique(o, exp.GESTO_DE_ESQUECER_A_FORMA, 3)
    item = _a_instalada(mod_id)
    livre = _o_livre_de(item, opcao_id)
    formas = _formas_do_livre_na_janela(item)
    if nome not in formas:
        raise RuntimeError("Essa forma não está gravada. Nada foi esquecido.")
    _ao_rascunho(mod_id, livre, {f: s for f, s in formas.items() if f != nome}, item)
    for opcao in (item.manifesto.opcoes if item.manifesto else ()):
        if opcao.tipo != "por_botao":
            continue
        atual = _valor_na_janela(item, opcao)
        if isinstance(atual, dict) and nome in atual.values():
            sem = {b: f for b, f in atual.items() if f != nome}
            with _dizendo_a_recusa():
                _MEXIDA.rascunho[opcao.id] = opcoes.validar(
                    opcao, sem, formas_extras=_formas_da_janela(item))
    _guardar_a_opcao_da_modificacao(mod_id)
    _montar_a_janela_da_extensao(mod_id)
    return {**_a_pintura_agora(ctx), "recado": f"«{nome}» esquecida."}


@gesto("07-lancadores.html", exp.GESTO_DO_MODO, grava="_guardar_a_opcao_da_modificacao")
def modo_do_livre_da_modificacao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Soltar», «Segurar» ou «Repetir» (o ``livre`` com ``modos``): o modo grava na hora, como
    as outras escolhas, e vale na barra e na extensão. ``data-v`` é ``mod:id:modo``."""
    _MEXIDA.armada = ()
    from hefesto_dualsense4unix.mods import opcoes

    mod_id, opcao_id, modo = _partes_do_clique(o, exp.GESTO_DO_MODO, 3)
    item = _a_instalada(mod_id)
    livre = _o_livre_de(item, opcao_id)
    chave = opcoes.chave_do_modo(item.manifesto)
    if chave is None:
        raise RuntimeError("Este controle livre não tem modos. Nada foi guardado.")
    with _dizendo_a_recusa():
        certo = opcoes.modo_valido(modo)
    if _MEXIDA.mod != mod_id:
        _MEXIDA.mod, _MEXIDA.rascunho = mod_id, {}
    antes = dict(_MEXIDA.rascunho)
    _MEXIDA.rascunho[chave] = certo
    recusa = _o_modo_na_extensao(mod_id, livre.id, certo, p)
    if recusa is not None:
        _MEXIDA.rascunho = antes
        _montar_a_janela_da_extensao(mod_id)
        raise RuntimeError(recusa)
    _guardar_a_opcao_da_modificacao(mod_id)
    _montar_a_janela_da_extensao(mod_id)
    return _a_pintura_agora(ctx)


METODOS |= {METODO_DA_ACAO, METODO_DO_LIVRE}
SEM_ECO = (*SEM_ECO, exp.GESTO_DA_ACAO, exp.GESTO_DO_LIVRE, exp.GESTO_DE_SOLTAR,
           exp.GESTO_DE_GRAVAR, exp.GESTO_DE_ESQUECER_A_FORMA, exp.GESTO_DO_MODO,
           exp.GESTO_DO_CANCELAR)
