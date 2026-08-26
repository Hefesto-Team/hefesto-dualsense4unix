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

Este módulo é a resposta única. O `cmd_doctor` já a consome; o
`daemon_actions` tem dono em outra árvore neste momento e é a próxima parada
(está no relatório da frente).

Cada base abaixo é um destino MEDIDO de instalação, não uma suposição.
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
       literal (`flatpak/br.andrefarias.Hefesto.yml:231,246,267`), e se um dia
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


__all__ = ["NOME_NO_SHARE", "bases_de_instalacao", "encontrar_arquivo_do_repo"]
