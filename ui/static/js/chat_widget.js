(function () {
  const history = [];
  let busy = false;
  let sessionId = "";

  function esc(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function mdToHtml(text) {
    if (window.marked && typeof window.marked.parse === "function") {
      return window.marked.parse(String(text || ""));
    }
    return esc(text || "").replace(/\n/g, "<br>");
  }

  function appendMessage(role, content) {
    const body = $("#floatingChatBody");
    const row = $("<div>").addClass("chat-row " + role);
    const bubble = $("<div>").addClass("chat-bubble");
    if (role === "bot") {
      bubble.html(mdToHtml(content));
    } else {
      bubble.text(content);
    }
    row.append(bubble);
    body.append(row);
    body.scrollTop(body.prop("scrollHeight"));
  }

  function setStatus(text) {
    $("#floatingChatStatus").text(text || "");
  }

  async function sendMessage() {
    if (busy) return;
    const input = $("#floatingChatInput");
    const message = (input.val() || "").trim();
    if (!message) return;
    input.val("");
    appendMessage("user", message);
    history.push({ role: "user", content: message });

    busy = true;
    setStatus("Thinking...");
    $("#floatingChatSend").prop("disabled", true);

    try {
      const res = await fetch("/chat/api/message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, history, session_id: sessionId }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        const err = data.error || ("HTTP " + res.status);
        appendMessage("bot", "Error: " + err);
        history.push({ role: "assistant", content: "Error: " + err });
      } else {
        if (data.session_id) {
          sessionId = String(data.session_id);
        }
        const reply = data.reply || "(empty)";
        appendMessage("bot", reply);
        history.push({ role: "assistant", content: reply });
      }
    } catch (e) {
      const err = "Request failed: " + (e.message || e);
      appendMessage("bot", err);
      history.push({ role: "assistant", content: err });
    } finally {
      busy = false;
      $("#floatingChatSend").prop("disabled", false);
      setStatus("");
      $("#floatingChatInput").focus();
    }
  }

  function togglePanel() {
    const panel = $("#floatingChatPanel");
    panel.toggleClass("open");
    if (panel.hasClass("open")) {
      $("#floatingChatInput").focus();
      if (history.length === 0) {
        const welcome =
          "Hi, I am NeuraGraph Assistant. I support pinned context and dry-run preview.\n\nTry:\n- /pin graph wf_cid_re_llm_linear\n- /pin dataset cid_dev_2samples.csv\n- /dryrun /create experiment\n- /create experiment";
        appendMessage("bot", welcome);
        history.push({ role: "assistant", content: welcome });
      }
    }
  }

  function insertCommand(cmd) {
    const input = $("#floatingChatInput");
    input.val(cmd);
    input.focus();
  }

  async function loadPalette() {
    const wrap = $("#floatingChatPalette");
    wrap.empty();
    try {
      const res = await fetch("/chat/api/command-catalog");
      const data = await res.json();
      if (!res.ok || !data.ok || !Array.isArray(data.items)) return;
      data.items.slice(0, 8).forEach((it) => {
        const chip = $("<span>")
          .addClass("chat-cmd-chip")
          .attr("title", it.desc || "")
          .text(it.cmd || "")
          .on("click", () => insertCommand(it.cmd || ""));
        wrap.append(chip);
      });
    } catch (_err) {
      // ignore palette loading errors
    }
  }

  function bindEvents() {
    $("#floatingChatFab").on("click", togglePanel);
    $("#floatingChatClose").on("click", togglePanel);
    $("#floatingChatSend").on("click", sendMessage);
    $("#floatingChatInput").on("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  }

  $(function () {
    bindEvents();
    loadPalette();
  });
})();
