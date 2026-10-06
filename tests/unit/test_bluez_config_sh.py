"""RADIO-ABERTO-01/E1-bis — a cura de `confirm` chega mesmo ao disco?

O DEFEITO, MEDIDO em 06/08/2026 na máquina do usuário:

    /etc/bluetooth/main.conf:25  JustWorksRepairing=always

dentro do bloco ``# >>> hefesto bluetooth >>>`` — ou seja, **escrito por uma
versão anterior deste próprio projeto**. Os assets passaram para ``confirm`` em
05/08 (sprint RADIO-ABERTO-01, entrega E1). O valor perigoso continuou no disco
por quatro dias porque a única coisa que reescreve aquele arquivo é uma
execução do ``install.sh``, e não houve nenhuma entre 02/08 (último backup
gravado pelo install) e 06/08.

**A E1 estava escrita e não chegava à máquina.** Nenhum teste podia acusar
isso: os portões que existiam (``test_radio_aberto_01.py``,
``test_bt_resilience_assets.py``, ``test_plataforma_wiring.py``) leem
``install.sh``/``uninstall.sh`` como TEXTO. Um ``awk`` quebrado, um ``cmp``
invertido ou um caminho que nunca abre o ``main.conf`` passavam verdes.

Esta bancada existe para fechar exatamente esse buraco. Ela roda o mecanismo
de verdade — ``scripts/bluez_config.sh`` — contra uma **raiz falsa** em
``tmp_path`` (``HEFESTO_BT_ETC``), com ``HEFESTO_BT_SUDO`` vazio. Nada em
``/etc`` é lido nem escrito, e a suíte não precisa de root. Precedente da casa:
``test_radio_aberto_e10.py`` faz o mesmo com ``bt_bonds_restore.sh --verificar``
via ``HEFESTO_BT_BONDS_SRC``.

AS MORDIDAS (cada uma arrancável, cada uma fica vermelha)

- troque ``confirm`` por ``always`` em ``assets/bluetooth/hefesto-bt.block`` →
  ``test_bloco_antigo_do_hefesto_com_always_vira_confirm`` fica vermelho;
- apague a regra do ``awk`` que descarta as faixas das sentinelas (o ``_skip``)
  → o bloco antigo com ``always`` sobrevive e o mesmo teste fica vermelho, e
  ``test_rodar_duas_vezes_nao_duplica_o_bloco`` também;
- apague a regra que neutraliza chave ativa fora de bloco →
  ``test_chave_insegura_fora_do_bloco_e_neutralizada`` fica vermelho;
- inverta o ``cmp`` de ``_gravar_se_mudou`` (backup antes de comparar) →
  ``test_rodar_duas_vezes_nao_gera_backup_novo`` fica vermelho;
- devolva o ``aplicar`` ao desenho antigo (``if -d main.conf.d`` … ``elif -f
  main.conf``, um OU outro) → ``test_dropin_presente_nao_deixa_always_no_main_conf``
  fica vermelho — essa é a assimetria que deixava o instalador anunciar
  ``confirm`` com o ``always`` vivo no arquivo que o BlueZ lê;
- troque a recusa da sentinela sem fechamento por um ``sed`` de faixa →
  ``test_sentinela_sem_fechamento_nao_come_o_resto_do_arquivo`` fica vermelho;
- apague a devolução da marca ``#hefesto-desativou# `` no ``remover`` →
  ``test_remover_devolve_a_chave_de_terceiro`` fica vermelho.

AS MORDIDAS DA SEGUNDA LEVA (06/08/2026, os achados da verificação adversarial)

- devolva a chamada de poda automática ao ``_aplicar``/``_remover`` →
  ``test_aplicar_nao_apaga_backup_nenhum`` fica vermelho (é a evidência do
  colapso "404 linhas -> 3 linhas" indo embora);
- tire a proteção do mais antigo ou a proteção por ESTADO no ``podar`` →
  ``test_podar_nunca_apaga_o_mais_antigo`` /
  ``test_podar_nunca_apaga_backup_de_conteudo_unico`` /
  ``test_podar_nunca_faz_um_estado_sumir_do_disco`` ficam vermelhos;
- volte ``_gravar_se_mudou`` para ``install -m644 tmp main.conf`` →
  ``test_escrita_interrompida_nao_trunca_o_main_conf`` fica vermelho (o arquivo
  dela fica cortado NO MEIO DO BLOCO) e
  ``test_falha_na_troca_atomica_devolve_o_arquivo_intacto`` também;
- apague o aviso do ``remover`` → ``test_remover_grita_o_always_que_devolve``
  fica vermelho;
- apague o ``_avisar_alheio_no_bloco`` →
  ``test_aplicar_nomeia_linha_de_terceiro_dentro_do_bloco`` fica vermelho;
- tire o ``else`` do passo 3d do ``install.sh`` →
  ``test_install_anuncia_o_pulo_do_bluez_com_no_udev`` fica vermelho;
- devolva o ``sed`` inline do ``doctor.sh`` →
  ``test_doctor_le_pelo_dono_unico`` fica vermelho;
- troque o ``if [[ -r ... ]]`` do ``_cat_conf`` por leitura direta →
  ``test_leitura_de_arquivo_ilegivel_escala_em_vez_de_desistir`` fica vermelho;
  tire a recusa do ``_conf_ilegivel`` no ``remover`` →
  ``test_remover_recusa_em_vez_de_concluir_que_nao_ha_nada_nosso`` fica vermelho;
- "conserte" o ``awk`` para preservar as linhas em branco do fim →
  ``test_remover_declara_a_excecao_das_linhas_em_branco_do_fim`` fica vermelho
  (a exceção é o preço da idempotência, e por isso é DECLARADA, não corrigida);
- devolva o ``|| true`` que engolia a falha do ``rm`` →
  ``test_podar_nao_anuncia_remocao_que_nao_aconteceu`` fica vermelho.

AS MORDIDAS DA TERCEIRA LEVA (06/08/2026 — a verificação adversarial reprovou
duas de três lentes, e estas são as curas). Todas MEDIDAS: arrancadas, vistas
vermelhas, devolvidas.

- devolva o nome de backup com resolução de um segundo
  (``...hefesto-${rotulo}$(date +%s)``, sem ``mktemp``) →
  ``test_duas_gravacoes_no_mesmo_segundo_nao_comem_o_backup_anterior`` e
  ``test_aplicar_e_remover_seguidos_nao_colidem`` ficam vermelhos: o backup
  destruído é sempre o de MAIOR valor, o estado imediatamente anterior;
- tire a limpeza do backup incompleto →
  ``test_backup_parcial_e_apagado_e_o_main_conf_nao_e_tocado`` fica vermelho;
- tire do ``_ler_chave`` a linha ``if (_grupo != "General") next`` → TRÊS casos
  de ``test_o_dono_unico_le_exatamente_o_que_o_bluez_le``
  (``grupo-errado-nao-conta``, ``so-em-policy-e-ausente-em-general``,
  ``nome-de-grupo-e-exato``) e o ``test_o_veredito_acompanha_o_grupo`` ficam
  vermelhos — quatro falhas ao todo (é o falso negativo do dono único:
  ``verificar`` dizia OK e o GKeyFile lia ``always``). A terceira leva escreveu
  aqui "quatro casos"; recontado em 06/08 numa medição em série, são três casos
  e quatro falhas;
- faça o PRIMEIRO valor vencer em vez do último →
  ``test_o_ultimo_vence_e_nao_o_primeiro`` e dois casos da tabela ficam
  vermelhos (a regra do ``tail -n 1`` não tinha teste que mordesse);
- volte a promessa única do rebaixamento do ``never`` →
  ``test_never_dentro_do_bloco_nao_ganha_promessa_que_nao_se_cumpre`` e
  ``test_never_fora_do_bloco_ganha_a_promessa_e_ela_se_cumpre`` ficam vermelhos;
  o mesmo texto no ``doctor.sh`` derruba
  ``test_o_doctor_nao_promete_devolucao_sem_ressalva``;
- tire a releitura final do disco do ``_aplicar`` →
  ``test_bloco_de_zero_byte_nao_anuncia_garantia`` fica vermelho (rc=0
  anunciando garantia com o arquivo sem a chave);
- tire o ``trap`` de limpeza →
  ``test_um_kill_no_meio_da_troca_nao_deixa_temporario`` fica vermelho; tire o
  ``trap`` E o ``rm -f`` do caminho de falha e
  ``test_a_troca_atomica_nao_deixa_temporario_quando_o_mv_fracassa`` cai junto.

AS MORDIDAS DA QUARTA LEVA (06/08/2026 — e uma RETRATAÇÃO). Todas MEDIDAS em
SÉRIE, sozinhas na árvore, com restauração conferida por md5:

- devolva a proteção por ARQUIVO no ``_podar`` ("nenhum OUTRO backup tem os
  mesmos bytes") → ``test_podar_nunca_faz_um_estado_sumir_do_disco`` fica
  vermelho: com vários estados de poucas cópias, todas fora da retenção, um
  estado inteiro do ``main.conf`` dela some do disco;
- devolva ``install -Dm644`` / ``rm -f`` ao caminho dos drop-ins →
  ``test_aplicar_nao_destroi_dropin_editado_a_mao`` e
  ``test_remover_nao_apaga_dropin_editado_a_mao_sem_copia`` ficam vermelhos;
- tire o ``! -empty`` do ``_lista_backups`` →
  ``test_backup_de_zero_byte_nao_conta_como_backup`` e
  ``test_o_resumo_do_aplicar_nao_soma_backup_vazio`` ficam vermelhos;
- tire SÓ a metade do ``cmp`` do ``_copia_de_seguranca`` →
  ``test_backup_que_mente_ter_copiado_e_pego_pelo_cmp`` fica vermelho.

  A RETRATAÇÃO, e é o motivo de o teste acima existir: a terceira leva afirmou
  aqui que arrancar o ``cmp`` deixava
  ``test_backup_parcial_e_apagado_e_o_main_conf_nao_e_tocado`` vermelho. NÃO
  DEIXA, e foi medido por terceiro e reproduzido aqui: o shim daquele teste faz
  o ``cp`` sair 1, o ``||`` curto-circuita e o ``cmp`` nunca chega a ser
  avaliado — com o ``cmp`` arrancado a bancada inteira segue VERDE. Mordida
  afirmada e não reproduzida é exatamente o defeito que a regra da casa proíbe,
  e a cura foi escrever a bancada que faltava (um ``cp`` que corta o arquivo e
  MENTE saindo 0), não apagar a frase.

A REVALIDAÇÃO DE 06/08/2026 — por que estas linhas foram reconferidas

Um diagnóstico independente MEDIU que as três rodadas anteriores rodaram com
agentes irmãos mutando ``scripts/bluez_config.sh`` e ``scripts/doctor.sh`` na
MESMA árvore, ao vivo: 14 execuções contaminadas só na terceira rodada. Toda
mordida medida naquela janela ficou SUSPEITA, nos dois sentidos — vermelho falso
(mordida afirmada que não existe) e verde falso (um ``cp ORIG`` alheio desfazia
a mutação antes do ``pytest``).

As NOVE mordidas daquela janela foram REFEITAS em série, uma de cada vez,
sozinhas na árvore, com a restauração conferida por md5 e por modo: D1
(``fail``→``pass``), D2 (detector fora do ``main()``), M1 (backup com resolução
de 1 s), o ``if (_grupo != "General") next``, P2 (poda automática de volta), M6
(sem ``trap``), M7 (promessa única do ``never``), a conferência final do disco, e
"o primeiro valor vence". As nove MORDEM, e apenas uma correção de número saiu
disso (a do grupo, acima). A cura estrutural que impede a repetição é a
ARVORE-CONGELADA-01, em ``tests/conftest.py``.

O ORÁCULO É OBRIGATÓRIO. Toda afirmação sobre "qual valor o BlueZ lê" passa
pelo ``_oraculo``, que roda o GLib GKeyFile — o parser REAL do ``bluetoothd`` —
num SUBPROCESSO. A bancada tinha um TERCEIRO parser em Python (o antigo helper
``_valor``), e foi exatamente por ali que a classe de defeito do GRUPO passou
batida: o dono e a bancada erravam do MESMO jeito, então concordavam.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.conftest import arvore_congelada

RAIZ = arvore_congelada()
SCRIPT = RAIZ / "scripts" / "bluez_config.sh"
ASSETS = RAIZ / "assets" / "bluetooth"
INSTALL = RAIZ / "install.sh"
UNINSTALL = RAIZ / "uninstall.sh"

MARCA = "#hefesto-desativou# "

MAIN_CONF_DELA = """[General]

