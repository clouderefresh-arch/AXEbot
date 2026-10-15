/* Premium motion: one entrance, then only the answer to a tap.
   gsap-core, gsap-timeline, gsap-scrolltrigger, ScrollTo from gsap-plugins.
   Transforms and autoAlpha only. matchMedia covers reduced motion. */
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
    duration: 0.7,
    ease: "power2.inOut",
    scrollTo: { y: id, offsetY: 0 },
  });
};

document.querySelector("#to-kak").addEventListener("click", (event) => {
  event.preventDefault();
  scrollToId("#kak");
});

const clauses = [...document.querySelectorAll(".clause")];
const meter = document.querySelector("#meter-fill");
const count = document.querySelector("#count");
const openHod = document.querySelector("#open-hod");
const hod = document.querySelector("#hod");

const marked = () => clauses.filter((button) => button.getAttribute("aria-pressed") === "true").length;

const paintMeter = () => {
  const done = marked();
  count.textContent = `Отмечено ${done} из 3`;
  openHod.disabled = done < 3;
  if (prefersReduce()) {
    gsap.set(meter, { scaleX: done / 3 });
    return;
  }
  gsap.to(meter, {
    scaleX: done / 3,
    duration: 0.4,
    ease: "power2.out",
    overwrite: "auto",
  });
};

clauses.forEach((button) => {
  const mark = button.querySelector(".mark i");
  button.addEventListener("click", () => {
    const next = button.getAttribute("aria-pressed") !== "true";
    button.setAttribute("aria-pressed", next ? "true" : "false");
    if (prefersReduce()) {
      gsap.set(mark, { scale: next ? 1 : 0 });
    } else {
      gsap.to(mark, {
        scale: next ? 1 : 0,
        duration: 0.2,
        ease: "power2.out",
        overwrite: "auto",
      });
    }
    paintMeter();
  });
});

document.querySelectorAll(".btn").forEach((button) => {
  button.addEventListener("pointerdown", () => {
    if (button.disabled || prefersReduce()) return;
    gsap.to(button, { scale: 0.98, duration: 0.12, ease: "power2.out", overwrite: "auto" });
  });
  const release = () => {
    if (prefersReduce()) return;
    gsap.to(button, { scale: 1, duration: 0.18, ease: "power2.out", overwrite: "auto" });
  };
  button.addEventListener("pointerup", release);
  button.addEventListener("pointerleave", release);
});

openHod.addEventListener("click", () => {
  if (openHod.disabled) return;
  const firstOpen = !hod.classList.contains("is-open");
  hod.classList.add("is-open");
  if (firstOpen && !prefersReduce()) {
    gsap.from("#hod .column", {
      y: 24,
      autoAlpha: 0,
      duration: 0.6,
      ease: "power2.out",
    });
  }
  ScrollTrigger.refresh();
  scrollToId("#hod");
});

const mm = gsap.matchMedia();

mm.add("(prefers-reduced-motion: no-preference)", () => {
  const intro = gsap.timeline({ defaults: { ease: "power2.out" } });
  intro
    .from(".portrait-wrap img", { scale: 1.05, duration: 1.1 }, 0)
    .from(".room-copy h1", { y: 24, autoAlpha: 0, duration: 0.7 }, 0.12)
    .from(".room-copy .lead, #to-kak", { y: 16, autoAlpha: 0, duration: 0.5, stagger: 0.08 }, 0.28);

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

  return () => {
    intro.kill();
    glow.kill();
    drift.kill();
  };
});
