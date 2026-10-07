"""A catraca da origem tem de MORDER: três números que só descem."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts" / "check_a_origem.py"

DONO = "src/hefesto_dualsense4unix/dono.py"
FORA = "src/hefesto_dualsense4unix/aba.py"

_CABECALHO = "comportamento,aba,dono,onde_html,veredito,economia_linhas,razao\n"
_EIXOS = ("transporte", "modo", "mascara", "jogador", "modelo")


def _modulo():
    spec = importlib.util.spec_from_file_location("_portao_a_origem", PORTAO)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_portao_a_origem"] = mod
    spec.loader.exec_module(mod)
    return mod


def _escreve(raiz: Path, rel: str, texto: str) -> None:
    destino = raiz / rel
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")


@pytest.fixture
def arvore(tmp_path, monkeypatch):
    """Uma árvore mínima, sem git, com o dono de cada eixo e o teto já gravado."""
    monkeypatch.delenv("HEFESTO_ORIGEM", raising=False)
    monkeypatch.delenv("HEFESTO_BASE_DA_LEVA", raising=False)
    linhas = "".join(
        f'eixo.{e}/dono,,dono.py:Dono,,EIXO,,"o dono do eixo {e} nesta árvore"\n'
        for e in _EIXOS)
    _escreve(tmp_path, "docs/data/donos-de-comportamento.csv", _CABECALHO + linhas)
    _escreve(tmp_path, "docs/data/mapa-controles.csv", "chave,x\naudio.alto_falante,1\n")
    _escreve(tmp_path, "docs/data/decisoes-de-produto.csv", "id,x\nD-UMA-DECISAO,1\n")
    _escreve(tmp_path, DONO, "class Dono:\n    pass\n")
    _escreve(tmp_path, FORA, "def f(x):\n    return x\n")
    mod = _modulo()

    def rodar(*extra: str, paga: bool = True) -> int:
        """`paga`: o crescimento já traz uma Origem, para o teste medir só o que quer medir."""
        origem = ["--origem", "audio.alto_falante"] if paga and "--origem" not in extra \
            and "--aceitar" not in extra and "--forcar-piso" not in extra else []
        return mod.main(["--raiz", str(tmp_path), *extra, *origem])

    assert rodar("--aceitar") == 0
    return tmp_path, mod, rodar


def _teto(raiz: Path, nome: str) -> dict:
    registro = json.loads((raiz / "docs/data/a-catraca-da-origem.json").read_text())
    return registro["medidas"][nome]


def test_a_arvore_de_partida_passa(arvore):
    _raiz, _mod, rodar = arvore
    assert rodar() == 0


# 1. O caso especial fora do dono


def test_ramo_por_transporte_fora_do_dono_reprova(arvore):
    raiz, _mod, rodar = arvore
    _escreve(raiz, FORA,
             'def f(c):\n    if c.transporte == "bt":\n        return 1\n    return 0\n')
    assert rodar() == 1


def test_o_mesmo_ramo_no_dono_passa(arvore):
    raiz, _mod, rodar = arvore
    _escreve(raiz, DONO, (
        'class Dono:\n    def f(self, c):\n        if c.transporte == "bt":\n'
        "            return 1\n"))
    assert rodar() == 0


@pytest.mark.parametrize("ramo", [
    'if modo == "xbox":\n        return 1',
    'if mascara in ("dualsense", "xbox360"):\n        return 1',
    "if jogador == 1:\n        return 1",
    "if vid == 0x054C:\n        return 1",
    'x = 1 if via == "usb" else 0',
])
def test_cada_eixo_e_medido(arvore, ramo):
    raiz, _mod, rodar = arvore
    _escreve(raiz, FORA, f"def f(modo, mascara, jogador, vid, via):\n    {ramo}\n    return 0\n")
    assert rodar() == 1


@pytest.mark.parametrize("ramo", [
    'RADIO = "bt"\n\n\ndef f(c):\n    if c.transporte == RADIO:\n        return 1\n    return 0\n',
    'VID_SONY: int = 0x054C\n\n\ndef f(vid):\n    return 1 if vid == VID_SONY else 0\n',
])
def test_a_constante_com_nome_continua_constante(arvore, ramo):
    """Dar nome à constante não tira o ramo da conta: era o desvio mais barato."""
    raiz, _mod, rodar = arvore
    _escreve(raiz, FORA, ramo)
    assert rodar() == 1


def test_comentario_e_string_nao_contam(arvore):
    raiz, _mod, rodar = arvore
    _escreve(raiz, FORA, (
        'def f(x):\n    # if transporte == "bt":\n    msg = "if transporte == \'bt\'"\n'
        '    """if modo == \\"xbox\\": """\n    return msg\n'))
    assert rodar() == 0


def test_constante_fora_do_vocabulario_nao_conta(arvore):
    raiz, _mod, rodar = arvore
    _escreve(raiz, FORA, "def f(modo):\n    if modo != 432:\n        return 1\n    return 0\n")
    assert rodar() == 0


def test_eixo_sem_dono_declarado_recusa(arvore):
    raiz, _mod, rodar = arvore
    csv_ = raiz / "docs/data/donos-de-comportamento.csv"
    csv_.write_text("".join(
        linha for linha in csv_.read_text().splitlines(keepends=True)
        if "eixo.modelo" not in linha))
    assert rodar() == 2


# 2. O remendo de sintoma


@pytest.mark.parametrize("remendo", [
    "time.sleep(0.5)",
    "client.pedir(timeout=5)",
    "try:\n        pass\n    except OSError:\n        pass",
])
def test_remendo_novo_reprova(arvore, remendo):
    raiz, _mod, rodar = arvore
    _escreve(raiz, FORA, f"import time\n\n\ndef f(client):\n    {remendo}\n")
    assert rodar() == 1


def test_laco_de_nova_tentativa_reprova(arvore):
    raiz, _mod, rodar = arvore
    _escreve(raiz, FORA, (
        "import time\n\n\ndef f():\n    for _ in range(3):\n        try:\n"
        "            return g()\n        except OSError as e:\n            log(e)\n"
        "        time.sleep(1)\n"))
    assert rodar() == 1


def test_remendo_que_sai_desce_o_teto_sozinho(arvore):
    raiz, _mod, rodar = arvore
    _escreve(raiz, FORA, "import time\n\n\ndef f():\n    time.sleep(1)\n    time.sleep(2)\n")
    assert rodar("--forcar-piso", "remendos-de-sintoma", "dois remendos de partida") == 0
    assert _teto(raiz, "remendos-de-sintoma")["por_item"] == {"aba.py": 2}
    _escreve(raiz, FORA, "import time\n\n\ndef f():\n    time.sleep(1)\n")
    assert rodar() == 0
    assert _teto(raiz, "remendos-de-sintoma")["por_item"] == {"aba.py": 1}


def test_o_remendo_novo_nao_se_esconde_atras_de_um_velho_que_saiu(arvore):
    raiz, _mod, rodar = arvore
    _escreve(raiz, FORA, "import time\n\n\ndef f():\n    time.sleep(1)\n")
    assert rodar("--forcar-piso", "remendos-de-sintoma", "um remendo de partida") == 0
    # o velho sai de `aba.py` e um novo nasce em outro arquivo: o total não muda
    _escreve(raiz, FORA, "def f():\n    return 1\n")
    _escreve(raiz, "src/hefesto_dualsense4unix/outro.py",
             "import time\n\n\ndef g():\n    time.sleep(1)\n")
    assert rodar() == 1


# 3. O tamanho exige a origem


def _cresce(raiz: Path, linhas: int = 100) -> None:
    _escreve(raiz, "src/hefesto_dualsense4unix/cresceu.py", "x = 1\n" * linhas)


def test_cem_linhas_sem_origem_reprovam(arvore):
    raiz, _mod, rodar = arvore
    _cresce(raiz)
    assert rodar(paga=False) == 1


def test_cem_linhas_com_origem_do_mapa_passam(arvore):
    raiz, _mod, rodar = arvore
    _cresce(raiz)
    assert rodar("--origem", "audio.alto_falante") == 0


def test_a_origem_da_decisao_dela_tambem_vale(arvore):
    raiz, _mod, rodar = arvore
    _cresce(raiz)
    assert rodar("--origem", "D-UMA-DECISAO") == 0


def test_origem_que_nao_existe_reprova(arvore):
    raiz, _mod, rodar = arvore
    _cresce(raiz)
    assert rodar("--origem", "id-que-ninguem-cadastrou") == 1


def test_o_tamanho_que_desce_regrava_o_teto_menor(arvore):
    raiz, _mod, rodar = arvore
    antes = _teto(raiz, "tamanho")["piso"]
    (raiz / FORA).write_text("")
    assert rodar(paga=False) == 0
    assert _teto(raiz, "tamanho")["piso"] < antes


def test_o_teto_nunca_sobe_sozinho(arvore):
    raiz, _mod, rodar = arvore
    antes = _teto(raiz, "tamanho")["piso"]
    _cresce(raiz)
    assert rodar("--origem", "audio.alto_falante") == 0
    assert _teto(raiz, "tamanho")["piso"] == antes


# 4. A mordida da própria régua


def test_com_o_detector_desligado_os_tres_casos_passam(arvore, monkeypatch):
    """Sem o detector de AST, os casos 1 e 2 passam: é ele que morde, e o teste acima prova."""
    raiz, mod, rodar = arvore
    _escreve(raiz, FORA, (
        'import time\n\n\ndef f(c):\n    time.sleep(0.5)\n'
        '    if c.transporte == "bt":\n        return 1\n    return 0\n'))
    assert rodar() == 1
    monkeypatch.setattr(mod, "ramos_de_eixo", lambda fonte: [])
    monkeypatch.setattr(mod, "remendos", lambda fonte: [])
    assert rodar() == 0


def test_os_donos_da_casa_declaram_os_cinco_eixos():
    mod = _modulo()
    donos = mod.donos_dos_eixos(RAIZ)
    assert set(donos) == set(_EIXOS)
    for eixo, arquivos in donos.items():
        for arquivo in arquivos:
            assert (RAIZ / mod.PACOTE / arquivo).exists(), f"o dono de {eixo} sumiu: {arquivo}"


# 5. A faixa de commits: a Origem vem da mensagem, que é o que o cherry-pick leva


def _git(raiz: Path, *args: str) -> str:
    import subprocess

    ambiente = {
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@exemplo.invalid",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@exemplo.invalid",
        "PATH": os.environ["PATH"], "HOME": str(raiz),
    }
    return subprocess.run(["git", *args], cwd=raiz, env=ambiente, check=True,
                          capture_output=True, text=True).stdout.strip()


def _commita_o_crescimento(raiz: Path, mensagem: str) -> str:
    _git(raiz, "init", "-q")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "base")
    base = _git(raiz, "rev-parse", "HEAD")
    _cresce(raiz)
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", mensagem)
    return base


def test_a_origem_no_commit_da_faixa_paga_o_crescimento(arvore):
    raiz, _mod, rodar = arvore
    base = _commita_o_crescimento(raiz, "feat(x): cresce\n\nOrigem: audio.alto_falante")
    assert rodar("--base", base, paga=False) == 0


def test_o_commit_da_faixa_sem_origem_nao_paga(arvore):
    raiz, _mod, rodar = arvore
    base = _commita_o_crescimento(raiz, "feat(x): cresce sem dizer por quê")
    assert rodar("--base", base, paga=False) == 1


def test_a_faixa_e_a_leva_e_nao_encolhe_quando_o_teto_se_regrava(arvore):
    """A Origem paga pela leva inteira: um commit do teto no meio não a apaga."""
    raiz, _mod, rodar = arvore
    _git(raiz, "init", "-q", "-b", "dev")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "base")
    _git(raiz, "checkout", "-q", "-b", "integra/leva")
    _cresce(raiz)
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "feat(x): cresce\n\nOrigem: audio.alto_falante")
    teto = raiz / "docs/data/a-catraca-da-origem.json"
    teto.write_text(teto.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "chore(catraca): o teto se regravou")
    assert rodar(paga=False) == 0
    _git(raiz, "checkout", "-q", "dev")
    _git(raiz, "merge", "-q", "--ff-only", "integra/leva")
    assert rodar(paga=False) == 1, "no dev, a faixa vazia não pode pagar o que o teto não subiu"


# 6. O pagamento viaja com o crescimento: o fecho registra a subida ANTES do merge ff

CADERNO = "docs/data/a-catraca-da-origem.json"
FECHO = RAIZ / "docs" / "process" / "ferramentas-da-leva" / "fecho.sh"
PAGA = "feat(x): cresce\n\nOrigem: audio.alto_falante"


def _caderno(raiz: Path) -> bytes:
    return (raiz / CADERNO).read_bytes()


def _integracao(raiz: Path, mensagem: str) -> None:
    """O `dev` com o teto gravado e uma integração que cresce com a `mensagem` no commit.

    Depois do crescimento a integração ainda regrava o teto (outra medida desceu): é o que,
    no `dev`, tira a `Origem:` da faixa, que passa a começar no último commit do teto.
    """
    _git(raiz, "init", "-q", "-b", "dev")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "base")
    _git(raiz, "checkout", "-q", "-b", "integra/leva")
    _cresce(raiz)
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", mensagem)
    teto = raiz / CADERNO
    teto.write_text(teto.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    _git(raiz, "add", CADERNO)
    _git(raiz, "commit", "-q", "-m", "chore(catraca): o teto se regravou")


def _desce_ao_dev(raiz: Path) -> None:
    _git(raiz, "checkout", "-q", "dev")
    _git(raiz, "merge", "-q", "--ff-only", "integra/leva")


def test_o_passo_do_fecho_leva_o_pagamento_ao_dev(arvore):
    """O estado de 07/10: pago na integração, vermelho no `dev`. Com o passo, o `dev` herda."""
    raiz, _mod, rodar = arvore
    antes = _teto(raiz, "tamanho")["piso"]
    _integracao(raiz, PAGA)
    assert rodar("--registrar-subida", paga=False) == 0
    tamanho = _teto(raiz, "tamanho")
    assert tamanho["piso"] > antes
    subida = tamanho["subidas"][-1]
    assert (subida["de"], subida["para"]) == (antes, tamanho["piso"])
    assert "audio.alto_falante" in subida["razao"], "a razão diz as Origem que pagaram"
    _git(raiz, "add", CADERNO)
    _git(raiz, "commit", "-q", "-m", "chore(catraca): o piso sobe")
    assert rodar(paga=False) == 0, "na integração, com o teto novo"
    _desce_ao_dev(raiz)
    assert rodar(paga=False) == 0, "no dev, a faixa vazia não precisa pagar o que o teto já subiu"


def test_sem_o_passo_do_fecho_o_mesmo_dev_fica_vermelho(arvore):
    """A mordida: arrancado o passo, o `dev` fica vermelho como hoje (a faixa dele é vazia)."""
    raiz, _mod, rodar = arvore
    _integracao(raiz, PAGA)
    assert rodar(paga=False) == 0, "a integração passa: a faixa traz a Origem"
    _desce_ao_dev(raiz)
    assert rodar(paga=False) == 1


def test_crescimento_sem_origem_nao_sobe_piso_nenhum(arvore):
    raiz, _mod, rodar = arvore
    _integracao(raiz, "feat(x): cresce sem dizer por quê")
    antes = _caderno(raiz)
    assert rodar("--registrar-subida", paga=False) == 1
    assert _caderno(raiz) == antes


def test_origem_que_ninguem_cadastrou_tambem_nao_sobe_piso(arvore):
    raiz, _mod, rodar = arvore
    _integracao(raiz, "feat(x): cresce\n\nOrigem: id-que-ninguem-cadastrou")
    antes = _caderno(raiz)
    assert rodar("--registrar-subida", paga=False) == 1
    assert _caderno(raiz) == antes


def test_registrar_a_subida_e_idempotente_e_sem_crescimento_nao_faz_nada(arvore):
    raiz, _mod, rodar = arvore
    inicial = _caderno(raiz)
    assert rodar("--registrar-subida", paga=False) == 0, "sem crescimento: nada a registrar"
    assert _caderno(raiz) == inicial
    _integracao(raiz, PAGA)
    assert rodar("--registrar-subida", paga=False) == 0
    registrado = _caderno(raiz)
    assert registrado != inicial
    assert rodar("--registrar-subida", paga=False) == 0
    assert _caderno(raiz) == registrado, "a segunda corrida não acrescenta subida"
    assert len(_teto(raiz, "tamanho")["subidas"]) == 1


def test_o_conferir_diz_o_que_registraria_sem_gravar(arvore):
    raiz, _mod, rodar = arvore
    _integracao(raiz, PAGA)
    antes = _caderno(raiz)
    assert rodar("--registrar-subida", "--conferir", paga=False) == 1
    assert _caderno(raiz) == antes
    assert rodar("--conferir", paga=False) == 2, "--conferir sozinho não é um modo"
    assert rodar("--registrar-subida", "--aceitar", paga=False) == 2
    assert rodar("--registrar-subida", "--forcar-piso", "tamanho", "x", paga=False) == 2
    assert _caderno(raiz) == antes


def _fecho_de_brinquedo(raiz: Path, rodar, mensagem: str, tmp: Path):
    """O `fecho.sh` de verdade, com o brinquedo como integração e uma casa de mentira."""
    import shutil

    if not FECHO.exists():
        pytest.skip("o fecho.sh mora em docs/process, que o git ignora: clone limpo não o tem")
    for nome in ("check_a_origem.py", "catraca.py"):
        destino = raiz / "scripts" / nome
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RAIZ / "scripts" / nome, destino)
    assert rodar("--forcar-piso", "tamanho", "a base do teste traz os dois scripts") == 0
    _integracao(raiz, mensagem)
    casa = tmp / "casa"
    casa.mkdir()
    (casa / "leva.env").write_text(
        f"MESA={raiz}\nVOO={tmp}\nINT={raiz}\nBRANCH=integra/leva\nPY={sys.executable}\n",
        encoding="utf-8")
    ambiente = {
        **os.environ, "LEVA": "teste", "CASA": str(casa), "TMPDIR": str(tmp), "HOME": str(raiz),
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@exemplo.invalid",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@exemplo.invalid",
    }

    def fecho(*args: str):
        import subprocess

        return subprocess.run(["bash", str(FECHO), *args], cwd=raiz, env=ambiente,
                              capture_output=True, text=True, check=False)

    return fecho


def test_o_fecho_registra_a_subida_e_commita_so_o_caderno(arvore, tmp_path_factory):
    raiz, _mod, rodar = arvore
    fecho = _fecho_de_brinquedo(
        raiz, rodar, PAGA, tmp_path_factory.mktemp("fecho"))
    topo = _git(raiz, "rev-parse", "HEAD")
    # O índice da integração pode ter o que quem coordena já adicionou: o passo não o leva junto.
    (raiz / "outro.bin").write_bytes(b"\x00")
    _git(raiz, "add", "outro.bin")
    conferido = fecho("--so", "catraca", "--conferir")
    assert conferido.returncode == 1 and "rodaria: catraca" in conferido.stdout, conferido.stdout
    assert _git(raiz, "rev-parse", "HEAD") == topo, "o --conferir não commita"
    r = fecho("--so", "catraca")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "piso do tamanho registrado e commitado" in r.stdout
    arvore_nova = _git(raiz, "write-tree")[:12]
    assert arvore_nova in r.stdout, "os recibos seguintes são da árvore nova do índice"
    assert _git(raiz, "log", "-1", "--format=%s").startswith("chore(catraca)")
    assert _git(raiz, "show", "--name-only", "--format=").splitlines() == [CADERNO]
    assert _git(raiz, "diff", "--cached", "--name-only").splitlines() == ["outro.bin"], (
        "o que já estava no índice segue no índice, fora do commit da catraca")
    _git(raiz, "rm", "-q", "--cached", "outro.bin")
    (raiz / "outro.bin").unlink()
    commit = _git(raiz, "rev-parse", "HEAD")
    outra = fecho("--so", "catraca")
    assert outra.returncode == 0 and "o piso não precisou subir" in outra.stdout, outra.stdout
    assert _git(raiz, "rev-parse", "HEAD") == commit, "idempotente: a segunda corrida não commita"
    _desce_ao_dev(raiz)
    assert rodar(paga=False) == 0, "o dev que recebe o merge ff do fecho fica verde"


def test_o_fecho_sem_o_passo_catraca_deixa_o_dev_vermelho(arvore, tmp_path_factory):
    """A mordida do fecho.sh: `--sem catraca` não registra nada, e o dev reprova como hoje."""
    raiz, _mod, rodar = arvore
    fecho = _fecho_de_brinquedo(
        raiz, rodar, PAGA, tmp_path_factory.mktemp("fecho"))
    topo = _git(raiz, "rev-parse", "HEAD")
    assert fecho("--so", "catraca", "--sem", "catraca").returncode == 0
    assert _git(raiz, "rev-parse", "HEAD") == topo
    _desce_ao_dev(raiz)
    assert rodar(paga=False) == 1


def test_o_fecho_para_no_crescimento_sem_origem(arvore, tmp_path_factory):
    raiz, _mod, rodar = arvore
    fecho = _fecho_de_brinquedo(
        raiz, rodar, "feat(x): cresce sem dizer por quê", tmp_path_factory.mktemp("fecho"))
    topo = _git(raiz, "rev-parse", "HEAD")
    antes = _caderno(raiz)
    r = fecho("--so", "catraca")
    assert r.returncode == 1 and "VERMELHO em catraca" in r.stdout, r.stdout
    assert _git(raiz, "rev-parse", "HEAD") == topo and _caderno(raiz) == antes