# >>> hefesto bluetooth >>>
# hefesto-dualsense4unix — bloco de uma versão anterior.
[General]
FastConnectable=true
JustWorksRepairing=always
# <<< hefesto bluetooth <<<
"""


def _etc(tmp_path: Path, main_conf: str | None = None, com_dropin_dir: bool = False) -> Path:
    """Monta a raiz falsa. NADA aqui encosta em /etc."""
    etc = tmp_path / "bluetooth"
    etc.mkdir()
    if main_conf is not None:
        (etc / "main.conf").write_text(main_conf, encoding="utf-8")
    if com_dropin_dir:
        (etc / "main.conf.d").mkdir()
    return etc


def _rodar(
    etc: Path,
    modo: str,
    manter: str = "10",
    arg: str | None = None,
    path_extra: Path | None = None,
    sudo_falso: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    ambiente = {
        **os.environ,
        "HEFESTO_BT_ETC": str(etc),
        "HEFESTO_BT_ASSETS": str(ASSETS),
        "HEFESTO_BT_SUDO": "",
        "HEFESTO_BT_BACKUPS_MANTER": manter,
    }
    if path_extra is not None:
        ambiente["PATH"] = f"{path_extra}:{os.environ.get('PATH', '')}"
    if sudo_falso is not None:
        ambiente["HEFESTO_BT_SUDO"] = str(sudo_falso.name)
        ambiente["HEFESTO_FAKE_SUDO_LOG"] = str(sudo_falso.parent / "escaladas.txt")
        ambiente["PATH"] = f"{sudo_falso.parent}:{ambiente.get('PATH', '')}"
    return subprocess.run(
        ["bash", str(SCRIPT), modo, *([arg] if arg is not None else [])],
        capture_output=True,
        text=True,
        timeout=60,
        env=ambiente,
    )


_ORACULO = """
import sys
from gi.repository import GLib
kf = GLib.KeyFile()
try:
    kf.load_from_file(sys.argv[1], GLib.KeyFileFlags.NONE)
except Exception as erro:
    sys.stdout.write("ERRO-DE-CARGA %s" % erro)
    raise SystemExit(0)
try:
    sys.stdout.write("VALOR %s" % kf.get_string(sys.argv[2], sys.argv[3]))
except Exception:
    sys.stdout.write("AUSENTE")
"""


def _oraculo(
    arquivo: Path, grupo: str = "General", chave: str = "JustWorksRepairing"
) -> str | None:
    """O que o GKeyFile — o parser REAL do bluetoothd — lê deste arquivo."""
    proc = subprocess.run(
        [sys.executable, "-c", _ORACULO, str(arquivo), grupo, chave],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0 or "ModuleNotFoundError" in proc.stderr:
        pytest.skip(
            "sem PyGObject neste ambiente — o oráculo GKeyFile é obrigatório "
            "para toda afirmação sobre 'qual valor o BlueZ lê', e não há "
            "substituto honesto (o job de GTK real do CI cobre estes testes)"
        )
    saida = proc.stdout
    if saida == "AUSENTE" or saida.startswith("ERRO-DE-CARGA"):
        return None
    assert saida.startswith("VALOR "), f"oráculo respondeu algo inesperado: {saida!r}"
    return saida[len("VALOR "):]


def _oraculo_recusa(arquivo: Path) -> str | None:
    """A mensagem com que o GKeyFile RECUSA o arquivo inteiro, ou None."""
    proc = subprocess.run(
        [sys.executable, "-c", _ORACULO, str(arquivo), "General", "JustWorksRepairing"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0 or "ModuleNotFoundError" in proc.stderr:
        pytest.skip("sem PyGObject neste ambiente — o oráculo GKeyFile é obrigatório")
    if proc.stdout.startswith("ERRO-DE-CARGA "):
        return proc.stdout[len("ERRO-DE-CARGA "):]
    return None


def _valor(etc: Path, chave: str = "JustWorksRepairing") -> str | None:
    """Valor que o BlueZ leria de `[General]` neste main.conf. Pelo oráculo."""
    return _oraculo(etc / "main.conf", "General", chave)


def _backups(etc: Path) -> list[Path]:
    return sorted(etc.glob("main.conf.bak.hefesto-*"))


def test_bloco_antigo_do_hefesto_com_always_vira_confirm(tmp_path: Path) -> None:
    """O caso que ninguém tratava: RECONHECER e CORRIGIR bloco nosso antigo."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    proc = _rodar(etc, "aplicar")

    assert proc.returncode == 0, proc.stderr
    texto = (etc / "main.conf").read_text(encoding="utf-8")
    assert _valor(etc) == "confirm", (
        "o bloco antigo do hefesto com JustWorksRepairing=always sobreviveu ao "
        "aplicar — é exatamente o defeito medido em 06/08/2026"
    )
    ativas_always = [
        ln for ln in texto.splitlines()
        if ln.strip().startswith("JustWorksRepairing") and ln.strip().endswith("always")
    ]
    assert not ativas_always, f"linha ativa com always sobreviveu: {ativas_always}"


def test_o_aplicar_diz_em_voz_alta_que_corrigiu_valor_do_proprio_hefesto(
    tmp_path: Path,
) -> None:
    """Correção silenciosa foi o que deixou o `always` viver quatro dias."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    proc = _rodar(etc, "aplicar")

    assert "always" in proc.stdout
    assert "ANTERIOR do hefesto" in proc.stdout
    assert "RADIO-ABERTO-01" in proc.stdout


def test_chave_insegura_fora_do_bloco_e_neutralizada(tmp_path: Path) -> None:
    """A chave também existe FORA das sentinelas — e o `always` solto mataria a cura."""
    etc = _etc(tmp_path, "[General]\nJustWorksRepairing = always\nName = BlueZ\n")
    proc = _rodar(etc, "aplicar")

    assert proc.returncode == 0, proc.stderr
    texto = (etc / "main.conf").read_text(encoding="utf-8")
    assert f"{MARCA}JustWorksRepairing = always" in texto, (
        "a chave insegura fora do bloco não foi neutralizada"
    )
    assert _valor(etc) == "confirm"
    assert "fora do bloco hefesto" in proc.stdout


def test_chave_comentada_do_template_upstream_fica_intacta(tmp_path: Path) -> None:
    """`#JustWorksRepairing = never` do template do BlueZ não é chave ativa."""
    etc = _etc(tmp_path, "[General]\n#JustWorksRepairing = never\nName = BlueZ\n")
    _rodar(etc, "aplicar")

    texto = (etc / "main.conf").read_text(encoding="utf-8")
    assert "\n#JustWorksRepairing = never\n" in texto
    assert f"{MARCA}#JustWorksRepairing" not in texto


def test_rodar_duas_vezes_nao_gera_backup_novo(tmp_path: Path) -> None:
    """BUG-INSTALL-MAIN-CONF-BACKUP-INFINITO-01, agora com portão."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    _rodar(etc, "aplicar")
    apos_primeiro = _backups(etc)
    assert len(apos_primeiro) == 1, "a primeira aplicação tem de deixar UM backup"

    proc = _rodar(etc, "aplicar")

    assert _backups(etc) == apos_primeiro, (
        "a segunda aplicação, sem mudança nenhuma, criou backup novo"
    )
    assert "nada a reescrever" in proc.stdout


