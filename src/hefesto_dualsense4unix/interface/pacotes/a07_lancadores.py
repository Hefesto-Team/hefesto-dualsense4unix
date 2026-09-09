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
    integrations/sentinela_do_wrapper.reparar_ou_adiar   o reparo, com os portões
    integrations/sentinela_do_wrapper.frase_do_aviso     a frase que vai à TELA
    integrations/steam_launch_options.rotulo_do_jogo     o nome, do `appmanifest`
    integrations/steam_launch_options.marcar_jogo_sem_wrapper    o "tirar daqui"
    integrations/steam_launch_options.desmarcar_jogo_sem_wrapper o "voltar a usar"
    integrations/steam_launch_options.steam_game_running_appid   o jogo em foco
    integrations/prontuario_dos_jogos.levantar_censo     os cinco impedimentos
    integrations/prontuario_dos_jogos.jogos_instalados   os `appmanifest` do disco
    integrations/prontuario_dos_jogos.pontes_confirmadas quem já sabe por onde entrar
    integrations/jogos_locais.pastas_de_atalhos          onde moram os `.desktop`
    integrations/steam_launch_options.with_steam_closed  fechar · aplicar · reabrir
    integrations/steam_launch_options.WRAPPER_LAUNCH     a linha que se copia
    app/actions/launch_wrapper_dialog.load_dismissed_appids  quem ela dispensou
    app/actions/launch_wrapper_dialog.add_dismissed_appid    o "não perguntar"
    app/actions/launch_wrapper_dialog.remove_dismissed_appid o "voltar a perguntar"
    app/actions/launch_wrapper_dialog.extract_steam_appid    o jogo em foco
    app/actions/home_actions.wrapper_banner_text         o aviso do jogo aberto
    app/actions/daemon_actions.format_steam_janela_recusa a recusa de fechar
    app/actions/carona_do_wrapper.passada                o tique da vigia da Steam
    app/actions/carona_do_wrapper.INTERVALO_DA_VIGIA_S   de quanto em quanto
    app/actions/carona_do_wrapper.ligada                 o desligador da suíte
    daemon/launch_env.launch_session_appid               1º degrau da escada
    daemon/launch_env.read_last_run_marker               3º degrau da escada

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
import re
import threading
import time
from typing import Any

from hefesto_dualsense4unix.interface import desenho_dos_lancadores as desenho

from . import Contexto, perfil, registrar

#: De quanto em quanto tempo a vigia repergunta ao disco. 20 s é o compromisso:
#: a linha de inicialização só muda quando a Steam a regrava (ao sair) ou quando
#: ela clica em Consertar — e o gesto invalida o cache na hora, então o TTL não
#: precisa ser curto para a tela parecer viva.
TTL_S = 20.0

#: Quanto tempo o "posso fechar a Steam?" fica ARMADO depois do primeiro
#: clique. Ver :func:`fechar_a_steam_e_repor` — é o consentimento que
#: `with_steam_closed` EXIGE de quem a chama, na forma que uma página tem.
SEGUNDOS_PARA_CONFIRMAR = 20.0

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


@dataclasses.dataclass(frozen=True)
class _Portoes:
    """Os DOIS portões do reparo, lidos na MESMA passada do censo.

    POR QUE ELES NÃO ENTRAM NA `Leitura`, e a razão é de território: a
    `desenho_dos_lancadores.Leitura` é do DESENHO — ela é fria de propósito,
    para o gerador rodar sem o produto, e o desenho não é arquivo desta frente.
    Aqui eles são de outra natureza: não vão para a tela como texto, decidem
    QUAL BOTÃO o cartão da Steam oferece.

    POR QUE NÃO SE MEDE NA HORA DE DESENHAR O BOTÃO: `steam_running()` e
    `steam_game_running()` varrem `/proc`, e o orçamento do tique é de 100 ms
    para a janela inteira — é a mesma razão que pôs o resto do disco na
    :class:`_Vigia`. O `censo_do_wrapper` já os mede a cada leitura, então o
    dado sai de graça: o que faltava era guardá-lo.

    QUEM ESCREVE É `_ler_do_disco`, e só ele — na thread da vigia. Quem lê é a
    pintura, na thread da janela. Dois bools trocados entre threads não pedem
    trava: a escrita é de um objeto inteiro, e ler o de antes por meio tique
    mostra um botão a mais ou a menos por 500 ms, nunca um estado inventado.
    """

    jogo_aberto: bool = False
    steam_aberta: bool = False


#: O que a última leitura viu dos dois portões. Ver :class:`_Portoes`.
PORTOES = _Portoes()


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

    O `onde` É O CAMINHO INTEIRO, e isso é o que a frase promete. A docstring
    de :data:`desenho.DIZ_ACHEI` diz, com todas as letras, que dizer ONDE *"é o
    que deixa ela conferir a resposta sem acreditar em mim"* — e o código tinha
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


def _o_que_a_steam_poe_no_meio() -> tuple[str, bool | None]:
    """`(a frase do Steam Input, está ligado?)` — os dois PERGUNTADOS ao dono.

    **NENHUMA PALAVRA DAQUI É MINHA.** A frase inteira sai de
    `emulation_actions.markup_status_steam_input`, que é quem escreve a mesma
    linha na janela velha — ela já nomeia o JOGO, já diz o que o Hefesto vai
    fazer e já conta a lista de exceções. Redigi-la aqui seria a segunda
    redação de um texto que tem dono, e as duas envelheceriam separadas: a
    docstring do dono guarda a decisão `D-33` dela (*a palavra "conflito" saiu
    porque não é conflito nenhum*), e uma cópia perderia isso calada.

    O QUE ESTA FUNÇÃO FAZ COM ELA É TRADUZIR DE MARCAÇÃO, e só: o dono devolve
    markup do **Pango** (`<span foreground="#…">`), que um navegador não
    entende — um `foreground=` não pinta nada no WebKit, e deixá-lo passar
    seria pôr atributo morto na tela dela. As tarjas saem, o texto volta a ser
    texto, e quem PINTA é a folha de estilo da própria aba: `.lanc-diz b` já é
    laranja (`aba07.CSS`), que é a cor que o dono escolheu para o estado ligado.

    O `<b>` SÓ NO ESTADO LIGADO E SÓ NA PRIMEIRA TARJA, que é exatamente o que
    o dono pinta de laranja — a segunda tarja dele (a contagem da lista de
    exceções) é cinza, e engordá-la junto seria dar peso de alarme a uma
    linha que só informa. "Desligado — tudo certo" e "Steam não encontrada" saem
    em texto corrido, que é o peso certo para uma notícia que não pede ação.

    E O TOM NÃO SE LÊ PELO HEXADECIMAL, de propósito: `#ffb86c` está escrito
    DENTRO do dono, sem nome, e digitá-lo aqui seria uma régua de cor —
    verde no dia em que ele mudasse de tom, e a ênfase iria para a tarja errada
    calada. O que se sabe sem adivinhar é `ligado`, e a primeira tarja é a que
    fala do estado. É a mesma conta, sem a segunda cópia.

    AS TRÊS LEITURAS SÃO DO MOTOR, e são as MESMAS que a aba Emulação usa —
    `daemon_actions.medir_jogos_com_steam_input` já chama a do meio por este
    mesmo caminho (`EmulationActionsMixin` como estático), o que prova que
    chamar o mixin sem instância é o idioma desta casa e não um atalho meu.

    NUNCA LEVANTA: quem chama é a :class:`_Vigia`, e um `localconfig.vdf`
    ilegível não pode apagar a resposta sobre o resto da aba. Sem medição a
    frase é `""` — e `""` é a tela CALANDO, não a tela dizendo "desligado".
    """
    import re as _re
    from html import unescape

    from hefesto_dualsense4unix.app.actions.emulation_actions import (
        EmulationActionsMixin,
        markup_status_steam_input,
    )
    from hefesto_dualsense4unix.integrations.steam_launch_options import (
        rotulo_do_jogo,
    )

    try:
        ligado = EmulationActionsMixin._steam_input_is_on()
        jogos = ([rotulo_do_jogo(a)
                  for a in EmulationActionsMixin._steam_input_appids_ligados()]
                 if ligado else [])
        excecoes, efetiva = EmulationActionsMixin._steam_input_excecao_status()
        bruto = markup_status_steam_input(ligado, jogos, excecoes, efetiva)
    except Exception:
        return "", None
    # O `unescape` DESFAZ O ESCAPE DO DONO (ele chama `html.escape` no ramo
    # ligado) para o `_texto` desta aba refazê-lo do jeito que o DOM devolve —
    # com a aspa CRUA. Escapar duas vezes poria `&amp;lt;` na tela; não
    # desescapar poria `&amp;` num nome de jogo que tem `&`.
    tarjas = _re.split(r"</?span[^>]*>", bruto)
    partes = [_texto(unescape(t)) for t in tarjas if t]
    if not partes:
        return "", ligado
    if ligado:
        partes[0] = f"<b>{partes[0]}</b>"
    return "".join(partes), ligado


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

    global PORTOES

    # UMA LEITURA DO `maquina.json` POR PASSADA, e ela serve às DUAS pontas: a
    # busca em disco e a lista de cartões. Ler duas vezes daria a chance de as
    # duas discordarem — um cartão desenhado para um lançador que a busca não
    # percorreu nasceria eternamente «NÃO LOCALIZADO».
    declarados = _declarados()
    onde_estao = _onde_estao_os_lancadores(declarados)

    try:
        censo = sw.censo_do_wrapper(anotar=False)
    except Exception as erro:  # o disco dela não pode derrubar a aba
        # OS PORTÕES VOLTAM AO PADRÃO, e não ficam com o valor de antes: sem
        # censo não há resposta sobre a Steam, e um `steam_aberta=True` velho
        # acenderia o botão que fecha a Steam dela com base numa leitura que
        # falhou. O padrão não oferece o botão, que é a recusa honesta.
        PORTOES = _Portoes()
        return desenho.Leitura(erros=(str(erro),), onde_estao=onde_estao,
                               declarados=declarados)

    # O `getattr` É TOLERÂNCIA A DUBLÊ, e não a um motor que mudou de nome: as
    # réguas desta casa montam censos de mentira com os campos que cada uma
    # precisa, e um censo sem os dois portões é um censo que não respondeu —
    # o padrão `False` não oferece o botão que fecha a Steam, que é a recusa
    # honesta. Quem impede que um RENOME morra em silêncio aqui é
    # `test_o_censo_de_verdade_responde_pelos_dois_portoes`, contra a `Censo`
    # de verdade: sem ele o botão sumiria para sempre sem nada acusar.
    PORTOES = _Portoes(jogo_aberto=bool(getattr(censo, "jogo_aberto", False)),
                       steam_aberta=bool(getattr(censo, "steam_aberta", False)))

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

    # O STEAM INPUT ENTRA NA MESMA PASSADA, e por isso ele custa o que custa:
    # ele lê os mesmos `localconfig.vdf` que o censo acabou de abrir, na THREAD
    # DA VIGIA. Medido nesta bancada em 06/09/2026: a leitura completa foi de
    # 64,6 ms para 68,7 ms — 4,1 ms para responder uma pergunta que a aba não
    # sabia responder. No tique, que é de 100 ms, isto não entra nunca.
    frase_do_steam_input, ligado = _o_que_a_steam_poe_no_meio()

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
        frase=sw.frase_do_aviso(censo),
        # A LINHA É A CONSTANTE DO MOTOR, e não uma segunda redação: é a MESMA
        # que o botão "Copiar opções para os jogos" da janela velha copia
        # (`daemon_actions.compose_launch` devolve `WRAPPER_LAUNCH` e nada mais)
        # e a MESMA que o `apply_wrapper_to_all_games` grava no vdf. Digitá-la
        # aqui seria a terceira cópia de 143 caracteres que já têm dono — e a
        # cópia envelheceria calada no dia em que o wrapper mudasse de caminho.
        linha=slo.WRAPPER_LAUNCH,
        steam_input=frase_do_steam_input,
        steam_input_ligado=ligado,
        erros=tuple(censo.erros),
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

    O TEXTO É O DELA, VERBATIM (`home_actions.WRAPPER_MISSING_TEXT`), e sai da
    própria função — nada é redigitado aqui.

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
    return f"<b>{_texto(texto)}</b><br>", appid


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


