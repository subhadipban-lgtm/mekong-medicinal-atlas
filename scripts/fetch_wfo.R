#!/usr/bin/env Rscript
# Match every atlas species name against the World Flora Online backbone with WorldFlora
# (Kindt 2020, https://doi.org/10.1002/aps3.11388), and write data/raw/wfo_match.csv.
#
# The static WFO backbone is downloaded once to data/raw/wfo/classification.csv by WFO.download().
# Run with: Rscript scripts/fetch_wfo.R
suppressPackageStartupMessages({ library(WorldFlora); library(jsonlite) })

root <- normalizePath(file.path(dirname(commandArgs(trailingOnly = FALSE)[4]), ".."))
raw  <- file.path(root, "data", "raw")
backbone <- file.path(raw, "wfo", "classification.csv")

if (!file.exists(backbone)) {
  message("Downloading the World Flora Online backbone (about 115 MB)…")
  WFO.download(save.dir = file.path(raw, "wfo"), WFO.remember = FALSE, timeout = 900)
}

names <- names(fromJSON(file.path(raw, "gbif_match_raw.json"), simplifyVector = FALSE))
message(sprintf("Matching %d names against World Flora Online…", length(names)))
res <- WFO.match(spec.data = data.frame(spec.name = names, stringsAsFactors = FALSE),
                 WFO.file = backbone, spec.name = "spec.name", Fuzzy = 0.1, verbose = FALSE)
write.csv(as.data.frame(res), file.path(raw, "wfo_match.csv"), row.names = FALSE)
message("Wrote data/raw/wfo_match.csv")
