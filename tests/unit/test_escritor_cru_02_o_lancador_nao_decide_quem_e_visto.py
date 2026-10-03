"""ESCRITOR-CRU-02 — quem joga fora da Steam também tem um escritor cru."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from hefesto_dualsense4unix.core import escritor_cru as ec


class TestAVarreduraAmplaVeAlemDaSteam:
    def test_ve_um_processo_que_nao_e_a_steam(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """**O CASO QUE ORIGINOU ESTA RÉGUA** — o jogo por Lutris/Heroic."""
        _proc_de_mentira(
            tmp_path,
            monkeypatch,
            {"4242": {"3": "/dev/hidraw6"}},
        )
        mapa = ec.holders_de_hidraw_de_qualquer_um()
        assert mapa == {"/dev/hidraw6": [4242]}, (
            "o escritor cru fora da Steam continua invisível"
        )

    def test_o_filtro_por_no_continua_valendo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Só os nós que interessam voltam — um teclado HID não é assunto."""
        _proc_de_mentira(
            tmp_path,
            monkeypatch,
            {"4242": {"3": "/dev/hidraw6", "4": "/dev/hidraw9"}},
        )
        assert ec.holders_de_hidraw_de_qualquer_um(["/dev/hidraw6"]) == {
            "/dev/hidraw6": [4242]
        }

    def test_nada_que_nao_seja_hidraw_atravessa(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A DISCRIÇÃO, e ela é a razão 3 que ficou de pé."""
        _proc_de_mentira(
            tmp_path,
            monkeypatch,
            {
                "4242": {
                    "3": "/dev/hidraw6",
                    "4": "/home/alguem/Documentos/carta-pessoal.odt",
                    "5": "socket:[12345]",
                }
            },
        )
        mapa = ec.holders_de_hidraw_de_qualquer_um()
        assert mapa == {"/dev/hidraw6": [4242]}
        assert not any("carta-pessoal" in str(v) for v in mapa.values())

    def test_processo_ilegivel_degrada_sem_derrubar(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Processo de outro usuário: `/proc/<pid>/fd` dá `OSError`."""
        _proc_de_mentira(
            tmp_path, monkeypatch, {"4242": {"3": "/dev/hidraw6"}, "9999": None}
        )
        assert ec.holders_de_hidraw_de_qualquer_um() == {"/dev/hidraw6": [4242]}


class TestNaoAcusamosANosMesmos:
    def test_o_proprio_daemon_sai_da_lista(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ARMADILHA DA CURA: o daemon segura o próprio hidraw."""
        eu = os.getpid()
        _proc_de_mentira(
            tmp_path,
            monkeypatch,
            {str(eu): {"3": "/dev/hidraw6", "4": "/dev/hidraw6"}},
        )
        assert ec.escritores_crus_alheios(["/dev/hidraw6"]) == {}

    def test_o_alheio_sobrevive_ao_filtro(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """E o nó que TEM os dois volta só com o alheio."""
        eu = os.getpid()
        _proc_de_mentira(
            tmp_path,
            monkeypatch,
            {str(eu): {"3": "/dev/hidraw6"}, "4242": {"3": "/dev/hidraw6"}},
        )
        assert ec.escritores_crus_alheios(["/dev/hidraw6"]) == {
            "/dev/hidraw6": [4242]
        }

    def test_no_so_com_o_nosso_pid_nao_vira_chave_vazia(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Chave com lista VAZIA leria como "sondado e tem alguém" no consumidor."""
        eu = os.getpid()
        _proc_de_mentira(
            tmp_path,
            monkeypatch,
            {str(eu): {"3": "/dev/hidraw0"}, "4242": {"3": "/dev/hidraw6"}},
        )
        mapa = ec.escritores_crus_alheios()
        assert "/dev/hidraw0" not in mapa, "nó só nosso virou chave"
        assert mapa == {"/dev/hidraw6": [4242]}


class TestASentinelaEstaLIGADA:
    """*A cura escrita e nunca ligada* é o defeito mais caro desta casa."""

    def test_o_default_da_sentinela_e_a_visao_ampla(self) -> None:
        """MORDIDA: devolver o default a `holders_de_hidraw`."""
        s = ec.SentinelaDeEscritorCru()
        assert s._sonda is ec.escritores_crus_alheios, (
            "a sentinela voltou a enxergar só a Steam"
        )

    def test_a_sonda_injetada_continua_vencendo(self) -> None:
        """O default não pode tirar de ninguém o direito de injetar a sua."""
        marca: list[object] = []

        def minha_sonda(nos=None):
            marca.append(nos)
            return {}

        s = ec.SentinelaDeEscritorCru(sonda=minha_sonda)
        s.sondar(["/dev/hidraw6"], agora=1.0)
        assert marca, "a sonda injetada não foi chamada"

    def test_o_caminho_da_janela_continua_restrito(self) -> None:
        """DE PROPÓSITO, e a razão está escrita no fonte."""
        janela = Path(
            "src/hefesto_dualsense4unix/daemon/ipc_handlers.py"
        ).read_text(encoding="utf-8")
        assert "holders_de_hidraw_de_qualquer_um" not in janela
        assert "from hefesto_dualsense4unix.core.escritor_cru import holders_de_hidraw" in janela


class TestOCustoEstaMedidoNoFonte:
    def test_o_orcamento_existe_e_nao_e_infinito(self) -> None:
        """Varredura sem teto trava o chamador quando o `/proc` engasga."""
        assert 0.0 < ec.ORCAMENTO_DA_VARREDURA_AMPLA_S <= 2.0


def _proc_de_mentira(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    processos: dict[str, dict[str, str] | None],
) -> None:
    """Monta `/proc/<pid>/fd/<n>` como symlinks de verdade, num tmp."""
    raiz = tmp_path / "proc"
    raiz.mkdir()
    ilegiveis: set[str] = set()
    for pid, fds in processos.items():
        d = raiz / pid / "fd"
        d.mkdir(parents=True)
        if fds is None:
            ilegiveis.add(str(d))
            continue
        for n, alvo in fds.items():
            (d / n).symlink_to(alvo)

    listdir_real = os.listdir

    def listdir(caminho, *a, **k):
        s = str(caminho)
        if s in ilegiveis:
            raise PermissionError(s)
        if s == "/proc":
            return listdir_real(raiz)
        if s.startswith("/proc/"):
            return listdir_real(str(raiz) + s[len("/proc"):])
        return listdir_real(caminho, *a, **k)

    readlink_real = os.readlink

    def readlink(caminho, *a, **k):
        s = str(caminho)
        if s.startswith("/proc/"):
            return readlink_real(str(raiz) + s[len("/proc"):])
        return readlink_real(caminho, *a, **k)

    monkeypatch.setattr(ec.os, "listdir", listdir)
    monkeypatch.setattr(ec.os, "readlink", readlink)
