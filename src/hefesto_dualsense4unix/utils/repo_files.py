"""Onde os arquivos do repositório (scripts, confs) estão em CADA instalação.

BG-05 (25/08/2026) — *o Python procura onde o pacote põe*.

O produto roda os scripts de `scripts/` a partir do Python: o `doctor` chama
`scripts/doctor.sh`, o `--fix-safe` chama mais três, e a aba Sistema chama
outros dois. Achar esses arquivos é uma pergunta só — **em que diretório esta
instalação pôs o `share/` do Hefesto?** — e ela tinha DUAS respostas no
código, que já haviam divergido:

- `app/actions/daemon_actions.py:495` (`BASES_DE_INSTALACAO`) — ganhou
  `/app/share` na T-02(b), hoje;
- `cli/cmd_doctor.py:23` (`_find_repo_file`) — ficou com as três bases de
  sempre, e por isso o `doctor` continuava cego no Flatpak.

Este módulo é a resposta única. **BG-BASES-01 (26/08/2026): as outras quatro
listas morreram aqui.** Eram cinco no total, e as quatro que sobreviviam ao
`cmd_doctor` cobriam bases diferentes umas das outras — por isso o mesmo
clique achava o script num formato de instalação e falhava no outro:

| resolvedor | bases | o que faltava |
|---|---|---|
| `daemon_actions.py:495` (`BASES_DE_INSTALACAO`) | 4 | `sys.prefix` e o `share/` do usuário |
| `emulation_actions.py:1200` (`_mic_script`) | 3 | as duas acima **e `/app/share`** |
| `emulation_actions.py:1763` (`_steam_input_script`) | 3 | as mesmas três |
| `cli/cmd_mic.py:92` (`_find_script`) | 3 | as mesmas três |

`sys.prefix/share/…` é AppImage, venv e Nix; `/app/share` é o Flatpak; o
`share/` do usuário é o `pip install --user`.

Todas passaram a chamar `encontrar_arquivo_do_repo()`.

Cada base abaixo é um destino MEDIDO de instalação, não uma suposição.

**O conselho de atualizar mora aqui pelo mesmo motivo** (BG-INSTALL-01):
`esta_instalacao_e_um_checkout()` e `como_atualizar_esta_instalacao()`
nasceram na T-03 dentro de `app/actions/daemon_actions.py`, e três frases de
tela que precisavam delas vivem FORA do `app/` — `integrations/storm_doctor.py`
é uma delas, e fazer `integrations/` importar de `app/` inverteria a camada.
A pergunta é a mesma deste módulo (*"o que esta instalação tem ao lado do
código?"*), então a resposta fica no mesmo lugar.
"""
from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from hefesto_dualsense4unix.utils import xdg_paths

#: Nome do diretório que este produto cria dentro de qualquer `share/`.
NOME_NO_SHARE = "hefesto-dualsense4unix"


def bases_de_instalacao() -> tuple[Path, ...]:
    """Os diretórios-base onde os arquivos do repo podem estar, em ordem.

    É função, e não constante, porque duas das bases dependem do AMBIENTE do
    processo (`sys.prefix` e `XDG_DATA_HOME`) — congelá-las no import faria a
    régua medir o ambiente de quem importou, não o de quem pergunta. É também
    o que dá mordida ao teste: ele monta um Flatpak de mentira mexendo em
    `sys.prefix` e a busca real cai lá dentro.

    A ordem, e o que cada uma vale (medido em 25/08/2026):

    1. **a raiz do checkout** — `parents[3]` a partir de
       `src/hefesto_dualsense4unix/utils/`. É a instalação editável, a da
       bancada dela. Contar errado aqui já custou a
       BUG-GUI-REPO-ROOT-OFFBYONE-01, em que os botões viravam no-op
       SILENCIOSO (toast de sucesso, nada executado) — por isso o teste
       confere que esta base contém `src/hefesto_dualsense4unix/`.
    2. **`sys.prefix/share/…`** — AppImage, venv e Nix, onde o wheel é
       instalado sob um prefixo próprio. Mesmo precedente que
       `gui/widgets/button_glyph.py:78` e `profiles/loader.py:114` já usam
       para glyphs e presets. Dentro do Flatpak `sys.prefix` é `/app`, então
       esta linha ALCANÇA o Flatpak sozinha.
    3. **`/app/share/…`** — o Flatpak escrito por extenso. É cinto e
       suspensório do item 2: o manifesto instala em `/app/share/…` de forma
       literal (`flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml`,
       nos `install -Dm644 … /app/share/…` do módulo `hefesto`), e se um dia
       o wheel for instalado com outro prefixo dentro da sandbox o item 2
       deixa de casar e este continua.
    4. **`XDG_DATA_HOME/…`** (`~/.local/share/hefesto-dualsense4unix`) — o
       `install.sh` instala aqui os glyphs (`:2922`), os wrappers de launch
       (`:2938`, `:2961`) e o `storm_watch.sh` (`:3239`). É também onde um
       `pip install --user` põe os data files.
    5. **`/usr/share/…`** — o `.deb` (`scripts/build_deb.sh:234`), o Arch
       (`packaging/arch/PKGBUILD:238`) e o Fedora (`%{_datadir}`).
    6. **`/usr/local/share/…`** — instalação manual com prefixo `/usr/local`.

    Repetição é removida preservando a ordem: com `sys.prefix == "/usr"` (o
    caso do `.deb` rodando o Python do sistema) os itens 2 e 5 são o mesmo
    diretório, e olhar duas vezes não acrescenta nada.
    """
    candidatas = (
        Path(__file__).resolve().parents[3],
        Path(sys.prefix) / "share" / NOME_NO_SHARE,
        Path("/app/share") / NOME_NO_SHARE,
        xdg_paths.data_dir(),
        Path("/usr/share") / NOME_NO_SHARE,
        Path("/usr/local/share") / NOME_NO_SHARE,
    )
    vistas: set[str] = set()
    ordenadas: list[Path] = []
    for base in candidatas:
        chave = str(base)
        if chave in vistas:
            continue
        vistas.add(chave)
        ordenadas.append(base)
    return tuple(ordenadas)


