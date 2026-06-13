// ========================= MotionKit =========================
const MotionKit = (() => {
    const stateMap = new WeakMap();
    const mouseState = { x: 0, y: 0, down: false };

    function clamp(value, min, max) { return Math.min(max, Math.max(min, value)); }

    function getState(element) {
        if (!stateMap.has(element)) {
            const rect = element.getBoundingClientRect();
            const computed = getComputedStyle(element);
            stateMap.set(element, {
                x: 0, y: 0, size: 100,
                width: rect.width, height: rect.height,
                opacity: Number.parseFloat(computed.opacity) || 1,
                color: 0, rotation: 0, brightness: 0,
                hasExplicitWidth: false, hasExplicitHeight: false
            });
        }
        return stateMap.get(element);
    }

    function applyState(element) {
        const state = getState(element);
        element.style.transform =
            `translate3d(${state.x}px, ${state.y}px, 0) scale(${state.size / 100}) rotate(${state.rotation}deg)`;
        element.style.opacity = String(clamp(state.opacity, 0, 1));
        const filters = [];
        if (state.color !== 0) filters.push(`hue-rotate(${state.color}deg)`);
        if (state.brightness !== 0) filters.push(`brightness(${100 + state.brightness}%)`);
        element.style.filter = filters.join(" ");
        if (state.hasExplicitWidth) element.style.width = `${Math.max(0, state.width)}px`;
        if (state.hasExplicitHeight) element.style.height = `${Math.max(0, state.height)}px`;
    }

    function getPointerHitElement() { return document.elementFromPoint(mouseState.x, mouseState.y); }

    function isPointerInside(element) {
        const rect = element.getBoundingClientRect();
        return mouseState.x >= rect.left && mouseState.x <= rect.right &&
               mouseState.y >= rect.top && mouseState.y <= rect.bottom;
    }

    function isPointerInsideExcluding(element, excludeSelector) {
        if (!isPointerInside(element)) return false;
        const hit = getPointerHitElement();
        if (!hit) return true;
        const excluded = hit.closest(excludeSelector);
        if (excluded && element.contains(excluded)) return false;
        return true;
    }

    function createLoop(step) {
        let running = true;
        function frame() { if (!running) return; step(); requestAnimationFrame(frame); }
        requestAnimationFrame(frame);
        return { stop() { running = false; } };
    }

    function animateState(element, update, done, finish) {
        return new Promise((resolve) => {
            function frame() {
                const state = getState(element);
                update(state);
                applyState(element);
                if (done(state)) { finish(state); applyState(element); resolve(); return; }
                requestAnimationFrame(frame);
            }
            requestAnimationFrame(frame);
        });
    }

    function setState(element, patch = {}) {
        const state = getState(element);
        Object.assign(state, patch);
        applyState(element);
        return state;
    }

    function sizeTo(element, target, rate = 8) {
        return animateState(element,
            (state) => { state.size += (target - state.size) / rate; },
            (state) => Math.abs(target - state.size) < 0.5,
            (state) => { state.size = target; });
    }

    function opacityTo(element, target, rate = 8) {
        return animateState(element,
            (state) => { state.opacity += (target - state.opacity) / rate; },
            (state) => Math.abs(target - state.opacity) < 0.01,
            (state) => { state.opacity = target; });
    }

    function widthTo(element, target, rate = 6) {
        const state = getState(element);
        state.hasExplicitWidth = true;
        return animateState(element,
            (state) => { state.width += (target - state.width) / rate; },
            (state) => Math.abs(target - state.width) < 1,
            (state) => { state.width = target; });
    }

    function floatScale(element, hover = 108, press = 96, normal = 100, damping = 0.18) {
        return createLoop(() => {
            const state = getState(element);
            const inside = isPointerInside(element);
            const target = mouseState.down && inside ? press : inside ? hover : normal;
            state.size += (target - state.size) * damping;
            applyState(element);
        });
    }

    function floatScaleConditional(element, resolver, damping = 0.18) {
        return createLoop(() => {
            const state = getState(element);
            const target = resolver({
                element, state, mouseState,
                hitElement: getPointerHitElement(),
                isInside: isPointerInside(element)
            });
            state.size += (target - state.size) * damping;
            applyState(element);
        });
    }

    window.addEventListener("pointermove", (event) => {
        mouseState.x = event.clientX; mouseState.y = event.clientY;
    }, { passive: true });
    window.addEventListener("pointerdown", () => { mouseState.down = true; }, { passive: true });
    window.addEventListener("pointerup", () => { mouseState.down = false; }, { passive: true });
    window.addEventListener("pointercancel", () => { mouseState.down = false; }, { passive: true });

    return {
        mouseState, clamp, getState, setState, applyState,
        getPointerHitElement, isPointerInside, isPointerInsideExcluding,
        createLoop, animateState, sizeTo, opacityTo, widthTo,
        floatScale, floatScaleConditional
    };
})();

