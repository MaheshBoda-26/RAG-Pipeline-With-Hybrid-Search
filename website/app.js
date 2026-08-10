/* ==========================================================================
   RAG Pipeline — app.js
   Motion: Anime.js entrance/scroll choreography.
   Anchor: canvas vector-space point-cloud (Design.md's 3D inspiration,
           expressed as an abstract field here).
   Rule: no spring/elastic easing; prefers-reduced-motion canvases everything.
   ========================================================================== */
(() => {
  "use strict";

  const REDUCED_MOTION =
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));

  document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initCanvas();
    initNav();
    initHero();
    initScrollReveal();
    initFeatureSpotlight();
    initCounters();
    initFlow();
    initDemo();
    initScrollLink();
  });

  /* ========================================================================
     Theme toggle (Design.md: light/dark, persisted)
     ======================================================================== */
  function initTheme() {
    const root = document.documentElement;
    const saved = localStorage.getItem("rag-theme");
    if (saved) root.setAttribute("data-theme", saved);

    const links = $(".nav-links");
    if (!links) return;

    const btn = document.createElement("button");
    btn.className = "theme-toggle";
    btn.type = "button";
    btn.setAttribute("aria-label", "Toggle color theme");
    btn.title = "Toggle theme";
    btn.innerHTML =
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="theme-sun" aria-hidden="true">' +
      '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>' +
      '<svg viewBox="0 0 24 24" fill="currentColor" class="theme-moon" aria-hidden="true">' +
      '<path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z"/></svg>';
    links.prepend(btn);

    btn.addEventListener("click", () => {
      const cur = root.getAttribute("data-theme") === "light" ? "dark" : "light";
      root.setAttribute("data-theme", cur);
      localStorage.setItem("rag-theme", cur);
    });
  }

  /* ========================================================================
     Canvas background — abstract vector-space field.
     A slow-rotating point cloud with nearest-neighbour links, mouse parallax.
     ======================================================================== */
  function initCanvas() {
    const canvas = $("#bg-canvas");
    if (!canvas || !canvas.getContext) return;
    const ctx = canvas.getContext("2d");

    let W = 0, H = 0, DPR = 1;
    let pts = [];
    let mouse = { x: 0, y: 0, tx: 0, ty: 0 };
    let angle = 0;
    let raf = 0;

    const COUNT = Math.min(260, Math.floor((window.innerWidth * window.innerHeight) / 5200));

    function resize() {
      DPR = Math.min(window.devicePixelRatio || 1, 2);
      W = window.innerWidth;
      H = window.innerHeight;
      canvas.width = W * DPR;
      canvas.height = H * DPR;
      canvas.style.width = W + "px";
      canvas.style.height = H + "px";
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
      build();
    }

    function build() {
      const seed = Math.random() * 1000;
      pts = [];
      for (let i = 0; i < COUNT; i++) {
        pts.push({
          // spherical-ish distribution, biased to center for depth
          x: (Math.random() - 0.5) * Math.min(W, 1400),
          y: (Math.random() - 0.5) * Math.min(H, 900),
          z: (Math.random() - 0.5) * 360,
          r: 0.6 + Math.random() * 1.6,
          seed: seed + i,
          hue: Math.random() < 0.18 ? "accent" : "primary",
        });
      }
    }

    function colorFor(type, alpha) {
      const root = getComputedStyle(document.documentElement);
      const hex =
        type === "accent"
          ? root.getPropertyValue("--accent-500").trim()
          : root.getPropertyValue("--primary-400").trim();
      return hexToRgba(hex || (type === "accent" ? "#7C3AED" : "#5B8DF0"), alpha);
    }

    function hexToRgba(hex, a) {
      const m = hex.replace("#", "");
      const v = m.length === 3 ? m.split("").map((c) => c + c).join("") : m;
      const n = parseInt(v, 16);
      return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
    }

    function step(t) {
      const target = 0.0025;
      angle += REDUCED_MOTION ? 0 : target;

      mouse.x += (mouse.tx - mouse.x) * 0.06;
      mouse.y += (mouse.ty - mouse.y) * 0.06;

      const cx = W / 2;
      const cy = H / 2;
      ctx.clearRect(0, 0, W, H);

      // rotate around Y then apply mouse parallax (weak, subtle)
      const rot = angle;
      const cos = Math.cos(rot);
      const sin = Math.sin(rot);

      for (const p of pts) {
        // rotate y-rotated projection
        const yp = p.y;
        const xp = p.x * cos - p.z * sin;
        const zp = p.x * sin + p.z * cos;

        const perspective = 700 / (700 + zp);
        const sx = cx + xp * perspective + mouse.x * 10;
        const sy = cy + yp * perspective + mouse.y * 10;

        if (sx < -40 || sx > W + 40 || sy < -40 || sy > H + 40) continue;

        const glow = Math.max(0, perspective);
        const alpha = Math.min(1, 0.18 + glow * 0.4 + (p.z > 0 ? 0.1 : 0));

        ctx.beginPath();
        ctx.arc(sx, sy, p.r * perspective, 0, Math.PI * 2);
        ctx.fillStyle = colorFor(p.hue, alpha);
        ctx.fill();
      }

      // link near neighbours (only a sample cheap pass)
      const linkTargets = pts.slice(0, Math.min(90, pts.length));
      ctx.lineWidth = 1;
      for (let i = 0; i < linkTargets.length; i++) {
        for (let j = i + 1; j < linkTargets.length; j++) {
          const a = linkTargets[i];
          const b = linkTargets[j];
          const dx = (a.x - b.x) * 1;
          const dy = (a.y - b.y) * 1;
          const dz = (a.z - b.z) * 1;
          const d = dx * dx + dy * dy + dz * dz;
          if (d < 26000) {
            const alpha = (1 - d / 26000) * 0.09;
            ctx.strokeStyle = colorFor("primary", alpha);
            ctx.beginPath();
            ctx.moveTo(
              cx + a.x * (700 / (700 + a.z)) + mouse.x * 10,
              cy + a.y * (700 / (700 + a.z)) + mouse.y * 10
            );
            ctx.lineTo(
              cx + b.x * (700 / (700 + b.z)) + mouse.x * 10,
              cy + b.y * (700 / (700 + b.z)) + mouse.y * 10
            );
            ctx.stroke();
          }
        }
      }

      if (t < Infinity) raf = requestAnimationFrame(step);
    }

    function onPointer(e) {
      mouse.tx = (e.clientX / W - 0.5) * 2;
      mouse.ty = (e.clientY / H - 0.5) * 2;
    }

    resize();
    step(0);
    window.addEventListener("resize", resize);
    window.addEventListener("pointermove", onPointer, { passive: true });

    // pause when tab hidden
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        cancelAnimationFrame(raf);
      } else {
        step(0);
      }
    });

    // stop entirely when the page is the canvas of a reduced-motion user
    if (REDUCED_MOTION) {
      cancelAnimationFrame(raf);
    }
  }

  /* ========================================================================
     Navigation: mobile toggle, active-link highlight, close on click.
     ======================================================================== */
  function initNav() {
    const toggle = $(".nav-toggle");
    const links = $(".nav-links");
    const menuAnchors = $$(".nav-links a");

    toggle?.addEventListener("click", () => {
      const open = !links.classList.contains("open");
      links.classList.toggle("open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });

    menuAnchors.forEach((a) => {
      a.addEventListener("click", () => {
        links.classList.remove("open");
        toggle?.setAttribute("aria-expanded", "false");
      });
    });

    // active section highlight
    const sections = $$("section[id]");
    const navLinks = $$('.nav-link[href^="#"]');
    const spy = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            const id = e.target.id;
            navLinks.forEach((l) =>
              l.classList.toggle("active", l.getAttribute("href") === "#" + id)
            );
          }
        });
      },
      { rootMargin: "-45% 0px -50% 0px" }
    );
    sections.forEach((s) => spy.observe(s));
  }

  /* ========================================================================
     Hero entrance (Anime.js timeline).
     ======================================================================== */
  function initHero() {
    if (REDUCED_MOTION) return;

    if (typeof anime === "undefined") {
      // graceful fallback -> CSS handles opacity via reveal
      return;
    }

    const tl = anime.timeline({
      duration: 900,
      easing: "cubicBezier(0.16, 1, 0.3, 1)",
    });

    tl.add({
      targets: ".hero-badge",
      opacity: [0, 1],
      translateY: [14, 0],
    })
      .add(
        {
          targets: ".title-line",
          opacity: [0, 1],
          translateY: [30, 0],
          delay: anime.stagger(120),
        },
        "-=500"
      )
      .add(
        {
          targets: ".hero-description",
          opacity: [0, 1],
          translateY: [20, 0],
        },
        "-=650"
      )
      .add(
        {
          targets: ".hero-cta .btn",
          opacity: [0, 1],
          translateY: [18, 0],
          delay: anime.stagger(120),
        },
        "-=650"
      )
      .add(
        {
          targets: ".stat",
          opacity: [0, 1],
          translateY: [14, 0],
          delay: anime.stagger(90),
        },
        "-=650"
      )
      .add(
        {
          targets: ".code-window",
          opacity: [0, 1],
          translateX: [40, 0],
          scale: [0.96, 1],
        },
        "-=1200"
      )
      .add(
        {
          targets: ".flow-step",
          opacity: [0, 1],
          translateY: [16, 0],
          delay: anime.stagger(80),
        },
        "-=700"
      );
  }

  /* ========================================================================
     Scroll reveal — sections & staggered cards.
     ======================================================================== */
  function initScrollReveal() {
    const els = $$(".section-header, .feature-card, .arch-stage, .arch-code, .step-card, .config-reference, .demo-interface, .hero-visual");

    if (!("IntersectionObserver" in window)) {
      els.forEach((e) => e.classList.remove("reveal"));
      return;
    }

    if (REDUCED_MOTION) {
      els.forEach((e) => e.classList.remove("reveal"));
      return;
    }

    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (!e.isIntersecting) return;
          const el = e.target;
          const isCard = el.classList.contains("feature-card") ||
                         el.classList.contains("step-card") ||
                         el.classList.contains("arch-stage");
          const isGroup = el.classList.contains("demo-interface");

          el.classList.remove("reveal");

          const targets = isCard ? el : el;
          const delayOf = (i) => (isGroup ? i * 90 : isCard ? 0 : 0);

          if (isGroup) {
            const kids = $$(":scope > *", el);
            anime({
              targets: kids,
              opacity: [0, 1],
              translateY: [22, 0],
              delay: anime.stagger(90),
              duration: 700,
              easing: "cubicBezier(0.16, 1, 0.3, 1)",
            });
          } else if (isCard) {
            // stagger sibling cards as a batch
            const group = el.parentElement.querySelectorAll(
              el.classList.contains("feature-card") ? ".feature-card" : ".step-card"
            );
            if (group.length > 1) {
              const idx = Array.from(group).indexOf(el);
              anime({
                targets: el,
                opacity: [0, 1],
                translateY: [26, 0],
                delay: idx * 80,
                duration: 700,
                easing: "cubicBezier(0.16, 1, 0.3, 1)",
              });
            } else {
              anime({ targets: el, opacity: [0, 1], translateY: [26, 0], duration: 700, easing: "cubicBezier(0.16, 1, 0.3, 1)" });
            }
          } else {
            anime({ targets: targets, opacity: [0, 1], translateY: [24, 0], duration: 700, easing: "cubicBezier(0.16, 1, 0.3, 1)" });
          }

          io.unobserve(el);
        });
      },
      { threshold: 0.12 }
    );

    els.forEach((e) => io.observe(e));
  }

  /* ========================================================================
     Feature card cursor spotlight (CSS --mx/--my).
     ======================================================================== */
  function initFeatureSpotlight() {
    $$(".feature-card").forEach((card) => {
      card.addEventListener("pointermove", (e) => {
        const r = card.getBoundingClientRect();
        const mx = ((e.clientX - r.left) / r.width) * 100;
        const my = ((e.clientY - r.top) / r.height) * 100;
        card.style.setProperty("--mx", mx.toFixed(1) + "%");
        card.style.setProperty("--my", my.toFixed(1) + "%");
        card.classList.add("spotlight");
      });
      card.addEventListener("pointerleave", () => card.classList.remove("spotlight"));
    });
  }

  /* ========================================================================
     Stat counters.
     ======================================================================== */
  function initCounters() {
    const stats = $$("[data-count]");
    if (!stats.length) return;

    const fmt = (n) => {
      if ((n - Math.floor(n)) !== 0) return n.toFixed(1);
      return Math.round(n).toString();
    };

    const run = (el) => {
      const target = parseFloat(el.getAttribute("data-count"));
      const isFloat = target % 1 !== 0;
      const suffix = !isFloat && target > 90 ? "%" : !isFloat ? "" : "";
      let start = null;
      const dur = REDUCED_MOTION ? 0 : 1100;
      const tick = (ts) => {
        if (!start) start = ts;
        const p = Math.min(1, (ts - start) / dur);
        const eased = 1 - Math.pow(1 - p, 3);
        el.textContent = isFloat ? (target * eased).toFixed(1) : Math.round(target * eased).toString() + suffix;
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    };

    if (REDUCED_MOTION) {
      stats.forEach((el) => {
        const target = parseFloat(el.getAttribute("data-count"));
        el.textContent = target % 1 !== 0 ? target.toFixed(1) : target.toString() + (target > 90 ? "%" : "");
      });
      return;
    }

    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (!e.isIntersecting) return;
          run(e.target);
          io.unobserve(e.target);
        });
      },
      { threshold: 0.4 }
    );
    stats.forEach((s) => io.observe(s));
  }

  /* ========================================================================
     Hero flow-diagram — auto-advancing highlight pass.
     ======================================================================== */
  function initFlow() {
    const steps = $$(".flow-step");
    if (!steps.length || REDUCED_MOTION) return;

    let i = 0;
    setInterval(() => {
      steps.forEach((s) => {
        s.style.borderColor = "";
        s.style.background = "";
        s.style.boxShadow = "";
      });
      const step = steps[i % steps.length];
      step.style.borderColor = "var(--primary-400)";
      step.style.boxShadow = "0 10px 30px -12px var(--glow-primary)";
      i++;
    }, 2400);
  }

  /* ========================================================================
     Live demo — weights, sample questions, ask flow (API + graceful mock).
     ======================================================================== */
  function initDemo() {
    const dense = $("#dense-weight");
    const sparse = $("#sparse-weight");
    const denseVal = $("#dense-value");
    const sparseVal = $("#sparse-value");
    const query = $("#query");
    const askBtn = $("#ask-btn");
    const area = $("#response-area");
    const ingestBtn = $("#ingest-btn");
    const samples = $$(".question-list li");

    if (dense && denseVal) {
      const sync = () => (denseVal.textContent = dense.value);
      dense.addEventListener("input", sync);
      sync();
    }
    if (sparse && sparseVal) {
      const sync = () => (sparseVal.textContent = sparse.value);
      sparse.addEventListener("input", sync);
      sync();
    }

    samples.forEach((li) => {
      li.addEventListener("click", () => {
        if (query) query.value = li.dataset.q || li.textContent;
        query?.focus();
      });
    });

    ingestBtn?.addEventListener("click", async () => {
      const url = $("#api-url")?.value || "http://localhost:8000";
      setBtnLoading(ingestBtn, true);
      toast("Ingesting sample docs…");
      try {
        const res = await fetch(url + "/v1/ingest", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: "./sample_docs" }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || res.status);
        toast("Ingest complete — " + ((data && data.chunks) || "corpus ready") + " chunks");
      } catch (e) {
        const msg = e && e.message ? String(e.message) : "unknown";
        if (/ECONNREFUSED|Failed to fetch|NetworkError/i.test(msg)) {
          toast("API not running. Start with: uvicorn api:app --reload");
        } else {
          toast("Ingest error: " + msg);
        }
      } finally {
        setBtnLoading(ingestBtn, false);
      }
    });

    askBtn?.addEventListener("click", () => {
      const q = (query?.value || "").trim();
      if (!q) {
        toast("Enter a question first");
        query?.focus();
        return;
      }
      ask(q);
    });
    query?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") askBtn?.click();
    });

    async function ask(q) {
      const url = $("#api-url")?.value || "http://localhost:8000";
      setBtnLoading(askBtn, true);
      renderThinking(area);
      try {
        const denseW = dense ? parseFloat(dense.value) : 0.7;
        const sparseW = sparse ? parseFloat(sparse.value) : 0.3;
        const res = await fetch(url + "/v1/ask", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: q, dense_weight: denseW, sparse_weight: sparseW }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || res.status);
        renderAnswer(area, data, q);
      } catch (e) {
        const msg = e && e.message ? String(e.message) : "unknown";
        if (/ECONNREFUSED|Failed to fetch|NetworkError/i.test(msg)) {
          // offline -> realistic mock so the page stays live
          toast("API offline — showing sample response");
          renderAnswer(area, mockAnswer(q), q, true);
        } else {
          toast("Error: " + msg);
          renderError(area);
        }
      } finally {
        setBtnLoading(askBtn, false);
      }
    }

    function setBtnLoading(btn, on) {
      if (!btn) return;
      btn.classList.toggle("loading", on);
      btn.disabled = on;
    }

    function renderThinking(area_) {
      area_.innerHTML =
        '<div class="response-placeholder"><div style="text-align:center">' +
        '<span style="display:inline-block;width:26px;height:26px;border-radius:50%;border:3px solid var(--surface-2);border-top-color:var(--primary-400);animation:spin .7s linear infinite"></span>' +
        '<p style="margin-top:12px">Retrieving, reranking & grounding…</p></div></div>';
    }

    function renderError(area_) {
      area_.innerHTML = '<div class="response-placeholder"><p>No response generated.</p></div>';
    }

    function renderAnswer(area_, data, q, isMock = false) {
      const answer = (data.answer || "").replace(/\n/g, "\n");
      const conf = data.confidence || data.confidence_score || {};
      const sources = data.sources || null;

      let html = '<div class="response-answer">';
      html += '<div class="answer-text">' + linkifyCitations(escapeHtml(answer)) + "</div>";

      // confidence breakdown
      const confMap = [
        ["retrieval", conf.retrieval_confidence],
        ["citation coverage", conf.citation_coverage],
        ["completeness", conf.completeness],
      ].filter((r) => typeof r[1] === "number");

      if (confMap.length || typeof conf.composite === "number") {
        html += '<div class="confidence-grid">';
        confMap.forEach(([label, val]) => {
          const pct = Math.round(val * 100);
          html +=
            '<span class="conf-label">' + label + '</span>' +
            '<span class="conf-val">' + pct + "%</span>" +
            '<div class="conf-bar"><div class="conf-fill" data-w="' + val.toFixed(2) + '"></div></div>';
        });
        if (typeof conf.composite === "number") {
          const cp = Math.round(conf.composite * 100);
          html +=
            '<span class="conf-label" style="font-weight:600">composite</span>' +
            '<span class="conf-val" style="color:var(--accent-500)">' + cp + "%</span>";
        }
        html += "</div>";
      }

      if (isMock) {
        html += '<p style="margin-top:14px;font-size:12.5px;color:var(--text-3)">' +
          "Live API offline — this is a static sample. Start <code>uvicorn api:app --reload</code> for real answers.</p>";
      }

      if (sources && sources.length) {
        html += '<div class="sources-list"><h5>Sources</h5>';
        sources.forEach((s, i) => {
          const path = s.source || s.path || s.file || "untracked";
          html += '<div class="source-item"><span class="src-num">[' + (i + 1) + "]</span>";
          html += '<span class="src-path">' + escapeHtml(path) + "</span>";
          html += "<span>" + escapeHtml(s.section || s.title || s.heading || "") + "</span></div>";
        });
        html += "</div>";
      }

      html += "</div>";
      area_.innerHTML = html;

      // animate confidence bars
      setTimeout(() => {
        $$(".conf-fill", area_).forEach((f) => {
          const w = parseFloat(f.dataset.w);
          f.style.width = Math.min(1, w) * 100 + "%";
        });
      }, 40);

      if (REDUCED_MOTION) () => {};
    }

    function linkifyCitations(text) {
      return text.replace(/\[(\d+)\]/g, '<span class="cite">$1</span>');
    }

    function escapeHtml(s) {
      return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function mockAnswer(q) {
      const snippet = q || "the question";
      return {
        answer:
          "To authenticate, supply an API key in the Authorization header [1] or use OAuth2 [2]. " +
          "Rate limits are enforced at 1000 req/min; exceeding them returns 429 with a Retry-After header [3]. " +
          "For " + snippet + ", refer to the specific endpoint documentation in the indexed set [4].",
        confidence: {
          retrieval_confidence: 0.87,
          citation_coverage: 1.0,
          completeness: 0.92,
          composite: 0.93,
        },
        sources: [
          { source: "sample_docs/authentication.md", section: "API Keys" },
          { source: "sample_docs/authentication.md", section: "OAuth2" },
          { source: "sample_docs/rate_limits.md", section: "Rate Limits" },
          { source: "sample_docs/endpoints.md", section: "Endpoints" },
        ],
      };
    }
  }

  /* ========================================================================
     Scroll cue link (hero-scroll -> next section)
     ======================================================================== */
  function initScrollLink() {
    const cue = $(".hero-scroll");
    const next = $(".features");
    cue?.addEventListener("click", () => {
      const target = next || $("#features");
      if (target) target.scrollIntoView({ behavior: REDUCED_MOTION ? "auto" : "smooth" });
    });
  }

  /* ========================================================================
     Toast
     ======================================================================== */
  function toast(msg) {
    let t = $(".toast");
    if (!t) {
      t = document.createElement("div");
      t.className = "toast";
      t.setAttribute("role", "status");
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(t._timer);
    t._timer = setTimeout(() => t.classList.remove("show"), 3200);
  }
})();