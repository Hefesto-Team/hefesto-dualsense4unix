"""QUEM-JOGA-E-QUEM-VIBRA-01 — o jogo manda, e não há portão de quem mexe na volta do rádio."""

from __future__ import annotations

import pathlib

from hefesto_dualsense4unix.integrations.quem_o_jogo_le import ENV_DO_JOGO, pids_de_jogo


def _proc_de_mentira(raiz: pathlib.Path, processos: dict[int, bool]) -> pathlib.Path:
    """`/proc` de mentira: `{pid: é_jogo}`."""
    base = raiz / "proc"
    for pid, e_jogo in processos.items():
        d = base / str(pid)
        d.mkdir(parents=True, exist_ok=True)
        env = f"{ENV_DO_JOGO}=/algum/prefixo\0HOME=/x\0" if e_jogo else "HOME=/x\0"
        (d / "environ").write_bytes(env.encode("utf-8"))
    return base


class TestOSinalDosPids:
    def test_so_e_jogo_quem_tem_a_env_do_proton(self, tmp_path):
        base = _proc_de_mentira(tmp_path, {11: True, 22: False})
        assert pids_de_jogo(base) == {11}

    def test_proc_ilegivel_nao_vira_jogo(self, tmp_path):
        assert pids_de_jogo(tmp_path / "nao-existe") == set()


class TestONaoHaPortaoDeQuemMexe:
    """O subsystem não consulta mais quem joga: o jogo manda, o controle obedece."""

    def _corpo(self) -> str:
        fonte = pathlib.Path(
            "src/hefesto_dualsense4unix/daemon/subsystems/alto_falante.py"
        ).read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def _casar_as_pontes") :]
        return corpo[: corpo.index("\n    def ", 1)]

    def test_a_volta_nao_consulta_quem_joga(self) -> None:
        """MORDIDA: devolva a consulta de quem mexeu à condição da háptica."""
        corpo = self._corpo()
        assert "este_joga" not in corpo, "o portão de quem mexe voltou à volta do rádio"
        assert "_quem_mexeu_na_partida" not in corpo
        assert "self._quem_o_jogo_le(controles)" not in corpo, (
            "a varredura de /proc voltou a rodar a cada volta"
        )

    def test_a_haptica_no_fio_exige_so_o_canal_aberto_e_o_ganho(self) -> None:
        """Desde 03/10/2026 não há modo; desde 26/10/2026 não há portão de toque."""
        corpo = self._corpo()
        i = corpo.index("leva = bool(")
        condicao = corpo[i : corpo.index("\n", i)]
        assert "endpoint_aberto" in condicao, "o canal saiu da condição da háptica"
        assert "este_joga" not in condicao
        assert "som_toca" not in condicao, "o alto-falante voltou a decidir a háptica"
