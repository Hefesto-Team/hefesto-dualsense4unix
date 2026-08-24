"""BERÇO-DE-TMP-01, a cauda do `$HOME` (24/08/2026).

A sprint mãe (`docs/process/sprints/
2026-08-07-BERCO-DE-TMP-01-a-suite-nao-suja-a-config-dela-suja-o-tmp.md`)
curou o `/tmp` e deixou aberto, em *"O que fica ABERTO"*: *"`utils/i18n.py` e
`core/system_check.py` continuam lendo o `$HOME` real sob teste, e o `HOME`
continua não isolado no autouse"*.

O PORQUÊ, medido em 24/08/2026: a fixture `_hefesto_fake_env` (`tests/
conftest.py`) já isolava os quatro `XDG_*` desde o BUG-TEST-CONFIG-LEAK-01,
mas `Path.home()`/`os.path.expanduser("~")` continuavam resolvendo o `$HOME`
REAL do dev em qualquer código que não passe pelos `XDG_*`. Dois casos
medidos, e os dois são LEITURA (não escrita — por isso o CANARIO-FS-01, que só
vigia escrita, ficava calado):

- `utils/i18n._candidate_locale_dirs()` inclui `Path.home()/.local/share/
  locale` como segundo candidato. Como o candidato XDG isolado nasce vazio, o
  `_find_locale_dir()` cai para este — e num source-install real, ele
  encontraria o catálogo `.mo` DELA, deixando `init_locale()` (que trava o
  resultado num flag de módulo pela sessão inteira) dependente do disco do
  dev, não do teste.
- `core/system_check._wireplumber_hijacks_mic()` lê `Path.home()/.local/
  state/wireplumber/default-nodes` direto. Todo teste que sobe o daemon passa
  por `_check_system_on_boot()`, que chama esta função — e o aviso resultante
  dependeria de o WirePlumber real da máquina ter fixado o DualSense como mic
  padrão, não do que o teste está exercitando.

A CURA é a mesma dos quatro `XDG_*`: a fixture agora isola o `HOME` também,
num diretório vazio por teste, sem escotilha própria (nenhuma suíte depende do
`$HOME` real; os 7 arquivos que já faziam `monkeypatch.setenv("HOME", ...)`
continuam livres — vencem por rodar depois desta fixture).

A MORDIDA: comentar as três linhas que isolam `HOME` em `_hefesto_fake_env`
(`tests/conftest.py`) faz os quatro testes abaixo reprovarem — o primeiro
porque `HOME` volta a ser o do dono do processo, os outros três porque os
caminhos que `i18n`/`system_check` resolveriam saem de dentro do `tmp_path`
da sessão. Devolvida a cura, os quatro voltam a passar.
"""
from __future__ import annotations

import os
import pwd
from pathlib import Path

from hefesto_dualsense4unix.core import system_check
from hefesto_dualsense4unix.utils import i18n


def test_home_isolado_nao_e_o_home_do_dono_do_processo() -> None:
    """`$HOME` sob teste não pode ser o `$HOME` real de quem roda a suíte.

    A referência não vem de `os.environ` (que é exatamente o que a fixture
    mexe) — vem de `pwd`, que lê `/etc/passwd` e ignora `HOME` por completo.
    É o único jeito de comparar contra o valor real sem depender do mecanismo
    que este teste está tentando provar.
    """
    home_real_do_processo = pwd.getpwuid(os.getuid()).pw_dir
    assert os.environ.get("HOME") != home_real_do_processo, (
        "a suíte está rodando com o $HOME REAL do dev — a fixture "
        "`_hefesto_fake_env` parou de isolar o HOME."
    )


def test_home_isolado_vive_dentro_do_tmp_da_sessao(tmp_path: Path) -> None:
    """`Path.home()` cai dentro do MESMO `tmp_path` que o teste recebeu.

    Amarra o mecanismo ao local exato (`tmp_path/.xdg/home`) — se alguém mover
    o isolamento para outro lugar sem atualizar este teste, ele reprova
    nomeando o caminho errado em vez de ficar cego à mudança.
    """
    assert Path.home() == tmp_path / ".xdg" / "home"
    assert Path.home().is_dir()


def test_system_check_nunca_alcanca_o_wireplumber_real(tmp_path: Path) -> None:
    """`_wireplumber_hijacks_mic()` lê dentro do isolamento, não da máquina.

    Path-containment em vez de "existe/não existe": não depende do disco real
    do dev ter (ou não ter) o arquivo, então o teste não muda de resultado
    conforme a mesa de quem roda — o que ele prova é ONDE o código olha.
    """
    alvo = Path.home() / ".local/state/wireplumber/default-nodes"
    assert str(alvo).startswith(str(tmp_path)), (
        f"`_wireplumber_hijacks_mic()` leria {alvo}, fora do HOME isolado — "
        "isto é a máquina real do dev, não o teste."
    )
    # Corolário comportamental: como o `home_dir` isolado nasce vazio, sem
    # `.local/state/wireplumber/`, a função nunca pode achar "dualsense" ali.
    assert system_check._wireplumber_hijacks_mic() is False


def test_i18n_fallback_de_home_fica_dentro_do_isolamento(tmp_path: Path) -> None:
    """O segundo candidato de `_candidate_locale_dirs()` não escapa do teste.

    O primeiro candidato já é `XDG_DATA_HOME/locale` (isolado desde o
    BUG-TEST-CONFIG-LEAK-01); este teste cobre o SEGUNDO, o `Path.home()`
    cru que só o BERÇO-DE-TMP-01 alcança.
    """
    candidatos = i18n._candidate_locale_dirs()
    fallback_de_home = candidatos[1]
    assert fallback_de_home == Path.home() / ".local" / "share" / "locale"
    assert str(fallback_de_home).startswith(str(tmp_path)), (
        f"o candidato de fallback de i18n é {fallback_de_home}, fora do HOME "
        "isolado — um source-install real do dev vazaria o catálogo dela "
        "para dentro da suíte."
    )
