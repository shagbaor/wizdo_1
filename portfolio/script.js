/* WIZDO — interactions */
(() => {
  const $ = (s, c = document) => c.querySelector(s);
  const $$ = (s, c = document) => [...c.querySelectorAll(s)];
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const finePointer = matchMedia("(hover: hover) and (pointer: fine)").matches;

  /* ---------- Loader ---------- */
  const finishLoad = () => requestAnimationFrame(() => document.body.classList.add("loaded"));
  if (document.readyState === "complete") setTimeout(finishLoad, 500);
  else window.addEventListener("load", () => setTimeout(finishLoad, 500));
  setTimeout(finishLoad, 2500); // safety net

  $("#year").textContent = new Date().getFullYear();

  /* ---------- Reveal on scroll ---------- */
  const io = new IntersectionObserver(
    (entries) => entries.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
    }),
    { threshold: 0.12, rootMargin: "0px 0px -8% 0px" }
  );
  $$(".reveal").forEach((el) => io.observe(el));

  /* ---------- Count-up ---------- */
  const countIO = new IntersectionObserver((entries) => entries.forEach((e) => {
    if (!e.isIntersecting) return;
    const el = e.target, to = +el.dataset.to, dur = 1800;
    countIO.unobserve(el);
    if (reduceMotion) { el.textContent = to; return; }
    const t0 = performance.now();
    const tick = (t) => {
      const p = Math.min((t - t0) / dur, 1);
      el.textContent = Math.round(to * (1 - Math.pow(1 - p, 4)));
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }), { threshold: 0.5 });
  $$(".count").forEach((el) => countIO.observe(el));

  /* ---------- Rotating "currently" text ---------- */
  const rot = $("#rotator");
  const phrases = ["Community Expansion", "Launch Campaigns", "Creator Programs", "Narrative Building", "Ecosystem Growth"];
  let ri = 0;
  if (rot && !reduceMotion) {
    setInterval(() => {
      rot.classList.add("out");
      setTimeout(() => {
        ri = (ri + 1) % phrases.length;
        rot.textContent = phrases[ri];
        rot.classList.remove("out");
        rot.classList.add("in");
        void rot.offsetWidth;
        rot.classList.remove("in");
      }, 350);
    }, 2800);
  }

  /* ---------- Scroll: progress, nav state, hide on scroll down ---------- */
  const navWrap = $(".nav-wrap");
  const progress = $(".progress");
  let lastY = scrollY, ticking = false;
  const onScroll = () => {
    const y = scrollY;
    const max = document.documentElement.scrollHeight - innerHeight;
    progress.style.setProperty("--p", max > 0 ? y / max : 0);
    navWrap.classList.toggle("scrolled", y > 20);
    if (!document.body.classList.contains("locked")) {
      navWrap.classList.toggle("hide", y > lastY && y > 400);
    }
    lastY = y;
    ticking = false;
  };
  addEventListener("scroll", () => { if (!ticking) { requestAnimationFrame(onScroll); ticking = true; } }, { passive: true });
  onScroll();

  /* ---------- Active nav link + sliding pill ---------- */
  const links = $$("[data-link]");
  const pill = $(".nav-pill");
  const movePill = (a) => {
    if (!a || !pill) { if (pill) pill.style.opacity = 0; return; }
    pill.style.width = a.offsetWidth + "px";
    pill.style.transform = `translateX(${a.offsetLeft}px)`;
    pill.style.opacity = 1;
  };
  let current = null;
  const sectionIO = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (!e.isIntersecting) return;
      const a = links.find((l) => l.getAttribute("href") === "#" + e.target.id);
      links.forEach((l) => l.classList.toggle("active", l === a));
      current = a || null;
      movePill(current);
    });
  }, { rootMargin: "-45% 0px -50% 0px" });
  $$("main section[id]").forEach((s) => sectionIO.observe(s));
  links.forEach((l) => {
    l.addEventListener("mouseenter", () => movePill(l));
    l.addEventListener("mouseleave", () => movePill(current));
  });
  addEventListener("resize", () => movePill(current));

  /* ---------- Mobile menu (circular reveal from the burger) ---------- */
  const burger = $(".burger"), menu = $("#menu");
  const setMenu = (open) => {
    const r = burger.getBoundingClientRect();
    menu.style.setProperty("--ox", r.left + r.width / 2 + "px");
    menu.style.setProperty("--oy", r.top + r.height / 2 + "px");
    burger.setAttribute("aria-expanded", open);
    burger.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    menu.classList.toggle("open", open);
    menu.setAttribute("aria-hidden", !open);
    document.body.classList.toggle("locked", open);
    document.body.classList.toggle("menu-open", open);
    navWrap.classList.remove("hide");
  };
  burger.addEventListener("click", () => setMenu(burger.getAttribute("aria-expanded") !== "true"));
  menu.addEventListener("click", (e) => {
    const a = e.target.closest("a");
    if (!a) return;
    const href = a.getAttribute("href");
    if (href && href.startsWith("#")) {
      e.preventDefault();
      setMenu(false);
      // wait for the overlay to start closing, then scroll
      setTimeout(() => $(href)?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" }), 250);
    } else {
      setMenu(false);
    }
  });
  addEventListener("keydown", (e) => { if (e.key === "Escape") setMenu(false); });
  matchMedia("(min-width: 861px)").addEventListener("change", (m) => m.matches && setMenu(false));

  if (reduceMotion) return;

  /* ---------- Cursor spotlight ---------- */
  if (finePointer) {
    const spot = $(".spotlight");
    addEventListener("pointermove", (e) => {
      spot.style.setProperty("--sx", e.clientX + "px");
      spot.style.setProperty("--sy", e.clientY + "px");
    }, { passive: true });
  }

  /* ---------- Card glow follow ---------- */
  $$(".card, .project, .service, .stat-card, .stack-col, .contact-link").forEach((el) => {
    el.addEventListener("pointermove", (e) => {
      const r = el.getBoundingClientRect();
      el.style.setProperty("--mx", e.clientX - r.left + "px");
      el.style.setProperty("--my", e.clientY - r.top + "px");
    }, { passive: true });
  });

  if (!finePointer) return;

  /* ---------- 3D tilt ---------- */
  $$(".tilt").forEach((el) => {
    const max = el.classList.contains("id-card") ? 12 : 6;
    const sheen = el.querySelector(".id-sheen");
    el.addEventListener("pointerenter", () => el.classList.add("tilting"));
    el.addEventListener("pointermove", (e) => {
      const r = el.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width, py = (e.clientY - r.top) / r.height;
      el.style.setProperty("--ry", (px - 0.5) * max + "deg");
      el.style.setProperty("--rx", (0.5 - py) * max + "deg");
      if (sheen) el.style.setProperty("--shx", 100 - px * 100 + "%");
    });
    el.addEventListener("pointerleave", () => {
      el.classList.remove("tilting");
      el.style.setProperty("--rx", "0deg");
      el.style.setProperty("--ry", "0deg");
    });
  });
  // ID card needs explicit transform since it isn't a .reveal element
  const id = $(".id-card");
  if (id) id.style.transform = "perspective(1000px) rotateX(var(--rx)) rotateY(var(--ry))";

  /* ---------- Magnetic buttons ---------- */
  $$(".magnetic").forEach((el) => {
    const strength = el.classList.contains("contact-link") ? 0.08 : 0.25;
    el.addEventListener("pointermove", (e) => {
      const r = el.getBoundingClientRect();
      el.style.setProperty("--tx", (e.clientX - r.left - r.width / 2) * strength + "px");
      el.style.setProperty("--ty", (e.clientY - r.top - r.height / 2) * strength + "px");
    });
    el.addEventListener("pointerleave", () => {
      el.style.setProperty("--tx", "0px");
      el.style.setProperty("--ty", "0px");
    });
  });

  /* ---------- Hero parallax ---------- */
  const visual = $(".hero-visual");
  const blobs = $$(".blob");
  addEventListener("pointermove", (e) => {
    const x = e.clientX / innerWidth - 0.5, y = e.clientY / innerHeight - 0.5;
    if (visual) visual.style.translate = `${x * -14}px ${y * -14}px`;
    blobs.forEach((b, i) => (b.style.translate = `${x * (i + 1) * 18}px ${y * (i + 1) * 18}px`));
  }, { passive: true });
})();
