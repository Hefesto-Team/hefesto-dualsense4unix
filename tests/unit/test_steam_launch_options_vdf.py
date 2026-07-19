"""DEDUP-05/UX-04: migração e strip das LaunchOptions no localconfig.vdf.

Tudo com FIXTURES — a aplicação no vdf REAL acontece só no ciclo final do
install (com a Steam fechada). A "linha 914" abaixo é a variante VELHA nossa
provada persistida ao vivo (2 dos 3 tokens + shader-cache); o critério de
aceite do sprint doc exige testá-la verbatim.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import steam_launch_options as slo

#: A variante de onda anterior persistida no vdf real (verbatim do sprint doc).
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


# --- migrate_value / strip_value (puras) -----------------------------------


def test_migrate_linha_914_vira_a_string_constante_do_wrapper():
    """O veneno inteiro (assinatura + co-ocorrentes + preload) sai e entra a
    chamada do wrapper — o preload volta pelo arquivo de env materializado."""
    assert slo.migrate_value(LINHA_914) == slo.WRAPPER_LAUNCH


def test_migrate_preserva_opcoes_genuinas_do_usuario():
    valor = f"MANGOHUD=1 {LINHA_914}"
    migrado = slo.migrate_value(valor)
    assert migrado == f"{slo.WRAPPER_PREFIX} MANGOHUD=1 %command%"
    assert slo.IGNORE_SIGNATURE not in migrado


def test_migrate_sem_command_explicita_o_placeholder():
    """LaunchOptions sem %command% são ARGUMENTOS do jogo — a migração
    explicita o %command% antes deles (semântica idêntica, embrulhada)."""
    valor = f"{slo.IGNORE_SIGNATURE} -fullscreen"
    migrado = slo.migrate_value(valor)
    assert migrado == f"{slo.WRAPPER_LAUNCH} -fullscreen"


def test_migrate_e_idempotente():
    uma_vez = slo.migrate_value(LINHA_914)
    assert slo.migrate_value(uma_vez) == uma_vez


def test_strip_da_linha_914_preserva_shader_cache_byte_a_byte():
    """UX-04 (uninstall): sai a assinatura + SDL_JOYSTICK_HIDAPI=0
    co-ocorrente; `__GL_SHADER_*` e o %command% ficam intactos."""
    assert slo.strip_value(LINHA_914) == (
        "__GL_SHADER_DISK_CACHE=1 __GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1 %command%"
    )


def test_strip_nao_caca_hidapi_solto():
    """SDL_JOYSTICK_HIDAPI=0 SEM a assinatura é fix legítimo de controle de
    terceiros (o 8BitDo) — o strip nunca o remove sozinho."""
    valor = "SDL_JOYSTICK_HIDAPI=0 %command%"
    assert slo.strip_value(valor) == valor


def test_strip_remove_o_wrapper_e_colapsa_linha_que_era_so_nossa():
    assert slo.strip_value(slo.WRAPPER_LAUNCH) == ""


# --- lista de IGNORE ESTENDIDA por vírgula (achado MED da revisão) -----------

#: A usuária estendeu a var para esconder um 2º device (Pro Controller 057e).
#: Remover só o nosso pedaço deixaria `,0x057e/0x2009` (sem `=`) pendurado —
#: o env(1)/sh tenta EXECUTÁ-lo → ENOENT → o jogo NUNCA MAIS abre.
LINHA_ESTENDIDA = (
    "SDL_JOYSTICK_HIDAPI=0 "
    "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6,0x057e/0x2009 %command%"
)


def test_migrate_nao_toca_lista_ignore_estendida():
    assert slo.migrate_value(LINHA_ESTENDIDA) == LINHA_ESTENDIDA


def test_strip_nao_toca_lista_ignore_estendida():
    assert slo.strip_value(LINHA_ESTENDIDA) == LINHA_ESTENDIDA


def test_nenhum_caminho_deixa_fragmento_sem_igual_pendurado():
    """A regressão exata reproduzida pela revisão: `,0x057e/0x2009` órfão."""
    for resultado in (
        slo.migrate_value(LINHA_ESTENDIDA),
        slo.strip_value(LINHA_ESTENDIDA),
    ):
        for token in resultado.split():
            assert token == "%command%" or "=" in token, resultado


def test_has_poison_exige_token_completo():
    assert slo.has_poison(LINHA_914) is True
    assert slo.has_poison(LINHA_ESTENDIDA) is False
    assert slo.has_extended_ignore(LINHA_ESTENDIDA) is True
    assert slo.has_extended_ignore(LINHA_914) is False


def test_transform_pula_linha_estendida_nos_dois_modos():
    texto = _vdf({"1599660": LINHA_ESTENDIDA})
    for modo in ("migrate", "strip"):
        novo, mudadas = slo.transform_vdf_text(texto, modo)
        assert mudadas == 0, modo
        assert novo == texto, modo


def test_main_reporta_ignore_estendido_sem_tocar(tmp_path, monkeypatch, capsys):
    vdf = tmp_path / "localconfig.vdf"
    original = _vdf({"1599660": LINHA_ESTENDIDA})
    vdf.write_text(original, encoding="utf-8")
    monkeypatch.setattr(slo, "steam_running", lambda: False)
    monkeypatch.setattr(slo, "steam_game_running", lambda: False)
    rc = slo.main(["--migrate", "--vdf", str(vdf)])
    assert rc == 0
    assert vdf.read_text(encoding="utf-8") == original
    out = capsys.readouterr().out
    assert "ESTENDIDO" in out
    assert "manualmente" in out


def test_strip_remove_o_wrapper_preservando_o_resto():
    valor = f"{slo.WRAPPER_PREFIX} MANGOHUD=1 %command%"
    assert slo.strip_value(valor) == "MANGOHUD=1 %command%"


# --- transform_vdf_text (parse por linha + escaping) ------------------------


def test_transform_migrate_so_toca_linhas_envenenadas():
    texto = _vdf({"1599660": LINHA_914, "620": "MANGOHUD=1 %command%"})
    novo, mudadas = slo.transform_vdf_text(texto, "migrate")
    assert mudadas == 1
    assert slo.IGNORE_SIGNATURE not in novo
    # A linha do usuário fica byte a byte.
    assert '"MANGOHUD=1 %command%"' in novo
    # O wrapper entra ESCAPADO (aspas viram \" no formato KeyValues da Steam).
    assert slo._vdf_escape(slo.WRAPPER_LAUNCH) in novo
    # O resto do arquivo permanece intacto.
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
    # shader-cache da linha legada é preservado (UX-04).
    assert "__GL_SHADER_DISK_CACHE=1" in novo


def test_migrate_depois_strip_zera_o_nosso_rastro():
    texto = _vdf({"1599660": LINHA_914})
    migrado, _ = slo.transform_vdf_text(texto, "migrate")
    limpo, _ = slo.transform_vdf_text(migrado, "strip")
    assert '"LaunchOptions"\t\t""' in limpo


# --- process_vdf (arquivo, backup, dry-run, idempotência) -------------------


def test_process_vdf_dry_run_nao_toca_no_arquivo(tmp_path: Path):
    vdf = tmp_path / "localconfig.vdf"
    original = _vdf({"1599660": LINHA_914})
    vdf.write_text(original, encoding="utf-8")
    changed, diff = slo.process_vdf(vdf, "migrate", dry_run=True)
    assert changed == 1
    assert diff  # o diff sai para inspeção
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
    # Aplicar 2x é no-op (não cria segundo backup).
    changed2, _ = slo.process_vdf(vdf, "migrate")
    assert changed2 == 0
    assert len(list(tmp_path.glob("*.bak.*"))) == 1


# --- CLI: recusa honesta com a Steam viva + recusa de sandbox ----------------


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
    assert "regrava o arquivo ao sair" in out  # a mensagem diz o PORQUÊ


def test_main_recusa_com_jogo_da_steam_aberto(tmp_path, monkeypatch, capsys):
    """DEDUP-05 exigência 2: `steam -shutdown` com jogo aberto MATA o jogo —
    migrate E strip recusam (rc=3) em vez de derrubar progresso não salvo.
    Vale inclusive com --stop-steam (o caminho do install/uninstall)."""
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

    assert parou == []  # a Steam NUNCA foi derrubada com o jogo aberto
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
    """Steam Flatpak/Snap: o wrapper do host é invisível à sandbox — escrever
    o caminho lá quebraria o launch (DEDUP-04). Em vez de PULAR (deixando o
    veneno legado gravado para sempre), o migrate faz só o STRIP: o veneno sai
    e o wrapper NÃO é escrito na sandbox. O strip explícito continua permitido."""
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
    assert slo.IGNORE_SIGNATURE not in texto  # veneno removido
    assert slo._vdf_escape(slo.WRAPPER_PREFIX) not in texto  # wrapper NÃO entra na sandbox
    assert "sandbox" in capsys.readouterr().out

    rc = slo.main(["--strip", "--vdf", str(vdf)])
    assert rc == 0
    assert slo.IGNORE_SIGNATURE not in vdf.read_text(encoding="utf-8")


def test_main_status_relata_sem_tocar(tmp_path, monkeypatch, capsys):
    vdf = tmp_path / "localconfig.vdf"
    original = _vdf({"1599660": LINHA_914})
    vdf.write_text(original, encoding="utf-8")
    monkeypatch.setattr(slo, "steam_running", lambda: True)  # status nem liga
    rc = slo.main(["--status", "--vdf", str(vdf)])
    assert rc == 0
    assert vdf.read_text(encoding="utf-8") == original
    assert "veneno" in capsys.readouterr().out


# --- paridade com o resto da entrega ----------------------------------------


@pytest.mark.parametrize(
    "arquivo",
    ["install.sh", "uninstall.sh", "scripts/doctor.sh", "assets/hefesto-launch.sh"],
)
def test_caminho_do_wrapper_e_o_mesmo_em_todo_lugar(arquivo: str):
    """O caminho estável do wrapper é contrato entre módulo Python, install,
    uninstall, doctor e o próprio wrapper — drift aqui = wrapper órfão."""
    root = Path(__file__).resolve().parents[2]
    texto = (root / arquivo).read_text(encoding="utf-8")
    assert slo.WRAPPER_HOME_RELPATH in texto


def test_uninstall_desenvenena_antes_de_apagar_o_wrapper():
    """Ordem obrigatória do DEDUP-04: vdf ANTES do wrapper (a assimetria já
    quebrou o mic; aqui deixaria veneno sem dono => zero controles)."""
    root = Path(__file__).resolve().parents[2]
    texto = (root / "uninstall.sh").read_text(encoding="utf-8")
    pos_strip = texto.index("--strip")
    pos_rm_wrapper = texto.index('rm -f "${LAUNCH_WRAPPER}"')
    assert pos_strip < pos_rm_wrapper


def test_install_migra_fora_do_bloco_do_steam_input():
    """Achado MED da revisão: a migração DEDUP-05 (P0) é um passo PRÓPRIO —
    `--keep-steam-input` (opt-out SÓ do PSSupport) e a ausência do
    disable_steam_input.sh não podem pular o desenvenenamento em silêncio."""
    root = Path(__file__).resolve().parents[2]
    texto = (root / "install.sh").read_text(encoding="utf-8")
    # Passo dedicado existe...
    assert 'step "11b"' in texto
    # ...e a migração vem DEPOIS do `fi` que fecha o bloco do Steam Input
    # (a habilitação do guard é a última coisa dentro do bloco).
    pos_fim_bloco_steam_input = texto.index("guard do Steam Input habilitado")
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
    # O resto do bloco fica intacto (a linha nova NÃO substitui nada).
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


def test_apply_wrapper_pula_ignore_estendido_sem_tocar():
    texto = _vdf({"1599660": LINHA_ESTENDIDA, "620": ""})
    novo, aplicados, pulados = slo.apply_wrapper_vdf_text(texto)
    assert ("1599660", "ignore_estendido") in pulados
    assert aplicados == ["620"]
    # A linha estendida permanece byte a byte.
    assert slo.read_launch_options_by_appid(novo)["1599660"] == LINHA_ESTENDIDA


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
    # dry_run é preview (contagem do diálogo da GUI) — nem consulta a Steam.
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
    """Achado #6: um localconfig.vdf não-UTF-8 (byte latin-1 legado /
    multi-usuário) vira erro POR-VDF em vez de abortar a varredura inteira com
    UnicodeDecodeError — o vdf válido seguinte continua sendo processado."""
    monkeypatch.setattr(slo, "steam_running", lambda: False)
    monkeypatch.setattr(slo, "steam_game_running", lambda: False)
    ruim = tmp_path / "ruim" / "localconfig.vdf"
    ruim.parent.mkdir()
    ruim.write_bytes(b'"UserLocalConfigStore"\n{\n\xff byte invalido\n}\n')
    bom = tmp_path / "bom" / "localconfig.vdf"
    bom.parent.mkdir()
    bom.write_text(_vdf({"620": "MANGOHUD=1 %command%"}), encoding="utf-8")

    resultado = slo.apply_wrapper_to_all_games(vdfs=[ruim, bom])
    # O ruim é reportado como erro por-vdf; o bom foi aplicado (não abortou).
    assert [e["vdf"] for e in resultado["errors"]] == [str(ruim)]
    assert [a["appid"] for a in resultado["applied"]] == ["620"]
    assert slo.read_launch_options_by_appid(bom.read_text(encoding="utf-8"))[
        "620"
    ].startswith(slo.WRAPPER_PREFIX)


def test_main_strip_vdf_nao_utf8_nao_estoura_traceback(
    tmp_path, monkeypatch, capsys
):
    """Achado #6: no --strip do uninstall, um vdf não-UTF-8 vira ERRO por-vdf
    (rc=1) e o loop segue limpando os demais — nunca traceback/abort deixando o
    veneno IGNORE gravado nos vdfs restantes ("zero controles pós-uninstall")."""
    monkeypatch.setattr(slo, "steam_running", lambda: False)
    monkeypatch.setattr(slo, "steam_game_running", lambda: False)
    ruim = tmp_path / "ruim" / "localconfig.vdf"
    ruim.parent.mkdir()
    ruim.write_bytes(b'"UserLocalConfigStore"\n{\n\xff\n}\n')
    bom = tmp_path / "bom" / "localconfig.vdf"
    bom.parent.mkdir()
    bom.write_text(_vdf({"1599660": LINHA_914}), encoding="utf-8")

    rc = slo.main(["--strip", "--vdf", str(ruim), "--vdf", str(bom)])
    assert rc == 1  # houve erro por-vdf...
    out = capsys.readouterr().out
    assert "ERRO" in out
    assert str(ruim) in out
    # ...mas o vdf bom foi desenvenenado (a varredura não abortou no ruim).
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
