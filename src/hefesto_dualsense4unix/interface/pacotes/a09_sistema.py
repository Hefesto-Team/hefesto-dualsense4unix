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
O `pacote()` delegava para `interface/sistema.pacote` — mas o `_leitura()` que o
alimentava preenchia TRÊS dos sete campos do `Leitura` (`status`, `autostart`,
`state`). Os outros quatro chegavam `None`, e a camada do produto faz a coisa
certa com `None`: devolve o traço. **Só que a página não é branca — ela é o
desenho dela.** Onde o pacote não escreve, o que fica na tela é o literal do
mockup, e ele é convincente:

    o que a tela mostrava          o que a máquina do usuário dizia (02/09, 04:23)
    ─────────────────────────────  ────────────────────────────────────────
    Como ele enxerga a janela: —   Sem ver nada agora (sem_foco_x)
    O que ele impõe:          —    Nada é limitado
    Perfil ativo:             —    meu_perfil
    8 linhas · nenhum aviso        6 linhas · nenhum aviso
    "Steam Input estava ligado     Steam Input desligado para o DualSense
     em 2 jogos — desliguei"       (e mais cinco, nenhuma igual às do desenho)
    [23:41:02] daemon pronto …     não há registro nenhum sendo lido

As quatro últimas eram o desenho FALANDO PELA MÁQUINA. É o defeito que o
docstring de `interface/sistema.py` nomeia como o mais caro possível nesta aba.

