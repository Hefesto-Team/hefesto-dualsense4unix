"""SOM-QUE-NAO-DORME-01 — o alto-falante do controle nunca dorme.

A DECISÃO DELA, textual (16/08/2026, 00h): *"precisamos setar o som sempre em
todos os controles no 100% e garantir que sempre fique acordado"*. Este arquivo
trava a metade do "sempre acordado".

O DEFEITO, MEDIDO NA ORELHA DELA
================================
Bancada de 15/08/2026 23h45 — controle azul (hw 0x00001111) no CABO, card2,
teste CEGO. Mesmo arquivo, mesma rota, mesmo volume::

    canal 1 sozinho, nó ocioso ......... ela: "não saiu"
    os quatro timbres logo depois ...... ela: "saiu no controle"
    canal 1 sozinho, nó já acordado .... ela: "tuuuuuuuu"

Nada mudou entre as três passadas além do ESTADO DO NÓ. O `pactl list sinks
short` mostra os sinks do DualSense em ``SUSPENDED`` quando ociosos, e o religar
do hardware **come o começo do som**. TRÊS leituras da primeira rodada foram
descartadas por causa disto — o defeito enganou a própria bancada antes de
enganar o jogo. Ensaio: ``sfx-no-suspenso-come-o-comeco`` em
``docs/data/ensaios.csv``.

A CURA, e por que ela é CONFIGURAÇÃO e não um fluxo aquecedor
=============================================================
MEDIDO no WirePlumber instalado nesta máquina (0.5.12), em
``/usr/share/wireplumber/scripts/node/suspend-node.lua:38-45``: ao entrar em
``idle``, o hook agenda a suspensão para ``session.suspend-timeout-seconds``
(padrão 5 s) e, **se o valor for ZERO, retorna sem agendar nada**. Quem suspende
o nó é esse relógio — não a falta de som. Um fluxo aquecedor de 1 LSB manteria o
nó em RUNNING pagando CPU, um cliente de áudio novo e um fluxo a arbitrar contra
os três modos que ela quer no fim do projeto; a regra chega no mesmo lugar sem
nada disso.

O QUE ESTE ARQUIVO TRAVA
========================
1. o drop-in 54 zera o relógio de suspensão **do sink do DualSense**;
2. e **não** faz isso com o microfone (um mic que nunca dorme é um mic sempre
   aberto — bateria e privacidade) nem com o resto da máquina;
3. o ``install.sh`` o instala **SEM FLAG**, fora de todo ramo de decisão sobre o
   microfone, nos DOIS caminhos (nativo e formatos empacotados);
4. o ``uninstall.sh`` o remove — nenhuma regra de áudio do Hefesto fica para
   trás depois de desinstalar o Hefesto;
5. a função de instalação é SÓ ARQUIVO, é idempotente, e o ``--enable-mic`` não
   a desfaz;
6. a aba Status consegue dizer o estado — inclusive denunciar a cura arrancada.

A semântica do item 1 é verificada executando a regra: o teste reimplementa a
decisão do ``suspend-node.lua`` (que está citada acima, linha a linha) e
pergunta a ela, para nomes de nó MEDIDOS nesta máquina, se o nó ainda seria
suspenso. Nada aqui toca hardware, áudio, daemon ou rede — roda no CI.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.app import audio_saida

RAIZ = Path(__file__).resolve().parents[2]
NOME = "54-hefesto-dualsense-alto-falante-nunca-dorme.conf"
DROPIN = RAIZ / "assets" / "wireplumber" / NOME
WP_FIX = RAIZ / "scripts" / "fix_wireplumber_default_source.sh"
INSTALL = RAIZ / "install.sh"
UNINSTALL = RAIZ / "uninstall.sh"

#: A chave que o `suspend-node.lua` lê. MEDIDO no fonte instalado (0.5.12).
CHAVE = "session.suspend-timeout-seconds"

#: O padrão do WirePlumber quando ninguém diz nada — cinco segundos de ócio e o
#: nó dorme. MEDIDO em `suspend-node.lua:41` (`or 5`).
PADRAO_DO_WIREPLUMBER_S = 5.0

#: Nomes MEDIDOS com `pactl list sinks short` nesta máquina, em 16/08/2026, com
#: dois controles na mesa. São eles que a regra precisa alcançar.
SINKS_DO_CONTROLE = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00.analog-surround-40",
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00.2.analog-surround-40",
)

#: O resto da máquina, medido no mesmo instante. Nada disto pode mudar de sono
#: por causa desta cura.
SINKS_DA_CASA = (
    "alsa_output.pci-0000_0c_00.4.iec958-stereo",
    "alsa_output.pci-0000_0a_00.1.hdmi-stereo",
)

#: A ENTRADA do controle. Fica de fora DE PROPÓSITO (ver item 2 do topo).
FONTE_DO_CONTROLE = (
    "alsa_input.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller"
    "-00.iec958-stereo"
)


# ---------------------------------------------------------------------------
# Um leitor mínimo de `monitor.alsa.rules`, e a decisão do suspend-node.lua
# ---------------------------------------------------------------------------


def _blocos_de_regra(texto: str) -> list[str]:
    """As regras de primeiro nível de ``monitor.alsa.rules = [ ... ]``.

    Varredura por chaves balanceadas em vez de regex de bloco: o arquivo tem
    comentários com chaves e parênteses dentro, e um regex ganancioso os
    engoliria. Linhas de comentário saem antes da varredura.
    """
    sem_comentario = "\n".join(
        linha for linha in texto.splitlines() if not linha.lstrip().startswith("#")
    )
    inicio = sem_comentario.find("monitor.alsa.rules")
    assert inicio >= 0, f"{NOME} não declara monitor.alsa.rules"
    corpo = sem_comentario[sem_comentario.index("[", inicio) + 1 :]
    blocos: list[str] = []
    profundidade = 0
    atual: list[str] = []
    for ch in corpo:
        if ch == "{":
            profundidade += 1
            if profundidade == 1:
                atual = []
                continue
        elif ch == "}":
            profundidade -= 1
            if profundidade == 0:
                blocos.append("".join(atual))
                continue
        if profundidade >= 1:
            atual.append(ch)
    return blocos


def _padroes_de_nome(bloco: str) -> list[str]:
    """As expressões de ``node.name = "~..."`` dentro de um bloco de regra."""
    trecho = bloco[bloco.find("matches") : bloco.find("actions")]
    return re.findall(r'node\.name\s*=\s*"~([^"]+)"', trecho)


def _props(bloco: str) -> dict[str, str]:
    """As ``update-props`` do bloco, como texto cru."""
    trecho = bloco[bloco.find("update-props") :]
    return {
        chave: valor.strip()
        for chave, valor in re.findall(r"([a-z][a-z0-9._-]*)\s*=\s*([^\n}]+)", trecho)
        if chave != "update-props"
    }


def _props_do_no(nome_do_no: str) -> dict[str, str]:
    """O que o drop-in acrescenta às propriedades de um nó com este nome."""
    saida: dict[str, str] = {}
    for bloco in _blocos_de_regra(DROPIN.read_text(encoding="utf-8")):
        if any(re.search(padrao, nome_do_no) for padrao in _padroes_de_nome(bloco)):
            saida.update(_props(bloco))
    return saida


def _vai_dormir(nome_do_no: str) -> bool:
    """A decisão do `suspend-node.lua`, reimplementada.

    Fonte, MEDIDA em ``/usr/share/wireplumber/scripts/node/suspend-node.lua``::

        local timeout =
            tonumber(node.properties["session.suspend-timeout-seconds"]) or 5
        if timeout == 0 then
          return
        end
        sources[id] = Core.timeout_add(timeout * 1000, ...)

    Ou seja: zero é o ÚNICO valor que impede o agendamento.
    """
    bruto = _props_do_no(nome_do_no).get(CHAVE)
    try:
        segundos = float(bruto) if bruto is not None else PADRAO_DO_WIREPLUMBER_S
    except ValueError:  # `tonumber` devolveria nil, e o lua cairia no `or 5`
        segundos = PADRAO_DO_WIREPLUMBER_S
    return segundos != 0.0


# ---------------------------------------------------------------------------
# 1. A regra, executada: o alto-falante do controle não dorme
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sink", SINKS_DO_CONTROLE)
def test_o_sink_do_controle_nao_dorme(sink: str) -> None:
    """ARRANQUE A CURA: apague a linha ``session.suspend-timeout-seconds = 0``
    do drop-in 54 (ou troque o 0 por qualquer outro número) e este teste REPROVA
    — é o estado exato da bancada de 15/08, em que o primeiro som depois do
    silêncio não saía.
    """
    assert not _vai_dormir(sink), (
        f"o sink {sink} continuaria sendo suspenso pelo WirePlumber depois de "
        f"{PADRAO_DO_WIREPLUMBER_S:.0f}s ocioso: o drop-in {NOME} não põe "
        f"'{CHAVE} = 0' nele. Medido em 15/08/2026 23h45 na orelha dela — com o "
        "nó suspenso, o começo do som se perde no religar do hardware."
    )


def test_a_regra_vale_para_qualquer_dualsense_e_nao_so_para_o_dela() -> None:
    """UNIVERSAL: nada de MAC, de índice de card, de ordem de conexão.

    O nome do nó carrega o índice do card (`-00.2.`) e a lista de sinks muda com
    quantos controles estão na mesa. Uma regra que casasse o nome inteiro curaria
    o controle dela e ninguém mais.
    """
    inventados = (
        "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00.7.analog-surround-40",
        "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Edge_Wireless_Controller-00.analog-surround-40",
        "alsa_output.usb-Sony_Interactive_Entertainment_dualsense_Wireless_Controller-00.analog-stereo",
    )
    dorminhocos = [nome for nome in inventados if _vai_dormir(nome)]
    assert not dorminhocos, (
        "estes sinks de DualSense continuariam dormindo — a regra não é "
        f"universal: {dorminhocos}"
    )


@pytest.mark.parametrize("sink", SINKS_DA_CASA)
def test_o_resto_da_maquina_dorme_como_sempre(sink: str) -> None:
    """A cura é do controle. A televisão e a placa do PC não são nossas."""
    assert _vai_dormir(sink), (
        f"{sink} não é do controle e teve o sono desligado pelo {NOME}: o "
        "produto estaria mudando o áudio da máquina inteira para curar o som do "
        "alto-falante do DualSense."
    )


def test_o_microfone_do_controle_continua_dormindo() -> None:
    """De propósito, e não é esquecimento.

    A queixa dela é o som que SAI. Um ``alsa_input`` que nunca suspende é um
    microfone com o hardware sempre aberto — bateria no rádio e privacidade na
    sala. Se um dia isso mudar, tem de ser uma decisão dela, não um efeito
    colateral de um regex largo demais.
    """
    assert _vai_dormir(FONTE_DO_CONTROLE), (
        f"o {NOME} desligou o sono da ENTRADA do controle ({FONTE_DO_CONTROLE}). "
        "Um microfone que nunca dorme fica sempre aberto — isso é decisão dela, "
        "não efeito colateral do padrão de nome."
    )


def test_o_drop_in_nao_decide_mais_nada() -> None:
    """Só o sono. Volume, rota, prioridade e quem toca são de outros donos.

    O 51 já brigou por ter opinião demais (prioridade de fonte) e virou três
    revisões. Este arquivo tem uma propriedade só, e o portão a mantém sozinha.
    """
    chaves: set[str] = set()
    for bloco in _blocos_de_regra(DROPIN.read_text(encoding="utf-8")):
        chaves.update(_props(bloco))
    assert CHAVE in chaves, f"o {NOME} não escreve mais o sono ({CHAVE})"
    assert chaves == {CHAVE}, (
        f"o {NOME} passou a escrever {sorted(chaves - {CHAVE})} além do sono — "
        "cada propriedade a mais é uma decisão de áudio tomada por um arquivo "
        "que a tela não mostra."
    )


def test_o_parser_deste_portao_concorda_com_o_do_pipewire() -> None:
    """A régua conferida contra uma contagem independente.

    *"O instrumento mente mais que o produto"* é regra desta casa, e o leitor de
    `monitor.alsa.rules` daqui em cima é instrumento: um regex que concorda
    consigo mesmo aprovaria um arquivo que o WirePlumber recusa, e o portão
    ficaria verde com o alto-falante dormindo na máquina dela.

    O `spa-json-dump` vem com o PipeWire e usa o MESMO parser de SPA-JSON que o
    WirePlumber usa para ler este arquivo. Quando ele existe, o portão exige que
    os dois leiam a mesma coisa. Onde ele não existe (CI enxuto), o teste pula —
    a checagem é reforço, não a base.
    """
    spa = shutil.which("spa-json-dump")
    if spa is None:
        pytest.skip("spa-json-dump não instalado (vem com o PipeWire)")
    bruto = subprocess.run(
        [spa, str(DROPIN)], capture_output=True, text=True, timeout=30, check=False
    )
    assert bruto.returncode == 0, (
        f"o parser do PipeWire RECUSOU o {NOME} — o WirePlumber ignoraria o "
        f"arquivo inteiro e o alto-falante continuaria dormindo: {bruto.stderr}"
    )
    lido = json.loads(bruto.stdout)
    regras = lido["monitor.alsa.rules"]
    assert len(regras) == 1
    props = regras[0]["actions"]["update-props"]
    assert props == {CHAVE: 0}, f"o PipeWire lê {props} onde este portão lê o sono zerado"
    # e o parser caseiro tem de chegar no mesmo lugar
    assert _props_do_no(SINKS_DO_CONTROLE[0]) == {CHAVE: "0"}


# ---------------------------------------------------------------------------
# 2. O install põe SEM FLAG, e o uninstall tira
# ---------------------------------------------------------------------------


#: Uma CHAMADA de verdade, não a palavra `--nunca-dorme` numa mensagem de aviso.
#: A primeira versão deste portão contava linhas com o texto, e não mordeu:
#: arrancada a chamada nativa, o `warn` que sobrava no outro ramo ainda
#: continha a palavra e o teste passou verde. O portão precisa exigir a
#: EXECUÇÃO, como o `test_paridade_quente_dos_instaladores` já ensinava.
_CHAMADA = re.compile(
    r"^\s*(?:if\s+)?bash\s+\"\$\{ROOT_DIR\}/scripts/fix_wireplumber_default_source\.sh\"\s+"
    r"(?:\\\s*\n\s*)?--nunca-dorme",
    re.M,
)

#: Onde começa o caminho NATIVO do instalador. Tudo antes disto é preparo comum
#: e o ramo dos formatos empacotados, que sai por um `exit 0` próprio.
_ANCORA_NATIVO = 'step "1/11"'


def test_o_install_chama_o_nunca_dorme_nos_dois_caminhos() -> None:
    """SEM FLAG, e nos DOIS caminhos do instalador.

    O `install.sh` tem duas saídas: a dos formatos empacotados
    (`--flatpak`/`--appimage`/`--deb`, que sai por um `exit 0` antes do passo
    1/11) e a nativa. MIC-EM-TODO-FORMATO-01 pagou em 10/08 exatamente por uma
    cura de áudio que só existia num deles — e a cura estava escrita.

    ARRANQUE A CURA: apague qualquer uma das duas chamadas e este teste REPROVA
    nomeando o caminho que ficou sem.
    """
    texto = INSTALL.read_text(encoding="utf-8")
    corte = texto.index(_ANCORA_NATIVO)
    empacotado = _CHAMADA.findall(texto[:corte])
    nativo = _CHAMADA.findall(texto[corte:])
    assert empacotado, (
        "o caminho dos formatos empacotados (--flatpak/--appimage/--deb) não "
        "chama o `fix_wireplumber_default_source.sh --nunca-dorme`: quem "
        "instalar por pacote fica com o alto-falante dormindo"
    )
    assert nativo, (
        "o caminho NATIVO do install.sh não chama o "
        "`fix_wireplumber_default_source.sh --nunca-dorme`: a instalação padrão "
        "fica com o alto-falante dormindo"
    )


def test_o_nunca_dorme_nao_depende_de_nenhuma_flag_de_microfone() -> None:
    """O sono da SAÍDA não pode ficar refém da política de ENTRADA.

    `--keep-dualsense-mic` diz "não rebaixe meu microfone". Não diz "aceito
    perder o começo de cada efeito sonoro". Se a chamada do `--nunca-dorme`
    cair dentro do `if`/`elif` que decide o microfone, a cura vira opt-in por
    acidente de posição — e "opt-in" é o que esta casa proíbe.

    ARRANQUE A CURA: mova a chamada para dentro do ramo do
    `WITH_WIREPLUMBER_FIX` e este teste REPROVA.
    """
    texto = INSTALL.read_text(encoding="utf-8")
    # As POSIÇÕES das chamadas, não o texto delas: as duas são literalmente
    # iguais, e procurar por `texto.index(...)` devolvia sempre a primeira — foi
    # assim que a primeira versão deste portão deixou passar a chamada movida
    # para dentro do ramo.
    for casamento in _CHAMADA.finditer(texto):
        antes = texto[: casamento.start()]
        ultimo_if = max(
            antes.rfind('if [[ "${WITH_WIREPLUMBER_DISABLE_MIC}"'),
            antes.rfind('elif [[ "${WITH_WIREPLUMBER_FIX}"'),
        )
        if ultimo_if < 0:
            continue  # nenhuma decisão de microfone antes desta chamada
        # havendo um `fi` de coluna zero entre o ramo e a chamada, o ramo já
        # fechou e a chamada está fora dele — que é o lugar certo.
        assert "\nfi\n" in antes[ultimo_if:], (
            "a chamada do --nunca-dorme está DENTRO do ramo que decide o "
            "microfone — a cura do alto-falante virou opt-in por acidente de "
            f"posição (linha {texto[: casamento.start()].count(chr(10)) + 1} do install.sh)"
        )


def test_o_uninstall_remove_a_regra() -> None:
    """PARIDADE: o que o install põe, o uninstall tira.

    ARRANQUE A CURA: apague o bloco de remoção do 54 no `uninstall.sh` e este
    teste REPROVA — seria uma regra de áudio do Hefesto sobrevivendo à
    desinstalação do Hefesto, na configuração de áudio DELA.
    """
    texto = UNINSTALL.read_text(encoding="utf-8")
    assert NOME in texto, f"o uninstall.sh não conhece o {NOME}"
    assert re.search(r'rm -f "\$\{WIREPLUMBER_DROPIN_ACORDADO\}"', texto), (
        f"o uninstall.sh cita o {NOME} mas não o REMOVE — citar não apaga arquivo"
    )


# ---------------------------------------------------------------------------
# 3. A função de instalação, EXECUTADA num HOME de mentira
# ---------------------------------------------------------------------------


def _ambiente(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """``(dir_dos_dropins, env)`` para rodar o wp-fix sem tocar no áudio de ninguém.

    Mesmo molde de `test_ligar_que_apagava_a_cura_01`: o script monta o
    ``DROPIN_DIR`` a partir do ``HOME`` no carregamento (e as variáveis são
    ``readonly``), então o HOME precisa ser falso ANTES do ``source``. Os dublês
    de ``systemctl``/``wpctl``/``pactl`` são cinto e suspensório — a função sob
    teste é só-arquivo, e se alguém acrescentar uma chamada dessas um dia, a
    sessão dela não paga a conta.
    """
    casa = tmp_path / "casa"
    dropins = casa / ".config" / "wireplumber" / "wireplumber.conf.d"
    dropins.mkdir(parents=True)
    binario = tmp_path / "bin"
    binario.mkdir()
    for nome in ("systemctl", "wpctl", "pactl"):
        alvo = binario / nome
        alvo.write_text(
            f'#!/bin/bash\nprintf "DUBLE {nome} %s\\n" "$*" >&2\nexit 0\n',
            encoding="utf-8",
        )
        alvo.chmod(0o755)
    env = {"PATH": f"{binario}:/usr/bin:/bin", "HOME": str(casa), "WP_FIX": str(WP_FIX)}
    return dropins, env


def _rodar(func: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Executa uma função REAL do wp-fix por ``source``, sem despachar o main."""
    return subprocess.run(
        ["bash", "-c", f'set --; source "$WP_FIX"; {func}'],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={**env},
    )


