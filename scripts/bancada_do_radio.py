#!/usr/bin/env python3
"""bancada_do_radio.py — o CONDUTOR da sentada do rádio, 19/09/2026.

A ENCOMENDA É DELA: *"Prepara todos os testes, deixa tudo pronto (…) pra em
uma sentada eu conseguir fazer todos os testes sem perdermos muito tempo. Pra
vc ir conduzindo tudo em software e eu ir executando as etapas do mundo físico
e te reportando"*.

POR QUE SUBCOMANDOS, E NÃO UM ASSISTENTE QUE ELA PILOTA
--------------------------------------------------------
A `a_folha_dos_ensaios` é uma folha que **ela** dirige, com deslizantes. Aqui é
o contrário: **eu** disparo cada etapa na conversa, ela faz o gesto físico e me
reporta. Um assistente interativo a obrigaria a ler prompt no terminal enquanto
tem o controle na mão — que é o que esta sentada existe para evitar.

Então cada etapa é um subcomando que roda, mede e volta. Sem `input()`.

O INSTRUMENTO DO DANO, e ele é medido
--------------------------------------
`poll.tick` do daemon, por `daemon.state_full`. Medido em 19/09 com a máquina
dela em uso, três janelas de 2 s: **57,24 · 57,42 · 57,42 tiques/s** — 0,3% de
variação. Qualquer queda que a varredura cause aparece contra esse piso.

É o instrumento certo porque mede o PRODUTO, não o rádio em abstrato: o que
importa não é quantos pacotes o adaptador perdeu, é se o daemon parou de ver o
controle.

O CADERNO É O DA CASA
----------------------
`docs/data/ensaios.csv`, versionado, mesmas colunas. A bancada não inventa
formato: uma medição que mora em arquivo próprio não é lida por ninguém.

USO::

    python3 scripts/bancada_do_radio.py estado        # a fotografia de partida
    python3 scripts/bancada_do_radio.py taxa 6        # a taxa de tique, N segundos
    python3 scripts/bancada_do_radio.py dano hci0     # liga scan e mede — devolve
    python3 scripts/bancada_do_radio.py bonds         # os bonds dobrados + o gesto
    python3 scripts/bancada_do_radio.py limpar hci0 44:46:48:00:00:03
    python3 scripts/bancada_do_radio.py controles     # quem está de pé, onde
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))


# ── as peças mínimas, sem depender da interface ──────────────────────────────
def _busctl(*args: str) -> str:
    fim = subprocess.run(
        ["busctl", "--system", *args], capture_output=True, text=True, check=False
    )
    return fim.stdout.strip()


def _adaptadores() -> list[str]:
    saida = _busctl("tree", "org.bluez")
    achados = []
    for linha in saida.splitlines():
        pedaco = linha.strip().lstrip("├└─│ ")
        if pedaco.startswith("/org/bluez/hci") and pedaco.count("/") == 3:
            achados.append(pedaco.rsplit("/", 1)[-1])
    return sorted(set(achados))


def _prop(caminho: str, interface: str, nome: str) -> str:
    cru = _busctl("get-property", "org.bluez", caminho, interface, nome)
    if not cru:
        return ""
    return cru.split(" ", 1)[-1].strip().strip('"')


def _devices() -> list[tuple[str, str]]:
    """[(hciN, MAC)] de todo device sob o BlueZ."""
    saida = _busctl("tree", "org.bluez")
    fora = []
    for linha in saida.splitlines():
        pedaco = linha.strip().lstrip("├└─│ ")
        if "/dev_" not in pedaco:
            continue
        hci = pedaco.split("/org/bluez/", 1)[-1].split("/", 1)[0]
        mac = pedaco.rsplit("/dev_", 1)[-1].replace("_", ":")
        if len(mac) == 17:
            fora.append((hci, mac))
    return sorted(set(fora))


def _tiques() -> int:
    from hefesto_dualsense4unix.cli.cmd_tray import _chamar

    r = _chamar("daemon.state_full") or {}
    return int((r.get("counters") or {}).get("poll.tick", 0))


def _evdev_de_movimento() -> str | None:
    """O nó de MOVIMENTO do DualSense — o fio que a varredura pode estreitar.

    POR QUE O `poll.tick` DO DAEMON NÃO SERVE, e isto foi medido em 19/09: a
    taxa dele é a MESMA com o controle no rádio (54,8/s) e no cabo (57,4/s).
    Ele conta as voltas do laço do daemon, que rodam pelo relógio — não os
    pacotes que chegam do controle. Um instrumento assim responde sobre o
    daemon, nunca sobre o rádio, e daria «sem dano» em qualquer cenário.

    POR QUE O NÓ DE MOVIMENTO, e não o dos botões: a IMU publica ~514
    pacotes/s com o controle PARADO em cima da mesa — o ruído do giroscópio
    basta. O nó dos botões fica em 0/s enquanto ninguém aperta nada, e mediria
    o silêncio.
    """
    candidatos = []
    for no in sorted(Path("/dev/input").glob("event*")):
        nome_f = Path(f"/sys/class/input/{no.name}/device/name")
        try:
            nome = nome_f.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if "DualSense" in nome and "Motion Sensors" in nome:
            candidatos.append(str(no))
    if not candidatos:
        return None
    # O maior número é o mais recente — e o do RÁDIO costuma nascer depois do
    # nó do cabo, que fica no disco desde o boot.
    return sorted(candidatos, key=lambda c: int(c.rsplit("event", 1)[-1]))[-1]


def _taxa_no_fio(caminho: str, segundos: float) -> float:
    """Pacotes por segundo que o controle entrega, contados no evdev."""
    import select
    import struct

    try:
        fd = os.open(caminho, os.O_RDONLY | os.O_NONBLOCK)
    except OSError:
        return -1.0
    n = 0
    t0 = time.monotonic()
    try:
        while time.monotonic() - t0 < segundos:
            pronto, _, _ = select.select([fd], [], [], 0.2)
            if not pronto:
                continue
            try:
                dados = os.read(fd, 24 * 256)
            except BlockingIOError:
                continue
            for i in range(0, len(dados) - 23, 24):
                tipo = struct.unpack("qqHHi", dados[i:i + 24])[2]
                if tipo == 0:  # EV_SYN — um pacote completo
                    n += 1
    finally:
        os.close(fd)
    dt = time.monotonic() - t0
    return n / dt if dt else 0.0


def _mascarar(mac: str) -> str:
    """A máscara da casa: octetos 4 e 5 zerados. Nada de MAC real em arquivo."""
    p = mac.split(":")
    if len(p) != 6:
        return mac
    return ":".join([p[0], p[1], p[2], "00", "00", p[5]])


# ── as etapas ────────────────────────────────────────────────────────────────
def etapa_estado() -> int:
    print("\n  ESTADO DE PARTIDA\n  " + "─" * 58)
    adps = _adaptadores()
    if not adps:
        print("  nenhum adaptador Bluetooth — não há bancada de rádio a fazer.")
        return 1
    print(f"\n  ADAPTADORES ({len(adps)})")
    for h in adps:
        caminho = f"/org/bluez/{h}"
        alias = _prop(caminho, "org.bluez.Adapter1", "Alias")
        lig = _prop(caminho, "org.bluez.Adapter1", "Powered")
        var = _prop(caminho, "org.bluez.Adapter1", "Discovering")
        quantos = len([1 for hci, _ in _devices() if hci == h])
        print(f"    {h}  {alias:26} ligado={lig:5} varrendo={var:5} bonds={quantos}")

    print("\n  CONTROLES CONECTADOS")
    vivos = 0
    for hci, mac in _devices():
        if _prop(f"/org/bluez/{hci}/dev_{mac.replace(':', '_')}",
                 "org.bluez.Device1", "Connected") == "true":
            vivos += 1
            print(f"    {_mascarar(mac)}  no {hci}")
    if not vivos:
        print("    nenhum no rádio (pode haver controle no CABO — ver abaixo)")

    try:
        tique = _tiques()
        print(f"\n  DAEMON  poll.tick = {tique}")
    except Exception as erro:
        print(f"\n  DAEMON  não respondeu ({erro.__class__.__name__}) — sem medida de dano")
    print("  " + "─" * 58 + "\n")
    return 0


def etapa_taxa(segundos: float = 6.0) -> int:
    """A taxa de tique do daemon — o piso contra o qual o dano se mede."""
    try:
        t0 = time.monotonic()
        p0 = _tiques()
        time.sleep(segundos)
        p1 = _tiques()
    except Exception as erro:
        print(f"  o daemon não respondeu ({erro.__class__.__name__}).")
        return 1
    dt = time.monotonic() - t0
    taxa = (p1 - p0) / dt if dt else 0.0
    print(f"  {taxa:7.2f} tiques/s   ({p1 - p0} em {dt:.2f}s)")
    return 0


def etapa_dano(alvo: str, segundos: float = 8.0, cruzado: bool = False) -> int:
    """Liga a varredura em `alvo`, mede a taxa DURANTE, e desliga.

    O `busctl call StartDiscovery` não serve: o BlueZ mata a busca quando o
    cliente que pediu fecha a conexão — medido em 19/09. Por isso aqui a busca
    corre num `bluetoothctl` VIVO, e este processo o mantém de pé.
    """
    # O RÁDIO DELA NÃO É BANCADA DE SUÍTE — RADIO-DELA-01, 19/09/2026.
    #
    # Esta etapa LIGA a varredura num adaptador vivo. A primeira régua escrita
    # para ela chamava-a de verdade, e o canário do `casa-sabe` acusou na
    # mesma corrida: o daemon reagiu e regravou `~/.config/.../controllers.json`
    # na máquina dela, com ela usando a máquina.
    #
    # É a TELA-DELA-01 com outro aparelho: *a suíte não toca o que é dela*. O
    # escape é declarado, e quem o declara assume a responsabilidade.
    if os.environ.get("PYTEST_CURRENT_TEST") and \
            os.environ.get("HEFESTO_BANCADA_PODE_TOCAR_O_RADIO") != "1":
        print("\n  RECUSADO: esta etapa LIGA a varredura num adaptador vivo, e")
        print("  quem a chamou está dentro da suíte. O rádio dela não é bancada")
        print("  de teste — o daemon reage e regrava o estado na máquina dela.")
        print("  Escape declarado: HEFESTO_BANCADA_PODE_TOCAR_O_RADIO=1\n")
        return 7

    if alvo not in _adaptadores():
        print(f"  {alvo} não existe. Há: {', '.join(_adaptadores())}")
        return 2
    endereco = _prop(f"/org/bluez/{alvo}", "org.bluez.Adapter1", "Address")

    # ZERO COM O ALVO FORA DA MESA NÃO É ZERO. Sem controle CONECTADO neste
    # adaptador, a varredura não tem o que atrapalhar, e a medição devolve
    # «sem dano» — que se lê como «a busca não atrapalha». É a armadilha que
    # esta casa já pagou, e ela custa uma conclusão inteira: quem ler o número
    # arquiva o assunto.
    no_alvo = [
        mac
        for hci, mac in _devices()
        if hci == alvo
        and _prop(f"/org/bluez/{hci}/dev_{mac.replace(':', '_')}",
                  "org.bluez.Device1", "Connected") == "true"
    ]
    outros = sorted({
        hci
        for hci, mac in _devices()
        if hci != alvo
        and _prop(f"/org/bluez/{hci}/dev_{mac.replace(':', '_')}",
                  "org.bluez.Device1", "Connected") == "true"
    })

    if not no_alvo and not cruzado:
        print(f"\n  NENHUM CONTROLE CONECTADO EM {alvo}.")
        print("  A varredura não teria o que atrapalhar, e a medição diria")
        print("  «sem dano» sobre uma mesa vazia. Conecte um DualSense por")
        print("  RÁDIO neste adaptador e chame de novo.\n")
        if outros:
            print(f"  (há controle conectado em: {', '.join(outros)})")
            print("  Para a medição CRUZADA — varrer AQUI e ver se o controle")
            print(f"  de LÁ sofre — chame:  dano {alvo} {segundos:.0f} --cruzado\n")
        return 4

    if not no_alvo:
        # A MEDIÇÃO CRUZADA, e ela é a que DECIDE A RESERVA — 19/09/2026.
        #
        # A guarda acima recusa medir sobre mesa vazia, e está certa para o
        # dano DIRETO. Mas a pergunta da reserva é outra: *varrer no adaptador
        # A atrapalha o controle que está no B?* Se atrapalhar, pôr os
        # controles nos dongles não adianta — a interferência seria de
        # espectro, e o espectro é um só.
        #
        # Recusar esta medição por falta de controle NO ALVO seria a guarda
        # cega justamente para a pergunta que ela existe para proteger.
        if not outros:
            print(f"\n  nem em {alvo} nem em outro adaptador há controle no rádio.")
            print("  A medição cruzada precisa de um controle EM ALGUM lugar.\n")
            return 4
        print(f"\n  MEDIÇÃO CRUZADA: varrendo em {alvo}, medindo o controle de "
              + ", ".join(outros))
    else:
        print(f"\n  {len(no_alvo)} controle(s) no rádio de {alvo}: "
              + ", ".join(_mascarar(m) for m in no_alvo))

    fio = _evdev_de_movimento()
    if not fio:
        print("\n  não achei o nó de MOVIMENTO de nenhum DualSense.")
        print("  Sem ele não há o que medir: é o fio em que os pacotes chegam.\n")
        return 8

    print(f"\n  DANO DA VARREDURA em {alvo} ({_mascarar(endereco)})")
    print(f"  instrumento: {fio} (pacotes do controle, não tiques do daemon)")
    print("  " + "─" * 58)
    print("  1. piso, sem varredura:")
    antes = _taxa_no_fio(fio, segundos)
    if antes <= 0:
        print(f"       {antes:7.1f} pacotes/s — sem leitura. Abortado.")
        return 8
    print(f"       {antes:7.1f} pacotes/s")

    proc = subprocess.Popen(
        ["bluetoothctl"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        assert proc.stdin is not None
        proc.stdin.write(f"select {endereco}\n")
        proc.stdin.flush()
        time.sleep(1.0)
        proc.stdin.write("scan on\n")
        proc.stdin.flush()
        time.sleep(2.5)
        varrendo = _prop(f"/org/bluez/{alvo}", "org.bluez.Adapter1", "Discovering")
        if varrendo != "true":
            print(f"  a varredura NÃO subiu em {alvo} (Discovering={varrendo}) — nada medido")
            return 3
        print("  2. com a varredura de pé:")
        durante = _taxa_no_fio(fio, segundos)
        print(f"       {durante:7.1f} pacotes/s")
    finally:
        # A BUSCA MORRE COM O CLIENTE, e é disso que dependemos para não deixar
        # o rádio dela varrendo se este processo cair.
        try:
            assert proc.stdin is not None
            proc.stdin.write("scan off\nquit\n")
            proc.stdin.flush()
        except (BrokenPipeError, AssertionError):
            pass
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        time.sleep(1.5)

    sobrou = _prop(f"/org/bluez/{alvo}", "org.bluez.Adapter1", "Discovering")
    queda = (antes - durante) / antes * 100 if antes else 0.0
    print(f"\n  QUEDA: {queda:5.1f}%   (rádio depois: Discovering={sobrou})")
    if queda < 2:
        print("  → a varredura NÃO alcançou o daemon nesta medição.")
    elif queda < 15:
        print("  → queda pequena, mas real. Meça de novo para separar do ruído.")
    else:
        print("  → DANO CLARO. A varredura rouba banda do controle neste adaptador.")
    print("  " + "─" * 58 + "\n")
    return 0


def etapa_bonds() -> int:
    """Os bonds dobrados, e o gesto de limpar cada um."""
    onde: dict[str, list[str]] = {}
    for hci, mac in _devices():
        onde.setdefault(mac, []).append(hci)
    dobrados = {m: hs for m, hs in onde.items() if len(hs) > 1}

    print("\n  BONDS POR CONTROLE\n  " + "─" * 58)
    for mac, hcis in sorted(onde.items()):
        marca = "  <<< DOBRADO" if len(hcis) > 1 else ""
        print(f"    {_mascarar(mac)}  {' '.join(sorted(hcis))}{marca}")
    if not dobrados:
        print("\n  nenhum dobrado — nada a limpar.")
        print("  " + "─" * 58 + "\n")
        return 0

    print(f"\n  {len(dobrados)} CONTROLE(S) COM CHAVE EM MAIS DE UM ADAPTADOR.")
    print("  A ESCOLHA É DELA: em qual adaptador cada um deve ficar.")
    print("  O gesto, para o que SAI (um por adaptador de origem):\n")
    ponte = "/usr/local/lib/hefesto-dualsense4unix/bt_ponte_privilegiada.sh"
    for mac, hcis in sorted(dobrados.items()):
        for h in sorted(hcis):
            end = _prop(f"/org/bluez/{h}", "org.bluez.Adapter1", "Address")
            print(f"    # tirar do {h}:")
            print(f"    sudo {ponte} esquecer {end} {mac}")
    print("\n  Ele apaga o bond E o cache SDP na mesma execução — o cache")
    print("  sozinho envenena o pareamento seguinte (SDP-CACHE-01).")
    print("  " + "─" * 58 + "\n")
    return 0


def etapa_limpar(alvo: str, mac_pedido: str) -> int:
    """Apaga o bond de UM controle em UM adaptador, pela ponte privilegiada.

    Aceita o MAC **mascarado** (`44:46:48:00:00:03`) e resolve o real aqui —
    assim o endereço de verdade não precisa atravessar a conversa nem o
    terminal. A máscara da casa zera os octetos 4 e 5, então ela identifica
    sozinha entre quatro controles.
    """
    if alvo not in _adaptadores():
        print(f"  {alvo} não existe. Há: {', '.join(_adaptadores())}")
        return 2
    candidatos = [
        mac for hci, mac in _devices() if hci == alvo and _mascarar(mac) == mac_pedido
    ]
    if not candidatos:
        candidatos = [mac for hci, mac in _devices() if hci == alvo and mac == mac_pedido]
    if not candidatos:
        print(f"  nenhum controle {mac_pedido} em {alvo}. Os de lá:")
        for hci, mac in _devices():
            if hci == alvo:
                print(f"    {_mascarar(mac)}")
        return 3
    if len(candidatos) > 1:
        print(f"  {mac_pedido} casa com {len(candidatos)} controles — recuso por ambiguidade.")
        return 3
    mac = candidatos[0]
    endereco = _prop(f"/org/bluez/{alvo}", "org.bluez.Adapter1", "Address")
    ponte = "/usr/local/lib/hefesto-dualsense4unix/bt_ponte_privilegiada.sh"
    if not Path(ponte).exists():
        print(f"  a ponte não está instalada em {ponte} — rode o ./install.sh")
        return 5
    print(f"\n  APAGANDO o bond de {_mascarar(mac)} em {alvo}")
    print("  (o bond E o cache SDP saem na mesma execução — o cache sozinho")
    print("   envenena o pareamento seguinte)\n")
    fim = subprocess.run(
        ["sudo", "-n", ponte, "esquecer", endereco, mac],
        capture_output=True,
        text=True,
        check=False,
    )
    saida = (fim.stdout + fim.stderr).strip()
    for linha in saida.splitlines()[:12]:
        print("    " + linha.replace(mac, _mascarar(mac)))
    if fim.returncode != 0:
        print(f"\n  a ponte recusou (rc={fim.returncode}). Nada foi apagado.")
        return fim.returncode
    depois = [m for h, m in _devices() if h == alvo and m == mac]
    print(f"\n  ainda em {alvo}? {'SIM — não saiu' if depois else 'não, saiu'}")
    return 0 if not depois else 6


def etapa_controles() -> int:
    """Quem está de pé, e por onde — o que ela precisa confirmar antes de medir."""
    from hefesto_dualsense4unix.cli.cmd_tray import _chamar

    estado = _chamar("daemon.state_full") or {}
    lista = estado.get("controllers") or estado.get("controles") or []
    print("\n  O QUE O DAEMON VÊ\n  " + "─" * 58)
    if not lista:
        conectado = estado.get("connected")
        transporte = estado.get("transport")
        print(f"    connected={conectado}  transport={transporte}")
        print("    (o daemon não devolveu lista por controle nesta versão)")
    else:
        for c in lista:
            uniq = str(c.get("uniq") or "?")
            print(f"    {uniq:20} transporte={c.get('transport')}  bateria={c.get('battery_pct')}")
    print("  " + "─" * 58 + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    etapa = args[0]
    if etapa == "estado":
        return etapa_estado()
    if etapa == "taxa":
        return etapa_taxa(float(args[1]) if len(args) > 1 else 6.0)
    if etapa == "dano":
        if len(args) < 2:
            print("  uso: dano <hciN> [segundos]")
            return 2
        cruzado = "--cruzado" in args
        resto = [a for a in args[2:] if not a.startswith("--")]
        return etapa_dano(args[1], float(resto[0]) if resto else 8.0, cruzado)
    if etapa == "bonds":
        return etapa_bonds()
    if etapa == "limpar":
        if len(args) < 3:
            print("  uso: limpar <hciN> <MAC-mascarado>")
            return 2
        return etapa_limpar(args[1], args[2].upper())
    if etapa == "controles":
        return etapa_controles()
    print(f"  etapa desconhecida: {etapa}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