O `Perfil ativo` era pior que falta: **este pacote o APAGAVA.** Ele emitia a
chave `perfil` com o rótulo do PERFIL DE BATERIA, e `perfil` é o endereço do
cabeçalho — o perfil de JOGO, que `pacotes.topo()` pinta nas dez abas com
`setdefault`. Chegando primeiro, o rótulo de bateria (`None`, porque ninguém o
lia) tomava o lugar e o cabeçalho inteiro virava travessão nesta aba.
"""
from __future__ import annotations

import contextlib
import html
import re
import sys
import textwrap
import threading
import time
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.app.actions import ambiente_na_tela as _ambiente
from hefesto_dualsense4unix.app.actions import daemon_actions as _daemon
from hefesto_dualsense4unix.app.actions import emulation_actions as _emulacao
from hefesto_dualsense4unix.app.actions.config import secao_orcamento as _orcamento

# no topo não custa nada aqui: este módulo já traz `interface.sistema` logo abaixo.
from hefesto_dualsense4unix.app.actions.home_actions import palavra_do_transporte
from hefesto_dualsense4unix.app.fala_do_mapa import formata_pt_br
from hefesto_dualsense4unix.core import formas_do_endereco as _formas
from hefesto_dualsense4unix.integrations import storm_doctor as _exame
from hefesto_dualsense4unix.interface import onde as _onde
from hefesto_dualsense4unix.interface import sistema as _tela
from hefesto_dualsense4unix.utils import maquina as _maquina

from . import (
    TRAVESSAO,
    Contexto,
    identidade_de,
    jogador_de,
    perfil,
    poda,
    registrar,
)
from . import confirmacao as _confirmacao

#: CORRIGIDO EM 01/09/2026. "versoes" e "consertos" tinham dono e viraram  # (noqa-acento) id
#: `interface/sistema.py:68` já a tinha medido e escrito:
SEM_DONO: dict[str, str] = {
    "plugins": "o IPC `plugin.list` existe e só a CLI o chama — não há botão no "
               "produto de hoje (medido em `interface/sistema.py:68`)",
}

#: CADUCA — não errada quando foi escrita, caduca. Ela dizia *"a pintura não tem
#: `aba_sistema.ENDERECOS` e NÃO EXISTE na página: o gerador nunca emitiu este
NAO_CHEGA_NA_TELA: dict[str, str] = {}

SEM_ALVO_NA_PAGINA: dict[str, str] = {}

#: cadências. Medido de novo aqui, em 02/09/2026, nesta máquina:
LENTO_S = 2.0

_LENTO: dict[str, Any] = {}

REGISTRO = "registro-texto"

#: um existe porque a régua da identidade julga o `--plastico` pelo endereço do
CAMPO_DA_FITA = "fita-chips"
CAMPO_DO_CHIP = "fita-chip"

CAMPO_DO_MODO_AVULSO = "corrigir-modo-quando"

#: `aba_sistema.linhas_do_status` e a pílula muda de cor com o estado; por isso
CAMPO_DO_STATUS = "status-lista"

CAMPO_DO_VERDE = "parar-ou-retomar-verde"

MODO_A_CORRIGIR = "sim"

#: O QUE NÃO CHEGA PELO RÁDIO É O SERIAL PUBLICADO NO `state_full` — ver

_PAINEL: list[str | None] = [None]

#: O PREÇO QUE A ENTREGA DE LÁ APONTOU era o censo das camadas sumir junto. Ele
_PERGUNTA: dict[str, Any] = {}


def _a_pergunta_venceu() -> None:
    """Tira a pergunta do painel quando o gesto do usuário deixou de estar armado."""
    dono = _PERGUNTA.get("gesto")
    if not dono or _armado_agora() == dono:
        return
    if _PAINEL[0] == _PERGUNTA.get("texto"):
        _PAINEL[0] = _PERGUNTA.get("fica")
    _PERGUNTA.clear()


def _no_painel(repouso: Any) -> str:
    """O que vai ao painel AGORA: o último pedido, ou o repouso da camada.

    O VALOR DE REPOUSO É DA CAMADA DO PRODUTO (`aba_sistema.pacote`, a chave
    `registro`), e não uma frase deste pacote. O usuário decidiu ali que, sem ninguém ter
    pedido, o painel mostra o traço — e o motivo vive em `SEM_FONTE`.

    O QUE ISSO ARRANCA DA TELA, e é o ponto inteiro: enquanto ninguém escrevia
    neste endereço, o painel continuava com as quatro linhas do mockup —
    `[23:41:02] daemon pronto · 2 controles`, `perfil "Mortal Kombat" aplicado
    aos 2`, `gatilho L2 escrito, sem leitura de volta`. Nenhuma delas aconteceu.
    Um registro técnico inventado é a pior espécie de mentira desta aba: ele
    parece a prova.
    """
    _a_pergunta_venceu()
    guardado = _PAINEL[0]
    if guardado is not None:
        return guardado
    return "—" if repouso is None else str(repouso)


def _para_o_painel(texto: str, pergunta_de: str = "",
                   fica: str | None = None) -> dict[str, Any]:
    """Guarda o texto E devolve a carga que o piloto escreve na hora."""
    _PAINEL[0] = texto
    _PERGUNTA.clear()
    if pergunta_de:
        _PERGUNTA.update(gesto=pergunta_de, texto=texto, fica=fica)
    return {"mesa": {REGISTRO: texto}}


def _limpar_o_painel() -> None:
    """O painel volta ao repouso no próximo tique — a pergunta do clique 1 SAI."""
    _PAINEL[0] = None
    _PERGUNTA.clear()


#: aparecendo"*. <!-- noqa-acento: citação literal -->
#: <!-- noqa-acento: citação literal -->
RECIBO_QUE_FICA_NA_TELA = ("corrigir-vulkan",)


def _relatar_o_recibo(gesto_: str, frase: str) -> None:
    """O recibo do segundo clique: sempre ao diário, e à TELA quando ele some."""
    if not frase:
        return
    print(f"[relato] {PAGINA} · {gesto_}: {frase}", file=sys.stderr)
    if gesto_ in RECIBO_QUE_FICA_NA_TELA:
        _para_o_painel(frase)


CLIQUE_DE_NOVO = "Clique de novo para confirmar."

LARGURA_DA_PERGUNTA = 120


def _pergunta_da_steam() -> str:
    """A pergunta do clique 1 de «Aplicar aos jogos da Steam», para o painel."""
    corpo = " ".join(_daemon.DaemonActionsMixin._STEAM_APPLY_CORPO.split())
    return f"{textwrap.fill(corpo, LARGURA_DA_PERGUNTA)}\n\n{CLIQUE_DE_NOVO}"


#: `tests/unit/test_cada_botao_da_aba_sistema_faz_o_que_diz.py`. Com ela na
ARMOU = "armou"

_DICAS: dict[str, str] = {}


def _dica_do_desenho(gesto_: str) -> str:
    """O `title` que o DESENHO dá àquele botão — LIDO da página, como o rótulo."""
    if not _DICAS:
        for publicado in (True, False):
            try:
                doc = _onde.pagina(PAGINA, publicado=publicado).read_text(
                    encoding="utf-8")
            except Exception:  # pragma: no cover - página fora do disco
                continue
            for tag in re.findall(r"<button\b[^>]*>", doc):
                nome = re.search(r'data-gesto="([^"]+)"', tag)
                dica = re.search(r'title="([^"]*)"', tag)
                if nome and dica:
                    _DICAS.setdefault(nome.group(1),
                                      html.unescape(dica.group(1)).strip())
    return _DICAS.get(gesto_, "")


def _pergunta_do_botao(gesto_: str) -> str:
    """A pergunta do clique 1 de Parar, Restaurar e Proton — nenhuma palavra nova.

    SISTEMA-BOTOES-01, 13/09/2026. Os três armavam SEM dizer nada, e o `title`
    publicado de cada um promete o contrário («Pergunta antes, dizendo o que se
    perde», «Quando não dá, diz o motivo»). A pergunta é esse `title`, requebrado
    na largura do painel, mais a instrução que esta aba já escreve.
    """
    dica = _dica_do_desenho(gesto_)
    if not dica:
        return CLIQUE_DE_NOVO
    return f"{textwrap.fill(dica, LARGURA_DA_PERGUNTA)}\n\n{CLIQUE_DE_NOVO}"


def _so_armou(de_pe: bool, carga: dict[str, Any] | None = None) -> dict[str, Any]:
    """A carga do clique que ARMOU: os rótulos, a pergunta e a chave :data:`ARMOU`."""
    fora = dict(carga or {})
    fora["blocos"] = blocos_dos_botoes(de_pe)
    fora[ARMOU] = True
    return fora


def _versao() -> str:
    try:
        perfil._com_o_src()
        import hefesto_dualsense4unix as h

        return str(getattr(h, "__version__", "") or "")
    except Exception:
        return ""


def _unidade() -> str:
    """O nome da unit do daemon, do DONO dela — nunca digitado."""
    from hefesto_dualsense4unix.daemon.service_install import SERVICE_NORMAL

    return str(SERVICE_NORMAL)


def _autostart() -> str | None:
    """A saída crua de `systemctl --user is-enabled`. `None` = nem deu para perguntar.

    A UNIT NÃO SE DIGITA — ela tem dono, e digitá-la já mentiu. Medido em
    01/09/2026: esta linha trazia a literal `hefesto-dev-dualsense4unix.service`,
    sobrevivente da purga do `-dev`. A unit com esse nome NÃO EXISTE mais;
    `systemctl --user is-enabled` devolvia `not-found` enquanto a verdade da
    máquina do usuário era `enabled`. A linha "Ligar junto com o computador" da aba
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
    exame da GTK. `_refresh_storm_diag` (`daemon_actions.py` e `:1185`)
    acrescenta ao `storm_report` mais dois achados, e os dois só FALAM QUANDO HÁ
    PROBLEMA (devolvem `None` quando está tudo bem — decisão de 22/08/2026
    para o vigia do Steam Input):

    * `medir_guarda_do_steam_input()` — o vigia morto. **2,8 ms**, entra aqui;
    * `medir_prontuario_dos_jogos()` — divergência entre os manifestos da Steam
      e os perfis do disco. **7,1 s**, e por isso NÃO entra aqui — ver
      :func:`_prontuario`.

    Medido por grep antes de ligar: as duas funções tinham UM chamador em toda a
    árvore, e era a GTK. São funções de MÓDULO — não pedem janela, não pedem
    `self` — então isto é ponte, não código novo. Na bancada, agora, as duas
    devolvem `None`: o exame continua com seis linhas, e é assim que a GTK
    também se comporta hoje. A diferença aparece no dia do problema, que é
    justamente o dia em que ela precisa ver.

    E A COERÊNCIA DOS PERFIS, desde 28/09/2026 — ver :func:`linhas_dos_perfis`.
    Ela também só fala quando há problema, e é o bloco que o `doctor` já tinha.
    """
    try:
        linhas = _exame.storm_report(controles_no_cabo=_exame.controles_no_cabo(state))
    except Exception:
        return None
    try:
        vigia = _daemon.medir_guarda_do_steam_input()
    except Exception:
        vigia = None
    if vigia:
        linhas.append(vigia)
    prontuario = _prontuario(pode_perguntar)
    if prontuario:
        linhas.append(prontuario)
    som = linha_do_som_do_sistema(state)
    if som:
        linhas.append(som)
    vulkan = linha_da_sobreposicao_vulkan()
    if vulkan:
        linhas.append(vulkan)
    with contextlib.suppress(Exception):
        linhas.extend(linhas_dos_perfis(pode_perguntar))
    return linhas


#: A camada do produto traduz os três vereditos (`interface/sistema`), e `INFO`
SELO_INFORMATIVO = "[INFO]"


def linha_do_som_do_sistema(
        state: dict[str, Any] | None) -> tuple[str, str] | None:
    """*"Som do sistema: sai em X, entra por Y"* — `None` quando não se sabe.

    **O PEDIDO É DE PRODUTO, 21/09/2026:** *"outra coisa que precisamos ter é
    sincronia com os canais de saida de som e entrada de som do sistema
    operacional. isso é importante."*
    <!-- noqa-acento: citação literal -->

    **OS NOMES SÃO OS DO PAINEL DO USUÁRIO, e é o ponto inteiro.** Eles vêm da
    `Description` que o próprio servidor de som publica — as mesmas palavras
    que o painel do COSMIC mostra («Microfone do Controle 1», «HDA NVidia
    Estéreo digital (HDMI)»). Ler o nome CRU aqui daria
    `alsa_output.pci-0000_0a_00.1.hdmi-stereo`, que não é palavra de quem quer
    jogar — e, pior, não seria o mesmo texto que ela lê do outro lado da tela.

    **NÃO CUSTA UM SUBPROCESSO.** O valor foi lido pelo `ouvinte_do_som` quando
    MUDOU e viaja no `state_full`. Esta aba já paga 2,4 s de exame; mais dois
    `pactl` por tique era o que não se podia acrescentar.

    **AUSÊNCIA É AUSÊNCIA.** Sem o bloco (daemon velho, `pactl` fora do PATH,
    ouvinte que ainda não respondeu) a linha NÃO APARECE — em vez de aparecer
    dizendo travessão. Uma linha de exame que diz "não sei" sobre som ensina
    que há algo errado com o som.
    """
    if not isinstance(state, dict):
        return None
    bloco = state.get("som_do_sistema")
    if not isinstance(bloco, dict):
        return None
    saida = str(bloco.get("saida_nome") or bloco.get("saida") or "").strip()
    entrada = str(bloco.get("entrada_nome") or bloco.get("entrada") or "").strip()
    if not saida and not entrada:
        return None
    partes = []
    if saida:
        partes.append(f"sai em {saida}")
    if entrada:
        partes.append(f"entra por {entrada}")
    return (SELO_INFORMATIVO, f"Som do sistema: {', '.join(partes)}")


def vulkan_corrigido() -> bool:
    """A pílula «Corrigir Vulkan»: acesa quando o lançador tira as camadas da Steam."""
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

    try:
        return cv.camadas_da_steam_fora()
    except Exception:
        return False


def linha_da_sobreposicao_vulkan() -> tuple[str, str] | None:
    """*"Sobreposição Vulkan: sem a da Steam"*, ou a Steam decide."""
    try:
        from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

        if not cv.a_steam_instalou_as_camadas():
            return None
        return (SELO_INFORMATIVO, cv.frase_do_estado(vulkan_corrigido()))
    except Exception:
        return None


_PERFIS: dict[str, Any] = {}


def linhas_dos_perfis(pode_perguntar: bool = True) -> list[tuple[str, str]]:
    """A coerência dos perfis entre si, no exame — e só quando há o que dizer."""
    if not pode_perguntar:
        return list(_PERFIS.get("linhas") or [])
    from hefesto_dualsense4unix.profiles import sanidade
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    try:
        pasta = profiles_dir()
        assinatura: tuple[Any, ...] | None = (str(pasta), *(
            (arq.name, arq.stat().st_mtime_ns) for arq in sorted(pasta.glob("*.json"))))
    except OSError:
        assinatura = None
    if assinatura is not None and _PERFIS.get("assinatura") == assinatura:
        return list(_PERFIS.get("linhas") or [])
    try:
        achados = sanidade.verificar_perfis_do_disco()
    except OSError as erro:
        motivo = erro.strerror or type(erro).__name__
        linhas = [("[WARN]", f"não deu para ler os perfis ({motivo})")]
    else:
        linhas = [(tag, achado.mensagem) for (tag, _), achado in zip(
            sanidade.linhas_de_relatorio(achados), achados, strict=True)
        ] if achados else []
    _PERFIS.update(assinatura=assinatura, linhas=linhas)
    return list(linhas)


_PRONTUARIO: dict[str, Any] = {}

_PRONTUARIO_EM_VOO: list[bool] = [False]

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
    """O prontuário SEM a varredura dos executáveis. Guarda o resultado e sai.

    ELA CUSTAVA 6,9 SEGUNDOS E ESTA TELA NÃO LIA UM BYTE DO USUÁRIO — medido em
    06/09/2026, e é a cura do pior tique das dez abas.

    `medir_prontuario_dos_jogos()` (`daemon_actions.py:596`) é a composição de
    dois donos: `prontuario_dos_jogos.levantar_censo()` e
    `interpretar_prontuario_dos_jogos(censo)`. O `examinar=True` do censo é o
    que abre o executável de cada jogo instalado para descobrir a API de
    entrada — e é ele, sozinho, que leva os 7 s. **Medido nesta máquina, com o
    veredito conferido nas duas formas:**
    <!-- noqa-acento: `examinar` é o nome do parâmetro do produto -->

        examinar=False        12 a 18 ms   22 jogos   veredito: None
        examinar=True      6.900 ms       22 jogos   veredito: None

    **O ÚNICO CAMPO QUE A LINHA DESTA TELA LÊ É `ponte_divergente`**, e ele não
    encosta na varredura: `prontuario_dos_jogos.py:385` o define como *"há
    carimbo de ponte confirmada"* contra *"a lista de exceções de hoje"*, os dois
    lidos do disco em milissegundos. Quem diz isso é o docstring do
    dono, em `:559`: *"O carimbo não depende de ler executável nenhum"*. A
    `evidencia`, que é tudo o que os 7 s produzem, entra em `NAO_SEI` e em
    `IMPEDIDO`, e nenhum dos dois chega a esta aba.

    **POR QUE NÃO CHAMAR `medir_prontuario_dos_jogos`:** ele não tem por onde
    receber o `examinar`, e `daemon_actions.py` está no `nao_toca` desta
    frente. Compor os dois donos aqui não é um segundo dono do fato — é o mesmo
    par, com o parâmetro que esta tela pode pagar. `interpretar_…` é PURA de
    propósito, e o docstring dela diz por quê: *"recebe o censo pronto: a
    leitura do disco é lenta o bastante para nunca rodar na linha do GTK"*. O
    diff de uma linha que devolveria o dono único está no relato desta frente.

    O `finally` é o que impede a thread de ficar presa "em voo" para sempre
    quando a medição levanta — sem ele, um erro numa Steam meio instalada
    calaria o prontuário até o fim da sessão.
    """
    try:
        from hefesto_dualsense4unix.integrations import prontuario_dos_jogos

        achado = _daemon.interpretar_prontuario_dos_jogos(
            prontuario_dos_jogos.levantar_censo(examinar=False))
    except Exception:
        achado = None
    _PRONTUARIO["achado"], _PRONTUARIO["quando"] = achado, time.monotonic()
    _PRONTUARIO_EM_VOO[0] = False


ROTULO_DA_IDENTIDADE = "Identidade de fábrica"

#: O QUE SE ESCREVE NO LUGAR DE UM SERIAL QUE O `state_full` NÃO TROUXE. É a
#:     transporte  state_full.serial  lido DO APARELHO (`ler_identidade_pelo_cabo`)
#: DAEMON: o `state_full` traz `serial: None` para quem está no rádio.
SEM_SERIAL_LIDO = "o serial só é lido no cabo"


def _nome_do_plastico(c: dict[str, Any], mesa: list[dict[str, Any]]) -> str:
    """O nome DESTE controle, pelo dono compartilhado — ou `""`.

    O dono é `pacotes.identidade_de`, e ele já sabe a ordem das quatro fontes
    (*o que O usuário nomeou > o modelo decodificado > o nome da MESA > o transporte
    só*), já descarta o `"Não sei"` da mesa e já casa por `uniq` em vez de por
    posição. Escrever aqui uma quinta leitura seria a segunda verdade que a lei
    de produto de 03/09 proíbe — e as abas 02 e 06 já o chamam com `ctx.mesa`.

    OS DOIS ÚLTIMOS DEGRAUS DE `identidade_de` NÃO SERVEM COMO NOME. Ele nunca
    devolve vazio: sem nome nenhum cai no transporte e, sem nem isso, no
    travessão. Nesta aba o transporte já está escrito ao lado — `P2 · BT · BT`
    afirmaria a mesma coisa duas vezes, e o travessão leria como defeito onde o
    que há é ausência de leitura.

    **O DESCARTE PASSOU A PERGUNTAR AO DONO — ONDA4-S10, 06/09/2026.** Ele era
    um conjunto CONGELADO no import (`{TRAVESSAO, *VIA_DO_TRANSPORTE.values()}`),
    montado sobre a tabela da sigla. Um conjunto de palavras é uma cópia da
    tradução: no dia em que o último degrau de `identidade_de` mudar de língua,
    o conjunto descarta a palavra de ontem e deixa passar a de hoje — e a linha
    volta a dizer `P2 · rádio · rádio`, sem erro, sem log e sem régua vermelha.

    AGORA A PERGUNTA É AO PRÓPRIO `identidade_de`, com um controle que só tem o
    transporte: o que ele devolve aí **é** o último degrau, para ESTE
    transporte, na língua que ele fale hoje. Não há palavra escrita aqui.
    """
    nome = str(identidade_de(c, mesa) or "").strip()
    ultimo_degrau = str(identidade_de({"transport": c.get("transport")}) or "").strip()
    return "" if nome in (TRAVESSAO, ultimo_degrau) else nome


def _linha_de_identidade(c: dict[str, Any], mesa: list[dict[str, Any]]) -> str:
    """`P1 · White · cabo · <serial>` — a identidade de fábrica de UM controle.

    DECISÃO 10 DO USUÁRIO, 03/09/2026: *"Serial de fábrica: inteiro, e SÓ na aba
    Sistema (a de diagnóstico)."* Ele é identificador único como um MAC, o daemon
    já o publica (`ipc_handlers._identidade_publicada`, ROTA-A de 02/09) e até
    hoje NENHUMA tela do produto o mostrava — nem esta, nem a GTK.

    O LUGAR É O PAINEL "Detalhes técnicos", e a escolha é de sobriedade: é a
    caixa de diagnóstico desta aba, ela já existe, já tem endereço
    (`registro-texto`) e já está publicada. Uma linha de estado nova custaria
    30px numa coluna que o gerador engenha para acabar no mesmo y da irmã — e
    seria mudança de DESENHO, que é decisão de produto.

    O NOME E O NÚMERO VÊM DE CIMA — 03/09/2026, e é a lei de produto:

        "se no topo tá mostrando controle white player 1, então cada aba vai
         usar os controles lá de cima. Não mistura com a info dos mockups."

    ESTA LINHA LIA SÓ O `modelo` DO `state_full`, e o `modelo` sai do serial —
    que o daemon **não publica para quem está no rádio** (ver
    :data:`SEM_SERIAL_LIDO`: o aparelho responde, o publicador é que cala).
    Fotografado na bancada em 03/09/2026, com o P1 no cabo e o P2 no rádio:

        a fita, no topo      P1 · White · USB
                             P2 · Galactic Purple · BT
        este painel, abaixo  P1 · White · cabo · <os 17 caracteres>
                             P2 · rádio · o serial só é lido no cabo

    O MESMO APARELHO, NA MESMA TELA, com a identidade presente num lugar e
    ausente no outro — e o dado existia: `mesa_viva.LeitorDeCor` já o lê pelo
    broker e traduz o código de fábrica pelo mapa DO USUÁRIO
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
    defeito. É a regra de produto — *campo sem informação não mostra nada*.

    A PALAVRA DO TRANSPORTE SAIU DAQUI — ONDA4-S10, 06/09/2026. Esta linha era
    `"cabo" if transport == "usb" else "rádio"`, e ela **já estava certa** — o
    que é exatamente o problema: era a QUARTA cópia de uma tradução que tem
    dona, e a única que dizia a palavra de produto. Duas coisas ela não tinha, e a
    dona tem: o transporte que o mapa não conhece volta CRU, para alguém o ver,
    e o transporte AUSENTE diz *"não sei por onde"* em vez de afirmar rádio
    sobre um campo que ninguém leu — que é o que o `else` fazia.

    **Este passo não muda um pixel na bancada**, e é o que impede a próxima
    pessoa de concluir que "a 09 já estava certa" e deixar a cópia viva.
    """
    numero = jogador_de(c)
    serial = str(c.get("serial") or "")
    via = palavra_do_transporte(c.get("transport"))
    quem = " · ".join(p for p in (f"P{numero}" if numero else "",
                                 _nome_do_plastico(c, mesa), via) if p)
    return f"{quem} · {serial or SEM_SERIAL_LIDO}"


def _repouso_do_painel(state: dict[str, Any] | None,
                       mesa: list[dict[str, Any]] | None = None) -> str:
    """O painel "Detalhes técnicos" SEM ninguém clicar — e ele deixa de ser um traço.

    A GTK NUNCA TEVE UM TRAÇO AQUI: o `Gtk.TextView` dela fica sempre com a saída
    de `systemctl status <unit>` (`daemon_actions.py` e `:2549`), reescrita
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

    O DIÁRIO SAIU DO REPOUSO — SISTEMA-BOTOES-01, 13/09/2026, a §3 da
    TELA-CALADA-04. As linhas do journal traziam o `uniq=` inteiro do controle,
    e o funil do piloto acusava `[texto banido] 'uniq'` a cada abertura da aba.
    `_systemctl_status_text` pede `-n 0`; o diário é do «Ver detalhes».

    A `mesa` É A FITA DO TOPO, e ela entra por aqui só para atravessar até
    :func:`_linha_de_identidade` — nada nesta função a lê. Tem valor padrão
    porque a faixa lenta a repassa e as réguas chamam as duas de um argumento
    só; sem mesa o painel escreve o que o `state_full` sozinho sabe, que é
    menos, e nunca o nome do desenho.
    """
    partes: list[str] = []
    try:
        status = _matriz()._systemctl_status_text(_unidade())
    except Exception as erro:
        status = f"Não consegui perguntar ao systemd: {erro}"
    partes.append(str(status).strip())
    controles = (state or {}).get("controllers") if isinstance(state, dict) else None
    vivos = [c for c in (controles or [])
             if isinstance(c, dict) and c.get("connected") is not False]
    if vivos:
        partes.append("")
        partes.append(ROTULO_DA_IDENTIDADE)
        partes += [f"  {_linha_de_identidade(c, mesa or [])}" for c in vivos]
    # bug»*. <!-- noqa-acento: citação literal --> O painel rola até o
    partes += ["", ROTULO_DO_DIARIO, _diario()]
    return "\n".join(partes).strip()


ROTULO_DO_DIARIO = "Registro do serviço"


#: `aba_sistema.ENDERECOS["bateria-frase"]`, declarado como
CAMPO_DO_ALCANCE = "bateria-frase"

CAMPO_DOS_PENDENTES = f"{CAMPO_DO_ALCANCE}-pendentes"

APELIDO_NA_TELA: dict[str, str] = {
    "Barra de luz": "luz",
    "Microfone por BT": "microfone",
}


def _plural(quantos: int, singular: str, plural: str) -> str:
    """Uma das duas palavras, pela contagem. ``0`` usa o plural, como em
    português.

    POR QUE ELE NASCEU AQUI — 11/09/2026, A1-038/039/040. Três recados desta
    aba escreviam `conserto(s) automático(s)`, `jogo(s)` e
    `plugin(s) carregado(s)`. **O plural entre parênteses não existe em língua
    nenhuma além da nossa** e não tem como ser traduzido: em inglês são duas
    formas, em russo são três. A casa já resolvia isso em `aba08._plural` e em
    `integrations.ordens_da_mesa._plural`; o que faltava era esta camada ter o
    seu.
    """
    return singular if quantos == 1 else plural


def _lista_em_portugues(nomes: list[str]) -> str:
    """`a`, `b` e `c` — com "e" antes do último. Vazio devolve vazio."""
    if not nomes:
        return ""
    if len(nomes) == 1:
        return nomes[0]
    return f"{', '.join(nomes[:-1])} e {nomes[-1]}"


# a diz inteira em `aba_sistema.frase_do_teto`.


def _perfil_da_bateria() -> str | None:
    """A chave do Perfil de Bateria GRAVADA no `maquina.json`, ou `None`."""
    try:
        return _orcamento.perfil_na_tela()
    except Exception:
        return None


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


_LENTO_EM_VOO: list[bool] = [False]

_LENTO_SELO: list[int] = [0]


def _ler_a_faixa_lenta(state: dict[str, Any] | None,
                       pode_perguntar: bool = True,
                       mesa: list[dict[str, Any]] | None = None,
                       ) -> tuple[Any, Any, Any, Any, Any]:
    """As cinco leituras caras, de verdade. Não se chama do tique — ver abaixo."""
    return (_autostart(), _achados(state, pode_perguntar), _perfil_da_bateria(),
            _status_do_daemon(state), _repouso_do_painel(state, mesa))


def _guardar_a_faixa_lenta(state: dict[str, Any] | None,
                           mesa: list[dict[str, Any]] | None = None,
                           selo: int | None = None) -> None:
    """A releitura, fora do laço do GTK. O `finally` é o que destrava o voo."""
    try:
        valor = _ler_a_faixa_lenta(state, mesa=mesa)
        if selo is None or selo == _LENTO_SELO[0]:
            _LENTO["valor"] = valor
    finally:
        if "valor" in _LENTO and (selo is None or selo == _LENTO_SELO[0]):
            _LENTO["quando"] = time.monotonic()
        _LENTO_EM_VOO[0] = False


def _faixa_lenta(state: dict[str, Any] | None,
                 mesa: list[dict[str, Any]] | None = None,
                 ) -> tuple[Any, Any, Any, Any, Any]:
    """As leituras CARAS: SÍNCRONA na primeira, EM THREAD nas releituras.

    Elas saem deste processo — subprocesso, disco — e nenhuma muda entre dois
    piscares. O tique da pintura é de 100 ms; a faixa lenta é de 2 s, que é a
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
        _LENTO["valor"] = _ler_a_faixa_lenta(state, pode_perguntar=False, mesa=mesa)
        _LENTO["quando"] = agora
        return _LENTO["valor"]  # type: ignore[no-any-return]
    if agora - float(_LENTO["quando"]) >= LENTO_S and not _LENTO_EM_VOO[0]:
        _LENTO_EM_VOO[0] = True
        threading.Thread(target=_guardar_a_faixa_lenta,
                         args=(state, mesa, _LENTO_SELO[0]),
                         daemon=True).start()
    return _LENTO["valor"]  # type: ignore[no-any-return]