def test_a_instalacao_poe_o_arquivo_e_e_idempotente(tmp_path: Path) -> None:
    """Instala; roda de novo e não mexe em nada.

    A idempotência não é elegância: sem ela, cada `install.sh` reiniciaria o
    WirePlumber da sessão dela por nada — e reiniciar áudio no meio de um jogo é
    um custo real para curar coisa nenhuma.
    """
    dropins, env = _ambiente(tmp_path)

    primeira = _rodar("install_dropin_acordado", env)
    assert primeira.returncode == 0, primeira.stderr
    posto = dropins / NOME
    assert posto.is_file(), "a função não criou o drop-in"
    assert posto.read_text(encoding="utf-8") == DROPIN.read_text(encoding="utf-8")

    segunda = _rodar("install_dropin_acordado", env)
    assert segunda.returncode == 3, (
        "a segunda passada tem de dizer 'já estava igual' (3) para o chamador "
        f"não reiniciar o WirePlumber à toa; devolveu {segunda.returncode}"
    )


def test_a_instalacao_nao_toca_no_audio_de_ninguem(tmp_path: Path) -> None:
    """SÓ ARQUIVO: nenhum `systemctl`, `wpctl` ou `pactl` dentro da função."""
    _, env = _ambiente(tmp_path)
    res = _rodar("install_dropin_acordado", env)
    assert "DUBLE" not in res.stderr, (
        "a função de instalação chamou uma ferramenta de áudio: "
        f"{res.stderr.strip()}"
    )


