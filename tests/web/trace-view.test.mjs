import test from "node:test";
import assert from "node:assert/strict";
import { prependTrace, clearTrace } from "../../web/trace-view.mjs";

// A narrow DOM boundary fake: assigning HTML is forbidden. Browser QA separately
// verifies the real DOM; tests here guard text identity, order and the size bound.
class Element {
  constructor(tag, doc) { this.tag = tag; this.ownerDocument = doc; this.nodes = []; this.value = ""; }
  set innerHTML(value) { throw new Error("untrusted HTML sink"); }
  set textContent(value) { this.value = String(value); this.nodes = []; }
  get textContent() { return this.value + this.nodes.map(n => n.textContent).join(""); }
  get children() { return this.nodes.filter(n => n.tag !== "#text"); }
  get lastChild() { return this.nodes.at(-1); }
  append(...nodes) { for (const n of nodes) { n.parent = this; this.nodes.push(n); } }
  prepend(n) { n.parent = this; this.nodes.unshift(n); }
  remove() { this.parent.nodes.splice(this.parent.nodes.indexOf(this), 1); }
}
function list() {
  const doc = { createElement(tag) { return new Element(tag, doc); },
    createTextNode(value) { const n = new Element("#text", doc); n.textContent = value; return n; } };
  return doc.createElement("ol");
}

test("reset removes prior replay decisions and counts before replacement records arrive", () => {
  const target = list(), summary = list();
  prependTrace(target, [{clock:'18:22', decision:'banner', why:'old run'}]);
  summary.textContent = 'old counts';
  clearTrace(target, summary);
  assert.equal(target.children.length, 0);
  assert.equal(summary.textContent, 'Waiting for replay decisions');
  prependTrace(target, [{clock:'0:01', decision:'skip', why:'new run'}]);
  assert.equal(target.children.length, 1);
  assert.doesNotMatch(target.textContent, /old run/);
});

test("delivered clock, decision and reason stay literal text, including HTML payloads", () => {
  const target = list();
  const entry = { clock:'<img src=x>', decision:'<script>bad()</script>', why:'<svg onload=bad()> & "quoted"' };
  prependTrace(target, [entry]);
  assert.equal(target.children.length, 1);
  assert.equal(target.children[0].textContent, '<img src=x> <script>bad()</script>: <svg onload=bad()> & "quoted"');
  assert.deepEqual(target.children[0].children.map(n => n.tag), ["span"]);
});
test("new decisions prepend in delivery order and retain their readable emphasis", () => {
  const target = list();
  prependTrace(target, [{clock:'0:01', decision:'first', why:'one'}, {clock:'0:02', decision:'second', why:'two'}]);
  assert.deepEqual(target.children.map(n => n.textContent), ['0:02 second: two', '0:01 first: one']);
  assert.equal(target.children[0].children[0].textContent, 'second');
});
test("trace keeps only forty latest entries across batches", () => {
  const target = list();
  for (let start = 0; start < 100; start += 10) {
    prependTrace(target, Array.from({length:10}, (_, i) => ({clock:String(start+i), decision:'skip', why:'reason'})));
    assert.ok(target.children.length <= 40);
  }
  assert.equal(target.children.length, 40);
  assert.equal(target.children[0].textContent, '99 skip: reason');
  assert.equal(target.children.at(-1).textContent, '60 skip: reason');
});
