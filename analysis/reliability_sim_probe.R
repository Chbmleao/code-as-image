# Looks into the sim_check miss of analysis/reliability.R (s2_model_project outside its interval)
# with the same simulated design: CoderUJB text, components SIM_TRUTH of reliability.R.
#
#   OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 mamba run -n codeimg-glmm Rscript \
#     analysis/reliability_sim_probe.R original|decomp|reml|mcmc
#
# original  rebuilds the sim_check dataset (same seed and draw order) and fits it by REML
# decomp    per project, the realized model:item means per model against their expected size, and
#           REML without the 1-item projects and on projects with 5 or more items
# reml      500 new datasets fitted by REML: mean, median and SD of each component
# mcmc      20 new datasets fitted by MCMCglmm with the main prior at base length: coverage
# Reads scratch/reliability/coderujb_answers.csv (scripts/reliability.py prep); prints only.
suppressPackageStartupMessages({
  library(lme4)
  library(MCMCglmm)
  library(parallel)
})

script_dir <- dirname(normalizePath(sub("^--file=", "", grep("^--file=", commandArgs(), value = TRUE))))
root <- dirname(script_dir)
mode <- commandArgs(trailingOnly = TRUE)[1]
stopifnot(mode %in% c("original", "decomp", "reml", "mcmc"))

SEED <- 20261114
TRUTH <- c(s2_model = 0.01, s2_project = 0.005, s2_item = 0.06, s2_model_project = 0.005,
           s2_model_item = 0.03, s2_run = 0.05)
REML_NAMES <- c(model = "s2_model", project = "s2_project", item = "s2_item",
                mp = "s2_model_project", mi = "s2_model_item", Residual = "s2_run")

base <- read.csv(file.path(root, "scratch/reliability/coderujb_answers.csv"),
                 stringsAsFactors = FALSE)
base$model <- factor(base$model)
base$project <- factor(base$project)
base$item <- factor(base$item)
base$mp <- interaction(base$model, base$project, drop = TRUE)
base$mi <- interaction(base$model, base$item, drop = TRUE)
base <- base[base$condition == "text", ]

# Same draw order as sim_check in reliability.R, so set.seed(SEED) gives its dataset.
simulate <- function(d) {
  draw <- function(f, s2) {
    e <- rnorm(nlevels(f), 0, sqrt(s2))
    list(e = e, x = e[as.integer(f)])
  }
  m <- draw(d$model, TRUTH[["s2_model"]])
  p <- draw(d$project, TRUTH[["s2_project"]])
  i <- draw(d$item, TRUTH[["s2_item"]])
  mp <- draw(d$mp, TRUTH[["s2_model_project"]])
  mi <- draw(d$mi, TRUTH[["s2_model_item"]])
  d$y <- 0.4 + m$x + p$x + i$x + mp$x + mi$x + rnorm(nrow(d), 0, sqrt(TRUTH[["s2_run"]]))
  attr(d, "mp_eff") <- mp$e
  attr(d, "mi_eff") <- mi$e
  d
}

reml <- function(d) {
  f <- lmer(y ~ 1 + (1 | model) + (1 | project) + (1 | item) + (1 | mp) + (1 | mi), data = d,
            control = lmerControl(calc.derivs = FALSE))
  v <- as.data.frame(VarCorr(f))
  setNames(v$vcov, REML_NAMES[v$grp])[names(TRUTH)]
}

if (mode == "original") {
  set.seed(SEED)
  d <- simulate(base)
  cat("realized variance of the model:project effects:", round(var(attr(d, "mp_eff")), 5), "\n")
  print(round(reml(d), 5))
} else if (mode == "decomp") {
  set.seed(SEED)
  d <- simulate(base)
  cells <- unique(d[, c("model", "project", "item", "mp", "mi")])
  cells$mi_e <- attr(d, "mi_eff")[as.integer(cells$mi)]
  by <- aggregate(mi_e ~ model + project + mp, cells, mean)
  n_p <- tapply(cells$item, cells$project, function(x) length(unique(x)))
  by$n <- n_p[as.character(by$project)]
  by$mp_e <- attr(d, "mp_eff")[as.integer(by$mp)]
  # ratio 1 is the expected size: s2_model_item / n_P for a mean over n_P items
  z <- aggregate(cbind(r_mi = mi_e^2 / (TRUTH[["s2_model_item"]] / n),
                       r_mp = mp_e^2 / TRUTH[["s2_model_project"]]) ~ project + n, by, mean)
  print(z[order(z$n), ], digits = 3, row.names = FALSE)
  cat("REML without the 1-item projects:\n")
  print(round(reml(droplevels(d[d$project %in% names(n_p)[n_p > 1], ])), 5))
  cat("REML on projects with 5 or more items:\n")
  print(round(reml(droplevels(d[d$project %in% names(n_p)[n_p >= 5], ])), 5))
} else if (mode == "reml") {
  set.seed(SEED + 1)
  est <- t(replicate(500, reml(simulate(base))))
  for (k in names(TRUTH)) {
    cat(sprintf("%-17s truth %.4f mean %.5f median %.5f sd %.5f\n", k, TRUTH[[k]],
                mean(est[, k]), median(est[, k]), sd(est[, k])))
  }
  cat("share with s2_model_project >= 0.0112:", mean(est[, "s2_model_project"] >= 0.0112), "\n")
} else {
  px <- list(V = 1, nu = 1, alpha.mu = 0, alpha.V = 0.25)
  ig <- list(V = 1, nu = 0.002)
  prior <- list(R = ig, G = setNames(rep(list(px), 5), paste0("G", 1:5)))
  res <- mclapply(1:20, function(r) {
    set.seed(SEED + 100 + r)
    m <- MCMCglmm(y ~ 1, random = ~ model + project + item + mp + mi, data = simulate(base),
                  prior = prior, nitt = 60000, burnin = 10000, thin = 25, verbose = FALSE)
    q <- apply(as.matrix(m$VCV)[, c("model", "project", "item", "mp", "mi", "units")], 2,
               quantile, c(0.025, 0.5, 0.975), type = 1)
    colnames(q) <- names(TRUTH)
    q
  }, mc.cores = 6, mc.preschedule = FALSE)
  for (k in names(TRUTH)) {
    lo <- sapply(res, function(q) q[1, k])
    md <- sapply(res, function(q) q[2, k])
    hi <- sapply(res, function(q) q[3, k])
    cat(sprintf("%-17s truth %.4f covered %2d/20 median of medians %.5f\n", k, TRUTH[[k]],
                sum(lo <= TRUTH[[k]] & TRUTH[[k]] <= hi), median(md)))
  }
}