def test_ligar_o_microfone_nao_desfaz_o_nunca_dorme(tmp_path: Path) -> None:
    """O botão "Ligar" do microfone já apagou uma cura desta casa uma vez.

    LIGAR-QUE-APAGAVA-A-CURA-01 (10/08): o `--enable-mic` removia o promotor 51
    junto com a supressão. O 54 não é supressão de nada — é o sono do
    alto-falante — e removê-lo ao mexer no microfone repetiria o mesmo defeito
    num arquivo novo.

    ARRANQUE A CURA: acrescente ``"${DROPIN_ACORDADO_DST}"`` ao ``for`` de
    ``_arma_dropins_do_mic`` e este teste REPROVA.
    """
    dropins, env = _ambiente(tmp_path)
    (dropins / NOME).write_text(DROPIN.read_text(encoding="utf-8"), encoding="utf-8")

    res = _rodar("_arma_dropins_do_mic", env)

    assert res.returncode == 0, res.stderr
    assert (dropins / NOME).is_file(), (
        "mexer no microfone apagou o drop-in que mantém o alto-falante acordado"
    )


def _bloco_de_remocao_do_uninstall() -> str:
    """O trecho REAL do `uninstall.sh` que apaga o 54, pronto para rodar.

    O teste não reescreve o que o uninstall faz — ele EXECUTA o texto do
    próprio arquivo, com o `${HOME}` do ambiente falso. Uma cura provada contra
    uma cópia da cura não prova nada.
    """
    texto = UNINSTALL.read_text(encoding="utf-8")
    decl = re.search(r'^readonly WIREPLUMBER_DROPIN_ACORDADO=.*$', texto, re.M)
    assert decl, "o uninstall.sh não declara WIREPLUMBER_DROPIN_ACORDADO"
    bloco = re.search(
        r'^if \[\[ -f "\$\{WIREPLUMBER_DROPIN_ACORDADO\}" \]\]; then\n.*?^fi$',
        texto,
        re.M | re.S,
    )
    assert bloco, "o uninstall.sh não tem o bloco que remove o 54"
    return f"log() {{ printf '[uninstall] %s\\n' \"$*\"; }}\n{decl.group(0)}\n{bloco.group(0)}\n"


