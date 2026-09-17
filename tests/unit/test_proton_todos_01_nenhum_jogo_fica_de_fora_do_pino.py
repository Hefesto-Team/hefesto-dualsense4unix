"""PROTON-TODOS-01 — nenhum jogo fica de fora do pino, nem os de depois.

**Decisão dela, 17/09/2026.** Vendo o DON'T SCREAM ficar no ``proton_11``
enquanto os outros 24 subiam para o ``GE-Proton11-7-x86_64``:

    "mas não era pra todos ficarem sobre o novo proton?"

e, quando a razão da guarda lhe foi explicada:

    "ele e todo o resto de agora em diante."

**O QUE A GUARDA `preservado` REALMENTE FAZ**, e por que a correção importa:
ela pula, por FORMA, toda entrada de jogo cujo ``name`` aponte para uma
ferramenta que não está em ``pinos_nossos``. Ela **não sabe** se aquilo foi
escolha de alguém. Nasceu em 19/08/2026 pelo motivo oposto — em 14/08 a trava
APAGOU três escolhas dela, e a queixa foi *"não anda. nem o microfone."* — e é
conservadora por desenho.

Em 17/09 ela foi descrita, nesta casa, como *"a escolha dela de 14/08"*. Não é.
Foi ela quem apanhou o erro, com a pergunta acima.

**O QUE MUDA E O QUE NÃO MUDA.** O padrão da FUNÇÃO continua sendo a guarda:
quem chamar ``lock_games_to_pinned_proton`` sem pedir não atropela ninguém. O
que passou a pedir é o PRODUTO — o ``install.sh`` chama ``--lock --todos``. A
diferença é de quem assume a decisão, e agora ela está assumida por escrito, com
data e com a frase dela.

Daqui em diante, exceção é NOMEADA e DATADA por ela, nunca inferida da forma do
arquivo.
"""

from __future__ import annotations

import pathlib

import pytest

from hefesto_dualsense4unix.integrations import proton_pin


PINO = "GE-Proton11-7-x86_64"


def _vdf(mapeamento: dict[str, str]) -> str:
    """Um `config.vdf` mínimo, com o bloco que o produto edita."""
    linhas = [
        '"InstallConfigStore"', "{", '\t"Software"', "\t{", '\t\t"Valve"',
        "\t\t{", '\t\t\t"Steam"', "\t\t\t{", '\t\t\t\t"CompatToolMapping"',
        "\t\t\t\t{",
    ]
    for app, nome in mapeamento.items():
        linhas += [
            f'\t\t\t\t\t"{app}"', "\t\t\t\t\t{",
            f'\t\t\t\t\t\t"name"\t\t"{nome}"',
            '\t\t\t\t\t\t"config"\t\t""',
            '\t\t\t\t\t\t"priority"\t\t"250"',
            "\t\t\t\t\t}",
        ]
    linhas += ["\t\t\t\t}", "\t\t\t}", "\t\t}", "\t}", "}"]
    return "\n".join(linhas) + "\n"


def _nomes(texto: str) -> dict[str, str]:
    import re
    return {a: n for a, n in re.findall(r'"(\d+|0)"\s*\{[^}]*?"name"\s*"([^"]*)"', texto, re.S)}


# ---------------------------------------------------------------------------
# 1 — a decisão dela
# ---------------------------------------------------------------------------
def test_com_todos_o_jogo_em_outra_ferramenta_migra() -> None:
    """A cena exata da queixa: o DON'T SCREAM em `proton_11`, o resto no pino."""
    original = _vdf({"0": PINO, "2497900": "proton_11", "111": PINO})

    novo, mudancas = proton_pin.build_compat_tool_mapping(
        original,
        tool_name=PINO,
        appids=["2497900", "111"],
        pinos_nossos=(PINO,),
        atropelar_escolha_dela=True,
    )

    assert _nomes(novo)["2497900"] == PINO, (
        "o jogo que apontava para outra ferramenta NÃO migrou com a ordem dela "
        "ligada — é a queixa de 17/09/2026"
    )
    assert mudancas["2497900"]["action"] != "preservado"
    assert mudancas["2497900"]["previous_name"] == "proton_11", (
        "o caminho de volta tem de ficar registrado: o `--unlock` devolve o "
        "`previous_name`, e sem ele a decisão dela vira via de mão única"
    )


