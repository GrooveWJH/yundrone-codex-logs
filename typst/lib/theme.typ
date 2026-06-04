#let poster-theme = (
  font: ("Noto Sans CJK SC","Noto Sans SC"),
  background: rgb("#f6f8fb"),
  primary: rgb("#111426"),
  secondary: rgb("#6b6b6b"),
  value: rgb("#7a848c"),
  value-on-bar: rgb("#000000"),
  rank: rgb("#b5bcc3"),
  grid: rgb("#dde2e6"),
  track: rgb("#e9eef2"),
  bar: rgb("#252b33"),
  top-line: rgb("#4f565f"),
  rainbow-stops: (
    (255, 107, 107),
    (255, 169, 77),
    (255, 212, 59),
    (105, 219, 124),
    (56, 217, 169),
    (77, 171, 247),
    (177, 151, 252),
  ),
  poster-width: 19.4cm,
  trio-gap: 1.2cm,
  chart-width: 15.9cm,
  chart-axis-bottom-safe-area: .72cm,
  chart-y-bottom-padding: 1.9,
  chart-y-top-padding: 2.55,
  chart-grid-bottom-extra: 1.9,
  chart-grid-top-extra: .35,
  chart-top-line-offset: 2.05,
  chart-top-line-x-start-ratio: 0,
  chart-top-line-x-end-ratio: 1,
  chart-top-line-stroke: 1.2pt,
  chart-bar-width: .72,
  chart-grid-stroke: .5pt,
  value-label-left-padding-ratio: .006,
  value-label-inside-min-ratio: .1,
  outer-inset: (x: 1.2cm, y: 1cm),
  header-chart-gap: 0em,
  header-right-gap: .3em,
  metric-size: 2em,
  report-size: 2.5em,
  period-size: 2.5em,
  window-size: 1.5em,
  rank-weight: 300,
  row-height: 1.5cm,
  chart-extra-height: 2.05cm,
)

#let metric-specs = (
  tokens: (
    title: "Codex token",
    report-label: "用量播报",
    accent: rgb("#332af5"),
  ),
  quota: (
    title: "Codex quota",
    report-label: "额度播报",
    accent: rgb("#047236"),
  ),
  intensity: (
    title: "Codex intensity",
    report-label: "强度播报",
    accent: rgb("#8559e4"),
  ),
)

#let period-specs = (
  daily: (
    label: "日统计",
    scope: "今日",
  ),
  weekly: (
    label: "周统计",
    scope: "本周",
  ),
  monthly: (
    label: "月统计",
    scope: "本月",
  ),
)
 
#let valid-metrics = metric-specs.keys()
#let valid-periods = period-specs.keys()

#let require-spec(table, key, kind) = {
  if key not in table {
    panic("Unknown " + kind + ": " + str(key))
  }
  table.at(key)
}
