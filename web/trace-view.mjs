// Presenter text comes from delivered records, including unknown future types.
export function prependTrace(list, entries) {
  for (const d of entries) {
    const doc = list.ownerDocument;
    const li = doc.createElement("li"), decision = doc.createElement("span");
    decision.textContent = d.decision;
    li.append(doc.createTextNode(`${d.clock} `), decision, doc.createTextNode(`: ${d.why}`));
    list.prepend(li);
  }
  while (list.children.length > 40) list.lastChild.remove();
}
