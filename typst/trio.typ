#import "lib/poster.typ": usage-trio-poster
#import "lib/theme.typ": poster-theme

#set page(width: auto, height: auto, margin: 0pt, fill: poster-theme.background)
#set text(font: ("Noto Sans CJK SC", "Noto Sans SC"))

#let metric = sys.inputs.at("metric", default: "tokens")
#let csv-dir = sys.inputs.at("csv-dir", default: "../../outputs/metrics")

#usage-trio-poster(metric, csv-dir: csv-dir)
