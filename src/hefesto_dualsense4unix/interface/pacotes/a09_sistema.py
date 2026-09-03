#!/usr/bin/env python3
"""O pacote da aba `09` Sistema.

O QUE TEM DONO: o serviço está de pé (o daemon respondeu — se ele calasse, não
haveria pacote), o perfil ativo, a política de bateria (`rumble_policy`, que é o
mesmo dado do Perfil de Bateria desta aba) e quantos controles ela alcança.

O ALCANCE É A LINHA QUE MAIS ERRA, e errou hoje: ela dizia *"Os 4 controles"*
com dois na mesa. Aqui ele sai de `conectados`, e a régua da aba o cobra.

O QUE NÃO TEM: as versões, os plugins e o estado dos consertos automáticos —
tudo isso é do `doctor` e do instalador, não do `state_full`.

A MEIA LIGAÇÃO DE 01/09, MEDIDA E FECHADA EM 02/09/2026
-------------------------------------------------------
O `pacote()` delegava para `gui/aba_sistema.pacote` — mas o `_leitura()` que o
alimentava preenchia TRÊS dos sete campos do `Leitura` (`status`, `autostart`,
`state`). Os outros quatro chegavam `None`, e a camada do produto faz a coisa
certa com `None`: devolve o traço. **Só que a página não é branca — ela é o
desenho dela.** Onde o pacote não escreve, o que fica na tela é o literal do
mockup, e ele é convincente:

    o que a tela mostrava          o que a máquina dela dizia (02/09, 04:23)
    ─────────────────────────────  ────────────────────────────────────────
    Como ele enxerga a janela: —   Sem ver nada agora (sem_foco_x)
    O que ele impõe:          —    Nada é limitado
    Perfil ativo:             —    meu_perfil
    8 linhas · nenhum aviso        6 linhas · nenhum aviso
    "Steam Input estava ligado     Steam Input desligado para o DualSense
     em 2 jogos — desliguei"       (e mais cinco, nenhuma igual às do desenho)
    [23:41:02] daemon pronto …     não há registro nenhum sendo lido

As quatro últimas eram o desenho FALANDO PELA MÁQUINA. É o defeito que o
docstring de `gui/aba_sistema.py` nomeia como o mais caro possível nesta aba.

O `Perfil ativo` era pior que falta: **este pacote o APAGAVA.** Ele emitia a
chave `perfil` com o rótulo do PERFIL DE BATERIA, e `perfil` é o endereço do
cabeçalho — o perfil de JOGO, que `pacotes.topo()` pinta nas dez abas com
`setdefault`. Chegando primeiro, o rótulo de bateria (`None`, porque ninguém o
lia) tomava o lugar e o cabeçalho inteiro virava travessão nesta aba.
"""
from __future__ import annotations

import html
import time
from typing import Any

# OS IMPORTS SÃO DE MÓDULO — o portão do `casa-sabe` segue o fecho de IMPORT a
# partir do piloto, e um `from … import` dentro de uma função não entra nele: a
# camada do produto continuava contando como promessa sem caminho mesmo depois
# de eu a ligar. O `sys.path` já tem o `src/` quando esta linha roda.
#
# OS QUATRO DE BAIXO SÃO O MOTOR DESTA ABA, e nenhum deles é novo: são as
# mesmas quatro fontes que o piloto `interface/sistema_viva.py` já lia em
# 31/08 e que o pacote não chamava. Reusar era a única saída honesta — escrever
# aqui um segundo detector de janela, um segundo exame ou uma segunda leitura do
# teto seria a regressão que esta rota existe para não repetir.
from hefesto_dualsense4unix.app.actions import ambiente_na_tela as _ambiente
from hefesto_dualsense4unix.app.actions import daemon_actions as _daemon
from hefesto_dualsense4unix.app.actions.config import secao_orcamento as _orcamento
from hefesto_dualsense4unix.gui import aba_sistema as _tela
from hefesto_dualsense4unix.integrations import storm_doctor as _exame

from . import Contexto, perfil, registrar

#: CORRIGIDO EM 01/09/2026. "versoes" e "consertos" tinham dono e viraram  # (noqa-acento) id
#: pintura. **"plugins" continua sem dono NA TELA, e a razão não é minha** — a
#: `gui/aba_sistema.py:95` já a tinha medido e escrito:
#:
#:     "IPC `plugin.list`/`plugin.reload`. Só a CLI chama
#:      (`cli/cmd_plugin.py`). Não há botão no produto de hoje."
#:
#: O método existe no daemon; o que não existe é quem o chame fora do terminal.
#: Este é o `sem_dono` legítimo desta casa: um valor que a tela mostraria como
#: se funcionasse, e que ninguém atende.
SEM_DONO: dict[str, str] = {
    "plugins": "o IPC `plugin.list` existe e só a CLI o chama — não há botão no "
               "produto de hoje (medido em `gui/aba_sistema.py:95`)",
}

#: O QUE O PRODUTO RESPONDE E ESTA TELA AINDA NÃO SABE ESCREVER — e é OUTRA
#: coisa que `SEM_DONO`. Ali o produto não tem quem atenda; aqui ele atende, e
#: falta o CAMINHO até o pixel. Ficam declarados porque o silêncio sobre eles é
#: o que faz alguém "ligar" duas vezes o que já está lido.
#:
#: Os três dependem de ESCRITA QUE NÃO É TEXTO — a pintura do piloto único
#: (`hefesto_vivo.BOOTSTRAP`) sabe escrever texto, largura, fundo, `value` e
#: `innerHTML`, e nenhum desses três se resolve com nenhum deles:
NAO_CHEGA_NA_TELA: dict[str, str] = {
    "hefesto-autostart": "o valor é a CLASSE `on` de um `<span class=\"chave\">`, "
                         "e a pintura não tem alvo de classe. Escrever texto no "
                         "`data-id` da linha apagaria o próprio interruptor.",
    "bateria-perfil": "o valor é qual dos TRÊS `<button>` leva a classe `on`. "
                      "Mesmo caso, e pior: o endereço é o `<div>` que os contém — "
                      "escrever texto nele apagaria os três botões.",
    "bateria-frase": "está em `aba_sistema.ENDERECOS` e NÃO EXISTE na página: o "
                     "gerador nunca emitiu este endereço, e a frase de "
                     "`frase_do_teto()` vive hoje dentro da dica do `?`.",
}