#: O rótulo do botão que dispensa o aviso. É o do diálogo da GTK, palavra por
#: palavra (`launch_wrapper_dialog.py:435`) — a mesma lista, o mesmo gesto, o
#: mesmo texto.
DISPENSAR = "Não perguntar para este jogo"

#: O nome do gesto que fecha a Steam, e o `data-v` que ARMA a segunda metade.
#: Ver :func:`fechar_a_steam_e_repor`.
FECHAR = "consertar-fechando-a-steam"

#: OS DOIS RÓTULOS SAEM DO DIÁLOGO DA GTK, e não de mim: o título do
#: consentimento (`daemon_actions._pedir_para_fechar_a_steam`, o `titulo`
#: padrão) vira o primeiro botão, e o `rotulo_ok` dele vira o segundo. O
#: diálogo que a janela velha mostra é, aqui, um botão que muda de rótulo.
PERGUNTA_DA_STEAM = "Posso fechar a Steam por uns 20 segundos?"
CONFIRMA_A_STEAM = "Fechar e continuar"

#: QUAL GESTO ESTÁ ARMADO E ATÉ QUANDO (`time.monotonic`). Vazio = nenhum.
#:
#: ERA UM FLOAT SÓ, e virou dicionário em 06/09/2026 com a `STEAM-INPUT-01`:
#: passaram a existir TRÊS botões que fecham a Steam nesta aba, e um relógio
#: único faria o consentimento de um valer para o outro — clicar em "Posso
#: fechar a Steam?" e confirmar em "Deixar tudo pronto" rodaria o segundo com o
#: sim dado ao primeiro. **O consentimento é do ATO, nunca da aba.**
#:
#: UM POR VEZ, e é de propósito: armar um DESARMA o outro. Dois consentimentos
#: pendurados ao mesmo tempo é tela guardando duas promessas dela sobre a mesma
#: Steam, e a segunda confirmação não teria como dizer a qual respondia.
_ARMADO: dict[str, float] = {}


def _armado_agora() -> str:
    """O gesto armado NESTE instante, ou `""` — e ele desarma sozinho no tempo.

    O relógio é LIDO aqui, e não guardado num `bool`: um `bool` armado por um
    clique que ninguém confirmou continuaria armado depois de a janela passar,
    e o segundo clique de dez minutos depois valeria como consentimento. É a
    mesma conta que `a09_sistema._armado_agora` faz, com o mesmo dono do
    número (:data:`SEGUNDOS_PARA_CONFIRMAR`).
    """
    for nome, ate in list(_ARMADO.items()):
        if time.monotonic() >= ate:
            del _ARMADO[nome]
    return next(iter(_ARMADO), "")


def _armar(nome: str) -> None:
    """Arma UM gesto e desarma o que estivesse — ver :data:`_ARMADO`."""
    _ARMADO.clear()
    _ARMADO[nome] = time.monotonic() + SEGUNDOS_PARA_CONFIRMAR


def _desarmar(nome: str = "") -> None:
    """Desarma um gesto (ou todos, sem nome)."""
    if nome:
        _ARMADO.pop(nome, None)
    else:
        _ARMADO.clear()


def _confirmo(nome: str) -> str:
    """O `data-v` que **só existe no botão já armado** daquele gesto.

    ELE É POR GESTO, e é o primeiro dos dois guardas: um `"steam:confirmo"`
    único faria o botão armado de um ato confirmar o outro, que é justamente o
    que :data:`_ARMADO` deixou de permitir do lado do relógio.
    """
    return f"{nome}:confirmo"


#: O `data-v` do "Posso fechar a Steam?" já armado. ERA `"steam:confirmo"`
#: cravado, e virou derivado em 06/09/2026 pela razão de :func:`_confirmo`.
CONFIRMO = _confirmo(FECHAR)


def _este_clique_confirma(nome: str, o: dict[str, Any]) -> bool:
    """Este clique é a CONFIRMAÇÃO? Quando não é, ARMA o botão e devolve `False`.

    OS DOIS GUARDAS SÃO INDEPENDENTES DE PROPÓSITO, e a razão está escrita em
    :func:`fechar_a_steam_e_repor`, que os inventou:

    1. o clique tem de trazer `_confirmo(nome)` no `data-v` — um valor que
       **só existe no cartão já armado**, escrito por :func:`_botao_armavel`;
    2. e tem de chegar dentro de :data:`SEGUNDOS_PARA_CONFIRMAR`.

    O PRIMEIRO É O QUE SEGURA A RÉGUA AUTOMÁTICA: a `--prova-gesto` clica o que
    o DOM tinha, e o DOM tinha a pergunta. Um guarda só bastaria hoje; dois é o
    que sobrevive a uma régua que releia o DOM entre cliques.

    FORA DO PRAZO ELE LEVANTA, em vez de agir ou de rearmar calado: a frase vai
    para a tela pelo caminho do `RuntimeError`, e o tique seguinte repõe a
    pergunta. Rearmar calado deixaria a tela dizendo "Fechar e continuar" sobre
    um consentimento que já tinha vencido.

    EXTRAÍDO EM 06/09/2026, e não é arrumação: o `fechar_a_steam_e_repor`
    guardava esta conta dentro de si, e os dois botões novos do Steam Input
    precisam da MESMA. Três cópias do consentimento que fecha a Steam dela é
    exatamente onde uma delas ficaria mais frouxa que as outras.
    """
    if str(o.get("v") or "").strip() != _confirmo(nome):
        _armar(nome)
        return False
    armado = _armado_agora() == nome
    _desarmar(nome)
    if not armado:
        raise RuntimeError(
            f"Passaram-se mais de {int(SEGUNDOS_PARA_CONFIRMAR)} segundos desde "
            "a pergunta — não fechei nada. Clique de novo para começar.")
    return True


# ---------------------------------------------------------------------------
# A VIGIA DA STEAM — a promessa que o cartão FAZIA e ninguém cumpria
#
# O QUE A TELA JÁ DIZIA, medido em 03/09/2026 nesta máquina: com a Steam aberta
# o `Consertar` recusa com a frase da sentinela, e ela termina em *"Feche a
# Steam e eu reponho"* (`sentinela_do_wrapper.frase_do_aviso`). Era uma promessa
# sem ninguém para cumpri-la: `reparar_ou_adiar` devolve `REPARO_ADIADO_STEAM`,
# o gesto vira tarja de 30 s, e **nada** reperguntava depois. Para o reparo
# acontecer ela tinha de fechar a Steam, LEMBRAR da tarja, voltar à aba 07 e
# clicar de novo — que é exatamente o que o pedido dela recusa: *"ela não pode
# precisar lembrar de nada"* (`carona_do_wrapper`, "A STEAM ABERTA").
#
# A JANELA VELHA CUMPRE, e desde 16/08: quando o reparo é adiado ela arma um
# `GLib.timeout_add_seconds(INTERVALO_DA_VIGIA_S)` que só pergunta *"a Steam já
# fechou?"* — sem reler o vdf — e o reparo ACONTECE quando ela sai da Steam.
#
# NADA AQUI É MOTOR NOVO. O tique é `carona_do_wrapper.passada(completa=False)`,
# a mesma função que o tique do GTK chama, com o mesmo desiste-barato e a mesma
# frase de volta; o relógio é o `INTERVALO_DA_VIGIA_S` DELE, lido a cada volta
# em vez de copiado — um 45 digitado aqui envelheceria calado no dia em que o
# dono mudasse o compromisso. O que muda é só o temporizador: onde a GTK tem o
# laço do GLib, uma página tem uma thread.
#
# O DESLIGADOR É O DO DONO, e ele não é opcional: `carona_do_wrapper.ligada()`
# lê o `HEFESTO_CARONA_WRAPPER`, que o `conftest.py` desliga em TODO teste
# justamente porque este caminho ESCREVE no `localconfig.vdf` — uma suíte
# rodando na máquina dela reescreveria a biblioteca dela em segundo plano.
# Quem quer exercitar a vigia religa por escrito.
# ---------------------------------------------------------------------------
class _VigiaDaSteam:
    """Repergunta "a Steam já fechou?" até o reparo caber — e então repõe.

    ELA SÓ NASCE DE UM CLIQUE DELA. Armar de dentro da pintura seria a mesma
    coisa que a :class:`_Vigia` de leitura existe para impedir, com o agravante
    de ESCREVER: quem arma é o gesto que ela acionou e que foi adiado, e a
    frase que a tela mostrou nesse instante é a promessa que esta classe
    cumpre.

    UMA POR VEZ, e :meth:`armada` pergunta à thread (`is_alive`) em vez de
    guardar um `bool` que uma exceção deixaria mentindo para sempre.

    NÃO GUARDA NADA EM DISCO, e a decisão é da sentinela, palavra por palavra:
    *"estado guardado sobre um vdf que muda sozinho envelheceria errado"*. Se a
    janela fechar antes, nada se perde — o censo é uma leitura de arquivo, e o
    próximo `Consertar` (ou o `install.sh`, ou o `doctor.sh`) refaz a conta do
    zero.

    O ERRO MANTÉM A VIGIA ARMADA, e é paridade deliberada com a janela velha:
    `passada` devolve ``adiado=True`` também no `REPARO_ERRO`, e o
    `_carona_reagir` do GTK arma sobre esse mesmo campo. Um vdf trancado no meio
    da escrita é transitório; desarmar no primeiro tropeço entregaria de volta
    o silêncio que esta classe existe para acabar.
    """

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._parar = threading.Event()
        self._trava = threading.Lock()
        self._noticia = ""
        self._quando = 0.0

    # -- o estado -----------------------------------------------------------
    def armada(self) -> bool:
        """Há vigia viva agora?"""
        thread = self._thread
        return thread is not None and thread.is_alive()

    def intervalo(self) -> float:
        """O relógio, PERGUNTADO ao dono a cada volta. Nunca digitado."""
        from hefesto_dualsense4unix.app.actions import carona_do_wrapper as cdw

        return float(cdw.INTERVALO_DA_VIGIA_S)

    # -- armar e desarmar ---------------------------------------------------
    def armar(self) -> bool:
        """Passa a reperguntar pela Steam. Devolve se ARMOU nesta chamada.

        O DESLIGADOR ANTES DE TUDO, e ele é do dono: `carona_do_wrapper.ligada()`
        lê o `HEFESTO_CARONA_WRAPPER`, que o `conftest.py` desliga em TODO teste
        porque este caminho ESCREVE no `localconfig.vdf`.

        NUNCA LEVANTA. Quem chama é o ramo de RECUSA de um gesto, e a recusa
        dela é a frase da sentinela — uma exceção daqui a trocaria por um
        traceback, que é a tela deixando de dizer o que o produto sabe.
        """
        try:
            from hefesto_dualsense4unix.app.actions import carona_do_wrapper as cdw

            if not cdw.ligada():
                return False
        except Exception:  # pragma: no cover - a carona sumiu do disco
            return False
        with self._trava:
            if self.armada():
                return False
            self._parar.clear()
            self._thread = threading.Thread(
                target=self._corpo, name="hefesto-vigia-da-steam", daemon=True
            )
            self._thread.start()
        return True

    def desarmar(self) -> None:
        """Pede à vigia que pare. Ela para no fim da espera em curso."""
        self._parar.set()

    # -- o tique ------------------------------------------------------------
    def tique(self) -> bool:
        """UMA volta. ``True`` = ainda há trabalho pendente, continue.

        O `completa=False` é o que torna o tique barato: com a Steam viva ele
        nem abre o `localconfig.vdf` — pergunta ao `/proc` e volta a dormir. A
        leitura completa (e a escrita) só acontece quando há chance real de
        repor.
        """
        from hefesto_dualsense4unix.app.actions import carona_do_wrapper as cdw

        try:
            resultado = cdw.passada(completa=False)
        except Exception:
            # Uma passada que levanta não pode desarmar a vigia em silêncio:
            # seria a promessa morrendo sem ninguém saber.
            return True
        if resultado.adiado:
            return True
        # A leitura da aba ficou velha no instante da escrita. `esquecer` é o
        # que faz o cartão se repintar sozinho no próximo tique da janela.
        VIGIA.esquecer()
        self._anotar(resultado.frase)
        return False

    def _corpo(self) -> None:
        while not self._parar.wait(self.intervalo()):
            if not self.tique():
                return

    # -- a notícia ----------------------------------------------------------
    def _anotar(self, frase: str) -> None:
        if not frase:
            return
        self._noticia = frase
        self._quando = time.monotonic()

    def noticia(self) -> str:
        """O que a vigia fez, enquanto a notícia vale. Vazio = nada a dizer.

        POR QUE ELA EXISTE: sem uma palavra, o reparo da vigia seria um cartão
        que muda sozinho enquanto ela olha outra coisa — e ela nunca saberia
        que o Hefesto cumpriu. A janela velha diz isso num toast do rodapé
        (`_carona_toast`); aqui a mesma frase entra no corpo do cartão da
        Steam, que é o lugar onde a recusa também aparece.

        A FRASE É A DO DONO, montada por `carona_do_wrapper.passada` — a mesma
        que a GTK mostra, com os jogos nomeados. Nada é redigitado aqui.

        E O RELÓGIO TAMBÉM É DELE: a notícia dura UMA volta da vigia
        (:meth:`intervalo`). Um número novo aqui seria a terceira duração de
        tela desta casa sem dono; a volta da vigia é o único relógio que este
        episódio já tem.

        NUNCA LEVANTA: quem chama é a PINTURA, duas vezes por segundo. Uma
        exceção aqui derrubaria a aba inteira por causa de uma frase.
        """
        if not self._noticia:
            return ""
        try:
            vale = self.intervalo()
        except Exception:  # pragma: no cover - a carona sumiu do disco
            self._noticia = ""
            return ""
        if time.monotonic() - self._quando >= vale:
            self._noticia = ""
            return ""
        return self._noticia


