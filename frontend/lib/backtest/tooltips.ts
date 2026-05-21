export const TOOLTIPS = {
  mode: '两者兼顾：同时计算固定和 Kelly 两种策略，便于对比。',
  fixed_stake: '固定模式下每场下注的金额（元）。不管评分高低都下这个数，便于简单评估。',
  initial_capital: 'Kelly 模式下的总资金池，凯利公式按当前本金比例决定每场下注金额。',
  model_config_id: '使用哪套模型规则。留空则用当前激活的模型。',
  bet_type: '模型建议下注的玩法：平局 = 直接买平；让球平 = 买让球后的平局。',
  total_score: '模型 6 维评分合计，满分 120。≥ 84 才会被推荐。',
  odds: '下注玩法对应的真实赔率（澳门欧赔）。下注金额 × 赔率 = 命中时的奖金。',
  stake_kelly: '凯利公式按评分高低自动分配的下注金额。评分越高投注越多。',
  roi_fixed: '固定模式总回报率：净盈亏 ÷ 总投入。',
  roi_kelly: 'Kelly 模式总回报率：净盈亏 ÷ 初始本金。'
} as const

export const BET_TYPE_LABEL: Record<string, string> = {
  draw: '平局',
  handicap_draw: '让球平'
}
