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
