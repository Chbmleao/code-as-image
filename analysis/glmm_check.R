# Checks the methodology 3.3 binomial GLMM on simulated data with the real design, and fits it
# once on the block-1 cells. Inputs come from scripts/glmm_cells.py (scratch/glmm/*.csv).
#
#   OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 mamba run -n codeimg-glmm Rscript \
#     analysis/glmm_check.R [--bench coderujb|deveval] [--reps 50] [--workers 6] [--block1]
#     [--scenario plausible|block1] [--in scratch/glmm] [--out results/glmm]
#     [--rss <scenario>/<bench>=<MB>/<wall s>,...]
#
# Writes <out>/sim_<bench>_<scenario>.csv and <out>/glmm.md, which is rebuilt from the CSVs of
# both scenarios; --reps 0 skips the fits and only rebuilds it. --block1 (the real-data fit) and
# the lme4 refits belong to the plausible scenario. Versions are in analysis/conda-osx-arm64.lock.
suppressPackageStartupMessages({
  library(glmmTMB)
  library(lme4)
  library(parallel)
})

args <- commandArgs(trailingOnly = TRUE)
opt <- function(name, default) {
  i <- match(paste0("--", name), args)
  if (is.na(i)) default else args[i + 1]
}
script_dir <- dirname(normalizePath(sub("^--file=", "", grep("^--file=", commandArgs(), value = TRUE))))
root <- dirname(script_dir)
path <- function(p) if (startsWith(p, "/")) p else file.path(root, p)

benches <- if (is.na(match("--bench", args))) c("coderujb", "deveval") else opt("bench", NULL)
reps <- as.integer(opt("reps", 50))
workers <- as.integer(opt("workers", 6))
scenario <- opt("scenario", "plausible")
stopifnot(scenario %in% c("plausible", "block1"))
do_block1 <- "--block1" %in% args && scenario == "plausible"
in_dir <- path(opt("in", "scratch/glmm"))
out_dir <- path(opt("out", "results/glmm"))
rss <- opt("rss", "")

SEED <- 20261112
CONDS <- c("text", "image10", "image12", "image14")
MODELS <- c("cyankiwi/Qwen3.5-27B-AWQ-4bit" = "Qwen3.5 27B", "google/gemma-4-12B-it" = "Gemma 4 12B",
            "jeffcookio/Mistral-Small-3.2-24B-Instruct-2506-awq-sym" = "Mistral Small 3.2 24B",
            "Qwen/Qwen3.5-9B" = "Qwen3.5 9B", "Qwen/Qwen2.5-VL-7B-Instruct" = "Qwen2.5-VL 7B")
TITLES <- c(coderujb = "CoderUJB", deveval = "DevEval")
TERMS <- c("item", "item:model", "item:condition", "project", "project:condition", "cell")
TRUE_SD <- c(item = 1.5, "item:model" = 0.8, "item:condition" = 0.5, project = 0.5,
             "project:condition" = 0.3, cell = 0.5)
# block-1 scenario truth: the block-1 fit's SDs rounded to 0.1 (results/glmm/glmm.md, Block-1 fit)
BLOCK1_SD <- list(
  coderujb = c(item = 4.0, "item:model" = 1.3, "item:condition" = 1.0, project = 0,
               "project:condition" = 0, cell = 1.4),
  deveval = c(item = 4.8, "item:model" = 1.1, "item:condition" = 1.1, project = 0,
              "project:condition" = 0.7, cell = 1.3))
SCENARIOS <- c("plausible", "block1")
truth_sd <- function(b, scenario) if (scenario == "plausible") TRUE_SD else BLOCK1_SD[[b]]
gated_terms <- function(b, scenario) {
  if (scenario == "plausible") {
    if (b == "coderujb") TERMS[1:3] else TERMS[1:5]
  } else {
    sd <- BLOCK1_SD[[b]]
    cand <- if (b == "coderujb") TERMS[1:3] else c(TERMS[1:3], "project:condition")
    cand[sd[cand] > 0]
  }
}
FORMULA <- cbind(k, n - k) ~ model * condition + (1 | item) + (1 | item:model) +
  (1 | item:condition) + (1 | project) + (1 | project:condition) + (1 | cell)
MIN_CONVERGED <- 0.96
SD_TOL <- 0.20
FIXED_TOL <- 0.15
LME4_TOL <- 0.05
BOUNDARY <- 0.01
LME4_REPS <- if (scenario == "plausible") 1:2 else integer()