def test_rodar_duas_vezes_nao_duplica_o_bloco(tmp_path: Path) -> None:
    """BUG-INSTALL-MAIN-CONF-CRESCE-01: nem bloco repetido, nem arquivo crescendo."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    _rodar(etc, "aplicar")
    primeiro = (etc / "main.conf").read_text(encoding="utf-8")
    _rodar(etc, "aplicar")
    _rodar(etc, "aplicar")
    terceiro = (etc / "main.conf").read_text(encoding="utf-8")

    assert primeiro == terceiro, "o arquivo mudou entre a 1a e a 3a aplicação"
    assert terceiro.count("# >>> hefesto bluetooth >>>") == 1
    ativas = [
        ln for ln in terceiro.splitlines()
        if ln.strip().startswith("JustWorksRepairing")
    ]
    assert ativas == ["JustWorksRepairing=confirm"]


def test_blocos_legados_de_instalacao_antiga_tambem_saem(tmp_path: Path) -> None:
    """Máquina anterior a 21/07 tinha UM bloco por chave. Os dois têm de sair."""
    etc = _etc(
        tmp_path,
        "[General]\n"
        "# >>> hefesto FastConnectable >>>\n[General]\nFastConnectable=true\n"
        "# <<< hefesto FastConnectable <<<\n"
        "# >>> hefesto JustWorksRepairing >>>\n[General]\nJustWorksRepairing = always\n"
        "# <<< hefesto JustWorksRepairing <<<\n",
    )
    _rodar(etc, "aplicar")

    texto = (etc / "main.conf").read_text(encoding="utf-8")
    assert "# >>> hefesto FastConnectable >>>" not in texto
    assert "# >>> hefesto JustWorksRepairing >>>" not in texto
    assert texto.count("# >>> hefesto bluetooth >>>") == 1
    assert _valor(etc) == "confirm"


def test_dropin_presente_nao_deixa_always_no_main_conf(tmp_path: Path) -> None:
    """O furo que o mapa chamou de 4-A, e que é o pior dos dois."""
    etc = _etc(tmp_path, MAIN_CONF_DELA, com_dropin_dir=True)
    proc = _rodar(etc, "aplicar")

    assert proc.returncode == 0, proc.stderr
    assert _valor(etc) == "confirm", (
        "com main.conf.d presente, o main.conf ficou com o valor antigo — o "
        "instalador anunciaria confirm e o BlueZ leria always"
    )
    assert (etc / "main.conf.d" / "hefesto-justworks.conf").exists()
    assert (etc / "main.conf.d" / "hefesto-fastconnectable.conf").exists()


def test_dropin_e_bloco_declaram_o_mesmo_valor(tmp_path: Path) -> None:
    """Os dois lugares dizendo a mesma coisa é o que torna a dúvida inofensiva."""
    etc = _etc(tmp_path, MAIN_CONF_DELA, com_dropin_dir=True)
    _rodar(etc, "aplicar")

    dropin = (etc / "main.conf.d" / "hefesto-justworks.conf").read_text(encoding="utf-8")
    ativos = [
        ln.split("=", 1)[1].strip()
        for ln in dropin.splitlines()
        if ln.strip().startswith("JustWorksRepairing")
    ]
    assert ativos == ["confirm"]
    assert _valor(etc) == "confirm"


_DROPIN_DELA = (
    "# escrito à mão por ela em 03/08\n"
    "[General]\n"
    "JustWorksRepairing=never\n"
    "FastConnectable=false\n"
)


def _backups_de_dropin(etc: Path) -> list[Path]:
    return sorted((etc / "main.conf.d").glob("*.bak.hefesto-dropin-*"))


def test_aplicar_nao_destroi_dropin_editado_a_mao(tmp_path: Path) -> None:
    """Reescrever por cima sem cópia é apagar decisão de produto — no outro caminho."""
    etc = _etc(tmp_path, MAIN_CONF_DELA, com_dropin_dir=True)
    alvo = etc / "main.conf.d" / "hefesto-justworks.conf"
    alvo.write_text(_DROPIN_DELA, encoding="utf-8")

    proc = _rodar(etc, "aplicar")

    assert proc.returncode == 0, proc.stderr
    guardados = [b.read_text(encoding="utf-8") for b in _backups_de_dropin(etc)]
    assert _DROPIN_DELA in guardados, (
        "o aplicar reescreveu um drop-in editado à mão SEM guardar cópia: "
        f"backups encontrados = {[b.name for b in _backups_de_dropin(etc)]}"
    )
    assert "hefesto-justworks.conf" in proc.stdout
    assert "conteúdo DIFERENTE do nosso" in proc.stdout, (
        "o arquivo dela foi reescrito em silêncio"
    )
    assert _oraculo(alvo) == "confirm"


def test_remover_nao_apaga_dropin_editado_a_mao_sem_copia(tmp_path: Path) -> None:
    """A mesma invariante pelo outro lado: `rm -f` sem backup é perda líquida."""
    etc = _etc(tmp_path, MAIN_CONF_DELA, com_dropin_dir=True)
    alvo = etc / "main.conf.d" / "hefesto-justworks.conf"
    alvo.write_text(_DROPIN_DELA, encoding="utf-8")

    proc = _rodar(etc, "remover")

    assert not alvo.exists(), "o remover deixou o drop-in para trás"
    guardados = [b.read_text(encoding="utf-8") for b in _backups_de_dropin(etc)]
    assert _DROPIN_DELA in guardados, (
        "o remover apagou um drop-in editado à mão SEM guardar cópia: "
        f"backups encontrados = {[b.name for b in _backups_de_dropin(etc)]}"
    )
    assert "conteúdo DIFERENTE do nosso" in proc.stdout


def test_dropin_igual_ao_nosso_asset_nao_gera_backup(tmp_path: Path) -> None:
    """A EXCEÇÃO DECLARADA — e a linha de base dos dois testes acima."""
    etc = _etc(tmp_path, MAIN_CONF_DELA, com_dropin_dir=True)

    _rodar(etc, "aplicar")
    assert _backups_de_dropin(etc) == [], "a primeira gravação gerou backup do nada"
    _rodar(etc, "aplicar")
    _rodar(etc, "remover")

    assert _backups_de_dropin(etc) == [], (
        "aplicar/aplicar/remover com o nosso próprio conteúdo gerou backup de "
        f"drop-in: {[b.name for b in _backups_de_dropin(etc)]}"
    )


def test_remover_devolve_o_arquivo_sem_chave_nossa(tmp_path: Path) -> None:
    """Ciclo completo: aplicar → remover tem de devolver o arquivo ORIGINAL."""
    original = "[General]\nName = BlueZ\n\n[Policy]\nAutoEnable=true\n"
    etc = _etc(tmp_path, original)

    _rodar(etc, "aplicar")
    assert _valor(etc) == "confirm"
    proc = _rodar(etc, "remover")

    assert proc.returncode == 0, proc.stderr
    assert (etc / "main.conf").read_text(encoding="utf-8") == original, (
        "o remover não devolveu o main.conf ao estado original"
    )
    assert _valor(etc) is None, "sobrou chave nossa depois do remover"


def test_remover_devolve_a_chave_de_terceiro(tmp_path: Path) -> None:
    """Instalar+desinstalar não pode ser destrutivo líquido sobre config alheia."""
    original = "[General]\nJustWorksRepairing = never\nName = BlueZ\n"
    etc = _etc(tmp_path, original)

    _rodar(etc, "aplicar")
    _rodar(etc, "remover")

    assert (etc / "main.conf").read_text(encoding="utf-8") == original


def test_remover_tira_os_dropins(tmp_path: Path) -> None:
    """Simetria do caminho A: o que o aplicar grava em main.conf.d, o remover tira."""
    etc = _etc(tmp_path, MAIN_CONF_DELA, com_dropin_dir=True)
    _rodar(etc, "aplicar")
    _rodar(etc, "remover")

    assert not (etc / "main.conf.d" / "hefesto-justworks.conf").exists()
    assert not (etc / "main.conf.d" / "hefesto-fastconnectable.conf").exists()


def test_remover_deixa_um_unico_backup_mesmo_com_tres_blocos(tmp_path: Path) -> None:
    """Os três removedores antigos faziam um `cp` cada — três arquivos por execução."""
    etc = _etc(
        tmp_path,
        "[General]\n"
        "# >>> hefesto FastConnectable >>>\nFastConnectable=true\n"
        "# <<< hefesto FastConnectable <<<\n"
        "# >>> hefesto JustWorksRepairing >>>\nJustWorksRepairing = always\n"
        "# <<< hefesto JustWorksRepairing <<<\n"
        "# >>> hefesto bluetooth >>>\nJustWorksRepairing=confirm\n"
        "# <<< hefesto bluetooth <<<\n",
    )
    _rodar(etc, "remover")

    assert len(_backups(etc)) == 1, "uma remoção deixou mais de um backup"


def test_remover_duas_vezes_nao_gera_backup_novo(tmp_path: Path) -> None:
    """O `cmp` vale para os dois lados — remover o que já saiu é no-op honesto."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    _rodar(etc, "remover")
    apos = _backups(etc)
    _rodar(etc, "remover")

    assert _backups(etc) == apos


@pytest.mark.parametrize("modo", ["aplicar", "remover"])
def test_sentinela_sem_fechamento_nao_come_o_resto_do_arquivo(
    tmp_path: Path, modo: str
) -> None:
    """`sed '/A/,/B/d'` sem B apaga ATÉ O FIM. Aqui a resposta é RECUSAR."""
    conteudo = (
        "[General]\n"
        "# >>> hefesto bluetooth >>>\n"
        "JustWorksRepairing=confirm\n"
        "ConteudoDeTerceiroDepoisDoBloco=1\n"
    )
    etc = _etc(tmp_path, conteudo)
    proc = _rodar(etc, modo)

    assert proc.returncode != 0, f"{modo} aceitou uma faixa sem fechamento"
    assert (etc / "main.conf").read_text(encoding="utf-8") == conteudo, (
        "o arquivo foi tocado apesar da recusa"
    )
    assert "sem fechamento" in proc.stderr


def test_aplicar_que_recusa_nao_anuncia_garantia(tmp_path: Path) -> None:
    """Anunciar sucesso depois de recusar é o defeito de comunicação da sprint."""
    etc = _etc(
        tmp_path, "[General]\n# >>> hefesto bluetooth >>>\nJustWorksRepairing=always\n"
    )
    proc = _rodar(etc, "aplicar")

    assert proc.returncode != 0
    assert "garantidos" not in proc.stdout


_PRE_COLAPSO = "main.conf.bak.hefesto-1784672963"
_POS_COLAPSO = "main.conf.bak.hefesto-1784694261"


def _povoar_como_a_maquina_dela(etc: Path, quantos: int = 37) -> list[Path]:
    """37 backups, com os dois pontos do colapso entre os MAIS ANTIGOS."""
    criados: list[Path] = []
    momento = 1_784_600_000

    pre = etc / _PRE_COLAPSO
    pre.write_text("linha\n" * 404, encoding="utf-8")
    os.utime(pre, (momento, momento))
    criados.append(pre)

    pos = etc / _POS_COLAPSO
    pos.write_text(
        "[General]\nFastConnectable=true\nJustWorksRepairing=always\n", encoding="utf-8"
    )
    os.utime(pos, (momento + 60, momento + 60))
    criados.append(pos)

    for i in range(quantos - 2):
        alvo = etc / f"main.conf.bak.hefesto-17861{i:05d}"
        alvo.write_text("[General]\n", encoding="utf-8")
        os.utime(alvo, (momento + 3600 + i * 60, momento + 3600 + i * 60))
        criados.append(alvo)
    return criados


def test_aplicar_nao_apaga_backup_nenhum(tmp_path: Path) -> None:
    """A EVIDÊNCIA NÃO SAI. Nem um arquivo, nem com 37 no diretório."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    antes = _povoar_como_a_maquina_dela(etc)

    proc = _rodar(etc, "aplicar", manter="10")

    assert proc.returncode == 0, proc.stderr
    for backup in antes:
        assert backup.exists(), f"o aplicar apagou {backup.name} — isso é evidência medida"
    assert (etc / _PRE_COLAPSO).read_text(encoding="utf-8").count("\n") == 404
    assert len(_backups(etc)) == 38
    assert "nenhum é apagado automaticamente" in proc.stdout


def test_remover_nao_apaga_backup_nenhum(tmp_path: Path) -> None:
    """O mesmo pelo outro lado: desinstalar também não é hora de faxina."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    antes = _povoar_como_a_maquina_dela(etc)

    _rodar(etc, "remover", manter="10")

    for backup in antes:
        assert backup.exists(), f"o remover apagou {backup.name}"


