let credentials = null;
let currentUser = null;
let currentSessionId = null;
let pendingActionId = null;
let pendingActionBusy = false;
let authMode = "login";
let menuItems = [];
const cart = new Map();
let noticeTimer;

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function showNotice(message, isError = false) {
  const notice = $("#notice");
  notice.textContent = message;
  notice.classList.toggle("error", isError);
  notice.classList.add("visible");
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => notice.classList.remove("visible"), 3300);
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (credentials) headers.set("Authorization", credentials);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...options, headers });
  if (response.status === 204) {
    return { removalMode: response.headers.get("X-Menu-Item-Removal") };
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.message || body.detail || `Request failed (${response.status})`);
  return body;
}

function money(value) {
  return `INR ${Number(value).toFixed(2)}`;
}

function setView(viewName) {
  $$(".view").forEach((view) => view.classList.remove("active-view"));
  $(`#${viewName}View`).classList.add("active-view");
  $$(".nav-button").forEach((button) => button.classList.toggle("active", button.dataset.view === viewName));
  if (viewName === "orders" && credentials) loadOrders();
  if (viewName === "assistant" && credentials && !currentSessionId) loadSessions();
}

function fillCategories(items) {
  const select = $("#categoryFilter");
  const current = select.value;
  const categories = [...new Set(items.map((item) => item.category))].sort();
  select.replaceChildren(new Option("All categories", ""));
  categories.forEach((category) => select.add(new Option(category, category)));
  if (categories.includes(current)) select.value = current;
}

async function loadMenu() {
  const params = new URLSearchParams();
  if ($("#keywordFilter").value.trim()) params.set("keyword", $("#keywordFilter").value.trim());
  if ($("#categoryFilter").value) params.set("category", $("#categoryFilter").value);
  if ($("#vegetarianFilter").checked) params.set("vegetarian", "true");
  if ($("#priceFilter").value) params.set("max_price", $("#priceFilter").value);
  try {
    menuItems = await api(`/api/menu_items?${params}`);
    fillCategories(menuItems);
    renderMenu();
  } catch (error) {
    showNotice(error.message, true);
  }
}

function renderMenu() {
  const grid = $("#menuGrid");
  grid.replaceChildren();
  $("#menuCount").textContent = `${menuItems.length} ${menuItems.length === 1 ? "dish" : "dishes"}`;
  $("#menuEmpty").classList.toggle("hidden", menuItems.length > 0);
  for (const item of menuItems) {
    const card = document.createElement("article");
    card.className = "menu-card";
    const image = document.createElement("img");
    image.className = "food-image";
    image.src = item.image_url || "https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=800&q=80";
    image.alt = item.title;
    image.loading = "lazy";
    image.onerror = () => { image.hidden = true; };
    const body = document.createElement("div");
    body.className = "menu-card-body";
    const top = document.createElement("div");
    top.className = "dish-top";
    const title = document.createElement("h3");
    title.className = "dish-title";
    title.textContent = item.title;
    top.append(title);
    if (item.vegetarian) {
      const marker = document.createElement("span");
      marker.className = "veg-mark";
      marker.setAttribute("role", "img");
      marker.setAttribute("aria-label", "Vegetarian");
      top.append(marker);
    }
    const description = document.createElement("p");
    description.className = "dish-description";
    description.textContent = item.description || item.declared_allergens;
    const meta = document.createElement("div");
    meta.className = "dish-meta";
    const price = document.createElement("strong");
    price.className = "dish-price";
    price.textContent = money(item.price);
    const stock = document.createElement("span");
    stock.className = "dish-stock";
    stock.textContent = item.capacity > 0 ? `${item.capacity} portions` : "Sold out";
    meta.append(price, stock);
    const actions = document.createElement("div");
    actions.className = "dish-actions";
    const add = document.createElement("button");
    add.className = "button button-accent";
    add.type = "button";
    add.disabled = item.capacity < 1;
    add.textContent = "Add to bag";
    add.addEventListener("click", () => addToCart(item));
    actions.append(add);
    if (currentUser?.role === "ADMIN") {
      const edit = document.createElement("button");
      edit.className = "button button-outline";
      edit.type = "button";
      edit.textContent = "Edit";
      edit.addEventListener("click", () => startEdit(item));
      actions.append(edit);
      const deleteItem = document.createElement("button");
      deleteItem.className = "button button-outline";
      deleteItem.type = "button";
      deleteItem.textContent = "Delete";
      deleteItem.addEventListener("click", async () => {
        if (!window.confirm(`Remove ${item.title} from the active menu? Its past order history will be kept.`)) return;
        try {
          const result = await api(`/api/menu_items/${item.id}`, { method: "DELETE" });
          showNotice(result?.removalMode === "archived"
            ? "Dish archived to preserve past order history."
            : "Dish permanently deleted.");
          await loadMenu();
        } catch (error) { showNotice(error.message, true); }
      });
      actions.append(deleteItem);
    }
    body.append(top, description, meta, actions);
    card.append(image, body);
    grid.append(card);
  }
  $("#adminPanel").classList.toggle("hidden", currentUser?.role !== "ADMIN");
}

