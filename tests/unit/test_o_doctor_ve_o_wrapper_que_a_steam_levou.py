"""O contrato `steam-localconfig` também pergunta: o wrapper que o Hefesto pôs ainda está lá?

A-STEAM-E-OS-LANCADORES-SEM-ARQUIVO-INTERNO-01, 07/10/2026. A Steam é dona do `localconfig.vdf` e já
apagou o `hefesto-launch` de um jogo sem aviso (17/09). Não há API para a Opção de Lançamento: a
cura é converger pelo estado lido (repor e reler) e o doctor nomear o CONTRATO que quebrou. A prova
usa o registro da sentinela (`wrapper-visto.json`) num lar de mentira, em `tmp_path`.
"""
from __future__ import annotations

from pathlib import Path

from hefesto_dualsense4unix.integrations import contratos_de_fora as cf
from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sen
from hefesto_dualsense4unix.integrations import steam_launch_options as slo

_T = "\t"


def _vdf(apps: dict[str, str]) -> str:
    blocos = "".join(
        f'{_T * 5}"{a}"\n{_T * 5}{{\n{_T * 6}"LaunchOptions"{_T * 2}"{v}"\n{_T * 5}}}\n'
        for a, v in apps.items()
    )
    return (
        '"UserLocalConfigStore"\n{\n'
        f'{_T}"Software"\n{_T}{{\n{_T * 2}"Valve"\n{_T * 2}{{\n{_T * 3}"Steam"\n{_T * 3}{{\n'
        f'{_T * 4}"apps"\n{_T * 4}{{\n{blocos}{_T * 4}}}\n{_T * 3}}}\n{_T * 2}}}\n{_T}}}\n}}\n'
    )


def _lar(tmp_path: Path, apps: dict[str, str], vistos: list[str]) -> cf.Ambiente:
    casa = tmp_path / "home"
    conf = casa / ".steam/steam/userdata/1/config/localconfig.vdf"
    conf.parent.mkdir(parents=True)
    conf.write_text(_vdf(apps), encoding="utf-8")
    sen.gravar_registro(vistos, home=casa)
    return cf.Ambiente(
        rodar=lambda argv: cf.Falta("sem a ferramenta"),
        home=casa,
        env={},
        raiz=tmp_path / "raiz",
    )


def _linha(amb: cf.Ambiente) -> tuple[str, str]:
    ((tag, msg),) = cf.linhas_do_doctor(
        amb, [c for c in cf.CONTRATOS if c.id == "steam-localconfig"]
    )
    return tag, msg


def test_jogo_visto_com_wrapper_que_voltou_sem_ele_quebra_o_contrato(tmp_path: Path) -> None:
    amb = _lar(tmp_path, {"620": "MANGOHUD=1 %command%"}, vistos=["620"])

    tag, msg = _linha(amb)

    assert tag == "[WARN]"
    assert "steam-localconfig" in msg and "620" in msg
    assert "grep -c hefesto-launch" in msg


def test_jogo_que_ainda_tem_o_wrapper_e_ok(tmp_path: Path) -> None:
    com_wrapper = slo._vdf_escape(slo.WRAPPER_PREFIX + " %command%")
    amb = _lar(tmp_path, {"620": com_wrapper}, vistos=["620"])

    assert _linha(amb)[0] == "[ OK ]"


def test_jogo_nunca_visto_com_wrapper_nao_e_regressao(tmp_path: Path) -> None:
    amb = _lar(tmp_path, {"620": "%command%"}, vistos=[])

    assert _linha(amb)[0] == "[ OK ]"


def test_jogo_que_ela_recusou_nao_e_regressao(tmp_path: Path) -> None:
    amb = _lar(tmp_path, {"620": "%command%"}, vistos=["620"])
    slo.marcar_jogo_sem_wrapper(620, path=slo.sem_wrapper_path(amb.home / ".config"))

    assert _linha(amb)[0] == "[ OK ]"


def test_leitura_sem_nenhum_app_nao_conclui_nada(tmp_path: Path) -> None:
    amb = _lar(tmp_path, {}, vistos=["620"])

    assert _linha(amb)[0] == "[ OK ]"


def test_linha_com_o_par_estendido_nao_e_regressao(tmp_path: Path) -> None:
    """A pergunta é a da sentinela: a linha que ela chama de intocável não vira contrato quebrado.

    MORDIDA: volte a sonda a uma regra própria (``WRAPPER_PREFIX not in valor``) e este reprova.
    """
    estendida = 'SDL_GAMECONTROLLER_IGNORE_DEVICES="0x054c/0x0ce6,0x057e/0x2009" %command%'
    amb = _lar(tmp_path, {"620": slo._vdf_escape(estendida)}, vistos=["620"])

    assert _linha(amb)[0] == "[ OK ]"


def test_a_recusa_mora_onde_o_xdg_config_home_diz(tmp_path: Path) -> None:
    amb = _lar(tmp_path, {"620": "%command%"}, vistos=["620"])
    config = tmp_path / "config-noutro-lugar"
    slo.marcar_jogo_sem_wrapper(620, path=slo.sem_wrapper_path(config))
    amb = cf.Ambiente(
        rodar=amb.rodar, home=amb.home, env={"XDG_CONFIG_HOME": str(config)}, raiz=amb.raiz
    )

    assert _linha(amb)[0] == "[ OK ]"


def test_o_registro_mora_onde_o_xdg_state_home_diz(tmp_path: Path) -> None:
    amb = _lar(tmp_path, {"620": "%command%"}, vistos=[])
    estado = tmp_path / "estado-noutro-lugar"
    sen.gravar_registro(["620"], path=estado / "hefesto-dualsense4unix" / sen.REGISTRO_BASENAME)
    amb = cf.Ambiente(
        rodar=amb.rodar, home=amb.home, env={"XDG_STATE_HOME": str(estado)}, raiz=amb.raiz
    )

    tag, msg = _linha(amb)

    assert tag == "[WARN]"
    assert "620" in msg
