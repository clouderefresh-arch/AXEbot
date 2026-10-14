/* Проверка навыков:
   motion-design — playful-сборка иллюстрации, premium-текст, три слоя
   gsap-core — from/to, autoAlpha, transform aliases, matchMedia
   gsap-timeline — одна последовательность вместо цепочки delay
   gsap-scrolltrigger — карточки слоя входят при прокрутке, once
   gsap-plugins — ScrollToPlugin для кнопки
   gsap-utils — clamp для сдвига курсора
   gsap-performance — только x/y/scale/rotation/autoAlpha и quickTo
*/
gsap.registerPlugin(ScrollTrigger, ScrollToPlugin);
gsap.defaults({ duration: 0.5, ease: "power3.out" });

const stage = document.querySelector("#stage");
const page = document.querySelector("#page");
const mm = gsap.matchMedia();

mm.add(
  {
    reduce: "(prefers-reduced-motion: reduce)",
    motion: "(prefers-reduced-motion: no-preference)",
  },
  (context) => {
    const { reduce } = context.conditions;
    const intro = gsap.timeline({ paused: true, defaults: { ease: "power3.out" } });

    if (reduce) {
      return;
    }

    gsap.set(".monitor", { rotationY: -8, transformOrigin: "50% 70%" });

    intro
      .from(".glow", { autoAlpha: 0, scale: 0.92, duration: 0.8 }, 0)
      .from(".scribble", { autoAlpha: 0, y: 12, duration: 0.6, stagger: 0.08 }, 0.05)
      .from(".neck, .stand", { y: 42, autoAlpha: 0, duration: 0.72 }, 0.12)
      .from(".monitor", { y: 42, autoAlpha: 0, rotationY: -24, duration: 0.72 }, 0.12)
      .from(".card-photo", { x: -36, y: 18, autoAlpha: 0, duration: 0.48, ease: "back.out(1.4)" }, 0.42)
      .from(".card-type", { y: 26, autoAlpha: 0, duration: 0.5 }, 0.52)
      .from(".cable", { autoAlpha: 0, scale: 0.94, rotation: -8, duration: 0.6, transformOrigin: "50% 50%" }, 0.48)
      .from(".pointer", { autoAlpha: 0, scale: 0.72, duration: 0.42, ease: "back.out(1.6)" }, 0.66)
      .from(".eyebrow, h1, .lead, .actions", { y: 18, autoAlpha: 0, duration: 0.45, stagger: 0.08 }, 0.2);

    const float = gsap.timeline({
      paused: true,
      repeat: -1,
      yoyo: true,
      defaults: { ease: "sine.inOut" },
    });
    float
      .to(".glow", { scale: 1.06, duration: 2.6 }, 0)
      .to(".cable", { rotation: 5, duration: 3.2 }, 0)
      .to(".scribble", { y: -10, duration: 2.8, stagger: 0.15 }, 0);

    intro.eventCallback("onComplete", () => float.play());
    intro.play();

    gsap.from(".step", {
      y: 28,
      autoAlpha: 0,
      duration: 0.45,
      stagger: 0.1,
      scrollTrigger: {
        trigger: ".steps",
        start: "top 78%",
        once: true,
      },
    });

    const limit = gsap.utils.clamp(-16, 16);
    const xTo = gsap.quickTo(".pointer", "x", { duration: 0.4, ease: "power3.out" });
    const yTo = gsap.quickTo(".pointer", "y", { duration: 0.4, ease: "power3.out" });
    const onMove = (event) => {
      const box = stage.getBoundingClientRect();
      const dx = (event.clientX - (box.left + box.width / 2)) / box.width;
      const dy = (event.clientY - (box.top + box.height / 2)) / box.height;
      xTo(limit(dx * 40));
      yTo(limit(dy * 32));
    };
    stage.addEventListener("pointermove", onMove);

    const onReplay = () => {
      float.pause(0);
      intro.restart();
    };
    document.querySelector("#replay").addEventListener("click", onReplay);

    page.dataset.motion = "running";

    return () => {
      stage.removeEventListener("pointermove", onMove);
      document.querySelector("#replay").removeEventListener("click", onReplay);
      delete page.dataset.motion;
    };
  },
  page
);

document.querySelector("#jump").addEventListener("click", () => {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  gsap.to(window, {
    duration: reduce ? 0 : 0.7,
    scrollTo: { y: "#layers", offsetY: 12 },
    ease: "power2.inOut",
  });
});

document.querySelectorAll(".btn").forEach((button) => {
  button.addEventListener("pointerdown", () => {
    gsap.to(button, { scale: 0.97, duration: 0.12, ease: "power2.out", overwrite: "auto" });
  });
  button.addEventListener("pointerup", () => {
    gsap.to(button, { scale: 1, duration: 0.2, ease: "power2.out", overwrite: "auto" });
  });
  button.addEventListener("pointerleave", () => {
    gsap.to(button, { scale: 1, duration: 0.2, ease: "power2.out", overwrite: "auto" });
  });
});
