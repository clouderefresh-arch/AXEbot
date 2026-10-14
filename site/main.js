/* Навыки на этой странице:
   motion-design — три слоя, playful на карточках, premium на тексте
   gsap-core — from/to, autoAlpha, matchMedia
   gsap-timeline — один вход вместо цепочки delay
   gsap-scrolltrigger — pin + scrub сборки, параллакс, вход карточек
   gsap-plugins — ScrollTo, ScrollSmoother, SplitText, ScrambleText,
                  DrawSVG, MorphSVG, MotionPath, Draggable, Inertia, Flip, Observer
   gsap-utils — clamp и quickTo для курсора
   gsap-performance — только transform и autoAlpha, quickTo на движении указателя
*/
gsap.registerPlugin(
  ScrollTrigger,
  ScrollToPlugin,
  ScrollSmoother,
  SplitText,
  ScrambleTextPlugin,
  DrawSVGPlugin,
  MorphSVGPlugin,
  MotionPathPlugin,
  Draggable,
  InertiaPlugin,
  Flip,
  Observer
);
gsap.defaults({ duration: 0.5, ease: "power3.out" });

const PHRASE = "Курсор идёт по кабелю";
const stage = document.querySelector("#stage");
const page = document.querySelector("#page");
const hud = document.querySelector("#hud");
const prefersReduce = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

let smoother = null;
let stepsIn = null;
let sunShown = false;

const setHud = (text) => {
  hud.textContent = text;
};

const scrollToTarget = (target) => {
  if (smoother && !prefersReduce()) {
    smoother.scrollTo(target, true, "top 80px");
    return;
  }
  gsap.to(window, {
    duration: prefersReduce() ? 0 : 0.7,
    scrollTo: { y: target, offsetY: 80 },
    ease: "power2.inOut",
  });
};

document.querySelector("#jump").addEventListener("click", () => scrollToTarget("#layers"));

document.querySelectorAll("[data-scroll]").forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    scrollToTarget(link.getAttribute("href"));
  });
});

document.querySelector("#morph").addEventListener("click", () => {
  sunShown = !sunShown;
  const duration = prefersReduce() ? 0 : 0.55;
  gsap.to("#icon-shape", {
    duration,
    morphSVG: sunShown ? "#icon-sun" : "#icon-mountain",
    ease: "power2.inOut",
    overwrite: "auto",
  });
  gsap.to("#icon-dot", {
    duration: prefersReduce() ? 0 : 0.3,
    autoAlpha: sunShown ? 0 : 1,
    overwrite: "auto",
  });
});

document.querySelector("#reorder").addEventListener("click", () => {
  if (stepsIn && stepsIn.progress() < 1) {
    stepsIn.progress(1);
  }
  const list = document.querySelector(".steps");
  const state = Flip.getState(".step");
  list.appendChild(list.firstElementChild);
  Flip.from(state, {
    duration: prefersReduce() ? 0 : 0.55,
    ease: "power2.inOut",
    absolute: true,
    stagger: 0.04,
  });
});

document.querySelectorAll(".btn").forEach((button) => {
  button.addEventListener("pointerdown", () => {
    gsap.to(button, {
      scale: 0.97,
      duration: prefersReduce() ? 0 : 0.12,
      ease: "power2.out",
      overwrite: "auto",
    });
  });
  const release = () => {
    gsap.to(button, {
      scale: 1,
      duration: prefersReduce() ? 0 : 0.2,
      ease: "power2.out",
      overwrite: "auto",
    });
  };
  button.addEventListener("pointerup", release);
  button.addEventListener("pointerleave", release);
});

Observer.create({
  target: window,
  type: "wheel",
  preventDefault: false,
  tolerance: 8,
  onUp: () => setHud("Колесо идёт вверх"),
  onDown: () => setHud("Колесо идёт вниз"),
});

