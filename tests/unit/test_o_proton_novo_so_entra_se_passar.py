"""O Proton novo só entra se passar.

Sprint O-PROTON-NOVO-SO-ENTRA-NO-LUGAR-DO-FIXADO-SE-PASSAR-NAS-PROVAS-01.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import qualificar_proton as qp
from hefesto_dualsense4unix.integrations.proton_pin import parse_pin_conf

RAIZ = Path(__file__).resolve().parents[2]

SCRIPT_DA_FIXADA = '''\
class Session:
    def init_session(self):
        if "sdlinput" in self.compat_config:
            self.env["PROTON_DISABLE_HIDRAW"] = "1"
            if "SDL_GAMECONTROLLER_IGNORE_DEVICES" in self.env:
                del self.env["SDL_GAMECONTROLLER_IGNORE_DEVICES"]
        if "PROTON_USE_XALIA" not in self.env:
            self.env["PROTON_USE_XALIA"] = "1"
'''


def _proton_de_mentira(raiz: Path, script: str = SCRIPT_DA_FIXADA, sem: str = "") -> Path:
    """Uma pasta de Proton com o script e os binários com as strings do contrato."""
    (raiz / "files/lib/wine/x86_64-unix").mkdir(parents=True)
    (raiz / "files/lib/wine/x86_64-windows").mkdir(parents=True)
    (raiz / "proton").write_text(script, encoding="utf-8")
    (raiz / "version").write_text(f"1 {raiz.name}\n", encoding="utf-8")
    conteudos: dict[str, bytes] = {}
    for _comp, arquivos, texto in qp.CONTRATO_DE_STRINGS:
        if f"{arquivos[0]}:{texto}" == sem:
            continue
        # o winebus.sys guarda em UTF-16, como o medido no 11-7
        dado = texto.encode("utf-16-le") if texto == "PROTON_DISABLE_HIDRAW" else texto.encode()
        alvo = arquivos[-1] if texto == "PROTON_DISABLE_HIDRAW" else arquivos[0]
        conteudos[alvo] = conteudos.get(alvo, b"\x00") + dado + b"\x00"
    for relativo, dado in conteudos.items():
        (raiz / "files/lib/wine" / relativo).write_bytes(dado)
    return raiz


ENVS = (
    "SDL_GAMECONTROLLER_IGNORE_DEVICES",
    "PROTON_DISABLE_HIDRAW",
    "PROTON_USE_XALIA",
    "PROTON_SONY_AUTO_XINPUT",
)


def test_a_ficha_da_fixada_passa(tmp_path: Path) -> None:
    fixada = _proton_de_mentira(tmp_path / "GE-Proton11-7")
    f = qp.ficha(fixada, fixada, ENVS)
    assert f.passou, f.faltas
    assert f.mudancas == []


def test_a_ficha_reprova_sem_a_env_do_mhwilds_no_mmdevapi(tmp_path: Path) -> None:
    fixada = _proton_de_mentira(tmp_path / "fixada")
    candidata = _proton_de_mentira(
        tmp_path / "candidata",
        sem="x86_64-windows/mmdevapi.dll:PROTON_ENABLE_MHWILDS_USB_AUDIO",
    )
    f = qp.ficha(candidata, fixada, ENVS)
    assert not f.passou
    assert any("mmdevapi" in falta and "MHWILDS" in falta for falta in f.faltas)


def test_a_ficha_acha_a_string_em_utf16_e_reprova_quando_some(tmp_path: Path) -> None:
    candidata = _proton_de_mentira(
        tmp_path / "c", sem="x86_64-unix/winebus.so:PROTON_DISABLE_HIDRAW"
    )
    f = qp.ficha(candidata, None, ENVS)
    assert any("PROTON_DISABLE_HIDRAW" in falta for falta in f.faltas)


def test_a_ficha_marca_o_del_do_ignore_num_ramo_novo(tmp_path: Path) -> None:
    fixada = _proton_de_mentira(tmp_path / "fixada")
    script = SCRIPT_DA_FIXADA + '''\
        if self.env.get("PROTON_ENABLE_WAYLAND") == "1":
            del self.env["SDL_GAMECONTROLLER_IGNORE_DEVICES"]
        self.env.setdefault("PROTON_SONY_AUTO_XINPUT", "1")
'''
    candidata = _proton_de_mentira(tmp_path / "candidata", script)
    f = qp.ficha(candidata, fixada, ENVS)
    assert f.passou
    assert any(
        "SDL_GAMECONTROLLER_IGNORE_DEVICES apaga" in m and "PROTON_ENABLE_WAYLAND" in m
        for m in f.mudancas
    ), f.mudancas
    assert any("PROTON_SONY_AUTO_XINPUT padrão" in m for m in f.mudancas)
    assert "mudança de ramo" in f.resumo()


def test_a_ficha_reprova_o_proton_da_valve_sem_as_envs_sony(tmp_path: Path) -> None:
    valve = tmp_path / "proton-10"
    (valve / "files/lib/wine/x86_64-unix").mkdir(parents=True)
    (valve / "proton").write_text(SCRIPT_DA_FIXADA, encoding="utf-8")
    f = qp.ficha(valve, None, ENVS)
    assert any("PROTON_KEEP_SONY_AUDIO_ENDPOINT_VISIBLE" in falta for falta in f.faltas)


RECIBO = """\
versão,sha256,ficha,rodada,veredito,prova,data
GE-Proton11-7-x86_64,{a},passou,herdada,passou,,2026-10-16
GE-Proton11-8-x86_64,{b},passou,a háptica não chegou,reprovou,háptica,2026-10-17
"""


def _pino(nome: str, sha: str) -> dict[str, str]:
    return {"name": nome, "url": "u", "sha256": sha}


def test_o_pino_com_versao_sem_a_linha_passou_reprova() -> None:
    recibo = qp.ler_recibo(RECIBO.format(a="a" * 64, b="b" * 64))
    assert qp.o_pino_sem_recibo(_pino("GE-Proton11-7-x86_64", "a" * 64), recibo) == []
    assert qp.o_pino_sem_recibo(_pino("GE-Proton11-8-x86_64", "b" * 64), recibo)
    assert qp.o_pino_sem_recibo(_pino("GE-Proton11-9-x86_64", "c" * 64), recibo)
    # o mesmo nome com outro tarball não passou
    assert qp.o_pino_sem_recibo(_pino("GE-Proton11-7-x86_64", "d" * 64), recibo)


def test_entre_duas_que_passam_fica_a_mais_antiga() -> None:
    texto = RECIBO.format(a="a" * 64, b="b" * 64).replace(
        "a háptica não chegou,reprovou,háptica", "passou,passou,"
    )
    recibo = qp.ler_recibo(texto)
    assert qp.a_minima_que_passa(recibo) == "GE-Proton11-7-x86_64"
    assert qp.o_pino_sem_recibo(_pino("GE-Proton11-8-x86_64", "b" * 64), recibo)


def test_o_pino_desta_casa_tem_o_recibo_passou() -> None:
    """A régua do pino, no repositório: o pino de hoje tem a linha «passou»."""
    pino = parse_pin_conf((RAIZ / "assets/proton-pin.conf").read_text(encoding="utf-8"))
    recibo = qp.ler_recibo((RAIZ / "docs/data/proton-qualificacao.csv").read_text(encoding="utf-8"))
    assert qp.o_pino_sem_recibo(pino, recibo) == []


def test_a_linha_do_recibo_so_passa_com_a_ficha_e_a_rodada() -> None:
    f = qp.Ficha(versao="GE-Proton11-8-x86_64")
    assert ",passou,passou,," in qp.linha_do_recibo(f, "b" * 64, "passou", "2026-10-17")
    assert ",reprovou," in qp.linha_do_recibo(f, "b" * 64, "gatilho", "2026-10-17")
    f.faltas.append("winepulse: sem Speaker__sink")
    assert ",reprovou," in qp.linha_do_recibo(f, "b" * 64, "passou", "2026-10-17")


def _rodada():
    caminho = RAIZ / "scripts/ensaios/a_rodada_do_proton_candidato.py"
    spec = importlib.util.spec_from_file_location("a_rodada_do_proton_candidato", caminho)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def test_a_rodada_recusa_fora_da_vm_e_do_ci() -> None:
    r = _rodada()
    assert not r.na_vm_ou_no_ci({}, ("sh", "-c", "echo none; exit 1"))
    assert r.na_vm_ou_no_ci({}, ("sh", "-c", "echo kvm"))
    assert r.na_vm_ou_no_ci({"CI": "true"}, ("false",))


def test_a_matriz_cobre_vpads_transportes_mascaras_e_wayland() -> None:
    casos = _rodada().matriz()
    assert len(casos) == 2 * 2 * 3 * 2
    assert {c.mascara for c in casos} == {"dualsense", "xbox", "nintendo"}


@pytest.mark.parametrize(
    ("estrago", "prova"),
    [
        ("canais", "háptica sem endpoint"),
        ("eco", "não chegou aos canais 3-4"),
        ("gatilho", "chegou diferente"),
        ("tom", "microfone"),
        ("ks", "devices KS"),
    ],
)
def test_a_rodada_julga_cada_prova(estrago: str, prova: str) -> None:
    """A mordida da rodada: cada prova estragada reprova, e a inteira passa."""
    r = _rodada()
    caso = r.Caso(1, "cabo", "dualsense", False)
    saida = "\n".join([
        '{"prova":"contagem","hid_sony":1,"ks_por_container":{"c1":'
        + str(2 if estrago == "ks" else 1) + "}}",
        '{"prova":"haptica","achou":true,"canais":'
        + str(2 if estrago == "canais" else 4) + ',"tocou":true}',
        '{"prova":"gatilho","escreveu":true,"bytes":"0204"}',
        '{"prova":"microfone","achou":true,"fracao_no_tom":0.9}',
        '{"prova":"fim","container_sony":"c1"}',
    ])
    lado = r.MedidaDoOutroLado(
        eco_rl_rr=0.1 if estrago == "eco" else 0.9,
        bytes_no_uhid="0205" if estrago == "gatilho" else "0204",
        tom_posto=estrago != "tom",
    )
    falhas = r.julgar(caso, r.ler_sonda(saida), lado)
    assert any(prova in f for f in falhas), falhas


def test_a_rodada_inteira_passa() -> None:
    r = _rodada()
    saida = "\n".join([
        '{"prova":"contagem","hid_sony":1,"ks_por_container":{"c1":1}}',
        '{"prova":"haptica","achou":true,"canais":4,"tocou":true}',
        '{"prova":"gatilho","escreveu":true,"bytes":"0204"}',
        '{"prova":"microfone","achou":true,"fracao_no_tom":0.9}',
        '{"prova":"fim","container_sony":"c1"}',
    ])
    caso = r.Caso(1, "cabo", "dualsense", False)
    assert r.julgar(caso, r.ler_sonda(saida), r.MedidaDoOutroLado(0.9, "0204", True)) == []