read_design <- function(b) read.csv(file.path(in_dir, paste0("design_", b, ".csv")),
                                    stringsAsFactors = FALSE)
read_cells <- function(b) read.csv(file.path(in_dir, paste0("block1_", b, "_cells.csv")),
                                   stringsAsFactors = FALSE)

grid_of <- function() {
  g <- expand.grid(model = names(MODELS), condition = CONDS, stringsAsFactors = FALSE)
  g$model <- factor(g$model, levels = names(MODELS))
  g$condition <- factor(g$condition, levels = CONDS)
  g
}

# cell logits at random effects 0, from the pooled block-1 pass rate, rounded to 0.1
truth_logits <- function(b) {
  d <- read_cells(b)
  g <- grid_of()
  g$logit <- mapply(function(m, c) {
    s <- d[d$model == m & d$condition == c, ]
    round(qlogis(sum(s$k) / sum(s$n)), 1)
  }, as.character(g$model), as.character(g$condition))
  g
}

quantities <- function(logits, grid) {
  names(logits) <- paste0("logit:", MODELS[as.character(grid$model)], ":", grid$condition)
  pen <- sapply(names(MODELS), function(m) {
    s <- grid$model == m
    logits[s & grid$condition == "text"] - mean(logits[s & grid$condition != "text"])
  })
  names(pen) <- paste0("penalty:", MODELS)
  c(logits, pen)
}

truth_vector <- function(b, sds) {
  g <- truth_logits(b)
  c(setNames(sds[TERMS], paste0("sd:", TERMS)), quantities(g$logit, g))
}

simulate_data <- function(b, design, g, rep, sds) {
  set.seed(SEED + rep)
  d <- expand.grid(item = design$item, model = names(MODELS), condition = CONDS,
                   stringsAsFactors = FALSE)
  d <- merge(d, design, by = "item", sort = FALSE)
  d$model <- factor(d$model, levels = names(MODELS))
  d$condition <- factor(d$condition, levels = CONDS)
  d$cell <- factor(seq_len(nrow(d)))
  draw <- function(key, sd) rnorm(nlevels(key), 0, sd)[as.integer(key)]
  key <- function(...) factor(paste(..., sep = ":"))
  mu <- g$logit[match(paste(d$model, d$condition), paste(g$model, g$condition))]
  eta <- mu + draw(factor(d$item), sds[["item"]]) +
    draw(key(d$item, d$model), sds[["item:model"]]) +
    draw(key(d$item, d$condition), sds[["item:condition"]]) +
    draw(factor(d$project), sds[["project"]]) +
    draw(key(d$project, d$condition), sds[["project:condition"]]) +
    draw(d$cell, sds[["cell"]])
  d$k <- rbinom(nrow(d), d$n, plogis(eta))
  d
}

capture <- function(expr) {
  msgs <- character()
  val <- withCallingHandlers(
    tryCatch(expr, error = function(e) structure(conditionMessage(e), class = "fit_error")),
    warning = function(w) {
      msgs <<- c(msgs, conditionMessage(w))
      invokeRestart("muffleWarning")
    })
  list(value = val, warnings = unique(msgs))
}

estimates <- function(engine, fit, grid) {
  beta <- if (engine == "glmmTMB") fixef(fit)$cond else fixef(fit)
  X <- model.matrix(~ model * condition, grid)
  logits <- drop(X %*% beta[colnames(X)])
  sds <- if (engine == "glmmTMB") {
    vc <- VarCorr(fit)$cond
    sapply(vc, function(m) attr(m, "stddev")[[1]])
  } else {
    v <- as.data.frame(VarCorr(fit))
    setNames(v$sdcor, v$grp)
  }
  c(setNames(sds[TERMS], paste0("sd:", TERMS)), quantities(logits, grid))
}

# one fit: converged is no error, optimizer code 0 and finite estimates
fit_one <- function(engine, d, grid) {
  secs <- NA_real_
  res <- capture({
    secs <- system.time(
      fit <- if (engine == "glmmTMB") {
        glmmTMB(FORMULA, data = d, family = binomial)
      } else {
        glmer(FORMULA, data = d, family = binomial, nAGQ = 1)
      })[["elapsed"]]
    fit
  })
  out <- list(engine = engine, seconds = secs, warnings = res$warnings, estimate = NULL,
              converged = FALSE, pdhess = NA, error = NA_character_)
  if (inherits(res$value, "fit_error")) {
    out$error <- unclass(res$value)
    return(out)
  }
  fit <- res$value
  est <- tryCatch(estimates(engine, fit, grid), error = function(e) NULL)
  if (is.null(est)) {
    out$error <- "estimates could not be extracted"
    return(out)
  }
  code <- if (engine == "glmmTMB") fit$fit$convergence else fit@optinfo$conv$opt
  out$estimate <- est
  out$converged <- identical(as.integer(code), 0L) && all(is.finite(est))
  if (engine == "glmmTMB") out$pdhess <- isTRUE(fit$sdr$pdHess)
  out
}