@poda
def _esquecer_a_mesa_de_antes(na_mesa: frozenset[str]) -> None:
    """Um controle saiu: a faixa lenta inteira é de antes dele sair."""
    _LENTO.clear()
    _LENTO_SELO[0] += 1


#: custa menos de um milissegundo (um `listdir` em `/sys/class/bluetooth`, o
#: ambiente do processo, um JSON pequeno), e ainda assim ficam na cadência da
_BARATO: dict[str, Any] = {}


def _sessao(variaveis: dict[str, str] | None = None) -> str | None:
    """``Wayland · COSMIC`` — o tipo da sessão e a área de trabalho, ou `None`."""
    import os

    from hefesto_dualsense4unix.app import ambiente

    fonte = os.environ if variaveis is None else variaveis
    tipo = {"wayland": "Wayland", "x11": "X11"}.get(
        str(fonte.get("XDG_SESSION_TYPE", "")).strip().lower(), "")
    try:
        ident = ambiente.ambiente_efetivo(variaveis=fonte)
        cru = ambiente.ambiente_lido(variaveis=fonte)
    except Exception:
        ident, cru = "", ""
    if ident in ambiente.NOMES_DE_TELA and ident != "outro":
        area = ambiente.NOMES_DE_TELA[ident]
    else:
        area = cru.split(":", 1)[0].strip() if cru else ""
    partes = [p for p in (tipo, area) if p]
    return " · ".join(partes) or None


def _adaptadores() -> int | None:
    """Quantos adaptadores Bluetooth a máquina tem. `None` = não deu para ler."""
    try:
        from hefesto_dualsense4unix.integrations import mesa_de_radio

        return len(mesa_de_radio.adaptadores_bluetooth())
    except Exception:
        return None


def proton_fixado() -> bool | None:
    """A pílula «Fixar Proton»: há trava NOSSA registrada nos jogos?"""
    import json

    try:
        from hefesto_dualsense4unix.integrations import proton_pin

        caminho = proton_pin.default_lock_state_path()
    except Exception:
        return None
    try:
        dado = json.loads(caminho.read_text(encoding="utf-8"))
    except OSError:
        return False
    except ValueError:
        return None
    if not isinstance(dado, dict):
        return None
    return bool(dado.get("tool_name")) and bool(dado.get("changes"))


