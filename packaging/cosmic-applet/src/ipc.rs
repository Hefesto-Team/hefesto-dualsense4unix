//! Cliente JSON-RPC 2.0 newline-delimited (UTF-8) sobre Unix socket.
//!
//! Espelha `src/hefesto_dualsense4unix/cli/ipc_client.py` do daemon Python:
//! cada requisição é UMA linha JSON terminada em `\n`; a resposta também é
//! uma única linha JSON. Usamos `tokio::net::UnixStream` + `BufReader` e um
//! timeout curto (~250 ms) por chamada — se o socket não existir ou o daemon
//! não responder a tempo, devolvemos `Err` e a UI degrada para "offline".
//!
//! Métodos consumidos pelo applet:
//!   - `daemon.state_full` -> estado completo (bateria, transporte, perfil...)
//!   - `profile.list`      -> lista de perfis
//!   - `profile.switch {name}` -> troca o perfil ativo
//!   - `daemon.emulation.suppress {suppressed}` -> liga/desliga o "modo jogo"

use std::path::PathBuf;
use std::time::Duration;

use serde::Deserialize;
use serde_json::json;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::net::UnixStream;

/// Timeout por chamada IPC. Curto de propósito: o painel não pode travar
/// esperando um daemon morto.
const IPC_TIMEOUT: Duration = Duration::from_millis(250);

/// Nome-base padrão do socket (igual a `IPC_SOCKET_DEFAULT_NAME` no Python).
const SOCKET_DEFAULT_NAME: &str = "hefesto-dualsense4unix.sock";
/// Env var que sobrescreve o nome-base do socket (paridade com o Python).
const SOCKET_ENV_VAR: &str = "HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME";
/// Subdiretório do app dentro do runtime dir.
const APP_DIR: &str = "hefesto-dualsense4unix";

/// Erro do cliente IPC. `Offline` cobre socket ausente / conexão recusada /
/// timeout — tudo que a UI deve tratar como "daemon não disponível".
#[derive(Debug, Clone)]
pub enum IpcError {
    /// Daemon indisponível (socket ausente, conexão recusada ou timeout).
    Offline,
    /// O daemon respondeu com um erro JSON-RPC `{code, message}`.
    Rpc { code: i64, message: String },
    /// Resposta malformada / falha de (de)serialização.
    Protocol(String),
}

impl std::fmt::Display for IpcError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            IpcError::Offline => write!(f, "daemon offline"),
            IpcError::Rpc { code, message } => write!(f, "[{code}] {message}"),
            IpcError::Protocol(msg) => write!(f, "protocolo: {msg}"),
        }
    }
}

/// Resolve o caminho do socket IPC.
///
/// Espelha `ipc_socket_path()` em `utils/xdg_paths.py`:
///   `$XDG_RUNTIME_DIR/hefesto-dualsense4unix/<nome>.sock`
/// Fallback (XDG_RUNTIME_DIR ausente, ex.: sessões raras): usa
/// `$XDG_CACHE_HOME/hefesto-dualsense4unix/runtime/` ou `~/.cache/...`.
/// O nome-base respeita a env var (apenas nome simples, sem `/`).
pub fn socket_path() -> PathBuf {
    let name = std::env::var(SOCKET_ENV_VAR)
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty() && !s.contains('/') && s != ".." && s != ".")
        .unwrap_or_else(|| SOCKET_DEFAULT_NAME.to_string());

    runtime_dir().join(name)
}