function addToCart(item) {
  const current = cart.get(item.id) || { item, quantity: 0 };
  if (current.quantity >= Math.min(10, item.capacity)) return showNotice("Maximum available quantity reached.", true);
  current.quantity += 1;
  cart.set(item.id, current);
  renderCart();
}

function renderCart() {
  const lines = $("#cartLines");
  lines.replaceChildren();
  let count = 0;
  let total = 0;
  for (const [id, entry] of cart) {
    count += entry.quantity;
    total += Number(entry.item.price) * entry.quantity;
    const line = document.createElement("div");
    line.className = "cart-line";
    const name = document.createElement("span");
    name.className = "cart-line-name";
    name.textContent = entry.item.title;
    const price = document.createElement("strong");
    price.className = "cart-line-price";
    price.textContent = money(Number(entry.item.price) * entry.quantity);
    const controls = document.createElement("div");
    controls.className = "cart-line-controls";
    const less = document.createElement("button");
    less.className = "small-action";
    less.textContent = "−";
    less.setAttribute("aria-label", `Remove one ${entry.item.title}`);
    less.addEventListener("click", () => changeCart(id, -1));
    const quantity = document.createElement("span");
    quantity.textContent = `Qty ${entry.quantity}`;
    const more = document.createElement("button");
    more.className = "small-action";
    more.textContent = "+";
    more.setAttribute("aria-label", `Add one ${entry.item.title}`);
    more.addEventListener("click", () => addToCart(entry.item));
    controls.append(less, quantity, more);
    line.append(name, price, controls);
    lines.append(line);
  }
  if (!cart.size) {
    const empty = document.createElement("p");
    empty.className = "muted-copy";
    empty.textContent = "Add something delicious to get started.";
    lines.append(empty);
  }
  $("#cartCount").textContent = String(count);
  $("#cartTotal").textContent = money(total);
  $("#checkoutButton").disabled = cart.size === 0;
}

function changeCart(id, delta) {
  const entry = cart.get(id);
  if (!entry) return;
  entry.quantity += delta;
  if (entry.quantity <= 0) cart.delete(id);
  renderCart();
}

async function checkout() {
  if (!credentials) return $("#loginDialog").showModal();
  const lines = [...cart.values()].map(({ item, quantity }) => ({ item_id: item.id, quantity }));
  try {
    const order = await api("/api/orders", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ lines }),
    });
    cart.clear();
    renderCart();
    showNotice(`Order #${order.id} confirmed.`);
    await loadMenu();
    await loadOrders();
    setView("orders");
  } catch (error) {
    showNotice(error.message, true);
    await loadMenu();
  }
}

async function loadOrders() {
  const list = $("#ordersList");
  if (!credentials) {
    list.textContent = "Sign in to see your orders.";
    return;
  }
  try {
    const orders = await api("/api/orders");
    list.replaceChildren();
    if (!orders.length) {
      list.textContent = "No orders yet. Browse the menu to get started.";
      return;
    }
    for (const order of orders) {
      const card = document.createElement("article");
      card.className = "order-card";
      const head = document.createElement("div");
      head.className = "order-head";
      const id = document.createElement("strong");
      id.className = "order-id";
      id.textContent = `Order #${order.id}`;
      const status = document.createElement("span");
      status.className = "status-pill";
      status.textContent = order.status;
      head.append(id, status);
      const detail = document.createElement("p");
      detail.className = "order-lines";
      detail.textContent = order.lines.map((line) => `${line.quantity} × ${line.title_snapshot}`).join(" · ");
      const bottom = document.createElement("div");
      bottom.className = "order-bottom";
      const date = document.createElement("span");
      date.textContent = new Date(order.created_at).toLocaleString();
      const total = document.createElement("strong");
      total.textContent = money(order.total);
      bottom.append(date, total);
      card.append(head, detail, bottom);
      if (order.status === "CONFIRMED") {
        const cancel = document.createElement("button");
        cancel.className = "button button-outline";
        cancel.type = "button";
        cancel.textContent = "Cancel order";
        cancel.addEventListener("click", async () => {
          if (!window.confirm(`Cancel order #${order.id}?`)) return;
          try {
            await api(`/api/orders/${order.id}/cancel`, { method: "POST" });
            showNotice(`Order #${order.id} cancelled.`);
            await loadOrders();
            await loadMenu();
          } catch (error) { showNotice(error.message, true); }
        });
        card.append(cancel);
      }
      list.append(card);
    }
  } catch (error) { showNotice(error.message, true); }
}