#: A vigia é do MÓDULO, pela mesma razão da :data:`VIGIA`: o pacote é recriado
#: a cada tique, e uma vigia dentro dele morreria meio segundo depois de armada.
VIGIA_DA_STEAM = _VigiaDaSteam()


def _botao_armavel(nome: str, pergunta: str) -> desenho.Acao:
    """O botão de DUAS CARAS: a pergunta, e a confirmação de quem já perguntou.

    UM DONO PINTA E CONFERE. A cara armada carrega `_confirmo(nome)` no `data-v`,
    e é o MESMO valor que o gesto exige no segundo clique — não há como a tela e
    o guarda discordarem. É a disciplina que `a09_sistema.CONFIRMA` já aplica
    pelo rótulo; aqui ela é pelo `data-v`, que é o vocabulário desta aba.

    O `verde` NA CARA ARMADA é o que diz, sem palavra nova, que o próximo clique
    AGE. Ver :func:`fechar_a_steam_e_repor`, que é quem escreveu esta forma.
    """
    if _armado_agora() == nome:
        return desenho.Acao(CONFIRMA_A_STEAM, "verde", nome, _confirmo(nome))
    return desenho.Acao(pergunta, "", nome, desenho.STEAM)


def acoes_do_steam_input(lida: desenho.Leitura | None) -> tuple[desenho.Acao, ...]:
    """Os TRÊS botões do Steam Input, e cada um só onde ele funciona.

    A DECISÃO É DELA, 06/09/2026 (`D-0609-STEAM-DIVIDIDO`): *"Steam Input e a
    lista de exceções ficam na aba 07"*. O que esta função acrescenta é a mesma
    coisa que :func:`com_o_que_o_daemon_diz` já acrescentava para o wrapper — o
    que só o produto VIVO sabe: se a Steam está aberta, se há jogo aberto, e o
    que a última leitura do disco viu.

    ============================  ==========================================
    botão                         quando ele aparece
    ============================  ==========================================
    "Desligar o Steam Input"      o produto MEDIU e ele está ligado
                                  (`steam_input_ligado is True`) e **não há
                                  jogo aberto** — com jogo aberto o produto não
                                  fecha a Steam por nada, e oferecer o botão
                                  seria oferecer uma recusa
    "Este jogo não funciona"      a leitura ALCANÇOU a biblioteca. É o único
                                  gesto por-jogo que a janela velha tem para o
                                  sintoma que ela mediu no aparelho, e ele é
                                  reversível: não fecha nada, não edita arquivo
                                  da Steam
    "Deixar tudo pronto"          **os DOIS têm trabalho** — falta atalho em
                                  algum jogo E o Steam Input está ligado. É a
                                  razão inteira de ele existir: os dois cabem
                                  numa janela de `with_steam_closed`, e pedir
                                  duas vezes é fazer a pessoa pagar duas vezes
                                  pelo mesmo fechamento da Steam. Com só um
                                  lado pendente, o botão daquele lado basta
    ============================  ==========================================

    NENHUM DELES APARECE SEM MEDIÇÃO. Uma `Leitura` sem `steam_input` — a
    primeira meia volta, e toda régua que monte uma à mão — sai daqui com tupla
    vazia, e o cartão fica exatamente como estava.
    """
    if lida is None or not lida.viu_a_biblioteca:
        return ()
    fora: list[desenho.Acao] = [
        desenho.Acao(desenho.JOGO_NAO_FUNCIONA_ROTULO, "",
                     desenho.JOGO_NAO_FUNCIONA, desenho.STEAM)
    ]
    if lida.steam_input_ligado is True and not PORTOES.jogo_aberto:
        fora.append(_botao_armavel(desenho.DESLIGAR_STEAM_INPUT,
                                   desenho.DESLIGAR_STEAM_INPUT_ROTULO))
        if lida.reparaveis:
            fora.append(_botao_armavel(desenho.TUDO_PRONTO,
                                       desenho.TUDO_PRONTO_ROTULO))
    return tuple(fora)


def com_o_que_o_daemon_diz(
    lancadores: list[desenho.Lancador],
    state: dict[str, Any] | None,
    lida: desenho.Leitura | None,
) -> list[desenho.Lancador]:
    """O cartão da Steam com o AVISO VIVO e os botões que o estado permite.

    QUATRO COISAS ENTRAM AQUI, e nenhuma delas é regra nova:

    0. **a notícia da vigia da Steam** — o que ela repôs sozinha depois de a
       Steam fechar, na frase do `carona_do_wrapper` (ver
       :meth:`_VigiaDaSteam.noticia`). Ela vem PRIMEIRO porque é a resposta ao
       clique dela: o aviso do jogo aberto é permanente, a notícia passa;
    1. **o aviso do jogo aberto sem o wrapper** — a decisão e o texto são de
       `home_actions.wrapper_banner_text` (ver :func:`aviso_do_jogo_aberto`);
    2. **"Não perguntar para este jogo"** — o botão que escreve na lista que a
       GTK já lia e que a interface nova só sabia DESFAZER. Até hoje o par
       estava pela metade aqui: `voltar-a-perguntar` existia desde 02/09 e
       nada nesta casa punha um appid na lista pela tela nova;
    3. **"Posso fechar a Steam por uns 20 segundos?"** — a parede que a GTK
       derrubou em HONESTIDADE-STEAM-01 e que o HTML tinha reerguido. Na mesa
       dela o caso comum é a Steam ABERTA, e nesse estado o `Consertar` recusa
       sempre; este botão é o caminho que a janela velha tem e esta não tinha.

    POR QUE AQUI E NÃO NO DESENHO: `dataclasses.replace` sobre o cartão que o
    desenho montou mantém UM dono para a forma do cartão. O desenho decide o
    que o cartão É; esta função acrescenta o que só o produto vivo sabe — e o
    dia em que `desenho_dos_lancadores` ganhar campo para isto, o que sai daqui
    é uma linha.

    O BOTÃO DE FECHAR A STEAM SÓ APARECE ONDE ELE FUNCIONA: há o que repor, a
    Steam está aberta e **nenhum jogo** está aberto. Com jogo aberto o produto
    não fecha a Steam por nada (`stop_steam` mataria o jogo e o progresso não
    salvo), então oferecer o botão ali seria oferecer uma recusa.
    """
    if not lancadores:
        return lancadores
    steam = lancadores[0]
    aviso, appid = aviso_do_jogo_aberto(state, lida)
    noticia = VIGIA_DA_STEAM.noticia()
    # DUAS VARIÁVEIS, e não uma: o botão "Não perguntar" pende do AVISO (e do
    # appid dele), nunca da notícia. Somar as duas numa só faria a notícia da
    # vigia acender um botão que não tem sobre o que agir.
    cabeca = (f"<b>{_texto(noticia)}</b><br>" if noticia else "") + aviso
    acoes = steam.acoes
    if aviso and appid:
        acoes = (*acoes, desenho.Acao(DISPENSAR, "", "nao-perguntar", appid))
    if (lida is not None and lida.reparaveis
            and PORTOES.steam_aberta and not PORTOES.jogo_aberto):
        acoes = (*acoes, _botao_armavel(FECHAR, PERGUNTA_DA_STEAM))
    # O `if extras` NÃO É ESTILO: sem ele a comparação de identidade lá embaixo
    # nunca mais casaria (desempacotar uma tupla cria outra), e o cartão passaria
    # a ser reconstruído em TODO tique — o segundo dono do samba, pela porta que
    # a `A-TELA-SAMBA-01` acabou de fechar nesta aba.
    extras = acoes_do_steam_input(lida)
    if extras:
        acoes = (*acoes, *extras)
    if cabeca == "" and acoes is steam.acoes:
        return lancadores
    fora = list(lancadores)
    fora[0] = dataclasses.replace(steam, diz=cabeca + steam.diz, acoes=acoes)
    return fora


