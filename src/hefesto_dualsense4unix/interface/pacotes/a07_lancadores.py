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

#: Quanto tempo o "posso fechar a Steam?" fica ARMADO depois do primeiro
#: clique. Ver :func:`fechar_a_steam_e_repor` — é o consentimento que
#: `with_steam_closed` EXIGE de quem a chama, na forma que uma página tem.
SEGUNDOS_PARA_CONFIRMAR = 20.0

#: O `abrir-lancador` SAIU DAQUI em 03/09/2026 — decisão 17 dela, e o motivo
#: escrito nesta linha era a pergunta errada: *"o daemon não tem método para
#: isso"* é verdade pelo IPC e o produto sabia abrir a Steam por outro caminho
#: desde 23/08 (`steam_launch_options.reopen_steam`). O botão tem dono agora;
#: quem conta o que ele sabe e o que não sabe é :func:`abrir_lancador`.
SEM_DONO: dict[str, str] = {
    "criar-perfil": "criar perfil é da aba Perfis (`a10_perfis`); dois caminhos "
                    "para o mesmo disco é como duas telas passam a discordar",
    "heroic": "o produto PROCURA os seis (`_onde_estao_os_lancadores`, pelas "
              "pastas de `.desktop` e pelo `PATH`) e sabe dizer se estão aqui, "
              "mas não LÊ a biblioteca de nenhum deles — nenhuma função de "
              "`src/` abre o catálogo do Heroic, do Lutris, do RetroArch, do "
              "Dolphin ou do mGBA, e por isso o cartão do que foi achado "
              "continua dizendo NÃO SEI",
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


def _onde_estao_os_lancadores() -> tuple[tuple[str, str], ...]:
    """PROCURA os SEIS lançadores nesta máquina. Não lê dentro de nenhum.

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
    lista percorrida é :data:`desenho.PROCURADOS`, que são os SEIS.

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
    for item in desenho.PROCURADOS:
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

    global PORTOES

    onde_estao = _onde_estao_os_lancadores()

    try:
        censo = sw.censo_do_wrapper(anotar=False)
    except Exception as erro:  # o disco dela não pode derrubar a aba
        # OS PORTÕES VOLTAM AO PADRÃO, e não ficam com o valor de antes: sem
        # censo não há resposta sobre a Steam, e um `steam_aberta=True` velho
        # acenderia o botão que fecha a Steam dela com base numa leitura que
        # falhou. O padrão não oferece o botão, que é a recusa honesta.
        PORTOES = _Portoes()
        return desenho.Leitura(erros=(str(erro),), onde_estao=onde_estao)

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

    return desenho.Leitura(
        com_wrapper=tuple(censo.com_wrapper),
        reparaveis=trio(censo.reparaveis),
        intocaveis=trio(censo.intocaveis),
        recusados=tuple((a, slo.rotulo_do_jogo(a)) for a in censo.recusados),
        dispensados=_dispensados(),
        instalados=instalados,
        pontes=pontes,
        onde_estao=onde_estao,
        frase=sw.frase_do_aviso(censo),
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
    própria função. Ver `espera_a_palavra_dela`: a última frase dele manda
    copiar as opções *"na aba Sistema"*, e no desenho novo não há esse botão em
    aba nenhuma — quem decide o texto é ela, não esta frente.

    A DISPENSA DELA É RESPEITADA, e é a metade que faz o par existir: se ela
    clicou em *"Não perguntar para este jogo"*, o aviso não volta para aquele
    appid. A lista sai da `Leitura` que a vigia já leu (`lida.dispensados`) —
    reler o JSON a cada tique seria disco na thread da janela, que é o que a
    :class:`_Vigia` existe para impedir.

    SEM O APPID O AVISO CONTINUA, e é decisão: `wrapper_used is False` é o
    daemon afirmando que HÁ jogo aberto sem o wrapper. Calar porque a
    `window_detect_last_class` ainda não casou trocaria um aviso verdadeiro por
    silêncio — o que some é só o botão de dispensar, que sem appid não teria
    sobre o que agir.
    """
    from hefesto_dualsense4unix.app.actions import home_actions as ha

    texto = ha.wrapper_banner_text(state)
    if not texto:
        return "", ""
    appid = _o_jogo_em_foco(state)
    if appid and lida is not None and appid in {a for a, _ in lida.dispensados}:
        return "", ""
    return f"<b>{_texto(texto)}</b><br>", appid


#: O rótulo do botão que dispensa o aviso. É o do diálogo da GTK, palavra por
#: palavra (`launch_wrapper_dialog.py:435`) — a mesma lista, o mesmo gesto, o
#: mesmo texto.
DISPENSAR = "Não perguntar para este jogo"

#: O nome do gesto que fecha a Steam, e o `data-v` que ARMA a segunda metade.
#: Ver :func:`fechar_a_steam_e_repor`.
FECHAR = "consertar-fechando-a-steam"
CONFIRMO = "steam:confirmo"

#: OS DOIS RÓTULOS SAEM DO DIÁLOGO DA GTK, e não de mim: o título do
#: consentimento (`daemon_actions._pedir_para_fechar_a_steam`, o `titulo`
#: padrão) vira o primeiro botão, e o `rotulo_ok` dele vira o segundo. O
#: diálogo que a janela velha mostra é, aqui, um botão que muda de rótulo.
PERGUNTA_DA_STEAM = "Posso fechar a Steam por uns 20 segundos?"
CONFIRMA_A_STEAM = "Fechar e continuar"

#: Até quando o "posso fechar a Steam?" está armado (`time.monotonic`). Zero =
#: desarmado. Ver :func:`fechar_a_steam_e_repor`.
_ARMADO_ATE = 0.0


def _armado() -> bool:
    return time.monotonic() < _ARMADO_ATE


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
        acoes = (
            *acoes,
            desenho.Acao(CONFIRMA_A_STEAM, "verde", FECHAR, CONFIRMO)
            if _armado()
            else desenho.Acao(PERGUNTA_DA_STEAM, "", FECHAR, desenho.STEAM),
        )
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
# POR QUE A FITA CHEGOU AQUI, sendo ela de todas as abas: `hefesto_vivo._fita`
# desiste da fita INTEIRA quando UM controle estiver sem cor
# (`any(not c.get("cor") for c in mesa)` → `return ""`), e o JS só troca o bloco
# `if(p.fita)`. Nesta máquina o `LeitorDeCor` não conhece o controle de rádio,
# então a fita NUNCA era repintada — e "deixar a fita como está" é deixar a
# fita do MOCKUP. Está relatado como trabalho de fora desta aba; o que esta aba
# pode fazer sozinha é escrever a SUA.
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
    Um controle sem cor lida sai `P2 • BT`, e não `P2 • Não sei • BT` nem — muito
    pior — o nome do controle do desenho.

    O QUE NÃO ENTRA, E É DECISÃO DESTA ABA: o `--plastico` e o `title` do chip.
    A fita daqui nasce ESMAECIDA (`fita_viva=False`, decisão dela de 28/08:
    nada nesta aba ajusta por controle), e `topo.html:207` apaga a borda de
    plástico justamente aí — *"a borda de 2px na cor do plástico é a marca da
    peça VIVA — some com a fita"*. Escrever uma cor que a folha de estilo
    descarta é um valor sem efeito na tela; e o `title` do desenho dizia *"a
    borda é a cor do plástico"*, uma frase que nesta aba é falsa. Quem explica a
    fita apagada aqui é o `title` da `<div class="fita inerte">`, que o
    `blocos` não toca.
    """
    nome = str(controle.get("nome") or "")
    lido = bool(controle.get("cor")) and nome and nome != SEM_LEITURA_DE_COR
    partes = [f"P{controle.get('jogador') or '?'}"]
    if lido:
        partes.append(_texto(nome))
    partes.append(_texto(controle.get("via") or ""))
    return ('<span class="chip plastico">'
            + ' <span class="pt">•</span> '.join(partes)
            + "</span>")


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
    somar diferente do total, e uma via nova (ou um `via` vazio) cai no lado do
    rádio em vez de sumir da conta. Duas somas independentes é como a tela ganha
    um "2 controles: 1 USB · 0 BT" que não fecha.
    """
    n = len(mesa)
    usb = sum(1 for c in mesa if str(c.get("via") or "").strip().upper() == "USB")
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
            '<span class="chip on">Todos</span>'
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
    return {
        "mesa": desenho.Quadro(lancadores=lancadores).valores(),
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
    que a fita desta aba nasce esmaecida (`fita_viva=False`) e por isso este
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
    fora["blocos"] = {**carga["blocos"], SELETOR_DA_FITA: fita_html(ctx.mesa)}
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
    return _resposta(VIGIA.ler(), ctx.state)


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
    return _resposta(VIGIA.ler(), ctx.state)


@gesto("07-lancadores.html", "voltar-a-perguntar")
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


@gesto("07-lancadores.html", "nao-perguntar")
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


@gesto("07-lancadores.html", FECHAR)
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
    global _ARMADO_ATE

    from hefesto_dualsense4unix.app.actions.daemon_actions import (
        format_steam_janela_recusa,
    )
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    if str(o.get("v") or "").strip() != CONFIRMO:
        _ARMADO_ATE = time.monotonic() + SEGUNDOS_PARA_CONFIRMAR
        return _resposta(VIGIA.agora(), ctx.state)
    if not _armado():
        _ARMADO_ATE = 0.0
        raise RuntimeError(
            f"Passaram-se mais de {int(SEGUNDOS_PARA_CONFIRMAR)} segundos desde "
            "a pergunta — não fechei nada. Clique de novo para começar.")
    _ARMADO_ATE = 0.0

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


@gesto("07-lancadores.html", desenho.ABRIR)
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


#: VAZIOS, E É A MEDIÇÃO QUE OS DEIXA VAZIOS: nenhum gesto desta aba fala com o
#: daemon. O wrapper vive em dois arquivos em disco, e `pacotes.daemon.metodos()`
#: não traz um método sequer que os toque.
PONTE: set[str] = set()
METODOS: set[str] = set()


PAGINA = "07-lancadores.html"
#: SUBIU DE 6 PARA 7 em 02/09/2026, com o "Voltar a perguntar" (decisão dela);
#: de 7 PARA 8 em 03/09/2026, com o "Abrir o lançador" (decisão 17 dela); e de
#: 8 PARA 10 no mesmo dia, com as duas faltas de paridade que a medição das dez
#: abas nomeou — o "Não perguntar para este jogo" (a metade de ida do par, que
#: só a GTK sabia escrever) e o "Posso fechar a Steam por uns 20 segundos?" (o
#: caminho para `with_steam_closed`, que a interface nova não tinha).
PISO_DA_ABA = 10

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
SEM_ECO = ("procurar", "consertar", "ver-o-que-impede", "detectar",
           "tirar-daqui", "voltar-a-usar", "voltar-a-perguntar",
           "abrir-lancador", "nao-perguntar", FECHAR)
