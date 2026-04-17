(() => {
  const root = document.querySelector("[data-chatbot-root]");
  if (!root) {
    return;
  }

  const toggle = root.querySelector("[data-chatbot-toggle]");
  const panel = root.querySelector("[data-chatbot-panel]");
  const close = root.querySelector("[data-chatbot-close]");
  const form = root.querySelector("[data-chatbot-form]");
  const messages = root.querySelector("[data-chatbot-messages]");

  const addMessage = (text, role) => {
    const item = document.createElement("article");
    item.className = `ik-chatbot-message ${role}`;
    item.textContent = text;
    messages.appendChild(item);
    messages.scrollTop = messages.scrollHeight;
  };

  const setOpen = (open) => {
    panel.hidden = !open;
  };

  root.hidden = false;

  toggle.addEventListener("click", () => {
    setOpen(panel.hidden);
  });

  close.addEventListener("click", () => {
    setOpen(false);
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const message = (formData.get("message") || "").toString().trim();
    if (!message) {
      return;
    }

    addMessage(message, "user");
    form.reset();

    try {
      const response = await fetch("/api/chatbot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      const payload = await response.json();
      addMessage(payload.reply || "Assistant could not answer right now.", "bot");
    } catch (_error) {
      addMessage("Network problem aavyo. Thodi vaar pachhi fari try karo.", "bot");
    }
  });
})();