/// Diretório do socket, paritário com `runtime_dir()` em `xdg_paths.py`:
///   - `XDG_RUNTIME_DIR` presente -> `$XDG_RUNTIME_DIR/hefesto-dualsense4unix/`
///   - ausente (fallback platformdirs) -> `<cache>/hefesto-dualsense4unix/runtime/`
fn runtime_dir() -> PathBuf {
    if let Ok(dir) = std::env::var("XDG_RUNTIME_DIR") {
        if !dir.is_empty() {
            return PathBuf::from(dir).join(APP_DIR);
        }
    }
    // Fallback: cache_dir/<app>/runtime (igual a platformdirs no Python).
    let cache = std::env::var("XDG_CACHE_HOME")
        .ok()
        .filter(|s| !s.is_empty())
        .map(PathBuf::from)
        .or_else(|| {
            std::env::var("HOME")
                .ok()
                .map(|h| PathBuf::from(h).join(".cache"))
        })
        .unwrap_or_else(|| PathBuf::from("/tmp"));
    cache.join(APP_DIR).join("runtime")
}

/// Estado completo retornado por `daemon.state_full`.
///
/// `#[serde(default)]` em cada campo torna a deserialização resiliente a
/// versões do daemon que (ainda) não enviem algum campo.
#[derive(Debug, Clone, Default, Deserialize)]
pub struct DaemonState {
    #[serde(default)]
    pub connected: bool,
    /// "usb" | "bluetooth" | null.
    #[serde(default)]
    pub transport: Option<String>,
    #[serde(default)]
    pub active_profile: Option<String>,
    /// Percentual de bateria 0-100, ou null se desconhecido.
    #[serde(default)]
    pub battery_pct: Option<i64>,
    /// FEAT-DAEMON-PAUSE-RESUME-01: true se o daemon está pausado (vivo, mas
    /// sem despachar input). serde(default)=false tolera daemons antigos.
    #[serde(default)]
    pub paused: bool,
    /// FEAT-DSX-GAMEMODE-SUPPRESS-01: true quando o "modo jogo" está ligado —
    /// a emulação de mouse/teclado fica suspensa (transitório, não persiste em
    /// disco), mas o gamepad segue vivo no jogo. Distinto de `paused`, que é o
    /// kill-switch amplo e persistente do daemon. serde(default)=false tolera
    /// daemons antigos.
    #[serde(default)]
    pub emulation_suppressed: bool,
}

/// Um perfil retornado por `profile.list`.
///
/// `priority` e `match_type` fazem parte do contrato do daemon e são
/// deserializados para fidelidade ao protocolo (e uso futuro: ordenar por
/// prioridade, exibir o tipo de match). A UI atual só consome `name`, então
/// ficam marcados como permitidos-sem-uso.
#[derive(Debug, Clone, Deserialize)]
pub struct ProfileInfo {
    pub name: String,
    #[serde(default)]
    #[allow(dead_code)]
    pub priority: i64,
    /// "any" | "criteria".
    #[serde(default)]
    #[allow(dead_code)]
    pub match_type: String,
}

#[derive(Debug, Deserialize)]
struct ProfileListResult {
    #[serde(default)]
    profiles: Vec<ProfileInfo>,
}

/// Envelope de resposta JSON-RPC.
#[derive(Debug, Deserialize)]
struct RpcResponse {
    #[serde(default)]
    result: Option<serde_json::Value>,
    #[serde(default)]
    error: Option<RpcErrorBody>,
}

#[derive(Debug, Deserialize)]
struct RpcErrorBody {
    code: i64,
    message: String,
}

/// Executa uma chamada JSON-RPC e devolve o `result` bruto.
///
/// Abre uma conexão nova por chamada (mesmo padrão da CLI Python: barato e
/// stateless). Todo o I/O é coberto por um único timeout de [`IPC_TIMEOUT`].
async fn call_raw(method: &str, params: serde_json::Value) -> Result<serde_json::Value, IpcError> {
    call_raw_at(socket_path(), method, params).await
}

