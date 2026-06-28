const chatScroll = document.getElementById("chat");
const chat = document.getElementById("chat-inner");
const input = document.getElementById("idea-input");
const sendBtn = document.getElementById("send-btn");
const rolesToggle = document.getElementById("roles-toggle");
const rolesDropdown = document.getElementById("roles-dropdown");
const rolesList = document.getElementById("roles-list");

let isRunning = false;
let availableRoles = [];
let hasEnteredChat = false;


function enterChatMode() {
  if (hasEnteredChat) return;
  hasEnteredChat = true;
  document.body.classList.remove("pre-chat");
  document.body.classList.add("in-chat");
  requestAnimationFrame(updateComposerHeight);
}

function updateComposerHeight() {
  const composer = document.getElementById("composer");
  const height = composer.getBoundingClientRect().height;
  document.documentElement.style.setProperty("--composer-height", `${height}px`);
}

function scrollChatToBottom() {
  chatScroll.scrollTop = chatScroll.scrollHeight;
}


// ROLE SELECTION
// On page load, ask the backend which roles exist (GET /roles) and
// render them as checkboxes. This is what lets the user pick
// "Domain Expert" + "Economist" instead of always getting
// "Security Engineer" on an idea that has nothing to do with software.
async function loadRoles() {
  try {
    const res = await fetch("/roles");
    const data = await res.json();
    availableRoles = data.roles;
    renderRoleCheckboxes();
  } catch (err) {
    rolesList.innerHTML = `<p class="roles-error">Couldn't load roles: ${err.message}</p>`;
  }
}

function renderRoleCheckboxes() {
  rolesList.innerHTML = availableRoles
    .map(
      (role) => `
      <label class="role-option">
        <input type="checkbox" value="${role.key}" ${role.default ? "checked" : ""}>
        <span class="role-name">${escapeHtml(role.name)}</span>
        <span class="role-desc">${escapeHtml(role.description)}</span>
      </label>`
    )
    .join("");
}

function getSelectedRoles() {
  return Array.from(rolesList.querySelectorAll("input[type=checkbox]:checked")).map(
    (el) => el.value
  );
}

rolesToggle.addEventListener("click", () => {
  rolesDropdown.classList.toggle("hidden");
});

// Close the dropdown if the user clicks anywhere outside it.
document.addEventListener("click", (e) => {
  if (!document.getElementById("roles-panel").contains(e.target)) {
    rolesDropdown.classList.add("hidden");
  }
});

loadRoles();


const composerObserver = new ResizeObserver(() => {
  if (hasEnteredChat) updateComposerHeight();
});
composerObserver.observe(document.getElementById("composer"));


// TEXTAREA BEHAVIOR
input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = input.scrollHeight + "px";
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendIdea();
  }
});

sendBtn.addEventListener("click", sendIdea);


// CHAT RENDERING
function addUserBubble(text) {
  const row = document.createElement("div");
  row.className = "bubble-row user";
  row.innerHTML = `<div class="bubble user"></div>`;
  row.querySelector(".bubble").textContent = text;
  chat.appendChild(row);
  scrollChatToBottom();
}

function addBotMessageContainer() {
  const row = document.createElement("div");
  row.className = "bubble-row bot";
  row.innerHTML = `<div class="bubble bot"></div>`;
  chat.appendChild(row);
  scrollChatToBottom();
  return row;
}

function setStatusLine(row, message) {
  const bubble = row.querySelector(".bubble");
  bubble.innerHTML = `<div class="status-line"><span class="dot"></span>${escapeHtml(message)}</div>`;
  scrollChatToBottom();
}

function printVerdictIntoBubble(row, verdictText) {
  const bubble = row.querySelector(".bubble");
  bubble.innerHTML = simpleMarkdownToHtml(verdictText);
  scrollChatToBottom();
}

function addStandaloneDownloadButton(afterRow, htmlContent) {
  const wrap = document.createElement("div");
  wrap.className = "download-standalone";
  wrap.innerHTML = `<button class="download-btn">⬇ Download full report (.html)</button>`;
  wrap.querySelector(".download-btn").addEventListener("click", () => downloadHtml(htmlContent));
  afterRow.insertAdjacentElement("afterend", wrap);
  scrollChatToBottom();
}

