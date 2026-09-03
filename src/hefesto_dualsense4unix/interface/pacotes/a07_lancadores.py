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
    app/actions/launch_wrapper_dialog.load_dismissed_appids  quem ela dispensou
    app/actions/launch_wrapper_dialog.remove_dismissed_appid o "voltar a perguntar"

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

SEM_DONO: dict[str, str] = {
    "abrir-lancador": "abrir a Steam (ou qualquer lançador) é `xdg-open`, não "
                      "IPC — o daemon não tem método para isso, e um botão que "
                      "responde calado é pior que um que recusa",
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
    disco, e o orçamento do tique é de 500 ms para a janela inteira.

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

    onde_estao = _onde_estao_os_lancadores()

    try:
        censo = sw.censo_do_wrapper(anotar=False)
    except Exception as erro:  # o disco dela não pode derrubar a aba
        return desenho.Leitura(erros=(str(erro),), onde_estao=onde_estao)

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


def _resposta(lida: desenho.Leitura | None) -> dict[str, Any]:
    """O que um gesto devolve para a tela — a mesma carga da pintura.

    Um gesto que trocasse só os campos deixaria a moldura do tique anterior:
    "Consertar" leva o cartão de `NÃO CHEGAM` a `CHEGAM` e a borda laranja
    ficaria até o próximo tique. Meio segundo de tela mentindo continua sendo
    tela mentindo.
    """
    return _pintura(desenho.cartoes(lida))


@registrar("07-lancadores.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    """A aba inteira, e ela NÃO depende de controle nenhum.

    O gerador já tinha medido isto e escrito no próprio arquivo: nenhuma função
    de `prontuario_dos_jogos` recebe controle, MAC, device ou transporte — os
    cinco impedimentos e as duas curas são fatos do JOGO EM DISCO. É por isso
    que a fita desta aba nasce esmaecida (`fita_viva=False`) e por isso este
    pacote não devolve `colunas`: não há nada a dizer por controle.
    """
    carga = _resposta(VIGIA.agora())
    valores = carga["mesa"]
    fora: dict[str, Any] = dict(valores)
    fora["blocos"] = carga["blocos"]
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
    return _resposta(VIGIA.ler())


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
    return _resposta(VIGIA.ler())


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
    return _com_outra_frase(desenho._e(censo.frase()))


def _com_outra_frase(diz: str) -> dict[str, Any]:
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
    cartoes = desenho.cartoes(lida)
    cartoes[0] = dataclasses.replace(cartoes[0], diz=diz)
    return _pintura(cartoes)


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
    return _com_outra_frase(
        f"<b>{desenho._e(slo.rotulo_do_jogo(appid))}</b> está aberto agora e "
        + ("<b>abre pelo atalho do Hefesto</b>." if tem else
           "<b>não abre pelo atalho do Hefesto</b> — clique em Consertar com o "
           "jogo e a Steam fechados."))


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
    return _resposta(VIGIA.ler())


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
    return _resposta(VIGIA.ler())


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
    return _resposta(VIGIA.ler())


#: VAZIOS, E É A MEDIÇÃO QUE OS DEIXA VAZIOS: nenhum gesto desta aba fala com o
#: daemon. O wrapper vive em dois arquivos em disco, e `pacotes.daemon.metodos()`
#: não traz um método sequer que os toque.
PONTE: set[str] = set()
METODOS: set[str] = set()


PAGINA = "07-lancadores.html"
#: SUBIU DE 6 PARA 7 em 02/09/2026, com o "Voltar a perguntar" (decisão dela).
PISO_DA_ABA = 7

#: SEM `PROVAS`, e a razão é o contrato da régua dos botões: ela injeta uma
#: `PonteDeMentira` e cobra QUAL função da ponte o gesto chamou. Um gesto que
#: não usa a ponte chamaria zero e a régua reprovaria por estar CERTO — o
#: defeito que esta casa nomeou onze vezes em 26/08 (*a régua reprovando a
#: melhora em vez do defeito*). Quem prova estes seis é
#: `tests/unit/test_a_aba_lancadores_diz_a_verdade.py`, com o `HOME` desviado e
#: o efeito cobrado NO ARQUIVO — que é a prova mais forte, não a mais fraca.
PROVAS: list[dict[str, Any]] = []

#: TODOS OS SETE, e não por preguiça: o `state_full` do daemon não tem UMA
#: chave sobre a Steam, sobre o `localconfig.vdf`, sobre a lista de recusados ou
#: sobre a de dispensados. O efeito destes botões é o DISCO e a TELA — e os dois
#: têm régua.
SEM_ECO = ("procurar", "consertar", "ver-o-que-impede", "detectar",
           "tirar-daqui", "voltar-a-usar", "voltar-a-perguntar")
