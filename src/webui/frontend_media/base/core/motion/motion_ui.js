// ========================= 浮现 + hover 动效 =========================
function appearIn(element, delay, rate) {
    var d = delay == null ? 0 : delay;
    var r = rate == null ? 5 : rate;
    MotionKit.setState(element, { size: 0, opacity: 0 });
    return new Promise(function (resolve) {
        setTimeout(function () {
            Promise.all([
                MotionKit.sizeTo(element, 100, r),
                MotionKit.opacityTo(element, 1, r)
            ]).then(resolve);
        }, d);
    });
}

// ========================= 通用动效初始化 =========================
function animateSectionsEntrance() {
    var sections = document.querySelectorAll('section.bg-panel, section.tab-panel');
    sections.forEach(function (section, i) {
        if (section.closest('.webui-content')) {
            appearIn(section, 80 + i * 60, 5);
        }
    });
}

function animateToolButtonsEntrance() {
    var toolBtns = document.querySelectorAll('.tool-btn');
    toolBtns.forEach(function (btn, i) { appearIn(btn, 120 + i * 40, 5); });
}

function animatePrimaryButtonsEntrance() {
    var primaryBtns = document.querySelectorAll('button.bg-accent');
    primaryBtns.forEach(function (btn, i) {
        if (btn.id !== 'chatSendBtn') {
            appearIn(btn, 200 + i * 50, 5);
        }
    });
}

function animateSidebarItemsEntrance() {
    var sidebarItems = document.querySelectorAll('.sidebar-nav-item');
    sidebarItems.forEach(function (item, i) {
        appearIn(item, 40 + i * 35, 5).then(function () {
            item.style.transform = '';
            item.style.opacity = '';
            item.style.filter = '';
        });
    });
}

function attachCardHoverLift() {
    var cards = document.querySelectorAll('.border.rounded-\\[14px\\], .border.rounded-xl');
    cards.forEach(function (card) {
        if (!card.closest('.tool-btn') && !card.tagName === 'BUTTON') {
            card.style.transition = 'transform 0.2s ease, box-shadow 0.2s ease';
            card.addEventListener('mouseenter', function () {
                card.style.transform = 'translateY(-2px)';
                card.style.boxShadow = '0 4px 12px rgba(21, 33, 56, 0.08)';
            });
            card.addEventListener('mouseleave', function () {
                card.style.transform = 'translateY(0)';
                card.style.boxShadow = 'none';
            });
        }
    });
}

function initAllMotionEffects() {
    animateSectionsEntrance();
    animateToolButtonsEntrance();
    animatePrimaryButtonsEntrance();
    animateSidebarItemsEntrance();
    attachCardHoverLift();
    setTimeout(attachHoverMotion, 300);
}

function _attachHoverMotionToolButtons() {
    var toolButtons = Array.from(document.querySelectorAll('.tool-btn'));
    toolButtons.forEach(function (btn) { MotionKit.floatScale(btn, 108, 96, 100, 0.18); });
}

function _attachHoverMotionActionButtons() {
    var sel = 'button:not(.tab-button):not(.tool-btn):not(.sidebar-nav-item):not(.custom-dropdown-trigger):not(.chat-msg-action)';
    var actionBtns = Array.from(document.querySelectorAll(sel));
    actionBtns.forEach(function (btn) {
        if (btn.id !== 'chatSendBtn' && !btn.classList.contains('bg-accent') && !btn.closest('.model-filters')) {
            MotionKit.floatScale(btn, 105, 97, 100, 0.15);
        }
    });
}

function _attachHoverMotionMainSectionsResolver(section) {
    return function (ctx) {
        if (!ctx.isInside) return 100;
        var hitButton = ctx.hitElement ? ctx.hitElement.closest('button') : null;
        var isInnerButton = !!hitButton && section.contains(hitButton);
        if (isInnerButton) return 100;
        return MotionKit.mouseState.down ? 99.5 : 100.5;
    };
}

function _attachHoverMotionMainSections() {
    var mainSections = document.querySelectorAll('section.bg-panel:not(.tab-panel)');
    mainSections.forEach(function (section) {
        MotionKit.floatScaleConditional(section, _attachHoverMotionMainSectionsResolver(section), 0.12);
    });
}

function attachHoverMotion() {
    _attachHoverMotionToolButtons();
    _attachHoverMotionActionButtons();
    _attachHoverMotionMainSections();
}

// ========================= Tab panel transitions =========================
function animateTabIn(panel) {
    return;
}

// ========================= Toast animation =========================
function animateToastIn(toastEl) {
    if (!toastEl) return;
    MotionKit.setState(toastEl, { opacity: 0, size: 90, y: 20 });
    MotionKit.opacityTo(toastEl, 1, 5);
    MotionKit.sizeTo(toastEl, 100, 5);
    var state = MotionKit.getState(toastEl);
    state.y = 0;
    MotionKit.applyState(toastEl);
}
