// Ultra-Fluid Cyber Engine (60FPS Infinite Wrap-Around & Dynamic Multi-Theme Support)
(function () {
    const canvas = document.getElementById("bg-particles");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    let mouse = {
        x: width / 2,
        y: height / 2,
        targetX: width / 2,
        targetY: height / 2
    };

    window.addEventListener("resize", () => {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
    });

    window.addEventListener("mousemove", (e) => {
        mouse.targetX = e.clientX;
        mouse.targetY = e.clientY + window.scrollY;
    });

    function getThemeParticleConfig() {
        const theme = document.documentElement.getAttribute("data-theme") || "cyan";
        switch (theme) {
            case "purple":
                return {
                    hues: [275, 285, 260],
                    isOled: false,
                    blob1: "rgba(168, 85, 247, ALPHA)",
                    blob2: "rgba(192, 132, 252, ALPHA)",
                    blob3: "rgba(139, 92, 246, ALPHA)",
                    blob4: "rgba(109, 40, 217, ALPHA)",
                    aura1: "rgba(168, 85, 247, 0.18)",
                    aura2: "rgba(192, 132, 252, 0.05)"
                };
            case "blue":
                return {
                    hues: [215, 225, 205],
                    isOled: false,
                    blob1: "rgba(37, 99, 235, ALPHA)",
                    blob2: "rgba(59, 130, 246, ALPHA)",
                    blob3: "rgba(96, 165, 250, ALPHA)",
                    blob4: "rgba(29, 78, 216, ALPHA)",
                    aura1: "rgba(37, 99, 235, 0.18)",
                    aura2: "rgba(59, 130, 246, 0.05)"
                };
            case "emerald":
                return {
                    hues: [155, 165, 145],
                    isOled: false,
                    blob1: "rgba(16, 185, 129, ALPHA)",
                    blob2: "rgba(52, 211, 153, ALPHA)",
                    blob3: "rgba(5, 150, 105, ALPHA)",
                    blob4: "rgba(4, 120, 87, ALPHA)",
                    aura1: "rgba(16, 185, 129, 0.18)",
                    aura2: "rgba(52, 211, 153, 0.05)"
                };
            case "oled":
                return {
                    hues: [0, 0, 0],
                    isOled: true,
                    blob1: "rgba(255, 255, 255, ALPHA)",
                    blob2: "rgba(200, 200, 210, ALPHA)",
                    blob3: "rgba(150, 150, 160, ALPHA)",
                    blob4: "rgba(100, 100, 110, ALPHA)",
                    aura1: "rgba(255, 255, 255, 0.12)",
                    aura2: "rgba(200, 200, 210, 0.04)"
                };
            case "crimson":
                return {
                    hues: [350, 335, 15],
                    isOled: false,
                    blob1: "rgba(225, 29, 72, ALPHA)",
                    blob2: "rgba(244, 63, 94, ALPHA)",
                    blob3: "rgba(255, 42, 95, ALPHA)",
                    blob4: "rgba(159, 18, 57, ALPHA)",
                    aura1: "rgba(225, 29, 72, 0.18)",
                    aura2: "rgba(244, 63, 94, 0.05)"
                };
            case "cyan":
            default:
                return {
                    hues: [188, 198, 178],
                    isOled: false,
                    blob1: "rgba(0, 242, 254, ALPHA)",
                    blob2: "rgba(14, 165, 233, ALPHA)",
                    blob3: "rgba(56, 189, 248, ALPHA)",
                    blob4: "rgba(2, 132, 199, ALPHA)",
                    aura1: "rgba(0, 242, 254, 0.18)",
                    aura2: "rgba(14, 165, 233, 0.05)"
                };
        }
    }

    let themeConfig = getThemeParticleConfig();

    // 1. Cyber Plasma Blobs
    class ThemeBlob {
        constructor(x, y, radius, blobKey, vx, vy) {
            this.x = x;
            this.y = y;
            this.baseRadius = radius;
            this.radius = radius;
            this.blobKey = blobKey;
            this.vx = vx;
            this.vy = vy;
            this.angle = Math.random() * Math.PI * 2;
        }

        update() {
            this.x += this.vx;
            this.y += this.vy;

            // Continuous infinite toroidal wrap-around
            if (this.x < -this.radius) this.x = width + this.radius;
            if (this.x > width + this.radius) this.x = -this.radius;
            if (this.y < -this.radius) this.y = height + this.radius;
            if (this.y > height + this.radius) this.y = -this.radius;

            this.angle += 0.012;
            this.radius = this.baseRadius + Math.sin(this.angle) * 35;
        }

        draw() {
            const rawColor = themeConfig[this.blobKey] || themeConfig.blob1;
            const grad = ctx.createRadialGradient(
                this.x, this.y, 0,
                this.x, this.y, this.radius
            );
            grad.addColorStop(0, rawColor.replace('ALPHA', '0.22'));
            grad.addColorStop(0.45, rawColor.replace('ALPHA', '0.07'));
            grad.addColorStop(1, 'transparent');

            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    // 2. Infinite Continuous Floating Sparks (Zero Sinking)
    class ThemeSpark {
        constructor() {
            this.init(true);
        }

        init(randomY = false) {
            this.x = Math.random() * width;
            this.y = randomY ? Math.random() * height : height + 10;
            this.size = Math.random() * 2.2 + 0.8;
            this.vy = -(Math.random() * 0.8 + 0.4);
            this.vx = (Math.random() - 0.5) * 0.5;
            this.alpha = Math.random() * 0.8 + 0.3;
            
            const hues = themeConfig.hues || [188, 198, 178];
            this.hue = hues[Math.floor(Math.random() * hues.length)];
            this.isOled = themeConfig.isOled;
        }

        update() {
            this.y += this.vy;
            this.x += this.vx;

            // Mouse proximity interaction
            const currentMouseY = mouse.targetY - window.scrollY;
            const dx = mouse.x - this.x;
            const dy = currentMouseY - this.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < 140) {
                const angle = Math.atan2(dy, dx);
                this.x -= Math.cos(angle) * 2;
                this.y -= Math.sin(angle) * 2;
            }

            // Wrap continuously when reaching top or sides
            if (this.y < -15) {
                this.init(false);
            }
            if (this.x < -10) this.x = width + 10;
            if (this.x > width + 10) this.x = -10;
        }

        draw() {
            if (this.isOled) {
                ctx.fillStyle = `rgba(255, 255, 255, ${this.alpha})`;
                ctx.shadowBlur = 10;
                ctx.shadowColor = `rgba(255, 255, 255, 0.8)`;
            } else {
                ctx.fillStyle = `hsla(${this.hue}, 95%, 60%, ${this.alpha})`;
                ctx.shadowBlur = 12;
                ctx.shadowColor = `hsla(${this.hue}, 95%, 60%, 0.85)`;
            }
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
            ctx.fill();
            ctx.shadowBlur = 0;
        }
    }

    const blobs = [
        new ThemeBlob(width * 0.15, height * 0.25, 440, "blob1", 0.22, 0.12),
        new ThemeBlob(width * 0.85, height * 0.35, 480, "blob2", -0.18, 0.2),
        new ThemeBlob(width * 0.5, height * 0.7, 500, "blob3", 0.15, -0.16),
        new ThemeBlob(width * 0.2, height * 0.9, 420, "blob4", -0.12, -0.14)
    ];

    const sparks = [];
    const sparkCount = Math.min(Math.floor(width / 16), 90);
    for (let i = 0; i < sparkCount; i++) {
        sparks.push(new ThemeSpark());
    }

    // Dynamic theme change listener
    window.addEventListener("themeChanged", () => {
        themeConfig = getThemeParticleConfig();
        sparks.forEach(s => s.init(true));
    });

    function animate() {
        ctx.clearRect(0, 0, width, height);

        // Smooth mouse spring
        mouse.x += (mouse.targetX - mouse.x) * 0.08;
        mouse.y += (mouse.targetY - mouse.y) * 0.08;

        // Interactive cursor aura
        const currentMouseY = mouse.targetY - window.scrollY;
        const cursorGrad = ctx.createRadialGradient(
            mouse.x, currentMouseY, 0,
            mouse.x, currentMouseY, 340
        );
        cursorGrad.addColorStop(0, themeConfig.aura1 || "rgba(0, 242, 254, 0.18)");
        cursorGrad.addColorStop(0.5, themeConfig.aura2 || "rgba(14, 165, 233, 0.05)");
        cursorGrad.addColorStop(1, "transparent");
        ctx.fillStyle = cursorGrad;
        ctx.beginPath();
        ctx.arc(mouse.x, currentMouseY, 340, 0, Math.PI * 2);
        ctx.fill();

        // Render blobs
        blobs.forEach(b => {
            b.update();
            b.draw();
        });

        // Render sparks
        sparks.forEach(s => {
            s.update();
            s.draw();
        });

        requestAnimationFrame(animate);
    }

    animate();
})();
