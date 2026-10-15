/* Premium: тонкие линии шапки, сборка фраз по прокрутке, вход бумаги.
   gsap-core, gsap-timeline, gsap-scrolltrigger, ScrollTo.
   Только transform и autoAlpha. */
gsap.registerPlugin(ScrollTrigger, ScrollToPlugin);
gsap.defaults({ duration: 0.45, ease: "power2.out" });

const prefersReduce = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const scrollToId = (id) => {
  const target = document.querySelector(id);
  if (!target) return;
  if (prefersReduce()) {
    target.scrollIntoView({ block: "start" });
    return;
  }
  gsap.to(window, {
    duration: 0.8,
    ease: "power2.inOut",
    scrollTo: { y: id, offsetY: 0 },
  });
};

document.querySelector("#to-kak").addEventListener("click", (event) => {
  event.preventDefault();
  scrollToId("#kak");
});

const reader = document.querySelector("#reader");
const readerTitle = document.querySelector("#reader-title");
const readerBody = document.querySelector("#reader-body");
const readerClose = document.querySelector("#reader-close");
let readerReturn = null;
let lockedScroll = 0;

const openReader = (button) => {
  readerTitle.textContent = button.querySelector(".topic-name").textContent;
  readerBody.innerHTML = button.querySelector(".topic-full").innerHTML;
  reader.hidden = false;
  document.body.classList.add("is-reading");
  lockedScroll = window.scrollY;
  document.body.style.top = `-${lockedScroll}px`;
  document.body.style.position = "fixed";
  document.body.style.width = "100%";
  readerReturn = button;
  if (prefersReduce()) {
    gsap.set(".reader-sheet", { autoAlpha: 1, y: 0 });
  } else {
    gsap.fromTo(
      ".reader-sheet",
      { y: 18, autoAlpha: 0 },
      { y: 0, autoAlpha: 1, duration: 0.4, ease: "power2.out" }
    );
  }
  readerClose.focus();
};

const closeReader = () => {
  const finish = () => {
    reader.hidden = true;
    document.body.classList.remove("is-reading");
    document.body.style.position = "";
    document.body.style.top = "";
    document.body.style.width = "";
    window.scrollTo(0, lockedScroll);
    ScrollTrigger.refresh();
    if (readerReturn) readerReturn.focus();
  };
  if (prefersReduce()) {
    finish();
    return;
  }
  gsap.to(".reader-sheet", {
    y: 12,
    autoAlpha: 0,
    duration: 0.25,
    ease: "power2.in",
    onComplete: finish,
  });
};

document.querySelectorAll(".topic").forEach((button) => {
  const line = button.querySelector(".topic-line");
  const icon = button.querySelector(".topic-press");
  const show = () => {
    if (prefersReduce()) return;
    gsap.to(line, { scaleX: 1, duration: 0.45, ease: "power2.out", overwrite: "auto" });
    gsap.to(icon, { y: 3, duration: 0.35, ease: "power2.out", overwrite: "auto" });
  };
  const hide = () => {
    if (prefersReduce()) return;
    gsap.to(line, { scaleX: 0, duration: 0.3, ease: "power2.in", overwrite: "auto" });
    gsap.to(icon, { y: 0, duration: 0.35, ease: "power2.out", overwrite: "auto" });
  };
  button.addEventListener("click", () => openReader(button));
  button.addEventListener("pointerenter", show);
  button.addEventListener("pointerleave", hide);
  button.addEventListener("focus", show);
  button.addEventListener("blur", hide);
});

readerClose.addEventListener("click", closeReader);

reader.addEventListener("click", (event) => {
  if (event.target === reader) closeReader();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !reader.hidden) closeReader();
});

document.querySelectorAll(".btn").forEach((button) => {
  button.addEventListener("pointerdown", () => {
    if (prefersReduce()) return;
    gsap.to(button, { scale: 0.98, duration: 0.12, ease: "power2.out", overwrite: "auto" });
  });
  const release = () => {
    if (prefersReduce()) return;
    gsap.to(button, { scale: 1, duration: 0.18, ease: "power2.out", overwrite: "auto" });
  };
  button.addEventListener("pointerup", release);
  button.addEventListener("pointerleave", release);
});