def test_sem_todos_a_guarda_continua_sendo_o_padrao() -> None:
    """O padrão da função não mudou — quem não pede, não atropela.

    Isto não é detalhe: a guarda existe porque em 14/08/2026 a trava apagou
    três escolhas dela. Quem chamar a função sem pedir explicitamente continua
    protegido, e quem pede assume a decisão por escrito.
    """
    original = _vdf({"0": PINO, "2497900": "proton_11"})

    novo, mudancas = proton_pin.build_compat_tool_mapping(
        original, tool_name=PINO, appids=["2497900"], pinos_nossos=(PINO,),
    )

    assert _nomes(novo)["2497900"] == "proton_11", "a guarda deixou de ser o padrão"
    # `changes` vem VAZIO ao preservar — medido, não suposto: o dicionário
    # registra o que MUDOU, e preservar é não mudar. A régua afirma o efeito
    # no arquivo, que é o que a pessoa sente, e não o formato do relatório.
    assert mudancas == {}, f"preservar não pode escrever nada: {mudancas}"
    assert novo == original, "o arquivo mudou apesar de a guarda ter preservado"


@pytest.mark.parametrize(
    "ferramenta",
    ["proton_11", "proton_experimental", "proton_hotfix", "GE-Proton9-20"],
)
def test_todos_alcanca_qualquer_ferramenta(ferramenta: str) -> None:
    """*"todo o resto"* é literal — não é uma lista de ferramentas conhecidas.

    Uma cura que enumerasse as ferramentas de hoje deixaria de fora a que a
    Steam inventar amanhã, e o defeito voltaria calado. É a diferença entre
    curar a CLASSE e curar a instância, que é ordem dela de 16/09/2026.
    """
    original = _vdf({"0": PINO, "42": ferramenta})

    novo, _ = proton_pin.build_compat_tool_mapping(
        original, tool_name=PINO, appids=["42"], pinos_nossos=(PINO,),
        atropelar_escolha_dela=True,
    )
    assert _nomes(novo)["42"] == PINO


# ---------------------------------------------------------------------------
# 2 — o PRODUTO pede, e é isso que faz valer "de agora em diante"
# ---------------------------------------------------------------------------
def test_o_install_pede_todos() -> None:
    """Sem esta linha, a decisão dela morre no CLI e nunca alcança a máquina.

    A MORDIDA: tire o `--todos` do `install.sh` e este teste reprova. É a
    diferença entre a cura existir e a cura estar LIGADA — o defeito mais caro
    desta casa.
    """
    import re

    # `parents[3]` já é a raiz: .../src/hefesto_dualsense4unix/integrations/x.py
    # → integrations → hefesto_dualsense4unix → src → RAIZ. Um `.parent` a mais
    # subia para fora do repo e o teste virava `skip` — e skip não mede nada.
    raiz = pathlib.Path(proton_pin.__file__).resolve().parents[3]
    inst = raiz / "install.sh"
    assert inst.is_file(), (
        f"o `install.sh` não está em {inst} — se o caminho mudou, reaponte-o; "
        "um `skip` aqui esconderia a asserção que importa"
    )

    texto = inst.read_text(encoding="utf-8")
    assert re.search(r"proton_pin\.py[^\n]*--lock\b[^\n]*--todos\b", texto) or \
           re.search(r'PROTON_PIN_PY\}"\s+--lock\s+--todos', texto), (
        "o `install.sh` chama `--lock` sem `--todos`: a guarda `preservado` "
        "volta a valer e jogo com outra ferramenta fica fora do pino, em "
        "silêncio. É a ordem dela de 17/09/2026"
    )


def test_a_flag_existe_no_cli() -> None:
    """E ela tem de estar no `--help`, senão ninguém a encontra."""
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, proton_pin.__file__, "--help"],
        capture_output=True, text=True, timeout=60,
    )
    assert "--todos" in r.stdout, "a flag sumiu do CLI"