# ---------------------------------------------------------------------------
# A FITA DESTA ABA — quem está na mesa AGORA, e só isso
#
# A LEI, e ela é dela (03/09/2026): *"se no topo tá mostrando controle white
# player 1, então cada aba vai usar os controles lá de cima. Não mistura com a
# info dos mockups."*
#
# O QUE ESTAVA NA TELA, medido nesta máquina com os dois controles dela na mesa:
# o cabeçalho dizia `2 controles: 1 USB · 1 BT` (certo, lido do aparelho) e a
# fita logo abaixo dizia `P1 · Cosmic Red · USB` e `P2 · Starlight Blue · BT` —
# os dois do DESENHO, e ela não tem nenhum dos dois.
#
# POR QUE A FITA CHEGOU AQUI, e por que ela quase toda foi embora — 06/09/2026
#
# ELA CHEGOU porque `hefesto_vivo._fita` desistia da fita INTEIRA quando UM
# controle estivesse sem cor (`any(not c.get("cor") for c in mesa)` → `""`), e o
# JS só troca o bloco `if(p.fita)`. Nesta máquina o `LeitorDeCor` não conhece o
# controle de rádio, então a fita NUNCA era repintada — e "deixar a fita como
# está" é deixar a fita do MOCKUP.
#
# ESSA GUARDA CAIU EM 03/09/2026, e o `_fita` passou a devolver a fita viva em
# TODA mesa que tenha alguém. **Ninguém veio desligar esta.** Resultado medido
# em 06/09/2026 pela `A-TELA-SAMBA-01`, com um controle no cabo e a mesa parada:
#
#     07-lancadores.html · 120 mutações em 40 tiques · 3,0 por tique
#     — dois donos escrevendo `.fita` no MESMO tique. O piloto troca o nó
#       inteiro (`f.outerHTML = desejado`) e três passos depois o `blocos` desta
#       aba o troca de volta. A aba 07 foi a ÚNICA das dez que não zerou.
#
# E QUEM GANHAVA ERA ESTA, porque o `blocos` corre por último. Prova sem
# ambiguidade, na foto de 06/09: a fita da aba 07 mostrava `Todos` com UM
# controle na mesa, e `monta.escolha_da_fita` **não emite `Todos` com um só**
# (`cabe_o_todos`: `> 1`). O chip que ela via era o desta função — sem
# `data-campo="fita-chip"`, sem a cor do plástico e sem o `title` que diz por
# que a cor não foi lida.
#
# A CURA É A FORMA QUE ESTA CASA JÁ ESCOLHEU PARA AS OUTRAS NOVE: **a fita tem
# UM dono, e é o piloto.** Esta aba só escreve quando o piloto NÃO escreve — a
# mesa vazia, onde `_fita` devolve `""` e deixar a fita "como está" seria deixar
# os dois chips do mockup na tela. Ver a condição em :func:`pacote`.
#
# POR QUE `blocos` E NÃO `data-campo`: o número de chips muda com a mesa, e não
# há endereço para um chip que ainda não existe — é a mesma razão pela qual a
# grade dos cartões viaja por aqui. E há uma segunda, que é de robustez: o
# `p.fita` troca `.fita` INTEIRA antes de a pintura visitar campo nenhum, então
# um `data-campo` dentro da fita pode simplesmente não existir mais no DOM na
# hora de escrever. O `blocos` corre DEPOIS e reconsulta o documento pela
# classe: ele acerta o alvo com ou sem a troca do bloco inteiro.
# ---------------------------------------------------------------------------
#: O bloco que esta aba reescreve no topo. É a CLASSE do esqueleto
#: (`interface/topo.html`), a mesma âncora que `monta.MARCA_DA_FITA` usa — o
#: texto do chip já mudou duas vezes nesta casa e a classe não.
SELETOR_DA_FITA = ".fita"

#: O texto que `mesa_viva.mesa_do_estado` põe em `nome` quando o leitor de cor
#: não conhece a peça. Ele é a AUSÊNCIA de leitura, não uma leitura — e a regra
#: dela é clara: *campo sem informação não mostra nada*.
SEM_LEITURA_DE_COR = "Não sei"


def _chip(controle: dict[str, Any]) -> str:
    """Um chip da fita, com o que a leitura TROUXE — e calado sobre o resto.

    O QUE ENTRA: o número do jogador e o transporte, sempre (os dois vêm do
    daemon, nunca faltam), e o nome do modelo **só quando o plástico foi lido**.
    Um controle sem cor lida sai `P2 • rádio`, e não `P2 • Não sei • rádio` nem
    — muito pior — o nome do controle do desenho.

    O QUE NÃO ENTRA, E É DECISÃO DESTA ABA: o `--plastico` e o `title` do chip.
    A fita daqui nasce ESMAECIDA (fora de `monta.ABAS_QUE_ESCOLHEM`, decisão dela de 28/08:
    nada nesta aba ajusta por controle), e `topo.html:207` apaga a borda de
    plástico justamente aí — *"a borda de 2px na cor do plástico é a marca da
    peça VIVA — some com a fita"*. Escrever uma cor que a folha de estilo
    descarta é um valor sem efeito na tela; e o `title` do desenho dizia *"a
    borda é a cor do plástico"*, uma frase que nesta aba é falsa. Quem explica a
    fita apagada aqui é o `title` da `<div class="fita inerte">`, que o
    `blocos` não toca.

    A PALAVRA DO TRANSPORTE É DA FUNÇÃO DONA — ONDA4-S10, 06/09/2026, decisão
    dela (D-05). O chip lia a `via` da mesa, que é a **sigla de máquina**
    (`USB`/`BT`); quem joga tem um cabo e tem um controle sem fio, e é isso que
    o chip passa a dizer. O import é TARDIO porque `pacotes/__init__.py:889`
    declara por escrito que GTK no topo deste módulo é o que se evita aqui.
    """
    from hefesto_dualsense4unix.app.actions.home_actions import palavra_do_transporte

    nome = str(controle.get("nome") or "")
    lido = bool(controle.get("cor")) and nome and nome != SEM_LEITURA_DE_COR
    partes = [f"P{controle.get('jogador') or '?'}"]
    if lido:
        partes.append(_texto(nome))
    partes.append(_texto(palavra_do_transporte(controle.get("transporte"))))
    # `<label>` E NÃO `<span>` — 05/09/2026. As outras nove abas emitem
    # `LABEL` nos chips da fita (medido no DOM vivo), e a 07 era o único desvio
    # de forma que sobrou. Ela é aba de LEITURA e não perde clique nenhum por
    # isso; o que se perde é a forma ser a mesma nas dez, que é o que faz uma
    # régua de fita valer para todas.
    return ('<label class="chip plastico">'
            + ' <span class="pt">•</span> '.join(partes)
            + "</label>")


def _texto(x: object) -> str:
    """Escapa para posição de TEXTO, com a aspa CRUA — como o desenho faz.

    A razão é a do `desenho_dos_lancadores._e`, e ela é de laço infinito: o
    piloto só reescreve quando `innerHTML !== valor`, e o lado esquerdo é o que
    o DOM **devolve**. Uma grafia que o DOM normaliza de volta nunca casa, e a
    reescrita não para nunca.
    """
    return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def quantos_da_mesa(mesa: list[dict[str, Any]]) -> str:
    """O trecho do "?" que conta controle, com a mesa VIVA em vez do mockup.

    A MESMA FONTE DO CABEÇALHO, e é o ponto inteiro: `ctx.mesa` é a leitura que
    `pacotes.topo` usa para escrever `1 controle: 1 USB · 0 BT`. Enquanto o "?"
    lia `monta.CONECTADOS` — a mesa do DESENHO, derivada no import do gerador —
    os dois números viviam no mesmo quadro dizendo coisas diferentes.

    O `BT` SAI POR SUBTRAÇÃO, e não por uma segunda contagem: `n - usb` não pode
    somar diferente do total, e um transporte novo (ou um `transporte` vazio)
    cai no lado do rádio em vez de sumir da conta. Duas somas independentes é
    como a tela ganha um "2 controles: 1 USB · 0 BT" que não fecha.

    **QUEM CONTA LÊ O TRANSPORTE, NUNCA A PALAVRA** — ONDA4-S10, 06/09/2026, e
    é a mesma cura de `mesa_viva.texto_da_contagem`. Esta soma comparava
    `c["via"] == "USB"`; a `via` é o que a TELA escreve, e a partir de D-05 ela
    pode dizer `cabo`. Contar pela palavra é como a frase do "?" passaria a
    dizer *"os 2 (0 no cabo, 2 no rádio)"* com os dois no cabo — errado, calado,
    e sem uma régua vermelha. `transporte` é a chave crua que
    `mesa_viva.mesa_do_estado` publica ao lado da palavra.
    """
    n = len(mesa)
    usb = sum(1 for c in mesa if str(c.get("transporte") or "").strip().lower() == "usb")
    return desenho.quantos_html(n, usb, n - usb)