function startEdit(item) {
  $("#editItemId").value = item.id;
  $("#itemTitle").value = item.title;
  $("#itemCategory").value = item.category;
  $("#itemPrice").value = item.price;
  $("#itemCapacity").value = item.capacity;
  $("#itemDescription").value = item.description;
  $("#itemAllergens").value = item.declared_allergens;
  $("#itemImageUrl").value = item.image_url;
  $("#itemVegetarian").checked = item.vegetarian;
  $("#adminPanel").scrollIntoView({ behavior: "smooth", block: "center" });
}

function clearMenuForm() {
  $("#menuForm").reset();
  $("#editItemId").value = "";
}

function clearMenuFilters() {
  $("#keywordFilter").value = "";
  $("#categoryFilter").value = "";
  $("#vegetarianFilter").checked = false;
  $("#priceFilter").value = "";
}

async function saveMenuItem(event) {
  event.preventDefault();
  const id = $("#editItemId").value;
  const body = {
    title: $("#itemTitle").value.trim(),
    category: $("#itemCategory").value.trim(),
    price: Number($("#itemPrice").value).toFixed(2),
    capacity: Number($("#itemCapacity").value),
    description: $("#itemDescription").value.trim(),
    vegetarian: $("#itemVegetarian").checked,
    declared_allergens: $("#itemAllergens").value.trim() || "Not specified",
    image_url: $("#itemImageUrl").value.trim(),
  };
  try {
    await api(id ? `/api/menu_items/${id}` : "/api/menu_items", { method: id ? "PUT" : "POST", body: JSON.stringify(body) });
    clearMenuForm();
    clearMenuFilters();
    showNotice(id ? "Menu item updated." : "Menu item added.");
    await loadMenu();
  } catch (error) { showNotice(error.message, true); }
}