def test_o_ciclo_uninstall_install_devolve_a_cura(tmp_path: Path) -> None:
    """A prova por CICLO, sem tocar na máquina de ninguém.

    "Toda cura entra no install, sem flag" só vale se sobreviver ao ciclo — foi
    `9c944a8` (*"o ciclo uninstall+install desligava SEIS curas de módulo em
    silêncio"*) que ensinou isto a esta casa. Rodar o `install.sh` e o
    `uninstall.sh` de verdade aqui reiniciaria o áudio de quem roda a suíte, e a
    bancada é dela — então o ciclo roda com as DUAS metades reais (a função do
    wp-fix e o bloco do uninstall, lido do arquivo) num HOME de mentira.

    ARRANQUE A CURA em qualquer uma das duas pontas e este teste REPROVA.
    """
    dropins, env = _ambiente(tmp_path)
    posto = dropins / NOME

    # install
    assert _rodar("install_dropin_acordado", env).returncode == 0
    assert posto.is_file(), "o install não pôs a regra"

    # uninstall — o texto REAL do uninstall.sh
    fora = subprocess.run(
        ["bash", "-c", _bloco_de_remocao_do_uninstall()],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={**env},
    )
    assert fora.returncode == 0, fora.stderr
    assert not posto.exists(), (
        "o uninstall deixou a regra de áudio do Hefesto na máquina depois de "
        "desinstalar o Hefesto"
    )

    # install de novo — e a cura VOLTA sem ninguém pedir
    assert _rodar("install_dropin_acordado", env).returncode == 0
    assert posto.is_file(), (
        "depois de um ciclo uninstall→install a regra não voltou: o alto-falante "
        "volta a dormir e o começo do som some, em silêncio"
    )


