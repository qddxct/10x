'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'

import { useAuthStore } from '@/lib/auth/store'
import {
  activateModelConfig,
  cloneModelConfig,
  createModelConfig,
  listModelConfigs,
  updateModelConfig
} from '@/lib/model-config/api'
import type { KellyBand, ModelConfig, WeightsJson } from '@/lib/model-config/types'

import styles from './model-client.module.css'

type Mode = 'view' | 'edit' | 'create'

interface Draft {
  name: string
  weights: WeightsJson
  thresholds: Record<string, number | string>
  kellyBands: Array<{ key: string; band: KellyBand }>
}

const WEIGHT_KEYS: Array<keyof WeightsJson> = [
  'euro',
  'asian',
  'goals',
  'intent',
  'compression',
  'team_stats'
]

const WEIGHT_LABELS: Record<string, string> = {
  euro: '欧赔',
  asian: '亚盘',
  goals: '进球',
  intent: '战意',
  compression: '压缩',
  team_stats: '球队状态'
}

const WEIGHT_GUIDE: Record<
  string,
  { meaning: string; range: string; low: string; high: string; recommended: string }
> = {
  euro: {
    meaning: '衡量竞彩平赔、胜负赔是否落在容易出平的赔率甜区。',
    range: '建议 15-30，默认 25。',
    low: '调低后盘口赔率信号影响变小。',
    high: '调高后更依赖赔率结构。',
    recommended: '平局模型建议 20-25；赔率质量好时可到 30。'
  },
  asian: {
    meaning: '衡量亚盘深浅，平手/浅盘更利于平局，让深盘更偏让平。',
    range: '建议 15-25，默认 20。',
    low: '调低后让球结构影响变小。',
    high: '调高后更强调盘口方向。',
    recommended: '默认 20 较稳，不建议低于 15。'
  },
  goals: {
    meaning: '衡量大小球盘口，低进球预期通常更利于平局。',
    range: '建议 10-25，默认 20。',
    low: '调低后不太区分低进球/高进球比赛。',
    high: '调高后低进球比赛会明显优先。',
    recommended: '联赛平局模型建议 15-20。'
  },
  intent: {
    meaning: '衡量杯赛、淘汰赛、战意场景对保守/搏命倾向的影响。',
    range: '建议 5-15，默认 15。',
    low: '调低后赛事情境影响变弱。',
    high: '调高后杯赛/淘汰赛权重更大。',
    recommended: '数据不足时保持 5-10；确定战意信息可靠时用 15。'
  },
  compression: {
    meaning: '衡量平赔是否被压低，代表市场对平局的定价收敛。',
    range: '建议 10-25，默认 20。',
    low: '调低后不太看平赔压缩。',
    high: '调高后低平赔/压缩场更容易高分。',
    recommended: '建议 15-20，过高会偏向低赔平。'
  },
  team_stats: {
    meaning: '衡量排名接近、近期状态、联赛平局率等基本面。',
    range: '建议 10-25，默认 20。',
    low: '调低后更像纯盘口模型。',
    high: '调高后更重视球队基本面。',
    recommended: '球队数据完整时 20；数据缺失多时降到 10-15。'
  }
}

const DEFAULT_SCORE_RULES = [
  {
    title: '欧赔结构',
    max: 25,
    lines: [
      '胜/负 2.30-2.80 且平赔 3.00-3.40：25分',
      '三项赔率越接近越高：离散≤10% 得25，≤20% 得18，≤35% 得10，≤60% 得5',
      '赔率缺失或结构过散：0分'
    ]
  },
  {
    title: '亚盘深浅',
    max: 20,
    lines: [
      '平手盘：20分',
      '平半盘：15-18分',
      '半球：12分左右；一球：8分；一球半以上：3分或更低',
      '盘口越浅，越认为双方接近，更利于平局判断'
    ]
  },
  {
    title: '进球预期',
    max: 20,
    lines: [
      '大小球≤2.25：20分',
      '大小球 2.5 附近：10分',
      '大小球≥2.75：0分',
      '没有大小球时，用平赔≤3.20 和浅盘口各补10分'
    ]
  },
  {
    title: '战意场景',
    max: 15,
    lines: [
      '杯赛、淘汰赛、首回合/次回合：15分',
      '普通联赛：5分',
      '这个维度表达比赛情境对保守或搏命倾向的影响'
    ]
  },
  {
    title: '平赔压缩',
    max: 20,
    lines: ['平赔≤3.20：20分', '平赔 3.20-3.60：10分', '平赔≥3.60 或缺失：0分']
  },
  {
    title: '球队状态',
    max: 20,
    lines: [
      '排名差≤2 加8分，≤5 加6分，≤10 加3分',
      '近期战绩越均衡、平局越多，分数越高',
      '主客两队赛季平局率越高，最高再加4分'
    ]
  }
]

