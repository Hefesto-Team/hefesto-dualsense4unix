#!/usr/bin/env python3
"""o_touchpad_chega_na_tela_de_baixo.py — o preço do `ignore`, medido no 3DS.

A PERGUNTA QUE ELE RESPONDE
----------------------------
*O touchpad do DualSense vira a tela de baixo do 3DS — com a cura que faz o
emulador sequer ABRIR no lugar?*

A tensão é real e as duas pontas foram medidas no mesmo dia, 10/09/2026:

    Ou o Azahar ABRE (sem o touchpad), ou ele VÊ o touchpad (e trava).
    A variável que cura o travamento é a mesma que apagaria o recurso.

Sem `SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6` o SDL abre o `hidraw` do
DualSense físico, a thread `HIDAPI Rumble` prende num futex e a janela nunca
nasce. Com a variável, o emulador lê o DualSense **virtual** que este produto
publica — e o virtual chega por `evdev`, onde touchpad de controle não existe
para a API de game controller do SDL.

«Provavelmente se perde» era a palavra da sprint, e «provavelmente» não é
medição. Este instrumento troca a palavra por número.

OS QUATRO DEGRAUS, e o instrumento fecha três
----------------------------------------------
0. **O recurso está LIGADO?** — o emulador tem, na própria interface, a opção
   *"Map touchpads on controllers like the DualSense directly to touch"*. Se
   ela estiver desligada, o dedo no touchpad não faz nada **por configuração**,
   e medir o resto sem dizer isso é montar a acusação errada. Lido do
   `qt-config.ini` do emulador, nunca da memória de ninguém.
1. **O nó EXISTE?** — o daemon publica um nó de touchpad por controle. Resolvido
   do sysfs a cada chamada.
2. **O emulador ABRE o nó, ou vê o aparelho por `hidraw`?** — lido de
   `/proc/<pid>/fd`, com cada descritor classificado por IDENTIDADE.
3. **O toque vira toque na tela de baixo?** — **só o olho dela fecha.** O
   instrumento imprime o gesto e se recusa a concluir.

O DEGRAU 2 NÃO PROVA O 3, e o instrumento nunca diz que prova. Descritor
fechado é evidência forte, não prova: o emulador poderia ler o toque por um
caminho que ninguém procurou.

AS ARMADILHAS QUE ELE FOI DESENHADO PARA NÃO REPETIR
-----------------------------------------------------
- **Número de nó não é endereço.** `event23` e `hidraw7` são posição na fila do
  kernel, e a fila anda: entre duas leituras com segundos de diferença um
  controle já sumiu e outro reapareceu com número diferente (medido em
  15/08/2026). Aqui todo descritor aberto é resolvido por identidade — quem é o
  aparelho, de quem ele é, por qual transporte fala — e o número aparece só
  como rótulo. **Um `hidraw` do vpad e um `hidraw` do físico dizem coisas
  opostas sobre o produto**, e distingui-los pelo número é sorteio.
- **Um ensaio que trava junto com o alvo nunca reprova.** O alvo desta medição
  é um processo cujo modo de falha É TRAVAR. Por isso `--abrir` tem teto de
  tempo e o travamento sai como RESULTADO — com a assinatura das threads — e
  não como espera para sempre.
- **A janela não nasce na tela dela.** Ela tem uma tela só. O `--abrir` desvia
  o emulador para o `Xvfb` da casa antes de o processo existir; a janela não
  tem para onde nascer na sessão viva.

O QUE ELE NUNCA FAZ
--------------------
Não escreve em aparelho nenhum, não chama `systemctl`, não toca em
configuração alheia (lê o `qt-config.ini`, nunca o edita), não usa `sudo`, e
mata só o processo que ele mesmo criou, **pelo PID**. O pior desfecho de um
erro aqui é um relatório errado.

Nenhum endereço de rádio sai daqui cru: toda linha impressa passa pela máscara
da casa. Uma máscara que se alimenta do que imprime não tem como ficar sem
agulha.

COMO USAR
----------
    # o que está aberto AGORA (o emulador já na tela, com a ROM carregada):
    o_touchpad_chega_na_tela_de_baixo.py

    # o instrumento abre o emulador sozinho, escondido, e mede:
    o_touchpad_chega_na_tela_de_baixo.py --abrir

    # a régua: rc=1 se o touchpad não chegou ao emulador
    o_touchpad_chega_na_tela_de_baixo.py --abrir --exigir-touchpad

    # A MORDIDA — arranca a cura e confirma que o instrumento ACUSA o
    # travamento em vez de travar junto:
    o_touchpad_chega_na_tela_de_baixo.py --abrir --sem-cura

O degrau 3 é dela, e o `--o-gesto` imprime o que ela tem de fazer.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_SCRIPTS = _AQUI.parent
_RAIZ = _SCRIPTS.parent
for _caminho in (str(_RAIZ / "src"), str(_SCRIPTS), str(_AQUI)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import identidade_do_vpad  # a régua única do vpad (VPAD-NO-ESPELHO-01)
from comum import (  # o chão dos instrumentos: um cabeçalho, uma tabela
    descobrir_aparelhos,
    cabecalho_do_instrumento,
    resumo,
    tabela,
)
from sanitizar_saida_de_agente import mascarar_enderecos  # a máscara da casa

#: O emulador desta medição, e o atalho dela — que é quem carrega a cura.
#: O `rodar.sh` lê o `default.env` VIVO a cada abertura, então ele nunca
#: digita a variável: ele pergunta ao daemon.
LANCADOR = Path.home() / "Lançadores" / "azahar" / "rodar.sh"

#: A configuração do emulador. É dela; este instrumento LÊ e nunca escreve.
CONFIG = Path(
    os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
) / "azahar-emu" / "qt-config.ini"

#: A opção da interface do emulador — *"Map touchpads on controllers like the
#: DualSense directly to touch"*, rotulada «Use controller touchpad» na tela.
#: O nome da chave sai do arquivo que o próprio emulador escreve.
CHAVE_DO_RECURSO = "use_touchpad"
CHAVE_DO_APARELHO_DE_TOQUE = "controller_touch_device"
CHAVE_DA_FONTE_DE_TOQUE = "touch_device"

#: O papel de cada nó, lido do sufixo que o `hid_playstation` dá ao nome. É o
#: mesmo sufixo no físico e no vpad, porque é o mesmo driver que os publica.
_PAPEIS = (
    (" Touchpad", "touchpad"),
    (" Motion Sensors", "movimento"),
    (" Headset Jack", "fone"),
)

#: O que faz um travamento ser ESTE travamento, e não um processo lento. A
#: assinatura foi medida em 10/09/2026 com `eu-stack`: a thread do rumble do
#: HIDAPI presa num futex, e a principal esperando por ela.
THREAD_DO_TRAVAMENTO = "HIDAPI Rumble"


def diga(texto: object = "") -> None:
    """Imprime com a máscara da casa aplicada — endereço e HOME."""
    print(mascarar_enderecos(str(texto), home=str(Path.home())))


# ---------------------------------------------------------------------------
# DEGRAU 0 — o recurso está ligado na configuração do emulador?
# ---------------------------------------------------------------------------


def _valores_do_ini(caminho: Path, chave: str) -> list[tuple[str, str]]:
    """Todos os `perfil\\chave=valor` do `.ini`, com o perfil ao lado.

    O emulador guarda um bloco por perfil de entrada (`profiles\\1\\...`), e
    ler só o primeiro esconderia um perfil ligado no segundo.
    """
    try:
        texto = caminho.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    achados: list[tuple[str, str]] = []
    padrao = re.compile(rf"^(.*?){re.escape(chave)}=(.*)$")
    for linha in texto.splitlines():
        if linha.endswith("\\default=true") or linha.endswith("\\default=false"):
            continue  # a linha-irmã que só diz "isto ainda é o padrão"
        casou = padrao.match(linha.strip())
        if casou:
            achados.append((casou.group(1).strip("\\") or "(sem perfil)",
                            casou.group(2).strip()))
    return achados


def degrau_zero() -> tuple[bool, list[str]]:
    """O recurso do touchpad está LIGADO? (ligado, linhas do relatório)."""
    linhas: list[str] = []
    if not CONFIG.is_file():
        linhas.append(f"  configuração ....... NÃO ACHEI em {CONFIG}")
        linhas.append("  o recurso está ..... NÃO SEI — sem o arquivo não há o que ler")
        return False, linhas

    linhas.append(f"  configuração ....... {CONFIG}")
    ligados = _valores_do_ini(CONFIG, CHAVE_DO_RECURSO)
    aparelhos = dict(_valores_do_ini(CONFIG, CHAVE_DO_APARELHO_DE_TOQUE))
    fontes = dict(_valores_do_ini(CONFIG, CHAVE_DA_FONTE_DE_TOQUE))

    if not ligados:
        linhas.append(
            f"  o recurso está ..... NÃO SEI — nenhuma chave `{CHAVE_DO_RECURSO}` "
            "no arquivo"
        )
        return False, linhas

    algum = False
    for perfil, valor in ligados:
        ligado = valor.strip().lower() == "true"
        algum = algum or ligado
        aparelho = aparelhos.get(perfil, "").strip() or "(vazio — nenhum controle atado)"
        fonte = fontes.get(perfil, "").strip() or "(vazio)"
        linhas.append(
            f"  {perfil:<12} {CHAVE_DO_RECURSO}={valor}"
            f"  {'<-- LIGADO' if ligado else '<-- DESLIGADO'}"
        )
        linhas.append(f"  {'':<12} {CHAVE_DO_APARELHO_DE_TOQUE}={aparelho}")
        linhas.append(f"  {'':<12} {CHAVE_DA_FONTE_DE_TOQUE}={fonte}")

    if not algum:
        linhas.append("")
        linhas.append(
            "  >> O RECURSO ESTÁ DESLIGADO NA CONFIGURAÇÃO. O dedo no touchpad "
            "não faria nada"
        )
        linhas.append(
            "  >> mesmo que o descritor estivesse aberto — e culpar o "
            "`IGNORE_DEVICES` por isso"
        )
        linhas.append("  >> seria acusar a coisa errada.")
    return algum, linhas


# ---------------------------------------------------------------------------
# DEGRAU 1 — os nós existem, e de quem é cada um
# ---------------------------------------------------------------------------


def _papel_do_nome(nome: str) -> str:
    for sufixo, papel in _PAPEIS:
        if nome.endswith(sufixo):
            return papel
    return "principal"


def nos_de_entrada() -> dict[str, dict[str, str]]:
    """`event27` -> quem ele é, resolvido AGORA do `/proc` e do sysfs.

    A fonte é `/proc/bus/input/devices`, que já traz o caminho de sysfs de cada
    nó (`S:`) — assim não há uma segunda busca em `/sys/class/input` que possa
    discordar da primeira entre uma leitura e outra.
    """
    fora: dict[str, dict[str, str]] = {}
    try:
        texto = Path("/proc/bus/input/devices").read_text(
            encoding="utf-8", errors="replace"
        )
    except OSError:
        return fora
    for bloco in texto.split("\n\n"):
        nome = re.search(r'N: Name="([^"]*)"', bloco)
        sysfs = re.search(r"S: Sysfs=(\S+)", bloco)
        uniq = re.search(r"U: Uniq=(\S*)", bloco)
        eventos = re.findall(r"(event\d+)", bloco)
        if not (nome and eventos):
            continue
        campos: dict[str, str] = {}
        if sysfs:
            campos = identidade_do_vpad.ler_uevent(
                f"/sys{sysfs.group(1)}/device/uevent"
            )
        e_vpad = identidade_do_vpad.e_vpad_do_hefesto(
            campos, uniq_do_no=uniq.group(1) if uniq else "", nome=nome.group(1)
        )
        hid_id = campos.get("HID_ID", "")
        barramento = hid_id.split(":")[0] if hid_id else ""
        if e_vpad:
            transporte = "vpad (sem transporte)"
        elif barramento == "0005":
            transporte = "rádio"
        elif barramento == "0003":
            transporte = "cabo"
        else:
            transporte = "?"
        for ev in eventos:
            fora[ev] = {
                "nome": nome.group(1),
                "papel": _papel_do_nome(nome.group(1)),
                "de_quem": "vpad do Hefesto" if e_vpad else "aparelho físico",
                "transporte": transporte,
                "mouse": ", ".join(re.findall(r"(mouse\d+)", bloco)) or "—",
            }
    return fora


def so_dualsense(nos: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """Os nós que são DualSense — vpad ou físico. O resto da máquina não é
    assunto desta medição, e listá-lo esconderia o que é."""
    return {
        ev: d
        for ev, d in nos.items()
        if "DualSense" in d["nome"] or d["de_quem"] == "vpad do Hefesto"
    }


# ---------------------------------------------------------------------------
# DEGRAU 2 — o que o emulador abriu, e por qual porta
# ---------------------------------------------------------------------------


def arvore_de(padrao: str, raiz: int | None = None) -> list[int]:
    """Todo processo cujo cmdline case com a expressão, MAIS os descendentes.

    Um AppImage roda dentro de um `mount` próprio e o binário de verdade é um
    filho: olhar só o processo cujo nome casa dá falso zero. Se `raiz` vier, a
    árvore é a DESSE processo — que é o caso do `--abrir`, em que o instrumento
    sabe exatamente quem criou.
    """
    alvos: set[int] = set()
    if raiz is not None:
        alvos.add(raiz)
    else:
        rx = re.compile(padrao, re.IGNORECASE)
        for p in Path("/proc").iterdir():
            if not p.name.isdigit():
                continue
            try:
                cmd = (p / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                    "utf-8", "replace"
                )
            except OSError:
                continue
            if rx.search(cmd):
                alvos.add(int(p.name))
    mudou = True
    while mudou:
        mudou = False
        for p in Path("/proc").iterdir():
            if not p.name.isdigit() or int(p.name) in alvos:
                continue
            try:
                st = (p / "stat").read_text(encoding="utf-8", errors="replace")
                ppid = int(st.rsplit(")", 1)[1].split()[1])
            except (OSError, IndexError, ValueError):
                continue
            if ppid in alvos:
                alvos.add(int(p.name))
                mudou = True
    return sorted(alvos)


def descritores(pids: list[int]) -> tuple[dict[str, list[int]], dict[str, list[int]]]:
    """Os `eventN` e os `hidrawN` abertos pela árvore, com quem os abriu."""
    eventos: dict[str, list[int]] = {}
    hidraws: dict[str, list[int]] = {}
    for pid in pids:
        try:
            for fd in (Path("/proc") / str(pid) / "fd").iterdir():
                try:
                    alvo = os.readlink(fd)
                except OSError:
                    continue
                casou = re.search(r"/dev/input/(event\d+)|/dev/(hidraw\d+)", alvo)
                if not casou:
                    continue
                nome = casou.group(1) or casou.group(2)
                destino = eventos if nome.startswith("event") else hidraws
                destino.setdefault(nome, []).append(pid)
        except OSError:
            continue
    return eventos, hidraws


def threads_travadas(pids: list[int]) -> list[tuple[int, str, str]]:
    """(tid, nome da thread, `wchan`) de cada thread da árvore.

    `wchan` é a função do kernel em que a thread está dormindo. É o que separa
    *"o processo está lento"* de *"o processo está preso num futex"* — e essa
    diferença é o diagnóstico inteiro deste ensaio.
    """
    fora: list[tuple[int, str, str]] = []
    for pid in pids:
        base = Path("/proc") / str(pid) / "task"
        try:
            tarefas = sorted(base.iterdir(), key=lambda p: int(p.name))
        except (OSError, ValueError):
            continue
        for tarefa in tarefas:
            try:
                comm = (tarefa / "comm").read_text(encoding="utf-8").strip()
                wchan = (tarefa / "wchan").read_text(encoding="utf-8").strip()
            except OSError:
                continue
            fora.append((int(tarefa.name), comm, wchan))
    return fora


def assinatura_do_futex(
    threads: list[tuple[int, str, str]]
) -> list[tuple[int, str, str]]:
    """As threads dormindo em futex — a corroboração do travamento.

    Em 10/09/2026 o `eu-stack` mostrou a thread `HIDAPI Rumble` presa num
    futex e a principal esperando por ela. Aqui a mesma coisa sai de
    `/proc/<tid>/wchan`, que é a função do kernel em que a thread dorme — e
    sem depender de o `eu-stack` existir na máquina.
    """
    return [t for t in threads if "futex" in t[2]]


#: Os quadros de pilha que decidem quem prende quem. Tudo o mais é ruído de
#: uma pilha de 41 threads, e ruído esconde a assinatura.
_QUADRO_QUE_IMPORTA = re.compile(
    r"hid|HID|SDL|sdl|udev|Rumble|Joystick|Controller|InputCommon"
)


def pilha_do_travamento(
    pids: list[int], *, segundos: float = 30.0
) -> tuple[str, list[str]]:
    """As pilhas das threads pelo `eu-stack` — o instrumento de 10/09/2026.

    O nome da thread não decide (thread sem nome herda o do processo), e o
    `wchan` diz onde ela dorme mas não quem a mandou dormir. A pilha diz.
    Devolve (motivo, quadros que importam) — motivo vazio quer dizer que a
    leitura foi feita.
    """
    if not pids:
        return "sem processo para olhar", []
    if not shutil.which("eu-stack"):
        return "`eu-stack` não existe nesta máquina — sem pilha", []
    escopo = ""
    try:
        escopo = Path("/proc/sys/kernel/yama/ptrace_scope").read_text(
            encoding="utf-8"
        ).strip()
    except OSError:
        escopo = ""
    try:
        saida = subprocess.run(
            ["eu-stack", "-p", str(pids[0])],
            capture_output=True, text=True, timeout=segundos, check=False,
        )
    except subprocess.TimeoutExpired:
        return f"`eu-stack` não respondeu em {segundos:.0f} s", []
    except OSError as erro:
        return f"`eu-stack` falhou: {erro}", []

    # O RETORNO DECIDE, NÃO A SAÍDA. Medido em 10/09/2026: com
    # `ptrace_scope=1` o `eu-stack` sai com rc=2 e AINDA IMPRIME duas linhas de
    # cabeçalho (`PID … - process`, `TID …:`). Aceitar a saída não vazia como
    # "leitura feita" fazia o instrumento anunciar *"pilha lida, e nenhum
    # quadro cita HID"* sobre uma pilha que ele nunca leu — e essa frase é uma
    # afirmação sobre o emulador, não sobre a recusa do kernel.
    if saida.returncode != 0:
        motivo = next(
            (linha.strip() for linha in (saida.stderr or "").splitlines()
             if "eu-stack:" in linha),
            "recusou sem dizer por quê",
        )
        if escopo and escopo != "0":
            motivo += (
                f" · kernel.yama.ptrace_scope={escopo}: só o processo PAI pode "
                "anexar, e este instrumento não eleva privilégio nenhum"
            )
        return f"NÃO LIDA — {motivo}", []

    linhas = saida.stdout.splitlines()
    com_simbolo = [
        linha for linha in linhas
        if re.search(r"0x[0-9a-f]+\s+[A-Za-z_][A-Za-z0-9_:.<>]{2,}", linha)
    ]
    if not com_simbolo:
        return (
            "lida, mas SEM SÍMBOLOS (o binário do emulador é `stripped`) — "
            "a pilha não nomeia quem prende quem"
        ), []
    quadros = [
        linha.strip() for linha in com_simbolo
        if _QUADRO_QUE_IMPORTA.search(linha)
    ]
    if not quadros:
        return (
            f"lida, {len(com_simbolo)} quadros com símbolo, e NENHUM cita "
            "HID, SDL ou udev"
        ), []
    return "", quadros[:12]


#: Menor que isto é janela de serviço do Qt (dono de seleção, tela de ícone),
#: não a janela do emulador. Medido: com a cura, a do emulador saiu 933x855; o
#: travamento deixa só uma de 3x3 na tela.
JANELA_DE_VERDADE = 200


def janelas(display: str | None) -> list[dict[str, object]]:
    """As janelas na tela `display`, com título e geometria.

    A janela é o sintoma que ELA vê: em 10/09 o Qt subia inteiro e a janela
    nunca nascia. Medir só o descritor deixaria esse sintoma de fora — e
    CONTAR janelas também deixaria, porque o processo travado ainda cria as
    janelinhas de serviço do Qt. O que separa uma coisa da outra é o tamanho.
    """
    if not display:
        return []
    try:
        saida = subprocess.run(
            ["xwininfo", "-root", "-tree", "-display", display],
            capture_output=True, text=True, timeout=10, check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    fora: list[dict[str, object]] = []
    for linha in saida.splitlines():
        casou = re.search(r'^\s+(0x[0-9a-f]+) ("[^"]*"|\(has no name\)).*?'
                          r"(\d+)x(\d+)\+", linha)
        if not casou:
            continue
        fora.append({
            "titulo": casou.group(2).strip('"'),
            "largura": int(casou.group(3)),
            "altura": int(casou.group(4)),
            "linha": linha.strip(),
        })
    return fora


def nasceu_janela(lista: list[dict[str, object]]) -> bool:
    """Alguma janela DE VERDADE nasceu?"""
    return any(
        int(j["largura"]) >= JANELA_DE_VERDADE
        and int(j["altura"]) >= JANELA_DE_VERDADE
        for j in lista
    )


# ---------------------------------------------------------------------------
# O `--abrir`: sobe o emulador escondido, com teto de tempo, e mata pelo PID
# ---------------------------------------------------------------------------


def alvo_sem_cura(lancador: Path) -> Path | None:
    """O executável CRU ao lado do atalho, para a mordida.

    A mordida do §5 exige rodar SEM a cura, e o atalho existe justamente para
    aplicá-la: ele lê o `default.env` vivo e exporta a variável. Rodar o atalho
    e chamar isso de «sem cura» seria a mordida que não morde — então quando o
    cru não é achado, o instrumento RECUSA em vez de medir outra coisa.
    """
    for candidato in sorted(lancador.parent.glob("*.AppImage")):
        if os.access(candidato, os.X_OK):
            return candidato
    return None


def abrir_o_emulador(
    lancador: Path, *, sem_cura: bool, segundos: float
) -> tuple[subprocess.Popen[bytes] | None, str | None, str]:
    """Sobe o emulador na tela de mentira. Devolve (processo, display, aviso)."""
    from hefesto_dualsense4unix.utils.tela_de_mentira import (
        garantir_tela_de_mentira,
    )

    display = garantir_tela_de_mentira()
    ambiente = dict(os.environ)
    comando = [str(lancador)]
    aviso = ""
    if sem_cura:
        cru = alvo_sem_cura(lancador)
        if cru is None:
            return None, display, (
                "RECUSADO: a mordida pede o executável CRU (sem o atalho que "
                f"aplica a cura) e não há nenhum `.AppImage` em {lancador.parent}. "
                "Rodar o atalho e chamar de «sem cura» seria mordida falsa."
            )
        comando = [str(cru)]
        ambiente.pop("SDL_GAMECONTROLLER_IGNORE_DEVICES", None)
        ambiente.pop("PROTON_DISABLE_HIDRAW", None)
        aviso = f"MORDIDA: {cru.name} SEM `SDL_GAMECONTROLLER_IGNORE_DEVICES`"

    proc = subprocess.Popen(
        comando,
        env=ambiente,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # grupo próprio: o que ele criar, ele mata
    )
    # Espera o processo mostrar o que veio mostrar. Sai antes do teto quando
    # já há janela E descritor de entrada: o que vier depois não muda a
    # resposta, e o teto é rede, não relógio de espera.
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        time.sleep(0.5)
        pids = arvore_de("", raiz=proc.pid)
        eventos, _ = descritores(pids)
        if eventos and nasceu_janela(janelas(display)):
            break
        if proc.poll() is not None:
            break
    return proc, display, aviso


def matar(proc: subprocess.Popen[bytes] | None) -> str:
    """Mata o que ESTE instrumento criou, pelo PID, e nada mais.

    Nunca por padrão de linha de comando: um `pkill -f` já derrubou o
    compositor dela em 04/09/2026.
    """
    if proc is None or proc.poll() is not None:
        return "nada a matar"
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (OSError, ProcessLookupError):
        proc.terminate()
    try:
        proc.wait(timeout=8)
        return f"encerrado (PID {proc.pid}, SIGTERM)"
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (OSError, ProcessLookupError):
        proc.kill()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        return f"NÃO MORREU (PID {proc.pid}) — confira à mão"
    return f"encerrado (PID {proc.pid}, SIGKILL — não respondeu ao SIGTERM)"


# ---------------------------------------------------------------------------
# O gesto do degrau 3 — o que só o olho dela fecha
# ---------------------------------------------------------------------------

O_GESTO = """\
O DEGRAU 3 É DELA, e é este o gesto:

  1. Abra o emulador pelo atalho e carregue a ROM (a ROM é dela; este
     instrumento não baixa nem procura nenhuma).
  2. Com o jogo RODANDO, arraste o dedo no touchpad do controle.
     A pergunta é uma só: A TELA DE BAIXO DO 3DS RESPONDEU?
  3. No mesmo instante, com o jogo ainda aberto, rode este instrumento sem
     bandeira nenhuma — o descritor conta a verdade antes do olho.

  UM GESTO POR VEZ. Gesto composto num ensaio produz AUSÊNCIA FALSA: em
  16/08/2026 pediu-se "gire o controle E passe o dedo" ao mesmo tempo, o
  touchpad saiu 0 de 8 bytes variando, e por pouco não se escreveu que o
  produto não preenchia os pontos de toque.
