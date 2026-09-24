#!/usr/bin/env python3
"""O pacote da aba `07` Lançadores — a aba que era desenho inteiro.

A DECISÃO DELA QUE ABRIU ESTA ABA, e ela CADUCOU outra, de um dia antes:

    01/09/2026 — *"a única que não faremos, só deixamos o botão levando pra
    ela, é a de lançadores."*

    02/09/2026 — *"não daria para incluir G e F aqui? (…) temos um mapa
    funcional disso no gtk. a estrutura sim, validar de fato eu poderia
    somente juntos com ele."*   <!-- noqa-acento: citação literal dela -->

A `F` é esta aba (`docs/process/sprints/arquivados/2026-09-02-ROTA-F-a-aba-lancadores.md`).
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
cinco diziam `NÃO ACHEI`. **Na máquina dela nada muda** — a Steam está lá, e a
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

O REPARO SAIU DESTA ABA — 21/09/2026, palavra dela: *"a ideia é termos os
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
`with_steam_closed`, sem o qual o `Consertar` recusa sempre na mesa dela.

`carona_do_wrapper.passada()` responderia parte disto — mas ela ESCREVE no
`localconfig.vdf` quando há o que repor, e uma PINTURA que escreve em disco a
cada tique é a coisa mais perigosa que esta aba poderia fazer. A pintura usa o
CENSO (read-only, seguro com a Steam aberta — e é por isso que ele é uma camada
separada do reparo); quem chama o caminho que escreve é o gesto "Consertar" e,
desde 03/09/2026, a :class:`_VigiaDaSteam` que esse gesto arma quando é adiado
— nunca a pintura, e nunca sem um clique dela antes.

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
Medido em 02/09/2026, na máquina dela:

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

#: O DIAGNÓSTICO QUE SAIU DA TELA — 11/09/2026, A2-041/042/043.
#:
#: As três recusas de `data-v` ausente contavam, NA TELA DELA, a marcação da
#: página: o nome do gesto, o `data-v`, o `appid`, a chave do cartão. Isso é o
#: que quem CONSERTA precisa ler; quem clicou precisa saber que nada mudou.
#: **São dois textos, e eram um só** — a recusa chega a ela pelo caminho do
#: `RuntimeError`/`ValueError` (`hefesto_vivo`), não a um terminal.
#:
#: O diagnóstico não se perdeu: ele vem para cá, no mesmo commit em que saiu do
#: cartão.
_LOG = logging.getLogger(__name__)

#: De quanto em quanto tempo a vigia repergunta ao disco. 20 s é o compromisso:
#: a linha de inicialização só muda quando a Steam a regrava (ao sair) ou quando
#: ela clica em Consertar — e o gesto invalida o cache na hora, então o TTL não
#: precisa ser curto para a tela parecer viva.
#:
#: **ESTES 20 s NÃO ENTRAM NA PODA POR HOTPLUG, E FOI MEDIDO** —
#: CACHE-SEM-PODA-01, 20/09/2026. A sprint listou este cache entre os seis que
#: *"não escutam a saída de um controle"*; a medição diz que ele não tem o que
#: escutar. Com a vigia CONGELADA de propósito e a mesma `Leitura` servindo as
#: duas pinturas, o canário do controle (nome e `uniq`) não aparece em nenhuma:
#:
#:     mesa cheia   o pacote nomeia o controle? não · traz o `uniq`? não
#:     mesa vazia   sobrou o nome? não · sobrou o `uniq`? não
#:     o que muda entre as duas pinturas: só `blocos[".fita"]`
#:
#: E a fita é o contrário de um cache: :func:`pacote` a monta de `ctx.mesa` a
#: cada tique. O que este arquivo guarda são fatos do JOGO EM DISCO — é o que o
#: docstring de :func:`pacote` já dizia com todas as letras. **Uma poda aqui
#: releria 38 ms de disco por hotplug para chegar à mesma `Leitura`.**
#:
#: Quem tranca a afirmação é `test_a_biblioteca_dos_lancadores_nao_guarda_controle`
#: — se um dia a `Leitura` ganhar um campo por `uniq`, o canário reaparece na
#: segunda pintura e a régua reprova nomeando.
TTL_S = 20.0

#: O TEMPO DO CONSENTIMENTO SAIU DAQUI em 21/09/2026: a aba 07 não fecha mais
#: a Steam por clique nenhum (os botões do estado saíram — ver
#: :func:`com_o_que_o_daemon_diz`), e quem ainda confirma em dois cliques lê o
#: dono dele, `pacotes/confirmacao.SEGUNDOS_PARA_CONFIRMAR`.

#: O `abrir-lancador` SAIU DAQUI em 03/09/2026 — decisão 17 dela, e o motivo
#: escrito nesta linha era a pergunta errada: *"o daemon não tem método para
#: isso"* é verdade pelo IPC e o produto sabia abrir a Steam por outro caminho
#: desde 23/08 (`steam_launch_options.reopen_steam`). O botão tem dono agora;
#: quem conta o que ele sabe e o que não sabe é :func:`abrir_lancador`.
#: O `heroic` SAIU DAQUI EM 09/09/2026 — LANCADORES-ZERO-01, e o motivo escrito
#: nesta linha virou FATO ERRADO no dia em que o censo nasceu. Ele dizia *"não
#: LÊ a biblioteca de nenhum deles — nenhuma função de `src/` abre o catálogo do
#: Heroic, do Lutris, do RetroArch, do Dolphin ou do mGBA, e por isso o cartão
#: do que foi achado continua dizendo NÃO SEI"*. As três afirmações caíram na
#: mesma leva: `integrations/censo_dos_lancadores` abre os cinco catálogos, o
#: selo do achado é `LOCALIZADO`, e a linha de baixo diz a contagem. Guardar a
#: frase velha ao lado da certa obrigaria a próxima pessoa a escolher entre
#: duas afirmações — que é o defeito que a regra desta casa existe para matar.
SEM_DONO: dict[str, str] = {
    "criar-perfil": "criar perfil é da aba Perfis (`a10_perfis`); dois caminhos "
                    "para o mesmo disco é como duas telas passam a discordar",
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


def _declarados() -> tuple[desenho.SemCenso, ...]:
    """O que ELA declarou no `maquina.json`, no molde do procurador.

    ELA ESCOLHEU ONDE PROCURAR, e o produto não tem como adivinhar isso: um
    Ryujinx em `/opt`, um AppImage no `~/Jogos`, um emulador que ninguém
    empacotou. É a definição do que mora naquele arquivo — o que o Hefesto
    **não tem como medir**.

    A TRADUÇÃO É DE UM CAMPO PARA O MESMO CAMPO, e é o que prova que não há
    segundo caminho: `rotulo` → `nome`, `atalhos` → `atalhos`, `comandos` →
    `comandos`. Se um dia divergirem, o `SemCenso` ganha o campo e o
    `LancadorDeclarado` também — nunca um conversor com regra própria.

    **NUNCA LEVANTA**, e a razão é a mesma de `carregar_maquina`: esta função é
    chamada pela vigia da aba, e um `maquina.json` estranho não pode derrubar a
    tela inteira. Sem declaração, a aba é a de fábrica — que é o pior caso
    honesto.

    NÃO SE GUARDA EM MEMÓRIA, e a escolha é medida contra o alvo: a leitura
    inteira já roda fora do tique, na :class:`_Vigia`, e `carregar_maquina` abre
    UM json de poucos bytes. Guardar num global obrigaria o gesto de registrar a
    lembrar-se de invalidá-lo — e um cartão que só aparece na próxima abertura
    do Hefesto é a forma mais cara do defeito-mãe desta casa.
    """
    # O `perfil` VEM DO TOPO DO MÓDULO, e isso é CURA MEDIDA — 08/09/2026.
    #
    # A primeira versão desta função chamava `perfil._com_o_src()` com o
    # `perfil` **nunca importado neste arquivo**. O `NameError` caía no
    # `except Exception` de baixo, a função devolvia `()`, e o registro inteiro
    # ficava morto sem uma linha de erro: ela clicaria em «Adicionar», o gesto
    # gravaria no `maquina.json` de verdade, e o cartão não apareceria NUNCA.
    # Quem revelou foi o CLIQUE de ponta a ponta — nenhuma régua de existência
    # veria, porque o motor estava todo lá.
    #
    # E O `except` FICOU ESTREITO POR CAUSA DISSO: ele cobre a LEITURA do disco,
    # que é o que pode falhar na máquina dela. Um nome que não existe é defeito
    # de código, e defeito de código tem de rebentar no import — onde toda régua
    # desta casa o vê.
    perfil._com_o_src()
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina

    try:
        declaracao = carregar_maquina()
    except Exception:  # pragma: no cover - o disco dela não derruba a aba
        return ()
    return tuple(
        desenho.SemCenso(chave=chave, nome=item.rotulo,
                         atalhos=tuple(item.atalhos),
                         comandos=tuple(item.comandos),
                         declarado=True)
        for chave, item in sorted(declaracao.lancadores.items())
    ) + _achados_por_conteudo()


def _achados_por_conteudo() -> tuple[desenho.SemCenso, ...]:
    """Os lançadores que a máquina DECLARA ser, e que ninguém digitou.

    **LANCADOR-ACHADO-01 §3, degrau 2 — 09/09/2026.** A busca do produto era
    por CINCO STRINGS que alguém escreveu no arquivo, e tudo que não batia
    sumia com um `NÃO LOCALIZADO` sobre um programa instalado e funcionando: o
    `net.lutris.Lutris-beta`, o AppImage que publica `.desktop`, o snap, o
    compilado em `/opt`, e todo lançador fora dos seis (itch, Bottles, ES-DE)
    — *e são dezenas de emuladores*.

    A palavra dela foi *"isso é uma falha de produto e a culpa é minha"*. **A
    culpa não é dela:** um produto que exige a forma certa de instalar
    terceiriza uma pergunta que ele mesmo deveria responder.

    A PERGUNTA VIROU SOBRE O MUNDO: `jogos_locais.e_lancador_de_jogos` lê o
    que o `.desktop` DIZ DE SI — `Categories=Game` mais `PackageManager` ou
    `Emulator`. É a mesma pergunta que o cartão do Flatpak já fazia ao
    procurar o COMANDO, e a assimetria que a §2 da sprint nomeia.

    **ELE ENTRA PELA PORTA QUE JÁ EXISTE**, e é o ponto: `desenho.procurados`
    soma os de fábrica ao que ela declarou, e **chave repetida ENSINA o
    primeiro cartão em vez de criar um segundo**. Então um achado cujo `stem`
    já é atalho de um cartão de fábrica não vira cartão novo — ele só confirma
    aquele. Um segundo procurador seria a assimetria que esta casa passou
    dias arrancando.

    `declarado=False`: ela não declarou nada, então o cartão **não** ganha o
    botão «Tirar» — não há declaração a esquecer. É a mesma regra que
    `cartao_sem_censo` já aplica.

    NUNCA LEVANTA, pela mesma razão de `_declarados`: a vigia da aba chama
    isto, e uma pasta ilegível não pode derrubar a tela.
    """
    from hefesto_dualsense4unix.integrations import jogos_locais as jl

    try:
        achados = jl.lancadores_por_conteudo()
    except Exception:  # pragma: no cover - o disco dela não derruba a aba
        return ()
    #: OS `stem` QUE OS CARTÕES DE FÁBRICA JÁ PROCURAM. Um achado que caia
    #: aqui não é notícia: o cartão dele existe e a busca de sempre o alcança.
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
    não está nela porque o produto LÊ a biblioteca dela. Só que ter censo do
    interior não responde se o lançador está aqui, e o cartão da Steam nascia
    com `presente=True` cravado. Numa casa de mentira sem Steam nenhuma o topo
    dizia **"1 encontrado"** e o cartão acendia o selo verde `CHEGAM`. Agora a
    lista percorrida é :func:`desenho.procurados`, que devolve os de fábrica
    **mais** o que ela declarou.

    UM PROCURADOR SÓ, E É ESTE — 08/09/2026. O lançador que ela acrescenta pelo
    botão de registro não ganha busca própria: ele entra na MESMA lista,
    com os MESMOS três campos, e é achado pelas MESMAS duas buscas. Um segundo
    caminho seria a assimetria que produz duas respostas para a mesma pergunta —
    e a segunda envelhece calada, porque só a máquina dela a exercita.

    AS PASTAS SÃO AS DO MOTOR, e não uma lista minha:
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
    """Os jogos que ELA mandou não perguntar mais — e que tela nenhuma mostrava.

    `launch_wrapper_dialog.load_dismissed_appids` guarda o "Não perguntar para
    este jogo" do lembrete, no `launch_dialog_dismissed.json`. A escrita tinha
    dono (o botão do diálogo da GTK) e a LEITURA não tinha nenhuma tela: o
    efeito de clicar era um silêncio permanente que ninguém podia consultar
    depois. Este é o primeiro chamador que devolve isso para os olhos dela.

    O RÓTULO VEM DO MESMO LUGAR DOS OUTROS (`slo.rotulo_do_jogo`), e ele já cai
    para `appid NNNN` quando o manifesto sumiu — um jogo dispensado e depois
    desinstalado continua na lista, e mostrar o número cru é melhor que sumir
    com a linha.
    """
    from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as lwd
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    try:
        appids = sorted(lwd.load_dismissed_appids())
    except Exception:
        return ()
    return tuple((a, slo.rotulo_do_jogo(a)) for a in appids)


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

    # UMA LEITURA DO `maquina.json` POR PASSADA, e ela serve às DUAS pontas: a
    # busca em disco e a lista de cartões. Ler duas vezes daria a chance de as
    # duas discordarem — um cartão desenhado para um lançador que a busca não
    # percorreu nasceria eternamente «NÃO LOCALIZADO».
    declarados = _declarados()
    onde_estao = _onde_estao_os_lancadores(declarados)
    # OS OUTROS CINCO CARTÕES SÃO LIDOS AQUI, e é o lugar certo — 09/09/2026.
    # A biblioteca de cada lançador, a linha do «Flatpak» e a pergunta da
    # estrada nasceram dentro da PINTURA, e custavam 6,4 ms de mediana por
    # tique na máquina dela (30 voltas, máximo 18,6 ms) — dez vezes por
    # segundo, num orçamento de 100 ms para a janela inteira. É a mesma razão
    # que pôs o resto do disco nesta vigia, e o próprio arquivo já a escrevia:
    # *"a pintura NUNCA bloqueia"*. Ver `desenho.DoDisco`.
    #
    # ELE FICA FORA DO `try` DO CENSO pela razão de sempre: a Steam quebrada
    # não pode apagar a resposta sobre o Heroic. `medir_no_disco` nunca levanta
    # — cada leitor de dentro dele já responde "não sei" em vez de explodir.
    #
    # O CONTADOR DE CADA CARTÃO (21/09/2026) conta os jogos da biblioteca cuja
    # janela já tem ponte confirmada num perfil — o mesmo número que só a Steam
    # mostrava. Ver `desenho_dos_lancadores.contador_html`.
    try:
        com_ponte = frozenset(pdj.classes_com_ponte())
    except Exception:
        com_ponte = frozenset()
    do_disco = desenho.medir_no_disco(onde_estao, declarados, com_ponte=com_ponte)

    try:
        censo = sw.censo_do_wrapper(anotar=False)
    except Exception as erro:  # o disco dela não pode derrubar a aba
        return desenho.Leitura(erros=(str(erro),), onde_estao=onde_estao,
                               declarados=declarados, do_disco=do_disco)

    try:
        instalados = len(pdj.jogos_instalados())
    except Exception:
        instalados = 0

    # A PONTE CONFIRMADA é o carimbo que o desenho prometia com o número
    # DIGITADO (`◆ 3 jogos já sabem por onde entrar`). `pontes_confirmadas` lê
    # os perfis do disco e responde a mesma pergunta — e não tinha chamador.
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
        # A FRASE DA SENTINELA SAIU DA `Leitura` — TELA-CALADA-02, 13/09/2026.
        # Ela ia inteira para o corpo do cartão a cada tique, sem clique, e a
        # palavra dela é *"em todas as abas da interface"*. O corpo diz a
        # contagem (`desenho_dos_lancadores.cartao_da_steam`); a frase continua
        # sendo a RECUSA do «Consertar», que a pede ao dono na hora do gesto.
        # A LINHA É A CONSTANTE DO MOTOR, e não uma segunda redação: é a MESMA
        # que o botão "Copiar opções para os jogos" da janela velha copia
        # (`daemon_actions.compose_launch` devolve `WRAPPER_LAUNCH` e nada mais)
        # e a MESMA que o `apply_wrapper_to_all_games` grava no vdf. Digitá-la
        # aqui seria a terceira cópia de 143 caracteres que já têm dono — e a
        # cópia envelheceria calada no dia em que o wrapper mudasse de caminho.
        linha=slo.WRAPPER_LAUNCH,
        erros=tuple(censo.erros),
        do_disco=do_disco,
    )


def _valores(lida: desenho.Leitura | None) -> dict[str, str]:
    """Os endereços da aba inteira, montados pelo desenho."""
    return desenho.Quadro(lancadores=desenho.cartoes(lida)).valores()


# ---------------------------------------------------------------------------
# O QUE O DAEMON JÁ DIZ, E A INTERFACE NOVA JOGAVA FORA
#
# A LEI 0, e ela é dela: *"no gtk eu já deixei praticamente tudo pronto…
# não temos que recriar nada. só aproveitar o que foi feito e integrar ao novo
# desenho."*
#
# O QUE FALTAVA, medido em 03/09/2026: o daemon publica
# `gamepad_emulation.wrapper_used` a cada tique — *"há jogo aberto AGORA e ele
# não passou pelo wrapper"* — e a GTK acende um banner com isso em DUAS abas,
# sem clique nenhum (`home_actions.wrapper_banner_text`, consumido pela Início
# e pela Status). Em `interface/` a chave não tinha um leitor: `grep -rn
# wrapper_used` só achava o dublê de perfis. A mesma pergunta, no HTML, exigia
# que ela suspeitasse do problema, saísse do jogo, abrisse esta aba e clicasse
# em Detectar.
#
# NADA DISTO É REGRA NOVA. A decisão é a função pura da GTK, a dispensa é a
# lista que a GTK escreve, e o appid sai do mesmo `extract_steam_appid` que o
# lembrete da GTK usa. O que esta aba acrescenta é a TELA.
# ---------------------------------------------------------------------------
def _o_jogo_em_foco(state: dict[str, Any] | None) -> str:
    """O appid do jogo Steam em foco AGORA, ou `""`. **Não toca o disco.**

    `window_detect_last_class` já vem no `state` que a pintura recebe, e quem o
    traduz é `launch_wrapper_dialog.extract_steam_appid` — a MESMA função que
    decide o lembrete da GTK, com a conversão `int`→`str` que ela documenta (um
    `==` entre `int` e `str` seria sempre falso, em silêncio).

    ESTA É A SEGUNDA EVIDÊNCIA da escada de :func:`detectar`, e aqui ela é a
    ÚNICA de propósito: as outras duas leem marker em disco, e a pintura roda
    duas vezes por segundo. Quem paga disco é o gesto, que roda em thread.
    """
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

    **A FRASE MUDOU EM 06/09/2026 (ONDA5-07-03), e a palavra é dela.** Ela
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
    dele toda vez que ele abrisse. **Um aviso que sobrevive à resposta dela
    ensina que o botão não obedece.**

    E AS DUAS SÃO A MESMA FRASE DELA, dita de dois jeitos: *"eu sei, deixa
    assim"*. O desfazer de cada uma já está na lista do cartão — *"Voltar a
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
    nunca teve esse defeito, porque a decisão dela é uma função PURA
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
            # O DAEMON JÁ RESPONDEU o que o dono iria ao disco perguntar: o
            # `wrapper_banner_text` acima só devolve texto no `False` LITERAL de
            # `wrapper_used`, que é *"há jogo aberto E ele não passou pelo
            # atalho"*. `True` aqui é essa resposta, no vocabulário do dono.
            vdf_cache={appid: True},
            dismissed=calados(lida) if lida is not None else set(),
            shown_this_session=set(),
            popup_open=False,
            dialog_open=False,
        )
        if acao != lwd.DECISION_PROMPT:
            return "", ""
    return f"<b>{_texto(JOGO_ABERTO_SEM_O_ATALHO)}</b><br>", appid


#: O RÓTULO DO JOGO ABERTO SEM O ATALHO — TELA-CALADA-02, 13/09/2026.
#:
#: ATÉ AQUI O CARTÃO RECEBIA A FRASE INTEIRA DA JANELA VELHA
#: (`home_actions.WRAPPER_MISSING_TEXT`, 28 palavras, com *"Reponho o atalho no
#: próximo Aplicar…"*), a cada tique e sem clique. A palavra dela sobre as frases
#: de status é *"em todas as abas da interface"*, e a régua da sprint deixa
#: ficar só rótulo de ESTADO: até seis palavras, sem primeira pessoa, sem
#: instrução.
#:
#: POR QUE NÃO SILÊNCIO, e foi medido na foto do piloto: o botão «Não perguntar
#: para este jogo» pende deste aviso. Sem nada escrito, o botão aparece no cartão
#: sem dizer SOBRE O QUÊ não perguntar — um botão que não se explica sozinho. O
#: rótulo diz o estado que o botão dispensa, e nada mais.
#:
#: A DECISÃO CONTINUA SENDO DO DONO: quem diz SE acende é
#: `home_actions.wrapper_banner_text` (e a dispensa, e o modo). Muda só o que se
#: escreve quando acende.
JOGO_ABERTO_SEM_O_ATALHO = "Jogo aberto sem o atalho"


def calados(lida: desenho.Leitura | None) -> set[str]:
    """Os appids sobre os quais ela JÁ RESPONDEU — as duas recusas juntas.

    ELA É PÚBLICA E TEM NOME PRÓPRIO porque a segunda tela precisa dela. A
    coluna Atenção da aba Jogar acende o MESMO aviso, pela MESMA função
    (`app/actions/jogar/painel.AVISOS_DA_TELA`, o `Aviso("JOGO", …)`), e não
    consulta lista nenhuma — a decisão `07[03]` manda calar nas DUAS. Esta
    frente não é dona daquele arquivo; o que ela pode fazer é deixar a conta
    escrita UMA vez, com nome, para a outra metade não a redigitar. **Está
    relatado como trabalho de fora desta aba.**

    NUNCA LEVANTA: quem chama é a pintura, duas vezes por segundo.
    """
    if lida is None:
        return set()
    return ({a for a, _ in lida.dispensados} | {a for a, _ in lida.recusados})


#: **O «Consertar» DOS OUTROS LANÇADORES SAIU — LANCADOR-LOCALIZAR-01,
#: 10/09/2026.** Aqui moravam a `PERGUNTA_DA_CURA` e o `CONFIRMA_A_CURA`, o
#: consentimento de dois tempos que segurava o lugar até ela ver o botão. Ela
#: viu, e o bloco PROVISÓRIO já deixava as duas saídas escritas: esta é a
#: segunda — *"ela decide que o botão NÃO deve existir → tire o ramo do
#: `consertar` em `desenho_dos_lancadores.cartao_sem_censo`"*.
#:
#: **O QUE CAIU FOI O VASO, NÃO A CURA.** `integrations/cura_por_estrada` fica,
#: com as 26 provas e a dívida declarada em
#: `tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py`: `hefesto-launch` só
#: age com jogo da Steam, e nenhum jogo do Heroic, do Lutris, do RetroArch, do
#: Dolphin ou do mGBA tem um — a lacuna continua aberta. O vaso certo é a
#: CARONA (`perfil.com_a_carona`, que o Salvar e o Aplicar já chamam), e quem a
#: constrói é a LANCADOR-CARONA-01.

#: O CONSENTIMENTO DE DOIS TEMPOS SAIU DESTA ABA — 21/09/2026. Ele mudou de
#: casa em 20/09 (`pacotes/confirmacao`, que o chip «Steam Input» da aba Jogar
#: também usa), e aqui ficavam os nomes privados com que esta aba o chamava.
#: Os três botões que fechavam a Steam saíram com a palavra dela — *"os mesmos
#: botões pra todos os lançadores. sempre."* —, e com eles o consentimento.



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

    OS BOTÕES SAÍRAM DAQUI — 21/09/2026, palavra dela: *"a ideia é termos os
    mesmos botões pra todos os lançadores. sempre."* Esta função pendurava no
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


# ---------------------------------------------------------------------------
# A FITA DESTA ABA SAIU DAQUI — 22/09/2026. Ela era `fita_html` + `_chip`, e
# desde 06/09 só escrevia com a mesa vazia, porque o piloto se calava ali. Em
# 21/09 o piloto passou a pintar a fita vazia também, e esta virou o segundo
# dono daquele caso — pintando `Selecionar:` + `Todos` sobre controle nenhum,
# que ela pediu para sumir: *"quando não tiver controle Não Aparece o
# selecionar:"*. A fita das dez abas é `hefesto_vivo._fita` → `monta.fita`, e
# as réguas do chip desta aba medem aquela (`test_a_aba_07_usa_o_controle_da_fita`).
# ---------------------------------------------------------------------------


def _texto(x: object) -> str:
    """Escapa para posição de TEXTO, com a aspa CRUA — como o desenho faz.

    A razão é a do `desenho_dos_lancadores._e`, e ela é de laço infinito: o
    piloto só reescreve quando `innerHTML !== valor`, e o lado esquerdo é o que
    o DOM **devolve**. Uma grafia que o DOM normaliza de volta nunca casa, e a
    reescrita não para nunca.
    """
    return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# `quantos_da_mesa` SAIU EM 11/09/2026 — A2-002, aprovada por ela, e saiu com a
# frase que ela alimentava. O "?" do quadro dizia *"a resposta vale igual para
# os N (x no cabo, y no rádio)"*; essa oração REPETIA o cabeçalho a dois
# centímetros, que é o dono do número.
#
# O QUE ELA CURAVA CONTINUA CURADO EM OUTRO LUGAR, e a lição não se perde: quem
# conta LÊ O TRANSPORTE, nunca a palavra da tela (ONDA4-S10, 06/09/2026) —
# `mesa_viva.texto_da_contagem` é quem escreve o cabeçalho, e a régua daquela
# lei mede as superfícies que restaram.


# ---------------------------------------------------------------------------
# A LISTA DE EXCLUSÃO — OS-LANCADORES-IGUAIS-E-A-LISTA-DE-EXCLUSAO-01, E5
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _Escolha:
    """Qual cartão abriu a escolha do jogo, e para quê.

    Do MÓDULO, pela razão da :data:`VIGIA`: o pacote é recriado a cada tique.
    É o mesmo papel do :data:`_PARA_QUEM` do «Localizar», com a lista junto.
    """

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

#: As classes de janela MEDIDAS que o cadastro do cartão não alcança. O flatpak
#: do RetroArch se chama `org.libretro.RetroArch`, e a janela dele diz
#: `com.libretro.RetroArch` (medido em 10/09/2026 com `cos-cli info`).
_JANELAS_MEDIDAS: dict[str, tuple[str, ...]] = {
    "retroarch": ("com.libretro.RetroArch",),
}

#: Os cartões cuja biblioteca o censo LÊ jogo por jogo, com a chave de janela.
_COM_BIBLIOTECA = ("heroic", "lutris")
#: O cartão que não é lançador de jogo: o Flatpak é o pacote dos outros.
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
    vazio saiu em 21/09/2026, palavra dela — *"é um espaço vertical que
    ganhamos ao remover"*.

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
        if (not any(a.gesto == desenho.EXCLUIR for a in lanc.acoes)
                or not por_cartao.get(lanc.chave)):
            saida.append(lanc)
            continue
        rodape = desenho.rodape_da_exclusao_html(por_cartao.get(lanc.chave, []))
        fora = rodape
        if lanc.chave == desenho.STEAM and lida is not None:
            filtrada = dataclasses.replace(
                lida, recusados=tuple(r for r in lida.recusados if r[0] not in appids_fora))
            lista = desenho.lista_de_jogos(filtrada)
            if desenho.LISTA_VAZIA not in lista and lista.strip():
                fora = lista + rodape
        saida.append(dataclasses.replace(lanc, fora=fora, tem_lista=True))
    return saida


def _relatar(gesto_: str, frase: str) -> None:
    """O recibo de um gesto da exclusão, no diário — a tela mostra o cartão."""
    print(f"[relato] {PAGINA} · {gesto_}: {frase}", file=sys.stderr)


def _pintura(lancadores: list[desenho.Lancador]) -> dict[str, Any]:
    """A carga da aba: os endereços **e a grade inteira**, com as molduras.

    POR QUE A GRADE VAI JUNTO, e é o defeito que esta função existe para curar
    (fotografado em 02/09/2026): a `MOLDURA` do cartão é uma CLASSE do
    contêiner, e a pintura do piloto não escreve classe — escreve texto,
    `innerHTML`, largura, fundo e `value`. Os cinco endereços por cartão
    (`-selo`, `-jogos`, `-diz`, `-acoes`, `-fora`) não alcançam o `<div
    class="lanc ...">`, e a página publicada nasce com os seis em `ausente`.
    Resultado medido: o cartão da Steam com o selo verde `CHEGAM` dentro de uma
    moldura cinza de *ausente* — a mesma tela dizendo duas coisas opostas.

    O `blocos` É O MECANISMO QUE JÁ EXISTE para isto, e não um segundo
    vocabulário: `a08_conexoes` troca o mapa do gabinete e a lista de aparelhos
    pelo mesmo caminho, pela mesma razão (um bloco cujo conteúdo muda de FORMA,
    e não só de valor). O piloto troca o `innerHTML` **só quando ele difere**.

    OS ENDEREÇOS CONTINUAM SENDO EMITIDOS, e isso não é redundância: eles são o
    contrato que a régua da aba cobra nos dois sentidos (nada emitido cai no
    chão, nada da página fica sem dono).

    FATO ERRADO, SUBSTITUÍDO — esta docstring afirmava que *"o `blocos` corre
    ANTES da `mesa` no piloto, de modo que os campos pousam na grade
    recém-trocada e escrevem o mesmo valor — zero pintura, zero briga"*. **Não
    é zero.** Medido na janela dela em 02/09/2026, com a MESMA carga pintada 20
    vezes seguidas: o piloto conta **uma pintura por volta, para sempre**, e a
    causa é do PINTOR e não daqui — o `escrever()` carimba
    `el.dataset.hefVisto = '1'` em todo elemento que visita
    (`hefesto_vivo.py:150`), a grade emitida NÃO tem esse atributo, e o
    `alvo.innerHTML !== html` de `:303` nunca casa. A ordem correta (`blocos`
    antes de `mesa`) é justamente o que garante o desencontro.

    NÃO É O APÓSTROFO, e a distinção importa para quem for curar: com um nome
    de jogo sem apóstrofo a contagem já era `1` a cada volta. O apóstrofo
    somava um SEGUNDO laço, na lista de jogos, e esse morreu com o `_e`/`_a` do
    desenho (ver :func:`desenho_dos_lancadores._e`). Este resta, e está
    relatado como trabalho do PINTOR: comparar ignorando o `data-hef-visto`,
    carimbar depois de comparar, ou pintar `blocos` DEPOIS de `mesa`.
    """
    # A LINHA «PARA QUEM» DA TELA DE REGISTRO SAI DAQUI, e não do `pacote()`,
    # porque ela tem de acompanhar TODA resposta — inclusive a do próprio clique
    # que abriu a tela. Emiti-la só na pintura do tique faria a tela abrir
    # dizendo o alvo ANTERIOR por até um décimo de segundo, e num campo cuja
    # única função é dizer "para qual?" isso é a tela respondendo errado.
    #
    # ELA É TEXTO E O PRODUTO É O DONO — por isso é `data-campo`, e por isso ela
    # pode ser repintada a cada tique sem brigar com ninguém. As DUAS caixas de
    # texto da tela não têm endereço nenhum, e a razão está em
    # `desenho.NOVO_ALVO`: um `data-campo` num `<input>` seria reescrito por
    # cima do que ela está digitando, dez vezes por segundo.
    # O NOME SAI DOS CARTÕES QUE JÁ ESTÃO NA MÃO, e não de uma leitura nova.
    # A primeira versão desta linha chamava `_declarados()` aqui — e isso é um
    # `maquina.json` aberto A CADA TIQUE, dez vezes por segundo, dentro do
    # orçamento de 100 ms da janela inteira. Toda leitura de disco desta aba
    # roda fora do tique, na `_Vigia`, e por uma razão que o próprio
    # `_onde_estao_os_lancadores` declara: *"disco é disco"*. Os `lancadores`
    # que chegam aqui JÁ vieram daquela leitura, com `chave` e `nome` — pedir
    # de novo ao disco o que já está no argumento é o custo pelo nada.
    quem = {x.chave: x.nome for x in lancadores}
    valores = desenho.Quadro(lancadores=lancadores).valores()
    valores[desenho.NOVO_PARA_QUEM] = (
        desenho.NOVO_PARA_O_CARTAO.format(nome=quem[_PARA_QUEM])
        if _PARA_QUEM in quem else desenho.NOVO_SEM_ALVO)
    blocos = {desenho.SELETOR_DA_GRADE: desenho.cartoes_html(lancadores)}
    # A ESCOLHA DO JOGO, quando um cartão a abriu: o miolo da pop-up inteiro,
    # montado no clique (ele lê a biblioteca do lançador) e repetido a cada
    # tique. O piloto só troca o `innerHTML` quando ele muda — e é isso que
    # guarda a opção que ela marcou entre um tique e outro.
    if _ESCOLHA.miolo:
        blocos[f"#{desenho.MIOLO_DA_ESCOLHA}"] = _ESCOLHA.miolo
    return {"mesa": valores, "blocos": blocos}


def _resposta(lida: desenho.Leitura | None,
              state: dict[str, Any] | None = None) -> dict[str, Any]:
    """O que um gesto devolve para a tela — a mesma carga da pintura.

    Um gesto que trocasse só os campos deixaria a moldura do tique anterior:
    "Consertar" leva o cartão de `NÃO CHEGAM` a `CHEGAM` e a borda laranja
    ficaria até o próximo tique. Meio segundo de tela mentindo continua sendo
    tela mentindo.

    O `state` É OPCIONAL E ELE IMPORTA: sem ele o aviso vivo do jogo aberto
    sumiria da tela pelo tempo entre o gesto e o tique seguinte, e o botão
    "Não perguntar para este jogo" sumiria junto — o clique dela apagaria por
    meio segundo justamente o aviso sobre o qual ela está agindo.
    """
    return _pintura(com_a_exclusao(
        com_o_que_o_daemon_diz(desenho.cartoes(lida), state, lida), lida))


@registrar("07-lancadores.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    """A aba inteira, e ela NÃO depende de controle nenhum.

    O gerador já tinha medido isto e escrito no próprio arquivo: nenhuma função
    de `prontuario_dos_jogos` recebe controle, MAC, device ou transporte — os
    cinco impedimentos e as duas curas são fatos do JOGO EM DISCO. É por isso
    que a fita desta aba nasce esmaecida (fora de `monta.ABAS_QUE_ESCOLHEM`) e por isso este
    pacote não devolve `colunas`: não há nada a dizer por controle.

    NÃO DEPENDER DE CONTROLE NÃO É PODER MENTIR SOBRE ELE — 03/09/2026. A fita
    continua na tela, e enquanto ela vinha do desenho esta aba afirmava dois
    controles que não estão na mesa dela. `ctx.mesa` é a mesma leitura que o
    cabeçalho usa, e a fita sai dela pelo piloto (`hefesto_vivo._fita`).
    """
    carga = _resposta(VIGIA.agora(), ctx.state)
    valores = carga["mesa"]
    # O "?" CONTAVA CONTROLE E DEIXOU DE CONTAR — 11/09/2026, A2-002, aprovada
    # por ela. A cura de 02/09 tirou o número dos CARTÕES e deixou o do texto de
    # ajuda; a de 03/09 deu-lhe endereço e alimentou-o da mesa VIVA. Agora a
    # frase inteira saiu: ela repetia o cabeçalho a dois centímetros, que é o
    # dono do número. Com ela saíram o `lanc-quantos`, o `quantos_html` e o
    # `quantos_da_mesa` — **um endereço emitido sem elemento na página é o
    # piloto pintando no vazio**, e por isso os três saem juntos.
    fora: dict[str, Any] = dict(valores)
    fora["blocos"] = dict(carga["blocos"])
    # A FITA NÃO SAI DAQUI — nem com a mesa vazia, desde 22/09/2026. Quem a
    # escreve nas dez abas é `hefesto_vivo._fita` (`monta.fita`); escrever por
    # cima dela era o segundo dono que fazia esta aba sambar 120 vezes em 40
    # tiques (06/09). A exceção da mesa vazia morreu em 21/09, quando o piloto
    # passou a pintar a fita vazia em vez de se calar; mantida, ela pintava
    # `Selecionar:` + `Todos` sobre controle nenhum, que ela pediu para sumir:
    # *"quando não tiver controle Não Aparece o selecionar:"*.
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
    return _resposta(VIGIA.ler(), ctx.state)


# ---------------------------------------------------------------------------
# O «CONSERTAR» DOS OUTROS LANÇADORES MORREU AQUI — LANCADOR-LOCALIZAR-01,
# 10/09/2026, e o que caiu foi o VASO, não a cura.
#
# Cinco funções viviam neste ponto: `_armado_da_cura`, `_qual_cartao`,
# `_com_a_confirmacao_da_cura`, `_o_cartao` e o gesto `consertar_lancador`.
# Elas nasceram em 09/09 com o botão «Consertar» do cartão LOCALIZADO, e o
# botão saiu por palavra dela:
#
#     "na real não faz sentido. Digo se tenho tudo instalado e tá pra ser
#      identificado não tem pq ter o botão de consertar. Ou no Máximo Localizar
#      o lançador. aí eu mesmo abro a tela e procuro o .desktop."
#
# A LEITURA DELA É A LEITURA CERTA DO CARTÃO como ele estava pintado: selo
# `LOCALIZADO`, moldura `chega` (a MESMA do `ok`/CHEGAM da Steam) e a frase do
# corpo terminando em *"um jogo aberto por aqui entra pelo mesmo caminho de
# qualquer outro"*. Nada ali declarava defeito, e embaixo disso o produto
# oferecia *consertar*.
#
# **A LACUNA CONTINUA ABERTA, e é real:** `assets/hefesto-launch.sh` só age com
# `SteamAppId`, e nenhum jogo do Heroic, do Lutris, do RetroArch, do Dolphin ou
# do mGBA tem um. `integrations/cura_por_estrada` continua sendo o único código
# que entrega o ambiente da ponte a um lançador que não é a Steam — o módulo e
# as 26 provas FICAM, com a dívida declarada em
# `tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py`.
#
# O VASO CERTO É A CARONA, e a palavra dela é de 16/08
# (`app/actions/carona_do_wrapper.py:7`): *"nem precisa ter um botão na gui, mas
# ele se auto corrigir ao clicarmos em aplicar ou salvar o perfil"*. Para a
# Steam a casa já honrou isso (`perfil.com_a_carona`, chamada pelo «Aplicar» e
# pelo «Salvar» do rodapé); para os outros, é a LANCADOR-CARONA-01.
# ---------------------------------------------------------------------------


def _com_outra_frase(diz: str,
                     state: dict[str, Any] | None = None) -> dict[str, Any]:
    """A aba de novo, com o corpo do cartão da Steam trocado.

    OS DOIS GESTOS QUE RESPONDEM COM TEXTO passam por aqui, e não montam o
    cartão cada um do seu jeito: dois lugares escrevendo o mesmo cartão é como
    um deles esquece um endereço e a tela fica com metade do valor velho.

    `dataclasses.replace` E NÃO UM CONSTRUTOR À MÃO, e a troca é uma cura: a
    versão anterior listava os nove campos do `Lancador` um a um, e o décimo
    campo (`presente`, nascido hoje) teria voltado ao PADRÃO em silêncio — a
    contagem do topo cairia de "2 encontrados" para "1 encontrado" **só depois
    de ela clicar em Detectar**, e nada acusaria. Copiar campo a campo é a
    forma de defeito que só aparece quando alguém acrescenta um campo, meses
    depois, sem saber que esta linha existe.
    """
    lida = VIGIA.agora()
    cartoes = com_o_que_o_daemon_diz(desenho.cartoes(lida), state, lida)
    cartoes[0] = dataclasses.replace(cartoes[0], diz=diz)
    return _pintura(cartoes)


#: A TERCEIRA EVIDÊNCIA responde por um jogo que **já fechou**, e por isso ela
#: tem frase própria: dizer "está aberto agora" sobre um jogo fechado seria a
#: tela afirmando o que o produto não mediu. Ver :func:`a_escada_do_jogo`.
FECHADO = "fechado"
ABERTO = "aberto"


def a_escada_do_jogo(state: dict[str, Any] | None) -> tuple[int | None, str]:
    """`(appid, "aberto"|"fechado")` — as TRÊS evidências da GTK, nesta ordem.

    ELA É A DA JANELA VELHA, e a ordem não é minha: `daemon_actions`
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
    """"Detectar o jogo que está aberto": diz QUAL é, ou recusa dizendo.

    A ESCADA É A DA GTK, e ela substituiu a evidência única — ver
    :func:`a_escada_do_jogo`, que traz a ordem e o que cada degrau alcança.
    Aqui fica só o que a tela diz de cada resposta.

    A FRASE DO JOGO FECHADO É DIFERENTE, e tinha de ser: o terceiro degrau
    responde por um jogo que **já não está rodando**, e reaproveitar o "está
    aberto agora" faria a tela afirmar o que o produto não mediu — que é o
    defeito que esta aba inteira existe para matar. Ela está em
    `espera_a_palavra_dela`: é texto novo, e texto de tela é dela.

    O QUE ELE NÃO FAZ: criar o perfil. Isso é da aba Perfis (`a10_perfis`), e
    ter dois caminhos para o mesmo disco é como duas telas passam a discordar.
    """
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    appid, quando = a_escada_do_jogo(ctx.state)
    if appid is None:
        # *"DE ONDE FOR"* É A MENSAGEM DA ABA INTEIRA, não desta recusa —
        # A2-055, 11/09/2026. 89 → 67.
        raise RuntimeError(
            "Nenhum jogo aberto agora. Abra o jogo, volte aqui e clique de "
            "novo.")
    lida = VIGIA.agora()
    tem = lida is not None and str(appid) in lida.com_wrapper
    nome = f"<b>{desenho._e(slo.rotulo_do_jogo(appid))}</b>"
    abertura = (f"{nome} está aberto agora e " if quando == ABERTO else
                f"{nome} foi o último jogo que passou pelo atalho do Hefesto, e "
                "já fechou. Ele ")
    return _com_outra_frase(
        abertura
        + ("<b>abre pelo atalho do Hefesto</b>." if tem else
           "<b>não abre pelo atalho do Hefesto</b>"
           + _quem_repoe_o_atalho(lida, appid)), ctx.state)


