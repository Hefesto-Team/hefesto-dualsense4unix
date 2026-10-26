"""O device KS do Hefesto não duplica o do Proton.

Sprint O-DEVICE-KS-DO-HEFESTO-NAO-DUPLICA-O-DO-PROTON-01. O GE-Proton11-8 (patch
0206) registra o MEDIA dos caminhos Sony com a mesma env que o Hefesto liga em
todo jogo: um dono por `ContainerId`, e quem já existe é o dono. O `system.reg`
de mentira tem a forma que o `setupapi` do Wine grava (`SetupDiCreateDeviceInfoW`
com a classe MEDIA e o `SPDRP_BASE_CONTAINERID` em minúsculas).
"""
from __future__ import annotations

from pathlib import Path

from hefesto_dualsense4unix.integrations import audio_ks_dualsense as ks

CABECALHO = "WINE REGISTRY Version 2\n;; All keys relative to \\\\Machine\n\n#arch=win64\n"
CABO = ks.Controle(pid=0x0CE6, bus=3, dev=28, usec=None)
OUTRO = ks.Controle(pid=0x0CE6, bus=3, dev=29, usec=None)


def _media_do_proton(controle: ks.Controle, inst: str = "5&1a2b3c4d&0&1") -> str:
    """O bloco que o 0206 grava para um DualSense, com o `ContainerId` dele."""
    chave = f"System\\\\ControlSet001\\\\Enum\\\\USB\\\\VID_054C&PID_{controle.pid:04X}\\\\{inst}"
    return (
        f"[{chave}] 1791398341\n"
        '"Class"="MEDIA"\n'
        f'"ClassGUID"="{ks.CLASSE_MEDIA.lower()}"\n'
        f'"ContainerId"="{ks.container_id(controle, bytes(8)).lower()}"\n'
        '"FriendlyName"="DualSense Wireless Controller"\n'
    )


def _nossos(texto: str) -> int:
    return sum(1 for b in ks._blocos(texto) if ks.e_bloco_nosso(b))


def test_sem_o_media_do_proton_o_hefestoks_e_escrito_como_hoje() -> None:
    novo = ks.texto_novo(CABECALHO, [CABO], 1)
    assert _nossos(novo) == 4
    assert "HEFESTOKS&003&028&0" in novo


def test_com_o_media_do_proton_no_mesmo_container_o_nosso_nao_e_escrito_e_o_antigo_sai() -> None:
    """MORDIDA: tire a leitura do MEDIA, e o mesmo ContainerId fica com dois devices.

    Prova da D-1610-O-KS-NAO-DUPLICA-O-MEDIA-DO-PROTON.
    """
    com_o_nosso = ks.texto_novo(CABECALHO, [CABO], 1)
    assert _nossos(com_o_nosso) > 0
    depois = ks.texto_novo(com_o_nosso + "\n" + _media_do_proton(CABO), [CABO], 2)
    assert _nossos(depois) == 0
    assert "HEFESTOKS" not in depois
    assert depois.count(ks.container_id(CABO, bytes(8)).lower()) == 1


def test_com_o_media_de_outro_container_o_nosso_e_escrito() -> None:
    texto = CABECALHO + "\n" + _media_do_proton(OUTRO)
    novo = ks.texto_novo(texto, [CABO], 1)
    assert "HEFESTOKS&003&028&0" in novo
    assert ks.controles_que_o_proton_cria(novo, [CABO, OUTRO]) == [OUTRO]


def test_o_media_velho_de_um_aparelho_que_saiu_nao_e_dono() -> None:
    """O 0207 guarda o endpoint Sony persistido: o Data4 de quem saiu não manda."""
    presente = ks.Controle(pid=0x0CE6, bus=3, dev=28, usec=222)
    velho = ks.container_id(presente, (111).to_bytes(8, "little")).lower()
    bloco = _media_do_proton(CABO).replace(ks.container_id(CABO, bytes(8)).lower(), velho)
    novo = ks.texto_novo(CABECALHO + "\n" + bloco, [presente], 1)
    assert "HEFESTOKS&003&028&" in novo


def test_o_usb_sem_classe_media_nao_e_o_proton() -> None:
    """O nosso próprio bloco (classe USB) não se confunde com o do Proton."""
    texto = ks.texto_novo(CABECALHO, [CABO], 1)
    assert ks.containers_do_proton(texto) == set()


def test_aplicar_diz_que_o_proton_ja_cria(tmp_path: Path) -> None:
    pfx = tmp_path / "pfx"
    pfx.mkdir()
    (pfx / "system.reg").write_text(CABECALHO + "\n" + _media_do_proton(CABO), encoding="utf-8")
    resultado = ks.aplicar(tmp_path, controles=[CABO, OUTRO], proc=tmp_path / "proc", carimbo=1)
    assert resultado.do_proton == 1
    texto = (pfx / "system.reg").read_text(encoding="utf-8")
    assert "HEFESTOKS&003&029&0" in texto
    assert "HEFESTOKS&003&028" not in texto