function downloadHtml(htmlContent) {
  const blob = new Blob([htmlContent], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "llm_council_report.html";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}


function simpleMarkdownToHtml(text) {
  const lines = text.replace(/\r\n/g, "\n").trim().split("\n");
  let html = "";
  let listBuffer = [];
  let listType = null;
  let tableBuffer = [];

  const inlineFormat = (line) =>
    escapeHtml(line)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, "<em>$1</em>");

  const flushList = () => {
    if (listBuffer.length) {
      html += `<${listType}>` + listBuffer.map((i) => `<li>${inlineFormat(i)}</li>`).join("") + `</${listType}>`;
      listBuffer = [];
      listType = null;
    }
  };

  const isTableRow = (line) => line.trim().startsWith("|") && line.trim().endsWith("|");
  const isTableSeparator = (line) =>
    isTableRow(line) &&
    line
      .trim()
      .slice(1, -1)
      .split("|")
      .every((cell) => /^:?-+:?$/.test(cell.trim()));

  const parseRow = (line) =>
    line.trim().slice(1, -1).split("|").map((c) => c.trim());

  const flushTable = () => {
    if (tableBuffer.length) {
      const header = parseRow(tableBuffer[0]);
      const bodyLines = isTableSeparator(tableBuffer[1]) ? tableBuffer.slice(2) : tableBuffer.slice(1);
      html += "<table><thead><tr>" + header.map((c) => `<th>${inlineFormat(c)}</th>`).join("") + "</tr></thead><tbody>";
      for (const rowLine of bodyLines) {
        if (!isTableRow(rowLine)) continue;
        const cells = parseRow(rowLine);
        html += "<tr>" + cells.map((c) => `<td>${inlineFormat(c)}</td>`).join("") + "</tr>";
      }
      html += "</tbody></table>";
      tableBuffer = [];
    }
  };

  let paragraphBuffer = [];
  const flushParagraph = () => {
    if (paragraphBuffer.length) {
      const joined = paragraphBuffer.join(" ").trim();
      if (joined) html += `<p>${inlineFormat(joined)}</p>`;
      paragraphBuffer = [];
    }
  };

  for (const raw of lines) {
    const line = raw.trim();

    if (!line) {
      flushParagraph();
      flushTable();
      continue;
    }

    if (isTableRow(line)) {
      flushParagraph();
      flushList();
      tableBuffer.push(line);
      continue;
    } else {
      flushTable();
    }

    if (/^[A-Z][A-Z \-]{2,40}:$/.test(line)) {
      flushParagraph();
      flushList();
      html += `<p class="label">${inlineFormat(line)}</p>`;
      continue;
    }

    const headingMatch = line.match(/^(#{1,6})\s+(.*)/);
    if (headingMatch) {
      flushParagraph();
      flushList();
      const level = Math.min(headingMatch[1].length + 2, 6);
      html += `<h${level}>${inlineFormat(headingMatch[2])}</h${level}>`;
      continue;
    }

    if (/^(-{3,}|\*{3,}|_{3,})$/.test(line)) {
      flushParagraph();
      flushList();
      html += "<hr>";
      continue;
    }

    const numbered = line.match(/^\d+[\.\)]\s+(.*)/);
    const bulleted = line.match(/^[\-\*]\s+(.*)/);

    if (numbered) {
      flushParagraph();
      if (listType !== "ol") { flushList(); listType = "ol"; }
      listBuffer.push(numbered[1]);
      continue;
    }

    if (bulleted) {
      flushParagraph();
      if (listType !== "ul") { flushList(); listType = "ul"; }
      listBuffer.push(bulleted[1]);
      continue;
    }

    flushList();
    paragraphBuffer.push(line);
  }

  flushParagraph();
  flushList();
  flushTable();

  return html;
}


// REJECTION TOAST
let toastTimeout = null;

function showRejectionToast(message) {
  const toast = document.getElementById("reject-toast");
  toast.textContent = message;
  toast.classList.add("visible");

  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => {
    toast.classList.remove("visible");
  }, 3500);
}


// MAIN SEND FLOW
async function sendIdea() {
  if (isRunning) return;
  const idea = input.value.trim();
  if (!idea) return;

  isRunning = true;
  sendBtn.disabled = true;

  const selectedRoles = getSelectedRoles();
  let botRow = null;
  let committed = false; // becomes true only once we know this idea was accepted

  try {
    const response = await fetch("/council", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idea, roles: selectedRoles }),
    });

    // The server streams back one JSON object per line. We read the
    // response body as a stream and split it into lines as they
    // arrive, instead of waiting for the whole thing.
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop(); // keep the last (possibly incomplete) line for next time

      for (const line of lines) {
        if (!line.trim()) continue;
        const data = JSON.parse(line);

        if (data.type === "rejected") {
          // Idea never gets committed to the chat at all 
          showRejectionToast(data.message);
          isRunning = false;
          sendBtn.disabled = false;
          return;
        }

        // First non-rejection message means the idea was accepted 
        if (!committed) {
          committed = true;
          enterChatMode();
          addUserBubble(idea);
          input.value = "";
          input.style.height = "auto";
          rolesDropdown.classList.add("hidden");
          botRow = addBotMessageContainer();
        }

        if (data.type === "status") {
          setStatusLine(botRow, data.message);
        } else if (data.type === "verdict") {
          printVerdictIntoBubble(botRow, data.text);
        } else if (data.type === "done") {
          addStandaloneDownloadButton(botRow, data.html);
        } else if (data.type === "error") {
          setStatusLine(botRow, "⚠ " + data.message);
        }
      }
    }
  } catch (err) {
    if (committed && botRow) {
      setStatusLine(botRow, "⚠ Connection error: " + err.message);
    } else {
      showRejectionToast("Connection error: " + err.message);
    }
  } finally {
    isRunning = false;
    sendBtn.disabled = false;
  }
}