def test_podar_por_padrao_so_simula(tmp_path: Path) -> None:
    """`podar` sem argumento NÃO apaga: diz o que sairia, e para por aí."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    antes = _povoar_como_a_maquina_dela(etc)

    proc = _rodar(etc, "podar", manter="10")

    assert proc.returncode == 0, proc.stderr
    for backup in antes:
        assert backup.exists(), "o dry-run apagou arquivo"
    assert "poda SIMULADA" in proc.stdout
    assert "--aplicar" in proc.stdout


def test_podar_nunca_apaga_o_mais_antigo(tmp_path: Path) -> None:
    """O mais antigo é o estado mais próximo do pré-hefesto. Fica, sempre."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    _povoar_como_a_maquina_dela(etc)

    proc = _rodar(etc, "podar", manter="1", arg="--aplicar")

    assert proc.returncode == 0, proc.stderr
    assert (etc / _PRE_COLAPSO).exists(), "a poda apagou o backup MAIS ANTIGO"
    assert "MAIS ANTIGO nunca sai" in proc.stdout


def test_podar_nunca_apaga_backup_de_conteudo_unico(tmp_path: Path) -> None:
    """Conteúdo único = única cópia daquele estado. É o instante do estrago."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    _povoar_como_a_maquina_dela(etc)

    proc = _rodar(etc, "podar", manter="1", arg="--aplicar")

    assert (etc / _POS_COLAPSO).exists(), (
        "a poda apagou o backup de 3 linhas — o instante do estrago, e a única "
        "cópia daquele estado do main.conf dela"
    )
    assert "ÚNICA cópia deste conteúdo" in proc.stdout
    assert len(_backups(etc)) < 37


def test_podar_nunca_faz_um_estado_sumir_do_disco(tmp_path: Path) -> None:
    """A promessa é sobre ESTADO, não sobre arquivo — e a regra velha não era."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    momento = 1_784_600_000
    estados = {
        "antigo": "[General]\n# estado A — o mais próximo do pré-hefesto\n",
        "meio": "[General]\nJustWorksRepairing=always\n# estado B — o do meio\n",
        "novo": "[General]\nJustWorksRepairing=confirm\n# estado C\n",
    }
    i = 0
    for nome, conteudo in estados.items():
        for _copia in range(3):
            alvo = etc / f"main.conf.bak.hefesto-{1786100000 + i}"
            alvo.write_text(conteudo, encoding="utf-8")
            os.utime(alvo, (momento + i * 60, momento + i * 60))
            i += 1
        assert nome

    antes = {b.read_bytes() for b in _backups(etc)}
    assert len(antes) == 3, "a fixture tem de ter TRÊS estados distintos"

    proc = _rodar(etc, "podar", manter="1", arg="--aplicar")

    assert proc.returncode == 0, proc.stderr
    depois = {b.read_bytes() for b in _backups(etc)}
    sumidos = antes - depois
    assert sumidos == set(), (
        "a poda fez um ESTADO do main.conf dela desaparecer inteiro do disco "
        f"({len(sumidos)} de {len(antes)}): "
        f"{[c.decode('utf-8').splitlines()[1] for c in sorted(sumidos)]}. "
        "A proteção era por ARQUIVO ('nenhum outro tem os mesmos bytes') e a "
        "frase impressa prometia ESTADO."
    )
    assert len(_backups(etc)) == 3, (
        f"sobraram {len(_backups(etc))} de 9 — a poda parou de podar"
    )
    assert "ÚNICA cópia deste conteúdo" in proc.stdout


def test_podar_nao_toca_backup_que_nao_e_nosso(tmp_path: Path) -> None:
    """Há um backup de OUTRA ferramenta em /etc/bluetooth que não é nosso."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    alheio = etc / "main.conf.bak.outra-ferramenta-1784689791"
    alheio.write_text("nao-e-nosso\n", encoding="utf-8")
    _povoar_como_a_maquina_dela(etc)

    _rodar(etc, "podar", manter="1", arg="--aplicar")

    assert alheio.exists(), "a poda apagou backup de terceiro"
    assert alheio.read_text(encoding="utf-8") == "nao-e-nosso\n"


def test_retencao_zero_desliga_a_poda(tmp_path: Path) -> None:
    """A retenção é declarada: `0` significa "não apague nada", e tem de valer."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    _povoar_como_a_maquina_dela(etc)

    proc = _rodar(etc, "podar", manter="0", arg="--aplicar")

    assert len(_backups(etc)) == 37
    assert "poda desligada" in proc.stdout


def test_podar_com_argumento_desconhecido_recusa(tmp_path: Path) -> None:
    """`podar --forca-tudo` não pode virar `podar --aplicar` por engano."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    _povoar_como_a_maquina_dela(etc)

    proc = _rodar(etc, "podar", arg="--forca-tudo")

    assert proc.returncode == 2
    assert len(_backups(etc)) == 37


def test_podar_nao_anuncia_remocao_que_nao_aconteceu(tmp_path: Path) -> None:
    """O `|| true` engolia a falha do `rm` e a frase de sucesso saía igual."""
    if os.geteuid() == 0:
        pytest.skip("como root o modo do diretório não impede o rm")
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    _povoar_como_a_maquina_dela(etc)
    etc.chmod(0o555)
    try:
        proc = _rodar(etc, "podar", manter="10", arg="--aplicar")
    finally:
        etc.chmod(0o755)

    assert proc.returncode != 0, "a poda falhou em tudo e mesmo assim saiu com 0"
    assert "não consegui remover" in proc.stderr
    assert "0 de 37 backup(s) removido(s)" in proc.stdout


def test_verificar_acusa_o_estado_da_maquina_dela(tmp_path: Path) -> None:
    """Antes desta entrega, NADA no projeto sabia dizer que a máquina estava assim."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    proc = _rodar(etc, "verificar")

    assert proc.returncode != 0
    assert "JustWorksRepairing: always" in proc.stdout
    assert "veredito: INSEGURO" in proc.stdout


def test_verificar_nao_escreve_nada(tmp_path: Path) -> None:
    """Modo de leitura que escreve não é modo de leitura."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    antes = (etc / "main.conf").read_bytes()
    listagem_antes = sorted(p.name for p in etc.iterdir())

    _rodar(etc, "verificar")

    assert (etc / "main.conf").read_bytes() == antes
    assert sorted(p.name for p in etc.iterdir()) == listagem_antes


def test_verificar_aprova_depois_do_aplicar(tmp_path: Path) -> None:
    """Linha de base — sem ela, um verificador que reprova tudo 'passaria'."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    _rodar(etc, "aplicar")
    proc = _rodar(etc, "verificar")

    assert proc.returncode == 0
    assert "veredito: OK" in proc.stdout


def test_sem_bluez_nada_explode(tmp_path: Path) -> None:
    """Máquina sem BlueZ: os três modos saem em paz, sem criar arquivo."""
    etc = _etc(tmp_path)
    for modo in ("aplicar", "remover", "verificar"):
        proc = _rodar(etc, modo)
        assert proc.returncode == 0, f"{modo}: {proc.stderr}"
    assert not (etc / "main.conf").exists()


