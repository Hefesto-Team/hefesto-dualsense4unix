"""README-DKMS-SUDO-01 — nenhum arquivo versionado manda rodar o `install.sh` com sudo.

A regra desta casa está no `CLAUDE.md` e nasceu de dano medido: **`install.sh`
nunca com `sudo`**. Com `sudo`, o `HOME` vira `/root` — o `.venv` nasce
root-owned, os symlinks vão para `/root/.local/bin` e as units de usuário para
`/root/.config/systemd/user`. É uma instalação que imprime sucesso e **não
existe** para o usuário que vai jogar. O estudo de 29/07/2026 mediu isso e
registrou que o `install.sh` **não tem guarda** contra o caso: o `acquire_sudo`
devolve 0 na hora quando `EUID==0`, sem um aviso sequer.

E o texto errado sobreviveu **seis versões** dentro de
`assets/dkms/hid-nintendo/README.md` — o pior lugar possível para ele estar,
porque aquele diretório **viaja para dentro do `.deb`, do PKGBUILD e do RPM**.
Quem instala por pacote recebe a instrução na própria máquina.

Este é o portão que faltava. Ele varre os arquivos **rastreados pelo git** (é
por isso que a regra da casa manda rodar os portões **depois** do `git add`) e
reprova qualquer forma de invocar o `install.sh` sob `sudo`.

**A lista de dispensas é curta e cada linha tem razão escrita.** Um documento
que *explica* o defeito precisa citá-lo — apagar a citação apagaria a memória
de por que a regra existe, e a casa não apaga decisão medida. O que o portão
proíbe é a **instrução**, não a **menção**.

A mordida: devolvendo `sudo bash install.sh` ao README do DKMS, este teste
reprova nomeando arquivo, linha e o texto da linha.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Toda forma de mandar o `install.sh` rodar debaixo de `sudo`:
#: `sudo install.sh`, `sudo bash install.sh`, `sudo sh ./install.sh`,
#: `sudo -E bash install.sh`, `sudo ./install.sh`. O `uninstall.sh` NÃO é alvo
#: deste portão (ele tem guarda própria e sprint própria) — daí o `(?<!un)`
#: antes do nome, que impede o casamento com `uninstall.sh`.
SUDO_INSTALL_RE = re.compile(
    r"sudo\b(?:\s+-\w+)*\s+(?:(?:bash|sh|zsh)\s+)?(?:\./)?(?<!un)install\.sh\b"
)

#: Extensões sem texto a auditar.
_SEM_TEXTO = {".png", ".svg", ".mo", ".ico", ".gif", ".jpg", ".jpeg", ".webp"}

#: Dispensas — cada uma com a razão pela qual a CITAÇÃO tem de ficar.
DISPENSAS: dict[str, str] = {
    # O estudo de dezessete agentes é onde o defeito foi MEDIDO e escrito.
    # Sem a citação, some a prova de por que a regra existe.
    "docs/process/estudos/2026-07-29-mapa-total-o-estudo-de-dezessete-agentes.md": (
        "é o estudo que MEDIU o dano do sudo; a citação é a prova"
    ),
    # Este próprio portão precisa escrever a forma proibida para poder caçá-la.
    "tests/unit/test_nenhum_arquivo_manda_rodar_install_com_sudo.py": (
        "é o portão; ele escreve a forma proibida para reconhecê-la"
    ),
    # 13/08/2026: o estudo de doze agentes remediu o caso e nomeou o que
    # CONTINUA aberto — o `install.sh` em si segue sem guarda de tempo de
    # execução (`install.sh:434` devolve 0 quando `EUID==0`, sem um aviso).
    # Este portão guarda o TEXTO versionado; aquele buraco é outro, e a citação
    # é o que impede que ele seja esquecido de novo.
    "docs/process/estudos/2026-08-13-o-projeto-inteiro-num-mapa-so.md": (
        "mede o buraco que SOBRA — o install.sh sem guarda de EUID==0; "
        "a citação é a prova, não a instrução"
    ),
    # 13/08/2026: o índice das doze levas registra, na linha da leva 9, que o
    # README do DKMS **parou de ensinar** a forma errada. A frase cita o que foi
    # removido para poder dizer que foi removido — é o registro do conserto, o
    # oposto de uma instrução. Sem a citação, a leva vira "mexeu no README" e
    # ninguém sabe o que mudou.
    "docs/process/sprints/2026-08-13-DOZE-LEVAS-01-o-que-ja-foi-feito-hoje-e-nao-se-refaz.md": (
        "registra que o README PAROU de ensinar a forma errada; a citação é o "
        "registro do conserto, não a instrução"
    ),
}


def _arquivos_rastreados() -> list[Path]:
    saida = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [
        REPO_ROOT / nome
        for nome in saida.split("\0")
        if nome and Path(nome).suffix.lower() not in _SEM_TEXTO
    ]


def test_o_regex_reconhece_as_formas_e_poupa_o_uninstall() -> None:
    """A régua antes da medição — senão o portão verde não prova nada."""
    for proibida in (
        "sudo install.sh",
        "sudo bash install.sh",
        "sudo sh install.sh",
        "sudo ./install.sh",
        "sudo bash ./install.sh",
        "sudo -E bash install.sh",
        "sudo -E ./install.sh",
    ):
        assert SUDO_INSTALL_RE.search(proibida), f"o portão é cego a {proibida!r}"
    for permitida in (
        "./install.sh --yes",
        "bash install.sh",
        "sudo bash uninstall.sh",
        "sudo ./uninstall.sh",
        "re-execute ./install.sh",
        'warn "sudo recusado — passo pulado (re-execute ./install.sh)"',
        "sudo apt install dkms",
    ):
        assert not SUDO_INSTALL_RE.search(permitida), (
            f"o portão reprova o que é legítimo: {permitida!r}"
        )


def test_nenhum_arquivo_versionado_manda_instalar_com_sudo() -> None:
    violacoes: list[str] = []
    for caminho in _arquivos_rastreados():
        rel = caminho.relative_to(REPO_ROOT).as_posix()
        if rel in DISPENSAS:
            continue
        try:
            texto = caminho.read_text(encoding="utf-8", errors="ignore")
        except (OSError, IsADirectoryError):
            continue  # apagado no working tree, submódulo, etc.
        for numero, linha in enumerate(texto.splitlines(), start=1):
            if SUDO_INSTALL_RE.search(linha):
                violacoes.append(f"{rel}:{numero}: {linha.strip()}")
    assert not violacoes, (
        "`install.sh` NUNCA com sudo — com sudo o HOME vira /root e a instalação "
        "não existe para o usuário. A forma certa é `./install.sh` (ou "
        "`./install.sh --yes` sem terminal interativo): o script pede a senha "
        "sozinho no passo que precisa dela.\n  " + "\n  ".join(violacoes)
    )


def test_toda_dispensa_e_um_arquivo_que_de_fato_cita_a_forma_proibida() -> None:
    """A dispensa vale por ARQUIVO INTEIRO — então ela não pode ser barata.

    Sem esta trava, a lista viraria a saída fácil: dispensar um arquivo
    preventivamente (sem citação nenhuma) desliga o portão para tudo que for
    escrito nele DEPOIS, e ninguém repara — que é a forma clássica de um portão
    verde deixar de valer.

    Exige duas coisas de cada linha: que o arquivo exista e seja rastreado (o
    portão só varre rastreados), e que ele REALMENTE contenha a forma proibida
    hoje. Dispensa que sobrevive ao texto que a justificava é dispensa rançosa,
    e sai.
    """
    rastreados = {
        c.relative_to(REPO_ROOT).as_posix() for c in _arquivos_rastreados()
    }
    for rel, razao in DISPENSAS.items():
        assert rel in rastreados, (
            f"dispensa aponta para arquivo que o git não rastreia: {rel} — "
            "o portão nem o varreria, então a linha só engorda a lista"
        )
        texto = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="ignore")
        assert SUDO_INSTALL_RE.search(texto), (
            f"dispensa RANÇOSA: {rel} já não cita a forma proibida ({razao!r}). "
            "Apague a linha — enquanto ela existir, o portão está desligado "
            "para esse arquivo inteiro sem que nada o justifique"
        )


def test_o_readme_do_dkms_ensina_a_forma_certa() -> None:
    """O arquivo que viaja no .deb/PKGBUILD/RPM tem de trazer a forma correta."""
    readme = REPO_ROOT / "assets" / "dkms" / "hid-nintendo" / "README.md"
    texto = readme.read_text(encoding="utf-8")
    assert "./install.sh --yes" in texto, (
        "o README empacotado tem de mostrar a invocação certa, não só deixar de "
        "mostrar a errada — quem instala por pacote lê este arquivo na máquina"
    )
    assert re.search(r"HOME vira /root", texto), (
        "e tem de dizer POR QUE, ali mesmo: sem a razão, o `sudo` volta na "
        "primeira vez que alguém encontrar um passo pedindo senha"
    )