"""


# ---------------------------------------------------------------------------


def medir(padrao: str, *, raiz: int | None, display: str | None) -> dict:
    """O retrato do degrau 2, agora."""
    pids = arvore_de(padrao, raiz=raiz)
    eventos, hidraws = descritores(pids)
    nos = nos_de_entrada()
    aparelhos = {a.hidraw: a for a in descobrir_aparelhos()}
    return {
        "pids": pids,
        "eventos": eventos,
        "hidraws": hidraws,
        "nos": nos,
        "aparelhos": aparelhos,
        "threads": threads_travadas(pids),
        "janelas": janelas(display) if display else None,
    }


def imprimir_degrau_dois(r: dict) -> tuple[bool, bool | None]:
    """Imprime o degrau 2. Devolve (o touchpad chegou?, a janela nasceu?).

    O segundo vem `None` quando a pergunta da janela não foi feita — e ela só
    se faz na tela que ESTE instrumento criou. Perguntar na sessão viva
    listaria as janelas dela, que não são assunto de medição nenhuma aqui.
    """
    diga(f"  processos na árvore ....... {len(r['pids'])}")
    if not r["pids"]:
        diga("  (nada a medir — nenhum processo casou com o padrão)")
        return False, None

    if r["janelas"] is None:
        diga("  janelas na tela ........... NÃO PERGUNTEI — a tela é dela, e "
             "listá-la não é medição")
        nasceu = None
    else:
        nasceu = nasceu_janela(r["janelas"])
    if nasceu is not None:
        diga(f"  janelas na tela ........... {len(r['janelas'])}"
             f"  ·  janela de verdade? {'SIM' if nasceu else 'NÃO'}")
        for janela in r["janelas"][:6]:
            diga(f"      {janela['linha']}")

    if nasceu is False:
        futex = assinatura_do_futex(r["threads"])
        diga("")
        diga("  >> TRAVOU — a janela do emulador NUNCA NASCEU dentro do teto.")
        diga("  >> É o sintoma que ela vê: o Qt sobe inteiro e o processo dorme.")
        if futex:
            # Uma pilha de threads de `llvmpipe` dormindo em futex é pool
            # ocioso, não travamento — e enterraria a assinatura no meio do
            # ruído. Sobem primeiro as que decidem: a principal e as do SDL.
            def _peso(t: tuple[int, str, str]) -> tuple[int, int]:
                marcada = t[1].startswith(THREAD_DO_TRAVAMENTO[:15])
                principal = t[0] in r["pids"]
                return (0 if marcada else 1 if principal else 2, t[0])

            escolhidas = sorted(futex, key=_peso)
            diga(f"  >> {len(futex)} thread(s) dormindo em futex, as que decidem "
                 "primeiro:")
            for tid, comm, wchan in escolhidas[:8]:
                if comm.startswith(THREAD_DO_TRAVAMENTO[:15]):
                    marca = "  <-- a thread do rumble do HIDAPI"
                elif tid in r["pids"]:
                    marca = "  <-- a PRINCIPAL, esperando por outra"
                else:
                    marca = ""
                diga(f"      tid={tid:<8} {comm:<20} {wchan}{marca}")
            if len(escolhidas) > 8:
                diga(f"      (+{len(escolhidas) - 8} threads, o pool ocioso do "
                     "renderizador)")
            if not any(t[1].startswith(THREAD_DO_TRAVAMENTO[:15])
                       for t in futex):
                diga(f"      nenhuma thread chamada `{THREAD_DO_TRAVAMENTO}` "
                     "na lista — e o NOME não decide:")
                diga("      thread sem nome herda o do processo, e é por isso "
                     "que a pilha vem abaixo.")
        else:
            diga("  >> nenhuma thread em futex — o travamento é de outra "
                 "família que a de 10/09.")
        nomes: dict[str, int] = {}
        for _tid, comm, _wchan in r["threads"]:
            nomes[comm] = nomes.get(comm, 0) + 1
        censo = ", ".join(
            f"{n}×{c}" if c > 1 else n
            for n, c in sorted(nomes.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
        )
        diga(f"  >> threads da árvore ({len(r['threads'])}): {censo}")
        herdadas = sum(1 for _t, comm, _w in r["threads"]
                       if comm == r["threads"][0][1]) if r["threads"] else 0
        if herdadas > 1:
            diga(f"  >> {herdadas} delas têm o nome do PROCESSO — são threads "
                 "sem nome próprio, e")
            diga("  >> nelas o censo por nome não responde nada. Quem responde "
                 "é a pilha:")
        motivo, quadros = pilha_do_travamento(r["pids"])
        if motivo:
            diga(f"  >> pilha .................. {motivo}")
        for quadro in quadros:
            diga(f"      {quadro}")
        diga("  >> É RESULTADO, não falha do ensaio: um emulador que não abre")
        diga("  >> não tem recurso de touchpad na prática.")

    linhas = []
    achou_touchpad = False
    for ev in sorted(r["eventos"], key=lambda e: int(e.removeprefix("event"))):
        d = r["nos"].get(ev, {})
        papel = d.get("papel", "?")
        if papel == "touchpad":
            achou_touchpad = True
        linhas.append([
            ev, papel, d.get("de_quem", "?"), d.get("transporte", "?"),
            d.get("nome", "?"),
        ])
    diga("")
    diga("  NÓS DE ENTRADA ABERTOS pelo emulador:")
    if linhas:
        for linha in tabela(
            ["nó", "papel", "de quem", "transporte", "nome"], linhas
        ).splitlines():
            diga(f"      {linha}")
    else:
        diga("      NENHUM — o emulador não abriu dispositivo de entrada algum")

    linhas = []
    for hr in sorted(r["hidraws"], key=lambda h: int(h.removeprefix("hidraw"))):
        a = r["aparelhos"].get(hr)
        if a is None:
            linhas.append([hr, "não é DualSense", "—", "—"])
            continue
        linhas.append([
            hr,
            "vpad do Hefesto" if a.e_vpad else "aparelho físico",
            a.transporte,
            a.nome,
        ])
    diga("")
    diga("  HIDRAW ABERTOS pelo emulador:")
    if linhas:
        for linha in tabela(
            ["nó", "de quem", "transporte", "nome"], linhas
        ).splitlines():
            diga(f"      {linha}")
    else:
        diga("      NENHUM — o SDL não está falando HID com aparelho nenhum")
        diga("      (é por aqui que a API de touchpad do SDL seria alimentada)")
    return achou_touchpad, nasceu


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--padrao", default="azahar",
                    help="regex do cmdline do emulador (padrão: azahar)")
    ap.add_argument("--lancador", type=Path, default=LANCADOR,
                    help="o atalho que carrega a cura")
    ap.add_argument("--abrir", action="store_true",
                    help="sobe o emulador escondido, mede e o mata pelo PID")
    ap.add_argument("--sem-cura", action="store_true",
                    help="A MORDIDA: roda o executável cru, sem o IGNORE_DEVICES")
    ap.add_argument("--segundos", type=float, default=30.0,
                    help="teto do --abrir; o travamento sai como resultado")
    ap.add_argument("--exigir-touchpad", action="store_true",
                    help="rc=1 se o nó de touchpad não chegou ao emulador")
    ap.add_argument("--o-gesto", action="store_true",
                    help="imprime o gesto do degrau 3 e para")
    args = ap.parse_args()

    if args.o_gesto:
        diga(O_GESTO)
        return 0

    diga(cabecalho_do_instrumento(
        "o touchpad chega na tela de baixo?",
        "o touchpad do DualSense vira a tela de baixo do 3DS?",
        bibliotecas=["identidade_do_vpad", "hefesto_dualsense4unix"],
        escreve_no_aparelho=False,
        daemon_precisa_parar=False,
    ))

    diga("")
    diga("DEGRAU 0 — o recurso está LIGADO na configuração do emulador?")
    recurso_ligado, linhas = degrau_zero()
    for linha in linhas:
        diga(linha)

    diga("")
    diga("DEGRAU 1 — o nó de touchpad EXISTE?")
    nos = so_dualsense(nos_de_entrada())
    linhas_um = [
        [ev, d["papel"], d["de_quem"], d["transporte"], d["mouse"]]
        for ev, d in sorted(nos.items(), key=lambda kv: int(kv[0].removeprefix("event")))
    ]
    for linha in tabela(
        ["nó", "papel", "de quem", "transporte", "ponteiro"], linhas_um
    ).splitlines():
        diga(f"  {linha}")
    touchpads = sorted(
        (ev for ev, d in nos.items() if d["papel"] == "touchpad"),
        key=lambda e: int(e.removeprefix("event")),
    )
    diga("")
    diga(f"  nós de touchpad na mesa ... {len(touchpads)}"
         + (f" ({', '.join(touchpads)})" if touchpads else " — NENHUM"))

    proc: subprocess.Popen[bytes] | None = None
    #: A tela só se pergunta quando é a que ESTE instrumento criou. A sessão
    #: viva é a dela, e listar as janelas dela não mede nada.
    display: str | None = None
    raiz: int | None = None
    if args.abrir:
        if not args.lancador.exists():
            diga("")
            diga(f"  RECUSADO: não achei o atalho {args.lancador}")
            return 1
        diga("")
        diga(f"DEGRAU 2 — abrindo o emulador (teto de {args.segundos:.0f} s)")
        proc, display, aviso = abrir_o_emulador(
            args.lancador, sem_cura=args.sem_cura, segundos=args.segundos
        )
        if proc is None:
            diga(f"  {aviso}")
            return 1
        if aviso:
            diga(f"  {aviso}")
        diga(f"  PID {proc.pid} · tela {display or '(a sessão viva)'}")
        raiz = proc.pid
    else:
        diga("")
        diga("DEGRAU 2 — o emulador ABRE o nó?")

    r: dict = {"pids": [], "hidraws": {}}
    chegou = False
    nasceu: bool | None = None
    try:
        r = medir(args.padrao, raiz=raiz, display=display)
        chegou, nasceu = imprimir_degrau_dois(r)
    finally:
        if proc is not None:
            diga("")
            diga(f"  encerramento .............. {matar(proc)}")

    diga("")
    diga("DEGRAU 3 — o toque vira toque na tela de baixo?")
    diga("  NÃO MEDIDO por este instrumento, e ele não vai fingir que mediu.")
    diga("  Descritor fechado é evidência forte, não prova: o emulador poderia")
    diga("  ler o toque por um caminho que ninguém procurou. Quem fecha é o")
    diga("  dedo dela no touchpad, com a ROM carregada. Veja `--o-gesto`.")

    if not r["pids"]:
        diga(resumo(
            "NADA MEDIDO no degrau 2 — nenhum processo do emulador estava "
            "aberto. Abra-o, ou use `--abrir`."
        ))
        return 1 if args.exigir_touchpad else 0

    if nasceu is False:
        veredito = (
            "o emulador NEM ABRIU — a janela não nasceu dentro do teto. O "
            "recurso de touchpad não existe na prática quando isto acontece"
        )
    elif chegou:
        veredito = "o nó de TOUCHPAD chegou ao emulador"
    elif r["hidraws"]:
        veredito = (
            "o touchpad NÃO chegou por evdev, mas o emulador tem `hidraw` "
            "aberto — é por ali que a API de touchpad do SDL seria alimentada"
        )
    else:
        veredito = (
            "o touchpad NÃO chegou ao emulador: nem nó de touchpad, nem "
            "`hidraw` nenhum"
        )
    if not recurso_ligado:
        veredito += " · E O RECURSO ESTÁ DESLIGADO NA CONFIGURAÇÃO (degrau 0)"
    diga(resumo(veredito))

    if args.exigir_touchpad and not chegou:
        diga("`--exigir-touchpad`: o degrau 2 está VERMELHO. rc=1.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