// ========================= 浮现 + hover 动效 =========================
function appearIn(element, delay = 0, rate = 5) {
    MotionKit.setState(element, { size: 0, opacity: 0 });
    return new Promise(resolve => {
        setTimeout(() => {
            Promise.all([MotionKit.sizeTo(element, 100, rate), MotionKit.opacityTo(element, 1, rate)]).then(resolve);
        }, delay);
    });
}

// ========================= 通用动效初始化 =========================
function initAllMotionEffects() {
    // Sections - staggered entrance
    const sections = document.querySelectorAll('section.bg-panel, section.tab-panel');
    sections.forEach((section, i) => {
        if (section.closest('.webui-content')) {
            // Only animate sections inside the main content area
            appearIn(section, 80 + i * 60, 5);
        }
    });

    // Tool buttons - staggered
    const toolBtns = document.querySelectorAll('.tool-btn');
    toolBtns.forEach((btn, i) => appearIn(btn, 120 + i * 40, 5));

    // Primary action buttons (exclude chatSendBtn as it has its own animation)
    const primaryBtns = document.querySelectorAll('button.bg-accent');
    primaryBtns.forEach((btn, i) => {
        if (btn.id !== 'chatSendBtn') {
            appearIn(btn, 200 + i * 50, 5);
        }
    });

    // Sidebar nav items - staggered
    const sidebarItems = document.querySelectorAll('.sidebar-nav-item');
    sidebarItems.forEach((item, i) => appearIn(item, 40 + i * 35, 5));

    // Cards - hover lift
    const cards = document.querySelectorAll('.border.rounded-\\[14px\\], .border.rounded-xl');
    cards.forEach(card => {
        if (!card.closest('.tool-btn') && !card.tagName === 'BUTTON') {
            card.style.transition = 'transform 0.2s ease, box-shadow 0.2s ease';
            card.addEventListener('mouseenter', () => {
                card.style.transform = 'translateY(-2px)';
                card.style.boxShadow = '0 4px 12px rgba(21, 33, 56, 0.08)';
            });
            card.addEventListener('mouseleave', () => {
                card.style.transform = 'translateY(0)';
                card.style.boxShadow = 'none';
            });
        }
    });

    // Attach floatScale to buttons
    setTimeout(attachHoverMotion, 300);
}

function attachHoverMotion() {
    // Tool buttons
    const toolButtons = Array.from(document.querySelectorAll('.tool-btn'));
    toolButtons.forEach((btn) => MotionKit.floatScale(btn, 108, 96, 100, 0.18));

    // Primary send button - skip animation, only add hover effect
    const sendBtn = document.getElementById('chatSendBtn');
    // Do NOT apply floatScale to avoid opacity issues

    // Action buttons (non-tab buttons)
    const actionBtns = Array.from(document.querySelectorAll('button:not(.tab-button):not(.tool-btn):not(.sidebar-nav-item):not(.custom-dropdown-trigger):not(.chat-msg-action)'));
    actionBtns.forEach(btn => {
        if (btn.id !== 'chatSendBtn' && !btn.classList.contains('bg-accent') && !btn.closest('.model-filters')) {
            MotionKit.floatScale(btn, 105, 97, 100, 0.15);
        }
    });

    // Main sections - subtle scale on hover
    const mainSections = document.querySelectorAll('section.bg-panel:not(.tab-panel)');
    mainSections.forEach(section => {
        MotionKit.floatScaleConditional(
            section,
            ({ isInside, hitElement }) => {
                if (!isInside) return 100;
                const hitButton = hitElement ? hitElement.closest('button') : null;
                const isInnerButton = !!hitButton && section.contains(hitButton);
                if (isInnerButton) return 100;
                return MotionKit.mouseState.down ? 99.5 : 100.5;
            },
            0.12
        );
    });
}

// ========================= Tab panel transitions =========================
function animateTabIn(panel) {
    // Disabled - conflicts with CSS fadeInUp animation
    return;
}

// ========================= Toast animation =========================
function animateToastIn(toastEl) {
    if (!toastEl) return;
    MotionKit.setState(toastEl, { opacity: 0, size: 90, y: 20 });
    MotionKit.opacityTo(toastEl, 1, 5);
    MotionKit.sizeTo(toastEl, 100, 5);
    // Animate y back to 0
    const state = MotionKit.getState(toastEl);
    state.y = 0;
    MotionKit.applyState(toastEl);
}
