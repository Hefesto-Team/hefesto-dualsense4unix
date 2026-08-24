"""Testes da ONDA0-Z7 · O AMBIENTE PRESUMIDO 01 — os caminhos da casa (Z7-B).

Cobre T-05 (`XDG_CONFIG_HOME` vale para os dois caminhos do WirePlumber),
T-06 (a faixa sintética de teste não pode morar no `config_dir()` de
produção — o portão `scripts/check_faixa_sintetica.py`) e T-07 (o rascunho da
mesa sobrevive a fechar o programa sem "Aplicar").
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from hefesto_dualsense4unix.utils import xdg_paths

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import check_faixa_sintetica  # import após o sys.path acima, de propósito


# ---------------------------------------------------------------------------
# T-05 — XDG_CONFIG_HOME vale para os dois caminhos do WirePlumber
# ---------------------------------------------------------------------------


class TestWireplumberConfigDir:
    def test_default_sem_xdg_config_home(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        esperado = tmp_path / ".config" / "wireplumber" / "wireplumber.conf.d"
        assert xdg_paths.wireplumber_config_dir() == esperado

    def test_honra_xdg_config_home(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A MORDIDA central de T-05: mover XDG_CONFIG_HOME move o caminho."""
        outro_lugar = tmp_path / "zz-outro-lugar"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(outro_lugar))
        esperado = outro_lugar / "wireplumber" / "wireplumber.conf.d"
        assert xdg_paths.wireplumber_config_dir() == esperado

    def test_storm_doctor_e_emulation_actions_concordam(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """As DUAS chamadas alheias (storm_doctor.py:252,
        emulation_actions.py:1003) devolvem O MESMO caminho sob o mesmo
        `XDG_CONFIG_HOME` — é a régua do item 1 do aceite (§9.1). Ambas
        chamadas de verdade, sem duplicar a lógica delas aqui."""
        outro_lugar = tmp_path / "zz-outro-lugar"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(outro_lugar))
        esperado = outro_lugar / "wireplumber" / "wireplumber.conf.d"

        from hefesto_dualsense4unix.app.actions.emulation_actions import (
            EmulationActionsMixin,
        )
        from hefesto_dualsense4unix.integrations.storm_doctor import (
            INFO,
            OK,
            check_wireplumber,
        )

        # storm_doctor.check_wireplumber devolve status/mensagem sobre o
        # diretório, não o path em si -- então provamos que ELE OLHA o
        # `outro_lugar` plantando o drop-in exatamente lá e vendo a mensagem
        # mudar de "sem drop-in" para "configurado".
        assert check_wireplumber()[0] == INFO  # ainda sem drop-in
        esperado.mkdir(parents=True)
        (esperado / "51-hefesto-dualsense-no-default-source.conf").touch()
        status, msg = check_wireplumber()
        assert status == OK and "51-hefesto" in msg

        assert EmulationActionsMixin._wp_dropin_dir() == esperado


# ---------------------------------------------------------------------------
# T-06 — a faixa sintética não mora no config_dir() de produção
# ---------------------------------------------------------------------------


