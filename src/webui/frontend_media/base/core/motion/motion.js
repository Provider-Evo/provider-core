// ========================= MotionKit =========================
// MotionKit primitives and facade; higher-level entrance/hover helpers.

var MotionKit = {
    mouseState: _motionMouseState,
    clamp: _motionClamp,
    getState: _motionGetState,
    setState: _motionSetState,
    applyState: _motionApplyState,
    getPointerHitElement: _motionGetPointerHitElement,
    isPointerInside: _motionIsPointerInside,
    isPointerInsideExcluding: _motionIsPointerInsideExcluding,
    createLoop: _motionCreateLoop,
    animateState: _motionAnimateState,
    sizeTo: _motionSizeTo,
    opacityTo: _motionOpacityTo,
    widthTo: _motionWidthTo,
    floatScale: _motionFloatScale,
    floatScaleConditional: _motionFloatScaleConditional
};