#: A FAIXA LENTA, e o período é o do `interface/sistema_viva.py` — o piloto de
#: uma aba só que já tinha medido este custo em 31/08 e separado as duas
#: cadências. Medido de novo aqui, em 02/09/2026, nesta máquina:
#:
#:     storm_report              2,374 ms
#:     systemctl is-enabled      1,592 ms
#:     perfil_na_tela            0,061 ms   (lê o `maquina.json` do disco)
#:     descrever_deteccao…       0,001 ms   (só lê o `state` que já veio)
#:     descrever_display_grafico 0,001 ms
#:
#: A 10 Hz as três primeiras seriam 40 ms por segundo de subprocesso e disco
#: para escrever o que não muda entre dois piscares. E o `systemctl` JÁ RODAVA
#: a cada tique antes desta mudança — a faixa lenta o tira de lá, então a aba
#: fica MAIS BARATA depois de ganhar três leituras.
LENTO_S = 2.0

#: `{"quando": monotonic, "valor": (autostart, achados, perfil_da_bateria)}`.
#: Vazio = nunca lido. As réguas o esvaziam para forçar a leitura — é o ponto
#: de injeção, e é por isso que ele não é um `functools.lru_cache`: um cache com
#: prazo que a régua não consegue zerar dá VERDE SOBRE O VALOR DE ANTES.
_LENTO: dict[str, Any] = {}

#: O ENDEREÇO DO PAINEL DE REGISTRO, e ele é o mesmo do gerador
#: (`aba09.py`, `_id("registro-texto")`). Escrito UMA vez aqui porque três
#: donos o usam; digitá-lo três vezes seria a segunda cópia de um fato.
REGISTRO = "registro-texto"

#: OS DOIS ENDEREÇOS DA FITA, e eles têm gêmeos em `aba09.py` — o gerador os
#: escreve na página, este arquivo escreve NELES. `test_aba09_a_fita_vem_de_cima`
#: compara os dois pares e reprova na divergência: escrito duas vezes sem régua,
#: os dois se afastam no dia em que alguém mudar um, e foi assim que a fita viva
#: morreu em silêncio em 27/08.
#:
#: POR QUE O CONJUNTO E NÃO O CHIP: o número de chips é o número de controles na
#: mesa, e não há `data-campo` para um chip que ainda não existe. O `-chips` leva
#: `data-hef-alvo="html"` e recebe o miolo inteiro da `.fita`; o `-chip` de cada
#: um existe porque a régua da identidade julga o `--plastico` pelo endereço do
#: PRÓPRIO elemento — e ela está certa em julgar assim.
CAMPO_DA_FITA = "fita-chips"
CAMPO_DO_CHIP = "fita-chip"

#: O TÍTULO DO CHIP SEM COR LIDA. Ele não nomeia tom nenhum — é a regra dela:
#: *campo sem informação não mostra nada*. Pelo rádio a cor do plástico NÃO
#: CHEGA, e quem diz isso é o mapa de canais (`identidade.cor_do_aparelho`,
#: `radio_aciona = não`), não um `if` decorado aqui.
SEM_COR_LIDA = "A cor do plástico deste controle não foi lida."

#: O QUE O ÚLTIMO "Ver …" PÔS NO PAINEL. `None` = ninguém pediu nada ainda.
#:
#: ELE PRECISOU EXISTIR NO DIA EM QUE A PINTURA ALCANÇOU O PAINEL, e a razão é
#: de relógio: `ver-detalhes` e `ver-plugins` devolvem texto, o piloto o escreve
#: na hora — e 500 ms depois o tique seguinte repintaria o valor de repouso por
#: cima. As oitenta linhas do registro apareceriam e sumiriam antes de ela
#: terminar de ler. Guardando o que foi pedido, a pintura passa a repintar **o
#: mesmo texto**, e o painel para quieto até o próximo clique.
#:
#: Uma lista de um elemento porque quem escreve são os gestos, que rodam noutra
#: thread; o que se troca é o conteúdo, nunca o nome.
_PAINEL: list[str | None] = [None]


def _no_painel(repouso: Any) -> str:
    """O que vai ao painel AGORA: o último pedido, ou o repouso da camada.

    O VALOR DE REPOUSO É DA CAMADA DO PRODUTO (`aba_sistema.pacote`, a chave
    `registro`), e não uma frase minha. Ela decidiu ali que, sem ninguém ter
    pedido, o painel mostra o traço — e o motivo vive em `SEM_FONTE`.

    O QUE ISSO ARRANCA DA TELA, e é o ponto inteiro: enquanto ninguém escrevia
    neste endereço, o painel continuava com as quatro linhas do mockup —
    `[23:41:02] daemon pronto · 2 controles`, `perfil "Mortal Kombat" aplicado
    aos 2`, `gatilho L2 escrito, sem leitura de volta`. Nenhuma delas aconteceu.
    Um registro técnico inventado é a pior espécie de mentira desta aba: ele
    parece a prova.
    """
    guardado = _PAINEL[0]
    if guardado is not None:
        return guardado
    return "—" if repouso is None else str(repouso)


def _para_o_painel(texto: str) -> dict[str, Any]:
    """Guarda o texto E devolve a carga que o piloto escreve na hora.

    AS DUAS COISAS JUNTAS, e por isso uma função em vez de dois passos: separá-las
    é convidar o gesto a devolver sem guardar, e um gesto assim pisca na tela e
    some no tique seguinte — o defeito exato que `_PAINEL` existe para matar.
    """
    _PAINEL[0] = texto
    return {"mesa": {REGISTRO: texto}}