/// Variante de [`call_raw`] com caminho de socket explícito (usada nos testes).
async fn call_raw_at(
    path: std::path::PathBuf,
    method: &str,
    params: serde_json::Value,
) -> Result<serde_json::Value, IpcError> {
    let fut = async {
        let stream = UnixStream::connect(&path)
            .await
            .map_err(|_| IpcError::Offline)?;
        let (read_half, mut write_half) = stream.into_split();

        let request = json!({
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        });
        let mut payload =
            serde_json::to_vec(&request).map_err(|e| IpcError::Protocol(e.to_string()))?;
        payload.push(b'\n');
        write_half
            .write_all(&payload)
            .await
            .map_err(|_| IpcError::Offline)?;
        write_half.flush().await.map_err(|_| IpcError::Offline)?;

        let mut reader = BufReader::new(read_half);
        let mut line = String::new();
        let n = reader
            .read_line(&mut line)
            .await
            .map_err(|_| IpcError::Offline)?;
        if n == 0 {
            // Conexão fechada antes da resposta.
            return Err(IpcError::Offline);
        }

        let resp: RpcResponse =
            serde_json::from_str(line.trim_end()).map_err(|e| IpcError::Protocol(e.to_string()))?;
        if let Some(err) = resp.error {
            return Err(IpcError::Rpc {
                code: err.code,
                message: err.message,
            });
        }
        resp.result
            .ok_or_else(|| IpcError::Protocol("resposta sem 'result'".to_string()))
    };

    match tokio::time::timeout(IPC_TIMEOUT, fut).await {
        Ok(res) => res,
        Err(_) => Err(IpcError::Offline),
    }
}

/// `daemon.state_full` — estado completo do daemon/controle.
pub async fn fetch_state() -> Result<DaemonState, IpcError> {
    let value = call_raw("daemon.state_full", json!({})).await?;
    serde_json::from_value(value).map_err(|e| IpcError::Protocol(e.to_string()))
}

/// `profile.list` — perfis disponíveis (ordenados por nome para UI estável).
pub async fn fetch_profiles() -> Result<Vec<ProfileInfo>, IpcError> {
    let value = call_raw("profile.list", json!({})).await?;
    let parsed: ProfileListResult =
        serde_json::from_value(value).map_err(|e| IpcError::Protocol(e.to_string()))?;
    let mut profiles = parsed.profiles;
    profiles.sort_by_key(|p| p.name.to_lowercase());
    Ok(profiles)
}

/// `profile.switch {name}` — ativa um perfil. Devolve o nome do perfil ativo.
pub async fn switch_profile(name: String) -> Result<String, IpcError> {
    let value = call_raw("profile.switch", json!({ "name": name })).await?;
    let active = value
        .get("active_profile")
        .and_then(|v| v.as_str())
        .map(str::to_string)
        .ok_or_else(|| IpcError::Protocol("switch sem 'active_profile'".to_string()))?;
    Ok(active)
}

