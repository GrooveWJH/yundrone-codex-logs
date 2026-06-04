#import "theme.typ": valid-metrics, valid-periods

#let _ensure-choice(value, choices, kind) = {
  if value not in choices {
    panic("Unknown " + kind + ": " + str(value))
  }
}

#let parse-metric-value(label) = {
  let text = str(label).trim()
  if text.ends-with("M") {
    float(text.slice(0, -1)) * 1000000
  } else if text.ends-with("K") {
    float(text.slice(0, -1)) * 1000
  } else {
    float(text)
  }
}

#let metric-csv-path(metric, period, base-dir: "../../outputs/metrics") = {
  _ensure-choice(metric, valid-metrics, "metric")
  _ensure-choice(period, valid-periods, "period")
  return base-dir + "/" + metric + "/" + period + ".csv"
}

#let metric-time-path(metric, base-dir: "../../outputs/metrics") = {
  _ensure-choice(metric, valid-metrics, "metric")
  return base-dir + "/" + metric + "/time"
}

#let metric-period-time-path(metric, period, base-dir: "../../outputs/metrics") = {
  _ensure-choice(metric, valid-metrics, "metric")
  _ensure-choice(period, valid-periods, "period")
  return base-dir + "/" + metric + "/" + period + ".time"
}

#let load-time(metric, base-dir: "../../outputs/metrics") = {
  read(metric-time-path(metric, base-dir: base-dir)).trim()
}

#let load-period-time(metric, period, base-dir: "../../outputs/metrics") = {
  read(metric-period-time-path(metric, period, base-dir: base-dir)).trim()
}

#let load-ranking(metric, period, base-dir: "../../outputs/metrics") = {
  let rows = csv(metric-csv-path(metric, period, base-dir: base-dir))
  if rows.len() <= 1 {
    return ()
  }

  rows.slice(1).map(row => {
    let label = row.at(2, default: "0")
    (
      rank: row.at(0, default: ""),
      name: row.at(1, default: ""),
      label: label,
      value: parse-metric-value(label),
    )
  })
}