const mm = gsap.matchMedia();

mm.add("(prefers-reduced-motion: no-preference)", () => {
  const intro = gsap.timeline({ defaults: { ease: "power2.out" } });
  intro
    .from(".hair-h", { scaleX: 0, duration: 0.8, stagger: 0.08 }, 0)
    .from(".hair-v", { scaleY: 0, duration: 0.5, stagger: 0.06 }, 0.15)
    .from(".mast-row a, .mast-row p", { autoAlpha: 0, duration: 0.4, stagger: 0.05 }, 0.2)
    .from(".portrait-wrap img", { scale: 1.05, duration: 1.1 }, 0)
    .from(".room-copy h1", { y: 24, autoAlpha: 0, duration: 0.7 }, 0.18)
    .from(".room-copy .lead, #to-kak", { y: 16, autoAlpha: 0, duration: 0.5, stagger: 0.08 }, 0.32);

  const glow = gsap.to(".room-light", {
    opacity: 0.55,
    duration: 3.6,
    repeat: -1,
    yoyo: true,
    ease: "sine.inOut",
  });

  const drift = gsap.to(".portrait-wrap img", {
    yPercent: -4,
    ease: "none",
    scrollTrigger: {
      trigger: ".room",
      start: "top top",
      end: "bottom top",
      scrub: 0.6,
    },
  });

  const spine = gsap.fromTo(
    ".pass-spine",
    { scaleY: () => window.innerHeight / document.documentElement.scrollHeight },
    {
      scaleY: 1,
      ease: "none",
      scrollTrigger: {
        trigger: document.body,
        start: "top top",
        end: "bottom bottom",
        scrub: 0.6,
      },
    }
  );

  const crosses = gsap.utils.toArray(".pass-h").map((line) =>
    gsap.to(line, {
      scaleX: 1,
      ease: "none",
      scrollTrigger: {
        trigger: line.parentElement,
        start: "top 80%",
        end: "top 35%",
        scrub: 0.6,
      },
    })
  );

  const tap = gsap.to(".press-dot", {
    scale: 0.55,
    duration: 0.9,
    repeat: -1,
    yoyo: true,
    ease: "sine.inOut",
  });

  gsap.set(".rise", { y: 22, autoAlpha: 0 });
  const batch = ScrollTrigger.batch(".rise", {
    start: "top 86%",
    once: true,
    onEnter: (elements) => {
      gsap.to(elements, {
        y: 0,
        autoAlpha: 1,
        duration: 0.55,
        stagger: 0.06,
        ease: "power2.out",
        overwrite: "auto",
      });
    },
  });

  return () => {
    intro.kill();
    glow.kill();
    drift.kill();
    spine.kill();
    tap.kill();
    crosses.forEach((item) => item.kill());
    batch.forEach((item) => item.kill());
    gsap.set(".rise", { clearProps: "all" });
  };
});

mm.add("(min-width: 861px) and (prefers-reduced-motion: no-preference)", () => {
  const story = gsap.timeline({
    defaults: { ease: "none" },
    scrollTrigger: {
      trigger: "#kak",
      start: "top top",
      end: "+=1200",
      pin: true,
      scrub: 0.6,
      anticipatePin: 1,
    },
  });
  story
    .fromTo(".story-rule", { scaleY: 0.18 }, { scaleY: 1, duration: 0.7 }, 0)
    .from(".line:nth-child(n + 2)", { y: 20, autoAlpha: 0, stagger: 0.32, duration: 0.4 }, 0.15);

  return () => story.kill();
});

mm.add("(max-width: 860px) and (prefers-reduced-motion: no-preference)", () => {
  const rule = gsap.from(".story-rule", {
    scaleY: 0,
    duration: 0.6,
    ease: "power2.out",
    scrollTrigger: { trigger: ".story", start: "top 80%", once: true },
  });
  const lines = gsap.from(".line:nth-child(n + 2)", {
    y: 16,
    autoAlpha: 0,
    stagger: 0.12,
    duration: 0.45,
    scrollTrigger: { trigger: ".story", start: "top 80%", once: true },
  });
  return () => {
    rule.kill();
    lines.kill();
  };
});
