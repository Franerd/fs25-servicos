const $ = (s) => document.querySelector(s),
  money = (v) =>
    new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    })
      .format(v)
      .replace("US$", "$");
const state = {
  services: [],
  packages: [],
  category: "Todos",
  expanded: false,
  orders: JSON.parse(localStorage.getItem("fs25-orders") || "[]"),
};
const els = {
  services: $("#services"),
  packages: $("#packages"),
  filters: $("#filters"),
  search: $("#search"),
  type: $("#quote-type"),
  item: $("#quote-item"),
  quantity: $("#quantity"),
  quantityLabel: $("#quantity-label"),
  unit: $("#unit-suffix"),
  supply: $("#supply"),
  inputCost: $("#input-cost"),
  inputWrap: $("#input-cost-wrap"),
};
const escapeHtml = (s) =>
  String(s).replace(
    /[&<>'"]/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[
        c
      ],
  );
function toast(message) {
  const e = $("#toast");
  e.textContent = message;
  e.classList.add("show");
  setTimeout(() => e.classList.remove("show"), 2600);
}
async function load() {
  const root = location.pathname.includes("/web/") ? "../data/" : "data/";
  [state.services, state.packages] = await Promise.all([
    fetch(root + "services.json").then((r) => r.json()),
    fetch(root + "packages.json").then((r) => r.json()),
  ]);
  renderFilters();
  renderServices();
  renderPackages();
  populateQuote();
  calculate();
  renderOrders();
}
function renderFilters() {
  els.filters.innerHTML = "";
  ["Todos", ...new Set(state.services.map((s) => s.category))].forEach((c) => {
    const b = document.createElement("button");
    b.textContent = c;
    b.className = c === state.category ? "active" : "";
    b.onclick = () => {
      state.category = c;
      renderFilters();
      renderServices();
    };
    els.filters.append(b);
  });
}
function filtered() {
  const q = els.search.value.trim().toLocaleLowerCase("pt-BR");
  return state.services.filter(
    (s) =>
      (state.category === "Todos" || s.category === state.category) &&
      `${s.name} ${s.category} ${s.inputs.join(" ")}`
        .toLocaleLowerCase("pt-BR")
        .includes(q),
  );
}
function renderServices() {
  const all = filtered(),
    items =
      state.expanded || els.search.value || state.category !== "Todos"
        ? all
        : all.slice(0, 8);
  $("#result-count").textContent =
    `${all.length} ${all.length === 1 ? "serviço encontrado" : "serviços encontrados"}`;
  els.services.innerHTML =
    items
      .map(
        (s) =>
          `<article class="service-card"><div class="service-top"><span class="icon-box">${s.icon}</span><span class="category">${s.category}</span></div><h3>${escapeHtml(s.name)}</h3><span class="input-note">${s.inputs.length ? "Insumo separado: " + escapeHtml(s.inputs.join(", ")) : "Máquina, combustível e operador inclusos"}</span><div class="price">${money(s.price)} <small>/ ${s.unit}</small></div><button class="card-action" data-id="${s.id}" data-type="service">CALCULAR ESTE SERVIÇO →</button></article>`,
      )
      .join("") ||
    '<div class="empty"><span>🔎</span><h3>Nada por aqui</h3><p>Tente outro termo ou categoria.</p></div>';
  $("#show-more").hidden =
    all.length <= 8 || els.search.value || state.category !== "Todos";
  document
    .querySelectorAll('.card-action[data-type="service"]')
    .forEach((b) => (b.onclick = () => selectQuote("service", b.dataset.id)));
}
function renderPackages() {
  els.packages.innerHTML = state.packages
    .map(
      (p) =>
        `<article class="package-card"><span class="icon-box">${p.icon}</span><h3>${escapeHtml(p.name)}</h3><p>${escapeHtml(p.description)}</p><div class="price">${money(p.price)} <small>/ ha</small></div><button class="card-action" data-id="${p.id}" data-type="package">SIMULAR PACOTE →</button></article>`,
    )
    .join("");
  document
    .querySelectorAll('.card-action[data-type="package"]')
    .forEach((b) => (b.onclick = () => selectQuote("package", b.dataset.id)));
}
function currentList() {
  return els.type.value === "service" ? state.services : state.packages;
}
function populateQuote(selected) {
  els.item.innerHTML = currentList()
    .map(
      (i) =>
        `<option value="${i.id}">${i.icon} ${escapeHtml(i.name)} — ${money(i.price)}/${i.unit}</option>`,
    )
    .join("");
  if (selected) els.item.value = selected;
  syncUnit();
}
function syncUnit() {
  const i =
      currentList().find((x) => x.id === els.item.value) || currentList()[0],
    labels = {
      ha: "Área em hectares",
      hora: "Quantidade de horas",
      viagem: "Quantidade de viagens",
    };
  els.quantityLabel.textContent = labels[i?.unit] || "Quantidade";
  els.unit.textContent = i?.unit === "hora" ? "h" : i?.unit || "";
}
function selectQuote(type, id) {
  els.type.value = type;
  populateQuote(id);
  calculate();
  $("#orcamento").scrollIntoView({ behavior: "smooth" });
  toast("Serviço adicionado à calculadora");
}
function discountRate(q, u) {
  if (u !== "ha") return 0;
  if (q > 50) return 0.1;
  if (q > 25) return 0.08;
  if (q > 10) return 0.05;
  return 0;
}
function values() {
  const item =
      currentList().find((x) => x.id === els.item.value) || currentList()[0],
    quantity = Math.max(0, Number(els.quantity.value) || 0),
    raw = item.price * quantity,
    minimum = item.minimum || 0,
    base = Math.max(raw, minimum),
    rate = discountRate(quantity, item.unit),
    discount = base * rate,
    inputCost = els.supply.checked
      ? Math.max(0, Number(els.inputCost.value) || 0) * 1.1
      : 0;
  return {
    item,
    quantity,
    raw,
    minimum,
    base,
    rate,
    discount,
    inputCost,
    total: base - discount + inputCost,
  };
}
function calculate() {
  if (!currentList().length) return;
  syncUnit();
  const v = values();
  $("#quote-badge").textContent =
    els.type.value === "service" ? "SERVIÇO AVULSO" : "PACOTE AGRÍCOLA";
  $("#subtotal").textContent = money(v.base);
  $("#discount-label").textContent = `Desconto (${Math.round(v.rate * 100)}%)`;
  $("#discount").textContent = `− ${money(v.discount)}`;
  $("#total").textContent = money(v.total);
  $("#inputs-total").textContent = money(v.inputCost);
  $("#inputs-row").classList.toggle("hidden", !els.supply.checked);
  els.inputWrap.classList.toggle("hidden", !els.supply.checked);
  $("#minimum-note").textContent =
    v.minimum && v.raw < v.minimum
      ? `Mínimo de ${money(v.minimum)} aplicado`
      : "";
}
function quoteText(v) {
  const u =
    v.item.unit === "hora"
      ? "h"
      : v.item.unit === "viagem"
        ? "viagem(ns)"
        : "ha";
  return `🚜 ORÇAMENTO — FS25 SERVIÇOS\n\n${v.item.icon} Serviço: ${v.item.name}\n📐 Quantidade: ${v.quantity.toLocaleString("pt-BR")} ${u}\n💵 Preço-base: ${money(v.base)}\n🏷️ Desconto: ${Math.round(v.rate * 100)}% (−${money(v.discount)})${v.inputCost ? `\n📦 Insumos + taxa: ${money(v.inputCost)}` : ""}\n\n💰 TOTAL ESTIMADO: ${money(v.total)}\n\nValores sujeitos à confirmação da ordem de serviço.`;
}
async function copy(text, message) {
  try {
    await navigator.clipboard.writeText(text);
    toast(message);
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    document.body.append(area);
    area.select();
    document.execCommand("copy");
    area.remove();
    toast(message);
  }
}
function renderOrders() {
  const box = $("#orders");
  if (!state.orders.length) {
    box.innerHTML =
      '<div class="empty"><span>📋</span><h3>Nenhuma ordem criada</h3><p>Calcule um orçamento e transforme-o em pedido.</p></div>';
    return;
  }
  box.innerHTML = state.orders
    .map(
      (o) =>
        `<article class="order-card"><span class="order-id">#${String(o.id).padStart(4, "0")}</span><div><h3>${escapeHtml(o.itemName)}</h3><p>${escapeHtml(o.customer)} • ${escapeHtml(o.farm)} / ${escapeHtml(o.field)} • ${o.quantity} ${o.unit} • ${money(o.total)}</p></div><span class="status-pill">AGUARDANDO ENVIO</span><button class="text-button copy-order" data-id="${o.id}">Copiar OS</button></article>`,
    )
    .join("");
  document.querySelectorAll(".copy-order").forEach(
    (b) =>
      (b.onclick = () => {
        const o = state.orders.find((x) => x.id === Number(b.dataset.id));
        copy(orderText(o), "Ordem copiada para o Discord");
      }),
  );
}
function orderText(o) {
  return `🚜 ORDEM DE SERVIÇO #${String(o.id).padStart(4, "0")}\n\n👤 Cliente: ${o.customer}\n🏡 Fazenda: ${o.farm}\n🌾 Campo: ${o.field}${o.crop ? `\n🌱 Cultura: ${o.crop}` : ""}\n\n🔧 Serviço: ${o.itemName}\n📐 Quantidade: ${o.quantity} ${o.unit}\n💰 Valor: ${money(o.total)}${o.notes ? `\n\n📝 Observações: ${o.notes}` : ""}\n\n📅 Status: 🟡 Aguardando aprovação`;
}
els.search.addEventListener("input", renderServices);
$("#show-more").onclick = () => {
  state.expanded = true;
  renderServices();
};
els.type.onchange = () => {
  populateQuote();
  calculate();
};
[els.item, els.quantity, els.supply, els.inputCost].forEach((e) =>
  e.addEventListener(e.type === "number" ? "input" : "change", calculate),
);
$("#copy").onclick = () =>
  copy(quoteText(values()), "Orçamento copiado para o Discord");
