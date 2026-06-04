#import "@preview/lilaq:0.6.0" as lq
#import "data.typ": load-period-time, load-ranking, load-time
#import "theme.typ": metric-specs, period-specs, poster-theme, require-spec

#let _text(body, theme: poster-theme, size: 1em, weight: 400, fill: black) = {
  text(font: theme.font, size: size, weight: weight, fill: fill)[#body]
}

#let _nice-step(max-value, tick-count: 5) = {
  if max-value <= 0 {
    return 1
  }
  let raw = max-value / tick-count
  let power = calc.pow(10, calc.floor(calc.log(raw, base: 10)))
  let normalized = raw / power
  let factor = if normalized <= 1 {
    1
  } else if normalized <= 2 {
    2
  } else if normalized <= 5 {
    5
  } else {
    10
  }
  factor * power
}

#let _axis-max(max-value, step) = {
  if max-value <= 0 {
    step
  } else {
    calc.ceil(max-value / step) * step
  }
}

#let _tick-values(axis-max, step) = {
  let count = int(calc.round(axis-max / step))
  range(0, count + 1).map(i => i * step)
}

#let _compact-count(value) = {
  if value >= 1000000 {
    str(calc.round(value / 1000000 * 100) / 100) + "M"
  } else if value >= 1000 {
    str(calc.round(value / 1000 * 10) / 10) + "K"
  } else {
    str(int(calc.round(value)))
  }
}

#let _compact-decimal(value) = {
  let rounded = calc.round(value * 100) / 100
  if rounded == int(rounded) {
    str(int(rounded))
  } else {
    str(rounded)
  }
}

#let _quota-dollars(value) = value / 1000000 * 2

#let _dollar-label(value) = "$" + _compact-decimal(_quota-dollars(value))

#let _tick-label(value, metric) = {
  if metric == "quota" {
    let label = _dollar-label(value)
    [#label]
  } else if value == 0 {
    [0]
  } else if metric == "tokens" {
    let label = _compact-count(value)
    [#label]
  } else {
    let label = _compact-decimal(value)
    [#label]
  }
}

#let _value-label(row, metric) = if metric == "quota" {
  _dollar-label(row.value)
} else {
  row.label
}

#let _lerp(start, end, amount) = start + (end - start) * amount

#let _mix-rgb(left, right, amount) = {
  rgb(
    int(calc.round(_lerp(left.at(0), right.at(0), amount))),
    int(calc.round(_lerp(left.at(1), right.at(1), amount))),
    int(calc.round(_lerp(left.at(2), right.at(2), amount))),
  )
}

#let _rainbow-color(index, count, theme) = {
  let stops = theme.rainbow-stops
  if count <= 1 or stops.len() == 1 {
    let first = stops.first()
    return rgb(first.at(0), first.at(1), first.at(2))
  }

  let progress = index / (count - 1)
  let segment-count = stops.len() - 1
  let scaled = progress * segment-count
  let segment = calc.min(int(calc.floor(scaled)), segment-count - 1)
  let amount = scaled - segment
  _mix-rgb(stops.at(segment), stops.at(segment + 1), amount)
}

#let _usage-header(metric, period, window, theme, show-left: true) = {
  let metric-info = require-spec(metric-specs, metric, "metric")
  let period-info = require-spec(period-specs, period, "period")
  let caption = if window == none { period-info.scope } else { window }
  let left-header = if show-left {
    stack(
      spacing: 0pt,
      block(inset: (y: .5em, x: 0pt))[
        #_text(metric-info.title, theme: theme, size: theme.metric-size, weight: 700, fill: metric-info.accent)
      ],
      block(inset: (y: .5em, x: 0pt))[
        #_text(metric-info.report-label, theme: theme, size: theme.report-size, weight: 700, fill: theme.primary)
      ],
    )
  } else {
    stack(
      spacing: 0pt,
      block(inset: (y: .5em, x: 0pt))[
        #_text(metric-info.title, theme: theme, size: theme.metric-size, weight: 700, fill: theme.background)
      ],
      block(inset: (y: .5em, x: 0pt))[
        #_text(metric-info.report-label, theme: theme, size: theme.report-size, weight: 700, fill: theme.background)
      ],
    )
  }

  grid(
    columns: (1fr, auto),
    left-header,
    align(right)[
      #stack(
        spacing: 0pt,
        block(inset: (y: .5em, x: 0pt))[
          #_text(period-info.label, theme: theme, size: theme.period-size, weight: 700, fill: theme.primary)
        ],
        v(theme.header-right-gap),
        block(inset: (y: .5em, x: 0pt))[
          #_text(caption, theme: theme, size: theme.window-size, weight: 300, fill: theme.secondary)
        ],
      )
    ],
  )
}

