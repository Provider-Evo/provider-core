// ========================= Candidate ID Mapping =========================
// 拆分自 state.js。无外部依赖，可在 state_core.js 之后任意位置加载。
/**
 * 统一的候选项 ID 映射表。
 * 将后端返回的原始模型 ID 映射为简短、易读的显示 ID。
 */
const candidateIdMap = {};
let candidateIdCounter = 0;

/**
 * 获取或创建候选项的映射 ID。
 * @param {string} originalId - 原始模型 ID
 * @returns {string} 映射后的简短 ID
 */
function mapCandidateId(originalId) {
  if (!originalId) return 'unknown';
  if (candidateIdMap[originalId]) {
    return candidateIdMap[originalId];
  }
  candidateIdCounter++;
  // 提取原始 ID 的关键部分
  var shortId = originalId;
  // 如果包含斜杠或冒号，取最后一部分
  var parts = originalId.split(/[/::]/);
  if (parts.length > 1) {
    shortId = parts[parts.length - 1];
  }
  // 如果仍然太长，截取前 20 字符
  if (shortId.length > 20) {
    shortId = shortId.slice(0, 20);
  }
  candidateIdMap[originalId] = shortId;
  return shortId;
}

/**
 * 重置 ID 映射（刷新模型列表时调用）。
 */
function resetCandidateIdMap() {
  Object.keys(candidateIdMap).forEach(function(key) {
    delete candidateIdMap[key];
  });
  candidateIdCounter = 0;
}