$("#use-quote").onclick = () => {
  $("#solicitar").scrollIntoView({ behavior: "smooth" });
  $("#customer").focus();
};
$("#request-form").onsubmit = (e) => {
  e.preventDefault();
  const v = values(),
    next = Math.max(0, ...state.orders.map((o) => o.id)) + 1,
    o = {
      id: next,
      customer: $("#customer").value.trim(),
      farm: $("#farm").value.trim(),
      field: $("#field").value.trim(),
      crop: $("#crop").value.trim(),
      notes: $("#notes").value.trim(),
      itemName: v.item.name,
      quantity: v.quantity,
      unit: v.item.unit,
      total: v.total,
      createdAt: new Date().toISOString(),
    };
  state.orders.unshift(o);
  localStorage.setItem("fs25-orders", JSON.stringify(state.orders));
  renderOrders();
  e.target.reset();
  $("#request-status").textContent =
    `OS #${String(next).padStart(4, "0")} criada e salva.`;
  copy(orderText(o), "OS criada e copiada para o Discord");
  $("#pedidos").scrollIntoView({ behavior: "smooth" });
};
$("#clear-orders").onclick = () => {
  if (
    state.orders.length &&
    confirm("Limpar todas as ordens salvas neste dispositivo?")
  ) {
    state.orders = [];
    localStorage.removeItem("fs25-orders");
    renderOrders();
    toast("Histórico local limpo");
  }
};
$("#menu-toggle").onclick = () => {
  const n = $("#nav-links"),
    open = n.classList.toggle("open");
  $("#menu-toggle").setAttribute("aria-expanded", open);
};
document
  .querySelectorAll(".nav-links a")
  .forEach((a) => (a.onclick = () => $("#nav-links").classList.remove("open")));
document.querySelectorAll(".video-choice").forEach(
  (button) =>
    (button.onclick = () => {
      document
        .querySelectorAll(".video-choice")
        .forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      $("#fs25-video").src =
        `https://www.youtube-nocookie.com/embed/${button.dataset.video}?rel=0&autoplay=1`;
    }),
);
load().catch(() =>
  document.body.insertAdjacentHTML(
    "afterbegin",
    '<p style="margin:0;padding:12px;background:#fee2e2;text-align:center">Não foi possível carregar o catálogo. Abra pela prévia local ou pelo GitHub Pages.</p>',
  ),
);