as_rows <- function(f, rep, truth) {
  est <- if (is.null(f$estimate)) rep(NA_real_, length(truth)) else f$estimate[names(truth)]
  data.frame(rep = rep, engine = f$engine, parameter = names(truth), truth = unname(truth),
             estimate = unname(est), converged = f$converged, pdhess = f$pdhess,
             seconds = round(f$seconds, 2), stringsAsFactors = FALSE)
}

run_bench <- function(b, sds) {
  design <- read_design(b)
  g <- truth_logits(b)
  truth <- truth_vector(b, sds)
  one <- function(r) {
    d <- simulate_data(b, design, g, r, sds)
    out <- list(glmmTMB = fit_one("glmmTMB", d, g))
    if (r %in% LME4_REPS) out$lme4 <- fit_one("lme4", d, g)
    cat(sprintf("%s rep %d: glmmTMB %.0f s, converged %s\n", b, r, out$glmmTMB$seconds,
                out$glmmTMB$converged), file = stderr())
    out
  }
  fits <- mclapply(seq_len(reps), one, mc.cores = workers, mc.preschedule = FALSE)
  # a worker killed by the OS returns NULL, not a try-error
  bad <- sapply(fits, function(f) is.null(f) || inherits(f, "try-error"))
  if (any(bad)) stop(sprintf("%s: replications %s died", b, paste(which(bad), collapse = ", ")))
  rows <- do.call(rbind, unlist(lapply(seq_along(fits), function(r) {
    lapply(fits[[r]], as_rows, rep = r, truth = truth)
  }), recursive = FALSE))
  notes <- do.call(rbind, unlist(lapply(seq_along(fits), function(r) {
    lapply(fits[[r]][names(fits[[r]]) == "lme4"], function(f) {
      data.frame(rep = r, error = if (is.na(f$error)) "" else f$error,
                 warnings = paste(f$warnings, collapse = "; "), stringsAsFactors = FALSE)
    })
  }), recursive = FALSE))
  list(rows = rows, lme4_notes = notes)
}

# the 6 SDs and level counts of the same model on the real block-1 cells; fixed effects are
# deliberately not extracted
run_block1 <- function(b) {
  d <- read_cells(b)
  d$model <- factor(d$model, levels = names(MODELS))
  d$condition <- factor(d$condition, levels = CONDS)
  d$cell <- factor(seq_len(nrow(d)))
  f <- fit_one("glmmTMB", d, grid_of())
  nlev <- c(item = nlevels(factor(d$item)),
            "item:model" = nlevels(interaction(d$item, d$model, drop = TRUE)),
            "item:condition" = nlevels(interaction(d$item, d$condition, drop = TRUE)),
            project = nlevels(factor(d$project)),
            "project:condition" = nlevels(interaction(d$project, d$condition, drop = TRUE)),
            cell = nlevels(d$cell))
  sd_names <- paste0("sd:", TERMS)
  truth <- truth_vector(b, TRUE_SD)[sd_names]
  rows <- as_rows(f, "block1", truth)
  lev <- data.frame(rep = "block1", engine = "glmmTMB", parameter = paste0("levels:", TERMS),
                    truth = NA_real_, estimate = unname(nlev), converged = f$converged,
                    pdhess = f$pdhess, seconds = round(f$seconds, 2), stringsAsFactors = FALSE)
  rbind(rows, lev)
}

f2 <- function(x) sprintf("%.2f", x)
mc_se <- function(x) if (length(x) > 1) sd(x) / sqrt(length(x)) else NA_real_
table_md <- function(header, rows) {
  c(paste0("| ", paste(header, collapse = " | "), " |"),
    paste0("|", paste(rep("---", length(header)), collapse = "|"), "|"),
    vapply(rows, function(r) paste0("| ", paste(r, collapse = " | "), " |"), ""))
}