async function login(event) {
  event.preventDefault();
  const username = $("#usernameInput").value.trim();
  const password = $("#passwordInput").value;
  credentials = `Basic ${btoa(`${username}:${password}`)}`;
  try {
    if (authMode === "signup") {
      await api("/api/auth/signup", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
    }
    currentUser = await api("/api/auth/me");
    $("#loginDialog").close();
    $("#loginForm").reset();
    $("#loginError").textContent = "";
    const signedUp = authMode === "signup";
    setAuthMode("login");
    updateAccount();
    await loadMenu();
    await loadOrders();
    await loadSessions();
    if (currentUser.role === "ADMIN") await loadDocuments();
    showNotice(signedUp ? `Account created. Welcome, ${currentUser.username}.` : `Signed in as ${currentUser.username}.`);
  } catch (error) {
    credentials = null;
    currentUser = null;
    $("#loginError").textContent = error.message;
  }
}

function setAuthMode(mode) {
  authMode = mode;
  const isSignup = mode === "signup";
  $("#authEyebrow").textContent = isSignup ? "Join Bowl & Bloom" : "Welcome back";
  $("#authTitle").textContent = isSignup ? "Create your account" : "Sign in to continue";
  $("#authHelp").textContent = isSignup
    ? "Create an account to place orders and save your conversations."
    : "Your credentials stay in memory only and are cleared when you sign out or close this page.";
  $("#authSubmit").textContent = isSignup ? "Create account" : "Sign in";
  $("#authModeToggle").textContent = isSignup ? "Already have an account? Sign in" : "New here? Create an account";
  $("#passwordInput").minLength = isSignup ? 12 : 0;
  $("#passwordInput").autocomplete = isSignup ? "new-password" : "current-password";
  $("#passwordHint").textContent = isSignup ? "Use at least 12 characters." : "";
  $("#loginError").textContent = "";
}

function updateAccount() {
  $("#accountLabel").textContent = currentUser ? `${currentUser.username} · ${currentUser.role.toLowerCase()}` : "Browsing as guest";
  $("#loginOpen").classList.toggle("hidden", Boolean(currentUser));
  $("#logoutButton").classList.toggle("hidden", !currentUser);
  renderMenu();
}

function logout() {
  credentials = null;
  currentUser = null;
  currentSessionId = null;
  pendingActionId = null;
  cart.clear();
  renderCart();
  updateAccount();
  $("#sessionList").textContent = "Sign in to save conversations.";
  $("#ordersList").textContent = "Sign in to see your orders.";
  $("#chatMessages").replaceChildren();
  $("#chatMessages").textContent = "Sign in to start a saved conversation.";
  showNotice("Signed out. Credentials cleared from memory.");
}

async function loadSessions() {
  if (!credentials) return;
  try {
    const sessions = await api("/api/chat/sessions");
    const list = $("#sessionList");
    list.replaceChildren();
    if (!sessions.length) {
      list.textContent = "No saved chats yet.";
      return;
    }
    sessions.forEach((session) => {
      const button = document.createElement("button");
      button.className = `session-item${session.id === currentSessionId ? " active" : ""}`;
      button.type = "button";
      button.dataset.sessionId = String(session.id);
      button.textContent = session.title;
      button.addEventListener("click", () => openSession(session.id));
      list.append(button);
    });
    if (!currentSessionId) await openSession(sessions[0].id);
  } catch (error) { showNotice(error.message, true); }
}

async function loadDocuments() {
  if (currentUser?.role !== "ADMIN") return;
  try {
    const documents = await api("/api/documents");
    const list = $("#documentList");
    list.replaceChildren();
    if (!documents.length) {
      list.textContent = "No active documents. Upload a policy file to enable grounded answers.";
      return;
    }
    documents.forEach((entry) => {
      const row = document.createElement("div");
      row.className = "document-row";
      const name = document.createElement("span");
      name.textContent = `${entry.filename} · v${entry.version}`;
      const status = document.createElement("span");
      status.className = "document-status";
      status.textContent = entry.status;
      const reindex = document.createElement("button");
      reindex.className = "small-action";
      reindex.type = "button";
      reindex.textContent = "Re-index";
      reindex.addEventListener("click", async () => {
        try {
          await api(`/api/documents/${entry.id}/reindex`, { method: "POST" });
          showNotice(`${entry.filename} re-indexed.`);
          await loadDocuments();
        } catch (error) { showNotice(error.message, true); }
      });
      row.append(name, status, reindex);
      list.append(row);
    });
  } catch (error) { showNotice(error.message, true); }
}

async function uploadDocument(event) {
  event.preventDefault();
  if (currentUser?.role !== "ADMIN") return showNotice("Admin access required.", true);
  const file = $("#documentFile").files[0];
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  try {
    await api("/api/documents", { method: "POST", body: form });
    $("#documentForm").reset();
    showNotice("Document indexed and available for policy answers.");
    await loadDocuments();
  } catch (error) { showNotice(error.message, true); }
}

async function newSession() {
  if (!credentials) return $("#loginDialog").showModal();
  try {
    const session = await api("/api/chat/sessions", { method: "POST", body: JSON.stringify({ title: "New conversation" }) });
    currentSessionId = session.id;
    pendingActionId = null;
    renderPendingAction(null);
    $("#chatMessages").replaceChildren();
    await loadSessions();
  } catch (error) { showNotice(error.message, true); }
}

async function openSession(id) {
  currentSessionId = id;
  pendingActionId = null;
  renderPendingAction(null);
  try {
    const [messages, actions] = await Promise.all([
      api(`/api/chat/sessions/${id}/messages`),
      api(`/api/chat/sessions/${id}/actions`),
    ]);
    const container = $("#chatMessages");
    container.replaceChildren();
    messages.forEach((message) => appendMessage(message.role, message.content, message.metadata_json?.citations || []));
    container.scrollTop = container.scrollHeight;
    $$(".session-item").forEach((button) => button.classList.toggle("active", Number(button.dataset.sessionId) === id));
    renderPendingAction(actions[0] || null);
  } catch (error) { showNotice(error.message, true); }
}

function appendMessage(role, text, citations = []) {
  const container = $("#chatMessages");
  const bubble = document.createElement("div");
  bubble.className = `message ${role === "user" ? "user-message" : "assistant-message"}`;
  const content = document.createElement("p");
  content.textContent = text;
  bubble.append(content);
  if (role === "assistant" && citations.length) {
    const chips = document.createElement("div");
    chips.className = "citation-list";
    citations.forEach((citation) => {
      const chip = document.createElement("span");
      chip.className = "citation-chip";
      chip.textContent = `${citation.filename}${citation.page ? ` · p. ${citation.page}` : ""}`;
      chips.append(chip);
    });
    bubble.append(chips);
  }
  container.append(bubble);
  container.scrollTop = container.scrollHeight;
}

function renderPendingAction(action) {
  const panel = $("#pendingAction");
  panel.replaceChildren();
  pendingActionBusy = false;
  pendingActionId = action?.id || null;
  panel.classList.toggle("hidden", !action);
  if (!action) return;
  const summary = document.createElement("p");
  summary.textContent = action.summary;
  const controls = document.createElement("div");
  controls.className = "pending-actions-row";
  const confirm = document.createElement("button");
  confirm.className = "button button-accent";
  confirm.type = "button";
  confirm.textContent = action.status === "PROCESSING" ? "Retry confirmation" : "Confirm action";
  confirm.addEventListener("click", () => decideAction(true));
  const reject = document.createElement("button");
  reject.className = "button button-outline";
  reject.type = "button";
  reject.textContent = "Reject";
  reject.hidden = action.status === "PROCESSING";
  reject.addEventListener("click", () => decideAction(false));
  controls.append(confirm, reject);
  panel.append(summary, controls);
}

async function decideAction(confirm) {
  if (!pendingActionId || pendingActionBusy) return;
  pendingActionBusy = true;
  const controls = [...$("#pendingAction").querySelectorAll("button")];
  const confirmButton = controls[0];
  const rejectButton = controls[1];
  controls.forEach((button) => { button.disabled = true; });
  confirmButton.textContent = confirm ? "Confirming..." : "Rejecting...";
  try {
    const result = await api(`/api/chat/actions/${pendingActionId}/confirm`, {
      method: "POST",
      body: JSON.stringify({ confirm }),
    });
    const orderId = result.result?.id;
    showNotice(confirm ? (orderId ? `Action complete. Order #${orderId}.` : "Action complete.") : "Action rejected; no order changed.");
    appendMessage("assistant", confirm ? "The confirmed action was completed through the order API." : "Understood. No order was changed.");
    renderPendingAction(null);
    await loadOrders();
    await loadMenu();
  } catch (error) {
    showNotice(error.message, true);
    confirmButton.disabled = false;
    rejectButton.disabled = false;
    confirmButton.textContent = "Retry confirmation";
    rejectButton.hidden = true;
  } finally {
    pendingActionBusy = false;
  }
}

async function sendChat(event) {
  event.preventDefault();
  if (!credentials) return $("#loginDialog").showModal();
  if (!currentSessionId) await newSession();
  if (!currentSessionId) return;
  const input = $("#chatInput");
  const message = input.value.trim();
  if (!message) return;
  input.value = "";
  appendMessage("user", message);
  $("#sendChat").disabled = true;
  try {
    const result = await api(`/api/chat/sessions/${currentSessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({ message }),
    });
    appendMessage("assistant", result.assistant_message.content, result.citations);
    renderPendingAction(result.pending_action);
    await loadSessions();
  } catch (error) {
    appendMessage("assistant", "I couldn't complete that request. Your message is saved; please try again.");
    showNotice(error.message, true);
  } finally { $("#sendChat").disabled = false; }
}

function bindEvents() {
  $$("[data-view]").forEach((button) => button.addEventListener("click", () => setView(button.dataset.view)));
  $("#loginOpen").addEventListener("click", () => $("#loginDialog").showModal());
  $("#loginClose").addEventListener("click", () => $("#loginDialog").close());
  $("#authModeToggle").addEventListener("click", () => setAuthMode(authMode === "login" ? "signup" : "login"));
  $("#loginForm").addEventListener("submit", login);
  $("#logoutButton").addEventListener("click", logout);
  $("#checkoutButton").addEventListener("click", checkout);
  $("#refreshOrders").addEventListener("click", loadOrders);
  $("#menuForm").addEventListener("submit", saveMenuItem);
  $("#cancelEdit").addEventListener("click", clearMenuForm);
  $("#documentForm").addEventListener("submit", uploadDocument);
  $("#newChat").addEventListener("click", newSession);
  $("#chatForm").addEventListener("submit", sendChat);
  ["#keywordFilter", "#categoryFilter", "#vegetarianFilter", "#priceFilter"].forEach((selector) => {
    $(selector).addEventListener(selector === "#keywordFilter" ? "input" : "change", loadMenu);
  });
  $("#clearFilters").addEventListener("click", () => {
    clearMenuFilters();
    loadMenu();
  });
}

bindEvents();
renderCart();
loadMenu();