def test_o_script_e_executavel_e_tem_sintaxe_valida() -> None:
    """Contrato dos scripts desta casa, e aqui vale dobrado: install e"""
    assert SCRIPT.stat().st_mode & 0o111, "bluez_config.sh não é executável"
    proc = subprocess.run(
        ["bash", "-n", str(SCRIPT)], capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, proc.stderr


def test_modo_desconhecido_nao_faz_nada(tmp_path: Path) -> None:
    """Um erro de digitação no chamador não pode virar reescrita silenciosa."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    antes = (etc / "main.conf").read_bytes()
    proc = _rodar(etc, "aplicarr")

    assert proc.returncode == 2
    assert (etc / "main.conf").read_bytes() == antes


def test_install_chama_o_aplicar_e_uninstall_chama_o_remover() -> None:
    """A bancada só vale se o install/uninstall usarem MESMO este mecanismo."""
    assert "scripts/bluez_config.sh\" aplicar" in INSTALL.read_text(encoding="utf-8")
    assert "scripts/bluez_config.sh\" remover" in UNINSTALL.read_text(encoding="utf-8")


def test_o_script_nunca_reinicia_o_bluetoothd() -> None:
    """Provado ao vivo em 2026-07-17: restart derruba os controles conectados."""
    fonte = SCRIPT.read_text(encoding="utf-8")
    assert "systemctl" not in fonte
    assert "bluetoothctl" not in fonte


def test_o_script_diz_com_todas_as_letras_quando_a_mudanca_vale(tmp_path: Path) -> None:
    """Ela precisa saber que o `confirm` só vale no próximo boot."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    proc = _rodar(etc, "aplicar")

    assert "PRÓXIMO BOOT" in proc.stdout
    assert "NÃO reiniciamos o bluetoothd" in proc.stdout


def test_todo_caminho_deriva_da_raiz_configuravel() -> None:
    """A bancada é segura porque NENHUM caminho é literal."""
    fonte = SCRIPT.read_text(encoding="utf-8")
    codigo = [
        ln for ln in fonte.splitlines()
        if not ln.lstrip().startswith("#") and "/etc/bluetooth" in ln
    ]
    assert codigo == ['ETC="${HEFESTO_BT_ETC:-/etc/bluetooth}"'], (
        f"caminho literal de /etc fora do padrão configurável: {codigo}"
    )


def _shim(tmp_path: Path, alvo: Path, comandos: tuple[str, ...], corta: bool) -> Path:
    """Sabota SÓ o que escreve DIRETO no arquivo vivo; o resto passa reto."""
    pasta = tmp_path / f"shim-{'corte' if corta else 'falha'}"
    pasta.mkdir(exist_ok=True)
    for nome in comandos:
        real = shutil.which(nome)
        assert real, f"sem {nome} nesta máquina"
        corpo = "    head -c 60 \"${@: -2:1}\" > \"${alvo}\" 2>/dev/null || true\n" if corta else ""
        (pasta / nome).write_text(
            "#!/usr/bin/env bash\n"
            'alvo="${@: -1}"\n'
            f'if [[ "${{alvo}}" == "{alvo}" ]]; then\n'
            f"{corpo}"
            "    exit 1\n"
            "fi\n"
            f'exec {real} "$@"\n',
            encoding="utf-8",
        )
        (pasta / nome).chmod(0o755)
    return pasta


def test_escrita_interrompida_nao_trunca_o_main_conf(tmp_path: Path) -> None:
    """Nenhuma escrita cai DIRETO sobre o main.conf vivo — nem uma."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    original = (etc / "main.conf").read_text(encoding="utf-8")
    pasta = _shim(tmp_path, etc / "main.conf", ("cp", "install"), corta=True)

    proc = _rodar(etc, "aplicar", path_extra=pasta)
    texto = (etc / "main.conf").read_text(encoding="utf-8")

    assert texto != original[:60], "o main.conf dela ficou TRUNCADO no meio do bloco"
    assert proc.returncode == 0, proc.stderr
    assert texto.count("# >>> hefesto bluetooth >>>") == 1
    assert "# <<< hefesto bluetooth <<<" in texto, (
        "o arquivo ficou com sentinela de abertura sem fechamento — a partir "
        "daqui aplicar E remover recusam para sempre"
    )
    assert _rodar(etc, "aplicar").returncode == 0


def test_falha_na_troca_atomica_devolve_o_arquivo_intacto(tmp_path: Path) -> None:
    """Falha no `mv` = nada aconteceu. O arquivo dela sobrevive BYTE A BYTE."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    original = (etc / "main.conf").read_bytes()
    pasta = _shim(tmp_path, etc / "main.conf", ("mv",), corta=False)

    proc = _rodar(etc, "aplicar", path_extra=pasta)

    assert proc.returncode != 0, "a troca falhou e o script disse que deu certo"
    assert (etc / "main.conf").read_bytes() == original, (
        "o main.conf mudou apesar de a escrita ter falhado"
    )
    assert "INTACTO" in proc.stderr
    assert "garantidos" not in proc.stdout
    assert len(_backups(etc)) == 1


def _sobras(etc: Path) -> list[str]:
    return sorted(p.name for p in etc.iterdir() if "hefesto-novo" in p.name)


def test_a_troca_atomica_nao_deixa_temporario_quando_o_mv_fracassa(tmp_path: Path) -> None:
    """ESTE TESTE NÃO MORDIA (achado de 06/08/2026, MEDIDO)."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    pasta = _shim(tmp_path, etc / "main.conf", ("mv",), corta=False)

    proc = _rodar(etc, "aplicar", path_extra=pasta)

    assert proc.returncode != 0, "a troca falhou e o script disse que deu certo"
    assert _sobras(etc) == [], (
        f"a troca atômica falhou e deixou temporário para trás: {_sobras(etc)}"
    )


def test_um_kill_no_meio_da_troca_nao_deixa_temporario(tmp_path: Path) -> None:
    """O `trap` que não existia: um kill entre o `mktemp` e o `mv`."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    original = (etc / "main.conf").read_bytes()
    pasta = tmp_path / "shim-kill"
    pasta.mkdir()
    real = shutil.which("chmod")
    assert real, "sem chmod nesta máquina"
    (pasta / "chmod").write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "${@: -1}" == *".main.conf.hefesto-novo."* ]]; then\n'
        '    kill -TERM "${PPID}"\n'
        "    sleep 5\n"
        "    exit 1\n"
        "fi\n"
        f'exec {real} "$@"\n',
        encoding="utf-8",
    )
    (pasta / "chmod").chmod(0o755)

    proc = _rodar(etc, "aplicar", path_extra=pasta)

    assert proc.returncode != 0, "o script morreu de TERM e anunciou sucesso"
    assert _sobras(etc) == [], (
        f"o kill no meio da troca deixou temporário órfão: {_sobras(etc)} — é o "
        "trap que não existia"
    )
    assert (etc / "main.conf").read_bytes() == original, (
        "o main.conf mudou apesar de o script ter morrido antes do mv"
    )


def test_verificar_reporta_temporario_orfao(tmp_path: Path) -> None:
    """O que um SIGKILL deixar para trás, alguém tem de saber contar."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    orfao = etc / ".main.conf.hefesto-novo.aBc123"
    orfao.write_text("[General]\n", encoding="utf-8")

    proc = _rodar(etc, "verificar")

    assert "temporarios-orfaos: 1" in proc.stdout, (
        "o verificador não conta os temporários órfãos que o script pode ter "
        "deixado em /etc/bluetooth"
    )
    assert f"temporario-orfao: {orfao}" in proc.stdout, "não nomeia o órfão"
    assert orfao.exists(), "o verificar APAGOU o órfão — modo de leitura não apaga"


def test_backup_de_zero_byte_nao_conta_como_backup(tmp_path: Path) -> None:
    """O backup nasce vazio do `mktemp`; um SIGKILL antes do `cp` o deixa assim."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    vivo = etc / "main.conf.bak.hefesto-1786000001"
    vivo.write_text("[General]\nJustWorksRepairing=always\n", encoding="utf-8")
    morto = etc / "main.conf.bak.hefesto-1786000002"
    morto.touch()
    assert morto.stat().st_size == 0

    proc = _rodar(etc, "verificar")

    assert "backups-hefesto: 1" in proc.stdout, (
        "o backup de ZERO byte foi contado como backup — ela lê 2 e tem 1"
    )
    assert "backups-suspeitos: 1" in proc.stdout, "o vazio sumiu da conta e da vista"
    assert f"backup-suspeito: {morto}" in proc.stdout, "não nomeia o suspeito"
    assert morto.exists(), "o verificar APAGOU o suspeito — modo de leitura não apaga"


def test_o_resumo_do_aplicar_nao_soma_backup_vazio(tmp_path: Path) -> None:
    """A mesma conta na frase que o `aplicar` imprime, que é a que ela lê."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    (etc / "main.conf.bak.hefesto-1786000001").write_text("[General]\n", encoding="utf-8")
    (etc / "main.conf.bak.hefesto-1786000002").touch()

    proc = _rodar(etc, "aplicar")

    assert proc.returncode == 0, proc.stderr
    assert "2 arquivo(s)" in proc.stdout, (
        f"a frase do resumo somou o backup vazio: {proc.stdout}"
    )
    assert "ZERO byte" in proc.stdout, (
        "o vazio saiu da conta em SILÊNCIO — trocar número errado por silêncio "
        "não é cura"
    )


def test_a_poda_nao_alcanca_backup_vazio(tmp_path: Path) -> None:
    """Não conta como backup, então não é candidato — e continua no disco."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    _povoar_como_a_maquina_dela(etc)
    morto = etc / "main.conf.bak.hefesto-1786099999"
    morto.touch()

    _rodar(etc, "podar", manter="1", arg="--aplicar")

    assert morto.exists(), "a poda apagou um arquivo que ela nem contava"


def test_o_temporario_do_remover_sai_de_mktemp(tmp_path: Path) -> None:
    """Sufixo fixo (`${tmp}.devolvido`) é nome previsível e sem O_EXCL."""
    codigo = [
        ln for ln in SCRIPT.read_text(encoding="utf-8").splitlines()
        if not ln.lstrip().startswith("#")
    ]
    assert not [ln for ln in codigo if ".devolvido" in ln], (
        "o remover voltou ao temporário de sufixo fixo, sem mktemp e sem O_EXCL"
    )
    assert any('devolvido="$(mktemp)"' in ln for ln in codigo)


def test_aplicar_nomeia_linha_de_terceiro_dentro_do_bloco(tmp_path: Path) -> None:
    """Dentro das sentinelas é o lugar mais óbvio para alguém escrever."""
    etc = _etc(
        tmp_path,
        "[General]\n"
        "# >>> hefesto bluetooth >>>\n"
        "[General]\n"
        "FastConnectable=true\n"
        "JustWorksRepairing=always\n"
        "ControllerMode = bredr\n"
        "MultiProfile = multiple\n"
        "# <<< hefesto bluetooth <<<\n",
    )
    proc = _rodar(etc, "aplicar")

    assert proc.returncode == 0, proc.stderr
    assert "ControllerMode = bredr" in proc.stdout, "a linha alheia saiu em silêncio"
    assert "MultiProfile = multiple" in proc.stdout
    assert "FORA das sentinelas" in proc.stdout
    assert "sai do arquivo: #" not in proc.stdout