summarise_bench <- function(sim) {
  g <- sim[sim$engine == "glmmTMB" & sim$rep != "block1" & !grepl("^levels:", sim$parameter), ]
  fits <- g[g$parameter == "sd:item", ]
  ok_reps <- fits$rep[fits$converged]
  ok <- g[g$rep %in% ok_reps, ]
  stat <- do.call(rbind, lapply(split(ok, ok$parameter), function(s) {
    data.frame(parameter = s$parameter[1], truth = s$truth[1], mean = mean(s$estimate),
               se = mc_se(s$estimate), stringsAsFactors = FALSE)
  }))
  rownames(stat) <- stat$parameter
  list(stat = stat, fits = fits, n_ok = nrow(fits[fits$converged, ]), n = nrow(fits))
}

report_bench <- function(b, sim, notes, scenario) {
  s <- summarise_bench(sim)
  st <- s$stat
  gated <- gated_terms(b, scenario)
  gated_sd <- paste0("sd:", gated)
  sd_rel <- abs(st[gated_sd, "mean"] - st[gated_sd, "truth"]) / st[gated_sd, "truth"]
  fixed <- c(paste0("logit:", MODELS, ":text"), paste0("penalty:", MODELS))
  fixed_dev <- abs(st[fixed, "mean"] - st[fixed, "truth"])
  c1 <- s$n_ok >= ceiling(MIN_CONVERGED * s$n)
  c2 <- all(sd_rel <= SD_TOL)
  c3 <- all(fixed_dev <= FIXED_TOL)
  verdict <- function(ok) if (ok) "PASS" else "FAIL"
  out <- c(sprintf("### %s", TITLES[[b]]), "",
           sprintf("- %s: Convergence, %d of %d fits converged (need %d). A rough screen.",
                   verdict(c1), s$n_ok, s$n, ceiling(MIN_CONVERGED * s$n)),
           sprintf("- %s: Standard deviations, the mean estimate is within %d%% of the truth for %s (largest gap %.0f%%).",
                   verdict(c2), round(100 * SD_TOL), paste(gated, collapse = ", "),
                   100 * max(sd_rel)),
           sprintf("- %s: Fixed effects, the mean of each model's text cell logit and size-averaged penalty is within %.2f logit of the truth (largest gap %.3f).",
                   verdict(c3), FIXED_TOL, max(fixed_dev)),
           "")
  bd <- sapply(TERMS, function(t) {
    e <- sim$estimate[sim$engine == "glmmTMB" & sim$rep != "block1" & sim$parameter == paste0("sd:", t)]
    sum(e < BOUNDARY, na.rm = TRUE)
  })
  sd_rows <- lapply(TERMS, function(t) {
    r <- st[paste0("sd:", t), ]
    bias <- if (r$truth == 0) sprintf("%+.2f (absolute)", r$mean) else
      sprintf("%+.0f%%", 100 * (r$mean / r$truth - 1))
    c(t, f2(r$truth), f2(r$mean), f2(r$se), bias,
      if (t %in% gated) "gated" else "reported", bd[[t]])
  })
  out <- c(out, "Standard deviations (logit scale), glmmTMB, mean over converged fits:", "",
           table_md(c("Term", "Truth", "Mean", "MC SE", "Bias", "Role", "Fits at boundary"), sd_rows),
           "",
           sprintf("Not-pdHess fits: %d of %d.", sum(!s$fits$pdhess, na.rm = TRUE), s$n), "")
  fx_rows <- lapply(fixed, function(p) {
    r <- st[p, ]
    c(sub(":text$", "", sub("^(logit|penalty):", "", p)), sub(":.*", "", p), f2(r$truth),
      f2(r$mean), f2(r$se),
      sprintf("%+.3f", r$mean - r$truth))
  })
  out <- c(out, "Gated fixed-effect quantities (text cell logit and size-averaged penalty):", "",
           table_md(c("Model", "Quantity", "Truth", "Mean", "MC SE", "Bias"), fx_rows), "")
  other <- setdiff(grep("^logit:", rownames(st), value = TRUE), fixed)
  ot_rows <- lapply(other, function(p) {
    r <- st[p, ]
    parts <- strsplit(sub("^logit:", "", p), ":")[[1]]
    c(parts[1], parts[2], f2(r$truth), f2(r$mean), f2(r$se), sprintf("%+.3f", r$mean - r$truth))
  })
  out <- c(out, "Other cell logits (reported, not gated):", "",
           table_md(c("Model", "Condition", "Truth", "Mean", "MC SE", "Bias"), ot_rows), "")
  if (scenario == "plausible") out <- c(out, lme4_section(sim, notes), "")
  list(lines = out, pass = c(c1, c2, c3))
}

