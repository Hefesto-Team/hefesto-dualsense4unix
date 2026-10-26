#!/usr/bin/env python3
"""A-OPCAO-QUE-A-STEAM-DESFAZ-APARECE-NO-DOCTOR-01 (08/10/2026).

A Steam é dona do `localconfig.vdf` e desfaz a escrita sem aviso. O `aplicar` das opções por
jogo já disse «aplicado» sobre uma linha que a Steam não leu (06/10); o doctor deu `[ OK ]`
com a opção sumida. O dono da tabela (`opcoes_por_jogo`) responde `conferir`, o contrato
`steam-localconfig` e o `doctor.sh` só repetem a resposta dele.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import contratos_de_fora as cf
from hefesto_dualsense4unix.integrations import opcoes_por_jogo as opj

RAIZ = Path(__file__).resolve().parents[2]
APPID = "990000021"
OPCOES = "VKD3D_CONFIG=no_upload_hvv %command%"
T = "\t"


def _vdf(linha_direta: str | None, linha_filha: str | None = None, appid: str = APPID) -> str:
    """O jogo na árvore canônica; a opção direta, a do bloco filho `cloud`, ou nenhuma."""
    direta = f'{T * 6}"LaunchOptions"{T * 2}"{linha_direta}"\n' if linha_direta else ""
    filha = (
        f'{T * 6}"cloud"\n{T * 6}{{\n{T * 7}"LaunchOptions"{T * 2}"{linha_filha}"\n{T * 6}}}\n'
        if linha_filha else ""
    )
    return (
        '"UserLocalConfigStore"\n{\n'
        f'{T}"Software"\n{T}{{\n{T * 2}"Valve"\n{T * 2}{{\n{T * 3}"Steam"\n{T * 3}{{\n'
        f'{T * 4}"apps"\n{T * 4}{{\n{T * 5}"{appid}"\n{T * 5}{{\n'
        f'{T * 6}"LastPlayed"{T * 2}"1791398598"\n{filha}{direta}'
        f'{T * 5}}}\n{T * 4}}}\n{T * 3}}}\n{T * 2}}}\n{T}}}\n}}\n'
    )


class Lar:
    """Um lar de mentira: Steam com uma conta, a tabela dela e o state do produto."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self.config = raiz / "config"
        self.estado = raiz / "state"
        self.vdf = raiz / ".steam/steam/userdata/1/config/localconfig.vdf"
        self.vdf.parent.mkdir(parents=True)
        opj.gravar({APPID: OPCOES}, config_home=self.config)

    def steam_escreve(self, texto: str) -> None:
        self.vdf.write_text(texto, encoding="utf-8")

    def aplicar(self) -> opj.Relato:
        return opj.aplicar(
            vdfs=[self.vdf], config_home=self.config, estado_home=self.estado)

    def conferir(self) -> dict[str, object]:
        return opj.conferir(
            vdfs=[self.vdf], config_home=self.config, estado_home=self.estado)

    def estados(self) -> list[str]:
        return [str(j["estado"]) for j in self.conferir()["jogos"]]  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def _a_steam_esta_fechada(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(opj, "steam_running", lambda: False)
    monkeypatch.setattr(opj, "steam_game_running", lambda: False)
    monkeypatch.setattr(opj, "ler_jogos_sem_wrapper", lambda path=None: [])


@pytest.fixture()
def lar(tmp_path: Path) -> Lar:
    return Lar(tmp_path)


def test_a_opcao_escrita_e_lida_de_volta_confere_ok(lar: Lar) -> None:
    lar.steam_escreve(_vdf("algo velho %command%"))
    assert lar.aplicar()["status"] == opj.APLICADO

    assert lar.estados() == [opj.OK]
    assert lar.conferir()["defeitos"] == []


def test_a_steam_que_desfaz_a_opcao_depois_e_nomeada(lar: Lar) -> None:
    """O defeito da sprint: a Steam regrava o arquivo e a opção some, sem aviso.

    ARRANQUE a anotação do `aplicar` no registro e este teste reprova: o jogo cai em
    `novo` («ainda não escrita»), que não é defeito, e o doctor volta a dar `[ OK ]`.
    """
    lar.steam_escreve(_vdf("algo velho %command%"))
    lar.aplicar()
    lar.steam_escreve(_vdf("algo velho %command%"))

    conferido = lar.conferir()

    assert [d["appid"] for d in conferido["defeitos"]] == [APPID]  # type: ignore[attr-defined]
    assert lar.estados() == [opj.DESFEITO_DEPOIS]


def test_a_releitura_que_desmente_a_escrita_fica_no_registro(
        lar: Lar, monkeypatch: pytest.MonkeyPatch) -> None:
    """A Steam regravou logo depois da escrita: o relato e o doctor dizem que foi desfeita."""
    lar.steam_escreve(_vdf("algo velho %command%"))
    antes = lar.vdf.read_text(encoding="utf-8")
    escreve = Path.write_text

    def steam_regrava(self: Path, dados: str, *args: object, **kw: object) -> int:
        feito = escreve(self, dados, *args, **kw)  # type: ignore[arg-type]
        if self.name == "localconfig.vdf":
            escreve(self, antes, encoding="utf-8")
        return feito

    monkeypatch.setattr(Path, "write_text", steam_regrava)
    relato = lar.aplicar()
    monkeypatch.undo()

    assert relato["status"] == opj.DESFEITO
    assert opj.ler_registro(lar.estado)[APPID]["resultado"] == opj.ESCRITO_E_DESFEITO
    assert lar.estados() == [opj.DESFEITO_NA_ESCRITA]


def test_a_opcao_que_ela_ainda_nao_aplicou_nao_e_defeito(lar: Lar) -> None:
    """Tabela nova, nada escrito: o `aplicar` ainda vai pôr, não há o que acusar."""
    lar.steam_escreve(_vdf("algo velho %command%"))

    assert lar.estados() == [opj.NOVO]
    assert lar.conferir()["defeitos"] == []


def test_a_opcao_so_no_bloco_filho_esta_fora_do_lugar(lar: Lar) -> None:
    """A Steam lê a linha FILHA DIRETA do jogo; a do `cloud` ela não lê (defeito de 06/10)."""
    querida = opj._valor_do_vdf(opj.linha_desejada(OPCOES, com_atalho=True))
    lar.steam_escreve(_vdf(None, linha_filha=querida))

    assert lar.estados() == [opj.FORA_DO_LUGAR]
    assert [d["estado"] for d in lar.conferir()["defeitos"]] == [  # type: ignore[attr-defined]
        opj.FORA_DO_LUGAR]


def test_o_jogo_que_a_conta_nao_tem_nao_entra(lar: Lar) -> None:
    lar.steam_escreve(_vdf("x %command%", appid="990000099"))

    assert lar.conferir() == {"jogos": [], "defeitos": []}


def test_tirar_o_jogo_da_tabela_tira_do_registro(lar: Lar) -> None:
    lar.steam_escreve(_vdf("algo velho %command%"))
    lar.aplicar()
    assert APPID in opj.ler_registro(lar.estado)

    assert opj.tirar(APPID, config_home=lar.config, estado_home=lar.estado) is True

    assert APPID not in opj.ler_registro(lar.estado)


def test_o_dry_run_nao_anota_nada(lar: Lar) -> None:
    lar.steam_escreve(_vdf("algo velho %command%"))
    opj.aplicar(vdfs=[lar.vdf], config_home=lar.config, estado_home=lar.estado, dry_run=True)

    assert not opj.registro_path(lar.estado).exists()


def test_o_registro_que_nao_abre_e_vazio_e_nunca_derruba(tmp_path: Path) -> None:
    caminho = opj.registro_path(tmp_path)
    caminho.parent.mkdir(parents=True)
    caminho.write_text("{não é json", encoding="utf-8")

    assert opj.ler_registro(tmp_path) == {}


def test_duas_contas_sem_resposta_o_conferir_nomeia_a_conta_e_o_aplicar_diz_o_arquivo(
        tmp_path: Path) -> None:
    """O `aplicar` escrevia `{p['vdf']}` LITERAL: faltava o `f` na segunda metade da frase.

    ARRANQUE o `f` e este teste reprova.
    """
    raiz = tmp_path / ".steam/steam"
    vdfs = []
    for conta in ("111", "222"):
        v = raiz / "userdata" / conta / "config" / "localconfig.vdf"
        v.parent.mkdir(parents=True)
        v.write_text(_vdf("x %command%"), encoding="utf-8")
        vdfs.append(v)
    config, estado = tmp_path / "config", tmp_path / "state"
    opj.gravar({APPID: OPCOES}, config_home=config)

    relato = opj.aplicar(vdfs=vdfs, config_home=config, estado_home=estado)
    conferido = opj.conferir(vdfs=vdfs, config_home=config, estado_home=estado)

    assert relato["status"] == opj.ERRO
    for erro in relato["erros"]:
        assert "{p[" not in erro["reason"], erro
        assert erro["vdf"] in erro["reason"], erro
    assert {d["estado"] for d in conferido["defeitos"]} == {opj.SEM_CONTA}  # type: ignore[attr-defined]


def test_o_cli_conferir_imprime_o_json_e_sai_0(
        lar: Lar, capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(lar.config))
    monkeypatch.setenv("XDG_STATE_HOME", str(lar.estado))
    lar.steam_escreve(_vdf("algo velho %command%"))
    lar.aplicar()
    lar.steam_escreve(_vdf("algo velho %command%"))

    assert opj.main(["--conferir", "--vdf", str(lar.vdf)]) == 0

    dito = json.loads(capsys.readouterr().out)
    assert [d["estado"] for d in dito["defeitos"]] == [opj.DESFEITO_DEPOIS]


def _loginusers(raiz: Path, logada: str) -> None:
    """O `loginusers.vdf` com as contas 111 e 222, a `logada` marcada `MostRecent`."""
    base = opj._BASE_DO_STEAMID64
    blocos = "".join(
        f'\t"{base + int(c)}"\n\t{{\n\t\t"AccountName"\t\t"c{c}"\n'
        + ('\t\t"MostRecent"\t\t"1"\n' if c == logada else "")
        + '\t\t"Timestamp"\t\t"1700000000"\n\t}\n'
        for c in ("111", "222")
    )
    (raiz / "config").mkdir(exist_ok=True)
    (raiz / "config" / "loginusers.vdf").write_text(
        '"users"\n{\n' + blocos + "}\n", encoding="utf-8")


def test_a_conta_que_a_steam_trocou_nao_herda_o_registro_da_outra(tmp_path: Path) -> None:
    """O registro é da conta em que o `aplicar` escreveu.

    A Steam passa a abrir a conta 222, onde o Hefesto nunca escreveu: a opção ali é `novo`,
    não `desfeito`. ARRANQUE a comparação da conta no `conferir` e este teste reprova: o
    doctor acusaria «a Steam desfez» uma opção que nunca esteve naquela conta.
    """
    raiz = tmp_path / ".steam/steam"
    vdfs = []
    for conta in ("111", "222"):
        v = raiz / "userdata" / conta / "config" / "localconfig.vdf"
        v.parent.mkdir(parents=True)
        v.write_text(_vdf("algo velho %command%"), encoding="utf-8")
        vdfs.append(v)
    config, estado = tmp_path / "config", tmp_path / "state"
    opj.gravar({APPID: OPCOES}, config_home=config)
    _loginusers(raiz, "111")
    assert opj.aplicar(vdfs=vdfs, config_home=config, estado_home=estado)["status"] == (
        opj.APLICADO)
    assert opj.ler_registro(estado)[APPID]["conta"] == "111"

    _loginusers(raiz, "222")
    conferido = opj.conferir(vdfs=vdfs, config_home=config, estado_home=estado)

    assert [(j["estado"], Path(j["vdf"]).parts[-3]) for j in conferido["jogos"]] == [
        (opj.NOVO, "222")]
    assert conferido["defeitos"] == []


def test_o_json_continua_sendo_a_tabela(
        lar: Lar, capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch) -> None:
    """O `ensaio-do-engasgo.sh` lê a TABELA pelo `--json` (`opcao_de`): o relato e o
    `--conferir` não tomam o lugar dela. TROQUE o `--json` pelo `conferir` e este teste reprova.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(lar.config))
    monkeypatch.setenv("XDG_STATE_HOME", str(lar.estado))
    lar.steam_escreve(_vdf("algo velho %command%"))
    lar.aplicar()

    assert opj.main(["--json"]) == 0

    assert json.loads(capsys.readouterr().out) == {APPID: OPCOES}
    ensaio = (RAIZ / "scripts/ensaio-do-engasgo.sh").read_text(encoding="utf-8")
    assert '"$DONO" --json' in ensaio


def _ambiente(lar: Lar) -> cf.Ambiente:
    return cf.Ambiente(
        rodar=lambda argv: cf.Falta("sem a ferramenta"),
        home=lar.raiz,
        env={"XDG_CONFIG_HOME": str(lar.config), "XDG_STATE_HOME": str(lar.estado)},
        raiz=lar.raiz / "raiz",
    )


def _linha_do_contrato(amb: cf.Ambiente) -> tuple[str, str]:
    ((tag, msg),) = cf.linhas_do_doctor(
        amb, [c for c in cf.CONTRATOS if c.id == "steam-localconfig"])
    return tag, msg


def test_o_contrato_nomeia_a_opcao_que_a_steam_desfez(lar: Lar) -> None:
    """ARRANQUE a chamada do `conferir` na sonda e este teste reprova: o doctor dá `[ OK ]`."""
    lar.steam_escreve(_vdf("algo velho %command%"))
    lar.aplicar()
    lar.steam_escreve(_vdf("algo velho %command%"))

    tag, msg = _linha_do_contrato(_ambiente(lar))

    assert tag != "[ OK ]", msg
    assert "steam-localconfig" in msg and APPID in msg and "opç" in msg


def test_o_contrato_e_ok_com_a_opcao_no_lugar(lar: Lar) -> None:
    lar.steam_escreve(_vdf("algo velho %command%"))
    lar.aplicar()

    assert _linha_do_contrato(_ambiente(lar))[0] == "[ OK ]"


def test_o_censo_declara_que_o_doctor_ve_a_conta_da_steam() -> None:
    """A linha `cfg:loginusers.vdf` do censo deixa de dizer `-`: a sonda a pergunta de fato."""
    contrato = next(c for c in cf.CONTRATOS if c.id == "steam-localconfig")
    assert "cfg:loginusers.vdf" in contrato.cobre
    csv = (RAIZ / "docs/data/contratos-de-fora.csv").read_text(encoding="utf-8")
    linha = next(li for li in csv.splitlines()
                 if "opcoes_por_jogo.py,cfg:loginusers.vdf" in li)
    assert "contrato:steam-localconfig" in linha


def _roda_o_check(lar: Lar, raiz_do_codigo: Path = RAIZ) -> str:
    texto = (RAIZ / "scripts/doctor.sh").read_text(encoding="utf-8")
    funcoes = ""
    for nome in ("check_opcoes_por_jogo", "_rotulo_do_appid"):
        achado = re.search(rf"^{nome}\(\) \{{.*?^\}}\n", texto, re.M | re.S)
        assert achado, f"perdi a função {nome} do doctor.sh"
        funcoes += achado.group(0)
    prelude = (
        "pass() { printf '[ OK ] %s\\n' \"$*\"; }\n"
        "fail() { printf '[FAIL] %s\\n' \"$*\"; }\n"
        "warn() { printf '[WARN] %s\\n' \"$*\"; }\n"
        "info() { :; }\n"
        f'ROOT_DIR="{raiz_do_codigo}"\n{funcoes}check_opcoes_por_jogo\n'
    )
    r = subprocess.run(
        ["bash", "-c", prelude], capture_output=True, text=True, timeout=60, check=False,
        stdin=subprocess.DEVNULL, cwd=str(RAIZ),
        env={
            "PATH": "/usr/bin:/bin", "HOME": str(lar.raiz), "LC_ALL": "C.UTF-8",
            "XDG_CONFIG_HOME": str(lar.config), "XDG_STATE_HOME": str(lar.estado),
        },
    )
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


def test_o_doctor_sh_nomeia_o_jogo_que_perdeu_a_opcao(lar: Lar) -> None:
    lar.steam_escreve(_vdf("algo velho %command%"))
    lar.aplicar()
    lar.steam_escreve(_vdf("algo velho %command%"))

    saida = _roda_o_check(lar)

    assert "[WARN]" in saida and "[FAIL]" not in saida, saida
    assert "steam-localconfig" in saida and APPID in saida and "--conferir" in saida, saida


def test_o_doctor_sh_da_ok_com_a_opcao_no_lugar(lar: Lar) -> None:
    lar.steam_escreve(_vdf("algo velho %command%"))
    lar.aplicar()

    assert "[ OK ]" in _roda_o_check(lar)


def test_o_doctor_sh_fica_calado_com_a_tabela_vazia(lar: Lar) -> None:
    opj.gravar({}, config_home=lar.config)
    lar.steam_escreve(_vdf("algo velho %command%"))

    assert _roda_o_check(lar).strip() == ""


def test_o_doctor_sh_repete_o_conferir_e_nao_reabre_o_vdf(lar: Lar, tmp_path: Path) -> None:
    """O doctor só repete a resposta do dono: com um `--conferir` dublê, o aviso é o do dublê.

    O vdf do lar diz que a opção está no lugar (o `aplicar` acabou de pô-la); o dublê responde
    `fora_do_lugar` duas vezes, e o doctor diz `fora_do_lugar` uma vez. COPIE a regra para o
    `doctor.sh` (reler o vdf) e este teste reprova: ele daria `[ OK ]`.
    """
    lar.steam_escreve(_vdf("algo velho %command%"))
    lar.aplicar()
    pacote = tmp_path / "duble" / "src" / "hefesto_dualsense4unix" / "integrations"
    pacote.mkdir(parents=True)
    for init in (pacote.parent / "__init__.py", pacote / "__init__.py"):
        init.write_text("", encoding="utf-8")
    defeito = {"appid": APPID, "estado": opj.FORA_DO_LUGAR, "vdf": str(lar.vdf)}
    resposta = {"jogos": [defeito], "defeitos": [defeito, defeito]}
    (pacote / "opcoes_por_jogo.py").write_text(
        "import json\n"
        "AVISO_DO_DEFEITO = {'fora_do_lugar': 'resposta do duble'}\n"
        "if __name__ == '__main__':\n"
        f"    print(json.dumps({resposta!r}))\n",
        encoding="utf-8",
    )

    saida = _roda_o_check(lar, raiz_do_codigo=tmp_path / "duble")

    assert "[ OK ]" not in saida, saida
    assert saida.count("[WARN]") == 1 and "resposta do duble" in saida, saida


def test_o_doctor_sh_chama_o_check_na_cadeia() -> None:
    texto = (RAIZ / "scripts/doctor.sh").read_text(encoding="utf-8")
    assert len(re.findall(r"^\s+check_opcoes_por_jogo$", texto, re.M)) == 1


def test_o_registro_e_estado_do_install_e_o_uninstall_o_tira() -> None:
    from hefesto_dualsense4unix.utils import memoria_dos_controles as m

    assert m.CLASSIFICACAO[opj.REGISTRO_BASENAME][0] == "install"
    assert opj.REGISTRO_BASENAME in (RAIZ / "uninstall.sh").read_text(encoding="utf-8")
