# Fits the methodology 3.3 reliability components with MCMCglmm on the 0/1 pass of every run, per
# benchmark and condition. Inputs come from scripts/reliability.py prep
# (scratch/reliability/<bench>_answers.csv); scripts/reliability.py report reads the outputs.
#
#   OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 mamba run -n codeimg-glmm Rscript \
#     analysis/reliability.R [--bench coderujb|deveval] [--prior main|ig] [--workers 6] [--sim]
#     [--in scratch/reliability] [--out results/reliability]
#
# Writes <in>/draws_<bench>.csv (every kept draw of the 6 variance components and the 5 model
# effects, per condition, prior and chain) and merges the gate of each fit into
# <out>/mcmc_diagnostics.csv. --sim fits one simulated dataset with the CoderUJB design instead and
# writes <out>/sim_check.csv. Versions are in analysis/conda-osx-arm64.lock.
suppressPackageStartupMessages({
  library(MCMCglmm)
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

BENCHES <- c("coderujb", "deveval")
PRIORS <- c("main", "ig")
benches <- if (is.na(match("--bench", args))) BENCHES else opt("bench", NULL)
priors <- if (is.na(match("--prior", args))) PRIORS else opt("prior", NULL)
stopifnot(all(benches %in% BENCHES), all(priors %in% PRIORS))
workers <- as.integer(opt("workers", 6))
do_sim <- "--sim" %in% args
in_dir <- path(opt("in", "scratch/reliability"))
out_dir <- path(opt("out", "results/reliability"))

SEED <- 20261114
CONDS <- c("text", "image10", "image12", "image14")
# VCV column of each term -> the name the report uses
TERMS <- c(model = "s2_model", project = "s2_project", item = "s2_item", mp = "s2_model_project",
           mi = "s2_model_item", units = "s2_run")
NITT <- 60000
BURNIN <- 10000
THIN <- 25
CHAINS <- 2
MAX_PSRF <- 1.05
MIN_ESS <- 400
RERUN_SCALE <- 3

# Half-Cauchy on each SD with scale 0.5, the largest SD a 0/1 score can have (alpha.V = 0.5^2).
px <- list(V = 1, nu = 1, alpha.mu = 0, alpha.V = 0.25)
ig <- list(V = 1, nu = 0.002)
make_prior <- function(name) {
  g <- if (name == "main") px else ig
  list(R = ig, G = setNames(rep(list(g), 5), paste0("G", 1:5)))
}

prepare <- function(d) {
  d$model <- factor(d$model)
  d$project <- factor(d$project)
  d$item <- factor(d$item)
  d$mp <- interaction(d$model, d$project, drop = TRUE)
  d$mi <- interaction(d$model, d$item, drop = TRUE)
  d
}

fit_chain <- function(d, prior, seed, scale) {
  set.seed(seed)
  t0 <- Sys.time()
  m <- MCMCglmm(y ~ 1, random = ~ model + project + item + mp + mi, data = d,
                prior = make_prior(prior), nitt = NITT * scale, burnin = BURNIN * scale,
                thin = THIN * scale, pr = TRUE, verbose = FALSE)
  vcv <- as.matrix(m$VCV)[, names(TERMS), drop = FALSE]
  colnames(vcv) <- TERMS
  eff <- as.matrix(m$Sol)[, grep("^model\\.", colnames(m$Sol)), drop = FALSE]
  stopifnot(ncol(eff) == nlevels(d$model))
  colnames(eff) <- paste0("a", seq_len(ncol(eff)))
  list(vcv = vcv, eff = eff, seconds = as.numeric(difftime(Sys.time(), t0, units = "secs")))
}

gate <- function(chains) {
  vcv <- lapply(chains, function(ch) coda::mcmc(ch$vcv))
  psrf <- coda::gelman.diag(coda::mcmc.list(vcv), autoburnin = FALSE,
                            multivariate = FALSE)$psrf[, 1]
  ess <- coda::effectiveSize(coda::mcmc.list(vcv))
  data.frame(component = TERMS, psrf = round(psrf[TERMS], 4), ess = round(ess[TERMS]),
             stringsAsFactors = FALSE)
}

# One job per fit and chain; fits that miss the gate run again once with every length tripled.
run_fits <- function(fits, data) {
  run <- function(fits, scale) {
    jobs <- do.call(rbind, lapply(seq_len(nrow(fits)), function(f)
      data.frame(fit = f, chain = seq_len(CHAINS))))
    out <- mclapply(seq_len(nrow(jobs)), function(j) {
      f <- fits[jobs$fit[j], ]
      fit_chain(data[[f$key]], f$prior, f$seed + jobs$chain[j] - 1, scale)
    }, mc.cores = workers, mc.preschedule = FALSE)
    bad <- vapply(out, inherits, logical(1), "try-error")
    if (any(bad)) stop(paste(unique(unlist(out[bad])), collapse = "\n"))
    lapply(seq_len(nrow(fits)), function(f) out[jobs$fit == f])
  }
  chains <- run(fits, 1)
  scale <- rep(1, nrow(fits))
  passes <- function(g) all(g$psrf <= MAX_PSRF & g$ess >= MIN_ESS)
  gates <- lapply(chains, gate)
  redo <- which(!vapply(gates, passes, logical(1)))
  if (length(redo)) {
    cat(sprintf("rerunning %d fit(s) at %dx: %s\n", length(redo), RERUN_SCALE,
                paste(fits$key[redo], fits$prior[redo], collapse = ", ")))
    again <- run(fits[redo, , drop = FALSE], RERUN_SCALE)
    chains[redo] <- again
    gates[redo] <- lapply(again, gate)
    scale[redo] <- RERUN_SCALE
  }
  list(chains = chains, gates = gates, scale = scale, passes = vapply(gates, passes, logical(1)))
}

draws_frame <- function(fit, chains) {
  do.call(rbind, lapply(seq_along(chains), function(k) {
    ch <- chains[[k]]
    data.frame(benchmark = fit$bench, condition = fit$condition, prior = fit$prior, chain = k,
               draw = seq_len(nrow(ch$vcv)), signif(ch$vcv, 8), signif(ch$eff, 8),
               check.names = FALSE)
  }))
}

diag_frame <- function(fit, g, scale, chains, ok) {
  data.frame(benchmark = fit$bench, condition = fit$condition, prior = fit$prior, g,
             nitt = NITT * scale, seconds = round(max(vapply(chains, `[[`, 0, "seconds")), 1),
             gate = ifelse(ok, "pass", "fail"), row.names = NULL)
}

merge_diagnostics <- function(new) {
  f <- file.path(out_dir, "mcmc_diagnostics.csv")
  old <- if (file.exists(f)) read.csv(f, stringsAsFactors = FALSE) else new[0, ]
  key <- function(d) paste(d$benchmark, d$condition, d$prior)
  all <- rbind(old[!key(old) %in% key(new), ], new)
  all <- all[order(match(all$benchmark, BENCHES), match(all$condition, CONDS),
                   match(all$prior, PRIORS), match(all$component, TERMS)), ]
  write.csv(all, f, row.names = FALSE)
}

read_answers <- function(b) {
  d <- read.csv(file.path(in_dir, paste0(b, "_answers.csv")), stringsAsFactors = FALSE)
  d$y <- as.numeric(d$passed)
  d
}

main_fits <- function() {
  data <- list()
  fits <- data.frame()
  for (bi in seq_along(BENCHES)) {
    b <- BENCHES[bi]
    if (!b %in% benches) next
    d <- read_answers(b)
    for (ci in seq_along(CONDS)) {
      key <- paste(b, CONDS[ci])
      data[[key]] <- prepare(d[d$condition == CONDS[ci], ])
      for (pi in seq_along(PRIORS)) {
        if (!PRIORS[pi] %in% priors) next
        fits <- rbind(fits, data.frame(key = key, bench = b, condition = CONDS[ci],
                                       prior = PRIORS[pi],
                                       seed = SEED + 1000 * bi + 100 * ci + 10 * pi,
                                       stringsAsFactors = FALSE))
      }
    }
  }
  res <- run_fits(fits, data)
  for (b in unique(fits$bench)) {
    s <- which(fits$bench == b)
    new <- do.call(rbind, lapply(s, function(f) draws_frame(fits[f, ], res$chains[[f]])))
    f <- file.path(in_dir, paste0("draws_", b, ".csv"))
    old <- if (file.exists(f)) read.csv(f, stringsAsFactors = FALSE, check.names = FALSE) else new[0, ]
    old <- old[!paste(old$condition, old$prior) %in% paste(new$condition, new$prior), ]
    write.csv(rbind(old, new), f, row.names = FALSE)
    cat(sprintf("%s: %d draws\n", f, nrow(new)))
  }
  merge_diagnostics(do.call(rbind, lapply(seq_len(nrow(fits)), function(f)
    diag_frame(fits[f, ], res$gates[[f]], res$scale[f], res$chains[[f]], res$passes[f]))))
  for (f in seq_len(nrow(fits))) {
    cat(sprintf("%s %s: gate %s, max PSRF %.3f, min ESS %d, %.0f s\n", fits$key[f], fits$prior[f],
                if (res$passes[f]) "pass" else "FAIL", max(res$gates[[f]]$psrf),
                as.integer(min(res$gates[[f]]$ess)),
                max(vapply(res$chains[[f]], `[[`, 0, "seconds"))))
  }
}

# Known components near the block-1 scale, continuous normal response: checks the sampler and that
# each VCV column carries the right name, not how a Gaussian model behaves on 0/1 data.
SIM_TRUTH <- c(s2_model = 0.01, s2_project = 0.005, s2_item = 0.06, s2_model_project = 0.005,
               s2_model_item = 0.03, s2_run = 0.05)
SIM_MU <- 0.4

sim_check <- function() {
  set.seed(SEED)
  d <- prepare(read_answers("coderujb"))
  d <- d[d$condition == "text", ]
  draw <- function(f, s2) rnorm(nlevels(f), 0, sqrt(s2))[as.integer(f)]
  d$y <- SIM_MU + draw(d$model, SIM_TRUTH[["s2_model"]]) +
    draw(d$project, SIM_TRUTH[["s2_project"]]) + draw(d$item, SIM_TRUTH[["s2_item"]]) +
    draw(d$mp, SIM_TRUTH[["s2_model_project"]]) + draw(d$mi, SIM_TRUTH[["s2_model_item"]]) +
    rnorm(nrow(d), 0, sqrt(SIM_TRUTH[["s2_run"]]))
  fits <- data.frame(key = "sim", bench = "coderujb", condition = "sim", prior = priors[1],
                     seed = SEED, stringsAsFactors = FALSE)
  res <- run_fits(fits, list(sim = d))
  v <- do.call(rbind, lapply(res$chains[[1]], `[[`, "vcv"))
  q <- function(x, p) unname(quantile(x, p, type = 1))
  out <- data.frame(component = TERMS, truth = SIM_TRUTH[TERMS],
                    median = signif(apply(v, 2, q, 0.5)[TERMS], 4),
                    lo = signif(apply(v, 2, q, 0.025)[TERMS], 4),
                    hi = signif(apply(v, 2, q, 0.975)[TERMS], 4), row.names = NULL)
  out$covered <- out$lo <= out$truth & out$truth <= out$hi
  out <- merge(out, res$gates[[1]], by = "component", sort = FALSE)
  out$gate <- ifelse(res$passes[1], "pass", "fail")
  out$seconds <- round(max(vapply(res$chains[[1]], `[[`, 0, "seconds")), 1)
  write.csv(out, file.path(out_dir, "sim_check.csv"), row.names = FALSE)
  print(out)
}

dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)
if (do_sim) sim_check() else main_fits()