def _leituras_baratas() -> tuple[int | None, str | None, bool | None]:
    """`(adaptadores, sessão, proton fixado)`, relidos a cada :data:`LENTO_S`."""
    agora = time.monotonic()
    if not _BARATO or agora - float(_BARATO.get("quando") or 0.0) >= LENTO_S:
        _BARATO["valor"] = (_adaptadores(), _sessao(), proton_fixado())
        _BARATO["quando"] = agora
    return _BARATO["valor"]  # type: ignore[no-any-return]


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
    # `"online_systemd" if ctx.state else "offline"`, e o comentário que a
    # camada de estado (`aba_sistema._ESTADO_DO_HEFESTO`) tem os quatro textos
    return _tela.Leitura(
        status=status,
        autostart=auto,
        state=ctx.state or None,
        achados=achados,
        deteccao=_frase(_daemon.descrever_deteccao_de_janela, ctx.state),
        ambiente=_frase(_ambiente.descrever_display_grafico, ctx.state),
        perfil=perfil_da_bateria,
        sessao=_leituras_baratas()[1],
        adaptadores=_leituras_baratas()[0],
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


#
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
    """`Selecionar:` — o rótulo, lido de `monta.ROTULO_DA_FITA`."""
    try:
        return str(_monta().ROTULO_DA_FITA)
    except Exception:
        return ""


def _um_chip(c: dict[str, Any], escolhido: str = "") -> str:
    """Um chip da fita, com o que se LEU daquele controle — e nada mais.

    A COR SÓ APARECE SE ALGUÉM A LEU. Sem leitura o chip perde a classe
    `plastico` (e com ela a borda colorida), perde o `--plastico` e perde o nome:
    é a regra de produto, *campo sem informação não mostra nada*. Inventar um tom para
    preencher seria repetir o defeito que esta frente veio matar, só que com
    outra cor.

    E O QUE SAI NÃO É `Não sei` NEM `—`: os dois são a AUSÊNCIA de leitura
    escrita como se fosse um nome. O chip termina no transporte.

    `escolhido` É O `pref` DE QUEM ACENDE, e o padrão `""` não acende ninguém —
    que é o certo enquanto o `Todos` está na fita, porque quem acende é ele.

    **A FITA E A LINHA DE IDENTIDADE FALAM A MESMA LÍNGUA — ONDA4-S10,
    06/09/2026.** A foto de 03/09 transcrita em `_linha_de_identidade` pegou as
    duas na MESMA tela em dialetos diferentes: a fita dizia a sigla de máquina e
    o painel logo abaixo dizia a palavra de produto. O chip lia `via` da mesa, que é a
    sigla; agora ele pergunta ao dono, com o `transporte` cru que a mesa publica
    ao lado. Nenhuma palavra é escrita aqui.
    """
    nome = str(c.get("nome") or "")
    cor = str(c.get("cor") or "")
    via = html.escape(palavra_do_transporte(c.get("transporte")))
    jogador = html.escape(str(c.get("jogador") or ""))
    ponto = ' <span class="pt">•</span> '
    aceso = " on" if escolhido and str(c.get("pref") or "") == escolhido else ""
    if not cor:
        return (f'<label class="chip{aceso}" data-campo="{CAMPO_DO_CHIP}">'
                f"P{jogador}{ponto}{via}</label>")
    return (f'<label class="chip plastico{aceso}" data-campo="{CAMPO_DO_CHIP}"'
            f' style="--plastico:{html.escape(_cor_da_zona(cor))}"'
            f' title="{html.escape(nome)} — a borda é a cor do plástico">'
            f"P{jogador}{ponto}{html.escape(nome)}{ponto}{via}</label>")


def _html_da_fita(mesa: list[dict[str, Any]]) -> str:
    """O miolo da `.fita` desta aba, montado com a mesa VIVA."""
    if not mesa:
        return ""
    mostra_todos, escolhido = _monta().escolha_da_fita("todos", mesa)
    partes = [f"<span>{html.escape(_rotulo_da_fita())}</span>"]
    if mostra_todos:
        partes.append('<label class="chip on">Todos</label>')
    partes += [_um_chip(c, "" if mostra_todos else escolhido) for c in mesa]
    return "\n      ".join(partes)


# texto, largura, `value`, classe, cor, fundo, `--plastico` e `innerHTML`, e não
def _curto(classe: str) -> str:
    """`com.system76.CosmicTerm` -> `CosmicTerm`. O último pedaço, e nada mais."""
    pedaco = classe.rsplit(".", 1)[-1].strip()
    return pedaco or classe


def _quem_esta_na_frente(state: Any) -> str:
    """A classe da janela em foco AGORA, ou `""` — a MESMA regra da GTK."""
    if not isinstance(state, dict) or not state.get("window_detect_seeing"):
        return ""
    valor = state.get("window_detect_current_class")
    if isinstance(valor, str) and valor and valor != "unknown":
        return valor
    return ""


def _com_quem_esta_na_frente(valor: Any, state: Any) -> str | None:
    """O valor da linha com o nome CURTO ao lado, e o INTEIRO no `title` dele."""
    if not isinstance(valor, str) or not valor or valor == _tela.NAO_DEU:
        return None
    classe = _quem_esta_na_frente(state)
    if not classe:
        return None
    return (f"{html.escape(valor)} <span class=\"pt\">·</span> "
            f'<span title="{html.escape(classe)}">{html.escape(_curto(classe))}</span>')


@registrar("09-sistema.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    """DELEGA para `interface/sistema.pacote` — a camada do PRODUTO.

    ELA JÁ EXISTIA E NUNCA TINHA SIDO LIGADA: dezoito nomes públicos em
    `interface/sistema.py`, e o `casa-sabe` os listava como promessa sem caminho.
    E ela foi escrita PARA ESTA PÁGINA — as chaves que devolve são os
    `data-campo` daqui: `hefesto-estado`, `hefesto-pausa`,
    `hefesto-troca-de-perfil`, `hefesto-ambiente`.

    E SABE MAIS QUE O PACOTE ANTIGO: cada valor vem com `txt`, a classe
    do selo (`cls`), o glifo (`g`) e a dica. O pacote antigo só tinha o texto, e as
    frases dele eram deste arquivo, enquanto estas vêm da camada do produto.

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
        # E O BOTÃO DO MODO IMPROVISADO SAI DAQUI TAMBÉM, pelo mesmo argumento
        nada = str(_monta().NADA_A_DIZER)
        return {"sem_dono": {"tela": {"sem_dono": True, "oque": str(erro)}},
                "blocos": blocos_dos_botoes(_de_pe(ctx)),
                CAMPO_DO_MODO_AVULSO: (
                    MODO_A_CORRIGIR
                    if _status_do_daemon(ctx.state) == "online_avulso" else ""),
                REGISTRO: _no_painel(None),
                CAMPO_DO_VERDE: "",
                "exame-lista": nada,
                **razoes_do_cinza(ctx),
                "cobertura": {"pintados": 0, "sem_dono": 1}}

    fora: dict[str, object] = {}
    fora[CAMPO_DO_STATUS] = _html_do_status(bruto.get("status") or [])
    fora["hefesto-autostart"] = bruto.get("autostart")
    fora["proton-fixado"] = _leituras_baratas()[2]
    fora["vulkan-corrigido"] = vulkan_corrigido()
    _, _, perfil_da_bateria, estado, repouso = _faixa_lenta(ctx.state or None,
                                                            ctx.mesa)
    fora["bateria-perfil"] = perfil_da_bateria
    fora[REGISTRO] = _no_painel(repouso)
    exame = bruto.get("exame")
    # D-A-CONTAGEM-DO-EXAME-SAIU — 25/09/2026, 22h13, pedido: *«Remove esse
    if isinstance(exame, dict):
        fora["exame-lista"] = _html_do_exame(_com_os_avisos(exame, ctx))
    tira = _html_da_fita(ctx.mesa)
    if tira:
        fora[CAMPO_DA_FITA] = tira
    fora.update(razoes_do_cinza(ctx))
    fora["sem_dono"] = {k: {"sem_dono": True, "oque": v} for k, v in SEM_DONO.items()}
    fora["cobertura"] = {"pintados": len(fora), "sem_dono": len(SEM_DONO)}
    fora[CAMPO_DO_MODO_AVULSO] = (
        MODO_A_CORRIGIR if estado == "online_avulso" else "")
    de_pe = estado in _tela.DE_PE
    pausado = _pausado(ctx)
    fora[CAMPO_DO_VERDE] = MODO_A_CORRIGIR if (pausado or not de_pe) else ""
    fora["blocos"] = blocos_dos_botoes(de_pe, pausado)
    return fora


#: o traduz em selo, classe e glifo é o dono da tradução (`interface/sistema.
VEREDITO_DO_AVISO = "[WARN]"


def _avisos_do_produto(ctx: Contexto) -> list[dict[str, Any]]:
    """As linhas que a coluna Atenção da Jogar publicava, já na forma do exame.

    A-TELA-PERGUNTA-AO-DONO-01, 28/09/2026. A coluna Atenção saiu da Jogar em
    07/09, por ordem de produto, e as fontes que só ela publicava ficaram caladas no
    produto: as de `painel.AVISOS_DA_TELA` e as duas que o pacote da Jogar
    junta a elas (o opt-out antigo e a divergência de máscara). Ficam fora as
    que a tela já diz noutro lugar (`a01_jogar._avisos_com_outra_casa`): a
    ponte com o jogo, que aqui saía como «AVISO · Nenhuma», e a pausa, o
    detector cego e o Freestyle, que o Status desta aba e a Jogar já mostram
    (`a01_jogar.FONTES_DO_PAINEL_COM_OUTRA_CASA`).

    QUEM ESCOLHE E ORDENA É O DONO DO CANAL (`a01_jogar.coluna_de_atencao`),
    e quem traduz o veredito em selo é `interface/sistema.exame` — nenhuma das
    duas contas se refaz aqui. Uma fonte que levanta não apaga o exame: vira
    uma linha que diz qual não respondeu, como as fontes do canal já fazem.

    POR TIQUE, e não na faixa lenta: as fontes leem o `state` que o tique já
    trouxe, e a única que abre arquivo é a lembrança do gamepad (um `stat` e
    uma linha). Medido em lar de mentira, 28/09/2026: 0,030 ms por chamada.
    """
    from . import a01_jogar

    try:
        avisos = a01_jogar.coluna_de_atencao(ctx)
    except Exception as erro:
        avisos = [{"texto": f"os avisos do produto não responderam "
                            f"({type(erro).__name__})."}]
    achados = [(VEREDITO_DO_AVISO, str(a.get("texto") or "")) for a in avisos
               if a.get("texto")]
    linhas: list[dict[str, Any]] = _tela.exame(achados)["linhas"]
    return linhas


def _com_os_avisos(exame: dict[str, Any], ctx: Contexto) -> dict[str, Any]:
    """O exame da camada do produto, com os avisos do produto no fim da lista."""
    avisos = _avisos_do_produto(ctx)
    if not avisos:
        return exame
    linhas = list(exame.get("linhas") or [])
    vazio = str(exame.get("vazio") or "")
    if not linhas and vazio:
        linhas = _tela.exame([("[INFO]", vazio)])["linhas"]
    return {**exame, "linhas": linhas + avisos, "vazio": ""}


def _pausado(ctx: Contexto) -> bool:
    """A pausa está ativa AGORA? O dado é `state_full["paused"]`, e só ele."""
    return bool(isinstance(ctx.state, dict) and ctx.state.get("paused"))


def _html_do_status(linhas: list[dict[str, Any]]) -> str:
    """As quatro linhas do Status, na MESMA marcação das linhas do exame."""
    return "".join(linha_do_status(linha) for linha in linhas)


def linha_do_status(linha: dict[str, Any]) -> str:
    """Uma linha do Status. Tudo escapado: o texto vem da camada do produto."""
    cls = html.escape(str(linha.get("cls") or "nt"))
    ident = html.escape(str(linha.get("id") or ""))
    dica = html.escape(str(linha.get("dica") or ""))
    titulo = f' title="{dica}"' if dica else ""
    href = str(linha.get("href") or "")
    tag, fim = ("a", "a") if href else ("div", "div")
    destino = f' href="{html.escape(href)}"' if href else ""
    return (f'<{tag} class="saude{" vai" if href else ""}" data-id="{ident}"{destino}>'
            f'<span class="selo {cls}"><span class="sg">'
            f'{html.escape(str(linha.get("g") or ""))}</span>'
            f'{html.escape(str(linha.get("selo") or ""))}</span>'
            f'<span class="txt"{titulo}>'
            f'<span>{html.escape(str(linha.get("txt") or ""))}</span></span>'
            f"</{fim}>")


def _html_do_exame(exame: dict[str, Any]) -> str:
    """As duas colunas de achados, prontas para o `innerHTML` de `.saude-cols`."""
    linhas = exame.get("linhas") or []
    if not linhas:
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
    `overflow:hidden;text-overflow:ellipsis;white-space:nowrap`. Medido na bancada, na foto do
    produto instalado, com um controle no cabo — **CINCO das
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
    quadro, que é desenho, e desenho é decisão de produto.

    O «O QUE FAZER» NÃO CHEGA MAIS À TELA — SISTEMA-BOTOES-01, 13/09/2026. Ele é
    instrução do `doctor`, e a linha da `WirePlumber` mandava clicar em
    «Aplicar correções» na aba Sistema, um botão que não existe. A frase é
    cortada no texto E no `title`, em `PREFIXO_DA_CURA` lido do dono
    (`storm_doctor`); o que fica é o estado. A régua do doctor continua exigindo
    o prefixo na string, que é o terminal.
    """
    cls = html.escape(str(achado.get("cls") or "nt"))
    txt = str(achado.get("txt") or "").split(_exame.PREFIXO_DA_CURA, 1)[0].rstrip()
    return (f'<div class="saude"><span class="selo {cls}">'
            f'<span class="sg">{html.escape(str(achado.get("g") or ""))}</span>'
            f'{html.escape(str(achado.get("selo") or ""))}</span>'
            f'<span class="txt" title="{html.escape(txt, quote=True)}">'
            f'<span>{html.escape(frase_curta_do_exame(txt))}</span>'
            "</span></div>")


#: ali. Pra ficar simples pro user.»* <!-- noqa-acento: citação literal -->
CORTES_DA_CABECA = (" (", " — ", ". ")


def cabeca_da_frase(frase: str) -> str:
    """`quirk anti-storm ativo (054c:…)` -> `Quirk anti-storm ativo`."""
    cabeca = frase.strip()
    for corte in CORTES_DA_CABECA:
        pedaco = cabeca.split(corte, 1)[0].strip()
        if pedaco:
            cabeca = pedaco
    cabeca = cabeca.rstrip(".").strip()
    return cabeca[:1].upper() + cabeca[1:] if cabeca else ""


#: <!-- noqa-acento: citação literal -->, e o jargão não é simples.
FRASES_CURTAS_DO_EXAME: tuple[tuple[str, str], ...] = (
    ("quirk anti-storm ativo", "Proteção do áudio USB ligada"),
    ("o cinto extra do áudio usb não está posto",
     "Proteção extra do áudio desligada"),
    ("steam input: não encontrei a steam", "Steam não encontrada"),
    ("steam input ligado para", "Steam Input ligado em jogos"),
    ("steam input ligado no ajuste global", "Steam Input ligado na Steam toda"),
    ("steam input desligado (com exceções", "Steam Input desligado, com exceções"),
    ("steam input desligado para o dualsense", "Steam Input desligado"),
    ("wireplumber configurado", "Ajuste de áudio instalado"),
    ("o ajuste de áudio do hefesto não está instalado",
     "Ajuste de áudio não instalado"),
    ("o mic e o fone do controle estão desligados de propósito",
     "Mic e fone desligados por escolha"),
    ("regra áudio-off inativa", "Mic e fone do controle liberados"),
    ("cura do travamento do usb ativa", "Cura do travamento do USB ativa"),
    ("a cura do travamento está agendada", "Cura do travamento agendada"),
    ("cura do travamento do usb ausente", "Cura do travamento do USB ausente"),
)


def frase_curta_do_exame(frase: str) -> str:
    """A frase da tela para um achado do exame: a da tabela, ou a cabeça."""
    chave = frase.strip().lower()
    for comeco, curta in FRASES_CURTAS_DO_EXAME:
        if chave.startswith(comeco):
            return curta
    return cabeca_da_frase(frase)


# ---------------------------------------------------------------------------
from . import gesto  # noqa: E402

SUFIXO_DA_RAZAO = "-razao"

#: São exatamente os três que `aba_sistema.travas()` alcança E que esta aba
#: (SISTEMA-BOTOES-01), pela decisão de produto D-OS-PLUGINS-APARECEM-ONDE-AGEM
BOTOES_CINZAS = ("reiniciar",)

#: troca o RÓTULO do botão do `daemon.reload`, logo o desenho mudou um pixel e
ESPERA_A_PUBLICACAO: dict[str, str] = {
    # publicar as dez abas, para os quatro DualSense aparecerem na bancada.
}


def razoes_do_cinza(ctx: Contexto) -> dict[str, str]:
    """A razão de cada botão cinza AGORA — vazia quando ele tem o que fazer."""
    try:
        travas = _tela.travas(_leitura(ctx))
    except Exception:
        travas = {}
    return {f"{nome}{SUFIXO_DA_RAZAO}": (_trava(ctx, nome, travas) or "")
            for nome in BOTOES_CINZAS}


def _trava(ctx: Contexto, nome: str,
           travas: dict[str, str] | None = None) -> str | None:
    """O motivo pelo qual aquele gesto estaria CINZA agora, ou `None`.

    `travas` É A CONTA JÁ FEITA, e existe para o TIQUE: :func:`razoes_do_cinza`
    pergunta à camada uma vez e passa o resultado aos três, em vez de montar
    três `Leitura` por volta. Sem ela, o comportamento é o de sempre.

    A CONTA É DA CAMADA DO PRODUTO — `aba_sistema.travas(leitura)` — e ela já
    estava escrita, medida e ligada até a penúltima camada quando esta frente
    começou: cobre `retomar`, `desligar`, `reiniciar` e `ver-detalhes`, com o
    motivo em português pronto para o tooltip. O que
    faltava era alguém chamá-la.

    ELA NÃO PINTA O BOTÃO DE CINZA, E ISSO ESTÁ DECLARADO. O desenho não tem
    estado apagado para `.btn` (medido: a folha desta página tem
    `.seg button:disabled`, e nada para `.btn`), e inventá-lo mudaria o que o usuário
    aprovou. O que esta função destrava é a metade que NÃO é desenho: o clique
    inútil passa a RECUSAR DIZENDO o motivo, em vez de disparar um no-op que se
    apresenta como ação. Era o defeito exato que
    `_aplicar_sensibilidade_ligar_desligar` curou na janela antiga:
    *"o clique inútil dispara `systemctl` de verdade, volta `rc=0`, e a tela
    confirma um trabalho que não houve."*
    """
    if nome == "retomar" and not (
            isinstance(ctx.state, dict) and "paused" in ctx.state):
        return None
    if travas is not None:
        return travas.get(nome)
    try:
        return _tela.travas(_leitura(ctx)).get(nome)
    except Exception:
        return None


#: `aba_sistema.travas()` tranca o `ver-detalhes` com a frase *"O serviço está
#: não tem regra de sensibilidade, e `_aplicar_sensibilidade_ligar_desligar` só
#: `interface/sistema.travas()`, que é a camada do produto e território de outra
TRAVA_QUE_NAO_VALE_AQUI: dict[str, str] = {
    "parar-ou-retomar": "`travas()` o tranca com o serviço desligado, dizendo *'O "
                "serviço já está desligado'* — e isso era verdade até 03/09/2026, "
                "quando ele deixou de ser um botão só de parar. Ela mandou o "
                "mesmo botão LIGAR nesse estado (*'um específico pra parar o "
                "Daemon E Ativar o Daemon'*), e obedecer à trava aqui recusaria "
                "exatamente o clique que ela pediu que passasse a funcionar. A "
                "cara de parar não precisa da trava: ela só aparece com o "
                "serviço de pé. Ver :func:`desligar`.",
}


def retomar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Sair da pausa. `daemon.resume` — e só quando HÁ pausa de que sair.

    ELE TINHA UM CHAMADOR EM TODO O `src/` — o terminal (`cli/app.py:373`), como
    a `interface/sistema.py:54` já tinha medido: *"a pausa fica gravada em disco e
    sobrevive a desligar o computador; até hoje só o terminal saía dela."* Este
    é o segundo, e é uma tela.

    A RECUSA ENTROU EM 03/09/2026, e o defeito estava na foto: com `paused:
    False` — medido na bancada — o botão ficava verde e clicável, e o clique
    mandava `daemon.resume` a um daemon que não está pausado. Um no-op que se
    apresenta como ação.
    """
    motivo = _trava(ctx, "retomar")
    if motivo:
        raise RuntimeError(motivo)
    p.chamar("daemon.resume")


#: `daemon.reload` **fez o trabalho e a resposta nunca chegou** — *"o pior
SEM_RESPOSTA_DO_SERVICO = (
    "Não consegui falar com o serviço: pode não ter reaplicado nada, e pode ter "
    "reaplicado sem me responder. Clique de novo com o serviço de pé.")


@gesto("09-sistema.html", "atualizar")
def atualizar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O que o serviço relê agora. `daemon.reload` — e o botão CONFERE se deu.

    O QUE ELE FAZ DE VERDADE, medido no fonte do daemon em 05/09/2026, e é
    MENOS do que "recarregar a configuração" dá a entender: o clique manda
    `daemon.reload` **sem `config_overrides`**, então `overrides` chega `{}`
    (`daemon/ipc_handlers.py:4542`) e `new_cfg = replace(self.daemon.config)` é
    uma cópia de valor igual (`:4553`). Os dois ramos que reaplicariam mouse e
    teclado comparam `old` com `new` (`daemon/lifecycle.py:1119` e `:2089`) e
    **nunca disparam** — o registro sai com `keys_changed=[]` (`:2094-2098`).
    Duas coisas acontecem, e são estas: `lifecycle.py:1117-1118` derruba e sobe
    o leitor dos atalhos do controle, e `ipc_handlers.py:4599` reescreve os
    arquivos de ambiente que a Steam usa. **A dica da aba diz essas duas**
    (`interface/aba09.py`, da `ONDA5-09-01`), e esta é a medição que a sustenta.

    ELE LEVA 9,5 SEGUNDOS, medido no daemon do usuário em 01/09/2026 — contra 1 ms do
    `daemon.resume` e 57 ms do `daemon.status`. É a razão de os gestos rodarem em
    thread: síncrono, este botão congelaria a janela inteira por nove segundos e
    meio, e quem clicou concluiria que o app travou. É também a razão de
    `daemon.reload` ter teto de 15 s em `ponte.TETOS` — e `chamar_detalhado`
    consulta o MESMO `ponte.teto()` que o `chamar` (`pacotes/ponte.py:161`),
    conferido: trocar de função não encolheu a espera para os 250 ms do padrão.
    Se encolher, este botão passa a recusar todo clique que funciona.

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

    **O RETORNO SE LÊ — 06/09/2026, e é a `ONDA5-09-02`.** Até hoje a linha era
    `p.chamar("daemon.reload")`, e `chamar` devolve `bool` que ninguém lia.
    `_safe_call` devolve `False` para serviço desligado, socket ausente, timeout
    e erro JSON-RPC (`app/ipc_bridge.py:74-81`); o gesto não levantava, o
    piloto executava o ramo do sucesso (`_deu_certo`,
    `interface/hefesto_vivo.py:2761`) e
    a tela dizia **"Pronto."** em verde. **A cena inteira, com o serviço
    parado:** o botão trocava de palavra, esperava o teto, voltava ao rótulo e
    afirmava ter feito. Nenhum byte havia saído. E ele não fica cinza para
    avisar — `atualizar` não está em `BOTOES_CINZAS`, de propósito (ver lá).

    O PADRÃO ERA O DO `ver_plugins` (que saiu da aba em 13/09/2026): ler o
    retorno e usá-lo. `_ok_e_motivo` é o que torna isto seguro contra o dublê
    da régua — o docstring dele diz por quê, e não é enfeite.

    `_LENTO.clear()` ACONTECE NOS DOIS DESFECHOS, e é escolha: uma recusa na
    tela ao lado de cinco leituras caras de até 2 s atrás seria a tela dizendo
    "não deu" sobre valores que ninguém releu.
    """
    ok, motivo = _ok_e_motivo(p.chamar_detalhado("daemon.reload"))
    _LENTO.clear()
    if not ok:
        raise RuntimeError(motivo or SEM_RESPOSTA_DO_SERVICO)


def _teto_do_perfil(escolha: str) -> str | None:
    """O que aquele botão grava em DISCO. Lido do produto, nunca digitado."""
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
    função o gesto rebentaria com `TypeError` na régua e funcionaria na mão do usuário
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
    `_effective_mult` (`core/rumble.py:104`) lê os dois e aplica `min` entre
    eles — `_sob_o_teto`, nunca produto —, então gravar a escolha do usuário como
    política apagaria a política por controle que as outras abas escrevem. Quem
    é dono desta escolha é o `orcamento.teto` do `maquina.json`, e o contrato do
    produto diz o mesmo: `interface/sistema.GESTOS["perfil-da-mesa"]` aponta para
    `secao_orcamento._ao_escolher:468`, que monta `{"orcamento": {"teto": …}}`.

    O QUE MUDA EM RELAÇÃO À JANELA ANTIGA, e é decisão de produto: lá o
    `_ao_escolher` **não manda IPC** — acumula em `host._maquina_pendente` e só o
    "Aplicar" do rodapé grava (`footer_actions.py`). Aqui vale a regra de
    01/09: *"clicar na cor já deveria aplicar"*. O gesto age na hora, e o
    caminho é o MESMO que aquele "Aplicar" usa — `machine_declare_detalhado`, do
    `ipc_bridge`. Não é uma segunda porta para o disco.

    E ELE PEGA NA HORA, sem reiniciar nada: o `_handle_machine_declare`
    (`daemon/ipc_handlers.py:5651`) relê o `maquina.json` e **rebinda**
    `daemon._maquina`; o `_orcamento_declarado` (`core/rumble.py:93`) lê a
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
        raise RuntimeError(motivo or "não consegui gravar o Perfil de Bateria")


def _systemctl(verbo: str) -> None:
    """Roda `systemctl --user <verbo>` pela janela antiga, e LEVANTA se não pegou."""
    janela = _matriz()
    if verbo in ("start", "restart"):
        janela._invoke_systemctl(["reset-failed", _unidade()], check=False)
    r = janela._invoke_systemctl([verbo, _unidade()], capture=True)
    rc = getattr(r, "returncode", -1) if r is not None else -1
    if rc != 0:
        detalhe = str(getattr(r, "stderr", "") or "").strip() if r is not None else ""
        recusa = _daemon._SYSTEMCTL_FAIL_MSG.get(verbo, "Não consegui falar com o sistema")
        raise RuntimeError(f"{recusa}{f': {detalhe}' if detalhe else '.'}")
    _LENTO.clear()


@gesto("09-sistema.html", "autostart", grava="_systemctl")
def autostart(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O ligável «Iniciar com o sistema». `systemctl --user enable|disable`.

    ELE ERA UM INTERRUPTOR MORTO, e essa é a pior espécie de botão morto: parece
    ter dois estados, o clique não muda nem a aparência (não há um `<script>` na
    página que troque a classe localmente), e quem clica não tem como saber que
    não pegou. Medido em execução em 02/09: `autostart` estava entre os SETE
    gestos desta página sem dono — o clique caía em `hefesto_vivo.py:2664`,
    imprimia `[gesto sem dono]` no stdout do processo e voltava.

    O QUE ELE MANDA É O CONTRÁRIO DO QUE ESTÁ LIDO, e a leitura é a mesma que
    pinta a chave: `_autostart()` devolve a saída crua de `is-enabled` e
    `aba_sistema.autostart_ligado` a traduz. A tela e o gesto não têm como
    discordar porque leem o mesmo lugar.

    E O ESTADO NÃO SE INVERTE ÀS CEGAS. Com `is-enabled` ilegível
    (`autostart_ligado` devolve `None`), o gesto RECUSA em vez de adivinhar: um
    `enable` disparado sobre "não sei" tem 50% de chance de desfazer a escolha
    do usuário sem que ninguém tenha pedido.

    ELE ESTÁ EM `hefesto_vivo.PERIGOSOS` — já estava, antes de ter dono — e por
    isso a prova automática desta casa NUNCA o clica. Ligar um gesto que mexe na
    configuração de boot dela sem esse isento seria a régua estragando a máquina
    para provar que sabe clicar.
    """
    ligado = _tela.autostart_ligado(_autostart())
    if ligado is None:
        raise RuntimeError(
            "Não consegui saber se o serviço liga sozinho, então o interruptor "
            "não se mexe.")
    _systemctl("disable" if ligado else "enable")


@gesto("09-sistema.html", "reiniciar", grava="_systemctl")
def reiniciar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Reiniciar o serviço". `systemctl --user restart`, com o `reset-failed`.

    A TRAVA VEM DA CAMADA DO PRODUTO: com o serviço desligado, `travas()`
    responde *"O serviço está desligado — não há o que reiniciar."* — e é essa a
    frase que chega à tela, não uma deste pacote.

    ELE TAMBÉM JÁ ESTAVA EM `hefesto_vivo.PERIGOSOS`: reiniciar o daemon derruba
    a sessão dele no meio do trabalho dela, e a régua não o clica.

    **E ELE REPÕE O LANÇADOR — decisão, 21/09/2026.** A pergunta foi do usuário:
    *"seria importante ele fechar e reabrir o launcher, seja steam, epic,
    heroic ou qualquer outro"*; posta entre três formas (automático · oferecido
    num segundo clique · botão separado), o usuário escolheu a primeira com estas
    palavras: *"Faz automático mesmo"*.
    <!-- noqa-acento: citação literal -->

    **O QUE ISSO CURA, e é medido:** o lançador que subiu ANTES do daemon
    segura o controle FÍSICO (`STEAM-NO-FISICO-01`, medido quatro vezes) —
    reiniciar sem repor devolvia a máquina ao estado que o reinício queria
    desfazer. A Steam ainda apaga sozinha o wrapper da Launch Option.

    **A REPOSIÇÃO VEM DEPOIS DO `restart`, e a ordem é a entrega:** o lançador
    tem de nascer com o daemon já de pé, senão ele pega o físico de novo e o
    gesto inteiro teria sido em vão.

    **QUEM DECIDE E QUEM AGE É `reposicao_dos_lancadores`**, e nenhuma regra
    dele mora aqui — inclusive a única exceção ao "automático": com jogo
    aberto, nada é fechado, porque fechar o lançador fecharia o jogo junto. Não
    é ressalva deste pacote; é o contrato que o produto já aplica desde 18/09.

    **A FALHA DA REPOSIÇÃO NÃO DESFAZ O REINÍCIO.** O `restart` já aconteceu e
    deu `rc=0`; levantar aqui faria a tela dizer "não consegui" sobre um
    serviço que reiniciou. O que acontecer vai ao recibo.
    """
    motivo = _trava(ctx, "reiniciar")
    if motivo:
        raise RuntimeError(motivo)
    _systemctl("restart")
    _repor_o_lancador()


def _repor_o_lancador() -> None:
    """Fecha e reabre o lançador aberto, e relata. Nunca levanta."""
    from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as rl

    try:
        recibo = rl.repor()
    except Exception as erro:
        _relatar_o_recibo("reiniciar", f"não consegui repor o lançador: {erro}")
        return
    _relatar_o_recibo("reiniciar", rl.frase_do_recibo(recibo))


# na Lançadores"**. E escolheu a palavra do botão armado, entre três:
# 21/09/2026 (o «Posso fechar a Steam», que saiu com os botões da Steam): o

CONFIRMA = "Confirma?"

_CONFIRMA_DO_GESTO: dict[str, str] = {}


#: O VERBO É DO USUÁRIO — *"em sistema um específico pra parar o Daemon E Ativar o
ATIVAR = "Ativar o serviço"

DESLIGAR = "parar-ou-retomar"

DESTRUTIVOS = (DESLIGAR, "restaurar-de-fabrica", "refazer-consertos",
               "aplicar-aos-jogos")

RETOMAR = "Retomar"

#: `refazer-proton`). O primeiro clique escreve o censo lá e o
SEM_MOTOR: dict[str, str] = {
}


def _seletor(gesto: str) -> str:
    """Como o `blocos:` endereça um botão desta página. Ver o bloco acima."""
    return f'[data-gesto="{gesto}"]'


_ROTULOS: dict[str, str] = {}


def _rotulo_do_desenho(gesto: str) -> str:
    """O que o DESENHO escreve naquele botão — LIDO da página, nunca digitado.

    O dono do rótulo é o gerador (`interface/aba09.py`, o `item()`), e o que ele
    produziu está na página que o produto renderiza. Digitar "Parar o serviço"
    aqui seria o segundo dono de uma palavra que o usuário escolheu — e envelheceria
    calado no dia em que ela trocasse o verbo, que é exatamente o que aconteceu
    em 31/08 ("encerrar" -> "parar").

    Devolve `""` quando não achou: quem chama trata como "não sei" e não escreve.

    A BANCADA ENTRA COMO SEGUNDA FONTE — 06/09/2026, e não é preferência: um
    botão que NASCE nesta leva (o "Aplicar aos jogos da Steam") só existe no
    desenho de hoje, porque **publicar é ato dela**. Sem a segunda fonte o
    rótulo sairia vazio, `blocos_dos_botoes` pularia o botão, o "Confirma?"
    nunca chegaria à tela — e o segundo clique não teria como trazer o rótulo
    que **só existe no botão armado**. O consentimento em dois cliques ficaria
    impossível de dar justamente no botão mais destrutivo da leva.

    A ORDEM É PUBLICADO PRIMEIRO, e ela importa: onde os dois têm o botão, quem
    manda é o que o produto RENDERIZA — comparar contra a bancada faria o guarda
    esperar uma palavra que a tela do usuário não mostra.
    """
    if not _ROTULOS:
        for publicado in (True, False):
            try:
                doc = _onde.pagina(PAGINA, publicado=publicado).read_text(
                    encoding="utf-8")
            except Exception:  # pragma: no cover - página fora do disco
                continue
            for achado in re.finditer(
                    r'data-gesto="([^"]+)"[^>]*>([^<]*)</button>', doc):
                _ROTULOS.setdefault(
                    achado.group(1),
                    html.unescape(achado.group(2)).strip())
    return _ROTULOS.get(gesto, "")


_ARMADO: dict[str, Any] = _confirmacao.ARMADO


def segundos_para_confirmar() -> float:
    """A janela do consentimento — PERGUNTADA a quem já a tem.

    O dono é `pacotes/confirmacao.SEGUNDOS_PARA_CONFIRMAR`, e ele não é um
    número solto: é *"o consentimento que `with_steam_closed` EXIGE de quem a
    chama, na forma que uma página tem"*. Um `20.0` digitado aqui seria a
    segunda duração de consentimento desta casa. ATÉ 21/09/2026 ele era lido
    pela aba 07, que o reexportava — e a aba 07 deixou de confirmar.
    """
    from . import confirmacao

    return float(confirmacao.SEGUNDOS_PARA_CONFIRMAR)


def _armado_agora() -> str:
    """O gesto armado NESTE instante, ou `""` — e ele desarma sozinho no tempo."""
    return _confirmacao.armado_agora()


def _rotulo_de_agora(gesto: str, de_pe: bool, pausado: bool = False) -> str:
    """O que aquele botão TEM de estar dizendo agora. Três caras, uma conta."""
    if gesto == _armado_agora():
        return _CONFIRMA_DO_GESTO.get(gesto) or CONFIRMA
    if gesto == DESLIGAR and not de_pe:
        return ATIVAR
    if gesto == DESLIGAR and pausado:
        return RETOMAR
    return _rotulo_do_desenho(gesto)


def blocos_dos_botoes(de_pe: bool, pausado: bool = False) -> dict[str, str]:
    """O `blocos:` que põe os cinco no rótulo de agora — do tique e do gesto."""
    fora: dict[str, str] = {}
    for gesto_ in DESTRUTIVOS:
        rotulo = _rotulo_de_agora(gesto_, de_pe, pausado)
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


def _confirmado(o: dict[str, Any], gesto_: str,
                antes_de_armar: Any = None) -> bool:
    """Este clique é a CONFIRMAÇÃO? Quando não é, ARMA o botão e devolve `False`."""
    rotulo = str(o.get("texto") or "").strip()
    armado = _armado_agora() == gesto_
    palavras_armadas = {CONFIRMA}
    especifica = _CONFIRMA_DO_GESTO.get(gesto_)
    if especifica:
        palavras_armadas.add(especifica)
    if rotulo in palavras_armadas:
        _ARMADO.clear()
        if not armado:
            raise RuntimeError(
                f"Passaram-se mais de {int(segundos_para_confirmar())} segundos "
                "desde a pergunta — não fiz nada. Clique de novo para começar.")
        return True
    _ARMADO.clear()
    if antes_de_armar is not None:
        antes_de_armar()
    _ARMADO.update(gesto=gesto_, ate=time.monotonic() + segundos_para_confirmar())
    return False


@gesto("09-sistema.html", DESLIGAR, grava="_systemctl")
def desligar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O PAR que o usuário pediu, num botão só: **Parar o serviço** e **Ativar o serviço**.

    DECISÃO, 03/09/2026: na aba Sistema, um controle específico para parar e ativar o daemon
    — **um** controle, os dois atos. E é o que a página comporta: a
    coluna de ações desta faixa tem quatro botões e o portão do gerador
    (`aba09.py`, o par de alturas) reprova o quinto, porque as duas colunas
    irmãs desta aba acabam no mesmo y. Um botão a mais abriria os 38px de vão
    que o usuário reclamou em 31/08.

    AS DUAS CARAS NÃO SÃO SIMÉTRICAS, e a assimetria é o ponto:

    * **Parar** derruba o serviço e os controles do usuário viram gamepads comuns —
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
    aqui recusaria exatamente o clique que o usuário pediu que funcionasse.

    O QUE ELE DEVOLVE é o `blocos:` dos cinco rótulos, para a troca ser
    instantânea: sem isso a palavra do botão só mudaria no tique seguinte, e
    quem clicou concluiria que não pegou.

    O CLIQUE 1 PERGUNTA — SISTEMA-BOTOES-01, 13/09/2026. Ele armava sem uma
    palavra, e piscava verde; o `title` publicado promete *"Pergunta antes,
    dizendo o que se perde"*. Agora o painel diz esse `title` e
    :data:`CLIQUE_DE_NOVO` (:func:`_pergunta_do_botao`), a carga leva
    :data:`ARMOU`, e o clique 2 limpa o painel antes de agir.
    """
    if _de_pe(ctx) and _pausado(ctx):
        _ARMADO.clear()
        retomar(ctx, o, p)
        return {"blocos": blocos_dos_botoes(True, False)}
    if not _de_pe(ctx):
        _ARMADO.clear()
        if not ativar_o_servico():
            raise RuntimeError(
                "Não liguei o serviço. Ou esta máquina não tem o Hefesto "
                "instalado pelo sistema, ou já há um Hefesto rodando por fora "
                "— e subir outro criaria um segundo.")
        return {"blocos": blocos_dos_botoes(_de_pe(ctx))}
    if not _confirmado(o, DESLIGAR):
        return _so_armou(True, _para_o_painel(_pergunta_do_botao(DESLIGAR),
                                              pergunta_de=DESLIGAR))
    _limpar_o_painel()
    _systemctl("stop")
    _matriz()._user_stopped_daemon = True
    return {"blocos": blocos_dos_botoes(False)}


def ativar_o_servico() -> bool:
    """Liga o serviço se ele estiver PARADO. Devolve se ELE precisou ligar.

    DONO ÚNICO DO ATO, e ele existe por causa da outra metade da decisão de produto:
    *"Adiciona essa função extra quando clicar em ligar"* — o interruptor
    **Ligado** da aba Jogar liga o serviço também, e é o mesmo ato que o "Ativar
    o serviço" desta aba faz. Escrito duas vezes, ele teria dois donos: uma
    cópia desarmaria o `_user_stopped_daemon` e a outra não, e o daemon voltaria
    a morrer no próximo F5 por um caminho e não pelo outro.

    OS TRÊS PORTÕES SÃO DO PRODUTO, e não deste pacote — são exatamente os que
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


SEGUNDOS_ATE_O_AVULSO_SAIR = 5.0


def _o_avulso_saiu(pid: int) -> bool:
    """Pede ao daemon avulso que saia e ESPERA. `True` quando ele já não vive."""
    import os
    import signal

    from hefesto_dualsense4unix.utils.single_instance import is_alive

    if not is_alive(pid):
        return True
    try:
        os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return not is_alive(pid)
    limite = time.monotonic() + SEGUNDOS_ATE_O_AVULSO_SAIR
    while time.monotonic() < limite:
        if not is_alive(pid):
            return True
        time.sleep(0.1)
    return not is_alive(pid)


#: (`test_o_corrigir_modo_recusa_fora_do_modo_improvisado`), então trocar o
NADA_A_CORRIGIR = "O serviço já sobe pelo sistema — não há o que corrigir."


@gesto("09-sistema.html", "corrigir-modo", grava="_systemctl")
def corrigir_modo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Corrigir o serviço" — a saída de quem caiu no modo improvisado.

    A LINHA **L315** DO CSV, e ela era a metade que faltava de um par. O HTML já
    RECONHECE `online_avulso` desde 03/09 — a linha "O serviço está" escreve
    *"Ligado, em modo improvisado"* em laranja —, e não oferecia saída nenhuma:
    **quem caía nesse estado era avisado e não tinha botão de conserto.** A
    janela antiga tinha (`daemon_actions.on_daemon_migrate_to_systemd`).

    O QUE É O MODO IMPROVISADO, medido pela matriz de três fontes do produto
    (`_daemon_status`): o processo está VIVO e a unit do systemd está parada.
    Funciona, e é frágil — ninguém o religa quando ele cai, e ele não volta com
    o computador.

    OS TRÊS TEMPOS SÃO OS DA JANELA ANTIGA, na ordem de produto: ler o pid, pedir ao
    processo avulso que saia, subir a unit. **Nenhum deles é escrito aqui de
    novo:** o pid vem de `_read_daemon_pid`, a saída passa por
    :func:`_o_avulso_saiu` (que consulta o `is_alive` do produto) e quem sobe a
    unit é :func:`ativar_o_servico` — o dono único do ato de ligar, com os três
    portões do produto e o `_user_stopped_daemon` desarmado.

    A ORDEM IMPORTA E É A RAZÃO DE `_o_avulso_saiu` ESPERAR: o terceiro portão
    de `ativar_o_servico` recusa subir a unit enquanto o avulso vive
    (BUG-MULTI-INSTANCE-01). Chamar os dois sem a espera no meio devolveria
    "não liguei" sobre um daemon que estava saindo.

    ELE RECUSA FORA DO ESTADO, e não é zelo: em `online_systemd` não há modo a
    corrigir, e em `offline` este botão MATARIA nada e subiria a unit — que é o
    trabalho do "Ativar o serviço", ao lado. Um botão que faz o trabalho do
    vizinho é o segundo dono de um ato.

    SEM CONFIRMAÇÃO, e pelo mesmo argumento do "Ativar o serviço": pedir dois
    cliques para CONSERTAR é uma parede na saída de emergência. O botão só
    aparece no estado em que ele é a única coisa a fazer.

    A PROVA AUTOMÁTICA NUNCA O CLICA: `grava="_systemctl"` o põe em
    `pacotes.perigosos()` pelo decorador, no mesmo commit que o ensinou a mexer
    no serviço dela.

    AS DUAS FRASES SÃO DO DONO, palavra por palavra
    (`daemon_actions.MIGRAR_DEU_CERTO` e `MIGRAR_NAO_DEU`) — elas saíram de
    dentro do `_on_migrate_done` hoje justamente para este gesto não redigitar
    o que a janela antiga já dizia.
    """
    if _status_do_daemon(ctx.state) != "online_avulso":
        raise RuntimeError(NADA_A_CORRIGIR)
    pid = _matriz()._read_daemon_pid()
    if pid is not None and not _o_avulso_saiu(pid):
        raise RuntimeError(
            f"{_daemon.MIGRAR_NAO_DEU} O Hefesto que roda por fora não saiu "
            "quando pedi — ele pode estar no meio de alguma coisa.")
    if not ativar_o_servico():
        raise RuntimeError(_daemon.MIGRAR_NAO_DEU)
    _LENTO.clear()
    return {"blocos": blocos_dos_botoes(_de_pe(ctx)),
            "recado": _daemon.MIGRAR_DEU_CERTO}


#: O desfecho de `with_steam_closed` quando há um jogo aberto: a Steam NÃO fecha, e
#: só a Steam espera — o resto do gesto (os outros lançadores) já rodou.
JANELA_COM_JOGO_ABERTO = "jogo_aberto"

#: O recibo, não a falha (O-APLICAR-SOLUCOES-COM-JOGO-ABERTO-DIZ-O-QUE-FEZ-01):
#: com um jogo aberto o gesto aplicou o que não exige fechar a Steam, e diz que a
#: Steam fica para quando o jogo fechar.
STEAM_FICA_PARA_DEPOIS = "A Steam fica para quando o jogo fechar."


@gesto("09-sistema.html", "aplicar-aos-jogos", grava="with_steam_closed")
def aplicar_aos_jogos(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Aplicar soluções nos lançadores» — o atalho na Steam, o ambiente nos outros.

    Desde 01/10/2026 (AS-SOLUCOES-NOS-LANCADORES-01) o botão vale para todo
    lançador: antes da Steam, a carona dos outros (o Heroic e as caixas do
    Flatpak) roda na hora. O que vem abaixo é a metade da Steam.

    A LINHA **L340** DO CSV, e ela nunca teve caminho na interface nova: o
    "Copiar a linha" da `07-lancadores` só entrega o texto na área de
    transferência, e sem este botão não havia por onde o atalho chegar aos
    jogos sem ela colar um a um. `D-0609-STEAM-DIVIDIDO` decidiu o endereço:
    **"Aplicar aos jogos" fica na 09.**

    O MOTOR É O MESMO DA JANELA ANTIGA, e o do "Deixar tudo pronto" que a aba
    07 teve até 21/09: `steam_launch_options.apply_wrapper_to_all_games` numa
    janela de `with_steam_closed`. Nada aqui reescreve o ato — nem o `getattr`
    defensivo, que é o contrato PATH-06: uma instalação antiga sem a aplicação
    em massa recusa DIZENDO, com a frase do dono
    (`daemon_actions.frase_sem_aplicacao_em_massa`).

    O CONSENTIMENTO É EXIGÊNCIA DO MOTOR, e não desenho da tela: `with_steam_closed`
    FECHA a Steam do usuário por uns 20 segundos. A pergunta é a mesma que o diálogo
    da janela antiga fazia — `DaemonActionsMixin._STEAM_APPLY_CORPO`, palavra
    por palavra —, e ela sai de lá hoje justamente para não haver duas.

    A PERGUNTA VAI AO PAINEL DE REGISTRO — TELA-CALADA-03, 13/09/2026. Ela ia
    por `recado`, e desde `8b0a3b48` esta aba não tem cartão nem faixa onde um
    recado pouse: medido no piloto oculto, o primeiro clique virava o botão em
    «Confirma?» e a tela não dizia uma palavra sobre o que ia acontecer. Agora
    ela vai para onde os primeiros cliques de «Refazer os consertos
    automáticos» e de «Tirar a sobreposição Vulkan» já escrevem
    (:func:`_pergunta_da_steam`), e chega pelo PACOTE — não depende do canal de
    recado, que a TELA-CALADA-01 cala para o sucesso.

    OS TRÊS DESFECHOS DO MOTOR ESTÃO COBERTOS, e nenhuma frase é deste pacote: a
    recusa da janela (`format_steam_janela_recusa` — jogo aberto, a Steam não
    fechou, resposta inesperada) e o resultado (`format_apply_wrapper_result` —
    quantos jogos mudaram, quantos ficaram, quantos falharam). **O resultado
    saiu da tela em 13/09/2026** (é recibo, e a régua dela tira recibo): ele vai
    ao diário da janela por :func:`_relatar_o_recibo`, e o segundo clique
    devolve só os rótulos. A recusa continua levantando — menos a do **jogo
    aberto**, que não é falha (03/10/2026): os outros lançadores já receberam o
    ambiente, e o painel diz quais e que a Steam fica para quando o jogo fechar.
    """
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    aplicar = getattr(slo, "apply_wrapper_to_all_games", None)
    if aplicar is None:
        raise RuntimeError(_daemon.frase_sem_aplicacao_em_massa())
    if not _confirmado(o, "aplicar-aos-jogos"):
        return _so_armou(_de_pe(ctx), _para_o_painel(
            _pergunta_da_steam(), pergunta_de="aplicar-aos-jogos"))
    _limpar_o_painel()
    from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe

    das_estradas = cpe.frase_das_estradas(cpe.curar_todas_as_estradas())
    _relatar_o_recibo("aplicar-aos-jogos", das_estradas)
    janela, resultado = slo.with_steam_closed(aplicar)
    if janela == JANELA_COM_JOGO_ABERTO:
        _relatar_o_recibo("aplicar-aos-jogos", STEAM_FICA_PARA_DEPOIS)
        return {"blocos": blocos_dos_botoes(_de_pe(ctx)),
                **_para_o_painel(f"{das_estradas} {STEAM_FICA_PARA_DEPOIS}")}
    recusa = _daemon.format_steam_janela_recusa(janela)
    if recusa is not None:
        raise RuntimeError(recusa)
    _relatar_o_recibo("aplicar-aos-jogos",
                      _daemon.format_apply_wrapper_result(resultado))
    return {"blocos": blocos_dos_botoes(_de_pe(ctx))}


@gesto("09-sistema.html", "restaurar-de-fabrica", grava="gravar_e_reaplicar")
def restaurar_de_fabrica(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Restaurar de fábrica" — o último dos cinco sem motor, e o mais destrutivo.

    A LINHA **L343** DO CSV. O botão estava na página desde que ela nasceu,
    vermelho, prometendo *"Pergunta antes"* — e o clique caía em
    `gesto_da_pagina() -> None`, imprimindo `[gesto sem dono]` no terminal de
    quem lançou a janela. Ela não tinha como saber que não pegou.

    O QUE O SEGURAVA NÃO ERA O MOTOR, e isso estava medido desde 04/09: os três
    passos do ato têm dono FORA da janela — o localizador do preset
    (`footer_actions._meu_perfil_asset`, função de MÓDULO), o
    `Profile.model_validate` do JSON e os três tempos de
    `pacotes.perfil.gravar_e_reaplicar` (disco, reaplicar, `launch_env.refresh`).
    O que era da janela é o diálogo — e a D-03 dela já o substituiu por dois
    cliques — e o refresh das abas velhas, que esta interface não tem.

    O QUE O SEGURAVA ERA A REDE DE SEGURANÇA: um gesto que grava restauraria o
    perfil do usuário quando a prova botão a botão o acionasse. A rede mora no
    decorador desde a `ONDA3-GESTO-DECLARA-01`, e este gesto a declara no mesmo
    commit em que nasce — `pacotes.perigosos()` o recebe derivado, e o
    `--prova-gesto` nunca o clica.

    A IDENTIDADE É DECIDIDA AQUI, e não pelo arquivo achado — é a
    PERFIL-PADRAO-PERSONALIZADO-01, e a razão está no dono: o asset pode ser o
    de hoje (`freestyle.json`) ou o de uma versão anterior ainda no `/usr/share`
    (`personalizado.json`, `meu_perfil.json`), e esses fariam o botão gravar de
    volta um nome que saiu, num arquivo à parte. O nome é «Freestyle» (24/09).

    O `era=` É O QUE FAZ ELE ADOTAR COMO ATIVO, e não um detalhe:
    `gravar_e_reaplicar` só manda `profile.switch` quando o perfil gravado é o
    que está valendo. A janela antiga faz isso com `adotar_como_ativo=True`;
    aqui, passar o nome que está valendo AGORA faz a comparação casar e o
    `switch` sair — que é a mesma coisa dita no vocabulário deste lado. Sem
    ele, o `.json` mudaria no disco e o controle continuaria com o perfil
    anterior, que é o sintoma que ela leu como *"não está salvando"*.

    AS DUAS FRASES SÃO DO DONO (`footer_actions.frase_do_preset_ausente` e
    `frase_do_restauro`), e as duas nasceram hoje: a primeira era dev-fala num
    toast (*"Asset 'personalizado.json' não encontrado"*) e a régua da palavra
    a carregava como dívida declarada desde 23/08. Trocá-la no dono pagou a
    dívida dos DOIS chamadores de uma vez.
    """
    import json

    from hefesto_dualsense4unix.app.actions import footer_actions as _rodape
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        perfil_que_esta_valendo,
    )
    from hefesto_dualsense4unix.profiles.loader import NOME_DO_PADRAO
    from hefesto_dualsense4unix.profiles.schema import Profile

    asset = _rodape._meu_perfil_asset()
    if asset is None:
        raise RuntimeError(_rodape.frase_do_preset_ausente())
    if not _confirmado(o, "restaurar-de-fabrica"):
        return _so_armou(_de_pe(ctx), _para_o_painel(
            _pergunta_do_botao("restaurar-de-fabrica"),
            pergunta_de="restaurar-de-fabrica"))
    _limpar_o_painel()
    cru = json.loads(asset.read_text(encoding="utf-8"))
    cru["name"] = NOME_DO_PADRAO
    prof = Profile.model_validate(cru)
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import (
        restaurar_o_computador,
    )

    restaurar_o_computador()
    era = perfil_que_esta_valendo(getattr(ctx, "state", None)).nome or ""
    perfil.gravar_e_reaplicar(prof, ctx, p, era=era)
    return {"blocos": blocos_dos_botoes(_de_pe(ctx)),
            "recado": _rodape.frase_do_restauro()}


# existe) continuam todas em :func:`_porque_o_proton_nao_trava`.


def _porque_o_proton_nao_trava(pin: Any, travar: Any) -> str | None:
    """Por que a fixação do Proton não pode acontecer AGORA — ou `None`."""
    sem_o_pin = _daemon.frase_sem_o_proton_pinado()
    if travar is None:
        return sem_o_pin
    onde_mora = getattr(pin, "default_pin_conf_path", None)
    try:
        conf = onde_mora() if onde_mora is not None else None
    except Exception:
        conf = None
    if conf is None or not Path(conf).is_file():
        return sem_o_pin
    no_disco = getattr(pin, "pino_instalado_nesta_maquina", None)
    try:
        instalado = no_disco() if no_disco is not None else True
    except Exception:
        instalado = False
    if not instalado:
        return sem_o_pin
    steam_viva = getattr(pin, "steam_running", None)
    if steam_viva is None:
        from hefesto_dualsense4unix.integrations import steam_launch_options as slo

        steam_viva = slo.steam_running
    if steam_viva():
        return ("A Steam está aberta — feche-a e clique de novo. Com ela aberta a "
                "mudança seria perdida ao sair.")
    return None


#: antiga usa — `daemon_actions.on_storm_fix_safe`, o laço do `_worker`.
#: no ramo `install)` de `scripts/fix_wireplumber_default_source.sh`: ele apaga
CONSERTOS: tuple[tuple[str, list[str]], ...] = (
    ("scripts/disable_steam_input.sh", ["--apply-quiet"]),
)

SEGUNDOS_DO_CONSERTO = 30

_ANTES_DO_CONSERTO: dict[str, Any] = {}


def _consertos_no_disco() -> list[tuple[Any, list[str]]]:
    """Os scripts de :data:`CONSERTOS` que EXISTEM nesta instalação."""
    janela = _matriz()
    achados: list[tuple[Any, list[str]]] = []
    for relpath, args in CONSERTOS:
        caminho = janela._find_repo_file(relpath)
        if caminho is not None:
            achados.append((caminho, args))
    return achados


def _versoes_que_sobram() -> list[Any]:
    """As versões do Proton sem uso (`proton_pin.versoes_que_sobram`). Nunca levanta."""
    try:
        from hefesto_dualsense4unix.integrations import proton_pin
        return list(proton_pin.versoes_que_sobram())
    except Exception:
        return []


def _gb(total: int) -> str:
    return formata_pt_br(total / 1e9) + " GB"


def _frase_das_que_vao_sair(sobras: list[Any]) -> str:
    """O que o primeiro clique mostra, antes de agir. Vazio quando nada sobra."""
    if not sobras:
        return ""
    nomes = ", ".join(s.pasta.name for s in sobras)
    quantas = "1 versão" if len(sobras) == 1 else f"{len(sobras)} versões"
    return (f"Vão para a lixeira {quantas} do Proton que nenhum jogo usa: "
            f"{nomes} ({_gb(sum(s.tamanho for s in sobras))}).")


def _frase_do_que_saiu(saiu: list[Any], recusadas: dict[str, str]) -> str:
    """O recibo: o que foi para a lixeira e o que ficou, com o motivo."""
    partes: list[str] = []
    if saiu:
        if len(saiu) == 1:
            quantas, verbo = "1 versão", "foi"
        else:
            quantas, verbo = f"{len(saiu)} versões", "foram"
        partes.append(f"{quantas} do Proton sem uso {verbo} para a lixeira "
                      f"({_gb(sum(s.tamanho for s in saiu))}).")
    for nome, motivo in recusadas.items():
        partes.append(f"{nome} ficou: {motivo}.")
    return " ".join(partes)


def _levar_as_que_sobram(sobras: list[Any]) -> str:
    """Manda para a lixeira o que o primeiro clique mostrou; devolve o recibo."""
    if not sobras:
        return ""
    try:
        from hefesto_dualsense4unix.integrations import proton_pin
        saiu, recusadas = proton_pin.desinstalar_as_que_sobram(sobras)
        return _frase_do_que_saiu(list(saiu), recusadas)
    except Exception as erro:
        return f"As versões do Proton sem uso ficaram: {erro}."


def _frase_do_que_vai_mudar(jogos: list[str] | None, sobras: list[Any] | None = None) -> str:
    """O que o clique 1 escreve no painel: o que EXISTE agora, sem agir."""
    quantos = len(_consertos_no_disco())
    if quantos != len(CONSERTOS):
        falta = f" ({len(CONSERTOS) - quantos} não está nesta instalação)"
    else:
        falta = ""
    linhas = [f"Vou rodar {quantos} "
              f"{_plural(quantos, 'conserto automático', 'consertos automáticos')}"
              f"{falta}, sem pedir senha e sem fechar nada."]
    if jogos is None:
        linhas.append("  Não consegui olhar quais jogos estão com o Steam Input "
                      "ligado — o resto continua valendo.")
    elif not jogos:
        linhas.append("  Nenhum jogo com Steam Input ligado fora da sua lista de "
                      "exceções. Nada a desligar aí.")
    else:
        linhas.append(f"  Steam Input ligado em {len(jogos)} "
                      f"{_plural(len(jogos), 'jogo', 'jogos')}: "
                      + ", ".join(jogos) + ".")
    if sobras:
        linhas.append("  " + _frase_das_que_vao_sair(sobras))
    linhas.append(f"  {CLIQUE_DE_NOVO}")
    return "\n".join(linhas)


@gesto("09-sistema.html", "refazer-consertos",
       grava="roda os scripts de conserto do sistema na máquina dela")
def refazer_consertos(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Refazer os consertos automáticos" — mede, mostra, e só então mexe."""
    if not _confirmado(o, "refazer-consertos"):
        try:
            jogos = _daemon.medir_jogos_com_steam_input()
        except Exception:
            jogos = None
        _ANTES_DO_CONSERTO["jogos"] = jogos
        sobras = _versoes_que_sobram()
        _ANTES_DO_CONSERTO["sobras"] = sobras
        return _so_armou(_de_pe(ctx), _para_o_painel(
            _frase_do_que_vai_mudar(jogos, sobras), pergunta_de="refazer-consertos"))

    _limpar_o_painel()
    import subprocess

    if "jogos" in _ANTES_DO_CONSERTO:
        jogos = _ANTES_DO_CONSERTO.pop("jogos")
    else:
        try:
            jogos = _daemon.medir_jogos_com_steam_input()
        except Exception:
            jogos = None
    relatorio: dict[str, Any] = {"ran": 0, "missing": 0, "steam_input": None,
                                 "steam_input_jogos": jogos}
    for relpath, args in CONSERTOS:
        caminho = _matriz()._find_repo_file(relpath)
        if caminho is None:
            relatorio["missing"] += 1
            continue
        with contextlib.suppress(Exception):
            proc = subprocess.run(["bash", str(caminho), *args], check=False,
                                  timeout=SEGUNDOS_DO_CONSERTO,
                                  capture_output=True, text=True)
            relatorio["ran"] += 1
            if "disable_steam_input" in relpath:
                relatorio["steam_input"] = (proc.returncode,
                                            (proc.stdout or "") + (proc.stderr or ""))
    vistas = {s.pasta for s in _ANTES_DO_CONSERTO.pop("sobras", [])}
    sobras = [s for s in _versoes_que_sobram() if s.pasta in vistas]
    recibo = _daemon.format_fix_safe_result(relatorio)
    if sobras:
        recibo = f"{recibo} {_levar_as_que_sobram(sobras)}"
    _LENTO.clear()
    _relatar_o_recibo("refazer-consertos", recibo)
    return {"blocos": blocos_dos_botoes(_de_pe(ctx))}


LINHAS_DO_DIARIO = 80


def mascarar_o_diario(texto: str) -> str:
    """O texto do diário na máscara da casa, pelo dono das formas do endereço."""
    return _formas.mascarar(texto)


def _diario() -> str:
    """As últimas :data:`LINHAS_DO_DIARIO` linhas do registro da unit, mascaradas."""
    import subprocess

    from hefesto_dualsense4unix.interface.frases_que_ela_baniu import citar
    from hefesto_dualsense4unix.utils import identidade

    unidade = identidade.atual().unit_daemon
    try:
        saida = subprocess.run(
            ["journalctl", "--user", "-u", unidade, "-n", str(LINHAS_DO_DIARIO),
             "--no-pager", "--output", "cat"],
            capture_output=True, text=True, timeout=8)
    except Exception as erro:
        return f"Não consegui ler o registro de {unidade}: {erro}"
    texto = (saida.stdout or "").strip() or (saida.stderr or "").strip()
    if not texto:
        return f"O registro de {unidade} está vazio."
    return citar(mascarar_o_diario(texto))


def _por_na_area_de_transferencia(texto: str) -> bool:
    """O texto na área de transferência, pelo laço do GTK. `False` = não deu."""
    try:
        from gi.repository import Gdk, GLib, Gtk
    except Exception:
        return False

    def _agora() -> bool:
        with contextlib.suppress(Exception):
            area = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            area.set_text(texto, -1)
            area.store()
        return False

    GLib.idle_add(_agora)
    return True


def _conhecidos_do_copiar(ctx: Contexto) -> list[str]:
    """Os endereços e os seriais que o «Copiar» sabe que são de um aparelho.

    Os `uniq` e os `serial` do `state_full` e da fita, e as chaves de controle
    e de adaptador do `maquina.json`, pela API do dono dele
    (`utils/maquina.carregar_maquina`, que nunca levanta). Um conhecido que não
    é endereço nem serial o dono ignora.
    """
    conhecidos: list[str] = []
    estado = ctx.state if isinstance(ctx.state, dict) else {}
    for controle in [*(estado.get("controllers") or []), *(ctx.mesa or [])]:
        if isinstance(controle, dict):
            conhecidos += [str(controle[chave]) for chave in ("uniq", "serial")
                           if controle.get(chave)]
    maquina = _maquina.carregar_maquina()
    conhecidos += [*(maquina.controles or {}), *(maquina.adaptadores or {})]
    return conhecidos


@gesto("09-sistema.html", "copiar-registro",
       grava="põe o registro na área de transferência dela")
def copiar_registro(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Copiar»: o painel INTEIRO na área de transferência, para colar num relato."""
    texto = _no_painel(_faixa_lenta(ctx.state or None, ctx.mesa)[4])
    if not texto or texto == _tela.NAO_DEU:
        raise RuntimeError("O registro ainda está vazio — não há o que copiar.")
    texto = _formas.mascarar(texto, _conhecidos_do_copiar(ctx))
    if not _por_na_area_de_transferencia(texto):
        raise RuntimeError("Não consegui usar a área de transferência.")


def _o_pino() -> tuple[Any, Any]:
    """O módulo do Proton pinado e a função de travar — `None` onde faltar."""
    import importlib

    try:
        pin: Any = importlib.import_module(
            "hefesto_dualsense4unix.integrations.proton_pin")
    except ImportError:
        pin = None
    return pin, getattr(pin, "lock_proton_for_all_games", None)


@gesto("09-sistema.html", "fixar-proton",
       grava="trava ou destrava o Proton de TODOS os jogos dela, e a Steam "
             "regrava o arquivo")
def fixar_proton(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O ligável «Fixar Proton»: liga travando, desliga destravando.

    UM CLIQUE, SEM PERGUNTA — 25/09/2026. O botão de ontem («Refazer a fixação
    do Proton») perguntava porque só sabia TRAVAR; o ligável desfaz pelo mesmo
    registro que o travar escreveu (`unlock_games_from_pinned_proton` reverte
    SÓ o que a trava diz ser nosso). O que ele não pode é agir com a Steam
    aberta — ela regrava o arquivo ao sair —, e isso continua recusando antes
    de tocar em nada (:func:`_porque_o_proton_nao_trava`).
    """
    _ARMADO.clear()
    pin, travar = _o_pino()
    motivo = _porque_o_proton_nao_trava(pin, travar)
    if motivo:
        raise RuntimeError(motivo)
    if proton_fixado():
        destravar = getattr(pin, "unlock_games_from_pinned_proton", None)
        if destravar is None:
            raise RuntimeError(_daemon.frase_sem_o_proton_pinado())
        resultado = destravar()
        if str(resultado.get("status")) not in ("unlocked", "noop"):
            raise RuntimeError(
                "Não consegui soltar o Proton dos jogos — nada foi mudado.")
    else:
        recibo = _daemon.format_proton_lock_result(travar(todos=True))
        if proton_fixado():
            sobra = _levar_as_que_sobram(_versoes_que_sobram())
            if sobra:
                recibo = f"{recibo} {sobra}"
        _relatar_o_recibo("fixar-proton", recibo)
    _BARATO.clear()


@gesto("09-sistema.html", "corrigir-vulkan", grava="curar_todos")
def corrigir_vulkan(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O ligável «Corrigir Vulkan»: liga tirando as camadas da Steam do jogo."""
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv
    from hefesto_dualsense4unix.integrations import lista_de_exclusao
    from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as rl

    _ARMADO.clear()
    ligar = not vulkan_corrigido()
    resultados: list[Any] = []
    if not ligar and cv.ha_o_que_devolver():
        if rl.jogo_aberto():
            raise RuntimeError(
                "Tem jogo aberto — feche-o e clique de novo. Com o jogo vivo o "
                "Windows do Proton regrava esse ajuste ao sair, e a mudança seria "
                "perdida.")
        resultados = cv.curar_todos(
            religar=True, forcar=True, excluir=lista_de_exclusao.ids_dos_prefixos())
    try:
        cv.gravar_camadas_da_steam_fora(ligar)
    except OSError as erro:
        raise RuntimeError(
            "Não consegui guardar a escolha do Vulkan na pasta de configuração: "
            f"{erro.strerror or erro}.") from erro
    _LENTO.clear()
    frase = cv.frase_do_ato(ligar)
    if any(r.mexeu or r.erro for r in resultados):
        frase = f"{frase} {_emulacao.frase_do_resultado(resultados, devolver=True)}"
    _relatar_o_recibo("corrigir-vulkan", frase)


PONTE = {"chamar", "chamar_detalhado", "machine_declare", "profile_switch"}
METODOS = {"daemon.resume", "daemon.reload", "launch_env.refresh",
           "machine.declare"}


PAGINA = "09-sistema.html"
PISO_DA_ABA = 12
PROVAS = [
    {"pagina": PAGINA, "gesto": "atualizar", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar_detalhado", ["daemon.reload"], {})]},
    {"pagina": PAGINA, "gesto": "perfil-da-mesa",  # (noqa-acento) id
     "clique": {"v": "bateria_longa"},
     "chama": [("machine_declare",
                [{"orcamento": {"teto": _teto_do_perfil("bateria_longa")}}], {})]},
    {"pagina": PAGINA, "gesto": "perfil-da-mesa", "clique": {"v": "eu_escolho"},  # (noqa-acento) id
     "chama": [("machine_declare",
                [{"orcamento": {"teto": _teto_do_perfil("eu_escolho")}}], {})]},
]

#: OS TRÊS CUJO EFEITO O `state_full` NÃO MOSTRA, e cada um por um motivo:
#:   atualizar       `daemon.reload` relê a configuração — o estado publicado
#: MUDAM o daemon, LEEM. `state_full` não teria o que ecoar mesmo que tudo
#: efeito deles está no SYSTEMD, não no `state_full`. O `enable` muda o que
#: `restart` derruba e sobe a mesma unit, deixando o `state_full` igual ao que
SEM_ECO = ("atualizar", "autostart", "perfil-da-mesa", "reiniciar",
           "copiar-registro", "fixar-proton", "corrigir-vulkan")
