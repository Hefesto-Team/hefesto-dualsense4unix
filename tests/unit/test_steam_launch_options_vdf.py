"""DEDUP-05/UX-04: migração e strip das LaunchOptions no localconfig.vdf."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from hefesto_dualsense4unix.integrations import steam_launch_options as slo

LINHA_914 = (
    "SDL_JOYSTICK_HIDAPI=0 SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6 "
    "__GL_SHADER_DISK_CACHE=1 __GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1 %command%"
)

_TAB = "\t"


def _vdf(launch_options: dict[str, str]) -> str:
    """Monta um localconfig.vdf mínimo com um app por (appid -> LaunchOptions)."""
    blocos = []
    for appid, valor in launch_options.items():
        blocos.append(
            f'{_TAB * 5}"{appid}"\n{_TAB * 5}{{\n'
            f'{_TAB * 6}"LaunchOptions"{_TAB * 2}"{valor}"\n'
            f'{_TAB * 6}"playtime"{_TAB * 2}"42"\n'
            f"{_TAB * 5}}}\n"
        )
    apps = "".join(blocos)
    return (
        '"UserLocalConfigStore"\n{\n'
        f'{_TAB}"Software"\n{_TAB}{{\n'
        f'{_TAB * 2}"Valve"\n{_TAB * 2}{{\n'
        f'{_TAB * 3}"Steam"\n{_TAB * 3}{{\n'
        f'{_TAB * 4}"apps"\n{_TAB * 4}{{\n'
        f"{apps}"
        f"{_TAB * 4}}}\n{_TAB * 3}}}\n{_TAB * 2}}}\n{_TAB}}}\n}}\n"
    )


def test_migrate_linha_914_vira_a_string_constante_do_wrapper():
    """O veneno inteiro (assinatura + co-ocorrentes + preload) sai e entra a"""
    assert slo.migrate_value(LINHA_914) == slo.WRAPPER_LAUNCH


def test_migrate_preserva_opcoes_genuinas_do_usuario():
    valor = f"MANGOHUD=1 {LINHA_914}"
    migrado = slo.migrate_value(valor)
    assert migrado == f"{slo.WRAPPER_PREFIX} MANGOHUD=1 %command%"
    assert slo.IGNORE_SIGNATURE not in migrado


def test_migrate_sem_command_explicita_o_placeholder():
    """LaunchOptions sem %command% são ARGUMENTOS do jogo — a migração"""
    valor = f"{slo.IGNORE_SIGNATURE} -fullscreen"
    migrado = slo.migrate_value(valor)
    assert migrado == f"{slo.WRAPPER_LAUNCH} -fullscreen"


def test_migrate_e_idempotente():
    uma_vez = slo.migrate_value(LINHA_914)
    assert slo.migrate_value(uma_vez) == uma_vez


def test_strip_da_linha_914_preserva_shader_cache_byte_a_byte():
    """UX-04 (uninstall): sai a assinatura + SDL_JOYSTICK_HIDAPI=0"""
    assert slo.strip_value(LINHA_914) == (
        "__GL_SHADER_DISK_CACHE=1 __GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1 %command%"
    )


def test_strip_nao_caca_hidapi_solto():
    """SDL_JOYSTICK_HIDAPI=0 SEM a assinatura é fix legítimo de controle de"""
    valor = "SDL_JOYSTICK_HIDAPI=0 %command%"
    assert slo.strip_value(valor) == valor


def test_strip_remove_o_wrapper_e_colapsa_linha_que_era_so_nossa():
    assert slo.strip_value(slo.WRAPPER_LAUNCH) == ""


LINHA_ESTENDIDA = (
    "SDL_JOYSTICK_HIDAPI=0 "
    "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6,0x057e/0x2009 %command%"
)

#: DualSense dela, com a tela dizendo que o atalho estava no lugar.
LINHA_NOSSO_PAR_EM_SEGUNDO = (
    "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x057e/0x2009,0x054c/0x0ce6 %command%"
)

LINHA_FORA_DO_ALCANCE = (
    'SDL_GAMECONTROLLER_IGNORE_DEVICES="0x054c/0x0ce6,0x057e/0x2009" %command%'
)


def test_a_subtracao_tira_o_nosso_par_e_deixa_o_dela():
    """O par sai de dentro da lista; a vírgula que sobraria é comida."""
    assert slo.subtrair_nosso_ignore(LINHA_ESTENDIDA) == (
        "SDL_JOYSTICK_HIDAPI=0 "
        "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x057e/0x2009 %command%"
    )


def test_a_subtracao_alcanca_o_nosso_par_em_qualquer_posicao():
    """No fim da lista e no MEIO dela — a assinatura colada não via nenhum."""
    assert slo.subtrair_nosso_ignore(LINHA_NOSSO_PAR_EM_SEGUNDO) == (
        "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x057e/0x2009 %command%"
    )
    no_meio = ("SDL_GAMECONTROLLER_IGNORE_DEVICES="
               "0x057e/0x2009,0x054c/0x0ce6,0x28de/0x1205 %command%")
    assert slo.subtrair_nosso_ignore(no_meio) == (
        "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x057e/0x2009,0x28de/0x1205 %command%"
    )


def test_a_lista_que_fica_vazia_leva_a_atribuicao_inteira():
    """`VAR=` pendurado é resíduo — a mesma regra do `%command%` órfão."""
    assert slo.subtrair_nosso_ignore(
        "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6 %command%"
    ) == "%command%"


def test_a_subtracao_devolve_byte_a_byte_a_linha_que_nao_e_nossa():
    for valor in (
        "MANGOHUD=1 %command%",
        "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x057e/0x2009 %command%",
        "SDL_JOYSTICK_HIDAPI=0 %command%",
        LINHA_FORA_DO_ALCANCE,
    ):
        assert slo.subtrair_nosso_ignore(valor) == valor, valor


def test_migrate_subtrai_o_nosso_par_da_lista_estendida():
    """ERA `test_migrate_nao_toca_lista_ignore_estendida`, e ele assertava o"""
    migrado = slo.migrate_value(LINHA_ESTENDIDA)
    assert migrado.startswith(slo.WRAPPER_PREFIX + " ")
    assert "0x057e/0x2009" in migrado, "o device que ELA escondeu foi jogado fora"
    assert "0x054c/0x0ce6" not in migrado, "o nosso par continua envenenando a linha"


def test_migrate_nao_embrulha_o_que_nao_alcanca():
    """A metade da razão antiga que NÃO caiu: embrulhar com o veneno vivo"""
    assert slo.migrate_value(LINHA_FORA_DO_ALCANCE) == LINHA_FORA_DO_ALCANCE


def test_migrate_ve_o_nosso_par_mesmo_quando_ele_nao_e_o_primeiro():
    """O buraco do Passo 5: `has_poison` e `has_extended_ignore` diziam os dois"""
    migrado = slo.migrate_value(LINHA_NOSSO_PAR_EM_SEGUNDO)
    assert migrado.startswith(slo.WRAPPER_PREFIX + " ")
    assert "0x054c/0x0ce6" not in migrado
    assert "0x057e/0x2009" in migrado


def test_strip_subtrai_o_nosso_par_da_lista_estendida():
    """ERA `test_strip_nao_toca_lista_ignore_estendida`. A razão de virar é a
    DESINSTALAÇÃO: o nosso par ficava na lista dela para sempre, e sem o
    wrapper aquele par manda o jogo ignorar o DualSense FÍSICO dela."""
    assert slo.strip_value(LINHA_ESTENDIDA) == (
        "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x057e/0x2009 %command%"
    )


def _sem_o_atalho(valor: str) -> str:
    """O valor sem a chamada do wrapper — para tokenizar o que sobra."""
    return valor.replace(slo.WRAPPER_PREFIX, "", 1).strip()


def test_nenhum_caminho_deixa_fragmento_sem_igual_pendurado():
    """A regressão exata reproduzida pela revisão: `,0x057e/0x2009` órfão."""
    fontes = (
        LINHA_ESTENDIDA,
        LINHA_NOSSO_PAR_EM_SEGUNDO,
        "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x057e/0x2009,0x054c/0x0ce6,0x28de/0x1205 %command%",
        "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6 %command%",
        "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6,0x057e/0x2009 VKD3D_CONFIG=dxr %command%",
        LINHA_914,
    )
    for fonte in fontes:
        for resultado in (
            slo.subtrair_nosso_ignore(fonte),
            _sem_o_atalho(slo.migrate_value(fonte)),
            _sem_o_atalho(slo.strip_value(fonte)),
        ):
            for token in resultado.split():
                assert token == "%command%" or "=" in token, (fonte, resultado)


def test_has_poison_ve_o_nosso_par_em_qualquer_posicao():
    """ERA `test_has_poison_exige_token_completo`, e o que ele exigia era o"""
    assert slo.has_poison(LINHA_914) is True
    assert slo.has_poison(LINHA_ESTENDIDA) is True
    assert slo.has_poison(LINHA_NOSSO_PAR_EM_SEGUNDO) is True
    assert slo.has_poison(LINHA_FORA_DO_ALCANCE) is True
    assert slo.has_poison("SDL_GAMECONTROLLER_IGNORE_DEVICES=0x057e/0x2009") is False
    assert slo.has_poison("MANGOHUD=1 %command%") is False
    assert slo.has_extended_ignore(LINHA_914) is False
    assert slo.has_extended_ignore(LINHA_ESTENDIDA) is False
    assert slo.has_extended_ignore(LINHA_NOSSO_PAR_EM_SEGUNDO) is False
    assert slo.has_extended_ignore(LINHA_FORA_DO_ALCANCE) is True


def test_transform_migra_a_linha_estendida_nos_dois_modos():
    """ERA `test_transform_pula_linha_estendida_nos_dois_modos`, e ele exigia"""
    texto = _vdf({"1599660": LINHA_ESTENDIDA})
    for modo in ("migrate", "strip"):
        novo, mudadas = slo.transform_vdf_text(texto, modo)
        assert mudadas == 1, modo
        assert "0x054c/0x0ce6" not in novo, modo
        assert "0x057e/0x2009" in novo, modo


def test_transform_nao_toca_o_que_a_subtracao_nao_alcanca():
    texto = _vdf({"1599660": slo._vdf_escape(LINHA_FORA_DO_ALCANCE)})
    for modo in ("migrate", "strip"):
        novo, mudadas = slo.transform_vdf_text(texto, modo)
        assert mudadas == 0, modo
        assert novo == texto, modo


def test_main_migra_a_linha_estendida_preservando_a_parte_dela(
    tmp_path, monkeypatch, capsys
):
    """ERA `test_main_reporta_ignore_estendido_sem_tocar`."""
    vdf = tmp_path / "localconfig.vdf"
    vdf.write_text(_vdf({"1599660": LINHA_ESTENDIDA}), encoding="utf-8")
    monkeypatch.setattr(slo, "steam_running", lambda: False)
    monkeypatch.setattr(slo, "steam_game_running", lambda: False)
    rc = slo.main(["--migrate", "--vdf", str(vdf)])
    assert rc == 0
    depois = vdf.read_text(encoding="utf-8")
    assert "hefesto-launch" in depois
    assert "0x057e/0x2009" in depois, "o device que ELA escondeu foi jogado fora"
    assert "0x054c/0x0ce6" not in depois
    capsys.readouterr()


def test_main_ainda_reporta_o_que_nao_alcanca(tmp_path, monkeypatch, capsys):
    vdf = tmp_path / "localconfig.vdf"
    original = _vdf({"1599660": slo._vdf_escape(LINHA_FORA_DO_ALCANCE)})
    vdf.write_text(original, encoding="utf-8")
    monkeypatch.setattr(slo, "steam_running", lambda: False)
    monkeypatch.setattr(slo, "steam_game_running", lambda: False)
    rc = slo.main(["--migrate", "--vdf", str(vdf)])
    assert rc == 0
    assert vdf.read_text(encoding="utf-8") == original
    out = capsys.readouterr().out
    assert "não sei desmontar" in out
    assert "manualmente" in out


def test_strip_remove_o_wrapper_preservando_o_resto():
    valor = f"{slo.WRAPPER_PREFIX} MANGOHUD=1 %command%"
    assert slo.strip_value(valor) == "MANGOHUD=1 %command%"


def test_transform_migrate_so_toca_linhas_envenenadas():
    texto = _vdf({"1599660": LINHA_914, "620": "MANGOHUD=1 %command%"})
    novo, mudadas = slo.transform_vdf_text(texto, "migrate")
    assert mudadas == 1
    assert slo.IGNORE_SIGNATURE not in novo
    assert '"MANGOHUD=1 %command%"' in novo
    assert slo._vdf_escape(slo.WRAPPER_LAUNCH) in novo
    assert '"playtime"' in novo


def test_transform_respeita_escaping_de_aspas_do_usuario():
    valor_escapado = 'sh -c \\"echo oi\\" %command%'
    texto = _vdf({"620": valor_escapado})
    novo, mudadas = slo.transform_vdf_text(texto, "migrate")
    assert mudadas == 0
    assert novo == texto


def test_transform_strip_remove_novo_e_legado():
    texto = _vdf(
        {
            "1599660": slo._vdf_escape(slo.WRAPPER_LAUNCH),
            "440": LINHA_914,
            "620": "MANGOHUD=1 %command%",
        }
    )
    novo, mudadas = slo.transform_vdf_text(texto, "strip")
    assert mudadas == 2
    assert slo._vdf_escape(slo.WRAPPER_PREFIX) not in novo
    assert slo.IGNORE_SIGNATURE not in novo
    assert '"MANGOHUD=1 %command%"' in novo
    assert "__GL_SHADER_DISK_CACHE=1" in novo


def test_migrate_depois_strip_zera_o_nosso_rastro():
    texto = _vdf({"1599660": LINHA_914})
    migrado, _ = slo.transform_vdf_text(texto, "migrate")
    limpo, _ = slo.transform_vdf_text(migrado, "strip")
    assert '"LaunchOptions"\t\t""' in limpo


def test_process_vdf_dry_run_nao_toca_no_arquivo(tmp_path: Path):
    vdf = tmp_path / "localconfig.vdf"
    original = _vdf({"1599660": LINHA_914})
    vdf.write_text(original, encoding="utf-8")
    changed, diff = slo.process_vdf(vdf, "migrate", dry_run=True)
    assert changed == 1
    assert diff
    assert vdf.read_text(encoding="utf-8") == original
    assert list(tmp_path.glob("*.bak.*")) == []


def test_process_vdf_migra_com_backup_e_e_idempotente(tmp_path: Path):
    vdf = tmp_path / "localconfig.vdf"
    vdf.write_text(_vdf({"1599660": LINHA_914}), encoding="utf-8")
    changed, _ = slo.process_vdf(vdf, "migrate")
    assert changed == 1
    backups = list(tmp_path.glob("localconfig.vdf.bak.hefesto-launch-*"))
    assert len(backups) == 1
    assert slo.IGNORE_SIGNATURE in backups[0].read_text(encoding="utf-8")
    changed2, _ = slo.process_vdf(vdf, "migrate")
    assert changed2 == 0
    assert len(list(tmp_path.glob("*.bak.*"))) == 1


def test_main_recusa_migrar_com_steam_aberta(tmp_path, monkeypatch, capsys):
    vdf = tmp_path / "localconfig.vdf"
    original = _vdf({"1599660": LINHA_914})
    vdf.write_text(original, encoding="utf-8")
    monkeypatch.setattr(slo, "steam_running", lambda: True)
    monkeypatch.setattr(slo, "steam_game_running", lambda: False)
    rc = slo.main(["--migrate", "--vdf", str(vdf)])
    assert rc == 3
    assert vdf.read_text(encoding="utf-8") == original
    out = capsys.readouterr().out
    assert "Steam está aberta" in out
    assert "regrava o arquivo ao sair" in out


def test_main_recusa_com_jogo_da_steam_aberto(tmp_path, monkeypatch, capsys):
    """DEDUP-05 exigência 2: `steam -shutdown` com jogo aberto MATA o jogo —"""
    vdf = tmp_path / "localconfig.vdf"
    original = _vdf({"1599660": LINHA_914})
    vdf.write_text(original, encoding="utf-8")
    monkeypatch.setattr(slo, "steam_running", lambda: True)
    monkeypatch.setattr(slo, "steam_game_running", lambda: True)
    parou = []
    monkeypatch.setattr(slo, "stop_steam", lambda: parou.append(True) or True)

    for args in (
        ["--migrate", "--vdf", str(vdf)],
        ["--migrate", "--stop-steam", "--vdf", str(vdf)],
        ["--strip", "--stop-steam", "--vdf", str(vdf)],
    ):
        rc = slo.main(args)
        assert rc == 3, args
        assert vdf.read_text(encoding="utf-8") == original

    assert parou == []
    out = capsys.readouterr().out
    assert "JOGO" in out
    assert "MATARIA" in out


def test_main_migra_com_steam_fechada(tmp_path, monkeypatch, capsys):
    vdf = tmp_path / "localconfig.vdf"
    vdf.write_text(_vdf({"1599660": LINHA_914}), encoding="utf-8")
    monkeypatch.setattr(slo, "steam_running", lambda: False)
    monkeypatch.setattr(slo, "steam_game_running", lambda: False)
    rc = slo.main(["--migrate", "--vdf", str(vdf)])
    assert rc == 0
    texto = vdf.read_text(encoding="utf-8")
    assert slo.IGNORE_SIGNATURE not in texto
    assert slo._vdf_escape(slo.WRAPPER_LAUNCH) in texto


def test_main_migrate_em_vdf_de_sandbox_so_remove_o_veneno(tmp_path, monkeypatch, capsys):
    """Steam Flatpak/Snap: o wrapper do host é invisível à sandbox — escrever"""
    sandbox = (
        tmp_path / ".var/app/com.valvesoftware.Steam/.steam/steam/userdata"
        / "12345678/config"
    )
    sandbox.mkdir(parents=True)
    vdf = sandbox / "localconfig.vdf"
    original = _vdf({"1599660": LINHA_914})
    vdf.write_text(original, encoding="utf-8")
    monkeypatch.setattr(slo, "steam_running", lambda: False)
    monkeypatch.setattr(slo, "steam_game_running", lambda: False)

    rc = slo.main(["--migrate", "--vdf", str(vdf)])
    assert rc == 0
    texto = vdf.read_text(encoding="utf-8")
    assert slo.IGNORE_SIGNATURE not in texto
    assert slo._vdf_escape(slo.WRAPPER_PREFIX) not in texto
    assert "sandbox" in capsys.readouterr().out

    rc = slo.main(["--strip", "--vdf", str(vdf)])
    assert rc == 0
    assert slo.IGNORE_SIGNATURE not in vdf.read_text(encoding="utf-8")


def test_main_status_relata_sem_tocar(tmp_path, monkeypatch, capsys):
    vdf = tmp_path / "localconfig.vdf"
    original = _vdf({"1599660": LINHA_914})
    vdf.write_text(original, encoding="utf-8")
    monkeypatch.setattr(slo, "steam_running", lambda: True)
    rc = slo.main(["--status", "--vdf", str(vdf)])
    assert rc == 0
    assert vdf.read_text(encoding="utf-8") == original
    assert "veneno" in capsys.readouterr().out


@pytest.mark.parametrize(
    "arquivo",
    ["install.sh", "uninstall.sh", "scripts/doctor.sh", "assets/hefesto-launch.sh"],
)
def test_caminho_do_wrapper_e_o_mesmo_em_todo_lugar(arquivo: str):
    """O caminho estável do wrapper é contrato entre módulo Python, install,"""
    root = Path(__file__).resolve().parents[2]
    texto = (root / arquivo).read_text(encoding="utf-8")
    assert slo.WRAPPER_HOME_RELPATH in texto


def test_uninstall_desenvenena_antes_de_apagar_o_wrapper():
    """Ordem obrigatória do DEDUP-04: vdf ANTES do wrapper (a assimetria já"""
    root = Path(__file__).resolve().parents[2]
    texto = (root / "uninstall.sh").read_text(encoding="utf-8")
    pos_strip = texto.index("--strip")
    pos_rm_wrapper = texto.index('rm -f "${LAUNCH_WRAPPER}"')
    assert pos_strip < pos_rm_wrapper


def test_install_migra_fora_do_bloco_do_steam_input():
    """Achado MED da revisão: a migração DEDUP-05 (P0) é um passo PRÓPRIO —"""
    root = Path(__file__).resolve().parents[2]
    texto = (root / "install.sh").read_text(encoding="utf-8")
    assert 'step "11b"' in texto
    pos_fim_bloco_steam_input = texto.index(
        "systemctl --user enable hefesto-steam-input-guard"
    )
    pos_migrate = texto.index("--migrate --stop-steam")
    assert pos_migrate > pos_fim_bloco_steam_input


# --- apply_wrapper_to_all_games (PATH-06 item 2: via em-massa consentida) ----


def _vdf_sem_launch_options(appid: str) -> str:
    """Um localconfig.vdf com um app SEM a linha LaunchOptions."""
    return (
        '"UserLocalConfigStore"\n{\n'
        f'{_TAB}"Software"\n{_TAB}{{\n'
        f'{_TAB * 2}"Valve"\n{_TAB * 2}{{\n'
        f'{_TAB * 3}"Steam"\n{_TAB * 3}{{\n'
        f'{_TAB * 4}"apps"\n{_TAB * 4}{{\n'
        f'{_TAB * 5}"{appid}"\n{_TAB * 5}{{\n'
        f'{_TAB * 6}"playtime"{_TAB * 2}"42"\n'
        f"{_TAB * 5}}}\n"
        f"{_TAB * 4}}}\n{_TAB * 3}}}\n{_TAB * 2}}}\n{_TAB}}}\n}}\n"
    )


def test_apply_wrapper_prefixa_preservando_opcoes_do_usuario():
    texto = _vdf({"620": "MANGOHUD=1 %command%"})
    novo, aplicados, pulados = slo.apply_wrapper_vdf_text(texto)
    assert aplicados == ["620"]
    assert pulados == []
    valores = slo.read_launch_options_by_appid(novo)
    assert valores["620"] == f"{slo.WRAPPER_PREFIX} MANGOHUD=1 %command%"


def test_apply_wrapper_insere_launch_options_em_jogo_sem_nenhuma():
    texto = _vdf_sem_launch_options("1599660")
    novo, aplicados, pulados = slo.apply_wrapper_vdf_text(texto)
    assert aplicados == ["1599660"]
    assert pulados == []
    valores = slo.read_launch_options_by_appid(novo)
    assert valores["1599660"] == slo.WRAPPER_LAUNCH
    assert '"playtime"' in novo


def test_apply_wrapper_e_idempotente_e_reporta_skip():
    texto = _vdf({"620": "MANGOHUD=1 %command%"})
    uma_vez, _, _ = slo.apply_wrapper_vdf_text(texto)
    duas_vezes, aplicados, pulados = slo.apply_wrapper_vdf_text(uma_vez)
    assert duas_vezes == uma_vez
    assert aplicados == []
    assert pulados == [("620", "ja_tem_wrapper")]


def test_apply_wrapper_remove_veneno_legado_junto():
    texto = _vdf({"1599660": LINHA_914})
    novo, aplicados, _ = slo.apply_wrapper_vdf_text(texto)
    assert aplicados == ["1599660"]
    assert slo.IGNORE_SIGNATURE not in novo
    assert slo.read_launch_options_by_appid(novo)["1599660"] == slo.WRAPPER_LAUNCH


def test_apply_wrapper_migra_o_ignore_estendido():
    """ERA `test_apply_wrapper_pula_ignore_estendido_sem_tocar`, e o nome dele"""
    texto = _vdf({"1599660": LINHA_ESTENDIDA, "620": ""})
    novo, aplicados, pulados = slo.apply_wrapper_vdf_text(texto)
    assert "1599660" in aplicados
    assert aplicados == ["1599660", "620"]
    assert ("1599660", "ignore_estendido") not in pulados
    linha = slo.read_launch_options_by_appid(novo)["1599660"]
    assert linha.startswith(slo.WRAPPER_PREFIX + " ")
    assert "0x057e/0x2009" in linha, "o device que ELA escondeu foi jogado fora"
    assert "0x054c/0x0ce6" not in linha


def test_apply_wrapper_ainda_pula_o_que_nao_alcanca():
    """O `skipped` não morreu — ele passou a nomear só o que sobra."""
    texto = _vdf({"1599660": slo._vdf_escape(LINHA_FORA_DO_ALCANCE), "620": ""})
    novo, aplicados, pulados = slo.apply_wrapper_vdf_text(texto)
    assert ("1599660", "ignore_estendido") in pulados
    assert aplicados == ["620"]
    assert slo.read_launch_options_by_appid(novo)["1599660"] == LINHA_FORA_DO_ALCANCE


def test_apply_wrapper_to_all_games_recusa_com_steam_aberta(tmp_path, monkeypatch):
    vdf = tmp_path / "localconfig.vdf"
    original = _vdf({"620": "MANGOHUD=1 %command%"})
    vdf.write_text(original, encoding="utf-8")
    monkeypatch.setattr(slo, "steam_running", lambda: True)
    monkeypatch.setattr(slo, "steam_game_running", lambda: False)
    resultado = slo.apply_wrapper_to_all_games(vdfs=[vdf])
    assert resultado["applied"] == []
    assert resultado["errors"] == [{"vdf": "", "appid": "", "reason": "steam_aberta"}]
    assert vdf.read_text(encoding="utf-8") == original


def test_apply_wrapper_to_all_games_recusa_com_jogo_aberto(tmp_path, monkeypatch):
    vdf = tmp_path / "localconfig.vdf"
    original = _vdf({"620": ""})
    vdf.write_text(original, encoding="utf-8")
    monkeypatch.setattr(slo, "steam_running", lambda: True)
    monkeypatch.setattr(slo, "steam_game_running", lambda: True)
    resultado = slo.apply_wrapper_to_all_games(vdfs=[vdf])
    assert resultado["errors"] == [
        {"vdf": "", "appid": "", "reason": "jogo_da_steam_aberto"}
    ]
    assert vdf.read_text(encoding="utf-8") == original


def test_apply_wrapper_to_all_games_aplica_com_backup(tmp_path, monkeypatch):
    vdf = tmp_path / "localconfig.vdf"
    vdf.write_text(
        _vdf({"620": "MANGOHUD=1 %command%", "440": slo._vdf_escape(slo.WRAPPER_LAUNCH)}),
        encoding="utf-8",
    )
    monkeypatch.setattr(slo, "steam_running", lambda: False)
    monkeypatch.setattr(slo, "steam_game_running", lambda: False)
    resultado = slo.apply_wrapper_to_all_games(vdfs=[vdf])
    assert [a["appid"] for a in resultado["applied"]] == ["620"]
    assert [(s["appid"], s["reason"]) for s in resultado["skipped"]] == [
        ("440", "ja_tem_wrapper")
    ]
    assert resultado["errors"] == []
    assert len(list(tmp_path.glob("localconfig.vdf.bak.hefesto-launch-*"))) == 1
    valores = slo.read_launch_options_by_appid(vdf.read_text(encoding="utf-8"))
    assert valores["620"].startswith(slo.WRAPPER_PREFIX)


def test_apply_wrapper_to_all_games_dry_run_nao_toca(tmp_path, monkeypatch):
    vdf = tmp_path / "localconfig.vdf"
    original = _vdf_sem_launch_options("1599660")
    vdf.write_text(original, encoding="utf-8")
    monkeypatch.setattr(
        slo, "steam_running", lambda: (_ for _ in ()).throw(AssertionError)
    )
    resultado = slo.apply_wrapper_to_all_games(vdfs=[vdf], dry_run=True)
    assert [a["appid"] for a in resultado["applied"]] == ["1599660"]
    assert vdf.read_text(encoding="utf-8") == original
    assert list(tmp_path.glob("*.bak.*")) == []


def test_apply_wrapper_to_all_games_vdf_nao_utf8_vira_erro_por_vdf(
    tmp_path, monkeypatch
):
    """Achado #6: um localconfig.vdf não-UTF-8 (byte latin-1 legado /"""
    monkeypatch.setattr(slo, "steam_running", lambda: False)
    monkeypatch.setattr(slo, "steam_game_running", lambda: False)
    ruim = tmp_path / "ruim" / "localconfig.vdf"
    ruim.parent.mkdir()
    ruim.write_bytes(b'"UserLocalConfigStore"\n{\n\xff byte invalido\n}\n')
    bom = tmp_path / "bom" / "localconfig.vdf"
    bom.parent.mkdir()
    bom.write_text(_vdf({"620": "MANGOHUD=1 %command%"}), encoding="utf-8")

    resultado = slo.apply_wrapper_to_all_games(vdfs=[ruim, bom])
    assert [e["vdf"] for e in resultado["errors"]] == [str(ruim)]
    assert [a["appid"] for a in resultado["applied"]] == ["620"]
    assert slo.read_launch_options_by_appid(bom.read_text(encoding="utf-8"))[
        "620"
    ].startswith(slo.WRAPPER_PREFIX)


def test_main_strip_vdf_nao_utf8_nao_estoura_traceback(
    tmp_path, monkeypatch, capsys
):
    """Achado #6: no --strip do uninstall, um vdf não-UTF-8 vira ERRO por-vdf"""
    monkeypatch.setattr(slo, "steam_running", lambda: False)
    monkeypatch.setattr(slo, "steam_game_running", lambda: False)
    ruim = tmp_path / "ruim" / "localconfig.vdf"
    ruim.parent.mkdir()
    ruim.write_bytes(b'"UserLocalConfigStore"\n{\n\xff\n}\n')
    bom = tmp_path / "bom" / "localconfig.vdf"
    bom.parent.mkdir()
    bom.write_text(_vdf({"1599660": LINHA_914}), encoding="utf-8")

    rc = slo.main(["--strip", "--vdf", str(ruim), "--vdf", str(bom)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "ERRO" in out
    assert str(ruim) in out
    assert slo.IGNORE_SIGNATURE not in bom.read_text(encoding="utf-8")


def test_apply_wrapper_to_all_games_pula_vdf_de_sandbox(tmp_path, monkeypatch):
    sandbox = (
        tmp_path / ".var/app/com.valvesoftware.Steam/.steam/steam/userdata"
        / "12345678/config"
    )
    sandbox.mkdir(parents=True)
    vdf = sandbox / "localconfig.vdf"
    original = _vdf({"620": ""})
    vdf.write_text(original, encoding="utf-8")
    monkeypatch.setattr(slo, "steam_running", lambda: False)
    monkeypatch.setattr(slo, "steam_game_running", lambda: False)
    resultado = slo.apply_wrapper_to_all_games(vdfs=[vdf])
    assert resultado["applied"] == []
    assert resultado["skipped"] == [
        {"vdf": str(vdf), "appid": "", "reason": "sandbox"}
    ]
    assert vdf.read_text(encoding="utf-8") == original


# HONESTIDADE-STEAM-01: o CORPO de stop_steam + a janela with_steam_closed


class _RelogioFalso:
    """`time` falso: `sleep` não dorme, só registra quanto FOI pedido."""

    def __init__(self) -> None:
        self.dormido: list[float] = []

    def sleep(self, segundos: float) -> None:
        self.dormido.append(segundos)

    def time(self) -> float:
        return 1000.0 + sum(self.dormido)


class _SubprocessFalso:
    """`subprocess` falso: registra Popen/run e nunca executa nada."""

    SubprocessError = Exception
    DEVNULL = -3

    def __init__(self) -> None:
        self.popen: list[list[str]] = []
        self.run_args: list[list[str]] = []

    def Popen(self, args, **_kwargs):  # noqa: N802 - espelha a API do stdlib
        self.popen.append(list(args))
        return None

    def run(self, args, **_kwargs):
        self.run_args.append(list(args))
        return SimpleNamespace(returncode=0, stdout="", stderr="")


def _prepara_stop_steam(monkeypatch, *, vivo_por: int, com_steam_no_path=True):
    """Instala os dublês e devolve (relogio, subproc, contador de checagens)."""
    relogio = _RelogioFalso()
    subproc = _SubprocessFalso()
    estado = {"restantes": vivo_por, "consultas": 0}

    def _steam_running() -> bool:
        estado["consultas"] += 1
        if estado["restantes"] > 0:
            estado["restantes"] -= 1
            return True
        return False

    monkeypatch.setattr(slo, "time", relogio)
    monkeypatch.setattr(slo, "subprocess", subproc)
    monkeypatch.setattr(slo, "steam_running", _steam_running)
    monkeypatch.setattr(slo, "steam_deste_lar", lambda *_a, **_k: [])
    monkeypatch.setattr(
        slo,
        "shutil",
        SimpleNamespace(
            which=lambda _n: "/usr/bin/steam" if com_steam_no_path else None
        ),
    )
    return relogio, subproc, estado


def test_stop_steam_sem_steam_viva_e_no_op(monkeypatch):
    relogio, subproc, _ = _prepara_stop_steam(monkeypatch, vivo_por=0)
    assert slo.stop_steam() is True
    assert subproc.popen == []
    assert subproc.run_args == []
    assert relogio.dormido == []


def test_stop_steam_usa_shutdown_e_nao_escala_para_pkill(monkeypatch):
    """Caminho feliz: `steam -shutdown` resolve, o pkill NUNCA é cogitado."""
    relogio, subproc, _ = _prepara_stop_steam(monkeypatch, vivo_por=1)

    assert slo.stop_steam() is True

    assert subproc.popen == [["steam", "-shutdown"]]
    assert subproc.run_args == []
    assert relogio.dormido == [2, 2]


def test_stop_steam_escala_por_pid_e_nunca_pelo_nome(monkeypatch):
    """A Steam resiste às 15 voltas: TERM primeiro, KILL depois, a cada PID"""
    relogio, subproc, _ = _prepara_stop_steam(monkeypatch, vivo_por=100)
    alvo = slo.ProcessoDaSteam(4242, "cliente", "/lar", "77")
    monkeypatch.setattr(slo, "steam_deste_lar", lambda *_a, **_k: [alvo])
    monkeypatch.setattr(slo, "_inicio", lambda _pasta: "77")
    sinais: list[tuple[int, int]] = []

    assert slo.stop_steam(sinalizar=lambda pid, sig: sinais.append((pid, sig))) is False

    assert subproc.popen == [["steam", "-shutdown"]]
    assert subproc.run_args == []
    assert sinais == [(4242, slo.signal.SIGTERM), (4242, slo.signal.SIGKILL)]
    assert relogio.dormido == [2] * 15 + [3, 3, 2]


def test_stop_steam_para_no_term_quando_ele_resolve(monkeypatch):
    relogio, subproc, _ = _prepara_stop_steam(monkeypatch, vivo_por=17)
    sinais: list[tuple[int, int]] = []
    alvo = slo.ProcessoDaSteam(4242, "cliente", "/lar", "77")
    monkeypatch.setattr(slo, "steam_deste_lar", lambda *_a, **_k: [alvo])
    monkeypatch.setattr(slo, "_inicio", lambda _pasta: "77")

    assert slo.stop_steam(sinalizar=lambda pid, sig: sinais.append((pid, sig))) is True

    assert subproc.run_args == []
    assert sinais == [(4242, slo.signal.SIGTERM)]
    assert relogio.dormido == [2] * 15 + [3, 2]


def test_stop_steam_sem_binario_steam_vai_direto_ao_sinal(monkeypatch):
    """Steam Flatpak/Snap sem `steam` no PATH: não há shutdown gracioso."""
    relogio, subproc, _ = _prepara_stop_steam(
        monkeypatch, vivo_por=100, com_steam_no_path=False
    )

    assert slo.stop_steam() is False

    assert subproc.popen == []
    assert subproc.run_args == []
    assert relogio.dormido == [3, 3, 2]


# --- with_steam_closed: a janela consentida que a GUI usa -------------------


def test_with_steam_closed_recusa_com_jogo_aberto_antes_de_tudo(monkeypatch):
    """Ordem inegociável: o gate de JOGO vem ANTES de qualquer decisão sobre a"""
    chamadas = {"stop": 0, "reopen": 0, "executou": 0}
    monkeypatch.setattr(slo, "steam_game_running", lambda: True)
    monkeypatch.setattr(slo, "steam_running", lambda: True)
    monkeypatch.setattr(
        slo, "stop_steam", lambda: chamadas.__setitem__("stop", chamadas["stop"] + 1)
    )
    monkeypatch.setattr(
        slo,
        "reopen_steam",
        lambda: chamadas.__setitem__("reopen", chamadas["reopen"] + 1),
    )

    status, resultado = slo.with_steam_closed(
        lambda: chamadas.__setitem__("executou", 1)
    )

    assert status == slo.STEAM_JANELA_JOGO_ABERTO
    assert resultado is None
    assert chamadas == {"stop": 0, "reopen": 0, "executou": 0}


def test_with_steam_closed_steam_ja_fechada_nao_fecha_nem_reabre(monkeypatch):
    monkeypatch.setattr(slo, "steam_game_running", lambda: False)
    monkeypatch.setattr(slo, "steam_running", lambda: False)
    monkeypatch.setattr(slo, "stop_steam", lambda: pytest.fail("não devia fechar"))
    monkeypatch.setattr(slo, "reopen_steam", lambda: pytest.fail("não devia reabrir"))

    status, resultado = slo.with_steam_closed(lambda: "feito")

    assert (status, resultado) == (slo.STEAM_JANELA_OK, "feito")


def test_with_steam_closed_fecha_roda_e_reabre(monkeypatch):
    ordem: list[str] = []
    monkeypatch.setattr(slo, "steam_game_running", lambda: False)
    monkeypatch.setattr(slo, "steam_running", lambda: True)
    monkeypatch.setattr(
        slo, "stop_steam", lambda: (ordem.append("stop"), True)[1]
    )
    monkeypatch.setattr(slo, "reopen_steam", lambda: ordem.append("reopen"))

    status, resultado = slo.with_steam_closed(
        lambda: (ordem.append("executou"), 42)[1]
    )

    assert (status, resultado) == (slo.STEAM_JANELA_OK, 42)
    assert ordem == ["stop", "executou", "reopen"]


def test_with_steam_closed_steam_teimosa_nao_edita_nada(monkeypatch):
    monkeypatch.setattr(slo, "steam_game_running", lambda: False)
    monkeypatch.setattr(slo, "steam_running", lambda: True)
    monkeypatch.setattr(slo, "stop_steam", lambda: False)
    monkeypatch.setattr(slo, "reopen_steam", lambda: pytest.fail("não reabre o que não fechou"))

    status, resultado = slo.with_steam_closed(lambda: pytest.fail("não devia rodar"))

    assert status == slo.STEAM_JANELA_NAO_FECHOU
    assert resultado is None


def test_with_steam_closed_reabre_mesmo_com_excecao_na_acao(monkeypatch):
    """A usuária não pode ficar SEM Steam porque a nossa ação estourou."""
    ordem: list[str] = []
    monkeypatch.setattr(slo, "steam_game_running", lambda: False)
    monkeypatch.setattr(slo, "steam_running", lambda: True)
    monkeypatch.setattr(slo, "stop_steam", lambda: True)
    monkeypatch.setattr(slo, "reopen_steam", lambda: ordem.append("reopen"))

    def _explode():
        raise OSError("disco sumiu")

    with pytest.raises(OSError):
        slo.with_steam_closed(_explode)

    assert ordem == ["reopen"]


def test_allowlist_path_respeita_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert slo.steam_input_allowlist_path() == (
        tmp_path / "hefesto-dualsense4unix" / "steam_input_apps.txt"
    )


def test_allowlist_nasce_com_cabecalho_quando_nao_existe(tmp_path):
    alvo = tmp_path / "sub" / "steam_input_apps.txt"

    assert slo.add_appid_to_steam_input_allowlist(2111190, path=alvo) == "adicionado"

    texto = alvo.read_text(encoding="utf-8")
    assert texto.startswith("# hefesto-dualsense4unix")
    assert slo.parse_steam_input_allowlist(texto) == ["2111190"]


def test_allowlist_preserva_cabecalho_e_comentarios_existentes(tmp_path):
    alvo = tmp_path / "steam_input_apps.txt"
    original = "# cabeçalho da usuária\n# não me apague\n2111190\n"
    alvo.write_text(original, encoding="utf-8")

    assert slo.add_appid_to_steam_input_allowlist(620, path=alvo) == "adicionado"

    texto = alvo.read_text(encoding="utf-8")
    assert texto.startswith(original)
    assert slo.parse_steam_input_allowlist(texto) == ["2111190", "620"]


def test_allowlist_nao_duplica(tmp_path):
    alvo = tmp_path / "steam_input_apps.txt"
    alvo.write_text("# topo\n2111190\n", encoding="utf-8")
    antes = alvo.read_text(encoding="utf-8")

    assert slo.add_appid_to_steam_input_allowlist("2111190", path=alvo) == "ja_estava"

    assert alvo.read_text(encoding="utf-8") == antes


def test_allowlist_appid_apenas_comentado_e_readicionado(tmp_path):
    """`# 620` é comentário, não presença — a linha morta não pode fazer o"""
    alvo = tmp_path / "steam_input_apps.txt"
    alvo.write_text("# topo\n# 620 desliguei este\n", encoding="utf-8")

    assert slo.add_appid_to_steam_input_allowlist(620, path=alvo) == "adicionado"

    assert "620" in slo.parse_steam_input_allowlist(
        alvo.read_text(encoding="utf-8")
    )


def test_allowlist_sem_quebra_de_linha_final_nao_gruda_appids(tmp_path):
    alvo = tmp_path / "steam_input_apps.txt"
    alvo.write_text("# topo\n2111190", encoding="utf-8")

    slo.add_appid_to_steam_input_allowlist(620, path=alvo)

    assert slo.parse_steam_input_allowlist(
        alvo.read_text(encoding="utf-8")
    ) == ["2111190", "620"]


@pytest.mark.parametrize("torto", ["", "abc", "12a", None])
def test_allowlist_recusa_appid_nao_numerico(tmp_path, torto):
    alvo = tmp_path / "steam_input_apps.txt"
    assert (
        slo.add_appid_to_steam_input_allowlist(torto, path=alvo) == "appid_invalido"
    )
    assert not alvo.exists()


def test_allowlist_erro_de_io_nao_levanta(tmp_path, monkeypatch):
    """É um clique de botão: falha vira status, nunca traceback."""
    alvo = tmp_path / "steam_input_apps.txt"
    monkeypatch.setattr(
        Path, "read_text", lambda *a, **k: (_ for _ in ()).throw(OSError("boom"))
    )
    assert slo.add_appid_to_steam_input_allowlist(620, path=alvo) == "erro"


def test_allowlist_grava_a_nota_como_comentario(tmp_path):
    alvo = tmp_path / "steam_input_apps.txt"
    slo.add_appid_to_steam_input_allowlist(620, path=alvo, nota="marcado pela GUI")
    texto = alvo.read_text(encoding="utf-8")
    assert "# marcado pela GUI\n620\n" in texto
    assert slo.parse_steam_input_allowlist(texto) == ["620"]


def test_allowlist_remove_o_appid_e_preserva_cabecalho_e_comentarios(tmp_path):
    alvo = tmp_path / "steam_input_apps.txt"
    alvo.write_text(
        "# cabeçalho da usuária\n# não me apague\n2111190\n620\n", encoding="utf-8"
    )

    assert slo.remove_appid_from_steam_input_allowlist(2111190, path=alvo) == "removido"

    texto = alvo.read_text(encoding="utf-8")
    assert texto == "# cabeçalho da usuária\n# não me apague\n620\n"


def test_allowlist_remove_leva_o_comentario_inline_junto(tmp_path):
    """`620 # marcado pela GUI` é UMA linha cujo appid é 620."""
    alvo = tmp_path / "steam_input_apps.txt"
    alvo.write_text("# topo\n620 # marcado pela GUI\n", encoding="utf-8")

    assert slo.remove_appid_from_steam_input_allowlist("620", path=alvo) == "removido"

    assert alvo.read_text(encoding="utf-8") == "# topo\n"


def test_allowlist_remove_deixa_a_nota_orfa_de_proposito(tmp_path):
    """Adivinhar "qual comentário era nosso" acertaria a nota do `add` e uma"""
    alvo = tmp_path / "steam_input_apps.txt"
    slo.add_appid_to_steam_input_allowlist(620, path=alvo, nota="marcado pela GUI")

    slo.remove_appid_from_steam_input_allowlist(620, path=alvo)

    texto = alvo.read_text(encoding="utf-8")
    assert "# marcado pela GUI" in texto
    assert slo.parse_steam_input_allowlist(texto) == []


def test_allowlist_remove_appid_ausente_nao_reescreve(tmp_path):
    alvo = tmp_path / "steam_input_apps.txt"
    alvo.write_text("# topo\n2111190\n", encoding="utf-8")
    antes = alvo.read_text(encoding="utf-8")

    assert slo.remove_appid_from_steam_input_allowlist(620, path=alvo) == "nao_estava"

    assert alvo.read_text(encoding="utf-8") == antes


def test_allowlist_remove_appid_so_comentado_e_nao_estava(tmp_path):
    """Simetria com o `add`, que RE-ADICIONA um appid comentado: linha morta"""
    alvo = tmp_path / "steam_input_apps.txt"
    alvo.write_text("# topo\n# 620 desliguei este\n", encoding="utf-8")

    assert slo.remove_appid_from_steam_input_allowlist(620, path=alvo) == "nao_estava"

    assert "# 620 desliguei este" in alvo.read_text(encoding="utf-8")


def test_allowlist_remove_sem_arquivo_nao_cria_nada(tmp_path):
    alvo = tmp_path / "sub" / "steam_input_apps.txt"

    assert slo.remove_appid_from_steam_input_allowlist(620, path=alvo) == "nao_estava"

    assert not alvo.exists()


@pytest.mark.parametrize("torto", ["", "abc", "12a", None])
def test_allowlist_remove_recusa_appid_nao_numerico(tmp_path, torto):
    alvo = tmp_path / "steam_input_apps.txt"
    alvo.write_text("# topo\n620\n", encoding="utf-8")

    assert (
        slo.remove_appid_from_steam_input_allowlist(torto, path=alvo)
        == "appid_invalido"
    )
    assert alvo.read_text(encoding="utf-8") == "# topo\n620\n"


def test_allowlist_remove_erro_de_io_nao_levanta(tmp_path, monkeypatch):
    alvo = tmp_path / "steam_input_apps.txt"
    alvo.write_text("# topo\n620\n", encoding="utf-8")
    monkeypatch.setattr(
        Path, "write_text", lambda *a, **k: (_ for _ in ()).throw(OSError("boom"))
    )
    assert slo.remove_appid_from_steam_input_allowlist(620, path=alvo) == "erro"


def test_allowlist_ida_e_volta_devolve_o_arquivo_ao_estado_util(tmp_path):
    """O ciclo completo do botão: marcar, desmarcar, marcar de novo."""
    alvo = tmp_path / "steam_input_apps.txt"

    assert slo.add_appid_to_steam_input_allowlist(2111190, path=alvo) == "adicionado"
    assert slo.remove_appid_from_steam_input_allowlist(2111190, path=alvo) == "removido"
    assert slo.parse_steam_input_allowlist(alvo.read_text(encoding="utf-8")) == []
    assert slo.add_appid_to_steam_input_allowlist(2111190, path=alvo) == "adicionado"
    assert slo.parse_steam_input_allowlist(alvo.read_text(encoding="utf-8")) == [
        "2111190"
    ]
