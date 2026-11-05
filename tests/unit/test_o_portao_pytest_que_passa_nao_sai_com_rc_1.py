"""O portão pytest grava o `rc` do pytest ao lado do `rc` do invólucro (vaga, bus e tela).

Medido em 01/11/2026 (ci-local, job GTK real): `portao-tem-chamador VERMELHO rc=1` com a saída
terminando em `11 passed in 0.64s`, e as outras três pernas `ok`. O `portoes.sh` só guardava o `rc`
da cadeia inteira (`vez-do-pytest.sh` > `dbus-run-session` > `xvfb-run` > `pytest`). Agora o `bash`
mais interno grava o `rc` do pytest ao lado; se o invólucro sai com outro, isso fica escrito na
saída do portão e na corrida (`involucro-mentiu.txt`), que é o instrumento para provar a causa.

O portão reprova se qualquer um dos dois sai com erro: o invólucro que mente não se esconde.

A SONDA DE CAMADAS (04/11/2026): cada camada da cadeia grava o `rc` com que saiu (`dbus.rc`,
`xvfb.rc`, o do pytest e o de fora, o do semáforo), e a linha `camadas:` diz que camada trocou
o `rc` que veio de dentro. O `ci-local` que reprovar com `rc=1` e «N passed» deixa o nome da
camada no `involucro-mentiu.txt`.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

RAIZ = Path(__file__).resolve().parents[2]
TABELA = "rapido|pytest-tela|pytest|tests/test_tela.py"


def _paralelo() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_portoes_em_paralelo_do_rc",
        RAIZ / "tests" / "unit" / "test_os_portoes_rodam_em_paralelo.py",
    )
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["_portoes_em_paralelo_do_rc"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _corre(
    tmp_path: Path,
    involucro: str,
    *,
    tela: str = "limpo\n",
    portoes: str | None = None,
    ambiente: dict[str, str] | None = None,
) -> tuple[dict[str, str], str]:
    """Roda o portão pytest atrás de um semáforo de mentira; devolve (status, saída da corrida)."""
    paralelo = _paralelo()
    vez = tmp_path / "vez-do-pytest.sh"
    vez.write_text("#!/usr/bin/env bash\n" + involucro, encoding="utf-8")
    repo = paralelo._monta(tmp_path, TABELA, arquivos={"dados/tela.txt": tela}, portoes=portoes)
    r = paralelo._corre(
        repo, "--rapido", "--sem-memoria",
        env={"HEFESTO_VEZ_DO_PYTEST": str(vez), **(ambiente or {})},
    )
    return paralelo._status(r.stdout), r.stdout


def test_o_involucro_com_1_e_o_pytest_verde_reprova_e_diz_a_camada(tmp_path: Path) -> None:
    status, saida = _corre(tmp_path, '"$@"\nexit 1\n')

    assert status == {"pytest-tela": "VERMELHO"}, saida
    assert "invólucro com rc diferente do pytest" in saida, saida
    assert "pytest-tela rc=1" in saida, saida


def test_o_pytest_vermelho_reprova_mesmo_com_o_involucro_saindo_com_0(tmp_path: Path) -> None:
    status, saida = _corre(tmp_path, '"$@"\nexit 0\n', tela="MORDIDA\n")

    assert status == {"pytest-tela": "VERMELHO"}, saida


def test_o_pytest_vermelho_reprova_com_o_involucro_igual(tmp_path: Path) -> None:
    status, saida = _corre(tmp_path, 'exec "$@"\n', tela="MORDIDA\n")

    assert status == {"pytest-tela": "VERMELHO"}, saida
    assert "invólucro com rc diferente" not in saida, saida


def test_o_involucro_que_cai_antes_de_o_pytest_rodar_reprova(tmp_path: Path) -> None:
    """Sem o `rc` do pytest gravado, vale o da cadeia: o portão nem chegou a rodar."""
    status, saida = _corre(tmp_path, "exit 1\n")

    assert status == {"pytest-tela": "VERMELHO"}, saida


def test_o_involucro_que_cai_antes_diz_que_camada_nao_gravou(tmp_path: Path) -> None:
    ambiente = _camadas_de_mentira(tmp_path)
    status, saida = _corre(tmp_path, "exit 1\n", ambiente=ambiente)

    assert status == {"pytest-tela": "VERMELHO"}, saida
    assert "o pytest nem gravou o rc; camadas: externo=1 dbus=? xvfb=? pytest=?" in saida, saida
    assert "sem rc gravado" not in saida, saida


def test_morde_o_pytest_vermelho_atras_do_involucro_verde(tmp_path: Path) -> None:
    """A mordida: sem ler o `rc` do pytest, o invólucro de `rc` 0 esconde o pytest vermelho."""
    texto = (RAIZ / "scripts" / "portoes.sh").read_text(encoding="utf-8")
    velho = '      [ "$prc" != 0 ] && [ "$rc" -eq 0 ] && rc=1\n'
    assert texto.count(velho) == 1
    status, saida = _corre(
        tmp_path, '"$@"\nexit 0\n', tela="MORDIDA\n", portoes=texto.replace(velho, "      :\n")
    )

    assert status == {"pytest-tela": "ok"}, saida


_DBUS_DE_MENTIRA = """#!/usr/bin/env bash
[ "$1" = -- ] && shift
"$@"
r=$?
exit {saida}
"""

_XVFB_DE_MENTIRA = """#!/usr/bin/env bash
erro=/dev/null
display=""
while true; do
  case "$1" in
    -a) shift ;;
    -n) display="$2"; shift 2 ;;
    -e) erro="$2"; shift 2 ;;
    *) break ;;
  esac
