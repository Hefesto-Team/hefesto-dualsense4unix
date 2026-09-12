#!/usr/bin/env python3
"""check_a_grafia_do_nome.py — o nome do produto se escreve `DualSense4Unix`.

O DEFEITO, e ele durou o repositório inteiro
---------------------------------------------
`utils/identidade.py` grafava ``Dualsense4Unix``, com **``s`` minúsculo**, e a
grafia se repetiu em **427 linhas de 174 arquivos** — tela, documento,
comentário, `.desktop`, AppStream, `.po`. O ``S`` é do **DualSense**, o aparelho
que dá nome ao produto; ``Dualsense`` não é nada.

**E ele travava uma cura já medida.** Em 11/09/2026 a barra da janela passou a
dizer o nome inteiro, por ordem dela — *"no nome da janela não conseguimos
deixar Hefesto - DualSense4Unix ao invés de só hefesto?"*  (noqa-acento: citação
literal dela) —, e as duas linhas que o fizeram, as de ``_MOLDURA`` logo abaixo,
nasceram com o nome **DIGITADO**, com a dívida escrita ao lado: ler do dono poria a grafia
errada na barra dela. Fechada a grafia, as duas passaram a ler. É o padrão desta
casa: *quando um valor tem dono, a régua PERGUNTA ao dono.*

AS DUAS PENEIRAS, e uma sozinha daria verde sobre o defeito da outra
---------------------------------------------------------------------
1. **A GRAFIA.** Nenhuma ocorrência de ``Dualsense4Unix`` em arquivo versionado,
   fora dos identificadores técnicos abaixo.
2. **O DONO.** Quem mostra o nome na moldura LÊ de ``identidade.nome_longo``. Um
   literal do nome longo dentro de ``set_title``/``set_subtitle`` reprova mesmo
   com a grafia CERTA — porque a grafia certa digitada em dois lugares é a
   próxima divergência esperando acontecer, que é exatamente como esta casa
   chegou aos 427.

O QUE ELE **NÃO** ACUSA, e cada exceção foi MEDIDA contra a árvore de 11/09
---------------------------------------------------------------------------
Nem toda ocorrência é o nome do produto em texto. Estas são **identificador
técnico**: strings que alguém de fora deste repositório casa LETRA POR LETRA.
Trocar a caixa delas não dá erro — dá silêncio, que é o preço que esta casa
mais paga.

* ``Hefesto-Dualsense4Unix`` (hífen, sem espaços) — é o ``wm_class`` de
  ``identidade.py``, o ``StartupWMClass=`` e o ``Icon=`` do ``.desktop`` **já
  instalado na máquina dela**, o ``last_class`` que o daemon gravou no estado, o
  ``window_class`` que os perfis de jogo guardam, e o nome dos arquivos
  ``.AppImage``/``.png``/``.flatpak`` que as releases publicaram.
  **O que quebraria:** o ícone some da dock (o ``StartupWMClass`` deixa de casar
  o que a janela publica), o perfil por janela para de trocar sozinho, e o
  ``park`` de janela do compositor erra o alvo. Tudo calado.
* ``com.vitoriamaria.HefestoDualsense4Unix`` — o app-id do Flatpak, o nome-base
  do ``.desktop`` e do ícone no tema ``hicolor``.
  **O que quebraria:** a atualização do Flatpak instalado (id novo = outro app,
  com outra pasta de perfis dentro do sandbox) e a resolução do ícone.
* ``… pad (Hefesto - Dualsense4Unix virtual)`` e o Pro Controller — o nome que o
  nó **uinput** publica no kernel. **Jogos sob Proton casam por SUBSTRING do
  nome** (é a razão escrita em ``test_a_marca_do_vpad_no_nome_e_a_de_hoje.py``).
  **O que quebraria:** as amarrações que a pessoa já salvou por nome de
  aparelho, em Steam e em cada jogo.
* ``Hefesto - Dualsense4Unix Virtual Keyboard`` / ``… Virtual Mouse+Keyboard`` —
  idem, e o compositor guarda configuração POR NOME de dispositivo.
  **O que quebraria:** a configuração de teclado/mouse virtual dela volta ao
  padrão, sem aviso.

Ordem dela, 11/09/2026, e é ela que decide estas quatro:

    *"a ideia é que todas as features mesmo do app funcionem nao so pra  (noqa-acento: citação literal dela)
    mim mas pra qualquer outro user"*

Uma troca de grafia que quebre o reconhecimento de janela, o ``.desktop`` ou o
nó de entrada quebra a instalação de **todo mundo**. Por isso o passo 1 foi
medir, não trocar.

A MORDIDA (arranque a cura, veja reprovar, devolva)
----------------------------------------------------
``tests/unit/test_portao_a_grafia_do_nome_morde.py`` fabrica os dois defeitos
num diretório de mentira e exige rc=1 nos dois, e exige rc=0 sobre os quatro
identificadores técnicos — porque uma régua que reprovasse o ``wm_class`` seria
pior que a ausência dela.

À mão, nesta árvore::

    sed -i 's/DualSense4Unix/Dualsense4Unix/' README.md
    python3 scripts/check_a_grafia_do_nome.py   # -> FALHA, nomeando README.md

REAPLICAR A CORREÇÃO (idempotente), quando uma costura trouxer texto novo::

    bash scripts/aplicar_a_grafia_do_nome.sh

A LISTAGEM é ``git ls-files --cached --others --exclude-standard``, nunca
``git grep``: portão é cego a arquivo novo, e esta casa já pagou por isso
(cicatriz ANONIMATO-CEGO-A-ARQUIVO-NOVO-01).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

#: A GRAFIA ERRADA, e as três guardas que protegem identificador técnico.
#: É a MESMA expressão de ``scripts/aplicar_a_grafia_do_nome.sh``, de propósito:
#: a régua e a cura têm de concordar sobre o que é texto e o que é endereço.
_ERRADA = re.compile(
    r"(?<![-\w])Dualsense4Unix(?! Virtual )(?! virtual\))"
)

#: Os arquivos que NOMEIAM a grafia errada como defeito — a citação não se
#: limpa, pela mesma razão do `noqa-acento`: apagar a grafia errada de dentro
#: do laudo que a achou destrói o laudo.
ISENTOS: dict[str, str] = {
    "docs/process/agentes/2026-09-11/ESQUELETO-C2-opus.md":
        "o laudo que ACHOU o defeito; as duas linhas citam a grafia errada.",
    "docs/process/sprints/2026-09-11-A-FILA-QUE-A-ONDA-ABRIU-INDICE.md":
        "a fila que abriu esta frente; o §4 escreve a grafia errada para nomeá-la.",
    "docs/process/sprints/2026-09-11-F6-O-NOME-TEM-UM-DONO-e-a-barra-passa-a-ler.md":
        "a sprint desta frente; o laudo cita as duas grafias lado a lado.",
    "scripts/check_a_grafia_do_nome.py":
        "esta régua: a docstring tem de poder escrever o que ela caça.",
    "scripts/aplicar_a_grafia_do_nome.sh":
        "a cura: a expressão tem de poder escrever o que ela substitui.",
    "tests/unit/test_portao_a_grafia_do_nome_morde.py":
        "a mordida: ela fabrica o defeito para ver a régua reprovar.",
}

#: A MOLDURA — quem mostra o nome tem de LER do dono. Os métodos que põem texto
#: na barra da janela e na bandeja.
_MOLDURA = (
    "src/hefesto_dualsense4unix/gui/ponte_da_tela.py",
    "src/hefesto_dualsense4unix/interface/ver.py",
)
_METODOS_DE_MOLDURA = re.compile(
    r"(?:set_title|set_subtitle|Gtk\.Window\()\s*\(?[^)\n]*"
    r"Hefesto\s*[-—]\s*DualSense4Unix"
)

_BINARIO = {".mo", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".gz", ".zip", ".AppImage"}


def _arquivos() -> list[Path]:
    """Rastreados **e** novos — portão é cego a arquivo novo por padrão."""
    saida = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=RAIZ, capture_output=True, text=True, check=True,
    ).stdout
    return [RAIZ / p for p in saida.split("\0") if p]


def a_grafia() -> list[tuple[str, int, str]]:
    """A primeira peneira: nenhuma grafia errada fora dos identificadores."""
    fora: list[tuple[str, int, str]] = []
    for caminho in _arquivos():
        rel = caminho.relative_to(RAIZ).as_posix()
        if rel in ISENTOS or caminho.suffix in _BINARIO or not caminho.is_file():
            continue
        try:
            texto = caminho.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for n, linha in enumerate(texto.splitlines(), 1):
            if _ERRADA.search(linha):
                fora.append((rel, n, linha.strip()[:110]))
    return fora


def o_dono() -> list[tuple[str, int, str]]:
    """A segunda peneira: a moldura LÊ o nome, não o digita."""
    fora: list[tuple[str, int, str]] = []
    for rel in _MOLDURA:
        caminho = RAIZ / rel
        if not caminho.is_file():
            fora.append((rel, 0, "o arquivo da moldura sumiu — a régua mede o mundo de ontem"))
            continue
        texto = caminho.read_text(encoding="utf-8")
        for n, linha in enumerate(texto.splitlines(), 1):
            if linha.lstrip().startswith("#"):
                continue  # comentário é prosa, não é o que a barra mostra
            if _METODOS_DE_MOLDURA.search(linha):
                fora.append((rel, n, linha.strip()[:110]))
        if "nome_longo" not in texto:
            fora.append((rel, 0, "não pergunta `identidade.…nome_longo` em lugar nenhum"))
    return fora


def _isentos_vivos() -> list[str]:
    """Isenção que isenta nada é isenção morta — e isso se diz em voz alta."""
    mortos = []
    for rel in ISENTOS:
        caminho = RAIZ / rel
        if not caminho.is_file():
            mortos.append(f"{rel}: o arquivo não existe mais")
            continue
        if not _ERRADA.search(caminho.read_text(encoding="utf-8")):
            mortos.append(f"{rel}: já não tem a grafia errada — a isenção venceu")
    return mortos


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--all", action="store_true", help="compatibilidade; já é o padrão")
    ap.parse_args()

    grafia = a_grafia()
    dono = o_dono()
    mortos = _isentos_vivos()

    for rel, n, linha in grafia:
        print(f"[FAIL] {rel}:{n} grafa `Dualsense4Unix`; o nome é `DualSense4Unix`")
        print(f"       {linha}")
    for rel, n, linha in dono:
        print(f"[FAIL] {rel}:{n} DIGITA o nome; ele tem dono — `identidade.atual().nome_longo`")
        print(f"       {linha}")
    for aviso in mortos:
        print(f"[AVISO] isenção morta em ISENTOS — {aviso}")

    if grafia or dono:
        print()
        print(f"FALHA: {len(grafia)} grafia(s) errada(s), {len(dono)} nome(s) digitado(s).")
        print("       O `S` é do DualSense. Identificador técnico (wm_class, app-id,")
        print("       nome de nó uinput) NÃO se troca — ver a docstring deste arquivo.")
        print("       Reaplicar a cura: bash scripts/aplicar_a_grafia_do_nome.sh")
        return 1

    print(f"OK: o nome se escreve `DualSense4Unix` em toda a árvore "
          f"({len(ISENTOS)} isenções declaradas), e a moldura lê do dono.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
