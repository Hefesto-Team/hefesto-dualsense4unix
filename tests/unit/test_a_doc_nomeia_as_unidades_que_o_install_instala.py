"""A doc de instalação tem de nomear TODA unidade de usuário que o install deixa.

O DEFEITO QUE ESTE ARQUIVO GUARDA
=================================
Até 22/08/2026 a tabela *"o que o instalador deixa na sua máquina"* de
`docs/usage/instalacao.md` listava as unidades de **sistema**
(`/etc/systemd/system/`) e **nenhuma** das de usuário. Seis ficam rodando em
`~/.config/systemd/user/`, e três delas são o vigia do Steam Input —
`hefesto-steam-input-guard.path`, `.timer` e `.service`.

O efeito não é acadêmico. A página descrevia o Steam Input OFF como um gesto da
instalação, e ele **não é**: o `.path` acorda quando a Steam escreve em
`userdata/` (isto é, quando ela acaba de sair) e o `.timer` acorda a cada 30
minutos. Quem religa o Steam Input de um jogo — o caminho documentado para ter
gyro no 8BitDo, em `troubleshooting-8bitdo.md` — vê a escolha voltar sozinha e
não tem, na documentação, uma linha que explique quem a desfez. É a forma
"no meu funciona" do problema: na máquina de quem instalou e nunca mexeu, nada
disso aparece.

A RÉGUA, E POR QUE ELA NÃO É UMA LISTA À MÃO
=============================================
O conjunto de unidades é LIDO do `install.sh` — todo alvo
`${…USER_UNIT_DIR}/<unidade>` que ele escreve. Uma lista escrita aqui
envelheceria junto com a documentação que deveria vigiar: as duas erradas,
concordando entre si, e o teste verde. Quem acrescentar a sétima unidade ao
`install.sh` ganha este portão de graça.

O `install.sh` é território de outra frente e **não é tocado por este arquivo** —
ele é lido, e só.

MORDIDAS (aplicadas uma a uma em 22/08/2026, todas reprovaram)
===============================================================
1. Apagar a linha `~/.config/systemd/user/` da tabela do `instalacao.md`:
   `test_toda_unidade_de_usuario_esta_documentada` reprova nomeando as seis.
2. Apagar só a menção ao `.timer`: o mesmo teste reprova nomeando **só ele** —
   é o caso que interessa, porque é ele que faz a reaplicação parecer mágica.
3. Trocar o extrator por uma lista de seis nomes escrita à mão:
   `test_a_lista_vem_do_install_e_nao_de_uma_lista_a_mao` reprova — ele monta um
   `install.sh` de mentira com uma unidade inventada e confere que o extrator a
   vê.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
INSTALL = RAIZ / "install.sh"
INSTALACAO = RAIZ / "docs" / "usage" / "instalacao.md"

#: `install -Dm644 … "${USER_UNIT_DIR}/x"`, `… > "${USER_UNIT_DIR}/y"`,
#: `readonly ALGO="${STORM_USER_UNIT_DIR}/z"` — o que interessa é o ALVO.
ALVO = re.compile(r"\$\{[A-Z_]*USER_UNIT_DIR\}/([A-Za-z0-9._@-]+)")

#: A pasta em prosa, que é como a pessoa a reconhece na tabela.
PASTA = "~/.config/systemd/user"


def unidades_de_usuario(caminho: Path | str) -> set[str]:
    """As unidades `--user` que o instalador escreve, lidas dele."""
    return set(ALVO.findall(Path(caminho).read_text(encoding="utf-8")))


def test_o_extrator_acha_alguma_coisa() -> None:
    """Régua que não acha nada aprova tudo — e essa é a falha silenciosa."""
    achadas = unidades_de_usuario(INSTALL)
    assert len(achadas) >= 4, (
        f"o extrator só achou {sorted(achadas)} em install.sh. Se o instalador "
        "deixou de escrever unidades de usuário, este arquivo tem de ser "
        "reescrito; se ele mudou a forma de escrevê-las, a régua ficou cega e "
        "passaria a aprovar qualquer documentação"
    )


def test_toda_unidade_de_usuario_esta_documentada() -> None:
    """A tabela do `instalacao.md` tem de nomear cada uma delas."""
    texto = INSTALACAO.read_text(encoding="utf-8")
    faltando = sorted(u for u in unidades_de_usuario(INSTALL) if u not in texto)
    assert not faltando, (
        f"o install.sh deixa {len(faltando)} unidade(s) de usuário que a "
        f"documentação não nomeia: {', '.join(faltando)}. Elas ficam RODANDO na "
        "máquina de quem instalou — e o vigia do Steam Input em particular "
        "desfaz, sozinho e depois, escolhas que a pessoa fez na Steam"
    )


def test_a_pasta_das_unidades_de_usuario_aparece_na_tabela() -> None:
    """Nomear as unidades sem dizer onde moram não ajuda ninguém a desligá-las."""
    assert PASTA in INSTALACAO.read_text(encoding="utf-8"), (
        f"{INSTALACAO.relative_to(RAIZ)} não cita {PASTA} — a pessoa não tem "
        "como achar o que precisa desabilitar"
    )


def test_o_vigia_do_steam_input_nao_e_descrito_como_gesto_unico() -> None:
    """As DUAS unidades de gatilho têm de estar na página, não só o serviço.

    Documentar apenas o `.service` deixaria a página dizendo o mesmo que dizia
    antes — "o instalador desliga o Steam Input" —, que é a leitura de gesto
    único. Quem explica a volta é o par `.path` + `.timer`.
    """
    texto = INSTALACAO.read_text(encoding="utf-8")
    gatilhos = [
        u
        for u in unidades_de_usuario(INSTALL)
        if "steam-input-guard" in u and u.rsplit(".", 1)[-1] in {"path", "timer"}
    ]
    assert len(gatilhos) == 2, (
        f"esperava o par .path + .timer do vigia no install.sh, achei {gatilhos}"
    )
    ausentes = [u for u in gatilhos if u not in texto]
    assert not ausentes, (
        f"a página não nomeia {', '.join(ausentes)}. Sem os dois gatilhos, ela "
        "volta a descrever o Steam Input OFF como um gesto da instalação — e o "
        "vigia reaplica a cada 30 min e a cada saída da Steam"
    )


def test_a_lista_vem_do_install_e_nao_de_uma_lista_a_mao(tmp_path: Path) -> None:
    """A validação da régua: ela tem de ver uma unidade que só existe no falso."""
    falso = tmp_path / "install.sh"
    falso.write_text(
        'USER_UNIT_DIR="${HOME}/.config/systemd/user"\n'
        'install -Dm644 "${ROOT_DIR}/assets/inventada.timer" '
        '"${USER_UNIT_DIR}/hefesto-inventada.timer"\n',
        encoding="utf-8",
    )
    assert unidades_de_usuario(falso) == {"hefesto-inventada.timer"}
    assert "hefesto-inventada.timer" not in unidades_de_usuario(INSTALL), (
        "a régua devolveu a unidade inventada lendo o install.sh de verdade — "
        "ela está devolvendo uma lista fixa em vez de ler o arquivo"
    )