#: O QUE O HEFESTO FAZ PELO JOGO SEM O ATALHO — STEAM-INPUT-01, acréscimo de
#: 24/09/2026. A frase terminava em *"clique em Consertar com o jogo e a Steam
#: fechados"*, e o «Consertar» saiu da aba em 21/09 (*"os mesmos botões pra
#: todos os lançadores. sempre."*): ela mandava a um botão que não existe.
#: Quem repõe hoje é o vigia de fora (`hefesto-steam-input-guard`, que acorda
#: quando a Steam escreve ao sair e roda a sentinela `--reparar`), e ele repôs o
#: do PRAGMATA sem clique nenhum na noite de 21/09. A frase diz isso, curta, na
#: forma da escolha dela para o chip «Steam Input» (*"Liga quando a Steam
#: fechar"*) — e não aponta botão nenhum, porque não há o que clicar.
REPOE_QUANDO_A_STEAM_FECHAR = " — ele volta quando a Steam fechar."


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

    É A RECUSA DELA, e o produto inteiro a respeita: `censo_do_wrapper` pula
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
    permanente, e desfazê-lo pedia editar um JSON à mão. Decisão dela,
    02/09/2026 — nasce o par, e o botão é este.

    A RECUSA VAI PARA A TELA, e é por isso que `remove_dismissed_appid` devolve
    `bool` em vez de engolir como o `add`: se o arquivo não deu para reescrever,
    a linha continuaria na lista e o segundo clique pareceria o primeiro — o
    botão que aceita o clique e não faz nada.
    """
    from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as lwd

    appid = _appid_do_clique(o, "voltar-a-perguntar")
    if not lwd.remove_dismissed_appid(appid):
        # O NOME DO ARQUIVO NO DISCO É NOSSO — A2-044, 11/09/2026. O que ela
        # precisa saber é o ESTADO em que a coisa ficou. 158 → 78.
        raise RuntimeError(
            "Não consegui voltar a perguntar por este jogo — o lembrete "
            "continua desligado.")
    VIGIA.esquecer()
    return _resposta(VIGIA.ler(), ctx.state)


@gesto("07-lancadores.html", desenho.ABRIR,
       grava="abre a janela da Steam por cima do que ela está fazendo")
def abrir_lancador(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Abrir o lançador": abre a Steam. Nos outros cinco, RECUSA dizendo.

    DECISÃO 17 DELA, 03/09/2026: o botão LIGA, e o gesto entra em
    `hefesto_vivo.PERIGOSOS` — as duas metades, e a segunda não é opcional. Sem
    ela a `--prova-gesto` clicaria este botão e abriria a Steam na tela dela,
    que é o oposto de toda janela desta casa nascer `--oculta`.

    O FATO QUE CAIU, e ele estava escrito no próprio arquivo:
    `SEM_DONO["abrir-lancador"]` dizia *"o daemon não tem método para isso"*.
    É verdade e é a **pergunta errada**. Medido em 03/09/2026:
    `pacotes.daemon.metodos()` tem **40 métodos**, e o único cujo nome sequer
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
        # A TELA NÃO CONFESSA DÍVIDA NOSSA — A2-039, 11/09/2026, aprovada por
        # ela. A frase dizia *"Ainda não sei abrir"* e *"só sabe … por
        # enquanto"*: duas confissões numa frase só, que é a forma exata que ela
        # proibiu em 07/09 (*"O app tem que funcionar e não mostrar na tela que
        # o app não presta."*). O CONSELHO já estava lá; o que sai é a desculpa
        # em volta. 197 → 114.
        nomes = {x.chave: x.nome for x in desenho.SEM_FONTE}
        raise RuntimeError(
            f"Abra o {nomes.get(qual, qual)} como você já abre — o perfil "
            "entra do mesmo jeito, pelo nome do processo e pela janela.")
    if not slo.reopen_steam():
        # O `xdg-open` E O `PATH` SAÍRAM — A2-040: eles não dizem nada a quem
        # lê, e o que fazer não muda com eles. 144 → 85.
        raise RuntimeError(
            "Não achei como abrir a Steam nesta máquina. Abra-a pelo seu "
            "menu — nada foi alterado.")
    return None


@gesto("07-lancadores.html", desenho.EXCLUIR)
def abrir_a_exclusao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Adicionar à lista de exclusão»: abre a escolha do jogo DAQUELE lançador.

    O mesmo clique abre a pop-up (a âncora muda o `:target`) e manda este gesto,
    que monta a lista — como o «Localizar» sabe para qual cartão abriu.
    """
    _abrir_a_escolha(desenho.EXCLUIR, str(o.get("v") or ""), ctx.state)
    return _resposta(VIGIA.agora(), ctx.state)