lme4_section <- function(sim, notes) {
  reps <- sim[sim$engine == "lme4", ]
  if (nrow(reps) == 0) return("lme4 cross-check: not run.")
  gated <- c(paste0("sd:", TERMS), paste0("logit:", MODELS, ":text"), paste0("penalty:", MODELS))
  rows <- lapply(unique(reps$rep), function(r) {
    a <- sim[sim$engine == "glmmTMB" & sim$rep == r & sim$parameter %in% gated, ]
    l <- sim[sim$engine == "lme4" & sim$rep == r & sim$parameter %in% gated, ]
    diff <- abs(a$estimate - l$estimate[match(a$parameter, l$parameter)])
    worst <- a$parameter[which.max(diff)]
    over <- a$parameter[!is.na(diff) & diff > LME4_TOL]
    n <- notes[notes$rep == r, ]
    n$error[is.na(n$error)] <- ""
    n$warnings[is.na(n$warnings)] <- ""
    c(r, if (all(is.na(l$estimate))) "no estimates" else sprintf("%.3f (%s)", max(diff, na.rm = TRUE), worst),
      length(over), if (length(over)) paste(over, collapse = ", ") else "none",
      if (nrow(n) && nzchar(n$error)) paste("error:", n$error) else "none",
      if (nrow(n) && nzchar(n$warnings)) n$warnings else "none")
  })
  c(sprintf("lme4 (glmer, nAGQ = 1) against glmmTMB on the same replications; agreement tolerance %.2f:", LME4_TOL), "",
    table_md(c("Rep", "Largest gap", "Gaps over tolerance", "Which", "lme4 error", "lme4 warnings"), rows))
}

time_section <- function(sims) {
  rows <- unlist(lapply(names(sims), function(sc) {
    unlist(lapply(names(sims[[sc]]), function(b) {
      s <- sims[[sc]][[b]]
      s <- s[s$rep != "block1" & s$parameter == "sd:item", ]
      lapply(unique(s$engine), function(e) {
        x <- s$seconds[s$engine == e]
        c(sc, TITLES[[b]], e, length(x), sprintf("%.0f", median(x)), sprintf("%.0f", max(x)))
      })
    }), recursive = FALSE)
  }), recursive = FALSE)
  c("## Time and memory", "",
    "Apple M4, 10 cores, 24 GB. Wall seconds per fit, measured inside the script, with 6 fits running at once (the 2 lme4 fits per benchmark ran in the same worker pool, so they shared the machine too):", "",
    table_md(c("Scenario", "Benchmark", "Engine", "Fits", "Median s", "Max s"), rows), "")
}

block1_section <- function(sims) {
  out <- c("## Block-1 fit", "",
           "The same model on the real block-1 cells (3 runs each), glmmTMB. Only the standard deviations and the level counts are kept; fixed effects are not written. Block 1 covers 56 of 79 DevEval repositories and 10 of 14 CoderUJB projects, so the CoderUJB project terms are indicative only. The truth column is the simulated value, not an estimate.", "")
  for (b in names(sims)) {
    s <- sims[[b]][sims[[b]]$rep == "block1", ]
    if (nrow(s) == 0) next
    sd <- s[grepl("^sd:", s$parameter), ]
    lv <- s[grepl("^levels:", s$parameter), ]
    rows <- lapply(TERMS, function(t) {
      c(t, f2(sd$truth[sd$parameter == paste0("sd:", t)]),
        f2(sd$estimate[sd$parameter == paste0("sd:", t)]),
        lv$estimate[lv$parameter == paste0("levels:", t)])
    })
    out <- c(out, sprintf("%s: converged %s, pdHess %s, %.0f s.", TITLES[[b]],
                          if (sd$converged[1]) "yes" else "no", if (isTRUE(sd$pdhess[1])) "yes" else "no",
                          sd$seconds[1]), "",
             table_md(c("Term", "Simulated truth", "Block-1 estimate", "Levels"), rows), "")
  }
  out
}