def fita_html(mesa: list[dict[str, Any]]) -> str:
    """O miolo da `.fita` desta aba: `Selecionar:`, `Todos` e a mesa VIVA.

    `Todos` nasce aceso porque é o alvo desta aba — ela não ajusta por controle,
    e por isso a fita é inerte. Uma mesa vazia devolve só o rótulo e o `Todos`:
    sem controle na mesa não há chip, que é o que a fita já fazia por decisão
    dela em 31/08 (*"ele só fica ativo se surgir controle naquela área"*).

    NÃO DEVOLVE VAZIO NUNCA, e isso é de propósito: `hefesto_vivo` troca o
    bloco por `innerHTML`, e um bloco vazio apagaria o rótulo `Selecionar:` da
    tela dela.
    """
    return ('<span>Selecionar:</span>'
            '<label class="chip on">Todos</label>'
            + "".join(_chip(c) for c in mesa))


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
    return {
        "mesa": valores,
        "blocos": {desenho.SELETOR_DA_GRADE: desenho.cartoes_html(lancadores)},
    }


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
    return _pintura(com_o_que_o_daemon_diz(desenho.cartoes(lida), state, lida))


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
    cabeçalho usa; daqui em diante a fita sai dela. Ver :func:`fita_html`.
    """
    carga = _resposta(VIGIA.agora(), ctx.state)
    valores = carga["mesa"]
    # O "?" TAMBÉM CONTAVA CONTROLE, e ninguém tinha olhado para ele: a cura de
    # 02/09 tirou o número dos CARTÕES e deixou o do texto de ajuda, que saía de
    # `monta.CONECTADOS` — a mesa do desenho, congelada no HTML. Ver
    # :func:`quantos_da_mesa`.
    valores[desenho.QUANTOS] = quantos_da_mesa(ctx.mesa)
    fora: dict[str, Any] = dict(valores)
    fora["blocos"] = dict(carga["blocos"])
    # A FITA SÓ SAI DAQUI QUANDO O PILOTO NÃO A ESCREVE — 06/09/2026. Com
    # alguém na mesa quem manda é `hefesto_vivo._fita`, que emite a fita
    # canônica das dez abas (`monta.fita`), com endereço, cor e dica. Escrever
    # por cima dela era o segundo dono que fazia esta aba sambar 120 vezes em 40
    # tiques — e a fita que ganhava era a MENOS informada das duas.
    #
    # COM A MESA VAZIA O PILOTO SE CALA (`_fita` devolve `""`), e "deixar a fita
    # como está" é deixar os dois chips do DESENHO na tela dela. É o único caso
    # em que esta aba ainda tem o que dizer, e `fita_html` diz o mínimo honesto:
    # o rótulo e o `Todos`, sem nomear controle nenhum.
    if not ctx.mesa:
        fora["blocos"][SELETOR_DA_FITA] = fita_html(ctx.mesa)
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


@gesto("07-lancadores.html", "consertar", grava="reparar_ou_adiar")
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

    E AGORA ALGUÉM CUMPRE A FRASE. A recusa arma a :data:`VIGIA_DA_STEAM`, que
    é a metade que faltava: até 03/09/2026 a tela prometia repor *"assim que a
    Steam fechar"* e nada reperguntava depois — ela tinha de fechar a Steam,
    lembrar da tarja de 30 s e voltar aqui para clicar de novo. Ver
    :class:`_VigiaDaSteam`.
    """
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw

    status, censo, _ = sw.reparar_ou_adiar()
    VIGIA.esquecer()
    if status in (sw.REPARO_ADIADO_JOGO, sw.REPARO_ADIADO_STEAM, sw.REPARO_ERRO):
        VIGIA_DA_STEAM.armar()
        raise RuntimeError(sw.frase_do_aviso(censo) or
                           "não consegui repor o atalho de inicialização")
    # Deu certo: não há o que vigiar, e uma vigia sobrevivente reabriria o vdf
    # de 45 em 45 s para nada.
    VIGIA_DA_STEAM.desarmar()
    return _resposta(VIGIA.ler(), ctx.state)


def _o_cartao(chave: str) -> desenho.SemCenso | None:
    """A `SemCenso` daquele cartão — inclusive um que ELA tenha declarado.

    LER DE `procurados()` E NÃO DE `SEM_FONTE` é o que faz o cartão declarado
    por ela também poder ser consertado: `SEM_FONTE` é a lista de fábrica, e
    quem acrescentou um lançador ao produto esperaria o mesmo botão nele.
    """
    lida = VIGIA.agora()
    for item in desenho.procurados(lida.declarados if lida is not None else ()):
        if item.chave == chave:
            return item
    return None


@gesto("07-lancadores.html", desenho.CONSERTAR_LANCADOR,
       grava="escrever_a_estrada")
def consertar_lancador(ctx: Contexto, o: dict[str, Any], p: Any
                       ) -> dict[str, Any]:
    """"Consertar" nos lançadores que não são a Steam — o ambiente por estrada.

    A §5.3 DA SPRINT, e é o irmão do :func:`consertar` da Steam com um alvo
    diferente: aquele repõe o **atalho de inicialização** no `localconfig.vdf`;
    este escreve o **ambiente** na configuração do lançador, porque
    `hefesto-launch` não alcança nenhum jogo sem `SteamAppId`.

    QUEM SABE ESCREVER É `cura_por_estrada`, e o gesto não decide nada: ele
    pergunta o plano, manda escrever e leva a frase para a tela. Duas estradas
    hoje — o `config.json` do Heroic e o arquivo de override do Flatpak dos
    demais —, e a escolha é do módulo, com a razão de cada uma escrita lá.

    **A RECUSA VAI PARA A TELA**, que é o contrato desta casa: `RuntimeError`
    vira a tarja laranja de 30 s com a frase do dono. Sem o ambiente publicado
    pelo serviço, a cura recusa dizendo o que ligar — **nunca inventa a conta**.
    Escrever aqui um `SDL_GAMECONTROLLER_IGNORE_DEVICES` deduzido seria uma
    segunda conta ao lado da do daemon, e a segunda envelhece calada.

    **O RECIBO VAI PELO CANAL DE RECADO, E NÃO PELO CORPO DO CARTÃO — medido
    na tela viva em 09/09/2026.** A primeira versão escrevia a frase no `diz`
    daquele cartão, como o `ver-o-que-impede` faz com o da Steam. **Fotografada
    1,6 s depois do clique, a frase já não estava lá:** o tique repinta o corpo
    do cartão a partir da leitura do disco, dez vezes por segundo, e o recibo
    vivia 100 ms. Quem tem prazo próprio é o `recado` — seis segundos, o
    `SEGUNDOS_DO_RECADO_DE_SUCESSO` do piloto —, e ele é um depósito DO PILOTO
    e não um valor da página. É a decisão dela de 04/09, a D-01.

    ELE DECLARA `grava=` PORQUE ESCREVE NA MÁQUINA DELA — o `config.json` do
    Heroic e o override do Flatpak são arquivos DELA, e a prova botão a botão
    (`--prova-gesto`) não pode clicá-lo sozinha. A lista é derivada daqui
    (`pacotes.perigosos()`), e não digitada num arquivo distante.
    """
    from hefesto_dualsense4unix.integrations import cura_por_estrada as cura

    qual = str(o.get("v") or "").strip()
    if not qual:
        raise ValueError(
            "consertar-lancador: o clique não disse qual lançador. Cada botão "
            "manda `data-v` com a chave do cartão — sem ela o gesto escreveria "
            "na configuração de um lançador escolhido por acaso.")
    item = _o_cartao(qual)
    if item is None:
        raise RuntimeError(
            "Não conheço este lançador. Procure de novo e tente outra vez.")
    frase = cura.escrever_a_estrada(
        cura.planejar(qual, item.atalhos, nome=item.nome))
    VIGIA.esquecer()
    return {**_resposta(VIGIA.ler(), ctx.state), "recado": frase}


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
    return _com_outra_frase(desenho._e(censo.frase()), ctx.state)


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
        raise RuntimeError(
            "Não achei jogo nenhum aberto agora. Abra o jogo de onde for, "
            "volte aqui e clique de novo.")
    lida = VIGIA.agora()
    tem = lida is not None and str(appid) in lida.com_wrapper
    nome = f"<b>{desenho._e(slo.rotulo_do_jogo(appid))}</b>"
    abertura = (f"{nome} está aberto agora e " if quando == ABERTO else
                f"{nome} foi o último jogo que passou pelo atalho do Hefesto, e "
                "já fechou. Ele ")
    return _com_outra_frase(
        abertura
        + ("<b>abre pelo atalho do Hefesto</b>." if tem else
           "<b>não abre pelo atalho do Hefesto</b> — clique em Consertar com o "
           "jogo e a Steam fechados."), ctx.state)


def _appid_do_clique(o: dict[str, Any], nome: str) -> str:
    """O appid que o botão da linha mandou. Vazio é RECUSA, nunca palpite."""
    appid = str(o.get("v") or "").strip()
    if not appid:
        raise ValueError(
            f"{nome}: o clique não disse qual jogo. Cada linha da lista manda "
            f"`data-v` com o appid — se ele sumiu do desenho, o botão agiria "
            f"sobre um jogo escolhido por acaso.")
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
        raise RuntimeError(
            "Não consegui tirar este jogo da lista de dispensados. O arquivo "
            "`launch_dialog_dismissed.json` não aceitou a escrita — o lembrete "
            "continua desligado para ele.")
    VIGIA.esquecer()
    return _resposta(VIGIA.ler(), ctx.state)


