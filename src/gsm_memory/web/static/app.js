/**
 * GSM Memory AI Assistant - Web Client Application Logic
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const chatMessages = document.getElementById("chat-messages");
  const chatInputForm = document.getElementById("chat-input-form");
  const queryInput = document.getElementById("query-input");
  const btnSend = document.getElementById("btn-send");
  const charCounter = document.getElementById("char-counter");
  const driverSelect = document.getElementById("driver-select");
  const timeSelect = document.getElementById("time-select");
  const btnClearChat = document.getElementById("btn-clear-chat");
  const scenariosChips = document.getElementById("scenarios-chips");
  const btnToggleInspector = document.getElementById("btn-toggle-inspector");
  const inspectorSection = document.getElementById("inspector-section");

  // Status Elements
  const statusNeo4j = document.getElementById("status-neo4j");
  const statusLangfuse = document.getElementById("status-langfuse");
  const statusBm25 = document.getElementById("status-bm25");
  const bm25Label = document.getElementById("bm25-label");
  const modelNameLabel = document.getElementById("model-name-label");

  // Inspector Elements
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");
  const citationsCount = document.getElementById("citations-count");
  const citationsSummary = document.getElementById("citations-summary");
  const citationsList = document.getElementById("citations-list");
  const graphCount = document.getElementById("graph-count");
  const graphStatNodes = document.getElementById("graph-stat-nodes");
  const graphStatEdges = document.getElementById("graph-stat-edges");
  const graphCanvasContainer = document.getElementById("graph-canvas-container");
  const graphEmptyState = document.getElementById("graph-empty-state");
  const subgraphSvg = document.getElementById("subgraph-svg");
  const svgNodesGroup = document.getElementById("svg-nodes-group");
  const svgEdgesGroup = document.getElementById("svg-edges-group");
  const nodeDetailsCard = document.getElementById("node-details-card");
  const nodeDetailLabel = document.getElementById("node-detail-label");
  const nodeDetailName = document.getElementById("node-detail-name");
  const nodeDetailProps = document.getElementById("node-detail-props");
  const btnCloseNode = document.getElementById("btn-close-node");
  const traceExternalLink = document.getElementById("trace-external-link");
  const metricLatency = document.getElementById("metric-latency");
  const metricStatus = document.getElementById("metric-status");
  const metricModel = document.getElementById("metric-model");

  let isSubmitting = false;

  // =========================================================================
  // 1. App Initialization & Health Check
  // =========================================================================
  async function initApp() {
    loadHealth();
    loadDrivers();
    loadScenarios();
    setupEventListeners();
  }

  async function loadHealth() {
    try {
      const res = await fetch("/api/health");
      if (!res.ok) throw new Error("Health fetch error");
      const data = await res.json();

      // Neo4j dot
      const nDot = statusNeo4j.querySelector(".status-dot");
      nDot.className = data.neo4j_connected ? "status-dot dot-active" : "status-dot dot-inactive";
      statusNeo4j.title = data.neo4j_connected ? "Neo4j KG Đang Kết Nối Trực Tiếp" : "Neo4j KG Chưa Kết Nối (Dùng Local Graph)";

      // Langfuse dot
      const lDot = statusLangfuse.querySelector(".status-dot");
      lDot.className = data.langfuse_connected ? "status-dot dot-active" : "status-dot dot-inactive";
      statusLangfuse.title = data.langfuse_connected ? "Langfuse Tracing Đang Kích Hoạt" : "Langfuse Tracing Tắt";

      // BM25
      const bDot = statusBm25.querySelector(".status-dot");
      bDot.className = "status-dot dot-active";
      bm25Label.textContent = `BM25 (${data.bm25_chunks_count} chunks)`;

      // Model label
      if (data.model) {
        const shortModel = data.model.split("/").pop().replace(":free", "");
        modelNameLabel.textContent = shortModel;
        metricModel.textContent = shortModel;
      }
    } catch (err) {
      console.warn("Could not check health:", err);
    }
  }

  async function loadDrivers() {
    try {
      const res = await fetch("/api/drivers");
      if (!res.ok) return;
      const drivers = await res.json();
      drivers.forEach(d => {
        const opt = document.createElement("option");
        opt.value = d.id;
        opt.textContent = `${d.code} - ${d.name}`;
        driverSelect.appendChild(opt);
      });
    } catch (e) {
      console.error("Error loading drivers:", e);
    }
  }

  async function loadScenarios() {
    try {
      const res = await fetch("/api/scenarios");
      if (!res.ok) return;
      const scenarios = await res.json();
      scenariosChips.innerHTML = "";

      scenarios.forEach(sc => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "scenario-chip";
        chip.innerHTML = `
          <span class="chip-tag ${sc.tag_color}">${sc.tag}</span>
          <span>${sc.title}</span>
        `;
        chip.title = sc.desc;
        chip.addEventListener("click", () => {
          queryInput.value = sc.query;
          autoResizeTextarea();
          if (sc.id === "scenario_2") {
            const opt = Array.from(driverSelect.options).find(o => o.text.includes("DRV-002"));
            if (opt) driverSelect.value = opt.value;
          } else if (sc.id === "scenario_3") {
            const opt = Array.from(driverSelect.options).find(o => o.text.includes("DRV-004"));
            if (opt) driverSelect.value = opt.value;
          }
          submitQuery();
        });
        scenariosChips.appendChild(chip);
      });
    } catch (e) {
      console.error("Error loading scenarios:", e);
    }
  }

  // =========================================================================
  // 2. Event Listeners & UI Controls
  // =========================================================================
  function setupEventListeners() {
    // Textarea input auto-resize & counter
    queryInput.addEventListener("input", () => {
      autoResizeTextarea();
      charCounter.textContent = `${queryInput.value.length} ký tự`;
    });

    // Enter to submit (Shift+Enter for newline)
    queryInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        submitQuery();
      }
    });

    // Form submit
    chatInputForm.addEventListener("submit", (e) => {
      e.preventDefault();
      submitQuery();
    });

    // Clear chat
    btnClearChat.addEventListener("click", () => {
      if (confirm("Bạn có chắc chắn muốn làm mới toàn bộ cuộc trò chuyện?")) {
        chatMessages.innerHTML = `
          <div class="welcome-card" id="welcome-card">
            <div class="welcome-icon-glow">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>
              </svg>
            </div>
            <h2>Cuộc Trò Chuyện Đã Được Làm Mới 🚀</h2>
            <p>Hệ thống sẵn sàng nhận câu hỏi mới về quy chế hoặc dữ liệu vận hành tài xế.</p>
          </div>
        `;
        resetInspector();
      }
    });

    // Toggle right inspector panel
    btnToggleInspector.addEventListener("click", () => {
      inspectorSection.classList.toggle("collapsed");
    });

    // Inspector Tabs Switch
    tabBtns.forEach(btn => {
      btn.addEventListener("click", () => {
        tabBtns.forEach(b => b.classList.remove("active"));
        tabPanes.forEach(p => p.classList.remove("active"));
        btn.classList.add("active");
        const targetId = btn.getAttribute("data-tab");
        const targetPane = document.getElementById(targetId);
        if (targetPane) targetPane.classList.add("active");
      });
    });

    // Close Node Details Card
    if (btnCloseNode) {
      btnCloseNode.addEventListener("click", () => {
        nodeDetailsCard.style.display = "none";
      });
    }
  }

  function autoResizeTextarea() {
    queryInput.style.height = "auto";
    queryInput.style.height = `${Math.min(queryInput.scrollHeight, 120)}px`;
  }

  // =========================================================================
  // 3. Chat Submission & Message Rendering
  // =========================================================================
  async function submitQuery() {
    const text = queryInput.value.trim();
    if (!text || isSubmitting) return;

    // Remove welcome card if present
    const welcomeCard = document.getElementById("welcome-card");
    if (welcomeCard) welcomeCard.remove();

    // Append User Message
    appendMessage("user", text);
    queryInput.value = "";
    autoResizeTextarea();
    charCounter.textContent = "0 ký tự";

    // Set Loading State
    setSubmitting(true);
    const typingRow = appendTypingIndicator();

    // Prepare payload
    const payload = {
      query: text,
      driver_id: driverSelect.value || null,
      time_mention: timeSelect.value || null,
    };

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      typingRow.remove();

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const data = await response.json();
      appendBotResponse(data);
      updateInspector(data);
    } catch (err) {
      typingRow.remove();
      appendMessage("bot", `⚠️ Đã xảy ra lỗi khi kết nối với máy chủ: ${err.message}. Vui lòng thử lại sau.`);
    } finally {
      setSubmitting(false);
    }
  }

  function setSubmitting(loading) {
    isSubmitting = loading;
    btnSend.disabled = loading;
    if (loading) {
      btnSend.classList.add("loading");
    } else {
      btnSend.classList.remove("loading");
    }
  }

  function appendMessage(role, content) {
    const row = document.createElement("div");
    row.className = `message-row ${role}-row`;

    const avatar = document.createElement("div");
    avatar.className = `avatar-badge ${role}-avatar`;
    avatar.innerHTML = role === "user" ? "Bác Tài" : "GSM";

    const bubbleContainer = document.createElement("div");
    bubbleContainer.className = "bubble-container";

    const bubble = document.createElement("div");
    bubble.className = `message-bubble ${role}-bubble`;
    bubble.innerHTML = formatMarkdown(content);

    bubbleContainer.appendChild(bubble);
    row.appendChild(avatar);
    row.appendChild(bubbleContainer);

    chatMessages.appendChild(row);
    scrollToBottom();
    return row;
  }

  function appendTypingIndicator() {
    const row = document.createElement("div");
    row.className = "message-row bot-row typing-row";

    const avatar = document.createElement("div");
    avatar.className = "avatar-badge bot-avatar";
    avatar.innerHTML = "GSM";

    const bubbleContainer = document.createElement("div");
    bubbleContainer.className = "bubble-container";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble bot-bubble";
    bubble.innerHTML = `
      <div style="display: flex; align-items: center; gap: 0.5rem; color: var(--text-dim); font-size: 0.85rem;">
        <span class="status-dot dot-loading"></span>
        <span>AI Chuyên viên GSM đang tra cứu quy chế & mở rộng đồ thị tri thức...</span>
      </div>
    `;

    bubbleContainer.appendChild(bubble);
    row.appendChild(avatar);
    row.appendChild(bubbleContainer);

    chatMessages.appendChild(row);
    scrollToBottom();
    return row;
  }

  function appendBotResponse(data) {
    const row = document.createElement("div");
    row.className = "message-row bot-row";

    const avatar = document.createElement("div");
    avatar.className = "avatar-badge bot-avatar";
    avatar.innerHTML = "GSM";

    const bubbleContainer = document.createElement("div");
    bubbleContainer.className = "bubble-container";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble bot-bubble";

    // Meta Header (Status Badge + Latency)
    let badgeClass = "badge-answered";
    let badgeText = "Đã Xác Thực Quy Chế";

    if (data.status === "NEEDS_CLARIFICATION") {
      badgeClass = "badge-clarification";
      badgeText = "Cần Làm Rõ Thông Tin";
    } else if (data.status === "ERROR") {
      badgeClass = "badge-error";
      badgeText = "Lỗi Xử Lý";
    }

    const header = document.createElement("div");
    header.className = "bubble-meta-header";
    header.innerHTML = `
      <span class="status-badge ${badgeClass}">${badgeText}</span>
      <span class="time-latency-tag">${data.latency_ms || 0} ms</span>
    `;
    bubble.appendChild(header);

    // Body Content
    const body = document.createElement("div");
    body.className = "bubble-content";

    if (data.status === "NEEDS_CLARIFICATION") {
      body.innerHTML = formatMarkdown(data.clarification_message || "Vui lòng cung cấp thêm thông tin.");

      // Quick Pick Actions for Missing Slots
      const clarificationBox = document.createElement("div");
      clarificationBox.className = "clarification-box";
      clarificationBox.innerHTML = `
        <div class="clarification-title">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px;">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          Gợi ý bổ sung nhanh:
        </div>
      `;

      const actionsWrap = document.createElement("div");
      actionsWrap.className = "clarification-quick-actions";

      // If missing driver
      if (data.missing_slots && data.missing_slots.includes("driver_id")) {
        const driversList = [
          { code: "DRV-002", name: "Bình" },
          { code: "DRV-001", name: "An" },
          { code: "DRV-004", name: "Dũng" },
        ];
        driversList.forEach(d => {
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "quick-pick-btn";
          btn.textContent = `🚗 Tôi là tài xế ${d.name} (${d.code})`;
          btn.addEventListener("click", () => {
            queryInput.value = `Tôi là tài xế ${d.name} (${d.code}), ` + queryInput.value;
            submitQuery();
          });
          actionsWrap.appendChild(btn);
        });
      }

      // If missing time
      if (data.missing_slots && data.missing_slots.includes("time_scope")) {
        const times = ["Tháng 9/2026", "30 ngày gần nhất"];
        times.forEach(t => {
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "quick-pick-btn";
          btn.textContent = `📅 Trong ${t}`;
          btn.addEventListener("click", () => {
            queryInput.value = `trong ${t}, ` + queryInput.value;
            submitQuery();
          });
          actionsWrap.appendChild(btn);
        });
      }

      clarificationBox.appendChild(actionsWrap);
      body.appendChild(clarificationBox);
    } else {
      body.innerHTML = formatMarkdown(data.answer || "Không nhận được nội dung trả lời.");
    }
    bubble.appendChild(body);

    // Citations & Trace footer pills
    const footer = document.createElement("div");
    footer.className = "citations-inline-bar";

    if (data.citations && data.citations.length > 0) {
      data.citations.forEach((c, idx) => {
        const pill = document.createElement("button");
        pill.type = "button";
        pill.className = "citation-inline-pill";
        pill.textContent = `[${idx + 1}] ${c.locator.split("#")[0].slice(0, 16)}...`;
        pill.title = `Xem dẫn chứng: ${c.locator}`;
        pill.addEventListener("click", () => {
          switchTab("tab-citations");
          highlightCitationCard(idx);
        });
        footer.appendChild(pill);
      });
    }

    if (data.trace_url) {
      const traceBtn = document.createElement("a");
      traceBtn.href = data.trace_url;
      traceBtn.target = "_blank";
      traceBtn.rel = "noopener noreferrer";
      traceBtn.className = "btn-trace-pill";
      traceBtn.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:12px;height:12px;">
          <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
        </svg>
        Langfuse Trace
      `;
      footer.appendChild(traceBtn);
    }

    if (footer.children.length > 0) {
      bubble.appendChild(footer);
    }

    bubbleContainer.appendChild(bubble);
    row.appendChild(avatar);
    row.appendChild(bubbleContainer);

    chatMessages.appendChild(row);
    scrollToBottom();
  }

  function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  // =========================================================================
  // 4. Inspector Updates (Citations, SVG Graph, Trace)
  // =========================================================================
  function updateInspector(data) {
    // 1. Citations
    const citations = data.citations || [];
    citationsCount.textContent = citations.length;

    if (citations.length === 0) {
      citationsSummary.textContent = "Không có dẫn chứng nào được thu thập cho truy vấn này.";
      citationsList.innerHTML = "";
    } else {
      citationsSummary.innerHTML = `Đã thu thập <strong>${citations.length}</strong> bằng chứng xác thực từ kho quy chế GSM và đồ thị sổ cái:`;
      citationsList.innerHTML = "";

      citations.forEach((c, idx) => {
        const card = document.createElement("div");
        card.className = "citation-card";
        card.id = `citation-card-${idx}`;

        let cat = "Quy chế GSM";
        if (c.locator.startsWith("ledger:")) cat = "Lịch sử chuyến đi";
        else if (c.locator.startsWith("computation:")) cat = "Số học hữu tỉ";
        else if (c.locator.startsWith("assertion:")) cat = "Chỉ số vận hành";

        card.innerHTML = `
          <div class="citation-header">
            <span class="citation-locator-tag">[${idx + 1}] ${c.locator}</span>
            <span class="citation-category-tag">${cat}</span>
          </div>
          <div class="citation-body">${escapeHtml(c.content)}</div>
        `;
        citationsList.appendChild(card);
      });
    }

    // 2. Subgraph Graph Render
    if (data.subgraph && data.subgraph.nodes && data.subgraph.nodes.length > 0) {
      renderSvgSubgraph(data.subgraph);
    } else {
      graphCount.textContent = "0";
      graphStatNodes.innerHTML = "<strong>0</strong> nút";
      graphStatEdges.innerHTML = "<strong>0</strong> cạnh";
      graphEmptyState.style.display = "flex";
      svgNodesGroup.innerHTML = "";
      svgEdgesGroup.innerHTML = "";
      nodeDetailsCard.style.display = "none";
    }

    // 3. Trace & Metrics
    if (data.trace_url) {
      traceExternalLink.href = data.trace_url;
      traceExternalLink.classList.remove("disabled");
      traceExternalLink.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="mini-icon">
          <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
        </svg>
        <span>Mở Trace Trên Langfuse Cloud</span>
      `;
    } else {
      traceExternalLink.href = "#";
      traceExternalLink.classList.add("disabled");
    }

    metricLatency.textContent = `${data.latency_ms || 0} ms`;
    metricStatus.textContent = data.status;
  }

  function resetInspector() {
    citationsCount.textContent = "0";
    citationsSummary.textContent = "Chưa có dữ liệu trích dẫn.";
    citationsList.innerHTML = "";
    graphCount.textContent = "0";
    graphEmptyState.style.display = "flex";
    svgNodesGroup.innerHTML = "";
    svgEdgesGroup.innerHTML = "";
    nodeDetailsCard.style.display = "none";
    traceExternalLink.classList.add("disabled");
    metricLatency.textContent = "-- ms";
    metricStatus.textContent = "--";
  }

  function switchTab(tabId) {
    tabBtns.forEach(b => {
      if (b.getAttribute("data-tab") === tabId) b.classList.add("active");
      else b.classList.remove("active");
    });
    tabPanes.forEach(p => {
      if (p.id === tabId) p.classList.add("active");
      else p.classList.remove("active");
    });
  }

  function highlightCitationCard(idx) {
    const card = document.getElementById(`citation-card-${idx}`);
    if (card) {
      card.scrollIntoView({ behavior: "smooth", block: "center" });
      card.style.borderColor = "var(--primary-emerald)";
      card.style.boxShadow = "0 0 14px var(--primary-emerald-glow)";
      setTimeout(() => {
        card.style.borderColor = "";
        card.style.boxShadow = "";
      }, 2000);
    }
  }

  // =========================================================================
  // 5. SVG Knowledge Graph Visualization
  // =========================================================================
  function renderSvgSubgraph(subgraph) {
    graphEmptyState.style.display = "none";
    graphCount.textContent = subgraph.node_count || subgraph.nodes.length;
    graphStatNodes.innerHTML = `<strong>${subgraph.node_count || subgraph.nodes.length}</strong> nút`;
    graphStatEdges.innerHTML = `<strong>${subgraph.edge_count || subgraph.edges.length}</strong> cạnh`;

    const svgWidth = graphCanvasContainer.clientWidth || 440;
    const svgHeight = 420;
    subgraphSvg.setAttribute("viewBox", `0 0 ${svgWidth} ${svgHeight}`);

    svgNodesGroup.innerHTML = "";
    svgEdgesGroup.innerHTML = "";

    const nodes = subgraph.nodes;
    const edges = subgraph.edges;

    // Layout calculation: center driver seed, ring for trips and meta
    const nodeCoords = new Map();
    const centerX = svgWidth / 2;
    const centerY = svgHeight / 2;

    const driverNode = nodes.find(n => n.label === "Driver") || nodes[0];
    nodeCoords.set(driverNode.id, { x: centerX, y: centerY, node: driverNode });

    const otherNodes = nodes.filter(n => n.id !== driverNode.id);
    const radius = Math.min(centerX, centerY) * 0.72;

    otherNodes.forEach((node, i) => {
      const angle = (2 * Math.PI * i) / otherNodes.length;
      const x = centerX + radius * Math.cos(angle);
      const y = centerY + radius * Math.sin(angle);
      nodeCoords.set(node.id, { x, y, node });
    });

    // Render Edges
    edges.forEach(edge => {
      const start = nodeCoords.get(edge.start_id);
      const end = nodeCoords.get(edge.end_id);
      if (!start || !end) return;

      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", start.x);
      line.setAttribute("y1", start.y);
      line.setAttribute("x2", end.x);
      line.setAttribute("y2", end.y);
      line.setAttribute("stroke", "rgba(255, 255, 255, 0.18)");
      line.setAttribute("stroke-width", "1.5");
      line.setAttribute("stroke-dasharray", edge.rel_type.includes("OPT") ? "4,3" : "none");
      svgEdgesGroup.appendChild(line);
    });

    // Render Nodes
    nodeCoords.forEach((coord, id) => {
      const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
      g.setAttribute("class", "svg-node-group");
      g.style.cursor = "pointer";

      let fillColor = "#8b5cf6"; // default other
      let r = 14;

      if (coord.node.label === "Driver") {
        fillColor = "#00d09c";
        r = 20;
      } else if (coord.node.label === "Trip") {
        fillColor = "#06b6d4";
        r = 12;
      } else if (coord.node.label === "Service" || coord.node.label === "Fleet") {
        fillColor = "#f59e0b";
        r = 13;
      }

      // Circle
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", coord.x);
      circle.setAttribute("cy", coord.y);
      circle.setAttribute("r", r);
      circle.setAttribute("fill", fillColor);
      circle.setAttribute("stroke", "#ffffff");
      circle.setAttribute("stroke-width", "2");

      // Label text
      const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      text.setAttribute("x", coord.x);
      text.setAttribute("y", coord.y + r + 13);
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("fill", "#cbd5e1");
      text.setAttribute("font-size", "10px");
      text.setAttribute("font-family", "Inter, sans-serif");
      text.textContent = coord.node.name ? coord.node.name.slice(0, 10) : coord.node.id.slice(0, 6);

      g.appendChild(circle);
      g.appendChild(text);

      // Node Click Inspector
      g.addEventListener("click", () => {
        showNodeDetails(coord.node);
      });

      svgNodesGroup.appendChild(g);
    });
  }

  function showNodeDetails(node) {
    nodeDetailsCard.style.display = "block";
    nodeDetailLabel.textContent = node.label;
    nodeDetailName.textContent = node.name || node.id;
    nodeDetailProps.textContent = JSON.stringify(node.props || {}, null, 2);
  }

  // =========================================================================
  // 6. Helpers (Markdown & Sanitization)
  // =========================================================================
  function formatMarkdown(text) {
    if (!text) return "";
    let html = escapeHtml(text);

    // Bold **text**
    html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

    // Headings
    html = html.replace(/^### (.*$)/gim, '<h4 style="color:var(--primary-emerald);margin:0.5rem 0 0.25rem 0;">$1</h4>');
    html = html.replace(/^## (.*$)/gim, '<h3 style="color:var(--text-main);margin:0.6rem 0 0.3rem 0;">$1</h3>');

    // Numbered lists
    html = html.replace(/^(\d+)\.\s+(.*$)/gim, '<div style="margin-left:0.5rem;margin-bottom:0.25rem;"><strong>$1.</strong> $2</div>');

    // Bullet lists
    html = html.replace(/^[-\*]\s+(.*$)/gim, '<div style="margin-left:0.5rem;margin-bottom:0.25rem;">• $1</div>');

    // Paragraph breaks
    html = html.replace(/\n\n/g, '<div style="height:0.6rem;"></div>');
    html = html.replace(/\n/g, '<br/>');

    return html;
  }

  function escapeHtml(string) {
    return String(string)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Start app
  initApp();
});