class TestPortaoFaixaSintetica:
    @pytest.mark.parametrize(
        "grafia",
        [
            "aabbcc000009",
            "aa:bb:cc:00:00:09",
            "02fe001234ab",
            "02:fe:00:12:34:ab",
            "e8473a998877",
            # SEM grafia com ':' para e8:47:3a aqui: `scripts/check_test_data.sh`
            # (ALLOWED_MAC) só permite as duas OUTRAS faixas na grafia com ':' —
            # achado durante esta sprint, relatado no lugar de consertado (fora
            # do escopo de T-06). A grafia sem ':' (linha acima) já prova que
            # este portão CASA a terceira faixa nas duas formas.
        ],
    )
    def test_reprova_nas_duas_grafias(self, tmp_path: Path, grafia: str) -> None:
        """A MORDIDA de T-06, direção 1: qualquer grafia das três faixas, em
        qualquer arquivo do config_dir(), reprova nomeando arquivo e linha."""
        alvo = tmp_path / "controllers.json"
        alvo.write_text(f'{{"controles": [{{"mac": "{grafia}"}}]}}\n', encoding="utf-8")

        achados = check_faixa_sintetica.achados(tmp_path)

        assert achados, f"não achou a faixa sintética {grafia!r}"
        assert str(alvo) in achados[0]
        assert ":1:" in achados[0]  # linha 1

    def test_passa_com_mac_real_sintetico_da_casa_fora_das_tres_faixas(
        self, tmp_path: Path
    ) -> None:
        """MAC de teste que NÃO é uma das três faixas proibidas não reprova —
        o portão é sobre estas TRÊS faixas específicas, não sobre todo MAC.

        O valor é `3c:9d:07:00:00:0a`, a SEGUNDA faixa sintética da casa
        (`test_anonimato_de_fixtures.py::_PREFIXOS_FORJADOS`, conferida contra
        o registro IEEE) com a máscara nos octetos 4 e 5. Serve aqui por ser a
        única coisa que este teste precisa — MAC-forma fora das três faixas do
        portão — e por já ser faixa DOCUMENTADA: qualquer outro token de 12 hex
        reprova `test_nenhum_mac_fora_das_faixas_forjadas_em_tests`, que é
        allowlist por desenho e não sabe distinguir "forjado óbvio" de real.
        """
        alvo = tmp_path / "controllers.json"
        alvo.write_text('{"controles": [{"mac": "3c9d0700000a"}]}\n', encoding="utf-8")

        assert check_faixa_sintetica.achados(tmp_path) == []

    def test_arrancar_a_faixa_da_lista_de_proibidas_faz_o_portao_passar(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A MORDIDA de T-06, direção 2: tirar 'aabbcc' de FAIXAS_SINTETICAS
        faz o PORTÃO passar (falso negativo) — e é assim que se prova que o
        teste acima não é um dublê que só sabe passar: ele depende de verdade
        da lista, e a lista precisa estar completa."""
        alvo = tmp_path / "controllers.json"
        alvo.write_text('{"mac": "aabbcc000009"}\n', encoding="utf-8")
        assert check_faixa_sintetica.achados(tmp_path) != []  # antes: reprova

        monkeypatch.setattr(
            check_faixa_sintetica,
            "_PADROES",
            {
                f: p
                for f, p in check_faixa_sintetica._PADROES.items()
                if f != "aabbcc"
            },
        )
        assert check_faixa_sintetica.achados(tmp_path) == []  # depois: passa (esperado)

    def test_diretorio_ausente_nao_explode(self, tmp_path: Path) -> None:
        assert check_faixa_sintetica.achados(tmp_path / "nao-existe") == []

    def test_main_devolve_1_com_achado_e_0_sem(self, tmp_path: Path) -> None:
        limpo = tmp_path / "limpo"
        limpo.mkdir()
        assert check_faixa_sintetica.main(["--config-dir", str(limpo)]) == 0

        sujo = tmp_path / "sujo"
        sujo.mkdir()
        (sujo / "controllers.json").write_text('{"mac": "e8473a000001"}', encoding="utf-8")
        assert check_faixa_sintetica.main(["--config-dir", str(sujo)]) == 1


# ---------------------------------------------------------------------------
# T-07 — o maquina.json sobrevive a fechar o programa
# ---------------------------------------------------------------------------


def _rodar(
    script: str, env: dict[str, str], timeout: float = 15.0
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )


class TestRascunhoDaMesaSobrevive:
    def test_grava_so_a_secao_mesa_sem_inventar_o_resto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.utils.maquina import (
            carregar_maquina,
            gravar_rascunho_da_mesa,
        )

        assert gravar_rascunho_da_mesa({"altura_da_antena": "acima"}) is True

        cfg = carregar_maquina()
        assert cfg.mesa.altura_da_antena == "acima"
        assert cfg.mesa.linha_de_visada is None  # não declarado -> não inventado
        assert cfg.controles == {}  # outra seção -- intocada

    def test_uma_segunda_gravacao_nao_apaga_a_primeira(self) -> None:
        """Fusão parcial: declarar de novo não apaga o que já estava lá."""
        from hefesto_dualsense4unix.utils.maquina import (
            carregar_maquina,
            gravar_rascunho_da_mesa,
        )

        gravar_rascunho_da_mesa({"altura_da_antena": "acima"})
        gravar_rascunho_da_mesa({"linha_de_visada": "livre"})

        cfg = carregar_maquina()
        assert cfg.mesa.altura_da_antena == "acima"
        assert cfg.mesa.linha_de_visada == "livre"

    def test_sobrevive_a_processo_morto_com_os_exit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A MORDIDA central de T-07: `os._exit` (sem atexit, sem GC, sem
        flush de nada que dependa de shutdown limpo) logo depois da gravação
        — e a leitura acontece NOUTRO processo, como o item 4 do aceite pede."""
        import os

        env = dict(os.environ)  # a fixture autouse já isolou XDG_CONFIG_HOME aqui

        escrever = (
            "from hefesto_dualsense4unix.utils.maquina import gravar_rascunho_da_mesa\n"
            "import os\n"
            "ok = gravar_rascunho_da_mesa({'altura_da_antena': 'acima', "
            "'linha_de_visada': 'com_gente'})\n"
            "assert ok is True\n"
            "os._exit(0)\n"
        )
        r1 = _rodar(escrever, env)
        assert r1.returncode == 0, f"stderr do processo que grava: {r1.stderr}"

        ler = (
            "import json\n"
            "from hefesto_dualsense4unix.utils.maquina import carregar_maquina\n"
            "cfg = carregar_maquina()\n"
            "print(json.dumps(cfg.mesa.model_dump(mode='json')))\n"
        )
        r2 = _rodar(ler, env)
        assert r2.returncode == 0, f"stderr do processo que lê: {r2.stderr}"
        mesa = json.loads(r2.stdout.strip().splitlines()[-1])
        assert mesa["altura_da_antena"] == "acima"
        assert mesa["linha_de_visada"] == "com_gente"

    def test_kill_exatamente_no_meio_de_uma_escrita_nao_atomica_trunca(
        self, tmp_path: Path
    ) -> None:
        """Prova que a TÉCNICA de mordida sabe flagrar truncamento — um
        escritor deliberadamente NÃO atômico (marcador + `SIGKILL` na hora
        exata), sem tocar `maquina.py`. É o dublê provando que sabe recusar
        (A2 do COMO-REGER-AGENTES): sem isto, ninguém saberia dizer se a
        verificação MANUAL feita durante a execução desta sprint (arrancar a
        troca atômica de `_escrever`, ver `maquina.json` truncar sob o mesmo
        kill, restaurar — colado no relatório do executor, não em código)
        estava testando alguma coisa de verdade.
        """
        alvo = tmp_path / "alvo.json"
        marcador = tmp_path / "meio.marker"
        payload = json.dumps({"mesa": {"altura_da_antena": "acima"}, "x": "y" * 64})

        script = (
            "import time\n"
            f"payload = {payload!r}\n"
            f"meio = len(payload) // 2\n"
            f"with open({str(alvo)!r}, 'w', encoding='utf-8') as fh:\n"
            "    fh.write(payload[:meio])\n"
            "    fh.flush()\n"
            "    import os as _os\n"
            "    _os.fsync(fh.fileno())\n"
            f"    open({str(marcador)!r}, 'w').close()\n"
            "    time.sleep(5)\n"
            "    fh.write(payload[meio:])\n"
        )
        import os

        proc = subprocess.Popen([sys.executable, "-c", script])
        prazo = time.monotonic() + 5.0
        try:
            while not marcador.exists():
                if time.monotonic() > prazo:
                    pytest.fail("o processo nunca chegou ao meio da escrita")
                time.sleep(0.01)
            proc.kill()
            proc.wait(timeout=5)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
        del os

        conteudo = alvo.read_text(encoding="utf-8")
        assert conteudo == payload[: len(payload) // 2]  # truncado, exatamente na metade
        with pytest.raises(json.JSONDecodeError):
            json.loads(conteudo)