def test_bloco_so_com_o_nosso_conteudo_nao_gera_alarme(tmp_path: Path) -> None:
    """Aviso que sai sempre é aviso que ninguém lê."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    proc = _rodar(etc, "aplicar")

    assert "sai do arquivo" not in proc.stdout


def test_remover_grita_o_always_que_devolve(tmp_path: Path) -> None:
    """O `aplicar` grita ao CORRIGIR; o `remover` era mudo ao DEVOLVER."""
    etc = _etc(tmp_path, "[General]\nJustWorksRepairing = always\nName = BlueZ\n")
    _rodar(etc, "aplicar")

    proc = _rodar(etc, "remover")

    assert proc.returncode == 0, proc.stderr
    assert "always" in proc.stdout
    assert "INJEÇÃO DE TECLAS" in proc.stdout
    assert "RADIO-ABERTO-01" in proc.stdout
    assert _valor(etc) == "always", "a linha dela não voltou (o remover apagou config alheia)"


def test_remover_diz_quando_a_chave_deixa_de_existir(tmp_path: Path) -> None:
    """Sem bloco nosso e sem linha dela, quem manda é o default da distro."""
    etc = _etc(tmp_path, "[General]\nName = BlueZ\n")
    _rodar(etc, "aplicar")

    proc = _rodar(etc, "remover")

    assert "default da distro" in proc.stdout


def test_aplicar_avisa_que_rebaixa_um_never(tmp_path: Path) -> None:
    """`never` é MAIS restritivo que o nosso `confirm` — rebaixar em silêncio não."""
    etc = _etc(tmp_path, "[General]\nJustWorksRepairing = never\nName = BlueZ\n")
    proc = _rodar(etc, "aplicar")

    assert "never" in proc.stdout
    assert "REBAIXAR" in proc.stdout
    assert "remover" in proc.stdout
    assert _valor(etc) == "confirm"


def test_sem_main_conf_o_aplicar_nao_anuncia_garantia(tmp_path: Path) -> None:
    """Com /etc/bluetooth presente e main.conf AUSENTE, nada foi escrito."""
    etc = _etc(tmp_path)
    proc = _rodar(etc, "aplicar")

    assert proc.returncode == 0, proc.stderr
    assert "garantidos" not in proc.stdout
    assert "NADA garantido" in proc.stdout


def test_remover_declara_a_excecao_das_linhas_em_branco_do_fim(tmp_path: Path) -> None:
    """A invariante "devolve byte a byte" tem UMA exceção, e ela é declarada."""
    original = "[General]\nName = BlueZ\n\n\n"
    etc = _etc(tmp_path, original)

    _rodar(etc, "aplicar")
    _rodar(etc, "remover")

    assert (etc / "main.conf").read_text(encoding="utf-8") == "[General]\nName = BlueZ\n"
    assert "A EXCEÇÃO DECLARADA da invariante" in SCRIPT.read_text(encoding="utf-8"), (
        "a exceção deixou de estar declarada no próprio script"
    )


def test_remover_recusa_em_vez_de_concluir_que_nao_ha_nada_nosso(tmp_path: Path) -> None:
    """main.conf ilegível fazia o `remover` decidir que não havia bloco nosso."""
    if os.geteuid() == 0:
        pytest.skip("root lê qualquer modo; o cenário não existe")
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    (etc / "main.conf").chmod(0o000)
    try:
        proc = _rodar(etc, "remover")
    finally:
        (etc / "main.conf").chmod(0o644)

    assert proc.returncode != 0, "o remover disse que estava tudo certo sem poder ler o arquivo"
    assert "não consigo LER" in proc.stderr
    assert "# >>> hefesto bluetooth >>>" in (etc / "main.conf").read_text(encoding="utf-8")


def test_verificar_nao_inventa_valor_quando_nao_consegue_ler(tmp_path: Path) -> None:
    """"não declarado" e "não consigo ler" são coisas MUITO diferentes."""
    if os.geteuid() == 0:
        pytest.skip("root lê qualquer modo; o cenário não existe")
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    (etc / "main.conf").chmod(0o000)
    try:
        proc = _rodar(etc, "verificar")
    finally:
        (etc / "main.conf").chmod(0o644)

    assert proc.returncode != 0
    assert "JustWorksRepairing: ilegível" in proc.stdout
    assert "veredito: DESCONHECIDO" in proc.stdout


def test_leitura_de_arquivo_ilegivel_escala_em_vez_de_desistir(tmp_path: Path) -> None:
    """Recusar é melhor que mentir; ESCALAR é melhor que recusar."""
    if os.geteuid() == 0:
        pytest.skip("root lê qualquer modo; o cenário não existe")
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    falso = tmp_path / "escalador" / "sudo-de-mentira"
    falso.parent.mkdir()
    falso.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$*" >> "${HEFESTO_FAKE_SUDO_LOG}"\n'
        'exec "$@"\n',
        encoding="utf-8",
    )
    falso.chmod(0o755)
    (etc / "main.conf").chmod(0o000)
    try:
        _rodar(etc, "verificar", sudo_falso=falso)
    finally:
        (etc / "main.conf").chmod(0o644)

    registro = (falso.parent / "escaladas.txt").read_text(encoding="utf-8")
    assert f"cat {etc / 'main.conf'}" in registro, (
        "a leitura desistiu do arquivo ilegível em vez de escalar — em produção "
        "isso é o uninstall deixando o bloco no disco"
    )


def test_verificar_nao_pede_sudo_para_arquivo_legivel() -> None:
    """O `verificar` é o que o doctor consome: senha em diagnóstico, não."""
    fonte = SCRIPT.read_text(encoding="utf-8")
    assert 'if [[ -r "${arquivo}" ]]; then' in fonte


def _secao_3d() -> str:
    """O passo 3d do install.sh, do cabeçalho até o 3d-bis."""
    texto = INSTALL.read_text(encoding="utf-8")
    inicio = texto.index("# 3d. Bluetooth no máximo")
    fim = texto.index("# 3d-bis.")
    return texto[inicio:fim]


def test_install_anuncia_o_pulo_do_bluez_com_no_udev() -> None:
    """`--no-udev` pulava a cura do BlueZ inteira SEM DIZER UMA PALAVRA."""
    secao = _secao_3d()
    assert '"${SKIP_UDEV}" -eq 1' in secao, "o passo 3d não tem ramo para --no-udev"
    assert "PULADO (--no-udev)" in secao
    assert "bluez_config.sh" in secao.split('"${SKIP_UDEV}" -eq 1')[1].split("elif")[0], (
        "o pulo não diz que a config do BlueZ ficou por fazer"
    )
    assert "verificar" in secao
    assert "JustWorksRepairing=always AGORA" in secao


def test_install_anuncia_o_pulo_tambem_quando_falta_sudo() -> None:
    """Sem o comando `sudo` o passo também sumia da saída, calado."""
    secao = _secao_3d()
    assert "PULADO (sem sudo nesta máquina)" in secao


def test_doctor_le_pelo_dono_unico() -> None:
    """Duas fontes para a mesma regra é a classe de defeito desta leva."""
    doctor = (RAIZ / "scripts" / "doctor.sh").read_text(encoding="utf-8")
    assert '"${dono}" verificar' in doctor
    assert "JustWorksRepairing[[:space:]]*=" not in doctor, (
        "o doctor voltou a ter o próprio parser de JustWorksRepairing"
    )


def test_doctor_avisa_em_vez_de_mentir_quando_o_dono_some() -> None:
    """Sem o `bluez_config.sh`, o doctor não pode dizer "não declarado"."""
    doctor = (RAIZ / "scripts" / "doctor.sh").read_text(encoding="utf-8")
    assert "o dono único da config do BlueZ não está aqui" in doctor


def test_duas_gravacoes_no_mesmo_segundo_nao_comem_o_backup_anterior(
    tmp_path: Path,
) -> None:
    """O estado imediatamente anterior é o backup de MAIOR valor. E era o que sumia."""
    etc = _etc(tmp_path, "[General]\nName = ESTADO-A-DELA\n")
    _rodar(etc, "aplicar")
    (etc / "main.conf").write_text("[General]\nName = ESTADO-B\n", encoding="utf-8")
    _rodar(etc, "aplicar")

    backups = _backups(etc)
    conteudos = [b.read_text(encoding="utf-8") for b in backups]
    assert len(backups) == 2, (
        f"duas gravações deixaram {len(backups)} backup(s): a segunda comeu a "
        "primeira porque o nome só tem resolução de um segundo"
    )
    assert any("ESTADO-A-DELA" in c for c in conteudos), (
        "o backup do estado imediatamente anterior foi DESTRUÍDO — é sempre o "
        "de maior valor, e era sempre ele que morria"
    )
    assert any("ESTADO-B" in c for c in conteudos)


def test_aplicar_e_remover_seguidos_nao_colidem(tmp_path: Path) -> None:
    """A reprodução do verificador, letra por letra: aplicar; remover; aplicar."""
    etc = _etc(tmp_path, "[General]\nName = ESTADO-ORIGINAL\n")
    inicio = time.monotonic()
    _rodar(etc, "aplicar")
    _rodar(etc, "remover")
    _rodar(etc, "aplicar")
    decorrido = time.monotonic() - inicio

    assert len(_backups(etc)) == 2, (
        f"aplicar+remover+aplicar em {decorrido:.2f}s deixou "
        f"{len(_backups(etc))} backup(s) em vez de 2 (um por estado)"
    )
    assert any(
        "ESTADO-ORIGINAL" in b.read_text(encoding="utf-8") for b in _backups(etc)
    ), "o estado ORIGINAL dela não sobreviveu ao ciclo"


def test_a_frase_do_resumo_deixou_de_ser_mentira(tmp_path: Path) -> None:
    """"nenhum é apagado automaticamente" saía na MESMA execução que apagava um."""
    etc = _etc(tmp_path, "[General]\nName = BlueZ\n")
    _rodar(etc, "aplicar")
    antes = {b.name for b in _backups(etc)}
    (etc / "main.conf").write_text("[General]\nName = OUTRO\n", encoding="utf-8")

    proc = _rodar(etc, "aplicar")

    assert "nenhum é apagado automaticamente" in proc.stdout
    assert antes.issubset({b.name for b in _backups(etc)}), (
        "a execução que imprimiu 'nenhum é apagado automaticamente' apagou um"
    )


def test_backup_parcial_e_apagado_e_o_main_conf_nao_e_tocado(tmp_path: Path) -> None:
    """Meio backup é pior que backup nenhum: tem cara de cópia fiel."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    original = (etc / "main.conf").read_bytes()
    pasta = tmp_path / "shim-backup-parcial"
    pasta.mkdir()
    real = shutil.which("cp")
    assert real
    (pasta / "cp").write_text(
        "#!/usr/bin/env bash\n"
        'destino="${@: -1}"\n'
        'if [[ "${destino}" == *"main.conf.bak.hefesto-"* ]]; then\n'
        '    head -c 118 "${@: -2:1}" > "${destino}" 2>/dev/null || true\n'
        "    exit 1\n"
        "fi\n"
        f'exec {real} "$@"\n',
        encoding="utf-8",
    )
    (pasta / "cp").chmod(0o755)

    proc = _rodar(etc, "aplicar", path_extra=pasta)

    assert proc.returncode != 0, "o aplicar seguiu adiante com um backup pela metade"
    assert _backups(etc) == [], (
        f"sobrou backup PARCIAL no disco: "
        f"{[(b.name, b.stat().st_size) for b in _backups(etc)]}"
    )
    assert (etc / "main.conf").read_bytes() == original
    assert "INCOMPLETO" in proc.stderr, "o backup parcial sumiu sem uma palavra"
    assert "garantidos" not in proc.stdout


def test_backup_que_mente_ter_copiado_e_pego_pelo_cmp(tmp_path: Path) -> None:
    """A metade do `cmp`, que até 06/08/2026 NÃO TINHA MORDIDA NENHUMA."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    original = (etc / "main.conf").read_bytes()
    assert len(original) > 118, "a fixture precisa ser maior que o corte"
    pasta = tmp_path / "shim-cp-que-mente"
    pasta.mkdir()
    real = shutil.which("cp")
    assert real
    (pasta / "cp").write_text(
        "#!/usr/bin/env bash\n"
        'destino="${@: -1}"\n'
        'if [[ "${destino}" == *"main.conf.bak.hefesto-"* ]]; then\n'
        '    head -c 118 "${@: -2:1}" > "${destino}" 2>/dev/null\n'
        "    exit 0\n"
        "fi\n"
        f'exec {real} "$@"\n',
        encoding="utf-8",
    )
    (pasta / "cp").chmod(0o755)

    proc = _rodar(etc, "aplicar", path_extra=pasta)

    assert proc.returncode != 0, (
        "o `cp` mentiu ter copiado, o `cmp` não conferiu, e o aplicar seguiu "
        "adiante para reescrever o conffile dela"
    )
    assert _backups(etc) == [], (
        "sobrou um 'backup' de 118 bytes que passa por cópia fiel: "
        f"{[(b.name, b.stat().st_size) for b in _backups(etc)]}"
    )
    assert (etc / "main.conf").read_bytes() == original, (
        "o main.conf dela foi reescrito com um backup cortado por trás"
    )
    assert "INCOMPLETO" in proc.stderr


def test_backup_integro_e_conferido_byte_a_byte(tmp_path: Path) -> None:
    """A linha de base do teste acima: um backup normal É uma cópia fiel."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    _rodar(etc, "aplicar")

    assert len(_backups(etc)) == 1
    assert _backups(etc)[0].read_text(encoding="utf-8") == MAIN_CONF_DELA