Observer.create({
  target: "#swipe-pad",
  type: "pointer,touch",
  preventDefault: true,
  tolerance: 16,
  onLeft: () => setHud("Провели влево"),
  onRight: () => setHud("Провели вправо"),
  onUp: () => setHud("Провели вверх"),
  onDown: () => setHud("Провели вниз"),
});

const mm = gsap.matchMedia();

mm.add(
  {
    reduce: "(prefers-reduced-motion: reduce)",
    motion: "(prefers-reduced-motion: no-preference)",
  },
  (context) => {
    const { reduce } = context.conditions;

    const armDrag = () => {
      const [drag] = Draggable.create("#stage .card-photo", {
        type: "x,y",
        bounds: { minX: -36, maxX: 150, minY: -28, maxY: 42 },
        inertia: !reduce,
        edgeResistance: 0.65,
        allowNativeTouchScrolling: false,
        cursor: "grab",
        activeCursor: "grabbing",
        zIndexBoost: true,
      });
      return drag;
    };

    if (reduce) {
      document.querySelector(".cipher").textContent = PHRASE;
      const drag = armDrag();
      page.dataset.motion = "reduced";
      return () => {
        drag.kill();
        delete page.dataset.motion;
      };
    }

    smoother = ScrollSmoother.create({
      wrapper: "#smooth-wrapper",
      content: "#smooth-content",
      smooth: 1.15,
      effects: true,
      smoothTouch: 0.1,
    });

    const split = SplitText.create("#page h1", {
      type: "words,chars",
      mask: "words",
      charsClass: "char",
      wordsClass: "word",
      aria: "auto",
    });

    gsap.set("#stage .monitor", { rotationY: -8, transformOrigin: "50% 70%" });
    gsap.set("#scrub-stage .monitor", { rotationY: -16, transformOrigin: "50% 70%" });

    const intro = gsap.timeline({ paused: true, defaults: { ease: "power3.out" } });
    intro
      .from("#stage .glow", { autoAlpha: 0, scale: 0.92, duration: 0.8 }, 0)
      .from("#stage .scribble", { drawSVG: 0, autoAlpha: 0, duration: 0.8, stagger: 0.08 }, 0.05)
      .from("#stage .neck, #stage .stand", { y: 42, autoAlpha: 0, duration: 0.72 }, 0.12)
      .from("#stage .monitor", { y: 42, autoAlpha: 0, rotationY: -24, duration: 0.72 }, 0.12)
      .from("#stage .card-photo", { x: -36, y: 18, autoAlpha: 0, duration: 0.48, ease: "back.out(1.4)" }, 0.42)
      .from("#stage .card-type", { y: 26, autoAlpha: 0, duration: 0.5 }, 0.52)
      .from("#cable-path", { drawSVG: 0, duration: 0.9 }, 0.4)
      .from("#stage .cable", { autoAlpha: 0, duration: 0.4 }, 0.4)
      .from("#stage .pointer", { autoAlpha: 0, scale: 0.72, duration: 0.42, ease: "back.out(1.6)" }, 0.66)
      .from(split.chars, { yPercent: 110, duration: 0.5, stagger: 0.02 }, 0.18)
      .from(".hero .lead, .hero .actions", { y: 18, autoAlpha: 0, duration: 0.45, stagger: 0.08 }, 0.22)
      .to(".cipher", {
        duration: 1.15,
        scrambleText: {
          text: PHRASE,
          chars: "АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЩЭЮЯ",
          revealDelay: 0.3,
          speed: 0.4,
        },
      }, 0.28);

    const float = gsap.timeline({
      paused: true,
      repeat: -1,
      yoyo: true,
      defaults: { ease: "sine.inOut" },
    });
    float
      .to("#stage .glow", { scale: 1.06, duration: 2.6 }, 0)
      .to("#stage .scribble", { y: -10, duration: 2.8, stagger: 0.15 }, 0);

    const ride = gsap.timeline({ paused: true });
    ride
      .to("#stage .pointer", {
        duration: 2.2,
        ease: "power1.inOut",
        immediateRender: false,
        motionPath: {
          path: "#cable-path",
          align: "#cable-path",
          alignOrigin: [0.45, 0.45],
          autoRotate: false,
        },
      })
      .to("#stage .pointer", { x: 0, y: 0, duration: 0.45, ease: "power3.out" });

    let photoDrag = null;
    let following = false;
    let handingBack = false;

    const xTo = gsap.quickTo("#stage .pointer", "x", { duration: 0.4, ease: "power3.out" });
    const yTo = gsap.quickTo("#stage .pointer", "y", { duration: 0.4, ease: "power3.out" });
    const limit = gsap.utils.clamp(-16, 16);

    const onMove = (event) => {
      if (event.target.closest("#stage .card")) {
        return;
      }
      if (!following) {
        if (handingBack || !ride.isActive()) {
          return;
        }
        handingBack = true;
        ride.pause();
        gsap.to("#stage .pointer", {
          x: 0,
          y: 0,
          duration: 0.35,
          ease: "power3.out",
          overwrite: "auto",
          onComplete: () => {
            handingBack = false;
            following = true;
          },
        });
        return;
      }
      const box = stage.getBoundingClientRect();
      const dx = (event.clientX - (box.left + box.width / 2)) / box.width;
      const dy = (event.clientY - (box.top + box.height / 2)) / box.height;
      xTo(limit(dx * 40));
      yTo(limit(dy * 32));
    };

    intro.eventCallback("onComplete", () => {
      float.play();
      photoDrag = armDrag();
      following = false;
      ride.restart();
    });
    ride.eventCallback("onComplete", () => {
      following = true;
    });

    const onReplay = () => {
      following = false;
      handingBack = false;
      ride.pause(0);
      float.pause(0);
      if (photoDrag) {
        photoDrag.kill();
        photoDrag = null;
      }
      gsap.set("#stage .pointer, #stage .card-photo", { x: 0, y: 0 });
      intro.restart();
    };

    document.querySelector("#replay").addEventListener("click", onReplay);
    stage.addEventListener("pointermove", onMove);

    gsap.to("#stage", {
      y: -72,
      ease: "none",
      scrollTrigger: {
        trigger: ".hero",
        start: "top top",
        end: "bottom top",
        scrub: 0.6,
      },
    });

    const build = gsap.timeline({
      defaults: { ease: "none" },
      scrollTrigger: {
        trigger: "#assemble",
        start: "top top",
        end: "+=1300",
        pin: true,
        scrub: 0.7,
        anticipatePin: 1,
        onUpdate: (self) => {
          document.querySelector("#scrub-label").textContent = `Сборка ${Math.round(self.progress * 100)}%`;
        },
      },
    });
    build
      .fromTo("#scrub-stage .monitor", { rotationY: -16 }, { rotationY: -8, duration: 1 }, 0)
      .from("#scrub-stage .card-photo", { x: -46, y: 22, autoAlpha: 0, duration: 0.45 }, 0.05)
      .from("#scrub-stage .card-type", { y: 32, autoAlpha: 0, duration: 0.45 }, 0.18)
      .from("#scrub-cable", { drawSVG: 0, duration: 0.7 }, 0.08)
      .from("#scrub-stage .pointer", { autoAlpha: 0, scale: 0.7, duration: 0.35 }, 0.4);

    stepsIn = gsap.from("#layers .step", {
      y: 28,
      autoAlpha: 0,
      duration: 0.45,
      stagger: 0.1,
      immediateRender: true,
      scrollTrigger: {
        id: "steps-in",
        trigger: "#layers .steps",
        start: "top 80%",
        once: true,
      },
    });

    intro.play();
    page.dataset.motion = "running";

    return () => {
      stage.removeEventListener("pointermove", onMove);
      document.querySelector("#replay").removeEventListener("click", onReplay);
      if (photoDrag) {
        photoDrag.kill();
      }
      split.revert();
      if (smoother) {
        smoother.kill();
        smoother = null;
      }
      stepsIn = null;
      delete page.dataset.motion;
    };
  }
);