def encontrar_arquivo_do_repo(
    relpath: str, bases: Sequence[Path] | None = None
) -> Path | None:
    """O caminho REAL de um arquivo do repo (ex.: `scripts/doctor.sh`).

    Devolve a primeira base em que o arquivo existe de verdade, e ``None``
    quando ele não está em nenhuma. Nunca devolve um caminho que não é
    arquivo: quem chama pode entregar o resultado ao `bash` sem conferir de
    novo, e um ``None`` significa *"não veio nesta instalação"*, não
    *"quebrou"*.

    `bases` existe para o teste e para quem quiser perguntar por uma lista
    específica; em produção ninguém passa.
    """
    for base in bases if bases is not None else bases_de_instalacao():
        candidato = base / relpath
        if candidato.is_file():
            return candidato
    return None


#: O gesto de atualizar, nos dois únicos casos que existem.
#:
#: **PROVISÓRIO — decisão dela** (carimbo herdado da T-03, 25/08/2026): a
#: frase de fora do checkout é o *mínimo aceitável* — honesta e universal,
#: mas não nomeia o gesto do formato (um `flatpak update`, um `apt upgrade`).
#: Nomear é texto novo de tela, e isso é dela.
#:
#: **A frase de fora do checkout é comparada palavra por palavra** com a do
#: `scripts/doctor.sh` (`_CONSELHO_GESTO_GENERICO`) por
#: `tests/unit/test_bg06_o_grau_e_o_conselho_que_serve_para_esta_instalacao.py`:
#: são duas cópias declaradas da mesma decisão, e o portão existe para elas
#: não divergirem. Mudar uma sem a outra reprova.
#:
#: **ELA É UM GESTO, não uma explicação**, e isso é de propósito: entra no
#: MESMO lugar da frase onde entrava "rode ./install.sh" ("…, ou <isto>",
#: "— <isto> e reconecte os controles"). Uma oração inteira no lugar quebra a
#: gramática de quem a interpola.
FRASE_DE_ATUALIZAR: dict[bool, str] = {
    True: "rode ./install.sh para atualizar o Hefesto",
    False: "atualize o Hefesto pelo mesmo caminho por onde você o instalou",
}


def esta_instalacao_e_um_checkout(bases: Sequence[Path] | None = None) -> bool:
    """Há um `install.sh` ao lado deste código?

    É a pergunta inteira: `./install.sh` só existe para quem clonou o
    repositório. Quem instalou por Flatpak, AppImage, Arch, Fedora ou Nix não
    tem checkout nenhum na máquina — e mandá-lo rodar `./install.sh` é
    mandá-lo a um lugar que não existe.

    Não é presunção sobre o formato: é a existência do arquivo no disco. A
    primeira base é a raiz do checkout (`bases_de_instalacao()[0]`), e é lá
    que o instalador estaria.

    `bases` existe para o teste e para quem quiser perguntar por uma lista
    específica, como em `encontrar_arquivo_do_repo`; em produção ninguém passa.
    """
    lista = bases if bases is not None else bases_de_instalacao()
    return (lista[0] / "install.sh").is_file()


def como_atualizar_esta_instalacao(e_checkout: bool | None = None) -> str:
    """O gesto de atualizar que serve para ESTA instalação, sem jargão.

    T-03 (SISTEMA-O-VIGIA-VIVO-01, 25/08/2026). As frases que mandavam rodar
    o instalador não mentiam — elas davam um **conselho impossível**: em cinco
    dos seis formatos em que este produto é instalado, `./install.sh` não está
    na máquina. O produto já sabia distinguir os dois casos; ninguém tinha
    perguntado.

    `e_checkout` é para quem JÁ perguntou e não quer perguntar duas vezes (é
    um `stat` no disco). Sem ele, a função pergunta sozinha.
    """
    if e_checkout is None:
        e_checkout = esta_instalacao_e_um_checkout()
    return FRASE_DE_ATUALIZAR[bool(e_checkout)]


__all__ = [
    "FRASE_DE_ATUALIZAR",
    "NOME_NO_SHARE",
    "bases_de_instalacao",
    "como_atualizar_esta_instalacao",
    "encontrar_arquivo_do_repo",
    "esta_instalacao_e_um_checkout",
]
