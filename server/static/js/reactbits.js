// ReactBits Interactive Utilities for Joyst Corporation
document.addEventListener("DOMContentLoaded", () => {
    initSpotlightCards();
    initAnimatedNumbers();
    initCommandPaletteShortcut();
});

// 1. ReactBits Spotlight Card Effect (Follows Mouse Movement)
function initSpotlightCards() {
    const cards = document.querySelectorAll(".spotlight-card");
    cards.forEach(card => {
        card.addEventListener("mousemove", (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            card.style.setProperty("--mouse-x", `${x}px`);
            card.style.setProperty("--mouse-y", `${y}px`);
        });
    });
}

// 2. Animated Number Counters
function initAnimatedNumbers() {
    const counters = document.querySelectorAll("[data-counter]");
    counters.forEach(counter => {
        const target = parseFloat(counter.getAttribute("data-counter"));
        if (isNaN(target)) return;

        let current = 0;
        const increment = target / 40;
        const timer = setInterval(() => {
            current += increment;
            if (current >= target) {
                counter.textContent = target.toLocaleString();
                clearInterval(timer);
            } else {
                counter.textContent = Math.floor(current).toLocaleString();
            }
        }, 25);
    });
}

// 3. Command Palette Shortcut (Ctrl + K)
function initCommandPaletteShortcut() {
    window.addEventListener("keydown", (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === "k") {
            e.preventDefault();
            const searchInput = document.querySelector(".search-input");
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            } else {
                const searchField = document.getElementById("license-search-input") || document.getElementById("user-search-input");
                if (searchField) searchField.focus();
            }
        }
    });
}

// 4. ReactBits VariableProximity Component Engine (Mouse Proximity Variable Font Physics)
function initVariableProximity() {
    const proximityElements = document.querySelectorAll("[data-variable-proximity]");
    proximityElements.forEach(el => {
        const text = el.getAttribute("data-label") || el.innerText.trim();
        const fromWeight = parseInt(el.getAttribute("data-from-weight") || "400");
        const toWeight = parseInt(el.getAttribute("data-to-weight") || "900");
        const radius = parseFloat(el.getAttribute("data-radius") || "220");

        el.innerHTML = "";
        const letters = [];
        const words = text.split(" ");

        words.forEach((word, wIdx) => {
            const wordSpan = document.createElement("span");
            wordSpan.style.display = "inline-block";
            wordSpan.style.whiteSpace = "nowrap";

            for (let i = 0; i < word.length; i++) {
                const charSpan = document.createElement("span");
                charSpan.textContent = word[i];
                charSpan.style.display = "inline-block";
                charSpan.style.fontWeight = fromWeight;
                charSpan.style.transition = "transform 0.08s ease-out, font-weight 0.08s ease-out, text-shadow 0.1s ease-out, color 0.1s ease-out";
                charSpan.style.willChange = "transform, font-weight";
                wordSpan.appendChild(charSpan);
                letters.push(charSpan);
            }

            el.appendChild(wordSpan);
            if (wIdx < words.length - 1) {
                const space = document.createElement("span");
                space.innerHTML = "&nbsp;";
                space.style.display = "inline-block";
                el.appendChild(space);
            }
        });

        // Mouse Tracker
        let mouseX = -9999;
        let mouseY = -9999;
        let ticking = false;

        function onMouseMove(e) {
            mouseX = e.clientX;
            mouseY = e.clientY;
            if (!ticking) {
                requestAnimationFrame(update);
                ticking = true;
            }
        }

        window.addEventListener("mousemove", onMouseMove);

        function update() {
            let anyHovered = false;

            letters.forEach(span => {
                const rect = span.getBoundingClientRect();
                const charX = rect.left + rect.width / 2;
                const charY = rect.top + rect.height / 2;
                const dist = Math.hypot(mouseX - charX, mouseY - charY);

                if (dist < radius) {
                    anyHovered = true;
                    // Gaussian falloff
                    const norm = Math.exp(-Math.pow(dist / (radius * 0.45), 2) / 2);
                    const weight = Math.round(fromWeight + (toWeight - fromWeight) * norm);
                    const scale = 1 + norm * 0.28;
                    const liftY = -norm * 10;

                    span.style.fontWeight = weight;
                    span.style.fontVariationSettings = `'wght' ${weight}, 'opsz' 36`;
                    span.style.transform = `scale(${scale}) translateY(${liftY}px)`;
                    span.style.textShadow = `0 0 ${Math.round(25 * norm)}px rgba(255, 42, 95, ${0.4 + norm * 0.6})`;
                    span.style.color = norm > 0.3 ? '#fff' : '';
                } else {
                    span.style.fontWeight = fromWeight;
                    span.style.fontVariationSettings = `'wght' ${fromWeight}, 'opsz' 14`;
                    span.style.transform = "scale(1) translateY(0px)";
                    span.style.textShadow = "";
                    span.style.color = "";
                }
            });

            ticking = false;
            if (anyHovered) {
                requestAnimationFrame(update);
                ticking = true;
            }
        }
    });
}