memory_section <- function() {
  if (!nzchar(rss)) return(character())
  rows <- lapply(strsplit(strsplit(rss, ",")[[1]], "[/=]"), function(x) {
    c(x[1], TITLES[[x[2]]], x[3], x[4])
  })
  c("One replication with one worker under `/usr/bin/time -l` (maximum resident set size). The plausible runs also include the lme4 refit of that replication, the block1 runs are glmmTMB only:", "",
    table_md(c("Scenario", "Benchmark", "Peak MB", "Wall s"), rows), "")
}

write_report <- function(sims, notes) {
  plaus <- sims$plausible
  n_reps <- function(set) sum(set[[1]]$engine == "glmmTMB" & set[[1]]$parameter == "sd:item" &
                                set[[1]]$rep != "block1")
  head <- c("# GLMM check on simulated data", "",
            "The methodology 3.3 model, fitted with glmmTMB (family binomial, Laplace) to data simulated with the real design and known components, to see whether it recovers them. Package versions are pinned in `analysis/conda-osx-arm64.lock`. Run: `analysis/glmm_check.R`, inputs from `scripts/glmm_cells.py`.", "",
            sprintf("Replications per benchmark and scenario: %d, seeds %d + r.", n_reps(plaus), SEED),
            "Design: every in-range item (859 DevEval, 136 CoderUJB) x 5 models x 4 conditions; 3 runs per cell for block-1 items and 2 for the rest (17,180 and 2,720 cells).",
            "Truth: cell logits are the block-1 pooled pass rates on the logit scale rounded to 0.1. Two scenarios differ only in the standard deviations: the plausible values (item 1.5, item:model 0.8, item:condition 0.5, project 0.5, project:condition 0.3, cell 0.5, not estimates) and the block-1 estimates.",
            "The convergence gate is a rough screen. The cell standard deviation is reported but not gated: with only 2 or 3 runs per cell the Laplace approximation is known to estimate it low, so a shortfall there is expected.",
            "")
  body <- "## Scenario 1: plausible standard deviations"
  body <- c(body, "")
  pass <- logical()
  for (b in names(plaus)) {
    r <- report_bench(b, plaus[[b]], notes[[b]], "plausible")
    body <- c(body, r$lines)
    pass <- c(pass, r$pass)
  }
  if (length(sims$block1)) {
    body <- c(body, "## Scenario 2: block-1 standard deviations", "",
              "The block-1 item standard deviations (4.0 and 4.8) are about three times the plausible 1.5, so the same design was simulated again with the standard deviations of the block-1 fit (rounded to 0.1, see the Block-1 fit section) as the truth. Same gates and thresholds. The standard deviations gated are those with a nonzero truth among item, item:model and item:condition, plus project:condition on DevEval; terms with a truth of 0 are reported as an absolute mean. glmmTMB only, no lme4 refits.", "")
    for (b in names(sims$block1)) {
      r <- report_bench(b, sims$block1[[b]], NULL, "block1")
      body <- c(body, r$lines)
      pass <- c(pass, r$pass)
    }
  }
  txt <- c(head, body, time_section(sims), memory_section(), block1_section(plaus))
  writeLines(txt, file.path(out_dir, "glmm.md"))
  pass
}

read_sim <- function(b, sc) {
  f <- file.path(out_dir, sprintf("sim_%s_%s.csv", b, sc))
  if (file.exists(f)) read.csv(f, stringsAsFactors = FALSE, colClasses = c(rep = "character"))
}

dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
for (b in if (reps > 0) benches else character()) {
  r <- run_bench(b, truth_sd(b, scenario))
  sim <- r$rows
  if (do_block1) sim <- rbind(sim, run_block1(b))
  sim$rep <- as.character(sim$rep)
  write.csv(sim, file.path(out_dir, sprintf("sim_%s_%s.csv", b, scenario)), row.names = FALSE)
  if (scenario == "plausible") {
    write.csv(r$lme4_notes, file.path(out_dir, paste0("lme4_notes_", b, ".csv")), row.names = FALSE)
  }
}
sims <- lapply(setNames(SCENARIOS, SCENARIOS), function(sc) {
  Filter(Negate(is.null), setNames(lapply(c("coderujb", "deveval"), read_sim, sc = sc),
                                   c("coderujb", "deveval")))
})
notes <- lapply(setNames(names(sims$plausible), names(sims$plausible)), function(b) {
  read.csv(file.path(out_dir, paste0("lme4_notes_", b, ".csv")), stringsAsFactors = FALSE,
           colClasses = c(rep = "character", error = "character", warnings = "character"))
})
pass <- write_report(sims, notes)
cat(sprintf("checks passed: %d of %d\n", sum(pass), length(pass)))
