#!/usr/bin/env python3
"""quem_o_jogo_abre.py — o par que separa o jogo que enxerga do que não enxerga.

A PERGUNTA QUE ELE RESPONDE
----------------------------
*Por que o Duskfade não vê o controle e o DON'T SCREAM vê, se os dois são a MESMA
coisa no disco?*

Em 16/08/2026 o censo de API de entrada
(`scripts/ensaios/api_de_entrada_dos_jogos.py`) mediu os 24 jogos dela e achou
14 com assinatura IDÊNTICA — `rawinput,xinput`, XInput carregado por
`LoadLibrary`, zero SDL. Treze funcionam. Um, o Duskfade, não. **O disco não
separa os dois**, e foi esse número que derrubou a ideia de escolher a máscara
pela engine: a heurística erraria em 13 de 14.

Se o disco não separa, o que separa está no COMPORTAMENTO — e comportamento só
se mede com o jogo aberto. É o que este instrumento faz.

O DESENHO É O PAR, e ele é o método desta casa
-----------------------------------------------
Não se mede o Duskfade sozinho. Mede-se o Duskfade CONTRA o DON'T SCREAM, na
mesma máquina, na mesma sessão, com os mesmos controles. Tudo o que for igual
nos dois está inocentado por construção; o que diferir é o suspeito.

É a mesma lógica do par doente/são da lightbar (15/08) e da troca de braços
(15/08 19h): comparar dois casos que diferem em UMA coisa é o que transforma
correlação em causa.

O QUE ELE OLHA, do processo VIVO de cada jogo
----------------------------------------------
1. **Quais nós de `/dev/input` o processo abriu.** É a pergunta central: o jogo
   que funciona abre o vpad; o que não funciona abre o quê? Nada? O físico?
2. **Quais `hidraw` ele abriu** — o caminho HIDAPI, que é outro.
3. **As variáveis de ambiente que decidem entrada**: se o wrapper rodou
   (`PROTON_DISABLE_HIDRAW` só existe se ele rodou), qual
   `SDL_GAMECONTROLLER_IGNORE_DEVICES` chegou, e se o `0x054c/0x0df2` — o PID do
   NOSSO vpad — está na lista que o jogo recebeu.
4. **A árvore de processos**, porque sob Proton o que abre o dispositivo pode ser
   o `wineserver` e não o `.exe`, e olhar só o processo do jogo dá falso zero.

O QUE ELE NÃO FAZ
------------------
Não escreve em aparelho nenhum, não abre nem fecha jogo, não toca na Steam, não
mexe em configuração. Lê `/proc` e `/sys`. O pior desfecho de um erro aqui é um
relatório errado.

E não conclui sozinho: ele imprime o par lado a lado e diz o que DIFERE. Quem
decide o que a diferença significa é quem está olhando.

COMO USAR — e a ordem importa
------------------------------
    # 1. com o DON'T SCREAM aberto (o que FUNCIONA), na tela do jogo:
    quem_o_jogo_abre.py --rotulo funciona

    # 2. feche, abra o Duskfade (o que NÃO funciona), na tela do jogo:
    quem_o_jogo_abre.py --rotulo quebrado

    # 3. o par, lado a lado:
    quem_o_jogo_abre.py --comparar

Rode com o jogo NA TELA, não no menu da Steam: o jogo só enumera controle depois
de subir. Se possível, mexa no analógico antes — alguns motores só abrem o
dispositivo quando o veem se mexer.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

#: Onde os retratos ficam. Fora do repositório de propósito: são estado de uma
#: sessão de bancada, não artefato versionado — quem quiser versionar copia.
ONDE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) \
    / "hefesto-dualsense4unix" / "quem-abre"

#: As variáveis que DECIDEM o que o jogo enxerga. As três primeiras são nossas
#: (só existem se o wrapper rodou); as outras são da Steam e do Proton.
VARS = (
    "PROTON_DISABLE_HIDRAW",
    "SDL_JOYSTICK_HIDAPI",
    "SDL_GAMECONTROLLER_USE_BUTTON_LABELS",
    "SDL_GAMECONTROLLER_IGNORE_DEVICES",
    "SDL_GAMECONTROLLER_ALLOW_STEAM_VIRTUAL_GAMEPAD",
    "SteamAppId",
    "SteamGameId",
)

#: O PID do nosso vpad. Se ele aparecer no IGNORE que o jogo recebeu, o jogo foi
#: instruído a ignorar justamente o aparelho que o produto oferece.
VPAD_VIDPID = "0x054c/0x0df2"


def _mascara(mac: str) -> str:
    p = mac.split(":")
    return mac if len(p) != 6 else ":".join([*p[:3], "00", "00", p[5]])


def nos_de_entrada() -> dict[str, str]:
    """`event42` -> o nome do dispositivo, para o relatório não ser só número."""
    fora: dict[str, str] = {}
    try:
        texto = Path("/proc/bus/input/devices").read_text(encoding="utf-8",
                                                          errors="replace")
    except OSError:
        return fora
    for bloco in texto.split("\n\n"):
        nome = re.search(r'N: Name="([^"]*)"', bloco)
        ev = re.search(r"H: Handlers=.*?(event\d+)", bloco)
        uniq = re.search(r"U: Uniq=(\S+)", bloco)
        if nome and ev:
            rot = nome.group(1)
            if uniq and uniq.group(1).count(":") == 5:
                rot += f"  [{_mascara(uniq.group(1))}]"
            fora[ev.group(1)] = rot
    return fora


def arvore_do_jogo(padrao: str) -> list[int]:
    """Todo processo cujo cmdline case, MAIS os filhos — sob Proton quem abre o
    dispositivo costuma ser outro processo que não o `.exe`."""
    alvos: set[int] = set()
    rx = re.compile(padrao, re.IGNORECASE)
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            cmd = (p / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                "utf-8", "replace")
        except OSError:
            continue
        if rx.search(cmd):
            alvos.add(int(p.name))
    # os filhos, uma geração de cada vez até estabilizar
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


def retrato(padrao: str) -> dict:
    """O que a árvore do jogo abriu e recebeu, agora."""
    nomes = nos_de_entrada()
    pids = arvore_do_jogo(padrao)
    eventos: dict[str, list[int]] = {}
    hidraws: dict[str, list[int]] = {}
    ambiente: dict[str, str] = {}
    for pid in pids:
        try:
            for fd in (Path("/proc") / str(pid) / "fd").iterdir():
                alvo = os.readlink(fd)
                m = re.search(r"(event\d+|hidraw\d+)", alvo)
                if not m:
                    continue
                (eventos if m.group(1).startswith("event") else hidraws) \
                    .setdefault(m.group(1), []).append(pid)
        except OSError:
            pass
        if not ambiente:
            try:
                bruto = (Path("/proc") / str(pid) / "environ").read_bytes()
                amb = dict(
                    linha.split("=", 1)
                    for linha in bruto.decode("utf-8", "replace").split("\0")
                    if "=" in linha
                )
                if "SteamAppId" in amb:
                    ambiente = amb
            except OSError:
                pass
    ign = ambiente.get("SDL_GAMECONTROLLER_IGNORE_DEVICES", "")
    return {
        "padrao": padrao,  # noqa-acento: chave de dado, não prosa
        "processos": len(pids),
        "eventos": {e: nomes.get(e, "?") for e in sorted(eventos)},
        "hidraws": sorted(hidraws),
        "vars": {v: ambiente.get(v, "(ausente)") for v in VARS if v !=
                 "SDL_GAMECONTROLLER_IGNORE_DEVICES"},
        "ignore_tem_nosso_vpad": VPAD_VIDPID in ign.lower(),
        "ignore_tamanho": len(ign),
        "ignore_e_nosso": ign.count(",") <= 2 and bool(ign),
        "wrapper_rodou": "PROTON_DISABLE_HIDRAW" in ambiente,
    }


def imprimir(r: dict, titulo: str) -> None:
    print(f"\n=== {titulo} ===")
    print(f"  processos na árvore ....... {r['processos']}")
    if not r["processos"]:
        # Sem processo não há o que afirmar. Imprimir "o wrapper não rodou"
        # aqui seria uma afirmação sobre um jogo que não está aberto — a mesma
        # classe de erro do instrumento que diz "o controle não respondeu"
        # quando quem não respondeu foi a porta.
        print("  (nada a medir — nenhum processo casou com o padrão)")
        return
    print(f"  o WRAPPER rodou? .......... "
          f"{'SIM' if r['wrapper_rodou'] else 'NÃO  <-- o launch_env não foi lido'}")
    print(f"  o IGNORE é o NOSSO? ....... "
          f"{'sim' if r['ignore_e_nosso'] else 'NÃO — é a lista da Steam'}"
          f"  ({r['ignore_tamanho']} caracteres)")
    veredito_vpad = (
        "SIM  <-- o jogo foi instruído a ignorar o que oferecemos"
        if r["ignore_tem_nosso_vpad"] else "não"
    )
    print(f"  ele manda ignorar o VPAD? . {veredito_vpad}")
    print(f"  nós de entrada abertos .... {len(r['eventos'])}")
    for ev, nome in r["eventos"].items():
        print(f"      {ev:<10} {nome}")
    if not r["eventos"]:
        print("      NENHUM — o jogo não abriu dispositivo de entrada algum")
    print(f"  hidraw abertos ............ {', '.join(r['hidraws']) or 'nenhum'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rotulo", help="grava o retrato com este nome "
                                     "(ex.: funciona, quebrado)")
    ap.add_argument("--padrao", default=r"\.exe|Shipping",
                    help="regex do cmdline do jogo (padrão pega .exe sob Proton)")
    ap.add_argument("--comparar", action="store_true",
                    help="mostra os retratos gravados lado a lado")
    args = ap.parse_args()

    ONDE.mkdir(parents=True, exist_ok=True)
    print("porta: /proc e /sys, leitura pura · não escreve em aparelho nenhum")

    if args.comparar:
        retratos = sorted(ONDE.glob("*.json"))
        if len(retratos) < 2:
            print(f"\nprecisa de 2 retratos, achei {len(retratos)} em {ONDE}")
            return 1
        dados = {p.stem: json.loads(p.read_text(encoding="utf-8"))
                 for p in retratos}
        for nome, r in dados.items():
            imprimir(r, nome)
        print("\n=== O QUE DIFERE — e é aqui que mora a causa ===")
        chaves = ("wrapper_rodou", "ignore_e_nosso", "ignore_tem_nosso_vpad")
        nomes = list(dados)
        for k in chaves:
            vals = {n: dados[n][k] for n in nomes}
            marca = "  <-- DIFERE" if len(set(vals.values())) > 1 else ""
            print(f"  {k:<26} " +
                  "  ".join(f"{n}={v}" for n, v in vals.items()) + marca)
        evs = {n: set(dados[n]["eventos"]) for n in nomes}
        so_de = {n: evs[n] - set().union(*(evs[o] for o in nomes if o != n))
                 for n in nomes}
        for n, s in so_de.items():
            if s:
                print(f"  nós que SÓ {n} abriu: " +
                      ", ".join(f"{e} ({dados[n]['eventos'][e]})" for e in sorted(s)))
        if not any(so_de.values()):
            print("  os dois abriram exatamente os mesmos nós")
        return 0

    r = retrato(args.padrao)
    imprimir(r, args.rotulo or "agora")
    if r["processos"] == 0:
        print("\n  NENHUM processo casou com o padrão. O jogo está aberto?")
        print("  tente --padrao com um pedaço do nome do executável.")
        return 1
    if args.rotulo:
        alvo = ONDE / f"{args.rotulo}.json"
        alvo.write_text(json.dumps(r, ensure_ascii=False, indent=1),
                        encoding="utf-8")
        print(f"\n  gravado: {alvo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