# ---------------------------------------------------------------------------
# 3 — a régua sabe reprovar
# ---------------------------------------------------------------------------
def test_a_regua_sabe_reprovar() -> None:
    """Com a ordem dela DESLIGADA, o caso central falha — é o que a prova.

    Se este teste passar com `atropelar_escolha_dela=True`, a régua acima não
    está medindo a flag: está medindo outra coisa que acontece de qualquer
    jeito.
    """
    original = _vdf({"0": PINO, "2497900": "proton_11"})

    sem, _ = proton_pin.build_compat_tool_mapping(
        original, tool_name=PINO, appids=["2497900"], pinos_nossos=(PINO,),
    )
    com, _ = proton_pin.build_compat_tool_mapping(
        original, tool_name=PINO, appids=["2497900"], pinos_nossos=(PINO,),
        atropelar_escolha_dela=True,
    )
    assert _nomes(sem)["2497900"] != _nomes(com)["2497900"], (
        "a flag não mudou nada — ou ela parou de ser lida, ou o jogo já era "
        "alcançado por outro caminho e esta régua dá verde sobre nada"
    )


# ---------------------------------------------------------------------------
# 4 — O CAMINHO, não o método (a mordida que faltava)
# ---------------------------------------------------------------------------
#
# ESTA CLASSE NASCEU DE UMA MORDIDA QUE NÃO MORDEU, em 17/09/2026. Arranquei o
# repasse `atropelar_escolha_dela=todos` de dentro de
# `lock_games_to_pinned_proton` e os nove testes acima ficaram VERDES: eles
# chamam `build_compat_tool_mapping` direto — que tem o parâmetro — e leem o
# texto do `install.sh`. O trecho do meio, que é justamente onde a flag pode se
# perder, não era exercido por ninguém.
#
# É a assinatura que esta casa persegue há meses: *a régua mede o MÉTODO e não
# o CAMINHO*, e passa verde com o laço de produção torto. A classe abaixo
# dirige a função pública, com um `config.vdf` de mentira, e por isso morde.
class TestOCaminhoDaFlag:
    """De `lock_games_to_pinned_proton(todos=…)` até o byte no arquivo."""

    def _cena(self, tmp_path: pathlib.Path) -> pathlib.Path:
        vdf = tmp_path / "config.vdf"
        vdf.write_text(_vdf({"0": PINO, "2497900": "proton_11"}), encoding="utf-8")
        return vdf

    def test_o_lock_com_todos_alcanca_o_jogo(self, tmp_path: pathlib.Path) -> None:
        """A MORDIDA: tire `atropelar_escolha_dela=todos` do `lock` e isto reprova."""
        vdf = self._cena(tmp_path)
        r = proton_pin.lock_games_to_pinned_proton(
            tool_name=PINO,
            appids=["2497900"],
            config_vdf=vdf,
            state_path=tmp_path / "estado.json",
            todos=True,
        )
        assert r["status"] in ("locked", "noop"), r
        assert _nomes(vdf.read_text(encoding="utf-8"))["2497900"] == PINO, (
            "o `todos=True` não chegou ao miolo que decide — o repasse se "
            "perdeu entre a função pública e `build_compat_tool_mapping`"
        )

    def test_o_lock_sem_todos_preserva(self, tmp_path: pathlib.Path) -> None:
        """O outro lado: sem pedir, o arquivo não muda. Sem este caso, um
        `todos` grudado em `True` passaria despercebido."""
        vdf = self._cena(tmp_path)
        antes = vdf.read_text(encoding="utf-8")
        proton_pin.lock_games_to_pinned_proton(
            tool_name=PINO,
            appids=["2497900"],
            config_vdf=vdf,
            state_path=tmp_path / "estado.json",
        )
        assert _nomes(vdf.read_text(encoding="utf-8"))["2497900"] == "proton_11", (
            "o padrão deixou de preservar: alguém grudou o `todos` em True"
        )
        assert vdf.read_text(encoding="utf-8") == antes