const THRESHOLD_KEYS = [
  'min_total_score',
  'recommend_total_score',
  'draw_min_score',
  'handicap_draw_min_score'
]

const THRESHOLD_GUIDE: Record<
  string,
  { label: string; meaning: string; range: string; effect: string; recommended: string }
> = {
  min_total_score: {
    label: '最低入池分',
    meaning: '低于这个分数的比赛一般只作为观察，不进入重点候选。',
    range: '常用 70-100。',
    effect: '越高越保守，候选更少；越低覆盖更多但噪音更大。',
    recommended: '普通 6 维模型建议 78-84；研究规则模型可 100+。'
  },
  recommend_total_score: {
    label: '推荐总分线',
    meaning: '总分达到该阈值且有下注方向时，标记为推荐。',
    range: '常用 84-108。',
    effect: '越高推荐越少但更集中；越低推荐更多但稳定性下降。',
    recommended: 'default 可 84-104；V3.2 当前用 108。'
  },
  draw_min_score: {
    label: '平局推荐线',
    meaning: '买“平”时需要达到的最低分。',
    range: '常用 84-108。',
    effect: '越高越少买平；越低平局候选更多。',
    recommended: '普通模型 84-104；V3.2 平局核心 108。'
  },
  handicap_draw_min_score: {
    label: '让平推荐线',
    meaning: '买“让平”时需要达到的最低分。',
    range: '常用 78-116。',
    effect: '越高越少买让平；越低更容易给出让平。',
    recommended: '让平风险更高，建议不低于平局线；V3.2 为 116。'
  }
}

const EXTRA_THRESHOLD_GUIDE: Record<string, string> = {
  strategy: '模型策略标识。empirical_v32_filtered 表示使用 V3.2 经验规则过滤候选。',
  draw_handicap_abs_max: '买平允许的最大让球绝对值。0 表示只接受平手盘，0.25 表示平手/平半都可。',
  euro_draw_min: '平赔最低要求。值越高，越少接受低平赔比赛。',
  compression_ratio_min: '压缩比例最低要求。值越高，越强调平赔被市场压缩。'
}

const KELLY_GUIDE = {
  min_score: '档位起始分，达到这个分数才进入该仓位档。',
  max_score: '档位最高分，超过后进入更高档或不匹配该档。',
  kelly_pct: '建议投入本金比例。0.010 = 1%，本金 10000 时建议 100。'
}

const BLANK_DRAFT: Draft = {
  name: '',
  weights: {
    euro: 20,
    asian: 20,
    goals: 20,
    intent: 10,
    compression: 15,
    team_stats: 15
  },
  thresholds: {
    min_total_score: 78,
    recommend_total_score: 84,
    draw_min_score: 84,
    handicap_draw_min_score: 78
  },
  kellyBands: [
    { key: 'low', band: { min_score: 78, max_score: 84, kelly_pct: 0.01 } },
    { key: 'mid', band: { min_score: 84, max_score: 96, kelly_pct: 0.015 } },
    { key: 'high', band: { min_score: 96, max_score: 120, kelly_pct: 0.02 } }
  ]
}

function toDraft(c: ModelConfig): Draft {
  return {
    name: c.name,
    weights: { ...c.weights_json },
    thresholds: { ...c.thresholds_json },
    kellyBands: Object.entries(c.kelly_bands_json ?? {}).map(([k, b]) => ({
      key: k,
      band: { ...b }
    }))
  }
}