# ---------------------------------------------------------------------------
# 4. A tela sabe dizer — inclusive quando a cura foi arrancada
# ---------------------------------------------------------------------------


def test_o_nome_do_arquivo_e_o_mesmo_dos_dois_lados() -> None:
    """O literal do Python e o arquivo em `assets/` não podem divergir.

    Se alguém renomear o asset sem renomear a constante, a aba Status passa a
    afirmar "pode dormir" com a cura instalada — e a tela mentindo sobre o
    produto é pior do que a tela calada.
    """
    assert audio_saida.NOME_REGRA_NUNCA_DORME == NOME == DROPIN.name


def test_a_tela_denuncia_a_cura_arrancada() -> None:
    """Com a regra fora do lugar, "acordado agora" não vale como "curado".

    Um nó pode estar acordado por acaso — alguém tocou algo há dois segundos.
    Chamar isso de curado esconderia justamente o estado que precisa aparecer.
    """
    acordado_por_acaso = {SINKS_DO_CONTROLE[0]: "RUNNING"}
    assert (
        audio_saida.texto_do_sono(False, acordado_por_acaso)
        == audio_saida.TEXTO_SONO_PODE_DORMIR
    )


def test_a_tela_le_os_quatro_estados() -> None:
    """Os quatro que existem, e nenhum a mais."""
    assert audio_saida.texto_do_sono(True, {}) == audio_saida.TEXTO_SONO_SEM_PLACA
    assert (
        audio_saida.texto_do_sono(True, {SINKS_DO_CONTROLE[0]: "SUSPENDED"})
        == audio_saida.TEXTO_SONO_ATRASADO
    )
    assert (
        audio_saida.texto_do_sono(
            True, {SINKS_DO_CONTROLE[0]: "IDLE", SINKS_DO_CONTROLE[1]: "RUNNING"}
        )
        == audio_saida.TEXTO_SONO_ACORDADO
    )
    assert (
        audio_saida.texto_do_sono(
            True, {SINKS_DO_CONTROLE[0]: "IDLE", SINKS_DO_CONTROLE[1]: "SUSPENDED"}
        )
        == audio_saida.TEXTO_SONO_ATRASADO
    ), "com DOIS controles, um dormindo já é um som que se perde"