#let _ranking-chart(rows, metric, theme) = {
  let frame-width = theme.poster-width - theme.outer-inset.x * 2
  let row-count = rows.len()
  if row-count == 0 {
    return block(width: frame-width, fill: theme.background, inset: 2em)[
      #align(center)[#_text([暂无数据], theme: theme, fill: theme.secondary)]
    ]
  }

  let values = rows.map(row => row.value)
  let max-value = calc.max(..values)
  let step = _nice-step(max-value)
  let axis-max = _axis-max(max-value, step)
  let ticks = _tick-values(axis-max, step)
  let positions = range(0, row-count).map(i => (row-count - 1 - i) * 2)
  let tracks = positions.map(_ => axis-max)
  let bar-fills = range(0, row-count).map(i => _rainbow-color(i, row-count, theme))
  let y-max = (row-count - 1) * 2
  let chart-y-min = 0 - theme.chart-grid-bottom-extra
  let chart-y-max = y-max + theme.chart-y-top-padding
  let top-line-y = y-max + theme.chart-top-line-offset
  let grid-y-max = top-line-y - theme.chart-grid-top-extra
  let top-line-x-min = axis-max * theme.chart-top-line-x-start-ratio
  let top-line-x-max = axis-max * theme.chart-top-line-x-end-ratio
  let height = theme.chart-extra-height + row-count * theme.row-height

  block(width: frame-width)[
    #align(center)[
      #pad(bottom: theme.chart-axis-bottom-safe-area)[
        #show: lq.set-tick(stroke: 0pt)
        #lq.diagram(
          width: theme.chart-width,
          height: height,
          bounds: "data-area",
          xlim: (0, axis-max),
          ylim: (chart-y-min, chart-y-max),
          margin: 0%,
          legend: none,
          fill: theme.background,
          grid: none,
          xaxis: (
            ticks: ticks.map(tick => (tick, _tick-label(tick, metric))),
            subticks: none,
            stroke: none,
            mirror: none,
          ),
          yaxis: none,

          lq.vlines(
            ..ticks,
            min: chart-y-min,
            max: grid-y-max,
            stroke: theme.chart-grid-stroke + theme.grid,
            z-index: 0,
          ),
          lq.hlines(
            top-line-y,
            min: top-line-x-min,
            max: top-line-x-max,
            stroke: theme.chart-top-line-stroke + theme.top-line,
            z-index: 3,
          ),
          lq.hbar(
            tracks,
            positions,
            width: theme.chart-bar-width,
            fill: theme.track,
            stroke: none,
            z-index: 1,
          ),
          lq.hbar(
            values,
            positions,
            width: theme.chart-bar-width,
            fill: bar-fills,
            stroke: none,
            z-index: 2,
          ),

          ..rows.enumerate().map(((i, row)) => {
            let y = (row-count - 1 - i) * 2
            let value-label = _value-label(row, metric)
            let can-label-inside = row.value >= axis-max * theme.value-label-inside-min-ratio
            let label-x = if can-label-inside {
              axis-max * theme.value-label-left-padding-ratio
            } else {
              row.value + axis-max * theme.value-label-left-padding-ratio
            }

            (
              lq.place(
                axis-max * -.006,
                y + .95,
                align: right + horizon,
                text(font: theme.font, size: 17pt, fill: theme.rank, weight: theme.rank-weight)[#("#" + row.rank)],
              ),
              lq.place(
                axis-max * .003,
                y + .95,
                align: left + horizon,
                text(font: theme.font, size: 19pt, fill: theme.primary, weight: 700)[#row.name],
              ),
              lq.place(
                label-x,
                y,
                align: left + horizon,
                text(font: theme.font, size: 15pt, fill: theme.value-on-bar, weight: 400)[#value-label],
              ),
            )
          }).flatten(),
        )
      ]
    ]
  ]
}

#let usage-poster(metric, period, window: none, csv-dir: "../../outputs/metrics", theme: poster-theme) = {
  let rows = load-ranking(metric, period, base-dir: csv-dir)
  let window-text = if window == none { load-time(metric, base-dir: csv-dir) } else { window }

  block(width: theme.poster-width, fill: theme.background, inset: theme.outer-inset)[
    #_usage-header(metric, period, window-text, theme)
    #v(theme.header-chart-gap)
    #_ranking-chart(rows, metric, theme)
  ]
}

#let _usage-poster-column(metric, period, window, theme, show-left: true, csv-dir: "../../outputs/metrics") = {
  let rows = load-ranking(metric, period, base-dir: csv-dir)

  block(width: theme.poster-width, fill: theme.background, inset: theme.outer-inset)[
    #_usage-header(metric, period, window, theme, show-left: show-left)
    #v(theme.header-chart-gap)
    #_ranking-chart(rows, metric, theme)
  ]
}

#let usage-trio-poster(metric, csv-dir: "../../outputs/metrics", theme: poster-theme) = {
  let periods = ("daily", "weekly", "monthly")
  let windows = periods.map(period => load-period-time(metric, period, base-dir: csv-dir))
  let total-width = theme.poster-width * 3 + theme.trio-gap * 2

  block(width: total-width, fill: theme.background)[
    #grid(
      columns: (theme.poster-width, theme.poster-width, theme.poster-width),
      gutter: theme.trio-gap,
      ..periods.enumerate().map(((i, period)) => {
        _usage-poster-column(
          metric,
          period,
          windows.at(i),
          theme,
          show-left: i == 0,
          csv-dir: csv-dir,
        )
      }),
    )
  ]
}