// Attach to DOM load & immediate trigger
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
        initVariableProximity();
        initParticleText();
    });
} else {
    initVariableProximity();
    initParticleText();
}

// 5. ReactBits ParticleText Engine (Canvas Glyph Sampling + Scatter / Reform Physics)
function initParticleText() {
    const containers = document.querySelectorAll(".particle-text");
    if (!containers.length) return;

    containers.forEach(container => {
        const text = container.getAttribute("data-text") || "JOYST AUTH";
        const particleSize = parseFloat(container.getAttribute("data-particle-size") || "2");
        const density = parseFloat(container.getAttribute("data-density") || "3");
        const color = container.getAttribute("data-color") || "#ffffff";
        const highlightColor = container.getAttribute("data-highlight-color") || "#ff2a5f";
        const scatter = parseFloat(container.getAttribute("data-scatter") || "180");
        const gatherDuration = parseFloat(container.getAttribute("data-gather-duration") || "1500");
        const stagger = parseFloat(container.getAttribute("data-stagger") || "400");
        const pointerRepel = parseFloat(container.getAttribute("data-pointer-repel") || "45");
        const repelRadius = parseFloat(container.getAttribute("data-repel-radius") || "130");
        const idleDrift = parseFloat(container.getAttribute("data-idle-drift") || "0.6");
        const fontWeight = container.getAttribute("data-font-weight") || "900";
        const glow = container.getAttribute("data-glow") !== "false";

        let canvas = container.querySelector(".particle-text__canvas");
        if (!canvas) {
            canvas = document.createElement("canvas");
            canvas.className = "particle-text__canvas";
            container.appendChild(canvas);
        }

        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        let particles = [];
        let animationFrame = null;
        let gathering = false;
        let gatherStart = 0;
        let width = 0;
        let height = 0;
        let dpr = 1;

        const pointer = {
            active: false,
            x: 0,
            y: 0,
            smoothX: 0,
            smoothY: 0
        };

        const hexToRgb = hex => {
            const clean = hex.replace("#", "").trim();
            if (!/^[0-9a-fA-F]{6}$/.test(clean)) return { r: 255, g: 42, b: 95 };
            return {
                r: parseInt(clean.slice(0, 2), 16),
                g: parseInt(clean.slice(2, 4), 16),
                b: parseInt(clean.slice(4, 6), 16)
            };
        };

        const mixRgb = (from, to, amount) => ({
            r: Math.round(from.r + (to.r - from.r) * amount),
            g: Math.round(from.g + (to.g - from.g) * amount),
            b: Math.round(from.b + (to.b - from.b) * amount)
        });

        const rgbToCss = rgb => `rgb(${rgb.r}, ${rgb.g}, ${rgb.b})`;
        const clamp = (val, min, max) => Math.min(Math.max(val, min), max);
        const easeOutCubic = t => 1 - Math.pow(1 - t, 3);

        const startGather = (fromScatter = true) => {
            if (!particles.length) return;
            const now = performance.now();

            particles.forEach(p => {
                if (fromScatter) {
                    const angle = p.seed * Math.PI * 2;
                    const dist = scatter * (0.35 + p.depth * 0.75);
                    p.x = p.targetX + Math.cos(angle) * dist + (p.depth - 0.5) * scatter * 0.5;
                    p.y = p.targetY + Math.sin(angle) * dist + (p.seed - 0.5) * scatter * 0.5;
                }
                p.startX = p.x;
                p.startY = p.y;
                p.delay = p.seed * stagger;
            });

            gatherStart = now;
            gathering = true;
        };

        const drawParticle = p => {
            const size = p.size;
            ctx.fillStyle = p.color;
            if (size <= 2.2) {
                ctx.fillRect(p.x - size / 2, p.y - size / 2, size, size);
                return;
            }
            ctx.beginPath();
            ctx.arc(p.x, p.y, size / 2, 0, Math.PI * 2);
            ctx.fill();
        };

        const render = now => {
            ctx.clearRect(0, 0, width, height);

            if (glow) {
                ctx.shadowBlur = particleSize * 3.5;
                ctx.shadowColor = highlightColor;
            } else {
                ctx.shadowBlur = 0;
            }

            pointer.smoothX += (pointer.x - pointer.smoothX) * 0.18;
            pointer.smoothY += (pointer.y - pointer.smoothY) * 0.18;

            let complete = true;

            particles.forEach(p => {
                let baseX = p.targetX;
                let baseY = p.targetY;
                let progress = 1;

                if (gathering) {
                    const local = (now - gatherStart - p.delay) / Math.max(1, gatherDuration);
                    progress = clamp(local, 0, 1);
                    const eased = easeOutCubic(progress);
                    baseX = p.startX + (p.targetX - p.startX) * eased;
                    baseY = p.startY + (p.targetY - p.startY) * eased;
                    if (progress < 1) complete = false;
                } else if (idleDrift > 0) {
                    const driftTime = now * 0.001;
                    baseX += Math.sin(driftTime * 0.9 + p.seed * 10) * idleDrift * p.depth;
                    baseY += Math.cos(driftTime * 0.75 + p.depth * 10) * idleDrift * p.depth;
                }

                if (pointer.active && pointerRepel > 0 && repelRadius > 0) {
                    const dx = baseX - pointer.smoothX;
                    const dy = baseY - pointer.smoothY;
                    const dist = Math.hypot(dx, dy);
                    if (dist > 0 && dist < repelRadius) {
                        const force = Math.pow(1 - dist / repelRadius, 2) * pointerRepel;
                        baseX += (dx / dist) * force;
                        baseY += (dy / dist) * force;
                    }
                }

                p.x += (baseX - p.x) * 0.22;
                p.y += (baseY - p.y) * 0.22;

                ctx.globalAlpha = clamp(0.35 + progress * 0.65, 0, 1);
                drawParticle(p);
            });

            ctx.globalAlpha = 1;
            ctx.shadowBlur = 0;

            if (gathering && complete) {
                gathering = false;
            }

            animationFrame = requestAnimationFrame(render);
        };

        const sampleText = () => {
            const rect = container.getBoundingClientRect();
            width = Math.floor(rect.width);
            height = Math.floor(rect.height);
            if (width <= 0 || height <= 0) return;

            dpr = Math.min(window.devicePixelRatio || 1, 2);
            canvas.width = Math.max(1, Math.floor(width * dpr));
            canvas.height = Math.max(1, Math.floor(height * dpr));
            canvas.style.width = "100%";
            canvas.style.height = "100%";
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

            const offscreen = document.createElement("canvas");
            const offCtx = offscreen.getContext("2d", { willReadFrequently: true });
            if (!offCtx) return;

            let resolvedSize = Math.min(Math.max(width * 0.08, 44), 76);
            let font = `${fontWeight} ${resolvedSize}px 'Plus Jakarta Sans', sans-serif`;

            offscreen.width = width;
            offscreen.height = height;
            offCtx.font = font;
            offCtx.textAlign = "center";
            offCtx.textBaseline = "middle";
            offCtx.fillStyle = "#ffffff";
            offCtx.fillText(text, width / 2, height / 2);

            const imageData = offCtx.getImageData(0, 0, width, height);
            const targets = [];
            const step = Math.max(2, Math.floor(density));

            for (let y = 0; y < height; y += step) {
                for (let x = 0; x < width; x += step) {
                    const alpha = imageData.data[(y * width + x) * 4 + 3];
                    if (alpha > 40) {
                        targets.push({ x, y, alpha: alpha / 255 });
                    }
                }
            }

            const maxParticles = 3200;
            const stride = Math.max(1, Math.ceil(targets.length / maxParticles));
            const baseRgb = hexToRgb(color);
            const highlightRgb = hexToRgb(highlightColor);
            const selected = targets.filter((_, idx) => idx % stride === 0);

            particles = selected.map((t, index) => {
                const seed = ((index * 9301 + 49297) % 233280) / 233280;
                const depth = 0.45 + (((index * 233 + 97) % 1000) / 1000) * 0.9;
                const blend = clamp(t.x / width + (seed - 0.5) * 0.35, 0, 1);
                const pColor = rgbToCss(mixRgb(baseRgb, highlightRgb, blend));
                const angle = seed * Math.PI * 2;
                const dist = scatter * (0.35 + depth * 0.75);

                return {
                    x: t.x + Math.cos(angle) * dist,
                    y: t.y + Math.sin(angle) * dist,
                    startX: t.x + Math.cos(angle) * dist,
                    startY: t.y + Math.sin(angle) * dist,
                    targetX: t.x,
                    targetY: t.y,
                    size: Math.max(0.8, particleSize * (0.75 + t.alpha * 0.45)),
                    color: pColor,
                    seed,
                    depth,
                    delay: seed * stagger
                };
            });

            pointer.x = width / 2;
            pointer.y = height / 2;
            pointer.smoothX = pointer.x;
            pointer.smoothY = pointer.y;

            startGather(false);

            if (!animationFrame) {
                animationFrame = requestAnimationFrame(render);
            }
        };

        const handlePointerMove = e => {
            const rect = canvas.getBoundingClientRect();
            pointer.x = e.clientX - rect.left;
            pointer.y = e.clientY - rect.top;
            pointer.active = true;
        };

        const handlePointerLeave = () => {
            pointer.active = false;
        };

        canvas.addEventListener("pointermove", handlePointerMove);
        canvas.addEventListener("pointerleave", handlePointerLeave);
        canvas.addEventListener("click", () => startGather(true));

        window.addEventListener("resize", () => {
            sampleText();
        });

        setTimeout(sampleText, 100);
    });
}



