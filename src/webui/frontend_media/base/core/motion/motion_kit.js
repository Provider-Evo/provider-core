// ========================= MotionKit primitives =========================
// Split out of motion.js: state map, pointer tracking, and animation
// primitives live here as free functions; motion.js assembles the exported
// MotionKit facade using these.

var _motionStateMap = new WeakMap();
var _motionMouseState = { x: 0, y: 0, down: false };

function _motionClamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
}

function _motionGetState(element) {
    if (!_motionStateMap.has(element)) {
        var rect = element.getBoundingClientRect();
        var computed = getComputedStyle(element);
        _motionStateMap.set(element, {
            x: 0, y: 0, size: 100,
            width: rect.width, height: rect.height,
            opacity: Number.parseFloat(computed.opacity) || 1,
            color: 0, rotation: 0, brightness: 0,
            hasExplicitWidth: false, hasExplicitHeight: false
        });
    }
    return _motionStateMap.get(element);
}

function _motionApplyState(element) {
    var state = _motionGetState(element);
    element.style.transform =
        'translate3d(' + state.x + 'px, ' + state.y + 'px, 0) scale(' +
        (state.size / 100) + ') rotate(' + state.rotation + 'deg)';
    element.style.opacity = String(_motionClamp(state.opacity, 0, 1));
    var filters = [];
    if (state.color !== 0) filters.push('hue-rotate(' + state.color + 'deg)');
    if (state.brightness !== 0) filters.push('brightness(' + (100 + state.brightness) + '%)');
    element.style.filter = filters.join(' ');
    if (state.hasExplicitWidth) element.style.width = Math.max(0, state.width) + 'px';
    if (state.hasExplicitHeight) element.style.height = Math.max(0, state.height) + 'px';
}

function _motionGetPointerHitElement() {
    return document.elementFromPoint(_motionMouseState.x, _motionMouseState.y);
}

function _motionIsPointerInside(element) {
    var rect = element.getBoundingClientRect();
    return _motionMouseState.x >= rect.left && _motionMouseState.x <= rect.right &&
           _motionMouseState.y >= rect.top && _motionMouseState.y <= rect.bottom;
}

function _motionIsPointerInsideExcluding(element, excludeSelector) {
    if (!_motionIsPointerInside(element)) return false;
    var hit = _motionGetPointerHitElement();
    if (!hit) return true;
    var excluded = hit.closest(excludeSelector);
    if (excluded && element.contains(excluded)) return false;
    return true;
}

function _motionCreateLoop(step) {
    var running = true;
    function frame() { if (!running) return; step(); requestAnimationFrame(frame); }
    requestAnimationFrame(frame);
    return { stop: function () { running = false; } };
}

function _motionAnimateState(element, update, done, finish) {
    return new Promise(function (resolve) {
        function frame() {
            var state = _motionGetState(element);
            update(state);
            _motionApplyState(element);
            if (done(state)) {
                finish(state);
                _motionApplyState(element);
                resolve();
                return;
            }
            requestAnimationFrame(frame);
        }
        requestAnimationFrame(frame);
    });
}

function _motionSetState(element, patch) {
    var state = _motionGetState(element);
    Object.assign(state, patch || {});
    _motionApplyState(element);
    return state;
}

function _motionSizeTo(element, target, rate) {
    var r = rate == null ? 8 : rate;
    return _motionAnimateState(element,
        function (state) { state.size += (target - state.size) / r; },
        function (state) { return Math.abs(target - state.size) < 0.5; },
        function (state) { state.size = target; });
}

function _motionOpacityTo(element, target, rate) {
    var r = rate == null ? 8 : rate;
    return _motionAnimateState(element,
        function (state) { state.opacity += (target - state.opacity) / r; },
        function (state) { return Math.abs(target - state.opacity) < 0.01; },
        function (state) { state.opacity = target; });
}

function _motionWidthTo(element, target, rate) {
    var r = rate == null ? 6 : rate;
    var state = _motionGetState(element);
    state.hasExplicitWidth = true;
    return _motionAnimateState(element,
        function (s) { s.width += (target - s.width) / r; },
        function (s) { return Math.abs(target - s.width) < 1; },
        function (s) { s.width = target; });
}

function _motionFloatScale(element, hover, press, normal, damping) {
    var h = hover == null ? 108 : hover;
    var p = press == null ? 96 : press;
    var n = normal == null ? 100 : normal;
    var d = damping == null ? 0.18 : damping;
    return _motionCreateLoop(function () {
        var state = _motionGetState(element);
        var inside = _motionIsPointerInside(element);
        var target = _motionMouseState.down && inside ? p : inside ? h : n;
        state.size += (target - state.size) * d;
        _motionApplyState(element);
    });
}

function _motionFloatScaleConditional(element, resolver, damping) {
    var d = damping == null ? 0.18 : damping;
    return _motionCreateLoop(function () {
        var state = _motionGetState(element);
        var target = resolver({
            element: element,
            state: state,
            mouseState: _motionMouseState,
            hitElement: _motionGetPointerHitElement(),
            isInside: _motionIsPointerInside(element)
        });
        state.size += (target - state.size) * d;
        _motionApplyState(element);
    });
}

window.addEventListener('pointermove', function (event) {
    _motionMouseState.x = event.clientX;
    _motionMouseState.y = event.clientY;
}, { passive: true });
window.addEventListener('pointerdown', function () { _motionMouseState.down = true; }, { passive: true });
window.addEventListener('pointerup', function () { _motionMouseState.down = false; }, { passive: true });
window.addEventListener('pointercancel', function () { _motionMouseState.down = false; }, { passive: true });