/// `daemon.emulation.suppress {suppressed}` — liga/desliga o "modo jogo":
/// suspende a emulação de mouse/teclado mantendo o gamepad vivo no jogo
/// (FEAT-DSX-GAMEMODE-SUPPRESS-01). Transitório — NÃO persiste em disco (ao
/// contrário do antigo `daemon.pause`, que renascia pausado no boot). Espelha a
/// semântica da GUI e do combo PS+Options. Devolve o novo `emulation_suppressed`
/// reportado pelo daemon (fallback: o valor solicitado).
pub async fn set_emulation_suppressed(suppressed: bool) -> Result<bool, IpcError> {
    let value = call_raw(
        "daemon.emulation.suppress",
        json!({ "suppressed": suppressed }),
    )
    .await?;
    let new_state = value
        .get("emulation_suppressed")
        .and_then(|v| v.as_bool())
        .unwrap_or(suppressed);
    Ok(new_state)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;
    use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
    use tokio::net::UnixListener;

    /// Sobe um servidor Unix socket de uma única conexão que lê uma linha de
    /// requisição e responde com `reply` (sem `\n` — adicionamos aqui).
    fn spawn_mock(path: PathBuf, reply: String) {
        let listener = UnixListener::bind(&path).expect("bind mock socket");
        tokio::spawn(async move {
            if let Ok((stream, _)) = listener.accept().await {
                let (read_half, mut write_half) = stream.into_split();
                let mut reader = BufReader::new(read_half);
                let mut line = String::new();
                let _ = reader.read_line(&mut line).await;
                let mut out = reply.into_bytes();
                out.push(b'\n');
                let _ = write_half.write_all(&out).await;
                let _ = write_half.flush().await;
            }
        });
    }

    fn temp_socket(tag: &str) -> PathBuf {
        let mut p = std::env::temp_dir();
        let uniq = format!(
            "hefesto-applet-test-{tag}-{}.sock",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        );
        p.push(uniq);
        let _ = std::fs::remove_file(&p);
        p
    }

    #[test]
    fn socket_path_uses_runtime_dir_layout() {
        // Não dependemos do ambiente real: o caminho sempre termina no
        // subdiretório do app + nome-base do socket.
        let path = socket_path();
        let s = path.to_string_lossy();
        assert!(
            s.ends_with("hefesto-dualsense4unix/hefesto-dualsense4unix.sock"),
            "{s}"
        );
    }

    #[tokio::test]
    async fn offline_when_socket_absent() {
        let path = temp_socket("absent");
        // Sem servidor: connect falha -> Offline (sem panic).
        let res = call_raw_at(path, "daemon.state_full", json!({})).await;
        assert!(matches!(res, Err(IpcError::Offline)));
    }

    #[tokio::test]
    async fn parses_state_full() {
        let path = temp_socket("state");
        spawn_mock(
            path.clone(),
            r#"{"jsonrpc":"2.0","id":1,"result":{"connected":true,"transport":"usb","active_profile":"Padrão","battery_pct":42}}"#
                .to_string(),
        );
        // Pequena espera para o listener ficar pronto.
        tokio::time::sleep(Duration::from_millis(20)).await;
        let value = call_raw_at(path, "daemon.state_full", json!({}))
            .await
            .expect("result");
        let state: DaemonState = serde_json::from_value(value).unwrap();
        assert!(state.connected);
        assert_eq!(state.transport.as_deref(), Some("usb"));
        assert_eq!(state.active_profile.as_deref(), Some("Padrão"));
        assert_eq!(state.battery_pct, Some(42));
    }

    #[tokio::test]
    async fn parses_profile_list_and_sorts() {
        let path = temp_socket("profiles");
        spawn_mock(
            path.clone(),
            r#"{"jsonrpc":"2.0","id":1,"result":{"profiles":[{"name":"Zelda","priority":1,"match_type":"any"},{"name":"apex","priority":2,"match_type":"criteria"}]}}"#
                .to_string(),
        );
        tokio::time::sleep(Duration::from_millis(20)).await;
        let value = call_raw_at(path, "profile.list", json!({}))
            .await
            .expect("result");
        let parsed: ProfileListResult = serde_json::from_value(value).unwrap();
        let mut profiles = parsed.profiles;
        profiles.sort_by_key(|p| p.name.to_lowercase());
        // Ordenação case-insensitive: "apex" antes de "Zelda".
        assert_eq!(profiles[0].name, "apex");
        assert_eq!(profiles[1].name, "Zelda");
    }

    #[tokio::test]
    async fn maps_rpc_error() {
        let path = temp_socket("err");
        spawn_mock(
            path.clone(),
            r#"{"jsonrpc":"2.0","id":1,"error":{"code":-32602,"message":"perfil inexistente"}}"#
                .to_string(),
        );
        tokio::time::sleep(Duration::from_millis(20)).await;
        let res = call_raw_at(path, "profile.switch", json!({"name":"x"})).await;
        match res {
            Err(IpcError::Rpc { code, message }) => {
                assert_eq!(code, -32602);
                assert_eq!(message, "perfil inexistente");
            }
            other => panic!("esperava Rpc, veio {other:?}"),
        }
    }
}
