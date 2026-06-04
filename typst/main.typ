#import "lib/poster.typ": usage-poster
#import "lib/theme.typ": poster-theme

#set page(width: auto, height: auto, margin: 0pt, fill: poster-theme.background)
#set text(font: ("Noto Sans CJK SC", "Noto Sans SC"))

#let metric = sys.inputs.at("metric", default: "tokens")
#let period = sys.inputs.at("period", default: "monthly")
#let window = sys.inputs.at("window", default: none)
#let csv-dir = sys.inputs.at("csv-dir", default: "../../outputs/metrics")

#usage-poster(metric, period, window: window, csv-dir: csv-dir)
