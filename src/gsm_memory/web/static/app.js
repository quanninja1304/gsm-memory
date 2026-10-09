/**
 * GSM Memory AI Assistant - Pure Dynamic Query Planning & Local Database Client
 */

document.addEventListener("DOMContentLoaded", () => {
  // =========================================================================
  // DOM Elements
  // =========================================================================
  const chatMessages = document.getElementById("chat-messages");
  const chatInputForm = document.getElementById("chat-input-form");
  const queryInput = document.getElementById("query-input");
  const btnSend = document.getElementById("btn-send");
  const charCounter = document.getElementById("char-counter");
  const btnClearChat = document.getElementById("btn-clear-chat");
  const btnToggleInspector = document.getElementById("btn-toggle-inspector");
  const inspectorSection = document.getElementById("inspector-section");

  // Sidebar & Sessions
  const btnToggleSidebar = document.getElementById("btn-toggle-sidebar");
  const sessionsSidebar = document.getElementById("sessions-sidebar");
  const btnNewChat = document.getElementById("btn-new-chat");
  const sessionsList = document.getElementById("sessions-list");
  const sidebarSessionsCount = document.getElementById("sidebar-sessions-count");
  const sidebarDbSummary = document.getElementById("sidebar-db-summary");

  // Context Memory Live Bar
  const memValDriver = document.getElementById("mem-val-driver");
  const memValTime = document.getElementById("mem-val-time");
  const memValPolicy = document.getElementById("mem-val-policy");
  const memValTopics = document.getElementById("mem-val-topics");
  const pillClarify = document.getElementById("pill-clarify");
  const memValClarify = document.getElementById("mem-val-clarify");
  const btnClearMemory = document.getElementById("btn-clear-memory");

  // Local DB Modal
  const btnOpenDb = document.getElementById("btn-open-db");
  const dbModalOverlay = document.getElementById("db-modal-overlay");
  const btnCloseDbModal = document.getElementById("btn-close-db-modal");
  const headerDbBadge = document.getElementById("header-db-badge");
  const modalDriversCount = document.getElementById("modal-drivers-count");
  const modalTripsCount = document.getElementById("modal-trips-count");
  const modalTabBtns = document.querySelectorAll(".modal-tab-btn");
  const modalTabPanes = document.querySelectorAll(".modal-tab-pane");
  const dbSearchDrivers = document.getElementById("db-search-drivers");
  const driversCardsGrid = document.getElementById("drivers-cards-grid");
  const tripsFilterDriver = document.getElementById("trips-filter-driver");
  const tripsFilterOutcome = document.getElementById("trips-filter-outcome");
  const tripsTableBody = document.getElementById("trips-table-body");
  const tripsStatusSummary = document.getElementById("trips-status-summary");
  const driversStatusSummary = document.getElementById("drivers-status-summary");
  const statsOverviewGrid = document.getElementById("stats-overview-grid");

  // Inspector Elements
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");

  // Tab 1: Plan
  const planEmptyNotice = document.getElementById("plan-empty-notice");
  const planCardDetails = document.getElementById("plan-card-details");
  const planStatusBadge = document.getElementById("plan-status-badge");
  const planIntentBadge = document.getElementById("plan-intent-badge");
  const planFieldDriver = document.getElementById("plan-field-driver");
  const planFieldTime = document.getElementById("plan-field-time");
  const planFieldPolicy = document.getElementById("plan-field-policy");
  const planFieldTopics = document.getElementById("plan-field-topics");
  const planFieldModalities = document.getElementById("plan-field-modalities");
  const planReasoningText = document.getElementById("plan-reasoning-text");
  const btnToggleJson = document.getElementById("btn-toggle-json");
  const planJsonView = document.getElementById("plan-json-view");

  // Tab 2: Citations
  const citationsCount = document.getElementById("citations-count");
  const citationsSummary = document.getElementById("citations-summary");
  const citationsList = document.getElementById("citations-list");

  // Tab 3: Graph
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

  // Tab 4: Trace
  const traceExternalLink = document.getElementById("trace-external-link");
  const metricLatency = document.getElementById("metric-latency");
  const metricStatus = document.getElementById("metric-status");
  const metricModel = document.getElementById("metric-model");

  // App State
  let currentSessionId = null;
  let isSubmitting = false;
  let cachedDrivers = [];
  let cachedTrips = [];

  // =========================================================================
  // 1. App Initialization
  // =========================================================================
  initApp();

  async function initApp() {
    setupEventListeners();
    await loadSessions();
    await refreshDbBadgeAndSummary();
  }

  function setupEventListeners() {
    // Textarea auto-resize & counter
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
      if (confirm("Bạn có chắc chắn muốn làm mới giao diện trò chuyện?")) {
        resetChatMessages();
        resetInspector();
      }
    });

    // Toggle sidebar
    if (btnToggleSidebar) {
      btnToggleSidebar.addEventListener("click", () => {
        sessionsSidebar.classList.toggle("collapsed");
      });
    }

    // New chat button
    btnNewChat.addEventListener("click", () => {
      startNewChat();
    });

    // Clear context memory button
    btnClearMemory.addEventListener("click", async () => {
      if (!currentSessionId) return;
      try {
        await fetch(`/api/sessions/${currentSessionId}/context`, { method: "DELETE" });
        updateContextMemoryUI({});
      } catch (err) {
        console.error("Error clearing context:", err);
      }
    });

    // Toggle inspector drawer
    btnToggleInspector.addEventListener("click", () => {
      inspectorSection.classList.toggle("collapsed");
    });

    // Drag-to-scroll interaction for Inspector tabs (Hold & Drag)
    const inspectorTabsContainer = document.querySelector(".inspector-tabs");
    let isMouseDown = false;
    let startX = 0;
    let initialScrollLeft = 0;
    let hasDragged = false;

    if (inspectorTabsContainer) {
      inspectorTabsContainer.addEventListener("mousedown", (e) => {
        isMouseDown = true;
        hasDragged = false;
        startX = e.pageX - inspectorTabsContainer.offsetLeft;
        initialScrollLeft = inspectorTabsContainer.scrollLeft;
        inspectorTabsContainer.classList.add("is-dragging");
      });

      window.addEventListener("mousemove", (e) => {
        if (!isMouseDown) return;
        const currentX = e.pageX - inspectorTabsContainer.offsetLeft;
        const walk = currentX - startX;
        if (Math.abs(walk) > 4) {
          hasDragged = true;
        }
        inspectorTabsContainer.scrollLeft = initialScrollLeft - walk;
      });

      window.addEventListener("mouseup", () => {
        if (!isMouseDown) return;
        isMouseDown = false;
        inspectorTabsContainer.classList.remove("is-dragging");
      });

      // Mouse wheel support as complementary gesture
      inspectorTabsContainer.addEventListener("wheel", (e) => {
        if (e.deltaY !== 0) {
          e.preventDefault();
          inspectorTabsContainer.scrollLeft += e.deltaY;
        }
      }, { passive: false });
    }

    tabBtns.forEach(btn => {
      btn.addEventListener("click", (e) => {
        if (hasDragged) {
          e.preventDefault();
          e.stopPropagation();
          return;
        }
        tabBtns.forEach(b => b.classList.remove("active"));
        tabPanes.forEach(p => p.classList.remove("active"));
        btn.classList.add("active");
        btn.scrollIntoView({ behavior: "smooth", inline: "nearest", block: "nearest" });
        const targetId = btn.getAttribute("data-tab");
        const targetPane = document.getElementById(targetId);
        if (targetPane) targetPane.classList.add("active");
      });
    });

    // Plan JSON View toggle
    btnToggleJson.addEventListener("click", () => {
      if (planJsonView.style.display === "none") {
        planJsonView.style.display = "block";
        btnToggleJson.textContent = "Ẩn JSON Query Plan";
      } else {
        planJsonView.style.display = "none";
        btnToggleJson.textContent = "Xem JSON Query Plan thuần";
      }
    });

    // Close Node Detail Card in Graph
    btnCloseNode.addEventListener("click", () => {
      nodeDetailsCard.style.display = "none";
    });

    // Local DB Modal Handlers
    btnOpenDb.addEventListener("click", () => {
      openDbModal();
    });

    btnCloseDbModal.addEventListener("click", () => {
      closeDbModal();
    });

    dbModalOverlay.addEventListener("click", (e) => {
      if (e.target === dbModalOverlay) {
        closeDbModal();
      }
    });

    // DB Modal Tab Switching
    modalTabBtns.forEach(btn => {
      btn.addEventListener("click", () => {
        modalTabBtns.forEach(b => b.classList.remove("active"));
        modalTabPanes.forEach(p => p.classList.remove("active"));
        btn.classList.add("active");
        const targetId = btn.getAttribute("data-modaltab");
        const targetPane = document.getElementById(targetId);
        if (targetPane) targetPane.classList.add("active");

        if (targetId === "modaltab-drivers") loadDbDrivers();
        else if (targetId === "modaltab-trips") loadDbTrips();
        else if (targetId === "modaltab-stats") loadDbStats();
      });
    });

    // Driver Search Filter
    dbSearchDrivers.addEventListener("input", () => {
      const term = dbSearchDrivers.value.toLowerCase().trim();
      filterDriversGrid(term);
    });

    // Trips Filters
    tripsFilterDriver.addEventListener("change", () => loadDbTrips());
    tripsFilterOutcome.addEventListener("change", () => loadDbTrips());
  }

  function autoResizeTextarea() {
    queryInput.style.height = "auto";
    const newHeight = Math.min(queryInput.scrollHeight, 180);
    queryInput.style.height = `${newHeight}px`;
  }

  // =========================================================================
  // 2. Chat Sessions Management (SQLite)
  // =========================================================================

  async function loadSessions() {
    try {
      const res = await fetch("/api/sessions?limit=50");
      if (!res.ok) return;
      const sessions = await res.json();
      sidebarSessionsCount.textContent = sessions.length;
      renderSessionsList(sessions);

      // Auto-load most recent session if available and not already loaded
      if (!currentSessionId && sessions.length > 0) {
        selectSession(sessions[0].session_id);
      }
    } catch (err) {
      console.error("Error loading sessions:", err);
    }
  }

  function renderSessionsList(sessions) {
    sessionsList.innerHTML = "";
    if (sessions.length === 0) {
      sessionsList.innerHTML = `<div style="padding:1rem;color:var(--text-dim);font-size:0.78rem;text-align:center;">Chưa có lịch sử trò chuyện. Bấm "+ Cuộc trò chuyện mới" để bắt đầu!</div>`;
      return;
    }

    sessions.forEach(s => {
      const item = document.createElement("div");
      item.className = `session-item ${s.session_id === currentSessionId ? "active" : ""}`;
      item.id = `session-item-${s.session_id}`;

      const dateStr = formatRelativeTime(s.updated_at);
      const msgCount = s.messages_count || 0;

      item.innerHTML = `
        <div class="session-info">
          <div class="session-title" title="${escapeHtml(s.title)}">${escapeHtml(s.title)}</div>
          <div class="session-meta">
            <span>${msgCount} tin nhắn</span>
            <span>•</span>
            <span>${dateStr}</span>
          </div>
        </div>
        <button type="button" class="session-del-btn" title="Xóa cuộc trò chuyện này">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px;">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
          </svg>
        </button>
      `;

      // Select session on click
      item.addEventListener("click", (e) => {
        if (e.target.closest(".session-del-btn")) return;
        selectSession(s.session_id);
      });

      // Delete session on trash button click
      const delBtn = item.querySelector(".session-del-btn");
      delBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        if (confirm(`Bạn có chắc chắn muốn xóa phiên hội thoại "${s.title}"?`)) {
          await deleteSession(s.session_id);
        }
      });

      sessionsList.appendChild(item);
    });
  }

  async function selectSession(sessionId) {
    currentSessionId = sessionId;
    document.querySelectorAll(".session-item").forEach(el => el.classList.remove("active"));
    const activeEl = document.getElementById(`session-item-${sessionId}`);
    if (activeEl) activeEl.classList.add("active");

    try {
      const res = await fetch(`/api/sessions/${sessionId}`);
      if (!res.ok) return;
      const data = await res.json();

      // Render messages
      renderSessionHistory(data.messages || []);

      // Update context memory bar
      updateContextMemoryUI(data.context || {});

      // If messages exist, update inspector with the last bot response
      const botMsgs = (data.messages || []).filter(m => m.role === "assistant");
      if (botMsgs.length > 0) {
        const last = botMsgs[botMsgs.length - 1];
        updateInspector({
          query_plan: last.query_plan,
          citations: last.citations,
          subgraph: last.subgraph,
          latency_ms: last.latency_ms,
        });
      } else {
        resetInspector();
      }
    } catch (err) {
      console.error("Error selecting session:", err);
    }
  }

  function startNewChat() {
    currentSessionId = null;
    document.querySelectorAll(".session-item").forEach(el => el.classList.remove("active"));
    resetChatMessages();
    updateContextMemoryUI({});
    resetInspector();
    queryInput.focus();
  }

  async function deleteSession(sessionId) {
    try {
      await fetch(`/api/sessions/${sessionId}`, { method: "DELETE" });
      if (currentSessionId === sessionId) {
        startNewChat();
      }
      await loadSessions();
      await refreshDbBadgeAndSummary();
    } catch (err) {
      console.error("Error deleting session:", err);
    }
  }

  function resetChatMessages() {
    chatMessages.innerHTML = `
      <div class="welcome-card" id="welcome-card">
        <div class="welcome-icon-glow">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>
          </svg>
        </div>
        <h2>Phiên Tra Cứu Vận Hành Mới 🚀</h2>
        <p>Hệ thống sẵn sàng hỗ trợ nhân viên vận hành. Hãy nhập mã tài xế hoặc yêu cầu kiểm tra đối soát quy chế để bắt đầu!</p>
      </div>
    `;
  }

  function renderSessionHistory(messages) {
    chatMessages.innerHTML = "";
    if (messages.length === 0) {
      resetChatMessages();
      return;
    }
    messages.forEach(msg => {
      if (msg.role === "user") {
        appendMessage("user", msg.content);
      } else {
        const isClarification =
          msg.status === "NEEDS_CLARIFICATION" ||
          (msg.query_plan && msg.query_plan.missing_fields && msg.query_plan.missing_fields.length > 0) ||
          (msg.query_plan && msg.query_plan.clarification_reasons && Object.keys(msg.query_plan.clarification_reasons).length > 0) ||
          (msg.content && (
            msg.content.includes("bổ sung thêm") ||
            msg.content.includes("bổ sung thông tin") ||
            msg.content.includes("bổ sung dữ liệu") ||
            msg.content.includes("vui lòng cung cấp") ||
            msg.content.includes("cần thêm thông tin") ||
            msg.content.includes("Yêu cầu bổ sung")
          ));

        appendBotResponse({
          status: isClarification ? "NEEDS_CLARIFICATION" : (msg.status || "ANSWERED"),
          answer: msg.content,
          clarification_message: msg.content,
          query_plan: msg.query_plan,
          citations: msg.citations,
          subgraph: msg.subgraph,
          latency_ms: msg.latency_ms,
        });
      }
    });
    scrollToBottom();
  }

  function updateContextMemoryUI(ctx) {
    ctx = ctx || {};

    // Driver
    const driverVal = ctx.driver_name ? `${ctx.driver_name} (${ctx.driver_code || ""})` : (ctx.driver_mention || ctx.driver_id || null);
    if (driverVal) {
      memValDriver.textContent = driverVal;
      memValDriver.classList.remove("empty");
    } else {
      memValDriver.textContent = "Chưa nhận diện";
      memValDriver.classList.add("empty");
    }

    // Time
    if (ctx.time_scope) {
      memValTime.textContent = ctx.time_scope;
      memValTime.classList.remove("empty");
    } else {
      memValTime.textContent = "Chưa có";
      memValTime.classList.add("empty");
    }

    // Policy
    if (ctx.policy_scope) {
      memValPolicy.textContent = ctx.policy_scope;
      memValPolicy.classList.remove("empty");
    } else {
      memValPolicy.textContent = "--";
      memValPolicy.classList.add("empty");
    }

    // Policy Topics
    if (memValTopics) {
      if (ctx.policy_topics) {
        memValTopics.textContent = ctx.policy_topics;
        memValTopics.classList.remove("empty");
      } else {
        memValTopics.textContent = "--";
        memValTopics.classList.add("empty");
      }
    }

    // Pending Clarification
    if (ctx.pending_clarification) {
      pillClarify.style.display = "flex";
      memValClarify.textContent = ctx.pending_clarification;
    } else {
      pillClarify.style.display = "none";
    }
  }

  // =========================================================================
  // 3. Chat Submission with Dynamic Session & Memory Persistence
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
    if (planStatusBadge) {
      planStatusBadge.className = "plan-status-badge status-analyzing";
      planStatusBadge.innerHTML = `<span class="badge-mini-spinner"></span> Đang phân tích...`;
    }
    const typingRow = appendTypingIndicator();

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: text,
          session_id: currentSessionId,
        }),
      });

      typingRow.remove();

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const data = await response.json();

      // Update current session id if new
      if (data.session_id && data.session_id !== currentSessionId) {
        currentSessionId = data.session_id;
        await loadSessions();
      }

      appendBotResponse(data);
      updateInspector(data);
      updateContextMemoryUI(data.active_context || {});
      await refreshDbBadgeAndSummary();
    } catch (err) {
      typingRow.remove();
      if (planStatusBadge) {
        planStatusBadge.className = "plan-status-badge";
        planStatusBadge.textContent = "Lỗi xử lý";
      }
      appendMessage("bot", `⚠️ Đã xảy ra lỗi khi kết nối với máy chủ: ${err.message}. Vui lòng thử lại.`);
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
    avatar.innerHTML = role === "user" ? "NV" : "GSM";
    avatar.title = role === "user" ? "Nhân viên Vận hành" : "Trợ lý AI GSM";

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

  // =========================================================================
  // Pipeline Step Definitions for Dynamic Processing Indicator
  // =========================================================================
  const PIPELINE_STEPS = [
    {
      step: 1,
      badge: "Bước 1/5",
      tag: "Kế hoạch truy vấn",
      title: "Phân tích Ý định & Lập Kế hoạch Truy vấn",
      desc: "Đọc bộ nhớ ngữ cảnh hội thoại, trích xuất mã tài xế và mốc thời gian...",
      thresholdMs: 0,
    },
    {
      step: 2,
      badge: "Bước 2/5",
      tag: "Xác thực thông tin",
      title: "Xác Thực Thông Tin & Tham Số",
      desc: "Đối soát dữ liệu vận hành, kiểm tra tính đầy đủ của tham số...",
      thresholdMs: 1200,
    },
    {
      step: 3,
      badge: "Bước 3/5",
      tag: "Đồ thị tri thức",
      title: "Truy Vấn Đồ Thị Tri Thức Vận Hành",
      desc: "Duyệt liên kết quan hệ các chuyến đi, tài xế và hồ sơ theo mốc lịch sử...",
      thresholdMs: 2500,
    },
    {
      step: 4,
      badge: "Bước 4/5",
      tag: "Truy xuất đa nguồn",
      title: "Truy Xuất Đa Nguồn & Tái Xếp Hạng",
      desc: "Khớp từ khóa văn bản, tìm kiếm ngữ nghĩa và xếp hạng mức độ liên quan...",
      thresholdMs: 4000,
    },
    {
      step: 5,
      badge: "Bước 5/5",
      tag: "Tổng hợp phản hồi",
      title: "Tổng Hợp Bằng Chứng & Soạn Thảo Phản Hồi",
      desc: "Đối chiếu căn cứ pháp lý, lập luận theo quy chế GSM và tạo câu trả lời...",
      thresholdMs: 5800,
    },
  ];

  function appendTypingIndicator() {
    const row = document.createElement("div");
    row.className = "message-row bot-row typing-row";

    const avatar = document.createElement("div");
    avatar.className = "avatar-badge bot-avatar";
    avatar.innerHTML = "GSM";

    const bubbleContainer = document.createElement("div");
    bubbleContainer.className = "bubble-container";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble bot-bubble processing-bubble";
    bubble.innerHTML = `
      <div class="processing-card">
        <div class="processing-top">
          <div class="processing-spinner-wrapper" aria-hidden="true">
            <div class="processing-spinner-ring"></div>
            <div class="processing-spinner-core"></div>
          </div>
          <div class="processing-info">
            <div class="processing-meta-line">
              <span class="processing-badge" id="proc-badge">Bước 1/5</span>
              <span class="processing-tag" id="proc-tag">Query Planning</span>
              <span class="processing-timer" id="proc-timer">0.0s</span>
            </div>
            <div class="processing-step-title step-text-fade" id="proc-title">
              Phân tích Ý định & Lập Kế hoạch Truy vấn
            </div>
            <div class="processing-step-desc step-text-fade" id="proc-desc">
              Đọc bộ nhớ ngữ cảnh hội thoại, trích xuất mã tài xế và mốc thời gian...
            </div>
          </div>
        </div>

        <div class="processing-timeline" id="proc-timeline" aria-label="Tiến trình xử lý các bước">
          <div class="proc-step-node active" data-step="1">
            <div class="node-bullet"><span class="node-num">1</span><span class="node-check">✓</span></div>
            <div class="node-name">Kế hoạch</div>
          </div>
          <div class="proc-step-line" data-line="1"></div>

          <div class="proc-step-node" data-step="2">
            <div class="node-bullet"><span class="node-num">2</span><span class="node-check">✓</span></div>
            <div class="node-name">Kiểm định</div>
          </div>
          <div class="proc-step-line" data-line="2"></div>

          <div class="proc-step-node" data-step="3">
            <div class="node-bullet"><span class="node-num">3</span><span class="node-check">✓</span></div>
            <div class="node-name">Đồ thị KG</div>
          </div>
          <div class="proc-step-line" data-line="3"></div>

          <div class="proc-step-node" data-step="4">
            <div class="node-bullet"><span class="node-num">4</span><span class="node-check">✓</span></div>
            <div class="node-name">Truy xuất</div>
          </div>
          <div class="proc-step-line" data-line="4"></div>

          <div class="proc-step-node" data-step="5">
            <div class="node-bullet"><span class="node-num">5</span><span class="node-check">✓</span></div>
            <div class="node-name">Tổng hợp</div>
          </div>
        </div>
      </div>
    `;

    bubbleContainer.appendChild(bubble);
    row.appendChild(avatar);
    row.appendChild(bubbleContainer);

    chatMessages.appendChild(row);
    scrollToBottom();

    // Elements
    const badgeEl = row.querySelector("#proc-badge");
    const tagEl = row.querySelector("#proc-tag");
    const timerEl = row.querySelector("#proc-timer");
    const titleEl = row.querySelector("#proc-title");
    const descEl = row.querySelector("#proc-desc");
    const nodes = row.querySelectorAll(".proc-step-node");
    const lines = row.querySelectorAll(".proc-step-line");

    const startTime = performance.now();
    let currentStepIdx = 0;

    function applyStep(idx) {
      currentStepIdx = idx;
      const step = PIPELINE_STEPS[idx];

      if (badgeEl) badgeEl.textContent = step.badge;
      if (tagEl) tagEl.textContent = step.tag;

      if (titleEl) {
        titleEl.textContent = step.title;
        titleEl.classList.remove("step-text-fade");
        void titleEl.offsetWidth; // re-trigger animation
        titleEl.classList.add("step-text-fade");
      }
      if (descEl) {
        descEl.textContent = step.desc;
        descEl.classList.remove("step-text-fade");
        void descEl.offsetWidth;
        descEl.classList.add("step-text-fade");
      }

      // Update timeline step nodes
      nodes.forEach((node, nodeIdx) => {
        node.classList.remove("active", "completed");
        if (nodeIdx < idx) {
          node.classList.add("completed");
        } else if (nodeIdx === idx) {
          node.classList.add("active");
        }
      });

      // Update timeline connecting lines
      lines.forEach((line, lineIdx) => {
        if (lineIdx < idx) {
          line.classList.add("completed");
        } else {
          line.classList.remove("completed");
        }
      });
    }

    const timerInterval = setInterval(() => {
      const elapsed = performance.now() - startTime;
      if (timerEl) {
        timerEl.textContent = `${(elapsed / 1000).toFixed(1)}s`;
      }

      let nextIdx = 0;
      for (let i = PIPELINE_STEPS.length - 1; i >= 0; i--) {
        if (elapsed >= PIPELINE_STEPS[i].thresholdMs) {
          nextIdx = i;
          break;
        }
      }

      if (nextIdx !== currentStepIdx) {
        applyStep(nextIdx);
        scrollToBottom();
      }
    }, 100);

    const origRemove = row.remove.bind(row);
    row.remove = function () {
      clearInterval(timerInterval);
      origRemove();
    };

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

    // 1. Status Banner for Clarification Gate
    if (data.status === "NEEDS_CLARIFICATION") {
      const banner = document.createElement("div");
      banner.className = "clarification-banner";
      banner.innerHTML = `
        <div class="banner-title">
          <svg class="clarification-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          <span>Yêu cầu bổ sung dữ liệu</span>
        </div>
        <div class="banner-desc">
          Hệ thống xác định câu hỏi cần bổ sung thông tin để tra cứu chính xác.
        </div>
      `;
      bubble.appendChild(banner);
    }

    // 2. Query Plan Card Preview inside bubble
    const plan = data.query_plan;
    if (plan) {
      const planCard = document.createElement("div");
      planCard.className = "chat-plan-card";

      const hasMissing = plan.missing_fields && plan.missing_fields.length > 0;
      const policyItems = [];
      if (plan.policy_scope && plan.policy_scope.length > 0) {
        policyItems.push(Array.isArray(plan.policy_scope) ? plan.policy_scope.join(", ") : plan.policy_scope);
      }
      if (plan.policy_topics && plan.policy_topics.length > 0) {
        policyItems.push(Array.isArray(plan.policy_topics) ? plan.policy_topics.join(", ") : plan.policy_topics);
      }
      const policyDisplay = policyItems.length > 0 ? policyItems.join(" / ") : "Không đề cập";

      const isPolicyLookup = plan.intent === "POLICY_LOOKUP";
      const driverDisplay = plan.driver_id
        ? `<span class="val-present">${escapeHtml(plan.driver_mention || plan.driver_id)}</span>`
        : (isPolicyLookup ? `<span class="val-present">Không yêu cầu</span>` : `<span class="val-missing">Chưa có (Thiếu ID)</span>`);

      const timeDisplay = plan.time_scope
        ? `<span class="val-present">${escapeHtml(plan.time_scope)}</span>`
        : (isPolicyLookup ? `<span class="val-present">Toàn bộ / Không yêu cầu</span>` : `<span class="val-missing">Chưa có (Thiếu thời gian cụ thể)</span>`);

      planCard.innerHTML = `
        <div class="chat-plan-header">
          <span>📋 AI Query Plan: ${plan.intent}</span>
          <span class="${hasMissing ? 'val-missing' : 'val-present'}">
            ${hasMissing ? '⚠️ Cần Bổ Sung Thông Tin' : '✅ Đủ Căn Cứ Truy Xuất'}
          </span>
        </div>
        <div class="chat-plan-grid">
          <div class="chat-plan-item">
            <span>Tài xế:</span> ${driverDisplay}
          </div>
          <div class="chat-plan-item">
            <span>Thời gian:</span> ${timeDisplay}
          </div>
          <div class="chat-plan-item">
            <span>Quy chế:</span> <strong>${escapeHtml(policyDisplay)}</strong>
          </div>
          <div class="chat-plan-item">
            <span>Kênh:</span> <strong>${(plan.modalities || []).join(", ") || "document"}</strong>
          </div>
        </div>
      `;
      bubble.appendChild(planCard);
    }

    // 3. Body Content
    const body = document.createElement("div");
    body.className = "bubble-content";

    if (data.status === "NEEDS_CLARIFICATION") {
      body.innerHTML = formatMarkdown(data.clarification_message || data.answer || "Vui lòng cung cấp thêm thông tin.");
    } else {
      body.innerHTML = formatMarkdown(data.answer || "Không nhận được nội dung trả lời.");
    }
    bubble.appendChild(body);

    // 4. Citations & Trace footer pills
    const footer = document.createElement("div");
    footer.className = "citations-inline-bar";

    if (data.citations && data.citations.length > 0) {
      data.citations.forEach((c, idx) => {
        const citeIndex = c.index || (idx + 1);
        const pill = document.createElement("button");
        pill.type = "button";
        pill.className = "citation-inline-pill";
        const shortName = c.policy_alias ? `[${c.policy_alias}]` : (c.name ? c.name.slice(0, 20) : (c.locator ? c.locator.slice(0, 16) : `Dẫn chứng ${citeIndex}`));
        pill.innerHTML = `<strong>[${citeIndex}]</strong> ${escapeHtml(shortName)}`;
        pill.title = `Xem chi tiết dẫn chứng [${citeIndex}]: ${c.name || c.locator}`;
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
  // 4. Inspector Updates (Query Plan, Citations, SVG Graph, Trace)
  // =========================================================================

  function updateInspector(data) {
    const plan = data.query_plan;

    // 1. Tab 1: AI Query Plan
    if (plan) {
      planEmptyNotice.style.display = "none";
      planCardDetails.style.display = "block";

      const hasMissing = plan.missing_fields && plan.missing_fields.length > 0;
      planStatusBadge.className = `plan-status-badge ${hasMissing ? 'status-needs-clarification' : 'status-ready'}`;
      planStatusBadge.textContent = hasMissing ? "Thiếu Trường Bắt Buộc" : "Kế Hoạch Hợp Lệ";
      planIntentBadge.textContent = plan.intent;

      planFieldDriver.innerHTML = plan.driver_id
        ? `<span class="val-present">${escapeHtml(plan.driver_mention || plan.driver_id)}</span>`
        : `<span class="val-missing">Chưa có (Thiếu ID tài xế)</span>`;

      planFieldTime.innerHTML = plan.time_scope
        ? `<span class="val-present">${escapeHtml(plan.time_scope)}</span>`
        : `<span class="val-missing">Chưa có (Thiếu mốc cụ thể)</span>`;

      planFieldPolicy.textContent = (plan.policy_scope && plan.policy_scope.length > 0)
        ? (Array.isArray(plan.policy_scope) ? plan.policy_scope.join(", ") : plan.policy_scope)
        : "Không đề cập";

      if (planFieldTopics) {
        planFieldTopics.textContent = (plan.policy_topics && plan.policy_topics.length > 0)
          ? (Array.isArray(plan.policy_topics) ? plan.policy_topics.join(", ") : plan.policy_topics)
          : "Không đề cập";
      }

      planFieldModalities.textContent = (plan.modalities || []).join(", ") || "document";
      planReasoningText.textContent = plan.reasoning || "Đã phân tích cú pháp ý định và các thực thể.";
      planJsonView.textContent = JSON.stringify(plan, null, 2);
    } else {
      planEmptyNotice.style.display = "block";
      planCardDetails.style.display = "none";
    }

    // 2. Tab 2: Citations
    const citations = data.citations || [];
    citationsCount.textContent = citations.length;

    if (citations.length === 0) {
      citationsSummary.textContent = "Chưa có dẫn chứng nào cho truy vấn này.";
      citationsList.innerHTML = "";
    } else {
      citationsSummary.innerHTML = `Đã thu thập <strong>${citations.length}</strong> bằng chứng xác thực từ kho quy chế GSM và đồ thị:`;
      citationsList.innerHTML = "";

      citations.forEach((c, idx) => {
        const card = document.createElement("div");
        card.className = "citation-card";
        card.id = `citation-card-${idx}`;

        const citeIndex = c.index || (idx + 1);
        const titleText = c.name || c.policy_title || c.locator || `Dẫn chứng ${citeIndex}`;
        const cat = c.category || "Bằng chứng hệ thống";
        const isDoc = (c.source_kind === "document") || (c.category && c.category.includes("quy chế"));

        // Meta chips
        let metaChipsHtml = '';
        if (c.policy_date || c.policy_category || (c.locator && !titleText.includes(c.locator))) {
          metaChipsHtml = '<div class="citation-meta-chips">';
          if (c.policy_date) {
            metaChipsHtml += `<span class="meta-chip chip-date"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg> Ngày: ${escapeHtml(c.policy_date)}</span>`;
          }
          if (c.policy_category) {
            metaChipsHtml += `<span class="meta-chip chip-category"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg> ${escapeHtml(c.policy_category)}</span>`;
          }
          if (c.locator && !titleText.includes(c.locator) && c.source_kind !== "document") {
            metaChipsHtml += `<span class="meta-chip chip-locator">Định danh: ${escapeHtml(c.locator)}</span>`;
          }
          metaChipsHtml += '</div>';
        }

        // Header
        const headerHtml = `
          <div class="citation-header">
            <div class="citation-header-left">
              <span class="citation-index-badge">[${citeIndex}]</span>
              <div class="citation-header-title-wrap">
                <span class="citation-card-title">${escapeHtml(titleText)}</span>
                ${metaChipsHtml}
              </div>
            </div>
            <div class="citation-header-right">
              <span class="citation-badge-kind kind-${c.source_kind || 'doc'}">${escapeHtml(cat)}</span>
              <button class="btn-copy-citation" title="Sao chép nội dung dẫn chứng" type="button">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                </svg>
              </button>
            </div>
          </div>
        `;

        // Body
        let bodyHtml = `<div class="citation-body">`;

        // 1. Excerpt highlight if present
        if (c.excerpt && c.excerpt.trim()) {
          bodyHtml += `
            <div class="citation-excerpt-callout">
              <div class="excerpt-badge">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                  <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
                </svg>
                Trọng tâm quy định tra cứu được:
              </div>
              <div class="excerpt-text">${formatMarkdown(c.excerpt)}</div>
            </div>
          `;
        }

        // 2. Full Content (collapsible for documents, direct for others)
        const contentStr = c.content || "";
        if (isDoc && contentStr.length > 250) {
          const wordEstimate = Math.round(contentStr.length / 5);
          const isExpanded = (idx === 0);
          bodyHtml += `
            <div class="citation-policy-container">
              <button class="btn-toggle-policy ${isExpanded ? 'expanded' : ''}" id="btn-toggle-doc-${idx}" type="button">
                <span class="toggle-icon">📖</span>
                <span class="toggle-label">Toàn văn quy chế đầy đủ ${c.policy_alias ? `[${c.policy_alias}]` : ''} (~${wordEstimate.toLocaleString()} từ)</span>
                <span class="toggle-arrow">${isExpanded ? '▲' : '▼'}</span>
              </button>
              <div class="citation-full-doc-drawer" id="drawer-doc-${idx}" style="display: ${isExpanded ? 'block' : 'none'};">
                <div class="drawer-notice">📜 Toàn văn quy định chuẩn hóa đầy đủ từ kho lưu trữ GSM:</div>
                <div class="policy-doc-content">${formatMarkdown(contentStr)}</div>
              </div>
            </div>
          `;
        } else {
          bodyHtml += `
            <div class="citation-simple-content">
              ${formatMarkdown(contentStr)}
            </div>
          `;
        }

        bodyHtml += `</div>`;

        card.innerHTML = headerHtml + bodyHtml;
        citationsList.appendChild(card);

        // Toggle button listener
        const toggleBtn = card.querySelector(`#btn-toggle-doc-${idx}`);
        if (toggleBtn) {
          toggleBtn.addEventListener("click", () => {
            const drawer = card.querySelector(`#drawer-doc-${idx}`);
            const arrow = toggleBtn.querySelector(".toggle-arrow");
            if (drawer.style.display === "none") {
              drawer.style.display = "block";
              arrow.textContent = "▲";
              toggleBtn.classList.add("expanded");
            } else {
              drawer.style.display = "none";
              arrow.textContent = "▼";
              toggleBtn.classList.remove("expanded");
            }
          });
        }

        // Copy button listener
        const copyBtn = card.querySelector(".btn-copy-citation");
        if (copyBtn) {
          copyBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            navigator.clipboard.writeText(contentStr).then(() => {
              copyBtn.classList.add("copied");
              setTimeout(() => copyBtn.classList.remove("copied"), 1500);
            });
          });
        }
      });
    }

    // 3. Tab 3: Subgraph Visualization (SVG Force Simulation / Layout)
    if (data.subgraph && data.subgraph.nodes && data.subgraph.nodes.length > 0) {
      renderSvgGraph(data.subgraph);
    } else {
      resetSvgGraph();
    }

    // 4. Tab 4: Trace
    if (data.trace_url) {
      traceExternalLink.href = data.trace_url;
      traceExternalLink.classList.remove("disabled");
    } else {
      traceExternalLink.href = "#";
      traceExternalLink.classList.add("disabled");
    }

    if (data.latency_ms) {
      metricLatency.textContent = `${data.latency_ms} ms`;
    }
    if (data.status) {
      metricStatus.textContent = data.status;
    }
  }

  function resetInspector() {
    planEmptyNotice.style.display = "block";
    planCardDetails.style.display = "none";
    citationsCount.textContent = "0";
    citationsSummary.textContent = "Chưa có dữ liệu trích dẫn.";
    citationsList.innerHTML = "";
    resetSvgGraph();
    metricLatency.textContent = "-- ms";
    metricStatus.textContent = "READY";
    traceExternalLink.href = "#";
    traceExternalLink.classList.add("disabled");
  }

  function switchTab(tabId) {
    tabBtns.forEach(b => {
      if (b.getAttribute("data-tab") === tabId) {
        b.click();
      }
    });
  }

  function highlightCitationCard(idx) {
    setTimeout(() => {
      const card = document.getElementById(`citation-card-${idx}`);
      if (card) {
        card.scrollIntoView({ behavior: "smooth", block: "center" });
        card.classList.add("highlight");
        setTimeout(() => card.classList.remove("highlight"), 2000);
      }
    }, 200);
  }

  // SVG Subgraph Rendering
  function renderSvgGraph(subgraph) {
    graphEmptyState.style.display = "none";
    graphStatNodes.innerHTML = `<strong>${subgraph.node_count}</strong> nút`;
    graphStatEdges.innerHTML = `<strong>${subgraph.edge_count}</strong> cạnh`;
    graphCount.textContent = subgraph.node_count;

    svgNodesGroup.innerHTML = "";
    svgEdgesGroup.innerHTML = "";

    const width = graphCanvasContainer.clientWidth || 450;
    const height = 450;
    const centerX = width / 2;
    const centerY = height / 2;

    const nodes = subgraph.nodes || [];
    const edges = subgraph.edges || [];

    // Radial layout around center
    const nodeCoords = {};
    const seedId = subgraph.seed_id;

    nodes.forEach((n, i) => {
      if (n.id === seedId) {
        nodeCoords[n.id] = { x: centerX, y: centerY };
      } else {
        const angle = (i / (nodes.length - (nodes.find(x => x.id === seedId) ? 1 : 0))) * 2 * Math.PI;
        const radius = Math.min(width, height) * 0.36;
        nodeCoords[n.id] = {
          x: centerX + radius * Math.cos(angle),
          y: centerY + radius * Math.sin(angle),
        };
      }
    });

    // Render Edges
    edges.forEach(e => {
      const start = nodeCoords[e.start_id];
      const end = nodeCoords[e.end_id];
      if (start && end) {
        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("x1", start.x);
        line.setAttribute("y1", start.y);
        line.setAttribute("x2", end.x);
        line.setAttribute("y2", end.y);
        line.setAttribute("class", "graph-edge");
        svgEdgesGroup.appendChild(line);
      }
    });

    // Render Nodes
    nodes.forEach(n => {
      const coord = nodeCoords[n.id] || { x: centerX, y: centerY };
      const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
      g.setAttribute("class", `graph-node-group node-${(n.label || "other").toLowerCase()}`);
      g.setAttribute("transform", `translate(${coord.x}, ${coord.y})`);

      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("r", n.id === seedId ? "16" : "11");
      circle.setAttribute("class", "graph-node");

      const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      text.setAttribute("dy", "22");
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("class", "graph-node-label");
      text.textContent = (n.name || n.label || "Node").slice(0, 14);

      g.appendChild(circle);
      g.appendChild(text);

      g.addEventListener("click", () => {
        showNodeDetails(n);
      });

      svgNodesGroup.appendChild(g);
    });
  }

  function resetSvgGraph() {
    graphEmptyState.style.display = "flex";
    graphStatNodes.innerHTML = "<strong>0</strong> nút";
    graphStatEdges.innerHTML = "<strong>0</strong> cạnh";
    graphCount.textContent = "0";
    svgNodesGroup.innerHTML = "";
    svgEdgesGroup.innerHTML = "";
    nodeDetailsCard.style.display = "none";
  }

  function showNodeDetails(node) {
    nodeDetailLabel.textContent = node.label || "Node";
    nodeDetailName.textContent = node.name || node.id;
    nodeDetailProps.innerHTML = "";

    const props = node.props || {};
    const entries = Object.entries(props);
    if (entries.length === 0) {
      nodeDetailProps.innerHTML = `<span style="color:var(--text-dim);font-size:0.75rem;">Không có thuộc tính mở rộng</span>`;
    } else {
      entries.forEach(([k, v]) => {
        const item = document.createElement("div");
        item.className = "node-prop-item";
        item.innerHTML = `
          <span class="prop-key">${escapeHtml(k)}:</span>
          <span class="prop-val">${escapeHtml(String(v))}</span>
        `;
        nodeDetailProps.appendChild(item);
      });
    }

    nodeDetailsCard.style.display = "block";
  }

  // =========================================================================
  // 5. Local Database Explorer Modal & Data Viewers
  // =========================================================================

  async function openDbModal() {
    dbModalOverlay.style.display = "flex";
    // Default open drivers tab
    loadDbDrivers();
    refreshDbBadgeAndSummary();
  }

  function closeDbModal() {
    dbModalOverlay.style.display = "none";
  }

  async function refreshDbBadgeAndSummary() {
    try {
      const res = await fetch("/api/db/stats");
      if (!res.ok) return;
      const stats = await res.json();
      if (headerDbBadge) headerDbBadge.textContent = `${stats.trips_count} Chuyến`;
      if (btnOpenDb) btnOpenDb.title = `Cơ sở dữ liệu vận hành (${stats.trips_count} chuyến đi, ${stats.drivers_count} tài xế)`;
      modalDriversCount.textContent = stats.drivers_count;
      modalTripsCount.textContent = stats.trips_count;
      sidebarDbSummary.textContent = `${stats.drivers_count} tài xế • ${stats.trips_count} chuyến đi`;
    } catch (e) {
      console.error("Error refreshing stats:", e);
    }
  }

  async function loadDbDrivers() {
    try {
      driversStatusSummary.textContent = "Đang tải dữ liệu...";
      const res = await fetch("/api/db/drivers");
      if (!res.ok) return;
      cachedDrivers = await res.json();
      driversStatusSummary.textContent = `${cachedDrivers.length} tài xế hoạt động`;
      modalDriversCount.textContent = cachedDrivers.length;
      renderDriversGrid(cachedDrivers);
      populateTripsDriverSelect(cachedDrivers);
    } catch (e) {
      driversStatusSummary.textContent = "Lỗi khi tải tài xế.";
    }
  }

  function renderDriversGrid(drivers) {
    driversCardsGrid.innerHTML = "";
    if (drivers.length === 0) {
      driversCardsGrid.innerHTML = `<div style="grid-column: 1/-1; text-align:center; padding:2rem; color:var(--text-dim);">Không tìm thấy tài xế phù hợp.</div>`;
      return;
    }

    drivers.forEach(d => {
      const card = document.createElement("div");
      card.className = "driver-card";

      const totalTrips = (d.completed_trips_count || 0) + (d.cancelled_trips_count || 0);
      const cancelPercent = ((d.cancellation_rate_30d || 0) * 100).toFixed(1);
      const isHighCancel = (d.cancellation_rate_30d || 0) > 0.10;

      card.innerHTML = `
        <div class="driver-card-header">
          <span class="driver-badge-code">${d.driver_code}</span>
          <span class="version-tag" style="font-size:0.68rem;">${escapeHtml(d.program || "full_time")}</span>
        </div>
        <div>
          <div class="driver-name">${escapeHtml(d.full_name)}</div>
          <div class="driver-sub">${escapeHtml(d.depot_name || "Depot")} • ${escapeHtml(d.region || "TP.HCM")}</div>
        </div>
        <div style="font-size:0.78rem;color:var(--text-muted);display:flex;flex-direction:column;gap:0.2rem;">
          <div>🚗 ${escapeHtml(d.vehicle_model || "VinFast VF e34")} (${escapeHtml(d.license_plate || "Chưa cấp")})</div>
          <div>📞 ${escapeHtml(d.phone || "--")} • ✉️ ${escapeHtml(d.email || "--")}</div>
        </div>
        <div class="driver-stats-row">
          <div class="driver-stat-col">
            <span class="stat-col-val" style="color:#f59e0b;">⭐ ${d.rating_avg.toFixed(2)}</span>
            <span class="stat-col-lbl">Đánh giá</span>
          </div>
          <div class="driver-stat-col">
            <span class="stat-col-val" style="color:${isHighCancel ? 'var(--status-error)' : 'var(--status-success)'};">${cancelPercent}%</span>
            <span class="stat-col-lbl">Tỷ lệ hủy 30d</span>
          </div>
          <div class="driver-stat-col">
            <span class="stat-col-val">${totalTrips}</span>
            <span class="stat-col-lbl">Tổng chuyến</span>
          </div>
        </div>
        <div class="driver-card-actions">
          <button type="button" class="btn-select-driver">
            💬 Tra cứu hồ sơ tài xế này
          </button>
        </div>
      `;

      card.querySelector(".btn-select-driver").addEventListener("click", () => {
        closeDbModal();
        startNewChat();
        queryInput.value = `Kiểm tra tài xế ${d.full_name} (${d.driver_code}), trong tháng 9/2026 theo quy chế P154 có bị vi phạm tiêu chuẩn do hủy chuyến không, tỷ lệ hủy chuyến là bao nhiêu?`;
        autoResizeTextarea();
        queryInput.focus();
      });

      driversCardsGrid.appendChild(card);
    });
  }

  function filterDriversGrid(term) {
    if (!term) {
      renderDriversGrid(cachedDrivers);
      return;
    }
    const filtered = cachedDrivers.filter(d => 
      (d.full_name && d.full_name.toLowerCase().includes(term)) ||
      (d.driver_code && d.driver_code.toLowerCase().includes(term)) ||
      (d.depot_name && d.depot_name.toLowerCase().includes(term)) ||
      (d.region && d.region.toLowerCase().includes(term))
    );
    renderDriversGrid(filtered);
  }

  function populateTripsDriverSelect(drivers) {
    const curVal = tripsFilterDriver.value;
    tripsFilterDriver.innerHTML = `<option value="">-- Tất cả tài xế --</option>`;
    drivers.forEach(d => {
      const opt = document.createElement("option");
      opt.value = d.driver_id;
      opt.textContent = `${d.driver_code} - ${d.full_name}`;
      tripsFilterDriver.appendChild(opt);
    });
    tripsFilterDriver.value = curVal;
  }

  async function loadDbTrips() {
    tripsStatusSummary.textContent = "Đang tải chuyến đi...";
    const driverId = tripsFilterDriver.value;
    const outcome = tripsFilterOutcome.value;

    let url = "/api/db/trips?limit=100";
    if (driverId) url += `&driver_id=${encodeURIComponent(driverId)}`;
    if (outcome) url += `&outcome=${encodeURIComponent(outcome)}`;

    try {
      const res = await fetch(url);
      if (!res.ok) return;
      cachedTrips = await res.json();
      tripsStatusSummary.textContent = `Hiển thị ${cachedTrips.length} chuyến đi`;
      modalTripsCount.textContent = cachedTrips.length;
      renderTripsTable(cachedTrips);
    } catch (e) {
      tripsStatusSummary.textContent = "Lỗi khi tải chuyến đi.";
    }
  }

  function renderTripsTable(trips) {
    tripsTableBody.innerHTML = "";
    if (trips.length === 0) {
      tripsTableBody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:2rem;color:var(--text-dim);">Không có chuyến đi nào phù hợp với bộ lọc.</td></tr>`;
      return;
    }

    trips.forEach(t => {
      const tr = document.createElement("tr");

      // Find driver name
      const driverObj = cachedDrivers.find(d => d.driver_id === t.driver_id);
      const driverName = driverObj ? `${driverObj.driver_code} (${driverObj.full_name})` : t.driver_id.slice(0, 8);

      const isCompleted = t.outcome === "completed";
      const outcomeBadge = isCompleted
        ? `<span class="badge-outcome outcome-completed">Hoàn thành</span>`
        : `<span class="badge-outcome outcome-cancelled" title="${escapeHtml(t.reason_code || '')}">Đã hủy</span>`;

      const dateStr = formatDateShort(t.start_time);
      const fareStr = t.fare_amount > 0 ? `${t.fare_amount.toLocaleString("vi-VN")} đ` : "0 đ";
      const distStr = `${t.distance_km.toFixed(1)} km`;
      const ratingStr = t.passenger_rating ? `⭐ ${t.passenger_rating}` : "--";

      tr.innerHTML = `
        <td style="font-family:var(--font-mono);font-size:0.75rem;color:var(--primary-cyan);">${t.trip_id.slice(0, 12)}...</td>
        <td><strong>${escapeHtml(driverName)}</strong></td>
        <td style="white-space:nowrap;font-size:0.75rem;color:var(--text-muted);">${dateStr}</td>
        <td>
          <div style="font-size:0.78rem;"><strong>Đón:</strong> ${escapeHtml(t.pickup_address)}</div>
          <div style="font-size:0.78rem;color:var(--text-muted);"><strong>Trả:</strong> ${escapeHtml(t.dropoff_address)}</div>
        </td>
        <td style="font-family:var(--font-mono);white-space:nowrap;">${distStr}</td>
        <td style="font-family:var(--font-mono);white-space:nowrap;color:var(--primary-emerald);">${fareStr}</td>
        <td>${outcomeBadge}</td>
        <td style="white-space:nowrap;">${ratingStr}</td>
      `;
      tripsTableBody.appendChild(tr);
    });
  }

  async function loadDbStats() {
    try {
      const res = await fetch("/api/db/stats");
      if (!res.ok) return;
      const s = await res.json();

      const sizeKb = (s.db_size_bytes / 1024).toFixed(1);

      statsOverviewGrid.innerHTML = `
        <div class="stat-card-lg">
          <div class="stat-card-num">${s.drivers_count}</div>
          <div class="stat-card-title">Tài Xế Vận Hành (Drivers)</div>
          <div class="stat-card-desc">Bao gồm 8 tài xế độc lập trong benchmark GSM với hồ sơ định danh, depot, xe điện và chỉ số vi phạm.</div>
        </div>

        <div class="stat-card-lg">
          <div class="stat-card-num">${s.trips_count}</div>
          <div class="stat-card-title">Chuyến Đi Lưu Trữ (Trips)</div>
          <div class="stat-card-desc">Gồm ${s.completed_trips_count} chuyến hoàn thành và ${s.cancelled_trips_count} chuyến hủy với lộ trình thực tế tại TP.HCM & Hà Nội.</div>
        </div>

        <div class="stat-card-lg">
          <div class="stat-card-num">${s.chat_sessions_count}</div>
          <div class="stat-card-title">Phiên Trò Chuyện (Chat Sessions)</div>
          <div class="stat-card-desc">Lưu trữ ${s.chat_messages_count} tin nhắn lịch sử bao gồm AI Query Plan, dẫn chứng quy chế và đồ thị tri thức.</div>
        </div>

        <div class="stat-card-lg">
          <div class="stat-card-num">${s.context_memories_count}</div>
          <div class="stat-card-title">Bộ Nhớ Ngữ Cảnh (Context Memories)</div>
          <div class="stat-card-desc">Tự động duy trì Tài xế đang kiểm tra, Mốc thời gian, Quy chế và Yêu cầu làm rõ qua các lượt hỏi đáp.</div>
        </div>

        <div class="stat-card-lg" style="grid-column: 1 / -1;">
          <div class="stat-card-num" style="font-size:1.4rem;">${sizeKb} KB</div>
          <div class="stat-card-title">Hồ Sơ Vận Hành Lưu Trữ</div>
          <div class="stat-card-desc">
            Dung lượng lưu trữ cục bộ: ${sizeKb} KB, đồng bộ an toàn và sẵn sàng phục vụ tra cứu.
          </div>
        </div>
      `;
    } catch (e) {
      console.error("Error loading stats:", e);
    }
  }

  // =========================================================================
  // 6. Utility Functions
  // =========================================================================

  function formatRelativeTime(isoStr) {
    if (!isoStr) return "";
    try {
      const d = new Date(isoStr);
      const now = new Date();
      const diffMs = now - d;
      const diffMin = Math.floor(diffMs / 60000);
      const diffHour = Math.floor(diffMin / 60);
      const diffDay = Math.floor(diffHour / 24);

      if (diffMin < 2) return "Vừa xong";
      if (diffMin < 60) return `${diffMin} phút trước`;
      if (diffHour < 24) return `${diffHour} giờ trước`;
      if (diffDay < 7) return `${diffDay} ngày trước`;
      return `${d.getDate()}/${d.getMonth() + 1}`;
    } catch (e) {
      return "";
    }
  }

  function formatDateShort(isoStr) {
    if (!isoStr) return "";
    try {
      const d = new Date(isoStr);
      return `${d.toLocaleDateString("vi-VN")} ${d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}`;
    } catch (e) {
      return isoStr;
    }
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatMarkdown(text) {
    if (!text) return "";
    let html = escapeHtml(text);

    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    // Italic
    html = html.replace(/(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)/g, "<em>$1</em>");
    // Code
    html = html.replace(/`(.*?)`/g, "<code>$1</code>");

    // Citation references like [1], [2], <strong>[1]</strong>
    html = html.replace(/(?:<strong>)?\[(\d+)\](?:<\/strong>)?/g, (match, num) => {
      const idx = parseInt(num, 10);
      if (idx >= 1 && idx <= 30) {
        return `<button class="chat-cite-tag" data-cite-idx="${idx - 1}" type="button" title="Xem chi tiết Dẫn chứng [${idx}]">[${idx}]</button>`;
      }
      return match;
    });

    // Links: [text](url)
    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="chat-link">$1</a>');

    // Headers
    html = html.replace(/^### (.*?)$/gm, "<h4>$1</h4>");
    html = html.replace(/^## (.*?)$/gm, "<h3>$1</h3>");
    html = html.replace(/^# (.*?)$/gm, "<h2>$1</h2>");

    // Section headers like "1. <strong>Kết luận...</strong>"
    html = html.replace(/^(\d+\.\s+<strong>.*?<\/strong>.*)$/gm, '<div class="chat-section-header">$1</div>');

    // Blockquotes: lines starting with &gt;
    html = html.replace(/^(\s*)&gt;\s*(.*?)$/gm, '<blockquote class="chat-blockquote">$2</blockquote>');
    // Merge consecutive blockquotes
    html = html.replace(/<\/blockquote>\s*<blockquote class="chat-blockquote">/g, "<br/>");

    // Markdown tables
    html = html.replace(/((?:\|[^\n]+\|\n?)+)/g, (tableText) => {
      const rows = tableText.trim().split("\n");
      if (rows.length < 2) return tableText;
      let tableHtml = '<div class="table-responsive"><table class="markdown-doc-table">';
      let isHeader = true;
      for (let r of rows) {
        if (!r.trim()) continue;
        if (r.replace(/[|\s-:]/g, "").length === 0) {
          isHeader = false;
          continue;
        }
        const cells = r.split("|").slice(1, -1).map(c => c.trim());
        if (isHeader) {
          tableHtml += '<thead><tr>' + cells.map(c => `<th>${c}</th>`).join('') + '</tr></thead><tbody>';
          isHeader = false;
        } else {
          tableHtml += '<tr>' + cells.map(c => `<td>${c}</td>`).join('') + '</tr>';
        }
      }
      tableHtml += '</tbody></table></div>';
      return tableHtml;
    });

    // Numbered list items: e.g. "1. Thời gian áp dụng: Từ ngày..."
    html = html.replace(/^(\d+)\.\s+(.*?)$/gm, '<li class="num-list-item"><strong class="num-bullet">$1.</strong> $2</li>');
    // Wrap consecutive num list items into ol
    html = html.replace(/((?:<li class="num-list-item">.*?<\/li>\s*)+)/gs, '<ol class="chat-num-list">$1</ol>');

    // Sub-lists: indented with spaces and - or *
    html = html.replace(/^\s{4,}[-*]\s+(.*?)$/gm, '<li class="sub-list-item">$1</li>');
    // Top lists: - or *
    html = html.replace(/^\s{0,3}[-*]\s+(.*?)$/gm, '<li class="list-item">$1</li>');

    // Wrap consecutive list items into ul
    html = html.replace(/((?:<li class="(?:sub-)?list-item">.*?<\/li>\s*)+)/gs, '<ul class="chat-list">$1</ul>');

    // Paragraphs / Newlines
    html = html.replace(/\n\s*\n/g, "</p><p>");
    html = html.replace(/\n/g, "<br/>");

    // Clean up br after blocks
    html = html.replace(/<\/div><br\/>/g, "</div>");
    html = html.replace(/<\/ul><br\/>/g, "</ul>");
    html = html.replace(/<\/ol><br\/>/g, "</ol>");
    html = html.replace(/<\/blockquote><br\/>/g, "</blockquote>");
    html = html.replace(/<p><\/p>/g, "");

    return `<div class="markdown-body">${html}</div>`;
  }

  // Click delegation for inline citation tags inside chat messages
  if (chatMessages) {
    chatMessages.addEventListener("click", (e) => {
      const citeBtn = e.target.closest(".chat-cite-tag");
      if (citeBtn) {
        const idx = parseInt(citeBtn.dataset.citeIdx, 10);
        if (!isNaN(idx)) {
          switchTab("tab-citations");
          highlightCitationCard(idx);
        }
      }
    });
  }
});