@gesto("07-lancadores.html", "nao-perguntar", grava="add_dismissed_appid")
def nao_perguntar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Não perguntar para este jogo": põe o appid no `launch_dialog_dismissed.json`.

    A METADE DE IDA DO PAR, e ela estava faltando AQUI — não no motor.
    `launch_wrapper_dialog.add_dismissed_appid` existe desde que o lembrete da
    GTK nasceu, e o `voltar-a-perguntar` desta aba (02/09) desfazia uma lista
    que **só a janela velha sabia escrever**. Enquanto isso valesse, a lista de
    dispensados da interface nova ficava CONGELADA no que a GTK tivesse posto,
    e no dia em que a GTK saísse de cena a metade de ida morreria junto.

    ELE SÓ APARECE COM O AVISO VIVO ACESO, que é o mesmo gatilho do botão da
    GTK: o diálogo dela nasce quando há jogo aberto sem o wrapper, e é ali que
    "não perguntar para ESTE jogo" tem sobre o que agir. Ver
    :func:`com_o_que_o_daemon_diz`.

    A CONFIRMAÇÃO É LIDA DE VOLTA, e não é zelo: `add_dismissed_appid` **engole
    a exceção** de propósito (ele roda no tique da GTK, onde derrubar a janela
    por um disco cheio seria pior que o defeito). Aqui ele roda no CLIQUE DELA,
    e um clique que falha calado é o defeito mais caro desta casa — o aviso
    voltaria no tique seguinte e o segundo clique pareceria o primeiro. É a
    mesma razão pela qual o `remove_dismissed_appid` devolve `bool`; como o
    `add` não devolve, quem confere é esta releitura.
    """
    from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as lwd

    appid = _appid_do_clique(o, "nao-perguntar")
    lwd.add_dismissed_appid(appid)
    if appid not in lwd.load_dismissed_appids():
        raise RuntimeError(
            "Não consegui guardar este jogo na lista de dispensados. O arquivo "
            "`launch_dialog_dismissed.json` não aceitou a escrita — o aviso vai "
            "voltar no próximo jogo aberto sem o atalho.")
    VIGIA.esquecer()
    return _resposta(VIGIA.ler(), ctx.state)


@gesto("07-lancadores.html", FECHAR, grava="with_steam_closed")
def fechar_a_steam_e_repor(ctx: Contexto, o: dict[str, Any],
                           p: Any) -> dict[str, Any]:
    """A parede que a GTK derrubou, e que o HTML tinha reerguido.

    O QUE ELE FAZ: pede a Steam fechada, repõe o atalho, e reabre a Steam —
    UMA vez cada, por `steam_launch_options.with_steam_closed`, que é o MESMO
    fluxo provado que os três botões da janela velha usam desde
    HONESTIDADE-STEAM-01. Nenhuma linha daqui fecha, aplica ou reabre nada:
    quem faz é o motor, e a ordem dos portões dele não é negociável (jogo
    aberto antes de tudo — `steam -shutdown` com jogo aberto MATA o jogo).

    POR QUE ELE PRECISOU EXISTIR, medido em 03/09/2026: com a Steam aberta o
    `consertar` desta aba recusa **sempre** (`reparar_ou_adiar` devolve
    `REPARO_ADIADO_STEAM`), e a mesa dela quase sempre tem a Steam aberta —
    ela clica no Hefesto justamente enquanto joga. O produto sabia fechar a
    Steam desde 25/07 e a interface nova não tinha um caminho para
    `with_steam_closed`; era a mesma parede, de novo, com outra tela.

    O CONSENTIMENTO EM DOIS CLIQUES, e ele é EXIGÊNCIA do motor, não desenho
    meu: a docstring do `with_steam_closed` diz que *"o consentimento NÃO mora
    aqui: quem chama tem de ter perguntado antes"*, porque o `stop_steam()`
    escala para `pkill -TERM` e depois `-KILL` depois de 30 s. A janela velha
    pergunta num diálogo; uma página pergunta com o botão. O primeiro clique
    ARMA e devolve o cartão com o botão trocado — o título do diálogo da GTK
    vira o primeiro rótulo, o `rotulo_ok` dela vira o segundo.

    E OS DOIS GUARDAS SÃO INDEPENDENTES DE PROPÓSITO. O segundo clique só vale
    se trouxer o `data-v` :data:`CONFIRMO`, que **só existe no cartão já
    armado**, e só dentro de :data:`SEGUNDOS_PARA_CONFIRMAR`. É o que impede a
    régua automática (`--prova-gesto`) de fechar a Steam DELA para provar que
    sabe clicar: ela clica o que o DOM tinha, e o DOM tinha a pergunta. Um
    guarda só bastaria hoje; dois é o que sobrevive a uma régua que releia o
    DOM entre cliques.

    A RECUSA É A FRASE DA GTK, palavra por palavra
    (`daemon_actions.format_steam_janela_recusa`) — ela já cobre os três
    desfechos do contrato e já diz, nos dois primeiros, que **nada foi mudado**.
    """
    from hefesto_dualsense4unix.app.actions.daemon_actions import (
        format_steam_janela_recusa,
    )
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    if not _este_clique_confirma(FECHAR, o):
        return _resposta(VIGIA.agora(), ctx.state)

    janela, resultado = slo.with_steam_closed(sw.reparar_ou_adiar)
    VIGIA.esquecer()
    recusa = format_steam_janela_recusa(janela)
    if recusa is not None:
        raise RuntimeError(recusa)
    status, censo, _ = resultado
    if status in (sw.REPARO_ADIADO_JOGO, sw.REPARO_ADIADO_STEAM, sw.REPARO_ERRO):
        # Fechar a Steam e ainda assim não caber (o jogo abriu no meio, o vdf
        # tropeçou) é o caso mais forte para a vigia: ela já fez o que a tela
        # pedia e continua sem o atalho.
        VIGIA_DA_STEAM.armar()
        raise RuntimeError(sw.frase_do_aviso(censo) or
                           "não consegui repor o atalho de inicialização")
    VIGIA_DA_STEAM.desarmar()
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
        raise ValueError(
            "abrir-lancador: o clique não disse qual lançador. Cada botão "
            "manda `data-v` com a chave do cartão — sem ela o gesto abriria um "
            "lançador escolhido por acaso.")
    if qual != desenho.STEAM:
        nomes = {x.chave: x.nome for x in desenho.SEM_FONTE}
        raise RuntimeError(
            f"Ainda não sei abrir o {nomes.get(qual, qual)}. O Hefesto só sabe "
            "abrir a Steam por enquanto — abra este lançador como você já abre, "
            "que o perfil casa pelo nome do processo e pela janela do mesmo "
            "jeito.")
    if not slo.reopen_steam():
        raise RuntimeError(
            "Não achei como abrir a Steam nesta máquina: nem o comando `steam` "
            "nem o `xdg-open` estão no PATH. Abra-a pelo seu menu — nada aqui "
            "foi alterado.")
    return None


# ---------------------------------------------------------------------------
# «COPIAR A LINHA» — a saída manual que a tela prometia e não oferecia
#
# O DEFEITO, medido em 04/09/2026: o cartão da Steam escreve *"N jogos com a
# linha intocável — só reparo manual"* e a frase da sentinela termina em
# *"Reparo manual."* — e **não existia UM botão de copiar em toda a interface
# nova** (`grep -rn WRAPPER_LAUNCH src/hefesto_dualsense4unix/interface/`
# devolvia zero). A tela mandava fazer à mão e não dava a mão.
#
# DECIDIDO — PO, 04/09/2026, `07[01]`: **os dois, só quando faz falta.**
# ---------------------------------------------------------------------------
#: Quanto o gesto espera a área de transferência CONFIRMAR. Ele é curto de
#: propósito: o gesto roda em thread, mas quem clicou está olhando o botão em
#: voo — e uma espera longa sobre um laço de GTK que pode nem existir (uma
#: régua chamando o gesto à mão) travaria o pouso do botão.
SEGUNDOS_PARA_COPIAR = 2.0

#: A TARJA DO SUCESSO, e ela é a decisão dela palavra por palavra (`07[01]`) —
#: a mesma primeira oração que a janela velha já diz no toast do
#: `on_storm_copy_launch`. Ela está escrita aqui porque lá é um literal solto
#: dentro do método, sem nome; **extrair a constante na GTK e importá-la é
#: trabalho de fora desta frente, e está relatado.**
COPIADO = ("Copiado! Cole em: Steam → jogo → Propriedades → Opções de "
           "inicialização.")


def para_a_area_de_transferencia(texto: str) -> bool:
    """Põe o texto na área de transferência e **CONFERE lendo de volta**.

    A LEITURA DE VOLTA NÃO É ZELO, e a cicatriz é da própria janela velha:
    `daemon_actions.on_storm_copy_launch` envolve o `set_text` num
    `contextlib.suppress(Exception)` e conclui `copied = True` — o `set_text`
    não devolve nada e ninguém pergunta ao ambiente se a seleção foi tomada.
    Aquele caminho diz *"Copiado!"* pelo fato de **não ter levantado**, que é
    outra pergunta. **Nenhum alarme sem medição** vale nos dois sentidos: um
    recibo que não mediu nada é um recibo que mente.

    O QUE ESTA FUNÇÃO AFIRMA, e é só isto: o texto que voltou da área de
    transferência é o mesmo que foi mandado. Ela não diagnostica POR QUE não
    voltou — o `False` é a ausência da confirmação, e a frase que a tela mostra
    a partir dele não inventa causa nenhuma.

    O `request_text` É ASSÍNCRONO DE PROPÓSITO. O irmão dele — `wait_for_text`
    — BLOQUEIA rodando um laço aninhado, e chamá-lo de dentro de um `idle_add`
    reentraria no laço da janela dela no meio da pintura. Aqui a leitura volta
    por retorno de chamada no mesmo laço, e quem espera é a thread do gesto,
    que é onde esperar é barato.

    SEM LAÇO DE GTK ELA DEVOLVE `False`, e isso é o comportamento certo, não
    uma limitação: uma régua que chame o gesto sem janela nenhuma **não tem**
    área de transferência, e dizer "copiei" ali seria a régua provando o que
    não aconteceu. É por isso que a decisão `07[01]` pediu OS DOIS — com a
    linha à mostra, o `False` não deixa ninguém sem saída.

    NUNCA LEVANTA: o `False` já carrega tudo o que o chamador precisa saber, e
    quem escreve a frase de recusa é o gesto, que sabe falar com ela.
    """
    if not texto:
        return False
    pronto = threading.Event()
    lido: list[str] = []

    def _no_laco_do_gtk() -> bool:
        try:
            # O `Gdk` GANHA VERSÃO DECLARADA, e a razão está MEDIDA nos dois
            # sentidos — 04/09/2026, com o ensaio deste botão:
            #
            #   DENTRO DO PILOTO ela NÃO é a cura. `hefesto_vivo` importa
            #   `Gtk` 3.0, o que já carrega o Gdk 3.0 no repositório, e um
            #   `from gi.repository import Gdk` sem versão resolve para o 3.0
            #   que está lá. Arrancada esta linha, o ensaio passa igual —
            #   está no relato desta frente, e a afirmação contrária que eu
            #   tinha escrito aqui CAIU.
            #
            #   FORA DELE ela é o que separa funcionar de recusar sempre. Num
            #   processo que chegue ao Gdk ANTES do Gtk, o gi escolhe o mais
            #   NOVO instalado — o GDK 4 nesta máquina —, e ali
            #   `SELECTION_CLIPBOARD` **não existe**. Foi exatamente o que o
            #   ensaio fez na primeira volta, no `import` do próprio módulo.
            #
            # O `suppress(ValueError)` é o outro lado: com o 3.0 já carregado o
            # pedido é inócuo; com outro carregado ele levanta, e o `except` de
            # fora devolve `False` — a recusa honesta, não um traceback.
            import contextlib

            import gi

            with contextlib.suppress(ValueError):
                gi.require_version("Gdk", "3.0")
            from gi.repository import Gdk, Gtk
            area = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            area.set_text(texto, -1)
            area.store()

            def _voltou(_area: Any, devolvido: Any, _dado: Any) -> None:
                if isinstance(devolvido, str):
                    lido.append(devolvido)
                pronto.set()

            area.request_text(_voltou, None)
        except Exception:
            pronto.set()
        return False

    try:
        from gi.repository import GLib
    except Exception:  # pragma: no cover - máquina sem GTK
        return False
    GLib.idle_add(_no_laco_do_gtk)
    pronto.wait(SEGUNDOS_PARA_COPIAR)
    return bool(lido) and lido[0] == texto


@gesto("07-lancadores.html", desenho.COPIAR, grava="set_text")
def copiar_a_linha(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Copiar a linha": a linha de inicialização do Hefesto na área de transferência.

    ELE SÓ EXISTE ONDE FAZ FALTA. O botão nasce no cartão da Steam **apenas**
    quando há jogo com a linha intocável (`desenho.cartao_da_steam`), que é o
    único estado em que o produto DECIDIU não repor sozinho — nos outros a
    `_VigiaDaSteam` repõe assim que o jogo e a Steam fecham, e um botão de
    copiar ali seria trabalho manual oferecido sem necessidade.

    A LINHA É A DO MOTOR (`steam_launch_options.WRAPPER_LAUNCH`), a MESMA que o
    botão da janela velha copia e a MESMA que o reparo grava no vdf. Este gesto
    não redige uma linha: se ele redigisse, a linha copiada e a linha aplicada
    poderiam divergir — e ela colaria à mão uma opção que o produto não
    reconhece depois.

    A RECUSA É HONESTA E APONTA A SAÍDA QUE SOBRA. Quando a área de
    transferência não confirma, a frase manda ela para o bloco que está na tela
    logo acima do botão — a segunda saída da mesma decisão. Uma recusa que só
    dissesse "não consegui" deixaria a pessoa exatamente onde o defeito a
    deixava.

    **NÃO GRAVA EM DISCO — E MESMO ASSIM PRECISA DE `PERIGOSOS`.** Ele
    substitui o que ela tiver na área de transferência, e a `--prova-gesto`
    clica todo `[data-gesto]` que achar. A linha que falta em
    `hefesto_vivo.PERIGOSOS` é `("07-lancadores.html", "copiar-a-linha")`, e
    aquele arquivo é de outra posse: **está relatado, com a linha exata.**
    """
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    if not para_a_area_de_transferencia(slo.WRAPPER_LAUNCH):
        raise RuntimeError(
            "Não consegui pôr a linha na área de transferência. Ela está à "
            "mostra no cartão, logo acima deste botão: selecione e copie com "
            "Ctrl+C. Nada foi alterado.")
    return {**_resposta(VIGIA.agora(), ctx.state), "recado": COPIADO}


