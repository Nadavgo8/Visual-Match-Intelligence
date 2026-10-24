import test from "node:test";
import assert from "node:assert/strict";
import { BACKOFF_MS, MessageGate, backoffDelay, hostTokenStore, openSession, sessionUrl } from "../../web/session.mjs";

test("reconnect backoff grows and stays bounded", () => {
  assert.deepEqual([0, 1, 2, 3, 4, 5, 50].map(backoffDelay), [500, 1000, 2000, 4000, 8000, 8000, 8000]);
  assert.equal(backoffDelay(-3), BACKOFF_MS[0]);
});

test("gate needs a snapshot first, then accepts only the same run in order", () => {
  const g = new MessageGate();
  assert.equal(g.accept({ type: "meters", seq: 1, run_id: "r1" }), false); // before any snapshot
  assert.equal(g.accept({ type: "snapshot", seq: 2, run_id: "r1" }), true);
  assert.equal(g.accept({ type: "feed", seq: 3, run_id: "r1" }), true);
  assert.equal(g.accept({ type: "feed", seq: 3, run_id: "r1" }), false); // duplicate
  assert.equal(g.accept({ type: "feed", seq: 2, run_id: "r1" }), false); // out of order
  assert.equal(g.accept({ type: "answer", seq: 4, run_id: "r0" }), false); // older run
  assert.equal(g.accept({ type: "snapshot", seq: 5, run_id: "r2" }), true);
  assert.equal(g.accept({ type: "feed", seq: 6, run_id: "r1" }), false);
  assert.equal(g.accept({ type: "feed", seq: 7, run_id: "r2" }), true);
  assert.equal(g.accept({ type: "feed", run_id: "r2" }), false); // unnumbered
});

test("a new connection restarts numbering but keeps the run until its snapshot", () => {
  const g = new MessageGate();
  g.accept({ type: "snapshot", seq: 1, run_id: "r3" });
  g.accept({ type: "feed", seq: 40, run_id: "r3" });
  g.connectionOpened();
  assert.equal(g.accept({ type: "snapshot", seq: 1, run_id: "r4" }), true);
  assert.equal(g.accept({ type: "feed", seq: 2, run_id: "r4" }), true);
});

test("session url carries role and host token only when present", () => {
  const loc = { protocol: "https:", host: "vmi.example" };
  assert.equal(sessionUrl(loc, "my room", "tv", null), "wss://vmi.example/ws/my%20room?role=tv");
  assert.equal(sessionUrl({ protocol: "http:", host: "x" }, "r", "tv", "t0k"), "ws://x/ws/r?role=tv&host=t0k");
});

test("host token store survives blocked storage", () => {
  const store = hostTokenStore("r", { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } });
  assert.equal(store.get(), null);
  store.set("t"); // must not throw
});

class FakeSocket {
  static made = [];
  constructor(url) { this.url = url; this.readyState = 0; this.sent = []; FakeSocket.made.push(this); }
  send(t) { this.sent.push(JSON.parse(t)); }
  close() { this.readyState = 3; this.onclose?.(); }
}

test("session stores a new host token, filters messages and reconnects with backoff", () => {
  FakeSocket.made = [];
  const got = [], status = [], waits = [];
  let token = null;
  const s = openSession({
    room: "r", role: "tv", onMessage: (m) => got.push(m.type), onStatus: (x) => status.push(x),
    hostToken: { get: () => token, set: (t) => { token = t; } },
    WebSocketImpl: FakeSocket, schedule: (fn, ms) => { waits.push(ms); fn(); }, loc: { protocol: "http:", host: "h" },
  });
  const a = FakeSocket.made[0];
  assert.equal(s.send({ cmd: "play" }), false); // not open yet: nothing sent
  a.readyState = 1; a.onopen();
  a.onmessage({ data: JSON.stringify({ type: "snapshot", seq: 1, run_id: "r1", host_token: "abc" }) });
  a.onmessage({ data: JSON.stringify({ type: "frame", seq: 2, run_id: "r0" }) });
  assert.deepEqual(got, ["snapshot"]);
  assert.equal(token, "abc");
  a.onclose(); // dropped: retried with the stored token
  assert.deepEqual(status, ["connected", "disconnected"]);
  assert.deepEqual(waits, [500]);
  assert.equal(FakeSocket.made[1].url, "ws://h/ws/r?role=tv&host=abc");
  s.close();
  assert.equal(FakeSocket.made.length, 2); // closing on purpose doesn't reconnect
});
