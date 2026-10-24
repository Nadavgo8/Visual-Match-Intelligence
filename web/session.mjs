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

  // A new connection: the server's sequence numbers start again.
  connectionOpened() { this.lastSeq = 0; }

  accept(m) {
    if (!Number.isInteger(m?.seq) || m.seq <= this.lastSeq) return false;
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
    ws = new WebSocketImpl(sessionUrl(loc, room, role, hostToken?.get()));
    gate.connectionOpened();
    ws.onopen = () => { attempt = 0; onStatus?.("connected"); };
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.type === "snapshot" && m.host_token) hostToken?.set(m.host_token);
      if (gate.accept(m)) onMessage(m);
    };
    ws.onclose = () => {
      if (closed) return;
      onStatus?.("disconnected");
      schedule(connect, backoffDelay(attempt++));
    };
  }

  connect();
  return {
    send(m) {
      if (ws?.readyState !== 1) return false;
      ws.send(JSON.stringify(m));
      return true;
    },
    close() { closed = true; ws?.close(); },
  };
}