# ---------------------------------------------------------------------------
# O STEAM INPUT — o que a Steam põe ENTRE o controle e o jogo
#
# DECISÃO DELA, 06/09/2026 (`D-0609-STEAM-DIVIDIDO`): **o Steam Input e a lista
# de exceções ficam aqui, na 07**; "Consertar problemas conhecidos", "Restaurar
# de fábrica" e "Aplicar aos jogos" ficam na 09.
#
# O QUE ESTAVA MEDIDO, e é o buraco que estes três fecham
# (`docs/data/paridade-gtk-html.csv`, linhas 250, 251 e 254): a janela velha
# desliga o Steam Input, marca o jogo que não funciona e faz as duas coisas de
# uma vez; a interface nova **não fazia nenhuma das três**, em aba nenhuma —
# `grep -rn steam_input_allowlist src/hefesto_dualsense4unix/interface/` devolvia
# ZERO. Quem jogasse com o Steam Input ligado via um controle que "não funciona"
# e nada na tela explicando por quê.
#
# NADA AQUI É MOTOR NOVO, e cada peça tem endereço:
#
#     emulation_actions.EmulationActionsMixin._steam_input_script    o script
#     emulation_actions.EmulationActionsMixin._steam_input_is_on     o veredito
#     emulation_actions.format_steam_input_result                    a frase
#     emulation_actions.steam_input_result_tag                       a tag
#     daemon_actions.format_game_broken_result                       a frase
#     daemon_actions.format_steam_ready_result                       a frase
#     daemon_actions.medir_jogos_com_steam_input                     a medição
#     daemon_actions.DaemonActionsMixin._STEAM_READY_CORPO           o consentimento
#     steam_launch_options.add_appid_to_steam_input_allowlist        a marca
#     steam_launch_options.apply_wrapper_to_all_games                o wrapper
#     steam_launch_options.with_steam_closed                         fechar/reabrir
#
# O CONSENTIMENTO É EXIGÊNCIA DO MOTOR, e não desenho meu: `with_steam_closed`
# diz por escrito que *"o consentimento NÃO mora aqui: quem chama tem de ter
# perguntado antes"*, porque `stop_steam()` escala para `pkill -TERM` e depois
# `-KILL` depois de 30 s. A janela velha pergunta num diálogo; uma página
# pergunta com o botão. Ver :func:`_este_clique_confirma`.
#
# E O VEREDITO É O ARQUIVO, NUNCA O `rc`: `_steam_input_is_on()` relê os
# `localconfig.vdf` depois de tudo, e é ESSA releitura que decide se a tela diz
# que deu certo. É a regra que a `HONESTIDADE-STEAM-01` deixou — o script pode
# sair 0 tendo ADIADO —, e aqui ela tem uma consequência a mais: a releitura
# escolhe entre o recado VERDE e a recusa LARANJA.
# ---------------------------------------------------------------------------
def _o_script_que_desliga() -> Any:
    """O `disable_steam_input.sh` desta instalação, ou `None`.

    PERGUNTADO AO DONO (`EmulationActionsMixin._steam_input_script`), que é um
    método de instância cujo corpo não toca em `self` — o mesmo idioma que
    `daemon_actions.medir_jogos_com_steam_input` já usa com os estáticos do
    mixin. Digitar `"scripts/disable_steam_input.sh"` aqui seria a quarta base
    de busca de um caminho que a `BG-BASES-01` já pagou uma vez para unificar.
    """
    from hefesto_dualsense4unix.app.actions.emulation_actions import (
        EmulationActionsMixin,
    )

    return EmulationActionsMixin._steam_input_script(None)  # type: ignore[arg-type]


def _o_steam_input_continua_ligado() -> bool | None:
    """A releitura do arquivo — o único veredito que esta aba aceita."""
    from hefesto_dualsense4unix.app.actions.emulation_actions import (
        EmulationActionsMixin,
    )

    return EmulationActionsMixin._steam_input_is_on()


def _rodar_o_script(script: Any) -> tuple[int, str]:
    """`bash <script> --apply-quiet` — a mesma linha da janela velha.

    `--apply-quiet` POR CONTRATO NUNCA FECHA A STEAM: com ela viva ele ADIA e
    sai 0. Quem fecha é `with_steam_closed`, e é por isso que os dois nunca
    disputam — um dono só decide matar processo da usuária.
    """
    import subprocess

    proc = subprocess.run(["bash", str(script), "--apply-quiet"], check=False,
                          timeout=180, capture_output=True, text=True)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


@gesto("07-lancadores.html", desenho.DESLIGAR_STEAM_INPUT, grava="with_steam_closed")
def desligar_o_steam_input(ctx: Contexto, o: dict[str, Any],
                           p: Any) -> dict[str, Any]:
    """"Desligar o Steam Input": tira a Steam do meio entre o controle e o jogo.

    A ORDEM DOS PORTÕES É A DA JANELA VELHA, e ela não é negociável
    (`emulation_actions._steam_input_decidir`):

    1. **jogo aberto ⇒ RECUSA.** `steam -shutdown` mataria o jogo e o progresso
       não salvo. A frase é a do dono (`status="jogo_aberto"`);
    2. **só a Steam aberta ⇒ pergunta.** O primeiro clique ARMA e devolve o
       cartão com o botão trocado; o segundo fecha a Steam por ~20 s, aplica e
       reabre — UMA vez cada, por `with_steam_closed`;
    3. **Steam fechada ⇒ aplica direto.** Não há consentimento a pedir quando
       não há nada a fechar, e pedi-lo seria cobrar um preço que não existe.

    A SONDAGEM É FEITA AGORA, e não lida da :data:`PORTOES`: aquela é de até 20
    segundos atrás, e ela pode ter aberto a Steam nesse meio-tempo. Aqui isso é
    barato — o gesto roda em thread (`hefesto_vivo._gesto`), que é onde varrer
    `/proc` não custa tique nenhum.

    O VEREDITO É O ARQUIVO. `format_steam_input_result` já recusa dizer "Pronto"
    sem evidência, e a evidência é a releitura dos `localconfig.vdf`
    (`ainda_ligado`). Aqui ela decide também a COR: desligado de verdade vira
    recado verde; qualquer outra coisa é recusa laranja, com a frase do dono.
    """
    from hefesto_dualsense4unix.app.actions.emulation_actions import (
        format_steam_input_result,
        steam_input_result_tag,
    )
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    script = _o_script_que_desliga()
    if script is None:
        raise RuntimeError(format_steam_input_result(status="sem_script"))
    if slo.steam_game_running():
        raise RuntimeError(format_steam_input_result(status="jogo_aberto"))

    if slo.steam_running():
        if not _este_clique_confirma(desenho.DESLIGAR_STEAM_INPUT, o):
            return {**_resposta(VIGIA.agora(), ctx.state),
                    "recado": PERGUNTA_DA_STEAM}
        janela, resultado = slo.with_steam_closed(lambda: _rodar_o_script(script))
        if janela == slo.STEAM_JANELA_JOGO_ABERTO:
            raise RuntimeError(format_steam_input_result(status="jogo_aberto"))
        if janela == slo.STEAM_JANELA_NAO_FECHOU:
            raise RuntimeError(format_steam_input_result(status="nao_fechou"))
        rc, saida = resultado
    else:
        rc, saida = _rodar_o_script(script)

    VIGIA.esquecer()
    ainda_ligado = _o_steam_input_continua_ligado()
    frase = format_steam_input_result(status="executado", rc=rc,
                                      tag=steam_input_result_tag(saida),
                                      ainda_ligado=ainda_ligado)
    if ainda_ligado is not False:
        raise RuntimeError(frase)
    return {**_resposta(VIGIA.ler(), ctx.state), "recado": frase}


@gesto("07-lancadores.html", desenho.JOGO_NAO_FUNCIONA, grava="add_appid_to_steam_input_allowlist")
def este_jogo_nao_funciona(ctx: Contexto, o: dict[str, Any],
                           p: Any) -> dict[str, Any]:
    """"Este jogo não funciona": põe o jogo na lista de exceções do Steam Input.

    SEM PERGUNTA, e isso é do motor e não descuido meu: o gesto **não fecha
    nada, não edita arquivo da Steam e é reversível** (uma linha num arquivo
    nosso, que a caixinha do editor de perfil também desfaz). É por isso que a
    janela velha não abre diálogo aqui, e é por isso que esta tela não abre
    também — pedir consentimento para um ato reversível ensina que todo botão
    pede consentimento, e aí o consentimento que importa deixa de ser lido.

    QUAL JOGO É: a mesma escada de três evidências de :func:`a_escada_do_jogo`,
    e é ela que faz o botão servir ao caso REAL — *"o jogo não funcionou, ela
    fechou, e só então veio reclamar"*. Sem jogo, a recusa é a frase do dono.

    A RECARGA NÃO É ZELO — ela é a metade que faz a marca VALER AGORA. A lista
    é relida do disco a cada consulta, mas o que entrega a entrada daquele jogo
    ao controle físico só nasce quando o daemon rematerializa o ambiente de
    inicialização. Sem ela a marca só valeria no próximo arranque do serviço, e
    a pessoa clicaria de novo achando que o primeiro clique não pegou. É o
    MESMO aviso best-effort que `daemon_actions._recarregar_apos_allowlist`
    manda (serviço parado é normal — ele rematerializa sozinho ao subir).
    """
    from hefesto_dualsense4unix.app.actions.daemon_actions import (
        format_game_broken_result,
    )
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    appid, _quando = a_escada_do_jogo(ctx.state)
    if appid is None:
        raise RuntimeError(format_game_broken_result(status="sem_jogo"))
    status = slo.add_appid_to_steam_input_allowlist(
        appid, nota="marcado pela tela: 'este jogo não funciona'")
    frase = format_game_broken_result(status=status, appid=appid)
    if status in ("appid_invalido", "erro"):
        raise RuntimeError(frase)
    p.chamar(METODO_DA_RECARGA)
    VIGIA.esquecer()
    return {**_resposta(VIGIA.ler(), ctx.state), "recado": frase}