function toPayload(draft: Draft): {
  name: string
  weights_json: WeightsJson
  thresholds_json: Record<string, number | string>
  kelly_bands_json: Record<string, KellyBand>
} {
  const kelly: Record<string, KellyBand> = {}
  draft.kellyBands.forEach((row, idx) => {
    const key = row.key.trim() || `band_${idx}`
    kelly[key] = row.band
  })
  return {
    name: draft.name.trim(),
    weights_json: draft.weights,
    thresholds_json: draft.thresholds,
    kelly_bands_json: kelly
  }
}

function pctLabel(value: number): string {
  if (!Number.isFinite(value)) return '-'
  return `${(value * 100).toFixed(2)}%`
}

export function ModelClient() {
  const user = useAuthStore((s) => s.user)
  const canEdit = user?.role === 'admin'

  const [configs, setConfigs] = useState<ModelConfig[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [mode, setMode] = useState<Mode>('view')
  const [draft, setDraft] = useState<Draft | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)

  const selected = useMemo(
    () => configs.find((c) => c.id === selectedId) ?? null,
    [configs, selectedId]
  )

  const loadList = useCallback(async (preferId?: number) => {
    setLoading(true)
    try {
      const res = await listModelConfigs()
      setConfigs(res.items)
      setError(null)
      const next =
        preferId != null && res.items.some((c) => c.id === preferId)
          ? preferId
          : (res.items.find((c) => c.is_active)?.id ?? res.items[0]?.id ?? null)
      setSelectedId(next)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadList()
  }, [loadList])

  const weightTotal = useMemo(() => {
    if (!draft) return 0
    return WEIGHT_KEYS.reduce<number>((acc, k) => acc + (Number(draft.weights[k]) || 0), 0)
  }, [draft])

  const handleEdit = () => {
    if (!selected) return
    setDraft(toDraft(selected))
    setMode('edit')
    setError(null)
  }

  const handleCreate = () => {
    setDraft({
      ...BLANK_DRAFT,
      kellyBands: BLANK_DRAFT.kellyBands.map((r) => ({ ...r, band: { ...r.band } }))
    })
    setMode('create')
    setError(null)
  }

  const handleCancel = () => {
    setDraft(null)
    setMode('view')
    setError(null)
  }

  const handleActivate = async () => {
    if (!selected) return
    setSaving(true)
    try {
      const res = await activateModelConfig(selected.id)
      await loadList(selected.id)
      setNotice(`已激活「${selected.name}」，同步重算今日评分 ${res.scores_recomputed} 条`)
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const handleClone = async () => {
    if (!selected) return
    const name = window.prompt(`克隆 ${selected.name} 为新名称：`, `${selected.name}-v2`)
    if (!name) return
    setSaving(true)
    try {
      const res = await cloneModelConfig(selected.id, name.trim())
      await loadList(res.id)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const handleSave = async () => {
    if (!draft) return
    setSaving(true)
    try {
      const payload = toPayload(draft)
      if (mode === 'create') {
        const res = await createModelConfig(payload)
        await loadList(res.id)
      } else if (selected) {
        const res = await updateModelConfig(selected.id, payload)
        await loadList(res.id)
      }
      setDraft(null)
      setMode('view')
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const updateWeight = (k: keyof WeightsJson, v: string) => {
    if (!draft) return
    const num = v === '' ? 0 : Number(v)
    setDraft({ ...draft, weights: { ...draft.weights, [k]: Number.isFinite(num) ? num : 0 } })
  }

  const updateThreshold = (k: string, v: string) => {
    if (!draft) return
    const num = v === '' ? 0 : Number(v)
    setDraft({
      ...draft,
      thresholds: { ...draft.thresholds, [k]: Number.isFinite(num) ? num : 0 }
    })
  }

  const updateKellyRow = (idx: number, patch: Partial<KellyBand> & { key?: string }) => {
    if (!draft) return
    const next = draft.kellyBands.map((row, i) => {
      if (i !== idx) return row
      return {
        key: patch.key ?? row.key,
        band: {
          min_score: patch.min_score ?? row.band.min_score,
          max_score: patch.max_score ?? row.band.max_score,
          kelly_pct: patch.kelly_pct ?? row.band.kelly_pct
        }
      }
    })
    setDraft({ ...draft, kellyBands: next })
  }

  const addKellyRow = () => {
    if (!draft) return
    setDraft({
      ...draft,
      kellyBands: [
        ...draft.kellyBands,
        {
          key: `band_${draft.kellyBands.length + 1}`,
          band: { min_score: 0, max_score: 1, kelly_pct: 0 }
        }
      ]
    })
  }

  const removeKellyRow = (idx: number) => {
    if (!draft) return
    setDraft({ ...draft, kellyBands: draft.kellyBands.filter((_, i) => i !== idx) })
  }

  const readOnly = mode === 'view'
  const showDraft = draft != null && (mode === 'edit' || mode === 'create')
  const displayedName = showDraft ? draft.name : (selected?.name ?? '')
  const displayedWeights = showDraft ? draft.weights : (selected?.weights_json ?? null)
  const displayedThresholds = showDraft ? draft.thresholds : (selected?.thresholds_json ?? null)
  const displayedBands = showDraft
    ? draft.kellyBands
    : selected
      ? Object.entries(selected.kelly_bands_json ?? {}).map(([k, b]) => ({ key: k, band: b }))
      : []
  const extraThresholdEntries = Object.entries(displayedThresholds ?? {}).filter(
    ([k]) => !THRESHOLD_KEYS.includes(k)
  )
  const isRuleModel = String(displayedThresholds?.strategy ?? '') === 'empirical_v32_filtered'

  return (
    <div className={styles.container}>
      <aside className={styles.sidebar}>
        <div className={styles.sidebarHeader}>
          <div className={styles.sidebarTitle}>版本列表</div>
          {canEdit && (
            <button
              className={styles.button}
              onClick={handleCreate}
              disabled={saving}
              aria-label="新建模型版本"
            >
              新建
            </button>
          )}
        </div>
        {loading ? (
          <div className={styles.empty}>加载中…</div>
        ) : configs.length === 0 ? (
          <div className={styles.empty}>暂无版本</div>
        ) : (
          configs.map((c) => (
            <div
              key={c.id}
              className={`${styles.listItem} ${selectedId === c.id ? styles.listItemActive : ''}`}
              onClick={() => {
                setSelectedId(c.id)
                setMode('view')
                setDraft(null)
              }}
              role="button"
              tabIndex={0}
            >
              <div
                style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
              >
                <span style={{ fontWeight: 500 }}>{c.name}</span>
                {c.is_active && <span className={styles.badge}>激活</span>}
              </div>
              <div className={styles.listMeta}>
                <span>#{c.id}</span>
                <span>{c.parent_id != null ? `克隆自 #${c.parent_id}` : '原创'}</span>
              </div>
            </div>
          ))
        )}
      </aside>

      <main className={styles.main}>
        <div className={styles.mainHeader}>
          <div>
            <div className={styles.title}>
              {mode === 'create' ? '新建模型' : displayedName || '选择一个版本'}
            </div>
            <div className={styles.subtitle}>
              6 维权重 · 评分阈值 · Kelly 档位 · 参数解释
              {!canEdit && ' · 只读模式'}
            </div>
          </div>
          <div className={styles.actions}>
            {readOnly && selected && canEdit && (
              <>
                <button
                  className={styles.buttonPrimary}
                  onClick={handleActivate}
                  disabled={saving || selected.is_active}
                >
                  {selected.is_active ? '已激活' : '激活'}
                </button>
                <button className={styles.button} onClick={handleClone} disabled={saving}>
                  克隆
                </button>
                <button className={styles.button} onClick={handleEdit} disabled={saving}>
                  编辑
                </button>
              </>
            )}
            {!readOnly && (
              <>
                <button
                  className={styles.buttonPrimary}
                  onClick={handleSave}
                  disabled={saving}
                  aria-label="保存模型配置"
                >
                  {saving ? '保存中…' : '保存'}
                </button>
                <button className={styles.button} onClick={handleCancel} disabled={saving}>
                  取消
                </button>
              </>
            )}
          </div>
        </div>

        {error && <div className={styles.errorBanner}>{error}</div>}
        {notice && (
          <div className={styles.noticeBanner} role="status">
            {notice}
          </div>
        )}

        {!selected && !showDraft ? (
          <div className={styles.empty}>请选择左侧版本查看详情</div>
        ) : (
          <>
            <section className={styles.section}>
              <div className={styles.sectionTitle}>基本信息</div>
              <div className={styles.explainBox}>
                <strong>{isRuleModel ? '经验规则模型' : '6 维加权模型'}</strong>
                <span>
                  {isRuleModel
                    ? '这个模型先用 V3.2 经验规则判断是否推荐，再用 6 维分数解释盘口和基本面。规则分不是连续加权分，而是命中规则后的固定映射：DRAW_V32_CORE 平=108，HDRAW_V32_CORE 让平=116；未命中规则时只展示 6 维解释分。'
                    : '这个模型把 6 个维度按权重相加，总分达到阈值后才会推荐。适合做可解释的基础评分。'}
                </span>
              </div>
              {!isRuleModel && (
                <div className={styles.rulePanel}>
                  <div className={styles.rulePanelHeader}>
                    <strong>default 打分规则</strong>
                    <span>总分 = 6 个维度得分按当前权重折算后相加，满分通常按 120 理解。</span>
                  </div>
                  <div className={styles.ruleGrid}>
                    {DEFAULT_SCORE_RULES.map((rule) => (
                      <div key={rule.title} className={styles.ruleCard}>
                        <div className={styles.ruleCardTitle}>
                          <span>{rule.title}</span>
                          <b>{rule.max}分</b>
                        </div>
                        <ul>
                          {rule.lines.map((line) => (
                            <li key={line}>{line}</li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              <div className={styles.grid}>
                <label className={styles.field}>
                  名称
                  <input
                    className={styles.input}
                    value={displayedName}
                    onChange={(e) => draft && setDraft({ ...draft, name: e.target.value })}
                    disabled={readOnly}
                    aria-label="模型名称"
                  />
                </label>
              </div>
            </section>

            <section className={styles.section}>
              <div className={styles.sectionTitle}>6 维权重（总上限 {weightTotal || '—'}）</div>
              <div className={styles.sectionHint}>
                权重代表每个维度最高能贡献多少分。总权重越接近 120，分数越容易和历史回测档位对齐。默认建议：欧赔 25、亚盘 20、进球 20、战意 15、压缩 20、球队状态 20。
              </div>
              <div className={styles.paramGrid}>
                {WEIGHT_KEYS.map((k) => (
                  <div key={k} className={styles.paramCard}>
                    <label className={styles.field}>
                      <span className={styles.paramLabel}>
                        {WEIGHT_LABELS[k]} <small>{k}</small>
                      </span>
                      <input
                        type="number"
                        className={styles.input}
                        value={displayedWeights?.[k] ?? 0}
                        min={0}
                        max={100}
                        onChange={(e) => updateWeight(k, e.target.value)}
                        disabled={readOnly}
                        aria-label={`权重-${k}`}
                      />
                    </label>
                    <div className={styles.paramExplain}>
                      <p>{WEIGHT_GUIDE[k].meaning}</p>
                      <span>{WEIGHT_GUIDE[k].range}</span>
                      <span>调低：{WEIGHT_GUIDE[k].low}</span>
                      <span>调高：{WEIGHT_GUIDE[k].high}</span>
                      <b>建议：{WEIGHT_GUIDE[k].recommended}</b>
                    </div>
                  </div>
                ))}
              </div>
              {showDraft && <div className={styles.totalBanner}>权重合计：{weightTotal}</div>}
            </section>

            <section className={styles.section}>
              <div className={styles.sectionTitle}>阈值</div>
              <div className={styles.sectionHint}>
                阈值决定“多少分才算候选、多少分才推荐”。阈值越高越保守，推荐更少；阈值越低覆盖更多，但容易引入噪音。
              </div>
              <div className={styles.paramGrid}>
                {THRESHOLD_KEYS.map((k) => (
                  <div key={k} className={styles.paramCard}>
                    <label className={styles.field}>
                      <span className={styles.paramLabel}>
                        {THRESHOLD_GUIDE[k].label} <small>{k}</small>
                      </span>
                      <input
                        type="number"
                        className={styles.input}
                        value={displayedThresholds?.[k] ?? 0}
                        onChange={(e) => updateThreshold(k, e.target.value)}
                        disabled={readOnly}
                        aria-label={`阈值-${k}`}
                      />
                    </label>
                    <div className={styles.paramExplain}>
                      <p>{THRESHOLD_GUIDE[k].meaning}</p>
                      <span>{THRESHOLD_GUIDE[k].range}</span>
                      <span>{THRESHOLD_GUIDE[k].effect}</span>
                      <b>建议：{THRESHOLD_GUIDE[k].recommended}</b>
                    </div>
                  </div>
                ))}
              </div>
              {extraThresholdEntries.length > 0 && (
                <div className={styles.extraGrid}>
                  {extraThresholdEntries.map(([k, v]) => (
                    <div key={k} className={styles.extraItem}>
                      <div>
                        <strong>{k}</strong>
                        <span>{EXTRA_THRESHOLD_GUIDE[k] ?? '扩展参数，用于特定模型策略。'}</span>
                      </div>
                      <code>{String(v)}</code>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className={styles.section}>
              <div className={styles.sectionTitle}>Kelly 档位</div>
              <div className={styles.sectionHint}>
                Kelly 是建议下注本金比例，不是胜率。比如 0.010 表示本金 1%。建议保守使用，实盘不建议超过 2%。
              </div>
              {displayedBands.length === 0 && (
                <div className={styles.empty}>尚未配置 Kelly 档位</div>
              )}
              {displayedBands.map((row, idx) => (
                <div key={`${row.key}-${idx}`} className={styles.kellyRow}>
                  <label className={styles.field}>
                    名称
                    <input
                      className={styles.input}
                      value={row.key}
                      onChange={(e) => updateKellyRow(idx, { key: e.target.value })}
                      disabled={readOnly}
                      aria-label={`kelly-key-${idx}`}
                    />
                  </label>
                  <label className={styles.field}>
                    min
                    <input
                      type="number"
                      className={styles.input}
                      value={row.band.min_score}
                      onChange={(e) => updateKellyRow(idx, { min_score: Number(e.target.value) })}
                      disabled={readOnly}
                      aria-label={`kelly-min-${idx}`}
                    />
                  </label>
                  <label className={styles.field}>
                    max
                    <input
                      type="number"
                      className={styles.input}
                      value={row.band.max_score}
                      onChange={(e) => updateKellyRow(idx, { max_score: Number(e.target.value) })}
                      disabled={readOnly}
                      aria-label={`kelly-max-${idx}`}
                    />
                  </label>
                  <label className={styles.field}>
                    kelly_pct
                    <input
                      type="number"
                      step={0.001}
                      className={styles.input}
                      value={row.band.kelly_pct}
                      onChange={(e) => updateKellyRow(idx, { kelly_pct: Number(e.target.value) })}
                      disabled={readOnly}
                      aria-label={`kelly-pct-${idx}`}
                    />
                  </label>
                  <div className={styles.kellyMeaning}>
                    {row.band.min_score}-{row.band.max_score} 分：建议 {pctLabel(row.band.kelly_pct)}
                  </div>
                  {!readOnly && (
                    <button
                      type="button"
                      className={styles.buttonDanger}
                      onClick={() => removeKellyRow(idx)}
                      aria-label={`删除档位 ${row.key}`}
                    >
                      删
                    </button>
                  )}
                </div>
              ))}
              <div className={styles.kellyGuide}>
                <span>{KELLY_GUIDE.min_score}</span>
                <span>{KELLY_GUIDE.max_score}</span>
                <span>{KELLY_GUIDE.kelly_pct}</span>
              </div>
              {!readOnly && (
                <button type="button" className={styles.button} onClick={addKellyRow}>
                  新增档位
                </button>
              )}
            </section>
          </>
        )}
      </main>
    </div>
  )
}
