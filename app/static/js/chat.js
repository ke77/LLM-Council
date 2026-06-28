const chat = document.getElementById("chat");
  const input = document.getElementById("idea-input");
  const sendBtn = document.getElementById("send-btn");

  let isRunning = false;

  // Auto-grow the textarea as the user types, capped by max-height in CSS.
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

  function addUserBubble(text) {
    const row = document.createElement("div");
    row.className = "bubble-row user";
    row.innerHTML = `<div class="bubble user"></div>`;
    row.querySelector(".bubble").textContent = text;
    chat.appendChild(row);
    chat.scrollTop = chat.scrollHeight;
  }

  function addBotStatusContainer() {
    const row = document.createElement("div");
    row.className = "bubble-row bot";
    row.innerHTML = `<div class="bubble bot" id="status-bubble"></div>`;
    chat.appendChild(row);
    chat.scrollTop = chat.scrollHeight;
    return row.querySelector("#status-bubble");
  }

  function setStatusLine(bubble, message) {
    bubble.innerHTML = `<div class="status-line"><span class="dot"></span>${escapeHtml(message)}</div>`;
    chat.scrollTop = chat.scrollHeight;
  }

  function showDownloadCard(bubble, htmlContent) {
    bubble.innerHTML = "";
    const card = document.createElement("div");
    card.className = "download-card";
    card.innerHTML = `
      <div class="label">
        <strong>Council report ready</strong>
        Your full report has been downloaded automatically.
      </div>
      <button class="download-btn">Download again</button>
    `;
    card.querySelector(".download-btn").addEventListener("click", () => downloadHtml(htmlContent));
    bubble.appendChild(card);
    chat.scrollTop = chat.scrollHeight;
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

  async function sendIdea() {
    if (isRunning) return;
    const idea = input.value.trim();
    if (!idea) return;

    isRunning = true;
    sendBtn.disabled = true;
    addUserBubble(idea);
    input.value = "";
    input.style.height = "auto";

    const statusBubble = addBotStatusContainer();
    setStatusLine(statusBubble, "Starting the council...");

    try {
      const response = await fetch("/council", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idea }),
      });

      // The server streams back one JSON object per line. We read
      // the response body as a stream and split it into lines as
      // they arrive, instead of waiting for the whole thing.
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

          if (data.type === "status") {
            setStatusLine(statusBubble, data.message);
          } else if (data.type === "done") {
            downloadHtml(data.html);
            showDownloadCard(statusBubble, data.html);
          } else if (data.type === "error") {
            setStatusLine(statusBubble, "⚠ " + data.message);
          }
        }
      }
    } catch (err) {
      setStatusLine(statusBubble, "⚠ Connection error: " + err.message);
    } finally {
      isRunning = false;
      sendBtn.disabled = false;
    }
  }