def test_a_leitura_do_pactl_pega_o_estado_e_ignora_o_resto_da_casa() -> None:
    """Formato tabulado real, copiado de `pactl list sinks short` desta máquina."""
    saida = (
        "19595\talsa_output.pci-0000_0c_00.4.iec958-stereo\tPipeWire"
        "\ts32le 2ch 48000Hz\tSUSPENDED\n"
        "33286\talsa_output.pci-0000_0a_00.1.hdmi-stereo\tPipeWire\ts16le 2ch 48000Hz\tIDLE\n"
        f"35872\t{SINKS_DO_CONTROLE[1]}\tPipeWire\ts16le 4ch 48000Hz\tSUSPENDED\n"
        f"38849\t{SINKS_DO_CONTROLE[0]}\tPipeWire\ts16le 4ch 48000Hz\tRUNNING\n"
    )
    estados = audio_saida.sono_dos_sinks_do_controle(saida)
    assert estados == {
        SINKS_DO_CONTROLE[1]: "SUSPENDED",
        SINKS_DO_CONTROLE[0]: "RUNNING",
    }


def test_o_caminho_da_regra_sai_do_home_e_nao_de_um_literal(tmp_path: Path) -> None:
    """A tela procura o arquivo onde o instalador o põe, em qualquer HOME."""
    esperado = tmp_path / ".config" / "wireplumber" / "wireplumber.conf.d" / NOME
    assert audio_saida.caminho_regra_nunca_dorme(str(tmp_path)) == str(esperado)
    assert not audio_saida.regra_nunca_dorme_instalada(str(tmp_path))
    esperado.parent.mkdir(parents=True)
    esperado.write_text("# dublê\n", encoding="utf-8")
    assert audio_saida.regra_nunca_dorme_instalada(str(tmp_path))