@gesto("07-lancadores.html", desenho.CRIAR_PERFIL)
def abrir_o_criar_perfil(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Criar perfil para um jogo»: a mesma escolha, no modo do perfil."""
    _abrir_a_escolha(desenho.CRIAR_PERFIL, str(o.get("v") or ""), ctx.state)
    return _resposta(VIGIA.agora(), ctx.state)


@gesto("07-lancadores.html", desenho.CONFIRMAR_EXCLUSAO, grava="adicionar")
def confirmar_a_exclusao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """Põe o jogo marcado na lista e tira dele, agora, o que o Hefesto pôs no disco.

    A LISTA É O DONO (`integrations/lista_de_exclusao`): ela escreve nas duas
    listas por feature e o `tirar_do_disco` tira o pino, o atalho, o device KS e
    as camadas Vulkan. Com a Steam aberta o disco espera o vigia — e o jogo já
    abre sem o Hefesto mesmo assim, porque o `hefesto-launch` lê a lista.
    """
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
    """«Tirar da lista»: o jogo volta ao Hefesto.

    A lista sai SÓ das listas por feature em que ELA escreveu; o pino e o
    atalho voltam quando a Steam fechar (o vigia), e o resto no próximo
    lançamento do jogo.
    """
    chave = str(o.get("v") or "").strip()
    status = lista_de_exclusao.tirar(chave)
    if status == "erro":
        raise RuntimeError("Não consegui tirar o jogo da lista de exclusão.")
    _relatar(desenho.TIRAR_DA_EXCLUSAO, f"{chave}: {status}")
    VIGIA.esquecer()
    return _resposta(VIGIA.ler(), ctx.state)


@gesto("07-lancadores.html", desenho.CONFIRMAR_PERFIL, grava="criar_para_o_jogo")
def confirmar_o_perfil(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """Cria o perfil do jogo marcado PELA ABA PERFIS, e a tela vai para lá.

    D-2109-O-CRIAR-PERFIL-LEVA-A-ABA-PERFIS: um gravador (o da aba Perfis,
    :func:`a10_perfis.criar_para_o_jogo`), dois caminhos de chegada. O botão de
    confirmar é uma âncora para `10-perfis.html`: o mesmo clique manda este
    gesto e troca de aba, e o perfil novo chega lá aberto no editor.
    """
    from . import a10_perfis

    jogo = _o_escolhido(o)
    janelas = _ESCOLHA.janelas.get(jogo.chave, ())
    classes = janelas if janelas else (jogo.chave,)
    frase = a10_perfis.criar_para_o_jogo(
        ctx, p, classes=classes, nome_do_jogo=jogo.nome.split(" — ")[0])
    _relatar(desenho.CONFIRMAR_PERFIL, frase)
    _ESCOLHA.limpar()
    return _resposta(VIGIA.agora(), ctx.state)


# ---------------------------------------------------------------------------
# REGISTRAR O QUE O HEFESTO NÃO CONHECE — 08/09/2026, pedido dela
#
# A PORTA É UMA SÓ e o gesto é um só (:data:`desenho.ADICIONAR`); o que muda é
# o que chega. Sem `forma`, o clique veio de um BOTÃO DE CARTÃO e o que ele faz
# é abrir a tela apontando para aquele cartão. Com `forma`, o clique veio do
# «Adicionar» da tela e traz o que ela digitou — é ali que se grava.
#
# POR QUE DUAS METADES NO MESMO GESTO, e não dois gestos: a tela abre por
# `:target`, que é CSS puro e não passa pelo Python. Sem a primeira metade,
# nada saberia para qual cartão a tela abriu, e a segunda teria de adivinhar
# pelo texto — que é o palpite que esta aba inteira existe para não dar.
# ---------------------------------------------------------------------------
#: PARA QUAL CARTÃO a tela de registro está aberta. Vazio = ela abriu pelo botão
#: global, e o lançador nasce novo.
#:
#: É MEMÓRIA DE SESSÃO, e é o certo: a pergunta que ele responde ("de qual
#: cartão foi o último clique?") só existe entre o clique e o «Adicionar». Gravá-lo
#: em disco seria guardar uma intenção que não sobrevive a fechar a janela.
_PARA_QUEM = ""

#: O TETO DO QUE ELA DIGITA, e ele é do LADO DE CÁ de propósito: o schema já tem
#: o dele (`LancadorDeclarado`), e este existe para a recusa chegar à TELA com
#: uma frase, em vez de subir como `ValidationError` do pydantic — que quem lê
#: não tem como interpretar.
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
    """O que ela digitou, resolvido no disco: `(campo, agulha, onde)`.

    AS TRÊS FORMAS QUE ELA PODE DIGITAR, e as três são aceitas porque as três
    são como um programa se nomeia nesta máquina:

    ==========================  ==========  ==================================
    o que ela digita            `campo`     o que se guarda
    ==========================  ==========  ==================================
    ``ryujinx``                 comandos    o comando, achado no ``PATH``
    ``/opt/Ryujinx/Ryujinx``    comandos    o caminho inteiro (é o AppImage)
    ``org.ryujinx.Ryujinx``     atalhos     o ``stem`` do ``.desktop``
    ==========================  ==========  ==================================

    O CAMINHO INTEIRO CABE EM ``comandos`` SEM UMA LINHA NOVA, e isso é
    medição, não sorte: ``shutil.which`` devolve o próprio caminho quando ele
    tem uma barra e é executável. É exatamente o caso que a frase do cartão
    ausente nomeia — *"um AppImage solto, por exemplo"*.

    **O TERCEIRO RETORNO É O QUE PROVA**: `onde` é o caminho que o disco
    devolveu, e é ele que a tela mostra. Dizer "guardei" sem dizer ONDE seria
    pedir que ela acredite; com o caminho, ela confere com um `ls`.

    DEVOLVE `("", "", "")` QUANDO NÃO ACHA NADA — e quem chama **não grava**.
    Guardar um lançador que não está no disco é fabricar um cartão que mente, e
    ele mentiria para sempre: a busca nunca o acharia, e o cartão diria «NÃO
    LOCALIZADO» sobre uma coisa que ela mesma acabou de declarar.
    """
    import shutil

    from hefesto_dualsense4unix.integrations import jogos_locais as jl

    # O `.desktop` PRIMEIRO, e a ordem importa num caso real: `flatpak run …`
    # publica atalhos com nome de pacote, e um `stem` que por acaso também seja
    # um comando no `PATH` deve ser lido como o atalho, que é o mais específico.
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
    """Os rótulos que o cartão de `chave` mostra NESTE instante.

    Pergunta ao DONO do desenho com a leitura VIVA, em vez de supor o estado.
    Uma leitura que levanta devolve tupla vazia: a recusa então não cita botão
    nenhum, que é melhor do que citar um que talvez não esteja lá.
    """
    try:
        lida = VIGIA.agora()
        for cartao in desenho.cartoes(lida):
            if cartao.chave == chave:
                return tuple(a.rotulo for a in cartao.acoes)
    except Exception:  # a recusa não pode virar erro de leitura
        return ()
    return ()


def _recusa_de_quem_ja_tem_cartao(chave: str, nome: str,
                                  tem: tuple[str, ...] | None = None) -> str:
    """A recusa do botão global para um lançador que já tem cartão de fábrica.

    **ELA MANDAVA CLICAR ONDE NÃO HAVIA NADA EM DOIS DOS TRÊS ESTADOS**, e o
    estado aberto era o da máquina dela — 08/09/2026, achado pelo conferente.
    A frase citava o «Localizar este Lançador», que o cartão só mostra quando o
    Hefesto NÃO achou. Numa máquina com a Steam instalada o cartão sai
    `selo='ok'` com «Abrir o lançador» e «Criar perfil para um jogo», e a tela
    mandava clicar num botão ausente.

    A régua que nasceu com o conserto do beco olhava só o estado `off` — ela
    montava uma `Leitura` com tudo vazio —, e por isso ficava verde. *Uma régua
    que só mede o estado em que a cura foi escrita não mede a cura.*

    **AGORA A FRASE PERGUNTA AO CARTÃO.** Ela cita o botão que ESTÁ lá, e quando
    nenhum dos dois serve ela diz o FATO e para — porque a alternativa é a tela
    inventar um caminho, que é o defeito de origem.

    A FRASE NÃO LEVA ARTIGO ANTES DO NOME: os nomes de cartão têm gêneros
    diferentes ("a Steam", "o Lutris") e esta aba escreve **a** Steam em toda
    parte. Mesma medição de `desenho.NOVO_PARA_O_CARTAO`.

    E OS RÓTULOS SÃO LIDOS, nunca digitados: esta frase manda clicar num botão,
    e um texto digitado aqui envelheceria calado no dia em que ela trocasse a
    palavra — que foi o dia de hoje.
    """
    #: `tem=None` PERGUNTA À MÁQUINA; uma tupla dispensa a leitura. O parâmetro
    #: existe para a régua poder cobrar os TRÊS estados — foi por medir só o
    #: estado em que a cura foi escrita que a primeira versão ficou verde sobre
    #: um beco aberto nos outros dois.
    if tem is None:
        tem = _botoes_do_cartao_agora(chave)
    abertura = f"{nome} já tem cartão nesta aba"

    # OS DOIS RÓTULOS DO MESMO BOTÃO — 11/09/2026, A2-022: o cartão não
    # localizado diz «Localizar este lançador» e o localizado diz «Apontar outro
    # caminho». A frase cita o que ESTÁ lá, e por isso pergunta por ambos — na
    # ordem em que o cartão os oferece.
    for aponta in (desenho.ADICIONAR_ROTULO, desenho.APONTAR_ROTULO):
        if aponta in tem:
            # O NOME APARECIA TRÊS VEZES EM 245 CARACTERES — A2-051,
            # 11/09/2026. 245 → 166.
            return (f"{abertura}. Use o «{aponta}» do cartão dele — assim o "
                    f"que você disser entra na busca daquele cartão, em vez "
                    f"de criar um segundo.")

    tirar = desenho.acao_de_tirar(chave).rotulo
    if tirar in tem:
        # A2-052, 11/09/2026: 194 → 144.
        return (f"{abertura}, e ele já está apontado. Use o «{tirar}» do "
                f"cartão dele primeiro — depois ele volta a perguntar onde "
                f"está.")

    # O TERCEIRO RAMO PERDEU O BECO — 10/09/2026. Ele dizia *"Se o que ele
    # achou não é o que você quer, me diga — hoje o cartão não tem por onde
    # trocar"*: o produto contando à usuária um buraco NOSSO, que é o que a
    # decisão dela de 07/09 proíbe. O buraco fechou (o «Localizar» está no
    # cartão achado), e a frase perdeu a razão de existir.
    #
    # ELE NÃO CITA BOTÃO NENHUM, e é o que o torna verdadeiro em todo estado
    # que sobra: a primeira meia volta (`nao_sei`, ainda não procurei), o cartão
    # da Steam que não conseguiu ler a biblioteca, e a leitura que LEVANTOU.
    # Nesses três não há botão a apontar, e inventar um é o defeito de origem
    # desta função — a tela mandando clicar onde não há nada.
    # A SEGUNDA FRASE ERA A PRIMEIRA AO CONTRÁRIO — A2-053, 11/09/2026.
    # 180 → 96.
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
        # A PRIMEIRA METADE: só aponta. `data-v` vazio é o botão global, e ele é
        # legítimo — quem recusa `v` vazio é o `abrir-lancador`, que sem ele
        # abriria um lançador escolhido por acaso. Aqui o vazio É a resposta.
        _PARA_QUEM = str(o.get("v") or "").strip()
        return _resposta(VIGIA.agora(), ctx.state)

    if not alvo:
        # OS TRÊS EXEMPLOS ESTÃO NO `placeholder` DO CAMPO que ela acabou de
        # deixar em branco — A2-046, 11/09/2026. A recusa os repetia pela
        # terceira vez na mesma tela (a outra é o `?`). 233 → 105.
        raise ValueError(
            "Diga onde ele está — os exemplos estão no campo. Ou clique em "
            f"«{desenho.PROCURAR_O_ARQUIVO_ROTULO}» e aponte com o mouse.")
    if len(alvo) > _MAXIMO_DA_AGULHA:
        # «LINHA DE INICIALIZAÇÃO» SAIU — A2-047: nesta aba a palavra nomeia
        # OUTRA coisa (o atalho do Hefesto na linha do jogo). 126 → 74.
        raise ValueError(
            f"São {len(alvo)} caracteres, e o teto é {_MAXIMO_DA_AGULHA}. Diga "
            "só o comando ou o nome do atalho.")
    # O RECIBO VEM ANTES DA LEITURA, e a ORDEM é cura: `_guardar_onde_ele_esta`
    # chama `VIGIA.esquecer()`, e num `{**_resposta(VIGIA.ler(), …), "recado":
    # …}` o Python avalia o `**` PRIMEIRO — a aba sairia pintada com a busca
    # velha, e o cartão que ela acabou de ensinar só acenderia no vencimento do
    # TTL. É o defeito "o botão que grava e responde calado", pelo avesso.
    recado = _guardar_onde_ele_esta(p, rotulo, alvo, _achar_o_que_ela_digitou)
    return {**_resposta(VIGIA.ler(), ctx.state), "recado": recado}


def _achar_o_que_ela_digitou(alvo: str) -> tuple[str, str, str]:
    """`onde_isso_esta`, e a RECUSA na língua de quem DIGITOU.

    São duas portas para a mesma pergunta e duas recusas, porque quem digitou um
    comando e quem apontou um arquivo erraram coisas diferentes — ver
    :func:`_achar_o_que_ela_apontou`.
    """
    achado = onde_isso_esta(alvo)
    if not achado[0]:
        # QUASE INTEIRA DE PROPÓSITO — A2-054, 11/09/2026. Esta recusa passa a
        # ser o ÚNICO dono do fato *"onde eu procurei"*, que saiu do `?` e do
        # corpo do cartão: é aqui que ele serve, porque é aqui que a busca
        # falhou. 172 → 161.
        raise RuntimeError(
            f"Não achei {alvo!r} nesta máquina. Procurei o comando no `PATH` e "
            f"o atalho `{alvo.rsplit('/', 1)[-1]}.desktop` nas pastas de "
            f"aplicativos. Confira e tente de novo; nada foi guardado.")
    return achado


def _guardar_onde_ele_esta(p: Any, rotulo: str, alvo: str,
                           achar: Callable[[str], tuple[str, str, str]]) -> str:
    """Grava a agulha no `maquina.json` e devolve o RECIBO. Dono único da escrita.

    **AS DUAS PORTAS DA TELA DE REGISTRO PASSAM POR AQUI** — o «Adicionar», que
    lê o que ela digitou, e o seletor do sistema
    (:data:`desenho.PROCURAR_O_ARQUIVO`), que lê o que ela apontou com o mouse.
    Dois caminhos até a mesma gravação, e a gravação é UMA: duas cópias desta
    função seriam duas validações, duas recusas e duas maneiras de escrever o
    mesmo `maquina.json` — e a segunda envelheceria calada, que é a razão pela
    qual esta aba já tinha UM gesto para os dois botões de registro.

    `achar` É QUEM RESOLVE E QUEM RECUSA, e é o único ponto em que os dois
    caminhos divergem: a frase de "não achei" tem de falar da coisa que ELA fez
    — digitar um comando, ou apontar um arquivo.

    A ORDEM DAS RECUSAS NÃO MUDOU: a chave e a colisão com cartão de fábrica
    vêm ANTES da procura em disco. Inverter faria quem digita «Steam» no botão
    global ouvir *"não achei"* em vez de *"já tem cartão nesta aba"* — a
    resposta certa para a pergunta errada.
    """
    global _PARA_QUEM

    para_quem = _PARA_QUEM
    de_fabrica = {x.chave: x.nome for x in desenho.EMBUTIDOS}

    chave = para_quem or chave_do_rotulo(rotulo)
    if not chave:
        # O «ENDEREÇO INTERNO DO CARTÃO» É A NOSSA CHAVE — A2-048, 11/09/2026:
        # ela não a escolhe nem a vê. 112 → 64.
        raise ValueError(
            "Diga como ele se chama — é o nome que aparece no topo do cartão.")
    if not para_quem and chave in de_fabrica:
        raise RuntimeError(_recusa_de_quem_ja_tem_cartao(chave, de_fabrica[chave]))

    campo, agulha, onde = achar(alvo)

    # O NOME DE UM CARTÃO QUE JÁ EXISTE NÃO SE REESCREVE. Quem chega pelo botão
    # de um cartão está dizendo ONDE ele está — não como ele se chama. Mandar o
    # que ela digitou aqui faria a gravação trocar o rótulo de um cartão de
    # fábrica (que é desenho que ela aprovou) ou apagar o nome que ela mesma deu
    # a um declarado, porque `fundir_declaracao` SOBRESCREVE valor que não é
    # dicionário. O cartão novo é o único caso em que o nome vem do teclado.
    de_hoje = {x.chave: x.nome for x in desenho.procurados(_declarados())}
    ok, motivo = _ok_e_motivo(p.machine_declare({"lancadores": {
        chave: {"rotulo": de_hoje.get(chave) or rotulo or chave,
                # A AGULHA NOVA SUBSTITUI A ANTERIOR DAQUELE CAMPO, e isso é a
                # fusão do `maquina.json` fazendo o que ela documenta. É o certo
                # aqui: ensinar de novo é CORRIGIR o que se ensinou antes, e uma
                # lista que só cresce não teria como perder o caminho errado
                # sem apagar o cartão inteiro.
                campo: [agulha]}}}))
    if not ok:
        raise RuntimeError(
            motivo or "Não consegui guardar isso agora. Nada foi alterado.")

    _PARA_QUEM = ""
    # ESQUECER É O QUE FAZ O CARTÃO ACENDER NO MESMO CLIQUE: a busca em disco
    # tem TTL, e sem isto o cartão novo só apareceria no vencimento — o botão
    # que grava e responde calado.
    VIGIA.esquecer()
    nome = de_fabrica.get(chave) if para_quem else rotulo
    recado = f"Guardei: {nome or chave} está em {onde}."

    # O QUE ELA DIGITOU E O PRODUTO NÃO USOU TEM DE SER DITO — 08/09/2026,
    # achado pelo conferente da segunda volta. Chegando pelo botão de um cartão,
    # a tela mostra «Como ele se chama» com rótulo e foco, e o nome digitado é
    # DESCARTADO: a chave e o rótulo vêm do cartão. Ela digitava e o produto
    # gravava outra coisa, calado.
    #
    # POR QUE O NOME DO CARTÃO GANHA, e isto não muda: aquele rótulo é DESENHO
    # que ela aprovou, e `test_o_que_ela_ensina_soma_com_a_busca_de_fabrica`
    # cobra que o ensino SOME com a busca em vez de trocar o nome. O defeito
    # nunca foi qual nome vence — é o silêncio.
    #
    # ESCONDER O CAMPO SERIA MELHOR, e é DESENHO: um campo a menos na caixa é
    # pixel, e pixel é decisão dela. Enquanto ela não vê, o produto para de
    # descartar calado — que é a metade que não precisa de aprovação nenhuma.
    if para_quem and rotulo and nome and rotulo.strip().casefold() != nome.casefold():
        # A CAIXA-ALTA DE ÊNFASE CAIU — A2-049, 11/09/2026: «ONDE» gritando no
        # meio da frase é a mesma maiúscula decorativa que saiu dos dois
        # rótulos, num lugar em que ela grita mais. 129 → 105.
        recado += (f" O nome «{rotulo.strip()}» não entrou: este cartão já se "
                   f"chama {nome}, e o botão dele só acrescenta onde procurar.")

    return recado


#: A PASTA EM QUE O SELETOR ABRE, e ela não é o `$HOME` por medição: DUAS das
#: quatro pastas de atalho desta máquina ficam dentro de `~/.local`, que um
#: seletor aberto no `$HOME` com arquivos ocultos desligados **não mostra**. A
#: sugestão é a primeira pasta de atalhos que existe no disco.
#:
#: **HOJE O PILOTO A DESCARTA, e isto está declarado em vez de escondido:**
#: `hefesto_vivo._escolher_arquivo` não repassa `sugestao` ao `_dialogo` (só o
#: `_salvar_arquivo` repassa), e aquele arquivo é de outra posse. O gesto manda
#: assim mesmo — o dia em que a linha nascer lá, isto passa a valer sem que
#: ninguém precise voltar aqui. Ver a entrega de LANCADOR-LOCALIZAR-01.
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


#: O TÍTULO DO DIÁLOGO DO SISTEMA. Ele é texto de tela, e diz o que ela vai
#: apontar — não "escolha um arquivo", que serviria para qualquer coisa.
TITULO_DO_SELETOR = "Escolha o atalho do lançador (.desktop)"


def _achar_o_que_ela_apontou(alvo: str) -> tuple[str, str, str]:
    """`onde_isso_esta`, e a RECUSA na língua de quem APONTOU um arquivo.

    **A RECUSA É OUTRA, e a diferença é medida.** Quem digitou errou o comando
    ou o nome do atalho, e a frase manda conferir os dois. Quem apontou com o
    mouse acertou o arquivo — o que ele pode ter errado é a PASTA: o produto só
    reencontra um `.desktop` que esteja numa das quatro pastas de aplicativos
    (`jogos_locais.pastas_de_atalhos`), e mandar a frase do teclado aqui seria
    dizer *"confira o caminho"* sobre um caminho que ela apontou com o dedo.

    **E A RECUSA ESTÁ CERTA, não é aspereza:** um atalho fora das quatro pastas
    é um lançador que a busca nunca acharia — o cartão diria «NÃO LOCALIZADO»
    para sempre sobre uma coisa que ela mesma acabou de apontar. É a mesma regra
    de `onde_isso_esta`: *não se grava o que não está no disco onde o produto
    procura*.
    """
    achado = onde_isso_esta(alvo)
    if not achado[0]:
        pastas = ", ".join(str(x) for x in _pastas_de_atalhos_para_a_frase())
        # A DESCRIÇÃO DA BUSCA SAIU E O CAMINHO A SEGUIR FICOU — A2-050,
        # 11/09/2026: a lista de pastas já está na variável, e é ela que serve.
        # 224 → 163.
        raise RuntimeError(
            f"Este arquivo está fora das pastas em que eu procuro, e eu não o "
            f"reencontraria: {alvo}. Escolha um atalho de "
            f"{pastas or 'uma pasta de aplicativos'}. Nada foi guardado.")
    return achado


def _pastas_de_atalhos_para_a_frase() -> tuple[str, ...]:
    """As pastas que a recusa NOMEIA — lidas do dono, nunca digitadas.

    Digitar as quatro aqui é como a frase envelhece calada no dia em que o
    `jogos_locais` ganhar a quinta. NUNCA levanta: uma recusa que vira erro de
    leitura troca a frase do dono por um traceback.
    """
    from hefesto_dualsense4unix.integrations import jogos_locais as jl

    try:
        return tuple(str(x) for x in jl.pastas_de_atalhos())
    except Exception:  # pragma: no cover - pastas ilegíveis
        return ()


@gesto("07-lancadores.html", desenho.PROCURAR_O_ARQUIVO, grava="machine_declare")
def procurar_o_arquivo(ctx: Contexto, o: dict[str, Any], p: Any
                       ) -> dict[str, Any] | None:
    """«Escolher o arquivo…» — ela aponta o `.desktop` com o mouse.

    **DECISÃO DELA, 09/09/2026, a opção (C):** *"Ou no Máximo Localizar o
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
    jogaria NA TELA DELA. O piloto devolve `None` e imprime no `stderr`, e este
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
    # A MESMA ORDEM DO «Adicionar»: o recibo primeiro, porque a gravação chama
    # `VIGIA.esquecer()` e a leitura tem de vir DEPOIS.
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
    clique dela — e é por isso que o botão é o mesmo nos dois casos, e não dois.

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
        # «APONTOU», E NÃO «DECLAROU» — A2-058, 11/09/2026: «declarar» é a
        # palavra do `maquina.json`; «apontar» é a palavra dos botões desta aba.
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
    """`(ok, motivo)`, seja tupla ou `bool` o que a ponte devolveu.

    A MESMA FUNÇÃO DA ABA 09 (`a09_sistema._ok_e_motivo`), e a cópia é
    consciente: os pacotes são território exclusivo por desenho — é o que deixa
    dez abas serem ligadas em paralelo sem uma linha de merge — e um pacote
    importar outro trocaria essa propriedade por sete linhas.

    A TOLERÂNCIA AO `bool` NÃO É ENFEITE: o dublê da régua dos botões devolve
    `True` para quase tudo, e sem esta função o gesto rebentaria com `TypeError`
    na régua e funcionaria na mão dela — a régua reprovando a cura.
    """
    if isinstance(resposta, tuple) and len(resposta) == 2:
        return bool(resposta[0]), resposta[1]
    return bool(resposta), None


#: O MÉTODO DA RECARGA nasceu aqui em 06/09/2026 com o "Este jogo não
#: funciona", e o gesto SAIU em 21/09/2026 com o desenho da lista de exclusão
#: (OS-LANCADORES-IGUAIS-E-A-LISTA-DE-EXCLUSAO-01). O nome fica neste módulo
#: porque o chip «Steam Input» da aba Jogar — quem escreve a mesma lista hoje —
#: o importa daqui, e é ELA quem o declara em `METODOS` agora.
METODO_DA_RECARGA = "launch_env.refresh"

#: A LISTA DE EXCLUSÃO NÃO FALA COM O DAEMON — 21/09/2026, e é de propósito: o
#: autoswitch relê a lista a cada volta (`lista_de_exclusao.contem`) e o
#: `hefesto-launch` a lê no lançamento. Não há ambiente a rematerializar.
#:
#: OS OUTROS CONTINUAM SEM PONTE, e a medição que os deixou assim não mudou:
#: o wrapper vive em dois arquivos em disco, e o `state_full` não tem UMA chave
#: sobre a Steam, sobre a lista de recusados ou sobre a de dispensados.
# `machine_declare` ENTROU EM 08/09/2026 com o lançador declarado por ELA: é a
# ÚNICA porta de escrita do `maquina.json`, e o lock daquele arquivo é de
# PROCESSO — uma segunda escrita viva noutro processo perderia a declaração de
# quem gravou primeiro, calada.
#: O `escolher_arquivo` ENTROU EM 10/09/2026 com o seletor do sistema da tela
#: de registro (decisão dela, a opção C). Ele é um PONTO DE EXTENSÃO da ponte,
#: não um método do daemon: o WebView não abre `FileChooserDialog` e a página
#: não alcança o disco — quem o abre é o piloto, que é GTK, e por isso ele não
#: entra em `METODOS`.
PONTE: set[str] = {"chamar", "machine_declare", "escolher_arquivo"}
METODOS: set[str] = {"machine.declare"}


PAGINA = "07-lancadores.html"
#: SUBIU DE 6 PARA 7 em 02/09/2026, com o "Voltar a perguntar" (decisão dela);
#: de 7 PARA 8 em 03/09/2026, com o "Abrir o lançador" (decisão 17 dela); e de
#: 8 PARA 10 no mesmo dia, com as duas faltas de paridade que a medição das dez
#: abas nomeou — o "Não perguntar para este jogo" (a metade de ida do par, que
#: só a GTK sabia escrever) e o "Posso fechar a Steam por uns 20 segundos?" (o
#: caminho para `with_steam_closed`, que a interface nova não tinha); e de
#: 10 PARA 11 em 04/09/2026, com o "Copiar a linha" (decisão `07[01]` do PO) —
#: o único botão de copiar de toda a interface nova; e de 11 PARA 14 em
#: 06/09/2026, com os TRÊS do Steam Input (decisão dela,
#: `D-0609-STEAM-DIVIDIDO`): "Desligar o Steam Input", "Este jogo não funciona"
#: e "Deixar tudo pronto".
#: e de 14 PARA 16 em 08/09/2026, com o registro do lançador que o Hefesto não
#: conhece (pedido dela): o de LOCALIZAR (:data:`desenho.ADICIONAR`) e o de
#: TIRAR (:data:`desenho.REMOVER`).
#: e de 16 PARA 17 em 09/09/2026, com a CURA POR ESTRADA — o ambiente do
#: Hefesto entrando nos lançadores que o atalho de inicialização da Steam não
#: alcança.
#:
#: **E CONTINUOU 17 EM 10/09/2026, com DOIS movimentos que se anulam na conta e
#: não se anulam na tela** (LANCADOR-LOCALIZAR-01): o `consertar-lancador` SAIU
#: por palavra dela, e o :data:`desenho.PROCURAR_O_ARQUIVO` — o seletor do
#: sistema na tela de registro — ENTROU. O piso só sobe, e aqui ele nem subiu
#: nem caiu: quem conta é a régua, e ela conta gestos com dono, não atos.
#:
#: e de 17 PARA 21 em 21/09/2026, com a LISTA DE EXCLUSÃO (desenho aprovado
#: por ela, OS-LANCADORES-IGUAIS-E-A-LISTA-DE-EXCLUSAO-01): ENTRARAM os cinco
#: da fileira comum e da pop-up — :data:`desenho.EXCLUIR`,
#: :data:`desenho.CRIAR_PERFIL`, :data:`desenho.CONFIRMAR_EXCLUSAO`,
#: :data:`desenho.CONFIRMAR_PERFIL` e :data:`desenho.TIRAR_DA_EXCLUSAO` — e
#: SAIU o «Este jogo não funciona», que o «Adicionar à lista de exclusão»
#: substituiu no cartão da Steam.
#:
#: **E DESCEU DE 21 PARA 14 na mesma noite, e a descida é a palavra dela**:
#: *"a ideia é termos os mesmos botões pra todos os lançadores. sempre."* Saíram
#: os sete botões que só o cartão da Steam tinha — «Consertar», «Ver o que
#: impede», «Posso fechar a Steam por uns 20 segundos?», «Não perguntar para
#: este jogo», «Copiar a linha», «Desligar o Steam Input» e «Deixar tudo
#: pronto». O piso só sobe para gesto que CAIU SEM QUERER; estes saíram de
#: propósito, e o que eles faziam à mão o produto faz sozinho (o vigia repõe o
#: atalho, o guarda desliga o Steam Input — `hefesto-steam-input-guard`).
PISO_DA_ABA = 14

#: SEM `PROVAS`, e a razão é o contrato da régua dos botões: ela injeta uma
#: `PonteDeMentira` e cobra QUAL função da ponte o gesto chamou. Um gesto que
#: não usa a ponte chamaria zero e a régua reprovaria por estar CERTO — o
#: defeito que esta casa nomeou onze vezes em 26/08 (*a régua reprovando a
#: melhora em vez do defeito*). Quem prova estes seis é
#: `tests/unit/test_a_aba_lancadores_diz_a_verdade.py`, com o `HOME` desviado e
#: o efeito cobrado NO ARQUIVO — que é a prova mais forte, não a mais fraca.
PROVAS: list[dict[str, Any]] = []

#: TODOS, e não por preguiça: o `state_full` do daemon não tem UMA chave sobre
#: a Steam, sobre o `localconfig.vdf`, sobre a lista de recusados ou sobre a de
#: dispensados. O efeito destes botões é o DISCO e a TELA — e os dois têm
#: régua. O `abrir-lancador` entrou em 03/09/2026 pelo motivo mais forte de
#: todos: o efeito dele é uma JANELA da Steam, que o daemon não vê nem por
#: acidente.
#:
#: OS SETE BOTÕES DA STEAM SAÍRAM DESTA LISTA em 21/09/2026 junto com os gestos
#: (ver :data:`PISO_DA_ABA`).
SEM_ECO = ("procurar", "detectar",
           "tirar-daqui", "voltar-a-usar", "voltar-a-perguntar",
           "abrir-lancador",
           # OS DOIS DO REGISTRO (08/09/2026) entram pelo mesmo motivo dos
           # outros catorze, e por um a mais: o efeito deles é o
           # `maquina.json`, e o `state_full` não tem UMA chave sobre a
           # declaração dela — nem sobre lançador nenhum.
           desenho.ADICIONAR, desenho.REMOVER,
           # O SELETOR DO SISTEMA (10/09/2026) entra pelo mesmo motivo dos dois
           # acima: quando ela escolhe um arquivo, o que muda é o `maquina.json`
           # — e o `state_full` não tem UMA chave sobre lançador. Quando ela
           # CANCELA, o gesto não muda nada em lugar nenhum, e cobrar eco de um
           # cancelamento seria reprovar o botão por estar certo.
           desenho.PROCURAR_O_ARQUIVO)

# A CURA POR ESTRADA saiu desta lista em 10/09/2026 junto com o gesto — ver o
# bloco «O «Consertar» DOS OUTROS LANÇADORES SAIU», logo abaixo de `calados`.
