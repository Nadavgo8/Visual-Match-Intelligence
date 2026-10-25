// Shared WebSocket session for the match screen and the companion app (D2-02).
//
// - Every server message carries `run_id` and a per-connection `seq`.
// - A `snapshot` starts a run: the client resets run-scoped state and applies it.
// - Messages from an older run, duplicates and out-of-order messages are dropped.
// - A dropped connection is reported as disconnected and retried with a bounded backoff;
//   the server sends a fresh snapshot on every connection, so nothing is invented meanwhile.

export const BACKOFF_MS = [500, 1000, 2000, 4000, 8000];

export function backoffDelay(attempt) {
  return BACKOFF_MS[Math.min(Math.max(attempt, 0), BACKOFF_MS.length - 1)];
}

export class MessageGate {
  constructor() { this.runId = null; this.lastSeq = 0; }

  // Every connection needs a fresh snapshot; the previous run is not a grant
  // to accept messages arriving before the replacement snapshot.
  connectionOpened() { this.lastSeq = 0; this.runId = null; }

  accept(m) {
    if (!m || typeof m.type !== "string" || typeof m.run_id !== "string" || !m.run_id
      || !Number.isSafeInteger(m.seq) || m.seq <= this.lastSeq) return false;
    if (this.runId === null && m.type !== "snapshot") return false;
    this.lastSeq = m.seq;
    if (m.type === "snapshot") { this.runId = m.run_id; return true; }
    return this.runId !== null && m.run_id === this.runId;
  }
}

export function hostTokenStore(room, storage = globalThis.sessionStorage) {
  const key = `vmi.host.${room}`;
  return {
    get() { try { return storage?.getItem(key) ?? null; } catch { return null; } },
    set(token) { try { storage?.setItem(key, token); } catch { /* private mode: host only for this tab */ } },
  };
}

export function sessionUrl(loc, room, role, token) {
  const q = new URLSearchParams({ role });
  if (token) q.set("host", token);
  return `${loc.protocol === "https:" ? "wss" : "ws"}://${loc.host}/ws/${encodeURIComponent(room)}?${q}`;
}

export function openSession({ room, role, onMessage, onStatus, hostToken = null,
                              WebSocketImpl = globalThis.WebSocket, schedule = setTimeout, loc = location }) {
  const gate = new MessageGate();
  let ws = null, attempt = 0, closed = false;

  function connect() {
    if (closed) return;
    const socket = new WebSocketImpl(sessionUrl(loc, room, role, hostToken?.get()));
    ws = socket;
    gate.connectionOpened();
    const current = () => !closed && ws === socket;
    socket.onopen = () => { if (current()) { attempt = 0; onStatus?.("connected"); } };
    socket.onmessage = (ev) => {
      if (!current()) return;
      let m;
      try { m = JSON.parse(ev.data); } catch { return; }
      if (!gate.accept(m)) return;
      if (m.type === "snapshot" && m.host_token) hostToken?.set(m.host_token);
      onMessage(m);
    };
    socket.onclose = () => {
      if (!current()) return;
      ws = null;
      onStatus?.("disconnected");
      schedule(() => { if (!closed && ws === null) connect(); }, backoffDelay(attempt++));
    };
  }

  connect();
  return {
    send(m) {
      if (ws?.readyState !== 1) return false;
      ws.send(JSON.stringify(m));
      return true;
    },
    close() { closed = true; const socket = ws; ws = null; socket?.close(); },
  };
}
