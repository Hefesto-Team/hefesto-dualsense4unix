"""CONSELHO-QUE-NAO-CURA-01 — três avisos do doctor mandavam fazer o que não"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from hefesto_dualsense4unix.integrations.proton_pin import parse_pin_conf as _pin_conf

ROOT = Path(__file__).resolve().parents[2]
DOCTOR = ROOT / "scripts" / "doctor.sh"

_CONF_DO_PINO = _pin_conf(
    (ROOT / "assets" / "proton-pin.conf").read_text(encoding="utf-8")
)
NOME_DO_PIN = _CONF_DO_PINO["name"]
SHA_DO_PIN = _CONF_DO_PINO["sha256"]

WRAPPER = slo.WRAPPER_PREFIX


def _config_vdf(por_jogo: dict[str, str], *, glob: str = NOME_DO_PIN) -> str:
    """`config.vdf` mínimo com CompatToolMapping (global + entradas por jogo)."""
    entradas = ""
    for appid, tool in {"0": glob, **por_jogo}.items():
        entradas += (
            f'\t\t\t\t\t"{appid}"\n\t\t\t\t\t{{\n'
            f'\t\t\t\t\t\t"name"\t\t"{tool}"\n'
            f'\t\t\t\t\t\t"config"\t\t""\n'
            f'\t\t\t\t\t\t"priority"\t\t"250"\n'
            "\t\t\t\t\t}\n"
        )
    return (
        '"InstallConfigStore"\n{\n\t"Software"\n\t{\n\t\t"Valve"\n\t\t{\n'
        '\t\t\t"Steam"\n\t\t\t{\n\t\t\t\t"CompatToolMapping"\n\t\t\t\t{\n'
        f"{entradas}"
        "\t\t\t\t}\n\t\t\t}\n\t\t}\n\t}\n}\n"
    )


def _lar_do_proton(
    tmp_path: Path,
    *,
    manifesto: str,
    por_jogo: dict[str, str] | None = None,
    registro: dict[str, dict[str, str]] | None = None,
) -> Path:
    """Um ``HOME`` de mentira com Steam nativa, o pin extraído e o registro."""
    lar = tmp_path / "lar"
    raiz = lar / ".steam/steam"
    (raiz / "config").mkdir(parents=True)
    (raiz / "steamapps").mkdir(parents=True)

    alvo = raiz / "compatibilitytools.d" / NOME_DO_PIN
    alvo.mkdir(parents=True)
    (alvo / "proton").write_text("#!/bin/sh\n", encoding="utf-8")
    (alvo / "version").write_text("1 mentira\n", encoding="utf-8")
    dentro = alvo / ".hefesto-proton-pin.json"
    if manifesto == "ok":
        dentro.write_text(
            json.dumps({"name": NOME_DO_PIN, "sha256": SHA_DO_PIN}), encoding="utf-8"
        )
    elif manifesto == "divergente":
        dentro.write_text(
            json.dumps({"name": NOME_DO_PIN, "sha256": "00" * 32}), encoding="utf-8"
        )
    elif manifesto == "corrompido":
        dentro.write_text('{"name": "GE-Proton10-34", "sha256"', encoding="utf-8")
    elif manifesto != "ausente":  # pragma: no cover - erro de quem escreve teste
        raise ValueError(manifesto)

    for appid, nome in (("2497900", "DON'T SCREAM"), ("316790", "Grim Fandango")):
        (raiz / "steamapps" / f"appmanifest_{appid}.acf").write_text(
            f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"{nome}"\n}}\n',
            encoding="utf-8",
        )
    (raiz / "config" / "config.vdf").write_text(
        _config_vdf(por_jogo or {}), encoding="utf-8"
    )

    estado = lar / ".local/state/hefesto-dualsense4unix"
    estado.mkdir(parents=True)
    (estado / "proton-pin-lock.json").write_text(
        json.dumps({"tool_name": NOME_DO_PIN, "changes": registro or {}}),
        encoding="utf-8",
    )
    return lar


def _rodar(funcao: str, lar: Path) -> str:
    res = subprocess.run(
        ["bash", "-c", f'source "$DOCTOR_SH"; {funcao}'],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env={
            "DOCTOR_SH": str(DOCTOR),
            "HOME": str(lar),
            "XDG_STATE_HOME": str(lar / ".local/state"),
            "XDG_CACHE_HOME": str(lar / ".cache"),
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "LC_ALL": "C.UTF-8",
            "NO_COLOR": "1",
        },
    )
    return res.stdout + res.stderr


def _mensagem(saida: str, frase: str) -> tuple[str, str]:
    """``(rótulo, linha)`` da mensagem que contém `frase`."""
    for linha in saida.splitlines():
        if frase not in linha:
            continue
        for rotulo in ("[ OK ]", "[WARN]", "[FAIL]"):
            if linha.startswith(rotulo):
                return rotulo, linha
        return ("[INFO]" if linha.startswith("       ") else "?"), linha
    raise AssertionError(f"frase ausente da saída: {frase!r}\n{saida}")


class TestOManifestoAusenteNaoPedeOInstaladorDeNovo:
    def test_manifesto_ausente_nao_manda_rodar_o_install(self, tmp_path: Path) -> None:
        saida = _rodar("check_proton_pin", _lar_do_proton(tmp_path, manifesto="ausente"))
        assert "por FORA do hefesto" in saida, saida
        assert "rodar o instalador de novo não muda isto" in saida, saida
        assert "o manifesto do hefesto não bate" not in saida, saida

    def test_manifesto_ausente_nao_e_alarme(self, tmp_path: Path) -> None:
        """Estado criado DE PROPÓSITO pelo produto não é alarme."""
        saida = _rodar("check_proton_pin", _lar_do_proton(tmp_path, manifesto="ausente"))
        rotulo, linha = _mensagem(saida, "por FORA do hefesto")
        assert rotulo == "[INFO]", linha

    def test_manifesto_divergente_continua_mandando_rodar_o_install(
        self, tmp_path: Path
    ) -> None:
        """O NEGATIVO: onde o install CURA, o conselho tem de continuar lá."""
        saida = _rodar(
            "check_proton_pin", _lar_do_proton(tmp_path, manifesto="divergente")
        )
        rotulo, linha = _mensagem(saida, "OUTRO sha256")
        assert rotulo == "[WARN]", linha
        assert "install.sh" in linha, linha

    def test_manifesto_batendo_continua_passando(self, tmp_path: Path) -> None:
        saida = _rodar("check_proton_pin", _lar_do_proton(tmp_path, manifesto="ok"))
        assert "presente e íntegro" in saida, saida

    def test_manifesto_ilegivel_diz_que_o_install_nao_resolve(
        self, tmp_path: Path
    ) -> None:
        saida = _rodar(
            "check_proton_pin", _lar_do_proton(tmp_path, manifesto="corrompido")
        )
        assert "trata isso como 'sem manifesto'" in saida, saida


class TestOJogoForaDoPinTemNomeERazao:
    def test_o_preservado_de_antes_da_ordem_volta_a_ser_aviso_com_o_fix(
        self, tmp_path: Path
    ) -> None:
        """FATO QUE CAIU, SUBSTITUÍDO — 18/09/2026."""
        lar = _lar_do_proton(
            tmp_path,
            manifesto="ok",
            por_jogo={"2497900": "proton_11"},
            registro={
                "2497900": {"action": "preservado", "previous_name": "proton_11"}
            },
        )
        saida = _rodar("check_proton_pin", lar)
        rotulo, linha = _mensagem(saida, "em outro Proton")
        assert rotulo == "[WARN]", linha
        assert "DON'T SCREAM" in linha, linha
        assert "proton_11" in linha, linha
        assert "doctor.sh --fix" in linha, linha
        assert "ESCOLHA SUA" not in saida, saida
        assert "Não há o que consertar" not in saida, saida
        assert "1 jogo(s) fora do Proton pinado" not in saida, saida

    def test_sem_registro_de_escolha_continua_alarmando_com_o_nome(
        self, tmp_path: Path
    ) -> None:
        """O NEGATIVO: sem prova de que foi escolha dela, o alarme fica."""
        lar = _lar_do_proton(
            tmp_path, manifesto="ok", por_jogo={"2497900": "proton_11"}, registro={}
        )
        saida = _rodar("check_proton_pin", lar)
        rotulo, linha = _mensagem(saida, "em outro Proton")
        assert rotulo == "[WARN]", linha
        assert "DON'T SCREAM" in linha, linha

    def test_tudo_no_pin_continua_passando(self, tmp_path: Path) -> None:
        lar = _lar_do_proton(tmp_path, manifesto="ok", por_jogo={})
        saida = _rodar("check_proton_pin", lar)
        assert "todos os jogos travados no Proton pinado" in saida, saida


_TAB = "\t"


def _bloco_apps(nivel: int, itens: dict[str, str]) -> str:
    dentro = ""
    for appid, valor in itens.items():
        dentro += (
            f'{_TAB * (nivel + 1)}"{appid}"\n{_TAB * (nivel + 1)}{{\n'
            f'{_TAB * (nivel + 2)}"LaunchOptions"{_TAB * 2}"{slo._vdf_escape(valor)}"\n'
            f"{_TAB * (nivel + 1)}}}\n"
        )
    return f'{_TAB * nivel}"apps"\n{_TAB * nivel}{{\n{dentro}{_TAB * nivel}}}\n'


def _lar_do_wrapper(
    tmp_path: Path, *, viva: dict[str, str], solta: dict[str, str]
) -> Path:
    lar = tmp_path / "lar"
    destino = lar / ".steam/steam/userdata/1/config"
    destino.mkdir(parents=True)
    corpo = (
        f'{_TAB}"Software"\n{_TAB}{{\n'
        f'{_TAB * 2}"Valve"\n{_TAB * 2}{{\n'
        f'{_TAB * 3}"Steam"\n{_TAB * 3}{{\n'
        f"{_bloco_apps(4, viva)}"
        f"{_TAB * 3}}}\n{_TAB * 2}}}\n{_TAB}}}\n"
    )
    corpo += _bloco_apps(1, solta)
    (destino / "localconfig.vdf").write_text(
        '"UserLocalConfigStore"\n{\n' + corpo + "}\n", encoding="utf-8"
    )
    return lar


class TestASobraForaDaArvoreViva:
    def test_sobra_sem_wrapper_nao_e_acusada_de_ser_nossa(self, tmp_path: Path) -> None:
        """O retrato do vdf dela: o órfão carrega a linha VKD3D, não a nossa."""
        lar = _lar_do_wrapper(
            tmp_path,
            viva={"316790": f"{WRAPPER} %command%"},
            solta={"413080": "VKD3D_CONFIG=no_upload_hvv %command%"},
        )
        saida = _rodar("check_arvore_canonica_do_wrapper", lar)
        rotulo, linha = _mensagem(saida, "sobra inerte")
        assert rotulo == "[INFO]", linha
        assert "NÃO carrega a nossa chamada do wrapper" in linha, linha
        assert "escritas por nós" not in saida, saida
        assert "o censo as conta como cobertura" not in saida, saida
        assert "falso conforto" not in saida, saida

    def test_sobra_com_o_wrapper_continua_sendo_acusada(self, tmp_path: Path) -> None:
        """O NEGATIVO: lixo nosso de verdade tem de continuar aparecendo."""
        lar = _lar_do_wrapper(
            tmp_path,
            viva={"316790": f"{WRAPPER} %command%"},
            solta={"413080": f"{WRAPPER} %command%"},
        )
        saida = _rodar("check_arvore_canonica_do_wrapper", lar)
        rotulo, linha = _mensagem(saida, "NOSSAS")
        assert rotulo == "[WARN]", linha
        assert "--recolher-fora-da-arvore-viva" in linha, linha

    def test_a_arvore_viva_intacta_continua_passando(self, tmp_path: Path) -> None:
        lar = _lar_do_wrapper(
            tmp_path, viva={"316790": f"{WRAPPER} %command%"}, solta={}
        )
        saida = _rodar("check_arvore_canonica_do_wrapper", lar)
        assert "chamam o wrapper" in saida, saida
        assert "sobra inerte" not in saida, saida


INSTALL = ROOT / "install.sh"
MARCADOR = "instalação pré-existente sem manifesto"


class TestOLacoEntreOInstallEOAviso:
    def test_ensure_mantem_a_instalacao_de_fora_e_nao_grava_manifesto(
        self, tmp_path: Path
    ) -> None:
        """A causa do laço, exercitada de verdade (sem rede, sem cache)."""
        from hefesto_dualsense4unix.integrations import proton_pin as pp

        compat = tmp_path / "compatibilitytools.d"
        alvo = compat / NOME_DO_PIN
        alvo.mkdir(parents=True)
        (alvo / "proton").write_text("#!/bin/sh\n", encoding="utf-8")
        (alvo / "version").write_text("1 mentira\n", encoding="utf-8")
        conf = {"name": NOME_DO_PIN, "url": "http://exemplo.invalido", "sha256": SHA_DO_PIN}

        for volta in (1, 2):
            resultado = pp.ensure_pinned_proton(
                conf,
                compat_dir=compat,
                cache_dir=tmp_path / "cache",
                downloader=None,
            )
            assert resultado.state == "already", (volta, resultado)
            assert MARCADOR in resultado.detail, (volta, resultado)
            assert not (alvo / pp.MANIFEST_BASENAME).exists(), volta
            relatorio = pp.proton_pin_report(
                conf, compat_dir=compat, config_vdf_text="", installed_appids=[]
            )
            assert relatorio["pinned_present"] is True, volta
            assert relatorio["pinned_manifest_ok"] is False, volta

    def test_o_install_procura_o_marcador_que_o_modulo_emite(self) -> None:
        """A frase é CONTRATO entre `proton_pin.py` e o passo 11c do install."""
        assert MARCADOR in INSTALL.read_text(encoding="utf-8")
        assert MARCADOR in (ROOT / "src/hefesto_dualsense4unix/integrations"
                            "/proton_pin.py").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "morta",
    [
        "o censo as conta como cobertura",
        "é delas que vem o falso conforto do censo",
    ],
)
def test_as_frases_derrubadas_sairam_do_fonte(morta: str) -> None:
    """Fato errado se SUBSTITUI, e sai de TODOS os lugares (regra da casa)."""
    vivas = [
        ln
        for ln in DOCTOR.read_text(encoding="utf-8").splitlines()
        if not ln.lstrip().startswith("#")
    ]
    culpadas = [ln for ln in vivas if morta in ln]
    assert not culpadas, culpadas