def _versao() -> str:
    try:
        perfil._com_o_src()
        import hefesto_dualsense4unix as h

        return str(getattr(h, "__version__", "") or "")
    except Exception:
        return ""


def _autostart() -> str | None:
    """A saída crua de `systemctl --user is-enabled`. `None` = nem deu para perguntar.

    A UNIT NÃO SE DIGITA — ela tem dono, e digitá-la já mentiu. Medido em
    01/09/2026: esta linha trazia a literal `hefesto-dev-dualsense4unix.service`,
    sobrevivente da purga do `-dev`. A unit com esse nome NÃO EXISTE mais;
    `systemctl --user is-enabled` devolvia `not-found` enquanto a verdade da
    máquina dela era `enabled`. A linha "Ligar junto com o computador" da aba
    Sistema afirmava o contrário do que estava valendo, e nenhuma régua via —
    porque o valor lido era um `str` plausível, não um erro.
    """
    import subprocess

    from hefesto_dualsense4unix.utils import identidade

    try:
        return subprocess.run(
            ["systemctl", "--user", "is-enabled", identidade.atual().unit_daemon],
            capture_output=True, text=True, timeout=3).stdout.strip()
    except Exception:
        return None


def _achados(state: dict[str, Any] | None) -> list[tuple[str, str]] | None:
    """O `storm_report`, que é READ-ONLY por contrato do próprio módulo.

    `None` **não é** lista vazia, e a camada do produto trata os dois de forma
    diferente: `None` vira *"O exame não respondeu"*, e `[]` vira *"O exame não
    achou nada a relatar nesta máquina"*. Engolir a diferença aqui faria uma
    falha de leitura passar por máquina limpa.

    O DENOMINADOR HONESTO vem do `state`: `controles_no_cabo` diz quantos
    controles estão no cabo AGORA, e é ele que decide se a frase do áudio fala
    no singular ou no plural.
    """
    try:
        return _exame.storm_report(controles_no_cabo=_exame.controles_no_cabo(state))
    except Exception:
        return None


def _perfil_da_bateria() -> str | None:
    """A chave do Perfil de Bateria GRAVADA no `maquina.json`, ou `None`.

    O dono é `secao_orcamento.perfil_na_tela`, e ele é o mesmo que o botão da
    janela antiga consulta. `None` quer dizer **ninguém escolheu** — e a nota de
    `PERFIL_POR_TETO` já decidiu que a ausência NÃO afunda "Tudo ligado".
    """
    try:
        return _orcamento.perfil_na_tela()
    except Exception:
        return None


def _faixa_lenta(state: dict[str, Any] | None) -> tuple[Any, Any, Any]:
    """As três leituras CARAS, uma vez a cada :data:`LENTO_S`.

    Elas saem deste processo — subprocesso, disco — e nenhuma muda entre dois
    piscares. O tique da pintura é de 500 ms; a faixa lenta é de 2 s, que é a
    mesma separação que `interface/sistema_viva.py` já tinha medido e escolhido.
    """
    agora = time.monotonic()
    if _LENTO and agora - float(_LENTO["quando"]) < LENTO_S:
        return _LENTO["valor"]  # type: ignore[no-any-return]
    valor = (_autostart(), _achados(state), _perfil_da_bateria())
    _LENTO["quando"], _LENTO["valor"] = agora, valor
    return valor


def _leitura(ctx: Contexto) -> Any:
    """O `Leitura` que a camada do produto espera — os SETE campos, não três.

    Cada campo dele nomeia quem o produz, e o docstring de lá lista todos. O
    que esta função faz é buscá-los; nenhum é calculado aqui.

    ATÉ 02/09/2026 ELA PREENCHIA TRÊS, e os quatro que faltavam não davam erro:
    a camada do produto devolve o traço honesto para `None`. Só que o traço
    NUNCA CHEGAVA À TELA — o pacote não emitia aqueles endereços, e o que ficava
    à vista era o literal do mockup. Um `None` calado aqui virava, três camadas
    adiante, a tela afirmando o desenho.
    """
    perfil._com_o_src()

    auto, achados, perfil_da_bateria = _faixa_lenta(ctx.state or None)
    # `online_systemd` porque o daemon respondeu: se `ctx.state` tem chave, ele
    # está no ar. O `daemon_actions._daemon_status()` distingue avulso de unit,
    # e essa distinção é da janela antiga — aqui o que importa é responder.
    return _tela.Leitura(
        status="online_systemd" if ctx.state else "offline",
        autostart=auto,
        state=ctx.state or None,
        achados=achados,
        # AS DUAS FRASES DO PRODUTO SOBRE O DETECTOR DE JANELA, e elas são
        # diferentes: a da PROMESSA (o perfil troca sozinho?) e a do MECANISMO
        # (por onde ele enxerga). As duas são funções de MÓDULO — nenhuma exige
        # a janela GTK —, e a segunda tinha ZERO chamadores no produto até o
        # `sistema_viva.py`, que ninguém carrega.
        deteccao=_frase(_daemon.descrever_deteccao_de_janela, ctx.state),
        ambiente=_frase(_ambiente.descrever_display_grafico, ctx.state),
        perfil=perfil_da_bateria,
    )


def _frase(fn: Any, state: Any) -> str | None:
    """A frase daquela função do produto, ou `None` quando ela levantou.

    `None` chega à camada de tela como *"ninguém respondeu"*, que é o que a
    pessoa precisa ler. Uma frase inventada aqui seria pior: a tela afirmaria
    um mecanismo que ninguém mediu.
    """
    try:
        return str(fn(state))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# A FITA — a identidade vem de CIMA, e é a lei dela de 03/09/2026:
#
#     "se no topo tá mostrando controle white player 1, então cada aba vai usar
#      os controles lá de cima. Não mistura com a info dos mockups."
#
# O QUE ELA VIU, e foi medido nesta aba com os dois controles dela na mesa:
#
#     o cabeçalho    `2 controles: 1 USB · 1 BT`   <- vivo, certo
#     a fita         `P1 · Cosmic Red · USB`
#                    `P2 · Starlight Blue · BT`    <- OS DOIS DO MOCKUP
#
# A CAUSA MEDIDA: `hefesto_vivo._fita` — o repintor que vale para as dez abas —
# desiste com `any(not c.get("cor") for c in mesa)`. No cabo isso é a espera de
# poucos tiques até a leitura voltar; **pelo rádio a cor NUNCA chega**, e quem
# diz isso é o mapa de canais (`identidade.cor_do_aparelho`, `radio_aciona =
# não`). Com um controle no rádio a guarda é permanente: a fita das dez páginas
# não repinta nunca, e o desenho fala pela máquina para sempre.
#
# ESTA ABA PASSA A ESCREVER A SUA. `hefesto_vivo._fita` é território de todas as
# dez e não é meu; o que é meu é o `data-campo` que o `aba09.py` põe na `.fita`
# desta página e o valor que sai daqui. Quando o repintor comum voltar a
# funcionar, os dois escrevem a MESMA coisa a partir da MESMA mesa — não há
# terceira verdade a divergir.
# ---------------------------------------------------------------------------
def _monta() -> Any:
    """O módulo `interface/monta.py`, importável de dentro do pacote.

    ELE PRECISA DE UM APELIDO, e não é capricho: `monta.py` faz `import onde`
    CRU — nasceu como script de gerador, e naquele contexto a pasta `interface/`
    é o `sys.path[0]`. Importado como módulo de pacote ele levanta
    `ModuleNotFoundError: No module named 'onde'`, medido em 03/09/2026. O
    `hefesto_vivo._fita` só escapa disso porque roda COMO script, de dentro
    daquela pasta.

    O APELIDO É EM `sys.modules`, NUNCA UM `sys.path.insert`. Pôr a pasta
    `interface/` no caminho de busca deixaria `casamento`, `mapa`, `regua`,
    `ver` e mais vinte nomes curtos visíveis como módulos de topo para todo o
    processo — e contaminação entre testes é o defeito mais caro de diagnosticar
    que existe. O apelido alcança UM nome, que é o único que falta.
    """
    import sys

    from hefesto_dualsense4unix.interface import onde as _onde

    sys.modules.setdefault("onde", _onde)
    from hefesto_dualsense4unix.interface import monta

    return monta


def _cor_da_zona(colorway: str) -> str:
    """O hex do plástico daquele modelo, LIDO de quem é dono dele.

    O dono é `interface/monta.cor_da_zona`, que por sua vez lê a folha que
    PINTA o desenho (`assets/ds_limpo.svg`, escrita por
    `scripts/gerar_cores_do_dualsense.py`). Digitar um hex aqui seria a segunda
    verdade que o portão `check_cores_do_dualsense.py` existe para matar — e foi
    assim que o Cosmic Red do mockup ficou `#b11f54` enquanto a amostragem dizia
    `#A51C48`.
    """
    return str(_monta().cor_da_zona(colorway))


def _rotulo_da_fita() -> str:
    """`Selecionar:` — o rótulo, lido de `monta.ROTULO_DA_FITA`.

    Decisão dela, 31/08/2026: *"aqui pode alterar pra colocar o **Selecionar:**
    em todas as abas."* Ele mora no `monta` porque é `monta.fita()` que emite a
    tira nas dez páginas; escrevê-lo de novo aqui faria as duas divergirem no dia
    em que ela mudar a palavra.
    """
    try:
        return str(_monta().ROTULO_DA_FITA)
    except Exception:
        # O RÓTULO NÃO PODE DERRUBAR A FITA. Se o `monta` não importar, o que se
        # perde é uma palavra de enfeite; o que NÃO se pode perder é a
        # identidade dos controles, que é o ponto inteiro desta função vizinha.
        return ""


def _um_chip(c: dict[str, Any]) -> str:
    """Um chip da fita, com o que se LEU daquele controle — e nada mais.

    A COR SÓ APARECE SE ALGUÉM A LEU. Sem leitura o chip perde a classe
    `plastico` (e com ela a borda colorida), perde o `--plastico` e perde o nome:
    é a regra dela, *campo sem informação não mostra nada*. Inventar um tom para
    preencher seria repetir o defeito que esta frente veio matar, só que com
    outra cor.

    E O QUE SAI NÃO É `Não sei` NEM `—`: os dois são a AUSÊNCIA de leitura
    escrita como se fosse um nome. O chip termina no transporte.
    """
    nome = str(c.get("nome") or "")
    cor = str(c.get("cor") or "")
    via = html.escape(str(c.get("via") or ""))
    jogador = html.escape(str(c.get("jogador") or ""))
    ponto = ' <span class="pt">•</span> '
    if not cor:
        return (f'<span class="chip" data-campo="{CAMPO_DO_CHIP}"'
                f' title="{html.escape(SEM_COR_LIDA)}">'
                f"P{jogador}{ponto}{via}</span>")
    return (f'<span class="chip plastico" data-campo="{CAMPO_DO_CHIP}"'
            f' style="--plastico:{html.escape(_cor_da_zona(cor))}"'
            f' title="{html.escape(nome)} — a borda é a cor do plástico">'
            f"P{jogador}{ponto}{html.escape(nome)}{ponto}{via}</span>")


def _html_da_fita(mesa: list[dict[str, Any]]) -> str:
    """O miolo da `.fita` desta aba, montado com a mesa VIVA.

    Devolve `""` com a mesa vazia, e o `pacote()` então NÃO emite a chave — o
    alvo `html` da pintura escreve `—` quando recebe vazio (`hefesto_vivo`, o
    `const t = vazio ? '—' : String(v)`), e isso apagaria a tira inteira entre
    uma reconexão e outra.

    O CHIP `Todos` FICA E NÃO GANHA ENDEREÇO: ele não é aparelho nenhum, não traz
    cor nem nome de plástico. Nesta aba a fita é INERTE — o `title` do desenho já
    diz que aqui os cards são leitura —, então `Todos` continua sendo o escolhido.
    """
    if not mesa:
        return ""
    partes = [f"<span>{html.escape(_rotulo_da_fita())}</span>",
              '<span class="chip on">Todos</span>']
    partes += [_um_chip(c) for c in mesa]
    return "\n      ".join(partes)


