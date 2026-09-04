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
import re
import threading
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
from hefesto_dualsense4unix.interface import onde as _onde

from . import (
    TRAVESSAO,
    VIA_DO_TRANSPORTE,
    Contexto,
    identidade_de,
    jogador_de,
    perfil,
    registrar,
)

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
#: OS DOIS PRIMEIROS SAÍRAM EM 03/09/2026, e a nota que os segurava estava
#: CADUCA — não errada quando foi escrita, caduca. Ela dizia *"a pintura não tem
#: alvo de classe"*, e o piloto único ganhou o alvo `classe` em 02/09
#: (`hefesto_vivo.escrever`, o ramo `if(alvo === 'classe')`). O que faltava
#: passou a ser só o endereço na página e a emissão aqui — as duas metades
#: entram juntas neste commit.
NAO_CHEGA_NA_TELA: dict[str, str] = {
    "bateria-frase": "está em `aba_sistema.ENDERECOS` e NÃO EXISTE na página: o "
                     "gerador nunca emitiu este endereço, e a frase de "
                     "`frase_do_teto()` vive hoje dentro da dica do `?`.",
}

#: O QUE O PACOTE EMITE E A PÁGINA NÃO TEM ONDE RECEBER — e é OUTRA espécie que
#: `NAO_CHEGA_NA_TELA`. Ali o valor NÃO PODE ser emitido (escrevê-lo apagaria o
#: widget que mora no endereço); aqui ele é emitido e cai no vazio, sem estrago:
#: o `achar()` do piloto devolve zero elementos e a pintura não conta nada.
#:
#: A CLASSE DA LINHA (`est ok` / `est warn` / `est info`) é o caso, e a razão é
#: de mecanismo: o alvo `classe` do piloto acende UMA classe por elemento, e a
#: linha de estado tem TRÊS, mutuamente exclusivas, no mesmo `<div>`. Não há
#: caminho no piloto de hoje que apague `ok` e acenda `warn` na mesma travessia.
#:
#: O QUE ISSO CUSTA NA TELA DELA, fotografado em 03/09/2026 às 04:26: a linha
#: "Trocar de perfil ao abrir o jogo" mostra o valor **Sem ver a janela agora**
#: em VERDE, porque a cor vem da classe congelada do desenho. O glifo ao lado
#: passou a ser pintado hoje (`-g`), então a leitura por SÍMBOLO já está certa;
#: o que sobra é a cor.
#:
#: O PREÇO MEDIDO, e ele é MAIOR do que a linha acima diz — 03/09/2026, nos
#: pixels da foto do produto com os dois controles na mesa:
#:
#:     linha                            glifo                    valor
#:     O serviço está                   ✓  verde                 Ligado   verde
#:     Pausado                          ✓  LARANJA (255,184,108) Não      laranja
#:     Trocar de perfil ao abrir o jogo  !  VERDE   (78,244,120)  Sem ver… verde
#:     Como ele enxerga a janela        ◆  ciano                  …        branco
#:
#: Um **`✓` em cor de alarme** e um **`!` em cor de OK** — duas linhas que se
#: contradizem DENTRO DE SI MESMAS. E o `?` desta aba promete que o selo carrega
#: símbolo E cor ao mesmo tempo *para quem não distingue verde de laranja ler o
#: estado pelo desenho*: hoje as duas leituras que ele oferece se desmentem.
#: A cura de 03/09 (o `-g`) MUDOU A MENTIRA DE LUGAR — antes o glifo mentia e a
#: cor acertava; agora é o contrário —, e é por isso que a metade que falta não
#: é um acabamento.
#:
#: A CURA TEM DOIS CAMINHOS E OS DOIS SÃO DE FORA DESTA ABA: ou o piloto ganha um
#: alvo que troque uma classe DENTRO DE UM CONJUNTO — `data-hef-classe="ok warn
#: info"` sem `data-hef-quando`, e o valor pintado É o nome da classe que fica;
#: `data-hef-classe` já está em `check_o_desenho_aprovado.INVISIVEIS`, logo o
#: `--publicar-enderecos 09` levaria os seis sem tocar no desenho dela —, ou o
#: desenho para de pintar a cor pela classe da linha, e esse é decisão dela.
SEM_ALVO_NA_PAGINA: dict[str, str] = {
    f"{linha}-cls": "a linha tem TRÊS classes exclusivas (`ok`/`warn`/`info`) e "
                    "o alvo `classe` do piloto acende UMA."
    for linha in ("hefesto-estado", "hefesto-pausa", "hefesto-troca-de-perfil",
                  "hefesto-ambiente", "bateria-impoe", "bateria-vale-para")
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
#: *campo sem informação não mostra nada*.
#:
#: FATO ERRADO, SUBSTITUÍDO (03/09/2026). Esta nota dizia *"pelo rádio a cor do
#: plástico NÃO CHEGA, e quem diz isso é o mapa de canais
#: (`identidade.cor_do_aparelho`, `radio_aciona = não`)"*. **O mapa diz o
#: contrário**, e desde 02/09: `mesa_viva.aciona("identidade.cor_do_aparelho",
#: …)` devolve `("sim", "sim")` — o par é cabo e rádio. A linha 111 do
#: `docs/data/mapa-controles.csv` foi corrigida naquele dia pelo próprio
#: produto, que leu `04` = Galactic Purple **por rádio** em 13,6 ms; o que muda
#: no rádio é o CRC do pedido, não a resposta.
#:
#: O QUE NÃO CHEGA PELO RÁDIO É O SERIAL PUBLICADO NO `state_full` — ver
#: :data:`SEM_SERIAL_LIDO` —, e com ele o `modelo` que o daemon decodifica. Os
#: dois fatos vinham sendo tratados como um só, e é por isso que um controle de
#: rádio ANÔNIMO parecia correto a quem olhasse. Ele não é: a cor é legível, e a
#: mesa a lê.
#:
#: A ausência que este título cobre continua existindo (o leitor ainda não
#: respondeu, ou respondeu `None`) — o que ela NÃO é mais é uma sentença do
#: transporte.
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


def _unidade() -> str:
    """O nome da unit do daemon, do DONO dela — nunca digitado.

    O dono é `daemon/service_install.SERVICE_NORMAL`, que por sua vez sai de
    `utils.identidade`. Pedi-lo a `daemon_actions` (que só o importa) funciona em
    execução e o `mypy` recusa, com razão:

        error: Module "…daemon_actions" does not explicitly export attribute
        "SERVICE_NORMAL"  [attr-defined]

    E a razão dele é a mesma desta casa: um nome tem UM dono, e pedir a quem só
    reexporta é o começo de duas verdades. A literal do `-dev` que sobreviveu à
    purga e fez esta aba afirmar `not-found` sobre uma unit `enabled` já cobrou
    essa lição em 01/09.
    """
    from hefesto_dualsense4unix.daemon.service_install import SERVICE_NORMAL

    return str(SERVICE_NORMAL)


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


def _achados(state: dict[str, Any] | None,
             pode_perguntar: bool = True) -> list[tuple[str, str]] | None:
    """O `storm_report` MAIS os dois achados condicionais da janela antiga.

    `None` **não é** lista vazia, e a camada do produto trata os dois de forma
    diferente: `None` vira *"O exame não respondeu"*, e `[]` vira *"O exame não
    achou nada a relatar nesta máquina"*. Engolir a diferença aqui faria uma
    falha de leitura passar por máquina limpa.

    O DENOMINADOR HONESTO vem do `state`: `controles_no_cabo` diz quantos
    controles estão no cabo AGORA, e é ele que decide se a frase do áudio fala
    no singular ou no plural.

    OS DOIS QUE FALTAVAM — 03/09/2026, e por isso o exame desta tela era 6/8 do
    exame da GTK. `_refresh_storm_diag` (`daemon_actions.py:1136` e `:1145`)
    acrescenta ao `storm_report` mais dois achados, e os dois só FALAM QUANDO HÁ
    PROBLEMA (devolvem `None` quando está tudo bem — decisão dela de 22/08/2026
    para o vigia do Steam Input):

    * `medir_guarda_do_steam_input()` — o vigia morto. **2,8 ms**, entra aqui;
    * `medir_prontuario_dos_jogos()` — divergência entre os manifestos da Steam
      e os perfis do disco. **7,1 s**, e por isso NÃO entra aqui — ver
      :func:`_prontuario`.

    Medido por grep antes de ligar: as duas funções tinham UM chamador em toda a
    árvore, e era a GTK. São funções de MÓDULO — não pedem janela, não pedem
    `self` — então isto é ponte, não código novo. Na mesa dela, agora, as duas
    devolvem `None`: o exame continua com seis linhas, e é assim que a GTK
    também se comporta hoje. A diferença aparece no dia do problema, que é
    justamente o dia em que ela precisa ver.
    """
    try:
        linhas = _exame.storm_report(controles_no_cabo=_exame.controles_no_cabo(state))
    except Exception:
        return None
    # UM ACHADO CONDICIONAL QUE LEVANTA NÃO PODE COMER O EXAME INTEIRO: ele entra
    # sob o seu próprio `try`, e uma Steam meio instalada não apaga as seis
    # linhas que já estavam prontas.
    try:
        vigia = _daemon.medir_guarda_do_steam_input()
    except Exception:
        vigia = None
    if vigia:
        linhas.append(vigia)
    prontuario = _prontuario(pode_perguntar)
    if prontuario:
        linhas.append(prontuario)
    return linhas


#: O PRONTUÁRIO DOS JOGOS LEVA 7,1 SEGUNDOS — medido na máquina dela em
#: 03/09/2026, com `time.monotonic` em volta da chamada:
#:
#:     _autostart                 3,9 ms      storm_report            3,3 ms
#:     _status_do_daemon          3,0 ms      guarda_do_steam_input   2,8 ms
#:     _systemctl_status_text     5,6 ms      perfil_na_tela          0,2 ms
#:     medir_prontuario_dos_jogos      7.148,8 ms
#:
#: **FATO DERRUBADO:** o comentário que o chama na janela antiga
#: (`daemon_actions.py:1145`) diz *"Roda dentro do worker porque leva ~1 s"*. Na
#: mesa dela ele leva SETE, e a ordem de grandeza é o que decide o desenho desta
#: função: 1 s numa faixa lenta de 2 s seria caro; 7 s é impossível.
#:
#: O QUE ACONTECEU QUANDO ELE ENTROU NA FAIXA LENTA, e está fotografado no relato
#: desta frente: a janela abriu, o tique custou **13.676 ms de mediana** e a aba
#: pintou **zero valores em 8 segundos**. A faixa lenta roda DENTRO do laço do
#: GTK; a janela antiga o chamava de dentro de um worker, e essa diferença não
#: estava escrita em lugar nenhum.
#:
#: A CURA É A DA JANELA ANTIGA, com o mecanismo do piloto: uma thread, uma de
#: cada vez, e o tique publica o que já se sabe. É o mesmo molde do leitor de cor
#: (`hefesto_vivo._contexto`) e do serial de fábrica
#: (`ipc_handlers._identidade_em_voo`) — perguntar é caro, então pergunta-se
#: fora do caminho e mostra-se a última resposta.
#:
#: `{"achado": (veredito, frase) | None, "quando": monotonic}`. Vazio = nunca
#: perguntado, e aí a primeira visita só DISPARA a pergunta.
_PRONTUARIO: dict[str, Any] = {}

#: A pergunta está em voo? Uma lista de um elemento porque quem a zera é a
#: thread, e o que se troca é o conteúdo, nunca o nome.
_PRONTUARIO_EM_VOO: list[bool] = [False]

#: De quanto em quanto tempo vale a pena repetir uma pergunta de 7 s. Cinco
#: minutos: o prontuário compara os manifestos da Steam com os perfis do disco, e
#: os dois só mudam quando ela instala um jogo ou salva um perfil.
PRONTUARIO_S = 300.0


def _prontuario(pode_perguntar: bool = True) -> tuple[str, str] | None:
    """O achado do prontuário JÁ SABIDO, e dispara a próxima pergunta se venceu.

    NUNCA BLOQUEIA. Devolve `None` na primeira visita — o exame sai com as seis
    ou sete linhas que já tem — e a linha aparece sozinha no tique seguinte à
    volta da thread. É a mesma honestidade do `_identidade_de_fabrica` do daemon:
    enquanto não voltar, a resposta é "ainda não sei", e não uma invenção.

    `pode_perguntar=False` NA PRIMEIRA LEITURA DA FAIXA LENTA, e a razão é o
    relógio: aquela é a única que roda DENTRO do laço do GTK (ver
    `_faixa_lenta`), e disparar ali a varredura de 7 s faz as quatro leituras
    seguintes disputarem o disco com ela. Medido em 03/09/2026: o primeiro tique
    da janela custou **1.271 ms** com a pergunta solta, e a mediana dos outros
    dezenove foi **4,7 ms**. Adiando-a para a primeira RELEITURA — que já é
    thread — o pico sai do caminho e a linha do prontuário chega dois segundos
    depois, que é quando ela chegaria de qualquer jeito.
    """
    agora = time.monotonic()
    venceu = (not _PRONTUARIO
              or agora - float(_PRONTUARIO.get("quando") or 0.0) > PRONTUARIO_S)
    if venceu and pode_perguntar and not _PRONTUARIO_EM_VOO[0]:
        _PRONTUARIO_EM_VOO[0] = True
        threading.Thread(target=_perguntar_o_prontuario, daemon=True).start()
    achado = _PRONTUARIO.get("achado")
    return achado if isinstance(achado, tuple) else None


def _perguntar_o_prontuario() -> None:
    """A pergunta de 7 s, fora do laço do GTK. Guarda o resultado e sai.

    O `finally` é o que impede a thread de ficar presa "em voo" para sempre
    quando a medição levanta — sem ele, um erro numa Steam meio instalada
    calaria o prontuário até o fim da sessão.
    """
    try:
        achado = _daemon.medir_prontuario_dos_jogos()
    except Exception:
        achado = None
    _PRONTUARIO["achado"], _PRONTUARIO["quando"] = achado, time.monotonic()
    _PRONTUARIO_EM_VOO[0] = False


#: O RÓTULO DA LINHA DE IDENTIDADE do painel técnico. Fica aqui, e não solto na
#: `f-string`, porque a régua desta frente o LÊ para achar o bloco — digitá-lo
#: nos dois lugares criaria o segundo dono da mesma palavra.
ROTULO_DA_IDENTIDADE = "Identidade de fábrica"

#: O QUE SE ESCREVE NO LUGAR DE UM SERIAL QUE O `state_full` NÃO TROUXE. É a
#: regra dela — *campo sem informação não mostra nada*.
#:
#: ATENÇÃO — ESTA FRASE ESTÁ NA TELA DELA E ELA É IMPRECISA — medido em 03/09/2026, e
#: fica declarado aqui porque trocar texto de tela é decisão dela, e a cura de
#: verdade não é neste arquivo. O que se mediu, com os dois controles na mesa:
#:
#:     transporte  state_full.serial  lido DO APARELHO (`ler_identidade_pelo_cabo`)
#:     cabo        os 17 caracteres   17 caracteres · fatia da cor `00`
#:     rádio       `None`             17 caracteres · fatia da cor `04`
#:
#: O APARELHO RESPONDE NOS DOIS. O `0x80`/`0x81` funciona por rádio desde
#: 02/09 — é a linha 111 do `docs/data/mapa-controles.csv`, e é o mesmo caminho
#: que devolve a cor do plástico (a cor É `serial[4:6]`). Quem não publica é o
#: DAEMON: o `state_full` traz `serial: None` para quem está no rádio.
#:
#: LOGO A FRASE CERTA NÃO É SOBRE O CABO — é sobre o publicador. A cura tem duas
#: metades e nenhuma é desta aba: `ipc_handlers._identidade_publicada` passar a
#: publicar o serial do rádio, ou o `mesa_viva.LeitorDeCor` guardar a identidade
#: inteira em vez de só a cor (ele JÁ faz a leitura que traz os 17 caracteres,
#: uma vez por endereço, e joga fora tudo menos o tom). A segunda não custa uma
#: leitura nova. Enquanto nenhuma acontecer, esta linha diz ao suporte que o
#: aparelho não deu o número — e ele deu.
SEM_SERIAL_LIDO = "o serial só é lido no cabo"


#: OS DOIS ÚLTIMOS DEGRAUS DE `identidade_de`, que aqui NÃO servem como nome.
#: Ele nunca devolve vazio: sem nome nenhum cai no transporte (`"USB"`/`"BT"`) e,
#: sem nem isso, no travessão. Nesta linha o transporte já está escrito ao lado,
#: em palavra — `P2 · BT · rádio` afirmaria a mesma coisa duas vezes, e o
#: travessão leria como defeito onde o que há é ausência de leitura.
_NAO_E_NOME = frozenset({TRAVESSAO, *VIA_DO_TRANSPORTE.values()})


def _nome_do_plastico(c: dict[str, Any], mesa: list[dict[str, Any]]) -> str:
    """O nome DESTE controle, pelo dono compartilhado — ou `""`.

    O dono é `pacotes.identidade_de`, e ele já sabe a ordem das quatro fontes
    (*o que ELA nomeou > o modelo decodificado > o nome da MESA > o transporte
    só*), já descarta o `"Não sei"` da mesa e já casa por `uniq` em vez de por
    posição. Escrever aqui uma quinta leitura seria a segunda verdade que a lei
    dela de 03/09 proíbe — e as abas 02 e 06 já o chamam com `ctx.mesa`.
    """
    nome = str(identidade_de(c, mesa) or "").strip()
    return "" if nome in _NAO_E_NOME else nome


def _linha_de_identidade(c: dict[str, Any], mesa: list[dict[str, Any]]) -> str:
    """`P1 · White · cabo · <serial>` — a identidade de fábrica de UM controle.

    DECISÃO 10 DELA, 03/09/2026: *"Serial de fábrica: inteiro, e SÓ na aba
    Sistema (a de diagnóstico)."* Ele é identificador único como um MAC, o daemon
    já o publica (`ipc_handlers._identidade_publicada`, ROTA-A de 02/09) e até
    hoje NENHUMA tela do produto o mostrava — nem esta, nem a GTK.

    O LUGAR É O PAINEL "Detalhes técnicos", e a escolha é de sobriedade: é a
    caixa de diagnóstico desta aba, ela já existe, já tem endereço
    (`registro-texto`) e já está publicada. Uma linha de estado nova custaria
    30px numa coluna que o gerador engenha para acabar no mesmo y da irmã — e
    seria mudança de DESENHO, que é decisão dela e não minha.

    O NOME E O NÚMERO VÊM DE CIMA — 03/09/2026, e é a lei dela:

        "se no topo tá mostrando controle white player 1, então cada aba vai
         usar os controles lá de cima. Não mistura com a info dos mockups."

    ESTA LINHA LIA SÓ O `modelo` DO `state_full`, e o `modelo` sai do serial —
    que o daemon **não publica para quem está no rádio** (ver
    :data:`SEM_SERIAL_LIDO`: o aparelho responde, o publicador é que cala).
    Fotografado na mesa dela em 03/09/2026, com o P1 no cabo e o P2 no rádio:

        a fita, no topo      P1 · White · USB
                             P2 · Galactic Purple · BT
        este painel, abaixo  P1 · White · cabo · <os 17 caracteres>
                             P2 · rádio · o serial só é lido no cabo

    O MESMO APARELHO, NA MESMA TELA, com a identidade presente num lugar e
    ausente no outro — e o dado existia: `mesa_viva.LeitorDeCor` já o lê pelo
    broker e traduz o código de fábrica pelo mapa DELA
    (`docs/data/cores-do-dualsense.csv`, 28 modelos). Quem sabe juntar as duas
    portas é `pacotes.identidade_de`; ver :func:`_nome_do_plastico`.

    O NÚMERO SAI DE `pacotes.jogador_de` pela mesma razão. A conta daqui lia o
    `player` do daemon ANTES do `player_slot` — a ordem INVERTIDA da que a GTK
    usa (`actions/base.numero_do_controle` lê o slot na frente), e o `player` é
    `None` para quem o co-op não enxerga, em qualquer transporte. Duas cópias da
    mesma regra é o defeito que fez o mesmo controle ser "Controle 1" numa tela
    e "Sony 3" na outra.

    A PROSA ACIMA NÃO CITA A CHAMADA VELHA DE PROPÓSITO: a `RÉGUA 4` do
    `test_os_donos_de_fato.py` caça a leitura crua por LINHA e só pula o que
    começa com `#` — uma docstring que a transcrevesse reprovaria a cura que a
    apagou.

    NADA AQUI É INVENTADO: sem nome lido a linha não escreve nome nenhum, e sem
    serial ela diz :data:`SEM_SERIAL_LIDO` em vez de um travessão que leria como
    defeito. É a regra dela — *campo sem informação não mostra nada*.
    """
    numero = jogador_de(c)
    serial = str(c.get("serial") or "")
    via = "cabo" if str(c.get("transport") or "") == "usb" else "rádio"
    quem = " · ".join(p for p in (f"P{numero}" if numero else "",
                                 _nome_do_plastico(c, mesa), via) if p)
    return f"{quem} · {serial or SEM_SERIAL_LIDO}"


def _repouso_do_painel(state: dict[str, Any] | None,
                       mesa: list[dict[str, Any]] | None = None) -> str:
    """O painel "Detalhes técnicos" SEM ninguém clicar — e ele deixa de ser um traço.

    A GTK NUNCA TEVE UM TRAÇO AQUI: o `Gtk.TextView` dela fica sempre com a saída
    de `systemctl status <unit>` (`daemon_actions.py:1970` e `:2549`), reescrita
    a cada refresh — quem abre a aba já lê "está ativo? desde quando? falhou?".
    Esta tela mostrava `—` até alguém clicar em "Ver detalhes", e a nota de
    `aba_sistema.SEM_FONTE` que explicava o traço falava de OUTRA coisa (as 80
    linhas do registro, que o `ver-detalhes` passou a entregar em 01/09).

    O TEXTO DO `systemctl status` É DA JANELA ANTIGA, chamado e não copiado:
    `_matriz()._systemctl_status_text`. A unit vem de `_unidade()`, que a pede ao
    dono dela — nunca digitada, pela razão que `_autostart()` já pagou.

    E A IDENTIDADE DE FÁBRICA VEM POR ÚLTIMO, que é a decisão 10 dela. As duas
    coisas cabem no mesmo painel porque as duas respondem à mesma pergunta —
    *"o que eu digo ao suporte?"*.

    A ORDEM FOI MEDIDA, NÃO ESCOLHIDA. O painel tem 110 px (seis linhas) e leva
    `data-hef-rolar="fim"`: ele SEMPRE mostra o fim do texto. E
    `systemctl status --no-pager` não acaba nas propriedades — ele emenda as
    últimas linhas do journal. Com a identidade no começo, a foto de 03/09/2026
    às 04:41 mostrou seis linhas de journal e nenhuma da identidade: o dado que a
    decisão 10 mandou aparecer estava no painel e fora da vista. Invertida, o
    fim é a identidade, e o `systemctl status` fica a uma rolada acima.

    A `mesa` É A FITA DO TOPO, e ela entra por aqui só para atravessar até
    :func:`_linha_de_identidade` — nada nesta função a lê. Tem valor padrão
    porque a faixa lenta a repassa e as réguas chamam as duas de um argumento
    só; sem mesa o painel escreve o que o `state_full` sozinho sabe, que é
    menos, e nunca o nome do desenho.
    """
    partes: list[str] = []
    try:
        status = _matriz()._systemctl_status_text(_unidade())
    except Exception as erro:  # a frase precisa do motivo, e ele vem do erro
        status = f"Não consegui perguntar ao systemd: {erro}"
    partes.append(str(status).strip())
    controles = (state or {}).get("controllers") if isinstance(state, dict) else None
    vivos = [c for c in (controles or [])
             if isinstance(c, dict) and c.get("connected") is not False]
    if vivos:
        partes.append("")
        partes.append(ROTULO_DA_IDENTIDADE)
        partes += [f"  {_linha_de_identidade(c, mesa or [])}" for c in vivos]
    return "\n".join(partes).strip()


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


#: A JANELA ANTIGA, INSTANCIADA SEM JANELA NENHUMA — e é o achado de reuso desta
#: frente, 03/09/2026.
#:
#: `DaemonActionsMixin` é a classe de onde saem TRÊS coisas que esta aba devia à
#: GTK e reescrever seria a regressão que esta rota existe para não repetir:
#:
#:     `_daemon_status()`        a matriz de TRÊS fontes, com os quatro estados
#:     `_systemctl_status_text()` o que a GTK põe no painel técnico em repouso
#:     `_journalctl_tail()`      as 80 linhas do registro
#:
#: **Ela é um MIXIN, e um mixin não precisa da janela para ser instanciado.**
#: Medido em 03/09/2026: `DaemonActionsMixin()` constrói sem argumento nenhum, e
#: os três métodos acima só tocam `subprocess` e o arquivo de pid — nenhum toca
#: um widget. O que se ganha é a REGRA com um dono só: enquanto isto não
#: existia, `interface/sistema_viva.py:116` carregava uma cópia da matriz e o
#: próprio docstring dela se declarava *"um segundo leitor da mesma regra"* —
#: e a cópia estava ERRADA num ponto que ninguém tinha medido: ela procura o pid
#: em `…/hefesto-dualsense4unix.pid` e o produto o grava em `…/daemon.pid`
#: (`daemon_actions._read_daemon_pid`, via `xdg_paths.runtime_dir`). Conferido no
#: disco desta máquina: o arquivo que existe é `daemon.pid`. O segundo leitor
#: respondia `offline` a todo daemon avulso.
#:
#: UMA INSTÂNCIA SÓ, e criada na primeira vez que alguém precisa: construí-la a
#: cada tique não custaria nada mensurável, mas guardá-la deixa explícito que
#: **não há estado nenhum aqui dentro** — se houvesse, esta linha seria o bug.
_JANELA_ANTIGA: list[Any] = []


def _matriz() -> Any:
    """A instância de `DaemonActionsMixin` desta sessão. Ver :data:`_JANELA_ANTIGA`."""
    if not _JANELA_ANTIGA:
        _JANELA_ANTIGA.append(_daemon.DaemonActionsMixin())
    return _JANELA_ANTIGA[0]


def _status_do_daemon(state: dict[str, Any] | None) -> str:
    """Um dos QUATRO estados da janela antiga — não os dois que esta aba tinha.

    ATÉ 03/09/2026 ESTA ABA COLAPSAVA A MATRIZ EM DOIS: `"online_systemd" if
    ctx.state else "offline"`. A camada de tela sabe os quatro
    (`aba_sistema._ESTADO_DO_HEFESTO`) e nunca recebia os outros dois, então:

    * com o daemon rodando FORA do systemd, a tela escrevia "Ligado" com selo
      verde e a dica *"Se travar, ele volta sozinho"* — que é FALSO nesse
      estado. A GTK escreve "Ligado, em modo improvisado", em laranja;
    * enquanto a unit sobe, `iniciando` virava "Desligado".

    O `state` CONTINUA VALENDO COMO PISO. `_daemon_status()` fala com o systemd e
    com o arquivo de pid, não com o daemon: se ele levantar, ou responder
    `offline` enquanto o IPC acabou de devolver um `state_full`, quem tem razão é
    o `state` — o daemon respondeu, logo está de pé. Nesse desempate sai
    `online_avulso`, que é exatamente o que a matriz chama de "vivo e não pelo
    systemd", e não `online_systemd`, que afirmaria uma unit que ninguém viu.
    """
    try:
        status = str(_matriz()._daemon_status())
    except Exception:
        status = "offline"
    if state and status == "offline":
        return "online_avulso"
    return status


#: A releitura está em voo? Ver :func:`_faixa_lenta`.
_LENTO_EM_VOO: list[bool] = [False]


def _ler_a_faixa_lenta(state: dict[str, Any] | None,
                       pode_perguntar: bool = True,
                       mesa: list[dict[str, Any]] | None = None,
                       ) -> tuple[Any, Any, Any, Any, Any]:
    """As cinco leituras caras, de verdade. Não se chama do tique — ver abaixo."""
    return (_autostart(), _achados(state, pode_perguntar), _perfil_da_bateria(),
            _status_do_daemon(state), _repouso_do_painel(state, mesa))


def _guardar_a_faixa_lenta(state: dict[str, Any] | None,
                           mesa: list[dict[str, Any]] | None = None) -> None:
    """A releitura, fora do laço do GTK. O `finally` é o que destrava o voo."""
    try:
        _LENTO["valor"] = _ler_a_faixa_lenta(state, mesa=mesa)
    finally:
        _LENTO["quando"] = time.monotonic()
        _LENTO_EM_VOO[0] = False


def _faixa_lenta(state: dict[str, Any] | None,
                 mesa: list[dict[str, Any]] | None = None,
                 ) -> tuple[Any, Any, Any, Any, Any]:
    """As leituras CARAS: SÍNCRONA na primeira, EM THREAD nas releituras.

    Elas saem deste processo — subprocesso, disco — e nenhuma muda entre dois
    piscares. O tique da pintura é de 500 ms; a faixa lenta é de 2 s, que é a
    mesma separação que `interface/sistema_viva.py` já tinha medido e escolhido.

    ERAM TRÊS E VIRARAM CINCO em 03/09/2026 — o estado do serviço (dois
    `systemctl` e um `stat`) e o repouso do painel técnico (mais um `systemctl`).

    POR QUE A RELEITURA SAIU DO LAÇO, e é medição, não precaução: o `_prontuario`
    ronda em thread própria a cada 5 minutos e varre os manifestos da Steam por
    7 segundos. Enquanto ele varre, o disco fica disputado e as CINCO leituras
    daqui — que custam 18 ms com a máquina calma — passaram a custar **1.840 ms**
    e **302 ms** em duas voltas medidas em 03/09/2026. A faixa lenta roda dentro
    do laço do GTK: isso é a janela dela travada por quase dois segundos, uma vez
    a cada cinco minutos, sem nada na tela dizendo por quê.

    A JANELA ANTIGA JÁ FAZIA ASSIM, e é dela o molde: `_refresh_daemon_view_async`
    e `_refresh_storm_diag` submetem tudo a um worker e devolvem por
    `GLib.idle_add`. O que faltava aqui era o mesmo cuidado.

    A PRIMEIRA CONTINUA SÍNCRONA, e as duas razões são de comportamento:

    * **a primeira pintura tem de ser verdadeira.** Com tudo assíncrono, o
      primeiro tique escreveria travessão em cinco lugares e a tela piscaria de
      "não sei" para o valor — o oposto do que esta aba está curando. Medida
      com a máquina calma, a primeira leva 18 ms;
    * **`_LENTO` é o ponto de injeção das réguas.** O docstring dele diz que as
      réguas o esvaziam para forçar a leitura; se esvaziar passasse a devolver
      `None` até uma thread voltar, toda régua desta aba viraria uma corrida.

    A `mesa` ATRAVESSA POR AQUI, e ela é a única entrada que MUDA dentro da
    janela de 2 s: a cor do plástico é perguntada em thread e chega depois do
    primeiro tique. O painel técnico ganha o nome do controle na releitura
    seguinte, e é a mesma espera que a fita do topo já tem — não uma nova.
    """
    agora = time.monotonic()
    if not _LENTO:
        # `pode_perguntar=False`: a varredura de 7 s do prontuário fica para a
        # primeira RELEITURA, que já é thread. Ver `_prontuario`.
        _LENTO["valor"] = _ler_a_faixa_lenta(state, pode_perguntar=False, mesa=mesa)
        _LENTO["quando"] = agora
        return _LENTO["valor"]  # type: ignore[no-any-return]
    if agora - float(_LENTO["quando"]) >= LENTO_S and not _LENTO_EM_VOO[0]:
        _LENTO_EM_VOO[0] = True
        threading.Thread(target=_guardar_a_faixa_lenta, args=(state, mesa),
                         daemon=True).start()
    return _LENTO["valor"]  # type: ignore[no-any-return]


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

    auto, achados, perfil_da_bateria, status, _repouso = _faixa_lenta(
        ctx.state or None, ctx.mesa)
    # O ESTADO VEM DA MATRIZ DE TRÊS FONTES DA JANELA ANTIGA — ver
    # `_status_do_daemon`. Até 03/09/2026 esta linha era
    # `"online_systemd" if ctx.state else "offline"`, e o comentário que a
    # defendia dizia que a distinção "é da janela antiga". Ela é da TELA: a
    # camada de estado (`aba_sistema._ESTADO_DO_HEFESTO`) tem os quatro textos
    # escritos, com cor e dica próprias, e recebia dois.
    return _tela.Leitura(
        status=status,
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
# desistia com `any(not c.get("cor") for c in mesa)`, e bastava UM controle sem
# cor no dicionário do leitor para a fita das dez páginas não repintar.
#
# FATO ERRADO, SUBSTITUÍDO (03/09/2026): este parágrafo atribuía a guarda
# permanente ao TRANSPORTE — *"pelo rádio a cor NUNCA chega, e quem diz isso é
# o mapa de canais (`identidade.cor_do_aparelho`, `radio_aciona = não`)"*. O
# mapa diz `("sim", "sim")`; ver a nota de `SEM_COR_LIDA`. O que segura a cor
# não é o rádio: é a THREAD — `LeitorDeCor.perguntar` bloqueia, e até ela voltar
# o item de mesa nasce sem `cor`. É espera, não sentença, e é por isso que a
# guarda tinha de olhar a MESA VAZIA e não a cor ausente.
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


# ---------------------------------------------------------------------------
# A DECISÃO 2 DELA — 03/09/2026:
#
#     "Aba Sistema, nome do compositor: o CURTO na tela (`CosmicTerm`), o
#      INTEIRO na dica (`com.system76.CosmicTerm`)."
#
# O NOME É O DA JANELA QUE ESTÁ NA FRENTE, publicado em
# `window_detect_current_class`, e é o mesmo dado que a GTK já mostra na linha
# dela: `descrever_deteccao_de_janela` escreve *"funcionando (na frente agora:
# com.system76.CosmicTerm)"*. Nesta tela a frase longa ia inteira para a dica da
# LINHA e o valor da coluna dizia só "Ligado" — o nome não aparecia em lugar
# nenhum, nem curto nem inteiro.
#
# POR QUE O ALVO É `html` E NÃO UM ALVO DE `title`: o piloto sabe escrever
# texto, largura, `value`, classe, cor, fundo, `--plastico` e `innerHTML`, e não
# sabe escrever atributo. O `innerHTML` leva o `title` DENTRO do valor, que é o
# hover em cima da própria palavra — e é onde a pessoa passa o mouse. Um alvo
# `title` novo no piloto seria mudança em arquivo de todas as dez abas por uma
# linha de uma.
# ---------------------------------------------------------------------------
def _curto(classe: str) -> str:
    """`com.system76.CosmicTerm` -> `CosmicTerm`. O último pedaço, e nada mais.

    A REGRA É A DO NOME REVERSO DE DOMÍNIO, que é o que um `app_id` de Wayland é
    — e ela degrada sozinha: uma classe SEM ponto (`Hefesto-Dualsense4Unix`,
    medida na mesa dela) volta inteira, que é o certo. Um ponto no fim devolveria
    vazio, e aí o inteiro é a resposta honesta.
    """
    pedaco = classe.rsplit(".", 1)[-1].strip()
    return pedaco or classe


def _quem_esta_na_frente(state: Any) -> str:
    """A classe da janela em foco AGORA, ou `""` — a MESMA regra da GTK.

    `descrever_deteccao_de_janela` só nomeia a janela **dentro do ramo
    `vendo`**, e a queda de `window_detect_current_class` para
    `window_detect_last_class` acontece lá dentro. As duas metades vêm juntas de
    propósito, e a primeira é a que importa: `last_class` é STICKY — ela guarda
    a última janela que se conseguiu ler e não decai. Fora do ramo `vendo`, o
    nome que ela devolve é de horas atrás.

    MEDIDO na mesa dela em 03/09/2026: `seeing=False`, `current=unknown`,
    `last=Hefesto-Dualsense4Unix`, `useful_age_sec=5861` — uma hora e meia. Ler o
    `last` fora do `vendo` faria a linha dizer "Sem ver a janela agora ·
    Hefesto" e nomear uma janela que não está na frente há uma hora e meia.
    """
    if not isinstance(state, dict) or not state.get("window_detect_seeing"):
        return ""
    for chave in ("window_detect_current_class", "window_detect_last_class"):
        valor = state.get(chave)
        if isinstance(valor, str) and valor and valor != "unknown":
            return valor
    return ""


def _com_quem_esta_na_frente(valor: Any, state: Any) -> str | None:
    """O valor da linha com o nome CURTO ao lado, e o INTEIRO no `title` dele.

    Devolve `None` quando não há nome a acrescentar — e aí o `pacote()` não
    reescreve nada, e a linha continua com o texto que a camada do produto
    formou. Acrescentar um separador solto seria pior que não acrescentar.

    TUDO ESCAPADO: a classe da janela vem de fora do produto (é o nome que o
    programa em foco declarou), e ela entra num `innerHTML`. É a mesma escapada
    que `descrever_deteccao_de_janela` faz para o markup do Pango.
    """
    if not isinstance(valor, str) or not valor or valor == _tela.NAO_DEU:
        return None
    classe = _quem_esta_na_frente(state)
    if not classe:
        return None
    return (f"{html.escape(valor)} <span class=\"pt\">·</span> "
            f'<span title="{html.escape(classe)}">{html.escape(_curto(classe))}</span>')


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
        # O `blocos:` DOS BOTÕES SAI TAMBÉM DAQUI, e esta é a metade que
        # importa: com o serviço parado a camada do produto levanta e a aba
        # inteira emudece — que é exatamente o instante em que ela precisa ler
        # "Ativar o serviço" no botão. Deixar este ramo sem os rótulos faria a
        # saída de emergência existir só enquanto ela não é necessária.
        return {"sem_dono": {"tela": {"sem_dono": True, "oque": str(erro)}},
                "blocos": blocos_dos_botoes(_de_pe(ctx)),
                "cobertura": {"pintados": 0, "sem_dono": 1}}

    fora: dict[str, object] = {}
    for chave, v in (bruto.get("valores") or {}).items():
        # O ACHATAMENTO: a camada devolve `{"txt": …, "cls": …, "g": …}` e a
        # tela endereça as três coisas separadas. O `-cls` continua sem alvo na
        # página (ver `NAO_CHEGA_NA_TELA`); o `-g` ganhou o dele em 03/09.
        if isinstance(v, dict):
            fora[chave] = v.get("txt", "—")
            fora[f"{chave}-cls"] = v.get("cls", "")
            # O GLIFO, e ele é a metade ACESSÍVEL do selo. Ver o comentário do
            # `est()` em `interface/aba09.py`: fotografado em 03/09 às 04:26, a
            # linha "Pausado" mostrava o valor `Não` ao lado de um `!` laranja
            # do desenho, e "Trocar de perfil ao abrir o jogo" mostrava "Sem ver
            # a janela agora" ao lado de um `✓` verde. Quem lê o símbolo lia o
            # contrário de quem lê o valor.
            fora[f"{chave}-g"] = v.get("g", "")
        else:
            fora[chave] = v
    # A DECISÃO 2 DELA entra DEPOIS do achatamento, porque ela reescreve um dos
    # valores que a camada já formou. Ver `_curto_e_inteiro`.
    troca = _com_quem_esta_na_frente(fora.get("hefesto-troca-de-perfil"), ctx.state)
    if troca is not None:
        fora["hefesto-troca-de-perfil"] = troca
    # O INTERRUPTOR E O BOTÃO ACESO — os dois valores que `NAO_CHEGA_NA_TELA`
    # segurava até 03/09/2026, e os dois são CLASSE, não texto.
    #
    # `autostart` chega da camada como `True` / `False` / `None`, e os três
    # significam coisas diferentes: o alvo `classe` acende no `True`, apaga no
    # `False` e apaga também no `None` — que é o certo, porque "não consegui
    # perguntar ao systemd" não é "ligado". O glifo ao lado diz qual dos dois.
    auto = bruto.get("autostart")
    fora["hefesto-autostart"] = auto
    fora["hefesto-autostart-g"] = _tela.GLIFO_OK if auto is True else (
        "○" if auto is False else _tela.GLIFO_INFO)
    # O PERFIL DE BATERIA É A CHAVE DO PRODUTO (`tudo_ligado`, `bateria_longa`,
    # `eu_escolho`) e não o rótulo: quem compara é o `data-hef-quando` de cada
    # botão, que o gerador escreve a partir do mesmo `PERFIS`. `None` — ninguém
    # escolheu — apaga os três, e é o que `secao_orcamento.perfil_na_tela` já
    # decidira: a ausência NÃO afunda "Tudo ligado".
    #
    # OS DOIS SAEM DA FAIXA LENTA, e chamá-la de novo aqui NÃO custa leitura
    # nenhuma: `_leitura()` acabou de rodar no mesmo tique e o cache de 2 s
    # responde. Ler o `maquina.json` e o `systemctl status` uma segunda vez por
    # tique seria desfazer, dentro desta função, o que a faixa lenta existe para
    # fazer.
    _, _, perfil_da_bateria, estado, repouso = _faixa_lenta(ctx.state or None,
                                                            ctx.mesa)
    fora["bateria-perfil"] = perfil_da_bateria
    fora[REGISTRO] = _no_painel(repouso)
    exame = bruto.get("exame")
    if isinstance(exame, dict):
        fora["exame-contagem"] = _html_da_contagem(exame.get("contagem"))
        fora["exame-lista"] = _html_do_exame(exame)
    # A FITA DESTA ABA, e ela sai da MESA — nunca do desenho. Só entra quando há
    # o que escrever: uma string vazia vira `—` no alvo `html` e apagaria a tira.
    tira = _html_da_fita(ctx.mesa)
    if tira:
        fora[CAMPO_DA_FITA] = tira
    # OS RÓTULOS DOS CINCO DESTRUTIVOS — quem REPÕE é o tique. Ver o bloco do
    # consentimento em dois cliques: sem esta linha um "Confirma?" ficaria na
    # tela para sempre depois de ela armar um botão e sair, e o "Ativar o
    # serviço" nunca voltaria a ser "Parar o serviço" quando o daemon subisse.
    #
    # É `blocos:` E NÃO `mesa:` de propósito: o endereço é o `data-gesto` que o
    # desenho já tem, e não um `data-campo` novo — logo esta cura alcança a
    # página PUBLICADA de hoje, sem esperar publicação nenhuma.
    fora["sem_dono"] = {k: {"sem_dono": True, "oque": v} for k, v in SEM_DONO.items()}
    fora["cobertura"] = {"pintados": len(fora), "sem_dono": len(SEM_DONO)}
    # DEPOIS DA COBERTURA, e não antes: `pintados` conta ENDEREÇO de valor, e
    # `blocos` é chave de contrato — somá-la inflaria em um o instrumento com
    # que esta casa prova que um endereço existe.
    fora["blocos"] = blocos_dos_botoes(estado in _tela.DE_PE)
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
# e a `a08_conexoes.py:1773` já o usa para o mapa do gabinete — que portanto
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
    """Uma linha do exame. Tudo escapado: a frase vem do `doctor`, não daqui.

    A FRASE INTEIRA VAI NO `title`, e é a cura de 03/09/2026. A linha do exame é
    UMA linha e o desenho a corta: `09-sistema.html:825` diz
    `overflow:hidden;text-overflow:ellipsis;white-space:nowrap`. Medido na mesa
    dela, na foto do produto instalado, com um controle no cabo — **CINCO das
    seis linhas cortavam**, e sem `title` não havia como ler o resto:

        cura do travamento do USB ATIVA (mic e fone do co…      68 car, ~22 escondidos
        áudio presente no único controle no cabo (mic+fon…      71 car, ~23 escondidos
        quirk anti-storm ativo (054c:0ce6 — áudio USB esp…      55 car,  ~6 escondidos
        WirePlumber configurado (51-hefesto-dualsense-n…        69 car, ~22 escondidos
        regra áudio-off inativa — o mic e o fone do controle…   88 car, ~37 escondidos

    **A ÚLTIMA É A QUE DECIDE, e ela não corta informação: INVERTE.** O texto
    inteiro é *"regra áudio-off inativa — o mic e o fone do controle estão
    liberados. O que fazer: nada."* O que sobra na tela ao lado de um selo
    `NOTA` é *"o mic e o fone do controle…"*, que se lê como problema. As duas
    metades escondidas são justamente **estão liberados** e **O que fazer:
    nada** — a resposta.

    E O PORTÃO NÃO PEGAVA, porque ele mede a PALAVRA e não o PIXEL:
    `test_a_saude_do_sistema_diz_o_que_fazer.test_toda_frase_de_alarme_tem_o_que_fazer`
    exige `"O que fazer:"` DENTRO da string, e a string sempre teve. Verde sobre
    uma frase que a tela cortava antes do "O que fazer".

    O `title` É A CURA DESTA CASA E NÃO UM DESENHO NOVO: `aba09.py` já a usa nos
    valores que encurta (ver `APELIDO_NA_TELA` e o `inteiro=` do `est()`), e a
    nota de lá diz o mesmo — *"a frase INTEIRA continua no `title` do valor (…)
    é ele que segura a informação"*. Quebrar a linha em duas mudaria a altura do
    quadro, que é desenho, e desenho é decisão dela.
    """
    cls = html.escape(str(achado.get("cls") or "nt"))
    txt = str(achado.get("txt") or "")
    return (f'<div class="saude"><span class="selo {cls}">'
            f'<span class="sg">{html.escape(str(achado.get("g") or ""))}</span>'
            f'{html.escape(str(achado.get("selo") or ""))}</span>'
            f'<span class="txt" title="{html.escape(txt, quote=True)}">'
            f'<span>{html.escape(txt)}</span>'
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


def _trava(ctx: Contexto, nome: str) -> str | None:
    """O motivo pelo qual aquele gesto estaria CINZA agora, ou `None`.

    A CONTA É DA CAMADA DO PRODUTO — `aba_sistema.travas(leitura)` — e ela já
    estava escrita, medida e ligada até a penúltima camada quando esta frente
    começou: cobre `retomar`, `desligar`, `reiniciar`, `ver-plugins` e
    `ver-detalhes`, com o motivo em português pronto para o tooltip. O que
    faltava era alguém chamá-la.

    ELA NÃO PINTA O BOTÃO DE CINZA, E ISSO ESTÁ DECLARADO. O desenho não tem
    estado apagado para `.btn` (medido: a folha desta página tem
    `.seg button:disabled`, e nada para `.btn`), e inventá-lo mudaria o que ela
    aprovou. O que esta função destrava é a metade que NÃO é desenho: o clique
    inútil passa a RECUSAR DIZENDO o motivo, em vez de disparar um no-op que se
    apresenta como ação. Era o defeito exato que
    `_aplicar_sensibilidade_ligar_desligar` curou na janela antiga:
    *"o clique inútil dispara `systemctl` de verdade, volta `rc=0`, e a tela
    confirma um trabalho que não houve."*
    """
    if nome == "retomar" and not (
            isinstance(ctx.state, dict) and "paused" in ctx.state):
        # A TRAVA DO `retomar` SÓ VALE COM A PAUSA LEGÍVEL, e a distinção é da
        # própria camada: `linha_da_pausa` separa "Não" de "não deu para saber
        # se está pausado", e `travas()` não — ela lê `bool(state.get("paused"))`
        # e trata a chave AUSENTE como "não pausado". Recusar aí seria afirmar
        # um estado que ninguém leu, e o preço do contrário é zero: um
        # `daemon.resume` num daemon não pausado é no-op.
        return None
    try:
        return _tela.travas(_leitura(ctx)).get(nome)
    except Exception:
        # UMA TRAVA QUE LEVANTA NÃO PODE TRANCAR O BOTÃO. Sem leitura não há
        # motivo para recusar, e recusar sem motivo é pior que deixar clicar.
        return None


#: A ÚNICA TRAVA DA CAMADA DO PRODUTO QUE ESTE ARQUIVO **NÃO** OBEDECE, e ela é
#: nomeada aqui em vez de ignorada em silêncio — 03/09/2026.
#:
#: `aba_sistema.travas()` (`gui/aba_sistema.py:606`) tranca `ver-plugins` E
#: `ver-detalhes` com a mesma frase: *"O serviço está desligado — não há o que
#: perguntar a ele."* Para o `ver-plugins` a frase é exata: ele fala com o
#: daemon por IPC (`plugin.reload` + `plugin.list`), e um daemon parado não
#: responde. Para o `ver-detalhes` ela é FALSA neste produto:
#:
#:     o `ver-detalhes` daqui NÃO pergunta ao daemon. Ele roda
#:     `journalctl --user -u <unit> -n 80`, que lê o JOURNAL do systemd — um
#:     arquivo do sistema, que continua inteiro depois de a unit cair.
#:
#: E TRANCÁ-LO CUSTARIA EXATAMENTE O QUE ELE EXISTE PARA DAR: com o serviço
#: desligado, "Ver detalhes" é o botão que responde **por que ele caiu**.
#: Obedecer à trava apagaria a única pista no minuto em que ela é a única coisa
#: que importa. A janela antiga também não a tranca — `on_daemon_view_logs:2387`
#: não tem regra de sensibilidade, e `_aplicar_sensibilidade_ligar_desligar` só
#: alcança Ligar, Desligar e Reiniciar.
#:
#: A CURA NÃO É MINHA: a linha que tranca os dois juntos está em
#: `gui/aba_sistema.travas()`, que é a camada do produto e território de outra
#: frente. Enquanto ela não separar os dois, esta divergência fica DECLARADA —
#: e `test_a_09_sistema_fecha_a_paridade.py` a cobra nos dois sentidos, para
#: que ela não vire um esquecimento no dia em que `travas()` for corrigida.
TRAVA_QUE_NAO_VALE_AQUI: dict[str, str] = {
    "desligar": "`travas()` o tranca com o serviço desligado, dizendo *'O "
                "serviço já está desligado'* — e isso era verdade até 03/09/2026, "
                "quando ele deixou de ser um botão só de parar. Ela mandou o "
                "mesmo botão LIGAR nesse estado (*'um específico pra parar o "
                "Daemon E Ativar o Daemon'*), e obedecer à trava aqui recusaria "
                "exatamente o clique que ela pediu que passasse a funcionar. A "
                "cara de parar não precisa da trava: ela só aparece com o "
                "serviço de pé. Ver :func:`desligar`.",
    "ver-detalhes": "`travas()` o tranca com o serviço desligado, e este gesto "
                    "não fala com o daemon: ele lê o journal do systemd, que "
                    "sobrevive à queda da unit. Trancá-lo apagaria a resposta "
                    "para 'por que ele caiu?' no minuto em que ela é a única "
                    "que importa.",
}


@gesto("09-sistema.html", "retomar")
def retomar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Sair da pausa. `daemon.resume` — e só quando HÁ pausa de que sair.

    ELE TINHA UM CHAMADOR EM TODO O `src/` — o terminal (`cli/app.py:421`), como
    a `gui/aba_sistema.py:77` já tinha medido: *"a pausa fica gravada em disco e
    sobrevive a desligar o computador; até hoje só o terminal saía dela."* Este
    é o segundo, e é uma tela.

    A RECUSA ENTROU EM 03/09/2026, e o defeito estava na foto: com `paused:
    False` — medido na mesa dela — o botão ficava verde e clicável, e o clique
    mandava `daemon.resume` a um daemon que não está pausado. Um no-op que se
    apresenta como ação.
    """
    motivo = _trava(ctx, "retomar")
    if motivo:
        raise RuntimeError(motivo)
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

    E ELE PASSA A RELER A ABA, que é a METADE que a janela antiga faz com este
    mesmo rótulo — 03/09/2026. O `on_daemon_refresh:2267` da GTK não toca no
    daemon: ele relê o estado, o exame e a linha do detector. Aqui o botão
    mandava o daemon reaplicar a configuração e deixava a TELA com o valor de
    antes por até dois segundos, porque as cinco leituras caras vivem num cache
    de `LENTO_S`. Zerar `_LENTO` faz a próxima pintura reler tudo na hora — o
    mesmo gesto que `_systemctl()` já fazia depois de mexer no serviço, e pela
    mesma razão: quem clicou não pode concluir que não pegou.

    A ORDEM IMPORTA: zera-se DEPOIS de o `daemon.reload` voltar. Zerar antes
    faria a releitura acontecer no meio dos 9,5 s e publicar o estado de antes
    como se fosse o de depois.
    """
    p.chamar("daemon.reload")
    _LENTO.clear()


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
    `_effective_mult` (`core/rumble.py:191`) lê os dois e aplica `min` entre
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
    (`daemon/ipc_handlers.py:5609`) relê o `maquina.json` e **rebinda**
    `daemon._maquina`; o `_orcamento_declarado` (`core/rumble.py:167`) lê a
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


# ---------------------------------------------------------------------------
# OS DOIS QUE ERAM `systemctl` E NADA MAIS — 03/09/2026.
#
# Dos SETE gestos desta página sem dono, dois eram só uma chamada de systemd na
# janela antiga, sem diálogo, sem widget e sem estado de janela:
#
#     autostart   `on_daemon_autostart_toggled:2398` -> `enable` / `disable`
#     reiniciar   `on_daemon_service_restart:2277`   -> `reset-failed` + `restart`
#
# OS OUTROS CINCO CONTINUAM SEM DONO, E DE PROPÓSITO — ver `SEM_CONFIRMACAO`.
#
# NADA AQUI É LÓGICA NOVA: quem executa é `_invoke_systemctl` da janela antiga,
# e as frases de sucesso e de falha são as dela (`_SYSTEMCTL_OK_MSG` e
# `_SYSTEMCTL_FAIL_MSG`, escritas em 26/08 pela LEIGO-03 justamente para o toast
# não dizer `rc=0`). Escrever outras aqui daria à mesma ação duas vozes.
# ---------------------------------------------------------------------------
def _systemctl(verbo: str) -> None:
    """Roda `systemctl --user <verbo>` pela janela antiga, e LEVANTA se não pegou.

    O `reset-failed` ANTES de `restart` é da janela antiga e não é zelo: sem ele
    o `StartLimitBurst` do systemd recusa o restart de quem clicou duas vezes, e
    a tela receberia "não consegui" sobre uma unit perfeitamente sã.

    A UNIT NÃO SE DIGITA — vem de `_unidade()`. É a mesma lição que `_autostart()`
    pagou em 01/09, quando uma literal do `-dev` sobreviveu à purga e fez a tela
    afirmar `not-found` sobre uma unit `enabled`.

    A FALHA VIRA `RuntimeError` COM O `stderr` JUNTO. Um gesto que engolisse o
    `rc != 0` deixaria o interruptor parado sem uma palavra — que é o silêncio
    que este arquivo inteiro existe para acabar.
    """
    janela = _matriz()
    if verbo in ("start", "restart"):
        janela._invoke_systemctl(["reset-failed", _unidade()], check=False)
    r = janela._invoke_systemctl([verbo, _unidade()], capture=True)
    rc = getattr(r, "returncode", -1) if r is not None else -1
    if rc != 0:
        detalhe = str(getattr(r, "stderr", "") or "").strip() if r is not None else ""
        recusa = _daemon._SYSTEMCTL_FAIL_MSG.get(verbo, "Não consegui falar com o systemd")
        raise RuntimeError(f"{recusa}{f': {detalhe}' if detalhe else '.'}")
    # O CACHE DE 2s SAI DO CAMINHO. Sem isto o interruptor só se mexeria no tique
    # seguinte à expiração da faixa lenta — até dois segundos depois do clique —,
    # e quem clicou concluiria que não pegou. Zerar aqui faz a próxima pintura
    # reler `is-enabled` e o estado do serviço na hora, e ela é síncrona
    # justamente porque `_LENTO` ficou vazio (ver `_faixa_lenta`).
    _LENTO.clear()


@gesto("09-sistema.html", "autostart")
def autostart(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O interruptor "Ligar junto com o computador". `systemctl --user enable|disable`.

    ELE ERA UM INTERRUPTOR MORTO, e essa é a pior espécie de botão morto: parece
    ter dois estados, o clique não muda nem a aparência (não há um `<script>` na
    página que troque a classe localmente), e quem clica não tem como saber que
    não pegou. Medido em execução em 02/09: `autostart` estava entre os SETE
    gestos desta página sem dono — o clique caía em `hefesto_vivo.py:1018`,
    imprimia `[gesto sem dono]` no stdout do processo e voltava.

    O QUE ELE MANDA É O CONTRÁRIO DO QUE ESTÁ LIDO, e a leitura é a mesma que
    pinta a chave: `_autostart()` devolve a saída crua de `is-enabled` e
    `aba_sistema.autostart_ligado` a traduz. A tela e o gesto não têm como
    discordar porque leem o mesmo lugar.

    E O ESTADO NÃO SE INVERTE ÀS CEGAS. Com `is-enabled` ilegível
    (`autostart_ligado` devolve `None`), o gesto RECUSA em vez de adivinhar: um
    `enable` disparado sobre "não sei" tem 50% de chance de desfazer a escolha
    dela sem que ninguém tenha pedido.

    ELE ESTÁ EM `hefesto_vivo.PERIGOSOS` — já estava, antes de ter dono — e por
    isso a prova automática desta casa NUNCA o clica. Ligar um gesto que mexe na
    configuração de boot dela sem esse isento seria a régua estragando a máquina
    para provar que sabe clicar.
    """
    ligado = _tela.autostart_ligado(_autostart())
    if ligado is None:
        raise RuntimeError(
            "Não consegui perguntar ao systemd se o serviço liga sozinho — e "
            "sem saber o estado de agora, o interruptor não adivinha.")
    _systemctl("disable" if ligado else "enable")


@gesto("09-sistema.html", "reiniciar")
def reiniciar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Reiniciar o serviço". `systemctl --user restart`, com o `reset-failed`.

    A TRAVA VEM DA CAMADA DO PRODUTO: com o serviço desligado, `travas()`
    responde *"O serviço está desligado — não há o que reiniciar."* — e é essa a
    frase que chega à tela, não uma minha.

    ELE TAMBÉM JÁ ESTAVA EM `hefesto_vivo.PERIGOSOS`: reiniciar o daemon derruba
    a sessão dele no meio do trabalho dela, e a régua não o clica.
    """
    motivo = _trava(ctx, "reiniciar")
    if motivo:
        raise RuntimeError(motivo)
    _systemctl("restart")


# ---------------------------------------------------------------------------
# O CONSENTIMENTO EM DOIS CLIQUES — decisão DELA, 03/09/2026
#
# ELA ESCOLHEU, entre as três formas que lhe foram postas: **"Dois cliques, como
# na Lançadores"**. E escolheu a palavra do botão armado, entre três:
# **"Confirma?"**.
#
# O MECANISMO NÃO NASCE AQUI — ELE JÁ RODA EM PRODUÇÃO. A `07-lancadores`
# confirma assim desde 03/09 (`a07_lancadores.fechar_a_steam_e_repor`): o
# primeiro clique ARMA e devolve o botão com o rótulo trocado; o segundo só vale
# se trouxer o valor que **só existe no botão já armado**, e só dentro da janela
# de tempo. Os dois guardas são independentes de propósito — um deles sozinho
# basta hoje; dois é o que sobrevive a uma régua que releia o DOM entre cliques.
#
# O QUE MUDA AQUI É O CANAL, e a razão é de MECANISMO, não de gosto. Lá o valor
# viaja num `data-v` porque aquela aba REMONTA o cartão inteiro a cada pintura.
# Esta página é ESTÁTICA: o desenho não tem `data-v` nestes botões, e um
# `data-campo` novo só chegaria à tela dela **depois de publicar** — ou seja, a
# cura ficaria guardada na bancada enquanto os botões continuam mortos na mesa
# dela. Aqui o valor que só existe no botão armado é o **RÓTULO**:
#
#     `hefesto_vivo.BOOTSTRAP`, o ouvinte de clique -> `texto: alvo.textContent`
#
# O piloto já manda o rótulo em `o["texto"]`, e quem o escreve é o mesmo
# `blocos:` que arma. Um dono só (:data:`CONFIRMA`) pinta e confere — não há
# como a tela e o guarda discordarem, que é a mesma disciplina do `data-v` de lá.
#
# E POR ISSO A CURA ALCANÇA A PÁGINA PUBLICADA DE HOJE, sem publicar nada:
# `blocos:` endereça por SELETOR CSS (`hefesto_vivo`, `document.querySelector`),
# e `[data-gesto="…"]` é o endereço que o desenho JÁ tem nos cinco botões.
# Nenhum pixel novo, nenhum atributo novo, nenhuma linha do mockup.
#
# QUEM REPÕE O RÓTULO É O TIQUE, e não o gesto: `pacote()` emite o `blocos:` a
# cada volta com o rótulo que cada botão TEM de estar mostrando agora. Sem isso
# um "Confirma?" ficaria na tela para sempre depois de ela clicar uma vez e sair
# — a tela mentindo sobre o estado, que é o defeito que esta aba inteira existe
# para não repetir. O `blocos:` do piloto compara antes de escrever
# (`alvo.innerHTML !== html`), então emitir todo tique não mexe no DOM nem soma
# pintura nenhuma quando nada mudou.
# ---------------------------------------------------------------------------

#: A PALAVRA DO BOTÃO ARMADO. É DELA, escolhida entre três em 03/09/2026.
CONFIRMA = "Confirma?"

#: O VERBO É DELA — *"em sistema um específico pra parar o Daemon E Ativar o
#: Daemon"*, 03/09/2026. O SUBSTANTIVO não é escolha minha: é o vocabulário
#: desta aba, fechado com ela em 31/08 e escrito no `mockup/TODO-DELA.md` —
#: *"Sistema: a aba diz **serviço**, e o verbo é **Parar**"*. Daí "Ativar o
#: serviço", e não "Ativar o Daemon": "Daemon" é a palavra dela para o que a
#: TELA chama de serviço, e a tela tem de falar uma língua só.
ATIVAR = "Ativar o serviço"

#: O gesto do botão que passou a ter DUAS CARAS. O `data-gesto` não muda com a
#: cara — quem despacha é o desenho, e o desenho é um botão só. Ver
#: :func:`desligar`.
DESLIGAR = "desligar"

#: OS CINCO DESTRUTIVOS DESTA PÁGINA — a lista que `SEM_CONFIRMACAO` guardava
#: até 03/09/2026, e que agora tem quem lhe dê o consentimento. Dois deles
#: ganharam motor neste commit; os três que sobram estão em :data:`SEM_MOTOR`,
#: e o que os segura NÃO é mais a falta de confirmação.
DESTRUTIVOS = ("desligar", "restaurar-de-fabrica", "refazer-consertos",
               "refazer-proton", "procurar-camadas")

#: O QUE AINDA SEGURA TRÊS DOS CINCO — e a razão MUDOU em 03/09/2026.
#:
#: **O FATO QUE CAIU:** `SEM_CONFIRMACAO` dizia *"não há primitiva de
#: confirmação"*. Isso deixou de ser verdade no instante em que ela escolheu os
#: dois cliques — e a `07-lancadores` já o desmentia no produto inteiro. O que
#: sobra é OUTRA coisa, e é de MOTOR: o ato destes três mora dentro de um
#: handler da janela GTK que fala com a janela (toast, diálogo, `self.window`),
#: e não há função de produto a chamar de fora. Reescrever o miolo aqui criaria
#: um SEGUNDO DONO da mesma regra — que é a regressão que esta rota existe para
#: não repetir.
#:
#: `procurar-camadas` tem um risco a mais, e ele não é de motor: o `title` dele
#: promete *"Se achar, mostra qual é antes de tirar"* — TRÊS tempos (procurar ·
#: mostrar o achado · tirar), e dois cliques cobrem dois. O que falta a ele é
#: DESENHO, e desenho é dela.
SEM_MOTOR: dict[str, str] = {
    "restaurar-de-fabrica": "o ato mora em `footer_actions.on_restore_default:1477` "
                            "— ele lê `self._get('main_window')`, grava pelo funil "
                            "e manda TODAS as abas da janela velha se repintarem.",
    "refazer-consertos": "o ato mora dentro do `_worker` de "
                         "`daemon_actions.on_storm_fix_safe:1218`, junto com o "
                         "toast de cada etapa — não há função de produto que rode "
                         "os dois scripts e devolva o relatório.",
    "procurar-camadas": "`emulation_actions.on_camadas_engasgo:2075` — o motor "
                        "(`camadas_vulkan.censo`) é limpo, mas o botão promete "
                        "MOSTRAR o achado ENTRE procurar e tirar, e isso é uma "
                        "tela que ainda não existe. É desenho, e desenho é dela.",
}


def _seletor(gesto: str) -> str:
    """Como o `blocos:` endereça um botão desta página. Ver o bloco acima."""
    return f'[data-gesto="{gesto}"]'


#: Os rótulos do DESENHO, lidos da página publicada na primeira vez que alguém
#: pergunta. Vazio = nunca lido.
_ROTULOS: dict[str, str] = {}


def _rotulo_do_desenho(gesto: str) -> str:
    """O que o DESENHO escreve naquele botão — LIDO da página, nunca digitado.

    O dono do rótulo é o gerador (`interface/aba09.py`, o `item()`), e o que ele
    produziu está na página que o produto renderiza. Digitar "Parar o serviço"
    aqui seria o segundo dono de uma palavra que ela escolheu — e envelheceria
    calado no dia em que ela trocasse o verbo, que é exatamente o que aconteceu
    em 31/08 ("encerrar" -> "parar").

    Devolve `""` quando não achou: quem chama trata como "não sei" e não escreve.
    """
    if not _ROTULOS:
        try:
            doc = _onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")
        except Exception:  # pragma: no cover - página fora do disco
            doc = ""
        for achado in re.finditer(
                r'data-gesto="([^"]+)"[^>]*>([^<]*)</button>', doc):
            _ROTULOS[achado.group(1)] = html.unescape(achado.group(2)).strip()
    return _ROTULOS.get(gesto, "")


#: O QUE ESTÁ ARMADO AGORA: `{"gesto": …, "ate": <time.monotonic>}`. Vazio =
#: nada armado. Uma coisa só de cada vez — armar o segundo desarma o primeiro,
#: e o tique repõe o rótulo daquele.
_ARMADO: dict[str, Any] = {}


def segundos_para_confirmar() -> float:
    """A janela do consentimento — PERGUNTADA a quem já a tem.

    O dono é `a07_lancadores.SEGUNDOS_PARA_CONFIRMAR`, e ele não é um número
    solto: é *"o consentimento que `with_steam_closed` EXIGE de quem a chama, na
    forma que uma página tem"*. Um `20.0` digitado aqui seria a segunda duração
    de consentimento desta casa, e as duas se afastariam na primeira mudança.
    """
    from . import a07_lancadores

    return float(a07_lancadores.SEGUNDOS_PARA_CONFIRMAR)


def _armado_agora() -> str:
    """O gesto armado NESTE instante, ou `""` — e ele desarma sozinho no tempo.

    O relógio é lido aqui, e não guardado num `bool`: um `bool` armado por um
    clique que ninguém confirmou continuaria armado depois de a janela passar, e
    o segundo clique de dez minutos depois valeria como consentimento.
    """
    if _ARMADO and time.monotonic() >= float(_ARMADO.get("ate") or 0.0):
        _ARMADO.clear()
    return str(_ARMADO.get("gesto") or "")


def _rotulo_de_agora(gesto: str, de_pe: bool) -> str:
    """O que aquele botão TEM de estar dizendo agora. Três caras, uma conta.

    A ordem importa: armado vence estado. Um botão armado que voltasse a dizer
    "Ativar o serviço" porque o serviço caiu no meio deixaria o consentimento
    dela pendurado sobre uma pergunta que a tela não mostra mais.
    """
    if gesto == _armado_agora():
        return CONFIRMA
    if gesto == DESLIGAR and not de_pe:
        return ATIVAR
    return _rotulo_do_desenho(gesto)


def blocos_dos_botoes(de_pe: bool) -> dict[str, str]:
    """O `blocos:` que põe os cinco no rótulo de agora — do tique e do gesto.

    O MESMO PARA OS DOIS CAMINHOS, de propósito: o gesto devolve isto para a
    troca ser INSTANTÂNEA (não esperar o tique), e o tique devolve isto para
    REPOR. Duas montagens diferentes é como as duas se afastariam.

    Rótulo vazio (o desenho não tem aquele botão) NÃO entra: escrever `""` num
    `blocos:` apagaria o miolo do elemento, e um botão sem palavra nenhuma é
    pior que um botão com a palavra velha.
    """
    fora: dict[str, str] = {}
    for gesto_ in DESTRUTIVOS:
        rotulo = _rotulo_de_agora(gesto_, de_pe)
        if rotulo:
            fora[_seletor(gesto_)] = html.escape(rotulo)
    return fora


def _de_pe(ctx: Contexto) -> bool:
    """O serviço está de pé? A lista dos estados "de pé" é da CAMADA DO PRODUTO.

    `aba_sistema.DE_PE` são os dois que contam como vivo (`online_systemd` e
    `online_avulso`). Perguntar a ela, em vez de comparar com `"offline"`, é o
    que impede esta aba de voltar a colapsar os QUATRO estados em dois — que foi
    o defeito curado em 03/09 e está escrito em :func:`_status_do_daemon`.
    """
    return _status_do_daemon(ctx.state) in _tela.DE_PE


def _confirmado(o: dict[str, Any], gesto_: str) -> bool:
    """Este clique é a CONFIRMAÇÃO? Quando não é, ARMA o botão e devolve `False`.

    OS DOIS GUARDAS, e eles são independentes:

    1. o clique tem de trazer :data:`CONFIRMA` em `o["texto"]` — o rótulo que
       **só existe no botão já armado**, escrito pelo `blocos:` de quem armou;
    2. e tem de chegar dentro de :func:`segundos_para_confirmar`.

    O SEGUNDO SEM O PRIMEIRO NÃO BASTARIA, e o caso é real: a prova automática
    desta casa (`--prova-gesto`) clica cada botão UMA vez por volta, com o que o
    DOM tinha — e o DOM tinha a pergunta. É o mesmo raciocínio escrito em
    `a07_lancadores.fechar_a_steam_e_repor`.

    FORA DO PRAZO ELE LEVANTA, em vez de agir ou de rearmar calado: a frase vai
    para a tarja pelo caminho do `RuntimeError`, e o tique seguinte repõe o
    rótulo do desenho. Rearmar calado deixaria a tela dizendo "Confirma?" sobre
    um consentimento que já tinha vencido.
    """
    rotulo = str(o.get("texto") or "").strip()
    armado = _armado_agora() == gesto_
    if rotulo == CONFIRMA:
        _ARMADO.clear()
        if not armado:
            raise RuntimeError(
                f"Passaram-se mais de {int(segundos_para_confirmar())} segundos "
                "desde a pergunta — não fiz nada. Clique de novo para começar.")
        return True
    _ARMADO.clear()
    _ARMADO.update(gesto=gesto_, ate=time.monotonic() + segundos_para_confirmar())
    return False


@gesto("09-sistema.html", DESLIGAR)
def desligar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O PAR que ela pediu, num botão só: **Parar o serviço** e **Ativar o serviço**.

    DECISÃO DELA, 03/09/2026, com estas palavras: *"E em sistema um específico
    pra parar o Daemon E Ativar o Daemon (sendo que em jogar também consegue
    isso)."* — **um** controle, os dois atos. E é o que a página comporta: a
    coluna de ações desta faixa tem quatro botões e o portão do gerador
    (`aba09.py`, o par de alturas) reprova o quinto, porque as duas colunas
    irmãs desta aba acabam no mesmo y. Um botão a mais abriria os 38px de vão
    que ela reclamou em 31/08.

    AS DUAS CARAS NÃO SÃO SIMÉTRICAS, e a assimetria é o ponto:

    * **Parar** derruba o serviço e os controles dela viram gamepads comuns —
      pede os dois cliques (:func:`_confirmado`);
    * **Ativar** devolve o que já estava parado. Não há o que perder, e pedir
      confirmação para consertar seria uma parede na saída de emergência: com o
      daemon parado esta aba emudece INTEIRA (`pacote()` cai no `sem_dono`), e
      este botão é o único caminho de volta que a interface nova tem.

    O `_user_stopped_daemon` É METADE DO ATO, e a janela antiga já o sabia
    (`daemon_actions.on_daemon_stop:2234`): sem ele o `ensure_daemon_running`
    ressuscita o daemon na próxima abertura, e o "Parar" dura até o próximo F5.
    Ele é armado **no sucesso**, nunca no clique — e aqui isso sai de graça,
    porque :func:`_systemctl` LEVANTA quando o `rc != 0`. "Ativar" o desarma,
    que é o gesto explícito de volta, exatamente como o `on_daemon_start:2231`.

    A TRAVA DA CAMADA NÃO É CONSULTADA NESTE, e está declarado: `travas()` prende
    o `desligar` com *"O serviço já está desligado"* — que é verdade e deixou de
    ser trava no instante em que o botão passou a LIGAR nesse estado. Consultá-la
    aqui recusaria exatamente o clique que ela pediu que funcionasse.

    O QUE ELE DEVOLVE é o `blocos:` dos cinco rótulos, para a troca ser
    instantânea: sem isso a palavra do botão só mudaria no tique seguinte, e
    quem clicou concluiria que não pegou.
    """
    if not _de_pe(ctx):
        _ARMADO.clear()
        if not ativar_o_servico():
            # OS TRÊS PORTÕES DO PRODUTO recusaram, e nenhum deles é falha do
            # systemd — por isso a frase não fala em `rc`. Ver
            # :func:`ativar_o_servico`.
            raise RuntimeError(
                "Não liguei o serviço, e o systemd nem chegou a ser chamado: "
                "ou esta máquina não tem a unit instalada (o instalador nunca "
                "rodou aqui), ou já há um Hefesto vivo fora do systemd — e "
                "nesse caso subir a unit criaria um segundo.")
        return {"blocos": blocos_dos_botoes(_de_pe(ctx))}
    if not _confirmado(o, DESLIGAR):
        return {"blocos": blocos_dos_botoes(True)}
    _systemctl("stop")
    _matriz()._user_stopped_daemon = True
    return {"blocos": blocos_dos_botoes(False)}


def ativar_o_servico() -> bool:
    """Liga o serviço se ele estiver PARADO. Devolve se ELE precisou ligar.

    DONO ÚNICO DO ATO, e ele existe por causa da outra metade da decisão dela:
    *"Adiciona essa função extra quando clicar em ligar"* — o interruptor
    **Ligado** da aba Jogar liga o serviço também, e é o mesmo ato que o "Ativar
    o serviço" desta aba faz. Escrito duas vezes, ele teria dois donos: uma
    cópia desarmaria o `_user_stopped_daemon` e a outra não, e o daemon voltaria
    a morrer no próximo F5 por um caminho e não pelo outro.

    OS TRÊS PORTÕES SÃO DO PRODUTO, e não meus — são exatamente os que
    `daemon_actions.ensure_daemon_running` consulta antes de subir o daemon, na
    ordem dele:

    1. **sem unit instalada, não se liga nada** (`detect_installed_unit`). Quem
       nunca rodou o `install.sh` não tem o que iniciar, e um `systemctl start`
       aí devolve erro sobre uma unit que não existe;
    2. **já ativo, não se liga de novo** (`_is_service_active`) — é o defeito
       que `travas()` nomeia: `systemctl start` numa unit ativa devolve `rc=0` e
       a tela confirmaria um trabalho que não houve;
    3. **daemon avulso vivo, não se duplica** (`_daemon_pid_alive`, a
       BUG-MULTI-INSTANCE-01): com o daemon rodando fora do systemd, subir a
       unit criaria um segundo processo disputando o mesmo hidraw.

    O PRIMEIRO PORTÃO É TAMBÉM O QUE MANTÉM A SUÍTE FORA DO SYSTEMD DESTA
    MÁQUINA: a régua de `test_os_botoes_tem_dono` clica o `hefesto` da aba Jogar
    de verdade, e o `conftest.py` desvia o `HOME` para um lar de mentira — não
    há unit instalada lá, e este ato vira no-op antes de tocar em `systemctl`.
    Uma régua que liga o daemon de quem a executa não é régua.

    NÃO LEVANTA QUANDO JÁ ESTÁ DE PÉ — devolve `False`. Quem chama da aba Jogar
    não está pedindo para ligar: está pedindo o MODO, e ligar é o que falta
    quando falta. Levantar aí trocaria um gesto que funciona por uma recusa.
    Quando ele TENTA e não consegue, `_systemctl` levanta com o `stderr` junto —
    e aí a recusa é verdadeira e vai para a tela.
    """
    from hefesto_dualsense4unix.daemon.service_install import ServiceInstaller

    janela = _matriz()
    try:
        if ServiceInstaller().detect_installed_unit() is None:
            return False
    except Exception:
        return False
    if str(janela._is_service_active()) == "active":
        return False
    if janela._daemon_pid_alive():
        return False
    janela._user_stopped_daemon = False
    _systemctl("start")
    return True


@gesto("09-sistema.html", "refazer-proton")
def refazer_proton(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Refazer a fixação do Proton" — dois cliques, e o motor é o da GTK.

    O QUE MUDOU EM 03/09/2026: ele estava entre os cinco sem dono porque
    *"promete perguntar antes"*. A pergunta existe agora (ver o bloco do
    consentimento), e o motor **nunca foi o handler** — é
    `integrations.proton_pin.lock_proton_for_all_games`, com o portão da Steam
    aberta e a frase de retorno de `daemon_actions.format_proton_lock_result`.
    O `on_proton_lock:1793` da janela antiga é o diálogo e o toast em volta
    dele; nada aqui reescreve uma linha do ato.

    O `getattr` DEFENSIVO É DO CONTRATO DA LANE DO PIN (PLAT-01), e não zelo
    meu: uma instalação sem o módulo — ou sem a função — recusa DIZENDO e
    apontando o caminho, em vez de rebentar com `AttributeError`. A frase de
    "como atualizar" é a do produto.

    A STEAM ABERTA RECUSA, e a razão é da própria lane: ela regrava o
    `config.vdf` ao sair, e a edição seria perdida. Um botão que "aplicasse" e
    perdesse a aplicação é o botão que responde calado com outro nome.

    O RECIBO VAI PARA O PAINEL DE REGISTRO, que é onde esta aba já põe o que os
    botões respondem (`ver-plugins`, `ver-detalhes`). Na janela antiga é um
    toast; aqui não há toast, e jogar fora o `format_proton_lock_result` seria
    perder exatamente o que ele diz — quantos jogos foram travados, ou por quê
    não deu.

    NÃO É CLICADO POR RÉGUA NENHUMA: `("09-sistema.html", "refazer-proton")` já
    está em `hefesto_vivo.PERIGOSOS` desde antes de ele ter dono.
    """
    if not _confirmado(o, "refazer-proton"):
        return {"blocos": blocos_dos_botoes(_de_pe(ctx))}
    import importlib

    try:
        pin: Any = importlib.import_module(
            "hefesto_dualsense4unix.integrations.proton_pin")
    except ImportError:
        pin = None
    travar = getattr(pin, "lock_proton_for_all_games", None)
    if travar is None:
        raise RuntimeError(
            "Esta instalação ainda não tem o Proton pinado — "
            f"{_daemon.como_atualizar_esta_instalacao()}.")
    steam_viva = getattr(pin, "steam_running", None)
    if steam_viva is None:
        from hefesto_dualsense4unix.integrations import steam_launch_options as slo

        steam_viva = slo.steam_running
    if steam_viva():
        raise RuntimeError(
            "A Steam está aberta — feche-a e clique de novo. Não travo o Proton "
            "com a Steam viva porque ela regrava o arquivo ao sair e a mudança "
            "seria perdida.")
    carga = _para_o_painel(_daemon.format_proton_lock_result(travar()))
    carga["blocos"] = blocos_dos_botoes(_de_pe(ctx))
    return carga


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

    A TRAVA ENTROU EM 03/09/2026, e ela é a mesma de `retomar` e `reiniciar`:
    `aba_sistema.travas()` responde *"O serviço está desligado — não há o que
    perguntar a ele."* Com o serviço parado os dois métodos vão a um daemon que
    não está lá; sem a trava, o clique voltava calado e o painel continuava com
    o texto do último pedido — quem clicou concluiria que a lista de agora é
    aquela. O motivo é da camada do produto, não uma frase minha.
    """
    motivo = _trava(ctx, "ver-plugins")
    if motivo:
        raise RuntimeError(motivo)
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

    ESTE É O ÚNICO GESTO DESTA ABA QUE **NÃO** OBEDECE A `travas()`, e a razão
    está em :data:`TRAVA_QUE_NAO_VALE_AQUI`.
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


#: OS CINCO QUE NÃO SÃO IPC, e por isso não estão aqui. Medidos no fonte em
#: 01/09/2026, um a um — a linha de cada um está no relato da leva:
#:
#:   `desligar`             `_run_systemctl_async("stop")` (daemon_actions.py:2234)
#:   `refazer-consertos`    `bash scripts/*.sh` (…:1218)
#:   `refazer-proton`       diálogo GTK + `config.vdf` da Steam (…:1793)
#:   `procurar-camadas`     censo do `system.reg` em disco (emulation_actions.py:2075)
#:   `restaurar-de-fabrica` cópia do asset + `DraftConfig` (footer_actions.py:1477)
#:
#: ERAM OITO, DEPOIS SETE, E AGORA SÃO CINCO. `ver-detalhes` e `ver-plugins`
#: saíram em 01/09/2026 — a nota que os mantinha aqui dizia que ligá-los *"exige
#: o helper privilegiado ou um método de log que o daemon não tem"*, e o registro
#: do daemon é o journal de uma unit do USUÁRIO: `journalctl --user` o lê sem
#: sudo. `reiniciar` e `autostart` saíram em 03/09/2026, pela mesma espécie de
#: descoberta: `systemctl` não é IPC, mas também não é GTK — é subprocesso, e a
#: janela antiga o dispara por um método (`_invoke_systemctl`) que não toca
#: widget nenhum. **Não ser IPC nunca quis dizer não ter caminho.**
#:
#: OS CINCO QUE FICAM TÊM O MOTIVO EM `SEM_CONFIRMACAO`, e ele não é de
#: mecanismo: os cinco PROMETEM perguntar antes, e não há primitiva de
#: confirmação nesta interface.
PONTE = {"chamar", "machine_declare", "resultado"}
METODOS = {"daemon.resume", "daemon.reload", "machine.declare",
           "plugin.reload", "plugin.list"}


PAGINA = "09-sistema.html"
#: ERAM CINCO E VIRARAM SETE em 03/09/2026 — `autostart` e `reiniciar`.
#:
#: OS DOIS NOVOS NÃO ENTRAM EM `PROVAS`, e a razão é a régua, não a preguiça: a
#: prova de `test_os_botoes_tem_dono` clica o gesto DE VERDADE contra uma
#: `PonteDeMentira` e confere as chamadas que chegaram À PONTE. Estes dois não
#: passam pela ponte — eles chamam `systemctl` pela janela antiga —, então a
#: prova não veria chamada nenhuma e, pior, o clique RODARIA `systemctl --user
#: restart` e `enable/disable` na máquina de quem rodasse a suíte. Uma régua que
#: reinicia o daemon de quem a executa não é régua.
#:
#: QUEM OS MEDE É `tests/unit/test_a_09_sistema_sai_do_desenho.py`, com o
#: `_invoke_systemctl` da janela antiga dublado — o clique inteiro roda, e o que
#: se confere é o comando que teria ido ao systemd.
#:
#: E VIRARAM NOVE no mesmo dia, com o consentimento em dois cliques: `desligar`
#: (que agora é o PAR "Parar o serviço"/"Ativar o serviço") e `refazer-proton`.
#: Nenhum dos dois entra em `PROVAS`, pela mesma razão dos dois de cima e com um
#: agravante: um clique de régua no `desligar` pararia o daemon de quem roda a
#: suíte. Os dois já estão em `hefesto_vivo.PERIGOSOS` desde antes de terem dono.
PISO_DA_ABA = 9
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
#:
#: `autostart` e `reiniciar` ENTRARAM EM 03/09/2026, e o motivo é de fonte: o
#: efeito deles está no SYSTEMD, não no `state_full`. O `enable` muda o que
#: `is-enabled` responde — que a tela lê, e por isso o interruptor se mexe —, e o
#: `restart` derruba e sobe a mesma unit, deixando o `state_full` igual ao que
#: era. Nenhum dos dois é clicado pela prova automática: os dois estão em
#: `hefesto_vivo.PERIGOSOS`.
SEM_ECO = ("atualizar", "autostart", "perfil-da-mesa", "reiniciar", "retomar",
           "ver-plugins", "ver-detalhes")