done
printf '%s\\n' "$display" >> "{pasta}/displays"
echo "Xvfb de mentira: o servidor saiu antes da hora" > "$erro"
"$@"
r=$?
exit {saida}
"""


def _camadas_de_mentira(
    tmp_path: Path, *, dbus: int | None = None, xvfb: int | None = None
) -> dict[str, str]:
    """`dbus-run-session` e `xvfb-run` de mentira: rodam o comando e saem com o `rc` pedido
    (sem pedido, com o do comando, como os de verdade)."""
    pasta = tmp_path / "camadas"
    pasta.mkdir()
    saida = {None: '"$r"'}
    (pasta / "dbus-run-session").write_text(
        _DBUS_DE_MENTIRA.format(saida=saida.get(dbus, dbus)), encoding="utf-8"
    )
    (pasta / "xvfb-run").write_text(
        _XVFB_DE_MENTIRA.format(saida=saida.get(xvfb, xvfb), pasta=pasta), encoding="utf-8"
    )
    for nome in ("dbus-run-session", "xvfb-run"):
        (pasta / nome).chmod(0o755)
    return {"PATH": f"{pasta}:{os.environ['PATH']}"}


def test_a_camada_de_fora_que_troca_o_rc_fica_escrita(tmp_path: Path) -> None:
    ambiente = _camadas_de_mentira(tmp_path)
    status, saida = _corre(tmp_path, '"$@"\nexit 1\n', ambiente=ambiente)

    assert status == {"pytest-tela": "VERMELHO"}, saida
    assert "camadas: externo=1 dbus=0 xvfb=0 pytest=0" in saida, saida
    assert "trocou o rc: externo (0 -> 1)" in saida, saida


def test_o_xvfb_que_troca_o_rc_diz_que_foi_ele(tmp_path: Path) -> None:
    ambiente = _camadas_de_mentira(tmp_path, xvfb=1)
    status, saida = _corre(tmp_path, '"$@"\nexit 1\n', ambiente=ambiente)

    assert status == {"pytest-tela": "VERMELHO"}, saida
    assert "externo=1 dbus=1 xvfb=1 pytest=0" in saida, saida
    assert "trocou o rc: xvfb (0 -> 1)" in saida, saida


def test_o_dbus_que_troca_o_rc_diz_que_foi_ele(tmp_path: Path) -> None:
    ambiente = _camadas_de_mentira(tmp_path, dbus=1)
    status, saida = _corre(tmp_path, '"$@"\nexit 1\n', ambiente=ambiente)

    assert status == {"pytest-tela": "VERMELHO"}, saida
    assert "externo=1 dbus=1 xvfb=0 pytest=0" in saida, saida
    assert "trocou o rc: dbus (0 -> 1)" in saida, saida


def test_as_camadas_honestas_nao_acusam_ninguem(tmp_path: Path) -> None:
    ambiente = _camadas_de_mentira(tmp_path)
    status, saida = _corre(tmp_path, '"$@"\n', ambiente=ambiente)

    assert status == {"pytest-tela": "ok"}, saida
    assert "invólucro com rc diferente" not in saida, saida


def test_morde_a_sonda_do_xvfb_arrancada(tmp_path: Path) -> None:
    """Sem a sonda no `xvfb-run`, o `rc` dele some e a culpa não cai nele."""
    texto = (RAIZ / "scripts" / "portoes.sh").read_text(encoding="utf-8")
    velho = "bash -c '$_ANOTA_O_RC' $lar/xvfb.rc xvfb-run -a -n $((100 + n)) -e $lar/xvfb.err"
    assert texto.count(velho) == 1
    ambiente = _camadas_de_mentira(tmp_path, xvfb=1)
    status, saida = _corre(
        tmp_path, '"$@"\nexit 1\n', ambiente=ambiente,
        portoes=texto.replace(velho, "xvfb-run -a"),
    )

    assert status == {"pytest-tela": "VERMELHO"}, saida
    assert "trocou o rc: xvfb (0 -> 1)" not in saida, saida


def test_cada_portao_tem_o_seu_display_e_o_que_o_xvfb_escreveu_fica_na_saida(
    tmp_path: Path,
) -> None:
    """Dois portões de pytest ao mesmo tempo não disputam o mesmo `:99` do `xvfb-run -a`."""
    ambiente = _camadas_de_mentira(tmp_path, xvfb=1)
    tabela = TABELA + "\n" + TABELA.replace("pytest-tela", "pytest-tela-2")
    paralelo = _paralelo()
    vez = tmp_path / "vez-do-pytest.sh"
    vez.write_text('#!/usr/bin/env bash\n"$@"\n', encoding="utf-8")
    repo = paralelo._monta(tmp_path, tabela, arquivos={"dados/tela.txt": "limpo\n"})
    r = paralelo._corre(
        repo, "--rapido", "--sem-memoria",
        env={"HEFESTO_VEZ_DO_PYTEST": str(vez), **ambiente},
    )

    pedidos = (tmp_path / "camadas" / "displays").read_text(encoding="utf-8").split()
    assert len(set(pedidos)) == 2 and all(p.isdigit() for p in pedidos), pedidos
    assert "o que o Xvfb escreveu:" in r.stdout, r.stdout
    assert "Xvfb de mentira: o servidor saiu antes da hora" in r.stdout, r.stdout