# `grava="with_steam_closed"` E NÃO `apply_wrapper_to_all_games`, que é
# quem de fato reescreve a linha de TODOS os jogos: ele chega aqui por
# `getattr(slo, …)` e a árvore não o enxerga. A direção B da régua
# reprovou a primeira declaração deste gesto por isso, no dia em que ela
# nasceu — e a porta declarada tem de ser a que a árvore confirma.
@gesto("07-lancadores.html", desenho.TUDO_PRONTO, grava="with_steam_closed")
def deixar_tudo_pronto(ctx: Contexto, o: dict[str, Any],
                       p: Any) -> dict[str, Any]:
    """"Deixar tudo pronto": os DOIS trabalhos, com UM consentimento só.

    ELE EXISTE PORQUE ELA PEDIU, com estas palavras: *"tem jogos que precisamos
    ativar entrada steam, outros que temos que colocar comandos de inicialização
    — é uma confusão real"*. O que sai da tela não são os dois mecanismos: é a
    ESCOLHA entre eles.

    UM CONSENTIMENTO, E NÃO DOIS, e a razão é medida: os dois cabem numa janela
    de `with_steam_closed`, e pedir duas vezes é fazer a pessoa pagar duas vezes
    pelo mesmo fechamento da Steam. É por isso que o botão só aparece quando os
    DOIS lados têm trabalho (ver :func:`acoes_do_steam_input`) — com um só
    pendente, o botão daquele lado já resolve com um consentimento igual.

    A MEDIÇÃO ACONTECE DENTRO DA JANELA E ANTES DO SCRIPT, e a ordem é do dono
    (`D-33`): é o último instante em que o arquivo ainda diz de QUAL jogo
    estamos falando — depois de o script rodar, já foi zerado.

    A FRASE DO CONSENTIMENTO É DO MOTOR, palavra por palavra
    (`DaemonActionsMixin._STEAM_READY_CORPO`, o corpo do diálogo da janela
    velha). As quebras de parágrafo viram espaço porque um recado é uma linha,
    não uma caixa — e nenhuma palavra dela muda no caminho.
    """
    from hefesto_dualsense4unix.app.actions.daemon_actions import (
        DaemonActionsMixin,
        format_steam_janela_recusa,
        format_steam_ready_result,
        medir_jogos_com_steam_input,
    )
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    if not _este_clique_confirma(desenho.TUDO_PRONTO, o):
        return {**_resposta(VIGIA.agora(), ctx.state),
                "recado": " ".join(
                    DaemonActionsMixin._STEAM_READY_CORPO.split())}

    script = _o_script_que_desliga()
    aplicar = getattr(slo, "apply_wrapper_to_all_games", None)

    def _acao() -> dict[str, Any]:
        saida: dict[str, Any] = {"script": None, "wrapper": None,
                                 "steam_input_jogos": medir_jogos_com_steam_input()}
        if script is not None:
            saida["script"] = _rodar_o_script(script)
        if aplicar is not None:
            saida["wrapper"] = aplicar()
        return saida

    janela, dados = slo.with_steam_closed(_acao)
    VIGIA.esquecer()
    recusa = format_steam_janela_recusa(janela)
    if recusa is not None:
        raise RuntimeError(recusa)
    frase = format_steam_ready_result(janela=janela, dados=dados,
                                      script_ok=script is not None,
                                      wrapper_ok=aplicar is not None)
    if _o_steam_input_continua_ligado() is True:
        raise RuntimeError(frase)
    return {**_resposta(VIGIA.ler(), ctx.state), "recado": frase}


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

    if desenho.ADICIONAR_ROTULO in tem:
        return (f"{abertura}, e o Hefesto não achou onde ele está. Use o "
                f"«{desenho.ADICIONAR_ROTULO}» do cartão dele — assim o que "
                f"você me disser entra na busca daquele cartão, em vez de "
                f"criar um segundo com o mesmo nome.")

    tirar = desenho.acao_de_tirar(chave).rotulo
    if tirar in tem:
        return (f"{abertura}, e ele já está apontado. Para apontar outro, use "
                f"o «{tirar}» do cartão dele primeiro — o cartão volta a "
                f"perguntar onde ele está, e a sua resposta entra ali.")

    return (f"{abertura}, e o Hefesto já o achou sozinho nesta máquina. Não há "
            f"o que apontar: o que você digitar aqui criaria um segundo cartão "
            f"com o mesmo nome. Se o que ele achou não é o que você quer, me "
            f"diga — hoje o cartão não tem por onde trocar.")


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

    para_quem = _PARA_QUEM
    de_fabrica = {x.chave: x.nome for x in desenho.EMBUTIDOS}

    if not alvo:
        raise ValueError(
            "Diga onde ele está: o comando (`ryujinx`), o caminho do programa "
            "(`/opt/Ryujinx/Ryujinx`) ou o nome do atalho "
            "(`org.ryujinx.Ryujinx`). É o que eu preciso para achá-lo.")
    if len(alvo) > _MAXIMO_DA_AGULHA:
        raise ValueError(
            f"São {len(alvo)} caracteres, e o teto é {_MAXIMO_DA_AGULHA}. O que "
            "eu preciso é do comando ou do nome do atalho, não da linha de "
            "inicialização inteira.")

    chave = para_quem or chave_do_rotulo(rotulo)
    if not chave:
        raise ValueError(
            "Diga como ele se chama. O nome é o que aparece no topo do cartão, "
            "e é dele que sai o endereço interno do cartão.")
    if not para_quem and chave in de_fabrica:
        raise RuntimeError(_recusa_de_quem_ja_tem_cartao(chave, de_fabrica[chave]))

    campo, agulha, onde = onde_isso_esta(alvo)
    if not campo:
        raise RuntimeError(
            f"Não achei {alvo!r} nesta máquina. Procurei o comando no `PATH` e "
            f"o atalho `{alvo.rsplit('/', 1)[-1]}.desktop` nas pastas de "
            f"aplicativos. Confira o caminho e tente de novo — nada foi "
            f"guardado.")

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
        recado += (f" O nome que você digitou, «{rotulo.strip()}», não entrou: "
                   f"este cartão já se chama {nome}, e o que o botão dele "
                   f"acrescenta é ONDE procurar.")

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
        raise ValueError(
            "esquecer-lancador: o clique não disse qual. Cada botão manda "
            "`data-v` com a chave do cartão — sem ela eu apagaria a declaração "
            "de um lançador escolhido por acaso.")
    declarados = {x.chave: x.nome for x in _declarados()}
    if qual not in declarados:
        raise RuntimeError(
            "Não há nada a tirar deste cartão: ele é de fábrica e você não "
            "declarou nada sobre ele.")

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


#: O ÚNICO MÉTODO DO DAEMON QUE ESTA ABA CHAMA, e ele nasceu em 06/09/2026 com
#: o "Este jogo não funciona". Ver :func:`este_jogo_nao_funciona`.
METODO_DA_RECARGA = "launch_env.refresh"

#: FATO SUBSTITUÍDO — 06/09/2026. Aqui estava escrito que *"nenhum gesto desta
#: aba fala com o daemon"*, e era verdade até o "Este jogo não funciona" nascer:
#: marcar o jogo na lista de exceções só VALE AGORA se o daemon rematerializar o
#: ambiente de inicialização, e o método existe (`launch_env.refresh`) — é o
#: mesmo aviso best-effort que a janela velha manda depois da mesma escrita.
#:
#: OS OUTROS DEZ CONTINUAM SEM PONTE, e a medição que os deixou assim não mudou:
#: o wrapper vive em dois arquivos em disco, e o `state_full` não tem UMA chave
#: sobre a Steam, sobre a lista de recusados ou sobre a de dispensados.
# `machine_declare` ENTROU EM 08/09/2026 com o lançador declarado por ELA: é a
# ÚNICA porta de escrita do `maquina.json`, e o lock daquele arquivo é de
# PROCESSO — uma segunda escrita viva noutro processo perderia a declaração de
# quem gravou primeiro, calada.
PONTE: set[str] = {"chamar", "machine_declare"}
METODOS: set[str] = {METODO_DA_RECARGA, "machine.declare"}


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
#: e de 16 PARA 17 em 09/09/2026, com a CURA POR ESTRADA
#: (:data:`desenho.CONSERTAR_LANCADOR`): o ambiente do Hefesto entrando nos
#: lançadores que o atalho de inicialização da Steam não alcança.
PISO_DA_ABA = 17

#: SEM `PROVAS`, e a razão é o contrato da régua dos botões: ela injeta uma
#: `PonteDeMentira` e cobra QUAL função da ponte o gesto chamou. Um gesto que
#: não usa a ponte chamaria zero e a régua reprovaria por estar CERTO — o
#: defeito que esta casa nomeou onze vezes em 26/08 (*a régua reprovando a
#: melhora em vez do defeito*). Quem prova estes seis é
#: `tests/unit/test_a_aba_lancadores_diz_a_verdade.py`, com o `HOME` desviado e
#: o efeito cobrado NO ARQUIVO — que é a prova mais forte, não a mais fraca.
PROVAS: list[dict[str, Any]] = []

#: TODOS OS DEZ, e não por preguiça: o `state_full` do daemon não tem UMA
#: chave sobre a Steam, sobre o `localconfig.vdf`, sobre a lista de recusados ou
#: sobre a de dispensados. O efeito destes botões é o DISCO e a TELA — e os dois
#: têm régua. O `abrir-lancador` entrou em 03/09/2026 pelo motivo mais forte de
#: todos: o efeito dele é uma JANELA da Steam, que o daemon não vê nem por
#: acidente.
#:
#: O `consertar-fechando-a-steam` PARECE a exceção e não é: ele muda
#: `gamepad_emulation.wrapper_used` — mas só no próximo jogo que ela abrir, e
#: nunca no eco de um gesto. Um `state_full` lido logo depois responde o mesmo
#: que respondia antes, e uma régua que cobrasse eco dele reprovaria o botão
#: por estar CERTO.
#:
#: O `copiar-a-linha` ENTROU EM 04/09/2026 pelo mesmo motivo do
#: `abrir-lancador`, e ainda mais forte: o efeito dele é a ÁREA DE
#: TRANSFERÊNCIA do ambiente gráfico dela, que o daemon não vê de jeito nenhum.
#:
#: E OS TRÊS DO STEAM INPUT ENTRAM PELO MESMO MOTIVO — 06/09/2026. O
#: `state_full` não tem UMA chave sobre o Steam Input: quem responde se ele está
#: ligado é o `localconfig.vdf` da Steam, lido do disco
#: (`emulation_actions._steam_input_is_on`), e a lista de exceções é um arquivo
#: nosso. O `este-jogo-nao-funciona` PARECE a exceção porque manda
#: `launch_env.refresh` ao daemon — e não é: o método rematerializa o ambiente
#: de inicialização e **não publica nada** no `state_full`. Uma régua que
#: cobrasse eco dele reprovaria o botão por estar CERTO.
SEM_ECO = ("procurar", "consertar", "ver-o-que-impede", "detectar",
           "tirar-daqui", "voltar-a-usar", "voltar-a-perguntar",
           "abrir-lancador", "nao-perguntar", FECHAR, desenho.COPIAR,
           desenho.DESLIGAR_STEAM_INPUT, desenho.JOGO_NAO_FUNCIONA,
           desenho.TUDO_PRONTO,
           # OS DOIS DO REGISTRO (08/09/2026) entram pelo mesmo motivo dos
           # outros catorze, e por um a mais: o efeito deles é o
           # `maquina.json`, e o `state_full` não tem UMA chave sobre a
           # declaração dela — nem sobre lançador nenhum.
           desenho.ADICIONAR, desenho.REMOVER,
           # A CURA POR ESTRADA (09/09/2026) entra pelo motivo mais forte da
           # lista: o efeito dela é o `config.json` do Heroic e o arquivo de
           # override do Flatpak — arquivos de OUTROS programas, que o daemon
           # não lê nem por acidente. Um `state_full` pedido logo depois
           # responde exatamente o que respondia antes.
           desenho.CONSERTAR_LANCADOR)
