#!/usr/bin/env python3
"""os_nos_de_som_por_controle.py — os quatro nós na lista VIVA do sistema, por controle.

A PERGUNTA QUE ELE RESPONDE (SOM-POR-CONTROLE-01 §1 e §6; MIC-OS-QUATRO-01)
----------------------------------------------------------------------------
Duas sprints estão `feita` — O-ALTO-FALANTE-VIRTUAL-01 e SOM-QUE-SAI-01 — e
os nós que elas descrevem **não estavam na mesa dela em 08/09 às 23h**
(`pactl`: 2 sinks USB, 2 fontes USB, HDMI padrão, 0 «Alto-falante do
Controle N», 0 nó de rádio). *Régua verde sobre nó que não existe é a
assinatura dos instrumentos falsos desta casa.* Este instrumento lê a lista
viva e diz, por controle físico:

    sink FÍSICO (a placa USB)     só no cabo, e some com o cabo
    «Alto-falante do Controle N»  o nó por controle, que NÃO some
    «Microfone do Controle N»     idem, na entrada
    a FONTE                       mix (há um loopback do monitor da saída
                                  padrão para o nó) ou sfx (o nó está livre)

É LEITURA PURA: `pactl`, `/sys` e `/proc`. Não escreve no aparelho, não muda
o sink padrão, não carrega módulo nenhum.

A MORDIDA DO §6, ao vivo
------------------------
`--observar 60` fica sessenta segundos relendo a lista a cada 2 s e imprime
cada nó que APARECEU ou SUMIU. É o teste de *tirar o cabo de um e o nó dele
continuar na lista* — ela tira, o instrumento diz o que a lista fez.

Os nomes dos nós são decisão dela de 09/09/2026 (*"4a"*): «Alto-falante do
Controle N» · «Microfone do Controle N». Esses rótulos são o que ELA lê; o
instrumento **não casa por eles**.

O DONO DO NÓ SE PERGUNTA PELO NOME DE DENTRO, NUNCA PELA PROSA (12/09/2026)
--------------------------------------------------------------------------
TRES-CONTAS-PARA-UM-NUMERO-01 §6. Até 11/09 este instrumento decidia de quem
era o nó comparando o TEXTO do `Description`, cujo N é o número do assento.
Medido em 09/09: entre duas corridas, com a mesa mudando, **o mesmo nó virtual
passou a ser atribuído a outro controle** — o número andou, o texto andou junto,
e o censo seguiu o texto.

A ressalva dela fecha a questão, e é sobre PRODUTO:

    *"aí é foda pq a ideia não é termos nada focado pro meu caso apenas, mas
    como produto que possa funcionar com outra pessoa."*  (noqa-acento: dela)

O rótulo é prosa em português: muda com tradução, muda quando o assento anda, e
some se alguém renomear o nó à mão. A âncora é o que o daemon ESCREVE e não muda
de forma — o NOME de dentro do nó, que carrega o endereço do controle:

    `alto_falante_bt.nome_do_sink(uniq)`      → `hefesto_som_<hex6>`
    `canal_do_microfone.nome_do_canal(uniq)`  → `hefesto_mic_<hex6>`

Os dois vêm do produto, por `uniq`. A metade da saída já casava assim desde que
nasceu; a da ENTRADA recebia `""` no lugar do nome e por isso só tinha a prosa.
Renomeie o `Description` de um nó à mão e o censo continua acertando o dono — se
ele errar, ele voltou a ler prosa.

USO
    os_nos_de_som_por_controle.py
    os_nos_de_som_por_controle.py --observar 60
    os_nos_de_som_por_controle.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)

from comum import CABO, cabecalho_do_instrumento, resumo
from escrita_pelo_broker import alvos_da_mesa, mascarar
from microfone_no_cabo import placas_de_dualsense


def _rotulo_do_produto(qual: str) -> str:
    """«Alto-falante do Controle» / «Microfone do Controle», do DONO da constante.

    Estavam digitados aqui, os dois. Um rótulo digitado num instrumento é a forma
    de régua falsa que esta casa já nomeou onze vezes: ela mede o que ALGUÉM
    escreveu, não o que o produto publica — mude o rótulo no produto e o censo
    passa a dizer «NÃO EXISTE» a um nó que está lá.

    Só entra na FRASE que ela lê (a coluna de faltas). Quem decide o dono do nó é
    `_casa`, pelo nome de dentro.
    """
    try:
        if qual == "saida":
            from hefesto_dualsense4unix.integrations import alto_falante_bt as dono
            return str(dono.NOME_DO_ALTO_FALANTE_DO_CONTROLE)
        from hefesto_dualsense4unix.integrations import dualsense_bt_audio as mic
        return str(mic.NOME_DO_MICROFONE_DO_CONTROLE)
    except Exception:
        return ""


def _falta(qual: str, numero: int, nome_de_dentro: str) -> str:
    """A frase da coluna de faltas: o rótulo que ela lê E o nome que o censo procurou."""
    rotulo = _rotulo_do_produto(qual)
    pedacos = [f"«{rotulo} {numero}»" if rotulo else "", f"({nome_de_dentro})" if nome_de_dentro else ""]
    alvo = " ".join(p for p in pedacos if p)
    return f"sem {alvo}" if alvo else "sem o nó (controle sem identidade legível)"


def pactl(*argv: str) -> str:
    """`pactl <argv>` EM INGLÊS, ou "" quando o pactl não existe ou o servidor não responde.

    `LC_ALL=C` não é capricho: na máquina dela o pactl fala português — `Nome:`,
    `Descrição:` — e um parser que procura `Name:` diz «NÃO EXISTE» a um sink
    que está lá. Foi o que aconteceu na primeira corrida, em 09/09.
    """
    if not shutil.which("pactl"):
        return ""
    try:
        proc = subprocess.run(["pactl", *argv], capture_output=True, text=True, timeout=8,
                              check=False, env={**os.environ, "LC_ALL": "C"})
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout if proc.returncode == 0 else ""


def linhas_curtas(saida: str) -> list[tuple[str, str]]:
    """`pactl list short X` -> [(nome, resto)], ignorando o índice."""
    achados = []
    for linha in saida.splitlines():
        partes = linha.split("\t")
        if len(partes) >= 2:
            achados.append((partes[1], "\t".join(partes[2:])))
    return achados


def blocos_longos(saida: str) -> list[dict[str, str]]:
    """`pactl list sinks|sources` -> um dicionário por bloco, com Name, Description e as propriedades."""
    blocos: list[dict[str, str]] = []
    atual: dict[str, str] = {}
    for linha in saida.splitlines():
        if linha and not linha.startswith((" ", "\t")):
            if atual:
                blocos.append(atual)
            atual = {}
            continue
        despida = linha.strip()
        if ":" in despida and not despida.startswith('"'):
            chave, _, valor = despida.partition(":")
            atual[chave.strip()] = valor.strip()
        elif "=" in despida:
            chave, _, valor = despida.partition("=")
            atual[chave.strip()] = valor.strip().strip('"')
    if atual:
        blocos.append(atual)
    return blocos


def loopbacks(saida_modulos: str) -> list[str]:
    """Os argumentos de cada `module-loopback` carregado — é neles que mora o mix."""
    return [resto for nome, resto in linhas_curtas(saida_modulos) if nome == "module-loopback"]


@dataclass
class NoDoControle:
    mac: str
    transporte: str
    sink_fisico: str = ""
    fonte_fisica: str = ""
    alto_falante_virtual: str = ""
    microfone_virtual: str = ""
    fonte: str = "sfx"  #: mix quando há loopback apontando para o nó
    faltas: list[str] = field(default_factory=list)


def _nome_do_sink_de_dentro(mac: str) -> str:
    """`hefesto_som_<hex6>` deste controle, PERGUNTADO ao produto."""
    try:
        from hefesto_dualsense4unix.integrations import alto_falante_bt
    except ImportError:
        return ""
    try:
        return alto_falante_bt.nome_do_sink(mac) or ""
    except Exception:
        return ""


def _nome_da_fonte_de_dentro(mac: str) -> str:
    """`hefesto_mic_<hex6>` deste controle, PERGUNTADO ao dono do canal.

    O par do `_nome_do_sink_de_dentro`, e ele FALTAVA — era por isso que a
    metade da entrada só tinha o texto do `Description` para casar.
    """
    try:
        from hefesto_dualsense4unix.integrations import canal_do_microfone
    except ImportError:
        return ""
    try:
        return canal_do_microfone.nome_do_canal(mac) or ""
    except Exception:
        return ""


def _casa(nome: str, nome_de_dentro: str) -> bool:
    """O nó é DESTE controle? Pelo nome de dentro, nunca pelo rótulo.

    Casa por igualdade, não por substring: `hefesto_mic_c311f0` não pode casar
    com um `hefesto_mic_c311f01` que não é dele — é a mesma armadilha que
    `SourceVirtualPipeWire._modulos_da_source` já paga com casamento por token.

    Sem nome de dentro (controle sem identidade legível) a resposta é NÃO. O
    censo prefere dizer «NÃO EXISTE» a atribuir o nó de alguém ao vizinho: a
    ausência é resposta, o dono errado é mentira.
    """
    return bool(nome_de_dentro) and nome == nome_de_dentro


def _numero_pelo_daemon() -> dict[str, int]:
    """`uniq -> «Controle N»`, lido do daemon VIVO; vazio quando ele não responde.

    **É O `player_slot`, e só ele — TRES-CONTAS-PARA-UM-NUMERO-01, 12/09/2026.**
    Este dicionário lia `player`, `jogador`, `assento` ou `slot`, o primeiro que
    aparecesse numa varredura em profundidade do estado. Eram até QUATRO campos
    para a pergunta que tem UM dono: o `player_slot` é o número que o cartão
    imprime (`app/actions/base.numero_do_controle`) e é o que o daemon usa para
    batizar o nó. `player` é outra pergunta — *"este controle está jogando
    agora, e como quem?"* —, e fora do co-op ele é `1` para todos.

    O número aqui é só para a TABELA e para a ordenação; quem decide o dono do
    nó é `_casa`, pelo nome de dentro.
    """
    try:
        from hefesto_dualsense4unix.app import ipc_bridge
        estado = ipc_bridge.daemon_state_full() or {}
    except Exception:
        return {}
    numeros: dict[str, int] = {}
    pilha: list = [estado]
    while pilha:
        item = pilha.pop()
        if isinstance(item, dict):
            uniq = item.get("uniq")
            numero = item.get("player_slot")
            if (
                isinstance(uniq, str)
                and isinstance(numero, int)
                and not isinstance(numero, bool)
                and numero > 0
            ):
                numeros[uniq.lower()] = numero
            pilha.extend(item.values())
        elif isinstance(item, list):
            pilha.extend(item)
    return numeros


def censo(aparelhos: list) -> list[NoDoControle]:
    sinks = blocos_longos(pactl("list", "sinks"))
    fontes = blocos_longos(pactl("list", "sources"))
    modulos = loopbacks(pactl("list", "short", "modules"))
    placas = {p.dono.hidraw: p for p in placas_de_dualsense(aparelhos) if p.dono is not None}
    numeros = _numero_pelo_daemon()
    ordenados = sorted(aparelhos, key=lambda x: (numeros.get(x.mac.lower(), 99), x.hidraw))
    resultado: list[NoDoControle] = []
    for posicao, a in enumerate(ordenados, start=1):
        numero = numeros.get(a.mac.lower(), posicao)
        no = NoDoControle(mac=mascarar(a.mac), transporte=a.transporte)
        sink_de_dentro = _nome_do_sink_de_dentro(a.mac)
        fonte_de_dentro = _nome_da_fonte_de_dentro(a.mac)
        placa = placas.get(a.hidraw)
        for s in sinks:
            nome = s.get("Name", "")
            if placa is not None and s.get("alsa.card") == placa.numero and nome.startswith("alsa_output"):
                no.sink_fisico = nome
            if _casa(nome, sink_de_dentro):
                no.alto_falante_virtual = nome
        for f in fontes:
            nome = f.get("Name", "")
            if placa is not None and f.get("alsa.card") == placa.numero and nome.startswith("alsa_input"):
                no.fonte_fisica = nome
            if _casa(nome, fonte_de_dentro):
                no.microfone_virtual = nome
        if no.alto_falante_virtual and any(no.alto_falante_virtual in m for m in modulos):
            no.fonte = "mix"
        if not no.alto_falante_virtual:
            no.faltas.append(_falta("saida", numero, sink_de_dentro))
        if not no.microfone_virtual:
            no.faltas.append(_falta("entrada", numero, fonte_de_dentro))
        if a.transporte == CABO and not no.sink_fisico:
            no.faltas.append("sem placa USB de saída (cabo de só-carga?)")
        resultado.append(no)
    return resultado


def tabela(nos: list[NoDoControle]) -> str:
    cab = f"{'controle':<20} {'transp.':<7} {'placa USB':<9} {'alto-falante virtual':<22} {'mic virtual':<22} fonte"
    linhas = [cab, "-" * len(cab)]
    for n in nos:
        linhas.append(
            f"{n.mac:<20} {n.transporte:<7} {'sim' if n.sink_fisico else '—':<9} "
            f"{(n.alto_falante_virtual or 'NÃO EXISTE')[:22]:<22} {(n.microfone_virtual or 'NÃO EXISTE')[:22]:<22} {n.fonte}"
        )
    return "\n".join(linhas)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--observar", type=float, default=0.0, help="segundos relendo a lista a cada 2 s")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    aparelhos = alvos_da_mesa()
    if not args.json:
        print(cabecalho_do_instrumento(
            "os_nos_de_som_por_controle",
            "cada controle tem o seu nó de saída e o seu de entrada na lista viva — e ele não some?",
            bibliotecas=["hefesto_dualsense4unix.integrations.alto_falante_bt"],
            escreve_no_aparelho=False))
        print(f"\nsaída padrão .... {pactl('get-default-sink').strip() or 'NÃO SEI'}")
        print(f"entrada padrão .. {pactl('get-default-source').strip() or 'NÃO SEI'}\n")

    nos = censo(aparelhos)
    if args.json:
        print(json.dumps([asdict(n) for n in nos], ensure_ascii=False, indent=1))
        return 0
    print(tabela(nos))
    faltas = [f"{n.mac}: {', '.join(n.faltas)}" for n in nos if n.faltas]

    if args.observar > 0:
        print(f"\nOBSERVANDO por {args.observar:g} s — tire o cabo de um, ou ligue o rádio, e olhe:")
        antes = {(n.mac, n.alto_falante_virtual, n.microfone_virtual, n.sink_fisico) for n in nos}
        fim = time.monotonic() + args.observar
        while time.monotonic() < fim:
            time.sleep(2.0)
            agora_nos = censo(alvos_da_mesa())
            agora = {(n.mac, n.alto_falante_virtual, n.microfone_virtual, n.sink_fisico) for n in agora_nos}
            for item in sorted(agora - antes):
                print(f"  {time.strftime('%H:%M:%S')}  APARECEU  {item}")
            for item in sorted(antes - agora):
                print(f"  {time.strftime('%H:%M:%S')}  SUMIU     {item}")
            antes = agora
        nos = censo(alvos_da_mesa())
        faltas = [f"{n.mac}: {', '.join(n.faltas)}" for n in nos if n.faltas]

    if not nos:
        print(resumo("nenhum DualSense físico na mesa — não há o que contar."))
        return 1
    if faltas:
        print(resumo("FALTA: " + " · ".join(faltas)))
        return 1
    print(resumo(f"os {len(nos)} controles têm nó de saída e de entrada na lista viva."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