_TABELA_DO_GRUPO: list[tuple[str, str, str | None]] = [
    (
        "grupo-errado-nao-conta",
        "[General]\nJustWorksRepairing=always\n\n[Policy]\nJustWorksRepairing=confirm\n",
        "always",
    ),
    (
        "so-em-policy-e-ausente-em-general",
        "[General]\nName = BlueZ\n\n[Policy]\nJustWorksRepairing=always\n",
        None,
    ),
    (
        "o-ultimo-de-general-vence",
        "[General]\nJustWorksRepairing=never\nJustWorksRepairing=always\n",
        "always",
    ),
    (
        "general-repetido-faz-merge-e-o-ultimo-vence",
        "[General]\nJustWorksRepairing=never\n[Policy]\nX=1\n[General]\nJustWorksRepairing=always\n",
        "always",
    ),
    (
        "general-repetido-que-nao-redeclara-nao-apaga",
        "[General]\nJustWorksRepairing=always\n[Policy]\nX=1\n[General]\nFastConnectable=true\n",
        "always",
    ),
    (
        "comentario-nao-e-chave-nem-indentado",
        "[General]\n   # JustWorksRepairing=always\nJustWorksRepairing=confirm\n",
        "confirm",
    ),
    (
        "espaco-em-volta-do-igual-some-a-esquerda",
        "[General]\nJustWorksRepairing =   always\n",
        "always",
    ),
    (
        "cerquilha-no-meio-do-valor-NAO-e-comentario",
        "[General]\nJustWorksRepairing=confirm # nota\n",
        "confirm # nota",
    ),
    (
        "nome-de-grupo-e-exato",
        "[General ]\nJustWorksRepairing=always\n",
        None,
    ),
]


@pytest.mark.parametrize(
    ("nome", "conteudo_conf", "esperado"),
    [(n, c, e) for n, c, e in _TABELA_DO_GRUPO],
    ids=[n for n, _, _ in _TABELA_DO_GRUPO],
)
def test_a_tabela_do_grupo_nao_e_ficcao(
    tmp_path: Path, nome: str, conteudo_conf: str, esperado: str | None
) -> None:
    """Primeiro: o que a tabela AFIRMA é mesmo o que o GKeyFile lê."""
    alvo = tmp_path / "main.conf"
    alvo.write_text(conteudo_conf, encoding="utf-8")

    assert _oraculo(alvo) == esperado, (
        f"a tabela mente sobre o caso '{nome}' — corrija a TABELA, nunca o "
        "oráculo, que é o parser do bluetoothd"
    )


@pytest.mark.parametrize(
    ("nome", "conteudo_conf", "esperado"),
    [(n, c, e) for n, c, e in _TABELA_DO_GRUPO],
    ids=[n for n, _, _ in _TABELA_DO_GRUPO],
)
def test_o_dono_unico_le_exatamente_o_que_o_bluez_le(
    tmp_path: Path, nome: str, conteudo_conf: str, esperado: str | None
) -> None:
    """E então: o `verificar` responde a MESMA coisa, caso a caso."""
    etc = _etc(tmp_path, conteudo_conf)

    proc = _rodar(etc, "verificar")
    lido = next(
        (
            ln[len("JustWorksRepairing: "):]
            for ln in proc.stdout.splitlines()
            if ln.startswith("JustWorksRepairing: ")
        ),
        None,
    )

    assert lido == (esperado if esperado is not None else "ausente"), (
        f"caso '{nome}': o dono único leu {lido!r} e o BlueZ lê {esperado!r} — "
        "é falso negativo do dono, consumido pelo doctor e pelo install"
    )


def test_o_veredito_acompanha_o_grupo(tmp_path: Path) -> None:
    """O caso MEDIDO, até o veredito: `OK` com `always` vivo era o estrago."""
    etc = _etc(
        tmp_path,
        "[General]\nJustWorksRepairing=always\n\n[Policy]\nJustWorksRepairing=confirm\n",
    )

    proc = _rodar(etc, "verificar")

    assert proc.returncode != 0, "veredito OK com JustWorksRepairing=always em [General]"
    assert "veredito: INSEGURO" in proc.stdout
    assert _valor(etc) == "always", "o oráculo confirma: é always que o BlueZ lê"