@registrar("09-sistema.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    """DELEGA para `gui/aba_sistema.pacote` — a camada do PRODUTO.

    ELA JÁ EXISTIA E NUNCA TINHA SIDO LIGADA: dezoito nomes públicos em
    `gui/aba_sistema.py`, e o `casa-sabe` os listava como promessa sem caminho.
    E ela foi escrita PARA ESTA PÁGINA — as chaves que devolve são os
    `data-campo` daqui: `hefesto-estado`, `hefesto-pausa`,
    `hefesto-troca-de-perfil`, `hefesto-ambiente`.

    E SABE MAIS QUE O QUE EU TINHA ESCRITO: cada valor vem com `txt`, a classe
    do selo (`cls`), o glifo (`g`) e a dica. Meu pacote só tinha o texto — e as
    frases dele eram minhas, enquanto estas foram escritas com ela.

    O QUE ELE EMITE É O ENDEREÇO DA PÁGINA, E NADA MAIS — 02/09/2026. Antes
    saíam quatro chaves com o nome que a CAMADA usa (`frase`, `autostart`,
    `perfil`, `registro`), e nenhuma delas é endereço desta tela. Três eram
    órfãs inofensivas; a quarta era um estrago:

        `perfil` É O CABEÇALHO DAS DEZ ABAS — o perfil de JOGO, que
        `pacotes.topo()` pinta com `setdefault`. Este pacote o emitia com o
        rótulo do PERFIL DE BATERIA, que ninguém lia e portanto era `None`.
        Chegando primeiro, tomava o lugar, e o cabeçalho da aba Sistema virava
        `Perfil ativo —` com o daemon publicando `active_profile: 'meu_perfil'`.
        Fotografado em 02/09/2026 às 04:23.

    A regra que fica: **um pacote de aba só emite endereço DAQUELA página.** O
    que é de todas é do dono compartilhado, e um nome curto e genérico
    (`perfil`, `conta`, `estado`) é do dono compartilhado até prova contrária.
    """
    perfil._com_o_src()

    try:
        bruto = _tela.pacote(_leitura(ctx))
    except Exception as erro:
        return {"sem_dono": {"tela": {"sem_dono": True, "oque": str(erro)}},
                "cobertura": {"pintados": 0, "sem_dono": 1}}

    fora: dict[str, object] = {}
    for chave, v in (bruto.get("valores") or {}).items():
        # O ACHATAMENTO: a camada devolve `{"txt": …, "cls": …}` e a tela
        # endereça o texto. A classe e o glifo são pintura de estado, e ficam
        # para quem os quiser — o `-cls` e o `-g` são endereços novos.
        if isinstance(v, dict):
            fora[chave] = v.get("txt", "—")
            fora[f"{chave}-cls"] = v.get("cls", "")
        else:
            fora[chave] = v
    registro = bruto.get("registro")
    fora[REGISTRO] = _no_painel(
        registro.get("txt") if isinstance(registro, dict) else registro)
    exame = bruto.get("exame")
    if isinstance(exame, dict):
        fora["exame-contagem"] = _html_da_contagem(exame.get("contagem"))
        fora["exame-lista"] = _html_do_exame(exame)
    # A FITA DESTA ABA, e ela sai da MESA — nunca do desenho. Só entra quando há
    # o que escrever: uma string vazia vira `—` no alvo `html` e apagaria a tira.
    tira = _html_da_fita(ctx.mesa)
    if tira:
        fora[CAMPO_DA_FITA] = tira
    fora["sem_dono"] = {k: {"sem_dono": True, "oque": v} for k, v in SEM_DONO.items()}
    fora["cobertura"] = {"pintados": len(fora), "sem_dono": len(SEM_DONO)}
    return fora


# ---------------------------------------------------------------------------
# O EXAME — a lista inteira, e por que ela vai como HTML
# ---------------------------------------------------------------------------
# O NÚMERO DE LINHAS É DO DADO, e o desenho tem oito. `storm_report` devolveu
# SEIS na máquina dela em 02/09/2026, e as duas condicionais dele devolvem
# `None` quando não há o que dizer — logo o número varia. Não há como pintar
# campo a campo o que não tem endereço fixo: não existe `data-campo` para uma
# linha que ainda não existe.
#
# POR QUE NÃO O `blocos:`, QUE SERIA O CAMINHO ÓBVIO — e isto é um achado, não
# uma escolha: `pacotes.normalizar()` DESCARTA todo valor `dict`, e `blocos` é
# um `dict`. Medido em 02/09/2026:
#
#     >>> pacotes.normalizar({'blocos': {'.x': '<b>1</b>'}, 'a': 1})
#     {'mesa': {'a': 1}, 'colunas': {}}
#
# O piloto tem o mecanismo (`hefesto_vivo.BOOTSTRAP`, o laço sobre `p.blocos`),
# e a `a08_conexoes.py:763` já o usa para o mapa do gabinete — que portanto
# TAMBÉM não chega à tela. O conserto é uma linha em `pacotes/__init__.py`, que
# é território compartilhado e não é meu; está no relatório desta frente.
#
# O que sobra e FUNCIONA hoje é o alvo `html` da pintura por `data-campo`: uma
# STRING atravessa o `normalizar` intacta, e `data-hef-alvo="html"` a escreve
# como `innerHTML`. É o que o gerador desta aba passou a marcar.
def _html_do_exame(exame: dict[str, Any]) -> str:
    """As duas colunas de achados, prontas para o `innerHTML` de `.saude-cols`.

    A FORMA É A DO PRODUTO, e não uma terceira: cada linha sai com o selo, o
    glifo e a frase, na mesma marcação que `interface/sistema_viva.py` monta no
    JS dele (`achado()`), e o corte em duas colunas é o mesmo `ceil(len/2)` que
    o gerador usa. O que fica de fora é o `?` do desenho — as explicações longas
    do mockup foram escritas à mão para os achados DE BANCADA, e `storm_report`
    não devolve nenhuma. Inventá-las aqui seria escrever no lugar dela.
    """
    linhas = exame.get("linhas") or []
    if not linhas:
        # O VAZIO TAMBÉM É UM ACHADO, e a camada do produto já escreveu os dois
        # textos possíveis — o "não respondeu" e o "não achou nada". Um painel
        # em branco faria os dois parecerem a mesma coisa.
        vazio = html.escape(str(exame.get("vazio") or ""))
        return ('<div class="col-lista"><div class="saude" style="color:var(--texto-mudo)">'
                f'<span class="txt"><span>{vazio}</span></span></div></div>'
                '<div class="risco"></div><div class="col-lista"></div>')
    meio = (len(linhas) + 1) // 2
    return (f'<div class="col-lista">{"".join(_linha_do_exame(a) for a in linhas[:meio])}</div>'
            '<div class="risco"></div>'
            f'<div class="col-lista">{"".join(_linha_do_exame(a) for a in linhas[meio:])}</div>')


def _linha_do_exame(achado: dict[str, Any]) -> str:
    """Uma linha do exame. Tudo escapado: a frase vem do `doctor`, não daqui."""
    cls = html.escape(str(achado.get("cls") or "nt"))
    return (f'<div class="saude"><span class="selo {cls}">'
            f'<span class="sg">{html.escape(str(achado.get("g") or ""))}</span>'
            f'{html.escape(str(achado.get("selo") or ""))}</span>'
            f'<span class="txt"><span>{html.escape(str(achado.get("txt") or ""))}</span>'
            "</span></div>")


def _html_da_contagem(texto: Any) -> str:
    """`6 linhas · nenhum aviso` com o `·` de volta no `<span class="sep">`.

    A FRASE É DA CAMADA DO PRODUTO (`aba_sistema.exame`), que a deriva da lista
    — o "8" do desenho é literal de bancada e seria falso na primeira máquina
    que não tivesse oito. O que se faz aqui é devolver ao separador a classe que
    o desenho lhe deu; escrever a frase como texto puro apagaria o `<span>` e
    mudaria a cor do `·` na tela dela.
    """
    if not texto:
        return ""
    return html.escape(str(texto)).replace(" · ", ' <span class="sep">·</span> ')




# ---------------------------------------------------------------------------
# OS GESTOS — ver o exemplo comentado em `a04_iluminacao.py`
# ---------------------------------------------------------------------------
from . import gesto  # noqa: E402


@gesto("09-sistema.html", "retomar")
def retomar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Sair da pausa. `daemon.resume`.

    ELE TINHA UM CHAMADOR EM TODO O `src/` — o terminal (`cli/app.py:421`), como
    a `gui/aba_sistema.py:77` já tinha medido: *"a pausa fica gravada em disco e
    sobrevive a desligar o computador; até hoje só o terminal saía dela."* Este
    é o segundo, e é uma tela.
    """
    # `daemon.resume` não tem função no `ipc_bridge` — é o degrau 3 da ponte, e
    # passa pelo mesmo `_safe_call`, com o mesmo timeout do resto do produto.
    p.chamar("daemon.resume")


@gesto("09-sistema.html", "atualizar")
def atualizar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Recarregar a configuração. `daemon.reload`.

    ELE LEVA 9,5 SEGUNDOS, medido no daemon dela em 01/09/2026 — contra 1 ms do
    `daemon.resume` e 57 ms do `daemon.status`. É a razão de os gestos rodarem em
    thread: síncrono, este botão congelaria a janela inteira por nove segundos e
    meio, e quem clicou concluiria que o app travou.
    """
    p.chamar("daemon.reload")


def _teto_do_perfil(escolha: str) -> str | None:
    """O que aquele botão grava em DISCO. Lido do produto, nunca digitado.

    `TETO_POR_PERFIL` (`app/actions/config/secao_orcamento.py:137`) é o dono da
    tradução botão → disco, e ela não é óbvia: `tudo_ligado` grava
    `"balanceado"` e não `"max"` (os dois devolvem o mesmo teto, e `balanceado`
    é o nome que a aba Vibração já usa), `bateria_longa` grava `"economia"`, e
    `eu_escolho` grava `None` — a AUSÊNCIA de teto de mesa.

    **O `None` não é "não mandar a chave", e a diferença decide o botão.** O
    `fundir_declaracao` (`utils/maquina.py:650`) documenta as duas: *"`None`
    presente na declaração é uma escolha e SOBRESCREVE. Só a AUSÊNCIA da chave
    preserva o que havia."* Omitir a chave no "Eu escolho" deixaria o teto
    antigo em disco com o botão aceso dizendo que não há teto.

    `KeyError` de propósito num `data-v` que não é perfil: gravar um teto que
    ninguém escolheu é pior que o gesto cair dizendo o nome.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.actions.config.secao_orcamento import (
        TETO_POR_PERFIL,
    )

    return TETO_POR_PERFIL[escolha]


def _ok_e_motivo(resposta: Any) -> tuple[bool, str | None]:
    """`(ok, motivo)`, seja tupla ou `bool` o que a ponte devolveu.

    O `ipc_bridge.machine_declare:861` devolve `(ok, motivo)` com o motivo já
    traduzido para frase de tela (`_MOTIVOS_MAQUINA`), e ele é o ponto do botão:
    `versao_desconhecida` quer dizer *"não gravei nada, e os bytes ficaram
    intactos"* — o botão aceso na tela passaria a mentir. Um gesto que descarta
    o retorno perde exatamente isso e vira o botão que responde calado.

    A TOLERÂNCIA AO `bool` NÃO É ENFEITE: o dublê da régua
    (`tests/unit/test_os_botoes_tem_dono.py`, `PonteDeMentira.__getattr__`)
    devolve a dupla só para `identity…_set` e `True` para todo o resto. Sem esta
    função o gesto rebentaria com `TypeError` na régua e funcionaria na mão dela
    — a régua reprovando a cura, que é a forma de defeito que esta casa já pagou
    onze vezes em 26/08.
    """
    if isinstance(resposta, tuple) and len(resposta) == 2:
        return bool(resposta[0]), resposta[1]
    return bool(resposta), None


@gesto("09-sistema.html", "perfil-da-mesa")
def perfil_da_mesa(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Os três botões do Perfil de Bateria. `machine.declare`, e vale AGORA.

    POR QUE `machine.declare` E NÃO `rumble.policy_set`, que seria o palpite: o
    teto da MESA e a política de vibração são dois donos diferentes. O
    `_effective_mult` (`core/rumble.py:185`) lê os dois e aplica `min` entre
    eles — `_sob_o_teto`, nunca produto —, então gravar a escolha dela como
    política apagaria a política por controle que as outras abas escrevem. Quem
    é dono desta escolha é o `orcamento.teto` do `maquina.json`, e o contrato do
    produto diz o mesmo: `gui/aba_sistema.GESTOS["perfil-da-mesa"]` aponta para
    `secao_orcamento._ao_escolher:468`, que monta `{"orcamento": {"teto": …}}`.

    O QUE MUDA EM RELAÇÃO À JANELA ANTIGA, e é decisão dela: lá o
    `_ao_escolher` **não manda IPC** — acumula em `host._maquina_pendente` e só o
    "Aplicar" do rodapé grava (`footer_actions.py:353`). Aqui vale a regra de
    01/09: *"clicar na cor já deveria aplicar"*. O gesto age na hora, e o
    caminho é o MESMO que aquele "Aplicar" usa — `machine_declare_detalhado`, do
    `ipc_bridge`. Não é uma segunda porta para o disco.

    E ELE PEGA NA HORA, sem reiniciar nada: o `_handle_machine_declare`
    (`daemon/ipc_handlers.py:5324`) relê o `maquina.json` e **rebinda**
    `daemon._maquina`; o `_orcamento_declarado` (`core/rumble.py:105`) lê a
    fonte a cada pedido de vibração, e não uma cópia do boot. Está escrito lá
    com todas as letras: *"uma cópia feita no boot ficaria velha exatamente no
    instante em que ela acabou de escolher"*.

    A declaração é PARCIAL de propósito. O daemon funde contra o disco sob lock
    (`gravar_maquina_com_descartes:753`), então mandar só o orçamento não apaga
    a mesa, os controles nem o mapa que as outras seções declararam.
    """
    escolha = str(o.get("v") or "")
    if not escolha:
        raise ValueError(
            "perfil-da-mesa: o clique não disse qual dos três perfis. O botão "
            "manda `data-v` — se ele voltou a ser `data-perfil`, o piloto não o "
            "encaminha e os três viram o mesmo clique.")
    try:
        teto = _teto_do_perfil(escolha)
    except KeyError:
        raise ValueError(
            f"perfil-da-mesa: {escolha!r} não é perfil do produto. Os que existem "
            f"estão em `secao_orcamento.PERFIS`.") from None
    ok, motivo = _ok_e_motivo(p.machine_declare({"orcamento": {"teto": teto}}))
    if not ok:
        raise RuntimeError(motivo or "não consegui gravar o perfil da mesa")


@gesto("09-sistema.html", "ver-plugins")
def ver_plugins(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """Relê os plugins do disco e ESCREVE a lista no painel de registro.

    O daemon atende os dois métodos desde sempre (`ipc_server.py:184-185`); o
    que faltava era o caminho de volta, e ele nasceu em 01/09/2026 — um gesto
    pode devolver a mesma carga que a pintura consome, e o piloto a escreve.

    A ORDEM É RELER E DEPOIS LISTAR, e não o contrário: o botão promete *"Lista
    os plugins do daemon e relê"*, e listar antes de reler mostraria o estado
    VELHO — quem clicou depois de mexer num plugin leria a lista de antes e
    concluiria que o arquivo dele não foi visto.

    QUANDO NÃO HÁ PLUGINS a página diz isso com todas as letras, e diz o
    porquê: `_handle_plugin_list` devolve `[]` tanto quando o subsistema está
    desligado quanto quando ele está ligado e vazio. Um "Nenhum plugin" seco
    faria as duas situações parecerem a mesma.
    """
    releu = p.chamar("plugin.reload")
    lista = p.resultado("plugin.list")
    itens = lista if isinstance(lista, list) else []
    if not itens:
        motivo = ("os plugins estão ligados e não há nenhum no diretório"
                  if releu else "os plugins não estão habilitados neste daemon")
        return _para_o_painel(f"Nenhum plugin carregado — {motivo}.")
    linhas = [f"{len(itens)} plugin(s) carregado(s)" + ("" if releu else " · a releitura falhou")]
    for it in itens:
        d = it if isinstance(it, dict) else {}
        nome = str(d.get("name") or d.get("nome") or "?")
        estado = "desligado" if d.get("disabled") else "ligado"
        casa = str(d.get("profile_match") or "todos os perfis")
        linhas.append(f"  {nome} · {estado} · {casa}")
    return _para_o_painel("\n".join(linhas))


@gesto("09-sistema.html", "ver-detalhes")
def ver_detalhes(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """As últimas 80 linhas do registro técnico, no painel ao lado.

    NÃO É IPC, E NÃO PRECISA SER: o daemon não tem método de log, mas o registro
    dele é o journal da unit do USUÁRIO — `journalctl --user` o lê sem sudo e
    sem helper privilegiado. A nota que dizia *"ligá-lo da tela exige o helper
    privilegiado"* estava errada e saiu; medido em 01/09/2026 nesta máquina.

    A UNIT NÃO SE DIGITA. Ela vem de `utils/identidade`, pelo mesmo motivo que a
    leitura do autostart passou a vir: a literal do `-dev` sobreviveu à purga
    num lugar e fez a tela afirmar `not-found` sobre uma unit `enabled`.
    """
    import subprocess

    from hefesto_dualsense4unix.utils import identidade

    unidade = identidade.atual().unit_daemon
    try:
        saida = subprocess.run(
            # `--output cat` É A LINHA DO DAEMON, e nada mais. O padrão
            # (`short-precise`) prefixa cada linha com data, host e
            # `unidade[pid]:` — 62 colunas antes da primeira letra da mensagem.
            # Fotografado em 01/09/2026: no painel de 110px o prefixo ocupava a
            # largura inteira e a mensagem saía pela direita, fora da vista.
            # E ele seria um SEGUNDO carimbo de tempo: o daemon já escreve o
            # dele (`2026-09-01T15:34:02.460365 [info ] …`), que é o que a
            # pessoa precisa para casar a linha com o que ela fez.
            ["journalctl", "--user", "-u", unidade, "-n", "80",
             "--no-pager", "--output", "cat"],
            capture_output=True, text=True, timeout=8)
    except Exception as erro:  # a frase de tela precisa do motivo, e ele vem do erro
        return _para_o_painel(f"Não consegui ler o registro de {unidade}: {erro}")
    texto = (saida.stdout or "").strip()
    if not texto:
        # O `stderr` É A FRASE, e não um "sem linhas" nosso: `journalctl` diz
        # por que não deu — unit inexistente, sem permissão, journal vazio — e
        # inventar um texto aqui apagaria a única pista de quem clicou.
        texto = (saida.stderr or "").strip() or f"O registro de {unidade} está vazio."
    return _para_o_painel(texto)


#: OS SETE QUE NÃO SÃO IPC, e por isso não estão aqui. Medidos no fonte em
#: 01/09/2026, um a um — a linha de cada um está no relato da leva:
#:
#:   `reiniciar`            `systemctl --user restart` (daemon_actions.py:2277)
#:   `desligar`             `_run_systemctl_async("stop")` (daemon_actions.py:2234)
#:   `autostart`            `systemctl --user enable/disable` (…:2398)
#:   `refazer-consertos`    `bash scripts/*.sh` (…:1218)
#:   `refazer-proton`       diálogo GTK + `config.vdf` da Steam (…:1793)
#:   `procurar-camadas`     censo do `system.reg` em disco (emulation_actions.py:2075)
#:   `restaurar-de-fabrica` cópia do asset + `DraftConfig` (footer_actions.py:1477)
#:
#: ERAM OITO. `ver-detalhes` saiu desta lista em 01/09/2026, e a nota que o
#: mantinha aqui estava errada: ela dizia que ligá-lo *"exige o helper
#: privilegiado ou um método de log que o daemon não tem"*. O registro do daemon
#: é o journal de uma unit do USUÁRIO — `journalctl --user` o lê sem sudo.
#: `ver-plugins` saiu junto, pelo caminho de volta que nasceu no mesmo dia.
PONTE = {"chamar", "machine_declare", "resultado"}
METODOS = {"daemon.resume", "daemon.reload", "machine.declare",
           "plugin.reload", "plugin.list"}


PAGINA = "09-sistema.html"
PISO_DA_ABA = 5
PROVAS = [
    {"pagina": PAGINA, "gesto": "retomar", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["daemon.resume"], {})]},
    {"pagina": PAGINA, "gesto": "atualizar", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["daemon.reload"], {})]},
    # A CHAVE DE DISCO NÃO SE DIGITA NA PROVA. Se a prova dissesse `"economia"`
    # e alguém trocasse a tradução no produto, a régua continuaria verde
    # cobrando o valor VELHO — a régua virando o segundo dono do fato que ela
    # existe para medir.
    {"pagina": PAGINA, "gesto": "perfil-da-mesa",  # (noqa-acento) id
     "clique": {"v": "bateria_longa"},
     "chama": [("machine_declare",
                [{"orcamento": {"teto": _teto_do_perfil("bateria_longa")}}], {})]},
    # O "Eu escolho" grava `None` PRESENTE, e é a prova de que a ausência de
    # teto viaja como escolha e não como omissão.
    {"pagina": PAGINA, "gesto": "perfil-da-mesa", "clique": {"v": "eu_escolho"},  # (noqa-acento) id
     "chama": [("machine_declare",
                [{"orcamento": {"teto": _teto_do_perfil("eu_escolho")}}], {})]},
    # RELER E DEPOIS LISTAR, nesta ordem — e a ordem é o que a prova cobra.
    # Listar antes de reler mostraria o estado velho, e quem clicou depois de
    # mexer num plugin leria a lista de antes.
    {"pagina": PAGINA, "gesto": "ver-plugins", "clique": {},  # (noqa-acento) id
     "chama": [("chamar", ["plugin.reload"], {}),
               ("resultado", ["plugin.list"], {})]},
]

#: OS TRÊS CUJO EFEITO O `state_full` NÃO MOSTRA, e cada um por um motivo:
#:
#:   atualizar       `daemon.reload` relê a configuração — o estado publicado
#:                   fica igual quando nada no disco mudou, e é o certo.
#:   perfil-da-mesa  grava `orcamento.teto` no `maquina.json`, não no daemon.
#:   retomar         `daemon.resume` num daemon que não está pausado é no-op.
#:                   Ele TEM eco — provado em 01/09: com `paused=True`, o clique
#:                   o levou a `False`. A régua o clica sem pausar antes, e é
#:                   por isso que ele entra aqui.
#:
#: OS DOIS QUE MOSTRAM entram aqui por outra razão, e ela é de espécie: eles não
#: MUDAM o daemon, LEEM. `state_full` não teria o que ecoar mesmo que tudo
#: funcionasse — o efeito deles é a tela, e quem os mede é
#: `test_o_gesto_devolve_para_a_tela.py`.
SEM_ECO = ("atualizar", "perfil-da-mesa", "retomar", "ver-plugins", "ver-detalhes")