def test_o_ultimo_vence_e_nao_o_primeiro(tmp_path: Path) -> None:
    """A regra `tail -n 1` sem teste: trocar por `head -n 1` passava verde."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    _rodar(etc, "aplicar")
    with (etc / "main.conf").open("a", encoding="utf-8") as fh:
        fh.write("\n[General]\nJustWorksRepairing=always\n")

    proc = _rodar(etc, "verificar")

    assert _valor(etc) == "always", "o oráculo: quem vem depois vence"
    assert "JustWorksRepairing: always" in proc.stdout, (
        "o dono único leu a PRIMEIRA ocorrência — quem apensa depois do nosso "
        "bloco vence, e o veredito sairia OK com always no ar"
    )
    assert proc.returncode != 0


def test_aplicar_corrige_o_caso_do_grupo(tmp_path: Path) -> None:
    """Detectar não basta: depois do `aplicar`, o BlueZ tem de ler `confirm`."""
    etc = _etc(
        tmp_path,
        "[General]\nJustWorksRepairing=always\n\n[Policy]\nJustWorksRepairing=confirm\n",
    )

    proc = _rodar(etc, "aplicar")

    assert proc.returncode == 0, proc.stderr
    assert _valor(etc) == "confirm"


def test_never_fora_do_bloco_ganha_a_promessa_e_ela_se_cumpre(tmp_path: Path) -> None:
    """Fora do bloco a promessa é verdadeira — e o teste cobra o cumprimento."""
    original = "[General]\nJustWorksRepairing = never\nName = BlueZ\n"
    etc = _etc(tmp_path, original)

    proc = _rodar(etc, "aplicar")
    assert "volta inteira" in proc.stdout
    assert "FORA do bloco" in proc.stdout
    assert _valor(etc) == "confirm"

    _rodar(etc, "remover")
    assert (etc / "main.conf").read_text(encoding="utf-8") == original, (
        "a promessa foi feita e não foi cumprida"
    )
    assert _valor(etc) == "never"


def test_never_dentro_do_bloco_nao_ganha_promessa_que_nao_se_cumpre(
    tmp_path: Path,
) -> None:
    """Dentro do bloco a linha SAI e não volta. Então não se promete que volta."""
    etc = _etc(
        tmp_path,
        "[General]\nName = BlueZ\n"
        "# >>> hefesto bluetooth >>>\n"
        "[General]\n"
        "FastConnectable=true\n"
        "JustWorksRepairing=never\n"
        "# <<< hefesto bluetooth <<<\n",
    )

    proc = _rodar(etc, "aplicar")

    assert "REBAIXAR" in proc.stdout
    assert "DENTRO do bloco hefesto" in proc.stdout, (
        "o aviso não diz que a linha está dentro do bloco"
    )
    assert "não a devolve" in proc.stdout or "NÃO a devolve" in proc.stdout, (
        "o aviso não nomeia o que vai sumir"
    )
    assert "volta inteira no 'remover'" not in proc.stdout.split("DENTRO do bloco")[0], (
        "a promessa falsa continua sendo feita antes da ressalva"
    )
    assert _valor(etc) == "confirm"

    _rodar(etc, "remover")
    assert _valor(etc) is None, (
        "se o `never` de dentro do bloco passou a voltar, a promessa pode ser "
        "feita de novo — mas então este teste é que tem de mudar, de propósito"
    )


def test_o_doctor_nao_promete_devolucao_sem_ressalva() -> None:
    """O mesmo texto vivia no doctor, e é lá que ela lê primeiro."""
    doctor = (RAIZ / "scripts" / "doctor.sh").read_text(encoding="utf-8")
    aviso = next(
        ln for ln in doctor.splitlines()
        if "JustWorksRepairing=never no main.conf" in ln
    )
    assert "FORA das sentinelas" in aviso and "DENTRO do bloco" in aviso, (
        "o doctor voltou a prometer a devolução da linha sem dizer que ela só "
        "vale FORA do bloco hefesto"
    )


def test_bloco_de_zero_byte_nao_anuncia_garantia(tmp_path: Path) -> None:
    """Cada passo deu certo e o resultado não existe."""
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "hefesto-bt.block").write_text("", encoding="utf-8")
    for nome in ("hefesto-fastconnectable.conf", "hefesto-justworks.conf"):
        shutil.copy(ASSETS / nome, assets / nome)
    etc = _etc(tmp_path, "[General]\nName = BlueZ\n")

    ambiente = {
        **os.environ,
        "HEFESTO_BT_ETC": str(etc),
        "HEFESTO_BT_ASSETS": str(assets),
        "HEFESTO_BT_SUDO": "",
    }
    proc = subprocess.run(
        ["bash", str(SCRIPT), "aplicar"],
        capture_output=True,
        text=True,
        timeout=60,
        env=ambiente,
    )

    assert proc.returncode != 0, (
        "o aplicar saiu com 0 e o arquivo final não tem a chave nenhuma"
    )
    assert "garantidos" not in proc.stdout
    assert "reli" in proc.stderr, "a conferência final do disco não aconteceu"
    assert _valor(etc) is None


def test_o_comentario_nao_promete_durabilidade_que_nao_entrega() -> None:
    """`rename(2)` dá ATOMICIDADE, não DURABILIDADE — e não há `fsync` aqui."""
    fonte = SCRIPT.read_text(encoding="utf-8")
    assert "ATOMICIDADE, não DURABILIDADE" in fonte, (
        "o comentário da troca atômica voltou a prometer durabilidade"
    )
    assert "fsync" in fonte, "a ausência do fsync deixou de ser declarada"
    codigo = [
        ln for ln in fonte.splitlines()
        if not ln.lstrip().startswith("#") and "queda de energia" in ln
    ]
    assert codigo == []


def test_verificar_reporta_o_valor_dos_dropins(tmp_path: Path) -> None:
    """O ANEXO da verificação adversarial, avaliado e reportado."""
    etc = _etc(
        tmp_path,
        "[General]\nFastConnectable=true\nJustWorksRepairing=confirm\n",
        com_dropin_dir=True,
    )
    (etc / "main.conf.d" / "zz-de-terceiro.conf").write_text(
        "[General]\nJustWorksRepairing=always\n", encoding="utf-8"
    )

    proc = _rodar(etc, "verificar")

    assert "dropin-JustWorksRepairing: zz-de-terceiro.conf=always" in proc.stdout, (
        "o verificar continua cego para o VALOR dentro de main.conf.d"
    )
    assert "dropin-em-conflito: zz-de-terceiro.conf declara always" in proc.stdout
    assert "veredito: OK" in proc.stdout, (
        "o veredito passou a depender de main.conf.d — neste BlueZ o diretório "
        "é inerte (MEDIDO), e alarme falso é o defeito de costas"
    )


def test_dropin_nosso_nao_vira_conflito(tmp_path: Path) -> None:
    """Aviso que sai sempre é aviso que ninguém lê."""
    etc = _etc(tmp_path, MAIN_CONF_DELA, com_dropin_dir=True)
    _rodar(etc, "aplicar")

    proc = _rodar(etc, "verificar")

    assert "dropin-JustWorksRepairing: hefesto-justworks.conf=confirm" in proc.stdout
    assert "dropin-em-conflito" not in proc.stdout


def test_a_nota_do_no_udev_nao_alega_o_que_o_ci_nao_faz() -> None:
    """Decisão gravada sobre medição FALSA é pior que decisão sem nota."""
    secao = INSTALL.read_text(encoding="utf-8")
    assert "máquina de build" not in secao, (
        "a justificativa falsa voltou: o CI não roda o install.sh"
    )
    assert "o CI não roda o `install.sh`" in secao, "a nota datada sumiu"

    fluxos = RAIZ / ".github" / "workflows"
    invocacoes = []
    for arquivo in sorted(fluxos.glob("*.yml")):
        for numero, linha in enumerate(
            arquivo.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if "install.sh" not in linha or "shellcheck" in linha:
                continue
            if linha.lstrip().startswith("#"):
                continue
            invocacoes.append(f"{arquivo.name}:{numero}: {linha.strip()}")
    assert "SEGUNDA NOTA DATADA" in secao, (
        "o CI roda o install.sh desde 19/08/2026, e o `install.sh` voltou a ter "
        "só a nota de 06/08 dizendo que ele NÃO roda. Uma nota datada não se "
        f"apaga e não envelhece calada. Invocações vivas: {invocacoes}"
    )
    assert invocacoes, (
        "o CI deixou de rodar o `install.sh`. Se foi de propósito, reescreva a "
        "SEGUNDA nota datada dizendo por quê — mas saiba o que se perde: era "
        "esse job que aferia o instalador no PATH de uma usuária comum, e sem "
        "ele o bloqueante do `ldconfig` fora do `/usr/sbin` volta a ser "
        "invisível para todo portão desta casa"
    )


def test_o_caso_do_link_simbolico_esta_dito(tmp_path: Path) -> None:
    """Não é regressão, não é o caso dela — mas merece a linha no comentário."""
    assert "LINK SIMBÓLICO" in SCRIPT.read_text(encoding="utf-8")

    alvo = tmp_path / "main.conf.real"
    alvo.write_text("[General]\nName = BlueZ\n", encoding="utf-8")
    etc = tmp_path / "bluetooth"
    etc.mkdir()
    (etc / "main.conf").symlink_to(alvo)

    proc = _rodar(etc, "aplicar")

    assert proc.returncode == 0, proc.stderr
    assert _valor(etc) == "confirm", "o valor seguro não chegou ao arquivo lido"
    assert not (etc / "main.conf").is_symlink(), (
        "se o link passou a ser preservado, ÓTIMO — mas então o comentário e "
        "este teste têm de mudar juntos, de propósito"
    )


_TABELA_DA_RECUSA: list[tuple[str, str]] = [
    (
        "linha-solta-sem-igual",
        "[General]\nJustWorksRepairing=confirm\nlinha-solta-sem-igual\n",
    ),
    (
        "linha-solta-com-espaco",
        "[General]\nJustWorksRepairing=confirm\nisto tem espaco e nada mais\n",
    ),
    (
        "chave-antes-do-primeiro-grupo",
        "JustWorksRepairing=always\n[General]\nJustWorksRepairing=confirm\n",
    ),
]


@pytest.mark.parametrize(
    ("nome", "conteudo_conf"),
    _TABELA_DA_RECUSA,
    ids=[n for n, _ in _TABELA_DA_RECUSA],
)
def test_a_tabela_da_recusa_nao_e_ficcao(
    tmp_path: Path, nome: str, conteudo_conf: str
) -> None:
    """Primeiro: o GKeyFile RECUSA MESMO estes arquivos, inteiros."""
    alvo = tmp_path / "main.conf"
    alvo.write_text(conteudo_conf, encoding="utf-8")

    assert _oraculo_recusa(alvo) is not None, (
        f"a tabela afirma que o GKeyFile recusa '{nome}' e ele NÃO recusa — "
        "corrija a TABELA, nunca o oráculo"
    )
    assert _oraculo(alvo) is None


@pytest.mark.parametrize(
    ("nome", "conteudo_conf"),
    _TABELA_DA_RECUSA,
    ids=[n for n, _ in _TABELA_DA_RECUSA],
)
def test_o_dono_unico_nao_aprova_arquivo_que_o_bluez_descarta(
    tmp_path: Path, nome: str, conteudo_conf: str
) -> None:
    """O falso `OK` mais silencioso que havia."""
    etc = _etc(tmp_path, conteudo_conf)

    proc = _rodar(etc, "verificar")

    assert proc.returncode != 0, f"caso '{nome}': o dono aprovou o arquivo"
    assert "veredito: OK" not in proc.stdout, (
        f"caso '{nome}': `veredito: OK` sobre um arquivo que o bluetoothd "
        "descarta inteiro"
    )
    assert "veredito: RECUSADO" in proc.stdout
    assert "recusado pelo parser" in proc.stdout, "não diz QUE linha é"


def test_o_aplicar_nao_anuncia_garantia_sobre_arquivo_recusado(tmp_path: Path) -> None:
    """E a outra boca: escrever a chave num arquivo recusado não garante nada."""
    etc = _etc(
        tmp_path,
        "[General]\nName = BlueZ\nlinha-solta-que-o-parser-recusa\n",
    )

    proc = _rodar(etc, "aplicar")

    assert proc.returncode != 0, "anunciou sucesso sobre um arquivo que o BlueZ descarta"
    assert "garantidos" not in proc.stdout
    assert "RECUSA" in proc.stderr
    assert "linha-solta-que-o-parser-recusa" in proc.stderr, "não nomeia a linha"
    assert _oraculo_recusa(etc / "main.conf") is not None


def test_arquivo_valido_com_bloco_nosso_nao_e_acusado_de_recusa(tmp_path: Path) -> None:
    """A linha de base: um detector de recusa que acusa tudo não serve."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)

    _rodar(etc, "aplicar")
    proc = _rodar(etc, "verificar")

    assert _oraculo_recusa(etc / "main.conf") is None, (
        "o arquivo que NÓS escrevemos é recusado pelo GKeyFile de verdade"
    )
    assert "recusado pelo parser" not in proc.stdout
    assert "veredito: OK" in proc.stdout


def test_crlf_o_dono_le_o_mesmo_que_o_bluez(tmp_path: Path) -> None:
    """MEDIDO: o GKeyFile descarta o `\\r` do fim e PRESERVA os espaços."""
    conteudo = "[General]\r\nJustWorksRepairing=confirm\r\n"
    etc = _etc(tmp_path, conteudo)
    assert _valor(etc) == "confirm", "a premissa do teste mudou — confira o oráculo"

    proc = _rodar(etc, "verificar")

    assert "JustWorksRepairing: confirm\n" in proc.stdout, (
        "o dono leu o CR como parte do valor: discorda do BlueZ E embaralha a "
        f"mensagem no terminal. Saída bruta: {proc.stdout!r}"
    )
    assert "veredito: OK" in proc.stdout, (
        "um main.conf salvo com CRLF virou 'INSEGURO' sem nada de inseguro nele"
    )


def test_valor_vazio_existe_e_nao_e_ausente(tmp_path: Path) -> None:
    """MEDIDO: `JustWorksRepairing=` faz o GKeyFile dizer que a chave EXISTE."""
    etc = _etc(tmp_path, "[General]\nJustWorksRepairing=\n")
    assert _valor(etc) == "", "a premissa do teste mudou — confira o oráculo"

    proc = _rodar(etc, "verificar")

    assert "JustWorksRepairing: ausente" not in proc.stdout, (
        "chave declarada com valor vazio foi relatada como AUSENTE"
    )
    assert "JustWorksRepairing: (vazio)" in proc.stdout
    assert "veredito: INSEGURO" in proc.stdout


def test_as_tres_excecoes_do_devolve_byte_a_byte_estao_declaradas(
    tmp_path: Path,
) -> None:
    """A invariante tinha TRÊS exceções e só uma estava escrita (achado (e))."""
    fonte = SCRIPT.read_text(encoding="utf-8")
    assert "AS TRÊS EXCEÇÕES da promessa" in fonte, (
        "as exceções da invariante 3 deixaram de estar declaradas no cabeçalho"
    )

    for sub in ("i", "ii", "iii"):
        (tmp_path / sub).mkdir()
    etc = _etc(tmp_path / "i", "[General]\nName = BlueZ\n\n\n")
    _rodar(etc, "aplicar")
    _rodar(etc, "remover")
    assert (etc / "main.conf").read_text(encoding="utf-8") == "[General]\nName = BlueZ\n"

    dentro = (
        "[General]\n"
        "# >>> hefesto bluetooth >>>\n"
        "[General]\n"
        "JustWorksRepairing=never\n"
        "# <<< hefesto bluetooth <<<\n"
    )
    etc = _etc(tmp_path / "ii", dentro)
    _rodar(etc, "remover")
    assert "JustWorksRepairing" not in (etc / "main.conf").read_text(encoding="utf-8"), (
        "a exceção (ii) deixou de existir — reveja a declaração do cabeçalho"
    )

    etc = _etc(
        tmp_path / "iii",
        "[General]\n"
        f"{MARCA}JustWorksRepairing=always\n"
        "# >>> hefesto bluetooth >>>\n"
        "# <<< hefesto bluetooth <<<\n",
    )
    _rodar(etc, "remover")
    depois = (etc / "main.conf").read_text(encoding="utf-8")
    assert f"{MARCA}JustWorksRepairing" not in depois, (
        "a exceção (iii) deixou de existir — reveja a declaração do cabeçalho"
    )
    assert "JustWorksRepairing=always" in depois, (
        "a linha marcada nem foi devolvida nem ficou marcada — é um terceiro "
        "comportamento, e nenhum dos três está declarado"
    )
